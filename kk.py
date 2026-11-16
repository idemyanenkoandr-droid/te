import asyncio, logging, sys, aiosqlite, random
from datetime import datetime
from aiogram import Bot, Dispatcher, F, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, Message, CallbackQuery, FSInputFile
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

TOKEN = "9015162416:AAEixgAFj4s_i50xqXIl5kl9uEVxorQclmA"
ADMIN_ID = 8946102327
DB = "bot.db"
dp = Dispatcher()

COMMUNITY_CHAT_LINK = "https://t.me/+qKIiNFcKUcdlOTcy"
OWNER_LINK = "https://t.me/Greyf_lol"

class AdminStates(StatesGroup):
    waiting_for_sponsor = State()
    waiting_for_broadcast = State()
    waiting_for_min_withdrawal = State()
    waiting_for_ref_reward = State()
    waiting_for_promo_code = State()
    waiting_for_promo_reward = State()
    waiting_for_promo_limit = State()
    waiting_for_check_user = State()
    waiting_for_reject_reason = State()
    waiting_for_balance_user = State()
    waiting_for_balance_amount = State()

class UserStates(StatesGroup):
    waiting_for_promo_input = State()
    waiting_for_game_bet = State()
    waiting_for_withdraw_details = State()
    waiting_for_withdraw_amount = State()
    waiting_for_withdraw_comment = State()

# 4 головні кнопки внизу екрана
main_reply_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👤 Профіль"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="💸 Заробити Stars"), KeyboardButton(text="🎟 Промокод")],
        [KeyboardButton(text="🎲 Ігри (Казино)")]
    ],
    resize_keyboard=True
)

async def db_exec(query, params=(), fetch=None):
    async with aiosqlite.connect(DB) as db:
        async with db.execute(query, params) as cur:
            if fetch == "one": res = await cur.fetchone()
            elif fetch == "all": res = await cur.fetchall()
            else: res = await db.commit()
            return res

async def init_db():
    await db_exec("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    await db_exec("CREATE TABLE IF NOT EXISTS sponsors (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, link TEXT, chat_id TEXT)")
    await db_exec("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, 
        username TEXT, 
        balance REAL DEFAULT 0, 
        earned REAL DEFAULT 0, 
        invited INT DEFAULT 0, 
        joined_date TEXT, 
        join_day TEXT,
        referrer_id INTEGER DEFAULT 0,
        sub_rewarded REAL DEFAULT 0
    )""")
    await db_exec("""CREATE TABLE IF NOT EXISTS promos (
        code TEXT PRIMARY KEY,
        reward REAL,
        max_uses INT,
        used_count INT DEFAULT 0
    )""")
    await db_exec("""CREATE TABLE IF NOT EXISTS promo_activations (
        user_id INTEGER,
        code TEXT,
        PRIMARY KEY(user_id, code)
    )""")
    await db_exec("""CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        amount REAL,
        details TEXT,
        comment TEXT,
        status TEXT DEFAULT 'pending'
    )""")
    
    async with aiosqlite.connect(DB) as db:
        async with db.execute("PRAGMA table_info(users)") as cursor:
            columns = [col[1] for col in await cursor.fetchall()]
        if "referrer_id" not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN referrer_id INTEGER DEFAULT 0")
        if "sub_rewarded" not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN sub_rewarded REAL DEFAULT 0")
        await db.commit()

    defaults = {
        'active_sponsor': '1',
        'min_withdrawal': '50',
        'ref_reward': '2',
        'bot_start_date': datetime.now().strftime("%Y-%m-%d"),
        'casino_status': 'on',
        'casino_win_chance': '50'
    }
    for k, v in defaults.items():
        row = await db_exec("SELECT value FROM settings WHERE key=?", (k,), fetch="one")
        if not row:
            await db_exec("INSERT INTO settings (key, value) VALUES (?, ?)", (k, v))

async def get_active_sponsor():
    sp_id = await db_exec("SELECT value FROM settings WHERE key='active_sponsor'", fetch="one")
    if not sp_id: return None
    return await db_exec("SELECT name, link, chat_id FROM sponsors WHERE id=?", (sp_id[0],), fetch="one")

async def check_sub(bot: Bot, user_id: int, chat_id: str) -> bool:
    try:
        target = chat_id.strip()
        if not target.startswith("-100") and not target.startswith("@") and not target.isdigit():
            target = f"@{target}"
        elif target.isdigit():
            target = int(target)

        m = await bot.get_chat_member(chat_id=target, user_id=user_id)
        return m.status in ["creator", "administrator", "member"]
    except Exception as e:
        print(f"Помилка перевірки підписки для {chat_id}: {e}")
        return False

@dp.message(CommandStart())
async def start(message: Message, bot: Bot):
    user_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    day_str = datetime.now().strftime("%Y-%m-%d")

    args = message.text.split()
    referrer_id = 0
    if len(args) > 1 and args[1].isdigit():
        ref_candidate = int(args[1])
        if ref_candidate != user_id:
            referrer_id = ref_candidate

    existing_user = await db_exec("SELECT user_id, referrer_id FROM users WHERE user_id=?", (user_id,), fetch="one")
    if not existing_user:
        await db_exec(
            "INSERT INTO users (user_id, username, balance, earned, invited, joined_date, join_day, referrer_id, sub_rewarded) VALUES (?, ?, 0, 0, 0, ?, ?, ?, 0)",
            (user_id, username, now_str, day_str, referrer_id)
        )
    else:
        await db_exec("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))

    sponsor = await get_active_sponsor()

    if not sponsor or await check_sub(bot, user_id, sponsor[2]):
        await message.answer(
            f"Вітаю, <b>{message.from_user.full_name}</b>! 🎉\n"
            f"Ти успішно в системі <b>StarsBack</b>.", 
            reply_markup=main_reply_kb, 
            parse_mode=ParseMode.HTML
        )
    else:
        kb_sub = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"📢 {sponsor[0]}", url=sponsor[1])],
            [InlineKeyboardButton(text="🔄 Перевірити підписку ✅", callback_data="check_sub")]
        ])
        await message.answer(
            f"👋 Вітаю! Перед тим як почати користуватися ботом та заробляти зірки, будь ласка, підпишись на наш канал-спонсор нижче:", 
            reply_markup=kb_sub, 
            parse_mode=ParseMode.HTML
        )

@dp.callback_query(F.data == "check_sub")
async def check(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    sponsor = await get_active_sponsor()

    if sponsor and await check_sub(bot, user_id, sponsor[2]):
        user_info = await db_exec("SELECT referrer_id, sub_rewarded FROM users WHERE user_id=?", (user_id,), fetch="one")
        if user_info:
            referrer_id = user_info[0]
            sub_rewarded = user_info[1]
            
            if referrer_id > 0 and sub_rewarded == 0:
                ref_rew_row = await db_exec("SELECT value FROM settings WHERE key='ref_reward'", fetch="one")
                reward_amt = float(ref_rew_row[0]) if ref_rew_row else 2.0
                
                await db_exec("UPDATE users SET balance = balance + ?, earned = earned + ?, invited = invited + 1 WHERE user_id=?", (reward_amt, reward_amt, referrer_id))
                await db_exec("UPDATE users SET sub_rewarded = ? WHERE user_id=?", (reward_amt, user_id))

        await callback.message.answer(
            "✅ <b>Ти успішно підписався на спонсора!</b>\n"
            "Тепер тобі повністю доступний функціонал бота, заробляй зірки, запрошуй друзів та виводь нагороди! 🚀", 
            reply_markup=main_reply_kb, 
            parse_mode=ParseMode.HTML
        )
        try:
            await callback.message.delete()
        except:
            pass
    else:
        user_info = await db_exec("SELECT referrer_id, sub_rewarded FROM users WHERE user_id=?", (user_id,), fetch="one")
        if user_info:
            referrer_id = user_info[0]
            sub_rewarded = user_info[1]
            
            if referrer_id > 0 and sub_rewarded > 0:
                await db_exec("UPDATE users SET balance = MAX(0, balance - ?), earned = MAX(0, earned - ?), invited = MAX(0, invited - 1) WHERE user_id=?", (sub_rewarded, sub_rewarded, referrer_id))
                await db_exec("UPDATE users SET sub_rewarded = 0 WHERE user_id=?", (user_id,))

        await callback.answer("❌ Ви ще не підписалися на канал спонсора!", show_alert=True)

@dp.message(F.text == "💸 Заробити Stars")
async def earn_stars_msg(message: Message, bot: Bot):
    user_id = message.from_user.id
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    
    ref_rew_row = await db_exec("SELECT value FROM settings WHERE key='ref_reward'", fetch="one")
    reward_amt = ref_rew_row[0] if ref_rew_row else "2"

    text = (
        f"💸 <b>Заробіток зірок (Stars)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Запрошуй друзів за своїм посиланням та отримуй <b>{reward_amt} ⭐</b> за кожного підписаного друга!\n\n"
        f"🔗 <b>Твоє реферальне посилання:</b>\n"
        f"<code>{ref_link}</code>"
    )
    await message.answer(text, reply_markup=main_reply_kb, parse_mode=ParseMode.HTML)

@dp.message(F.text == "👤 Профіль")
async def show_profile_msg(message: Message):
    user_id = message.from_user.id
    user = await db_exec("SELECT username, balance, earned, invited, joined_date FROM users WHERE user_id=?", (user_id,), fetch="one")
    min_w = await db_exec("SELECT value FROM settings WHERE key='min_withdrawal'", fetch="one")
    min_limit = float(min_w[0]) if min_w else 50.0

    username = user[0] if user and user[0] else f"@{message.from_user.username}"
    balance = user[1] if user else 0
    earned = user[2] if user else 0
    invited = user[3] if user else 0
    joined = user[4] if user else "Невідомо"

    profile_text = (
        f"👤 <b>Юзернейм:</b> {username}\n"
        f"⭐ <b>Баланс:</b> {balance} Stars\n"
        f"💎 <b>Зароблено всього:</b> {earned} Stars\n"
        f"👥 <b>Запрошено людей:</b> {invited}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📅 <b>Дата реєстрації:</b> {joined}"
    )

    kb_profile = InlineKeyboardMarkup(inline_keyboard=[])
    if balance >= min_limit:
        kb_profile.inline_keyboard.append([InlineKeyboardButton(text="💸 Вивести", callback_data="start_withdraw")])

    try:
        photo = FSInputFile("IMG_0877.jpeg")
        await message.answer_photo(photo=photo, caption=profile_text, reply_markup=kb_profile if kb_profile.inline_keyboard else None, parse_mode=ParseMode.HTML)
    except:
        await message.answer(text=profile_text, reply_markup=kb_profile if kb_profile.inline_keyboard else None, parse_mode=ParseMode.HTML)

# --- ВИПЛАТИ ---
@dp.callback_query(F.data == "start_withdraw")
async def withdraw_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("💳 Введи свій юзернейм або реквізити для виводу:", parse_mode=ParseMode.HTML)
    await state.set_state(UserStates.waiting_for_withdraw_details)
    await callback.answer()

@dp.message(UserStates.waiting_for_withdraw_details)
async def withdraw_details_step(message: Message, state: FSMContext):
    await state.update_data(withdraw_details=message.text.strip())
    await message.answer("⭐ Введи суму зірок, яку хочеш вивести:", parse_mode=ParseMode.HTML)
    await state.set_state(UserStates.waiting_for_withdraw_amount)

@dp.message(UserStates.waiting_for_withdraw_amount)
async def withdraw_amount_step(message: Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        amount = float(message.text.strip())
    except:
        await message.answer("❌ Введи коректне число!")
        return

    user = await db_exec("SELECT balance FROM users WHERE user_id=?", (user_id,), fetch="one")
    balance = user[0] if user else 0
    min_w = await db_exec("SELECT value FROM settings WHERE key='min_withdrawal'", fetch="one")
    min_limit = float(min_w[0]) if min_w else 50.0

    if amount < min_limit or amount > balance:
        await message.answer(f"❌ Сума не може перевищувати баланс ({balance} ⭐) і бути меншою за мінімальний вивід ({min_limit} ⭐).")
        return

    await state.update_data(withdraw_amount=amount)
    
    kb_skip = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустити", callback_data="skip_comment")]
    ])
    await message.answer("💬 Залиш коментар до виплати (або натисни кнопку пропустити):", reply_markup=kb_skip, parse_mode=ParseMode.HTML)
    await state.set_state(UserStates.waiting_for_withdraw_comment)

@dp.message(UserStates.waiting_for_withdraw_comment)
async def withdraw_comment_step(message: Message, state: FSMContext, bot: Bot):
    comment = message.text.strip()
    await finalize_withdrawal(message.from_user.id, message.from_user.username, comment, state, bot, message)

@dp.callback_query(F.data == "skip_comment")
async def skip_comment_cb(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await finalize_withdrawal(callback.from_user.id, callback.from_user.username, "Без коментаря", state, bot, callback.message)
    await callback.answer()

async def finalize_withdrawal(user_id, tg_username, comment, state, bot, message):
    data = await state.get_data()
    details = data.get("withdraw_details")
    amount = data.get("withdraw_amount")
    username_str = f"@{tg_username}" if tg_username else f"ID: {user_id}"

    await db_exec("INSERT INTO withdrawals (user_id, username, amount, details, comment, status) VALUES (?, ?, ?, ?, ?, 'pending')", 
                  (user_id, username_str, amount, details, comment))
    
    await db_exec("UPDATE users SET balance = balance - ? WHERE user_id=?", (amount, user_id))
    await state.clear()

    await message.answer("✅ <b>Заявку на виплату успішно створено!</b>\nАдміністратор перевірить її найближчим часом.", reply_markup=main_reply_kb, parse_mode=ParseMode.HTML)

    admin_text = (
        f"💸 <b>Нова заявка на виплату!</b>\n\n"
        f"👤 Користувач: {username_str} (<code>{user_id}</code>)\n"
        f"⭐ Сума: <b>{amount} Stars</b>\n"
        f"💳 Реквізити: <code>{details}</code>\n"
        f"💬 Коментар: {comment}"
    )
    last_w = await db_exec("SELECT id FROM withdrawals ORDER BY id DESC LIMIT 1", fetch="one")
    w_id = last_w[0]

    kb_admin_w = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Виплатити", callback_data=f"w_pay_{w_id}"), InlineKeyboardButton(text="❌ Відмовити", callback_data=f"w_reject_{w_id}")]
    ])
    try:
        await bot.send_message(ADMIN_ID, admin_text, reply_markup=kb_admin_w, parse_mode=ParseMode.HTML)
    except:
        pass

@dp.callback_query(F.data == "adm_withdrawals_list")
async def adm_withdrawals_list(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    pending = await db_exec("SELECT id, user_id, username, amount, details, comment FROM withdrawals WHERE status='pending'", fetch="all")
    if not pending:
        await callback.message.answer("📭 Наразі немає активних заяв на виплату.")
        await callback.answer()
        return

    for w_id, user_id, username, amount, details, comment in pending:
        text = (
            f"💸 <b>Заявка #{w_id}</b>\n"
            f"👤 Користувач: {username} (<code>{user_id}</code>)\n"
            f"⭐ Сума: <b>{amount} Stars</b>\n"
            f"💳 Реквізити: <code>{details}</code>\n"
            f"💬 Коментар: {comment}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Виплатити", callback_data=f"w_pay_{w_id}"), InlineKeyboardButton(text="❌ Відмовити", callback_data=f"w_reject_{w_id}")]
        ])
        await callback.message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()

@dp.callback_query(F.data.startswith("w_pay_"))
async def admin_pay_withdrawal(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id != ADMIN_ID: return
    w_id = int(callback.data.split("_")[2])
    w = await db_exec("SELECT user_id, amount FROM withdrawals WHERE id=?", (w_id,), fetch="one")
    if not w:
        await callback.answer("❌ Заявку не знайдено!", show_alert=True)
        return
    
    user_id, amount = w
    await db_exec("UPDATE withdrawals SET status='paid' WHERE id=?", (w_id,))
    
    w_row = await db_exec("SELECT value FROM settings WHERE key='total_withdrawn'", fetch="one")
    curr_w = float(w_row[0]) if w_row else 0.0
    await db_exec("INSERT OR REPLACE INTO settings (key, value) VALUES ('total_withdrawn', ?)", (str(curr_w + amount),))

    try:
        await bot.send_message(user_id, f"🎉 <b>Вашу виплату на суму {amount} ⭐ успішно здійснено!</b> Гроші надійшли за реквізитами.", parse_mode=ParseMode.HTML)
    except:
        pass

    await callback.message.edit_text(callback.message.text + "\n\n<b>[СТАТУС: ВИПЛАЧЕНО ✅]</b>", parse_mode=ParseMode.HTML)
    await callback.answer("Виплату підтверджено!")

@dp.callback_query(F.data.startswith("w_reject_"))
async def admin_reject_withdrawal(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    w_id = int(callback.data.split("_")[2])
    await state.update_data(reject_w_id=w_id, reject_msg_id=callback.message.message_id)
    await callback.message.answer("❌ Введи причину відмови виплати:")
    await state.set_state(AdminStates.waiting_for_reject_reason)
    await callback.answer()

@dp.message(AdminStates.waiting_for_reject_reason)
async def process_reject_reason(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id != ADMIN_ID: return
    reason = message.text.strip()
    data = await state.get_data()
    w_id = data.get("reject_w_id")

    w = await db_exec("SELECT user_id, amount FROM withdrawals WHERE id=?", (w_id,), fetch="one")
    if w:
        user_id, amount = w
        await db_exec("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
        await db_exec("UPDATE withdrawals SET status='rejected' WHERE id=?", (w_id,))

        try:
            await bot.send_message(user_id, f"❌ <b>Вашу виплату відхилено!</b>\nПричина: {reason}\nКошти повернено на баланс.", parse_mode=ParseMode.HTML)
        except:
            pass

    await message.answer("✅ Відмову оформлено, кошти повернено користувачу.")
    await state.clear()

# --- СПОНСОРИ (СПИСОК ТА ВИДАЛЕННЯ) ---
@dp.callback_query(F.data == "adm_sponsors_list")
async def adm_sponsors_list(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    sponsors = await db_exec("SELECT id, name, link, chat_id FROM sponsors", fetch="all")
    active_sp = await db_exec("SELECT value FROM settings WHERE key='active_sponsor'", fetch="one")
    active_id = active_sp[0] if active_sp else "1"

    if not sponsors:
        await callback.message.answer("📭 У базі немає жодного спонсора.")
        await callback.answer()
        return

    for s_id, name, link, chat_id in sponsors:
        is_active = " (АКТИВНИЙ ⭐)" if str(s_id) == str(active_id) else ""
        text = (
            f"📢 <b>Спонсор #{s_id}{is_active}</b>\n"
            f"🔹 Назва: {name}\n"
            f"🔗 Посилання: {link}\n"
            f"🆔 Чат ID: <code>{chat_id}</code>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Видалити спонсора", callback_data=f"del_sp_{s_id}")]
        ])
        await callback.message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()

@dp.callback_query(F.data.startswith("del_sp_"))
async def delete_sponsor(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    sp_id = callback.data.split("_")[2]
    await db_exec("DELETE FROM sponsors WHERE id=?", (sp_id,))
    await callback.message.edit_text("✅ Спонсора успішно видалено!", parse_mode=ParseMode.HTML)
    await callback.answer()

# --- ЗМІНА БАЛАНСУ ЮЗЕРА ---
@dp.callback_query(F.data == "adm_change_balance")
async def adm_change_balance_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("💳 Введи ID або юзернейм користувача, якому хочеш змінити баланс:", parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_for_balance_user)
    await callback.answer()

@dp.message(AdminStates.waiting_for_balance_user)
async def process_balance_user(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    query_text = message.text.strip().replace("@", "")

    user = await db_exec("SELECT user_id, username, balance FROM users WHERE user_id=? OR username=?", (query_text, f"@{query_text}"), fetch="one")
    if not user:
        await message.answer("❌ Користувача не знайдено в базі!")
        await state.clear()
        return

    target_id, target_name, curr_bal = user
    await state.update_data(target_user_id=target_id, target_username=target_name)
    await message.answer(f"👤 Користувач: <b>{target_name}</b> (ID: <code>{target_id}</code>)\n⭐ Поточний баланс: <b>{curr_bal} Stars</b>\n\nВведи новий баланс для цього користувача:", parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_for_balance_amount)

@dp.message(AdminStates.waiting_for_balance_amount)
async def process_balance_amount(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    try:
        new_balance = float(message.text.strip())
    except:
        await message.answer("❌ Введи лише число!")
        return

    data = await state.get_data()
    target_id = data.get("target_user_id")
    target_name = data.get("target_username")

    await db_exec("UPDATE users SET balance = ? WHERE user_id=?", (new_balance, target_id))
    await message.answer(f"✅ Баланс користувача <b>{target_name}</b> успішно змінено на <b>{new_balance} Stars</b> ⭐!", parse_mode=ParseMode.HTML)
    await state.clear()

# --- ПЕРЕВІРКА ПОДПИСОК (АНТИ-СКАМ) ---
@dp.callback_query(F.data == "adm_check_subs")
async def adm_check_subs_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("🔍 Введи ID або юзернейм користувача для перевірки його рефералів:", parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_for_check_user)
    await callback.answer()

@dp.message(AdminStates.waiting_for_check_user)
async def process_check_user(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id != ADMIN_ID: return
    query_text = message.text.strip().replace("@", "")

    user = await db_exec("SELECT user_id, username FROM users WHERE user_id=? OR username=?", (query_text, f"@{query_text}"), fetch="one")
    if not user:
        await message.answer("❌ Користувача не знайдено в базі!", reply_markup=main_reply_kb)
        await state.clear()
        return

    target_id, target_name = user
    refs = await db_exec("SELECT user_id, username, joined_date, sub_rewarded FROM users WHERE referrer_id=?", (target_id,), fetch="all")

    if not refs:
        await message.answer(f"👤 Користувач {target_name} (<code>{target_id}</code>) не запросив жодного реферала.", parse_mode=ParseMode.HTML)
        await state.clear()
        return

    sponsor = await get_active_sponsor()
    report = f"📊 <b>Звіт по рефералах користувача {target_name}</b> (ID: <code>{target_id}</code>):\n\n"
    
    active_count = 0
    total_count = len(refs)

    for r_id, r_name, r_date, r_rew in refs:
        is_sub = "Ні ❌"
        if sponsor:
            subbed = await check_sub(bot, r_id, sponsor[2])
            if subbed:
                is_sub = "Так ✅"
                active_count += 1
        
        report += f"• <b>{r_name or r_id}</b>\n  Підписка: {is_sub} | Дата: {r_date}\n\n"

    report += f"📈 <b>Всього рефералів:</b> {total_count}\n"
    report += f"🟢 <b>Активних (підписаних на спонсора):</b> {active_count}\n"
    report += f"🔴 <b>Відписалися:</b> {total_count - active_count}"

    await message.answer(report, parse_mode=ParseMode.HTML)
    await state.clear()

@dp.message(F.text == "📊 Статистика")
async def show_stats_msg(message: Message):
    start_date_row = await db_exec("SELECT value FROM settings WHERE key='bot_start_date'", fetch="one")
    days_working = 1
    if start_date_row:
        try:
            d1 = datetime.strptime(start_date_row[0], "%Y-%m-%d")
            d2 = datetime.now()
            days_working = max(1, (d2 - d1).days + 1)
        except:
            pass

    today_str = datetime.now().strftime("%Y-%m-%d")
    today_users = await db_exec("SELECT COUNT(*) FROM users WHERE join_day=?", (today_str,), fetch="one")
    total_users = await db_exec("SELECT COUNT(*) FROM users", fetch="one")
    with_row = await db_exec("SELECT value FROM settings WHERE key='total_withdrawn'", fetch="one")
    total_withdrawn = with_row[0] if with_row else "0"

    t_users_count = today_users[0] if today_users else 0
    all_users_count = total_users[0] if total_users else 0

    stats_text = (
        f"📊 <b>Статистика проекту:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"⏳ <b>Працює днів:</b> {days_working}\n"
        f"📥 <b>Зайшло за сьогодні:</b> {t_users_count}\n"
        f"👥 <b>Зайшло за весь час:</b> {all_users_count}\n"
        f"💸 <b>Всього виведено:</b> {total_withdrawn} Stars"
    )

    kb_stats = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Чат ком'юніті", url=COMMUNITY_CHAT_LINK)],
        [InlineKeyboardButton(text="👑 Власник", url=OWNER_LINK)]
    ])

    try:
        photo = FSInputFile("IMG_0876.jpeg")
        await message.answer_photo(photo=photo, caption=stats_text, reply_markup=kb_stats, parse_mode=ParseMode.HTML)
    except:
        await message.answer(text=stats_text, reply_markup=kb_stats, parse_mode=ParseMode.HTML)

# --- ПРОМОКОДИ ---
@dp.message(F.text == "🎟 Промокод")
async def promo_menu(message: Message, state: FSMContext):
    await message.answer("🎟 <b>Активація промокоду</b>\n\nНадішли промокод у чат, щоб отримати свої Stars ⭐:", reply_markup=main_reply_kb, parse_mode=ParseMode.HTML)
    await state.set_state(UserStates.waiting_for_promo_input)

@dp.message(UserStates.waiting_for_promo_input)
async def activate_promo(message: Message, state: FSMContext):
    user_id = message.from_user.id
    code = message.text.strip()
    
    promo = await db_exec("SELECT reward, max_uses, used_count FROM promos WHERE code=?", (code,), fetch="one")
    if not promo:
        await message.answer("❌ Такого промокоду не існує або він не дійсний!", reply_markup=main_reply_kb)
        await state.clear()
        return
        
    reward, max_uses, used_count = promo
    
    used_before = await db_exec("SELECT * FROM promo_activations WHERE user_id=? AND code=?", (user_id, code), fetch="one")
    if used_before:
        await message.answer("⚠️ Ти вже активував цей промокод раніше!", reply_markup=main_reply_kb)
        await state.clear()
        return
        
    if used_count >= max_uses:
        await message.answer("⌛ Вичерпано ліміт активацій цього промокоду!", reply_markup=main_reply_kb)
        await state.clear()
        return
        
    await db_exec("UPDATE users SET balance = balance + ?, earned = earned + ? WHERE user_id=?", (reward, reward, user_id))
    await db_exec("UPDATE promos SET used_count = used_count + 1 WHERE code=?", (code,))
    await db_exec("INSERT INTO promo_activations (user_id, code) VALUES (?, ?)", (user_id, code))
    
    await message.answer(f"🎉 <b>Успіх!</b> Твій баланс поповнено на <b>{reward} ⭐</b>!", reply_markup=main_reply_kb, parse_mode=ParseMode.HTML)
    await state.clear()

# --- ІГРИ (КАЗИНО) ---
@dp.message(F.text == "🎲 Ігри (Казино)")
async def casino_menu(message: Message):
    status_row = await db_exec("SELECT value FROM settings WHERE key='casino_status'", fetch="one")
    if status_row and status_row[0] == 'off':
        await message.answer("⛔ Казино наразі вимкнено адміністратором.", reply_markup=main_reply_kb)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚽ Футбол", callback_data="game_football"), InlineKeyboardButton(text="🏀 Баскетбол", callback_data="game_basket")],
        [InlineKeyboardButton(text="🎳 Боулінг", callback_data="game_bowling")]
    ])
    await message.answer("🎲 <b>Вибери гру для ставки зірок (Stars):</b>\nКидай емодзі та вигравай на зароблені кошти!", reply_markup=kb, parse_mode=ParseMode.HTML)

@dp.callback_query(F.data.startswith("game_"))
async def play_game(callback: CallbackQuery, state: FSMContext, bot: Bot):
    status_row = await db_exec("SELECT value FROM settings WHERE key='casino_status'", fetch="one")
    if status_row and status_row[0] == 'off':
        await callback.answer("⛔ Казино вимкнено!", show_alert=True)
        return

    game_type = callback.data.split("_")[1]
    await state.update_data(game_type=game_type)
    
    user_id = callback.from_user.id
    user = await db_exec("SELECT balance FROM users WHERE user_id=?", (user_id,), fetch="one")
    balance = user[0] if user else 0

    await callback.message.answer(f"⭐ Твій поточний баланс: <b>{balance} Stars</b>\nВведи суму ставки для гри:", parse_mode=ParseMode.HTML)
    await state.set_state(UserStates.waiting_for_game_bet)
    await callback.answer()

@dp.message(UserStates.waiting_for_game_bet)
async def process_game_bet(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    try:
        bet = float(message.text.strip())
    except:
        await message.answer("❌ Введи коректне число для ставки!", reply_markup=main_reply_kb)
        return

    user = await db_exec("SELECT balance FROM users WHERE user_id=?", (user_id,), fetch="one")
    balance = user[0] if user else 0

    if bet <= 0 or bet > balance:
        await message.answer(f"❌ Недостатньо коштів! Твій баланс: {balance} Stars ⭐", reply_markup=main_reply_kb)
        await state.clear()
        return

    data = await state.get_data()
    game_type = data.get("game_type")
    
    await db_exec("UPDATE users SET balance = balance - ? WHERE user_id=?", (bet, user_id))
    await state.clear()

    chance_row = await db_exec("SELECT value FROM settings WHERE key='casino_win_chance'", fetch="one")
    win_chance = int(chance_row[0]) if chance_row else 50
    is_win = random.randint(1, 100) <= win_chance

    emoji_map = {
        "football": "⚽",
        "basket": "🏀",
        "bowling": "🎳"
    }
    dice_emoji = emoji_map.get(game_type, "⚽")

    msg = await message.answer_dice(emoji=dice_emoji)
    dice_val = msg.dice.value

    win_conditions = {
        "football": [3, 4, 5],
        "basket": [4, 5],
        "bowling": [6]
    }
    success_vals = win_conditions.get(game_type, [4, 5, 6])
    
    if is_win and dice_val not in success_vals:
        dice_val = random.choice(success_vals)
    elif not is_win and dice_val in success_vals:
        dice_val = random.choice([x for x in range(1, 7) if x not in success_vals])

    await asyncio.sleep(3)

    if dice_val in success_vals:
        win_amt = bet * 2
        await db_exec("UPDATE users SET balance = balance + ?, earned = earned + ? WHERE user_id=?", (win_amt, win_amt, user_id))
        await message.answer(f"🎉 <b>Перемога!</b> Твій виграш: <b>{win_amt} ⭐</b>!", reply_markup=main_reply_kb, parse_mode=ParseMode.HTML)
    else:
        await message.answer(f"😢 <b>Програш!</b> Ти втратив ставку у розмірі {bet} ⭐.", reply_markup=main_reply_kb, parse_mode=ParseMode.HTML)

# --- АДМІН-ПАНЕЛЬ ---
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID: return
    min_w = await db_exec("SELECT value FROM settings WHERE key='min_withdrawal'", fetch="one")
    ref_rew = await db_exec("SELECT value FROM settings WHERE key='ref_reward'", fetch="one")
    status_row = await db_exec("SELECT value FROM settings WHERE key='casino_status'", fetch="one")
    chance_row = await db_exec("SELECT value FROM settings WHERE key='casino_win_chance'", fetch="one")
    
    min_val = min_w[0] if min_w else "50"
    ref_val = ref_rew[0] if ref_rew else "2"
    c_status = status_row[0] if status_row else "on"
    c_chance = chance_row[0] if chance_row else "50"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Додати спонсора", callback_data="adm_add_sponsor"), InlineKeyboardButton(text="📋 Список спонсорів", callback_data="adm_sponsors_list")],
        [InlineKeyboardButton(text="🎟 Створити промокод", callback_data="adm_create_promo")],
        [InlineKeyboardButton(text="🔍 Перевірка підписки", callback_data="adm_check_subs")],
        [InlineKeyboardButton(text="💸 Виплати", callback_data="adm_withdrawals_list"), InlineKeyboardButton(text="💳 Змінити баланс", callback_data="adm_change_balance")],
        [InlineKeyboardButton(text=f"🎰 Казино: {c_status.upper()} (Шанс: {c_chance}%)", callback_data="adm_toggle_casino")],
        [InlineKeyboardButton(text=f"⚙️ Мін. вивід: {min_val} ⭐", callback_data="adm_set_min")],
        [InlineKeyboardButton(text=f"🎁 Нагорода за друга: {ref_val} ⭐", callback_data="adm_set_ref")],
        [InlineKeyboardButton(text="📢 Зробити розсилку", callback_data="adm_broadcast")]
    ])
    await message.answer("👑 <b>Головна адмін-панель StarsBack</b>\nОбери потрібну дію нижче:", reply_markup=kb, parse_mode=ParseMode.HTML)

@dp.callback_query(F.data == "adm_toggle_casino")
async def toggle_casino(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    status_row = await db_exec("SELECT value FROM settings WHERE key='casino_status'", fetch="one")
    current = status_row[0] if status_row else "on"
    new_status = "off" if current == "on" else "on"
    await db_exec("INSERT OR REPLACE INTO settings (key, value) VALUES ('casino_status', ?)", (new_status,))
    await callback.answer(f"✅ Статус казино змінено на: {new_status.upper()}")
    await admin_panel(callback.message)

@dp.callback_query(F.data == "adm_create_promo")
async def cb_create_promo(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("🎟 Надішли назву нового промокоду (наприклад: <code>START2026</code>):", parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_for_promo_code)
    await callback.answer()

@dp.message(AdminStates.waiting_for_promo_code)
async def promo_code_step(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    code = message.text.strip()
    await state.update_data(promo_code=code)
    await message.answer("🎁 Скільки зірок (Stars) дає цей промокод? (наприклад: <code>10</code>):", parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_for_promo_reward)

@dp.message(AdminStates.waiting_for_promo_reward)
async def promo_reward_step(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    try:
        reward = float(message.text.strip())
        await state.update_data(promo_reward=reward)
        await message.answer("👥 На скільки людей розрахований промокод? (наприклад: <code>50</code>):", parse_mode=ParseMode.HTML)
        await state.set_state(AdminStates.waiting_for_promo_limit)
    except:
        await message.answer("❌ Введи лише число (наприклад: 10)")

@dp.message(AdminStates.waiting_for_promo_limit)
async def promo_limit_step(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    try:
        limit = int(message.text.strip())
        data = await state.get_data()
        code = data.get("promo_code")
        reward = data.get("promo_reward")

        await db_exec("INSERT OR REPLACE INTO promos (code, reward, max_uses, used_count) VALUES (?, ?, ?, 0)", (code, reward, limit))
        await message.answer(f"✅ <b>Промокод успішно створено!</b>\n\nКод: <code>{code}</code>\nНагорода: {reward} ⭐\nЛіміт: {limit} людей", parse_mode=ParseMode.HTML)
        await state.clear()
    except:
        await message.answer("❌ Введи лише ціле число для ліміту людей.")

@dp.callback_query(F.data == "adm_set_min")
async def cb_set_min(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("⚙️ Надішли нове число для мінімального виводу (наприклад: <code>50</code>):", parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_for_min_withdrawal)
    await callback.answer()

@dp.message(AdminStates.waiting_for_min_withdrawal)
async def save_min_withdrawal(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    try:
        val = float(message.text.strip())
        await db_exec("INSERT OR REPLACE INTO settings (key, value) VALUES ('min_withdrawal', ?)", (str(val),))
        await message.answer(f"✅ Мінімальний вивід змінено на: <b>{val}</b> ⭐", reply_markup=main_reply_kb, parse_mode=ParseMode.HTML)
        await state.clear()
    except:
        await message.answer("❌ Помилка! Введи лише число.", parse_mode=ParseMode.HTML)

@dp.callback_query(F.data == "adm_set_ref")
async def cb_set_ref(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("🎁 Надішли нову кількість зірок за 1 запрошеного друга (наприклад: <code>3</code> або <code>5</code>):", parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_for_ref_reward)
    await callback.answer()

@dp.message(AdminStates.waiting_for_ref_reward)
async def save_ref_reward(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    try:
        val = float(message.text.strip())
        await db_exec("INSERT OR REPLACE INTO settings (key, value) VALUES ('ref_reward', ?)", (str(val),))
        await message.answer(f"✅ Нагорода за реферала змінена на: <b>{val}</b> ⭐", reply_markup=main_reply_kb, parse_mode=ParseMode.HTML)
        await state.clear()
    except:
        await message.answer("❌ Помилка! Введи лише число.", parse_mode=ParseMode.HTML)

@dp.callback_query(F.data == "adm_add_sponsor")
async def cb_add_sponsor(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer(
        "📝 <b>Додавання спонсора</b>\n\n"
        "Надішли дані у такому форматі (одним рядком через вертикальну риску):\n"
        "<code>Назва каналу | https://t.me/... | @username або -100xxx</code>",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminStates.waiting_for_sponsor)
    await callback.answer()

@dp.message(AdminStates.waiting_for_sponsor)
async def save_sponsor(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    try:
        name, link, chat_id = [x.strip() for x in message.text.split("|")]
        await db_exec("INSERT INTO sponsors (name, link, chat_id) VALUES (?, ?, ?)", (name, link, chat_id))
        last_id = await db_exec("SELECT id FROM sponsors ORDER BY id DESC LIMIT 1", fetch="one")
        await db_exec("INSERT OR REPLACE INTO settings (key, value) VALUES ('active_sponsor', ?)", (str(last_id[0]),))
        await message.answer(f"✅ Спонсор <b>{name}</b> успішно доданий і встановлений як активний!", reply_markup=main_reply_kb, parse_mode=ParseMode.HTML)
        await state.clear()
    except Exception:
        await message.answer("❌ Помилка формату! Спробуй ще раз:\n<code>Назва | Посилання | chat_id</code>", parse_mode=ParseMode.HTML)

@dp.callback_query(F.data == "adm_broadcast")
async def cb_broadcast(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("📢 Надішли текст або повідомлення, яке хочеш розіслати всім користувачам бота:")
    await state.set_state(AdminStates.waiting_for_broadcast)
    await callback.answer()

@dp.message(AdminStates.waiting_for_broadcast)
async def send_broadcast(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id != ADMIN_ID: return
    users = await db_exec("SELECT user_id FROM users", fetch="all")
    success, blocked = 0, 0
    status_msg = await message.answer("⏳ Розпочато розсилку...")
    for u in users:
        try:
            await bot.copy_message(chat_id=u[0], from_chat_id=message.chat.id, message_id=message.message_id)
            success += 1
            await asyncio.sleep(0.05)
        except:
            blocked += 1
    await status_msg.edit_text(f"✅ <b>Розсилку завершено!</b>\n\nОтримали: {success}\nЗаблокували бота: {blocked}", parse_mode=ParseMode.HTML)
    await state.clear()

async def main():
    await init_db()
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())