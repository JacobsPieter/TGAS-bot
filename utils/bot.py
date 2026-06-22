import logging

import discord
from discord.ext import commands

import utils.botstate as botstate


logger = logging.getLogger(name=__name__)

class Bot(commands.Bot):
    def __init__(self):
        logger.info(msg="Initialising base functionality")
        intents = discord.Intents.default()
        intents.members = True
        intents.guilds = True
        intents.messages = True
        intents.message_content = True

        self.state = botstate.Botstate()

        super().__init__(
            command_prefix="!",
            intents=intents
        )

    async def setup_hook(self):
        await self.load_cogs()

    async def on_ready(self):
        logger.info("Logged in as %s", self.user)
        print(f"✅ Logged in as {self.user}")
        await self.tree.sync()
        logger.info(msg="Command tree synchronised")


    async def load_cogs(self):
        logger.info(msg="Loading extentions...")

        extensions = [
        "cogs.anni_party",
        "cogs.random_gambling_messages",
        "cogs.api_depending.api_queries",
        "cogs.api_depending.tome_requesting",
        "cogs.api_depending.graid_tracking"
        ]

        for ext in extensions:
            logger.info("Loading %s...", ext)
            await self.load_extension(ext)
            logger.info("Finished loading %s", ext)

        logger.info(msg="Extentions loaded")