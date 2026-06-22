import datetime
import asyncio
import logging

import discord
from discord.ext import commands, tasks
from discord import ui
from discord import app_commands

import utils.database as db
import utils.general_classes as classes
import utils.discordutils as dc_utils
import utils.added_exceptions as excepts
from utils.added_exceptions import handle_loop_errors
from utils.bot import Bot





logger = logging.getLogger(name=__name__)

def init_database(database_path: str = ".\\persistent_data\\guild_api_database.db"):
    global meta, members_db, member_guild_raids_db # pylint: disable=global-variable-undefined

    p = database_path

    meta = db.MetaTable(p)

    members_db = db.UpdatingTable('members', p)
    
    member_guild_raids_db = db.UpdatingTable('member_guild_raids', p)



class GraidsCog(commands.Cog):
    def __init__(self, passed_bot):
        self.bot: Bot = passed_bot
        self.plot_semaphore = asyncio.Semaphore(3)


    async def cog_load(self) -> None:
        self.startup.start()


    @tasks.loop(count=1)
    @handle_loop_errors(logger=logger)
    async def startup(self):
        self.bot.loop.create_task(self.handle_graids_loop())

    async def handle_graids_loop(self):
        while True:
            try:
                data = await self.bot.state.graid_queue.get()
                await handle_graids(self.bot, data)
                self.bot.state.graid_queue.task_done()
            except Exception as e: #pylint: disable=broad-exception-caught
                excepts.handle_error(error=e, logger=logger)


    @app_commands.command(name="set_aspects_rewarded")
    async def reward_aspects(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AspectRewardModal())

    @app_commands.command(name="set_graid_channel")
    async def set_channel_for_graids(self, interaction: discord.Interaction, channel:discord.TextChannel):
        dc_utils.set_channel(channel=meta.ChannelUses.WYNNAPI_GRAIDS_TRACKING_SEND, discord_channel=channel, meta_db=meta)
        dc_utils.set_guild(guild=channel.guild, meta_db=meta)
        await interaction.response.send_message(content='channel set!', ephemeral=True)



async def handle_graids(bot: discord.Client, data):
    previous_members_db_res = members_db.fetchall()
    previous_members = {memberdata['uuid']: {key: value for key, value in memberdata.items() if key != 'uuid'} for memberdata in previous_members_db_res}
    completed_graids: dict[str, dict[str, int]] = {
        "notg": {},
        "nol": {},
        "tcc": {},
        "tna": {},
        "wtp": {},
    }
    for rank, rank_members in data['members'].items():
        if not rank in {"owner", "chief", "strategist", "captain", "recruiter", "recruit"}: # all guild ranks, will need updating in case of update
            continue
        for guild_member, member_data in rank_members.items():
            member = classes.APIMember(member=guild_member, memberdata=member_data, rank=rank, db=db)
            if previous_members.get(guild_member) is None and not member.total_guild_raids is None:
                member.update_member_guild_raids()
                continue
            if member.total_guild_raids is None:
                print(member.username)
                continue
            if previous_members[guild_member]['total_guild_raids'] < member.total_guild_raids:
                player_completed_raids = get_completed_graids(member=member)
                for raid, amount in player_completed_raids.items():
                    completed_graids[raid][member.uuid] = amount
                member.update_member_guild_raids()
    await send_discord_graids_completed_message(bot=bot, completed_graids=completed_graids)


def get_completed_graids(member: classes.APIMember) -> dict[str, int]:
    prev_graids_result = member_guild_raids_db.fetchone(primary_key_name='uuid', primary_key=member.uuid)
    if prev_graids_result is None:
        prev_graids_result = {raid: 0 for raid in ['notg', 'nol', 'tcc', 'tna', 'wtp']}
    prev_graids: list[int] = [prev_graids_result[raid] for raid in ['notg', 'nol', 'tcc', 'tna', 'wtp']]
    current_graids_result: list[int | None] = [member.notg_completions, member.nol_completions, member.tcc_completions, member.tna_completions, member.wtp_completions].copy()
    current_graids: list[int] = []
    for i, graid in enumerate(current_graids_result):
        if graid is None:
            current_graids.append(0)
        else:
            current_graids.append(graid)
    completed_graids = [current_graid - prev_graids[i] for i, current_graid in enumerate(current_graids)]

    new_aspects = sum(completed_graids)
    new_aspects += prev_graids_result["next_aspect"] + 2 * prev_graids_result['aspects']

    aspect_to_carry_over = new_aspects % 2 #Amount of raids to complete for next aspect reward

    aspects_to_reward = new_aspects // 2

    member_guild_raids_db.update(
        primary_key_name='uuid',
        primary_key=member.uuid,
        columns={
            'aspects': aspects_to_reward,
            'next_aspect': aspect_to_carry_over
        }
    )

    completed_graids_dict = {
        'notg': completed_graids[0],
        'nol': completed_graids[1],
        'tcc': completed_graids[2],
        'tna': completed_graids[3],
        'wtp': completed_graids[4]
    }

    to_pop = []
    for graid, amount in completed_graids_dict.items():
        if amount == 0:
            to_pop.append(graid)
    for raid in to_pop:
        completed_graids_dict.pop(raid)
    return completed_graids_dict


async def send_discord_graids_completed_message(
        bot: discord.Client,
        completed_graids: dict[str, dict[str, int]]):
    guild = dc_utils.get_guild(client=bot, meta_db=meta)
    channel = dc_utils.get_textchannel(channel=meta.ChannelUses.WYNNAPI_GRAIDS_TRACKING_SEND, guild=guild, meta_db=meta)

    embeds = []
    for raid, players in completed_graids.items():
        description = ""
        image = None
        colour = discord.Color.default()
        raid_name = raid
        if not len(players) > 0:
            continue
        for player, amount in players.items():
            player_description = "".join((f'{dc_utils.mention_user(user_uuid=player, guild=guild, members_db=members_db)}ㅤ{amount} | '))
            description = f'{description}\n{player_description}'
            match raid:
                case "notg":
                    image = "https://cdn.wynncraft.com/nextgen/raids/Nest%20of%20the%20Grootslangs.webp"
                    colour = discord.Color.dark_green()
                    raid_name = "Nest of the Grootslangs"
                case "nol":
                    image = "https://cdn.wynncraft.com/nextgen/raids/Orphion's%20Nexus%20of%20Light.webp"
                    colour = discord.Color.yellow()
                    raid_name = "Orphion's Nexus of Light"
                case "tcc":
                    image = "https://cdn.wynncraft.com/nextgen/raids/The%20Canyon%20Colossus.webp"
                    colour = discord.Color.blue()
                    raid_name = "The Canyon Colossus"
                case "tna":
                    image = "https://cdn.wynncraft.com/nextgen/raids/The%20Nameless%20Anomaly.webp"
                    colour = discord.Color.dark_purple()
                    raid_name = "The Nameless Anomaly"
                case "wtp":
                    image = "https://cdn.wynncraft.com/nextgen/raids/The%20Wartorn%20Palace.webp"
                    colour = discord.Color.brand_red()
                    raid_name = "The Wartorn Palace"
        embed = discord.Embed(title=raid_name, description=description, colour=colour, timestamp=datetime.datetime.now())
        embed.set_thumbnail(url=image)
        embeds.append(embed)

    aspect_embed = discord.Embed(title="Aspects", colour=discord.Color.magenta(), timestamp=datetime.datetime.now())
    aspect_reward_string = ""
    half_aspects_string = ""
    guild_raids_from_db = member_guild_raids_db.fetchall()
    for data in guild_raids_from_db:
        if data['aspects'] is None:
            member_guild_raids_db.update(primary_key_name='uuid', primary_key=data['uuid'], columns={'aspects': 0, 'next_aspect': 0})
            continue
        if data["aspects"] > 0:
            aspect_reward_string = f'{aspect_reward_string}\n{dc_utils.mention_user(user_uuid=data['uuid'], guild=guild, members_db=members_db)} | {data["aspects"]}'
        if data["next_aspect"] > 0:
            half_aspects_string = f'{half_aspects_string}\n{dc_utils.mention_user(user_uuid=data['uuid'], guild=guild, members_db=members_db)}'

    aspect_embed.add_field(name="aspects to reward", value=aspect_reward_string)
    aspect_embed.add_field(name="needs to complete another raid\nto get an aspect", value=half_aspects_string)

    if len(embeds) > 0:
        embeds.append(aspect_embed)
        if isinstance(channel, (discord.ForumChannel, discord.CategoryChannel)):
            return
        await channel.send(embeds=embeds)



class AspectRewardModal(discord.ui.Modal, title="Aspects rewarded in-game"):
    def __init__(self):
        super().__init__()
        db_result = {memberdata['uuid']: {key: value for key, value in memberdata.items() if key != 'uuid'} for memberdata in member_guild_raids_db.fetchall()}
        self.aspects_by_player: dict[str, int] = {member: data["aspects"] for member, data in db_result.items() if data["aspects"] > 0}
        self.create_modal_items()

    def create_modal_items(self):
        options = []
        for player, amount in self.aspects_by_player.items():
            to_add = discord.CheckboxGroupOption(label=f"{amount} aspects rewarded to {dc_utils.get_player_username(player_uuid=player, members_db=members_db)}", value=player)
            options.append(to_add)
            if len(options) >= 10:
                add_option_group = ui.Label(text="ㅤ", component=ui.CheckboxGroup(options=options, max_values=len(options), min_values=0, required=False))
                self.add_item(add_option_group)
                options = options[10:]
        if len(options) > 0:
            add_option_group = ui.Label(text="ㅤ", component=ui.CheckboxGroup(options=options, max_values=len(options), min_values=0, required=False))
            self.add_item(add_option_group)
        if self.total_children_count == 0:
            empty_text = ui.TextDisplay(content="All aspects have been rewarded!")
            self.add_item(empty_text)


    async def on_submit(self, interaction: discord.Interaction) -> None: #pylint: disable=arguments-differ
        reset_players = []
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("please send this from a guild", ephemeral=True)
            return
        for item in self.walk_children():
            if isinstance(item, ui.CheckboxGroup):
                for player in item.values:
                    member_guild_raids_db.update('uuid', player, columns={'aspects': 0})
                    reset_players.append(player)
        if len(reset_players) > 0:
            message = f"reset aspects for {', '.join(map(str,(dc_utils.mention_user(user_uuid=player, guild=guild, members_db=members_db) for player in reset_players)))}"
            await interaction.response.send_message(message, ephemeral=True)
        else:
            message = "ㅤ"
            await interaction.response.send_message(message, ephemeral=True, delete_after=0)



def main(global_bot):
    global graids_cog # pylint: disable=global-variable-undefined
    init_database()
    graids_cog = GraidsCog(passed_bot=global_bot)



async def setup(global_bot):
    main(global_bot=global_bot)
    await global_bot.add_cog(graids_cog)
