import os
import discord
import logging
import aiohttp
import json
import sqlite3
from datetime import timedelta, datetime
from collections import defaultdict
from discord import app_commands
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

# SQLite setup for XP leaderboard
conn = sqlite3.connect("xp_leaderboard.db")
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
    except FileNotFoundError:
        pass

# Save image data to JSON
def save_image_data():
    with open("image_storage.json", "w") as f:
        json.dump(image_storage, f)

load_image_data()  # Load image data on start

# Enable all intents including the privileged ones
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# Create bot and command tree
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Restrict command access to specific roles
def has_restricted_roles():
    async def predicate(interaction: discord.Interaction):
        allowed_roles = ALLOWED_ROLE_IDS
        user_roles = [role.id for role in interaction.user.roles]
        if any(role_id in user_roles for role_id in allowed_roles):
            return True
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return False
    return app_commands.check(predicate)

# Send message command
@tree.command(name="send_message", description="Send a message to a specific channel.")
@has_restricted_roles()
async def send_message(interaction: discord.Interaction, channel: discord.TextChannel, *, message: str):
    try:
        await channel.send(message)
        await interaction.response.send_message(f"Message sent to {channel.mention}", ephemeral=True)
    except Exception as e:
        logger.error(f"Error in /send_message command: {e}")
        await interaction.response.send_message("An error occurred while sending the message.", ephemeral=True)

# Start XP event every 15 minutes silently
@tasks.loop(minutes=15)
async def start_xp_event():
    global event_running
    event_running = True
    logger.info("XP event started.")
    await discord.utils.sleep_until(datetime.utcnow() + timedelta(minutes=5))
    event_running = False
    logger.info("XP event ended.")
    cursor.execute("DELETE FROM xp_leaderboard")
    conn.commit()

# Update leaderboard on each message
@bot.event
async def on_message(message):
    global event_running
    if message.author == bot.user or message.channel.id != event_channel_id:
        return
    if event_running:
        user_id = message.author.id
        current_time = datetime.utcnow().isoformat()
        cursor.execute("SELECT xp FROM xp_leaderboard WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        current_xp = result[0] if result else 0
        new_xp = current_xp + 1
        cursor.execute(
            "INSERT OR REPLACE INTO xp_leaderboard (user_id, xp, last_updated) VALUES (?, ?, ?)",
            (user_id, new_xp, current_time)
        )
        conn.commit()
    await bot.process_commands(message)

# Command to display the top 10 users in the XP leaderboard
@bot.command()
async def leaderboard(ctx):
    cursor.execute("SELECT user_id, xp FROM xp_leaderboard ORDER BY xp DESC LIMIT 10")
    top_users = cursor.fetchall()
    if top_users:
        leaderboard_message = "**Top 10 XP Leaderboard:**\n"
        for i, (user_id, xp) in enumerate(top_users, 1):
            user = await bot.fetch_user(user_id)
            leaderboard_message += f"{i}. {user.name} - {xp} XP\n"
        await ctx.send(leaderboard_message)
    else:
        await ctx.send("The leaderboard is currently empty.")

# Command to store a new image URL for a user with a timestamp
@bot.command()
async def store(ctx, username: str, image_url: str):
    image_storage[username] = {
        "image_url": image_url,
        "last_updated": datetime.utcnow().isoformat()
    }
    save_image_data()
    await ctx.send(f"Updated image for {username}.")

# Command to retrieve the stored image for a user
@bot.command()
async def proof(ctx, username: str):
    if username in image_storage:
        image_info = image_storage[username]
        await ctx.send(f"Image for {username}: {image_info['image_url']} (Last updated: {image_info['last_updated']})")
    else:
        await ctx.send(f"No image stored for {username}.")

# Detect deleted messages
@bot.event
async def on_message_delete(message):
    if message.author.bot or message.guild.me in message.mentions:
        return
    if message.guild and message.content:
        try:
            reply_info = ""
            if message.reference and message.reference.resolved:
                replied_user = message.reference.resolved.author
                reply_info = f"(This was a reply to {replied_user.mention})"
            embed = discord.Embed(
                title="Message Deleted",
                description=f"{message.author.mention} deleted a message in {message.channel.mention}:\n\n'{message.content}' {reply_info}",
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed)
        except discord.Forbidden:
            logger.error("Bot does not have permission to send messages in this channel.")
        except Exception as e:
            logger.error(f"Error sending deleted message log: {e}")

# Detect edited messages and log the change
@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content:
        return
    if before.guild:
        try:
            embed = discord.Embed(
                title="Message Edited",
                color=discord.Color.blue()
            )
            embed.add_field(name="Before", value=before.content, inline=False)
            embed.add_field(name="After", value=after.content, inline=False)
            embed.set_footer(text=f"Edited by {before.author.display_name} in #{before.channel}")
            await before.channel.send(embed=embed)
        except discord.Forbidden:
            logger.error("Bot does not have permission to send messages in this channel.")
        except Exception as e:
            logger.error(f"Error sending edited message log: {e}")

# Bot setup hook
async def setup_hook():
    global session
    session = aiohttp.ClientSession()
    logger.info("Bot setup complete.")

@bot.event
async def on_close():
    if session:
        await session.close()
    conn.close()

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'Logged in as {bot.user}')
    start_xp_event.start()  # Start the XP event loop

bot.setup_hook = setup_hook

try:
    bot.run(DISCORD_TOKEN)
except Exception as e:
    logger.error(f"Error starting the bot: {e}")
    
