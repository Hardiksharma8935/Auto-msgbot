import re
import os
import asyncio
from telegram.ext import ContextTypes
from config import OWNER_ID
from database import db
from utils import owner_only, build_inline_keyboard, build_reply_keyboard

# --- Command Handlers ---
@owner_only
async def start_cmd(update, context):
    reply_markup = await build_reply_keyboard()
    await update.message.reply_text("👋 Welcome Owner! Use /help to see all configuration commands.", reply_markup=reply_markup)

@owner_only
async def help_cmd(update, context):
    help_text = (
        "🛠 **Owner Control Panel**\n"
        "/setmessage `<text>` - Add ad\n"
        "/removemessage `<id>` - Delete ad\n"
        "/messages - List ads\n"
        "/setinterval `<minutes>` - Change frequency\n"
        "/welcome `<text>` - Set welcome (Or reply to media!)\n"
        "/buttons ... - Manage Inline Buttons\n"
        "/keyboard ... - Manage Reply Keyboard\n"
        "/groups - Active groups\n"
        "/stats - Bot analytics\n"
        "/broadcast - Reply to any message to send to all users"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

@owner_only
async def setmessage_cmd(update, context):
    if not update.message.text_html or len(update.message.text.split()) < 2:
        await update.message.reply_text("Usage: `/setmessage <b>My Ad</b>`\nYou can use Telegram's built-in formatting!", parse_mode="HTML")
        return
        
    command = update.message.text.split()[0]
    html_text = update.message.text_html.replace(command, '', 1).strip()
    
    await db.add_message(html_text)
    await update.message.reply_text("✅ Advertisement message added successfully!\n(Your bold, quotes, and links are saved!)")

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
    await update.message.reply_text(res[:4000], parse_mode='HTML')

@owner_only
async def setinterval_cmd(update, context):
    from jobs import ad_job
    try:
        minutes = int(context.args[0])
        if minutes < 1:
            raise ValueError
        await db.set_setting("interval", str(minutes))
        
        current_jobs = context.job_queue.get_jobs_by_name("ad_job")
        for job in current_jobs:
            job.schedule_removal()
        
        context.job_queue.run_repeating(ad_job, interval=minutes*60, first=5, name="ad_job")
        await update.message.reply_text(f"⏱ Advertisement interval updated to **{minutes} minutes**.", parse_mode="Markdown")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: `/setinterval <minutes>`", parse_mode="Markdown")

@owner_only
async def welcome_cmd(update, context):
    reply_msg = update.message.reply_to_message
    
    # Check if owner replied to media to set a rich welcome
    if reply_msg:
        media_id, media_type = None, None
        if reply_msg.photo: media_id, media_type = reply_msg.photo[-1].file_id, "photo"
        elif reply_msg.video: media_id, media_type = reply_msg.video.file_id, "video"
        elif reply_msg.document: media_id, media_type = reply_msg.document.file_id, "document"
        elif reply_msg.animation: media_id, media_type = reply_msg.animation.file_id, "animation"
        
        if media_id:
            await db.set_setting("welcome_media_id", media_id)
            await db.set_setting("welcome_media_type", media_type)
            
            caption = reply_msg.caption_html if reply_msg.caption_html else "Welcome {name}!"
            await db.set_setting("welcome", caption)
            await update.message.reply_text("✅ Media Welcome message updated!")
            return
            
    # Standard text-only welcome
    if not update.message.text_html or len(update.message.text.split()) < 2:
        await update.message.reply_text("Usage: `/welcome <text>`\nHint: Use {name} to insert the user's name.\n*You can also reply to a photo/video with /welcome to set a media welcome!*", parse_mode="HTML")
        return
        
    command = update.message.text.split()[0]
    html_text = update.message.text_html.replace(command, '', 1).strip()
    
    await db.set_setting("welcome", html_text)
    await db.set_setting("welcome_media_id", "") 
    await db.set_setting("welcome_media_type", "")
    await update.message.reply_text("✅ Text Welcome message updated!")

@owner_only
async def button_cmd(update, context):
    args = update.message.text.split(maxsplit=1)
    if len(args) < 2:
        await update.message.reply_text("Usage:\n`/buttons add url | Join | https://t.me/example`\n`/buttons add reply | Gift | Private gift!`\n`/buttons del <id>`\n`/buttons list`", parse_mode="Markdown")
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
            await update.message.reply_text("Invalid format. Use `|` to separate arguments.")
    elif cmd_str.startswith("del"):
        try:
            b_id = cmd_str.split()[1]
            await db.del_button(b_id)
            await update.message.reply_text("🗑 Button deleted.")
        except IndexError:
            await update.message.reply_text("Provide the button ID.")
    elif cmd_str.startswith("list"):
        btns = await db.get_all_buttons()
        res = "🔘 **Active Inline Buttons:**\n\n"
        for b in btns:
            res += f"**ID:** {b['id']} | **Name:** {b['name']} | **Type:** {b['btn_type']}\n"
        await update.message.reply_text(res or "No buttons configured.", parse_mode="Markdown")

@owner_only
async def keyboard_cmd(update, context):
    args = update.message.text.split(maxsplit=1)
    if len(args) < 2:
        help_text = (
            "⌨️ **Reply Keyboard Manager**\n\n"
            "`/keyboard enable` - Show keyboard\n"
            "`/keyboard disable` - Hide keyboard\n"
            "`/keyboard list` - View active buttons\n"
            "`/keyboard del <id>` - Remove button\n\n"
            "**Add Text/URL:**\n"
            "`/keyboard add text | ❤️ About | We are the best!`\n"
            "`/keyboard add url | 🌐 Website | https://google.com`\n\n"
            "**Add Media:**\nReply to media with:\n`/keyboard add media | 📸 View Photo`"
        )
        await update.message.reply_text(help_text, parse_mode="Markdown")
        return
    
    cmd_str = args[1]
    
    if cmd_str == "enable":
        await db.set_setting("keyboard_enabled", "1")
        await update.message.reply_text("✅ Reply Keyboard Enabled! Send /start to update your view.", reply_markup=await build_reply_keyboard())
    elif cmd_str == "disable":
        await db.set_setting("keyboard_enabled", "0")
        await update.message.reply_text("❌ Reply Keyboard Disabled! Send /start to update your view.", reply_markup=await build_reply_keyboard())
    elif cmd_str.startswith("list"):
        btns = await db.get_all_reply_buttons()
        res = "⌨️ **Active Reply Keyboard Buttons:**\n\n"
        for b in btns:
            res += f"**ID:** {b['id']} | **Name:** {b['name']} | **Type:** {b['r_type']}\n"
        await update.message.reply_text(res or "No buttons configured.", parse_mode="Markdown")
    elif cmd_str.startswith("del"):
        try:
            b_id = cmd_str.split()[1]
            await db.del_reply_button(b_id)
            await update.message.reply_text("🗑 Keyboard button deleted. Send /start to refresh.", reply_markup=await build_reply_keyboard())
        except IndexError:
            await update.message.reply_text("Provide the button ID.")
    elif cmd_str.startswith("add"):
        parts = cmd_str[4:].split("|")
        action_type = parts[0].strip().lower()
        
        if action_type in ['text', 'url'] and len(parts) == 3:
            name = parts[1].strip()
            content = parts[2].strip()
            await db.add_reply_button(name, action_type, content)
            await update.message.reply_text(f"✅ Button '{name}' added! Send /start to refresh.", reply_markup=await build_reply_keyboard())
        elif action_type == 'media' and len(parts) == 2:
            name = parts[1].strip()
            reply_msg = update.message.reply_to_message
            if not reply_msg:
                await update.message.reply_text("⚠️ You must reply to a photo, video, document, audio, or sticker to save it as media.")
                return
                
            media_id, media_type = None, None
            if reply_msg.photo: media_id, media_type = reply_msg.photo[-1].file_id, "photo"
            elif reply_msg.video: media_id, media_type = reply_msg.video.file_id, "video"
            elif reply_msg.document: media_id, media_type = reply_msg.document.file_id, "document"
            elif reply_msg.audio: media_id, media_type = reply_msg.audio.file_id, "audio"
            elif reply_msg.sticker: media_id, media_type = reply_msg.sticker.file_id, "sticker"
                
            if media_id:
                await db.add_reply_button(name, 'media', media_id, media_type)
                await update.message.reply_text(f"✅ Media Button '{name}' added! Send /start to refresh.", reply_markup=await build_reply_keyboard())
            else:
                await update.message.reply_text("⚠️ Unsupported media format.")
        else:
            await update.message.reply_text("⚠️ Invalid format. See `/keyboard` for instructions.")

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
                await asyncio.sleep(0.1)
            except Exception:
                failed += 1
        await status_msg.edit_text(f"✅ Broadcast Complete!\n\n**Delivered:** {sent}\n**Failed:** {failed}\n**Total:** {len(users)}", parse_mode="Markdown")
    else:
        await update.message.reply_text("Please reply to a message with `/broadcast` to send it out.", parse_mode="Markdown")

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
    result = update.my_chat_member
    chat = result.chat
    if result.new_chat_member.status in ['member', 'administrator']:
        await db.add_group(chat.id, chat.title)
        await context.bot.send_message(OWNER_ID, f"✅ Successfully joined **{chat.title}**!", parse_mode="Markdown")
    elif result.new_chat_member.status in ['left', 'kicked']:
        await db.remove_group(chat.id)

async def welcome_new_member(update, context):
    result = update.chat_member
    
    if result.new_chat_member.status in ['member', 'restricted'] and result.old_chat_member.status in ['left', 'kicked']:
        member = result.new_chat_member.user
        chat = result.chat
        
        if member.is_bot:
            return

        welcome_text = await db.get_setting("welcome")
        media_id = await db.get_setting("welcome_media_id")
        media_type = await db.get_setting("welcome_media_type")
        reply_markup = await build_inline_keyboard()
        
        formatted_text = welcome_text.replace("{name}", member.first_name)
        
        try:
            if media_id and media_type:
                if media_type == 'photo': await context.bot.send_photo(chat_id=chat.id, photo=media_id, caption=formatted_text, parse_mode="HTML", reply_markup=reply_markup)
                elif media_type == 'video': await context.bot.send_video(chat_id=chat.id, video=media_id, caption=formatted_text, parse_mode="HTML", reply_markup=reply_markup)
                elif media_type == 'document': await context.bot.send_document(chat_id=chat.id, document=media_id, caption=formatted_text, parse_mode="HTML", reply_markup=reply_markup)
                elif media_type == 'animation': await context.bot.send_animation(chat_id=chat.id, animation=media_id, caption=formatted_text, parse_mode="HTML", reply_markup=reply_markup)
            else:
                await context.bot.send_message(chat_id=chat.id, text=formatted_text, reply_markup=reply_markup, parse_mode="HTML")
        except Exception:
            pass

async def handle_callback(update, context):
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

async def handle_general_messages(update, context):
    if not update.message: return
    
    user_id = update.effective_user.id
    chat_type = update.message.chat.type
    text = update.message.text
    
    # 1. KEYBOARD INTERCEPTOR
    if text:
        btn = await db.get_reply_button_by_name(text)
        if btn:
            if btn['r_type'] == 'text': await update.message.reply_text(btn['content'])
            elif btn['r_type'] == 'url': await update.message.reply_text(f"🔗 {btn['content']}")
            elif btn['r_type'] == 'media':
                m_type = btn['media_type']
                file_id = btn['content']
                try:
                    if m_type == 'photo': await update.message.reply_photo(file_id)
                    elif m_type == 'video': await update.message.reply_video(file_id)
                    elif m_type == 'document': await update.message.reply_document(file_id)
                    elif m_type == 'audio': await update.message.reply_audio(file_id)
                    elif m_type == 'sticker': await update.message.reply_sticker(file_id)
                except Exception: pass
            return

    # 2. PRIVATE DM SUPPORT ROUTING
    if chat_type == 'private':
        if user_id == OWNER_ID:
            if update.message.reply_to_message:
                replied_msg_id = update.message.reply_to_message.message_id
                target_user = await db.get_support_user(replied_msg_id)
                
                if target_user:
                    try:
                        await update.message.copy(target_user)
                    except Exception:
                        await update.message.reply_text("❌ Failed to deliver: User blocked the bot.")
                else:
                    await update.message.reply_text("⚠️ Could not locate the user ID in the database. (Message too old or not a forwarded support ticket).")
        else:
            await db.add_user(user_id, update.effective_user.username)
            reply_markup = await build_reply_keyboard()
            
            try:
                await context.bot.send_message(chat_id=user_id, text="Message sent to support.", reply_markup=reply_markup)
            except Exception: pass

            msg = await update.message.copy(OWNER_ID)
            info_msg = await context.bot.send_message(OWNER_ID, f"💬 **DM from {update.effective_user.first_name}**", reply_to_message_id=msg.message_id, parse_mode="Markdown")
            
            await db.map_support_msg(msg.message_id, user_id)
            await db.map_support_msg(info_msg.message_id, user_id)
                        
