import asyncio
import logging
from telegram.error import RetryAfter, Forbidden, BadRequest
from database import db
from utils import build_inline_keyboard

current_msg_index = 0

async def ad_job(context):
    """Rotates and posts advertisements to all active groups."""
    global current_msg_index
    messages = await db.get_all_messages()
    
    if not messages:
        return
    
    # Safe index bounds handling
    msg_to_send = messages[current_msg_index % len(messages)]
    current_msg_index = (current_msg_index + 1) % len(messages)

    groups = await db.get_groups()
    reply_markup = await build_inline_keyboard()

    for group in groups:
        try:
            await context.bot.send_message(
                chat_id=group['id'],
                text=msg_to_send['text'],
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            await asyncio.sleep(0.5) 
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await context.bot.send_message(
                    chat_id=group['id'],
                    text=msg_to_send['text'],
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            except Exception: pass
        except BadRequest as e:
            logging.error(f"Failed sending ad to group {group['id']}: {e}")
            # Fallback attempt without HTML formatting if tags were malformed
            try:
                await context.bot.send_message(
                    chat_id=group['id'],
                    text=msg_to_send['text'],
                    reply_markup=reply_markup
                )
            except Exception: pass
        except (Forbidden):
            await db.remove_group(group['id'])
        except Exception as e:
            logging.error(f"Unexpected error in ad_job for group {group['id']}: {e}")
            
