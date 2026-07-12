"""
Handles the setup for the bot
"""
import logging
from typing import Any, cast


import discord
from discord import app_commands
from discord.ext import tasks, commands


import utils.database as db
import utils.added_exceptions as excepts
import utils.discordutils as dc_utils
from utils.added_exceptions import handle_loop_errors
import utils.paths as paths

logger = logging.getLogger(name=__name__)

def init_database(database_path = paths.DATABASE):
    global meta # pylint: disable=global-variable-undefined

    p = database_path

    meta = db.MetaTable(p)

class SetupCog(commands.Cog):
    def __init__(self, bot: discord.Client):
        self.bot = bot

    async def cog_load(self) -> None:
        self.startup.start()


    @tasks.loop(count=1)
    @handle_loop_errors(logger=logger)
    async def startup(self):
        guild = dc_utils.get_guild(self.bot, meta)
        self.bot.add_view(SetupView(guild))

    @app_commands.command(name='setup')
    async def setup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            raise RuntimeError('The guild doesn\'t exist, try sending the command from a guild')
        dc_utils.set_guild(guild, meta)
        await interaction.followup.send(view=SetupView(guild), ephemeral=True)




class SetupView(discord.ui.LayoutView):
    def __init__(self, guild):
        super().__init__(timeout=300)
        self.add_item(discord.ui.TextDisplay(content='# Bot setup'))
        self.add_item(discord.ui.TextDisplay(content='-# Annihilation parties hasn\'t yet been added'))

        self.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large))
        
        self.add_item(discord.ui.TextDisplay(content='## Guild Raids'))
        self.add_item(discord.ui.TextDisplay(content='Channel to use for updates'))
        try:
            current_graid_channel = dc_utils.get_textchannel(meta.ChannelUses.WYNNAPI_GRAIDS_TRACKING_SEND, guild, meta)
            class Graid_Channel_Select1(discord.ui.ChannelSelect):
                def __init__(self):
                    super().__init__(channel_types=[discord.ChannelType.text], default_values=[current_graid_channel])
                async def callback(self, interaction: discord.Interaction) -> Any:
                    dc_utils.set_channel(meta.ChannelUses.WYNNAPI_GRAIDS_TRACKING_SEND, cast(discord.TextChannel, self.values[0]), meta)
                    await interaction.response.send_message(content='ㅤ', ephemeral=True)
            self.add_item(discord.ui.ActionRow(Graid_Channel_Select1()))
        except:
            class Graid_Channel_Select2(discord.ui.ChannelSelect):
                def __init__(self):
                    super().__init__(channel_types=[discord.ChannelType.text], placeholder='Update channel')
                async def callback(self, interaction: discord.Interaction) -> Any:
                    dc_utils.set_channel(meta.ChannelUses.WYNNAPI_GRAIDS_TRACKING_SEND, cast(discord.TextChannel, self.values[0]), meta)
                    await interaction.response.send_message(content='ㅤ', ephemeral=True, delete_after=0.1)
            self.add_item(discord.ui.ActionRow(Graid_Channel_Select2()))
        
        self.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large))

        self.add_item(discord.ui.TextDisplay(content='## Tomes'))
        self.add_item(discord.ui.TextDisplay(content='Cooldown to request tomes (in days)'))
        self.tome_request_interval = meta.get_other(meta.OtherKeys.WYNNAPI_TOMES_REQUESTING_TIMEINTERVAL)
        if self.tome_request_interval is None:
            self.tome_request_interval = 14
        else:
            self.tome_request_interval = int(self.tome_request_interval)
        self.current_tome_request_interval = discord.ui.TextDisplay(content=str(self.tome_request_interval))
        self.add_item(self.current_tome_request_interval)
        class TomeRequestInterval_ConfirmButton(discord.ui.Button):
            def __init__(self, parent_view):
                self.parent_view = parent_view
                super().__init__(label='Confirm', style=discord.ButtonStyle.green)
            async def callback(self, interaction: discord.Interaction) -> Any:
                meta.set_other(meta.OtherKeys.WYNNAPI_TOMES_REQUESTING_TIMEINTERVAL, self.parent_view.tome_request_interval)
                await interaction.response.send_message(content='ㅤ', ephemeral=True)
        self.add_item(discord.ui.ActionRow(
            CounterButton(self, 'tome_request_interval', 10, label='+10', style=discord.ButtonStyle.green),
            CounterButton(self, 'tome_request_interval', 1, label='+1', style=discord.ButtonStyle.green),
            CounterButton(self, 'tome_request_interval', -1, label='-1', style=discord.ButtonStyle.red),
            CounterButton(self, 'tome_request_interval', -10, label='-10', style=discord.ButtonStyle.red),
            TomeRequestInterval_ConfirmButton(self)
            ))
        self.add_item(discord.ui.TextDisplay(content='weekly streak needed'))
        self.tome_weeklies_needed = meta.get_other(meta.OtherKeys.WYNNAPI_TOMES_REQUESTING_WEEKLYSTREAK)
        if self.tome_weeklies_needed is None:
            self.tome_weeklies_needed = 2
        else:
            self.tome_weeklies_needed = int(self.tome_weeklies_needed)
        self.current_tome_weeklies_needed = discord.ui.TextDisplay(content=str(self.tome_weeklies_needed))
        self.add_item(self.current_tome_weeklies_needed)
        class TomeWeekliesNeeded_ConfirmButton(discord.ui.Button):
            def __init__(self, parent_view):
                self.parent_view = parent_view
                super().__init__(label='Confirm', style=discord.ButtonStyle.green)
            async def callback(self, interaction: discord.Interaction) -> Any:
                meta.set_other(meta.OtherKeys.WYNNAPI_TOMES_REQUESTING_WEEKLYSTREAK, self.parent_view.tome_weeklies_needed)
                await interaction.response.send_message(content='ㅤ', ephemeral=True)
        self.add_item(discord.ui.ActionRow(
            CounterButton(self, 'tome_weeklies_needed', 10, label='+10', style=discord.ButtonStyle.green),
            CounterButton(self, 'tome_weeklies_needed', 1, label='+1', style=discord.ButtonStyle.green),
            CounterButton(self, 'tome_weeklies_needed', -1, label='-1', style=discord.ButtonStyle.red),
            CounterButton(self, 'tome_weeklies_needed', -10, label='-10', style=discord.ButtonStyle.red),
            TomeWeekliesNeeded_ConfirmButton(self)
            ))



class CounterButton(discord.ui.Button):
    def __init__(self, view, attribute_name: str, amount: int, label: str, style: discord.ButtonStyle):
        super().__init__(label=label, style=style)
        self.parent_view = view
        self.attribute_name = attribute_name
        self.amount = amount

    async def callback(self, interaction: discord.Interaction):
        current_value = getattr(self.parent_view, self.attribute_name)
        new_value = current_value + self.amount
        setattr(self.parent_view, self.attribute_name, new_value)
        display_attr_name = f"current_{self.attribute_name}"
        if hasattr(self.parent_view, display_attr_name):
            display_element = getattr(self.parent_view, display_attr_name)
            display_element.content = str(new_value)
        await interaction.response.edit_message(view=self.parent_view)



def main(global_bot):
    global setup_cog # pylint: disable=global-variable-undefined
    init_database()
    setup_cog = SetupCog(bot=global_bot)



async def setup(global_bot):
    main(global_bot=global_bot)
    await global_bot.add_cog(setup_cog)
