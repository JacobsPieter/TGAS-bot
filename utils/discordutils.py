import datetime
import re
import utils.database as db
import discord
import utils.added_exceptions as excepts
from enum import Enum

DISCORD_CHANNEL_TYPES = discord.TextChannel | discord.ForumChannel | discord.CategoryChannel

class DiscordTimestampForms(Enum):
    SHORT_TIME = 't'
    MEDIUM_TIME = 'T'
    SHORT_DATE = 'd'
    LONG_DATE = 'D'
    LONG_DATE_SHORT_TIME = 'f'
    FULL_DATE_SHORT_TIME = 'F'
    SHORT_DATE_SHORT_TIME = 's'
    SHORT_DATE_MEDIUM_TIME = 'S'
    RELATIVE_TIME = 'R'


def get_player_username(player_uuid: str, members_db: db.UpdatingTable) -> str:
    playerdata = members_db.fetchone('uuid', player_uuid)
    if not playerdata is None:
        playername: str = playerdata['username']
    else:
        playername = player_uuid
    return playername


def mention_user(user_uuid: str, guild: discord.Guild, members_db: db.UpdatingTable) -> str:
    playerdata = members_db.fetchone('uuid', user_uuid)
    if not playerdata is None:
        username: str = playerdata['username']
        name = guild.get_member_named(username) if not guild is None else None
        playername = name.mention if not name is None else username
    else:
        username = user_uuid
        playername = user_uuid
    return playername



def set_guild(guild: discord.Guild, meta_db: db.MetaTable) -> None:
    guild_id = guild.id
    return meta_db.set_guild_id(guild_id)

def get_guild(client: discord.Client, meta_db: db.MetaTable) -> discord.Guild:
    guild_id = meta_db.get_guild_id()
    if guild_id is None:
        raise excepts.GuildNotConfiguredError()
    guild = client.get_guild(guild_id)
    if guild is None:
        raise excepts.GuildNotFoundError(guild_id)
    return guild


def set_channel(channel: db.MetaTable.ChannelUses, discord_channel: DISCORD_CHANNEL_TYPES, meta_db: db.MetaTable):
    channel_id = discord_channel.id
    return meta_db.set_channel_id(channel, channel_id)

async def get_thread_by_id(channel_id: int, bot: discord.Client) -> discord.Thread:
    try:
        return_channel = await bot.fetch_channel(channel_id)
    except discord.NotFound as e:
        raise excepts.ChannelNotFoundError(channel_id)
    if not isinstance(return_channel, discord.Thread):
        raise TypeError(
            f"Expected ThreadChannel but got {type(return_channel).__name__}"
        )
    return return_channel

async def get_textchannel_by_id(channel_id: int, bot: discord.Client) -> discord.TextChannel:
    try:
        return_channel = await bot.fetch_channel(channel_id)
    except discord.NotFound as e:
        raise excepts.ChannelNotFoundError(channel_id)
    if not isinstance(return_channel, discord.TextChannel):
        raise TypeError(
            f"Expected TextChannel but got {type(return_channel).__name__}"
        )
    return return_channel

async def get_forumchannel_by_id(channel_id: int, bot: discord.Client) -> discord.ForumChannel:
    try:
        return_channel = await bot.fetch_channel(channel_id)
    except discord.NotFound as e:
        raise excepts.ChannelNotFoundError(channel_id)
    if not isinstance(return_channel, discord.ForumChannel):
        raise TypeError(
            f"Expected TextChannel but got {type(return_channel).__name__}"
        )
    return return_channel

def get_textchannel(channel: db.MetaTable.ChannelUses, guild: discord.Guild, meta_db: db.MetaTable) -> discord.TextChannel:
    channel_id = meta_db.get_channel_id(channel)
    if channel_id is None:
        raise excepts.ChannelNotConfiguredError(channel)
    return_channel = guild.get_channel(channel_id)
    if return_channel is None:
        raise excepts.MetaChannelNotFoundError(channel, channel_id)
    if not isinstance(return_channel, discord.TextChannel):
        raise TypeError(
            f"Expected TextChannel but got {type(return_channel).__name__}"
        )
    return return_channel

def get_forumchannel(channel: db.MetaTable.ChannelUses, guild: discord.Guild, meta_db: db.MetaTable) -> discord.ForumChannel:
    channel_id = meta_db.get_channel_id(channel)
    if channel_id is None:
        raise excepts.ChannelNotConfiguredError(channel)
    return_channel = guild.get_channel(channel_id)
    if return_channel is None:
        raise excepts.MetaChannelNotFoundError(channel, channel_id)
    if not isinstance(return_channel, discord.ForumChannel):
        raise TypeError(
            f"Expected ForumChannel but got {type(return_channel).__name__}"
        )
    return return_channel


def set_message(message: db.MetaTable.MessageIds, discord_message: discord.Message, meta_db: db.MetaTable):
    message_id = discord_message.id
    return meta_db.set_message_id(message, message_id)

async def get_message(message: db.MetaTable.MessageIds, channel: discord.TextChannel, meta_db: db.MetaTable) -> discord.Message:
    message_id = meta_db.get_message_id(message)
    if message_id is None:
        raise excepts.MessageNotConfiguredError(message)
    try:
        return_message = await channel.fetch_message(message_id)
    except discord.NotFound as e:
        raise excepts.MessageNotFoundError(message, message_id) from e
    return return_message


def set_role(role: db.MetaTable.RoleIds, discord_role: discord.Role, meta_db: db.MetaTable):
    role_id = discord_role.id
    return meta_db.set_role_id(role, role_id)

def get_role(role: db.MetaTable.RoleIds, guild: discord.Guild, meta_db: db.MetaTable) -> discord.Role:
    role_id = meta_db.get_role_id(role)
    if role_id is None:
        raise excepts.RoleNotConfiguredError(role)
    return_role = guild.get_role(role_id)
    if return_role is None:
        raise excepts.RoleNotFoundError(role, role_id)
    return return_role

def mention_role(role_to_mention: db.MetaTable.RoleIds, guild: discord.Guild, meta_db: db.MetaTable):
    role = get_role(role_to_mention, guild, meta_db)
    return role.mention


def parse_discord_timestamps(string: str) -> datetime.datetime:
    timestamp_regex = re.compile(pattern=r"<t:(\d+)(?::[tTdDfFsSR])?>")
    match = timestamp_regex.fullmatch(string=string)
    if not match:
        raise excepts.InvalidTimestampError(string)
    timestamp = datetime.datetime.fromtimestamp(timestamp=int(match.group(1)))
    return timestamp

def send_discord_timestamps(date_time: datetime.datetime, form: DiscordTimestampForms) -> str:
    return_string = f'<t:{int(date_time.timestamp())}:{form}'
    return return_string
