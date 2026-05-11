import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()


intents = discord.Intents.default()
intents.members = True
intents.message_content = True  # Required for message content processing

allowed_mentions = discord.AllowedMentions(users=True, roles=True)

TOKEN: str = os.getenv("BOT_TOKEN") #type: ignore

bot = commands.Bot(command_prefix="!", intents=intents)



async def load_cogs():
    await bot.load_extension("cogs.anni_party")
    await bot.load_extension("cogs.random_gambling_messages")
    await bot.load_extension("cogs.api_depending.api_queries")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.tree.sync()

async def main():
    await load_cogs()


if __name__ == '__main__':
    asyncio.run(main())
    bot.run(TOKEN)
