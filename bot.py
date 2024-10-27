import discord
from discord.ext import commands, tasks
import os
from collections import defaultdict

# Define the XP leaderboard, event channel, and image storage
xp_leaderboard = defaultdict(int)
event_channel_id = 1292553891581268010
event_running = False
image_storage = {}

# Set up bot with command prefix and intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Start XP event every 15 minutes silently
@tasks.loop(minutes=15)
async def start_xp_event():
    global event_running
    event_running = True
    print("XP event started.")

    # End the XP event after 5 minutes
    await discord.utils.sleep_until(discord.utils.utcnow() + discord.timedelta(minutes=5))
    event_running = False
    print("XP event ended.")

    # Reset XP leaderboard for the next event
    xp_leaderboard.clear()

# Update leaderboard on each message
@bot.event
async def on_message(message):
    global event_running

    # Ignore bot messages and messages outside the event channel
    if message.author == bot.user or message.channel.id != event_channel_id:
        return

    # Only count messages towards XP if an event is running
    if event_running:
        xp_leaderboard[message.author.id] += 1

    await bot.process_commands(message)

# Command to display the XP leaderboard
@bot.command()
async def leaderboard(ctx):
    if xp_leaderboard:
        leaderboard_message = "**XP Leaderboard:**\n"
        sorted_leaderboard = sorted(xp_leaderboard.items(), key=lambda item: item[1], reverse=True)
        for i, (user_id, xp) in enumerate(sorted_leaderboard, 1):
            user = await bot.fetch_user(user_id)
            leaderboard_message += f"{i}. {user.name} - {xp} XP\n"
        await ctx.send(leaderboard_message)
    else:
        await ctx.send("The leaderboard is currently empty.")

# Command to store a new image URL for a user
@bot.command()
async def store(ctx, username: str, image_url: str):
    # Store or update the image URL for the user
    image_storage[username] = image_url
    await ctx.send(f"Updated image for {username}.")

# Command to retrieve the stored image for a user
@bot.command()
async def proof(ctx, username: str):
    # Retrieve the image for the user
    image_url = image_storage.get(username)
    if image_url:
        await ctx.send(f"Image for {username}: {image_url}")
    else:
        await ctx.send(f"No image stored for {username}.")

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')
    start_xp_event.start()  # Start the XP event loop

# Run the bot with your token (use Render environment variables for secure storage)
bot.run(os.getenv("DISCORD_TOKEN"))
