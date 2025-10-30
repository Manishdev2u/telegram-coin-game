# ==============================================================================
# ===== TELEGRAM EARNING BOT (V8.1 - USER LISTING & APPROVALS) =============
# ==============================================================================
# NEW IN V8.1:
# - Admin panel can now list all users with "Next" and "Previous" buttons.
# - Interactive withdrawal system: Approve requests one-by-one.
# - Automatic notification sent to the user upon withdrawal approval.

import logging
import json
import os
import random
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

# --- Earning, Withdrawal & Game Settings ---
REFERRAL_REWARD = 12.0
DAILY_BONUS_REWARD = 6.0
TASK_REWARD = 5.0
MIN_WITHDRAWAL = 30.0
MIN_WITHDRAWAL_PER_REQUEST = 22.0
MIN_REFERRALS_FOR_WITHDRAWAL = 5
DAILY_GAME_LIMIT = 3
PREDEFINED_BETS = [1, 5, 10, 25]
USER_LIST_PAGE_SIZE = 5 # Number of users to show per page in admin list

# --- Task Configuration ---
TASK_DATA = {"task1": {"name": "Key Task 1", "url": "https://indianshortner.in/17BhjX"},"task2": {"name": "Key Task 2", "url": "https://indianshortner.in/oCNkcXV"}}
VALID_TASK_CODES = {"task1": {"51428", "63907", "58261", "55743", "60318", "64825", "59170", "52639", "67402", "56091"}, "task2": {"53384", "61847", "59436", "55209", "62741", "54613", "65927", "60084", "53592", "62075"}}
GUIDE_VIDEO_URL = "https://t.me/manishdevtips/27"

# --- Absolute File Paths ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
USER_DATA_FILE = os.path.join(SCRIPT_DIR, "user_data.json")
WITHDRAWALS_FILE = os.path.join(SCRIPT_DIR, "withdrawals.log")
GIFT_CODES_FILE = os.path.join(SCRIPT_DIR, "gift_codes.json")

# ======================== BOT CODE ========================
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def load_data(file_path):
    try:
        with open(file_path, 'r') as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError): return {}
def save_data(data, file_path):
    with open(file_path, 'w') as f: json.dump(data, f, indent=4)

user_data = load_data(USER_DATA_FILE)
gift_codes = load_data(GIFT_CODES_FILE)

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
CHOOSE_TASK, AWAITING_CODE, CHOOSE_METHOD_W, ASKING_AMOUNT_W, ASKING_DETAILS_W, CONFIRM_WITHDRAWAL_W, AWAITING_GIFT_CODE = range(7)
BROADCAST_MESSAGE, CREATE_GIFT_CODE_NAME, CREATE_GIFT_CODE_VALUE, CREATE_GIFT_CODE_LIMIT, CREATE_GIFT_CODE_EXPIRY = range(7, 12)
AWAIT_USER_ID, USER_ACTION_MENU, AWAIT_NEW_BALANCE, AWAIT_USER_MESSAGE = range(12, 16)

# --- Standard User Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user; user_id_str = str(user.id)
    if user_id_str not in user_data:
        user_data[user_id_str] = {"first_name": user.first_name, "username": user.username, "balance": 0.0, "referrals": 0, "referred_by": None, "join_date": datetime.utcnow().isoformat(), "total_earned": 0.0, "last_bonus_claim": None, "tasks_completed": {}, "transactions": [], "game_stats": {"last_play_date": "", "plays_today": 0}}
        if context.args and context.args[0].isdigit() and context.args[0] != user_id_str:
            user_data[user_id_str]["referred_by"] = context.args[0]
        save_data(user_data, USER_DATA_FILE)

    if not await is_user_member(user.id, context):
        welcome_msg = ("╔═══════════════════════╗\n" "║   🌟 <b>WELCOME!</b> 🌟   ║\n" "╚═══════════════════════╝\n\n" "✨ <b>Join Our Channels First</b> ✨\n\n" "🎁 <b>Join our channel to get gift redeem codes!</b>\n\n" "👇 <i>Click the buttons below to join</i> 👇")
        await update.message.reply_text(welcome_msg, reply_markup=get_join_channel_keyboard(), parse_mode=ParseMode.HTML); return
    
    welcome_text = (f"╔════════════════════════╗\n" f"║  🎉 <b>Welcome {user.first_name}!</b> 🎉  ║\n" "╚════════════════════════╝\n\n" "✨ <b>Your Earning Journey Starts Here!</b> ✨\n\n" "💰 <b>Earn Money Daily Through:</b>\n" f"   • 🔗 Referrals: <b>₹{REFERRAL_REWARD:.0f}</b> per friend\n" f"   • 🎯 Daily Tasks: <b>₹{TASK_REWARD:.0f}</b> each\n" f"   • 🎁 Daily Bonus: <b>₹{DAILY_BONUS_REWARD:.0f}</b>\n" "   • 🎫 Gift Codes: <b>Extra Cash!</b>\n\n" "🎁 <b>Join our channel to get gift redeem codes!</b>\n" f"📢 Channel: {GIFTCODE_CHANNEL}\n\n" "━━━━━━━━━━━━━━━━━━━━━━━━\n" "<i>👇 Use the menu below to navigate</i>")
    await update.message.reply_text(welcome_text, reply_markup=get_main_menu_keyboard(user.id), parse_mode=ParseMode.HTML)

# --- (All other original, non-admin handlers are here) ---
# ... This includes check_membership_handler, menu_button_handler, all the account handlers, etc.
# ... They are pasted below for completeness and are unchanged.
# NEW, CORRECTED VERSION
async def check_membership_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; user = query.from_user; user_id_str = str(user.id); await query.answer()
    
    if await is_user_member(user.id, context):
        # --- FIX ---
        # We now check for a new, dedicated flag instead of the 'referrals' count.
        if user_data[user_id_str].get("referred_by") and not user_data[user_id_str].get("referral_bonus_claimed"):
            referrer_id_str = user_data[user_id_str]["referred_by"]
            if referrer_id_str in user_data:
                # This part is still correct (giving points to inviter)
                user_data[referrer_id_str]["balance"] += REFERRAL_REWARD
                user_data[referrer_id_str]["referrals"] += 1
                user_data[referrer_id_str]["total_earned"] += REFERRAL_REWARD
                log_transaction(referrer_id_str, REFERRAL_REWARD, "Referral", f"Bonus for inviting {user.first_name}")
                
                # --- FIX ---
                # We now set our new flag to True. The new user's referral count remains 0.
                user_data[user_id_str]["referral_bonus_claimed"] = True 
                save_data(user_data, USER_DATA_FILE)

                try:
                    notification = (
                        "╔══════════════════════════╗\n"
                        "║      🎊 <b>NEW REFERRAL</b> 🎊      ║\n"
                        "╚══════════════════════════╝\n\n"
                        f"🎉 Congratulations! <b>{user.first_name}</b> has\n"
                        "   joined using your unique link.\n\n"
                        f"💰 You've been rewarded: <b>₹{REFERRAL_REWARD:.2f}</b>\n\n"
                        "🚀 <i>Keep sharing to earn even more!</i>"
                    )
                    await context.bot.send_message(chat_id=int(referrer_id_str), text=notification, parse_mode=ParseMode.HTML)
                except TelegramError as e: 
                    logger.warning(f"Failed to send referral notification to {referrer_id_str}: {e}")

        await query.message.delete()
        success_msg = (f"╔════════════════════════╗\n" f"║  ✅ <b>Welcome {user.first_name}!</b> ✅  ║\n" "╚════════════════════════╝\n\n" "🎉 <b>You're All Set!</b>\n\n" "🎁 <b>Join our channel to get gift redeem codes!</b>\n" f"📢 {GIFTCODE_CHANNEL}\n\n" "━━━━━━━━━━━━━━━━━━━━━━━━\n" "<i>👇 Use the menu below to start earning</i>")
        await query.message.reply_text(success_msg, reply_markup=get_main_menu_keyboard(user.id), parse_mode=ParseMode.HTML)
    else: 
        await query.answer("❌ You haven't joined all channels yet. Please join and try again.", show_alert=True)
async def menu_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    if not await is_user_member(query.from_user.id, context): await query.edit_message_text("🔔 Please join our channels to use the bot!", reply_markup=get_join_channel_keyboard()); return ConversationHandler.END
    data = query.data
    if data == 'back_to_menu': await query.edit_message_text("🏠 Main Menu", reply_markup=get_main_menu_keyboard(query.from_user.id)); return ConversationHandler.END
    elif data == 'account': await account_handler(update, context)
    elif data == 'bonus_zone': await bonus_zone_handler(update, context)
    elif data == 'referral_menu': await referral_menu_handler(update, context)
    elif data == 'how_to_earn': 
        await query.edit_message_text(f"💡 <b>How to Earn:</b>\n\n1. <b>Refer Friends:</b> Earn ₹{REFERRAL_REWARD:.2f} per referral.\n2. <b>Daily Tasks:</b> Earn ₹{TASK_REWARD:.2f} per task.\n3. <b>Daily Bonus:</b> Claim a free bonus of ₹{DAILY_BONUS_REWARD:.2f} daily.\n4. <b>Gift Codes:</b> Redeem special codes for extra cash.\n\n💸 Minimum withdrawal balance: <b>₹{MIN_WITHDRAWAL:.2f}</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]]), parse_mode=ParseMode.HTML)
    elif data == 'leaderboard':
        sorted_users = sorted(user_data.items(), key=lambda x: x[1].get('balance', 0), reverse=True)[:10]
        text = "🏆 <b>Top 10 Earners (by Balance):</b>\n\n"
        if not sorted_users: text += "<i>No users yet!</i>"
        else: text += "\n".join([f"{i+1}. {d.get('first_name', 'User')} - <b>₹{d.get('balance', 0):.2f}</b>" for i, (uid, d) in enumerate(sorted_users)])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]]), parse_mode=ParseMode.HTML)
    return ConversationHandler.END
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
    text = (f"🎁 Earn Upto <b>₹{REFERRAL_REWARD:.0f}</b> For Each Successful Referral!\n\n💡 Your Refer Link: {ref_link}\n\n🤔 Share Now & Boost Your Earnings Instantly!")
    share_text = (f"Hey! Friends Join {bot_info.first_name} 🚀 \ninvited By {user.first_name}\n\nMy Unique Link>>> {ref_link}\nEarn Flat ₹{REFERRAL_REWARD:.0f} Per Refer And Get Money 💴\n🔥 Earb Unlimited Money In Upi Wallets 🔥\n\n{bot_info.first_name}™ 🎗️\n👉For {bot_info.first_name} 🎗️ EarnCash Giftcodes Join\n{GIFTCODE_CHANNEL} 😎")
    keyboard = [[InlineKeyboardButton("📋 Invitation Log", callback_data='invitation_log'), InlineKeyboardButton("🏆 Leaderboard", callback_data='referral_leaderboard')], [InlineKeyboardButton("↗️ Share With Friends", switch_inline_query=share_text)], [InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
async def invitation_log_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; await query.answer(); user_id_str = str(query.from_user.id); referred_users = []
    for uid, data in user_data.items():
        if data.get("referred_by") == user_id_str: status = "✅ Completed" if data.get("referrals", 0) == 1 else "⏳ Pending"; referred_users.append(f"👤 {data.get('first_name', 'User')} - {status}")
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
    text = ("╔════════════════════════╗\n║   🎁 <b>BONUS ZONE</b> 🎁   ║\n╚════════════════════════╝\n\n✨ <b>Welcome to Extra Earnings!</b> ✨\n\n" f"💰 <b>Earn More Through:</b>\n   • 🎯 Daily Tasks: ₹{TASK_REWARD:.0f} each\n   • 🎁 Gift Codes: Bonus Cash\n   • 🧧 Daily Bonus: ₹{DAILY_BONUS_REWARD:.0f}\n\n" f"━━━━━━━━━━━━━━━━━━━━━━━━\n<i>👇 Choose an option to start earning</i>")
    keyboard = [[InlineKeyboardButton("💐 Complete Tasks", callback_data='tasks_start'), InlineKeyboardButton("🎁 Redeem Gift Code", callback_data='redeem_code_start')], [InlineKeyboardButton("🎮 Play Games", callback_data='play_games_menu')], [InlineKeyboardButton("🧧 Daily Bonus", callback_data='daily_bonus')], [InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
async def show_game_zone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    text = ("╔════════════════════════╗\n║    🎮 <b>GAME ZONE</b> 🎮    ║\n╚════════════════════════╝\n\n✨ <b>Ready to Play?</b> ✨\n\n👇 <i>Choose a game below. Good luck!</i>")
    keyboard = [[InlineKeyboardButton("🪙 Coin Flip", callback_data='game_coinflip_start')], [InlineKeyboardButton("🔙 Back to Bonus Zone", callback_data='bonus_zone')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
async def coinflip_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; user_id_str = str(query.from_user.id); today = get_today_str()
    user_data[user_id_str].setdefault('game_stats', {'last_play_date': '', 'plays_today': 0})
    if user_data[user_id_str]['game_stats']['last_play_date'] != today: user_data[user_id_str]['game_stats']['last_play_date'] = today; user_data[user_id_str]['game_stats']['plays_today'] = 0; save_data(user_data, USER_DATA_FILE)
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
    save_data(user_data, USER_DATA_FILE)
    full_result_text = f"{final_text}\n\nNew Balance: <b>₹{user_data[user_id_str]['balance']:.2f}</b>\nPlays Left Today: <b>{DAILY_GAME_LIMIT - user_data[user_id_str]['game_stats']['plays_today']}</b>"
    await query.edit_message_text(full_result_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Play Again", callback_data='game_coinflip_start')], [InlineKeyboardButton("🔙 Back to Game Zone", callback_data='play_games_menu')]]), parse_mode=ParseMode.HTML)
async def daily_bonus_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; user_id_str = str(query.from_user.id)
    if user_data[user_id_str].get('last_bonus_claim') == get_today_str(): await query.answer("⏳ You've already claimed your bonus today!", show_alert=True)
    else:
        user_data[user_id_str]['balance'] += DAILY_BONUS_REWARD; user_data[user_id_str]['total_earned'] += DAILY_BONUS_REWARD; user_data[user_id_str]['last_bonus_claim'] = get_today_str()
        log_transaction(user_id_str, DAILY_BONUS_REWARD, "Bonus", "Daily Bonus Claim"); save_data(user_data, USER_DATA_FILE)
        await query.answer(f"🎁 You claimed your daily bonus of ₹{DAILY_BONUS_REWARD:.2f}!", show_alert=True); await bonus_zone_handler(update, context)
async def tasks_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer(); user_id_str = str(query.from_user.id); tasks_completed = user_data[user_id_str].get('tasks_completed', {})
    task1_status, task2_status = ("✅" if tasks_completed.get('task1') == get_today_str() else "⏳"), ("✅" if tasks_completed.get('task2') == get_today_str() else "⏳")
    keyboard = [[InlineKeyboardButton(f"{task1_status} {TASK_DATA['task1']['name']}", callback_data='start_task_1')], [InlineKeyboardButton(f"{task2_status} {TASK_DATA['task2']['name']}", callback_data='start_task_2')], [InlineKeyboardButton("📹 Video Guide", url=GUIDE_VIDEO_URL)], [InlineKeyboardButton("🔙 Back to Bonus Zone", callback_data='bonus_zone')]]
    await query.edit_message_text(f"🎯 <b>Daily Tasks (₹{TASK_REWARD:.2f} each)</b>\n\nChoose a task to complete.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML); return CHOOSE_TASK
async def task_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query=update.callback_query;await query.answer();task_id="task1" if query.data=='start_task_1' else "task2"
    if user_data[str(query.from_user.id)].get('tasks_completed',{}).get(task_id)==get_today_str():await query.answer("You have already completed this task today!",show_alert=True);return CHOOSE_TASK
    context.user_data['current_task_id']=task_id;task_info=TASK_DATA[task_id]
    await query.edit_message_text(f"✅ <b>Starting {task_info['name']}!</b>\n\n1️⃣ Go to the website below.\n2️⃣ Find the 5-digit code.\n3️⃣ Send the code here.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"🔗 Go to Task",url=task_info['url'])],[InlineKeyboardButton("❌ Cancel Task",callback_data='cancel_task')]]),parse_mode=ParseMode.HTML);return AWAITING_CODE
async def receive_task_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    code=update.message.text;user_id_str=str(update.effective_user.id);task_id=context.user_data.get('current_task_id')
    if not task_id:await update.message.reply_text("Something went wrong.",reply_markup=get_main_menu_keyboard(update.effective_user.id));return ConversationHandler.END
    if code in VALID_TASK_CODES[task_id]:
        user_data[user_id_str]['balance']+=TASK_REWARD;user_data[user_id_str]['total_earned']+=TASK_REWARD;user_data[user_id_str].setdefault('tasks_completed',{})[task_id]=get_today_str()
        log_transaction(user_id_str,TASK_REWARD,"Task",f"Completed {TASK_DATA[task_id]['name']}");save_data(user_data,USER_DATA_FILE);context.user_data.pop('current_task_id',None)
        await update.message.reply_text(f"🎉 <b>Task Complete!</b> You earned <b>₹{TASK_REWARD:.2f}</b>!",parse_mode=ParseMode.HTML,reply_markup=get_main_menu_keyboard(update.effective_user.id));return ConversationHandler.END
    else:await update.message.reply_text("❌ Incorrect code. Please try again.");return AWAITING_CODE
async def cancel_task(update:Update,context:ContextTypes.DEFAULT_TYPE)->int:
    context.user_data.pop('current_task_id',None)
    if update.callback_query:await update.callback_query.answer();await bonus_zone_handler(update,context)
    else:await update.message.reply_text("Task cancelled.",reply_markup=get_main_menu_keyboard(update.effective_user.id))
    return ConversationHandler.END
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
    log_transaction(user_id_str,value,"Gift Code",f"Redeemed code {code}");save_data(user_data,USER_DATA_FILE)
    gift_codes[code].setdefault("used_by",[]).append(user_id_str);save_data(gift_codes,GIFT_CODES_FILE)
    await update.message.reply_text(f"✅ Success! You earned <b>₹{value:.2f}</b>!",parse_mode=ParseMode.HTML,reply_markup=get_main_menu_keyboard(update.effective_user.id));return ConversationHandler.END
async def withdraw_start(update:Update,context:ContextTypes.DEFAULT_TYPE)->int:
    query=update.callback_query;await query.answer();user_id_str=str(query.from_user.id);current_referrals=user_data[user_id_str].get('referrals',0)
    if current_referrals<MIN_REFERRALS_FOR_WITHDRAWAL:
        await query.edit_message_text(f"❌ <b>Withdrawal Locked!</b>\n\nYou need at least <b>{MIN_REFERRALS_FOR_WITHDRAWAL} successful referrals</b>.\nYou have <b>{current_referrals}</b>. You need <b>{MIN_REFERRALS_FOR_WITHDRAWAL-current_referrals} more</b>.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu",callback_data='back_to_menu')]]),parse_mode=ParseMode.HTML);return ConversationHandler.END
    if user_data[user_id_str]['balance']<MIN_WITHDRAWAL:await query.edit_message_text(f"❌ Minimum balance is <b>₹{MIN_WITHDRAWAL:.2f}</b>.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu",callback_data='back_to_menu')]]),parse_mode=ParseMode.HTML);return ConversationHandler.END
    context.user_data.clear();keyboard=[[InlineKeyboardButton("💳 UPI / PayPal",callback_data='withdraw_method_upi')],[InlineKeyboardButton("🎁 Google Play Code",callback_data='withdraw_method_gplay')],[InlineKeyboardButton("🔙 Back to Menu",callback_data='back_to_menu')]]
    await query.edit_message_text(f"💰 Your Balance: <b>₹{user_data[user_id_str]['balance']:.2f}</b>\n\n✨ Choose withdrawal method:",reply_markup=InlineKeyboardMarkup(keyboard),parse_mode=ParseMode.HTML);return CHOOSE_METHOD_W
async def withdraw_method_choice(update:Update,context:ContextTypes.DEFAULT_TYPE)->int:
    query=update.callback_query;await query.answer();method=query.data.replace('withdraw_method_','');context.user_data['withdrawal_method']=method
    await query.edit_message_text(f"💸 You chose <b>{method.upper().replace('UPI','UPI / PayPal')}</b>.\n\n➡️ Enter the amount to withdraw.\nAvailable: <b>₹{user_data[str(query.from_user.id)]['balance']:.2f}</b>\nMin Request: <b>₹{MIN_WITHDRAWAL_PER_REQUEST:.2f}</b>",parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel",callback_data='cancel_withdrawal')]]));return ASKING_AMOUNT_W
async def receive_withdrawal_amount(update:Update,context:ContextTypes.DEFAULT_TYPE)->int:
    user_id_str=str(update.effective_user.id)
    try:
        amount=float(update.message.text)
        if amount<MIN_WITHDRAWAL_PER_REQUEST:await update.message.reply_text(f"🚫 Minimum request is <b>₹{MIN_WITHDRAWAL_PER_REQUEST:.2f}</b>.",parse_mode=ParseMode.HTML);return ASKING_AMOUNT_W
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
    user_data[user_id_str]['balance']-=amount;log_transaction(user_id_str,-amount,"Withdrawal","Withdrawal Request");save_data(user_data,USER_DATA_FILE)
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
        [InlineKeyboardButton("📊 Bot Stats", callback_data='admin_stats'), InlineKeyboardButton("👥 Manage Users", callback_data='admin_manage_users_menu')],
        [InlineKeyboardButton("📢 Broadcast", callback_data='admin_broadcast'), InlineKeyboardButton("🎁 Manage Gift Codes", callback_data='admin_gift_codes')],
        [InlineKeyboardButton("📝 Review Withdrawals", callback_data='admin_view_withdrawals_0')],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_menu')]
    ]
    await query.edit_message_text("👑 *Admin Panel*\n\nWelcome, Admin. Select an option to manage the bot.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    total_users = len(user_data)
    total_balance = sum(u.get('balance', 0) for u in user_data.values())
    pending_withdrawals = 0
    try:
        with open(WITHDRAWALS_FILE, 'r') as f:
            content = f.read().strip()
            if content: pending_withdrawals = content.count("---end---")
    except FileNotFoundError: pass

    stats_text = (f"<b>📊 Bot Statistics</b>\n\n" f"👤 <b>Total Users:</b> {total_users}\n" f"💰 <b>Total Balance in Wallets:</b> ₹{total_balance:.2f}\n" f"⏳ <b>Pending Withdrawals:</b> {pending_withdrawals}\n")
    await query.edit_message_text(stats_text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')]]))

# --- NEW: User Listing and Management ---
async def admin_manage_users_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    keyboard = [
        [InlineKeyboardButton("👥 List All Users", callback_data='admin_list_users_0')],
        [InlineKeyboardButton("🆔 Find User by ID", callback_data='admin_find_user')],
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')]
    ]
    await query.edit_message_text("👥 *User Management*\n\nHow would you like to find a user?", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    page = int(query.data.split('_')[-1])
    
    user_ids = list(user_data.keys())
    start_index = page * USER_LIST_PAGE_SIZE
    end_index = start_index + USER_LIST_PAGE_SIZE
    
    paginated_users = user_ids[start_index:end_index]
    
    if not paginated_users:
        await query.answer("No users on this page.", show_alert=True)
        return

    text = "👥 <b>User List (Page {})</b>\n\n".format(page + 1)
    for uid in paginated_users:
        text += f"▪️ {user_data[uid].get('first_name', 'N/A')} (<code>{uid}</code>) - ₹{user_data[uid].get('balance', 0):.2f}\n"

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data=f"admin_list_users_{page-1}"))
    if end_index < len(user_ids):
        nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"admin_list_users_{page+1}"))
        
    keyboard = [nav_buttons, [InlineKeyboardButton("🔙 Back to User Menu", callback_data='admin_manage_users_menu')]]
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

# --- NEW: Interactive Withdrawal Approval ---
def get_withdrawals():
    try:
        with open(WITHDRAWALS_FILE, 'r') as f:
            content = f.read().strip()
            if not content: return []
            # Filter out empty strings that may result from splitting
            return [req for req in content.split('---end---') if req.strip()]
    except FileNotFoundError:
        return []

async def admin_browse_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    index = int(query.data.split('_')[-1])
    
    withdrawals = get_withdrawals()
    
    if not withdrawals:
        await query.edit_message_text("✅ No pending withdrawals.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')]]))
        return

    if index >= len(withdrawals):
        await query.answer("You are at the end of the list.", show_alert=True)
        index = len(withdrawals) - 1 # Stay on the last item
    
    request_text = withdrawals[index].strip()
    
    # Parse details for the approval button
    user_id = "Unknown"
    amount = "Unknown"
    timestamp = "Unknown"
    for line in request_text.split('\n'):
        if line.startswith("User ID:"): user_id = line.split(':')[1].strip()
        if line.startswith("Amount:"): amount = line.split(':')[1].strip()
        if line.startswith("Time:"): timestamp = line.split(':', 1)[1].strip()

    text = f"<b>📝 Withdrawal Request {index + 1} of {len(withdrawals)}</b>\n\n<pre>{request_text}</pre>"
    
    nav_buttons = []
    if index > 0: nav_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data=f"admin_view_withdrawals_{index-1}"))
    if index < len(withdrawals) - 1: nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"admin_view_withdrawals_{index+1}"))
    
    keyboard = [
        [InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_{timestamp}")],
        nav_buttons,
        [InlineKeyboardButton("🗑️ Clear Entire Log (Confirm)", callback_data='admin_clear_withdrawals_confirm')],
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')]
    ]
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_approve_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    timestamp_to_approve = query.data.split('_', 2)[-1]
    
    withdrawals = get_withdrawals()
    new_withdrawals_content = ""
    approved_request = None
    
    user_id_to_notify, amount_to_notify = None, None

    for req in withdrawals:
        if timestamp_to_approve in req:
            approved_request = req
            for line in req.strip().split('\n'):
                if line.startswith("User ID:"): user_id_to_notify = line.split(':')[1].strip()
                if line.startswith("Amount:"): amount_to_notify = line.split(':')[1].strip()
        else:
            new_withdrawals_content += req + "---end---\n\n"
            
    if approved_request:
        with open(WITHDRAWALS_FILE, 'w') as f:
            f.write(new_withdrawals_content)
            
        await query.answer("✅ Withdrawal Approved!", show_alert=True)
        
        # Notify the user
        if user_id_to_notify and amount_to_notify:
            try:
                success_message = f"✅ Your withdrawal request of <b>₹{float(amount_to_notify):.2f}</b> has been approved and processed. Thank you for using the bot!"
                await context.bot.send_message(chat_id=int(user_id_to_notify), text=success_message, parse_mode=ParseMode.HTML)
            except TelegramError as e:
                logger.warning(f"Could not notify user {user_id_to_notify} about withdrawal approval. Reason: {e}")
                await context.bot.send_message(chat_id=ADMIN_ID, text=f"⚠️ Could not notify user {user_id_to_notify} about withdrawal. They may have blocked the bot.")

        # Refresh the withdrawal view
        query.data = "admin_view_withdrawals_0" # Go back to the first request
        await admin_browse_withdrawals(update, context)
        
    else:
        await query.answer("❌ Could not find this withdrawal. It may have already been processed.", show_alert=True)

# --- (Other admin handlers from V8.0 are here) ---
# ... This includes clearing logs, user management conversation, broadcast, gift codes etc.
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
async def admin_find_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    await query.edit_message_text("👥 *Find User*\n\nPlease send the User ID of the user you want to manage.", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='admin_panel_cancel')]]))
    return AWAIT_USER_ID
async def admin_receive_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id_to_manage = update.message.text.strip()
    if not user_id_to_manage.isdigit() or user_id_to_manage not in user_data:
        await update.message.reply_text("❌ User not found. Please send a valid User ID from the database.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel_cancel_msg')]]))
        return AWAIT_USER_ID
    context.user_data['target_user_id'] = user_id_to_manage; target_user = user_data[user_id_to_manage]
    info_text = (f"<b>👤 Managing User:</b> {target_user.get('first_name', 'N/A')}\n" f"<b>ID:</b> <code>{user_id_to_manage}</code>\n" f"<b>Username:</b> @{target_user.get('username', 'N/A')}\n" f"<b>Balance:</b> ₹{target_user.get('balance', 0):.2f}\n" f"<b>Referrals:</b> {target_user.get('referrals', 0)}\n")
    keyboard = [[InlineKeyboardButton("💰 Edit Balance", callback_data='admin_user_edit_balance')], [InlineKeyboardButton("✉️ Send Message", callback_data='admin_user_send_message')], [InlineKeyboardButton("🔙 Find another user", callback_data='admin_find_user_restart')]]
    await update.message.reply_text(info_text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    return USER_ACTION_MENU
async def admin_user_action_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer(); action = query.data
    if action == 'admin_user_edit_balance': await query.edit_message_text("💰 Please send the new balance for this user."); return AWAIT_NEW_BALANCE
    elif action == 'admin_user_send_message': await query.edit_message_text("✉️ Please send the message you want to forward to this user."); return AWAIT_USER_MESSAGE
    elif action == 'admin_find_user_restart':
        await query.edit_message_text("👥 Please send the User ID of the next user.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel_cancel')]]))
        return AWAIT_USER_ID
    return USER_ACTION_MENU
async def admin_receive_new_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    target_user_id = context.user_data.get('target_user_id')
    try:
        new_balance = float(update.message.text)
        user_data[target_user_id]['balance'] = new_balance; save_data(user_data, USER_DATA_FILE)
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
async def admin_panel_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    context.user_data.clear(); await admin_panel(update, context)
    return ConversationHandler.END
async def admin_panel_cancel_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    await query.message.delete()
    context.user_data.clear();
    return ConversationHandler.END
async def admin_broadcast_start(update:Update,context:ContextTypes.DEFAULT_TYPE)->int:
    query=update.callback_query;await query.answer(); await query.edit_message_text("📢 Send the message to broadcast. Supports HTML.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel",callback_data='cancel_broadcast')]]));return BROADCAST_MESSAGE
# NEW, SMARTEST VERSION
async def admin_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    current_user_data = load_data(USER_DATA_FILE)
    message_to_send = update.message.text

    # --- NEW DEBUGGING LOGIC ---
    # Create a list of target users, EXCLUDING the admin
    target_users = [uid for uid in current_user_data if int(uid) != ADMIN_ID]

    # Check if there's anyone to send to BEFORE starting
    if not target_users:
        await update.message.reply_text(
            f"📢 Broadcast Canceled.\n"
            f"⚠️ There are no other users to send a message to.\n\n"
            f"Total users in database: {len(current_user_data)}\n"
            f"(The admin is always skipped).",
            reply_markup=get_main_menu_keyboard(update.effective_user.id)
        )
        return ConversationHandler.END
    # --- END OF NEW LOGIC ---

    success, fail = 0, 0
    await update.message.reply_text(f"📢 Sending broadcast to {len(target_users)} user(s)... Please wait.")

    # Loop through the pre-filtered target list
    for user_id_str in target_users:
        try:
            # First, TRY to send as HTML
            await context.bot.send_message(chat_id=int(user_id_str), text=message_to_send, parse_mode=ParseMode.HTML)
            success += 1
        except TelegramError as e:
            # If HTML fails, CATCH the error and try again as PLAIN TEXT
            if "can't parse entities" in str(e).lower():
                try:
                    await context.bot.send_message(chat_id=int(user_id_str), text=message_to_send)
                    success += 1
                except Exception as plain_e:
                    logger.warning(f"Failed broadcast (plain text fallback) to {user_id_str}: {plain_e}")
                    fail += 1
            else:
                logger.warning(f"Failed broadcast to {user_id_str}: {e}")
                fail += 1

    # Edit the "Sending..." message to show the final result
    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id,
        message_id=update.message.message_id + 1, # The ID of the "Sending..." message
        text=f"📢 Broadcast Finished.\n✅ Sent: {success}\n❌ Failed: {fail}"
    )
    # We send a new message with the menu because the previous one was edited.
    await update.message.reply_text("You are back in the main menu.", reply_markup=get_main_menu_keyboard(ADMIN_ID))
    return ConversationHandler.END
async def cancel_broadcast(update:Update,context:ContextTypes.DEFAULT_TYPE)->int:
    query=update.callback_query;await query.answer(); await query.edit_message_text("Broadcast cancelled.",reply_markup=get_main_menu_keyboard(query.from_user.id));return ConversationHandler.END
async def admin_gift_codes_menu(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    query=update.callback_query;await query.answer();active_code_count=0
    for code,data in gift_codes.items():
        try:
            if len(data.get("used_by",[]))<data.get("limit",1) and date.today()<=datetime.strptime(data.get("expiry_date","9999-12-31"),"%Y-%m-%d").date():active_code_count+=1
        except:continue
    text=f"🎁 Gift Code Management\n\n<b>{active_code_count}</b> active codes."
    keyboard=[[InlineKeyboardButton("➕ Create New Code",callback_data='admin_create_gift_code')],[InlineKeyboardButton("📋 View Active Codes",callback_data='admin_view_active_codes')],[InlineKeyboardButton("🔙 Back to Admin Panel",callback_data='admin_panel')]]
    await query.edit_message_text(text,parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup(keyboard))
async def admin_view_active_codes(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    query=update.callback_query;await query.answer();text="📋 <b>Active Gift Codes:</b>\n\n";active_codes_list=[]
    for code,data in gift_codes.items():
        try:
            usage,limit,expiry=len(data.get("used_by",[])),data.get("limit",1),datetime.strptime(data.get("expiry_date","9999-12-31"),"%Y-%m-%d").date()
            if usage<limit and date.today()<=expiry:active_codes_list.append(f"<code>{code}</code>: ₹{data['value']:.2f} | {usage}/{limit} used | Expires: {expiry.isoformat()}")
        except:continue
    if not active_codes_list:text+="<i>No active codes found.</i>"
    else:text+="\n".join(active_codes_list)
    await query.edit_message_text(text,parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back",callback_data='admin_gift_codes')]]))
async def admin_create_gift_code_start(update:Update,context:ContextTypes.DEFAULT_TYPE)->int:
    query=update.callback_query;await query.answer();context.user_data.clear()
    await query.edit_message_text(f"Enter code name (e.g., `WELCOME50`):",parse_mode=ParseMode.MARKDOWN);return CREATE_GIFT_CODE_NAME
async def admin_receive_gift_code_name(update:Update,context:ContextTypes.DEFAULT_TYPE)->int:
    code_name=update.message.text.strip().upper()
    if code_name in gift_codes:await update.message.reply_text("Code name already exists.");return CREATE_GIFT_CODE_NAME
    context.user_data['name']=code_name;await update.message.reply_text(f"Enter reward value (e.g., `25`):");return CREATE_GIFT_CODE_VALUE
async def admin_receive_gift_code_value(update:Update,context:ContextTypes.DEFAULT_TYPE)->int:
    try:context.user_data['value']=float(update.message.text);await update.message.reply_text(f"How many users can redeem this code?");return CREATE_GIFT_CODE_LIMIT
    except ValueError:await update.message.reply_text("Invalid value.");return CREATE_GIFT_CODE_VALUE
async def admin_receive_gift_code_limit(update:Update,context:ContextTypes.DEFAULT_TYPE)->int:
    try:context.user_data['limit']=int(update.message.text);await update.message.reply_text(f"Enter expiration date (YYYY-MM-DD):");return CREATE_GIFT_CODE_EXPIRY
    except ValueError:await update.message.reply_text("Invalid limit.");return CREATE_GIFT_CODE_LIMIT
async def admin_receive_gift_code_expiry(update:Update,context:ContextTypes.DEFAULT_TYPE)->int:
    try:
        expiry_str=update.message.text.strip();datetime.strptime(expiry_str,'%Y-%m-%d'); c=context.user_data
        gift_codes[c['name']]={"value":c['value'],"limit":c['limit'],"expiry_date":expiry_str,"used_by":[]}
        save_data(gift_codes,GIFT_CODES_FILE)
        await update.message.reply_text(f"✅ Success! Code `{c['name']}` created.",parse_mode=ParseMode.MARKDOWN,reply_markup=get_main_menu_keyboard(ADMIN_ID));return ConversationHandler.END
    except ValueError:await update.message.reply_text("❌ Invalid date format. Use YYYY-MM-DD.");return CREATE_GIFT_CODE_EXPIRY


def main() -> None:
    """Sets up and runs the bot."""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add all your conversation handlers
    # (Same as before)
    task_conv = ConversationHandler(entry_points=[CallbackQueryHandler(tasks_start,pattern='^tasks_start$')],states={CHOOSE_TASK:[CallbackQueryHandler(task_selected,pattern='^start_task_')],AWAITING_CODE:[MessageHandler(filters.TEXT & ~filters.COMMAND,receive_task_code)]},fallbacks=[CallbackQueryHandler(cancel_task,pattern='^cancel_task$'),CallbackQueryHandler(bonus_zone_handler,pattern='^bonus_zone$')])
    redeem_code_conv = ConversationHandler(entry_points=[CallbackQueryHandler(redeem_code_start,pattern='^redeem_code_start$')],states={AWAITING_GIFT_CODE:[MessageHandler(filters.TEXT & ~filters.COMMAND,receive_gift_code)]},fallbacks=[CallbackQueryHandler(bonus_zone_handler,pattern='^bonus_zone$')])
    withdraw_conv = ConversationHandler(entry_points=[CallbackQueryHandler(withdraw_start,pattern='^withdraw$')],states={CHOOSE_METHOD_W:[CallbackQueryHandler(withdraw_method_choice,pattern='^withdraw_method_')],ASKING_AMOUNT_W:[MessageHandler(filters.TEXT & ~filters.COMMAND,receive_withdrawal_amount)],ASKING_DETAILS_W:[MessageHandler(filters.TEXT & ~filters.COMMAND,receive_withdrawal_details)],CONFIRM_WITHDRAWAL_W:[CallbackQueryHandler(confirm_withdrawal,pattern='^confirm_withdrawal$|^edit_withdrawal_details$')]},fallbacks=[CallbackQueryHandler(cancel_withdrawal,pattern='^cancel_withdrawal$')])
    broadcast_conv = ConversationHandler(entry_points=[CallbackQueryHandler(admin_broadcast_start,pattern='^admin_broadcast$')],states={BROADCAST_MESSAGE:[MessageHandler(filters.TEXT & ~filters.COMMAND,admin_broadcast_message)]},fallbacks=[CallbackQueryHandler(cancel_broadcast,pattern='^cancel_broadcast$')])
    create_gift_code_conv = ConversationHandler(entry_points=[CallbackQueryHandler(admin_create_gift_code_start,pattern='^admin_create_gift_code$')],states={CREATE_GIFT_CODE_NAME:[MessageHandler(filters.TEXT & ~filters.COMMAND,admin_receive_gift_code_name)],CREATE_GIFT_CODE_VALUE:[MessageHandler(filters.TEXT & ~filters.COMMAND,admin_receive_gift_code_value)],CREATE_GIFT_CODE_LIMIT:[MessageHandler(filters.TEXT & ~filters.COMMAND,admin_receive_gift_code_limit)],CREATE_GIFT_CODE_EXPIRY:[MessageHandler(filters.TEXT & ~filters.COMMAND,admin_receive_gift_code_expiry)]},fallbacks=[CallbackQueryHandler(admin_gift_codes_menu,pattern='^admin_gift_codes$')])
    user_management_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_find_user_start, pattern='^admin_find_user$')],
        states={
            AWAIT_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_receive_user_id)],
            USER_ACTION_MENU: [CallbackQueryHandler(admin_user_action_choice, pattern='^admin_user_'), CallbackQueryHandler(admin_find_user_start, pattern='^admin_find_user_restart$')],
            AWAIT_NEW_BALANCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_receive_new_balance)],
            AWAIT_USER_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_receive_user_message)],
        },
        fallbacks=[CallbackQueryHandler(admin_panel_cancel, pattern='^admin_panel_cancel$'), CallbackQueryHandler(admin_panel_cancel_msg, pattern='^admin_panel_cancel_msg$')]
    )

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
    # --- Add all admin handlers ---
    application.add_handler(CallbackQueryHandler(admin_panel, pattern='^admin_panel$'))
    application.add_handler(CallbackQueryHandler(admin_stats, pattern='^admin_stats$'))
    application.add_handler(CallbackQueryHandler(admin_clear_withdrawals_confirm, pattern='^admin_clear_withdrawals_confirm$'))
    application.add_handler(CallbackQueryHandler(admin_clear_withdrawals_do, pattern='^admin_clear_withdrawals_do$'))
    application.add_handler(CallbackQueryHandler(admin_gift_codes_menu, pattern='^admin_gift_codes$'))
    application.add_handler(CallbackQueryHandler(admin_view_active_codes, pattern='^admin_view_active_codes$'))
    application.add_handler(CallbackQueryHandler(admin_manage_users_menu, pattern='^admin_manage_users_menu$'))
    application.add_handler(CallbackQueryHandler(admin_list_users, pattern='^admin_list_users_'))
    application.add_handler(CallbackQueryHandler(admin_browse_withdrawals, pattern='^admin_view_withdrawals_'))
    application.add_handler(CallbackQueryHandler(admin_approve_withdrawal, pattern='^admin_approve_'))

    # --- Add all conversation handlers ---
    application.add_handler(task_conv); application.add_handler(redeem_code_conv); application.add_handler(withdraw_conv)
    application.add_handler(broadcast_conv); application.add_handler(create_gift_code_conv); application.add_handler(user_management_conv)
    
    application.add_handler(CallbackQueryHandler(menu_button_handler))
    
    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()