from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread
import sqlite3
import uuid
import asyncio

API_ID = 24344133
API_HASH = "edbe7000baef13fa5a6c45c8edc4be66"
BOT_TOKEN = "8046719850:AAGxJ6Wn63mVJCq7SAHW2sU9aIL2VmfjZig"
BOT_USERNAME = "file_storing_gpt_bot"

app = Client(
    "file_store_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Flask keep-alive server
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Bot is Alive"


def run():
    flask_app.run(host='0.0.0.0', port=8080)


def keep_alive():
    t = Thread(target=run)
    t.start()


conn = sqlite3.connect("file_store.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS files (id TEXT, file_id TEXT, user_id INTEGER, file_name TEXT)""")
cur.execute("""CREATE TABLE IF NOT EXISTS batches (batch_id TEXT, user_id INTEGER, file_ids TEXT)""")
conn.commit()

user_temp_files = {}  # Temporarily hold files per user


def save_file(file_id, user_id, file_name):
    file_unique_id = str(uuid.uuid4())
    cur.execute("INSERT INTO files VALUES (?, ?, ?, ?)", (file_unique_id, file_id, user_id, file_name))
    conn.commit()
    return file_unique_id


def get_file(file_unique_id):
    cur.execute("SELECT file_id, file_name FROM files WHERE id=?", (file_unique_id,))
    return cur.fetchone()


def get_user_files(user_id):
    cur.execute("SELECT id, file_name FROM files WHERE user_id=?", (user_id,))
    return cur.fetchall()


def create_batch(user_id, file_ids):
    batch_id = str(uuid.uuid4())
    file_ids_str = ','.join(file_ids)
    cur.execute("INSERT INTO batches VALUES (?, ?, ?)", (batch_id, user_id, file_ids_str))
    conn.commit()
    return batch_id


def get_batch_files(batch_id):
    cur.execute("SELECT file_ids FROM batches WHERE batch_id=?", (batch_id,))
    result = cur.fetchone()
    if result:
        return result[0].split(',')
    return []


@app.on_message(filters.private & (filters.document | filters.photo | filters.video | filters.audio))
async def handle_file(client, message):
    user_id = message.from_user.id

    if user_id not in user_temp_files:
        user_temp_files[user_id] = []

    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
    elif message.photo:
        file_id = message.photo.file_id
        file_name = "Photo.jpg"
    elif message.video:
        file_id = message.video.file_id
        file_name = message.video.file_name or "Video.mp4"
    elif message.audio:
        file_id = message.audio.file_id
        file_name = message.audio.file_name or "Audio.mp3"
    else:
        await message.reply_text("❌ Unsupported file type.")
        return

    user_temp_files[user_id].append({'file_id': file_id, 'file_name': file_name})

    if message.forward_from_chat or message.forward_from:
        await message.reply_text("✅ Forwarded file received. Send more files or type /done when you have finished uploading.")
    else:
        await message.reply_text("✅ File received. Send more files or type /done when you have finished uploading.")


@app.on_message(filters.command('done'))
async def ask_file_action(client, message):
    user_id = message.from_user.id

    if user_id not in user_temp_files or not user_temp_files[user_id]:
        await message.reply_text("❌ You have not sent any files.")
        return

    buttons = [
        [InlineKeyboardButton("✅ Create Single File Links", callback_data="singlefile")],
        [InlineKeyboardButton("📦 Create Batch Link", callback_data="batchfile")]
    ]

    await message.reply_text(
        "❓ Do you want to create individual file links or one batch link for all your uploaded files?",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


@app.on_callback_query()
async def handle_file_decision(client, callback_query):
    user_id = callback_query.from_user.id

    if user_id not in user_temp_files or not user_temp_files[user_id]:
        await callback_query.message.reply_text("❌ You have no files to process.")
        await callback_query.answer()
        return

    files = user_temp_files[user_id]

    if callback_query.data == "singlefile":
        msg = "✅ Here are your individual file links:\n\n"
        for file in files:
            file_unique_id = save_file(file['file_id'], user_id, file['file_name'])
            link = f"https://t.me/{BOT_USERNAME}?start={file_unique_id}"
            msg += f"📄 {file['file_name']}\n🔗 {link}\n\n"

        await callback_query.message.reply_text(msg)
        user_temp_files[user_id] = []
        await callback_query.answer()

    elif callback_query.data == "batchfile":
        file_ids = []
        for file in files:
            file_unique_id = save_file(file['file_id'], user_id, file['file_name'])
            file_ids.append(file_unique_id)

        batch_id = create_batch(user_id, file_ids)
        batch_link = f"https://t.me/{BOT_USERNAME}?start=batch_{batch_id}"
        await callback_query.message.reply_text(f"✅ Batch link created successfully!\nHere is your link:\n{batch_link}")

        user_temp_files[user_id] = []
        await callback_query.answer()


@app.on_message(filters.command('createbatch'))
async def createbatch_warning(client, message):
    await message.reply_text("⚠️ Use the new system. Send all your files first, then type /done to proceed.")


@app.on_message(filters.command('start'))
async def start(client, message):
    if len(message.command) == 1:
        await message.reply_text(
            "👋 Welcome to File Store Bot!\n\n"
            "📂 Send me multiple files one after another.\n"
            "✅ When you finish sending, type /done.\n\n"
            "You can choose to create:\n"
            "1️⃣ Single File Links\n"
            "2️⃣ One Batch Link\n\n"
            "🗂️ /myfiles - View your file history\n"
            "📁 /mybatches - View your batch history"
        )
    else:
        file_unique_id = message.command[1]
        if file_unique_id.startswith('batch_'):
            batch_id = file_unique_id.replace('batch_', '')
            file_ids = get_batch_files(batch_id)

            if not file_ids:
                await message.reply_text("❌ Batch not found or empty.")
                return

            await message.reply_text("📦 Sending batch files...")

            for file_id in file_ids:
                file_data = get_file(file_id)
                if file_data:
                    await message.reply_document(file_data[0], caption=f"{file_data[1]}")
            return

        file_data = get_file(file_unique_id)
        if file_data:
            await message.reply_document(file_data[0], caption=f"Here is your file: {file_data[1]}")
        else:
            await message.reply_text("❌ File not found.")


@app.on_message(filters.command('myfiles'))
async def my_files(client, message):
    user_id = message.from_user.id
    files = get_user_files(user_id)

    if not files:
        await message.reply_text("❌ You have no files.")
        return

    msg = "🗂️ Your Uploaded Files:\n\n"
    for file in files:
        file_id, file_name = file
        link = f"https://t.me/{BOT_USERNAME}?start={file_id}"
        msg += f"📄 {file_name}\n🔗 {link}\n\n"

    await message.reply_text(msg)


@app.on_message(filters.command('mybatches'))
async def my_batches(client, message):
    user_id = message.from_user.id
    cur.execute("SELECT batch_id FROM batches WHERE user_id=?", (user_id,))
    batches = cur.fetchall()

    if not batches:
        await message.reply_text("❌ You have no batches.")
        return

    msg = "📦 Your Batches:\n\n"
    for batch in batches:
        batch_id = batch[0]
        link = f"https://t.me/{BOT_USERNAME}?start=batch_{batch_id}"
        msg += f"🔗 {link}\n"

    await message.reply_text(msg)


@app.on_message(filters.command('help'))
async def help_command(client, message):
    await message.reply_text(
        "📂 **File Store Bot Help**\n\n"
        "📥 Send multiple files to me.\n"
        "✅ When finished, type /done to choose how you want to create links.\n\n"
        "🗂️ /myfiles - View your uploaded files\n"
        "📦 /mybatches - View your batch history"
    )


if __name__ == "__main__":
    keep_alive()
    app.run()
