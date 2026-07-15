import asyncio
from telegram.error import RetryAfter, Forbidden, BadRequest
from database import db
from utils import build_keyboard

# Global state to maintain rotation sequence across all groups
current_msg_index = 0

async def ad_job(context):
    """Job executed at the configured interval to rotate and broadcast advertisements."""
    global current_msg_index
    messages = await db.get_all_messages()
    
    if not messages:
        return
    
    msg_to_send = messages[current_msg_index % len(messages)]
    current_msg_index += 1

    groups = await db.get_groups()
    reply_markup = await build_keyboard()

    for group in groups:
        try:
            await context.bot.send_message(
                chat_id=group['id'],
                text=msg_to_send['text'],
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            # Anti-spam interval between group sends
            await asyncio.sleep(0.5) 
        except RetryAfter as e:
            # Handles Telegram FloodWait correctly
            await asyncio.sleep(e.retry_after)
            await context.bot.send_message(
                chat_id=group['id'],
                text=msg_to_send['text'],
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        except (Forbidden, BadRequest):
            # Bot kicked or chat deleted; clean up database to optimize future iterations
            await db.remove_group(group['id'])
        except Exception:
            pass
          
