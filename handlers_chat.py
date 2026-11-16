from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from keyboards import get_main_kb, chat_kb, chat_gender_kb
from database import get_user
from config import chat_logger, ADMIN_ID

router = Router()

@router.message(F.text == "🎭 Анонимный чат")
async def anon_chat_start(message: types.Message):
    await message.answer("🎭 <b>Анонимный чат</b>\n\nС кем хочешь пообщаться?", reply_markup=chat_gender_kb, parse_mode="HTML")

@router.callback_query(F.data.startswith("chat_find_"))
async def anon_chat_search(callback: types.CallbackQuery):
    from main import bot
    import aiosqlite
    from database import DB_NAME
    
    my_id = callback.from_user.id
    pref = callback.data.replace("chat_find_", "")
    me = await get_user(my_id)
    if not me: return
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user2_id FROM active_chats WHERE user1_id = ? OR user2_id = ?", (my_id, my_id)) as cur:
            if await cur.fetchone():
                return await callback.answer("Ты уже в чате! Заверши текущий.", show_alert=True)

        query = "SELECT user_id FROM chat_queue WHERE user_id != ?"
        params = [my_id]
        if pref != "all":
            query += " AND gender_pref = ?"
            params.append(pref)
        query += " LIMIT 1"
        
        async with db.execute(query, params) as cur:
            partner = await cur.fetchone()
            
        if partner:
            partner_id = partner[0]
            await db.execute("DELETE FROM chat_queue WHERE user_id = ?", (partner_id,))
            await db.execute("INSERT INTO active_chats (user1_id, user2_id) VALUES (?, ?)", (my_id, partner_id))
            await db.commit()
            
            await callback.message.edit_text("✅ <b>Собеседник найден!</b>\nМожете начинать общение. Для выхода используйте кнопки ниже.", parse_mode="HTML")
            
            kb = chat_kb()
            try: 
                await bot.send_message(partner_id, "✅ <b>Собеседник найден!</b>\nМожете начинать общение.", reply_markup=kb, parse_mode="HTML")
            except: pass
            await callback.message.answer("Твой чат начался!", reply_markup=kb)
        else:
            await db.execute("INSERT OR REPLACE INTO chat_queue (user_id, gender_pref) VALUES (?, ?)", (my_id, pref))
            await db.commit()
            await callback.message.edit_text("🔍 <b>Ищем собеседника...</b>\nКак только кто-то зайдет, мы вас соединим. Ожидайте.", parse_mode="HTML")
            await callback.answer()

@router.callback_query(F.data == "chat_stop")
async def anon_chat_stop(callback: types.CallbackQuery):
    from main import bot
    import aiosqlite
    from database import DB_NAME
    
    my_id = callback.from_user.id
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user1_id, user2_id FROM active_chats WHERE user1_id = ? OR user2_id = ?", (my_id, my_id)) as cur:
            row = await cur.fetchone()
            
        if row:
            u1, u2 = row
            partner_id = u2 if u1 == my_id else u1
            await db.execute("DELETE FROM active_chats WHERE user1_id = ? OR user2_id = ?", (my_id, my_id))
            await db.commit()
            
            await callback.message.edit_text("🛑 Ты завершил чат.")
            try: 
                await bot.send_message(partner_id, "🛑 Собеседник завершил чат.", reply_markup=get_main_kb())
            except: pass
        else:
            await db.execute("DELETE FROM chat_queue WHERE user_id = ?", (my_id,))
            await db.commit()
            await callback.message.edit_text("🛑 Поиск отменен.")
            
    await callback.message.answer("Ты в главном меню.", reply_markup=get_main_kb())

@router.callback_query(F.data == "chat_next")
async def anon_chat_next(callback: types.CallbackQuery):
    from main import bot
    import aiosqlite
    from database import DB_NAME
    
    my_id = callback.from_user.id
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user1_id, user2_id FROM active_chats WHERE user1_id = ? OR user2_id = ?", (my_id, my_id)) as cur:
            row = await cur.fetchone()
            
        if row:
            u1, u2 = row
            partner_id = u2 if u1 == my_id else u1
            await db.execute("DELETE FROM active_chats WHERE user1_id = ? OR user2_id = ?", (my_id, my_id))
            await db.commit()
            try: 
                await bot.send_message(partner_id, "🔄 Собеседник ищет нового партнера...", reply_markup=get_main_kb())
            except: pass
            
    await callback.message.edit_text("🔄 <b>Ищем нового собеседника...</b>", parse_mode="HTML")
    await anon_chat_start(callback.message)

@router.callback_query(F.data == "chat_report")
async def chat_report(callback: types.CallbackQuery):
    from main import bot
    import aiosqlite
    from database import DB_NAME
    
    my_id = callback.from_user.id
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user1_id, user2_id FROM active_chats WHERE user1_id = ? OR user2_id = ?", (my_id, my_id)) as cur:
            row = await cur.fetchone()
            
        if not row:
            return await callback.answer("Чат не найден.", show_alert=True)
            
        u1, u2 = row
        partner_id = u2 if u1 == my_id else u1
        
        admin_text = (
            f"🚨 <b>ЖАЛОБА В АНОНИМНОМ ЧАТЕ!</b>\n"
            f"От: {callback.from_user.full_name} (ID: {my_id})\n"
            f"На: ID {partner_id}\n\n"
            f"Последние сообщения в чате можно посмотреть в файле <code>chat_logs.txt</code>."
        )
        admin_kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🗑 Забанить нарушителя", callback_data=f"admin_block_{partner_id}")],
            [types.InlineKeyboardButton(text="✅ Отклонить", callback_data="admin_ignore")]
        ])
        try:
            await bot.send_message(ADMIN_ID, admin_text, reply_markup=admin_kb, parse_mode="HTML")
            await callback.message.answer("✅ Жалоба отправлена администратору. Спасибо!")
        except: 
            pass

async def handle_chat_message(message: types.Message):
    from main import bot
    import aiosqlite
    from database import DB_NAME, get_user
    
    my_id = message.from_user.id
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user1_id, user2_id FROM active_chats WHERE user1_id = ? OR user2_id = ?", (my_id, my_id)) as cur:
            row = await cur.fetchone()
            
    if row:
        u1, u2 = row
        partner_id = u2 if u1 == my_id else u1
        
        try: 
            await bot.send_message(partner_id, f"💬 <b>Аноним:</b>\n{message.text}", parse_mode="HTML")
        except: 
            await message.answer("❌ Не удалось отправить сообщение. Собеседник заблокировал бота.")
            
        try:
            sender = await get_user(my_id)
            receiver = await get_user(partner_id)
            sender_name = f"@{sender[1]} ({my_id})" if sender and sender[1] else f"ID: {my_id}"
            receiver_name = f"@{receiver[1]} ({partner_id})" if receiver and receiver[1] else f"ID: {partner_id}"
            
            clean_text = message.text.replace("\n", " ")
            log_msg = f"ОТ: {sender_name} | КОМУ: {receiver_name} | ТЕКСТ: {clean_text}"
            chat_logger.info(log_msg)
        except Exception as e: 
            print(f"Ошибка записи лога в файл: {e}")