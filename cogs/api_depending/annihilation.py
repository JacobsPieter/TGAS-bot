import logging

import discord
from discord.ext import commands, tasks
from discord import app_commands

import utils.database as db
import utils.added_exceptions as excepts
from utils.added_exceptions import handle_loop_errors
import utils.discordutils as dc_utils
import utils.paths as paths

logger = logging.getLogger(name=__name__)


def init_database(database_path: str = paths.DATABASE):
    global meta # pylint: disable=global-variable-undefined

    p = database_path

    meta = db.MetaTable(p)

    anniparty_db = db.TrackingTable('annihilation_parties',p)
        # 'discord_id': str(),
        # 'anni_id': int(),
        # 'server_region': str(),
        # 'weapon': str(),
        # 'archetype': str(),
        # 'build_link': str(),
        # 'sure': bool(),
        # 'can_host': bool(),
        # 'current_host': bool(),
        # 'in_guild': bool(),
        # 'current_party_id': int()



class AnnihilationCog(commands.Cog):
    def __init__(self, bot):
        self.bot: discord.Client = bot

    async def cog_load(self):
        pass

    @tasks.loop(count=1)
    @handle_loop_errors(logger=logger)
    async def startup(self):
        self.bot.add_view(view=AnnihilationView())

    @app_commands.command(name='Start-Annihilation')
    async def start_annihilation(self, interaction: discord.Interaction):
        await interaction.response.defer()



class AnnihilationView(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)

        self.add_item(discord.ui.TextDisplay(content='# Annihilation is starting soon!'))
        self.add_item(
            discord.ui.TextDisplay(
                content=(
                    'Prepare to defend the province at the Corruption Portal near Detlas\n'
                    'Get your best build together and join up with our guild'
                    'to get rewards that will let you pile up your money higher than mount Wynn\n'
                )
            )
        )
        self.add_item(
            discord.ui.TextDisplay(
                content=(
                    '## Annihilation will begin <t:timestamp:R> (<t:timestamp:s>)\n'
                    'Press the Join! button below to reserve a spot in our party.'
                    '-# To get pinged next time get the <annihilation_role> at <role_channel>.'
                )
            )
        )


# async def setup(bot):
#     annihilation_cog = AnnihilationCog(bot=bot)
#     init_database()
#     await bot.add_cog(annihilation_cog)
