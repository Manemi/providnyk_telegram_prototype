import asyncio
import logging
import os
from collections import defaultdict
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import (
    FSInputFile,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from dotenv import load_dotenv

from game import db
from game.engine import (
    evaluate_theory,
    get_location_image,
    handle_player_text,
    new_game,
    render_evidence,
    render_intro,
    render_map,
    render_mission,
    render_notebook,
    render_profile,
    render_skills,
    render_suspects,
    start_or_get,
    use_hint,
)

load_dotenv()
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
router = Router()
USER_LOCKS: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
COVER_PATH = ASSETS_DIR / "cover.png"

BTN_HERO = "🧍 Герой"
BTN_MISSION = "🎯 Місія"
BTN_NOTEBOOK = "📒 Блокнот"
BTN_MAP = "🗺️ Карта"
BTN_HINT = "💡 Підказка"
BTN_COMMANDS = "⚙️ Команди"

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_HERO), KeyboardButton(text=BTN_MISSION)],
        [KeyboardButton(text=BTN_NOTEBOOK), KeyboardButton(text=BTN_MAP)],
        [KeyboardButton(text=BTN_HINT), KeyboardButton(text=BTN_COMMANDS)],
    ],
    resize_keyboard=True,
    input_field_placeholder="Напиши дію Тараса або обери розділ…",
    selective=False,
)

HELP_TEXT = """
📚 «Провідник: Контур» — українська детективно-шпигунська RPG-повість.

На старті ти обираєш:
1. Режим складності.
2. Характер Тараса.

Режими:
• Легкий — мʼякі підказки показуються автоматично.
• Середній — підказки обмежені; нові можна здобути за важливі зачіпки.
• Хардкор — без підказок, тільки карта, докази й власні висновки.

Нижні кнопки:
🧍 Герой — характеристики та навички.
🎯 Місія — завдання і стан справи.
📒 Блокнот — докази, версії, важливі нотатки.
🗺️ Карта — де Тарас, куди можна піти, що можна зробити.
💡 Підказка — використати підказку згідно з режимом.
⚙️ Команди — службові команди гри.

Показники після сцени:
⏳ Темп сцени — скільки дій уже зроблено в цій локації; це не заборона, а сигнал ритму.
🔥 Напруга справи — наскільки ситуація нагрівається: час, нерви, тиск обставин.
🚨 Ризик викриття — наскільки близько вороги/фігуранти до розуміння, що Тарас на їхньому сліді.

Команди:
/start — почати або продовжити
/newgame — нова справа з початку
/profile — стан Тараса
/skills — реальні навички героя
/mission — картка місії
/notebook — блокнот Тараса
/map — карта й варіанти дій
/hint — підказка
/evidence — докази
/suspects — підозрювані та фігуранти
/locations — доступні напрямки
/theory твоя версія — перевірити гіпотезу
/journal — журнал подій
/help — інструкція
""".strip()

COMMANDS_TEXT = """
⚙️ Команди гри

/start — почати або продовжити
/newgame — почати справу заново
/profile — характеристики Тараса
/skills — навички Тараса
/mission — картка місії
/notebook — блокнот
/map — карта й варіанти дій
/hint — підказка
/evidence — докази
/suspects — фігуранти
/locations — доступні напрямки
/theory текст — перевірити версію
/journal — журнал подій
/help — інструкція

Писати можна звичайною мовою:
«Оглянь номер, але нічого не чіпай»
«Притисни портьє питанням про час дзвінка»
«Іди до камери схову №46»
""".strip()


async def send_photo_if_exists(message: Message, filename: str | None, caption: str | None = None) -> None:
    if not filename:
        return
    path = ASSETS_DIR / filename
    if path.exists():
        await message.answer_photo(FSInputFile(path), caption=caption, reply_markup=MAIN_KEYBOARD)


async def send_episode_intro(message: Message, text: str) -> None:
    if COVER_PATH.exists():
        await message.answer_photo(FSInputFile(COVER_PATH), caption="🖼️ Обкладинка епізоду", reply_markup=MAIN_KEYBOARD)
    await message.answer(text, reply_markup=MAIN_KEYBOARD)


async def send_hero_card(message: Message) -> None:
    state = start_or_get(message.from_user.id)
    await message.answer(render_profile(state) + "\n\n" + render_skills(state), reply_markup=MAIN_KEYBOARD)


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    state = start_or_get(message.from_user.id)
    await send_episode_intro(message, render_intro(state))


@router.message(Command("newgame"))
async def cmd_newgame(message: Message) -> None:
    async with USER_LOCKS[message.from_user.id]:
        state = new_game(message.from_user.id)
        await message.answer("♻️ Нова справа відкрита. Спершу обери режим складності.", reply_markup=MAIN_KEYBOARD)
        await send_episode_intro(message, render_intro(state))


@router.message(Command("profile"))
async def cmd_profile(message: Message) -> None:
    await message.answer(render_profile(start_or_get(message.from_user.id)), reply_markup=MAIN_KEYBOARD)


@router.message(Command("skills"))
async def cmd_skills(message: Message) -> None:
    await message.answer(render_skills(start_or_get(message.from_user.id)), reply_markup=MAIN_KEYBOARD)


@router.message(Command("mission"))
async def cmd_mission(message: Message) -> None:
    await message.answer(render_mission(start_or_get(message.from_user.id)), reply_markup=MAIN_KEYBOARD)


@router.message(Command("notebook"))
async def cmd_notebook(message: Message) -> None:
    await message.answer(render_notebook(start_or_get(message.from_user.id)), reply_markup=MAIN_KEYBOARD)


@router.message(Command("map"))
@router.message(Command("locations"))
async def cmd_map(message: Message) -> None:
    await message.answer(render_map(start_or_get(message.from_user.id)), reply_markup=MAIN_KEYBOARD)


@router.message(Command("hint"))
async def cmd_hint(message: Message) -> None:
    async with USER_LOCKS[message.from_user.id]:
        answer, _state = use_hint(message.from_user.id)
    await message.answer(answer, reply_markup=MAIN_KEYBOARD)


@router.message(Command("evidence"))
async def cmd_evidence(message: Message) -> None:
    await message.answer(render_evidence(start_or_get(message.from_user.id)), reply_markup=MAIN_KEYBOARD)


@router.message(Command("suspects"))
async def cmd_suspects(message: Message) -> None:
    await message.answer(render_suspects(start_or_get(message.from_user.id)), reply_markup=MAIN_KEYBOARD)


@router.message(Command("theory"))
async def cmd_theory(message: Message) -> None:
    text = (message.text or "").replace("/theory", "", 1).strip()
    if not text:
        await message.answer("🧩 Напиши так:\n/theory чоловіка вбили через флешку, а портьє допоміг прибрати сліди", reply_markup=MAIN_KEYBOARD)
        return
    async with USER_LOCKS[message.from_user.id]:
        answer, _state = evaluate_theory(message.from_user.id, text)
    await message.answer(answer, reply_markup=MAIN_KEYBOARD)


@router.message(Command("journal"))
async def cmd_journal(message: Message) -> None:
    entries = db.get_journal(message.from_user.id, limit=8)
    if not entries:
        await message.answer("📓 Журнал порожній. Тарас ще не встиг образити систему фактами.", reply_markup=MAIN_KEYBOARD)
        return
    await message.answer("📓 Останні записи:\n\n" + "\n\n".join(entries), reply_markup=MAIN_KEYBOARD)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=MAIN_KEYBOARD)


@router.message(F.text == BTN_HERO)
async def btn_hero(message: Message) -> None:
    await send_hero_card(message)


@router.message(F.text == BTN_COMMANDS)
async def btn_commands(message: Message) -> None:
    await message.answer(COMMANDS_TEXT, reply_markup=MAIN_KEYBOARD)


@router.message(F.text == BTN_MISSION)
async def btn_mission(message: Message) -> None:
    await message.answer(render_mission(start_or_get(message.from_user.id)), reply_markup=MAIN_KEYBOARD)


@router.message(F.text == BTN_NOTEBOOK)
async def btn_notebook(message: Message) -> None:
    await message.answer(render_notebook(start_or_get(message.from_user.id)), reply_markup=MAIN_KEYBOARD)


@router.message(F.text == BTN_MAP)
async def btn_map(message: Message) -> None:
    await message.answer(render_map(start_or_get(message.from_user.id)), reply_markup=MAIN_KEYBOARD)


@router.message(F.text == BTN_HINT)
async def btn_hint(message: Message) -> None:
    async with USER_LOCKS[message.from_user.id]:
        answer, _state = use_hint(message.from_user.id)
    await message.answer(answer, reply_markup=MAIN_KEYBOARD)


@router.message(F.text)
async def on_text(message: Message) -> None:
    text = (message.text or "").strip()
    if not text:
        return
    async with USER_LOCKS[message.from_user.id]:
        answer, _state, image_name = await handle_player_text(message.from_user.id, text)
    await send_photo_if_exists(message, image_name)
    await message.answer(answer, reply_markup=MAIN_KEYBOARD)


async def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token or token == "put_your_telegram_bot_token_here":
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN in .env")
    db.init_db()
    bot = Bot(token=token)
    dp = Dispatcher()
    dp.include_router(router)
    drop_pending = os.getenv("DROP_PENDING_UPDATES", "false").lower() in {"1", "true", "yes", "on"}
    await bot.delete_webhook(drop_pending_updates=drop_pending)
    logger.info("Starting Провідник bot with database %s", db.db_path())
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
