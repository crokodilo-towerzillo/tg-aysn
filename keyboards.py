from datetime import date

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

_MONTHS_RU = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]
_EMPTY = "　"  # ideographic space — visually empty, uniquely identifiable


def _btn(text: str, cb: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=cb)


def _empty_btn() -> InlineKeyboardButton:
    return _btn(_EMPTY, "noop")


def _month_grid(
    year: int,
    active_from: tuple[int, int],
    active_to: tuple[int, int],
    cb_prefix: str,
) -> list[list[InlineKeyboardButton]]:
    rows = []
    for row_start in range(1, 13, 3):
        row = []
        for m in range(row_start, row_start + 3):
            if active_from <= (year, m) <= active_to:
                row.append(_btn(_MONTHS_RU[m - 1], f"{cb_prefix}:{year}:{m}"))
            else:
                row.append(_empty_btn())
        rows.append(row)
    return rows


def main_keyboard(shops: list[tuple[int, str, bool]]) -> InlineKeyboardMarkup:
    buttons = []
    for key_id, label, is_valid in shops:
        icon = "🟢" if is_valid else "🔴"
        buttons.append([_btn(f"{icon} {label}", f"calc:{key_id}")])
    buttons.append([_btn("➕ Добавить ключ", "add_key")])
    if shops:
        buttons.append([_btn("🗑 Удалить ключ", "delete_key")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def no_keys_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("➕ Добавить ключ", "add_key")]
    ])


def period_keyboard(key_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            _btn("📅 Этот месяц", f"period:this:{key_id}"),
            _btn("📅 Прошлый месяц", f"period:prev:{key_id}"),
        ],
        [_btn("✏️ Свой период", f"period:custom:{key_id}")],
        [_btn("🏠 Главная", "home")],
    ])


def delete_list_keyboard(shops: list[tuple[int, str, bool]]) -> InlineKeyboardMarkup:
    buttons = [
        [_btn(f"{'🟢' if is_valid else '🔴'} {label}", f"delete_select:{key_id}")]
        for key_id, label, is_valid in shops
    ]
    buttons.append([_btn("✖️ Отмена", "home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_delete_keyboard(key_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("✅ Да, удалить", f"delete_confirm:{key_id}"), _btn("✖️ Отмена", "home")]
    ])


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("✖️ Отмена", "home")]])


def result_keyboard(key_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("🔄 Другой период", f"period_again:{key_id}"), _btn("🏠 Главная", "home")]
    ])


def custom_from_keyboard(key_id: int, year: int | None = None) -> InlineKeyboardMarkup:
    today = date.today()
    if year is None:
        year = today.year
    prev_year = year - 1 if year > 2025 else None
    next_year = year + 1 if year < today.year else None
    nav = [
        _btn("◀️", f"cyf:{key_id}:{prev_year}") if prev_year else _empty_btn(),
        _btn(str(year), "noop"),
        _btn("▶️", f"cyf:{key_id}:{next_year}") if next_year else _empty_btn(),
    ]
    rows = [nav] + _month_grid(year, (2025, 1), (today.year, today.month), f"cf:{key_id}")
    rows.append([_btn("Отмена", "home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def custom_to_keyboard(key_id: int, from_y: int, from_m: int, year: int | None = None) -> InlineKeyboardMarkup:
    today = date.today()
    if year is None:
        year = today.year
    prev_year = year - 1 if year - 1 >= from_y else None
    next_year = year + 1 if year + 1 <= today.year else None
    nav = [
        _btn("◀️", f"cyt:{key_id}:{from_y}:{from_m}:{prev_year}") if prev_year else _empty_btn(),
        _btn(str(year), "noop"),
        _btn("▶️", f"cyt:{key_id}:{from_y}:{from_m}:{next_year}") if next_year else _empty_btn(),
    ]
    rows = [nav] + _month_grid(year, (from_y, from_m), (today.year, today.month), f"ct:{key_id}:{from_y}:{from_m}")
    rows.append([_btn("◀️ Назад", f"calc:{key_id}")])
    rows.append([_btn("✖️ Отмена", "home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
