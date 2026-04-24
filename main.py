import os
import json
import asyncio
import logging
from datetime import datetime
from pathlib import Path

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatJoinRequest,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ChatJoinRequestHandler,
    ChatMemberHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.error import TelegramError, BadRequest

# ── Optional Telethon ──
try:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl.functions.messages import GetChatInviteImportersRequest, HideChatJoinRequestRequest
    from telethon.tl.types import InputUserEmpty
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False
    print("⚠️  Telethon not installed. Run: pip install telethon")

# ═══════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════
BOT_TOKEN        = "8358164358:AAE5xKhSRAlsu3bK2_QkRP9omIDU2OOb42U"
ADMIN_IDS        = [7353041224, 6527836651]
ADMIN_ID         = ADMIN_IDS[0]
CHANNEL_ID       = -1002701185142
DATA_FILE        = "bot_data.json"

# Message IDs inside the channel to copy (no forward tag) to users
FORWARD_MSG_IDS  = [10, 11]

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════
#  PREMIUM EMOJI HELPERS
# ═══════════════════════════════════════════════════════
def pe(emoji_id: str, fallback: str = "✨") -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

E_CROWN   = pe("5217822164362739968", "👑")
E_STAR    = pe("5438496463044752972", "⭐")
E_CHECK   = pe("5206607081334906820", "✔️")
E_CROSS   = pe("5210952531676504517", "❌")
E_FIRE    = pe("5424972470023104089", "🔥")
E_BELL    = pe("5458603043203327669", "🔔")
E_DIAMOND = pe("5427168083074628963", "💎")
E_PARTY   = pe("5461151367559141950", "🎉")
E_WARN    = pe("5447644880824181073", "⚠️")
E_LOCK    = pe("5296369303661067030", "🔒")
E_GLOBE   = pe("5447410659077661506", "🌐")
E_SEARCH  = pe("5231012545799666522", "🔍")
E_GEAR    = pe("5341715473882955310", "⚙️")
E_SHIELD  = pe("5251203410396458957", "🛡")
E_EYES    = pe("5210956306952758910", "👀")
E_MEGA    = pe("5424818078833715060", "📣")
E_LINK    = pe("5271604874419647061", "🔗")
E_INFO    = pe("5334544901428229844", "ℹ️")
E_THUMB   = pe("5337080053119336309", "👍")
E_GREEN   = pe("5416081784641168838", "🟢")
E_RED     = pe("5411225014148014586", "🔴")
E_LIGHT   = pe("5456140674028019486", "⚡")
E_PIN     = pe("5397782960512444700", "📌")
E_NEW     = pe("5382357040008021292", "🆕")
E_CHART   = pe("5231200819986047254", "📊")
E_TRASH   = pe("5445267414562389170", "🗑")
E_STOP    = pe("5260293700088511294", "⛔")
E_BAN     = pe("5240241223632954241", "🚫")
E_ALERT   = pe("5395695537687123235", "🚨")
E_SPARK   = pe("5325547803936572038", "✨")
E_ARROW   = pe("5416117059207572332", "➡️")
E_PLUS    = pe("5397916757333654639", "➕")
E_HOUR    = pe("5386367538735104399", "⌛")
E_REFRESH = pe("5375338737028841420", "🔄")
E_COOL    = pe("5222079954421818267", "🆒")
E_FREE    = pe("5406756500108501710", "🆓")
E_MAIL    = pe("5253742260054409879", "✉️")
E_CHAT    = pe("5443038326535759644", "💬")
E_BOOK    = pe("5222444124698853913", "🔖")
E_HOME    = pe("5416041192905265756", "🏠")
E_DOWN    = pe("5406745015365943482", "⬇️")
E_UP      = pe("5449683594425410231", "🔼")
E_100     = pe("5341498088408234504", "💯")
E_BANG    = pe("5276032951342088188", "💥")
E_EDIT    = pe("5395444784611480792", "✏️")
E_FLAG    = pe("5460755126761312667", "🚩")
E_SHOP    = pe("5406683434124859552", "🛍")
E_COMET   = pe("5224607267797606837", "☄️")
E_MEDAL1  = pe("5440539497383087970", "🥇")
E_OK      = pe("5222079954421818267", "🆒")
E_PLAY    = pe("5264919878082509254", "▶️")

# ═══════════════════════════════════════════════════════
#  DATA PERSISTENCE
# ═══════════════════════════════════════════════════════
_DEFAULTS: dict = {
    "pending_requests": {},
    "accepted_users":   [],
    "declined_users":   [],
    "members":          [],
    "left_members":     [],
    "banned_users":     [],
    "stats": {
        "total_requests": 0,
        "total_accepted": 0,
        "total_declined": 0,
        "total_left":     0,
    },
    "settings": {
        "welcome_msg":       None,
        "request_msg":       None,
        "accepted_msg":      None,
        "declined_msg":      None,
        "left_msg":          None,
        "auto_accept":       False,
        "auto_accept_delay": 0,
    },
    "telethon_session":  None,
    "telethon_api_id":   None,
    "telethon_api_hash": None,
    "telethon_phone":    None,
    "broadcast_history": [],
}


def load_data() -> dict:
    if Path(DATA_FILE).exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                stored = json.load(f)
            import copy
            # Back-fill missing top-level keys
            for k, v in _DEFAULTS.items():
                if k not in stored:
                    stored[k] = copy.deepcopy(v)
            # Back-fill missing settings keys
            for k, v in _DEFAULTS["settings"].items():
                stored["settings"].setdefault(k, v)
            # Back-fill missing stats keys
            for k, v in _DEFAULTS["stats"].items():
                stored["stats"].setdefault(k, v)
            return stored
        except Exception as e:
            logger.error(f"Failed to load data: {e}")
    import copy
    return copy.deepcopy(_DEFAULTS)


def save_data(data: dict):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to save data: {e}")


bot_data: dict = load_data()

# ═══════════════════════════════════════════════════════
#  TELETHON
# ═══════════════════════════════════════════════════════
_telethon_client = None


async def get_telethon_client():
    global _telethon_client
    if not TELETHON_AVAILABLE:
        return None

    if _telethon_client is not None:
        try:
            if _telethon_client.is_connected() and await _telethon_client.is_user_authorized():
                return _telethon_client
        except Exception:
            pass
        _telethon_client = None

    sess     = bot_data.get("telethon_session")
    api_id   = bot_data.get("telethon_api_id")
    api_hash = bot_data.get("telethon_api_hash")
    if not (sess and api_id and api_hash):
        return None

    try:
        _telethon_client = TelegramClient(
            StringSession(sess), int(api_id), api_hash
        )
        await _telethon_client.connect()
        if await _telethon_client.is_user_authorized():
            return _telethon_client
    except Exception as e:
        logger.error(f"Telethon connect error: {e}")

    _telethon_client = None
    return None


# ═══════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════
def is_admin(uid: int) -> bool:
    return int(uid) in ADMIN_IDS


async def notify_admins(ctx: ContextTypes.DEFAULT_TYPE, text: str, **kwargs):
    for admin_id in ADMIN_IDS:
        try:
            await ctx.bot.send_message(
                admin_id, text,
                parse_mode=ParseMode.HTML,
                **kwargs
            )
        except TelegramError as e:
            logger.error(f"Could not notify admin {admin_id}: {e}")


async def is_member(uid: int, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        m = await ctx.bot.get_chat_member(CHANNEL_ID, uid)
        return m.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )
    except Exception:
        return False


async def safe_send(
    ctx: ContextTypes.DEFAULT_TYPE,
    uid: int,
    text: str,
    **kwargs
):
    """
    Send a private message safely.

    Important Telegram limit:
    the bot can DM a user only if the user has started the bot before
    or Telegram currently allows the bot to message them from a join request.
    """
    try:
        await ctx.bot.send_message(
            chat_id=uid,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            **kwargs
        )
        return True
    except TelegramError as e:
        logger.warning(f"safe_send failed uid={uid}: {e}")
        return False


def get_message_html_for_admin_panel(message) -> str:
    """
    Save admin-panel messages exactly as Telegram sends them.

    - Premium animated/custom emojis are stored as <tg-emoji emoji-id=...>.
    - Bold/italic/link entities copied from Telegram are preserved.
    - If the admin typed raw HTML manually, keep it as raw HTML.
    """
    if getattr(message, "entities", None):
        return message.text_html
    return message.text or ""


async def copy_channel_messages_to_user(
    ctx: ContextTypes.DEFAULT_TYPE,
    user_id: int
):
    """
    Copy channel messages (FORWARD_MSG_IDS) to a user WITHOUT the forward tag.
    Premium emojis are preserved automatically by copy_message.
    Falls back gracefully if a message doesn't exist.
    """
    if not FORWARD_MSG_IDS:
        return

    for msg_id in FORWARD_MSG_IDS:
        try:
            await ctx.bot.copy_message(
                chat_id=user_id,
                from_chat_id=CHANNEL_ID,
                message_id=msg_id,
            )
            await asyncio.sleep(0.4)          # slight delay to avoid flood
        except BadRequest as e:
            logger.warning(
                f"copy_message mid={msg_id} → uid={user_id}: {e}"
            )
        except TelegramError as e:
            logger.warning(
                f"copy_message mid={msg_id} → uid={user_id}: {e}"
            )


async def approve_join_request_safe(
    ctx: ContextTypes.DEFAULT_TYPE,
    user_id: int,
) -> tuple[bool, str]:
    """
    Approve a join request reliably.

    First tries the Bot API. If the request was picked with Telethon or is too old
    and the Bot API cannot approve it, falls back to the logged-in Telethon admin
    account. Returns (success, method/error).
    """
    try:
        await ctx.bot.approve_chat_join_request(CHANNEL_ID, user_id)
        return True, "bot_api"
    except BadRequest as e:
        bot_error = str(e)
        logger.warning(f"Bot API approve failed uid={user_id}: {bot_error}")
    except TelegramError as e:
        bot_error = str(e)
        logger.warning(f"Bot API approve TelegramError uid={user_id}: {bot_error}")
    except Exception as e:
        bot_error = str(e)
        logger.warning(f"Bot API approve unexpected uid={user_id}: {bot_error}")

    client = await get_telethon_client()
    if client:
        try:
            entity = await client.get_entity(CHANNEL_ID)
            await client(HideChatJoinRequestRequest(
                peer=entity,
                user_id=int(user_id),
                approved=True,
            ))
            return True, "telethon"
        except Exception as e:
            telethon_error = str(e)
            logger.error(f"Telethon approve failed uid={user_id}: {telethon_error}")
            return False, f"Bot API: {bot_error} | Telethon: {telethon_error}"

    return False, f"Bot API: {bot_error} | Telethon not connected"


async def decline_join_request_safe(
    ctx: ContextTypes.DEFAULT_TYPE,
    user_id: int,
) -> tuple[bool, str]:
    """
    Decline a join request reliably using Bot API, then Telethon fallback.
    """
    try:
        await ctx.bot.decline_chat_join_request(CHANNEL_ID, user_id)
        return True, "bot_api"
    except BadRequest as e:
        bot_error = str(e)
        logger.warning(f"Bot API decline failed uid={user_id}: {bot_error}")
    except TelegramError as e:
        bot_error = str(e)
        logger.warning(f"Bot API decline TelegramError uid={user_id}: {bot_error}")
    except Exception as e:
        bot_error = str(e)
        logger.warning(f"Bot API decline unexpected uid={user_id}: {bot_error}")

    client = await get_telethon_client()
    if client:
        try:
            entity = await client.get_entity(CHANNEL_ID)
            await client(HideChatJoinRequestRequest(
                peer=entity,
                user_id=int(user_id),
                approved=False,
            ))
            return True, "telethon"
        except Exception as e:
            telethon_error = str(e)
            logger.error(f"Telethon decline failed uid={user_id}: {telethon_error}")
            return False, f"Bot API: {bot_error} | Telethon: {telethon_error}"

    return False, f"Bot API: {bot_error} | Telethon not connected"


# ═══════════════════════════════════════════════════════
#  MESSAGE FORMATTERS
# ═══════════════════════════════════════════════════════
def fmt_accepted_msg(first_name: str) -> str:
    custom = bot_data["settings"].get("accepted_msg")
    if custom:
        return custom.replace("{first_name}", first_name)
    return (
        f"{E_PARTY} <b>Request Approved!</b> {E_PARTY}\n\n"
        f"{E_CROWN} Congratulations, <b>{first_name}</b>!\n\n"
        f"{E_CHECK} Your join request has been <b>approved</b>.\n"
        f"{E_DIAMOND} You now have <b>full access</b> to the channel.\n\n"
        f"{E_FIRE} Welcome to the community!\n"
        f"{E_SPARK} Enjoy your stay {E_100}"
    )


def fmt_declined_msg(first_name: str) -> str:
    custom = bot_data["settings"].get("declined_msg")
    if custom:
        return custom.replace("{first_name}", first_name)
    return (
        f"{E_CROSS} <b>Request Declined</b>\n\n"
        f"{E_WARN} Sorry <b>{first_name}</b>, your join request was <b>declined</b>.\n\n"
        f"{E_INFO} Please contact the admin for more information."
    )


def fmt_welcome_msg(first_name: str) -> str:
    custom = bot_data["settings"].get("welcome_msg")
    if custom:
        return custom.replace("{first_name}", first_name)
    return (
        f"{E_PARTY} <b>Welcome to the Channel!</b> {E_PARTY}\n\n"
        f"{E_STAR} Hello <b>{first_name}</b>!\n\n"
        f"{E_DIAMOND} You are now a verified member.\n"
        f"{E_FIRE} We're thrilled to have you here!\n\n"
        f"{E_CROWN} Enjoy the content {E_SPARK}"
    )


def fmt_request_msg(first_name: str) -> str:
    custom = bot_data["settings"].get("request_msg")
    if custom:
        return custom.replace("{first_name}", first_name)
    return (
        f"{E_BELL} <b>Request Received!</b>\n\n"
        f"{E_STAR} Hello <b>{first_name}</b>!\n\n"
        f"{E_CHECK} Your join request has been <b>received</b>.\n"
        f"{E_HOUR} Please wait while an admin reviews it.\n\n"
        f"{E_INFO} You will be notified once it's processed.\n\n"
        f"{E_SPARK} Thank you for your patience! {E_100}"
    )


def fmt_left_msg(first_name: str) -> str:
    custom = bot_data["settings"].get("left_msg")
    if custom:
        return custom.replace("{first_name}", first_name)
    return (
        f"{E_STOP} <b>Access Revoked</b> {E_BAN}\n\n"
        f"{E_WARN} Hello <b>{first_name}</b>,\n\n"
        f"{E_CROSS} You <b>can't use the bot anymore</b> as you left the channel.\n\n"
        f"{E_ARROW} Please <b>join again</b> to regain access.\n"
        f"{E_BELL} We hope to see you back soon! {E_SPARK}"
    )


# ═══════════════════════════════════════════════════════
#  KEYBOARDS
# ═══════════════════════════════════════════════════════
def admin_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Statistics",         callback_data="adm_stats"),
            InlineKeyboardButton("👀 Pending",            callback_data="adm_pending_0"),
        ],
        [
            InlineKeyboardButton("✅ Accept All",         callback_data="adm_accept_all"),
            InlineKeyboardButton("❌ Decline All",        callback_data="adm_decline_all"),
        ],
        [
            InlineKeyboardButton("📣 Broadcast",          callback_data="adm_broadcast"),
            InlineKeyboardButton("⚙️ Settings",           callback_data="adm_settings"),
        ],
        [
            InlineKeyboardButton("👥 Members",            callback_data="adm_members"),
            InlineKeyboardButton("🚫 Banned",             callback_data="adm_banned"),
        ],
        [
            InlineKeyboardButton("🔗 Telethon Login",    callback_data="adm_telethon"),
            InlineKeyboardButton("🔍 Pick Old Requests", callback_data="adm_pick_old"),
        ],
        [
            InlineKeyboardButton("📨 Forward Test",       callback_data="adm_fwd_test"),
            InlineKeyboardButton("🔄 Refresh",            callback_data="adm_home"),
        ],
    ])


def back_kb(cb: str = "adm_home") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔙 Back", callback_data=cb)]]
    )


# ═══════════════════════════════════════════════════════
#  /start
# ═══════════════════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_admin(user.id):
        text = (
            f"{E_CROWN} <b>Admin Control Panel</b> {E_CROWN}\n\n"
            f"{E_STAR} Welcome back, <b>{user.first_name}</b>!\n\n"
            f"{E_CHART} <b>Quick Stats</b>\n"
            f"{E_GREEN}  Pending  : <b>{len(bot_data['pending_requests'])}</b>\n"
            f"{E_CHECK}  Accepted : <b>{bot_data['stats']['total_accepted']}</b>\n"
            f"{E_CROSS}  Declined : <b>{bot_data['stats']['total_declined']}</b>\n"
            f"{E_RED}   Left     : <b>{bot_data['stats']['total_left']}</b>\n"
            f"{E_STOP}  Banned   : <b>{len(bot_data['banned_users'])}</b>\n\n"
            f"{E_ARROW} Choose an action below:"
        )
        await update.message.reply_text(
            text,
            reply_markup=admin_home_kb(),
            parse_mode=ParseMode.HTML,
        )
        return

    # ── Regular user ────────────────────────────────────
    uid_str   = str(user.id)
    in_banned = uid_str in bot_data["banned_users"]

    if in_banned:
        await update.message.reply_text(
            f"{E_STOP} <b>You are banned.</b>\n{E_INFO} Contact admin.",
            parse_mode=ParseMode.HTML,
        )
        return

    member     = await is_member(user.id, ctx)
    in_pending = uid_str in bot_data["pending_requests"]

    if member:
        await update.message.reply_text(
            f"{E_PARTY} <b>Hello {user.first_name}!</b>\n\n"
            f"{E_CHECK} You are an active channel member.\n"
            f"{E_DIAMOND} Use /help to see commands.",
            parse_mode=ParseMode.HTML,
        )
    elif in_pending:
        await update.message.reply_text(
            f"{E_HOUR} <b>Your request is pending</b>, {user.first_name}.\n"
            f"{E_INFO} Please wait for admin approval.",
            parse_mode=ParseMode.HTML,
        )
    else:
        # Build the correct public invite link from the numeric channel id
        channel_link_id = str(CHANNEL_ID).replace("-100", "")
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "📢 Join Channel",
                url=f"https://t.me/c/{channel_link_id}",
            )
        ]])
        await update.message.reply_text(
            f"{E_LOCK} <b>Access Restricted</b>\n\n"
            f"{E_WARN} Hello <b>{user.first_name}</b>,\n"
            f"You need to join our channel first!\n\n"
            f"{E_ARROW} Click below to send a join request.",
            reply_markup=kb,
            parse_mode=ParseMode.HTML,
        )


# ═══════════════════════════════════════════════════════
#  /help
# ═══════════════════════════════════════════════════════
async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_admin(user.id):
        text = (
            f"{E_CROWN} <b>Admin Commands</b>\n\n"
            f"{E_GEAR}  /start        — Admin panel\n"
            f"{E_INFO}  /help         — This message\n"
            f"{E_CHART} /stats        — Statistics\n"
            f"{E_MEGA}  /broadcast    — Broadcast to all members\n"
            f"{E_SEARCH}/user ID      — User info\n"
            f"{E_STOP}  /ban ID       — Ban user\n"
            f"{E_CHECK} /unban ID     — Unban user\n"
            f"{E_THUMB} /accept ID    — Accept request\n"
            f"{E_CROSS} /decline ID   — Decline request\n"
            f"{E_PLAY}  /acceptall    — Accept all pending\n"
            f"{E_TRASH} /declineall   — Decline all pending\n"
            f"{E_EYES}  /pending      — View pending requests\n"
            f"{E_SEARCH}/pick         — Pick old requests via Telethon\n"
            f"{E_REFRESH}/reload      — Reload data from disk\n"
        )
    else:
        text = (
            f"{E_STAR} <b>Commands</b>\n\n"
            f"{E_HOME}  /start      — Start bot\n"
            f"{E_INFO}  /help       — Help\n"
            f"{E_EYES}  /mystatus   — Your membership status\n"
            f"{E_BOOK}  /myinfo     — Your info\n"
        )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ═══════════════════════════════════════════════════════
#  JOIN REQUEST HANDLER  ← KEY FIX: sends messages on request
# ═══════════════════════════════════════════════════════
async def on_join_request(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    req: ChatJoinRequest = update.chat_join_request
    user    = req.from_user
    uid     = user.id
    uid_str = str(uid)

    # ── Banned → instant decline ─────────────────────────
    if uid_str in bot_data["banned_users"]:
        try:
            await req.decline()
        except Exception:
            pass
        await safe_send(
            ctx, uid,
            f"{E_STOP} <b>Request Declined</b>\n\n"
            f"{E_BAN} You are banned from this channel.",
        )
        return

    # ── Already recorded → skip duplicate ───────────────
    if uid_str in bot_data["pending_requests"]:
        return

    # ── Record the request ───────────────────────────────
    bot_data["pending_requests"][uid_str] = {
        "user_id":    uid,
        "first_name": user.first_name or "",
        "last_name":  user.last_name  or "",
        "username":   user.username   or "",
        "date":       datetime.now().isoformat(),
    }
    bot_data["stats"]["total_requests"] += 1
    save_data(bot_data)

    first_name = user.first_name or "there"

    # ── Auto-accept flow ─────────────────────────────────
    if bot_data["settings"].get("auto_accept"):
        delay = bot_data["settings"].get("auto_accept_delay", 0)
        if delay and delay > 0:
            await asyncio.sleep(delay)
        try:
            await req.approve()
        except Exception as e:
            logger.error(f"auto-accept approve uid={uid}: {e}")
            return

        bot_data["pending_requests"].pop(uid_str, None)
        if uid_str not in bot_data["accepted_users"]:
            bot_data["accepted_users"].append(uid_str)
        bot_data["stats"]["total_accepted"] += 1
        save_data(bot_data)

        # Send acceptance message
        await safe_send(ctx, uid, fmt_accepted_msg(first_name))
        # Copy channel messages without forward tag (premium emojis intact)
        await copy_channel_messages_to_user(ctx, uid)
        return

    # ── Manual-review flow ───────────────────────────────
    # 1. Tell the user their request was received
    await safe_send(ctx, uid, fmt_request_msg(first_name))

    # 2. Copy the channel messages to the user NOW (on request received)
    #    so they get the content while waiting — remove this block if you
    #    only want to send after approval.
    await copy_channel_messages_to_user(ctx, uid)

    # 3. Notify admins with accept / decline buttons
    admin_text = (
        f"{E_NEW} <b>New Join Request</b>\n\n"
        f"{E_EYES} <b>Name:</b> {user.first_name or ''} {user.last_name or ''}\n"
        f"{E_LINK} <b>Username:</b> "
        f"{'@' + user.username if user.username else 'N/A'}\n"
        f"{E_INFO} <b>ID:</b> <code>{uid}</code>\n"
        f"{E_CHART} <b>Pending:</b> {len(bot_data['pending_requests'])}"
    )
    admin_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Accept",        callback_data=f"accept_{uid}"),
            InlineKeyboardButton("❌ Decline",       callback_data=f"decline_{uid}"),
        ],
        [
            InlineKeyboardButton("🚫 Ban & Decline", callback_data=f"ban_{uid}"),
            InlineKeyboardButton("👤 Profile",       url=f"tg://user?id={uid}"),
        ],
    ])
    await notify_admins(ctx, admin_text, reply_markup=admin_kb)


# ═══════════════════════════════════════════════════════
#  CHAT MEMBER HANDLER  (joined / left)
# ═══════════════════════════════════════════════════════
async def on_chat_member(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Track channel joins/leaves and message users when they leave."""
    evt = update.chat_member
    if not evt or not evt.chat or evt.chat.id != CHANNEL_ID:
        return

    old_member = evt.old_chat_member
    new_member = evt.new_chat_member
    user = new_member.user
    uid_str = str(user.id)

    old_status = old_member.status
    new_status = new_member.status

    LEFT_STATUSES = {
        ChatMemberStatus.LEFT,
        ChatMemberStatus.BANNED,
        "left",
        "kicked",
    }
    ACTIVE_STATUSES = {
        ChatMemberStatus.MEMBER,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.OWNER,
        "member",
        "administrator",
        "creator",
    }

    old_is_active = old_status in ACTIVE_STATUSES
    new_is_active = new_status in ACTIVE_STATUSES
    old_is_left = old_status in LEFT_STATUSES
    new_is_left = new_status in LEFT_STATUSES

    first_name = user.first_name or "there"

    # ── JOINED ──────────────────────────────────────────
    if old_is_left and new_is_active:
        if uid_str not in bot_data["members"]:
            bot_data["members"].append(uid_str)
        bot_data["left_members"] = [
            u for u in bot_data["left_members"] if u != uid_str
        ]
        bot_data["pending_requests"].pop(uid_str, None)

        if uid_str not in bot_data["accepted_users"]:
            bot_data["accepted_users"].append(uid_str)
            bot_data["stats"]["total_accepted"] += 1

        save_data(bot_data)
        await safe_send(ctx, user.id, fmt_welcome_msg(first_name))
        return

    # ── LEFT / KICKED ────────────────────────────────────
    if old_is_active and new_is_left:
        bot_data["members"] = [u for u in bot_data["members"] if u != uid_str]
        if uid_str not in bot_data["left_members"]:
            bot_data["left_members"].append(uid_str)
        bot_data["stats"]["total_left"] += 1
        save_data(bot_data)

        sent = await safe_send(ctx, user.id, fmt_left_msg(first_name))
        await notify_admins(
            ctx,
            f"{E_RED} <b>Member Left</b>\n\n"
            f"{E_EYES} {first_name} "
            f"({'@' + user.username if user.username else 'no username'})\n"
            f"{E_INFO} ID: <code>{user.id}</code>\n"
            f"{E_MAIL} Leave DM: <b>{'Sent' if sent else 'Failed'}</b>\n\n"
            f"{E_WARN} If DM failed, the user has not started the bot or blocked it.",
        )
        return


# ═══════════════════════════════════════════════════════
#  CALLBACK QUERY ROUTER
# ═══════════════════════════════════════════════════════
async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    user = q.from_user
    data = q.data

    if not is_admin(user.id):
        await q.answer("⛔ Not authorized!", show_alert=True)
        return

    await q.answer()

    if data.startswith("accept_"):
        uid = int(data[7:])
        await _cb_accept_one(q, ctx, uid)

    elif data.startswith("decline_"):
        uid = int(data[8:])
        await _cb_decline_one(q, ctx, uid)

    elif data.startswith("ban_"):
        uid = int(data[4:])
        await _cb_ban_one(q, ctx, uid)

    elif data.startswith("unban_"):
        uid_str = data[6:]
        if uid_str in bot_data["banned_users"]:
            bot_data["banned_users"].remove(uid_str)
            save_data(bot_data)
        await _show_banned(q, ctx)

    elif data == "adm_home":
        await _show_home(q, ctx)

    elif data == "adm_stats":
        await _show_stats(q, ctx)

    elif data.startswith("adm_pending_"):
        page = int(data.split("_")[2])
        await _show_pending(q, ctx, page)

    elif data == "adm_accept_all":
        await _cb_accept_all(q, ctx)

    elif data == "adm_decline_all":
        await _cb_decline_all(q, ctx)

    elif data == "adm_broadcast":
        ctx.user_data["awaiting"] = "broadcast"
        await q.edit_message_text(
            f"{E_MEGA} <b>Broadcast</b>\n\n"
            f"Send your message (HTML supported).\n"
            f"Targets: <b>{len(bot_data['members'])}</b> members.\n\n"
            f"/cancel to abort.",
            parse_mode=ParseMode.HTML,
        )

    elif data == "adm_settings":
        await _show_settings(q, ctx)

    elif data == "toggle_auto_accept":
        bot_data["settings"]["auto_accept"] = not bot_data["settings"].get(
            "auto_accept", False
        )
        save_data(bot_data)
        await _show_settings(q, ctx)

    elif data == "set_delay":
        ctx.user_data["awaiting"] = "auto_accept_delay"
        await q.edit_message_text(
            f"{E_HOUR} Send the delay in <b>seconds</b> (0 = instant):\n"
            f"/cancel to abort.",
            parse_mode=ParseMode.HTML,
        )

    elif data.startswith("setmsg_"):
        msg_type = data[7:]
        ctx.user_data["awaiting"] = f"setmsg_{msg_type}"
        await q.edit_message_text(
            f"{E_EDIT} <b>Set {msg_type} message</b>\n\n"
            f"Send the new message (HTML supported).\n"
            f"Placeholders: <code>{{first_name}}</code>\n\n"
            f"/cancel to abort.",
            parse_mode=ParseMode.HTML,
        )

    elif data == "reset_msgs":
        for k in [
            "request_msg", "accepted_msg", "declined_msg",
            "welcome_msg",  "left_msg",
        ]:
            bot_data["settings"][k] = None
        save_data(bot_data)
        await _show_settings(q, ctx)

    elif data == "adm_members":
        await _show_members(q, ctx)

    elif data == "adm_banned":
        await _show_banned(q, ctx)

    elif data == "adm_telethon":
        await _show_telethon(q, ctx)

    elif data == "telethon_logout":
        await _telethon_logout(q, ctx)

    elif data == "adm_pick_old":
        await _pick_old_requests(q, ctx)

    elif data == "adm_fwd_test":
        await _fwd_test(q, ctx)

    else:
        await q.answer("Unknown action.", show_alert=True)


# ═══════════════════════════════════════════════════════
#  CALLBACK HELPERS
# ═══════════════════════════════════════════════════════
async def _show_home(q, ctx):
    text = (
        f"{E_CROWN} <b>Admin Control Panel</b> {E_CROWN}\n\n"
        f"{E_CHART} <b>Quick Stats</b>\n"
        f"{E_GREEN}  Pending  : <b>{len(bot_data['pending_requests'])}</b>\n"
        f"{E_CHECK}  Accepted : <b>{bot_data['stats']['total_accepted']}</b>\n"
        f"{E_CROSS}  Declined : <b>{bot_data['stats']['total_declined']}</b>\n"
        f"{E_RED}   Left     : <b>{bot_data['stats']['total_left']}</b>\n"
        f"{E_STOP}  Banned   : <b>{len(bot_data['banned_users'])}</b>\n\n"
        f"{E_ARROW} Choose an action below:"
    )
    await q.edit_message_text(
        text,
        reply_markup=admin_home_kb(),
        parse_mode=ParseMode.HTML,
    )


async def _show_stats(q, ctx):
    text = (
        f"{E_CHART} <b>Bot Statistics</b> {E_CHART}\n\n"
        f"{E_HOUR}  Pending requests : <b>{len(bot_data['pending_requests'])}</b>\n"
        f"{E_CHECK} Total accepted   : <b>{bot_data['stats']['total_accepted']}</b>\n"
        f"{E_CROSS} Total declined   : <b>{bot_data['stats']['total_declined']}</b>\n"
        f"{E_GREEN} Current members  : <b>{len(bot_data['members'])}</b>\n"
        f"{E_RED}   Total left       : <b>{bot_data['stats']['total_left']}</b>\n"
        f"{E_STOP}  Banned users     : <b>{len(bot_data['banned_users'])}</b>\n"
        f"{E_FIRE}  Total requests   : <b>{bot_data['stats']['total_requests']}</b>\n"
    )
    await q.edit_message_text(
        text, reply_markup=back_kb(), parse_mode=ParseMode.HTML
    )


async def _show_pending(q, ctx, page: int = 0):
    pending  = list(bot_data["pending_requests"].items())
    per_page = 8
    total    = len(pending)
    start    = page * per_page
    end      = start + per_page
    chunk    = pending[start:end]

    if not pending:
        await q.edit_message_text(
            f"{E_CHECK} <b>No pending requests!</b>",
            reply_markup=back_kb(),
            parse_mode=ParseMode.HTML,
        )
        return

    text = (
        f"{E_EYES} <b>Pending Requests — Page {page + 1}</b>"
        f" ({total} total)\n\n"
    )
    buttons: list[list[InlineKeyboardButton]] = []

    for uid_str, info in chunk:
        name = info.get("first_name", "?")
        text += f"{E_STAR} <b>{name}</b> — <code>{uid_str}</code>\n"
        buttons.append([
            InlineKeyboardButton(f"✅ {name}", callback_data=f"accept_{uid_str}"),
            InlineKeyboardButton(f"❌ {name}", callback_data=f"decline_{uid_str}"),
            InlineKeyboardButton("🚫",          callback_data=f"ban_{uid_str}"),
        ])

    nav = []
    if page > 0:
        nav.append(
            InlineKeyboardButton("⬅️ Prev", callback_data=f"adm_pending_{page - 1}")
        )
    if end < total:
        nav.append(
            InlineKeyboardButton("➡️ Next", callback_data=f"adm_pending_{page + 1}")
        )
    if nav:
        buttons.append(nav)

    buttons.append([
        InlineKeyboardButton("✅ Accept All",  callback_data="adm_accept_all"),
        InlineKeyboardButton("❌ Decline All", callback_data="adm_decline_all"),
    ])
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="adm_home")])

    await q.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML,
    )


async def _cb_accept_one(q, ctx, target_id: int):
    uid_str = str(target_id)

    # Grab user info BEFORE popping from pending
    info = bot_data["pending_requests"].get(uid_str, {})
    first_name = info.get("first_name", "there") or "there"

    ok, method = await approve_join_request_safe(ctx, target_id)
    if not ok:
        try:
            await q.edit_message_text(
                f"{E_CROSS} <b>Accept failed!</b>\n"
                f"{E_INFO} User <code>{target_id}</code> was not approved.\n\n"
                f"<code>{method[:350]}</code>",
                reply_markup=back_kb("adm_pending_0"),
                parse_mode=ParseMode.HTML,
            )
        except BadRequest:
            pass
        return

    bot_data["pending_requests"].pop(uid_str, None)
    if uid_str not in bot_data["accepted_users"]:
        bot_data["accepted_users"].append(uid_str)
    if uid_str not in bot_data["members"]:
        bot_data["members"].append(uid_str)
    bot_data["stats"]["total_accepted"] += 1
    save_data(bot_data)

    # Send acceptance message
    await safe_send(ctx, target_id, fmt_accepted_msg(first_name))
    # Copy channel messages without forward tag (premium emojis preserved)
    await copy_channel_messages_to_user(ctx, target_id)

    try:
        await q.edit_message_text(
            f"{E_CHECK} <b>Accepted!</b>\n"
            f"{E_INFO} User <code>{target_id}</code> approved via <b>{method}</b>.",
            reply_markup=back_kb("adm_pending_0"),
            parse_mode=ParseMode.HTML,
        )
    except BadRequest:
        pass   # message not modified — fine


async def _cb_decline_one(q, ctx, target_id: int):
    uid_str = str(target_id)

    info       = bot_data["pending_requests"].get(uid_str, {})
    first_name = info.get("first_name", "there") or "there"

    ok, method = await decline_join_request_safe(ctx, target_id)
    if not ok:
        try:
            await q.edit_message_text(
                f"{E_CROSS} <b>Decline failed!</b>\n"
                f"{E_INFO} User <code>{target_id}</code> was not declined.\n\n"
                f"<code>{method[:350]}</code>",
                reply_markup=back_kb("adm_pending_0"),
                parse_mode=ParseMode.HTML,
            )
        except BadRequest:
            pass
        return

    bot_data["pending_requests"].pop(uid_str, None)
    if uid_str not in bot_data["declined_users"]:
        bot_data["declined_users"].append(uid_str)
    bot_data["stats"]["total_declined"] += 1
    save_data(bot_data)

    await safe_send(ctx, target_id, fmt_declined_msg(first_name))

    try:
        await q.edit_message_text(
            f"{E_CROSS} <b>Declined!</b>\n"
            f"{E_INFO} User <code>{target_id}</code> declined via <b>{method}</b>.",
            reply_markup=back_kb("adm_pending_0"),
            parse_mode=ParseMode.HTML,
        )
    except BadRequest:
        pass


async def _cb_ban_one(q, ctx, target_id: int):
    uid_str = str(target_id)

    try:
        await ctx.bot.decline_chat_join_request(CHANNEL_ID, target_id)
    except Exception:
        pass

    bot_data["pending_requests"].pop(uid_str, None)
    if uid_str not in bot_data["banned_users"]:
        bot_data["banned_users"].append(uid_str)
    bot_data["stats"]["total_declined"] += 1
    save_data(bot_data)

    await safe_send(
        ctx, target_id,
        f"{E_STOP} <b>Banned & Declined</b>\n\n"
        f"{E_CROSS} You have been banned from this channel.",
    )

    try:
        await q.edit_message_text(
            f"{E_STOP} <b>Banned!</b>\n"
            f"{E_INFO} User <code>{target_id}</code> banned & declined.",
            reply_markup=back_kb("adm_pending_0"),
            parse_mode=ParseMode.HTML,
        )
    except BadRequest:
        pass


async def _cb_accept_all(q, ctx):
    pending = dict(bot_data["pending_requests"])
    if not pending:
        await q.edit_message_text(
            f"{E_CHECK} No pending requests!",
            reply_markup=back_kb(),
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        await q.edit_message_text(
            f"{E_HOUR} <b>Accepting {len(pending)} requests…</b>",
            parse_mode=ParseMode.HTML,
        )
    except BadRequest:
        pass

    ok = fail = 0
    failed_lines = []
    for uid_str, info in pending.items():
        uid        = int(uid_str)
        first_name = info.get("first_name", "there") or "there"

        approved, method = await approve_join_request_safe(ctx, uid)
        if not approved:
            fail += 1
            failed_lines.append(f"{uid}: {method[:120]}")
            await asyncio.sleep(0.2)
            continue

        bot_data["pending_requests"].pop(uid_str, None)
        if uid_str not in bot_data["accepted_users"]:
            bot_data["accepted_users"].append(uid_str)
        if uid_str not in bot_data["members"]:
            bot_data["members"].append(uid_str)
        bot_data["stats"]["total_accepted"] += 1
        ok += 1

        await safe_send(ctx, uid, fmt_accepted_msg(first_name))
        await copy_channel_messages_to_user(ctx, uid)
        await asyncio.sleep(0.2)

    save_data(bot_data)

    extra = ""
    if failed_lines:
        extra = "\n\n<b>Failed:</b>\n<code>" + "\n".join(failed_lines[:5]) + "</code>"
    try:
        await q.edit_message_text(
            f"{E_CHECK} <b>Bulk Accept Complete!</b>\n\n"
            f"{E_GREEN} Success : {ok}\n"
            f"{E_RED}   Failed  : {fail}"
            f"{extra}",
            reply_markup=back_kb(),
            parse_mode=ParseMode.HTML,
        )
    except BadRequest:
        pass


async def _cb_decline_all(q, ctx):
    pending = dict(bot_data["pending_requests"])
    if not pending:
        await q.edit_message_text(
            f"{E_CHECK} No pending requests!",
            reply_markup=back_kb(),
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        await q.edit_message_text(
            f"{E_HOUR} <b>Declining {len(pending)} requests…</b>",
            parse_mode=ParseMode.HTML,
        )
    except BadRequest:
        pass

    ok = fail = 0
    failed_lines = []
    for uid_str, info in pending.items():
        uid        = int(uid_str)
        first_name = info.get("first_name", "there") or "there"

        declined, method = await decline_join_request_safe(ctx, uid)
        if not declined:
            fail += 1
            failed_lines.append(f"{uid}: {method[:120]}")
            await asyncio.sleep(0.2)
            continue

        bot_data["pending_requests"].pop(uid_str, None)
        if uid_str not in bot_data["declined_users"]:
            bot_data["declined_users"].append(uid_str)
        bot_data["stats"]["total_declined"] += 1
        ok += 1
        await safe_send(ctx, uid, fmt_declined_msg(first_name))
        await asyncio.sleep(0.2)

    save_data(bot_data)

    extra = ""
    if failed_lines:
        extra = "\n\n<b>Failed:</b>\n<code>" + "\n".join(failed_lines[:5]) + "</code>"
    try:
        await q.edit_message_text(
            f"{E_CROSS} <b>Bulk Decline Complete!</b>\n\n"
            f"{E_GREEN} Success : {ok}\n"
            f"{E_RED}   Failed  : {fail}"
            f"{extra}",
            reply_markup=back_kb(),
            parse_mode=ParseMode.HTML,
        )
    except BadRequest:
        pass


async def _show_settings(q, ctx):
    s     = bot_data["settings"]
    aa    = s.get("auto_accept", False)
    delay = s.get("auto_accept_delay", 0)

    def yn(v): return "✅ On" if v else "❌ Off"

    text = (
        f"{E_GEAR} <b>Settings</b>\n\n"
        f"{E_PLAY}  Auto Accept : {yn(aa)}\n"
        f"{E_HOUR} Auto Delay  : {delay}s\n\n"
        f"{E_EDIT} <b>Custom messages</b>\n"
        f"  Request  : {'✅ custom' if s.get('request_msg')  else '❌ default'}\n"
        f"  Accepted : {'✅ custom' if s.get('accepted_msg') else '❌ default'}\n"
        f"  Declined : {'✅ custom' if s.get('declined_msg') else '❌ default'}\n"
        f"  Welcome  : {'✅ custom' if s.get('welcome_msg')  else '❌ default'}\n"
        f"  Left     : {'✅ custom' if s.get('left_msg')     else '❌ default'}\n"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"{'🔴 Disable' if aa else '🟢 Enable'} Auto Accept",
                callback_data="toggle_auto_accept",
            ),
            InlineKeyboardButton("⏱ Set Delay", callback_data="set_delay"),
        ],
        [
            InlineKeyboardButton("📝 Request msg",  callback_data="setmsg_request"),
            InlineKeyboardButton("📝 Accepted msg", callback_data="setmsg_accepted"),
        ],
        [
            InlineKeyboardButton("📝 Declined msg", callback_data="setmsg_declined"),
            InlineKeyboardButton("📝 Welcome msg",  callback_data="setmsg_welcome"),
        ],
        [
            InlineKeyboardButton("📝 Left msg",  callback_data="setmsg_left"),
            InlineKeyboardButton("🗑 Reset All", callback_data="reset_msgs"),
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="adm_home")],
    ])
    await q.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)


async def _show_members(q, ctx):
    members = bot_data["members"]
    text    = f"{E_CROWN} <b>Members ({len(members)})</b>\n\n"
    if members:
        for i, uid in enumerate(members[:30], 1):
            text += f"{i}. <code>{uid}</code>\n"
        if len(members) > 30:
            text += f"\n<i>…and {len(members) - 30} more</i>"
    else:
        text += f"{E_INFO} No tracked members yet."
    await q.edit_message_text(text, reply_markup=back_kb(), parse_mode=ParseMode.HTML)


async def _show_banned(q, ctx):
    banned  = bot_data["banned_users"]
    text    = f"{E_STOP} <b>Banned Users ({len(banned)})</b>\n\n"
    buttons: list[list[InlineKeyboardButton]] = []
    if banned:
        for i, uid in enumerate(banned[:20], 1):
            text += f"{i}. <code>{uid}</code>\n"
            buttons.append([
                InlineKeyboardButton(f"✅ Unban {uid}", callback_data=f"unban_{uid}")
            ])
    else:
        text += f"{E_CHECK} No banned users."
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="adm_home")])
    await q.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML,
    )


async def _show_telethon(q, ctx):
    client = await get_telethon_client()
    if client:
        try:
            me   = await client.get_me()
            text = (
                f"{E_GREEN} <b>Telethon Session Active</b>\n\n"
                f"{E_STAR} Logged in as: <b>{me.first_name}</b>\n"
                f"{E_INFO} ID: <code>{me.id}</code>\n"
                f"{E_LINK} Phone: <code>{me.phone}</code>"
            )
            kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔍 Pick Old Requests", callback_data="adm_pick_old"
                    ),
                    InlineKeyboardButton("🔴 Logout", callback_data="telethon_logout"),
                ],
                [InlineKeyboardButton("🔙 Back", callback_data="adm_home")],
            ])
        except Exception as e:
            text = f"{E_CROSS} Session error: {e}"
            kb   = back_kb()
    else:
        text = (
            f"{E_RED} <b>Telethon Not Connected</b>\n\n"
            f"{E_INFO} To log in, send your <b>API ID</b> now.\n\n"
            f"Get API credentials from https://my.telegram.org\n\n"
            f"/cancel to abort."
        )
        ctx.user_data["awaiting"] = "telethon_api_id"
        kb = back_kb()
    await q.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)


async def _telethon_logout(q, ctx):
    global _telethon_client
    if _telethon_client:
        try:
            await _telethon_client.log_out()
        except Exception:
            pass
        _telethon_client = None
    for k in [
        "telethon_session", "telethon_api_id",
        "telethon_api_hash", "telethon_phone",
    ]:
        bot_data[k] = None
    save_data(bot_data)
    await q.edit_message_text(
        f"{E_CHECK} <b>Logged out from Telethon!</b>",
        reply_markup=back_kb(),
        parse_mode=ParseMode.HTML,
    )


async def _pick_old_requests(q, ctx):
    if not TELETHON_AVAILABLE:
        await q.edit_message_text(
            f"{E_CROSS} Telethon not installed.\n"
            f"Run: <code>pip install telethon</code>",
            reply_markup=back_kb(),
            parse_mode=ParseMode.HTML,
        )
        return

    client = await get_telethon_client()
    if not client:
        await q.edit_message_text(
            f"{E_WARN} Telethon not connected!\nPlease login first.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Login", callback_data="adm_telethon")],
                [InlineKeyboardButton("🔙 Back",  callback_data="adm_home")],
            ]),
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        await q.edit_message_text(
            f"{E_HOUR} <b>Fetching old join requests…</b>",
            parse_mode=ParseMode.HTML,
        )
    except BadRequest:
        pass

    try:
        entity = await client.get_entity(CHANNEL_ID)
        result = await client(GetChatInviteImportersRequest(
            peer=entity,
            limit=100,
            requested=True,
            offset_date=None,
            offset_user=InputUserEmpty(),
            q="",
        ))

        if not result.importers:
            await q.edit_message_text(
                f"{E_CHECK} <b>No old pending requests found!</b>",
                reply_markup=back_kb(),
                parse_mode=ParseMode.HTML,
            )
            return

        user_map = {u.id: u for u in result.users}

        for imp in result.importers:
            uid_str = str(imp.user_id)
            u       = user_map.get(imp.user_id)
            bot_data["pending_requests"][uid_str] = {
                "user_id":    imp.user_id,
                "first_name": getattr(u, "first_name", "") or "",
                "last_name":  getattr(u, "last_name",  "") or "",
                "username":   getattr(u, "username",   "") or "",
                "date": (
                    imp.date.isoformat()
                    if imp.date else datetime.now().isoformat()
                ),
            }
        save_data(bot_data)

        text    = f"{E_SEARCH} <b>Found {len(result.importers)} Old Requests</b>\n\n"
        buttons: list[list[InlineKeyboardButton]] = []

        for imp in result.importers[:10]:
            u    = user_map.get(imp.user_id)
            name = getattr(u, "first_name", str(imp.user_id)) or str(imp.user_id)
            text += f"{E_STAR} <b>{name}</b> — <code>{imp.user_id}</code>\n"
            buttons.append([
                InlineKeyboardButton(f"✅ {name}", callback_data=f"accept_{imp.user_id}"),
                InlineKeyboardButton(f"❌ {name}", callback_data=f"decline_{imp.user_id}"),
                InlineKeyboardButton("🚫",          callback_data=f"ban_{imp.user_id}"),
            ])

        if len(result.importers) > 10:
            text += f"\n<i>Showing first 10 of {len(result.importers)}</i>"

        buttons.append([
            InlineKeyboardButton("✅ Accept All",  callback_data="adm_accept_all"),
            InlineKeyboardButton("❌ Decline All", callback_data="adm_decline_all"),
        ])
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="adm_home")])

        await q.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML,
        )

    except Exception as e:
        logger.error(f"pick_old_requests error: {e}")
        await q.edit_message_text(
            f"{E_CROSS} <b>Error:</b>\n<code>{e}</code>",
            reply_markup=back_kb(),
            parse_mode=ParseMode.HTML,
        )


async def _fwd_test(q, ctx):
    """Copy configured channel messages to the admin (no forward tag)."""
    sent   = 0
    errors = []
    for msg_id in FORWARD_MSG_IDS:
        try:
            await ctx.bot.copy_message(
                chat_id=q.from_user.id,
                from_chat_id=CHANNEL_ID,
                message_id=msg_id,
            )
            sent += 1
            await asyncio.sleep(0.4)
        except BadRequest as e:
            errors.append(f"msg_id={msg_id}: {e}")
        except TelegramError as e:
            errors.append(f"msg_id={msg_id}: {e}")

    err_text = "\n".join(errors) if errors else "none"
    try:
        await q.edit_message_text(
            f"{E_CHECK} <b>Forward Test</b>\n\n"
            f"{E_GREEN} Sent  : {sent}/{len(FORWARD_MSG_IDS)}\n"
            f"{E_CROSS} Errors: {err_text}",
            reply_markup=back_kb(),
            parse_mode=ParseMode.HTML,
        )
    except BadRequest:
        pass


# ═══════════════════════════════════════════════════════
#  TEXT MESSAGE HANDLER  (admin input states)
# ═══════════════════════════════════════════════════════
async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (update.message.text or "").strip()
    html_text = get_message_html_for_admin_panel(update.message).strip()

    # /cancel always works
    if text.lower() == "/cancel":
        ctx.user_data.pop("awaiting", None)
        await update.message.reply_text(
            f"{E_CHECK} Cancelled.",
            reply_markup=admin_home_kb() if is_admin(user.id) else None,
            parse_mode=ParseMode.HTML,
        )
        return

    # Non-admin
    if not is_admin(user.id):
        if not await is_member(user.id, ctx):
            await update.message.reply_text(
                f"{E_LOCK} <b>Access Denied</b>\n\n"
                f"{E_WARN} Join the channel first to use the bot.",
                parse_mode=ParseMode.HTML,
            )
        return

    awaiting = ctx.user_data.get("awaiting", "")

    # ── Telethon login flow ──────────────────────────────
    if awaiting == "telethon_api_id":
        if not text.isdigit():
            await update.message.reply_text(
                f"{E_CROSS} Must be a number.", parse_mode=ParseMode.HTML
            )
            return
        bot_data["telethon_api_id"] = text
        save_data(bot_data)
        ctx.user_data["awaiting"] = "telethon_api_hash"
        await update.message.reply_text(
            f"{E_CHECK} API ID saved!\n{E_ARROW} Now send your <b>API Hash</b>:",
            parse_mode=ParseMode.HTML,
        )

    elif awaiting == "telethon_api_hash":
        bot_data["telethon_api_hash"] = text
        save_data(bot_data)
        ctx.user_data["awaiting"] = "telethon_phone"
        await update.message.reply_text(
            f"{E_CHECK} API Hash saved!\n"
            f"{E_ARROW} Now send your <b>phone number</b> (+country code):",
            parse_mode=ParseMode.HTML,
        )

    elif awaiting == "telethon_phone":
        global _telethon_client
        bot_data["telethon_phone"] = text
        save_data(bot_data)
        try:
            _telethon_client = TelegramClient(
                StringSession(),
                int(bot_data["telethon_api_id"]),
                bot_data["telethon_api_hash"],
            )
            await _telethon_client.connect()
            sent_code = await _telethon_client.send_code_request(text)
            ctx.user_data["telethon_phone_hash"] = sent_code.phone_code_hash
            ctx.user_data["awaiting"] = "telethon_code"
            await update.message.reply_text(
                f"{E_CHECK} Code sent!\n"
                f"{E_ARROW} Enter the code with spaces:\n"
                f"e.g. <code>1 2 3 4 5</code>",
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            await update.message.reply_text(
                f"{E_CROSS} Error: {e}", parse_mode=ParseMode.HTML
            )
            ctx.user_data.pop("awaiting", None)

    elif awaiting == "telethon_code":
        code = text.replace(" ", "")
        try:
            await _telethon_client.sign_in(
                bot_data["telethon_phone"],
                code,
                phone_code_hash=ctx.user_data.get("telethon_phone_hash"),
            )
            bot_data["telethon_session"] = _telethon_client.session.save()
            save_data(bot_data)
            ctx.user_data.pop("awaiting", None)
            me = await _telethon_client.get_me()
            await update.message.reply_text(
                f"{E_PARTY} <b>Login Successful!</b>\n\n"
                f"{E_GREEN} Logged in as <b>{me.first_name}</b>"
                f" (<code>{me.id}</code>)",
                reply_markup=admin_home_kb(),
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            err = str(e).lower()
            if "two" in err or "password" in err:
                ctx.user_data["awaiting"] = "telethon_2fa"
                await update.message.reply_text(
                    f"{E_LOCK} <b>2FA Required</b>\n"
                    f"{E_ARROW} Send your password:",
                    parse_mode=ParseMode.HTML,
                )
            else:
                await update.message.reply_text(
                    f"{E_CROSS} Code error: {e}", parse_mode=ParseMode.HTML
                )
                ctx.user_data.pop("awaiting", None)

    elif awaiting == "telethon_2fa":
        try:
            await _telethon_client.sign_in(password=text)
            bot_data["telethon_session"] = _telethon_client.session.save()
            save_data(bot_data)
            ctx.user_data.pop("awaiting", None)
            me = await _telethon_client.get_me()
            await update.message.reply_text(
                f"{E_PARTY} <b>Login Successful!</b>\n"
                f"{E_GREEN} Logged in as <b>{me.first_name}</b>",
                reply_markup=admin_home_kb(),
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            await update.message.reply_text(
                f"{E_CROSS} 2FA error: {e}", parse_mode=ParseMode.HTML
            )
            ctx.user_data.pop("awaiting", None)

    elif awaiting == "auto_accept_delay":
        if text.isdigit():
            bot_data["settings"]["auto_accept_delay"] = int(text)
            save_data(bot_data)
            ctx.user_data.pop("awaiting", None)
            await update.message.reply_text(
                f"{E_CHECK} Delay set to <b>{text}s</b>!",
                reply_markup=admin_home_kb(),
                parse_mode=ParseMode.HTML,
            )
        else:
            await update.message.reply_text(
                f"{E_CROSS} Send a valid number.", parse_mode=ParseMode.HTML
            )

    elif awaiting.startswith("setmsg_"):
        msg_type = awaiting[7:]
        key_map  = {
            "request":  "request_msg",
            "accepted": "accepted_msg",
            "declined": "declined_msg",
            "welcome":  "welcome_msg",
            "left":     "left_msg",
        }
        key = key_map.get(msg_type)
        if key:
            # Store Telegram HTML when entities exist so premium animated emojis
            # remain exactly as copied and pasted from the admin panel.
            bot_data["settings"][key] = html_text
            save_data(bot_data)
        ctx.user_data.pop("awaiting", None)
        await update.message.reply_text(
            f"{E_CHECK} <b>{msg_type.title()} message updated!</b>",
            reply_markup=admin_home_kb(),
            parse_mode=ParseMode.HTML,
        )

    elif awaiting == "broadcast":
        ctx.user_data.pop("awaiting", None)
        members = bot_data["members"]
        if not members:
            await update.message.reply_text(
                f"{E_WARN} No members to broadcast to!",
                parse_mode=ParseMode.HTML,
            )
            return

        prog = await update.message.reply_text(
            f"{E_HOUR} Broadcasting to {len(members)} members…",
            parse_mode=ParseMode.HTML,
        )
        ok = fail = blocked = 0
        for uid_str in members:
            try:
                await ctx.bot.send_message(
                    int(uid_str), html_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True
                )
                ok += 1
            except TelegramError as e:
                err = str(e).lower()
                if "blocked" in err or "deactivated" in err:
                    blocked += 1
                else:
                    fail += 1
            await asyncio.sleep(0.05)

        bot_data["broadcast_history"].append({
            "date":    datetime.now().isoformat(),
            "snippet": html_text[:80],
            "ok":      ok,
            "fail":    fail,
            "blocked": blocked,
        })
        save_data(bot_data)
        await prog.edit_text(
            f"{E_MEGA} <b>Broadcast Complete!</b>\n\n"
            f"{E_GREEN} Delivered : {ok}\n"
            f"{E_RED}   Failed   : {fail}\n"
            f"{E_STOP}  Blocked  : {blocked}",
            parse_mode=ParseMode.HTML,
        )

    else:
        # Admin sent something without a known awaiting state
        await update.message.reply_text(
            f"{E_INFO} Use /start to open the admin panel.",
            reply_markup=admin_home_kb(),
            parse_mode=ParseMode.HTML,
        )


# ═══════════════════════════════════════════════════════
#  STANDALONE ADMIN COMMANDS
# ═══════════════════════════════════════════════════════
async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    text = (
        f"{E_CHART} <b>Stats</b>\n\n"
        f"Pending  : {len(bot_data['pending_requests'])}\n"
        f"Accepted : {bot_data['stats']['total_accepted']}\n"
        f"Declined : {bot_data['stats']['total_declined']}\n"
        f"Members  : {len(bot_data['members'])}\n"
        f"Left     : {bot_data['stats']['total_left']}\n"
        f"Banned   : {len(bot_data['banned_users'])}\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_accept(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not ctx.args:
        await update.message.reply_text(
            f"{E_INFO} /accept &lt;user_id&gt;", parse_mode=ParseMode.HTML
        )
        return
    uid     = int(ctx.args[0])
    uid_str = str(uid)

    info       = bot_data["pending_requests"].get(uid_str, {})
    first_name = info.get("first_name", "there") or "there"

    try:
        await ctx.bot.approve_chat_join_request(CHANNEL_ID, uid)
    except BadRequest as e:
        logger.info(f"cmd /accept uid={uid}: {e}")

    bot_data["pending_requests"].pop(uid_str, None)
    if uid_str not in bot_data["accepted_users"]:
        bot_data["accepted_users"].append(uid_str)
    bot_data["stats"]["total_accepted"] += 1
    save_data(bot_data)

    await safe_send(ctx, uid, fmt_accepted_msg(first_name))
    await copy_channel_messages_to_user(ctx, uid)
    await update.message.reply_text(
        f"{E_CHECK} User {uid} accepted!", parse_mode=ParseMode.HTML
    )


async def cmd_decline(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not ctx.args:
        await update.message.reply_text(
            f"{E_INFO} /decline &lt;user_id&gt;", parse_mode=ParseMode.HTML
        )
        return
    uid     = int(ctx.args[0])
    uid_str = str(uid)

    info       = bot_data["pending_requests"].get(uid_str, {})
    first_name = info.get("first_name", "there") or "there"

    try:
        await ctx.bot.decline_chat_join_request(CHANNEL_ID, uid)
    except BadRequest as e:
        logger.info(f"cmd /decline uid={uid}: {e}")

    bot_data["pending_requests"].pop(uid_str, None)
    if uid_str not in bot_data["declined_users"]:
        bot_data["declined_users"].append(uid_str)
    bot_data["stats"]["total_declined"] += 1
    save_data(bot_data)
    await safe_send(ctx, uid, fmt_declined_msg(first_name))
    await update.message.reply_text(
        f"{E_CROSS} User {uid} declined!", parse_mode=ParseMode.HTML
    )


async def cmd_ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not ctx.args:
        await update.message.reply_text(
            f"{E_INFO} /ban &lt;user_id&gt;", parse_mode=ParseMode.HTML
        )
        return
    uid_str = ctx.args[0]
    try:
        await ctx.bot.decline_chat_join_request(CHANNEL_ID, int(uid_str))
    except Exception:
        pass
    bot_data["pending_requests"].pop(uid_str, None)
    if uid_str not in bot_data["banned_users"]:
        bot_data["banned_users"].append(uid_str)
    save_data(bot_data)
    await update.message.reply_text(
        f"{E_STOP} User {uid_str} banned!", parse_mode=ParseMode.HTML
    )


async def cmd_unban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not ctx.args:
        await update.message.reply_text(
            f"{E_INFO} /unban &lt;user_id&gt;", parse_mode=ParseMode.HTML
        )
        return
    uid_str = ctx.args[0]
    if uid_str in bot_data["banned_users"]:
        bot_data["banned_users"].remove(uid_str)
        save_data(bot_data)
        await update.message.reply_text(
            f"{E_CHECK} User {uid_str} unbanned!", parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            f"{E_WARN} User {uid_str} was not banned.", parse_mode=ParseMode.HTML
        )


async def cmd_acceptall(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    pending = dict(bot_data["pending_requests"])
    if not pending:
        await update.message.reply_text(
            f"{E_CHECK} No pending!", parse_mode=ParseMode.HTML
        )
        return
    msg = await update.message.reply_text(
        f"{E_HOUR} Accepting {len(pending)}…", parse_mode=ParseMode.HTML
    )
    ok = 0
    for uid_str, info in pending.items():
        uid        = int(uid_str)
        first_name = info.get("first_name", "there") or "there"
        try:
            await ctx.bot.approve_chat_join_request(CHANNEL_ID, uid)
        except Exception:
            pass
        if uid_str not in bot_data["accepted_users"]:
            bot_data["accepted_users"].append(uid_str)
        bot_data["stats"]["total_accepted"] += 1
        ok += 1
        await safe_send(ctx, uid, fmt_accepted_msg(first_name))
        await copy_channel_messages_to_user(ctx, uid)
        await asyncio.sleep(0.2)
    bot_data["pending_requests"].clear()
    save_data(bot_data)
    await msg.edit_text(
        f"{E_CHECK} Accepted {ok} requests!", parse_mode=ParseMode.HTML
    )


async def cmd_declineall(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    pending = dict(bot_data["pending_requests"])
    if not pending:
        await update.message.reply_text(
            f"{E_CHECK} No pending!", parse_mode=ParseMode.HTML
        )
        return
    msg = await update.message.reply_text(
        f"{E_HOUR} Declining {len(pending)}…", parse_mode=ParseMode.HTML
    )
    ok = 0
    for uid_str, info in pending.items():
        uid        = int(uid_str)
        first_name = info.get("first_name", "there") or "there"
        try:
            await ctx.bot.decline_chat_join_request(CHANNEL_ID, uid)
        except Exception:
            pass
        if uid_str not in bot_data["declined_users"]:
            bot_data["declined_users"].append(uid_str)
        bot_data["stats"]["total_declined"] += 1
        ok += 1
        await safe_send(ctx, uid, fmt_declined_msg(first_name))
        await asyncio.sleep(0.2)
    bot_data["pending_requests"].clear()
    save_data(bot_data)
    await msg.edit_text(
        f"{E_CROSS} Declined {ok} requests!", parse_mode=ParseMode.HTML
    )


async def cmd_pending(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    pending = bot_data["pending_requests"]
    if not pending:
        await update.message.reply_text(
            f"{E_CHECK} No pending requests!", parse_mode=ParseMode.HTML
        )
        return
    text = f"{E_EYES} <b>Pending ({len(pending)})</b>\n\n"
    for i, (uid, info) in enumerate(list(pending.items())[:30], 1):
        text += f"{i}. <b>{info.get('first_name','?')}</b> — <code>{uid}</code>\n"
    if len(pending) > 30:
        text += f"\n<i>…and {len(pending) - 30} more</i>"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_user(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not ctx.args:
        await update.message.reply_text(
            f"{E_INFO} /user &lt;user_id&gt;", parse_mode=ParseMode.HTML
        )
        return
    uid  = ctx.args[0]
    info = bot_data["pending_requests"].get(uid, {})
    text = (
        f"{E_SEARCH} <b>User Info</b>\n\n"
        f"{E_INFO} ID       : <code>{uid}</code>\n"
        f"{E_STAR}  Name     : {info.get('first_name','?')} {info.get('last_name','')}\n"
        f"{E_LINK}  Username : @{info.get('username','N/A')}\n\n"
        f"Pending  : {'✅' if uid in bot_data['pending_requests'] else '❌'}\n"
        f"Accepted : {'✅' if uid in bot_data['accepted_users']   else '❌'}\n"
        f"Member   : {'✅' if uid in bot_data['members']          else '❌'}\n"
        f"Left     : {'✅' if uid in bot_data['left_members']     else '❌'}\n"
        f"Banned   : {'✅' if uid in bot_data['banned_users']     else '❌'}\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_pick(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not TELETHON_AVAILABLE:
        await update.message.reply_text(
            f"{E_CROSS} Telethon not installed. "
            f"Run: <code>pip install telethon</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    client = await get_telethon_client()
    if not client:
        await update.message.reply_text(
            f"{E_WARN} Telethon not connected! Use /start → Telethon Login.",
            parse_mode=ParseMode.HTML,
        )
        return

    msg = await update.message.reply_text(
        f"{E_HOUR} Fetching old requests…", parse_mode=ParseMode.HTML
    )
    try:
        entity = await client.get_entity(CHANNEL_ID)
        result = await client(GetChatInviteImportersRequest(
            peer=entity, limit=100, requested=True,
            offset_date=None, offset_user=InputUserEmpty(), q="",
        ))

        if not result.importers:
            await msg.edit_text(
                f"{E_CHECK} No old pending requests found!",
                parse_mode=ParseMode.HTML,
            )
            return

        user_map = {u.id: u for u in result.users}
        for imp in result.importers:
            uid_str = str(imp.user_id)
            u       = user_map.get(imp.user_id)
            bot_data["pending_requests"][uid_str] = {
                "user_id":    imp.user_id,
                "first_name": getattr(u, "first_name", "") or "",
                "last_name":  getattr(u, "last_name",  "") or "",
                "username":   getattr(u, "username",   "") or "",
                "date": (
                    imp.date.isoformat()
                    if imp.date else datetime.now().isoformat()
                ),
            }
        save_data(bot_data)

        text    = f"{E_SEARCH} <b>Found {len(result.importers)} requests</b>\n\n"
        buttons: list[list[InlineKeyboardButton]] = []
        for imp in result.importers[:10]:
            u    = user_map.get(imp.user_id)
            name = getattr(u, "first_name", str(imp.user_id)) or str(imp.user_id)
            text += f"{E_STAR} {name} — <code>{imp.user_id}</code>\n"
            buttons.append([
                InlineKeyboardButton(
                    f"✅ {name}", callback_data=f"accept_{imp.user_id}"
                ),
                InlineKeyboardButton(
                    f"❌ {name}", callback_data=f"decline_{imp.user_id}"
                ),
            ])
        buttons.append([
            InlineKeyboardButton("✅ Accept All",  callback_data="adm_accept_all"),
            InlineKeyboardButton("❌ Decline All", callback_data="adm_decline_all"),
        ])
        await msg.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.error(f"cmd_pick error: {e}")
        await msg.edit_text(
            f"{E_CROSS} Error: <code>{e}</code>", parse_mode=ParseMode.HTML
        )


async def cmd_reload(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    global bot_data
    bot_data = load_data()
    await update.message.reply_text(
        f"{E_REFRESH} Data reloaded!", parse_mode=ParseMode.HTML
    )


async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not ctx.args:
        await update.message.reply_text(
            f"{E_INFO} /broadcast &lt;message&gt;", parse_mode=ParseMode.HTML
        )
        return
    text    = " ".join(ctx.args)
    members = bot_data["members"]
    msg     = await update.message.reply_text(
        f"{E_HOUR} Broadcasting…", parse_mode=ParseMode.HTML
    )
    ok = fail = 0
    for uid_str in members:
        try:
            await ctx.bot.send_message(
                int(uid_str), text, parse_mode=ParseMode.HTML
            )
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)
    await msg.edit_text(
        f"{E_MEGA} Done! {E_GREEN} {ok} sent, {E_RED} {fail} failed.",
        parse_mode=ParseMode.HTML,
    )


async def cmd_mystatus(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    uid_str = str(user.id)
    member  = await is_member(user.id, ctx)

    if uid_str in bot_data["banned_users"]:
        status = f"{E_STOP} Banned"
    elif member:
        status = f"{E_GREEN} Active Member"
    elif uid_str in bot_data["pending_requests"]:
        status = f"{E_HOUR} Pending Approval"
    else:
        status = f"{E_RED} Not a Member"

    await update.message.reply_text(
        f"{E_EYES} <b>Your Status</b>\n\n"
        f"{E_INFO} Name   : <b>{user.first_name}</b>\n"
        f"{E_LINK} User   : @{user.username or 'N/A'}\n"
        f"{E_STAR} Status : {status}",
        parse_mode=ParseMode.HTML,
    )


async def cmd_myinfo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"{E_BOOK} <b>Your Info</b>\n\n"
        f"{E_INFO} ID        : <code>{user.id}</code>\n"
        f"{E_STAR}  First Name: {user.first_name}\n"
        f"{E_STAR}  Last Name : {user.last_name or 'N/A'}\n"
        f"{E_LINK}  Username  : @{user.username or 'N/A'}\n"
        f"{E_GLOBE} Language  : {user.language_code or 'N/A'}\n"
        f"{E_DIAMOND} Premium : "
        f"{'✅' if getattr(user, 'is_premium', False) else '❌'}",
        parse_mode=ParseMode.HTML,
    )


# ═══════════════════════════════════════════════════════
#  ERROR HANDLER
# ═══════════════════════════════════════════════════════
async def on_error(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    err = ctx.error
    logger.error(f"Unhandled error: {err}", exc_info=err)
    ignore = ("conflict:", "blocked", "deactivated", "chat not found", "message is not modified")
    if any(s in str(err).lower() for s in ignore):
        return
    await notify_admins(
        ctx,
        f"{E_ALERT} <b>Bot Error:</b>\n<code>{str(err)[:400]}</code>",
    )


# ═══════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("help",       cmd_help))
    app.add_handler(CommandHandler("stats",      cmd_stats))
    app.add_handler(CommandHandler("accept",     cmd_accept))
    app.add_handler(CommandHandler("decline",    cmd_decline))
    app.add_handler(CommandHandler("ban",        cmd_ban))
    app.add_handler(CommandHandler("unban",      cmd_unban))
    app.add_handler(CommandHandler("acceptall",  cmd_acceptall))
    app.add_handler(CommandHandler("declineall", cmd_declineall))
    app.add_handler(CommandHandler("pending",    cmd_pending))
    app.add_handler(CommandHandler("user",       cmd_user))
    app.add_handler(CommandHandler("pick",       cmd_pick))
    app.add_handler(CommandHandler("reload",     cmd_reload))
    app.add_handler(CommandHandler("broadcast",  cmd_broadcast))
    app.add_handler(CommandHandler("mystatus",   cmd_mystatus))
    app.add_handler(CommandHandler("myinfo",     cmd_myinfo))

    # Join requests (highest priority)
    app.add_handler(ChatJoinRequestHandler(on_join_request))

    # Member status changes
    app.add_handler(
        ChatMemberHandler(on_chat_member, ChatMemberHandler.CHAT_MEMBER)
    )

    # Inline buttons
    app.add_handler(CallbackQueryHandler(on_callback))

    # Free-text (admin states + member guard)
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, on_text)
    )

    # Errors
    app.add_error_handler(on_error)

    print("=" * 54)
    print("  🤖  Advanced Request-Accept Bot  —  RUNNING")
    print(f"  📢  Channel  : {CHANNEL_ID}")
    print(f"  👑  Admins   : {ADMIN_IDS}")
    print(f"  📨  Fwd IDs  : {FORWARD_MSG_IDS}")
    print("=" * 54)

    app.run_polling(
        allowed_updates=[
            Update.MESSAGE,
            Update.CALLBACK_QUERY,
            Update.CHAT_JOIN_REQUEST,
            Update.CHAT_MEMBER,
            Update.MY_CHAT_MEMBER,
        ],
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
