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
import utils.paths as paths





logger = logging.getLogger(name=__name__)

def init_database(database_path = paths.DATABASE):
    global meta, members_db, member_wars_db # pylint: disable=global-variable-undefined

    p = database_path

    meta = db.MetaTable(p)

    members_db = db.UpdatingTable('members', p)
    
    member_wars_db = db.UpdatingTable('member_wars', p)



class WarsCog(commands.Cog):
    def __init__(self, passed_bot):
        self.bot: Bot = passed_bot


    async def cog_load(self) -> None:
        self.startup.start()


    @tasks.loop(count=1)
    @handle_loop_errors(logger=logger)
    async def startup(self):
        self.bot.loop.create_task(self.handle_wars_loop())
        guild = dc_utils.get_guild(self.bot, meta)
        self.bot.add_view(view=WarCompletionsView(guild=guild))

    async def handle_wars_loop(self):
        while True:
            try:
                data = await self.bot.state.war_queue.get()
                guild = dc_utils.get_guild(self.bot, meta)
                await handle_wars(guild, data)
                self.bot.state.war_queue.task_done()
            except Exception as e: #pylint: disable=broad-exception-caught
                excepts.handle_error(error=e, logger=logger)

    @app_commands.command(name="setup_wars")
    async def setup_wars(self, interaction: discord.Interaction, channel:discord.TextChannel, payout: int):
        dc_utils.set_channel(channel=meta.ChannelUses.WYNNAPI_WAR_TRACKING_SEND, discord_channel=channel, meta_db=meta)
        dc_utils.set_guild(guild=channel.guild, meta_db=meta)
        meta.set_other(other=db.MetaTable.OtherKeys.WYNNAPI_WARS_PAYOUT_AMOUNT, value=payout )
        await interaction.response.send_message(content='channel set!', ephemeral=True)
        guild = dc_utils.get_guild(self.bot, meta)
        await update_war_payouts_live_message(guild)

    @app_commands.command(name='reward_war_payouts')
    async def reward_war_payouts(self, interaction: discord.Interaction):
        await interaction.response.send_modal(WarPayoutRewardModal())
    
    @app_commands.command(name='start_new_war_payout_period')
    async def start_new_war_payout_period(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        database_result = member_wars_db.fetchall()
        for member in database_result:
            backlog = member['payout']
            member_wars_db.update('uuid', member['uuid'], columns={'total_before_last_payout': member['total'],'backlog': backlog})
        guild = dc_utils.get_guild(self.bot, meta)
        channel = dc_utils.get_textchannel(channel=db.MetaTable.ChannelUses.WYNNAPI_WAR_TRACKING_SEND, guild=guild, meta_db=meta)
        message = await channel.send(view=WarCompletionsView(guild))
        dc_utils.set_message(meta.MessageIds.WYNNAPI_WAR_TRACKING_LAYOUTVIEW, message, meta)
        await interaction.followup.send(content='Reset payout period', ephemeral=True)



async def handle_wars(guild: discord.Guild, data: dict):
    previous_members_db_res = members_db.fetchall()
    previous_members = {memberdata['uuid']: {key: value for key, value in memberdata.items() if key != 'uuid'} for memberdata in previous_members_db_res}
    
    completed_wars: dict[str, int] = {}
    for rank, rank_members in data['members'].items():
        if not rank in {"owner", "chief", "strategist", "captain", "recruiter", "recruit"}: # all guild ranks, will need updating in case of update
            continue
        for guild_member, member_data in rank_members.items():
            if member_data.get('globalData', None) is None:
                #print(member.username)
                continue
            if member_data['globalData'].get('wars', None) is None:
                continue
            if previous_members.get(guild_member) is None and not member_data['globalData'] is None:
                member_wars_db.update(
                    primary_key_name='uuid',
                    primary_key=guild_member,
                    columns={
                        'total': member_data['globalData']['wars'],
                        'total_before_last_payout': member_data['globalData']['wars'],
                        'payout': 0
                        }
                    )
                continue
            member_wars_db_res = member_wars_db.fetchone('uuid', guild_member)
            if member_wars_db_res is None:
                member_wars_db.update(
                    primary_key_name='uuid',
                    primary_key=guild_member,
                    columns={
                        'total': member_data['globalData']['wars'],
                        'total_before_last_payout': member_data['globalData']['wars'],
                        'payout': 0
                        }
                    )
                continue
            if previous_members[guild_member]['wars'] < member_data['globalData']['wars']:
                logger.info('%s completed %s war(s)', member_data['username'], member_data['globalData']['wars'] - previous_members[guild_member]['wars'])
                player_completed_wars = member_data['globalData']['wars'] - previous_members[guild_member]['wars']
                # member_wars_db_res = member_wars_db.fetchone('uuid', guild_member)
                # if member_wars_db_res is None:
                #     raise excepts.DatabaseException(message=f'For member {guild_member} there isn\'t an entry get in the member_wars_db, but they were called.')
                current_payout = member_wars_db_res['payout']
                per_war_payout = meta.get_other(db.MetaTable.OtherKeys.WYNNAPI_WARS_PAYOUT_AMOUNT)
                if per_war_payout is None:
                    raise excepts.DatabaseException(message=f'No war payout amount has been set!')
                payout = int(per_war_payout) * player_completed_wars + current_payout
                member_wars_db.update(
                    primary_key_name='uuid',
                    primary_key=guild_member,
                    columns={
                        'total': member_data['globalData']['wars'],
                        'payout': payout
                        }
                    )
                completed_wars[guild_member] = player_completed_wars
                continue
    await update_war_payouts_live_message(guild=guild)



async def update_war_payouts_live_message(guild: discord.Guild):
    """
    Updates the live war payouts message with current payout information.

    Args:
        guild (discord.Guild): The guild to update the message for
    """

    channel = dc_utils.get_textchannel(meta.ChannelUses.WYNNAPI_WAR_TRACKING_SEND, guild, meta)

    try:
        message = await dc_utils.get_message(meta.MessageIds.WYNNAPI_WAR_TRACKING_LAYOUTVIEW, channel, meta)
        await message.edit(view=WarCompletionsView(guild))
    except excepts.MessageNotConfiguredError:
        message = await channel.send(view=WarCompletionsView(guild))
        dc_utils.set_message(meta.MessageIds.WYNNAPI_WAR_TRACKING_LAYOUTVIEW, message, meta)
    except excepts.MessageNotFoundError:
        message = await channel.send(view=WarCompletionsView(guild))
        dc_utils.set_message(meta.MessageIds.WYNNAPI_WAR_TRACKING_LAYOUTVIEW, message, meta)


def format_currency(amount: int) -> str:
    stx = amount // (64 * 64)
    le = (amount // 64) % 64
    eb = amount % 64
    formatted_payout = f'{f'{stx}STX ' if stx > 0 else ''}{f'{le}LE ' if le > 0 else ''}{f'{eb}EB ' if eb > 0 else ''}'
    return formatted_payout



def create_payout_message(guild: discord.Guild) -> str:
    to_return_string = ''
    member_wars_db_res = member_wars_db.fetchall()
    members_with_wars = [member for member in member_wars_db_res if member['payout'] - member['backlog'] > 0]
    members_with_wars.sort(key=lambda member: member["payout"] - member["backlog"], reverse=True)
    for member in members_with_wars:
        done_wars = member['total'] - member['total_before_last_payout']
        mentioned_member = dc_utils.mention_user(member['uuid'], guild, members_db)
        formatted_payout = format_currency(member['payout'] - member['backlog'])
        member_string = f'`{done_wars:>8}` | **`{formatted_payout:>15}`** | {mentioned_member}'
        to_return_string = '\n1. '.join((to_return_string, member_string))
    return to_return_string


def create_backlog_message(guild: discord.Guild) -> str:
    to_return_string = ''
    member_wars_db_res = member_wars_db.fetchall()
    members_with_backlog = [member for member in member_wars_db_res if member['backlog'] > 0]
    for member in members_with_backlog:
        mentioned_member = dc_utils.mention_user(member['uuid'], guild, members_db)
        formatted_payout = format_currency(member['backlog'])
        member_string = f'**`{formatted_payout:>15}`** | {mentioned_member}'
        to_return_string = '\n1. '.join((to_return_string, member_string))
    return to_return_string


class WarCompletionsView(discord.ui.LayoutView):
    def __init__(self, guild):
        super().__init__(timeout=None)
        
        self.guild = guild

        self.add_item(discord.ui.TextDisplay(content='# Wars'))
        self.add_item(discord.ui.TextDisplay(content='## What is warring?'))
        self.add_item(
            discord.ui.TextDisplay(
                content='insert warring explanation here'
            )
        )

        self.add_item(discord.ui.Separator())

        self.add_item(discord.ui.TextDisplay(content='## What are the rewards'))
        self.add_item(discord.ui.TextDisplay(content='### For the guild'))
        self.add_item(
            discord.ui.TextDisplay(
                content=(
                    '- Guild tomes;\n'
                    '- Season rating;\n'
                    '  - Ranking higher on a leaderboard will give the guild more cosmetic rewards at the end of a season;\n'
                    '  - Getting to certain season rating tresholds will give non-cosmetic rewards such as:\n'
                    '    - Emeralds;\n'
                    '    - Guild bank slots;\n'
                    '    - Guild tomes.\n'
                    '- Disoverability;\n'
                    '  - people will see our guild faster, so we will get more recruits\n'
                )
            )
        )
        self.add_item(discord.ui.TextDisplay(content='### For you as a guild member'))
        self.add_item(
            discord.ui.TextDisplay(
                content=(
                    '- 16 EB per war;\n'
                    '- a new kind of content to explore;\n'
                    '- Having fun with the war team;\n'
                    '- Annoying big guilds :wink: ;\n'
                    '- A higher war count to flex on your friends'
                )
            )
        )

        self.add_item(discord.ui.Separator())

        self.add_item(discord.ui.TextDisplay(content='## Current warcounts and the rewards for them'))
        payout_message = create_payout_message(self.guild)
        if payout_message == '':
            payout_message = 'No one has done a war yet.'
        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(
                    content=payout_message
                )
            )
        )
        self.add_item(discord.ui.TextDisplay(content='## Payout backlog'))
        self.add_item(discord.ui.TextDisplay(content='-# These people still have rewards from previous cycles left'))
        backlog_message = create_backlog_message(self.guild)
        if backlog_message == '':
            backlog_message = 'No backlog exists'
        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(
                    content=backlog_message
                )
            )
        )


class WarPayoutRewardModal(discord.ui.Modal, title='War payouts to do'):
    def __init__(self):
        super().__init__()
        db_result = member_wars_db.fetchall()
        self.to_reward = [member for member in db_result if member['payout'] > 0]
        self.add_items()
    
    def add_items(self):
        options = []
        for member in self.to_reward:
            to_add = discord.CheckboxGroupOption(label=f"{format_currency(member['payout'])} rewarded to {dc_utils.get_player_username(player_uuid=member['uuid'], members_db=members_db)}", value=member['uuid'])
            options.append(to_add)
            if len(options) >= 10:
                add_option_group = ui.Label(text="ㅤ", component=ui.CheckboxGroup(options=options, max_values=len(options), min_values=0, required=False))
                self.add_item(add_option_group)
                options = options[10:]
        if len(options) > 0:
            add_option_group = ui.Label(text="ㅤ", component=ui.CheckboxGroup(options=options, max_values=len(options), min_values=0, required=False))
            self.add_item(add_option_group)
        if self.total_children_count == 0:
            empty_text = ui.TextDisplay(content="All payouts have been done!")
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
                    member_wars_db.update('uuid', player, columns={'payout': 0, 'backlog': 0})
                    reset_players.append(player)
        if len(reset_players) > 0:
            message = f"reset aspects for {', '.join(map(str,(dc_utils.mention_user(user_uuid=player, guild=guild, members_db=members_db) for player in reset_players)))}"
            await interaction.response.send_message(message, ephemeral=True)
        else:
            message = "ㅤ"
            await interaction.response.send_message(message, ephemeral=True, delete_after=0)
        await update_war_payouts_live_message(guild)




def main(global_bot):
    global wars_cog # pylint: disable=global-variable-undefined
    init_database()
    wars_cog = WarsCog(passed_bot=global_bot)



async def setup(global_bot):
    main(global_bot=global_bot)
    await global_bot.add_cog(wars_cog)
