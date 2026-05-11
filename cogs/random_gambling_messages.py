import random as rd

import discord
from discord.ext import commands


def send_random_gambling_encouragement_message():
    """
    Generate a random gambling encouragement message.

    Returns a random message from a predefined list of gambling-related
    encouragement messages.

    Returns:
        str: A random gambling encouragement message
    """
    messages = [
        'Yes, gamble!',
        'Of course you should!',
        'gamba',
        '90% of gamblers quit before they win big'
        ]
    return rd.choice(messages)



class GamblingMessages(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Handle incoming messages and respond to gambling-related content.

        Monitors all messages in Discord channels and responds with random
        gambling encouragement messages when gambling-related keywords are detected.

        Args:
            message (discord.Message): The incoming Discord message

        Raises:
            discord.DiscordException: If there's an issue sending the response
        """
        if message.author == self.bot.user:
            return

        encouraged_words = ['gamble', 'gamba', 'roll', 'gambling', 'gambler', 'luck']
        if any(encouraged_behaviour in message.content.lower() for encouraged_behaviour in encouraged_words):  # pylint: disable=line-too-long
            await message.channel.send(send_random_gambling_encouragement_message())
    
async def setup(bot):
    await bot.add_cog(GamblingMessages(bot))
