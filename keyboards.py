from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import CHANNEL_ID, CATEGORIES, PREMIUM_TIERS

def get_main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🔍 Поиск анкет"), KeyboardButton(text="🎭 Анонимный чат")],
        [KeyboardButton(text="💰 Экономика")],
        [KeyboardButton(text="👤 Мой профиль"), KeyboardButton(text="📊 Моя статистика")],
        [KeyboardButton(text="💎 Premium"), KeyboardButton(text="💌 Кто меня лайкнул")],
        [KeyboardButton(text="🎁 Пригласить друга"), KeyboardButton(text="🎁 Ежедневный бонус")],
        [KeyboardButton(text="🎟 Активировать промокод")],
        [KeyboardButton(text="📜 Правила"), KeyboardButton(text="🛑 Скрыть анкету")]
    ], resize_keyboard=True)

def edit_profile_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить Имя", callback_data="edit_name")],
        [InlineKeyboardButton(text="Изменить Возраст", callback_data="edit_age")],
        [InlineKeyboardButton(text="Изменить Город", callback_data="edit_city")],
        [InlineKeyboardButton(text="Изменить Описание", callback_data="edit_bio")],
        [InlineKeyboardButton(text="Изменить Фото", callback_data="edit_photo")]
    ])

def profile_kb(target_id):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👎 Скип", callback_data=f"skip_{target_id}"),
        InlineKeyboardButton(text="👋 Привет", callback_data=f"hello_{target_id}"),
        InlineKeyboardButton(text="❤️ Лайк", callback_data=f"like_{target_id}")
    )
    builder.row(
        InlineKeyboardButton(text="💌 Написать", callback_data=f"msg_{target_id}"),
        InlineKeyboardButton(text="🚩 Жалоба", callback_data=f"report_{target_id}")
    )
    return builder.as_markup()

def chat_kb():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⏭ Следующий", callback_data="chat_next"),
        InlineKeyboardButton(text="🚩 Пожаловаться", callback_data="chat_report"),
        InlineKeyboardButton(text="🛑 Завершить", callback_data="chat_stop")
    )
    return builder.as_markup()

gender_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="👩 Я девушка")], [KeyboardButton(text="👨 Я парень")]], 
    resize_keyboard=True, one_time_keyboard=True
)
pref_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="👩 Девушки")], [KeyboardButton(text="👨 Парни")], [KeyboardButton(text="🌈 Всё равно")]], 
    resize_keyboard=True, one_time_keyboard=True
)
skip_bio_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="⏭ Пропустить описание")]], 
    resize_keyboard=True, one_time_keyboard=True
)
rules_agree_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="✅ Я согласен с правилами")]], 
    resize_keyboard=True, one_time_keyboard=True
)

chat_gender_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="👨 Парня", callback_data="chat_find_boy")],
    [InlineKeyboardButton(text="👩 Девушку", callback_data="chat_find_girl")],
    [InlineKeyboardButton(text="🌈 Всё равно", callback_data="chat_find_all")]
])

def get_ad_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ Подписаться на канал", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")],
        [InlineKeyboardButton(text="Продолжить без подписки", callback_data="check_sub_or_skip")]
    ])

def get_sub_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ Подписаться на канал", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")],
        [InlineKeyboardButton(text="Я подписался", callback_data="check_sub_limit")]
    ])

def categories_kb(selected: list):
    builder = InlineKeyboardBuilder()
    for cat in CATEGORIES:
        mark = "✅ " if cat in selected else "⬜ "
        builder.button(text=f"{mark}{cat}", callback_data=f"cat_{cat}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="Готово ➡️", callback_data="cat_done"))
    return builder.as_markup()

def premium_menu_kb(prem_type):
    builder = InlineKeyboardBuilder()
    
    if not prem_type:
        builder.row(InlineKeyboardButton(text=f"💎 Standard ({PREMIUM_TIERS['standard']['price']}₽/мес)", callback_data="buy_standard"))
        builder.row(InlineKeyboardButton(text=f"👑 Deluxe ({PREMIUM_TIERS['deluxe']['price']}₽/мес)", callback_data="buy_deluxe"))
    else:
        tier_name = PREMIUM_TIERS[prem_type]['name']
        builder.row(InlineKeyboardButton(text=f"✅ Активен: {tier_name}", callback_data="noop"))
        
        if prem_type == "deluxe":
             builder.row(InlineKeyboardButton(text="🎨 Кастомизация профиля", callback_data="deluxe_customization"))
             
        builder.row(InlineKeyboardButton(text="🏷 Управление тегом", callback_data="edit_tag_start"))
        
    return builder.as_markup()

def deluxe_customization_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🖼 Сменить рамку", callback_data="change_frame"))
    builder.row(InlineKeyboardButton(text="🌈 Цвет ника", callback_data="change_color"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="premium_back"))
    return builder.as_markup()