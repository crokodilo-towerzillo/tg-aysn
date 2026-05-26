from datetime import date

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import calculator
import db
import keyboards

router = Router()


def _this_month() -> tuple[tuple[int, int], tuple[int, int]]:
    today = date.today()
    return (today.year, today.month), (today.year, today.month)


def _last_month() -> tuple[tuple[int, int], tuple[int, int]]:
    today = date.today()
    y, m = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
    return (y, m), (y, m)


async def _show_result(
    target: CallbackQuery | Message,
    key_id: int,
    month_from: tuple[int, int],
    month_to: tuple[int, int],
):
    user_id = target.message.chat.id if isinstance(target, CallbackQuery) else target.chat.id
    row = db.get_key(key_id, user_id=user_id)
    if row is None:
        text = "Магазин не найден."
        kb = keyboards.cancel_keyboard()
    elif not row["is_valid"]:
        text = "Ключ недействителен. Удалите магазин и добавьте заново."
        kb = keyboards.result_keyboard(key_id)
    else:
        tax = calculator.calculate_tax(key_id, month_from, month_to)
        period_str = calculator.format_period(month_from, month_to)
        if tax is None:
            text = f"За {period_str} отчётов не найдено."
        else:
            tax_fmt = f"{tax:,}".replace(",", " ")
            text = f"Налог АУСН 8% за {period_str}:\n{tax_fmt} руб."
        kb = keyboards.result_keyboard(key_id)

    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb)
        await target.answer()
    else:
        await target.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("calc:"))
async def cb_calc_select(call: CallbackQuery):
    key_id = int(call.data.split(":")[1])
    row = db.get_key(key_id, user_id=call.message.chat.id)
    if row is None:
        await call.answer("Магазин не найден", show_alert=True)
        return
    if calculator.needs_sync(row["last_synced_at"]):
        await call.message.edit_text("Обновляю данные...")
        await calculator.sync_reports(key_id, db.decrypt_key(row), "2025-01-01")
    await call.message.edit_text(
        "Выберите период:", reply_markup=keyboards.period_keyboard(key_id)
    )
    await call.answer()


@router.callback_query(F.data.startswith("period_again:"))
async def cb_period_again(call: CallbackQuery):
    key_id = int(call.data.split(":")[1])
    if db.get_key(key_id, user_id=call.message.chat.id) is None:
        await call.answer("Магазин не найден", show_alert=True)
        return
    await call.message.edit_text(
        "Выберите период:", reply_markup=keyboards.period_keyboard(key_id)
    )
    await call.answer()


@router.callback_query(F.data.startswith("period:this:"))
async def cb_period_this(call: CallbackQuery, state: FSMContext):
    await state.clear()
    key_id = int(call.data.split(":")[2])
    m_from, m_to = _this_month()
    await _show_result(call, key_id, m_from, m_to)


@router.callback_query(F.data.startswith("period:prev:"))
async def cb_period_prev(call: CallbackQuery, state: FSMContext):
    await state.clear()
    key_id = int(call.data.split(":")[2])
    m_from, m_to = _last_month()
    await _show_result(call, key_id, m_from, m_to)


@router.callback_query(F.data.startswith("period:custom:"))
async def cb_period_custom_start(call: CallbackQuery):
    key_id = int(call.data.split(":")[2])
    if db.get_key(key_id, user_id=call.message.chat.id) is None:
        await call.answer("Магазин не найден", show_alert=True)
        return
    await call.message.edit_text(
        "Выберите начало периода:", reply_markup=keyboards.custom_from_keyboard(key_id)
    )
    await call.answer()


@router.callback_query(F.data.startswith("cf:"))
async def cb_custom_from(call: CallbackQuery):
    _, key_id, y, m = call.data.split(":")
    key_id, y, m = int(key_id), int(y), int(m)
    if db.get_key(key_id, user_id=call.message.chat.id) is None:
        await call.answer("Магазин не найден", show_alert=True)
        return
    await call.message.edit_text(
        "Выберите конец периода:", reply_markup=keyboards.custom_to_keyboard(key_id, y, m)
    )
    await call.answer()


@router.callback_query(F.data.startswith("ct:"))
async def cb_custom_to(call: CallbackQuery, state: FSMContext):
    parts = call.data.split(":")
    key_id = int(parts[1])
    from_y, from_m, to_y, to_m = int(parts[2]), int(parts[3]), int(parts[4]), int(parts[5])
    await state.clear()
    await _show_result(call, key_id, (from_y, from_m), (to_y, to_m))


@router.callback_query(F.data.startswith("cyf:"))
async def cb_custom_year_from(call: CallbackQuery):
    parts = call.data.split(":")
    key_id, year = int(parts[1]), int(parts[2])
    if db.get_key(key_id, user_id=call.message.chat.id) is None:
        await call.answer("Магазин не найден", show_alert=True)
        return
    await call.message.edit_reply_markup(reply_markup=keyboards.custom_from_keyboard(key_id, year))
    await call.answer()


@router.callback_query(F.data.startswith("cyt:"))
async def cb_custom_year_to(call: CallbackQuery):
    parts = call.data.split(":")
    key_id, from_y, from_m, year = int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])
    if db.get_key(key_id, user_id=call.message.chat.id) is None:
        await call.answer("Магазин не найден", show_alert=True)
        return
    await call.message.edit_reply_markup(reply_markup=keyboards.custom_to_keyboard(key_id, from_y, from_m, year))
    await call.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(call: CallbackQuery):
    await call.answer()
