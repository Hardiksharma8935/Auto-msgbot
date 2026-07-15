import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", 0))
DB_PATH = os.getenv("DB_PATH", "bot_data.db")

if not BOT_TOKEN or not OWNER_ID:
    raise ValueError("⚠️ BOT_TOKEN and OWNER_ID must be provided in the .env file.")
  
