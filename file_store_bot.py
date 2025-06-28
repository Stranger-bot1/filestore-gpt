# file_store_bot.py

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import uuid
import os

API_ID = 24344133
API_HASH = "edbe7000baef13fa5a6c45c8edc4be66"
BOT_TOKEN = "8046719850:AAGxJ6Wn63mVJCq7SAHW2sU9aIL2VmfjZig"
BOT_USERNAME = "file_storing_gpt_bot"

app = Client("file_store_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

conn = sqlite3.connect("file_store.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS files (id TEXT, file_id TEXT, user_id INTEGER, file_name TEXT)""")
cur.execute("""CREATE TABLE IF NOT EXISTS batches (batch_id TEXT, user_id INTEGER, file_ids TEXT)""")
conn.commit()


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


@app.on_message(filters.private & filters.document)
async def handle_file(client, message):
    file_id = message.document.file_id
    file_name = message.document.file_name
    user_id = message.from_user.id

    file_unique_id = save_file(file_id, user_id, file_name)

    link = f"https://t.me/{BOT_USERNAME}?start={file_unique_id}"
    await message.reply_text(f"✅ File saved successfully!\nHere is your shareable link:\n{link}")


@app.on_message(filters.command('start'))
async def start(client, message):
    if len(message.command) == 1:
        await message.reply_text(
            "👋 Welcome to File Store Bot!\n\n"
            "📂 Send me any file and I'll give you a permanent shareable link.\n\n"
            "🗂️ /myfiles - View your files\n"
            "📦 /createbatch - Create a batch of files\n"
            "📁 /mybatches - View your batches"
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


@app.on_message(filters.command('createbatch'))
async def create_batch_command(client, message):
    user_id = message.from_user.id
    files = get_user_files(user_id)

    if not files:
        await message.reply_text("❌ You have no files to batch.")
        return

    buttons = []
    for file in files:
        file_id, file_name = file
        buttons.append([InlineKeyboardButton(f"✅ {file_name}", callback_data=f"batchselect_{file_id}")])

    buttons.append([InlineKeyboardButton("✔️ Create Batch", callback_data="createbatch_final")])

    await message.reply_text("Select files to add to your batch:", reply_markup=InlineKeyboardMarkup(buttons))
    app.user_batch_selections = {user_id: []}


@app.on_callback_query()
async def batch_selection(client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data

    if data.startswith("batchselect_"):
        file_id = data.split("_")[1]
        if file_id not in app.user_batch_selections[user_id]:
            app.user_batch_selections[user_id].append(file_id)
        await callback_query.answer("✅ File added to batch")

    elif data == "createbatch_final":
        selected_files = app.user_batch_selections.get(user_id, [])
        if not selected_files:
            await callback_query.message.reply_text("❌ No files selected for batch.")
            return

        batch_id = create_batch(user_id, selected_files)
        batch_link = f"https://t.me/{BOT_USERNAME}?start=batch_{batch_id}"
        await callback_query.message.reply_text(f"✅ Batch created!\nHere is your link:\n{batch_link}")

    await callback_query.answer()


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
        "📂 **File Store Bot Commands**\n\n"
        "/myfiles - View your uploaded files\n"
        "/createbatch - Create a batch of files\n"
        "/mybatches - View your batches\n"
        "Send a file to get a shareable link"
    )


app.run()
