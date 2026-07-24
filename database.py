import aiosqlite
from config import DB_PATH

class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    async def _execute(self, query, params=()):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(query, params)
            await db.commit()

    async def _fetchall(self, query, params=()):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            return await cursor.fetchall()

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS buttons (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, btn_type TEXT, content TEXT)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY, title TEXT, is_active INTEGER DEFAULT 0)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS reply_buttons (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, r_type TEXT, content TEXT, media_type TEXT, caption TEXT)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS support_logs (msg_id INTEGER PRIMARY KEY, user_id INTEGER)''')
            
            # Safe Schema Migrations
            try: await db.execute("ALTER TABLE groups ADD COLUMN is_active INTEGER DEFAULT 0")
            except Exception: pass
            
            try: await db.execute("ALTER TABLE reply_buttons ADD COLUMN caption TEXT")
            except Exception: pass

            # Default settings
            await db.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', ('interval', '30'))
            await db.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', ('welcome', 'Welcome to {group}! Glad to have you here, {name} ❤️'))
            await db.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', ('keyboard_enabled', '1'))
            await db.commit()

    # --- Groups ---
    async def add_group(self, group_id, title):
        await self._execute('INSERT INTO groups (id, title, is_active) VALUES (?, ?, 0) ON CONFLICT(id) DO UPDATE SET title=excluded.title', (group_id, title))

    async def set_group_active(self, group_id, is_active=1):
        await self._execute('UPDATE groups SET is_active = ? WHERE id = ?', (is_active, group_id))

    async def is_group_active(self, group_id):
        res = await self._fetchall('SELECT is_active FROM groups WHERE id = ?', (group_id,))
        return bool(res[0]['is_active']) if res else False

    async def remove_group(self, group_id):
        await self._execute('DELETE FROM groups WHERE id = ?', (group_id,))

    async def get_groups(self):
        return await self._fetchall('SELECT * FROM groups')

    # --- Users ---
    async def add_user(self, user_id, username):
        await self._execute('INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)', (user_id, username))

    async def get_all_users(self):
        return await self._fetchall('SELECT * FROM users')

    # --- Messages (Ads) ---
    async def add_message(self, text):
        await self._execute('INSERT INTO messages (text) VALUES (?)', (text,))

    async def clear_all_messages(self):
        await self._execute('DELETE FROM messages')

    async def del_message(self, msg_id):
        await self._execute('DELETE FROM messages WHERE id = ?', (msg_id,))

    async def get_all_messages(self):
        return await self._fetchall('SELECT * FROM messages')

    # --- Settings ---
    async def set_setting(self, key, value):
        await self._execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))

    async def get_setting(self, key):
        res = await self._fetchall('SELECT value FROM settings WHERE key = ?', (key,))
        return res[0]['value'] if res else ""

    # --- Inline Buttons ---
    async def add_button(self, name, btn_type, content):
        await self._execute('INSERT INTO buttons (name, btn_type, content) VALUES (?, ?, ?)', (name, btn_type, content))

    async def del_button(self, btn_id):
        await self._execute('DELETE FROM buttons WHERE id = ?', (btn_id,))

    async def get_all_buttons(self):
        return await self._fetchall('SELECT * FROM buttons')

    async def get_button(self, btn_id):
        res = await self._fetchall('SELECT * FROM buttons WHERE id = ?', (btn_id,))
        return res[0] if res else None

    # --- Reply Keyboard Buttons ---
    async def add_reply_button(self, name, r_type, content, media_type=None, caption=None):
        await self._execute('INSERT INTO reply_buttons (name, r_type, content, media_type, caption) VALUES (?, ?, ?, ?, ?)', (name, r_type, content, media_type, caption))

    async def del_reply_button(self, btn_id):
        await self._execute('DELETE FROM reply_buttons WHERE id = ?', (btn_id,))

    async def get_all_reply_buttons(self):
        return await self._fetchall('SELECT * FROM reply_buttons')

    async def get_reply_button_by_name(self, name):
        res = await self._fetchall('SELECT * FROM reply_buttons WHERE name = ?', (name,))
        return res[0] if res else None

    # --- Support Log Mapping ---
    async def map_support_msg(self, msg_id, user_id):
        await self._execute('INSERT OR REPLACE INTO support_logs (msg_id, user_id) VALUES (?, ?)', (msg_id, user_id))

    async def get_support_user(self, msg_id):
        res = await self._fetchall('SELECT user_id FROM support_logs WHERE msg_id = ?', (msg_id,))
        return res[0]['user_id'] if res else None

db = Database()
