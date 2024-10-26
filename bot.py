import discord
from discord.ext import commands
import os

# Define tracked users with their IDs
tracked_users = {
    "Karm": 1153464189566865468,
    "Samir": 879401301526609972,
    "Allie": 765678235258060811
}

# Dictionary to store interaction data
interaction_data = {
    "Karm": {"Samir": 0, "Allie": 0},
    "Samir": {"Karm": 0, "Allie": 0},
    "Allie": {"Karm": 0, "Samir": 0}
}

# Set up bot with command prefix
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Calculate affinity score
def calculate_affinity_score(interaction_count):
    score = min(interaction_count * 2, 100)  # Cap score at 100%
    return score

# Get compatibility statement based on score
def get_affinity_statement(score):
    if score >= 80:
        return "This is a close relationship! They could definitely be a great match."
    elif score >= 50:
        return "They share a strong bond. These two seem to enjoy each other’s company."
    elif score >= 20:
        return "They have a decent connection but might need more time together."
    else:
        return "These two might need to interact more to know each other better."

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')
    
    # Fetch recent messages in the specified channel
    channel = bot.get_channel(1292553891581268010)  # Use your channel ID here
    async for message in channel.history(limit=100):  # Check the last 100 messages
        for name, user_id in tracked_users.items():
            if str(user_id) in message.content or name in message.content:
                for other_name in tracked_users.keys():
                    if other_name != name and (str(tracked_users[other_name]) in message.content or other_name in message.content):
                        interaction_data[name][other_name] += 1
    print("Historical message analysis complete.")

@bot.event
async def on_message(message):
    # Ignore messages sent by the bot itself
    if message.author == bot.user:
        return

    # Track mentions of each tracked user in messages
    for name, user_id in tracked_users.items():
        if str(user_id) in message.content or name in message.content:
            for other_name in tracked_users.keys():
                if other_name != name and (str(tracked_users[other_name]) in message.content or other_name in message.content):
                    interaction_data[name][other_name] += 1

    await bot.process_commands(message)

@bot.command()
async def check_affinity(ctx, user1: str, user2: str):
    # Custom responses for specific pairs
    if (user1 == "Karm" and user2 == "Samir") or (user1 == "Samir" and user2 == "Karm"):
        score = 85
        statement = "These two talk like lovers and seem destined to be together!"
    elif (user1 == "Allie" and user2 == "Samir") or (user1 == "Samir" and user2 == "Allie"):
        score = 77
        statement = "They truly love each other and share a deep connection!"
    # General case for other pairs
    elif user1 in tracked_users and user2 in tracked_users and user1 != user2:
        interaction_count = interaction_data[user1][user2]
        score = calculate_affinity_score(interaction_count)
        statement = get_affinity_statement(score)
    else:
        await ctx.send("Please provide valid tracked usernames (Karm, Samir, Allie) for comparison.")
        return

    # Send the response
    await ctx.send(f'Affinity Score between {user1} and {user2}: {score}%\n{statement}')

# Run the bot with your token (use Render environment variables for secure storage)
bot.run(os.getenv("DISCORD_TOKEN"))
