import os
import discord
import logging
import traceback
import random
import requests
import time
import re
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

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN environment variable not set!")

# Role and Channel IDs
ALLOWED_ROLE_IDS = [1292555279246032916, 1292555408724066364]
log_channel_id = 1295049931840819280
guess_channel_id = 1304587760161656894

monitored_user_ids = {879401309972}
dm_allowed_user_ids = {713290565835554839}

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

command_usage = {}
guessing_game_leaderboard = {}

target_number = random.randint(1, 1000)
logger.info(f"Target number for guessing game set to: {target_number}")

def rate_limit_check(user_id, command_name, limit=5, interval=60):
    current_time = time.time()
    if user_id not in command_usage:
        command_usage[user_id] = {}
    if command_name not in command_usage[user_id]:
        command_usage[user_id][command_name] = []
    timestamps = command_usage[user_id][command_name]
    timestamps = [t for t in timestamps if current_time - t < interval]
    command_usage[user_id][command_name] = timestamps

    if len(timestamps) >= limit:
        retry_after = int(interval - (current_time - timestamps[0]))
        return False, retry_after
    timestamps.append(current_time)
    return True, None

def has_restricted_roles():
    async def predicate(interaction: discord.Interaction):
        user_roles = [role.id for role in interaction.user.roles]
        if any(role_id in user_roles for role_id in ALLOWED_ROLE_IDS):
            return True
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return False
    return app_commands.check(predicate)

@tasks.loop(minutes=15)
async def auto_sync_commands():
    try:
        synced = await tree.sync()
        logger.info(f'Auto-sync completed. {len(synced)} commands synced.')
    except Exception:
        logger.error(f"Error during periodic command sync: {traceback.format_exc()}")

def is_word(text):
    """ Check if text contains alphabetical characters, excluding symbols and emoticons. """
    return bool(re.search(r'[a-zA-Z]', text))

def advanced_grammar_check(text):
    url = "https://api.languagetool.org/v2/check"
    data = {"text": text, "language": "en-US"}
    try:
        response = requests.post(url, data=data, timeout=10)
        response.raise_for_status()
        matches = response.json().get("matches", [])
        
        # Filter out corrections that aren't words (e.g., symbols, emoticons)
        corrections = []
        for match in matches:
            # Only include corrections if the text contains letters (ignoring symbols or emoticons)
            if is_word(match['context']['text']):
                error_type = match['rule']['issueType']
                context = match['context']['text']
                error_text = f"**Error Type:** {error_type.capitalize()}\n"
                error_text += f"**Problem:** {context}\n"
                error_text += f"**Suggested Correction:** {match['replacements'][0]['value'] if match['replacements'] else 'No suggestion'}"
                corrections.append(error_text)
        
        return corrections
    except (requests.RequestException, ValueError):
        logger.warning("Failed to reach LanguageTool API.")
        return ["Unable to perform grammar check due to API issues."]

@bot.event
async def on_message(message):
    global target_number

    if message.author.bot:
        return

    # Only check for grammar for specific monitored users
    if message.author.id in monitored_user_ids:
        corrections = advanced_grammar_check(message.content)
        if corrections:
            feedback = "\n\n".join(corrections)
            await message.channel.send(f"Grammar and Spelling Suggestions:\n{feedback}")

    # Guessing game logic
    if message.channel.id == guess_channel_id:
        try:
            guess = int(message.content)
            if guess == target_number:
                await message.author.send(f"🎉 You guessed the correct number: {target_number}!")
                await message.channel.send(f"{message.author.mention} won the game!")
                guessing_game_leaderboard[message.author] = guessing_game_leaderboard.get(message.author, 0) + 1
                target_number = random.randint(1, 1000)
                logger.info(f"New target number set: {target_number}")
            else:
                await message.add_reaction("❌")
        except ValueError:
            pass

    await bot.process_commands(message)

@bot.event
async def on_message_delete(message):
    if message.author.bot or message.guild is None:
        return
    log_channel = bot.get_channel(log_channel_id)
    if log_channel:
        deleter = "Unknown"
        try:
            async for entry in message.guild.audit_logs(action=discord.AuditLogAction.message_delete, limit=1):
                if entry.target.id == message.author.id and (discord.utils.utcnow() - entry.created_at).total_seconds() < 5:
                    deleter = entry.user.mention
                    break
            embed = discord.Embed(
                title="Message Deleted",
                color=discord.Color.red()
            )
            embed.add_field(name="Author", value=message.author.mention, inline=True)
            embed.add_field(name="Channel", value=message.channel.mention, inline=True)
            embed.add_field(name="Deleted by", value=deleter, inline=True)
            embed.add_field(name="Content", value=message.content[:1024] or "No content", inline=False)
            await log_channel.send(embed=embed)
        except Exception:
            logger.error(f"Error in on_message_delete: {traceback.format_exc()}")

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
        except Exception:
            logger.error(f"Error sending edited message log: {traceback.format_exc()}")

@tree.command(name="shutdown", description="Safely shut down the bot.")
@has_restricted_roles()
async def shutdown(interaction: discord.Interaction):
    await interaction.response.send_message("Shutting down...", ephemeral=True)
    await bot.close()
    logger.info("Bot is shutting down...")

@tree.command(name="ping", description="Check the bot's latency.")
async def ping(interaction: discord.Interaction):
    try:
        latency = bot.latency * 1000
        embed = discord.Embed(
            title="Pong! 🏓",
            description=f"Latency: {latency:.2f}ms",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception:
        logger.error(f"Error in /ping command: {traceback.format_exc()}")

@tree.command(name="purge", description="Delete a specified number of recent messages.")
@has_restricted_roles()
async def purge(interaction: discord.Interaction, amount: int):
    allowed, retry_after = rate_limit_check(interaction.user.id, 'purge')
    if not allowed:
        await interaction.response.send_message(f"Rate limited. Try again in {retry_after} seconds.", ephemeral=True)
        return
    if amount <= 0:
        await interaction.response.send_message("Please specify a number greater than 0.", ephemeral=True)
        return
    deleted = await interaction.channel.purge(limit=amount)
    embed = discord.Embed(
        title="Purge Successful",
        description=f"Deleted {len(deleted)} messages.",
        color=discord.Color.red()
    )
    await interaction.followup.send(embed=embed, ephemeral=True)

@tree.command(name="leaderboard", description="Display the guessing game leaderboard.")
async def leaderboard(interaction: discord.Interaction):
    leaderboard_text = "\n".join([f"{user.mention}: {score} wins" for user, score in sorted(guessing_game_leaderboard.items(), key=lambda x: x[1], reverse=True)])
    embed = discord.Embed(
        title="Guessing Game Leaderboard",
        description=leaderboard_text or "No winners yet.",
        color=discord.Color.gold()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandInvokeError):
        logger.error(f"Error in command {ctx.command}: {error}")
        await ctx.send("An unexpected error occurred while processing the command.")

@bot.event
async def on_ready():
    synced = await tree.sync()
    if not auto_sync_commands.is_running():
        auto_sync_commands.start()
    logger.info(f'Logged in as {bot.user} with initial sync.')

bot.run(DISCORD_TOKEN)
