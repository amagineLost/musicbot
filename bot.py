import discord
from discord.ext import commands, tasks
import os
from collections import defaultdict

# Define the XP leaderboard and event channel
xp_leaderboard = defaultdict(int)
event_channel_id = 1292553891581268010
event_running = False

# Set up bot with command prefix
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Start XP event every 15 minutes
@tasks.loop(minutes=15)
async def start_xp_event():
    global event_running
    event_running = True
    channel = bot.get_channel(event_channel_id)
    await channel.send("🎉 **XP Event is happening!** 🎉 Chat in this channel to earn XP. Whoever is on top of the leaderboard when it ends will win a reward!")

    # End the XP event after 5 minutes
    await discord.utils.sleep_until(discord.utils.utcnow() + discord.timedelta(minutes=5))
    event_running = False

    # Announce the winner
    if xp_leaderboard:
        winner = max(xp_leaderboard, key=xp_leaderboard.get)
        winner_xp = xp_leaderboard[winner]
        await channel.send(f"🏆 **XP Event has ended!** 🏆\nCongratulations <@{winner}> with {winner_xp} XP! You win the reward!")

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

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')
    start_xp_event.start()  # Start the XP event loop

# Run the bot with your token (use Render environment variables for secure storage)
bot.run(os.getenv("DISCORD_TOKEN"))
