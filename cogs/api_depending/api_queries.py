import os
from enum import Enum
import json
import datetime
import asyncio
from typing import Any

import requests
import discord
from discord import app_commands
from discord.ext import tasks, commands
from discord import ui

import cogs.api_depending.api_database as db


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
        response = await asyncio.to_thread(requests.get, url, headers=headers, timeout=30)
        
        return response


    async def get_endpoint_data(self, url: str):
        data = await self.get_endpoint(url)
        json_data = data.json()
        return json_data

    async def dump_endpoint_data(self, url: str):

        with open("testing\\playerdata.json", 'w') as file: #pylint: disable=unspecified-encoding
            data = await self.get_endpoint(url)
            json.dump(data.json(), file)




def init_database(database_path: str = ".\\persistent_data\\guild_api_database.db"):
    global meta, members_db, member_guild_raids_db, tome_requested_db # pylint: disable=global-variable-undefined

    p = database_path

    meta = db.UpdatingTable("meta", p)
    meta.create(('key', str()), {'value': str()})

    members_db = db.UpdatingTable('members', p)
    members_db.create(
        ('uuid', str()),
        {
            'username': str(),
            'guild_rank': str(),
            'last_seen': datetime.datetime.now(),
            'playtime': float(),
            'weekly': bool(),
            'weekly_streak': int(),
            'contributed': int(),
            'contribution_rank': int(),
            'joined_guild': datetime.datetime.now(),
            'left_guild': bool(),
            'total_guild_raids': int(),
            'wars': int()
        })
    
    member_guild_raids_db = db.UpdatingTable('member_guild_raids', p)
    member_guild_raids_db.create(
        ('uuid', str()),
        {
            'total': int(),
            'notg': int(),
            'nol': int(),
            'tcc': int(),
            'tna': int(),
            'wtp': int(),
            'aspects': int(),
            'next_aspect': int()
        }
        )
    
    tome_requested_db = db.TrackingTable('tome_requested', p)
    tome_requested_db.create(
        columns={
            'uuid': str(),
            }
        )




class APIMember:
    def __init__(self, member, memberdata, rank):
        self.uuid = member
        self.username = memberdata['username']
        self.guild_rank = rank

        if not memberdata['lastJoin'] is None:
            self.last_online = datetime.datetime.fromisoformat(memberdata['lastJoin'].replace("Z", "+00:00"))
        else:
            self.last_online = 0
        
        if not memberdata['restrictions']['main_access']:
            self.playtime = memberdata['globalData']['playtime']
            self.total_guild_raids = memberdata['globalData']['currentGuildRaids']['total']
            self.notg_completions = memberdata['globalData']['currentGuildRaids']['list']['Nest of the Grootslangs']
            self.nol_completions = memberdata['globalData']['currentGuildRaids']['list']["Orphion's Nexus of Light"]
            self.tcc_completions = memberdata['globalData']['currentGuildRaids']['list']['The Canyon Colossus']
            self.tna_completions = memberdata['globalData']['currentGuildRaids']['list']['The Nameless Anomaly']
            self.wtp_completions = memberdata['globalData']['currentGuildRaids']['list']['The Wartorn Palace']
            self.wars = memberdata['globalData'].get('wars', 0)
        else:
            self.playtime = None
            self.total_guild_raids = None
            self.notg_completions = None
            self.nol_completions = None
            self.tcc_completions = None
            self.tna_completions = None
            self.wtp_completions = None
            self.wars = None
        
        if not memberdata['restrictions']['guild_high_ranked_access']:
            self.weekly = memberdata['weekly']['completed']
            self.weekly_streak = memberdata['weekly']['streak']
        else:
            self.weekly = None
            self.weekly_streak = None
        
        self.contributed = memberdata['contributed']
        self.contribution_rank = memberdata['contributionRank']
        self.joined_guild = datetime.datetime.fromisoformat(memberdata['joined'].replace("Z", "+00:00"))
        self.left_guild = False

    def update_member_database(self):
        members_db.update(
            'uuid',
            self.uuid,
            columns={
                'username': self.username,
                'guild_rank': self.guild_rank,
                'last_seen': self.last_online,
                'playtime': self.playtime,
                'weekly': self.weekly,
                'weekly_streak': self.weekly_streak,
                'contributed': self.contributed,
                'contribution_rank': self.contribution_rank,
                'joined_guild': self.joined_guild,
                'left_guild': self.left_guild,
                'total_guild_raids': self.total_guild_raids,
                'wars': self.wars
            })

    def update_member_guild_raids(self):
        member_guild_raids_db.update(
            'uuid',
            self.uuid,
            columns={
                'total': self.total_guild_raids,
                'notg': self.notg_completions,
                'nol': self.nol_completions,
                'tcc': self.tcc_completions,
                'tna': self.tna_completions,
                'wtp': self.wtp_completions,
            })



def get_completed_graids(member: APIMember):
    prev_graids_result = member_guild_raids_db.fetchone('uuid', member.uuid)
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
        'uuid',
        member.uuid,
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

def mention_user(user_uuid: str, guild: discord.Guild) -> str:
    playerdata = members_db.fetchone('uuid', user_uuid)
    if not playerdata is None:
        username: str = playerdata['username']
        name = guild.get_member_named(username) if not guild is None else None
        playername = name.mention if not name is None else username
    else:
        username = user_uuid
        playername = user_uuid
    return playername


def get_player_username(player_uuid: str) -> str:
    playerdata = members_db.fetchone('uuid', player_uuid)
    if not playerdata is None:
        playername: str = playerdata['username']
    else:
        playername = player_uuid
    return playername


class APIQueries(commands.Cog):
    def __init__(self, passed_bot):
        self.bot: discord.Client = passed_bot


    async def start_loop(self):
        await self.fetch_guild_endpoint.start()
        print("Loop for querying the WynnAPI has been started.")

    async def cog_load(self) -> None:
        asyncio.create_task(api_queries.start_loop())

        self.bg_task.start()


    @tasks.loop(count=1)
    async def bg_task(self):

        guild_id = meta.fetchone('key', "guild_id")
        if guild_id is None:
            print("Please set guild first!")
            return

        guild_id = int(guild_id['value'])

        guild = self.bot.get_guild(guild_id)

        if guild is None:
            try:
                guild = await self.bot.fetch_guild(guild_id)
            except discord.NotFound:
                print("Guild not found / bot removed")
                return
        
        self.bot.add_view(RequestedTomesView(guild))

        await update_tome_live_message(guild)


    @app_commands.command(name="set_graid_channel")
    async def set_channel_for_graids(self, interaction: discord.Interaction, channel:discord.TextChannel, role: discord.Role):
        role_id = meta.fetchone('key', 'api_queries_role_id')
        if not role_id is None:
            if interaction.user.get_role(int(role_id['value'])) is None: # type: ignore pylint: disable=line-too-long
                return await interaction.response.send_message(
                    content="You don't have permission to use this command"
                    )
        meta.update('key', 'graid_message_channel', {'value': str(channel.id)})
        meta.update('key', 'guild_id', {'value': str(channel.guild.id)})
        meta.update('key', 'api_queries_role_id', {'value': str(role.id)})
        await interaction.response.send_message(content='channel and role set!', ephemeral=True)


    @tasks.loop(minutes=2)
    async def fetch_guild_endpoint(self):
        data = await api_handler.get_endpoint_data(api_handler.construct_guild_endpoint_url())

        #TODO: implement guild global data handling
        await handle_graids(self, data)

        for rank, rank_members in data['members'].items():
            if not rank in {"owner", "chief", "strategist", "captain", "recruiter", "recruit"}: # all guild ranks, will need updating in case of update
                continue
            for guild_member, member_data in rank_members.items():
                member = APIMember(guild_member, member_data, rank)
                if member.total_guild_raids is None:
                    continue
                member.update_member_database()

    @app_commands.command(name="set_aspects_rewarded")
    async def reward_aspects(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AspectRewardModal())

    @app_commands.command(name='setup_tomes', description='all times are in days')
    async def setup_tomes(self, interaction:discord.Interaction, cooldown: int, required_weekly_streak: int):
        meta.update('key', 'tome_required_weekly_streak', columns={'value': str(required_weekly_streak)})
        meta.update('key', 'tome_request_time_interval', columns={'value': str(cooldown)})
        await interaction.response.send_message(content='Config has been set.', ephemeral=True)

    @app_commands.command(name='send_tome_requests_message')
    async def send_tome_requests_message(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        if isinstance(channel, (discord.ForumChannel, discord.CategoryChannel)) or channel is None:
            return
        guild = interaction.guild
        if guild is None:
            return
        meta.update('key', 'guild_id', columns={'value': guild.id})
        meta.update('key', 'tome_requests_channel_id', columns={'value': channel.id})
        await update_tome_live_message(guild)


async def handle_graids(cog: APIQueries, data):
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
            member = APIMember(guild_member, member_data, rank)
            if previous_members.get(guild_member) is None and not member.total_guild_raids is None:
                member.update_member_guild_raids()
                continue
            if member.total_guild_raids is None:
                print(member.username)
                continue
            if previous_members[guild_member]['total_guild_raids'] < member.total_guild_raids:
                player_completed_raids = get_completed_graids(member)
                for raid, amount in player_completed_raids.items():
                    completed_graids[raid][member.uuid] = amount
                member.update_member_guild_raids()
    await send_discord_graids_completed_message(cog, completed_graids=completed_graids)



async def send_discord_graids_completed_message(cog: APIQueries, completed_graids: dict[str, dict[str, int]]):
    channel_id_res = meta.fetchone('key', 'graid_message_channel')
    if channel_id_res is None:
        print("Channel needs to be set! Use the command for setting up this module to set the channel.")
        return
    channel_id = channel_id_res['value']
    channel = cog.bot.get_channel(int(channel_id))
    if channel is None:
        await cog.bot.fetch_channel(int(channel_id))
        channel = cog.bot.get_channel(int(channel_id))
        if channel is None:
            return
    if not isinstance(channel, (discord.abc.GuildChannel)):
        return
    guild = channel.guild

    embeds = []
    for raid, players in completed_graids.items():
        description = ""
        image = None
        colour = discord.Color.default()
        raid_name = raid
        if not len(players) > 0:
            continue
        for player, amount in players.items():
            player_description = "".join((f'{mention_user(player, guild)}ㅤ{amount} | '))
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
            member_guild_raids_db.update('uuid', data['uuid'], columns={'aspects': 0, 'next_aspect': 0})
            continue
        if data["aspects"] > 0:
            aspect_reward_string = f'{aspect_reward_string}\n{mention_user(data['uuid'], guild)} | {data["aspects"]}'
        if data["next_aspect"] > 0:
            half_aspects_string = f'{half_aspects_string}\n{mention_user(data['uuid'], guild)}'

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
            to_add = discord.CheckboxGroupOption(label=f"{amount} aspects rewarded to {get_player_username(player)}", value=player)
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


    async def on_submit(self, interaction: discord.Interaction) -> None:
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
            message = f"reset aspects for {', '.join(map(str,(mention_user(player, guild) for player in reset_players)))}"
            await interaction.response.send_message(message, ephemeral=True)
        else:
            message = "ㅤ"
            await interaction.response.send_message(message, ephemeral=True, delete_after=0)
        

async def handle_tome_requests(interaction: discord.Interaction):
    #TODO: Make a command to set a tome as been rewarded
    if isinstance(interaction.user, discord.Member):
        username = interaction.user.nick
    else:
        print('here!')
        return
    membersdata = members_db.fetchall_conditional(f'username = \'{username}\'')
    if membersdata == []:
        await interaction.followup.send(content="You don't seem to be in the guild.\nIf you are, this is an error, please report\nIf you aren't in the guild, please ignore", ephemeral=True)
        return
    memberdata = membersdata[0]
    uuid = memberdata['uuid']
    try:
        tome_requested_db_result = tome_requested_db.fetchlast_conditional(f'uuid = \'{uuid}\'')
    except AttributeError as e:
        tome_requested_db_result = {'timestamp': 0}
        print(e)
    last_requested_timestamp = tome_requested_db_result['timestamp']
    last_requested = datetime.datetime.fromtimestamp(last_requested_timestamp)
    time_elapsed_needed = meta.fetchone('key','tome_request_time_interval')
    if time_elapsed_needed is None:
        await interaction.followup.send(content='Please ask a moderator to set the minimum interval needed to request a tome again', ephemeral=True)
        return
    if datetime.datetime.now() - last_requested < datetime.timedelta(days=int(time_elapsed_needed['value'])):
        await interaction.followup.send(content=f'Please wait {time_elapsed_needed['value']} days since your last request before requesting a tome again', ephemeral=True)
        return
    if not memberdata['weekly']:
        await interaction.followup.send(content='Please do your weekly before requesting a tome', ephemeral=True)
        return
    required_weekly_streak = meta.fetchone('key', 'tome_required_weekly_streak')
    if required_weekly_streak is None:
        await interaction.followup.send(content='Please ask a moderator to set the minimum weekly streak to request a tome', ephemeral=True)
        return
    if memberdata['weekly_streak'] < int(required_weekly_streak['value']):
        await interaction.followup.send(content=f'You need a weekly streak of at least {required_weekly_streak['value']} to request a tome', ephemeral=True)
        return
    tome_requested_db.updatecolumns(columns={'uuid': uuid})
    if interaction.guild is None:
        await interaction.followup.send(content='Please don\'t use this outside a server')
        return
    await interaction.followup.send(content="Your tome has been requested, it will be given to you shortly", ephemeral=True)
    await update_tome_live_message(interaction.guild)


def create_cooldown_string(guild: discord.Guild) -> str:
    try:
        requests = tome_requested_db.fetchall()
    except AttributeError as e:
        requests = []
        print(e)
    if requests == []:
        return 'No one currently on cooldown.'
    cooldown = meta.fetchone('key', 'tome_request_time_interval')
    if cooldown is None:
        return 'error while constructing cooldown list'
    on_cooldown_str = ''
    for memberdict in requests:
        if datetime.datetime.now() - datetime.datetime.fromtimestamp(memberdict['timestamp']) > datetime.timedelta(days=int(cooldown['value'])):
            continue
        timestamp_value = int(memberdict['timestamp']) + int(datetime.timedelta(days=int(cooldown['value'])).total_seconds())
        on_cooldown_str = '\n'.join((on_cooldown_str, f'{mention_user(memberdict['uuid'], guild)} ---------- <t:{timestamp_value}> | <t:{timestamp_value}:R>'))
    if on_cooldown_str == '':
        return 'No one currently on cooldown.'
    return f'Person ---------- Date for next possible request | relative time\n{on_cooldown_str}'


class RequestedTomesView(discord.ui.LayoutView):
    #TODO: Make persistent after restarts
    def __init__(self, guild):
        super().__init__(timeout=None)

        self.add_item(discord.ui.TextDisplay(content='# What are Guild Tomes?'))
        self.add_item(discord.ui.TextDisplay(
            content=(
                'A guild tome is a type of tome a guild can reward. '
                'Tomes are unlocked after doing the quest \'Realm of Light I\'. '
                'For a guild tome you also need to have at least level 100 to equip it. '
                'You can find the tome menu by going into the compass and then click on the book.\n'
                'Their bonusses are always skill points. There are 6 types of guild tome:\n'
                '- Brute\'s Tome of Allegiance - giving +4 strength;\n'
                '- Sadist\'s Tome of Allegiance - giving +4 dexterity;\n'
                '- Mastermind\'s Tome of Allegiance - giving +4 intelligence;\n'
                '- Arsonist\'s Tome of Allegiance - giving +4 defense;\n'
                '- Ghost\'s Tome of Allegiance - giving +4 agility and\n'
                '- Assimilator\'s Tome of Allegiance - giving +1 to every skill point.\n'
                )
            ))

        self.add_item(discord.ui.Separator(
            spacing = discord.SeparatorSpacing.large,
            visible = True,
            ))

        self.add_item(discord.ui.TextDisplay(content='# How can you get them?'))
        self.add_item(discord.ui.TextDisplay(
            content=(
                '## Weekly\n'
                '- You need to have done your weekly in the week you are requesting the tome and\n'
                '- You need to have a weekly streak of at least 2 weeks\n'
                '  - _Exception for new members: if you are new you only have to wait 7 '
                'days before requesting a tome. You still have to do your weekly._\n'
                '## Cooldown\n'
                'After you requested a tome you will be put on a 2 week cooldown before you can request a new one.\n'
                '-# These rules are needed because we only regenerate them at that speed.'
                'If we were to hand them out faster we would run out so we can\'t give everyone the '
                'tome they deserve.'
                )
            ))

        self.add_item(discord.ui.Separator(
            spacing = discord.SeparatorSpacing.large,
            visible = True,
            ))

        self.add_item(discord.ui.TextDisplay(content='# People currently on cooldown'))
        self.add_item(discord.ui.Container(
            discord.ui.TextDisplay(
                content=create_cooldown_string(guild)
                )
            ))
        self.add_item(discord.ui.Container(
            discord.ui.TextDisplay(
                content=(
                    '### People who have requested a tome but not yet received one\n'
                    '-# You will receive one as soon as possible\n'
                    '-# Your cooldown has already started\n'
                    'Jacobs0811'
                    )
                )
            ))
        
        class RequestButton(discord.ui.Button):
            async def callback(self, interaction: discord.Interaction) -> Any:
                await interaction.response.defer(ephemeral=True)
                await handle_tome_requests(interaction)

        self.add_item(discord.ui.ActionRow(RequestButton(label='Request a tome', style=discord.ButtonStyle.green)))



async def update_tome_live_message(guild: discord.Guild):
    """
    Updates the live party message with current party information.

    Args:
        guild (discord.Guild): The guild to update the message for
    """
    channel_meta_id = meta.fetchone('key',"tome_requests_channel_id")
    if channel_meta_id is None:
        print('Please set a channel!')
        return
    channel_id: int = int(channel_meta_id['value'])
    channel = guild.get_channel(channel_id)
    if channel is None:
        return
    if isinstance(channel, (discord.ForumChannel, discord.CategoryChannel)):
        return

    message_id = meta.fetchone('key', "live_tome_message_id")


    try:
        if message_id:
            message = await channel.fetch_message(int(message_id['value']))
            await message.edit(view=RequestedTomesView(guild))
        else:
            message = await channel.send(view=RequestedTomesView(guild))
            meta.update('key', 'live_tome_message_id', columns={"value": str(message.id)})
    except discord.NotFound:
        message = await channel.send(view=RequestedTomesView(guild))
        meta.update('key', 'live_tome_message_id', columns={"value": str(message.id)})



def main(global_bot):
    global api_handler, api_queries # pylint: disable=global-variable-undefined
    api_handler = APIHandler()
    api_queries = APIQueries(global_bot)
    init_database()

    



async def setup(global_bot):
    main(global_bot)
    await global_bot.add_cog(api_queries)

    

if __name__ == '__main__':
    print('Maybe be smart and make this do something')    
    #print(api_handler.get_endpoint_data("https://api.wynncraft.com/v3/player/Jacobs0811?fullResult"))
    #api_handler.dump_endpoint_data(api_handler.construct_guild_endpoint_url())
    #test = fetch_guild_endpoint()

