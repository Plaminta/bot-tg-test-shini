from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards import gender_kb, pref_kb, skip_bio_kb, rules_agree_kb, categories_kb, get_main_kb
from database import save_user, add_exp, get_user
from config import RULES_TEXT, find_city

router = Router()

class Reg(StatesGroup):
    age = State()
    gender = State()
    looking_for = State()
    city = State()
    name = State()
    bio = State()
    photo = State()
    categories = State()

@router.message(CommandStart(deep_link=True))
async def start_ref(message: types.Message, command: CommandStart, state: FSMContext):
    args = command.args
    user = await get_user(message.from_user.id)
    
    # Если пользователь уже есть и активен - просто показываем меню
    if user and user[10] == 1: 
        if user[11] == 1: return await message.answer("🚫 Вы заблокированы.")
        return await message.answer("👋 С возвращением!", reply_markup=get_main_kb())

    referrer_id = None
    if args and args.isdigit():
        referrer_id = int(args)
        if referrer_id == message.from_user.id: referrer_id = None 

    await state.update_data(referrer_id=referrer_id)
    await message.answer(RULES_TEXT, parse_mode="HTML", reply_markup=rules_agree_kb)
    await state.set_state(Reg.age)

@router.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if user and user[10] == 1:
        if user[11] == 1: return await message.answer("🚫 Вы заблокированы.")
        return await message.answer("👋 С возвращением!", reply_markup=get_main_kb())
    
    await state.update_data(referrer_id=None)
    await message.answer(RULES_TEXT, parse_mode="HTML", reply_markup=rules_agree_kb)
    await state.set_state(Reg.age) 

@router.message(F.text == "📜 Правила")
async def show_rules(message: types.Message):
    await message.answer(RULES_TEXT, parse_mode="HTML")

# Обработчик согласия с правилами
@router.message(Reg.age, F.text == "✅ Я согласен с правилами")
async def rules_accepted(message: types.Message, state: FSMContext):
    await message.answer(
        "✨ <b>Добро пожаловать!</b>\nДавай создадим твою анкету.\n\nСколько тебе лет? (введи число от 14 до 99)", 
        parse_mode="HTML", 
        reply_markup=types.ReplyKeyboardRemove()
    )

# Обработчик ввода возраста
@router.message(Reg.age)
async def reg_age(message: types.Message, state: FSMContext):
    try:
        age = int(message.text)
        if not (14 <= age <= 99):
            raise ValueError
    except ValueError:
        return await message.answer("⚠️ Пожалуйста, введи возраст корректным числом (от 14 до 99).")
        
    await state.update_data(age=age)
    await message.answer("Отлично. Выбери свой пол:", reply_markup=gender_kb)
    await state.set_state(Reg.gender)

@router.message(Reg.gender, F.text.in_(["👩 Я девушка", "👨 Я парень"]))
async def reg_gender(message: types.Message, state: FSMContext):
    gender = "girl" if "девушка" in message.text else "boy"
    await state.update_data(gender=gender)
    await message.answer("Кого ты ищешь?", reply_markup=pref_kb)
    await state.set_state(Reg.looking_for)

@router.message(Reg.looking_for, F.text.in_(["👩 Девушки", "👨 Парни", "🌈 Всё равно"]))
async def reg_pref(message: types.Message, state: FSMContext):
    if "Всё равно" in message.text: pref = "all"
    elif "Девушки" in message.text: pref = "girl"
    else: pref = "boy"
    
    await state.update_data(looking_for=pref)
    await message.answer("📍 Из какого ты города? (только Крым)")
    await state.set_state(Reg.city)

@router.message(Reg.city)
async def reg_city(message: types.Message, state: FSMContext):
    city_name = find_city(message.text)
    if not city_name: 
        return await message.answer("❌ Город не найден в списке крымских городов. Попробуй еще раз (например: Симферополь, Севастополь).")
    
    await state.update_data(city=city_name)
    await message.answer("📝 Как тебя зовут?")
    await state.set_state(Reg.name)

@router.message(Reg.name)
async def reg_name(message: types.Message, state: FSMContext):
    if len(message.text) < 2:
        return await message.answer("⚠️ Имя слишком короткое. Введи настоящее имя или никнейм.")
        
    await state.update_data(name=message.text)
    await message.answer("📖 Расскажи о себе пару слов (или нажми кнопку ниже, чтобы пропустить):", reply_markup=skip_bio_kb)
    await state.set_state(Reg.bio)

@router.message(Reg.bio, F.text == "⏭ Пропустить описание")
async def reg_skip_bio(message: types.Message, state: FSMContext):
    await state.update_data(bio="")
    await message.answer("✨ Выбери свои увлечения:", reply_markup=categories_kb([]))
    await state.set_state(Reg.categories)

@router.message(Reg.bio)
async def reg_bio(message: types.Message, state: FSMContext):
    await state.update_data(bio=message.text)
    await message.answer("✨ Выбери свои увлечения:", reply_markup=categories_kb([]))
    await state.set_state(Reg.categories)

@router.callback_query(Reg.categories, F.data.startswith("cat_"))
async def reg_categories(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("categories", [])
    
    if callback.data == "cat_done":
        if not selected: 
            return await callback.answer("Выбери хотя бы одну категорию!", show_alert=True)
        await callback.message.edit_text("📸 Отлично! Теперь отправь свое лучшее фото.")
        await state.set_state(Reg.photo)
        return
    
    cat = callback.data.replace("cat_", "")
    if cat in selected: 
        selected.remove(cat)
    else: 
        selected.append(cat)
        
    await state.update_data(categories=selected)
    await callback.message.edit_reply_markup(reply_markup=categories_kb(selected))

@router.message(Reg.photo, F.photo)
async def reg_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cats = ", ".join(data.get("categories", []))
    referrer_id = data.get("referrer_id", None)
    
    # Сохраняем пользователя
    await save_user(
        message.from_user.id, 
        message.from_user.username, 
        data['age'], 
        data['gender'], 
        data['looking_for'], 
        data['city'], 
        data['name'], 
        data['bio'], 
        message.photo[-1].file_id, 
        cats, 
        referrer_id
    )
    await state.clear()
    
    # Уведомляем реферера
    if referrer_id:
        await add_exp(referrer_id, 50)
        try: 
            from main import bot
            await bot.send_message(referrer_id, f"🎁 По твоей ссылке зарегистрировался новый пользователь!\nТебе начислено <b>+50 XP</b>!", parse_mode="HTML")
        except: pass
    
    text = "🎉 <b>Твоя анкета готова!</b>\n\nДобро пожаловать в Twinz.\nЖелаем найти свою вторую половинку! ❤️"
    await message.answer(text, reply_markup=get_main_kb(), parse_mode="HTML")