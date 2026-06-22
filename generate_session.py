"""
Run this ONCE on your local computer (NOT on Vercel) to generate
TELEGRAM_SESSION string. Then paste it into Vercel env vars.

  pip install telethon
  python generate_session.py
"""
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

API_ID = int(input("TELEGRAM_API_ID: ").strip())
API_HASH = input("TELEGRAM_API_HASH: ").strip()

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    print("\n=== COPY THIS into Vercel as TELEGRAM_SESSION ===\n")
    print(client.session.save())
    print("\n=================================================\n")
