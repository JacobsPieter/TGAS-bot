import discord
from discord import app_commands

import json
import requests
import os
from PIL import Image, ImageDraw, ImageFont
import math
import datetime

from dotenv import load_dotenv

FONT_URL = "https://fonts.gstatic.com/s/opensans/v14/cJZKeOuBrn4kERxqtaUH3SZ2oysoEQEeKwjgmXLRnTc.ttf"
FONT_PATH = "OpenSans-Regular.ttf"

from discord.ext import tasks

WYNN_GUILD_QUERY_INTERVAL = 2 #minutes
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


client = Info()




@tasks.loop(minutes=WYNN_GUILD_QUERY_INTERVAL)
async def looping_calculations(guild_prefix, channel_id: int):
    global prev_guild_data, prev_guild_members, guild_data, guild_members, guild_loop_started
    if not guild_loop_started:
        prev_guild_data = {}
        prev_guild_members = {}
        guild_loop_started = True

    else:
        prev_guild_data = guild_data
        prev_guild_members = guild_members
    guild_data = get_wynn_data(guild_prefix)
    guild_members = get_member_stats(guild_data)

    await check_completions((guild_members, prev_guild_members), channel_id)
    await xp_contributions(guild_members, prev_guild_members, WYNN_GUILD_QUERY_INTERVAL, channel_id)











async def check_completions(data: tuple, channel_id: int):
    guild_members, prev_guild_members = data

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
            ''.join((error_messages, f'{player} completed a suspiciously high amount of guild raids ({total_completions}) the past {WYNN_GUILD_QUERY_INTERVAL} minutes\n'))
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
    
    """ time = datetime.datetime.now()
    if not time.minute == 59:
        next_update_dc_timestamp = int(datetime.datetime.now().replace(minute=time.minute+1).timestamp())
    else:
        next_update_dc_timestamp = int(datetime.datetime.now().timestamp()) """
    
    channel: discord.TextChannel = client.get_channel(channel_id) # type: ignore
    if not len(embed.fields) == 0:
        await channel.send(
            content=error_messages,
            #content=f"next update at <t:{next_update_dc_timestamp}:T> (<t:{next_update_dc_timestamp}:R>) This might be inaccurate as I can't be bothered to handle edge cases",
            embed=embed)




async def xp_contributions(guild_members, prev_guild_members, timespan, channel_id):
    contributed_deltas = {}
    for player, data in prev_guild_members.items():
        contributed_delta = guild_members[player]['contributed'] - data['contributed']
        if contributed_delta == 0:
            continue
        contributed_deltas[player] = contributed_delta
    contributed_return_string = ''
    for player, amount in contributed_deltas.items():
        contributed_return_string = ''.join((contributed_return_string, f'{player}: {amount}\n'))
    if not len(contributed_return_string) == 0:
        embed = discord.Embed(title=f'Xp contributed in the last {timespan} minutes per player')
        embed.add_field(name='list', value=contributed_return_string[:1024])
        channel: discord.TextChannel = client.get_channel(channel_id) # type: ignore
        await channel.send(embed=embed)








@client.tree.command(name="start_looping_calculations", description="starts tracking guild raid completions")
async def start_looping_calculations(interaction: discord.Interaction):
    await interaction.response.defer()
    guild_prefix = 'TGAS'
    target_channel_id = interaction.channel_id
    if target_channel_id == None:
        return

    await interaction.followup.send('*started tracking*')
    await looping_calculations.start(guild_prefix, target_channel_id)







@client.tree.command(name="guild_raids", description="returns a list of all completed guild raids by each member")
async def raids(interaction: discord.Interaction):
    await interaction.response.defer()
    raid_data = get_guild_raids_per_player(get_member_stats(get_wynn_data()))
    
    complete_text = ''
    for player, stats in raid_data.items():
        text_template = f"# {player}\n\nTotal: {stats['total']}\n- NOTG: {stats['Nest of the Grootslangs']}\n- NOL: {stats["Orphion's Nexus of Light"]}\n- TCC: {stats['The Canyon Colossus']}\n- TNA: {stats['The Nameless Anomaly']}\n==\n\\"
        complete_text += text_template
    render_markdown_card(complete_text, 'data.png')
    with open('data.png', "rb") as f:
        data = discord.File(f)
    await interaction.followup.send(file=data)


def download_font():
    if not os.path.exists(FONT_PATH):
        print("Downloading font...")
        resp = requests.get(FONT_URL)
        resp.raise_for_status()
        with open(FONT_PATH, "wb") as f:
            f.write(resp.content)
        print("Font downloaded:", FONT_PATH)
    else:
        print("Font already exists:", FONT_PATH)

download_font()

# --- Step 2: The renderer with markdown and card layout ---

def render_markdown_card(
    text: str,
    output_path: str,
    width=500,
    padding=40,
    collumns=8,
    bg_color=(35, 35, 35, 255),
    card_color=(255, 255, 255, 255),
    border_color=(200, 200, 200, 255),
):

    # Load the downloaded font
    font_normal = ImageFont.truetype(FONT_PATH, 28)
    font_bold   = ImageFont.truetype(FONT_PATH, 32)
    font_code   = ImageFont.truetype(FONT_PATH, 26)
    font_h1     = ImageFont.truetype(FONT_PATH, 44)
    font_h2     = ImageFont.truetype(FONT_PATH, 36)

    # Sample icons (make sure these exist in your project)
    """ icons = {
        "info": Image.open("icons/info.png").convert("RGBA"),
        "warning": Image.open("icons/warning.png").convert("RGBA"),
    } """

    img = Image.new("RGBA", (width*collumns + 2 * padding, 10000), bg_color)
    draw = ImageDraw.Draw(img)
    y = padding
    x = padding
    max_y = y
    player_list: list = text.split('\\')

    for i, player in enumerate(player_list):
        if i % math.ceil(len(player_list)/collumns) == 0 and i != 0:
            max_y = y
            y = padding
            x += width
        for raw_line in player.split("\n"):
            line = raw_line.strip()
            if not line:
                y += 36
                continue

            # Headings
            if line.startswith("# "):
                draw.text((x + padding, y), line[2:], font=font_h1, fill="white")
                y += 60
                continue
            if line.startswith("## "):
                draw.text((x + padding, y), line[3:], font=font_h2, fill="white")
                y += 52
                continue

            if line.startswith("=="):
                y += 20
                draw.rectangle((x + padding, y - 4, x + width - padding, y + 2), fill=(230, 230, 230, 255))
                y += 50
                continue

            # List item
            if line.startswith("- "):
                draw.rectangle(
                    (x, y - 4, x + width - padding, y + 38),
                    #fill=(230, 230, 230, 255),
                )
                draw.text((x + padding + 20, y), line[2:], font=font_normal, fill="white")
                y += 46
                continue

            # Inline formatting

                # Default
            draw.text((x, y), line, font=font_normal, fill="white")

            y += 42

    
    total_width = collumns * width

    img.crop((0, 0, total_width + padding, max_y + padding)).save(output_path)





client.run(BOT_TOKEN)