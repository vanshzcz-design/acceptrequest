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
    MessageEntity,
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
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS        = [7353041224, 6527836651]
ADMIN_ID         = ADMIN_IDS[0]
CHANNEL_ID       = -1002232875049
DATA_FILE        = "bot_data.json"

# Source channel where message IDs below exist.
# If your host/source channel is different from the request channel, set
# FORWARD_SOURCE_CHANNEL_ID in Railway Variables, example: -1002701185142
FORWARD_SOURCE_CHANNEL_ID = int(os.getenv("FORWARD_SOURCE_CHANNEL_ID", "-1002701185142"))

# Message IDs inside the source/host channel to copy (no forward tag) to users.
# You can override from Railway Variables: FORWARD_MSG_IDS=10,11
def _parse_forward_msg_ids() -> list[int]:
    raw = os.getenv("FORWARD_MSG_IDS", "10,11")
    ids: list[int] = []
    for part in raw.replace(" ", "").split(","):
        if part and part.lstrip("-").isdigit():
            ids.append(int(part))
    return ids or [10, 11]

FORWARD_MSG_IDS  = _parse_forward_msg_ids()

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
        "welcome_msg":        None,
        "welcome_entities":   None,
        "request_msg":        None,
        "request_entities":   None,
        "accepted_msg":       None,
        "accepted_entities":  None,
        "declined_msg":       None,
        "declined_entities":  None,
        "left_msg":           None,
        "left_entities":      None,
        "auto_accept":        False,
        "auto_accept_delay":  0,
        "activity_channel_id": CHANNEL_ID,
        "forward_source_channel_id": FORWARD_SOURCE_CHANNEL_ID,
        "admin_join_leave_notify": False,
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
            for k, v in _DEFAULTS.items():
                if k not in stored:
                    stored[k] = copy.deepcopy(v)
            for k, v in _DEFAULTS["settings"].items():
                stored["settings"].setdefault(k, v)
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
# Migration: if an old DB stored the request channel as forward source, reset it to host channel.
try:
    _settings = bot_data.setdefault("settings", {})
    if int(_settings.get("forward_source_channel_id") or CHANNEL_ID) == int(CHANNEL_ID):
        _settings["forward_source_channel_id"] = int(FORWARD_SOURCE_CHANNEL_ID)
        save_data(bot_data)
except Exception as _e:
    logger.warning(f"forward source migration skipped: {_e}")


def get_activity_channel_id() -> int:
    """Return the channel ID used for all bot activities.
    Admin can change this from Settings. Falls back to CHANNEL_ID.
    """
    try:
        return int(bot_data.get("settings", {}).get("activity_channel_id") or CHANNEL_ID)
    except Exception:
        return int(CHANNEL_ID)


def set_activity_channel_id(channel_id: int):
    bot_data.setdefault("settings", {})["activity_channel_id"] = int(channel_id)
    save_data(bot_data)


def get_forward_source_channel_id() -> int:
    """Return the host/source channel ID used for copy_message.
    This can be different from the activity/request channel.
    """
    try:
        return int(bot_data.get("settings", {}).get("forward_source_channel_id") or FORWARD_SOURCE_CHANNEL_ID)
    except Exception:
        return int(FORWARD_SOURCE_CHANNEL_ID)


def set_forward_source_channel_id(channel_id: int):
    bot_data.setdefault("settings", {})["forward_source_channel_id"] = int(channel_id)
    save_data(bot_data)

# ═══════════════════════════════════════════════════════
#  ENTITY SERIALIZATION (for premium emoji support)
# ═══════════════════════════════════════════════════════

def serialize_entities(entities) -> list | None:
    """Convert telegram MessageEntity list to JSON-serializable list."""
    if not entities:
        return None
    result = []
    for e in entities:
        d = {
            "type":   e.type.value if hasattr(e.type, "value") else str(e.type),
            "offset": e.offset,
            "length": e.length,
        }
        if e.url:
            d["url"] = e.url
        if e.user:
            d["user_id"] = e.user.id
        if e.language:
            d["language"] = e.language
        if e.custom_emoji_id:
            d["custom_emoji_id"] = e.custom_emoji_id
        result.append(d)
    return result


def deserialize_entities(data_list: list | None) -> list | None:
    """Convert JSON list back to MessageEntity objects."""
    if not data_list:
        return None
    from telegram import User as TGUser
    entities = []
    for d in data_list:
        try:
            entity = MessageEntity(
                type=d["type"],
                offset=d["offset"],
                length=d["length"],
                url=d.get("url"),
                language=d.get("language"),
                custom_emoji_id=d.get("custom_emoji_id"),
            )
            entities.append(entity)
        except Exception as ex:
            logger.warning(f"deserialize_entities skip: {ex}")
    return entities if entities else None


def shift_entities_for_replacements(
    serialized_entities: list | None,
    original_text: str,
    replacements: dict[str, str],
) -> list | None:
    """
    Deserialize saved entities and shift offsets when placeholders are replaced.
    This keeps premium animated emojis and formatting working in admin messages.
    """
    if not serialized_entities:
        return None

    adjusted = []
    for ent in serialized_entities:
        d = dict(ent)
        offset = int(d.get("offset", 0))
        for placeholder, value in replacements.items():
            start = 0
            while True:
                idx = original_text.find(placeholder, start)
                if idx == -1:
                    break
                if idx < offset:
                    offset += len(value) - len(placeholder)
                start = idx + len(placeholder)
        d["offset"] = offset
        adjusted.append(d)

    return deserialize_entities(adjusted)


def apply_placeholders_with_entities(
    original_text: str,
    serialized_entities: list | None,
    **values,
) -> tuple[str, list | None]:
    replacements = {f"{{{k}}}": str(v) for k, v in values.items()}
    text = original_text
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)

    entities = shift_entities_for_replacements(
        serialized_entities,
        original_text,
        replacements,
    )
    return text, entities


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
        m = await ctx.bot.get_chat_member(get_activity_channel_id(), uid)
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
    entities: list | None = None,
    **kwargs
):
    """
    Send a message; silently ignore if user blocked the bot.
    If entities are provided (for premium emoji support), send without parse_mode.
    Otherwise send with HTML parse_mode.
    """
    try:
        if entities:
            await ctx.bot.send_message(
                uid,
                text,
                entities=entities,
                **kwargs
            )
        else:
            await ctx.bot.send_message(
                uid,
                text,
                parse_mode=ParseMode.HTML,
                **kwargs
            )
        return True
    except TelegramError as e:
        logger.debug(f"safe_send uid={uid}: {e}")
        return False


async def copy_channel_messages_to_user(
    ctx: ContextTypes.DEFAULT_TYPE,
    user_id: int
) -> int:
    """
    Copy channel messages (FORWARD_MSG_IDS) to a user WITHOUT the forward tag.
    Premium emojis are preserved automatically by copy_message.
    Falls back gracefully if a message doesn't exist.
    """
    if not FORWARD_MSG_IDS:
        return 0

    sent = 0
    for msg_id in FORWARD_MSG_IDS:
        try:
            await ctx.bot.copy_message(
                chat_id=user_id,
                from_chat_id=get_forward_source_channel_id(),
                message_id=msg_id,
            )
            sent += 1
            await asyncio.sleep(0.4)
        except BadRequest as e:
            logger.warning(
                f"copy_message source={get_forward_source_channel_id()} mid={msg_id} → uid={user_id}: {e}"
            )
        except TelegramError as e:
            logger.warning(
                f"copy_message source={get_forward_source_channel_id()} mid={msg_id} → uid={user_id}: {e}"
            )
    return sent


async def approve_join_request_safe(
    ctx: ContextTypes.DEFAULT_TYPE,
    user_id: int,
) -> tuple[bool, str]:
    """
    Approve a join request reliably.
    First tries Bot API, then falls back to Telethon.
    """
    try:
        await ctx.bot.approve_chat_join_request(get_activity_channel_id(), user_id)
        return True, "bot_api"
    except BadRequest as e:
        bot_error = str(e)
        logger.warning(f"Bot API approve failed uid={user_id}: {bot_error}")
        if "User_already_participant" in bot_error:
            return True, "already_joined"
        if "Hide_requester_missing" in bot_error:
            return False, "request_missing"
    except TelegramError as e:
        bot_error = str(e)
        logger.warning(f"Bot API approve TelegramError uid={user_id}: {bot_error}")
    except Exception as e:
        bot_error = str(e)
        logger.warning(f"Bot API approve unexpected uid={user_id}: {bot_error}")

    client = await get_telethon_client()
    if client:
        try:
            entity = await client.get_entity(get_activity_channel_id())
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
        await ctx.bot.decline_chat_join_request(get_activity_channel_id(), user_id)
        return True, "bot_api"
    except BadRequest as e:
        bot_error = str(e)
        logger.warning(f"Bot API decline failed uid={user_id}: {bot_error}")
        if "Hide_requester_missing" in bot_error:
            return False, "request_missing"
    except TelegramError as e:
        bot_error = str(e)
        logger.warning(f"Bot API decline TelegramError uid={user_id}: {bot_error}")
    except Exception as e:
        bot_error = str(e)
        logger.warning(f"Bot API decline unexpected uid={user_id}: {bot_error}")

    client = await get_telethon_client()
    if client:
        try:
            entity = await client.get_entity(get_activity_channel_id())
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
#  Returns (text, entities_or_None)
#  If custom message with saved entities → returns (text, entities)
#  If custom message text only → returns (text, None) with HTML parse_mode
#  If default → returns (html_text, None)
# ═══════════════════════════════════════════════════════

def fmt_accepted_msg(first_name: str) -> tuple[str, list | None]:
    custom      = bot_data["settings"].get("accepted_msg")
    custom_ents = bot_data["settings"].get("accepted_entities")
    if custom:
        return apply_placeholders_with_entities(
            custom,
            custom_ents,
            first_name=first_name,
        )
    return (
        f"{E_PARTY} <b>Request Approved!</b> {E_PARTY}\n\n"
        f"{E_CROWN} Congratulations, <b>{first_name}</b>!\n\n"
        f"{E_CHECK} Your join request has been <b>approved</b>.\n"
        f"{E_DIAMOND} You now have <b>full access</b> to the channel.\n\n"
        f"{E_FIRE} Welcome to the community!\n"
        f"{E_SPARK} Enjoy your stay {E_100}"
    ), None


def fmt_declined_msg(first_name: str) -> tuple[str, list | None]:
    custom      = bot_data["settings"].get("declined_msg")
    custom_ents = bot_data["settings"].get("declined_entities")
    if custom:
        return apply_placeholders_with_entities(
            custom,
            custom_ents,
            first_name=first_name,
        )
    return (
        f"{E_CROSS} <b>Request Declined</b>\n\n"
        f"{E_WARN} Sorry <b>{first_name}</b>, your join request was <b>declined</b>.\n\n"
        f"{E_INFO} Please contact the admin for more information."
    ), None


def fmt_welcome_msg(first_name: str) -> tuple[str, list | None]:
    custom      = bot_data["settings"].get("welcome_msg")
    custom_ents = bot_data["settings"].get("welcome_entities")
    if custom:
        return apply_placeholders_with_entities(
            custom,
            custom_ents,
            first_name=first_name,
        )
    return (
        f"{E_PARTY} <b>Welcome to the Channel!</b> {E_PARTY}\n\n"
        f"{E_STAR} Hello <b>{first_name}</b>!\n\n"
        f"{E_DIAMOND} You are now a verified member.\n"
        f"{E_FIRE} We're thrilled to have you here!\n\n"
        f"{E_CROWN} Enjoy the content {E_SPARK}"
    ), None


def fmt_request_msg(first_name: str) -> tuple[str, list | None]:
    custom      = bot_data["settings"].get("request_msg")
    custom_ents = bot_data["settings"].get("request_entities")
    if custom:
        return apply_placeholders_with_entities(
            custom,
            custom_ents,
            first_name=first_name,
        )
    return (
        f"{E_BELL} <b>Request Received!</b>\n\n"
        f"{E_STAR} Hello <b>{first_name}</b>!\n\n"
        f"{E_CHECK} Your join request has been <b>received</b>.\n"
        f"{E_HOUR} Please wait while an admin reviews it.\n\n"
        f"{E_INFO} You will be notified once it's processed.\n\n"
        f"{E_SPARK} Thank you for your patience! {E_100}"
    ), None


def fmt_left_msg(first_name: str) -> tuple[str, list | None]:
    custom      = bot_data["settings"].get("left_msg")
    custom_ents = bot_data["settings"].get("left_entities")
    if custom:
        return apply_placeholders_with_entities(
            custom,
            custom_ents,
            first_name=first_name,
        )
    return (
        f"{E_CHAT} <b>Hello {first_name} bhai!</b>\n\n"
        f"{E_INFO} Agar koi problem thi ya aapko help chahiye, toh hum hamesha yahan hain {E_ARROW} @ADNAN_HACK_MANAGER\n\n"
        f"{E_FREE} <b>SPECIAL GIFT CODE JUST FOR YOU:</b>\n"
        f"{E_SPARK} <code>F65F5A6AB87B0A5AD6141EE73BB9C656</code> {E_SPARK}\n\n"
        f"{E_FIRE} Wapas join karo aur apna reward miss mat karo!\n"
        f"{E_LINK} https://t.me/+25K-yX2HWtBiZTk1\n\n"
        f"{E_LIGHT} Jaldi join karo — niche hack de diya hai, use karo aur profit karo!"
    ), None


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
            InlineKeyboardButton("🔗 Telethon Login",     callback_data="adm_telethon"),
            InlineKeyboardButton("🔍 Pick Old Requests",  callback_data="adm_pick_old"),
        ],
        [
            InlineKeyboardButton("📨 Forward Test",       callback_data="adm_fwd_test"),
            InlineKeyboardButton("🔄 Refresh",            callback_data="adm_home"),
        ],
        [
            InlineKeyboardButton("⬇️ Get DB",             callback_data="adm_get_db"),
            InlineKeyboardButton("⬆️ Upload DB",          callback_data="adm_upload_db"),
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
        channel_link_id = str(get_activity_channel_id()).replace("-100", "")
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
            f"{E_DOWN}  /getdb        — Download database file\n"
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
#  JOIN REQUEST HANDLER
# ═══════════════════════════════════════════════════════
async def on_join_request(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    req: ChatJoinRequest = update.chat_join_request
    user    = req.from_user
    uid     = user.id
    uid_str = str(uid)

    # Only process requests from the active/admin-set channel.
    if req.chat.id != get_activity_channel_id():
        logger.info(f"Ignored join request from non-active channel {req.chat.id}; active={get_activity_channel_id()}")
        return

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
    # ── Already recorded → send host-channel copy again (rejoin/duplicate request) ──
    if uid_str in bot_data["pending_requests"]:
        # Rejoin/duplicate request: ALWAYS copy host-channel messages only.
        # No normal fallback message here, so premium emojis stay exactly as in host channel.
        copied_count = await copy_channel_messages_to_user(ctx, uid)
        if copied_count == 0:
            logger.warning(
                f"No host-channel messages copied for duplicate request uid={uid}. "
                f"Check forward source={get_forward_source_channel_id()} and msg_ids={FORWARD_MSG_IDS}"
            )
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

        # Auto-accept request DM: ALWAYS copy host-channel messages only.
        # Do not send the normal accepted/request message here.
        copied_count = await copy_channel_messages_to_user(ctx, uid)
        if copied_count == 0:
            logger.warning(
                f"No host-channel messages copied for auto-accepted request uid={uid}. "
                f"Check forward source={get_forward_source_channel_id()} and msg_ids={FORWARD_MSG_IDS}"
            )
        return

    # ── Manual-review flow ───────────────────────────────
    # Join request DM: copy host-channel messages without forward tag.
    # copy_message preserves premium animated emoji entities.
    copied_count = await copy_channel_messages_to_user(ctx, uid)
    if copied_count == 0:
        logger.warning(
            f"No host-channel messages copied for new request uid={uid}. "
            f"Check forward source={get_forward_source_channel_id()} and msg_ids={FORWARD_MSG_IDS}"
        )

    # Notify admins with accept / decline buttons
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
    # Admin notification toggle also controls new join-request alerts.
    # User still receives the copied host-channel message above.
    if bot_data["settings"].get("admin_join_leave_notify", False):
        await notify_admins(ctx, admin_text, reply_markup=admin_kb)


# ═══════════════════════════════════════════════════════
#  CHAT MEMBER HANDLER  (joined / left)
#  FIX: Use ANY_CHAT_MEMBER to capture all member events.
#  FIX: left message now correctly sends via safe_send.
# ═══════════════════════════════════════════════════════
async def on_chat_member(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # Handle both chat_member and my_chat_member updates
    evt = update.chat_member or update.my_chat_member
    if not evt:
        return

    # Only process events for the active/admin-set channel.
    active_channel_id = get_activity_channel_id()
    if evt.chat.id != active_channel_id:
        logger.info(f"Ignored chat_member update from channel {evt.chat.id}; active={active_channel_id}")
        return

    user       = evt.new_chat_member.user
    uid_str    = str(user.id)
    old_status = evt.old_chat_member.status
    new_status = evt.new_chat_member.status

    LEFT_STATUSES   = {ChatMemberStatus.LEFT, ChatMemberStatus.BANNED}
    ACTIVE_STATUSES = {
        ChatMemberStatus.MEMBER,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.OWNER,
    }

    # ── JOINED ──────────────────────────────────────────
    if old_status in LEFT_STATUSES and new_status in ACTIVE_STATUSES:
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

        # Member joined: copy host-channel message only; do not send normal welcome message.
        copied_count = await copy_channel_messages_to_user(ctx, user.id)
        if copied_count == 0:
            logger.warning(
                f"No host-channel messages copied for joined member uid={user.id}. "
                f"Check forward source={get_forward_source_channel_id()} and msg_ids={FORWARD_MSG_IDS}"
            )

        if bot_data["settings"].get("admin_join_leave_notify", False):
            await notify_admins(
                ctx,
                f"{E_GREEN} <b>Member Joined</b>\n\n"
                f"{E_EYES} {user.first_name} "
                f"({'@' + user.username if user.username else 'no username'})\n"
                f"{E_INFO} ID: <code>{user.id}</code>\n"
                f"{E_PIN} Active Channel: <code>{get_activity_channel_id()}</code>",
            )

    # ── LEFT / KICKED ────────────────────────────────────
    elif old_status in ACTIVE_STATUSES and new_status in LEFT_STATUSES:
        bot_data["members"] = [
            u for u in bot_data["members"] if u != uid_str
        ]
        if uid_str not in bot_data["left_members"]:
            bot_data["left_members"].append(uid_str)
        bot_data["stats"]["total_left"] += 1
        save_data(bot_data)

        first_name = user.first_name or "there"

        # FIX: Send left message with custom premium emoji/entity support.
        # Note: Telegram only allows DM if user has started the bot and not blocked it.
        text, ents = fmt_left_msg(first_name)
        sent = await safe_send(ctx, user.id, text, entities=ents)

        if bot_data["settings"].get("admin_join_leave_notify", False):
            await notify_admins(
                ctx,
                f"{E_RED} <b>Member Left</b>\n\n"
                f"{E_EYES} {user.first_name} "
                f"({'@' + user.username if user.username else 'no username'})\n"
                f"{E_INFO} ID: <code>{user.id}</code>\n"
                f"{E_CHAT} Leave DM: <b>{'Sent ✅' if sent else 'Failed ❌ — user must start bot / not block bot'}</b>\n"
                f"{E_PIN} Active Channel: <code>{get_activity_channel_id()}</code>",
            )


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

    elif data == "toggle_admin_join_leave_notify":
        bot_data["settings"]["admin_join_leave_notify"] = not bot_data["settings"].get(
            "admin_join_leave_notify", False
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

    elif data == "set_activity_channel":
        ctx.user_data["awaiting"] = "activity_channel_id"
        await q.edit_message_text(
            f"{E_MEGA} <b>Set Activity Channel</b>\n\n"
            f"Send the channel ID for all bot activities.\n"
            f"Current: <code>{get_activity_channel_id()}</code>\n\n"
            f"Example: <code>-1002232875049</code>\n\n"
            f"Make sure the bot is admin in that channel and has permission to receive member updates.\n"
            f"/cancel to abort.",
            parse_mode=ParseMode.HTML,
        )


    elif data == "set_forward_source_channel":
        ctx.user_data["awaiting"] = "forward_source_channel_id"
        await q.edit_message_text(
            f"{E_MEGA} <b>Set Forward Source Channel</b>\n\n"
            f"Send the host/source channel ID where message IDs {FORWARD_MSG_IDS} exist.\n"
            f"Current: <code>{get_forward_source_channel_id()}</code>\n\n"
            f"Example: <code>-1002701185142</code>\n\n"
            f"Make sure the bot is admin in that source channel and can read/copy messages.\n"
            f"/cancel to abort.",
            parse_mode=ParseMode.HTML,
        )

    elif data.startswith("setmsg_"):
        msg_type = data[7:]
        ctx.user_data["awaiting"] = f"setmsg_{msg_type}"
        await q.edit_message_text(
            f"{E_EDIT} <b>Set {msg_type} message</b>\n\n"
            f"Send the new message.\n"
            f"✅ <b>Premium emojis are fully supported</b> — just paste/send with them.\n"
            f"Placeholders: <code>{{first_name}}</code>\n\n"
            f"/cancel to abort.",
            parse_mode=ParseMode.HTML,
        )

    elif data == "reset_msgs":
        for k in [
            "request_msg",  "request_entities",
            "accepted_msg", "accepted_entities",
            "declined_msg", "declined_entities",
            "welcome_msg",  "welcome_entities",
            "left_msg",     "left_entities",
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

    elif data == "adm_get_db":
        await _cb_get_db(q, ctx)

    elif data == "adm_upload_db":
        ctx.user_data["awaiting"] = "upload_db"
        await q.edit_message_text(
            f"{E_UP} <b>Upload Database</b>\n\n"
            f"Send the <code>bot_data.json</code> file now.\n"
            f"⚠️ This will <b>overwrite</b> current data!\n\n"
            f"/cancel to abort.",
            parse_mode=ParseMode.HTML,
        )

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

    text, ents = fmt_accepted_msg(first_name)
    await safe_send(ctx, target_id, text, entities=ents)
    await copy_channel_messages_to_user(ctx, target_id)

    try:
        await q.edit_message_text(
            f"{E_CHECK} <b>Accepted!</b>\n"
            f"{E_INFO} User <code>{target_id}</code> approved via <b>{method}</b>.",
            reply_markup=back_kb("adm_pending_0"),
            parse_mode=ParseMode.HTML,
        )
    except BadRequest:
        pass


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

    text, ents = fmt_declined_msg(first_name)
    await safe_send(ctx, target_id, text, entities=ents)

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
        await ctx.bot.decline_chat_join_request(get_activity_channel_id(), target_id)
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

        text, ents = fmt_accepted_msg(first_name)
        await safe_send(ctx, uid, text, entities=ents)
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
        text, ents = fmt_declined_msg(first_name)
        await safe_send(ctx, uid, text, entities=ents)
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
    admin_notify = s.get("admin_join_leave_notify", False)
    delay = s.get("auto_accept_delay", 0)

    def yn(v): return "✅ On" if v else "❌ Off"

    text = (
        f"{E_GEAR} <b>Settings</b>\n\n"
        f"{E_PLAY}  Auto Accept : {yn(aa)}\n"
        f"{E_BELL} Admin Join/Leave Notify : {yn(admin_notify)}\n"
        f"{E_HOUR} Auto Delay  : {delay}s\n"
        f"{E_MEGA} Activity Channel : <code>{get_activity_channel_id()}</code>\n"
        f"{E_MAIL} Forward Source : <code>{get_forward_source_channel_id()}</code>\n"
        f"{E_INFO} Forward Msg IDs : <code>{FORWARD_MSG_IDS}</code>\n\n"
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
            InlineKeyboardButton(
                f"{'🔴 Disable' if admin_notify else '🟢 Enable'} Admin Notify",
                callback_data="toggle_admin_join_leave_notify",
            ),
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
        [
            InlineKeyboardButton("📢 Set Activity Channel", callback_data="set_activity_channel"),
        ],
        [
            InlineKeyboardButton("📨 Set Forward Source", callback_data="set_forward_source_channel"),
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
        entity = await client.get_entity(get_activity_channel_id())
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
                from_chat_id=get_forward_source_channel_id(),
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


async def _cb_get_db(q, ctx):
    """Send the database file to the admin."""
    if not Path(DATA_FILE).exists():
        try:
            await q.edit_message_text(
                f"{E_CROSS} <b>Database file not found!</b>",
                reply_markup=back_kb(),
                parse_mode=ParseMode.HTML,
            )
        except BadRequest:
            pass
        return

    try:
        await q.edit_message_text(
            f"{E_HOUR} <b>Sending database…</b>",
            parse_mode=ParseMode.HTML,
        )
    except BadRequest:
        pass

    try:
        with open(DATA_FILE, "rb") as f:
            await ctx.bot.send_document(
                chat_id=q.from_user.id,
                document=f,
                filename=DATA_FILE,
                caption=(
                    f"{E_DOWN} <b>Database Export</b>\n"
                    f"{E_INFO} File: <code>{DATA_FILE}</code>\n"
                    f"{E_CHART} Members: <b>{len(bot_data['members'])}</b>\n"
                    f"{E_GREEN} Pending: <b>{len(bot_data['pending_requests'])}</b>"
                ),
                parse_mode=ParseMode.HTML,
            )
        try:
            await q.edit_message_text(
                f"{E_CHECK} <b>Database sent!</b>",
                reply_markup=back_kb(),
                parse_mode=ParseMode.HTML,
            )
        except BadRequest:
            pass
    except Exception as e:
        logger.error(f"get_db error: {e}")
        try:
            await q.edit_message_text(
                f"{E_CROSS} <b>Error sending DB:</b>\n<code>{e}</code>",
                reply_markup=back_kb(),
                parse_mode=ParseMode.HTML,
            )
        except BadRequest:
            pass


# ═══════════════════════════════════════════════════════
#  TEXT / DOCUMENT MESSAGE HANDLER  (admin input states)
# ═══════════════════════════════════════════════════════
async def on_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle database file uploads from admins."""
    user = update.effective_user
    if not is_admin(user.id):
        return

    awaiting = ctx.user_data.get("awaiting", "")
    if awaiting != "upload_db":
        return

    doc = update.message.document
    if not doc:
        return

    # Validate it's a JSON file
    if not (doc.file_name and doc.file_name.endswith(".json")):
        await update.message.reply_text(
            f"{E_CROSS} Please send a <code>.json</code> file.",
            parse_mode=ParseMode.HTML,
        )
        return

    ctx.user_data.pop("awaiting", None)

    try:
        file = await ctx.bot.get_file(doc.file_id)
        downloaded = await file.download_as_bytearray()
        content    = downloaded.decode("utf-8")

        # Validate JSON
        new_data = json.loads(content)

        # Back-fill missing keys to avoid KeyError after restore
        import copy
        for k, v in _DEFAULTS.items():
            if k not in new_data:
                new_data[k] = copy.deepcopy(v)
        for k, v in _DEFAULTS["settings"].items():
            new_data["settings"].setdefault(k, v)
        for k, v in _DEFAULTS["stats"].items():
            new_data["stats"].setdefault(k, v)

        # Write to disk
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=2, default=str)

        # Reload in memory
        global bot_data
        bot_data = new_data

        await update.message.reply_text(
            f"{E_CHECK} <b>Database Uploaded Successfully!</b>\n\n"
            f"{E_GREEN} Members : <b>{len(bot_data['members'])}</b>\n"
            f"{E_HOUR}  Pending : <b>{len(bot_data['pending_requests'])}</b>\n"
            f"{E_STOP}  Banned  : <b>{len(bot_data['banned_users'])}</b>",
            reply_markup=admin_home_kb(),
            parse_mode=ParseMode.HTML,
        )
    except json.JSONDecodeError as e:
        await update.message.reply_text(
            f"{E_CROSS} <b>Invalid JSON file!</b>\n<code>{e}</code>",
            reply_markup=admin_home_kb(),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.error(f"upload_db error: {e}")
        await update.message.reply_text(
            f"{E_CROSS} <b>Upload failed:</b>\n<code>{e}</code>",
            reply_markup=admin_home_kb(),
            parse_mode=ParseMode.HTML,
        )


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()

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

    elif awaiting == "activity_channel_id":
        channel_text = text.replace(" ", "")
        if not channel_text.startswith("-100") or not channel_text[1:].isdigit():
            await update.message.reply_text(
                f"{E_CROSS} Send a valid private channel ID like <code>-1002232875049</code>.",
                parse_mode=ParseMode.HTML,
            )
            return
        set_activity_channel_id(int(channel_text))
        ctx.user_data.pop("awaiting", None)
        await update.message.reply_text(
            f"{E_CHECK} <b>Activity channel updated!</b>\n"
            f"{E_MEGA} New channel: <code>{get_activity_channel_id()}</code>\n\n"
            f"{E_WARN} Make sure bot is admin in this channel, then restart/deploy the bot.",
            reply_markup=admin_home_kb(),
            parse_mode=ParseMode.HTML,
        )


    elif awaiting == "forward_source_channel_id":
        channel_text = text.replace(" ", "")
        if not channel_text.startswith("-100") or not channel_text[1:].isdigit():
            await update.message.reply_text(
                f"{E_CROSS} Send a valid private channel ID like <code>-1002701185142</code>.",
                parse_mode=ParseMode.HTML,
            )
            return
        set_forward_source_channel_id(int(channel_text))
        ctx.user_data.pop("awaiting", None)
        await update.message.reply_text(
            f"{E_CHECK} <b>Forward source channel updated!</b>\n"
            f"{E_MAIL} New source: <code>{get_forward_source_channel_id()}</code>\n\n"
            f"{E_WARN} Now use 📨 Forward Test. If it still says message not found, the message IDs are wrong or bot cannot access that source channel.",
            reply_markup=admin_home_kb(),
            parse_mode=ParseMode.HTML,
        )

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
            "request":  ("request_msg",  "request_entities"),
            "accepted": ("accepted_msg", "accepted_entities"),
            "declined": ("declined_msg", "declined_entities"),
            "welcome":  ("welcome_msg",  "welcome_entities"),
            "left":     ("left_msg",     "left_entities"),
        }
        keys = key_map.get(msg_type)
        if keys:
            text_key, ents_key = keys
            msg = update.effective_message
            msg_text = msg.text if msg.text is not None else (msg.caption or "")
            raw_entities = msg.entities if msg.text is not None else (msg.caption_entities or [])

            # Store exact copied text + entities so premium animated emojis remain premium emojis.
            bot_data["settings"][text_key] = msg_text
            bot_data["settings"][ents_key] = serialize_entities(raw_entities or [])

            save_data(bot_data)

        ctx.user_data.pop("awaiting", None)
        await update.message.reply_text(
            f"{E_CHECK} <b>{msg_type.title()} message updated!</b>\n"
            f"{E_SPARK} Premium emojis preserved: "
            f"{'✅' if bot_data['settings'].get(keys[1] if keys else '') else '—'}",
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

        # Capture entities for premium emoji support in broadcast
        msg = update.effective_message
        broadcast_text = msg.text if msg.text is not None else (msg.caption or "")
        broadcast_entities = msg.entities if msg.text is not None else (msg.caption_entities or None)

        for uid_str in members:
            try:
                if broadcast_entities:
                    await ctx.bot.send_message(
                        int(uid_str),
                        broadcast_text,
                        entities=broadcast_entities,
                    )
                else:
                    await ctx.bot.send_message(
                        int(uid_str),
                        broadcast_text,
                        parse_mode=ParseMode.HTML,
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
            "snippet": broadcast_text[:80],
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
        await ctx.bot.approve_chat_join_request(get_activity_channel_id(), uid)
    except BadRequest as e:
        logger.info(f"cmd /accept uid={uid}: {e}")

    bot_data["pending_requests"].pop(uid_str, None)
    if uid_str not in bot_data["accepted_users"]:
        bot_data["accepted_users"].append(uid_str)
    bot_data["stats"]["total_accepted"] += 1
    save_data(bot_data)

    text, ents = fmt_accepted_msg(first_name)
    await safe_send(ctx, uid, text, entities=ents)
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
        await ctx.bot.decline_chat_join_request(get_activity_channel_id(), uid)
    except BadRequest as e:
        logger.info(f"cmd /decline uid={uid}: {e}")

    bot_data["pending_requests"].pop(uid_str, None)
    if uid_str not in bot_data["declined_users"]:
        bot_data["declined_users"].append(uid_str)
    bot_data["stats"]["total_declined"] += 1
    save_data(bot_data)

    text, ents = fmt_declined_msg(first_name)
    await safe_send(ctx, uid, text, entities=ents)
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
        await ctx.bot.decline_chat_join_request(get_activity_channel_id(), int(uid_str))
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
            await ctx.bot.approve_chat_join_request(get_activity_channel_id(), uid)
        except Exception:
            pass
        if uid_str not in bot_data["accepted_users"]:
            bot_data["accepted_users"].append(uid_str)
        bot_data["stats"]["total_accepted"] += 1
        ok += 1
        text, ents = fmt_accepted_msg(first_name)
        await safe_send(ctx, uid, text, entities=ents)
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
            await ctx.bot.decline_chat_join_request(get_activity_channel_id(), uid)
        except Exception:
            pass
        if uid_str not in bot_data["declined_users"]:
            bot_data["declined_users"].append(uid_str)
        bot_data["stats"]["total_declined"] += 1
        ok += 1
        text, ents = fmt_declined_msg(first_name)
        await safe_send(ctx, uid, text, entities=ents)
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
        entity = await client.get_entity(get_activity_channel_id())
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


async def cmd_getdb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Download the database file via command."""
    if not is_admin(update.effective_user.id):
        return
    if not Path(DATA_FILE).exists():
        await update.message.reply_text(
            f"{E_CROSS} Database file not found!", parse_mode=ParseMode.HTML
        )
        return
    try:
        with open(DATA_FILE, "rb") as f:
            await ctx.bot.send_document(
                chat_id=update.effective_user.id,
                document=f,
                filename=DATA_FILE,
                caption=(
                    f"{E_DOWN} <b>Database Export</b>\n"
                    f"{E_INFO} File: <code>{DATA_FILE}</code>\n"
                    f"{E_GREEN} Members: <b>{len(bot_data['members'])}</b>\n"
                    f"{E_HOUR}  Pending: <b>{len(bot_data['pending_requests'])}</b>"
                ),
                parse_mode=ParseMode.HTML,
            )
    except Exception as e:
        await update.message.reply_text(
            f"{E_CROSS} Error: <code>{e}</code>", parse_mode=ParseMode.HTML
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
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN env variable is missing. Add it in Railway Variables.")

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
    app.add_handler(CommandHandler("getdb",      cmd_getdb))
    app.add_handler(CommandHandler("broadcast",  cmd_broadcast))
    app.add_handler(CommandHandler("mystatus",   cmd_mystatus))
    app.add_handler(CommandHandler("myinfo",     cmd_myinfo))

    # Join requests (highest priority)
    app.add_handler(ChatJoinRequestHandler(on_join_request))

    # FIX: Use ANY_CHAT_MEMBER to properly capture member join/leave events
    # in channels. CHAT_MEMBER alone misses many channel member updates.
    app.add_handler(
        ChatMemberHandler(on_chat_member, ChatMemberHandler.ANY_CHAT_MEMBER)
    )

    # Inline buttons
    app.add_handler(CallbackQueryHandler(on_callback))

    # Document handler for DB upload (must be before text handler)
    app.add_handler(
        MessageHandler(filters.Document.ALL, on_document)
    )

    # Free-text (admin states + member guard)
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, on_text)
    )

    # Errors
    app.add_error_handler(on_error)

    print("=" * 54)
    print("  🤖  Advanced Request-Accept Bot  —  RUNNING")
    print(f"  📢  Channel  : {get_activity_channel_id()}")
    print(f"  📨  Fwd Src  : {get_forward_source_channel_id()}")
    print(f"  👑  Admins   : {ADMIN_IDS}")
    print(f"  📨  Fwd IDs  : {FORWARD_MSG_IDS}")
    print("=" * 54)

    app.run_polling(
        allowed_updates=[
            Update.MESSAGE,
            Update.CALLBACK_QUERY,
            Update.CHAT_JOIN_REQUEST,
            Update.CHAT_MEMBER,        # channel member updates
            Update.MY_CHAT_MEMBER,     # bot's own member updates
        ],
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
