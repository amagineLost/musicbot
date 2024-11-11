import os
import discord
import logging
import traceback
import random
import language_tool_python
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

# Initialize the language tool for grammar and spelling checks
tool = language_tool_python.LanguageTool('en-US')

# Role IDs for restricted commands
ALLOWED_ROLE_IDS = [1292555279246032916, 1292555408724066364]

# Channel IDs
log_channel_id = 1295049931840819280  # Channel for logging deleted/edited messages
guess_channel_id = 1304587760161656894  # Channel for the guessing game

# Generate a random number between 1 and 1,000 for the guessing game
target_number = random.randint(1, 1000)
logger.info(f"Target number for guessing game set to: {target_number}")

# User ID to monitor for grammar and spelling
monitored_user_id = 879401301526609972

# Enable all intents, including privileged ones
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True

# Create bot and command tree
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Remove the default help command
bot.remove_command('help')

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
@tasks.loop(minutes=15)
async def auto_sync_commands():
    try:
        synced = await tree.sync()
        logger.info(f'Auto-sync completed. {len(synced)} commands synced.')
    except Exception as e:
        logger.error(f"Error during periodic command sync: {traceback.format_exc()}")

# Grammar and spelling check for specific user
@bot.event
async def on_message(message):
    global target_number  # Declare target_number as global at the start of the function

    # Avoid handling messages from bots
    if message.author.bot:
        return

    # Check for grammar and spelling if the message author is the monitored user
    if message.author.id == monitored_user_id:
        matches = tool.check(message.content)
        if matches:
            corrections = []
            for match in matches:
                corrections.append(f"**Mistake:** {match.context}")
                corrections.append(f"**Suggestion:** {match.replacements[0] if match.replacements else 'No suggestion'}")
            correction_message = "\n".join(corrections)

            # Send a reply with corrections
            await message.channel.send(
                f"Hey {message.author.mention}, here’s a grammar and spelling check on your message:\n\n{correction_message}"
            )

    # Check if the message is in the specified guessing channel
    if message.channel.id == guess_channel_id:
        try:
            # Convert the message content to an integer
            guess = int(message.content)
            
            # Check if the guess matches the target number
            if guess == target_number:
                # Send a DM to the user with the specific message
                await message.author.send(f"Congratulations! 🎉 You guessed the correct number: {target_number}. You've won!")
                
                # Announce the winner in the channel
                await message.channel.send(f"{message.author.mention} has guessed the correct number and won the game!")
                
                # Reset the target number for the next round (new range from 1 to 1,000)
                target_number = random.randint(1, 1000)
                logger.info(f"New target number set for guessing game: {target_number}")
            else:
                await message.add_reaction("❌")  # Indicate an incorrect guess
            
        except ValueError:
            # Ignore non-integer messages
            pass

    # Process other bot commands or events
    await bot.process_commands(message)

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

# /allie command with a detailed paragraph
@tree.command(name="allie", description="Explain why Allie and Cole Walters should be together.")
async def allie(interaction: discord.Interaction):
    try:
        await interaction.response.defer()
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
        await interaction.followup.send(embed=embed)
    except Exception as e:
        logger.error(f"Error in /allie command: {traceback.format_exc()}")
        await interaction.followup.send("An error occurred while generating the message.", ephemeral=True)

# /send_message command with rate limiter
@tree.command(name="send_message", description="Send a message to a specific channel.")
@has_restricted_roles()
async def send_message(interaction: discord.Interaction, channel: discord.TextChannel, *, message: str):
    if not rate_limit_check(interaction.user.id, 'send_message'):
        await interaction.response.send_message("You're using this command too frequently. Please wait a bit.", ephemeral=True)
        return
    try:
        await interaction.response.defer(ephemeral=True)
        await channel.send(message)
        embed = discord.Embed(
            title="Message Sent",
            description=f"Message sent to {channel.mention}",
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(f"Sent message to {channel.name} by {interaction.user.name}")
    except discord.Forbidden:
        logger.error("Bot does not have permission to send messages to the specified channel.")
        await interaction.followup.send("I do not have permission to send messages to that channel.", ephemeral=True)
    except discord.HTTPException as e:
        logger.error(f"HTTPException in /send_message command: {e}")
        await interaction.followup.send(f"An error occurred while sending the message: {e}", ephemeral=True)
    except Exception as e:
        logger.error(f"General error in /send_message command: {traceback.format_exc()}")
        await interaction.followup.send("An unexpected error occurred.", ephemeral=True)

# /kissing command to send a fun kissing message between two users
@tree.command(name="kissing", description="Send a fun kissing message between two users.")
async def kissing(interaction: discord.Interaction, user1: discord.User, user2: discord.User):
    try:
        await interaction.response.send_message(
            f"{user1.mention} and {user2.mention} are sharing a sweet kiss! 💋", 
            ephemeral=False
        )
        logger.info(f"Kissing command used to kiss {user1.name} and {user2.name}")
    except Exception as e:
        logger.error(f"Error in /kissing command: {traceback.format_exc()}")
        await interaction.response.send_message("An unexpected error occurred while processing the kissing command.", ephemeral=True)

# DM command restricted to a specific user
@tree.command(name="dm", description="Send a private message to a specific user.")
async def dm(interaction: discord.Interaction, user: discord.User, *, message: str):
    # Check if the command user is the allowed user
    if interaction.user.id != 713290565835554839:
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    # Try to send a DM to the specified user
    try:
        await user.send(message)  # Send the message to the specified user
        await interaction.response.send_message(f"Message sent to {user.display_name}.", ephemeral=True)
        logger.info(f"/dm command used by {interaction.user.name} to send a DM to {user.name}.")
    except discord.Forbidden:
        logger.error("Bot cannot send a DM to the specified user.")
        await interaction.response.send_message("I cannot send a DM to this user. They may have DMs disabled.", ephemeral=True)
    except Exception as e:
        logger.error(f"Error in /dm command: {traceback.format_exc()}")
        await interaction.response.send_message("An unexpected error occurred while sending the message.", ephemeral=True)

# Event handler for deleted messages with embeds and audit log lookup
@bot.event
async def on_message_delete(message):
    if message.author.bot or message.guild is None:
        return

    log_channel = bot.get_channel(log_channel_id)
    if log_channel:
        deleter = "Unknown"
        try:
            # Fetch the audit logs to find who deleted the message
            async for entry in message.guild.audit_logs(action=discord.AuditLogAction.message_delete, limit=1):
                if entry.target.id == message.author.id and (discord.utils.utcnow() - entry.created_at).total_seconds() < 5:
                    deleter = entry.user.mention
                    break

            # Truncate the message content to 1024 characters if it's too long
            message_content = message.content or "No content"
            if len(message_content) > 1024:
                message_content = message_content[:1021] + "..."

            # Embed with detailed deletion information
            embed = discord.Embed(
                title="Message Deleted",
                color=discord.Color.red()
            )
            embed.add_field(name="Author", value=message.author.mention, inline=True)
            embed.add_field(name="Channel", value=message.channel.mention, inline=True)
            embed.add_field(name="Deleted by", value=deleter, inline=True)
            embed.add_field(name="Content", value=message_content, inline=False)

            await log_channel.send(embed=embed)
            logger.info(f"Logged deleted message from {message.author} in {message.channel}, deleted by {deleter}")

        except discord.Forbidden:
            logger.error("Bot does not have permission to view audit logs.")
            await log_channel.send("Error: I do not have permission to view audit logs to detect the message deleter.")
        except Exception as e:
            logger.error(f"Error in on_message_delete: {traceback.format_exc()}")

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
