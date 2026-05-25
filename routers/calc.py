from datetime import date

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import calculator
import db
import keyboards

router = Router()


class CalcPeriod(StatesGroup):
    custom_input = State()


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
    row = db.get_key(key_id)
    if row is None:
        text = "Магазин не найден."
        kb = keyboards.cancel_keyboard()
    elif not row["is_valid"]:
        text = "Ключ недействителен, обновите его."
        kb = keyboards.result_keyboard(key_id)
    else:
        tax = calculator.calculate_tax(key_id, month_from, month_to)
        period_str = calculator.format_period(month_from, month_to)
        if tax is None:
            text = f"За {period_str} отчётов не найдено."
        else:
            tax_fmt = f"{tax:,}".replace(",", " ")
            text = f"Налог АУСН 8% за {period_str}: {tax_fmt} руб."
        kb = keyboards.result_keyboard(key_id)

    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb)
        await target.answer()
    else:
        await target.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("calc:"))
async def cb_calc_select(call: CallbackQuery, state: FSMContext):
    key_id = int(call.data.split(":")[1])
    await state.update_data(key_id=key_id)
    await call.message.edit_text(
        "Выберите период:", reply_markup=keyboards.period_keyboard(key_id)
    )
    await call.answer()


@router.callback_query(F.data.startswith("period_again:"))
async def cb_period_again(call: CallbackQuery, state: FSMContext):
    key_id = int(call.data.split(":")[1])
    await state.update_data(key_id=key_id)
    await call.message.edit_text(
        "Выберите период:", reply_markup=keyboards.period_keyboard(key_id)
    )
    await call.answer()


@router.callback_query(F.data.startswith("period:this:"))
async def cb_period_this(call: CallbackQuery):
    key_id = int(call.data.split(":")[2])
    m_from, m_to = _this_month()
    await _show_result(call, key_id, m_from, m_to)


@router.callback_query(F.data.startswith("period:prev:"))
async def cb_period_prev(call: CallbackQuery):
    key_id = int(call.data.split(":")[2])
    m_from, m_to = _last_month()
    await _show_result(call, key_id, m_from, m_to)


@router.callback_query(F.data.startswith("period:custom:"))
async def cb_period_custom_start(call: CallbackQuery, state: FSMContext):
    key_id = int(call.data.split(":")[2])
    await state.set_state(CalcPeriod.custom_input)
    await state.update_data(key_id=key_id)
    await call.message.edit_text(
        "Введите период в формате MM.YY-MM.YY\nНапример: 01.26-03.26 (январь–март 2026)",
        reply_markup=keyboards.cancel_keyboard(),
    )
    await call.answer()


@router.message(CalcPeriod.custom_input)
async def custom_period_input(message: Message, state: FSMContext):
    data = await state.get_data()
    key_id = data["key_id"]
    parsed = calculator.parse_period(message.text or "")
    if isinstance(parsed, str):
        await message.answer(parsed, reply_markup=keyboards.cancel_keyboard())
        return
    await state.clear()
    m_from, m_to = parsed
    await _show_result(message, key_id, m_from, m_to)
