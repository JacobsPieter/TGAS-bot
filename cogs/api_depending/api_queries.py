import os
import math
from enum import Enum
import json
import datetime
import asyncio
from itertools import pairwise, dropwhile
import logging


from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure

import requests

import discord
from discord import app_commands
from discord.ext import tasks, commands


import utils.database as db
import utils.discordutils as dc_utils
import utils.added_exceptions as excepts
from utils.added_exceptions import handle_loop_errors
import utils.general_classes as classes
from utils.bot import Bot

logger = logging.getLogger(name=__name__)

class APIHandler:
    WYNN_API_BASE_URL = "https://api.wynncraft.com/v3/"

    WYNN_API_TOKEN: str = os.getenv("WYNN_API_TOKEN") #type: ignore

    class GuildIdentifier(Enum):
        PREFIX = 'prefix'
        GUILDNAME = 'name'

    class MemberIdentifier(Enum):
        UUID = 'uuid'
        USERNAME = 'username'



    def construct_guild_endpoint_url(self, identifier: GuildIdentifier = GuildIdentifier.PREFIX, guild: str = 'TGAS', memberidentifier: MemberIdentifier = MemberIdentifier.UUID) -> str:
        if identifier == self.GuildIdentifier.GUILDNAME:
            return f'{self.WYNN_API_BASE_URL}/guild/{guild}?identifier={memberidentifier.value}'
        return f'{self.WYNN_API_BASE_URL}guild/{identifier.value}/{guild}?identifier={memberidentifier.value}'

    async def get_endpoint(self, url: str):
        headers = {
        "Authorization": f"Bearer {self.WYNN_API_TOKEN}"
        }
        response = await asyncio.to_thread(requests.get, url, headers=headers, timeout=10)
        
        return response


    async def get_endpoint_data(self, url: str):
        response = await self.get_endpoint(url)

        if not response.ok:
            raise ConnectionError(f"API error {response.status_code}: {response.text[:200]}")

        if not response.text.strip():
            raise ValueError("Empty response from API")

        try:
            return response.json()
        except ValueError as exc:
            raise ValueError(f"Invalid JSON response: {response.text[:200]}") from exc


    async def dump_endpoint_data(self, url: str):

        with open("testing\\playerdata.json", 'w') as file: #pylint: disable=unspecified-encoding
            data = await self.get_endpoint(url)
            json.dump(data.json(), file)




def init_database(database_path: str = ".\\persistent_data\\guild_api_database.db"):
    global meta, members_db, playtime_tracking_db # pylint: disable=global-variable-undefined

    p = database_path

    meta = db.MetaTable(p)

    members_db = db.UpdatingTable('members', p)

    playtime_tracking_db = db.TrackingTable('playtime', p)





class APIQueries(commands.Cog):
    def __init__(self, passed_bot):
        self.bot: Bot = passed_bot
        self.plot_semaphore = asyncio.Semaphore(3)


    async def start_loop(self):
        self.fetch_guild_endpoint.start()
        print("Loop for querying the WynnAPI has been started.")

    async def cog_load(self) -> None:
        self.startup.start()


    @tasks.loop(count=1)
    @handle_loop_errors(logger=logger)
    async def startup(self):

        await self.bot.wait_until_ready()

        self.fetch_guild_endpoint.start()

        self.update_playtime_loop.start()

        guild = dc_utils.get_guild(self.bot, meta)

        if guild is None:
            guild_id = meta.get_guild_id()
            if guild_id is None:
                raise excepts.GuildNotConfiguredError()
            try:
                guild = await self.bot.fetch_guild(guild_id)
            except discord.NotFound as e:
                raise excepts.GuildNotFoundError(guild_id=guild_id) from e
        

        


    @tasks.loop(minutes=2)
    @handle_loop_errors(logger=logger)
    async def fetch_guild_endpoint(self):
        data = await api_handler.get_endpoint_data(api_handler.construct_guild_endpoint_url())
        
        await self.bot.state.graid_queue.put(data)


        for rank, rank_members in data['members'].items():
            if not rank in {"owner", "chief", "strategist", "captain", "recruiter", "recruit"}: # all guild ranks, will need updating in case of update
                continue
            for guild_member, member_data in rank_members.items():
                member = classes.APIMember(member=guild_member, memberdata=member_data, rank=rank, db=members_db)
                if member.total_guild_raids is None:
                    continue
                member.update_member_database()
    
    @fetch_guild_endpoint.before_loop
    async def fetch_guild_endpoint_before_loop(self):
        await self.bot.wait_until_ready()


    @app_commands.command(name='get_user_playtime_graph')
    async def get_user_playtime_graph(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer()
        async with self.plot_semaphore:
            member_to_get = member.display_name
            member_db_res = members_db.fetchall_conditional(f'username = \'{member_to_get}\'')
            if member_db_res is None:
                return await interaction.followup.send(content='Please ask this for someone in the guild or check your input. I don\'t have data for non-guild members')
            uuid = member_db_res[0]['uuid']
            playtime_history = playtime_tracking_db.fetchall_conditional(f'uuid = \'{uuid}\' ORDER BY timestamp DESC')
            hour_time = datetime.timedelta(hours=2).total_seconds()
            playtime_history.sort(key=lambda r: r['timestamp'])
            playtime_history_cleaned = [{'timestamp': snapshot['timestamp'], 'playtime': snapshot['playtime']} for snapshot in playtime_history]
            if not playtime_history_cleaned:
                return await interaction.followup.send("Not enough data yet.")

            playtime_history_filled_in: list[dict[str, float]] = []
            for point1, point2 in pairwise(playtime_history_cleaned):
                if point2['timestamp'] - point1['timestamp'] >= hour_time + 60: # Giving a little bit of wiggle room
                    for e in range(math.floor((point2['timestamp'] - point1['timestamp']) // hour_time)):
                        playtime_history_filled_in.append(
                            {
                                'timestamp': point1['timestamp'] + e*hour_time,
                                'playtime': point1['playtime']
                            }
                        )
                    continue
                playtime_history_filled_in.append(point1)
            playtime_history_filled_in.append(playtime_history_cleaned[-1])
            playtime_history_diffs = [{'timestamp': snapshot['timestamp'], 'playtime': snapshot['playtime'] - playtime_history_filled_in[i]['playtime']} for i, snapshot in enumerate(playtime_history_filled_in[1:], start=0)]

            
            hourly_playtime_history = [{'timestamp': datetime.datetime.fromtimestamp(snapshot['timestamp']), 'playtime': round(snapshot['playtime'], 1)} for snapshot in playtime_history_diffs]
            indexes = [snapshot['timestamp'] for snapshot in hourly_playtime_history]
            values = [snapshot['playtime'] for snapshot in hourly_playtime_history]

            path = f".\\temp_data\\player_activity_chart_{interaction.id}.png"
            await render_chart_async(indexes, values, width=1/(13), title="Twohourly Playtime", output_path=path)

            try:
                await interaction.followup.send(file=discord.File(path))
            except discord.NotFound:
                return
            finally:
                await asyncio.to_thread(os.remove, path)



    @tasks.loop(hours=2)
    @handle_loop_errors(logger=logger)
    async def update_playtime_loop(self):
        try:
            members = members_db.fetchall()
            for member in members:
                if member['playtime'] is None:
                    continue
                current_tracked_playtime = playtime_tracking_db.fetchlast_conditional(condition=f'uuid = \'{member["uuid"]}\'')
                if current_tracked_playtime is None:
                    playtime_tracking_db.updatecolumns(columns={'uuid': member['uuid'], 'playtime': member['playtime']})
                    continue
                if current_tracked_playtime['playtime'] == member['playtime']:
                    continue
                playtime_tracking_db.updatecolumns(columns={'uuid': member['uuid'], 'playtime': member['playtime']})
        except: # pylint: disable=bare-except
            return

    @update_playtime_loop.before_loop
    async def playtime_updating_loop_before_loop(self):
        await self.bot.wait_until_ready()



def generate_bar_chart(x, y, width, title: str):
    fig = Figure()
    FigureCanvas(fig)

    ax = fig.add_subplot(111)
    ax.bar(x, y, width=width)

    ax.set_title(title)
    ax.tick_params(axis='x', labelrotation=45)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    ax.text(
        0.99, 0.01,
        f"{timestamp}",
        transform=ax.transAxes,
        ha='right',
        va='bottom',
        fontsize=8,
        alpha=0.7
    )

    fig.tight_layout()

    return fig


async def render_chart_async(x, y, width, title: str, output_path):
    fig = await asyncio.to_thread(generate_bar_chart, x, y, width, title)

    # save in background thread (IMPORTANT: blocking operation)
    await asyncio.to_thread(fig.savefig, output_path, bbox_inches="tight", dpi=150)

    # explicit cleanup
    await asyncio.to_thread(fig.clf)
    del fig

    return output_path


def skip_until_threshold(data, key, threshold):
    if not data:
        return []

    limit = data[0][key] + threshold
    return list(dropwhile(lambda d: d[key] < limit, data))



def main(global_bot):
    global api_handler, api_queries # pylint: disable=global-variable-undefined
    api_handler = APIHandler()
    api_queries = APIQueries(passed_bot=global_bot)
    init_database()



async def setup(global_bot):
    main(global_bot=global_bot)
    await global_bot.add_cog(api_queries)



if __name__ == '__main__':
    print('Maybe be smart and make this do something')
