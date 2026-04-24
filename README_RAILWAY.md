# Railway Deploy Files

Upload this folder to GitHub, then deploy on Railway.

Set these Railway Variables:

- BOT_TOKEN = your Telegram bot token
- ADMIN_IDS = 7353041224,6527836651
- CHANNEL_ID = -1002701185142
- FORWARD_MSG_IDS = 10,11
- DATA_FILE = bot_data.json

Start command:
python main.py

Important:
- Add the bot as channel admin.
- Enable permission to approve join requests/add users.
- For old picked requests, login Telethon from the admin panel after deploy.
