import os
import discord
import logging
import aiohttp
import json
import sqlite3
from datetime import timedelta, datetime
from discord.ext import commands, tasks

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Retrieve the bot token from Render's environment variables
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN environment variable not set!")

# Role IDs for restricted commands
ALLOWED_ROLE_IDS = [1292555279246032916, 1292555408724066364]

# Event channel and image storage
event_channel_id = 1292553891581268010
event_running = False
image_storage = {}

# Set up SQLite database connection with error handling
db_path = "xp_leaderboard.db"

# Delete the database if it's corrupted
if os.path.exists(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    except sqlite3.DatabaseError:
        os.remove(db_path)
        conn = sqlite3.connect(db_path)

# Now create the database and table if it doesn’t exist
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS xp_leaderboard (
    user_id INTEGER PRIMARY KEY,
    xp INTEGER,
    last_updated TEXT
)
""")
conn.commit()

# Load image data from JSON
def load_image_data():
    global image_storage
    try:
        with open("image_storage.json", "r") as f:
            image_storage = json.load(f)
            logger.info("Image data loaded successfully.")
    except FileNotFoundError:
        logger.info("No existing image storage found. Starting fresh.")
        image_storage = {}

# Save image data to JSON
def save_image_data():
    with open("image_storage.json", "w") as f:
        json.dump(image_storage, f)
        logger.info("Image data saved successfully.")

load_image_data()  # Load image data on start

# Enable all intents including the privileged ones
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# Create bot and command tree
bot = commands.Bot(command_prefix="!", intents=intents)

# Task to start XP event every hour with logging control
@tasks.loop(hours=1)
async def start_xp_event():
    global event_running
    event_running = True
    logger.info("XP event started.")

    # End the XP event after 5 minutes
    await discord.utils.sleep_until(datetime.utcnow() + timedelta(minutes=5))
    event_running = False
    logger.info("XP event ended.")

    # Clear the XP leaderboard after the event ends
    cursor.execute("DELETE FROM xp_leaderboard")
    conn.commit()

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}')
    start_xp_event.start()

# Handle unknown commands to reduce log noise
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        logger.info(f"Unknown command used: {ctx.message.content}")
    else:
        logger.error(f"An error occurred: {error}")

try:
    bot.run(DISCORD_TOKEN)
except Exception as e:
    logger.error(f"Error starting the bot: {e}")
