import logging
import requests
import asyncio
import os
import datetime

import discord
from discord.ext import commands, tasks
from discord import app_commands

import utils.database as db
import utils.added_exceptions as excepts
from utils.added_exceptions import handle_loop_errors
import utils.discordutils as dc_utils
import utils.paths as paths

logger = logging.getLogger(name=__name__)


def init_database(database_path = paths.DATABASE):
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
        self.startup.start()

    @tasks.loop(count=1)
    @handle_loop_errors(logger=logger)
    async def startup(self):
        await self.bot.wait_until_ready()
        self.bot.add_view(view=AnnihilationView(0, dc_utils.get_guild(self.bot, meta)))
        print('here first!')
        self.fetch_we_api_loop.start()

    @app_commands.command(name='start-annihilation')
    async def start_annihilation(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.fetch_we_api()
        await interaction.followup.send('started')


    @tasks.loop(minutes=2)
    @handle_loop_errors(logger=logger)
    async def fetch_we_api_loop(self):
        print('here!')
        await self.fetch_we_api()

    
    async def fetch_we_api(self):

        url = "https://api.wynncraft.com/v3/map/world-events"

        response = await asyncio.to_thread(requests.get, url, timeout=10)

        if not response.ok:
            raise ConnectionError(f"API error {response.status_code}: {response.text[:200]}")

        if not response.text.strip():
            raise ValueError("Empty response from API")

        try:
            answer = response.json()
        except ValueError as exc:
            raise ValueError(f"Invalid JSON response: {response.text[:200]}") from exc

        await handle_api_result(answer, self.bot)



async def handle_api_result(res, bot):
    for we in res:
        if we['name'] == "Prelude to Annihilation":
            print('-'*52)
        print(f'{we['name']:<27} | {we['internalName']} | {int(datetime.datetime.fromisoformat(we['schedule']).timestamp()) if we['schedule'] is not None else None}')
        if we['internalName'] == "a63b2c02":
            print('-'*52)

    for we in res:
        if we["internalName"] == "468d25a5": # or we['internalName'] == "a63b2c02":
            if we['schedule'] is None:
                meta.set_other(meta.OtherKeys.ANNIHILATION_PARTIES_TRACKING_ACTIVE, '0')
                continue

            current_id_db_res = meta.get_other(meta.OtherKeys.ANNIHILATION_PARTIES_TRACKING_ID)
            if current_id_db_res is None:
                current_id = 0
            else:
                current_id = int(current_id_db_res)

            if meta.get_other(meta.OtherKeys.ANNIHILATION_PARTIES_TRACKING_ACTIVE) == "0":
                meta.set_other(meta.OtherKeys.ANNIHILATION_PARTIES_TRACKING_ACTIVE, '1')
                current_id += 1
                meta.set_other(meta.OtherKeys.ANNIHILATION_PARTIES_TRACKING_ID, f"{current_id}")
                await start_annihilation(we['schedule'], bot, we['name'])
                
            
async def start_annihilation(schedule_api: str, bot, name):
    guild = dc_utils.get_guild(bot, meta)
    schedule = int(datetime.datetime.fromisoformat(schedule_api).timestamp())
    channel = dc_utils.get_textchannel(meta.ChannelUses.ANNIHILATION_PARTIES_SIGNUP_LIVE, guild, meta)
    await channel.send(f'# {name}\n-#Testing with treetop cradle, can\'t be bothered to change the text')
    await channel.send(view=AnnihilationView(schedule, guild))


class AnnihilationView(discord.ui.LayoutView):
    def __init__(self, schedule, guild):
        super().__init__(timeout=None)

        self.add_item(discord.ui.TextDisplay(content='# Annihilation is starting soon!'))
        self.add_item(
            discord.ui.TextDisplay(
                content=(
                    'Prepare to defend the province at the Corruption Portal near Detlas\n'
                    'Get your best build together and join up with our guild'
                )
            )
        )
        self.add_item(
            discord.ui.TextDisplay(
                content=(
                    f'## Annihilation will begin <t:{schedule}:R> (<t:{schedule}:s>)\n'
                    'Press the Join! button below to reserve a spot in our party.\n'
                    f'-# To get pinged next time get the {dc_utils.mention_role(meta.RoleIds.SPECIFIC_ANNIHILATION_PING, guild, meta)} role at <role_channel>.'
                )
            )
        )




async def setup(bot):
    init_database()
    annihilation_cog = AnnihilationCog(bot=bot)
    await bot.add_cog(annihilation_cog)
