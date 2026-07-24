import re
import os
import asyncio
from telegram.ext import ContextTypes
from config import OWNER_ID
from database import db
from utils import owner_only, build_inline_keyboard, build_reply_keyboard, escape_html

# --- Start & Help ---
async def start_cmd(update, context):
    chat = update.effective_chat
    user = update.effective_user
    reply_markup = await build_reply_keyboard()

    if chat.type in ['group', 'supergroup']:
        # Activate Group for Keyboard & Services (Recovers old groups instantly)
        await db.add_group(chat.id, chat.title)
        await db.set_group_active(chat.id, 1)
        
        text = (
            f"✨ <b>Bot Activated in {escape_html(chat.title)}!</b>\n\n"
            f"Hello {user.mention_html()} 👋\n"
            "Use the menu keyboard below to explore links, offers, and support!"
        )
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        # Private Chat
        await db.add_user(user.id, user.username)
        if user.id == OWNER_ID:
            await update.message.reply_text("👋 <b>Welcome Owner!</b>\nUse /help to open the Admin Control Panel.", reply_markup=reply_markup, parse_mode="HTML")
        else:
            await update.message.reply_text(f"👋 Welcome <b>{escape_html(user.first_name)}</b>!\n\nUse the menu buttons below to interact with us.", reply_markup=reply_markup, parse_mode="HTML")

@owner_only
async def help_cmd(update, context):
    help_text = (
        "👑 <b>Owner Control Panel</b>\n\n"
        "📢 <b>Ad Messages:</b>\n"
        "<code>/setmessage &lt;text&gt;</code> - Add an ad\n"
        "<code>/setmessage replace &lt;text&gt;</code> - Replace ALL ads\n"
        "<code>/clearmessages</code> - Delete all saved ads\n"
        "<code>/removemessage &lt;id&gt;</code> - Remove specific ad\n"
        "<code>/messages</code> - View all saved ads\n"
        "<code>/setinterval &lt;minutes&gt;</code> - Change post frequency\n\n"
        "🎉 <b>Welcome Setup:</b>\n"
        "<code>/welcome &lt;text&gt;</code> - Set welcome (Use {name} and {group})\n"
        "<i>Reply to a photo/video with /welcome to set a media welcome!</i>\n\n"
        "🔘 <b>Buttons:</b>\n"
        "<code>/buttons</code> - Manage Inline Buttons\n"
        "<code>/keyboard</code> - Manage Reply Keyboard Menu\n\n"
        "📊 <b>Management:</b>\n"
        "<code>/groups</code> - View joined groups\n"
        "<code>/stats</code> - View system analytics\n"
        "<code>/broadcast</code> - Reply to any message to broadcast"
    )
    await update.message.reply_text(help_text, parse_mode='HTML')

# --- Ad Message Management ---
@owner_only
async def setmessage_cmd(update, context):
    if not update.message.text_html or len(update.message.text.split()) < 2:
        await update.message.reply_text("Usage:\n<code>/setmessage My Ad Text</code> (Adds ad)\n<code>/setmessage replace My Ad Text</code> (Overwrites all old ads)", parse_mode="HTML")
        return

    full_text = update.message.text_html
    command_part = update.message.text.split()[0] # The exact command typed
    content = full_text.replace(command_part, '', 1).strip()

    if content.lower().startswith("replace"):
        content = content[7:].strip()
        await db.clear_all_messages()
        await db.add_message(content)
        await update.message.reply_text("🔄 <b>All previous ads replaced with new ad message!</b>\n(Your formatting is saved perfectly)", parse_mode="HTML")
    else:
        await db.add_message(content)
        await update.message.reply_text("✅ <b>New advertisement message added!</b>\n(Your formatting is saved perfectly)", parse_mode="HTML")

@owner_only
async def clearmessages_cmd(update, context):
    await db.clear_all_messages()
    await update.message.reply_text("🗑 <b>All advertisement messages have been deleted.</b>", parse_mode="HTML")

@owner_only
async def removemessage_cmd(update, context):
    try:
        msg_id = int(context.args[0])
        await db.del_message(msg_id)
        await update.message.reply_text(f"🗑 Message ID <code>{msg_id}</code> deleted!", parse_mode="HTML")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: <code>/removemessage &lt;id&gt;</code>", parse_mode="HTML")

@owner_only
async def messages_cmd(update, context):
    msgs = await db.get_all_messages()
    if not msgs:
        await update.message.reply_text("📜 No advertisement messages found in database.")
        return
    
    res = "📜 <b>Saved Advertisements:</b>\n\n"
    for m in msgs:
        # Render the EXACT HTML without escaping it so formatting works
        res += f"🔹 <b>ID:</b> <code>{m['id']}</code>\n{m['text']}\n───────────────\n"
    
    await update.message.reply_text(res[:4000], parse_mode='HTML')

@owner_only
async def setinterval_cmd(update, context):
    from jobs import ad_job
    try:
        minutes = int(context.args[0])
        if minutes < 1: raise ValueError
        await db.set_setting("interval", str(minutes))
        
        current_jobs = context.job_queue.get_jobs_by_name("ad_job")
        for job in current_jobs:
            job.schedule_removal()
        
        context.job_queue.run_repeating(ad_job, interval=minutes*60, first=5, name="ad_job")
        await update.message.reply_text(f"⏱ Interval updated to <b>{minutes} minutes</b>.", parse_mode="HTML")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: <code>/setinterval &lt;minutes&gt;</code>", parse_mode="HTML")

@owner_only
async def welcome_cmd(update, context):
    reply_msg = update.message.reply_to_message
    
    if reply_msg:
        media_id, media_type = None, None
        if reply_msg.photo: media_id, media_type = reply_msg.photo[-1].file_id, "photo"
        elif reply_msg.video: media_id, media_type = reply_msg.video.file_id, "video"
        elif reply_msg.document: media_id, media_type = reply_msg.document.file_id, "document"
        elif reply_msg.animation: media_id, media_type = reply_msg.animation.file_id, "animation"
        
        if media_id:
            await db.set_setting("welcome_media_id", media_id)
            await db.set_setting("welcome_media_type", media_type)
            caption = reply_msg.caption_html if reply_msg.caption_html else "Welcome to {group}, {name}! ❤️"
            await db.set_setting("welcome", caption)
            await update.message.reply_text("🖼 <b>Media Welcome Message Updated!</b>", parse_mode="HTML")
            return
            
    if not update.message.text_html or len(update.message.text.split()) < 2:
        await update.message.reply_text("Usage: <code>/welcome &lt;text&gt;</code>\nUse {name} for username and {group} for group title.\nOr reply to a photo/video with /welcome!", parse_mode="HTML")
        return
        
    full_text = update.message.text_html
    command_part = update.message.text.split()[0]
    html_text = full_text.replace(command_part, '', 1).strip()
    
    await db.set_setting("welcome", html_text)
    await db.set_setting("welcome_media_id", "") 
    await db.set_setting("welcome_media_type", "")
    await update.message.reply_text("📝 <b>Text Welcome Message Updated!</b>", parse_mode="HTML")

# --- Inline & Reply Keyboard Commands ---
@owner_only
async def button_cmd(update, context):
    args = update.message.text.split(maxsplit=1)
    if len(args) < 2:
        await update.message.reply_text("Usage:\n<code>/buttons add url | Join | https://t.me/example</code>\n<code>/buttons add reply | Secret | Gift text</code>\n<code>/buttons del &lt;id&gt;</code>\n<code>/buttons list</code>", parse_mode="HTML")
        return
    
    cmd_str = args[1]
    if cmd_str.startswith("add"):
        parts = cmd_str[4:].split("|")
        if len(parts) == 3:
            b_type, name, content = parts[0].strip().lower(), parts[1].strip(), parts[2].strip()
            if b_type in ['url', 'reply']:
                await db.add_button(name, b_type, content)
                await update.message.reply_text(f"✅ Inline Button <b>{name}</b> added!", parse_mode="HTML")
            else:
                await update.message.reply_text("Type must be `url` or `reply`.")
        else:
            await update.message.reply_text("Format error. Use `|` as separator.")
    elif cmd_str.startswith("del"):
        try:
            b_id = int(cmd_str.split()[1])
            await db.del_button(b_id)
            await update.message.reply_text("🗑 Button deleted.")
        except (IndexError, ValueError):
            await update.message.reply_text("Provide valid button ID.")
    elif cmd_str.startswith("list"):
        btns = await db.get_all_buttons()
        res = "🔘 <b>Active Inline Buttons:</b>\n\n"
        for b in btns:
            res += f"• <b>ID:</b> <code>{b['id']}</code> | <b>Name:</b> {b['name']} | <b>Type:</b> {b['btn_type']}\n"
        await update.message.reply_text(res or "No inline buttons set.", parse_mode="HTML")

@owner_only
async def keyboard_cmd(update, context):
    args = update.message.text.split(maxsplit=1)
    if len(args) < 2:
        help_text = (
            "⌨️ <b>Reply Keyboard Manager</b>\n\n"
            "<code>/keyboard enable</code> - Show keyboard\n"
            "<code>/keyboard disable</code> - Hide keyboard\n"
            "<code>/keyboard list</code> - List buttons\n"
            "<code>/keyboard del &lt;id&gt;</code> - Delete button\n\n"
            "<b>Add Text/URL:</b>\n"
            "<code>/keyboard add text | 🎁 VIP | Join VIP channel here: https://t.me/xxx</code>\n"
            "<code>/keyboard add url | 🌐 Site | https://google.com</code>\n\n"
            "<b>Add Media:</b>\nReply to photo/video/doc with:\n<code>/keyboard add media | 📸 View Offer | Check this out!</code>"
        )
        await update.message.reply_text(help_text, parse_mode="HTML")
        return
    
    cmd_str = args[1]
    if cmd_str == "enable":
        await db.set_setting("keyboard_enabled", "1")
        await update.message.reply_text("✅ Reply Keyboard Enabled! Send `/start` to view.", reply_markup=await build_reply_keyboard(), parse_mode="HTML")
    elif cmd_str == "disable":
        await db.set_setting("keyboard_enabled", "0")
        await update.message.reply_text("❌ Reply Keyboard Disabled!", reply_markup=await build_reply_keyboard())
    elif cmd_str.startswith("list"):
        btns = await db.get_all_reply_buttons()
        res = "⌨️ <b>Active Keyboard Buttons:</b>\n\n"
        for b in btns:
            res += f"• <b>ID:</b> <code>{b['id']}</code> | <b>Name:</b> {b['name']} | <b>Type:</b> {b['r_type']}\n"
        await update.message.reply_text(res or "No keyboard buttons set.", parse_mode="HTML")
    elif cmd_str.startswith("del"):
        try:
            b_id = int(cmd_str.split()[1])
            await db.del_reply_button(b_id)
            await update.message.reply_text("🗑 Keyboard button deleted.", reply_markup=await build_reply_keyboard())
        except (IndexError, ValueError):
            await update.message.reply_text("Provide valid button ID.")
    elif cmd_str.startswith("add"):
        parts = cmd_str[4:].split("|")
        action_type = parts[0].strip().lower()
        
        if action_type in ['text', 'url'] and len(parts) >= 3:
            name = parts[1].strip()
            content = "|".join(parts[2:]).strip()
            await db.add_reply_button(name, action_type, content)
            await update.message.reply_text(f"✅ Keyboard button <b>{name}</b> added!", reply_markup=await build_reply_keyboard(), parse_mode="HTML")
        elif action_type == 'media' and len(parts) >= 2:
            name = parts[1].strip()
            caption = "|".join(parts[2:]).strip() if len(parts) > 2 else ""
            reply_msg = update.message.reply_to_message
            if not reply_msg:
                await update.message.reply_text("⚠️ Reply to a photo, video, or document with <code>/keyboard add media | &lt;Name&gt; | [Caption]</code>", parse_mode="HTML")
                return
                
            media_id, media_type = None, None
            if reply_msg.photo: media_id, media_type = reply_msg.photo[-1].file_id, "photo"
            elif reply_msg.video: media_id, media_type = reply_msg.video.file_id, "video"
            elif reply_msg.document: media_id, media_type = reply_msg.document.file_id, "document"
            elif reply_msg.audio: media_id, media_type = reply_msg.audio.file_id, "audio"
            elif reply_msg.sticker: media_id, media_type = reply_msg.sticker.file_id, "sticker"
                
            if media_id:
                await db.add_reply_button(name, 'media', media_id, media_type, caption)
                await update.message.reply_text(f"✅ Media button <b>{name}</b> added!", reply_markup=await build_reply_keyboard(), parse_mode="HTML")
            else:
                await update.message.reply_text("⚠️ Unsupported media format.")

# --- Admin Analytics & Broadcast ---
@owner_only
async def broadcast_cmd(update, context):
    if update.message.reply_to_message:
        users = await db.get_all_users()
        sent, failed = 0, 0
        status_msg = await update.message.reply_text("🚀 <b>Broadcasting message...</b>", parse_mode="HTML")
        for u in users:
            try:
                await update.message.reply_to_message.copy(u['id'])
                sent += 1
                await asyncio.sleep(0.05)
            except Exception:
                failed += 1
        await status_msg.edit_text(f"✅ <b>Broadcast Complete!</b>\n\n• <b>Delivered:</b> <code>{sent}</code>\n• <b>Failed:</b> <code>{failed}</code>\n• <b>Total:</b> <code>{len(users)}</code>", parse_mode="HTML")
    else:
        await update.message.reply_text("Reply to any message with <code>/broadcast</code> to send it to all users.", parse_mode="HTML")

@owner_only
async def stats_cmd(update, context):
    users = len(await db.get_all_users())
    groups = len(await db.get_groups())
    msgs = len(await db.get_all_messages())
    db_size = os.path.getsize(db.db_path) / 1024 if os.path.exists(db.db_path) else 0
    await update.message.reply_text(f"📊 <b>System Analytics:</b>\n\n👥 <b>Users:</b> <code>{users}</code>\n🏢 <b>Groups:</b> <code>{groups}</code>\n📝 <b>Saved Ads:</b> <code>{msgs}</code>\n💾 <b>DB Size:</b> <code>{db_size:.2f} KB</code>", parse_mode="HTML")

@owner_only
async def groups_cmd(update, context):
    groups = await db.get_groups()
    if not groups:
        await update.message.reply_text("Bot is not active in any groups.")
        return
    res = "🏢 <b>Active Groups:</b>\n\n"
    for g in groups:
        res += f"• <b>{escape_html(g['title'])}</b> (ID: <code>{g['id']}</code>)\n"
    await update.message.reply_text(res[:4000], parse_mode="HTML")

# --- Event Handlers ---
async def bot_added_to_group(update, context):
    result = update.my_chat_member
    chat = result.chat
    if result.new_chat_member.status in ['member', 'administrator']:
        await db.add_group(chat.id, chat.title)
        await db.set_group_active(chat.id, 1) # Auto activate when added
        await context.bot.send_message(OWNER_ID, f"✅ Bot added to group <b>{escape_html(chat.title)}</b>!", parse_mode="HTML")
    elif result.new_chat_member.status in ['left', 'kicked']:
        await db.remove_group(chat.id)

async def welcome_new_member(update, context):
    result = update.chat_member
    if result.new_chat_member.status in ['member', 'restricted'] and result.old_chat_member.status in ['left', 'kicked']:
        member = result.new_chat_member.user
        chat = result.chat
        if member.is_bot: return

        welcome_text = await db.get_setting("welcome")
        media_id = await db.get_setting("welcome_media_id")
        media_type = await db.get_setting("welcome_media_type")
        reply_markup = await build_inline_keyboard()
        
        formatted_text = welcome_text.replace("{name}", member.first_name).replace("{group}", chat.title)
        
        try:
            if media_id and media_type:
                if media_type == 'photo': await context.bot.send_photo(chat_id=chat.id, photo=media_id, caption=formatted_text, parse_mode="HTML", reply_markup=reply_markup)
                elif media_type == 'video': await context.bot.send_video(chat_id=chat.id, video=media_id, caption=formatted_text, parse_mode="HTML", reply_markup=reply_markup)
                elif media_type == 'document': await context.bot.send_document(chat_id=chat.id, document=media_id, caption=formatted_text, parse_mode="HTML", reply_markup=reply_markup)
                elif media_type == 'animation': await context.bot.send_animation(chat_id=chat.id, animation=media_id, caption=formatted_text, parse_mode="HTML", reply_markup=reply_markup)
            else:
                await context.bot.send_message(chat_id=chat.id, text=formatted_text, reply_markup=reply_markup, parse_mode="HTML")
        except Exception: pass

async def handle_callback(update, context):
    query = update.callback_query
    data = query.data
    
    if data.startswith('btn:'):
        btn_id = data.split(':')[1]
        btn = await db.get_button(btn_id)
        if btn and btn['btn_type'] == 'reply':
            try:
                await context.bot.send_message(chat_id=query.from_user.id, text=btn['content'])
                await query.answer("Check your DM! 📬", show_alert=True)
            except Exception:
                await query.answer("⚠️ Please start the bot in private message first!", show_alert=True)
    await query.answer()

async def handle_general_messages(update, context):
    if not update.message: return
    
    user_id = update.effective_user.id
    chat = update.effective_chat
    text = update.message.text

    # --- Auto-Recover Old Groups ---
    if chat.type in ['group', 'supergroup']:
        # This guarantees old groups are saved back to the database automatically
        await db.add_group(chat.id, chat.title)
        await db.set_group_active(chat.id, 1)

    # 1. KEYBOARD BUTTON INTERCEPTOR
    if text:
        btn = await db.get_reply_button_by_name(text)
        if btn:
            caption = btn['caption'] or ""
            if btn['r_type'] == 'text': 
                await update.message.reply_text(btn['content'], parse_mode="HTML")
            elif btn['r_type'] == 'url': 
                await update.message.reply_text(f"{btn['content']}", parse_mode="HTML")
            elif btn['r_type'] == 'media':
                m_type = btn['media_type']
                file_id = btn['content']
                try:
                    if m_type == 'photo': await update.message.reply_photo(file_id, caption=caption, parse_mode="HTML")
                    elif m_type == 'video': await update.message.reply_video(file_id, caption=caption, parse_mode="HTML")
                    elif m_type == 'document': await update.message.reply_document(file_id, caption=caption, parse_mode="HTML")
                    elif m_type == 'audio': await update.message.reply_audio(file_id, caption=caption, parse_mode="HTML")
                    elif m_type == 'sticker': await update.message.reply_sticker(file_id)
                except Exception: pass
            return

    # 2. PRIVATE DM SUPPORT ROUTING
    if chat.type == 'private':
        if user_id == OWNER_ID:
            if update.message.reply_to_message:
                replied_msg_id = update.message.reply_to_message.message_id
                target_user = await db.get_support_user(replied_msg_id)
                
                if target_user:
                    try:
                        await update.message.copy(target_user)
                    except Exception:
                        await update.message.reply_text("❌ Could not deliver: User blocked the bot.")
                else:
                    await update.message.reply_text("⚠️ User ID mapping not found for this message.")
        else:
            await db.add_user(user_id, update.effective_user.username)
            
