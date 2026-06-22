import datetime
import logging

import discord
from discord.ext import commands, tasks
from discord import ui, app_commands

import utils.database as db
import utils.discordutils as dc_utils
import utils.added_exceptions as excepts
from utils.added_exceptions import handle_loop_errors

logger = logging.getLogger(name=__name__)


def init_database(database_path: str = ".\\persistent_data\\guild_api_database.db"):
    global meta, members_db, tome_requested_db # pylint: disable=global-variable-undefined

    p = database_path

    meta = db.MetaTable(p)

    members_db = db.UpdatingTable('members', p)
        
    tome_requested_db = db.TrackingTable('tome_requested', p)


class TomesCog(commands.Cog):
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.guild: discord.Guild

    async def cog_load(self) -> None:
        self.startup.start()


    @tasks.loop(count=1)
    @handle_loop_errors(logger=logger)
    async def startup(self):
        self.guild = dc_utils.get_guild(client=self.bot, meta_db=meta)
        self.tome_update_looping.start()
        self.bot.add_view(view=RequestedTomesView(guild=self.guild))


    @app_commands.command(name='setup_tomes', description='all times are in days')
    async def setup_tomes(self, interaction:discord.Interaction, cooldown: int, required_weekly_streak: int):
        meta.set_other(meta.OtherKeys.WYNNAPI_TOMES_REQUESTING_TIMEINTERVAL, cooldown)
        meta.set_other(meta.OtherKeys.WYNNAPI_TOMES_REQUESTING_WEEKLYSTREAK, required_weekly_streak)
        await interaction.response.send_message(content='Config has been set.', ephemeral=True)

    @app_commands.command(name='send_tome_requests_message')
    async def send_tome_requests_message(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel) or channel is None:
            return
        guild = interaction.guild
        if guild is None:
            return
        dc_utils.set_guild(guild, meta)
        dc_utils.set_channel(meta.ChannelUses.WYNNAPI_TOMES_REQUESTING_LIVE, channel, meta)
        if not self.tome_update_looping.is_running():
            self.tome_update_looping.start()
    
    @tasks.loop(minutes=2)
    @handle_loop_errors(logger=logger)
    async def tome_update_looping(self):
        try:
            guild = dc_utils.get_guild(self.bot, meta)
            await update_tome_live_message(guild)
        except: # pylint: disable=bare-except
            return

    @tome_update_looping.before_loop
    async def tome_update_looping_before_loop(self):
        await self.bot.wait_until_ready()


    @app_commands.command(name='reward_tomes')
    async def reward_tomes(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TomeRewardModal())

async def handle_tome_requests(interaction: discord.Interaction):
    if not isinstance(interaction.user, discord.Member):
        return
    username = interaction.user.display_name
    membersdata = members_db.fetchall_conditional(f'username = \'{username}\'')
    if membersdata is None:
        return await interaction.followup.send(content="You don't seem to be in the guild.\nIf you are, this is an error, please report\nIf you aren't in the guild, please ignore", ephemeral=True)
    memberdata = membersdata[0]
    uuid = memberdata['uuid']
    tome_requested_db_res = tome_requested_db.fetchlast_conditional(f'uuid = \'{uuid}\'')
    if tome_requested_db_res is not None:
        tome_requested_db_result = tome_requested_db_res 
    else:
        tome_requested_db_result = {'timestamp': 0}
    last_requested_timestamp = tome_requested_db_result['timestamp']
    last_requested = datetime.datetime.fromtimestamp(last_requested_timestamp)
    time_elapsed_needed_str = meta.get_other(meta.OtherKeys.WYNNAPI_TOMES_REQUESTING_TIMEINTERVAL)
    if time_elapsed_needed_str is None:
        return await interaction.followup.send(content='Please ask a moderator to set the minimum interval needed to request a tome again', ephemeral=True)
    time_elapsed_needed = int(time_elapsed_needed_str)
    if datetime.datetime.now() - last_requested < datetime.timedelta(days=time_elapsed_needed):
        return await interaction.followup.send(content=f'Please wait {time_elapsed_needed} days since your last request before requesting a tome again', ephemeral=True)
    if not memberdata['weekly']:
        return await interaction.followup.send(content='Please do your weekly before requesting a tome', ephemeral=True)
    required_weekly_streak_str = meta.get_other(meta.OtherKeys.WYNNAPI_TOMES_REQUESTING_WEEKLYSTREAK)
    if required_weekly_streak_str is None:
        return await interaction.followup.send(content='Please ask a moderator to set the minimum weekly streak to request a tome', ephemeral=True)
    required_weekly_streak = int(required_weekly_streak_str)
    if memberdata['weekly_streak'] < required_weekly_streak:
        return await interaction.followup.send(content=f'You need a weekly streak of at least {required_weekly_streak} to request a tome', ephemeral=True)
    tome_requested_db.updatecolumns(columns={'uuid': uuid})
    if interaction.guild is None:
        return await interaction.followup.send(content='Please don\'t use this outside a server')
    members_db.update('uuid', uuid, columns={'requested_tome_received': 0})
    guild = interaction.guild
    if guild is None:
        return await interaction.followup.send(content="An error has occured, try again later", ephemeral=True)
    await update_tome_live_message(guild)
    await interaction.followup.send(content="Your tome has been requested, it will be given to you shortly", ephemeral=True)


def create_tome_cooldown_string(guild: discord.Guild) -> str:
    try:
        requested = tome_requested_db.fetchall()
    except AttributeError as e:
        requested = []
        print(e)
    if requested == []:
        return 'No one currently on cooldown.'
    cooldown_db_res = meta.get_other(meta.OtherKeys.WYNNAPI_TOMES_REQUESTING_TIMEINTERVAL)
    if cooldown_db_res is None:
        return 'error while constructing cooldown list'
    cooldown = int(cooldown_db_res)
    on_cooldown_str = ''
    for memberdict in requested:
        if (datetime.datetime.now() - datetime.datetime.fromtimestamp(memberdict['timestamp'])).total_seconds() > datetime.timedelta(days=int(cooldown)).total_seconds():
            continue
        timestamp_value = int(memberdict['timestamp']) + int(datetime.timedelta(days=int(cooldown)).total_seconds())
        on_cooldown_str = '\n'.join((on_cooldown_str, f'{dc_utils.mention_user(memberdict['uuid'], guild, members_db)} ---------- <t:{timestamp_value}> | <t:{timestamp_value}:R>'))
    if on_cooldown_str == '':
        return 'No one currently on cooldown.'
    return f'Person ---------- Date for next possible request | relative time\n{on_cooldown_str}'

def create_tome_to_still_hand_out_string(guild: discord.Guild) -> str:
    db_res = members_db.fetchall_conditional('requested_tome_received = 0')
    if db_res == []:
        return ''
    return_str = ''
    for member in db_res:
        return_str = '\n- '.join((return_str, dc_utils.mention_user(member['uuid'], guild, members_db)))
    return f'### People who have requested a tome but not yet received one\n-# You will receive one as soon as possible\n-# Your cooldown has already started{return_str}'


class RequestedTomesView(discord.ui.LayoutView):
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

        self.add_item(discord.ui.TextDisplay(content='# People currently on cooldown\n-# This may take a few minutes to update'))
        self.add_item(discord.ui.Container(
            discord.ui.TextDisplay(
                content=create_tome_cooldown_string(guild)
                )
            ))
        
        tomes_to_reward = create_tome_to_still_hand_out_string(guild)
        if not tomes_to_reward == '':
            self.add_item(discord.ui.Container(
                discord.ui.TextDisplay(
                    content=tomes_to_reward
                    )
                ))
        
        class RequestButton(discord.ui.Button):
            async def callback(self, interaction: discord.Interaction):
                await interaction.response.defer(ephemeral=True)
                await handle_tome_requests(interaction)

        self.add_item(discord.ui.ActionRow(RequestButton(label='Request a tome', style=discord.ButtonStyle.green)))



async def update_tome_live_message(guild: discord.Guild):
    """
    Updates the live tome requests message with current requests information.

    Args:
        guild (discord.Guild): The guild to update the message for
    """

    channel = dc_utils.get_textchannel(meta.ChannelUses.WYNNAPI_TOMES_REQUESTING_LIVE, guild, meta)

    try:
        message = await dc_utils.get_message(meta.MessageIds.WYNNAPI_TOMES_REQUESTING_LAYOUTVIEW, channel, meta)
        await message.edit(view=RequestedTomesView(guild))
    except excepts.MessageNotConfiguredError:
        message = await channel.send(view=RequestedTomesView(guild))
        dc_utils.set_message(meta.MessageIds.WYNNAPI_TOMES_REQUESTING_LAYOUTVIEW, message, meta)
    except excepts.MessageNotFoundError:
        message = await channel.send(view=RequestedTomesView(guild))
        dc_utils.set_message(meta.MessageIds.WYNNAPI_TOMES_REQUESTING_LAYOUTVIEW, message, meta)


class TomeRewardModal(discord.ui.Modal, title="Tomes rewarded in-game"):
    def __init__(self):
        super().__init__()
        self.db_result = members_db.fetchall_conditional('requested_tome_received = 0')
        if self.db_result == []:
            self.add_item(discord.ui.TextDisplay(content='All tomes have been rewarded!'))
        else:
            self.to_reward_list = [row['uuid'] for row in self.db_result]
            self.to_reward_set = set()
            self.to_reward: dict[str, int] = {}
            for row in self.to_reward_list:
                if row in self.to_reward_set:
                    self.to_reward[row] += 1
                    continue
                self.to_reward[row] = 1
            self.create_modal_items()

    def create_modal_items(self):
        options = []
        for player, amount in self.to_reward.items():
            to_add = discord.CheckboxGroupOption(label=f"{amount} tomes rewarded to {dc_utils.get_player_username(player, members_db)}", value=player)
            options.append(to_add)
            if len(options) >= 10:
                add_option_group = ui.Label(text="ㅤ", component=ui.CheckboxGroup(options=options, max_values=len(options), min_values=0, required=False))
                self.add_item(add_option_group)
                options = options[10:]
        if len(options) > 0:
            add_option_group = ui.Label(text="ㅤ", component=ui.CheckboxGroup(options=options, max_values=len(options), min_values=0, required=False))
            self.add_item(add_option_group)


    async def on_submit(self, interaction: discord.Interaction) -> None: #pylint: disable=arguments-differ
        message_send = await interaction.response.defer(ephemeral=True)
        reset_players = []
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("please send this from a guild", ephemeral=True)
            return
        for item in self.walk_children():
            if isinstance(item, ui.CheckboxGroup):
                for player in item.values:
                    members_db.update('uuid', player, columns={'requested_tome_received': 1})
                    reset_players.append(player)
        if len(reset_players) > 0:
            await update_tome_live_message(guild)
            message = f"reset tomes to reward for {', '.join(map(str,(dc_utils.mention_user(player, guild, members_db) for player in reset_players)))}"
            await interaction.followup.send(message, ephemeral=True)
        else:
            message = "ㅤ"
            await interaction.followup.send(message, ephemeral=True)
            if message_send is None:
                return
            await interaction.followup.delete_message(message_send.id)

def main(global_bot):
    global tomes_cog # pylint: disable=global-variable-undefined
    init_database()
    tomes_cog = TomesCog(bot=global_bot)

async def setup(global_bot):
    main(global_bot=global_bot)
    await global_bot.add_cog(tomes_cog)
