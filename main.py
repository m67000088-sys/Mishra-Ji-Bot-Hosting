"""
main.py
-------
TheHostServer - Telegram Bot Hosting Service
Entry point. Sets up all command handlers.

Developed by Aditya

Run with:
    export BOT_TOKEN="your_host_bot_token"
    python main.py
"""

import logging
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

import db
import deploy
import manager

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

WELCOME_TEXT = """🤖 Welcome to Bot Hosting Service!

I can host your Telegram bots written in Python.

Commands:
/deploy - Upload and deploy a new bot
/list - List your deployed bots
/stop <id> - Stop a running bot
/start_bot <id> - Start a stopped bot
/delete <id> - Delete a deployed bot
/help - Show this message

How to deploy:
1. Send me a .zip file or .py file
2. Include requirements.txt
3. Make sure your bot uses long polling (not webhooks)
4. Your bot should read token from environment variable BOT_TOKEN

Limits:
- Max 5 bots per user
- Max file size: 10MB
- Python 3.11+
- Supports python-telegram-bot library

Developed by Aditya
"""

# in-memory state: user_id -> waiting for file? / waiting for token for which bot_id?
pending_deploys = {}   # user_id -> {"folder": str, "entry": str, "name": str}
pending_token = {}     # user_id -> deploy dict waiting for token text


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_TEXT)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_TEXT)


async def deploy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if db.count_user_bots(user_id) >= manager.MAX_BOTS_PER_USER:
        await update.message.reply_text(
            f"❌ Limit reached. Max {manager.MAX_BOTS_PER_USER} bots per user allowed."
        )
        return
    await update.message.reply_text(
        "📦 Send me your bot's .zip file (with requirements.txt) or a single .py file."
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    document = update.message.document

    if db.count_user_bots(user_id) >= manager.MAX_BOTS_PER_USER:
        await update.message.reply_text(
            f"❌ Limit reached. Max {manager.MAX_BOTS_PER_USER} bots per user allowed."
        )
        return

    if not (document.file_name.endswith(".zip") or document.file_name.endswith(".py")):
        await update.message.reply_text("❌ Sirf .zip ya .py file bhejo.")
        return

    try:
        deploy.validate_size(document.file_size, manager.MAX_FILE_SIZE_MB)
    except ValueError as e:
        await update.message.reply_text(f"❌ {e}")
        return

    await update.message.reply_text("⏳ Receiving file...")

    tg_file = await document.get_file()
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=os.path.splitext(document.file_name)[1]
    ) as tmp:
        local_path = tmp.name
    await tg_file.download_to_drive(local_path)

    try:
        folder_path = deploy.prepare_folder(user_id, document.file_name)
        entry_file = deploy.extract_upload(local_path, folder_path)
    except Exception as e:
        await update.message.reply_text(f"❌ Deploy failed: {e}")
        return
    finally:
        os.remove(local_path)

    bot_name = deploy.safe_bot_name(os.path.splitext(document.file_name)[0])
    pending_deploys[user_id] = {
        "folder": folder_path,
        "entry": entry_file,
        "name": bot_name,
    }
    pending_token[user_id] = True

    await update.message.reply_text(
        f"✅ File received. Entry point detected: `{entry_file}`\n\n"
        "Ab apne bot ka Telegram BOT_TOKEN bhejo (BotFather se liya hua):",
        parse_mode="Markdown",
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if pending_token.get(user_id) and user_id in pending_deploys:
        token = update.message.text.strip()
        info = pending_deploys.pop(user_id)
        pending_token.pop(user_id, None)

        await update.message.reply_text("🔧 Installing dependencies... isme thoda time lagega.")

        try:
            venv_path = manager.make_venv(info["folder"])
            manager.install_requirements(info["folder"], venv_path)
        except Exception as e:
            await update.message.reply_text(f"❌ Dependency install failed: {e}")
            return

        bot_id = db.add_bot(
            user_id, info["name"], info["folder"], info["entry"], token
        )
        bot_row = db.get_bot(bot_id, user_id)

        try:
            pid = manager.start_bot(bot_row)
            db.update_status(bot_id, "running", pid)
            await update.message.reply_text(
                f"🚀 Bot deployed and started!\nID: `{bot_id}`\nName: {info['name']}\n\n"
                f"Use /list to see all your bots, /stop {bot_id} to stop it.",
                parse_mode="Markdown",
            )
        except Exception as e:
            db.update_status(bot_id, "crashed")
            await update.message.reply_text(f"⚠️ Bot saved but failed to start: {e}")
        return

    await update.message.reply_text("Type /help to see available commands.")


async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bots = db.list_bots(user_id)
    if not bots:
        await update.message.reply_text("Tumne abhi tak koi bot deploy nahi kiya. /deploy try karo.")
        return

    lines = ["📋 *Your deployed bots:*\n"]
    for b in bots:
        running = manager.is_running(b["pid"])
        status_icon = "🟢 running" if running else "🔴 stopped"
        lines.append(f"`{b['id']}` - {b['bot_name']} ({status_icon})")
    lines.append("\nUse /stop <id>, /start_bot <id>, or /delete <id>")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: /stop <bot_id>")
        return
    bot_row = db.get_bot(context.args[0], user_id)
    if not bot_row:
        await update.message.reply_text("Bot nahi mila.")
        return
    manager.stop_bot(bot_row["pid"])
    db.update_status(bot_row["id"], "stopped", None)
    await update.message.reply_text(f"🛑 Bot `{bot_row['id']}` stopped.", parse_mode="Markdown")


async def start_bot_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: /start_bot <bot_id>")
        return
    bot_row = db.get_bot(context.args[0], user_id)
    if not bot_row:
        await update.message.reply_text("Bot nahi mila.")
        return
    try:
        pid = manager.start_bot(bot_row)
        db.update_status(bot_row["id"], "running", pid)
        await update.message.reply_text(f"🚀 Bot `{bot_row['id']}` started.", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Start failed: {e}")


async def delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: /delete <bot_id>")
        return
    bot_row = db.get_bot(context.args[0], user_id)
    if not bot_row:
        await update.message.reply_text("Bot nahi mila.")
        return
    manager.stop_bot(bot_row["pid"])
    import shutil
    shutil.rmtree(bot_row["folder_path"], ignore_errors=True)
    db.delete_bot(bot_row["id"], user_id)
    await update.message.reply_text(f"🗑️ Bot `{bot_row['id']}` deleted.", parse_mode="Markdown")


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Mishra Ji Bot Hosting is running")

    def log_message(self, format, *args):
        return


def start_health_server():
    """Render Web Service ke health check ke liye lightweight HTTP server."""
    port = int(os.environ.get("PORT", "10000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health server listening on 0.0.0.0:%s", port)
    return server


def main():
    os.makedirs("bots_data/users", exist_ok=True)
    db.init_db()

    # Token GitHub/code mein nahi rakha gaya.
    # Render Environment Variable ka naam: BOT_TOKEN
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "BOT_TOKEN environment variable is not set. "
            "Render Settings -> Environment Variables mein BOT_TOKEN set karo."
        )

    # Render Web Service ke liye HTTP health endpoint start karo.
    start_health_server()

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("deploy", deploy_cmd))
    app.add_handler(CommandHandler("list", list_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("start_bot", start_bot_cmd))
    app.add_handler(CommandHandler("delete", delete_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("TheHostServer starting... (long polling)")
    app.run_polling()


if __name__ == "__main__":
    main()
