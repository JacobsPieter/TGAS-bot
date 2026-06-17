import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import utils.added_exceptions as excepts

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
    EXTENSIONS = [
    "cogs.anni_party",
    "cogs.random_gambling_messages",
    "cogs.api_depending.api_queries"
    ]
    for ext in EXTENSIONS:
        await bot.load_extension(ext)


def main():
    global global_bot # pylint: disable=global-variable-undefined
    bot = Bot()
    global_bot = bot
    bot.run(TOKEN)



if __name__ == '__main__':
    main()

@global_bot.tree.error
async def error_handling(interaction: discord.Interaction, error):
    if not interaction.response.is_done():
        await interaction.response.send_message('An error occured', ephemeral=True)
    excepts.handle_error(error)

