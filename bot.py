import os
import discord
import logging
import traceback
from discord import app_commands
from discord.ext import commands, tasks

# Set up detailed logging with timestamps and save to a file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.FileHandler("discord_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Retrieve the bot token from Render's environment variables
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN environment variable not set!")

# Role IDs for restricted commands
ALLOWED_ROLE_IDS = [1292555279246032916, 1292555408724066364]

# Channel ID where logs of deleted and edited messages will be sent
log_channel_id = 1295049931840819280

# Enable all intents, including privileged ones
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True

# Create bot and command tree
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Helper function for rate limiting
command_usage = {}

def rate_limit_check(user_id, command_name, limit=5, interval=60):
    from time import time
    current_time = time()
    if user_id not in command_usage:
        command_usage[user_id] = {}
    if command_name not in command_usage[user_id]:
        command_usage[user_id][command_name] = []
    timestamps = command_usage[user_id][command_name]

    # Filter out old timestamps
    timestamps = [t for t in timestamps if current_time - t < interval]
    if len(timestamps) >= limit:
        return False
    timestamps.append(current_time)
    command_usage[user_id][command_name] = timestamps
    return True

# Restrict command access to specific roles
def has_restricted_roles():
    async def predicate(interaction: discord.Interaction):
        user_roles = [role.id for role in interaction.user.roles]
        if any(role_id in user_roles for role_id in ALLOWED_ROLE_IDS):
            return True
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return False
    return app_commands.check(predicate)

# Periodic task to auto-sync commands
@tasks.loop(minutes=15)  # Adjusted the interval to 15 minutes
async def auto_sync_commands():
    try:
        synced = await tree.sync()
        logger.info(f'Auto-sync completed. {len(synced)} commands synced.')
    except Exception as e:
        logger.error(f"Error during periodic command sync: {traceback.format_exc()}")

# /ping command to check bot latency
@tree.command(name="ping", description="Check the bot's latency.")
async def ping(interaction: discord.Interaction):
    try:
        latency = bot.latency * 1000  # Convert latency to milliseconds
        embed = discord.Embed(
            title="Pong! 🏓",
            description=f"Latency: {latency:.2f}ms",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        logger.error(f"Error in /ping command: {traceback.format_exc()}")
        await interaction.response.send_message("An error occurred while checking latency.", ephemeral=True)

# /purge command with a rate limiter
@tree.command(name="purge", description="Delete a specified number of recent messages.")
@has_restricted_roles()
async def purge(interaction: discord.Interaction, amount: int):
    if not rate_limit_check(interaction.user.id, 'purge'):
        await interaction.response.send_message("You're using this command too frequently. Please wait a bit.", ephemeral=True)
        return
    try:
        await interaction.response.defer(ephemeral=True)

        if not interaction.channel.permissions_for(interaction.user).manage_messages:
            await interaction.followup.send("You do not have permission to manage messages.", ephemeral=True)
            return

        if amount <= 0:
            await interaction.followup.send("Please specify a number greater than 0.", ephemeral=True)
            return

        deleted = await interaction.channel.purge(limit=amount)
        embed = discord.Embed(
            title="Purge Successful",
            description=f"Deleted {len(deleted)} messages.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(f"/purge command used by {interaction.user.name}: {len(deleted)} messages deleted.")

    except discord.Forbidden:
        logger.error("Bot does not have permission to delete messages.")
        await interaction.followup.send("I do not have permission to delete messages in this channel.", ephemeral=True)
    except discord.HTTPException as e:
        logger.error(f"HTTPException in /purge command: {e}")
        await interaction.followup.send(f"An error occurred while deleting messages: {e}", ephemeral=True)
    except Exception as e:
        logger.error(f"General error in /purge command: {traceback.format_exc()}")
        await interaction.followup.send("An unexpected error occurred.", ephemeral=True)

# /send_message command with rate limiter
@tree.command(name="send_message", description="Send a message to a specific channel.")
@has_restricted_roles()
async def send_message(interaction: discord.Interaction, channel: discord.TextChannel, *, message: str):
    if not rate_limit_check(interaction.user.id, 'send_message'):
        await interaction.response.send_message("You're using this command too frequently. Please wait a bit.", ephemeral=True)
        return
    try:
        await channel.send(message)
        embed = discord.Embed(
            title="Message Sent",
            description=f"Message sent to {channel.mention}",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"Sent message to {channel.name} by {interaction.user.name}")
    except discord.Forbidden:
        logger.error("Bot does not have permission to send messages to the specified channel.")
        await interaction.response.send_message("I do not have permission to send messages to that channel.", ephemeral=True)
    except discord.HTTPException as e:
        logger.error(f"HTTPException in /send_message command: {e}")
        await interaction.response.send_message(f"An error occurred while sending the message: {e}", ephemeral=True)
    except Exception as e:
        logger.error(f"General error in /send_message command: {traceback.format_exc()}")
        await interaction.response.send_message("An unexpected error occurred.", ephemeral=True)

# /allie command with a detailed paragraph
@tree.command(name="allie", description="Explain why Allie and Cole Walters should be together.")
async def allie(interaction: discord.Interaction):
    try:
        paragraph = (
            "Allie and Cole Walters from 'My Life with the Walter Boys' share an undeniable chemistry that "
            "captures the essence of young, unexpected love. Cole’s charming and adventurous nature complements "
            "Allie's resilience and determination as she navigates her new life. Their relationship is built on "
            "growth, understanding, and the balance between fiery moments and heartfelt connections. Despite the "
            "challenges they face, their dynamic brings out the best in each other, showcasing a bond that’s both "
            "playful and deeply meaningful. The way Cole’s spontaneity pushes Allie out of her comfort zone, and how "
            "she, in turn, grounds him with her thoughtful presence, forms a story that is not only compelling but "
            "also a testament to how opposites can attract and create a beautiful partnership."
        )
        embed = discord.Embed(
            title="Allie and Cole Walters",
            description=paragraph,
            color=discord.Color.purple()
        )
        await interaction.response.send_message(embed=embed, ephemeral=False)
    except Exception as e:
        logger.error(f"Error in /allie command: {traceback.format_exc()}")
        await interaction.response.send_message("An error occurred while generating the message.", ephemeral=True)

# Event handler for deleted messages with embeds
@bot.event
async def on_message_delete(message):
    if message.author.bot or message.guild is None:
        return
    log_channel = bot.get_channel(log_channel_id)
    if log_channel:
        try:
            embed = discord.Embed(
                title="Message Deleted",
                description=f"**Author**: {message.author.mention}\n**Channel**: {message.channel.mention}\n\n{message.content}",
                color=discord.Color.red()
            )
            await log_channel.send(embed=embed)
            logger.info(f"Logged deleted message from {message.author.name} in {message.channel.name}")
        except Exception as e:
            logger.error(f"Error sending deleted message log: {traceback.format_exc()}")

# Event handler for edited messages with improved checking
@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content.strip() == after.content.strip():
        return
    log_channel = bot.get_channel(log_channel_id)
    if log_channel:
        try:
            embed = discord.Embed(
                title="Message Edited",
                color=discord.Color.blue()
            )
            embed.add_field(name="Before", value=before.content[:1024] or "Empty", inline=False)
            embed.add_field(name="After", value=after.content[:1024] or "Empty", inline=False)
            embed.set_footer(text=f"Edited by {before.author.display_name} in #{before.channel}")
            await log_channel.send(embed=embed)
            logger.info(f"Logged edited message by {before.author.name} in {before.channel.name}")
        except Exception as e:
            logger.error(f"Error sending edited message log: {traceback.format_exc()}")

# Custom help command
@bot.command()
async def help(ctx):
    embed = discord.Embed(title="Help", description="List of commands and their descriptions")
    for command in bot.commands:
        embed.add_field(name=f"/{command.name}", value=command.help or "No description", inline=False)
    await ctx.send(embed=embed)

# Log when the bot is ready and start the periodic sync
@bot.event
async def on_ready():
    try:
        synced = await tree.sync()  # Ensure all application commands are synced
        logger.info(f'Initial sync completed. {len(synced)} commands synced.')
    except Exception as e:
        logger.error(f"Error during initial command sync: {traceback.format_exc()}")

    if not auto_sync_commands.is_running():
        auto_sync_commands.start()  # Start the loop for periodic command syncing
    logger.info(f'Logged in as {bot.user}')

# Run the bot with error handling
try:
    bot.run(DISCORD_TOKEN)
except Exception as e:
    logger.error(f"Error starting the bot: {traceback.format_exc()}")
