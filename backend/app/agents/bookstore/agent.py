import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentMessage, AgentResponse, BaseAgent
from app.agents.registry import AgentRegistry
from app.agents.bookstore.prompts import INTENT_PARSE_SYSTEM, RECOMMEND_SYSTEM
from app.integrations.anthropic_client import parse_intent, generate_response
from app.models.bookstore import Book, InventoryLog


@AgentRegistry.register
class BookstoreAgent(BaseAgent):
    agent_type = "bookstore"

    def get_default_config(self) -> dict:
        return {"welcome_message": "Добро пожаловать в книжный магазин! Спросите о наличии книг или попросите рекомендацию."}

    def get_roles(self) -> list[str]:
        return ["admin", "manager", "user"]

    async def handle_message(self, message: AgentMessage, db: AsyncSession) -> AgentResponse:
        intent_data = await parse_intent(
            INTENT_PARSE_SYSTEM.format(role=message.role, text=message.text)
        )

        intent = intent_data.get("intent", "unknown")
        params = intent_data.get("params", {})

        match intent:
            case "greeting":
                return AgentResponse(
                    text=message.agent_config.get(
                        "welcome_message",
                        "Привет! Я бот книжного магазина. Спросите о книгах или попросите рекомендацию.",
                    ),
                    intent=intent,
                )
            case "help":
                return AgentResponse(text=self._help_text(message.role), intent=intent)
            case "search_books" | "check_inventory":
                return await self._handle_search(params, message, db)
            case "add_books":
                if message.role not in ("admin", "manager"):
                    return AgentResponse(text="У вас нет прав для добавления книг.", intent=intent)
                return await self._handle_add(params, message, db)
            case "sell_book":
                if message.role not in ("admin", "manager"):
                    return AgentResponse(text="У вас нет прав для продажи книг.", intent=intent)
                return await self._handle_sell(params, message, db)
            case "recommend":
                return await self._handle_recommend(params, message, db)
            case "list_genres":
                return await self._handle_list_genres(message, db)
            case _:
                return AgentResponse(
                    text="Не совсем понял запрос. Попробуйте спросить о наличии книг, попросить рекомендацию или написать /help.",
                    intent="unknown",
                )

    async def _handle_search(self, params: dict, message: AgentMessage, db: AsyncSession) -> AgentResponse:
        query = select(Book).where(Book.agent_id == message.agent_id, Book.quantity > 0)

        if title := params.get("query") or params.get("title"):
            query = query.where(Book.title.ilike(f"%{title}%"))
        if author := params.get("author"):
            query = query.where(Book.author.ilike(f"%{author}%"))
        if genre := params.get("genre"):
            query = query.where(Book.genre.ilike(f"%{genre}%"))

        result = await db.execute(query.limit(20))
        books = result.scalars().all()

        if not books:
            return AgentResponse(text="К сожалению, ничего не найдено.", intent="search_books", intent_data=params)

        lines = ["Найденные книги:\n"]
        for b in books:
            price_str = f", {b.price} руб." if b.price else ""
            lines.append(f"📚 {b.title} — {b.author or 'Автор неизвестен'} (кол-во: {b.quantity}{price_str})")

        return AgentResponse(text="\n".join(lines), intent="search_books", intent_data=params)

    async def _handle_add(self, params: dict, message: AgentMessage, db: AsyncSession) -> AgentResponse:
        title = params.get("title", "").strip()
        if not title:
            return AgentResponse(text="Укажите название книги.", intent="add_books")

        quantity = int(params.get("quantity", 1))
        author = params.get("author")
        price = params.get("price")

        result = await db.execute(
            select(Book).where(Book.agent_id == message.agent_id, Book.title.ilike(f"%{title}%"))
        )
        book = result.scalar_one_or_none()

        if book:
            book.quantity += quantity
        else:
            book = Book(
                agent_id=message.agent_id,
                title=title,
                author=author,
                quantity=quantity,
                price=price,
            )
            db.add(book)
            await db.flush()

        log = InventoryLog(
            book_id=book.id,
            agent_id=message.agent_id,
            change_type="arrival",
            quantity_change=quantity,
            note=f"Добавлено через Telegram",
            performed_by=message.telegram_id,
        )
        db.add(log)
        await db.commit()

        return AgentResponse(
            text=f"Добавлено: {title} — {quantity} шт. (всего на складе: {book.quantity})",
            intent="add_books",
            intent_data=params,
        )

    async def _handle_sell(self, params: dict, message: AgentMessage, db: AsyncSession) -> AgentResponse:
        title = params.get("title", "").strip()
        if not title:
            return AgentResponse(text="Укажите название книги.", intent="sell_book")

        quantity = int(params.get("quantity", 1))

        result = await db.execute(
            select(Book).where(Book.agent_id == message.agent_id, Book.title.ilike(f"%{title}%"))
        )
        book = result.scalar_one_or_none()

        if not book:
            return AgentResponse(text=f"Книга «{title}» не найдена.", intent="sell_book")

        if book.quantity < quantity:
            return AgentResponse(
                text=f"Недостаточно книг «{book.title}». На складе: {book.quantity} шт.",
                intent="sell_book",
            )

        book.quantity -= quantity
        log = InventoryLog(
            book_id=book.id,
            agent_id=message.agent_id,
            change_type="sale",
            quantity_change=-quantity,
            note="Продажа через Telegram",
            performed_by=message.telegram_id,
        )
        db.add(log)
        await db.commit()

        return AgentResponse(
            text=f"Продано: {book.title} — {quantity} шт. (осталось: {book.quantity})",
            intent="sell_book",
            intent_data=params,
        )

    async def _handle_recommend(self, params: dict, message: AgentMessage, db: AsyncSession) -> AgentResponse:
        query = select(Book).where(Book.agent_id == message.agent_id, Book.quantity > 0)
        if genre := params.get("genre"):
            query = query.where(Book.genre.ilike(f"%{genre}%"))

        result = await db.execute(query.limit(50))
        books = result.scalars().all()

        if not books:
            return AgentResponse(text="Пока нет доступных книг для рекомендации.", intent="recommend")

        books_text = "\n".join(
            f"- {b.title} ({b.author or '?'}) — жанр: {b.genre or '?'}, кол-во: {b.quantity}"
            for b in books
        )
        preferences = params.get("preferences") or params.get("genre") or message.text

        response_text = await generate_response(
            RECOMMEND_SYSTEM.format(books=books_text, preferences=preferences)
        )

        return AgentResponse(text=response_text, intent="recommend", intent_data=params)

    async def _handle_list_genres(self, message: AgentMessage, db: AsyncSession) -> AgentResponse:
        from sqlalchemy import distinct

        result = await db.execute(
            select(distinct(Book.genre)).where(Book.agent_id == message.agent_id, Book.genre.isnot(None))
        )
        genres = [r[0] for r in result.all()]

        if not genres:
            return AgentResponse(text="Пока нет книг с указанными жанрами.", intent="list_genres")

        return AgentResponse(
            text="Доступные жанры:\n" + "\n".join(f"• {g}" for g in sorted(genres)),
            intent="list_genres",
        )

    def _help_text(self, role: str) -> str:
        base = (
            "Я бот книжного магазина. Вот что я умею:\n\n"
            "📖 Поиск книг — спросите «какие книги есть?» или «есть книги по фантастике?»\n"
            "💡 Рекомендации — «посоветуй что почитать» или «посоветуй детектив»\n"
            "📋 Жанры — «какие жанры есть?»\n"
        )
        if role in ("admin", "manager"):
            base += (
                "\n🔧 Управление (для администраторов):\n"
                "➕ Добавить — «приехало 5 книг Война и Мир»\n"
                "➖ Продажа — «продана книга Мастер и Маргарита»\n"
            )
        return base
