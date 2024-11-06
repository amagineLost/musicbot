import os
import discord
import logging
import asyncio
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

# Channel ID where logs of deleted and edited messages will be sent
log_channel_id = 1295049931840819280

# Enable all intents, including privileged ones
intents = discord.Intents.all()

# Create bot and command tree
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

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
@tasks.loop(minutes=10)  # Adjust the interval as needed
async def auto_sync_commands():
    try:
        synced = await tree.sync()
        logger.info(f'Auto-sync completed. {len(synced)} commands synced.')
    except Exception as e:
        logger.error(f"Error during periodic command sync: {e}")

# /ping command to check bot latency
@tree.command(name="ping", description="Check the bot's latency.")
async def ping(interaction: discord.Interaction):
    try:
        latency = bot.latency * 1000  # Convert latency to milliseconds
        await interaction.response.send_message(f"Pong! 🏓 Latency: {latency:.2f}ms", ephemeral=True)
    except Exception as e:
        logger.error(f"Error in /ping command: {e}")
        await interaction.response.send_message("An error occurred while checking latency.", ephemeral=True)

# /purge command to delete a specified number of messages
@tree.command(name="purge", description="Delete a specified number of recent messages.")
@has_restricted_roles()
async def purge(interaction: discord.Interaction, amount: int):
    if not interaction.channel.permissions_for(interaction.user).manage_messages:
        await interaction.response.send_message("You do not have permission to manage messages.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("Please specify a number greater than 0.", ephemeral=True)
        return

    try:
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.response.send_message(f"Deleted {len(deleted)} messages.", ephemeral=True)
    except discord.Forbidden:
        logger.error("Bot does not have permission to delete messages.")
        await interaction.response.send_message("I do not have permission to delete messages in this channel.", ephemeral=True)
    except discord.HTTPException as e:
        logger.error(f"HTTPException in /purge command: {e}")
        await interaction.response.send_message(f"An error occurred while deleting messages: {e}", ephemeral=True)
    except Exception as e:
        logger.error(f"General error in /purge command: {e}")
        await interaction.response.send_message(f"An unexpected error occurred: {e}", ephemeral=True)

# /send_message command to send a custom message to a specific channel
@tree.command(name="send_message", description="Send a message to a specific channel.")
@has_restricted_roles()
async def send_message(interaction: discord.Interaction, channel: discord.TextChannel, *, message: str):
    try:
        await channel.send(message)
        await interaction.response.send_message(f"Message sent to {channel.mention}", ephemeral=True)
        logger.info(f"Sent message to {channel.name} by {interaction.user.name}")
    except Exception as e:
        logger.error(f"Error in /send_message command: {e}")
        await interaction.response.send_message("An error occurred while sending the message.", ephemeral=True)

# /allie command with an explanation paragraph
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
        await interaction.response.send_message(paragraph, ephemeral=False)
    except Exception as e:
        logger.error(f"Error in /allie command: {e}")
        await interaction.response.send_message("An error occurred while generating the message.", ephemeral=True)

# /kissing command for mentioning two users and a custom message
@tree.command(name="kissing", description="Mention two users and add a custom second message.")
async def kissing(interaction: discord.Interaction, user1: discord.Member, user2: discord.Member, *, custom_message: str):
    try:
        embed = discord.Embed(
            description=f"{user1.mention} kissed {user2.mention}. ~\n{custom_message}",
            color=discord.Color.from_rgb(255, 182, 193)  # Custom pink color using RGB values
        )
        embed.set_footer(text='Anime: Kanojo, Okarishimasu')
        await interaction.response.send_message(embed=embed)
        logger.info(f"Kissing command used by {interaction.user.name} for {user1.name} and {user2.name}")
    except Exception as e:
        logger.error(f"Error in /kissing command: {e}")
        await interaction.response.send_message("An error occurred while generating the message.", ephemeral=True)

# Event handler for deleted messages
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
        except Exception as e:
            logger.error(f"Error sending deleted message log: {e}")

# Event handler for edited messages
@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content:
        return
    log_channel = bot.get_channel(log_channel_id)
    if log_channel:
        try:
            embed = discord.Embed(
                title="Message Edited",
                color=discord.Color.blue()
            )
            embed.add_field(name="Before", value=before.content, inline=False)
            embed.add_field(name="After", value=after.content, inline=False)
            embed.set_footer(text=f"Edited by {before.author.display_name} in #{before.channel}")
            await log_channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Error sending edited message log: {e}")

# Log when the bot is ready and start the periodic sync
@bot.event
async def on_ready():
    try:
        synced = await tree.sync()  # Ensure all application commands are synced
        logger.info(f'Initial sync completed. {len(synced)} commands synced.')
    except Exception as e:
        logger.error(f"Error during initial command sync: {e}")
    
    if not auto_sync_commands.is_running():
        auto_sync_commands.start()  # Start the loop for periodic command syncing
    logger.info(f'Logged in as {bot.user}')

# Run the bot with error handling
try:
    bot.run(DISCORD_TOKEN)
except Exception as e:
    logger.error(f"Error starting the bot: {e}")
