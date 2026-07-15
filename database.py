import aiosqlite
from config import DB_PATH

class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    async def _execute(self, query, params=()):
        """Base execution method for easy migration to Postgres (asyncpg) later."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(query, params)
            await db.commit()

    async def _fetchall(self, query, params=()):
        """Base fetch method."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            return await cursor.fetchall()

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS buttons (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, btn_type TEXT, content TEXT)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY, title TEXT)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT)''')
            
            # Default configurations
            await db.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', ('interval', '30'))
            await db.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', ('welcome', 'Welcome to the group {name}!'))
            await db.commit()

    # --- Groups ---
    async def add_group(self, group_id, title):
        await self._execute('INSERT OR REPLACE INTO groups (id, title) VALUES (?, ?)', (group_id, title))

    async def remove_group(self, group_id):
        await self._execute('DELETE FROM groups WHERE id = ?', (group_id,))

    async def get_groups(self):
        return await self._fetchall('SELECT * FROM groups')

    # --- Users ---
    async def add_user(self, user_id, username):
        await self._execute('INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)', (user_id, username))

    async def get_all_users(self):
        return await self._fetchall('SELECT * FROM users')

    # --- Messages ---
    async def add_message(self, text):
        await self._execute('INSERT INTO messages (text) VALUES (?)', (text,))

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

    # --- Buttons ---
    async def add_button(self, name, btn_type, content):
        await self._execute('INSERT INTO buttons (name, btn_type, content) VALUES (?, ?, ?)', (name, btn_type, content))

    async def del_button(self, btn_id):
        await self._execute('DELETE FROM buttons WHERE id = ?', (btn_id,))

    async def get_all_buttons(self):
        return await self._fetchall('SELECT * FROM buttons')

    async def get_button(self, btn_id):
        res = await self._fetchall('SELECT * FROM buttons WHERE id = ?', (btn_id,))
        return res[0] if res else None

db = Database()
