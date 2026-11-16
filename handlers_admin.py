from datetime import datetime, timedelta
from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import get_user, block_user, set_premium
from keyboards import get_main_kb
from config import ADMIN_ID, CHANNEL_ID, PREMIUM_TIERS

router = Router()

class PromoCreate(StatesGroup):
    code = State()
    uses = State()
    days = State()

# --- ЖАЛОБЫ В АНКЕТАХ ---
@router.callback_query(F.data.startswith("report_"))
async def report_start(callback: types.CallbackQuery):
    target_id = int(callback.data.split("_")[1])
    if target_id == callback.from_user.id: 
        return await callback.answer("Нельзя на себя!", show_alert=True)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="Спам", callback_data=f"rep_Спам_{target_id}")
    builder.button(text="18+", callback_data=f"rep_18+_{target_id}")
    builder.button(text="Оскорбления", callback_data=f"rep_Оскорбления_{target_id}")
    builder.adjust(2)
    await callback.message.edit_caption(caption="Выберите причину жалобы:", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("rep_"))
async def report_reason(callback: types.CallbackQuery, bot: Bot):
    reason = callback.data.split("_")[1]
    target_id = int(callback.data.split("_")[2])
    
    offender = await get_user(target_id)
    if not offender: return await callback.answer("Удален.", show_alert=True)
    
    admin_text = f"🚨 ЖАЛОБА!\nПричина: {reason}\nНа: {offender[6]} ({target_id})\nОт: {callback.from_user.full_name} ({callback.from_user.id})"
    admin_kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🗑 Забанить", callback_data=f"admin_block_{target_id}")],
        [types.InlineKeyboardButton(text="✅ Ок", callback_data="admin_ignore")]
    ])
    try:
        if offender[8]: await bot.send_photo(ADMIN_ID, offender[8], caption=admin_text, reply_markup=admin_kb)
        else: await bot.send_message(ADMIN_ID, admin_text, reply_markup=admin_kb)
        await callback.message.edit_caption(caption="✅ Жалоба отправлена.", reply_markup=None)
    except Exception: pass

@router.callback_query(F.data.startswith("admin_block_"))
async def admin_block(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    target_id = int(callback.data.split("_")[2])
    await block_user(target_id)
    await callback.message.edit_caption(caption=(callback.message.caption or "") + "\n🔴 ЗАБЛОКИРОВАН")

@router.callback_query(F.data == "admin_ignore")
async def admin_ignore(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.edit_caption(caption=(callback.message.caption or "") + "\n🟢 ОТКЛОНЕНО")

# --- ПРОМОКОДЫ ---
@router.message(F.text == "🎟 Активировать промокод")
async def activate_promo_start(message: types.Message):
    await message.answer("Введи промокод:")

@router.message(Command("createpromo"))
async def create_promo_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("Введи название промокода (например, TWINZ2026):")
    await state.set_state(PromoCreate.code)

@router.message(PromoCreate.code)
async def create_promo_code(message: types.Message, state: FSMContext):
    await state.update_data(code=message.text.upper())
    await message.answer("Сколько раз можно использовать этот промокод? (введи число):")
    await state.set_state(PromoCreate.uses)

@router.message(PromoCreate.uses)
async def create_promo_uses(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Введи число!")
    await state.update_data(uses=int(message.text))
    await message.answer("На сколько дней выдается Premium по этому промокоду? (введи число):")
    await state.set_state(PromoCreate.days)

@router.message(PromoCreate.days)
async def create_promo_days(message: types.Message, state: FSMContext):
    import aiosqlite
    from database import DB_NAME
    if not message.text.isdigit(): return await message.answer("Введи число!")
    days = int(message.text)
    
    data = await state.get_data()
    code = data['code']
    uses = data['uses']
    
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO promocodes (code, days, max_uses, used_count) VALUES (?, ?, ?, 0)", (code, days, uses))
        await db.commit()
        
    await message.answer(f"✅ <b>Промокод успешно создан!</b>\n\nКод: <code>{code}</code>\nАктиваций: {uses}\nДней Premium: {days}", parse_mode="HTML", reply_markup=get_main_kb())
    await state.clear()

# --- ПОКУПКА PREMIUM И ВЫДАЧА ---
@router.callback_query(F.data.startswith("buy_"))
async def buy_premium_callback(callback: types.CallbackQuery):
    tier_key = callback.data.replace("buy_", "")
    if tier_key not in PREMIUM_TIERS: return
    
    price = PREMIUM_TIERS[tier_key]['price']
    name = PREMIUM_TIERS[tier_key]['name']
    
    await callback.message.edit_text(
        f"💳 <b>Покупка {name} Premium</b>\n\n"
        f"Стоимость: {price} руб.\n\n"
        f"Для оплаты переведите сумму на карту: \n"
        f"<code>0000 0000 0000 0000</code>\n\n"
        f"И отправьте скриншот админу: @admin_username",
        parse_mode="HTML"
    )

@router.message(F.text.startswith("/give_prem"))
async def give_prem(message: types.Message, bot: Bot):
    if message.from_user.id != ADMIN_ID: return
    
    args = message.text.split()
    if len(args) < 3:
        return await message.answer("Использование: /give_prem ID TYPE DAYS\nТипы: standard, deluxe")
        
    try:
        target_id = int(args[1])
        prem_type = args[2].lower()
        days = int(args[3]) if len(args) > 3 else 30
        
        if prem_type not in ["standard", "deluxe"]:
            return await message.answer("Неверный тип. Используйте standard или deluxe.")
            
        await set_premium(target_id, days, prem_type)
        
        tier_name = PREMIUM_TIERS[prem_type]['name']
        await message.answer(f"✅ Выдан {tier_name} Premium пользователю {target_id} на {days} дней.")
        try: 
            await bot.send_message(target_id, f"💎 <b>Тебе выдан {tier_name} Premium!</b>\nНаслаждайся новыми возможностями.", parse_mode="HTML")
        except: pass
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

# --- АНКЕТА ДНЯ ---
@router.message(Command("anketa_dnya"))
async def anketa_dnya(message: types.Message, bot: Bot):
    import aiosqlite
    from database import DB_NAME, get_level_info
    if message.from_user.id != ADMIN_ID: return
        
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM users WHERE is_premium = 1 AND is_active = 1 ORDER BY RANDOM() LIMIT 1") as cur:
            profile = await cur.fetchone()
            
    if not profile:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT * FROM users WHERE is_active = 1 ORDER BY RANDOM() LIMIT 1") as cur:
                profile = await cur.fetchone()
                
    if not profile:
        return await message.answer("Нет активных анкет.")

    _, username, age, gender, looking_for, city, name, bio, photo_id, categories, _, _, _, is_this_prem, _, _, _, tag, hide_prem = profile[:19]
    lvl, exp = await get_level_info(profile[0])
    
    show_prem = is_this_prem and hide_prem == 0
    header = "<b>💎 PREMIUM АНКЕТА ДНЯ</b>\n" if show_prem else "<b>👤 АНКЕТА ДНЯ</b>\n"
    header += "━━━━━━━━━━━━━━━━━━━━\n"
    
    name_str = f"{name}, {age}"
    if tag: name_str += f"  <code>[{tag}]</code>"
    
    main_info = f"<b>{name_str}</b>\n📍 <code>{city}</code>\n\n"
    lvl_block = f"<blockquote><b>🏆 УРОВЕНЬ {lvl}</b></blockquote>\n"
    
    cat_block = ""
    if categories:
        cat_block = f"\n<b>🎯 ИНТЕРЕСЫ</b>\n"
        for c in categories.split(', '): cat_block += f"• <i>{c}</i>\n"
            
    bio_block = f"\n<b>📝 О СЕБЕ</b>\n<blockquote>{bio}</blockquote>" if bio else ""
    
    final_caption = header + main_info + lvl_block + cat_block + bio_block
    
    try:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="Смотреть в боте", url=f"https://t.me/{(await bot.get_me()).username}")]])
        await bot.send_photo(CHANNEL_ID, photo_id, caption=final_caption, parse_mode="HTML", reply_markup=kb)
        await message.answer("✅ Анкета дня опубликована в канале!")
    except Exception as e:
        await message.answer(f"Ошибка публикации: {e}")