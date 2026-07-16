import logging
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ChatMemberHandler
from config import BOT_TOKEN
from database import db
from handlers import (
    start_cmd, help_cmd, setmessage_cmd, removemessage_cmd, messages_cmd,
    setinterval_cmd, welcome_cmd, button_cmd, keyboard_cmd, groups_cmd, stats_cmd, broadcast_cmd,
    bot_added_to_group, welcome_new_member, handle_dm, handle_callback
)
from jobs import ad_job

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def post_init(application):
    await db.init_db()
    interval_str = await db.get_setting("interval")
    interval = int(interval_str) if interval_str else 30
    application.job_queue.run_repeating(ad_job, interval=interval*60, first=10, name="ad_job")
    logging.info(f"Database initialized. Job scheduled every {interval} minutes.")

if __name__ == '__main__':
    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("setmessage", setmessage_cmd))
    application.add_handler(CommandHandler("removemessage", removemessage_cmd))
    application.add_handler(CommandHandler("messages", messages_cmd))
    application.add_handler(CommandHandler("setinterval", setinterval_cmd))
    application.add_handler(CommandHandler("welcome", welcome_cmd))
    application.add_handler(CommandHandler("buttons", button_cmd))
    application.add_handler(CommandHandler("keyboard", keyboard_cmd))
    application.add_handler(CommandHandler("groups", groups_cmd))
    application.add_handler(CommandHandler("stats", stats_cmd))
    application.add_handler(CommandHandler("broadcast", broadcast_cmd))

    application.add_handler(ChatMemberHandler(bot_added_to_group, ChatMemberHandler.MY_CHAT_MEMBER))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, handle_dm))

    application.run_polling()
    
