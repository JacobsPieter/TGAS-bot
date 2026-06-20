import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import datetime

import utils.added_exceptions as excepts
import cogs.database as db

load_dotenv()



allowed_mentions = discord.AllowedMentions(users=True, roles=True)

TOKEN: str = os.getenv("BOT_TOKEN") #type: ignore


class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.guilds = True
        intents.messages = True
        intents.message_content = True

        super().__init__(
            command_prefix="!",
            intents=intents
        )

    async def setup_hook(self):
        print("🔧 setup_hook: loading extensions")

        await load_cogs(self)

        print("🔧 setup_hook: extensions loaded")

    async def on_ready(self):
        print(f"✅ Logged in as {self.user}")
        await self.tree.sync()


async def load_cogs(bot):
    extensions = [
    "cogs.anni_party",
    "cogs.random_gambling_messages",
    "cogs.api_depending.api_queries",
    "cogs.api_depending.tome_requesting",
    "cogs.api_depending.graid_tracking"
    ]
    for ext in extensions:
        await bot.load_extension(ext)



def init_database(database_path: str = ".\\persistent_data\\guild_api_database.db"):
    global meta, members_db, member_guild_raids_db, tome_requested_db, playtime_tracking_db # pylint: disable=global-variable-undefined

    p = database_path


    general_database_operations_object = db.Database(p)
    general_database_operations_object.run_migrations()


    meta = db.MetaTable(p)
    meta.create()

    members_db = db.UpdatingTable('members', p)
    members_db.create(
        ('uuid', str()),
        {
            'username': str(),
            'guild_rank': str(),
            'last_seen': datetime.datetime.now(),
            'playtime': float(),
            'weekly': bool(),
            'weekly_streak': int(),
            'contributed': int(),
            'contribution_rank': int(),
            'joined_guild': datetime.datetime.now(),
            'left_guild': bool(),
            'total_guild_raids': int(),
            'wars': int(),
            'requested_tome_received': bool()
        })
    
    member_guild_raids_db = db.UpdatingTable('member_guild_raids', p)
    member_guild_raids_db.create(
        ('uuid', str()),
        {
            'total': int(),
            'notg': int(),
            'nol': int(),
            'tcc': int(),
            'tna': int(),
            'wtp': int(),
            'aspects': int(),
            'next_aspect': int()
        }
        )
    
    tome_requested_db = db.TrackingTable('tome_requested', p)
    tome_requested_db.create(
        columns={
            'uuid': str()
            }
        )

    playtime_tracking_db = db.TrackingTable('playtime', p)
    playtime_tracking_db.create(
        columns={
            'uuid': str(),
            'playtime': float()
        }
    )

def main():
    global global_bot # pylint: disable=global-variable-undefined
    bot = Bot()
    global_bot = bot
    bot.run(TOKEN)



if __name__ == '__main__':
    main()

@global_bot.tree.error
async def error_handling(interaction: discord.Interaction, error):
    if not interaction.response.is_done():
        await interaction.response.send_message('An error occured', ephemeral=True)
    excepts.handle_error(error)

