import discord
from discord import app_commands

import requests
import os

import database
import markdown_card

from dotenv import load_dotenv

FONT_URL = "https://fonts.gstatic.com/s/opensans/v14/cJZKeOuBrn4kERxqtaUH3SZ2oysoEQEeKwjgmXLRnTc.ttf"
FONT_PATH = "OpenSans-Regular.ttf"

from discord.ext import tasks

WYNN_GUILD_API_QUERY_INTERVAL = 2 #minutes
WYNN_XP_RETURN_INTERVAL = 60 #minutes


guild_loop_started = False

guild_members: dict
guild_data: dict



def get_wynn_data(guild_prefix='TGAS') -> dict:
    url = f"https://api.wynncraft.com/v3/guild/prefix/{guild_prefix}?identifier=username"
    guild_data: dict = requests.get(url, timeout=30).json()
    return guild_data





def get_member_stats(guild_data: dict) -> dict:
    members = {}
    for rank in guild_data['members']:
        if isinstance(guild_data['members'][rank], int):
            continue
        for member in guild_data['members'][rank]:
            members[member] = guild_data['members'][rank][member]
    return members
    

def get_player_guild_raids(player: str, member_stats) -> dict[str, int]:
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
    guild_raids_per_player = {}
    for member, _ in member_stats.items():
        guild_raids_per_player[member] = get_player_guild_raids(member, member_stats)
    return guild_raids_per_player





class Info(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()




load_dotenv()
BOT_TOKEN: str = os.getenv("BOT_TOKEN") #type: ignore

db = database.Database()


client = Info()



@tasks.loop(minutes=WYNN_GUILD_API_QUERY_INTERVAL)
async def guild_api_query(guild_prefix):
    global prev_guild_data, prev_guild_members, guild_data, guild_members, guild_loop_started
    if not guild_loop_started:
        prev_guild_data = {}
        prev_guild_members = {}

    else:
        prev_guild_data = guild_data
        prev_guild_members = guild_members
    guild_data = get_wynn_data(guild_prefix)
    guild_members = get_member_stats(guild_data)
    if not guild_loop_started:
        for player, data in guild_members.items():
            db.update_member_contribution(uuid=data['uuid'], username=player, new_contribution=data['contributed'])
            for raid, amount in get_player_guild_raids(player, guild_members).items():
                if not raid == 'total':
                    db.update_raid_stat(uuid=data['uuid'], raid_name=raid, completions=amount)
        guild_loop_started = True






@tasks.loop(minutes=WYNN_GUILD_API_QUERY_INTERVAL)
async def check_graid_completions(channel_id: int):
    error_messages: str = ''

    new_completions: dict[str, dict[str, int]] = {
        'Nest of the Grootslangs': {},
        "Orphion's Nexus of Light": {},
        'The Canyon Colossus': {},
        'The Nameless Anomaly': {}
    }
    for player in prev_guild_members:
        prev_completions = get_player_guild_raids(player, prev_guild_members)
        completions = get_player_guild_raids(player, guild_members)
        total_completions = 0
        for raid in completions:
            #print(f'{player}: {raid}:\n    prev: {prev_completions[raid]}\n    present: {amount}\n    delta: {prev_completions[raid] - amount}')
            if completions[raid] - prev_completions[raid] != 0:
                new_completions[raid][player] = completions[raid] - prev_completions[raid]
                total_completions += completions[raid] - prev_completions[raid]
        if total_completions < 0 or total_completions > 10: #arbitrary number I hope would be high enough to not catch any false positives
            ''.join((error_messages, f'{player} completed a suspiciously high amount of guild raids ({total_completions}) the past {WYNN_GUILD_API_QUERY_INTERVAL} minutes\n'))
    
    for raid, raid_data in new_completions.items():
        completion_sum = 0
        for player, amount in raid_data.items():
            completion_sum += amount
        if not completion_sum % 4 == 0:
            ''.join((error_messages, f'An error occured in the completions of {raid}\nplease send a bug report\n'))

    
    embed = discord.Embed(title='guild raid completions', description='completed guild raids last minutes', color=discord.Color.green())
    
    for raid in new_completions:
        raid_completions_string = ''
        for player, times in new_completions[raid].items():
            raid_completions_string = ''.join((raid_completions_string, f'\n{player} completed {raid} {times} times'))
        if not raid_completions_string == '':
            embed.add_field(name=raid, value=raid_completions_string, inline=False)
    
    channel: discord.TextChannel = client.get_channel(channel_id) # type: ignore
    if not len(embed.fields) == 0:
        await channel.send(
            content=error_messages,
            embed=embed)








@tasks.loop(minutes=WYNN_XP_RETURN_INTERVAL)
async def xp_contributions(timespan, channel_id):
    contributed_deltas = {}
    for player, data in prev_guild_members.items():
        contributed_delta = guild_members[player]['contributed'] - data['contributed']
        if contributed_delta == 0:
            continue
        contributed_deltas[player] = contributed_delta
        db.update_member_contribution(uuid=data['uuid'], username=player, new_contribution=guild_members[player]['contributed'])

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
    await interaction.response.defer()
    guild_prefix = 'TGAS'
    target_channel_id = interaction.channel_id
    if target_channel_id == None:
        return


    await interaction.followup.send('*started tracking*')
    await guild_api_query.start(guild_prefix)



@client.tree.command(name="start_tracking_guild_raids", description="starts tracking guild raid completions")
async def track_guild_raids(interaction: discord.Interaction):
    await interaction.response.defer()
    guild_prefix = 'TGAS'
    target_channel_id = interaction.channel_id
    if target_channel_id == None:
        return


    await interaction.followup.send('*started tracking*')
    await check_graid_completions.start(target_channel_id)

@client.tree.command(name="start_tracking_xp", description="starts tracking xp contributions")
async def track_xp_contributions(interaction: discord.Interaction):
    await interaction.response.defer()
    guild_prefix = 'TGAS'
    target_channel_id = interaction.channel_id
    if target_channel_id == None:
        return


    await interaction.followup.send('*started tracking*')
    await xp_contributions.start(WYNN_XP_RETURN_INTERVAL, target_channel_id)





@client.tree.command(name="guild_raids", description="returns a list of all completed guild raids by each member")
async def raids(interaction: discord.Interaction):
    await interaction.response.defer()
    raid_data = get_guild_raids_per_player(get_member_stats(get_wynn_data()))
    
    complete_text = ''
    for player, stats in raid_data.items():
        text_template = f"# {player}\n\nTotal: {stats['total']}\n- NOTG: {stats['Nest of the Grootslangs']}\n- NOL: {stats["Orphion's Nexus of Light"]}\n- TCC: {stats['The Canyon Colossus']}\n- TNA: {stats['The Nameless Anomaly']}\n==\n\\"
        complete_text += text_template
    markdown_card.render_markdown_card(complete_text, 'data.png')
    with open('data.png', "rb") as f:
        data = discord.File(f)
    await interaction.followup.send(file=data)






client.run(BOT_TOKEN)