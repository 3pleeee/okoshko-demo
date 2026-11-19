import asyncio, os, sqlite3
from datetime import date, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

SERVICES = {
    "cut": "Haircut - $25",
    "beard": "Beard trim - $15",
    "combo": "Cut + beard - $35",
}
HOURS = ["10:00", "12:00", "14:00", "16:00", "18:00"]
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

db = sqlite3.connect("bookings.db")
db.execute("CREATE TABLE IF NOT EXISTS bookings "
           "(user_id INT, name TEXT, service TEXT, day TEXT, hour TEXT)")
dp = Dispatcher()


class Booking(StatesGroup):
    service = State()
    day = State()
    hour = State()


def keyboard(items, prefix):
    kb = InlineKeyboardBuilder()
    for key, label in items:
        kb.button(text=label, callback_data=f"{prefix}:{key}")
    return kb.adjust(1).as_markup()


def taken(day):
    rows = db.execute("SELECT hour FROM bookings WHERE day = ?", (day,))
    return {row[0] for row in rows}


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.set_state(Booking.service)
    await message.answer("Hi! What would you like to book?",
                         reply_markup=keyboard(SERVICES.items(), "svc"))


@dp.callback_query(Booking.service, F.data.startswith("svc:"))
async def pick_service(call: CallbackQuery, state: FSMContext):
    await state.update_data(service=call.data.split(":")[1])
    days = [date.today() + timedelta(days=i) for i in range(1, 6)]
    buttons = [(d.isoformat(), d.strftime("%a %d %b")) for d in days]
    await state.set_state(Booking.day)
    await call.message.edit_text("Pick a day:",
                                 reply_markup=keyboard(buttons, "day"))


@dp.callback_query(Booking.day, F.data.startswith("day:"))
async def pick_day(call: CallbackQuery, state: FSMContext):
    day = call.data.split(":", 1)[1]
    free = [h for h in HOURS if h not in taken(day)]
    if not free:
        return await call.answer("Fully booked, try another day",
                                 show_alert=True)
    await state.update_data(day=day)
    await state.set_state(Booking.hour)
    await call.message.edit_text("Pick a time:",
                                 reply_markup=keyboard([(h, h) for h in free], "hour"))


@dp.callback_query(Booking.hour, F.data.startswith("hour:"))
async def pick_hour(call: CallbackQuery, state: FSMContext):
    hour = call.data.split(":", 1)[1]
    data = await state.get_data()
    if hour in taken(data["day"]):
        return await call.answer("Someone just took this slot",
                                 show_alert=True)
    name = call.from_user.full_name
    db.execute("INSERT INTO bookings VALUES (?, ?, ?, ?, ?)",
               (call.from_user.id, name, data["service"], data["day"], hour))
    db.commit()
    await state.clear()
    text = f"{SERVICES[data['service']]}\n{data['day']} at {hour}"
    await call.message.edit_text(f"Booked! See you soon.\n\n{text}")
    if OWNER_ID:
        await call.bot.send_message(OWNER_ID, f"New booking from {name}:\n{text}")


async def main():
    await dp.start_polling(Bot(os.environ["BOT_TOKEN"]))


if __name__ == "__main__":
    asyncio.run(main())
