import asyncio
import logging
import time

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentMessage
from app.agents.registry import AgentRegistry
from app.database import async_session
from app.models.agent import Agent
from app.models.agent_user import AgentUser
from app.models.message_log import MessageLog
from app.integrations.whisper_client import transcribe_voice

logger = logging.getLogger(__name__)


class TelegramBotManager:
    """Manages running Telegram bots via polling."""

    def __init__(self):
        self._bots: dict[int, Bot] = {}
        self._tasks: dict[int, asyncio.Task] = {}

    async def start_bot(self, agent_id: int, bot_token: str, agent_type: str):
        if agent_id in self._tasks:
            return

        bot = Bot(token=bot_token)
        dp = Dispatcher()
        self._bots[agent_id] = bot

        @dp.message(CommandStart())
        async def cmd_start(message: types.Message):
            await self._handle_message(agent_id, agent_type, message)

        @dp.message()
        async def handle_all(message: types.Message):
            await self._handle_message(agent_id, agent_type, message)

        task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))
        self._tasks[agent_id] = task
        logger.info(f"Bot started for agent {agent_id}")

    async def stop_bot(self, agent_id: int):
        if agent_id in self._tasks:
            self._tasks[agent_id].cancel()
            del self._tasks[agent_id]
        if agent_id in self._bots:
            await self._bots[agent_id].session.close()
            del self._bots[agent_id]
            logger.info(f"Bot stopped for agent {agent_id}")

    async def stop_all(self):
        for agent_id in list(self._tasks.keys()):
            await self.stop_bot(agent_id)

    async def _handle_message(self, agent_id: int, agent_type: str, message: types.Message):
        start_time = time.time()
        text = ""
        message_type = "text"

        if message.voice:
            message_type = "voice"
            try:
                bot = self._bots[agent_id]
                file = await bot.get_file(message.voice.file_id)
                file_bytes = await bot.download_file(file.file_path)
                text = await transcribe_voice(file_bytes.read())
            except Exception as e:
                logger.error(f"Voice transcription failed: {e}")
                await message.answer("Не удалось распознать голосовое сообщение. Попробуйте текстом.")
                return
        elif message.text:
            text = message.text
        else:
            await message.answer("Я понимаю только текстовые и голосовые сообщения.")
            return

        async with async_session() as db:
            # Get or create agent user
            agent_user = await self._get_or_create_user(db, agent_id, message.from_user)

            if agent_user.is_blocked:
                await message.answer("Вы заблокированы.")
                return

            # Get agent config
            result = await db.execute(select(Agent).where(Agent.id == agent_id))
            agent = result.scalar_one_or_none()
            config = agent.config if agent else {}

            # Process through agent
            try:
                agent_handler = AgentRegistry.get(agent_type)
                agent_msg = AgentMessage(
                    telegram_id=message.from_user.id,
                    chat_id=message.chat.id,
                    text=text,
                    role=agent_user.role,
                    agent_id=agent_id,
                    agent_config=config,
                )
                response = await agent_handler.handle_message(agent_msg, db)
            except Exception as e:
                logger.error(f"Agent handler error: {e}")
                response_text = "Произошла ошибка. Попробуйте позже."
                await message.answer(response_text)
                return

            processing_ms = int((time.time() - start_time) * 1000)

            # Log message
            log = MessageLog(
                agent_id=agent_id,
                telegram_id=message.from_user.id,
                direction="incoming",
                message_type=message_type,
                content_text=text,
                intent=response.intent,
                intent_data=response.intent_data,
                response_text=response.text,
                processing_ms=processing_ms,
            )
            db.add(log)
            await db.commit()

            await message.answer(response.text)

    async def _get_or_create_user(
        self, db: AsyncSession, agent_id: int, tg_user: types.User
    ) -> AgentUser:
        result = await db.execute(
            select(AgentUser).where(
                AgentUser.agent_id == agent_id,
                AgentUser.telegram_id == tg_user.id,
            )
        )
        agent_user = result.scalar_one_or_none()

        if not agent_user:
            agent_user = AgentUser(
                agent_id=agent_id,
                telegram_id=tg_user.id,
                telegram_username=tg_user.username,
                display_name=tg_user.full_name,
                role="user",
            )
            db.add(agent_user)
            await db.commit()
            await db.refresh(agent_user)

        return agent_user


bot_manager = TelegramBotManager()
