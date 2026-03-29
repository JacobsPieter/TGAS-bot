"""
Wynncraft Guild Discord Bot

A Discord bot for tracking and managing Wynncraft guild statistics, including
member contributions, raid completions, and guild progression. The bot provides
real-time tracking of guild data from the Wynncraft API and presents it in
various formats for Discord channels.

Features:
- Real-time guild data tracking from Wynncraft API
- Member contribution monitoring
- Guild raid completion tracking
- Markdown-formatted raid statistics display
- Automated reporting and notifications

Author: Pieter Jacobs
"""

import os


import discord
from discord import app_commands
from discord.ext import tasks
import requests
from dotenv import load_dotenv


import database
import markdown_card



FONT_URL = "https://fonts.gstatic.com/s/opensans/v14/" \
            "cJZKeOuBrn4kERxqtaUH3SZ2oysoEQEeKwjgmXLRnTc.ttf"
FONT_PATH = "OpenSans-Regular.ttf"



WYNN_GUILD_API_QUERY_INTERVAL = 2  # minutes
WYNN_XP_RETURN_INTERVAL = 60  # minutes


GUILD_LOOP_STARTED = False

guild_members: dict = {}
guild_data: dict = {}



def get_wynn_data(guild_prefix='TGAS') -> dict:
    """
    Fetch guild data from the Wynncraft API.
    
    Retrieves comprehensive guild information including member lists, contributions,
    and raid statistics for the specified guild prefix.
    
    Args:
        guild_prefix (str, optional): The guild prefix to fetch data for. Defaults to 'TGAS'.
        
    Returns:
        dict: The complete guild data from the Wynncraft API
        
    Raises:
        requests.RequestException: If the API request fails
    """
    url = f"https://api.wynncraft.com/v3/guild/prefix/{guild_prefix}?identifier=username"
    get_guild_data: dict = requests.get(url, timeout=30).json()
    return get_guild_data





def get_member_stats(entered_guild_data: dict) -> dict:
    """
    Extract and flatten member statistics from guild data.
    
    Processes the nested guild data structure to create a flat dictionary
    of members with their associated statistics.
    
    Args:
        entered_guild_data (dict): The raw guild data from the Wynncraft API
        
    Returns:
        dict: A flat dictionary mapping member names to their statistics
    """
    members = {}
    for rank in entered_guild_data['members']:
        if isinstance(entered_guild_data['members'][rank], int):
            continue
        for member in entered_guild_data['members'][rank]:
            members[member] = entered_guild_data['members'][rank][member]
    return members


def get_player_guild_raids(player: str, member_stats) -> dict[str, int]:
    """
    Extract flattened guild raid statistics for a specific player.
    
    Processes the nested raid statistics structure to create a flat dictionary
    of raid names and their completion counts for the specified player.
    
    Args:
        player (str): The player's username
        member_stats (dict): The complete member statistics dictionary
        
    Returns:
        dict[str, int]: A flat dictionary mapping raid names to completion counts
    """
    stats = member_stats
    player_stats = stats[player]['guildRaids'].items()
    flat_player_stats = {}
    for stat, item in player_stats:
        if isinstance(item, dict):
            for child_stat, child_item in item.items():
                flat_player_stats[child_stat] = child_item
        else:
            flat_player_stats[stat] = item
    return flat_player_stats


def get_guild_raids_per_player(member_stats) -> dict[str, dict[str, int]]:
    """
    Get raid completion statistics for all guild members.
    
    Processes member statistics to extract raid completion data for every member
    in the guild.
    
    Args:
        member_stats (dict): The complete member statistics dictionary
        
    Returns:
        dict[str, dict[str, int]]: Nested dictionary mapping member names to their raid statistics
    """
    guild_raids_per_player = {}
    for member, _ in member_stats.items():
        guild_raids_per_player[member] = get_player_guild_raids(member, member_stats)
    return guild_raids_per_player


def get_latest_graid_completions(uuid) -> dict[str, int]:
    """
    Get the most recent raid completion counts for a member from the database.
    
    Queries the database to retrieve the latest recorded completion counts for
    all possible guild raids for the specified member.
    
    Args:
        uuid (str): The member's unique identifier
        
    Returns:
        dict[str, int]: Dictionary mapping raid names to their latest completion counts
    """
    possible_raids = ['total', 'Nest of the Grootslangs', "Orphion's Nexus of Light",
                      'The Canyon Colossus', 'The Nameless Anomaly']
    completions: dict = {'total': 0,
                         'Nest of the Grootslangs': 0,
                         "Orphion's Nexus of Light": 0,
                         'The Canyon Colossus': 0,
                         'The Nameless Anomaly': 0}
    for raid in possible_raids:
        completions[raid] = db.get_latest_raid_completions(uuid=uuid, raid_name=raid)
    return completions









class Info(discord.Client):
    """
    Discord bot client for Wynncraft guild management.
    
    Extends discord.Client to provide guild tracking functionality including
    member statistics, raid completions, and contribution monitoring.
    """
    def __init__(self):
        """
        Initialize the Discord bot client with default intents and command tree.
        """
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        """
        Set up the bot by syncing slash commands with Discord.
        """
        await self.tree.sync()




load_dotenv()
BOT_TOKEN: str = os.getenv("BOT_TOKEN") #type: ignore

db = database.Database()


client = Info()



@tasks.loop(minutes=WYNN_GUILD_API_QUERY_INTERVAL)
async def guild_api_query(guild_prefix):
    """
    Periodically query the Wynncraft API for guild data and update the database.
    
    This task runs every 2 minutes to fetch the latest guild information and
    synchronize it with the local database. On the first run, it populates the
    database with all existing member data.
    
    Args:
        guild_prefix (str): The guild prefix to query data for
    """
    global guild_data, guild_members # pylint: disable=global-statement
    guild_data = get_wynn_data(guild_prefix)
    guild_members = get_member_stats(guild_data)







@tasks.loop(minutes=WYNN_GUILD_API_QUERY_INTERVAL)
async def check_graid_completions(channel_id: int):
    """
    Monitor and report new guild raid completions to a Discord channel.
    
    Compares current raid completion counts with previously recorded values
    and reports any new completions in a formatted Discord embed message.
    
    Args:
        channel_id (int): The Discord channel ID where completion reports should be sent
    """
    error_messages: str = ''

    new_completions: dict[str, dict[str, int]] = {
        'total': {},
        'Nest of the Grootslangs': {},
        "Orphion's Nexus of Light": {},
        'The Canyon Colossus': {},
        'The Nameless Anomaly': {}
    }
    for player, data in guild_members.items():
        prev_completions = get_latest_graid_completions(data['uuid'])
        completions = get_player_guild_raids(player, guild_members)
        for raid, recent_completions in completions.items():
            if recent_completions > prev_completions[raid]:
                new_completions[raid][player] = recent_completions - prev_completions[raid]
                db.update_raid_stat(data['uuid'], raid, recent_completions)
    for raid, raid_data in new_completions.items():
        completion_sum = 0
        for player, amount in raid_data.items():
            completion_sum += amount


    embed = discord.Embed(title='guild raid completions',
                          description='completed guild raids last minutes',
                          color=discord.Color.green())

    for raid, completion_data in new_completions.items():
        raid_completions_string = ''
        for player, times in completion_data.items():
            raid_completions_string = ''.join((raid_completions_string,
                                               f'\n{player} completed {raid} {times} times'))
        if not raid_completions_string == '':
            embed.add_field(name=raid, value=raid_completions_string, inline=False)

    channel: discord.TextChannel = client.get_channel(channel_id) # type: ignore
    if not len(embed.fields) == 0:
        await channel.send(
            content=error_messages,
            embed=embed)









@tasks.loop(minutes=WYNN_XP_RETURN_INTERVAL)
async def xp_contributions(timespan, channel_id):
    """
    Monitor and report member XP contributions to a Discord channel.
    
    Tracks changes in member contribution values and reports new contributions
    in a formatted Discord embed message every hour.
    
    Args:
        timespan (int): The time interval in minutes for the contribution report
        channel_id (int): The Discord channel ID where contribution reports should be sent
    """
    contributed_deltas = {}
    for player, data in guild_members.items():
        contributed_delta = data['contributed'] - db.get_latest_contribution(data['uuid'])
        if contributed_delta <= 0:
            continue
        contributed_deltas[player] = contributed_delta
        db.update_member_contribution(uuid=data['uuid'], username=player,
                                      new_contribution=guild_members[player]['contributed'])


    contributed_return_string = ''
    for player, amount in contributed_deltas.items():
        contributed_return_string = ''.join((contributed_return_string, f'{player}: {amount}\n'))

    if not len(contributed_return_string) == 0:
        embed = discord.Embed(title=f'Xp contributed in the last {timespan} minutes per player')
        embed.add_field(name='list', value=contributed_return_string[:1024])
        channel: discord.TextChannel = client.get_channel(channel_id) # type: ignore
        await channel.send(embed=embed)



@client.tree.command(name='track_api_changes')
async def api_looping(interaction: discord.Interaction):
    """
    Start tracking API changes for the guild.
    
    Begins periodic monitoring of the Wynncraft API to track guild data changes.
    This command must be run in the channel where you want tracking updates.
    
    Args:
        interaction (discord.Interaction): The Discord interaction that triggered this command
    """
    await interaction.response.defer()
    guild_prefix = 'TGAS'
    target_channel_id = interaction.channel_id
    if target_channel_id is None:
        return


    await interaction.followup.send('*started tracking*')
    await guild_api_query.start(guild_prefix)



@client.tree.command(name="start_tracking_guild_raids",
                     description="starts tracking guild raid completions")
async def track_guild_raids(interaction: discord.Interaction):
    """
    Start tracking guild raid completions in the current channel.
    
    Begins monitoring and reporting new guild raid completions to the channel
    where this command is executed.
    
    Args:
        interaction (discord.Interaction): The Discord interaction that triggered this command
    """
    await interaction.response.defer()
    target_channel_id = interaction.channel_id
    if target_channel_id is None:
        return


    await interaction.followup.send('*started tracking*')
    await check_graid_completions.start(target_channel_id)

@client.tree.command(name="start_tracking_xp", description="starts tracking xp contributions")
async def track_xp_contributions(interaction: discord.Interaction):
    """
    Start tracking member XP contributions in the current channel.
    
    Begins monitoring and reporting new member contribution changes to the channel
    where this command is executed. Reports are sent every hour.
    
    Args:
        interaction (discord.Interaction): The Discord interaction that triggered this command
    """
    await interaction.response.defer()
    target_channel_id = interaction.channel_id
    if target_channel_id is None:
        return
    for player, data in guild_members.items():
        db.update_member_contribution(uuid=data['uuid'], username=player,
                                        new_contribution=data['contributed'])
        for raid, amount in get_player_guild_raids(player, guild_members).items():
            if not raid == 'total':
                db.update_raid_stat(uuid=data['uuid'], raid_name=raid, completions=amount)


    await interaction.followup.send('*started tracking*')
    await xp_contributions.start(WYNN_XP_RETURN_INTERVAL, target_channel_id)





@client.tree.command(name="guild_raids",
                     description="returns a list of all completed guild raids by each member")
async def raids(interaction: discord.Interaction):
    """
    Generate and display a comprehensive guild raid completion report.
    
    Creates a formatted image showing raid completion statistics for all guild members,
    including total completions and breakdowns by individual raid type.
    
    Args:
        interaction (discord.Interaction): The Discord interaction that triggered this command
    """
    raid_data = {}
    await interaction.response.defer()
    for player, data in guild_members.items():
        raid_data[player] = get_latest_graid_completions(data['uuid'])

    complete_text = ''
    for player, stats in raid_data.items():
        text_template = f"""# {player}

        Total: {stats['total']}
        - NOTG: {stats['Nest of the Grootslangs']}
        - NOL: {stats["Orphion's Nexus of Light"]}
        - TCC: {stats['The Canyon Colossus']}
        - TNA: {stats['The Nameless Anomaly']}
        ==
        \\"""
        complete_text += text_template
    markdown_card.render_markdown_card(complete_text, 'data.png')
    with open('data.png', "rb") as f:
        data = discord.File(f)
    await interaction.followup.send(file=data)






client.run(BOT_TOKEN)
