import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentMessage, AgentResponse, BaseAgent
from app.agents.registry import AgentRegistry
from app.agents.bookstore.prompts import INTENT_PARSE_SYSTEM, RECOMMEND_SYSTEM
from app.agents.bookstore.book_lookup import verify_book_title
from app.integrations.anthropic_client import parse_intent, generate_response
from app.models.bookstore import Book, InventoryLog


@AgentRegistry.register
class BookstoreAgent(BaseAgent):
    agent_type = "bookstore"

    # user state: telegram_id -> awaiting action
    _user_state: dict[int, str] = {}

    def get_default_config(self) -> dict:
        return {"welcome_message": "Добро пожаловать в книжный магазин! Спросите о наличии книг или попросите рекомендацию."}

    def get_roles(self) -> list[str]:
        return ["admin", "manager", "user"]

    QUICK_BUTTONS = ["📚 Книги на продажу", "📦 Арендный шкаф", "🔍 Поиск книги"]

    async def handle_message(self, message: AgentMessage, db: AsyncSession) -> AgentResponse:
        # Quick button shortcuts — bypass LLM
        if message.text in ("📚 Книги на продажу", "📚 Список книг"):
            return await self._handle_search({"category": "sale"}, message, db)

        if message.text == "📦 Арендный шкаф":
            return await self._handle_search({"category": "rental"}, message, db)

        if message.text == "🔍 Поиск книги":
            self._user_state[message.telegram_id] = "search"
            return AgentResponse(
                text="Введите название книги или имя автора:",
                intent="search_prompt",
            )

        # Handle pending state
        state = self._user_state.pop(message.telegram_id, None)
        if state == "search":
            return await self._handle_search({"query": message.text}, message, db)

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
                    buttons=self.QUICK_BUTTONS,
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
            case "remove_book":
                if message.role not in ("admin", "manager"):
                    return AgentResponse(text="У вас нет прав для удаления книг.", intent=intent)
                return await self._handle_remove(params, message, db)
            case "edit_book":
                if message.role not in ("admin", "manager"):
                    return AgentResponse(text="У вас нет прав для редактирования книг.", intent=intent)
                return await self._handle_edit(params, message, db)
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
        from sqlalchemy import or_

        category = params.get("category")
        query = select(Book).where(Book.agent_id == message.agent_id, Book.quantity > 0)

        # Filter by category if specified
        if category:
            query = query.where(Book.category == category)

        if q := params.get("query") or params.get("title"):
            query = query.where(or_(Book.title.ilike(f"%{q}%"), Book.author.ilike(f"%{q}%")))
        if author := params.get("author"):
            query = query.where(Book.author.ilike(f"%{author}%"))
        if genre := params.get("genre"):
            query = query.where(Book.genre.ilike(f"%{genre}%"))

        result = await db.execute(query.limit(50))
        books = result.scalars().all()

        if not books:
            return AgentResponse(text="К сожалению, ничего не найдено.", intent="search_books", intent_data=params)

        # Group by genre -> author -> books
        from collections import defaultdict
        by_genre: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
        for b in books:
            genre_key = b.genre or ""
            author_key = b.author or "Автор неизвестен"
            by_genre[genre_key][author_key].append(b)

        category_label = "📦 Арендный шкаф" if category == "rental" else "📖 Книги на продажу" if category == "sale" else "📖 Найденные книги"
        lines = [f"{category_label}:\n"]
        for genre in sorted(by_genre.keys(), key=lambda g: (g == "", g)):
            if genre:
                lines.append(f"\n📂 {genre}:")
            elif by_genre.keys() - {""}:
                lines.append("\n📂 Без категории:")
            for author in sorted(by_genre[genre].keys()):
                lines.append(f"\n  ✍️ {author}:")
                for b in sorted(by_genre[genre][author], key=lambda x: x.title):
                    price_str = f" — {b.price} руб." if b.price else ""
                    lines.append(f"    📚 {b.title}{price_str}")

        return AgentResponse(text="\n".join(lines), intent="search_books", intent_data=params, buttons=self.QUICK_BUTTONS)

    async def _handle_add(self, params: dict, message: AgentMessage, db: AsyncSession) -> AgentResponse:
        category = params.get("category", "sale")

        # Support both new format (books array) and legacy (single title)
        books_list = params.get("books")
        if not books_list:
            title = params.get("title", "").strip()
            if not title:
                return AgentResponse(text="Укажите название книги.", intent="add_books")
            books_list = [{
                "title": title,
                "author": params.get("author"),
                "genre": params.get("genre"),
                "quantity": params.get("quantity", 1),
                "price": params.get("price"),
            }]

        added_lines = []
        verified_lines = []

        for item in books_list:
            title = (item.get("title") or "").strip()
            if not title:
                continue

            quantity = int(item.get("quantity") or 1)
            author = item.get("author")
            genre = item.get("genre")
            price = item.get("price")

            # Verify book title via OpenLibrary
            lookup = await verify_book_title(title, author)
            original_title = title
            if lookup:
                if lookup["title"] and lookup["title"].lower() != title.lower():
                    title = lookup["title"]
                    verified_lines.append(f"«{original_title}» → «{title}»")
                if lookup["author"] and not author:
                    author = lookup["author"]

            result = await db.execute(
                select(Book).where(
                    Book.agent_id == message.agent_id,
                    Book.category == category,
                    Book.title.ilike(f"%{title}%"),
                )
            )
            book = result.scalar_one_or_none()

            if book:
                book.quantity += quantity
                if author and not book.author:
                    book.author = author
                if genre and not book.genre:
                    book.genre = genre
            else:
                book = Book(
                    agent_id=message.agent_id,
                    category=category,
                    title=title,
                    author=author,
                    genre=genre,
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
                note="Добавлено через Telegram",
                performed_by=message.telegram_id,
            )
            db.add(log)

            author_str = f" — {book.author}" if book.author else ""
            added_lines.append(f"📚 {book.title}{author_str}: +{quantity} (всего: {book.quantity})")

        if not added_lines:
            return AgentResponse(text="Не удалось распознать книги. Укажите названия.", intent="add_books")

        await db.commit()

        category_label = "📦 Аренда" if category == "rental" else "🏪 Продажа"
        text_parts = [f"✅ Добавлено ({category_label}):\n" + "\n".join(added_lines)]
        if verified_lines:
            text_parts.append("\n🔍 Уточнены названия:\n" + "\n".join(verified_lines))

        return AgentResponse(
            text="\n".join(text_parts),
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

    async def _handle_remove(self, params: dict, message: AgentMessage, db: AsyncSession) -> AgentResponse:
        # Support both titles (array) and title (single string) for backwards compat
        titles = params.get("titles") or []
        if not titles:
            title = params.get("title", "").strip()
            if title:
                titles = [title]
        if not titles:
            return AgentResponse(text="Укажите название книги.", intent="remove_book")

        reason = params.get("reason", "удалено")
        removed = []
        not_found = []

        for t in titles:
            result = await db.execute(
                select(Book).where(Book.agent_id == message.agent_id, Book.title.ilike(f"%{t}%"))
            )
            book = result.scalar_one_or_none()
            if not book:
                not_found.append(t)
                continue

            log = InventoryLog(
                book_id=book.id,
                agent_id=message.agent_id,
                change_type="adjustment",
                quantity_change=-book.quantity,
                note=f"Списание: {reason}",
                performed_by=message.telegram_id,
            )
            db.add(log)
            removed.append(book.title)
            await db.delete(book)

        await db.commit()

        lines = []
        if removed:
            lines.append("Удалено: " + ", ".join(f"«{t}»" for t in removed))
        if not_found:
            lines.append("Не найдено: " + ", ".join(f"«{t}»" for t in not_found))

        return AgentResponse(
            text="\n".join(lines),
            intent="remove_book",
            intent_data=params,
        )

    async def _handle_edit(self, params: dict, message: AgentMessage, db: AsyncSession) -> AgentResponse:
        title = params.get("title", "").strip()
        if not title:
            return AgentResponse(text="Укажите название книги для редактирования.", intent="edit_book")

        result = await db.execute(
            select(Book).where(Book.agent_id == message.agent_id, Book.title.ilike(f"%{title}%"))
        )
        book = result.scalar_one_or_none()

        if not book:
            return AgentResponse(text=f"Книга «{title}» не найдена.", intent="edit_book")

        changes = []
        if new_title := params.get("new_title"):
            book.title = new_title
            changes.append(f"название → {new_title}")
        if new_author := params.get("new_author"):
            book.author = new_author
            changes.append(f"автор → {new_author}")
        if new_genre := params.get("new_genre"):
            book.genre = new_genre
            changes.append(f"жанр → {new_genre}")
        if (new_qty := params.get("new_quantity")) is not None:
            old_qty = book.quantity
            book.quantity = int(new_qty)
            changes.append(f"кол-во → {book.quantity} (было {old_qty})")
            log = InventoryLog(
                book_id=book.id,
                agent_id=message.agent_id,
                change_type="adjustment",
                quantity_change=book.quantity - old_qty,
                note="Корректировка через Telegram",
                performed_by=message.telegram_id,
            )
            db.add(log)
        if (new_price := params.get("new_price")) is not None:
            book.price = float(new_price)
            changes.append(f"цена → {book.price} руб.")

        if not changes:
            return AgentResponse(text="Не указаны поля для изменения.", intent="edit_book")

        await db.commit()

        return AgentResponse(
            text=f"Книга «{book.title}» обновлена:\n" + "\n".join(f"• {c}" for c in changes),
            intent="edit_book",
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
            f"- {b.title} ({b.author or '?'}) — жанр: {b.genre or '?'}"
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
            "📦 Арендный шкаф — «покажи арендные книги» или нажмите кнопку\n"
            "💡 Рекомендации — «посоветуй что почитать» или «посоветуй детектив»\n"
            "📋 Жанры — «какие жанры есть?»\n"
        )
        if role in ("admin", "manager"):
            base += (
                "\n🔧 Управление (для администраторов):\n"
                "➕ Добавить — «добавь книгу Война и Мир»\n"
                "📦 Аренда — «аренда добавь Мастер и Маргарита»\n"
                "➖ Продажа — «продана книга Мастер и Маргарита»\n"
                "✏️ Изменить — «измени автора книги Слон на Филипенко»\n"
                "🗑 Удалить — «удали книгу Маугли»\n"
            )
        return base
