import re
import os
import asyncio
from telegram.ext import ContextTypes
from config import OWNER_ID
from database import db
from utils import owner_only, build_keyboard
from jobs import ad_job

# --- Command Handlers ---
@owner_only
async def start_cmd(update, context):
    await update.message.reply_text("👋 Welcome Owner! Use /help to see all configuration commands.")

@owner_only
async def help_cmd(update, context):
    help_text = (
        "🛠 **Owner Control Panel**\n"
        "/setmessage `<html text>` - Add ad\n"
        "/removemessage `<id>` - Delete ad\n"
        "/messages - List ads\n"
        "/setinterval `<minutes>` - Change frequency\n"
        "/welcome `<html text>` - Set welcome\n"
        "/buttons add url | `<Name>` | `<Link>`\n"
        "/buttons add reply | `<Name>` | `<Text>`\n"
        "/buttons del `<id>`\n"
        "/buttons list\n"
        "/groups - Active groups\n"
        "/stats - Bot analytics\n"
        "/broadcast - Reply to any message to send to all users"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

@owner_only
async def setmessage_cmd(update, context):
    text = update.message.text.partition(' ')[2]
    if not text:
        await update.message.reply_text("Usage: `/setmessage <b>My Ad</b>`", parse_mode="Markdown")
        return
    await db.add_message(text)
    await update.message.reply_text("✅ Advertisement message added successfully!")

@owner_only
async def removemessage_cmd(update, context):
    try:
        msg_id = int(context.args[0])
        await db.del_message(msg_id)
        await update.message.reply_text(f"🗑 Message ID {msg_id} deleted!")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: `/removemessage <id>`", parse_mode="Markdown")

@owner_only
async def messages_cmd(update, context):
    msgs = await db.get_all_messages()
    if not msgs:
        await update.message.reply_text("No advertisement messages configured.")
        return
    res = "📜 **Saved Messages:**\n\n"
    for m in msgs:
        res += f"**ID:** {m['id']}\n{m['text']}\n{'-'*20}\n"
    await update.message.reply_text(res[:4000], parse_mode='Markdown')

@owner_only
async def setinterval_cmd(update, context):
    try:
        minutes = int(context.args[0])
        if minutes < 1:
            raise ValueError
        await db.set_setting("interval", str(minutes))
        
        # Reschedule active jobs
        current_jobs = context.job_queue.get_jobs_by_name("ad_job")
        for job in current_jobs:
            job.schedule_removal()
        
        context.job_queue.run_repeating(ad_job, interval=minutes*60, first=5, name="ad_job")
        await update.message.reply_text(f"⏱ Advertisement interval updated to **{minutes} minutes**.", parse_mode="Markdown")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: `/setinterval <minutes>`", parse_mode="Markdown")

@owner_only
async def welcome_cmd(update, context):
    text = update.message.text.partition(' ')[2]
    if not text:
        await update.message.reply_text("Usage: `/welcome <text>`\nHint: Use `{name}` in your text to dynamically insert the user's name.", parse_mode="Markdown")
        return
    await db.set_setting("welcome", text)
    await update.message.reply_text("✅ Welcome message updated!")

@owner_only
async def button_cmd(update, context):
    args = update.message.text.split(maxsplit=1)
    if len(args) < 2:
        await update.message.reply_text("Usage:\n`/buttons add url | Join | https://t.me/example`\n`/buttons add reply | Gift | Here is your private gift!`\n`/buttons del <id>`\n`/buttons list`", parse_mode="Markdown")
        return
    
    cmd_str = args[1]
    if cmd_str.startswith("add"):
        parts = cmd_str[4:].split("|")
        if len(parts) == 3:
            b_type = parts[0].strip().lower()
            name = parts[1].strip()
            content = parts[2].strip()
            if b_type in ['url', 'reply']:
                await db.add_button(name, b_type, content)
                await update.message.reply_text(f"✅ Button '{name}' added successfully!")
            else:
                await update.message.reply_text("Type must be 'url' or 'reply'.")
        else:
            await update.message.reply_text("Invalid format. Use the pipe `|` character to separate arguments.")
    elif cmd_str.startswith("del"):
        try:
            b_id = cmd_str.split()[1]
            await db.del_button(b_id)
            await update.message.reply_text("🗑 Button deleted.")
        except IndexError:
            await update.message.reply_text("Provide the button ID.")
    elif cmd_str.startswith("list"):
        btns = await db.get_all_buttons()
        res = "🔘 **Active Buttons:**\n\n"
        for b in btns:
            res += f"**ID:** {b['id']} | **Name:** {b['name']} | **Type:** {b['btn_type']}\n"
        await update.message.reply_text(res or "No buttons configured.", parse_mode="Markdown")

@owner_only
async def broadcast_cmd(update, context):
    if update.message.reply_to_message:
        users = await db.get_all_users()
        sent, failed = 0, 0
        status_msg = await update.message.reply_text("🚀 Broadcast started...")
        for u in users:
            try:
                await update.message.reply_to_message.copy(u['id'])
                sent += 1
                await asyncio.sleep(0.1) # Anti-Spam
            except Exception:
                failed += 1
        await status_msg.edit_text(f"✅ Broadcast Complete!\n\n**Delivered:** {sent}\n**Failed:** {failed}\n**Total:** {len(users)}", parse_mode="Markdown")
    else:
        await update.message.reply_text("Please reply to a message (text, photo, video, etc) with `/broadcast` to send it out.", parse_mode="Markdown")

@owner_only
async def stats_cmd(update, context):
    users = len(await db.get_all_users())
    groups = len(await db.get_groups())
    msgs = len(await db.get_all_messages())
    db_size = os.path.getsize(db.db_path) / 1024 if os.path.exists(db.db_path) else 0
    await update.message.reply_text(f"📊 **System Statistics:**\n\n👥 Users: {users}\n🏢 Groups: {groups}\n📝 Ad Messages: {msgs}\n💾 DB Size: {db_size:.2f} KB", parse_mode="Markdown")

@owner_only
async def groups_cmd(update, context):
    groups = await db.get_groups()
    if not groups:
        await update.message.reply_text("Bot is not in any active groups.")
        return
    res = "🏢 **Active Groups:**\n\n"
    for g in groups:
        res += f"- {g['title']} (ID: `{g['id']}`)\n"
    await update.message.reply_text(res[:4000], parse_mode="Markdown")

# --- Event Handlers ---
async def bot_added_to_group(update, context):
    """Admin Rights Check when bot is added to a group."""
    result = update.my_chat_member
    chat = result.chat
    
    if result.new_chat_member.status in ['member', 'administrator']:
        await db.add_group(chat.id, chat.title)
        if result.new_chat_member.status != 'administrator' or not result.new_chat_member.can_post_messages:
            await context.bot.send_message(OWNER_ID, f"⚠️ I was added to the group **{chat.title}**, but I lack permissions to post. Please ensure I am an Admin with posting rights.", parse_mode="Markdown")
    elif result.new_chat_member.status in ['left', 'kicked']:
        await db.remove_group(chat.id)

async def welcome_new_member(update, context):
    """Fires Auto Welcome on user join."""
    new_members = update.message.new_chat_members
    if new_members:
        welcome_text = await db.get_setting("welcome")
        reply_markup = await build_keyboard()
        for member in new_members:
            if member.id != context.bot.id:
                try:
                    await context.bot.send_message(
                        chat_id=update.message.chat_id,
                        text=welcome_text.replace("{name}", member.first_name),
                        reply_markup=reply_markup,
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

async def handle_callback(update, context):
    """Processes Inline Keyboard clicks for private reply buttons."""
    query = update.callback_query
    data = query.data
    
    if data.startswith('btn:'):
        btn_id = data.split(':')[1]
        btn = await db.get_button(btn_id)
        if btn and btn['btn_type'] == 'reply':
            try:
                await context.bot.send_message(chat_id=query.from_user.id, text=btn['content'])
                await query.answer("Check your DMs! 📬", show_alert=True)
            except Exception:
                await query.answer("⚠️ Please start the bot in private messages first to receive this file/message!", show_alert=True)
    await query.answer()

async def handle_dm(update, context):
    """Two-way private chat routing between users and the Owner."""
    user_id = update.effective_user.id
    
    if user_id == OWNER_ID:
        # Owner replying back to a user
        if update.message.reply_to_message:
            replied_text = update.message.reply_to_message.text or update.message.reply_to_message.caption or ""
            match = re.search(r'#user_(\d+)', replied_text)
            if match:
                target_user = int(match.group(1))
                try:
                    await update.message.copy(target_user)
                except Exception as e:
                    await update.message.reply_text(f"❌ Failed to deliver: User blocked bot or chat unavailable.")
            else:
                await update.message.reply_text("⚠️ Could not locate the user ID in the message you replied to.")
    else:
        # User sending DM to bot (Forwarding to Owner)
        await db.add_user(user_id, update.effective_user.username)
        msg = await update.message.copy(OWNER_ID)
        await context.bot.send_message(OWNER_ID, f"💬 **DM from {update.effective_user.first_name}**\nTo reply, reply to the message above.\n`#user_{user_id}`", reply_to_message_id=msg.message_id, parse_mode="Markdown")
      
