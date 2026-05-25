import asyncio

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

import calculator
import db
import keyboards

router = Router()


class AddKey(StatesGroup):
    label = State()
    token = State()


_WELCOME = (
    "Привет! Я считаю налог АУСН «доходы» 8% по вашим продажам на Wildberries.\n\n"
)

_TOKEN_INSTRUCTION = (
    "🔑 Введите API-ключ Wildberries\n\n"
    "1️⃣ Профиль → Интеграции по API\n"
    "2️⃣ Создать токен → Для интеграции вручную\n"
    "3️⃣ Персональный токен\n"
    "4️⃣ Финансы\n"
    "5️⃣ Только чтение"
)


def _build_main_screen(user_id: int, welcome: bool = False) -> tuple[str, InlineKeyboardMarkup]:
    keys = db.get_keys(user_id)
    prefix = _WELCOME if welcome else ""
    if not keys:
        return prefix + "Ваши магазины:", keyboards.no_keys_keyboard()
    shops = [(k["id"], k["label"], bool(k["is_valid"])) for k in keys]
    return prefix + "Ваши магазины:", keyboards.main_keyboard(shops)


async def _sync_all(keys: list) -> None:
    async def _one(key_row):
        if not calculator.needs_sync(key_row["last_synced_at"]):
            return
        api_key = db.decrypt_key(key_row)
        await calculator.sync_reports(key_row["id"], api_key, "2025-01-01")

    await asyncio.gather(*[_one(k) for k in keys])


async def _edit_or_answer(message: Message, bot_msg_id: int | None, text: str, kb=None) -> int:
    if bot_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=bot_msg_id,
                text=text,
                reply_markup=kb,
            )
            return bot_msg_id
        except TelegramBadRequest as e:
            if "not modified" in e.message.lower():
                return bot_msg_id
    sent = await message.answer(text, reply_markup=kb)
    return sent.message_id


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    user_id = message.chat.id
    keys = db.get_keys(user_id)

    if keys and any(calculator.needs_sync(k["last_synced_at"]) for k in keys):
        msg = await message.answer("Обновляю данные...")
        await _sync_all(keys)
        text, kb = _build_main_screen(user_id, welcome=True)
        await msg.edit_text(text, reply_markup=kb)
    else:
        text, kb = _build_main_screen(user_id, welcome=True)
        await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "home")
async def cb_home(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text, kb = _build_main_screen(call.message.chat.id)
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "add_key")
async def cb_add_key_start(call: CallbackQuery, state: FSMContext):
    if len(db.get_keys(call.message.chat.id)) >= 15:
        await call.message.edit_text(
            "Достигнут лимит 15 магазинов. Удалите один, чтобы добавить новый.",
            reply_markup=keyboards.cancel_keyboard(),
        )
        await call.answer()
        return
    await state.set_state(AddKey.label)
    await state.update_data(bot_msg_id=call.message.message_id)
    await call.message.edit_text(
        "Введите имя магазина:", reply_markup=keyboards.cancel_keyboard()
    )
    await call.answer()


@router.message(AddKey.label)
async def add_key_label(message: Message, state: FSMContext):
    label = message.text.strip() if message.text else ""
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    data = await state.get_data()
    bot_msg_id = data.get("bot_msg_id")

    if not label:
        await _edit_or_answer(
            message, bot_msg_id,
            "Имя не может быть пустым. Введите имя магазина:",
            keyboards.cancel_keyboard(),
        )
        return

    if len(label) > 100:
        await _edit_or_answer(
            message, bot_msg_id,
            "Имя слишком длинное (максимум 100 символов). Введите имя магазина:",
            keyboards.cancel_keyboard(),
        )
        return

    existing = db.get_keys(message.chat.id)
    if any(k["label"] == label for k in existing):
        await _edit_or_answer(
            message, bot_msg_id,
            f'Имя "{label}" уже занято. Введите другое:',
            keyboards.cancel_keyboard(),
        )
        return

    await state.update_data(label=label)
    await state.set_state(AddKey.token)
    await _edit_or_answer(message, bot_msg_id, _TOKEN_INSTRUCTION, keyboards.cancel_keyboard())


@router.message(AddKey.token)
async def add_key_token(message: Message, state: FSMContext):
    api_key = message.text.strip() if message.text else ""
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    data = await state.get_data()
    label = data["label"]
    bot_msg_id = data.get("bot_msg_id")

    valid = await calculator.validate_key(api_key)
    if not valid:
        await _edit_or_answer(
            message, bot_msg_id,
            _TOKEN_INSTRUCTION + "\n\n❌ Ключ недействителен, проверьте тип токена",
            keyboards.cancel_keyboard(),
        )
        return

    key_id = db.add_key(user_id=message.chat.id, label=label, api_key=api_key)
    await state.clear()
    effective_id = await _edit_or_answer(message, bot_msg_id, "Загружаю историю отчётов...")
    await calculator.sync_reports(key_id, api_key, "2025-01-01")
    text, kb = _build_main_screen(message.chat.id)
    await _edit_or_answer(message, effective_id, f'Магазин "{label}" добавлен 🟢\n\n{text}', kb)


@router.callback_query(F.data == "delete_key")
async def cb_delete_key_start(call: CallbackQuery):
    keys = db.get_keys(call.message.chat.id)
    shops = [(k["id"], k["label"], bool(k["is_valid"])) for k in keys]
    await call.message.edit_text(
        "Выберите магазин для удаления:",
        reply_markup=keyboards.delete_list_keyboard(shops),
    )
    await call.answer()


@router.callback_query(F.data.startswith("delete_select:"))
async def cb_delete_select(call: CallbackQuery):
    key_id = int(call.data.split(":")[1])
    row = db.get_key(key_id, user_id=call.message.chat.id)
    if row is None:
        await call.answer("Магазин не найден")
        return
    await call.message.edit_text(
        f'Удалить "{row["label"]}"? Данные отчётов будут удалены.',
        reply_markup=keyboards.confirm_delete_keyboard(key_id),
    )
    await call.answer()


@router.callback_query(F.data.startswith("delete_confirm:"))
async def cb_delete_confirm(call: CallbackQuery):
    key_id = int(call.data.split(":")[1])
    row = db.get_key(key_id, user_id=call.message.chat.id)
    if row is None:
        await call.answer("Магазин не найден")
        return
    label = row["label"]
    db.delete_key(key_id)
    text, kb = _build_main_screen(call.message.chat.id)
    await call.message.edit_text(f'Магазин "{label}" удалён.\n\n{text}', reply_markup=kb)
    await call.answer()
