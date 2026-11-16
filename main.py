import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from database import init_db
from config import TOKEN
from handlers_registration import router as reg_router
from handlers_main import router as main_router
from handlers_chat import router as chat_router
from handlers_economy import router as econ_router
from handlers_admin import router as admin_router

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

dp.include_router(reg_router)      
dp.include_router(chat_router)     
dp.include_router(econ_router)     
dp.include_router(admin_router)    
dp.include_router(main_router)     

async def main():
    print("Инициализация базы данных...")
    await init_db()
    print("База данных готова. Запуск бота...")
    await asyncio.sleep(0.5)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())