# ==============================================================================
# ===== TELEGRAM EARNING BOT (V9.0 - DYNAMIC SETTINGS & SS TASKS) =========
# ==============================================================================
# NEW IN V9.0:
# - Global Bot Settings: Admin can change rewards & limits live via a new menu.
# - Advanced User Management: Clickable user list to view detailed user info.
# - New Task Type: Screenshot Verification system added.
# - Full Admin Task Management: Create, view, edit, toggle, and delete tasks.
# - Screenshot Verification Panel: Admins can approve/reject submissions, which
#   automatically pays the user.

import logging
import json
import os
import random
import uuid
from datetime import datetime, date

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler)
from telegram.constants import ParseMode
from telegram.error import TelegramError

# =========================== CONFIGURATION ====================================
BOT_TOKEN = "8397200778:AAHu3p4RYfK0_SiX4cc8uZehNHBlin_jyKs"
ADMIN_ID = 6580698563
CHANNEL_1_ID = "@manishdevtips"
CHANNEL_2_ID = "@DailyEarnNetwork"
CHANNEL_3_ID = "@RewardVault"
CHANNEL_4_ID = "@Cedarpaytaskearn"
GIFTCODE_CHANNEL = "@RewardVault"

# --- Earning, Withdrawal & Game Settings (Now Loaded from settings.json) ---
DAILY_GAME_LIMIT = 3
PREDEFINED_BETS = [1, 5, 10, 25]
USER_LIST_PAGE_SIZE = 5 # Number of users to show per page in admin list

# --- Task Configuration (Key Verification) ---
TASK_DATA = {"task1": {"name": "Key Task 1", "url": "https://indianshortner.in/17BhjX"},"task2": {"name": "Key Task 2", "url": "https://indianshortner.in/oCNkcXV"}}
VALID_TASK_CODES = {"task1": {"51428", "63907", "58261", "55743", "60318", "64825", "59170", "52639", "67402", "56091"}, "task2": {"53384", "61847", "59436", "55209", "62741", "54613", "65927", "60084", "53592", "62075"}}
GUIDE_VIDEO_URL = "https://t.me/manishdevtips/27"

# --- Absolute File Paths ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
USER_DATA_FILE = os.path.join(SCRIPT_DIR, "user_data.json")
WITHDRAWALS_FILE = os.path.join(SCRIPT_DIR, "withdrawals.log")
GIFT_CODES_FILE = os.path.join(SCRIPT_DIR, "gift_codes.json")
SETTINGS_FILE = os.path.join(SCRIPT_DIR, "settings.json") # NEW
TASKS_FILE = os.path.join(SCRIPT_DIR, "tasks.json") # NEW
SUBMISSIONS_FILE = os.path.join(SCRIPT_DIR, "submissions.json") # NEW

# ======================== BOT CODE ========================
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Generic Data Loaders/Savers ---
def load_json(file_path, default_data={}):
    try:
        with open(file_path, 'r') as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError): return default_data
def save_json(data, file_path):
    with open(file_path, 'w') as f: json.dump(data, f, indent=4)

# --- Load All Bot Data ---
user_data = load_json(USER_DATA_FILE)
gift_codes = load_json(GIFT_CODES_FILE)
settings = load_json(SETTINGS_FILE, default_data={
    "referral_reward": 12.0, "daily_bonus_reward": 6.0, "min_withdrawal": 30.0,
    "min_withdrawal_per_request": 22.0, "min_referrals_for_withdrawal": 5
})
tasks_db = load_json(TASKS_FILE)
submissions_db = load_json(SUBMISSIONS_FILE)

async def is_user_member(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        for channel_id in [CHANNEL_1_ID, CHANNEL_2_ID, CHANNEL_3_ID, CHANNEL_4_ID]:
            member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']: return False
        return True
    except TelegramError as e: logger.error(f"Error checking membership for {user_id}: {e}"); return False

def get_today_str(): return date.today().isoformat()

def log_transaction(user_id_str: str, amount: float, type: str, description: str):
    user_data[user_id_str].setdefault('transactions', []).append({"date": datetime.utcnow().isoformat(), "amount": amount, "type": type, "description": description})
    user_data[user_id_str]['transactions'] = user_data[user_id_str]['transactions'][-20:]

def get_main_menu_keyboard(user_id: int):
    keyboard = [[InlineKeyboardButton("👤 Account", callback_data='account'), InlineKeyboardButton("🎁 Bonus Zone", callback_data='bonus_zone')], [InlineKeyboardButton("🔗 Referral", callback_data='referral_menu'), InlineKeyboardButton("💸 Withdraw", callback_data='withdraw')], [InlineKeyboardButton("🏆 Leaderboard", callback_data='leaderboard'), InlineKeyboardButton("ℹ️ How to Earn", callback_data='how_to_earn')]]
    if user_id == ADMIN_ID: keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data='admin_panel')])
    return InlineKeyboardMarkup(keyboard)

def get_join_channel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel 1", url=f"https://t.me/{CHANNEL_1_ID.lstrip('@')}")],
        [InlineKeyboardButton("📢 Join Channel 2", url=f"https://t.me/{CHANNEL_2_ID.lstrip('@')}")],
        [InlineKeyboardButton("📢 Join Channel 3", url=f"https://t.me/{CHANNEL_3_ID.lstrip('@')}")],
        [InlineKeyboardButton("📢 Join Channel 4", url=f"https://t.me/{CHANNEL_4_ID.lstrip('@')}")],
        [InlineKeyboardButton("✅ Check Membership", callback_data='check_membership')]
    ])

# --- CONVERSATION HANDLER STATES ---
(CHOOSE_TASK, AWAITING_CODE, CHOOSE_METHOD_W, ASKING_AMOUNT_W, ASKING_DETAILS_W, CONFIRM_WITHDRAWAL_W, AWAITING_GIFT_CODE,
 BROADCAST_MESSAGE, CREATE_GIFT_CODE_NAME, CREATE_GIFT_CODE_VALUE, CREATE_GIFT_CODE_LIMIT, CREATE_GIFT_CODE_EXPIRY,
 AWAIT_USER_ID, USER_ACTION_MENU, AWAIT_NEW_BALANCE, AWAIT_USER_MESSAGE, AWAIT_NEW_SETTING_VALUE,
 CREATE_TASK_TITLE, CREATE_TASK_DESC, CREATE_TASK_LINK, CREATE_TASK_REWARD, CREATE_TASK_QTY, EDIT_TASK_VALUE,
 AWAITING_SCREENSHOT) = range(24)


# --- Standard User Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user; user_id_str = str(user.id)
    if user_id_str not in user_data:
        user_data[user_id_str] = {"first_name": user.first_name, "username": user.username, "balance": 0.0, "referrals": 0, "referred_by": None, "join_date": datetime.utcnow().isoformat(), "total_earned": 0.0, "last_bonus_claim": None, "tasks_completed": {}, "transactions": [], "game_stats": {"last_play_date": "", "plays_today": 0}, "completed_ss_tasks": []}
        if context.args and context.args[0].isdigit() and context.args[0] != user_id_str:
            user_data[user_id_str]["referred_by"] = context.args[0]
        save_json(user_data, USER_DATA_FILE)

    if not await is_user_member(user.id, context):
        welcome_msg = ("╔═══════════════════════╗\n" "║   🌟 <b>WELCOME!</b> 🌟   ║\n" "╚═══════════════════════╝\n\n" "✨ <b>Join Our Channels First</b> ✨\n\n" "🎁 <b>Join our channel to get gift redeem codes!</b>\n\n" "👇 <i>Click the buttons below to join</i> 👇")
        await update.message.reply_text(welcome_msg, reply_markup=get_join_channel_keyboard(), parse_mode=ParseMode.HTML); return
    
    welcome_text = (f"╔════════════════════════╗\n" f"║  🎉 <b>Welcome {user.first_name}!</b> 🎉  ║\n" "╚════════════════════════╝\n\n" "✨ <b>Your Earning Journey Starts Here!</b> ✨\n\n" "💰 <b>Earn Money Daily Through:</b>\n" f"   • 🔗 Referrals: <b>₹{settings['referral_reward']:.0f}</b> per friend\n" f"   • 🎯 Daily Tasks & SS Tasks\n" f"   • 🎁 Daily Bonus: <b>₹{settings['daily_bonus_reward']:.0f}</b>\n" "   • 🎫 Gift Codes: <b>Extra Cash!</b>\n\n" "🎁 <b>Join our channel to get gift redeem codes!</b>\n" f"📢 Channel: {GIFTCODE_CHANNEL}\n\n" "━━━━━━━━━━━━━━━━━━━━━━━━\n" "<i>👇 Use the menu below to navigate</i>")
    await update.message.reply_text(welcome_text, reply_markup=get_main_menu_keyboard(user.id), parse_mode=ParseMode.HTML)

# --- (All other original, non-admin handlers are here, updated to use 'settings') ---
async def check_membership_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; user = query.from_user; user_id_str = str(user.id); await query.answer()
    referral_reward = settings['referral_reward']
    if await is_user_member(user.id, context):
        if user_data[user_id_str].get("referred_by") and not user_data[user_id_str].get("referral_bonus_claimed"):
            referrer_id_str = user_data[user_id_str]["referred_by"]
            if referrer_id_str in user_data:
                user_data[referrer_id_str]["balance"] += referral_reward
                user_data[referrer_id_str]["referrals"] += 1
                user_data[referrer_id_str]["total_earned"] += referral_reward
                log_transaction(referrer_id_str, referral_reward, "Referral", f"Bonus for inviting {user.first_name}")
                user_data[user_id_str]["referral_bonus_claimed"] = True 
                save_json(user_data, USER_DATA_FILE)
                try:
                    notification = (f"🎊 <b>NEW REFERRAL</b> 🎊\n\n🎉 Congratulations! <b>{user.first_name}</b> has joined using your link.\n💰 You've been rewarded: <b>₹{referral_reward:.2f}</b>")
                    await context.bot.send_message(chat_id=int(referrer_id_str), text=notification, parse_mode=ParseMode.HTML)
                except TelegramError as e: logger.warning(f"Failed to send referral notification to {referrer_id_str}: {e}")
        await query.message.delete()
        success_msg = (f"╔════════════════════════╗\n" f"║  ✅ <b>Welcome {user.first_name}!</b> ✅  ║\n" "╚════════════════════════╝\n\n" "🎉 <b>You're All Set!</b>\n\n" "🎁 <b>Join our channel to get gift redeem codes!</b>\n" f"📢 {GIFTCODE_CHANNEL}\n\n" "━━━━━━━━━━━━━━━━━━━━━━━━\n" "<i>👇 Use the menu below to start earning</i>")
        await query.message.reply_text(success_msg, reply_markup=get_main_menu_keyboard(user.id), parse_mode=ParseMode.HTML)
    else: await query.answer("❌ You haven't joined all channels yet. Please join and try again.", show_alert=True)
async def menu_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    if not await is_user_member(query.from_user.id, context): await query.edit_message_text("🔔 Please join our channels to use the bot!", reply_markup=get_join_channel_keyboard()); return ConversationHandler.END
    data = query.data
    if data == 'back_to_menu': await query.edit_message_text("🏠 Main Menu", reply_markup=get_main_menu_keyboard(query.from_user.id)); return ConversationHandler.END
    elif data == 'account': await account_handler(update, context)
    elif data == 'bonus_zone': await bonus_zone_handler(update, context)
    elif data == 'referral_menu': await referral_menu_handler(update, context)
    elif data == 'how_to_earn': 
        await query.edit_message_text(f"💡 <b>How to Earn:</b>\n\n1. <b>Refer Friends:</b> Earn ₹{settings['referral_reward']:.2f} per referral.\n2. <b>Daily & Screenshot Tasks.</b>\n3. <b>Daily Bonus:</b> Claim a free bonus of ₹{settings['daily_bonus_reward']:.2f} daily.\n4. <b>Gift Codes:</b> Redeem special codes for extra cash.\n\n💸 Minimum withdrawal balance: <b>₹{settings['min_withdrawal']:.2f}</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]]), parse_mode=ParseMode.HTML)
    elif data == 'leaderboard':
        sorted_users = sorted(user_data.items(), key=lambda x: x[1].get('balance', 0), reverse=True)[:10]
        text = "🏆 <b>Top 10 Earners (by Balance):</b>\n\n"
        if not sorted_users: text += "<i>No users yet!</i>"
        else: text += "\n".join([f"{i+1}. {d.get('first_name', 'User')} - <b>₹{d.get('balance', 0):.2f}</b>" for i, (uid, d) in enumerate(sorted_users)])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]]), parse_mode=ParseMode.HTML)
    return ConversationHandler.END
async def daily_bonus_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; user_id_str = str(query.from_user.id)
    daily_bonus = settings['daily_bonus_reward']
    if user_data[user_id_str].get('last_bonus_claim') == get_today_str(): await query.answer("⏳ You've already claimed your bonus today!", show_alert=True)
    else:
        user_data[user_id_str]['balance'] += daily_bonus; user_data[user_id_str]['total_earned'] += daily_bonus; user_data[user_id_str]['last_bonus_claim'] = get_today_str()
        log_transaction(user_id_str, daily_bonus, "Bonus", "Daily Bonus Claim"); save_json(user_data, USER_DATA_FILE)
        await query.answer(f"🎁 You claimed your daily bonus of ₹{daily_bonus:.2f}!", show_alert=True); await bonus_zone_handler(update, context)

# ... (payout_history, my_stats, etc. remain largely unchanged) ...
async def account_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; user_id_str = str(query.from_user.id); balance = user_data[user_id_str].get('balance', 0)
    text = (f"╔═══════════════════════╗\n║   💼 <b>YOUR ACCOUNT</b> 💼   ║\n╚═══════════════════════╝\n\n💰 <b>Current Balance:</b> ₹{balance:.2f}\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n" f"💡 <i>Tap 'Withdraw' to transfer your\nbalance to UPI/Wallet</i>\n\n👇 <b>Choose an option below:</b>")
    keyboard = [[InlineKeyboardButton("🧾 Mini Statement", callback_data='mini_statement'), InlineKeyboardButton("🏦 Payout History", callback_data='payout_history')], [InlineKeyboardButton("📊 My Stats", callback_data='my_stats')], [InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
async def my_stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; await query.answer(); user_id_str = str(query.from_user.id); ud = user_data.get(user_id_str, {}); join_date = datetime.fromisoformat(ud.get('join_date', datetime.utcnow().isoformat())).strftime('%d %b %Y')
    stats_text = (f"╔══════════════════════╗\n║   📊 <b>YOUR STATS</b> 📊   ║\n╚══════════════════════╝\n\n📅 <b>Join Date:</b> {join_date}\n\n" f"💰 <b>Total Earned:</b> ₹{ud.get('total_earned', 0.0):.2f}\n\n👥 <b>Successful Referrals:</b> {ud.get('referrals', 0)}\n\n" f"━━━━━━━━━━━━━━━━━━━━━━━━\n<i>Keep earning and growing! 🚀</i>")
    await query.edit_message_text(stats_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Account", callback_data='account')]]), parse_mode=ParseMode.HTML)
async def mini_statement_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; await query.answer(); user_id_str = str(query.from_user.id); transactions = user_data[user_id_str].get('transactions', []); text = "╔════════════════════════╗\n║  🧾 <b>MINI STATEMENT</b> 🧾  ║\n╚════════════════════════╝\n\n<b>Last 5 Transactions:</b>\n\n"
    if not transactions: text += "<i>📭 No transactions recorded yet.</i>\n\n<i>Start earning to see your transactions!</i>"
    else:
        for tx in reversed(transactions[-5:]): emoji = "💚" if tx['amount'] >= 0 else "💔"; text += f"{emoji} <code>{datetime.fromisoformat(tx['date']).strftime('%d %b, %H:%M')} | {('+' if tx['amount'] >= 0 else '')}₹{tx['amount']:.2f} | {tx['description']}</code>\n"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Account", callback_data='account')]]), parse_mode=ParseMode.HTML)
async def payout_history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; await query.answer(); user_id_str = str(query.from_user.id); text = "🏦 <b>Your Payout History:</b>\n\n"; found_requests = False
    try:
        with open(WITHDRAWALS_FILE, 'r') as f: content = f.read()
        for req in reversed(content.split('---end---')):
            if f"User ID: {user_id_str}" in req: found_requests = True; lines = req.strip().split('\n'); time = next((l for l in lines if l.startswith("Time:")), "Time: N/A").split(' ')[1]; amount = next((l for l in lines if l.startswith("Amount:")), "Amount: N/A").split(' ')[1]; details = next((l for l in lines if l.startswith("Details:")), "Details: N/A").split(' ', 1)[1]; text += f"<code>{datetime.fromisoformat(time).strftime('%d %b %Y')} | {amount} | {details}</code>\n"
    except FileNotFoundError: pass
    if not found_requests: text += "<i>You have not made any withdrawal requests yet.</i>"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Account", callback_data='account')]]), parse_mode=ParseMode.HTML)
async def referral_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; user = query.from_user; bot_info = await context.bot.get_me(); ref_link = f"https://t.me/{bot_info.username}?start={user.id}"
    referral_reward = settings['referral_reward']
    text = (f"🎁 Earn Upto <b>₹{referral_reward:.0f}</b> For Each Successful Referral!\n\n💡 Your Refer Link: {ref_link}\n\n🤔 Share Now & Boost Your Earnings Instantly!")
    share_text = (f"Hey! Friends Join {bot_info.first_name} 🚀 \ninvited By {user.first_name}\n\nMy Unique Link>>> {ref_link}\nEarn Flat ₹{referral_reward:.0f} Per Refer And Get Money 💴\n🔥 Earb Unlimited Money In Upi Wallets 🔥\n\n{bot_info.first_name}™ 🎗️\n👉For {bot_info.first_name} 🎗️ EarnCash Giftcodes Join\n{GIFTCODE_CHANNEL} 😎")
    keyboard = [[InlineKeyboardButton("📋 Invitation Log", callback_data='invitation_log'), InlineKeyboardButton("🏆 Leaderboard", callback_data='referral_leaderboard')], [InlineKeyboardButton("↗️ Share With Friends", switch_inline_query=share_text)], [InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
async def invitation_log_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; await query.answer(); user_id_str = str(query.from_user.id); referred_users = []
    for uid, data in user_data.items():
        if data.get("referred_by") == user_id_str: status = "✅ Completed" if data.get("referral_bonus_claimed") else "⏳ Pending"; referred_users.append(f"👤 {data.get('first_name', 'User')} - {status}")
    text = "📋 <b>Your Invitation Log:</b>\n\n"
    if not referred_users: text += "<i>You haven't referred anyone yet.</i>"
    else: text += "\n".join(referred_users)
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Referral Menu", callback_data='referral_menu')]]), parse_mode=ParseMode.HTML)
async def referral_leaderboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; await query.answer(); sorted_users = sorted(user_data.items(), key=lambda x: x[1].get('referrals', 0), reverse=True)[:10]
    text = "🏆 <b>Top 10 Referrers:</b>\n\n"
    if not any(d.get('referrals', 0) > 0 for uid, d in sorted_users): text += "<i>No one has referred anyone yet!</i>"
    else: text += "\n".join([f"{i+1}. {d.get('first_name', 'User')} - <b>{d.get('referrals', 0)} referrals</b>" for i, (uid, d) in enumerate(sorted_users)])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Referral Menu", callback_data='referral_menu')]]), parse_mode=ParseMode.HTML)
async def bonus_zone_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    daily_bonus = settings['daily_bonus_reward']
    text = (f"🎁 <b>BONUS ZONE</b> 🎁\n\n✨ <b>Welcome to Extra Earnings!</b> ✨\n\n💰 <b>Earn More Through:</b>\n   • 🎯 Key Verification Tasks\n   • ✅ Screenshot Tasks\n   • 🎁 Gift Codes\n   • 🧧 Daily Bonus: ₹{daily_bonus:.0f}\n\n" f"━━━━━━━━━━━━━━━━━━━━━━━━\n<i>👇 Choose an option to start earning</i>")
    keyboard = [
        [InlineKeyboardButton("🎯 Key Verification Tasks", callback_data='tasks_start'), InlineKeyboardButton("✅ Screenshot Tasks", callback_data='ss_tasks_list')],
        [InlineKeyboardButton("🎁 Redeem Gift Code", callback_data='redeem_code_start'), InlineKeyboardButton("🎮 Play Games", callback_data='play_games_menu')],
        [InlineKeyboardButton("🧧 Daily Bonus", callback_data='daily_bonus')],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

# --- (Game handlers remain unchanged) ---
async def show_game_zone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    text = ("╔════════════════════════╗\n║    🎮 <b>GAME ZONE</b> 🎮    ║\n╚════════════════════════╝\n\n✨ <b>Ready to Play?</b> ✨\n\n👇 <i>Choose a game below. Good luck!</i>")
    keyboard = [[InlineKeyboardButton("🪙 Coin Flip", callback_data='game_coinflip_start')], [InlineKeyboardButton("🔙 Back to Bonus Zone", callback_data='bonus_zone')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
async def coinflip_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; user_id_str = str(query.from_user.id); today = get_today_str()
    user_data[user_id_str].setdefault('game_stats', {'last_play_date': '', 'plays_today': 0})
    if user_data[user_id_str]['game_stats']['last_play_date'] != today: user_data[user_id_str]['game_stats']['last_play_date'] = today; user_data[user_id_str]['game_stats']['plays_today'] = 0; save_json(user_data, USER_DATA_FILE)
    plays_left = DAILY_GAME_LIMIT - user_data[user_id_str]['game_stats']['plays_today']; balance = user_data[user_id_str]['balance']
    if plays_left <= 0: await query.answer("🚫 You've used all your game plays for today.", show_alert=True); return
    text = f"🎮 <b>Coin Flip Game</b>\n\nBalance: <b>₹{balance:.2f}</b>\nPlays Left Today: <b>{plays_left}</b>\n\nChoose your bet amount:"
    bet_buttons = [InlineKeyboardButton(f"₹{bet}", callback_data=f"select_bet_{bet}") for bet in PREDEFINED_BETS if balance >= bet]
    if not bet_buttons: await query.answer("You don't have enough balance to make any bets.", show_alert=True); return
    keyboard = [bet_buttons, [InlineKeyboardButton("🔙 Back to Game Zone", callback_data='play_games_menu')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
async def select_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; user_id_str = str(query.from_user.id); bet_amount = int(query.data.split('_')[2])
    if user_data[user_id_str]['balance'] < bet_amount: await query.answer("🚫 You don't have enough balance for this bet!", show_alert=True); return
    text = f"You are betting <b>₹{bet_amount:.2f}</b>.\n\nChoose your side:"
    keyboard = [[InlineKeyboardButton("🪙 Heads", callback_data=f"play_coinflip_{bet_amount}_heads"), InlineKeyboardButton("🪙 Tails", callback_data=f"play_coinflip_{bet_amount}_tails")], [InlineKeyboardButton("🔙 Change Bet", callback_data='game_coinflip_start')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
async def play_coinflip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer(); user_id_str = str(query.from_user.id); _, _, bet_str, choice = query.data.split('_'); bet_amount = int(bet_str)
    if user_data[user_id_str]['balance'] < bet_amount or (DAILY_GAME_LIMIT - user_data[user_id_str]['game_stats']['plays_today']) <= 0: await query.edit_message_text("Error: Insufficient balance or no plays left.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Games", callback_data='play_games_menu')]])); return
    await query.edit_message_text("Flipping... 🪙")
    result = random.choice(['heads', 'tails']); user_data[user_id_str]['game_stats']['plays_today'] += 1
    if choice == result:
        payout = bet_amount; user_data[user_id_str]['balance'] += payout; log_transaction(user_id_str, payout, "Game Win", f"Coin Flip win (bet ₹{bet_amount:.2f})"); final_text = f"It was <b>{result.capitalize()}</b>! 🎉 You WON!\n\n+ ₹{payout:.2f}"
    else:
        payout = -bet_amount; user_data[user_id_str]['balance'] += payout; log_transaction(user_id_str, payout, "Game Loss", f"Coin Flip loss (bet ₹{bet_amount:.2f})"); final_text = f"It was <b>{result.capitalize()}</b>... 😕 You lost.\n\n- ₹{abs(payout):.2f}"
    save_json(user_data, USER_DATA_FILE)
    full_result_text = f"{final_text}\n\nNew Balance: <b>₹{user_data[user_id_str]['balance']:.2f}</b>\nPlays Left Today: <b>{DAILY_GAME_LIMIT - user_data[user_id_str]['game_stats']['plays_today']}</b>"
    await query.edit_message_text(full_result_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Play Again", callback_data='game_coinflip_start')], [InlineKeyboardButton("🔙 Back to Game Zone", callback_data='play_games_menu')]]), parse_mode=ParseMode.HTML)

# --- (Key verification task handlers remain mostly unchanged) ---
async def tasks_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer(); user_id_str = str(query.from_user.id); tasks_completed = user_data[user_id_str].get('tasks_completed', {})
    task1_status, task2_status = ("✅" if tasks_completed.get('task1') == get_today_str() else "⏳"), ("✅" if tasks_completed.get('task2') == get_today_str() else "⏳")
    keyboard = [[InlineKeyboardButton(f"{task1_status} {TASK_DATA['task1']['name']}", callback_data='start_task_1')], [InlineKeyboardButton(f"{task2_status} {TASK_DATA['task2']['name']}", callback_data='start_task_2')], [InlineKeyboardButton("📹 Video Guide", url=GUIDE_VIDEO_URL)], [InlineKeyboardButton("🔙 Back to Bonus Zone", callback_data='bonus_zone')]]
    await query.edit_message_text(f"🎯 <b>Key Verification Tasks</b>\n\nChoose a task to complete.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML); return CHOOSE_TASK
async def task_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query=update.callback_query;await query.answer();task_id="task1" if query.data=='start_task_1' else "task2"
    if user_data[str(query.from_user.id)].get('tasks_completed',{}).get(task_id)==get_today_str():await query.answer("You have already completed this task today!",show_alert=True);return CHOOSE_TASK
    context.user_data['current_task_id']=task_id;task_info=TASK_DATA[task_id]
    await query.edit_message_text(f"✅ <b>Starting {task_info['name']}!</b>\n\n1️⃣ Go to the website below.\n2️⃣ Find the 5-digit code.\n3️⃣ Send the code here.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"🔗 Go to Task",url=task_info['url'])],[InlineKeyboardButton("❌ Cancel Task",callback_data='cancel_task')]]),parse_mode=ParseMode.HTML);return AWAITING_CODE
async def receive_task_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    code=update.message.text;user_id_str=str(update.effective_user.id);task_id=context.user_data.get('current_task_id')
    task_reward = 5.0 # This is from the old system, can be made dynamic if needed
    if not task_id:await update.message.reply_text("Something went wrong.",reply_markup=get_main_menu_keyboard(update.effective_user.id));return ConversationHandler.END
    if code in VALID_TASK_CODES[task_id]:
        user_data[user_id_str]['balance']+=task_reward;user_data[user_id_str]['total_earned']+=task_reward;user_data[user_id_str].setdefault('tasks_completed',{})[task_id]=get_today_str()
        log_transaction(user_id_str,task_reward,"Task",f"Completed {TASK_DATA[task_id]['name']}");save_json(user_data,USER_DATA_FILE);context.user_data.pop('current_task_id',None)
        await update.message.reply_text(f"🎉 <b>Task Complete!</b> You earned <b>₹{task_reward:.2f}</b>!",parse_mode=ParseMode.HTML,reply_markup=get_main_menu_keyboard(update.effective_user.id));return ConversationHandler.END
    else:await update.message.reply_text("❌ Incorrect code. Please try again.");return AWAITING_CODE
async def cancel_task(update:Update,context:ContextTypes.DEFAULT_TYPE)->int:
    context.user_data.pop('current_task_id',None)
    if update.callback_query:await update.callback_query.answer();await bonus_zone_handler(update,context)
    else:await update.message.reply_text("Task cancelled.",reply_markup=get_main_menu_keyboard(update.effective_user.id))
    return ConversationHandler.END

# --- (Gift Code handlers are unchanged) ---
async def redeem_code_start(update:Update,context:ContextTypes.DEFAULT_TYPE)->int:
    query=update.callback_query;await query.answer()
    await query.edit_message_text("🎁 Please enter the gift code:",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Bonus Zone",callback_data='bonus_zone')]]));return AWAITING_GIFT_CODE
async def receive_gift_code(update:Update,context:ContextTypes.DEFAULT_TYPE)->int:
    user_id_str=str(update.effective_user.id);code=update.message.text.strip().upper()
    if code not in gift_codes:await update.message.reply_text("❌ Invalid gift code.");return AWAITING_GIFT_CODE
    code_data=gift_codes[code]
    if date.today()>datetime.strptime(code_data.get("expiry_date","9999-12-31"),"%Y-%m-%d").date(): await update.message.reply_text("❌ This gift code has expired."); return AWAITING_GIFT_CODE
    if user_id_str in code_data.get("used_by",[]): await update.message.reply_text("❌ You have already redeemed this code."); return AWAITING_GIFT_CODE
    if len(code_data.get("used_by",[]))>=code_data.get("limit",1): await update.message.reply_text("❌ This code has reached its usage limit."); return AWAITING_GIFT_CODE
    value=code_data["value"];user_data[user_id_str]['balance']+=value;user_data[user_id_str]['total_earned']+=value
    log_transaction(user_id_str,value,"Gift Code",f"Redeemed code {code}");save_json(user_data,USER_DATA_FILE)
    gift_codes[code].setdefault("used_by",[]).append(user_id_str);save_json(gift_codes,GIFT_CODES_FILE)
    await update.message.reply_text(f"✅ Success! You earned <b>₹{value:.2f}</b>!",parse_mode=ParseMode.HTML,reply_markup=get_main_menu_keyboard(update.effective_user.id));return ConversationHandler.END
# --- (Withdrawal handlers updated to use settings) ---
async def withdraw_start(update:Update,context:ContextTypes.DEFAULT_TYPE)->int:
    query=update.callback_query;await query.answer();user_id_str=str(query.from_user.id);current_referrals=user_data[user_id_str].get('referrals',0)
    min_referrals = settings['min_referrals_for_withdrawal']; min_withdrawal = settings['min_withdrawal']
    if current_referrals < min_referrals:
        await query.edit_message_text(f"❌ <b>Withdrawal Locked!</b>\n\nYou need at least <b>{min_referrals} successful referrals</b>.\nYou have <b>{current_referrals}</b>. You need <b>{min_referrals-current_referrals} more</b>.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu",callback_data='back_to_menu')]]),parse_mode=ParseMode.HTML);return ConversationHandler.END
    if user_data[user_id_str]['balance'] < min_withdrawal:await query.edit_message_text(f"❌ Minimum balance is <b>₹{min_withdrawal:.2f}</b>.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu",callback_data='back_to_menu')]]),parse_mode=ParseMode.HTML);return ConversationHandler.END
    context.user_data.clear();keyboard=[[InlineKeyboardButton("💳 UPI / PayPal",callback_data='withdraw_method_upi')],[InlineKeyboardButton("🎁 Google Play Code",callback_data='withdraw_method_gplay')],[InlineKeyboardButton("🔙 Back to Menu",callback_data='back_to_menu')]]
    await query.edit_message_text(f"💰 Your Balance: <b>₹{user_data[user_id_str]['balance']:.2f}</b>\n\n✨ Choose withdrawal method:",reply_markup=InlineKeyboardMarkup(keyboard),parse_mode=ParseMode.HTML);return CHOOSE_METHOD_W
async def withdraw_method_choice(update:Update,context:ContextTypes.DEFAULT_TYPE)->int:
    query=update.callback_query;await query.answer();method=query.data.replace('withdraw_method_','');context.user_data['withdrawal_method']=method
    min_req = settings['min_withdrawal_per_request']
    await query.edit_message_text(f"💸 You chose <b>{method.upper().replace('UPI','UPI / PayPal')}</b>.\n\n➡️ Enter the amount to withdraw.\nAvailable: <b>₹{user_data[str(query.from_user.id)]['balance']:.2f}</b>\nMin Request: <b>₹{min_req:.2f}</b>",parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel",callback_data='cancel_withdrawal')]]));return ASKING_AMOUNT_W
async def receive_withdrawal_amount(update:Update,context:ContextTypes.DEFAULT_TYPE)->int:
    user_id_str=str(update.effective_user.id); min_req = settings['min_withdrawal_per_request']
    try:
        amount=float(update.message.text)
        if amount<min_req:await update.message.reply_text(f"🚫 Minimum request is <b>₹{min_req:.2f}</b>.",parse_mode=ParseMode.HTML);return ASKING_AMOUNT_W
        if amount>user_data[user_id_str]['balance']:await update.message.reply_text(f"🚫 Insufficient balance.",parse_mode=ParseMode.HTML);return ASKING_AMOUNT_W
        context.user_data['withdrawal_amount']=amount;prompt="💳 Please send your **UPI ID**." if context.user_data['withdrawal_method']=='upi' else "🎁 Please specify the desired **Google Play Code value**."
        await update.message.reply_text(f"✅ Amount set to <b>₹{amount:.2f}</b>.\n\n{prompt}",parse_mode=ParseMode.HTML);return ASKING_DETAILS_W
    except ValueError:await update.message.reply_text("🚫 Invalid amount.");return ASKING_AMOUNT_W
async def receive_withdrawal_details(update:Update,context:ContextTypes.DEFAULT_TYPE)->int:
    context.user_data['withdrawal_details']=update.message.text;method=context.user_data['withdrawal_method'];amount=context.user_data['withdrawal_amount']
    text=f"📝 <b>Confirm Request:</b>\n\n<b>Method:</b> <code>{method.upper()}</code>\n<b>Amount:</b> <b>₹{amount:.2f}</b>\n<b>Details:</b> <code>{update.message.text}</code>"
    keyboard=[[InlineKeyboardButton("✅ Confirm",callback_data='confirm_withdrawal'),InlineKeyboardButton("✏️ Edit",callback_data='edit_withdrawal_details')],[InlineKeyboardButton("❌ Cancel",callback_data='cancel_withdrawal')]]
    await update.message.reply_text(text,parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup(keyboard));return CONFIRM_WITHDRAWAL_W
async def confirm_withdrawal(update:Update,context:ContextTypes.DEFAULT_TYPE)->int:
    query=update.callback_query;await query.answer();user_id_str=str(query.from_user.id)
    if query.data=='edit_withdrawal_details':await query.edit_message_text("✏️ Okay, please send correct payment details.");return ASKING_DETAILS_W
    amount=context.user_data.get('withdrawal_amount');
    if user_data[user_id_str]['balance']<amount:await query.edit_message_text("🚫 Insufficient balance.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu",callback_data='back_to_menu')]]));context.user_data.clear();return ConversationHandler.END
    user_data[user_id_str]['balance']-=amount;log_transaction(user_id_str,-amount,"Withdrawal","Withdrawal Request");save_json(user_data,USER_DATA_FILE)
    method=context.user_data.get('withdrawal_method');details=context.user_data.get('withdrawal_details')
    log_msg=f"WITHDRAWAL\nTime: {datetime.utcnow().isoformat()}\nUser ID: {query.from_user.id}\nUsername: @{query.from_user.username or 'N/A'}\nMethod: {method}\nAmount: {amount}\nDetails: {details}\n---end---\n\n"
    with open(WITHDRAWALS_FILE,'a') as f:f.write(log_msg)
    admin_notification=f"🚨 <b>NEW WITHDRAWAL!</b> 🚨\n\nUser: <a href='tg://user?id={query.from_user.id}'>{query.from_user.first_name}</a>\nAmount: <b>₹{amount:.2f}</b>\nDetails: <code>{details}</code>"
    try:await context.bot.send_message(chat_id=ADMIN_ID,text=admin_notification,parse_mode=ParseMode.HTML)
    except Exception as e:logger.error(f"Failed to notify admin: {e}")
    await query.edit_message_text(f"✅ <b>Request Submitted!</b>\n\nProcessing takes ⏳ <b>2-5 working days</b> ⏳.\nRemaining balance: <b>₹{user_data[user_id_str]['balance']:.2f}</b>",parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu",callback_data='back_to_menu')]]));context.user_data.clear();return ConversationHandler.END
async def cancel_withdrawal(update:Update,context:ContextTypes.DEFAULT_TYPE)->int:
    context.user_data.clear()
    if update.callback_query:await update.callback_query.answer("Withdrawal cancelled.",show_alert=True);await update.callback_query.edit_message_text("💸 Withdrawal process cancelled.",reply_markup=get_main_menu_keyboard(update.effective_user.id))
    else:await update.message.reply_text("💸 Withdrawal process cancelled.",reply_markup=get_main_menu_keyboard(update.effective_user.id))
    return ConversationHandler.END

# ==========================================================
# ================= NEW & UPGRADED ADMIN FEATURES ============
# ==========================================================

async def admin_panel(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    query=update.callback_query; await query.answer()
    if query.from_user.id != ADMIN_ID: return
    keyboard=[
        [InlineKeyboardButton("📊 Bot Stats", callback_data='admin_stats'), InlineKeyboardButton("⚙️ Bot Settings", callback_data='admin_settings_menu')],
        [InlineKeyboardButton("👥 Manage Users", callback_data='admin_list_users_0')],
        [InlineKeyboardButton("📢 Broadcast", callback_data='admin_broadcast'), InlineKeyboardButton("🎁 Manage Gift Codes", callback_data='admin_gift_codes')],
        [InlineKeyboardButton("🎯 Task Management", callback_data='admin_task_menu'), InlineKeyboardButton("✔️ Verify Submissions", callback_data='admin_verify_ss_0')],
        [InlineKeyboardButton("📝 Review Withdrawals", callback_data='admin_view_withdrawals_0')],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]
    ]
    await query.edit_message_text("👑 *Admin Panel*\n\nWelcome, Admin. Select an option to manage the bot.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

# --- (Stats handler is unchanged) ---
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    total_users = len(user_data)
    total_balance = sum(u.get('balance', 0) for u in user_data.values())
    pending_withdrawals = 0; pending_submissions = len(submissions_db)
    try:
        with open(WITHDRAWALS_FILE, 'r') as f:
            content = f.read().strip()
            if content: pending_withdrawals = content.count("---end---")
    except FileNotFoundError: pass
    stats_text = (f"<b>📊 Bot Statistics</b>\n\n" f"👤 <b>Total Users:</b> {total_users}\n" f"💰 <b>Total Balance in Wallets:</b> ₹{total_balance:.2f}\n" f"⏳ <b>Pending Withdrawals:</b> {pending_withdrawals}\n" f"✔️ <b>Pending Submissions:</b> {pending_submissions}\n")
    await query.edit_message_text(stats_text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')]]))

# --- NEW: Global Bot Settings ---
async def admin_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    text = (
        "⚙️ <b>Global Bot Settings</b>\n\n"
        "These are default values for ALL users.\n\n"
        f"🔗 Referral Reward: <b>₹{settings['referral_reward']:.2f}</b>\n"
        f"🎁 Daily Bonus: <b>₹{settings['daily_bonus_reward']:.2f}</b>\n"
        f" withdrawing for the first time\n"
        f"💰 Min Withdrawal: <b>₹{settings['min_withdrawal']:.2f}</b>\n"
        f"💸 Min Per Request: <b>₹{settings['min_withdrawal_per_request']:.2f}</b>\n"
        f"👥 Min Referrals: <b>{settings['min_referrals_for_withdrawal']}</b>"
    )
    keyboard = [
        [InlineKeyboardButton("Edit Referral Reward", callback_data='admin_edit_setting_referral_reward')],
        [InlineKeyboardButton("Edit Daily Bonus", callback_data='admin_edit_setting_daily_bonus_reward')],
        [InlineKeyboardButton("Edit Min Withdrawal", callback_data='admin_edit_setting_min_withdrawal')],
        [InlineKeyboardButton("Edit Min Per Request", callback_data='admin_edit_setting_min_withdrawal_per_request')],
        [InlineKeyboardButton("Edit Min Referrals", callback_data='admin_edit_setting_min_referrals_for_withdrawal')],
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')]
    ]
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
async def admin_edit_setting_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    setting_key = query.data.replace('admin_edit_setting_', '')
    context.user_data['setting_to_edit'] = setting_key
    
    # Provide user-friendly names
    setting_names = {
        "referral_reward": "Referral Reward", "daily_bonus_reward": "Daily Bonus Reward",
        "min_withdrawal": "Minimum Withdrawal", "min_withdrawal_per_request": "Minimum Per Request",
        "min_referrals_for_withdrawal": "Minimum Referrals for Withdrawal"
    }
    
    await query.edit_message_text(f"✏️ Please enter the new value for <b>{setting_names.get(setting_key, setting_key.replace('_', ' ').title())}</b>.", parse_mode=ParseMode.HTML)
    return AWAIT_NEW_SETTING_VALUE
async def admin_receive_new_setting(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    setting_key = context.user_data.get('setting_to_edit')
    new_value = update.message.text.strip()
    if not setting_key:
        await update.message.reply_text("An error occurred. Please try again.")
        return ConversationHandler.END
    try:
        # Convert to float or int based on the key
        final_value = int(new_value) if 'referrals' in setting_key else float(new_value)
        settings[setting_key] = final_value
        save_json(settings, SETTINGS_FILE)
        await update.message.reply_text(f"✅ Setting <b>{setting_key}</b> updated to <b>{final_value}</b>.", parse_mode=ParseMode.HTML)
        # Fake a callback query to go back to the menu
        fake_query = type('obj', (object,), {'data': 'admin_settings_menu', 'from_user': update.effective_user, 'edit_message_text': update.message.reply_text, 'answer': lambda: None})
        await admin_settings_menu(fake_query, context)
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Invalid number. Please try again.")
        return AWAIT_NEW_SETTING_VALUE

# --- UPGRADED: User Listing and Management ---
async def admin_list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    page = int(query.data.split('_')[-1])
    user_ids = list(user_data.keys())
    start_index = page * USER_LIST_PAGE_SIZE
    end_index = start_index + USER_LIST_PAGE_SIZE
    paginated_users = user_ids[start_index:end_index]

    if not paginated_users:
        await query.answer("No users on this page.", show_alert=True); return

    text = f"👥 <b>All Users (Page {page + 1})</b>"
    user_buttons = []
    for uid in paginated_users:
        u_info = user_data[uid]
        button_text = f"{u_info.get('first_name', 'N/A')} (₹{u_info.get('balance', 0):.2f})"
        user_buttons.append([InlineKeyboardButton(button_text, callback_data=f"admin_view_user_{uid}")])

    nav_buttons = []
    if page > 0: nav_buttons.append(InlineKeyboardButton("◀️ Prev", callback_data=f"admin_list_users_{page-1}"))
    if end_index < len(user_ids): nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"admin_list_users_{page+1}"))
    
    keyboard = user_buttons + [nav_buttons, [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')]]
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
async def admin_view_user_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    user_id_to_manage = query.data.split('_')[-1]
    
    if user_id_to_manage not in user_data:
        await query.edit_message_text("❌ User not found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='admin_list_users_0')]]))
        return ConversationHandler.END

    context.user_data['target_user_id'] = user_id_to_manage
    target_user = user_data[user_id_to_manage]
    join_date_str = datetime.fromisoformat(target_user.get('join_date', datetime.utcnow().isoformat())).strftime('%Y-%m-%d %H:%M')

    info_text = (
        f"👤 <b>User Details</b>\n\n"
        f"<b>Basic Info:</b>\n"
        f"• ID: <code>{user_id_to_manage}</code>\n"
        f"• Name: {target_user.get('first_name', 'N/A')}\n"
        f"• Username: @{target_user.get('username', 'N/A')}\n"
        f"• Joined: {join_date_str}\n\n"
        f"<b>Earning Info:</b>\n"
        f"• Balance: <b>₹{target_user.get('balance', 0):.2f}</b>\n"
        f"• Referrals: {target_user.get('referrals', 0)}\n"
    )
    keyboard = [
        [InlineKeyboardButton("💰 Edit Balance", callback_data='admin_user_edit_balance'), InlineKeyboardButton("✉️ Send Message", callback_data='admin_user_send_message')],
        [InlineKeyboardButton("🔙 Back to User List", callback_data='admin_list_users_0')]
    ]
    await query.edit_message_text(info_text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    return USER_ACTION_MENU

# --- NEW: Screenshot Task Handlers (USER-FACING) ---
async def list_screenshot_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    user_id_str = str(query.from_user.id)
    
    # Ensure the user has the list for completed tasks
    user_data[user_id_str].setdefault('completed_ss_tasks', [])
    
    available_tasks = []
    for task_id, task in tasks_db.items():
        # Check if task is active, not completed by user, and not full
        if (task['status'] == 'active' and 
            task_id not in user_data[user_id_str]['completed_ss_tasks'] and
            len(task.get('completions', [])) < task['quantity']):
            available_tasks.append(task)
            
    if not available_tasks:
        await query.edit_message_text("✅ No new screenshot tasks available right now. Please check back later!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Bonus Zone", callback_data='bonus_zone')]]))
        return

    text = "✅ <b>Available Screenshot Tasks</b>\n\nChoose a task to complete:"
    keyboard = []
    for task in available_tasks:
        keyboard.append([InlineKeyboardButton(f"🎯 {task['title']} - ₹{task['reward']}", callback_data=f"ss_task_details_{task['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 Back to Bonus Zone", callback_data='bonus_zone')])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
async def show_screenshot_task_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    task_id = query.data.split('_')[-1]
    task = tasks_db.get(task_id)

    if not task:
        await query.edit_message_text("❌ Task not found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='ss_tasks_list')]]))
        return
        
    text = (f"🎯 <b>Task: {task['title']}</b>\n\n"
            f"📝 <b>Description:</b> {task['description']}\n\n"
            f"💰 <b>Reward:</b> ₹{task['reward']:.2f}\n\n"
            f"👇 Go to the link, complete the action, and submit a screenshot.")
            
    keyboard = [
        [InlineKeyboardButton("🔗 Go to Link", url=task['link'])],
        [InlineKeyboardButton("🧾 Submit Screenshot", callback_data=f"ss_task_submit_{task['id']}")],
        [InlineKeyboardButton("🔙 Back to Task List", callback_data='ss_tasks_list')]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
async def start_screenshot_submission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    task_id = query.data.split('_')[-1]
    context.user_data['submitting_task_id'] = task_id
    await query.edit_message_text("Please send the screenshot now.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data='cancel_ss_submission')]]))
    return AWAITING_SCREENSHOT
async def receive_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    task_id = context.user_data.get('submitting_task_id')
    task = tasks_db.get(task_id)

    if not task or not update.message.photo:
        await update.message.reply_text("Something went wrong. Please try again.")
        return ConversationHandler.END

    submission_id = str(uuid.uuid4())
    photo_file_id = update.message.photo[-1].file_id # Get the highest resolution

    submissions_db[submission_id] = {
        "id": submission_id,
        "task_id": task_id,
        "user_id": str(user.id),
        "photo_file_id": photo_file_id,
        "timestamp": datetime.utcnow().isoformat()
    }
    save_json(submissions_db, SUBMISSIONS_FILE)

    await update.message.reply_text("✅ Screenshot submitted!\n⏳ Waiting for verification.\n📝 Admin will verify your task soon.")
    
    # Notify Admin
    admin_msg = (f"✔️ <b>New Screenshot Submission!</b>\n\n"
                 f"<b>User:</b> <a href='tg://user?id={user.id}'>{user.first_name}</a>\n"
                 f"<b>Task:</b> {task['title']}")
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode=ParseMode.HTML, 
                                       reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👀 Review Now", callback_data='admin_verify_ss_0')]]))
    except Exception as e:
        logger.error(f"Failed to send submission notification to admin: {e}")

    context.user_data.clear()
    return ConversationHandler.END
async def cancel_ss_submission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Submission cancelled.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Bonus Zone", callback_data='bonus_zone')]]))
    return ConversationHandler.END

# --- NEW: Admin Screenshot Task Management ---
async def admin_task_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    total = len(tasks_db)
    active = sum(1 for t in tasks_db.values() if t['status'] == 'active')
    inactive = total - active
    
    text = (f"🎯 <b>Task Management</b>\n\n"
            f"📋 Total Tasks: {total}\n"
            f"✅ Active: {active}\n"
            f"❌ Inactive: {inactive}")
            
    keyboard = [
        [InlineKeyboardButton("➕ Add New Task", callback_data='admin_task_add')],
        [InlineKeyboardButton("📄 View All Tasks", callback_data='admin_task_view_0')],
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
async def admin_add_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    context.user_data['new_task'] = {}
    await query.edit_message_text("✏️ Enter the task <b>Title</b>:", parse_mode=ParseMode.HTML)
    return CREATE_TASK_TITLE
async def admin_task_receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_task']['title'] = update.message.text
    await update.message.reply_text("📝 Enter the task <b>Description</b>:", parse_mode=ParseMode.HTML)
    return CREATE_TASK_DESC
async def admin_task_receive_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_task']['description'] = update.message.text
    await update.message.reply_text("🔗 Enter the task <b>URL/Link</b>:", parse_mode=ParseMode.HTML)
    return CREATE_TASK_LINK
async def admin_task_receive_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_task']['link'] = update.message.text
    await update.message.reply_text("💰 Enter the task <b>Reward</b> (e.g., 50.0):", parse_mode=ParseMode.HTML)
    return CREATE_TASK_REWARD
async def admin_task_receive_reward(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        context.user_data['new_task']['reward'] = float(update.message.text)
        await update.message.reply_text("📊 Enter the <b>Quantity</b> (max number of completions):", parse_mode=ParseMode.HTML)
        return CREATE_TASK_QTY
    except ValueError:
        await update.message.reply_text("❌ Invalid number. Please enter a valid reward value.")
        return CREATE_TASK_REWARD
async def admin_task_receive_qty(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        context.user_data['new_task']['quantity'] = int(update.message.text)
        
        # Finalize and save the task
        task_data = context.user_data['new_task']
        task_id = str(uuid.uuid4())
        tasks_db[task_id] = {
            "id": task_id,
            "title": task_data['title'],
            "description": task_data['description'],
            "link": task_data['link'],
            "reward": task_data['reward'],
            "quantity": task_data['quantity'],
            "status": 'inactive',  # Default to inactive
            "completions": []
        }
        save_json(tasks_db, TASKS_FILE)
        
        await update.message.reply_text(f"✅ Task '<b>{task_data['title']}</b>' created successfully and set to inactive.", parse_mode=ParseMode.HTML)
        context.user_data.clear()
        
        # Fake a query to go back to the menu
        fake_query = type('obj', (object,), {'data': 'admin_task_menu', 'from_user': update.effective_user, 'edit_message_text': update.message.reply_text, 'answer': lambda: None})
        await admin_task_menu(fake_query, context)

        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Invalid number. Please enter a whole number for quantity.")
        return CREATE_TASK_QTY

# --- (Withdrawal approval handlers are mostly unchanged) ---
def get_withdrawals():
    try:
        with open(WITHDRAWALS_FILE, 'r') as f:
            content = f.read().strip()
            if not content: return []
            return [req for req in content.split('---end---') if req.strip()]
    except FileNotFoundError: return []
async def admin_browse_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    index = int(query.data.split('_')[-1])
    withdrawals = get_withdrawals()
    if not withdrawals:
        await query.edit_message_text("✅ No pending withdrawals.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')]])); return
    if index >= len(withdrawals):
        await query.answer("You are at the end of the list.", show_alert=True); index = len(withdrawals) - 1
    request_text = withdrawals[index].strip()
    timestamp = "Unknown"
    for line in request_text.split('\n'):
        if line.startswith("Time:"): timestamp = line.split(':', 1)[1].strip()
    text = f"<b>📝 Withdrawal Request {index + 1} of {len(withdrawals)}</b>\n\n<pre>{request_text}</pre>"
    nav_buttons = []
    if index > 0: nav_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data=f"admin_view_withdrawals_{index-1}"))
    if index < len(withdrawals) - 1: nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"admin_view_withdrawals_{index+1}"))
    keyboard = [[InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_wd_{timestamp}")], nav_buttons, [InlineKeyboardButton("🗑️ Clear Entire Log (Confirm)", callback_data='admin_clear_withdrawals_confirm')], [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')]]
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
async def admin_approve_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; timestamp_to_approve = query.data.replace('admin_approve_wd_', '')
    withdrawals = get_withdrawals(); new_withdrawals_content = ""; approved_request = None
    user_id_to_notify, amount_to_notify = None, None
    for req in withdrawals:
        if timestamp_to_approve in req:
            approved_request = req
            for line in req.strip().split('\n'):
                if line.startswith("User ID:"): user_id_to_notify = line.split(':')[1].strip()
                if line.startswith("Amount:"): amount_to_notify = line.split(':')[1].strip()
        else: new_withdrawals_content += req + "---end---\n\n"
    if approved_request:
        with open(WITHDRAWALS_FILE, 'w') as f: f.write(new_withdrawals_content)
        await query.answer("✅ Withdrawal Approved!", show_alert=True)
        if user_id_to_notify and amount_to_notify:
            try:
                success_message = f"✅ Your withdrawal request of <b>₹{float(amount_to_notify):.2f}</b> has been approved and processed. Thank you!"
                await context.bot.send_message(chat_id=int(user_id_to_notify), text=success_message, parse_mode=ParseMode.HTML)
            except TelegramError as e:
                logger.warning(f"Could not notify user {user_id_to_notify} about withdrawal approval. Reason: {e}")
                await context.bot.send_message(chat_id=ADMIN_ID, text=f"⚠️ Could not notify user {user_id_to_notify} about withdrawal.")
        query.data = "admin_view_withdrawals_0" # Go back to the first request
        await admin_browse_withdrawals(update, context)
    else: await query.answer("❌ Could not find this withdrawal. It may have already been processed.", show_alert=True)

# --- NEW: Admin Submission Verification ---
async def admin_browse_submissions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    page = int(query.data.split('_')[-1])
    
    submission_ids = list(submissions_db.keys())
    
    if not submission_ids:
        await query.edit_message_text("✅ No pending submissions to verify.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')]]))
        return

    if page >= len(submission_ids):
        await query.answer("You are at the end of the list.", show_alert=True); page = len(submission_ids) - 1
        
    submission_id = submission_ids[page]
    submission = submissions_db[submission_id]
    task = tasks_db.get(submission['task_id'], {})
    submitting_user = user_data.get(submission['user_id'], {})
    
    text = (
        f"✔️ <b>Screenshot Verification ({page + 1}/{len(submission_ids)})</b>\n\n"
        f"<b>User Details:</b>\n"
        f" • ID: <code>{submission['user_id']}</code>\n"
        f" • Name: {submitting_user.get('first_name', 'N/A')}\n"
        f" • Username: @{submitting_user.get('username', 'N/A')}\n\n"
        f"<b>Task Details:</b>\n"
        f" • Title: {task.get('title', 'N/A')}\n"
        f" • Reward: ₹{task.get('reward', 0):.2f}"
    )

    nav_buttons = []
    if page > 0: nav_buttons.append(InlineKeyboardButton("◀️ Prev", callback_data=f"admin_verify_ss_{page-1}"))
    if page < len(submission_ids) - 1: nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"admin_verify_ss_{page+1}"))
    
    keyboard = [
        [InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_ss_{submission_id}"), InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_ss_{submission_id}")],
        nav_buttons,
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')]
    ]
    
    # Send photo first, then text with buttons
    await query.message.delete() # Delete the old menu message
    await context.bot.send_photo(chat_id=query.from_user.id, photo=submission['photo_file_id'], caption=text, 
                                 parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
async def admin_approve_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    submission_id = query.data.split('_')[-1]
    
    if submission_id not in submissions_db:
        await query.answer("❌ This submission was already processed.", show_alert=True)
        # Refresh view to show remaining submissions
        query.data = 'admin_verify_ss_0'
        await admin_browse_submissions(update, context)
        return
        
    await query.answer("Approving...")
    submission = submissions_db.pop(submission_id) # Remove from pending
    task = tasks_db.get(submission['task_id'])
    user_id_str = submission['user_id']
    
    if task and user_id_str in user_data:
        # Give reward
        reward = task['reward']
        user_data[user_id_str]['balance'] += reward
        user_data[user_id_str]['total_earned'] += reward
        log_transaction(user_id_str, reward, "Task", f"Approved: {task['title']}")
        
        # Mark as completed for user and task
        user_data[user_id_str].setdefault('completed_ss_tasks', []).append(submission['task_id'])
        task.setdefault('completions', []).append(user_id_str)
        
        save_json(user_data, USER_DATA_FILE)
        save_json(tasks_db, TASKS_FILE)
        save_json(submissions_db, SUBMISSIONS_FILE)
        
        # Notify user
        try:
            await context.bot.send_message(chat_id=int(user_id_str), 
                                           text=f"✅ Your submission for the task '<b>{task['title']}</b>' has been approved!\n\n💰 You've earned <b>₹{reward:.2f}</b>.",
                                           parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.warning(f"Failed to notify user {user_id_str} of approval: {e}")
            
    # Refresh view
    query.data = 'admin_verify_ss_0'
    await admin_browse_submissions(update, context)
async def admin_reject_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    submission_id = query.data.split('_')[-1]

    if submission_id not in submissions_db:
        await query.answer("❌ This submission was already processed.", show_alert=True)
        # Refresh view to show remaining submissions
        query.data = 'admin_verify_ss_0'
        await admin_browse_submissions(update, context)
        return
        
    await query.answer("Rejecting...")
    submission = submissions_db.pop(submission_id) # Remove from pending
    save_json(submissions_db, SUBMISSIONS_FILE)
    
    task = tasks_db.get(submission['task_id'], {})
    user_id_str = submission['user_id']
    
    # Notify user
    try:
        await context.bot.send_message(chat_id=int(user_id_str), 
                                       text=f"❌ Your submission for the task '<b>{task.get('title', 'Unknown')}</b>' has been rejected. Please ensure you followed all instructions.",
                                       parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Failed to notify user {user_id_str} of rejection: {e}")
        
    # Refresh view
    query.data = 'admin_verify_ss_0'
    await admin_browse_submissions(update, context)

# --- Admin Gift Code Management ---
async def admin_gift_codes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    total_codes = len(gift_codes)
    active_codes = sum(1 for code in gift_codes.values() if len(code.get('used_by', [])) < code.get('limit', 1))
    
    text = (
        f"🎁 <b>Gift Code Management</b>\n\n"
        f"📋 Total Codes: {total_codes}\n"
        f"✅ Active: {active_codes}\n"
        f"❌ Expired/Full: {total_codes - active_codes}\n\n"
        f"<i>Use this panel to manage gift codes.</i>"
    )
    
    keyboard = [
        [InlineKeyboardButton("📋 View All Codes", callback_data='admin_view_gift_codes')],
        [InlineKeyboardButton("➕ Create New Code", callback_data='admin_create_gift_code')],
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

async def admin_view_gift_codes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    
    if not gift_codes:
        await query.edit_message_text(
            "📭 No gift codes created yet.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='admin_gift_codes')]])
        )
        return
    
    text = "🎁 <b>All Gift Codes:</b>\n\n"
    for code, data in gift_codes.items():
        used = len(data.get('used_by', []))
        limit = data.get('limit', 1)
        value = data.get('value', 0)
        expiry = data.get('expiry_date', 'N/A')
        status = "✅ Active" if used < limit else "❌ Full"
        text += f"<code>{code}</code> - ₹{value:.2f} ({used}/{limit}) {status}\n"
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='admin_gift_codes')]]),
        parse_mode=ParseMode.HTML
    )

async def admin_create_gift_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    
    # Create a simple gift code with default values
    code = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=6))
    
    text = (
        f"✏️ <b>Quick Gift Code Created!</b>\n\n"
        f"Code: <code>{code}</code>\n\n"
        f"Default Settings:\n"
        f"• Value: ₹25.00\n"
        f"• Limit: 10 uses\n"
        f"• Expiry: 30 days\n\n"
        f"<i>Code has been saved and is ready to use!</i>"
    )
    
    # Create the code
    from datetime import timedelta
    expiry_date = (datetime.utcnow() + timedelta(days=30)).strftime('%Y-%m-%d')
    gift_codes[code] = {
        "value": 25.0,
        "limit": 10,
        "expiry_date": expiry_date,
        "used_by": []
    }
    save_json(gift_codes, GIFT_CODES_FILE)
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Gift Codes", callback_data='admin_gift_codes')]]),
        parse_mode=ParseMode.HTML
    )

# --- Admin Task Viewing ---
async def admin_view_all_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    page = int(query.data.split('_')[-1])
    
    if not tasks_db:
        await query.edit_message_text(
            "📭 No tasks created yet.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='admin_task_menu')]]),
            parse_mode=ParseMode.HTML
        )
        return
    
    task_ids = list(tasks_db.keys())
    if page >= len(task_ids):
        page = 0
    
    task_id = task_ids[page]
    task = tasks_db[task_id]
    
    status_emoji = "✅" if task['status'] == 'active' else "❌"
    completions = len(task.get('completions', []))
    
    text = (
        f"📄 <b>Task Details ({page + 1}/{len(task_ids)})</b>\n\n"
        f"<b>Title:</b> {task['title']}\n"
        f"<b>Description:</b> {task['description']}\n"
        f"<b>Link:</b> {task['link']}\n"
        f"<b>Reward:</b> ₹{task['reward']:.2f}\n"
        f"<b>Completions:</b> {completions}/{task['quantity']}\n"
        f"<b>Status:</b> {status_emoji} {task['status'].title()}"
    )
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Prev", callback_data=f"admin_task_view_{page-1}"))
    if page < len(task_ids) - 1:
        nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"admin_task_view_{page+1}"))
    
    toggle_text = "❌ Deactivate" if task['status'] == 'active' else "✅ Activate"
    keyboard = [
        [InlineKeyboardButton(toggle_text, callback_data=f"admin_task_toggle_{task_id}")],
        [InlineKeyboardButton("🗑️ Delete Task", callback_data=f"admin_task_delete_{task_id}")],
        nav_buttons,
        [InlineKeyboardButton("🔙 Back to Task Menu", callback_data='admin_task_menu')]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

async def admin_toggle_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    task_id = query.data.split('_')[-1]
    
    if task_id in tasks_db:
        task = tasks_db[task_id]
        task['status'] = 'inactive' if task['status'] == 'active' else 'active'
        save_json(tasks_db, TASKS_FILE)
        await query.answer(f"Task status changed to {task['status']}!", show_alert=True)
        
        # Find current page
        task_ids = list(tasks_db.keys())
        page = task_ids.index(task_id)
        query.data = f'admin_task_view_{page}'
        await admin_view_all_tasks(update, context)
    else:
        await query.answer("Task not found!", show_alert=True)

async def admin_delete_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    task_id = query.data.split('_')[-1]
    
    if task_id in tasks_db:
        task_title = tasks_db[task_id]['title']
        del tasks_db[task_id]
        save_json(tasks_db, TASKS_FILE)
        await query.answer(f"Task '{task_title}' deleted!", show_alert=True)
        query.data = 'admin_task_menu'
        await admin_task_menu(update, context)
    else:
        await query.answer("Task not found!", show_alert=True)

# --- (Other admin handlers from V8.0 are here) ---
# ... This includes clearing logs, broadcast, gift codes etc. (user management conv moved)
async def admin_clear_withdrawals_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    keyboard = [[InlineKeyboardButton("🔴 YES, CLEAR IT", callback_data='admin_clear_withdrawals_do')], [InlineKeyboardButton("🟢 NO, GO BACK", callback_data='admin_panel')]]
    await query.edit_message_text("<b>⚠️ Are you sure?</b>\n\nThis will permanently delete the entire withdrawals log file.", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
async def admin_clear_withdrawals_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        if os.path.exists(WITHDRAWALS_FILE): os.remove(WITHDRAWALS_FILE)
        await query.answer("Withdrawals log has been cleared.", show_alert=True)
    except Exception as e:
        logger.error(f"Error clearing withdrawals file: {e}"); await query.answer(f"Error: {e}", show_alert=True)
    await admin_panel(update, context)
async def admin_user_action_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer(); action = query.data
    if action == 'admin_user_edit_balance': await query.edit_message_text("💰 Please send the new balance for this user."); return AWAIT_NEW_BALANCE
    elif action == 'admin_user_send_message': await query.edit_message_text("✉️ Please send the message you want to forward to this user."); return AWAIT_USER_MESSAGE
    return USER_ACTION_MENU
async def admin_receive_new_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    target_user_id = context.user_data.get('target_user_id')
    try:
        new_balance = float(update.message.text)
        user_data[target_user_id]['balance'] = new_balance; save_json(user_data, USER_DATA_FILE)
        await update.message.reply_text(f"✅ Success! User {target_user_id}'s balance set to ₹{new_balance:.2f}.", reply_markup=get_main_menu_keyboard(ADMIN_ID))
        return ConversationHandler.END
    except ValueError: await update.message.reply_text("❌ Invalid amount. Please send a number."); return AWAIT_NEW_BALANCE
async def admin_receive_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    target_user_id = context.user_data.get('target_user_id'); message_to_send = update.message.text
    try:
        await context.bot.send_message(chat_id=int(target_user_id), text=f"✉️ A message from the admin:\n\n{message_to_send}")
        await update.message.reply_text(f"✅ Message sent to user {target_user_id}.", reply_markup=get_main_menu_keyboard(ADMIN_ID))
    except TelegramError as e:
        await update.message.reply_text(f"❌ Failed to send message. Error: {e}", reply_markup=get_main_menu_keyboard(ADMIN_ID))
    return ConversationHandler.END
async def admin_broadcast_start(update:Update,context:ContextTypes.DEFAULT_TYPE)->int:
    query=update.callback_query;await query.answer(); await query.edit_message_text("📢 Send the message to broadcast. Supports HTML.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel",callback_data='cancel_broadcast')]]));return BROADCAST_MESSAGE
async def admin_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message_to_send = update.message.text; target_users = [uid for uid in user_data if int(uid) != ADMIN_ID]
    if not target_users:
        await update.message.reply_text("📢 Broadcast Canceled. No other users to send to.", reply_markup=get_main_menu_keyboard(update.effective_user.id)); return ConversationHandler.END
    success, fail = 0, 0
    await update.message.reply_text(f"📢 Sending broadcast to {len(target_users)} user(s)...")
    for user_id_str in target_users:
        try:
            await context.bot.send_message(chat_id=int(user_id_str), text=message_to_send, parse_mode=ParseMode.HTML)
            success += 1
        except TelegramError:
            try:
                await context.bot.send_message(chat_id=int(user_id_str), text=message_to_send)
                success += 1
            except Exception as e: logger.warning(f"Failed broadcast (fallback) to {user_id_str}: {e}"); fail += 1
    await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=update.message.message_id + 1, text=f"📢 Broadcast Finished.\n✅ Sent: {success}\n❌ Failed: {fail}")
    await update.message.reply_text("You are back in the main menu.", reply_markup=get_main_menu_keyboard(ADMIN_ID))
    return ConversationHandler.END
async def cancel_broadcast(update:Update,context:ContextTypes.DEFAULT_TYPE)->int:
    query=update.callback_query;await query.answer(); await query.edit_message_text("Broadcast cancelled.",reply_markup=get_main_menu_keyboard(query.from_user.id));return ConversationHandler.END

# --- (All other handlers from the previous version remain here, unchanged) ---

def main() -> None:
    """Sets up and runs the bot."""
    # Optional: Add proxy configuration if Telegram is blocked
    # Uncomment and configure if needed:
    # from telegram.ext import ApplicationBuilder
    # application = ApplicationBuilder().token(BOT_TOKEN).proxy_url('http://proxy_host:proxy_port').build()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation Handlers
    task_conv = ConversationHandler(entry_points=[CallbackQueryHandler(tasks_start,pattern='^tasks_start$')],states={CHOOSE_TASK:[CallbackQueryHandler(task_selected,pattern='^start_task_')],AWAITING_CODE:[MessageHandler(filters.TEXT & ~filters.COMMAND,receive_task_code)]},fallbacks=[CallbackQueryHandler(cancel_task,pattern='^cancel_task$'),CallbackQueryHandler(bonus_zone_handler,pattern='^bonus_zone$')])
    redeem_code_conv = ConversationHandler(entry_points=[CallbackQueryHandler(redeem_code_start,pattern='^redeem_code_start$')],states={AWAITING_GIFT_CODE:[MessageHandler(filters.TEXT & ~filters.COMMAND,receive_gift_code)]},fallbacks=[CallbackQueryHandler(bonus_zone_handler,pattern='^bonus_zone$')])
    withdraw_conv = ConversationHandler(entry_points=[CallbackQueryHandler(withdraw_start,pattern='^withdraw$')],states={CHOOSE_METHOD_W:[CallbackQueryHandler(withdraw_method_choice,pattern='^withdraw_method_')],ASKING_AMOUNT_W:[MessageHandler(filters.TEXT & ~filters.COMMAND,receive_withdrawal_amount)],ASKING_DETAILS_W:[MessageHandler(filters.TEXT & ~filters.COMMAND,receive_withdrawal_details)],CONFIRM_WITHDRAWAL_W:[CallbackQueryHandler(confirm_withdrawal,pattern='^confirm_withdrawal$|^edit_withdrawal_details$')]},fallbacks=[CallbackQueryHandler(cancel_withdrawal,pattern='^cancel_withdrawal$')])
    broadcast_conv = ConversationHandler(entry_points=[CallbackQueryHandler(admin_broadcast_start,pattern='^admin_broadcast$')],states={BROADCAST_MESSAGE:[MessageHandler(filters.TEXT & ~filters.COMMAND,admin_broadcast_message)]},fallbacks=[CallbackQueryHandler(cancel_broadcast,pattern='^cancel_broadcast$')])
    #... (gift code conv is omitted for brevity but is in the full code)
    
    # NEW Conversation Handlers
    settings_conv = ConversationHandler(entry_points=[CallbackQueryHandler(admin_edit_setting_start, pattern='^admin_edit_setting_')], states={AWAIT_NEW_SETTING_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_receive_new_setting)]}, fallbacks=[CallbackQueryHandler(admin_settings_menu, pattern='^admin_settings_menu$')])
    user_management_conv = ConversationHandler(entry_points=[CallbackQueryHandler(admin_view_user_details, pattern='^admin_view_user_')], states={USER_ACTION_MENU: [CallbackQueryHandler(admin_user_action_choice, pattern='^admin_user_')], AWAIT_NEW_BALANCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_receive_new_balance)], AWAIT_USER_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_receive_user_message)],}, fallbacks=[CallbackQueryHandler(admin_list_users, pattern='^admin_list_users_0$')])
    add_task_conv = ConversationHandler(entry_points=[CallbackQueryHandler(admin_add_task_start, pattern='^admin_task_add$')], states={CREATE_TASK_TITLE:[MessageHandler(filters.TEXT & ~filters.COMMAND, admin_task_receive_title)], CREATE_TASK_DESC:[MessageHandler(filters.TEXT & ~filters.COMMAND, admin_task_receive_desc)], CREATE_TASK_LINK:[MessageHandler(filters.TEXT & ~filters.COMMAND, admin_task_receive_link)], CREATE_TASK_REWARD:[MessageHandler(filters.TEXT & ~filters.COMMAND, admin_task_receive_reward)], CREATE_TASK_QTY:[MessageHandler(filters.TEXT & ~filters.COMMAND, admin_task_receive_qty)]}, fallbacks=[CallbackQueryHandler(admin_task_menu, pattern='^admin_task_menu$')])
    ss_submission_conv = ConversationHandler(entry_points=[CallbackQueryHandler(start_screenshot_submission, pattern='^ss_task_submit_')], states={AWAITING_SCREENSHOT: [MessageHandler(filters.PHOTO, receive_screenshot)]}, fallbacks=[CallbackQueryHandler(cancel_ss_submission, pattern='^cancel_ss_submission$')])
    
    # Add all handlers to the application
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(check_membership_handler, pattern='^check_membership$'))
    # --- Add all regular handlers ---
    application.add_handler(CallbackQueryHandler(daily_bonus_handler, pattern='^daily_bonus$'))
    application.add_handler(CallbackQueryHandler(my_stats_handler, pattern='^my_stats$'))
    application.add_handler(CallbackQueryHandler(mini_statement_handler, pattern='^mini_statement$'))
    application.add_handler(CallbackQueryHandler(payout_history_handler, pattern='^payout_history$'))
    application.add_handler(CallbackQueryHandler(invitation_log_handler, pattern='^invitation_log$'))
    application.add_handler(CallbackQueryHandler(referral_leaderboard_handler, pattern='^referral_leaderboard$'))
    application.add_handler(CallbackQueryHandler(show_game_zone, pattern='^play_games_menu$'))
    application.add_handler(CallbackQueryHandler(coinflip_start, pattern='^game_coinflip_start$'))
    application.add_handler(CallbackQueryHandler(select_bet, pattern='^select_bet_'))
    application.add_handler(CallbackQueryHandler(play_coinflip, pattern='^play_coinflip_'))
    application.add_handler(CallbackQueryHandler(list_screenshot_tasks, pattern='^ss_tasks_list$'))
    application.add_handler(CallbackQueryHandler(show_screenshot_task_details, pattern='^ss_task_details_'))
    
    # --- Add all admin handlers ---
    application.add_handler(CallbackQueryHandler(admin_panel, pattern='^admin_panel$'))
    application.add_handler(CallbackQueryHandler(admin_stats, pattern='^admin_stats$'))
    application.add_handler(CallbackQueryHandler(admin_clear_withdrawals_confirm, pattern='^admin_clear_withdrawals_confirm$'))
    application.add_handler(CallbackQueryHandler(admin_clear_withdrawals_do, pattern='^admin_clear_withdrawals_do$'))
    application.add_handler(CallbackQueryHandler(admin_gift_codes, pattern='^admin_gift_codes$'))
    application.add_handler(CallbackQueryHandler(admin_view_gift_codes, pattern='^admin_view_gift_codes$'))
    application.add_handler(CallbackQueryHandler(admin_create_gift_code, pattern='^admin_create_gift_code$'))
    application.add_handler(CallbackQueryHandler(admin_list_users, pattern='^admin_list_users_'))
    application.add_handler(CallbackQueryHandler(admin_browse_withdrawals, pattern='^admin_view_withdrawals_'))
    application.add_handler(CallbackQueryHandler(admin_approve_withdrawal, pattern='^admin_approve_wd_'))
    application.add_handler(CallbackQueryHandler(admin_settings_menu, pattern='^admin_settings_menu$'))
    application.add_handler(CallbackQueryHandler(admin_task_menu, pattern='^admin_task_menu$'))
    application.add_handler(CallbackQueryHandler(admin_view_all_tasks, pattern='^admin_task_view_'))
    application.add_handler(CallbackQueryHandler(admin_toggle_task, pattern='^admin_task_toggle_'))
    application.add_handler(CallbackQueryHandler(admin_delete_task, pattern='^admin_task_delete_'))
    application.add_handler(CallbackQueryHandler(admin_browse_submissions, pattern='^admin_verify_ss_'))
    application.add_handler(CallbackQueryHandler(admin_approve_submission, pattern='^admin_approve_ss_'))
    application.add_handler(CallbackQueryHandler(admin_reject_submission, pattern='^admin_reject_ss_'))

    # --- Add all conversation handlers ---
    application.add_handler(task_conv); application.add_handler(redeem_code_conv); application.add_handler(withdraw_conv)
    application.add_handler(broadcast_conv) #; application.add_handler(create_gift_code_conv); 
    application.add_handler(user_management_conv)
    application.add_handler(settings_conv); application.add_handler(add_task_conv); application.add_handler(ss_submission_conv)
    
    application.add_handler(CallbackQueryHandler(menu_button_handler))
    
    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()