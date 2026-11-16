import asyncio
from datetime import datetime, timedelta
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards import get_main_kb, edit_profile_kb, profile_kb, get_ad_kb, premium_menu_kb, deluxe_customization_kb
from database import (
    get_user, get_stats, get_next_profile, mark_ad_seen, get_unread_like, 
    add_like, add_skip, count_likers, get_all_likers, get_level_info, deactivate_user,
    check_premium_status, DB_NAME, get_declension, get_pronoun
)
from handlers_chat import handle_chat_message
from config import ADMIN_ID, CHANNEL_ID, PREMIUM_TIERS

router = Router()

class EditProfile(StatesGroup):
    name = State()
    age = State()
    city = State()
    bio = State()
    photo = State()
    tag = State()

@router.message(F.text == "📊 Моя статистика")
async def show_stats(message: types.Message):
    stats = await get_stats(message.from_user.id)
    text = (
        "📊 <b>Твоя статистика в Twinz</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👀 <b>Просмотров анкеты:</b> {stats['views']}\n"
        f"❤️ <b>Лайков получено:</b> {stats['likes_received']}\n"
        f"👎 <b>Пропусков (дизлайков):</b> {stats['skips_received']}\n\n"
        f"🔥 <b>Твоя конверсия:</b> {stats['conversion']}%\n"
        f"<i>(Это процент людей, которым ты понравился из всех, кто видел твою анкету)</i>\n\n"
        f"🏆 <b>Место в топе:</b> #{stats['position']} по лайкам\n"
        f"💌 <b>Лайков поставил(а):</b> {stats['likes_given']}\n"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "💎 Premium")
async def premium_menu(message: types.Message):
    prem_type = await check_premium_status(message.from_user.id)
    
    text = "💎 <b>Управление подпиской</b>\n\n"
    if prem_type:
        info = PREMIUM_TIERS[prem_type]
        text += f"🏆 Ваш статус: <b>{info['name']}</b>\n\n"
        text += "<b>Ваши возможности:</b>\n"
        for line in info['desc'].split('\n'):
            text += f"{line}\n"
    else:
        text += "Выберите подходящий тариф:\n\n"
        text += f"<b>💎 Standard ({PREMIUM_TIERS['standard']['price']}₽)</b>\n{PREMIUM_TIERS['standard']['desc']}\n\n"
        text += f"<b>👑 Deluxe ({PREMIUM_TIERS['deluxe']['price']}₽)</b>\n{PREMIUM_TIERS['deluxe']['desc']}"
        
    await message.answer(text, reply_markup=premium_menu_kb(prem_type), parse_mode="HTML")

@router.callback_query(F.data == "premium_back")
async def premium_back(cb: types.CallbackQuery):
    await premium_menu(cb.message)

@router.callback_query(F.data == "deluxe_customization")
async def deluxe_cust_menu(cb: types.CallbackQuery):
    await cb.message.edit_text("🎨 <b>Эксклюзивные настройки Deluxe</b>", reply_markup=deluxe_customization_kb(), parse_mode="HTML")

@router.message(F.text == "🎁 Ежедневный бонус")
async def daily_bonus(message: types.Message):
    from database import add_exp
    import aiosqlite
    user_id = message.from_user.id
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT last_claim, streak FROM bonuses WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
        if row:
            last_claim, streak = row
            if last_claim == today:
                return await message.answer("🎁 Ты уже получал бонус сегодня. Возвращайся завтра!")
            if last_claim == yesterday: new_streak = streak + 1
            else: new_streak = 1
        else: new_streak = 1
            
        await db.execute("INSERT OR REPLACE INTO bonuses (user_id, last_claim, streak) VALUES (?, ?, ?)", (user_id, today, new_streak))
        await db.commit()
        
    if new_streak == 7:
        prem_until = datetime.now() + timedelta(days=1)
        prem_str = prem_until.strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE users SET is_premium = 1, premium_until = ? WHERE user_id = ?", (prem_str, user_id))
            await db.commit()
        reward_text = "🎉 <b>Стрик 7 дней!</b> Тебе выдан Premium на 1 день!"
    else:
        await add_exp(user_id, 30)
        reward_text = "Тебе начислено <b>+30 XP</b>!"
        
    await message.answer(f"🎁 <b>Бонус получен!</b>\nТвой стрик: {new_streak} дней.\n\n{reward_text}", parse_mode="HTML")

@router.message(F.text == "🔍 Поиск анкет")
async def show_profile(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user or user[11] == 1: return
    if user[10] == 0: return await message.answer("Твоя анкета скрыта. Нажми /start.")

    if user[12] == 0:
        await mark_ad_seen(message.from_user.id)
        await message.answer("✨ <b>Хочешь получать больше лайков?</b>\nПодпишись на наш канал <b>Twinz</b> и получай 50 лайков в день!", reply_markup=get_ad_kb(), parse_mode="HTML")
        return

    unread_liker = await get_unread_like(message.from_user.id)
    if unread_liker:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="👀 Посмотреть кто это", callback_data=f"check_like_{unread_liker}")]])
        await message.answer("💌 <b>У тебя новая симпатия!</b>\nКому-то понравилась твоя анкета. Посмотрим кто это?", reply_markup=kb, parse_mode="HTML")
        return
    
    my_prem = await check_premium_status(message.from_user.id)
    profile, is_prem_target = await get_next_profile(message.from_user.id, user[3], user[4], user[5], user[9], my_prem)
    
    if not profile: return await message.answer("😔 Анкеты закончились. Загляни позже!")
        
    try:
        _, username, age, gender, looking_for, city, name, bio, photo_id, categories, _, _, _, is_this_prem, _, _, _, tag, hide_prem, coins, farm_lvl, last_claim, hide_age, vip_badge, ghost_mode, prem_lvl, prem_type_target = profile[:27]
    except ValueError:
        _, username, age, gender, looking_for, city, name, bio, photo_id, categories, _, _, _, is_this_prem, _, _, _, tag, hide_prem = profile[:19]
        prem_type_target = None 
    
    lvl, exp = await get_level_info(profile[0])
    next_lvl_exp = lvl * 100
    filled = int((exp / next_lvl_exp) * 10)
    bar = "█" * filled + "░" * (10 - filled)
    
    header = ""
    if prem_type_target == "deluxe":
        header = "<b>👑 DELUXE АНКЕТА</b> <i>(Эксклюзив)</i>\n"
    elif prem_type_target == "standard":
        header = "<b>💎 STANDARD АНКЕТА</b>\n"
    else:
        header = "<b>👤 АНКЕТА</b>\n"
        
    header += "━━━━━━━━━━━━━━━━━━━━\n"
    
    name_str = f"{name}, {age}"
    if tag: 
        if prem_type_target == "deluxe":
            name_str += f"  <code>✨[{tag}]✨</code>"
        else:
            name_str += f"  <code>[{tag}]</code>"
    
    main_info = f"<b>{name_str}</b>\n📍 <code>{city}</code>\n\n"
    lvl_block = f"<blockquote><b>🏆 УРОВЕНЬ {lvl}</b>\n<code>[{bar}]</code> {exp} / {next_lvl_exp} XP</blockquote>\n"
    
    cat_block = ""
    if categories:
        cat_block = f"\n<b>🎯 ИНТЕРЕСЫ</b>\n"
        for c in categories.split(', '): cat_block += f"• <i>{c}</i>\n"
            
    bio_block = f"\n<b>📝 О СЕБЕ</b>\n<blockquote>{bio}</blockquote>" if bio else ""
    
    final_caption = header + main_info + lvl_block + cat_block + bio_block
    await message.answer_photo(photo_id, caption=final_caption, parse_mode="HTML", reply_markup=profile_kb(profile[0]))

@router.message(F.text == "👤 Мой профиль")
async def my_profile(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user: return
    
    my_prem_type = await check_premium_status(message.from_user.id)
    is_admin = (message.from_user.id == ADMIN_ID)
    
    status = "🟢 В поиске" if user[10] == 1 else "⚪ Скрыта"
    lvl, exp = await get_level_info(user[0])
    next_lvl_exp = lvl * 100
    filled = int((exp / next_lvl_exp) * 10)
    bar = "█" * filled + "░" * (10 - filled)
    
    stats = await get_stats(user[0])
    
    if is_admin:
        header = "<b>🛡️ АДМИНИСТРАТОР TWINZ</b>\n<i>Полный контроль над системой</i>\n"
    elif my_prem_type == "deluxe":
        header = "<b>👑 DELUXE ПРОФИЛЬ</b>\n<i>Максимальные возможности!</i>\n"
    elif my_prem_type == "standard":
        header = "<b>💎 STANDARD ПРОФИЛЬ</b>\n<i>Расширенные возможности</i>\n"
    else:
        header = "<b>👤 ПРОФИЛЬ</b>\n"
        
    header += "━━━━━━━━━━━━━━━━━━━━\n"
    
    name_str = f"{user[6]}, {user[2]}"
    if user[17]: name_str += f"  <code>[{user[17]}]</code>"
    
    main_info = f"<b>{name_str}</b>\n📍 <code>{user[5]}</code>\n\n"
    lvl_block = f"<blockquote><b>🏆 УРОВЕНЬ {lvl}</b>\n<code>[{bar}]</code> {exp} / {next_lvl_exp} XP\n<i>До следующего уровня: {next_lvl_exp - exp} XP</i></blockquote>\n"
    
    cat_block = ""
    if user[9]:
        cat_block = f"\n<b>🎯 ИНТЕРЕСЫ</b>\n"
        for c in user[9].split(', '): cat_block += f"• <i>{c}</i>\n"
            
    bio_block = f"\n<b>📝 О СЕБЕ</b>\n<blockquote>{user[7]}</blockquote>\n" if user[7] else ""
    
    stat_block = f"\n📊 <b>Статистика:</b>\n❤️ {stats['likes_received']} | 👎 {stats['skips_received']} | 🔥 {stats['conversion']}%\n"
    
    footer = f"\n┗ 📊 Статус: <b>{status}</b>"
    
    await message.answer_photo(user[8], caption=header + main_info + lvl_block + cat_block + bio_block + stat_block + footer, parse_mode="HTML", reply_markup=edit_profile_kb())

@router.callback_query(F.data.startswith("hello_"))
async def hello_handler(callback: types.CallbackQuery, bot: Bot):
    target_id = int(callback.data.split("_")[1])
    me = await get_user(callback.from_user.id)
    
    try:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="❤️ Ответить взаимностью", callback_data=f"like_{callback.from_user.id}"),
             types.InlineKeyboardButton(text="👎 Пропустить", callback_data=f"skip_{callback.from_user.id}")]
        ])
        await bot.send_message(
            target_id, 
            f"👋 <b>Тебе отправили привет!</b>\n\nКому-то понравилась твоя анкета, и он(а) хочет пообщаться.\nНажми «Ответить», чтобы открыть контакты.", 
            parse_mode="HTML", reply_markup=kb
        )
        await callback.answer("Привет отправлен! Если человек ответит взаимностью, вы увидите контакты.")
    except:
        await callback.answer("Не удалось отправить привет.", show_alert=True)
        
    await show_profile(callback.message)

class MsgSend(StatesGroup):
    text = State()

@router.callback_query(F.data.startswith("msg_"))
async def msg_start(callback: types.CallbackQuery, state: FSMContext):
    target_id = int(callback.data.split("_")[1])
    await state.update_data(msg_target=target_id)
    await callback.message.answer("💌 Напиши сообщение:")
    await state.set_state(MsgSend.text)
    await callback.message.delete()

@router.message(MsgSend.text)
async def msg_send(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    target_id = data['msg_target']
    me = await get_user(message.from_user.id)
    if not me: return
    try:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="❤️ Ответить", callback_data=f"like_{message.from_user.id}"),
             types.InlineKeyboardButton(text="👎 Пропустить", callback_data=f"skip_{message.from_user.id}")]
        ])
        await bot.send_message(target_id, f"💌 <b>Сообщение:</b>\n\n<i>{message.text}</i>", parse_mode="HTML", reply_markup=kb)
        await message.answer("✅ Отправлено!")
    except Exception: 
        await message.answer("❌ Ошибка.")
    await state.clear()

@router.callback_query(F.data == "edit_profile")
async def edit_profile_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("Что хочешь изменить?", reply_markup=edit_profile_kb())

@router.callback_query(F.data.startswith("edit_"))
async def edit_profile_start(callback: types.CallbackQuery, state: FSMContext):
    action = callback.data.split("_")[1]
    if action == "name":
        await callback.message.answer("Введи новое имя:")
        await state.set_state(EditProfile.name)
    elif action == "age":
        await callback.message.answer("Введи новый возраст (числом):")
        await state.set_state(EditProfile.age)
    elif action == "city":
        await callback.message.answer("Введи новый город (только Крым):")
        await state.set_state(EditProfile.city)
    elif action == "bio":
        await callback.message.answer("Введи новое описание:")
        await state.set_state(EditProfile.bio)
    elif action == "photo":
        await callback.message.answer("Отправь новое фото:")
        await state.set_state(EditProfile.photo)
    await callback.message.delete()

@router.message(EditProfile.name)
async def edit_name(message: types.Message, state: FSMContext):
    import aiosqlite
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET name = ? WHERE user_id = ?", (message.text, message.from_user.id))
        await db.commit()
    await message.answer("✅ Имя изменено!", reply_markup=get_main_kb())
    await state.clear()

@router.message(EditProfile.age)
async def edit_age(message: types.Message, state: FSMContext):
    import aiosqlite
    if not message.text.isdigit(): return await message.answer("⚠️ Введи число!")
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET age = ? WHERE user_id = ?", (int(message.text), message.from_user.id))
        await db.commit()
    await message.answer("✅ Возраст изменен!", reply_markup=get_main_kb())
    await state.clear()

@router.message(EditProfile.city)
async def edit_city(message: types.Message, state: FSMContext):
    import aiosqlite
    from config import find_city
    city_name = find_city(message.text)
    if not city_name: return await message.answer("❌ Город не найден в Крыму.")
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET city = ? WHERE user_id = ?", (city_name, message.from_user.id))
        await db.commit()
    await message.answer("✅ Город изменен!", reply_markup=get_main_kb())
    await state.clear()

@router.message(EditProfile.bio)
async def edit_bio(message: types.Message, state: FSMContext):
    import aiosqlite
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET bio = ? WHERE user_id = ?", (message.text, message.from_user.id))
        await db.commit()
    await message.answer("✅ Описание изменено!", reply_markup=get_main_kb())
    await state.clear()

@router.message(EditProfile.photo, F.photo)
async def edit_photo(message: types.Message, state: FSMContext):
    import aiosqlite
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET photo_id = ? WHERE user_id = ?", (message.photo[-1].file_id, message.from_user.id))
        await db.commit()
    await message.answer("✅ Фото изменено!", reply_markup=get_main_kb())
    await state.clear()

@router.message(F.text == "💌 Кто меня лайкнул")
async def who_liked_me(message: types.Message):
    likers = await get_all_likers(message.from_user.id)
    if not likers:
        return await message.answer("😔 Пока никто не оценил твою анкету. Заполни профиль красивее!")
        
    await message.answer(f"👀 <b>Твоя анкета понравилась {len(likers)} людям!</b>\nВот они:", parse_mode="HTML")
    
    for l in likers[:5]: 
        _, username, age, gender, looking_for, city, name, bio, photo_id, categories = l[:10]
        lvl, exp = await get_level_info(l[0])
        builder = types.InlineKeyboardBuilder()
        builder.button(text="❤️ Ответить взаимностью", callback_data=f"like_{l[0]}")
        builder.button(text="👎 Пропустить", callback_data=f"skip_{l[0]}")
        caption = f"<b>{name}, {age}</b>\n🏆 Уровень: {lvl}\n📍 {city}"
        await message.answer_photo(photo_id, caption=caption, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.message(F.text == "🎁 Пригласить друга")
async def invite_friend(message: types.Message, bot: Bot):
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={message.from_user.id}"
    text = f"🎁 <b>Приглашай друзей и получай опыт!</b>\n\nЗа каждого друга по твоей ссылке ты получаешь <b>+50 XP</b>.\n\nТвоя ссылка:\n<code>{link}</code>"
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "🛑 Скрыть анкету")
async def stop_search(message: types.Message):
    await deactivate_user(message.from_user.id)
    await message.answer("Твоя анкета скрыта из поиска.", reply_markup=get_main_kb())

@router.callback_query(F.data.startswith("check_like_"))
async def check_like_handler(callback: types.CallbackQuery):
    liker_id = int(callback.data.split("_")[2])
    liker = await get_user(liker_id)
    if not liker: 
        await callback.message.delete()
        return 
        
    import aiosqlite
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO likes (from_id, to_id) VALUES (?, ?)", (callback.from_user.id, liker_id))
        await db.commit()
        
    _, username, age, gender, looking_for, city, name, bio, photo_id, categories = liker[:10]
    contact = f"@{username}" if username else f"[Ссылка](tg://user?id={liker_id})"
    await callback.message.answer_photo(photo_id, caption=f"💘 <b>Взаимная симпатия!</b>\n\nПиши первым: {contact}", parse_mode="HTML")
    await callback.message.delete()

@router.callback_query(F.data.startswith("like_"))
async def like_handler(callback: types.CallbackQuery, bot: Bot):
    target_id = int(callback.data.split("_")[1])
    my_id = callback.from_user.id
    
    me = await get_user(my_id)
    is_match = await add_like(my_id, target_id)
    
    if is_match:
        target_user = await get_user(target_id)
        my_contact = f"@{me[1]}" if me[1] else f"[Ссылка](tg://user?id={my_id})"
        target_contact = f"@{target_user[1]}" if target_user[1] else f"[Ссылка](tg://user?id={target_id})"
        
        await callback.message.answer(f"💘 <b>Взаимная симпатия!</b>\n\nКонтакт: {target_contact}", parse_mode="HTML")
        try: 
            await bot.send_message(target_id, f"💘 <b>Взаимная симпатия!</b>\n\nКонтакт: {my_contact}", parse_mode="HTML")
        except Exception: pass
    else:
        likes_count = await count_likers(target_id)
        my_gender_word = get_declension(likes_count, me[3])
        target_user = await get_user(target_id)
        pronoun = get_pronoun(target_user[3])
        try:
            await bot.send_message(target_id, f"❤️ Ты понравился {likes_count} {my_gender_word}. Показать {pronoun}?", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="👀 Показать", callback_data=f"like_{my_id}"), types.InlineKeyboardButton(text="👎 Скрыть", callback_data=f"skip_{my_id}")]
            ]))
        except Exception: pass
            
    await callback.answer("❤️ Лайк отправлен!")

@router.callback_query(F.data.startswith("skip_"))
async def skip_handler(callback: types.CallbackQuery):
    target_id = int(callback.data.split("_")[1])
    await add_skip(callback.from_user.id, target_id)
    
    try: await callback.message.edit_text("👎 Пропущено.")
    except Exception: pass
    try: await callback.message.delete()
    except Exception: pass
    await show_profile(callback.message)

@router.message(F.text & ~F.text.startswith("/") & ~F.text.in_([
    "🔍 Поиск анкет", "🎭 Анонимный чат", "👤 Мой профиль", "📊 Моя статистика", "💎 Premium", 
    "💌 Кто меня лайкнул", "🎁 Пригласить друга", "🎁 Ежедневный бонус", 
    "🎟 Активировать промокод", "📜 Правила", "🛑 Скрыть анкету", "💰 Экономика",
    "✅ Я согласен с правилами", "⏭ Пропустить описание",
    "👩 Я девушка", "👨 Я парень", "👩 Девушки", "👨 Парни", "🌈 Всё равно"
]))
async def handle_text(message: types.Message):
    my_id = message.from_user.id
    import aiosqlite
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user1_id, user2_id FROM active_chats WHERE user1_id = ? OR user2_id = ?", (my_id, my_id)) as cur:
            if await cur.fetchone():
                await handle_chat_message(message)
                return
                
        code = message.text.upper()
        async with db.execute("SELECT days, max_uses, used_count FROM promocodes WHERE code = ?", (code,)) as cur:
            promo = await cur.fetchone()
            
        if promo:
            days, max_uses, used_count = promo
            if used_count >= max_uses:
                return await message.answer("❌ Этот промокод больше не действителен (закончились активации).")
                
            prem_until = datetime.now() + timedelta(days=days)
            prem_until_str = prem_until.strftime("%Y-%m-%d %H:%M:%S")
            
            await db.execute("UPDATE users SET is_premium = 1, premium_until = ? WHERE user_id = ?", (prem_until_str, my_id))
            await db.execute("UPDATE promocodes SET used_count = used_count + 1 WHERE code = ?", (code,))
            await db.commit()
            
            await message.answer(f"🎉 <b>Промокод активирован!</b>\nТебе выдан Premium на {days} дней!", parse_mode="HTML", reply_markup=get_main_kb())