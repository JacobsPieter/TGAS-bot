import os
import datetime
import logging

import discord
from dotenv import load_dotenv

import utils.added_exceptions as excepts
import utils.logger as log
import utils.database as db
import utils.bot as bot_class
import utils.paths as paths

load_dotenv()



allowed_mentions = discord.AllowedMentions(users=True, roles=True)

TOKEN: str = os.getenv("BOT_TOKEN") #type: ignore




def init_database(database_path = paths.DATABASE):
    global meta, members_db, member_guild_raids_db, tome_requested_db, playtime_tracking_db # pylint: disable=global-variable-undefined

    logger.info(msg='Initialising the database...')

    p = str(database_path)


    general_database_operations_object = db.Database(p)
    general_database_operations_object.run_migrations()

    logger.info(msg="Creating tables if they don't exist yet...")

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
    
    member_wars_db = db.UpdatingTable('member_wars', p)
    member_wars_db.create(
        ('uuid', str()),
        {
            'total': int(),
            'total_before_last_payout': int(),
            'payout': int(),
            'backlog': int()
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

    # annihilation_parties_db = db.TrackingTable('annihilation_parties', p)
    # annihilation_parties_db.create(
    #     columns={
    #         'discord_id': str(),
    #         'anni_id': int(),
    #         'server_region': str(),
    #         'weapon': str(),
    #         'archetype': str(),
    #         'build_link': str(),
    #         'sure': bool(),
    #         'can_host': bool(),
    #         'current_host': bool(),
    #         'in_guild': bool(),
    #         'current_party_id': int()
    #     },
    #     extra_sql='UNIQUE(discord_id, anni_id)'
    # )

    logger.info(msg="Database initalisation done")





log.init_logging()
logger = logging.getLogger(__name__)
logger.info(msg='Starting bot...')
init_database()
bot = bot_class.Bot()


@bot.tree.error
async def error_handling(interaction: discord.Interaction, error):
    if not interaction.response.is_done():
        await interaction.response.send_message(content='An error occured', ephemeral=True)
    else:
        await interaction.followup.send(content="An error has occured while processing the command", ephemeral=True)
    module = interaction.__module__
    local_logger = logging.getLogger(name=module)
    excepts.handle_error(error=error, logger=local_logger)



bot.run(TOKEN)
