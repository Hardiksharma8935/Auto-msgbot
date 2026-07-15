from functools import wraps
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import OWNER_ID
from database import db

def owner_only(func):
    """Decorator to restrict commands to the bot owner."""
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        if update.effective_user.id != OWNER_ID:
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

async def build_keyboard():
    """Generates the inline keyboard markup containing all active configured buttons."""
    buttons_data = await db.get_all_buttons()
    keyboard = []
    for b in buttons_data:
        if b['btn_type'] == 'url':
            keyboard.append([InlineKeyboardButton(b['name'], url=b['content'])])
        elif b['btn_type'] == 'reply':
            keyboard.append([InlineKeyboardButton(b['name'], callback_data=f"btn:{b['id']}")])
    return InlineKeyboardMarkup(keyboard) if keyboard else None
  
