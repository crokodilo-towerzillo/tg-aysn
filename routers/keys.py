import asyncio
from datetime import datetime

from aiogram import F, Router
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


async def _build_main_screen(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    keys = db.get_keys(user_id)
    if not keys:
        return "Ваши магазины:", keyboards.no_keys_keyboard()
    statuses = await asyncio.gather(
        *[calculator.validate_key(db.decrypt_key(k)) for k in keys]
    )
    for key, is_valid in zip(keys, statuses):
        db.update_key_validity(key["id"], is_valid)
    shops = [(k["id"], k["label"], ok) for k, ok in zip(keys, statuses)]
    return "Ваши магазины:", keyboards.main_keyboard(shops)


async def _sync_all(keys: list) -> None:
    async def _one(key_row):
        if not calculator.needs_sync(key_row["last_synced_at"]):
            return
        api_key = db.decrypt_key(key_row)
        ls = key_row["last_synced_at"]
        date_from = (
            datetime.fromisoformat(ls).strftime("%Y-%m-%d") if ls else "2025-01-01"
        )
        await calculator.sync_reports(key_row["id"], api_key, date_from)

    await asyncio.gather(*[_one(k) for k in keys])


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.chat.id
    keys = db.get_keys(user_id)

    if keys and any(calculator.needs_sync(k["last_synced_at"]) for k in keys):
        msg = await message.answer("Обновляю данные...")
        await _sync_all(keys)
        text, kb = await _build_main_screen(user_id)
        await msg.edit_text(text, reply_markup=kb)
    else:
        text, kb = await _build_main_screen(user_id)
        await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "home")
async def cb_home(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text, kb = await _build_main_screen(call.message.chat.id)
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "add_key")
async def cb_add_key_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(AddKey.label)
    await call.message.edit_text(
        "Введите метку магазина:", reply_markup=keyboards.cancel_keyboard()
    )
    await call.answer()


@router.message(AddKey.label)
async def add_key_label(message: Message, state: FSMContext):
    label = message.text.strip() if message.text else ""
    if not label:
        await message.answer("Метка не может быть пустой:", reply_markup=keyboards.cancel_keyboard())
        return
    await state.update_data(label=label)
    await state.set_state(AddKey.token)
    text = (
        "Введите API ключ WB:\n\n"
        "Создайте токен в ЛК WB → Профиль → Настройки → "
        "Доступ к API → категория Финансы (тип: Персональный или Сервисный)"
    )
    await message.answer(text, reply_markup=keyboards.cancel_keyboard())


@router.message(AddKey.token)
async def add_key_token(message: Message, state: FSMContext):
    api_key = message.text.strip() if message.text else ""
    data = await state.get_data()
    label = data["label"]

    valid = await calculator.validate_key(api_key)
    if not valid:
        await message.answer(
            "Ключ недействителен, проверьте тип токена и попробуйте снова:",
            reply_markup=keyboards.cancel_keyboard(),
        )
        return

    key_id = db.add_key(user_id=message.chat.id, label=label, api_key=api_key)
    await state.clear()
    msg = await message.answer("Загружаю историю отчётов...")
    await calculator.sync_reports(key_id, api_key, "2025-01-01")
    text, kb = await _build_main_screen(message.chat.id)
    await msg.edit_text(f'Магазин "{label}" добавлен 🟢\n\n{text}', reply_markup=kb)


@router.callback_query(F.data == "delete_key")
async def cb_delete_key_start(call: CallbackQuery):
    keys = db.get_keys(call.message.chat.id)
    shops = [(k["id"], k["label"]) for k in keys]
    await call.message.edit_text(
        "Выберите магазин для удаления:",
        reply_markup=keyboards.delete_list_keyboard(shops),
    )
    await call.answer()


@router.callback_query(F.data.startswith("delete_select:"))
async def cb_delete_select(call: CallbackQuery):
    key_id = int(call.data.split(":")[1])
    row = db.get_key(key_id)
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
    row = db.get_key(key_id)
    label = row["label"] if row else "Магазин"
    db.delete_key(key_id)
    text, kb = await _build_main_screen(call.message.chat.id)
    await call.message.edit_text(f'Магазин "{label}" удалён.\n\n{text}', reply_markup=kb)
    await call.answer()
