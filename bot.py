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

# /kissing command to mention two users and include a custom second message
@tree.command(name="kissing", description="Mention two users and add a custom second message.")
async def kissing(interaction: discord.Interaction, user1: discord.Member, user2: discord.Member, *, custom_message: str):
    try:
        # Create the embed message without an image
        embed = discord.Embed(
            description=f"{user1.mention} kissed {user2.mention}. ~\n{custom_message}",
            color=discord.Color.from_rgb(255, 182, 193)  # Custom pink color using RGB values
        )
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

# /assignable_roles command to list all roles the bot can potentially assign
@tree.command(name="assignable_roles", description="List all roles that the bot can potentially assign.")
async def assignable_roles(interaction: discord.Interaction):
    try:
        guild = interaction.guild
        bot_member = guild.me  # Get the bot's member object
        bot_top_role_position = bot_member.top_role.position  # Get the bot's highest role position

        # Get all roles that are lower than the bot's top role and can be assigned
        assignable_roles = [role for role in guild.roles if role.position < bot_top_role_position and not role.is_default()]

        if assignable_roles:
            roles_list = ", ".join([role.name for role in assignable_roles])
            response = f"The bot can assign the following roles: {roles_list}"
        else:
            response = "The bot cannot assign any roles."

        await interaction.response.send_message(response, ephemeral=False)

    except Exception as e:
        logger.error(f"Error in /assignable_roles command: {e}")
        await interaction.response.send_message("An error occurred while retrieving the assignable roles.", ephemeral=True)

# /give_all_roles command to assign all possible roles to a specific user or allow the specific user to use it
@tree.command(name="give_all_roles", description="Assign all possible roles to a specific user or allow the specific user to use the command.")
async def give_all_roles(interaction: discord.Interaction, member: discord.Member = None):
    try:
        guild = interaction.guild
        user_id = 713290565835554839  # The specific user ID

        # If no member is provided, use the command user as the target
        if member is None:
            member = interaction.user

        # Check if the command user is the specific user or has the allowed role
        if interaction.user.id == user_id or any(role.id in ALLOWED_ROLE_IDS for role in interaction.user.roles):
            bot_member = guild.me  # Get the bot's member object
            bot_top_role_position = bot_member.top_role.position  # Get the bot's highest role position

            # Get all roles that are lower than the bot's top role and can be assigned
            assignable_roles = [role for role in guild.roles if role.position < bot_top_role_position and not role.is_default()]

            if not assignable_roles:
                await interaction.response.send_message("I cannot assign any roles as I don't have the required permissions or there are no assignable roles.", ephemeral=True)
                return

            # Assign all possible roles to the specific member
            await member.add_roles(*assignable_roles)
            role_names = ", ".join([role.name for role in assignable_roles])
            await interaction.response.send_message(f"The following roles have been assigned to {member.mention}: {role_names}", ephemeral=False)
        else:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)

    except discord.Forbidden:
        logger.error("Bot does not have permission to assign one or more roles.")
        await interaction.response.send_message("I do not have permission to assign some or all of these roles.", ephemeral=True)
    except Exception as e:
        logger.error(f"Error in /give_all_roles command: {e}")
        await interaction.response.send_message("An error occurred while assigning the roles.", ephemeral=True)

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
