import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()



allowed_mentions = discord.AllowedMentions(users=True, roles=True)

TOKEN: str = os.getenv("BOT_TOKEN") #type: ignore


class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.guilds = True
        intents.messages = True
        intents.message_content = True

        super().__init__(
            command_prefix="!",
            intents=intents
        )

    async def setup_hook(self):
        print("🔧 setup_hook: loading extensions")

        await load_cogs(self)

        print("🔧 setup_hook: extensions loaded")

    async def on_ready(self):
        print(f"✅ Logged in as {self.user}")
        await self.tree.sync()


async def load_cogs(bot):
    await bot.load_extension("cogs.anni_party")
    #await bot.load_extension("cogs.random_gambling_messages")
    #await bot.load_extension("cogs.api_depending.api_queries")


def main():
    bot = Bot()
    bot.run(TOKEN)


if __name__ == '__main__':
    main()
