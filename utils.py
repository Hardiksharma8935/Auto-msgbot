from functools import wraps
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from config import OWNER_ID
from database import db

def owner_only(func):
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        if update.effective_user.id != OWNER_ID:
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

async def build_inline_keyboard():
    """Generates the inline keyboard for ad messages."""
    buttons_data = await db.get_all_buttons()
    keyboard = []
    for b in buttons_data:
        if b['btn_type'] == 'url':
            keyboard.append([InlineKeyboardButton(b['name'], url=b['content'])])
        elif b['btn_type'] == 'reply':
            keyboard.append([InlineKeyboardButton(b['name'], callback_data=f"btn:{b['id']}")])
    return InlineKeyboardMarkup(keyboard) if keyboard else None

async def build_reply_keyboard():
    """Generates the persistent user Reply Keyboard menu."""
    is_enabled = await db.get_setting("keyboard_enabled")
    if is_enabled == '0':
        return ReplyKeyboardRemove()
        
    buttons_data = await db.get_all_reply_buttons()
    if not buttons_data:
        return ReplyKeyboardRemove()

    keyboard = []
    row = []
    for b in buttons_data:
        row.append(KeyboardButton(b['name']))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
        
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)
    
