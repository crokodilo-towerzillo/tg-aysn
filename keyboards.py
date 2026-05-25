from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_keyboard(shops: list[tuple[int, str, bool]]) -> InlineKeyboardMarkup:
    """shops: [(key_id, label, is_valid), ...]"""
    buttons = []
    for key_id, label, is_valid in shops:
        icon = "🟢" if is_valid else "🔴"
        buttons.append([InlineKeyboardButton(
            text=f"{icon} {label}", callback_data=f"calc:{key_id}"
        )])
    buttons.append([InlineKeyboardButton(text="Добавить ключ", callback_data="add_key")])
    if shops:
        buttons.append([InlineKeyboardButton(text="Удалить ключ", callback_data="delete_key")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def no_keys_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить ключ", callback_data="add_key")]
    ])


def period_keyboard(key_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Этот месяц", callback_data=f"period:this:{key_id}"),
            InlineKeyboardButton(text="Прошлый месяц", callback_data=f"period:prev:{key_id}"),
        ],
        [InlineKeyboardButton(text="Свой период", callback_data=f"period:custom:{key_id}")],
        [InlineKeyboardButton(text="Главная", callback_data="home")],
    ])


def delete_list_keyboard(shops: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    """shops: [(key_id, label), ...]"""
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"delete_select:{key_id}")]
        for key_id, label in shops
    ]
    buttons.append([InlineKeyboardButton(text="Отмена", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_delete_keyboard(key_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да, удалить", callback_data=f"delete_confirm:{key_id}"),
            InlineKeyboardButton(text="Отмена", callback_data="home"),
        ]
    ])


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="home")]
    ])


def result_keyboard(key_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Другой период", callback_data=f"period_again:{key_id}"),
            InlineKeyboardButton(text="Главная", callback_data="home"),
        ]
    ])
