import os
import discord
import logging
import aiohttp
import json
import sqlite3
from datetime import timedelta, datetime
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

# Channel ID where logs of deleted and edited messages will be sent
log_channel_id = 1295049931840819280

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

# Leaderboard command to display the top 10 users
@bot.command(name="leaderboard1", help="Displays the top 10 users in the XP leaderboard.")
async def leaderboard1(ctx):
    try:
        # Fetch top 10 users sorted by XP in descending order
        cursor.execute("SELECT user_id, xp FROM xp_leaderboard ORDER BY xp DESC LIMIT 10")
        leaderboard_data = cursor.fetchall()
        
        # Format the leaderboard message
        if leaderboard_data:
            leaderboard_message = "**XP Leaderboard**\n\n"
            for rank, (user_id, xp) in enumerate(leaderboard_data, start=1):
                user = bot.get_user(user_id) or f"<@{user_id}>"  # Mention the user or fallback to user_id if not found
                leaderboard_message += f"{rank}. {user}: {xp} XP\n"
        else:
            leaderboard_message = "No data available on the leaderboard yet."

        await ctx.send(leaderboard_message)
    except Exception as e:
        logger.error(f"Error retrieving leaderboard: {e}")
        await ctx.send("An error occurred while retrieving the leaderboard.")

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}')
    await tree.sync()  # Ensure all application commands are synced
    start_xp_event.start()

# Handle unknown commands to reduce log noise
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        logger.info(f"Unknown command used: {ctx.message.content}")
    else:
        logger.error(f"An error occurred: {error}")

# Detect deleted messages and log to the specified channel only
@bot.event
async def on_message_delete(message):
    if message.author.bot or message.guild.me in message.mentions:
        return
    if message.guild and message.content:
        log_channel = bot.get_channel(log_channel_id)
        if log_channel:
            try:
                # Construct reply information if applicable
                reply_info = ""
                if message.reference and message.reference.resolved:
                    replied_user = message.reference.resolved.author
                    reply_info = f"(This was a reply to {replied_user.mention})"
                
                # Embed with deleted message details
                embed = discord.Embed(
                    title="Message Deleted",
                    description=f"{message.author.mention} deleted a message in {message.channel.mention}:\n\n'{message.content}' {reply_info}",
                    color=discord.Color.red()
                )
                await log_channel.send(embed=embed)
            except discord.Forbidden:
                logger.error("Bot does not have permission to send messages in the log channel.")
            except Exception as e:
                logger.error(f"Error sending deleted message log: {e}")

# Detect edited messages and log the changes in the specified channel only
@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content:
        return
    log_channel = bot.get_channel(log_channel_id)
    if log_channel:
        try:
            # Embed with edited message details
            embed = discord.Embed(
                title="Message Edited",
                color=discord.Color.blue()
            )
            embed.add_field(name="Before", value=before.content, inline=False)
            embed.add_field(name="After", value=after.content, inline=False)
            embed.set_footer(text=f"Edited by {before.author.display_name} in #{before.channel}")
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            logger.error("Bot does not have permission to send messages in the log channel.")
        except Exception as e:
            logger.error(f"Error sending edited message log: {e}")

try:
    bot.run(DISCORD_TOKEN)
except Exception as e:
    logger.error(f"Error starting the bot: {e}")
