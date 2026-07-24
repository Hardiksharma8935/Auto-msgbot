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
        # Activate Group for Keyboard & Services
        await db.add_group(chat.id, chat.title)
        await db.set_group_active(chat.id, 1)
        
        text = (
            f"✨ **Bot Activated in {escape_html(chat.title)}!**\n\n"
            f"Hello {user.mention_markdown_v2()} 👋\n"
            "Use the menu keyboard below to explore links, offers, and support!"
        )
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        # Private Chat
        await db.add_user(user.id, user.username)
        if user.id == OWNER_ID:
            await update.message.reply_text("👋 **Welcome Owner!**\nUse `/help` to open the Admin Control Panel.", reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await update.message.reply_text(f"👋 Welcome **{escape_html(user.first_name)}**!\n\nUse the menu buttons below to interact with us.", reply_markup=reply_markup, parse_mode="Markdown")

@owner_only
async def help_cmd(update, context):
    help_text = (
        "👑 **Owner Control Panel**\n\n"
        "📢 **Ad Messages:**\n"
        "`/setmessage <text>` - Add an ad\n"
        "`/setmessage replace <text>` - Replace ALL ads with this new one\n"
        "`/clearmessages` - Delete all saved ads\n"
        "`/removemessage <id>` - Remove specific ad\n"
        "`/messages` - View all saved ads\n"
        "`/setinterval <minutes>` - Change post frequency\n\n"
        "🎉 **Welcome Setup:**\n"
        "`/welcome <text>` - Set welcome text (Use `{name}` and `{group}`)\n"
        "*Reply to a photo/video with `/welcome` to set a media welcome!*\n\n"
        "🔘 **Buttons:**\n"
        "`/buttons` - Manage Inline Buttons\n"
        "`/keyboard` - Manage Reply Keyboard Menu\n\n"
        "📊 **Management:**\n"
        "`/groups` - View joined groups\n"
        "`/stats` - View system analytics\n"
        "`/broadcast` - Reply to any message to broadcast"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

# --- Ad Message Management ---
@owner_only
async def setmessage_cmd(update, context):
    if not update.message.text_html or len(update.message.text.split()) < 2:
        await update.message.reply_text("Usage:\n`/setmessage <b>My Ad Text</b>` (Adds ad)\n`/setmessage replace <b>My Ad Text</b>` (Overwrites all old ads)", parse_mode="Markdown")
        return

    full_text = update.message.text_html
    command_part = full_text.split()[0]
    content = full_text.replace(command_part, '', 1).strip()

    if content.lower().startswith("replace"):
        content = content[7:].strip()
        await db.clear_all_messages()
        await db.add_message(content)
        await update.message.reply_text("🔄 **All previous ads replaced with new ad message!**", parse_mode="Markdown")
    else:
        await db.add_message(content)
        await update.message.reply_text("✅ **New advertisement message added!**", parse_mode="Markdown")

@owner_only
async def clearmessages_cmd(update, context):
    await db.clear_all_messages()
    await update.message.reply_text("🗑 **All advertisement messages have been deleted.**")

@owner_only
async def removemessage_cmd(update, context):
    try:
        msg_id = int(context.args[0])
        await db.del_message(msg_id)
        await update.message.reply_text(f"🗑 Message ID `{msg_id}` deleted!", parse_mode="Markdown")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: `/removemessage <id>`", parse_mode="Markdown")

@owner_only
async def messages_cmd(update, context):
    msgs = await db.get_all_messages()
    if not msgs:
        await update.message.reply_text("📜 No advertisement messages found in database.")
        return
    
    res = "📜 **Saved Advertisements:**\n\n"
    for m in msgs:
        # Safe raw preview display
        res += f"🔹 **ID:** `{m['id']}`\n{escape_html(m['text'])}\n───────────────\n"
    
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
        await update.message.reply_text(f"⏱ Interval updated to **{minutes} minutes**.", parse_mode="Markdown")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: `/setinterval <minutes>`", parse_mode="Markdown")

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
            await update.message.reply_text("🖼 **Media Welcome Message Updated!**", parse_mode="Markdown")
            return
            
    if not update.message.text_html or len(update.message.text.split()) < 2:
        await update.message.reply_text("Usage: `/welcome <text>`\nUse `{name}` for username and `{group}` for group title.\nOr reply to a photo/video with `/welcome`!", parse_mode="Markdown")
        return
        
    full_text = update.message.text_html
    command_part = full_text.split()[0]
    html_text = full_text.replace(command_part, '', 1).strip()
    
    await db.set_setting("welcome", html_text)
    await db.set_setting("welcome_media_id", "") 
    await db.set_setting("welcome_media_type", "")
    await update.message.reply_text("📝 **Text Welcome Message Updated!**", parse_mode="Markdown")

# --- Inline & Reply Keyboard Commands ---
@owner_only
async def button_cmd(update, context):
    args = update.message.text.split(maxsplit=1)
    if len(args) < 2:
        await update.message.reply_text("Usage:\n`/buttons add url | Join | https://t.me/example`\n`/buttons add reply | Secret | Gift text`\n`/buttons del <id>`\n`/buttons list`", parse_mode="Markdown")
        return
    
    cmd_str = args[1]
    if cmd_str.startswith("add"):
        parts = cmd_str[4:].split("|")
        if len(parts) == 3:
            b_type, name, content = parts[0].strip().lower(), parts[1].strip(), parts[2].strip()
            if b_type in ['url', 'reply']:
                await db.add_button(name, b_type, content)
                await update.message.reply_text(f"✅ Inline Button **{name}** added!", parse_mode="Markdown")
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
        res = "🔘 **Active Inline Buttons:**\n\n"
        for b in btns:
            res += f"• **ID:** `{b['id']}` | **Name:** {b['name']} | **Type:** {b['btn_type']}\n"
        await update.message.reply_text(res or "No inline buttons set.", parse_mode="Markdown")

@owner_only
async def keyboard_cmd(update, context):
    args = update.message.text.split(maxsplit=1)
    if len(args) < 2:
        help_text = (
            "⌨️ **Reply Keyboard Manager**\n\n"
            "`/keyboard enable` - Show keyboard\n"
            "`/keyboard disable` - Hide keyboard\n"
            "`/keyboard list` - List buttons\n"
            "`/keyboard del <id>` - Delete button\n\n"
            "**Add Text/URL:**\n"
            "`/keyboard add text | 🎁 VIP | Join VIP channel here: https://t.me/xxx`\n"
            "`/keyboard add url | 🌐 Site | https://google.com`\n\n"
            "**Add Media:**\nReply to photo/video/doc with:\n`/keyboard add media | 📸 View Offer | Check this out!`"
        )
        await update.message.reply_text(help_text, parse_mode="Markdown")
        return
    
    cmd_str = args[1]
    if cmd_str == "enable":
        await db.set_setting("keyboard_enabled", "1")
        await update.message.reply_text("✅ Reply Keyboard Enabled! Send `/start` to view.", reply_markup=await build_reply_keyboard(), parse_mode="Markdown")
    elif cmd_str == "disable":
        await db.set_setting("keyboard_enabled", "0")
        await update.message.reply_text("❌ Reply Keyboard Disabled!", reply_markup=await build_reply_keyboard())
    elif cmd_str.startswith("list"):
        btns = await db.get_all_reply_buttons()
        res = "⌨️ **Active Keyboard Buttons:**\n\n"
        for b in btns:
            res += f"• **ID:** `{b['id']}` | **Name:** {b['name']} | **Type:** {b['r_type']}\n"
        await update.message.reply_text(res or "No keyboard buttons set.", parse_mode="Markdown")
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
            await update.message.reply_text(f"✅ Keyboard button **{name}** added!", reply_markup=await build_reply_keyboard(), parse_mode="Markdown")
        elif action_type == 'media' and len(parts) >= 2:
            name = parts[1].strip()
            caption = "|".join(parts[2:]).strip() if len(parts) > 2 else ""
            reply_msg = update.message.reply_to_message
            if not reply_msg:
                await update.message.reply_text("⚠️ Reply to a photo, video, or document with `/keyboard add media | <Name> | [Caption]`")
                return
                
            media_id, media_type = None, None
            if reply_msg.photo: media_id, media_type = reply_msg.photo[-1].file_id, "photo"
            elif reply_msg.video: media_id, media_type = reply_msg.video.file_id, "video"
            elif reply_msg.document: media_id, media_type = reply_msg.document.file_id, "document"
            elif reply_msg.audio: media_id, media_type = reply_msg.audio.file_id, "audio"
            elif reply_msg.sticker: media_id, media_type = reply_msg.sticker.file_id, "sticker"
                
            if media_id:
                await db.add_reply_button(name, 'media', media_id, media_type, caption)
                await update.message.reply_text(f"✅ Media button **{name}** added!", reply_markup=await build_reply_keyboard(), parse_mode="Markdown")
            else:
                await update.message.reply_text("⚠️ Unsupported media format.")

# --- Admin Analytics & Broadcast ---
@owner_only
async def broadcast_cmd(update, context):
    if update.message.reply_to_message:
        users = await db.get_all_users()
        sent, failed = 0, 0
        status_msg = await update.message.reply_text("🚀 **Broadcasting message...**", parse_mode="Markdown")
        for u in users:
            try:
                await update.message.reply_to_message.copy(u['id'])
                sent += 1
                await asyncio.sleep(0.05)
            except Exception:
                failed += 1
        await status_msg.edit_text(f"✅ **Broadcast Complete!**\n\n• **Delivered:** `{sent}`\n• **Failed:** `{failed}`\n• **Total:** `{len(users)}`", parse_mode="Markdown")
    else:
        await update.message.reply_text("Reply to any message with `/broadcast` to send it to all users.", parse_mode="Markdown")

@owner_only
async def stats_cmd(update, context):
    users = len(await db.get_all_users())
    groups = len(await db.get_groups())
    msgs = len(await db.get_all_messages())
    db_size = os.path.getsize(db.db_path) / 1024 if os.path.exists(db.db_path) else 0
    await update.message.reply_text(f"📊 **System Analytics:**\n\n👥 **Users:** `{users}`\n🏢 **Groups:** `{groups}`\n📝 **Saved Ads:** `{msgs}`\n💾 **DB Size:** `{db_size:.2f} KB`", parse_mode="Markdown")

@owner_only
async def groups_cmd(update, context):
    groups = await db.get_groups()
    if not groups:
        await update.message.reply_text("Bot is not active in any groups.")
        return
    res = "🏢 **Active Groups:**\n\n"
    for g in groups:
        res += f"• **{escape_html(g['title'])}** (ID: `{g['id']}`)\n"
    await update.message.reply_text(res[:4000], parse_mode="HTML")

# --- Event Handlers ---
async def bot_added_to_group(update, context):
    result = update.my_chat_member
    chat = result.chat
    if result.new_chat_member.status in ['member', 'administrator']:
        await db.add_group(chat.id, chat.title)
        await context.bot.send_message(OWNER_ID, f"✅ Bot added to group **{escape_html(chat.title)}**!", parse_mode="HTML")
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

    # 1. KEYBOARD BUTTON INTERCEPTOR (Groups & Private Chats)
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
            # Route DM to Owner
            msg = await update.message.copy(OWNER_ID)
            info_msg = await context.bot.send_message(OWNER_ID, f"💬 **DM from {escape_html(update.effective_user.first_name)}**", reply_to_message_id=msg.message_id, parse_mode="HTML")
            
            await db.map_support_msg(msg.message_id, user_id)
            await db.map_support_msg(info_msg.message_id, user_id)
            
