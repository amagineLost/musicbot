import os
import discord
import logging
import sqlite3
import asyncio
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

# Channel ID where logs of deleted and edited messages will be sent
log_channel_id = 1295049931840819280

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

# /send_message command
@tree.command(name="send_message", description="Send a message to a specific channel.")
@has_restricted_roles()
async def send_message(interaction: discord.Interaction, channel: discord.TextChannel, *, message: str):
    try:
        await channel.send(message)
        await interaction.response.send_message(f"Message sent to {channel.mention}", ephemeral=True)
    except Exception as e:
        logger.error(f"Error in /send_message command: {e}")
        await interaction.response.send_message("An error occurred while sending the message.", ephemeral=True)

# /allie command to explain why Allie and Cole Walters should be together
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

# /kissing command
@tree.command(name="kissing", description="Allie kisses Zeeke!")
async def kissing(interaction: discord.Interaction):
    try:
        # Fixed names for the kiss interaction
        sender = 'Allie'
        receiver = 'Zeeke'
        
        # Count of interactions (this should be dynamically managed with a database in a real setup)
        kiss_count = 33  # Example count, update logic as needed for real tracking
        
        # Create the embed message
        embed = discord.Embed(
            description=f"{sender} returned {receiver}'s kiss. ~\nkarm and {receiver} have kissed {kiss_count} times.",
            color=discord.Color.pink()
        )
        embed.set_image(url='https://cdn.nekotina.com/images/vuywvDR4.gif')  # Provided image link
        embed.set_footer(text='Anime: Kanojo, Okarishimasu')

        # Send the embed response
        await interaction.response.send_message(embed=embed)
    except discord.HTTPException as http_err:
        logger.error(f"HTTPException in /kissing command: {http_err}")
        await interaction.response.send_message("An error occurred while generating the message due to an HTTP error.", ephemeral=True)
    except discord.Forbidden as forbidden_err:
        logger.error(f"Forbidden error in /kissing command: {forbidden_err}")
        await interaction.response.send_message("An error occurred due to lack of permissions.", ephemeral=True)
    except Exception as e:
        logger.error(f"General error in /kissing command: {e}")
        await interaction.response.send_message("An error occurred while generating the message.", ephemeral=True)

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
                # Embed with deleted message details
                embed = discord.Embed(
                    title="Message Deleted",
                    description=f"{message.author.mention} deleted a message in {message.channel.mention}:\n\n'{message.content}'",
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

# Log when the bot is ready
@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}')
    await tree.sync()  # Ensure all application commands are synced

# Run the bot with error handling
try:
    bot.run(DISCORD_TOKEN)
except Exception as e:
    logger.error(f"Error starting the bot: {e}")
