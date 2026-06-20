from __future__ import annotations

from typing import Any


def handle_error(error: Exception):
    if isinstance(error, DatabaseException):
        #logger.warning(error)
        pass

    if isinstance(error, DiscordAPIException):
        #logger.warning(error)
        pass

    #logger.exception("Unhandled error", exc_info=error)


class BotBaseException(Exception):
    """
    Base exception for the bot, all exceptions should inherit from here
    """



class DatabaseException(BotBaseException):
    """
    Base exception for all database-related errors.

    This should be raised when required data is missing,
    malformed, or otherwise unavailable from the database.

    Future functionality such as automatic logging,
    metrics collection, or user notifications can be
    implemented here and inherited by all database
    exceptions.
    """

    def __init__(self, message: str):
        # logger.error(message)
        super().__init__(message)

class GuildNotConfiguredError(DatabaseException):
    """
    Raised when no guild ID has been configured in the
    database.
    """

    def __init__(self):
        super().__init__(
            "No guild ID has been configured in the database."
        )

class ChannelNotConfiguredError(DatabaseException):
    """
    Raised when a required channel ID is missing from the
    database.
    """

    def __init__(self, channel: Any):
        self.channel = channel

        super().__init__(
            f"Channel '{channel.name}' has not been configured."
        )   

class MessageNotConfiguredError(DatabaseException):
    """
    Raised when a required message ID is missing from the
    database.
    """

    def __init__(self, message: Any):
        self.message = message

        super().__init__(
            f"Message '{message.name}' has not been configured."
        )

class RoleNotConfiguredError(DatabaseException):
    """
    Raised when a required role ID is missing from the
    database.
    """

    def __init__(self, role: Any):
        self.role = role

        super().__init__(
            f"Role '{role.name}' has not been configured."
        )


class DiscordAPIException(BotBaseException):
    """
    Base exception for all Discord object lookup errors.

    This should be raised when an object is expected to
    exist in Discord but cannot be resolved.

    Future functionality such as automatic logging,
    retry mechanisms, or error reporting can be
    implemented here and inherited by all Discord API
    exceptions.
    """

    def __init__(self, message: str):
        # logger.error(message)
        super().__init__(message)

class GuildNotFoundError(DiscordAPIException):
    """
    Raised when a configured guild ID cannot be resolved
    to a Discord guild.
    """

    def __init__(self, guild_id: int, in_cache=True):
        self.guild_id = guild_id

        super().__init__(
            f"Guild with ID {guild_id} could not be found {'in cache.' if in_cache else '.'}"
        )

class ChannelNotFoundError(DiscordAPIException):
    """
    Raised when a configured channel ID cannot be resolved
    within the Discord guild.
    """

    def __init__(self, channel: Any, channel_id: int):
        self.channel = channel
        self.channel_id = channel_id

        super().__init__(
            f"Channel '{channel.name}' "
            f"(ID {channel_id}) could not be found."
        )

class MessageNotFoundError(DiscordAPIException):
    """
    Raised when a configured message ID cannot be resolved
    from Discord.
    """

    def __init__(self, message: Any, message_id: int):
        self.message = message
        self.message_id = message_id

        super().__init__(
            f"Message '{message.name}' "
            f"(ID {message_id}) could not be found."
        )

class RoleNotFoundError(DiscordAPIException):
    """
    Raised when a configured role ID cannot be resolved
    within Discord.
    """

    def __init__(self, role: Any, role_id: int):
        self.role = role
        self.role_id = role_id

        super().__init__(
            f"Role '{role.name}' "
            f"(ID {role_id}) could not be found."
        )


class InvalidTimestampError(BotBaseException, ValueError):
    """Raised when a provided timestamp is not a valid Discord timestamp."""

    def __init__(self, value: str):
        self.value = value
        super().__init__(f"Invalid Discord timestamp format: `{value}`")
