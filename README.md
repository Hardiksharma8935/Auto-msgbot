# Auto-msgbot
# Personal Promotion Telegram Bot

A robust, async Python Telegram bot designed for group promotion, broadcasting, and community management.

## Deployment on Railway
1. Fork or push this repository to GitHub.
2. Create a new project on Railway and deploy from the GitHub repo.
3. In the Railway dashboard, go to the **Variables** tab and add `BOT_TOKEN` and `OWNER_ID`.
4. **Important for SQLite:** To prevent database resets on new deployments, attach a Volume in Railway. Mount it to a directory (e.g., `/app/data`) and set the `DB_PATH` environment variable to `/app/data/bot_data.db`.

## Commands Overview (Owner Only)
- `/start` - Start the bot in DM
- `/help` - View all commands
- `/setmessage <text>` - Add an ad message (Supports HTML)
- `/removemessage <id>` - Remove an ad message
- `/messages` - List active messages
- `/setinterval <minutes>` - Set ad rotation frequency
- `/welcome <text>` - Set welcome message (Use `{name}` for user's name)
- `/buttons add url | <Name> | <Link>` - Add a URL button
- `/buttons add reply | <Name> | <Text>` - Add a private DM reply button
- `/buttons del <id>` - Remove a button
- `/buttons list` - Show all buttons
- `/groups` - View joined groups
- `/stats` - View bot statistics
- `/broadcast` - Reply to any message (text/photo/video) with this command to broadcast
- 
