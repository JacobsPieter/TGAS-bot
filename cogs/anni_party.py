"""
Discord bot module for managing Guild Annihilation party signups and organization.

This module provides functionality for:
- Managing party signups for Guild Annihilation events
- Organizing players into balanced parties by region
- Creating Discord embeds to display party information
- Handling user interactions through Discord buttons and modals
- Managing database operations for persistent storage

The bot automatically detects when a new Annihilation event starts and creates a new signup session.
Players can sign up with their preferred region, weapon, and playstyle, and the system organizes
them into balanced parties of up to 10 players per region.

Classes:
    Region: Enum representing available server regions
    PartyMember: Represents a player who has signed up for a party
    Party: Represents a complete party with members organized by region
    AnniView: Discord view with signup button
    BuildSubmitModal: Modal for submitting player build information
    PersonalSignupView: View for player signup process

Functions:
    get_current_anni_id: Gets the current Annihilation event ID
    set_current_anni_id: Sets the current Annihilation event ID
    get_meta: Gets metadata value from database
    set_meta: Sets metadata value in database
    get_signups: Gets all signups for current event
    get_parties: Organizes signups into balanced parties
    get_unsure: Gets players who haven't confirmed attendance
    create_embeds: Creates Discord embeds for party display
    update_live_message: Updates the live party message
    start_new_event: Starts a new Annihilation event
    setup_anni_parties: Sets up the bot for a specific channel
    on_message: Event handler for detecting new Annihilation events
    on_ready: Bot ready event handler
"""

import os
import asyncio
import sqlite3
import time
from enum import Enum
from dotenv import load_dotenv

import discord
from discord.ext import tasks, commands
from discord import app_commands


load_dotenv()

# ------------------ CONFIG ------------------
TEAM_SIZE = 10  # Maximum players per party



# ------------------ DB ------------------
def init_database():
    global db_lock, conn, cursor
    conn = sqlite3.connect("persistent_data\\anni_party.db", check_same_thread=False)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS signups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT NOT NULL,
        anni_id INTEGER NOT NULL,
        region TEXT NOT NULL,
        weapon TEXT NOT NULL,
        archetype TEXT NOT NULL,
        reserve INTEGER NOT NULL DEFAULT 0,
        can_lead INTEGER NOT NULL DEFAULT 0,
        guild_outsider INTEGER NOT NULL DEFAULT 0,
        timestamp INTEGER NOT NULL,
        UNIQUE(user_id, anni_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)
    conn.commit()

    db_lock = asyncio.Lock()

    version = conn.execute("PRAGMA user_version").fetchone()[0]

    if version < 1:
        try:
            conn.execute("""
                ALTER TABLE signups
                ADD COLUMN guild_outsider
                INTEGER DEFAULT 0
            """)
        except sqlite3.OperationalError:
            pass
        conn.execute("PRAGMA user_version = 1")

    conn.commit()

def get_current_anni_id() -> int:
    """
    Gets the current Annihilation event ID from the database.

    Returns:
        int: The current event ID, or 1 if no event is set
    """
    value = get_meta("current_anni_id")
    return int(value) if value is not None else 1

def set_current_anni_id(value: int):
    """
    Sets the current Annihilation event ID in the database.

    Args:
        value (int): The new event ID to set
    """
    set_meta("current_anni_id", str(value))

def get_meta(key: str) -> str|None:
    """
    Gets a metadata value from the database.

    Args:
        key (str): The metadata key to retrieve

    Returns:
        str: The metadata value, or None if not found
    """
    cursor.execute("SELECT value FROM meta WHERE key = ?", (key,))
    row = cursor.fetchone()
    return row[0] if row else None

def set_meta(key: str, value: str):
    """
    Sets a metadata value in the database.

    Args:
        key (str): The metadata key to set
        value (str): The value to store
    """
    cursor.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
        (key, str(value)),
    )
    conn.commit()

class Region(Enum):
    """
    Enum representing available server regions for Annihilation parties.

    Attributes:
        EU: Europe server region
        NA: North America server region
        AS: Asia server region
        NONE: No region selected
    """
    EU = 'EU'
    NA = 'NA'
    AS = 'AS'
    NONE = 'NONE'

class PartyMember:
    """
    Represents a player who has signed up for an Annihilation party.

    Attributes:
        name (str): The player's username
        weapon (str): The player's chosen weapon
        archetype (str): The player's playstyle archetype
        preferred_region (Region): The player's preferred server region
        confirmed (bool): Whether the player has confirmed attendance
        leader (bool): Whether the player is a party leader
    """
    def __init__(
            self,
            name: str,
            weapon: str,
            archetype: str,
            preferred_region: Region,
            confirmed: bool = True,
            leader: bool = False,
            guild_outsider: bool = False
            ):
        self.name = name
        self.weapon = weapon
        self.archetype = archetype
        self.preferred_region = preferred_region
        self.confirmed = confirmed
        self.leader = leader
        self.guild_outsider = guild_outsider

class Party:
    """
    Represents a complete Annihilation party with organized members.

    Attributes:
        __region (Region): The party's server region
        __members (list[PartyMember]): List of party members
        __leader (PartyMember | None): The party leader, if any
    """
    def __init__(self, region: Region, members: list[PartyMember]):
        self.__region: Region = region
        self.__members: list[PartyMember] = members
        self.__leader: PartyMember | None = None
        for member in members:
            if member.leader:
                self.__leader = member
                members.remove(member)

    def get_region(self):
        """
        Gets the party's server region as a string.

        Returns:
            str: The region value (e.g., 'EU', 'NA', 'AS')
        """
        return self.__region.value

    def get_members(self):
        """
        Gets the complete list of party members including the leader.

        Returns:
            list[PartyMember]: List of all party members
        """
        if not self.__leader is None:
            members = [self.__leader]
        else:
            members = []
        for member in self.__members:
            members.append(member)
        return members

    def has_leader(self) -> bool:
        """
        Checks if the party has a designated leader.

        Returns:
            bool: True if the party has a leader, False otherwise
        """
        if self.__leader is None:
            return False
        return True

async def get_signups() -> list[PartyMember]:
    """
    Gets all player signups for the current Annihilation event.

    Returns:
        list[PartyMember]: List of all players who have signed up
    """
    anni_id = get_current_anni_id()

    async with db_lock:
        cursor.execute("""
            SELECT user_id, username, region, weapon, archetype, reserve, can_lead, guild_outsider, timestamp
            FROM signups
            WHERE anni_id = ?
        """, (anni_id,))
        rows = cursor.fetchall()

    partymembers: list[PartyMember] = []
    for row in rows:
        match row[2]:
            case 'EU':
                region = Region.EU
            case 'NA':
                region = Region.NA
            case 'AS':
                region = Region.AS
            case _:
                region = Region.NONE
        member = PartyMember(
            name=row[1],
            weapon=row[3],
            archetype=row[4],
            preferred_region=region,
            confirmed=row[5],
            leader=row[6],
            guild_outsider=row[7]
            )
        partymembers.append(member)

    return partymembers

async def get_parties() -> list[Party]:
    """
    Organizes all confirmed signups into balanced parties by region.

    Returns:
        list[Party]: List of organized parties
    """
    signups = await get_signups()
    if signups == []:
        return []
    possible_party_members = [member for member in signups if member.confirmed and not member.guild_outsider]
    parties: list[Party] = []
    EU_members: list[PartyMember] = [] #pylint: disable=invalid-name
    NA_members: list[PartyMember] = [] #pylint: disable=invalid-name
    AS_members: list[PartyMember] = [] #pylint: disable=invalid-name
    region_groups = (EU_members, NA_members, AS_members)

    for member in possible_party_members:
        match member.preferred_region:
            case Region.EU:
                EU_members.append(member)
            case Region.NA:
                NA_members.append(member)
            case Region.AS:
                AS_members.append(member)

    leftovers: list[PartyMember] = []
    for region_group in region_groups:
        while len(region_group) > 10:
            parties.append(Party(region_group[0].preferred_region, region_group[:10]))
            region_group = region_group[10:]
        leftovers.extend(region_group)

    while len(leftovers) > 10:
        parties.append(Party(
            max(
                set((leftover.preferred_region for leftover in leftovers)),
                key=[leftover.preferred_region for leftover in leftovers].count
                ),
            leftovers[:10]
            ))
        leftovers = leftovers[10:]

    if not len(leftovers) < 2:
        parties.append(Party(
            max(
                set((leftover.preferred_region for leftover in leftovers)),
                key=[leftover.preferred_region for leftover in leftovers].count
                ),
            leftovers
            ))
    elif len(leftovers) == 1:
        parties.append(Party(leftovers[0].preferred_region, leftovers))

    return parties

async def get_unsure() -> list[PartyMember]:
    """
    Gets players who have signed up but haven't confirmed attendance.

    Returns:
        list[PartyMember]: List of players with unconfirmed status
    """
    signups = await get_signups()
    confirmation_pending = [member for member in signups if not member.confirmed and not member.guild_outsider]
    return confirmation_pending

async def get_outsiders() -> list[PartyMember]:
    signups = await get_signups()
    outsiders = [member for member in signups if member.guild_outsider]
    return outsiders

async def create_embeds(guild: discord.Guild):
    """
    Creates Discord embeds to display party information for a guild.

    Args:
        guild (discord.Guild): The guild to create embeds for

    Returns:
        list[discord.Embed]: List of embeds displaying party information
    """
    embeds = []
    parties = await get_parties()
    if parties == []:
        embed = discord.Embed(title='Guild Annihilation Party', colour=discord.Colour.brand_red())
        embed.add_field(name='Server Region', value='Waiting for people to sign up', inline=False)
        embed.add_field(name='Party', value='No one has signed up yet')
        embeds.append(embed)
    else:
        for party in parties:
            embed = discord.Embed(
                title="Guild Annihilation Party",
                colour=discord.Colour.brand_red()
                )
            embed.add_field(
                name='Server Region',
                value=party.get_region(), inline=False
                )
            members = party.get_members()
            name = guild.get_member_named(members[0].name)
            if name is None:
                party_members_string: str = f' {members[0].name} - {members[0].weapon} | {members[0].archetype}' #pylint: disable=line-too-long
            else:
                party_members_string: str = f' {name.mention} - {members[0].weapon} | {members[0].archetype}' #pylint: disable=line-too-long
            for member in members[1:]:
                name = guild.get_member_named(member.name)
                if name is None:
                    party_members_string = ''.join((party_members_string, f'\n {member.name} - {member.weapon} | {member.archetype}')) #pylint: disable=line-too-long
                else:
                    party_members_string = ''.join((party_members_string, f'\n {name.mention} - {member.weapon} | {member.archetype}')) #pylint: disable=line-too-long
            if party.has_leader():
                party_members_string = ''.join(('👑', party_members_string))
            embed.add_field(name='Party', value=party_members_string)
            embeds.append(embed)

    unsures = await get_unsure()
    if not unsures == []:
        unsure_list = discord.Embed(title='People still unsure if they will be present', colour=discord.Colour.red()) #pylint: disable=line-too-long
        unsure_string = ''
        for unsure in unsures:
            name = guild.get_member_named(unsure.name)
            if name is None:
                unsure_string = ''.join((unsure_string, f'\n {unsure.name} - {unsure.weapon} | {unsure.archetype}')) #pylint: disable=line-too-long
            else:
                unsure_string = ''.join((unsure_string, f'\n {name.mention} - {unsure.weapon} | {unsure.archetype}')) #pylint: disable=line-too-long
        unsure_list.add_field(name='', value=unsure_string)
        embeds.append(unsure_list)
    
    outsiders = await get_outsiders()
    if not outsiders == []:
        outsider_list = discord.Embed(title='People not in the guild wanting to join', colour=discord.Colour.red())
        outsider_string = ''
        for outsider in outsiders:
            name = guild.get_member_named(outsider.name)
            if name is None:
                outsider_string = ''.join((outsider_string, f'\n {outsider.name} - {outsider.weapon} | {outsider.archetype}'))
            else:
                outsider_string = ''.join((outsider_string, f'\n {name.mention} - {outsider.weapon} | {outsider.archetype}')) #pylint: disable=line-too-long
        outsider_list.add_field(name='', value=outsider_string)
        embeds.append(outsider_list)
    return embeds


async def update_live_message(guild: discord.Guild):
    """
    Updates the live party message with current party information.

    Args:
        guild (discord.Guild): The guild to update the message for
    """
    channel_meta_id = get_meta("channel_id")
    if channel_meta_id is None:
        print('Please set a channel!')
        return
    channel_id: int = int(channel_meta_id)
    channel = guild.get_channel(channel_id)
    if channel is None:
        return
    if isinstance(channel, (discord.ForumChannel, discord.CategoryChannel)):
        return

    embeds = await create_embeds(guild)
    message_id = get_meta("live_message_id")

    try:
        if message_id:
            message = await channel.fetch_message(int(message_id))
            await message.edit(embeds=embeds, view=AnniView())
        else:
            message = await channel.send(embeds=embeds, view=AnniView())
            set_meta("live_message_id", str(message.id))
    except discord.NotFound:
        message = await channel.send(embeds=embeds, view=AnniView())
        set_meta("live_message_id", str(message.id))

class AnniView(discord.ui.View):
    """
    Discord view containing the signup button for Annihilation parties.
    """
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Sign up",
        style=discord.ButtonStyle.success,
        custom_id="anni:signup",
    )
    async def signup_button(self, interaction: discord.Interaction, button: discord.ui.Button): #pylint: disable=unused-argument
        """
        Handles the signup button click event.

        Args:
            interaction (discord.Interaction): The interaction that triggered the button
            button (discord.ui.Button): The button that was clicked
        """
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message(content='An error occured while trying to get the guild in the signup button\nPlease report to an @developer')
        await interaction.response.send_message(
            content='ㅤ',
            view=PersonalSignupView(guild),
            ephemeral=True,
            )

    @discord.ui.button(
        label="Leave",
        style=discord.ButtonStyle.danger,
        custom_id="anni:leave",
    )
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button): #pylint: disable=unused-argument
        """
        Handles the leave button click event.

        Args:
            interaction (discord.Interaction): The interaction that triggered the button
            button (discord.ui.Button): The button that was clicked
        """
        cursor.execute(
            """
            DELETE FROM signups
            WHERE user_id = ?
            AND anni_id = ?
            """, (interaction.user.id, get_current_anni_id())
            )
        
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(content='An error occured', ephemeral=True)
            return
        await update_live_message(guild)

        await interaction.response.send_message(
            content='You have been removed from the party',
            ephemeral=True
            )


class BuildSubmitModal(discord.ui.Modal, title='Submit your build'):
    """
    Modal for players to submit their weapon and playstyle information.
    """
    weapon = discord.ui.TextInput(label='Weapon', style=discord.TextStyle.short, required=True)

    archetype = discord.ui.TextInput(label='Playstyle', style=discord.TextStyle.short, required=True) #pylint: disable=line-too-long

    def __init__(self) -> None:
        super().__init__(timeout=300)
        self.__parsed_build: tuple[str, str] = ('','')

    async def on_submit(self, interaction: discord.Interaction): # pylint: disable=arguments-differ
        """
        Handles the modal submission event.

        Args:
            interaction (discord.Interaction): The interaction that submitted the modal
        """
        self.__parsed_build = self.weapon.value.strip(), self.archetype.value.strip()
        await interaction.response.send_message(content='ㅤ', ephemeral=True, delete_after=0) #pylint: disable=line-too-long

    def get_build(self) -> tuple[str, str]:
        """
        Gets the parsed build information from the modal.

        Returns:
            tuple[str, str]: Tuple containing weapon and archetype
        """
        return self.__parsed_build

class PersonalSignupView(discord.ui.View):
    """
    View for handling the player signup process with multiple steps.
    """
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=600)
        self.region = Region.NONE
        self.weapon: str = ''
        self.archetype: str = ''
        self.sure = True
        minimum_guild_required_role_db_res = get_meta('anni_parties_minimum_required_role')
        if not minimum_guild_required_role_db_res is None:
            self.minimum_role = int(minimum_guild_required_role_db_res)
        else:
            self.minimum_role = None


    @discord.ui.button(label='enter build', style=discord.ButtonStyle.success, row=0)
    async def build_button(self, interaction: discord.Interaction, button: discord.ui.Button): # pylint: disable=unused-argument
        """
        Handles the build submission button click.

        Args:
            interaction (discord.Interaction): The interaction that triggered the button
            button (discord.ui.Button): The button that was clicked
        """
        build_modal = BuildSubmitModal()
        await interaction.response.send_modal(build_modal)
        await build_modal.wait()
        self.weapon, self.archetype = build_modal.get_build()

    @discord.ui.select(options=[discord.SelectOption(label="I'm sure I can be there", value='True', default=True), discord.SelectOption(label="I'm not sure I can be here", value='False')], row=1) #pylint: disable=line-too-long
    async def availabilityselect(self, interaction:discord.Interaction, select: discord.ui.Select):
        """
        Handles the availability selection dropdown.

        Args:
            interaction (discord.Interaction): The interaction that triggered the select
            select (discord.ui.Select): The select menu that was changed
        """
        if select.values[0] == 'True':
            self.sure = True
        else:
            self.sure = False
        await interaction.response.send_message(content=f'ㅤ', ephemeral=True, delete_after=0) #pylint: disable=line-too-long

    @discord.ui.select(
            options=[
                discord.SelectOption(label='EU'),
                discord.SelectOption(label='NA'),
                discord.SelectOption(label='AS')
                ],
            row=2,
            placeholder='Preferred server region'
            )
    async def regionselect(self, interaction:discord.Interaction, select: discord.ui.Select):
        """
        Handles the region selection dropdown.

        Args:
            interaction (discord.Interaction): The interaction that triggered the select
            select (discord.ui.Select): The select menu that was changed
        """
        match select.values[0]:
            case 'EU':
                self.region = Region.EU
            case 'NA':
                self.region = Region.NA
            case 'AS':
                self.region = Region.AS
        await interaction.response.send_message(content='ㅤ', ephemeral=True, delete_after=0) #pylint: disable=line-too-long


    @discord.ui.button(
        label='submit',
        style=discord.ButtonStyle.success,
        row=4
    )
    async def submit_button(self, interaction: discord.Interaction, button: discord.ui.Button): # pylint: disable=unused-argument
        """
        Handles the final signup submission.

        Args:
            interaction (discord.Interaction): The interaction that triggered the button
            button (discord.ui.Button): The button that was clicked
        """
        member = interaction.user
        if not isinstance(member, discord.Member):
            return await interaction.response.send_message(content='Please send this from a server and report to a @developer', ephemeral=True)
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message(content='apparently this server does not exist, try again, maybe report idk') #pylint: disable=line-too-long
        anni_id = get_current_anni_id()
        await interaction.response.send_message(content='Submitting... Please wait', ephemeral=True)

        if self.region == Region.NONE:
            await interaction.edit_original_response(content='Please select a region before submitting') #pylint: disable=line-too-long
            return
        if self.weapon == '' or self.archetype == '':
            await interaction.edit_original_response(content='Please fill in a build')
            return
        if self.minimum_role is None:
            guild_outsider_flag = False
        else:
            if member.get_role(self.minimum_role) is None:
                guild_outsider_flag = True
            else:
                guild_outsider_flag = False
        leader_flag = False

        async with db_lock:
            cursor.execute("""
                INSERT OR REPLACE INTO signups
                (user_id, username, anni_id, region, weapon, archetype, reserve, can_lead, guild_outsider, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                member.id,
                str(member),
                anni_id,
                self.region.value,
                self.weapon,
                self.archetype,
                int(self.sure),
                int(leader_flag),
                int(guild_outsider_flag),
                int(time.time()),
            ))
            conn.commit()

        await interaction.edit_original_response(content='Your party application has been submitted')
        await update_live_message(guild)

async def start_new_event(guild: discord.Guild, bot: discord.Client):
    """
    Starts a new Annihilation event and resets the signup system.

    Args:
        guild (discord.Guild): The guild where the event is starting
    """
    old_anni_id = get_current_anni_id()
    new_anni_id = old_anni_id + 1
    set_current_anni_id(new_anni_id)

    # Clear the live message reference so a new dashboard gets created
    async with db_lock:
        cursor.execute("DELETE FROM meta WHERE key = ?", ("live_message_id",))
        conn.commit()

    channel_meta_id = get_meta("channel_id")
    if channel_meta_id is None:
        print('Please set a channel!')
        return
    channel_id: int = int(channel_meta_id)
    channel = guild.get_channel(channel_id)
    if channel is None:
        return

    embed = discord.Embed(
        title="🟢 Annihilation party signups!",
        description="Press **Join** to reserve a spot in the guild anni party.",
        color=discord.Color.brand_red(),
    )
    if isinstance(channel, (discord.ForumChannel, discord.CategoryChannel)):
        return
    await channel.send(embed=embed)
    bot.add_view(AnniView())
    await update_live_message(guild)


class AnniParty(commands.Cog):
    def __init__(self, self_bot):
        self.bot: discord.Client = self_bot

    @commands.Cog.listener()
    async def on_ready(self):

        if get_meta("current_anni_id") is None:
            set_current_anni_id(1)
        
    async def cog_load(self):

        self.bot.add_view(AnniView())
        self.bg_task.start()


    @tasks.loop(count=1)
    async def bg_task(self):

        init_database()

        guild_id = get_meta("guild_id")
        if guild_id is None:
            print("Please set guild first!")
            return

        guild_id = int(guild_id)

        guild = self.bot.get_guild(guild_id)

        if guild is None:
            try:
                guild = await self.bot.fetch_guild(guild_id)
            except discord.NotFound:
                print("Guild not found / bot removed")
                return

        await update_live_message(guild)
    

    @app_commands.command(name='setup_anni_parties',
        description='Used to configure the annihilation parties module of the mod.'
        )
    async def setup_anni_parties(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        role_to_mention: discord.Role,
        minimum_needed_role: discord.Role): # pylint: disable=unused-argument,disable=line-too-long
        """
        Discord command to set up the Annihilation parties system for a specific channel.

        Args:
            interaction (discord.Interaction): The interaction that triggered the command
            channel (discord.TextChannel): The channel to set up for parties
        """
        set_meta('channel_id', str(channel.id))
        set_meta('guild_id', str(interaction.guild_id))
        set_meta('anni_ping_role_to_mention', str(role_to_mention.id))
        set_meta('anni_parties_minimum_required_role', str(minimum_needed_role.id))
        await interaction.response.send_message(content='channel and role to mention set!', ephemeral=True)
    
    # @commands.Cog.listener()
    # async def on_message(self, message: discord.Message):
    #     """
    #     Event handler for detecting new Annihilation events from game messages.

    #     Args:
    #         message (discord.Message): The message that was received
    #     """
    #     if message.author.bot:
    #         return

    #     channel_id = get_meta('channel_id')  #type: ignore
    #     if not channel_id is None:
    #         if message.channel.id == int(channel_id):
    #             if "Prelude to Annihilation!\nHateful echoes erupt from the Realm of War.\nWynn faces Annihilation." in message.content: #pylint: disable=line-too-long
    #                 guild = message.guild
    #                 if guild is None:
    #                     return
    #                 await start_new_event(guild)

    @app_commands.command(
            name='start-anni-party-signups',
            description='Starts the signup process for the guild anni parties')
    async def start_annihilation_parties(self, interaction: discord.Interaction):
        """
        Discord command to send a test embed and start the signup process.

        Args:
            interaction (discord.Interaction): The interaction that triggered the command
        """
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            await interaction.followup.send(content="apparently the discord server you are sending this from doesn't exist, please don't report. I don't want to deal with this", ephemeral=True) #pylint: disable=line-too-long
            return
        channel = interaction.channel
        if channel is None:
            return await interaction.followup.send(content='An error occured while getting this interaction\'s channel\nPlease try again and report this to someone with the @developer role')
        if isinstance(channel, (discord.ForumChannel, discord.CategoryChannel)):
            return await interaction.followup.send(content='An error occured while getting this interaction\'s channel\nPlease try again and report this to someone with the @developer role')
        await interaction.followup.send(content='started signups!', ephemeral=True)
        role_db_res = get_meta('anni_ping_role_to_mention')
        if role_db_res is None:
            await interaction.followup.send(content='Please have a hr member set the role to mention', ephemeral=True)
            return
        role_id = int(role_db_res)
        role = guild.get_role(role_id)
        if role is None:
            return await interaction.followup.send(content='Error while trying to fetch the role', ephemeral=True)
        await channel.send(content=f'{role.mention} Annihilation starts soon!')
        await start_new_event(guild, self.bot)



async def setup(global_bot):
    print('setup called')
    await global_bot.add_cog(AnniParty(global_bot))


if __name__ == '__main__':
    print('make this do something first maybe')
