import asyncio
import logging
import os
import random
import re
from pathlib import Path
from urllib.parse import quote, urlparse

import aiosqlite
from aiohttp import web
from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup,
    MenuButtonWebApp, Message, WebAppInfo,
)
from aiogram.utils.web_app import safe_parse_webapp_init_data
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBAPP_URL = os.environ["WEBAPP_URL"].rstrip("/")   # фронтенд на GitHub Pages
API_URL = os.getenv("API_URL", "").rstrip("/")      # публичный HTTPS-адрес этого сервера
PORT = int(os.getenv("PORT", "8080"))

_u = urlparse(WEBAPP_URL)
PAGES_ORIGIN = f"{_u.scheme}://{_u.netloc}"         # нужен для CORS

BASE = Path(__file__).parent
CARDS_DIR = BASE / "docs" / "cards"                 # те же файлы публикуются на Pages
DB_PATH = BASE / "bot.db"

RARITY = {
    "common": "⚪ Обычная",
    "rare": "🔵 Редкая",
    "epic": "🟣 Эпическая",
    "legendary": "🟡 Легендарная",
}

# id, название, редкость, файл в docs/cards, вес выпадения
CARDS = [
    ("ash_fox", "Пепельный лис", "common", "ash_fox.png", 40),
    ("moon_owl", "Лунная сова", "common", "moon_owl.png", 40),
    ("crystal_golem", "Кристальный голем", "rare", "crystal_golem.png", 25),
    ("storm_dragon", "Штормовой дракон", "epic", "storm_dragon.png", 10),
    ("gold_phoenix", "Золотой феникс", "legendary", "gold_phoenix.png", 3),
]

router = Router()


# ---------- база данных ----------
async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS cards (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                rarity TEXT NOT NULL,
                image TEXT NOT NULL,
                weight INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS user_cards (
                user_id INTEGER NOT NULL,
                card_id TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 1,
                first_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, card_id)
            );
            """
        )
        await db.executemany(
            """INSERT INTO cards (id, name, rarity, image, weight) VALUES (?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET name=excluded.name, rarity=excluded.rarity,
               image=excluded.image, weight=excluded.weight""",
            CARDS,
        )
        await db.commit()


async def give_random_card(user_id: int, username: str | None):
    card = random.choices(CARDS, weights=[c[4] for c in CARDS])[0]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO users (id, username) VALUES (?,?)
               ON CONFLICT(id) DO UPDATE SET username=excluded.username""",
            (user_id, username),
        )
        await db.execute(
            """INSERT INTO user_cards (user_id, card_id) VALUES (?,?)
               ON CONFLICT(user_id, card_id) DO UPDATE SET count = count + 1""",
            (user_id, card[0]),
        )
        async with db.execute(
            "SELECT count FROM user_cards WHERE user_id=? AND card_id=?", (user_id, card[0])
        ) as cur:
            count = (await cur.fetchone())[0]
        await db.commit()
    return card, count


async def get_collection(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT c.id, c.name, c.rarity, c.image, COALESCE(uc.count, 0) AS count
               FROM cards c
               LEFT JOIN user_cards uc ON uc.card_id = c.id AND uc.user_id = ?
               ORDER BY c.rowid""",
            (user_id,),
        ) as cur:
            rows = await cur.fetchall()
    return [
        {
            "id": r["id"],
            "rarity": r["rarity"],
            "count": r["count"],
            "name": r["name"] if r["count"] else None,    # название неоткрытых не отдаём
            "image": r["image"] if r["count"] else None,  # имя файла; сама картинка лежит на Pages
        }
        for r in rows
    ]


# ---------- бот ----------
def webapp_link() -> str:
    # адрес API передаём во фронтенд через параметр ?api=, потому что он меняется при каждом запуске туннеля
    return f"{WEBAPP_URL}/?api={quote(API_URL, safe='')}"


def app_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🃏 Моя коллекция", web_app=WebAppInfo(url=webapp_link()))
    ]])


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Это бот-коллекция карточек.\n\n"
        "/free — получить случайную карточку\n"
        "/collection — открыть коллекцию",
        reply_markup=app_keyboard(),
    )


@router.message(Command("collection"))
async def cmd_collection(message: Message):
    await message.answer("Твоя коллекция:", reply_markup=app_keyboard())


@router.message(Command("free"))
async def cmd_free(message: Message):
    card, count = await give_random_card(message.from_user.id, message.from_user.username)
    _, name, rarity, image, _ = card
    status = "🆕 Новая карточка!" if count == 1 else f"Повторка, у тебя уже ×{count}"
    caption = f"<b>{name}</b>\n{RARITY[rarity]}\n\n{status}"
    path = CARDS_DIR / image
    if path.exists():
        await message.answer_photo(FSInputFile(path), caption=caption, reply_markup=app_keyboard())
    else:
        await message.answer(caption + "\n\n(файл картинки не найден)", reply_markup=app_keyboard())


# ---------- API для Mini App ----------
@web.middleware
async def cors(request: web.Request, handler):
    if request.method == "OPTIONS":
        resp = web.Response(status=204)
    else:
        try:
            resp = await handler(request)
        except web.HTTPException as e:
            resp = e
    resp.headers["Access-Control-Allow-Origin"] = PAGES_ORIGIN
    resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    return resp


async def api_collection(request: web.Request) -> web.Response:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("tma "):
        return web.json_response({"error": "unauthorized"}, status=401)
    try:
        data = safe_parse_webapp_init_data(BOT_TOKEN, auth[4:])
    except ValueError:
        return web.json_response({"error": "bad init data"}, status=401)
    return web.json_response({"cards": await get_collection(data.user.id)})


def make_web_app() -> web.Application:
    app = web.Application(middlewares=[cors])
    app.router.add_get("/api/collection", api_collection)
    app.router.add_get("/", lambda _: web.Response(text="card bot api ok"))
    return app


# ---------- туннель cloudflared ----------
async def start_tunnel():
    proc = await asyncio.create_subprocess_exec(
        "cloudflared", "tunnel", "--url", f"http://localhost:{PORT}",
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    url_re = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
    found = asyncio.get_running_loop().create_future()

    async def pump():  # читаем вывод до конца, чтобы процесс не завис на заполненном буфере
        async for line in proc.stderr:
            m = url_re.search(line.decode(errors="ignore"))
            if m and not found.done():
                found.set_result(m.group(0))

    task = asyncio.create_task(pump())
    url = await asyncio.wait_for(found, timeout=45)
    return proc, task, url


async def main() -> None:
    global API_URL
    logging.basicConfig(level=logging.INFO)
    await init_db()

    runner = web.AppRunner(make_web_app())
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()

    tunnel = None
    if not API_URL:
        try:
            tunnel, _pump, API_URL = await start_tunnel()
        except FileNotFoundError:
            raise SystemExit("cloudflared не найден. Установите его (см. README) или задайте API_URL в .env")
        except asyncio.TimeoutError:
            raise SystemExit("cloudflared не выдал адрес за 45 секунд. Проверьте интернет и попробуйте снова")
    logging.info("API: %s", API_URL)
    logging.info("Mini App: %s", webapp_link())

    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(text="Коллекция", web_app=WebAppInfo(url=webapp_link()))
    )
    dp = Dispatcher()
    dp.include_router(router)
    try:
        await dp.start_polling(bot)
    finally:
        if tunnel and tunnel.returncode is None:
            tunnel.terminate()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
