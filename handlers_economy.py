import asyncio
from datetime import datetime
from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import get_user
from config import FARM_UPGRADES, MARKET_ITEMS, STOCKS

router = Router()

@router.message(F.text == "💰 Экономика")
async def econ_menu(m: types.Message):
    print("--- БОТ УВИДЕЛ КНОПКУ ЭКОНОМИКА ---")
    u = await get_user(m.from_user.id)
    if not u:
        print("--- ОШИБКА: Пользователь не найден в базе ---")
        return
    try:
        text = f"💰 <b>Твоя экономика</b>\n\n🪙 Баланс: <b>{u[24]}</b> Твинкоинов\n🏡 Ферма: {FARM_UPGRADES[u[25]]['name']}"
        b = InlineKeyboardBuilder()
        b.row(types.InlineKeyboardButton(text="🚜 Ферма", callback_data="farm_open"), types.InlineKeyboardButton(text="🛒 Маркетплейс", callback_data="market_open"))
        b.row(types.InlineKeyboardButton(text="📈 Биржа акций", callback_data="stock_open"))
        await m.answer(text, reply_markup=b.as_markup(), parse_mode="HTML")
        print("--- ОТВЕТ ОТПРАВЛЕН ---")
    except Exception as e:
        print(f"--- ОШИБКА В ЭКОНОМИКЕ: {e} ---")
        
# --- ФЕРМА ---
@router.callback_query(F.data == "farm_open")
async def farm_open(cb: types.CallbackQuery):
    u = await get_user(cb.from_user.id)
    today = datetime.now().strftime("%Y-%m-%d")
    status = "🌙 Ферма спит. Возвращайся завтра!" if u[26] == today else "☀️ Готова к сбору урожая!"
    b = InlineKeyboardBuilder()
    b.row(types.InlineKeyboardButton(text="🧺 Собрать" if u[26] != today else "💤 Отдых", callback_data="farm_claim"))
    b.row(types.InlineKeyboardButton(text="🏗 Улучшить", callback_data="farm_upgrade"))
    b.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="econ_back"))
    await cb.message.edit_text(f"🚜 <b>Ферма: {FARM_UPGRADES[u[25]]['name']}</b>\n\n{status}", reply_markup=b.as_markup(), parse_mode="HTML")

@router.callback_query(F.data == "farm_claim")
async def farm_claim(cb: types.CallbackQuery):
    import aiosqlite
    from database import DB_NAME
    u = await get_user(cb.from_user.id)
    today = datetime.now().strftime("%Y-%m-%d")
    if u[26] == today: return await cb.answer("Уже собрано!", show_alert=True)
    inc = FARM_UPGRADES[u[25]]['income']
    await cb.message.edit_text("🧑‍🌾 Сбор урожая..."); await asyncio.sleep(1)
    await cb.message.edit_text("🌾 Собираем пшеницу..."); await asyncio.sleep(1)
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET coins = coins + ?, last_farm_claim = ? WHERE user_id = ?", (inc, today, cb.from_user.id))
        await db.commit()
    await cb.answer(f"✅ +{inc} 🪙!", show_alert=True)
    await farm_open(cb)

@router.callback_query(F.data == "farm_upgrade")
async def farm_upgrade(cb: types.CallbackQuery):
    import aiosqlite
    from database import DB_NAME
    u = await get_user(cb.from_user.id)
    lvl = u[25]
    if lvl >= 4: return await cb.answer("Максимум!", show_alert=True)
    cost = FARM_UPGRADES[lvl]['next_cost']
    if u[24] < cost: return await cb.answer(f"Нужно {cost} 🪙.", show_alert=True)
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET coins = coins - ?, farm_level = farm_level + 1 WHERE user_id = ?", (cost, cb.from_user.id))
        await db.commit()
    await cb.answer("🏗 Улучшено!", show_alert=True)
    await farm_open(cb)

# --- МАРКЕТПЛЕЙС ---
@router.callback_query(F.data == "market_open")
async def market_open(cb: types.CallbackQuery):
    b = InlineKeyboardBuilder()
    for k, v in MARKET_ITEMS.items(): b.row(types.InlineKeyboardButton(text=f"{v['name']} - {v['price']} 🪙", callback_data=f"buy_{k}"))
    b.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="econ_back"))
    await cb.message.edit_text("🛒 <b>Маркетплейс</b>\nВыбирай:", reply_markup=b.as_markup(), parse_mode="HTML")

@router.callback_query(F.data.startswith("buy_"))
async def buy_item(cb: types.CallbackQuery):
    import aiosqlite
    from database import DB_NAME
    i_id = cb.data.replace("buy_", "")
    u = await get_user(cb.from_user.id)
    item = MARKET_ITEMS[i_id]
    if u[24] < item['price']: return await cb.answer("Мало монет!", show_alert=True)
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET coins = coins - ? WHERE user_id = ?", (item['price'], cb.from_user.id))
        await db.execute("INSERT INTO inventory (user_id, item_id, purchase_date) VALUES (?, ?, ?)", (cb.from_user.id, i_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        if i_id == "premium_day":
            from datetime import timedelta
            prem = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
            await db.execute("UPDATE users SET is_premium = 1, premium_until = ? WHERE user_id = ?", (prem, cb.from_user.id))
        elif i_id == "vip_badge": await db.execute("UPDATE users SET vip_badge = 1 WHERE user_id = ?", (cb.from_user.id,))
        elif i_id == "hide_age": await db.execute("UPDATE users SET hide_age = 1 WHERE user_id = ?", (cb.from_user.id,))
        elif i_id == "ghost_mode": await db.execute("UPDATE users SET ghost_mode = 1 WHERE user_id = ?", (cb.from_user.id,))
        await db.commit()
    await cb.answer(f"✅ Куплено: {item['name']}!", show_alert=True)
    await market_open(cb)

# --- БИРЖА АКЦИЙ ---
@router.callback_query(F.data == "stock_open")
async def stock_open(cb: types.CallbackQuery):
    b = InlineKeyboardBuilder()
    for k, v in STOCKS.items(): b.row(types.InlineKeyboardButton(text=f"{v['name']} | {v['price']} 🪙", callback_data=f"stock_{k}"))
    b.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="econ_back"))
    await cb.message.edit_text("📈 <b>Биржа акций</b>", reply_markup=b.as_markup(), parse_mode="HTML")

@router.callback_query(F.data.startswith("stock_"))
async def stock_act(cb: types.CallbackQuery):
    import aiosqlite
    from database import DB_NAME
    st_id = cb.data.replace("stock_", "")
    if st_id == "open": return
    st = STOCKS[st_id]
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT amount FROM stocks WHERE user_id = ? AND stock_id = ?", (cb.from_user.id, st_id)) as cur:
            r = await cur.fetchone(); amt = r[0] if r else 0
    b = InlineKeyboardBuilder()
    b.row(types.InlineKeyboardButton(text=f"Купить ({st['price']} 🪙)", callback_data=f"buy_stock_{st_id}"))
    if amt > 0: b.row(types.InlineKeyboardButton(text=f"Продать ({st['price']} 🪙)", callback_data=f"sell_stock_{st_id}"))
    b.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="stock_open"))
    await cb.message.edit_text(f"📈 <b>{st['name']}</b>\n💰 Цена: {st['price']}\n📦 У тебя: {amt} шт.", reply_markup=b.as_markup(), parse_mode="HTML")

@router.callback_query(F.data.startswith("buy_stock_"))
async def buy_stock(cb: types.CallbackQuery):
    import aiosqlite
    from database import DB_NAME
    st_id = cb.data.replace("buy_stock_", "")
    u = await get_user(cb.from_user.id)
    if u[24] < STOCKS[st_id]['price']: return await cb.answer("Мало монет!", show_alert=True)
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET coins = coins - ? WHERE user_id = ?", (STOCKS[st_id]['price'], cb.from_user.id))
        await db.execute("INSERT INTO stocks (user_id, stock_id, amount) VALUES (?, ?, 1) ON CONFLICT(user_id, stock_id) DO UPDATE SET amount = amount + 1", (cb.from_user.id, st_id))
        await db.commit()
    await cb.answer("Куплено!", show_alert=True); await stock_act(cb)

@router.callback_query(F.data.startswith("sell_stock_"))
async def sell_stock(cb: types.CallbackQuery):
    import aiosqlite
    from database import DB_NAME
    st_id = cb.data.replace("sell_stock_", "")
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (STOCKS[st_id]['price'], cb.from_user.id))
        await db.execute("UPDATE stocks SET amount = amount - 1 WHERE user_id = ? AND stock_id = ?", (cb.from_user.id, st_id))
        await db.commit()
    await cb.answer("Продано!", show_alert=True); await stock_act(cb)

@router.callback_query(F.data == "econ_back")
async def econ_back(cb: types.CallbackQuery): await econ_menu(cb.message)