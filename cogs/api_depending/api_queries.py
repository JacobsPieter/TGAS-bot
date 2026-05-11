import os
from enum import Enum
import sqlite3
import json
import datetime

from dotenv import load_dotenv
import requests
import discord
from discord import app_commands
from discord.ext import tasks, commands


load_dotenv()

# ------------------ CONFIG ------------------
# Bot token from environment variables
TOKEN: str = os.getenv("BOT_TOKEN")  #type: ignore
GUILD_ID = 1475943041570312285 #TODO: IMPLEMENT CORRECT LOGIC FOR IT __VERY TEMPORARY__

# ------------------ BOT SETUP ------------------
intents = discord.Intents.default()
intents.members = True
intents.message_content = True  # Required for message content processing

allowed_mentions = discord.AllowedMentions(users=True, roles=True)

bot = commands.Bot(command_prefix="!", intents=intents)

class APIHandler:
    WYNN_API_BASE_URL = "https://api.wynncraft.com/v3/"

    WYNN_API_TOKEN: str = os.getenv("WYNN_API_TOKEN") #type: ignore

    class GuildIdentifier(Enum):
        PREFIX = 'prefix'
        GUILDNAME = 'name'

    class MemberIdentifier(Enum):
        UUID = 'uuid'
        USERNAME = 'username'



    def construct_guild_endpoint_url(self, identifier: GuildIdentifier = GuildIdentifier.PREFIX, guild: str = 'TGAS', memberidentifier: MemberIdentifier = MemberIdentifier.UUID) -> str:
        if identifier == self.GuildIdentifier.GUILDNAME:
            return f'{self.WYNN_API_BASE_URL}/guild/{guild}?identifier={memberidentifier.value}'
        return f'{self.WYNN_API_BASE_URL}guild/{identifier.value}/{guild}?identifier={memberidentifier.value}'

    def get_endpoint(self, url: str):
        headers = {
        "Authorization": f"Bearer {self.WYNN_API_TOKEN}"
        }
        response = requests.get(url, headers=headers, timeout=30)
        return response


    def get_endpoint_data(self, url: str):
        data = self.get_endpoint(url).json()
        return data

    def dump_endpoint_data(self, url: str):

        with open("testing\\playerdata.json", 'w') as file: #pylint: disable=unspecified-encoding
            json.dump(self.get_endpoint(url).json(), file)


class DataBaseHandler:
    def __init__(self, db_path: str = '.\\persistent_data\\api_requests.db'):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self._create_tables()
    
    def _create_tables(self):

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
            )

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_data (
                uuid TEXT PRIMARY KEY,
                level INTEGER,
                xp_percent INTEGER,
                territories INTEGER,
                wars INTEGER,
                raids INTEGER,
                member_count INTEGER
            )
            """
            )
        
        #TODO: add wars to this table
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS members (
                uuid TEXT PRIMARY KEY,
                username TEXT,
                guild_rank TEXT,
                last_online INTEGER,
                playtime INTEGER,
                weekly INTEGER,
                weekly_streak INTEGER,
                contributed INTEGER,
                contribution_rank INTEGER,
                joined_guild INTEGER,
                left_guild INTEGER,
                total_guild_raids INTEGER,
                last_updated_timestamp INTEGER
            )
            """
            )
        
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS member_guild_raids (
                uuid TEXT PRIMARY KEY,
                total INTEGER,
                notg INTEGER,
                nol INTEGER,
                tcc INTEGER,
                tna INTEGER,
                wtp INTEGER,
                aspects INTEGER,
                next_aspect INTEGER,
                latest_timestamp INTEGER
            )
            """
        )
        
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_raid_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raid TEXT,
                party_member1 TEXT,
                party_member2 TEXT,
                party_member3 TEXT,
                party_member4 TEXT,
                timestamp INTEGER
            )
            """
        )

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS member_rank_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT,
                old_rank TEXT,
                rank TEXT,
                timestamp INTEGER
            )
            """
        )

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS member_playtime_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT,
                playtime INTEGER,
                timestamp INTEGER
            )
            """
        )

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS member_contribution_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT,
                contribution INTEGER,
                timestamp INTEGER
            )
            """
        )

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS member_contribution_rank_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT,
                old_contribution_rank INTEGER,
                contribution_rank INTEGER,
                timestamp INTEGER
            )
            """
        )

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS member_guild_join_leave_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT,
                activity INTEGER,
                timestamp INTEGER
            )
            """
        ) # activity should be set to 1 if joining and to 0 if leaving

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS wars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT,
            wars INTEGER,
            timestamp INTEGER
            )
            """
        )
        
        self.conn.commit()


    def set_meta(self, key: str, value: str):
        """
        Sets a metadata value in the database.

        Args:
            key (str): The metadata key to set
            value (str): The value to store
        """
        self.cursor.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            (key, str(value)),
        )


    def _pick(self, new_value, old_value, default=None):
        if new_value is not None:
            return new_value
        if old_value is not None:
            return old_value
        return default

    def update_members(
        self,
        uuid: str,
        username: str | None,
        guild_rank: str | None,
        last_online: int | None,
        playtime: int | None,
        weekly: int | None,
        weekly_streak: int | None,
        contributed: int | None,
        contribution_rank: int | None,
        joined_guild: int | None,
        left_guild: int | None,
        total_guild_raids: int | None,
        ):

        self.conn.row_factory = sqlite3.Row


        try:
            self.cursor.execute(
                """
                SELECT *
                FROM members
                WHERE uuid = ?
                """,
                (uuid,)
            )
            row = self.cursor.fetchone()
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error while reading member {uuid}") from e

        now = int(datetime.datetime.now().timestamp())

        if row is None:
            # first time we see this uuid
            full_row = {
                "uuid": uuid,
                "username": username,
                "guild_rank": guild_rank,
                "last_online": last_online,
                "playtime": playtime if not playtime is None else 0,
                "weekly": weekly if not weekly is None else 0,
                "weekly_streak": weekly_streak if not weekly_streak is None else 0,
                "contributed": contributed,
                "contribution_rank": contribution_rank,
                "joined_guild": joined_guild,
                "left_guild": left_guild,
                "total_guild_raids": total_guild_raids if not total_guild_raids is None else 0,
                "last_updated_timestamp": now,
            }

            # decide whether you want to allow partial first inserts
            missing = [k for k in full_row if full_row[k] is None]
            if missing:
                print(guild_rank)
                print(uuid)
                print(username)
                print(missing)
                #raise ValueError
            
            self.cursor.execute(
                """
                INSERT INTO members (
                    uuid,
                    username,
                    guild_rank,
                    last_online,
                    playtime,
                    weekly,
                    weekly_streak,
                    contributed,
                    contribution_rank,
                    joined_guild,
                    left_guild,
                    total_guild_raids,
                    last_updated_timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid,
                    username,
                    guild_rank,
                    last_online,
                    playtime if not playtime is None else 0,
                    weekly if not weekly is None else 0,
                    weekly_streak if not weekly_streak is None else 0,
                    contributed,
                    contribution_rank,
                    joined_guild,
                    left_guild,
                    total_guild_raids if not total_guild_raids is None else 0,
                    now,
                )
            )
        else:
            # preserve old values when the new value is None
            full_row = {
                "uuid": uuid,
                "username": self._pick(username, row["username"], 'None'),
                "guild_rank": self._pick(guild_rank, row["guild_rank"], 'None'),
                "last_online": self._pick(last_online, row["last_online"], 0),
                "playtime": self._pick(playtime, row["playtime"], 0),
                "weekly": self._pick(weekly, row["weekly"], 0),
                "weekly_streak": self._pick(weekly_streak, row["weekly_streak"], 0),
                "contributed": self._pick(contributed, row["contributed"], 0),
                "contribution_rank": self._pick(contribution_rank, row["contribution_rank"], 0),
                "joined_guild": self._pick(joined_guild, row["joined_guild"], 0),
                "left_guild": self._pick(left_guild, row["left_guild"], 0),
                "total_guild_raids": self._pick(total_guild_raids, row["total_guild_raids"], 0),
                "last_updated_timestamp": now,
            }

            self.cursor.execute(
                """
                UPDATE members
                SET
                    username = :username,
                    guild_rank = :guild_rank,
                    last_online = :last_online,
                    playtime = :playtime,
                    weekly = :weekly,
                    weekly_streak = :weekly_streak,
                    contributed = :contributed,
                    contribution_rank = :contribution_rank,
                    joined_guild = :joined_guild,
                    left_guild = :left_guild,
                    total_guild_raids = :total_guild_raids,
                    last_updated_timestamp = :last_updated_timestamp
                WHERE uuid = :uuid
                """,
                full_row
            )
        
        self.conn.commit()

    def update_member_guild_raids(
            self,
            uuid: str,
            total: int | None = None,
            notg: int | None = None,
            nol: int | None = None,
            tcc: int | None = None,
            tna: int | None = None,
            wtp: int | None = None,
            aspects: int | None = None,
            next_aspect: int | None = None
        ):

    
        self.conn.row_factory = sqlite3.Row
        try:
            self.cursor.execute(
                """
                SELECT *
                FROM member_guild_raids
                WHERE uuid = ?
                """,
                (uuid,)
            )
            row = self.cursor.fetchone()
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error while reading member {uuid}") from e

        now = int(datetime.datetime.now().timestamp())

        if row is None:
            # first time we see this uuid
            self.cursor.execute(
                """
                INSERT INTO member_guild_raids (
                    uuid,
                    total,
                    notg,
                    nol,
                    tcc,
                    tna,
                    wtp,
                    aspects,
                    next_aspect,
                    latest_timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid,
                    total if not total is None else 0,
                    notg if not notg is None else 0,
                    nol if not nol is None else 0,
                    tcc if not tcc is None else 0,
                    tna if not tna is None else 0,
                    wtp if not wtp is None else 0,
                    aspects if not aspects is None else 0,
                    next_aspect if not next_aspect is None else 0,
                    now
                )
            )

        else:
            # preserve old values when the new value is None
            full_row = {
                "uuid": uuid,
                "total": self._pick(total, row["total"], 0),
                "notg": self._pick(notg, row["notg"], 0),
                "nol": self._pick(nol, row["nol"], 0),
                "tcc": self._pick(tcc, row["tcc"], 0),
                "tna": self._pick(tna, row["tna"], 0),
                "wtp": self._pick(wtp, row["wtp"], 0),
                "aspects": self._pick(aspects, row["aspects"], 0),
                "next_aspect": self._pick(next_aspect, row["next_aspect"], 0),
                "latest_timestamp": now,
            }

            self.cursor.execute(
                """
                UPDATE member_guild_raids
                SET
                    total = :total,
                    notg = :notg,
                    nol = :nol,
                    tcc = :tcc,
                    tna = :tna,
                    wtp = :wtp,
                    aspects = :aspects,
                    next_aspect = :next_aspect,
                    latest_timestamp = :latest_timestamp
                WHERE uuid = :uuid
                """,
                full_row
            )
        
        self.conn.commit()
    
    def update_guild_raid_history(self, raid: str, party: tuple[str, str, str, str]):
        party_member1, party_member2, party_member3, party_member4 = party

        now = int(datetime.datetime.now().timestamp())

        full_row = {
            "raid": raid,
            "party_member1": party_member1,
            "party_member2": party_member2,
            "party_member3": party_member3,
            "party_member4": party_member4,
            "timestamp": now
            }

        self.cursor.execute(
            """
            INSERT INTO guild_raid_history (
            raid, party_member1, party_member2, party_member3, party_member4,
            timestamp
            ) VALUES (
            :raid, :party_member1, :party_member2, :party_member3, :party_member4,
            :timestamp
            )
            """,
            full_row
            )

        self.conn.commit()
    










    def get_meta(self, key: str) -> str|None:
        """
        Gets a metadata value from the database.

        Args:
            key (str): The metadata key to retrieve

        Returns:
            str: The metadata value, or None if not found
        """
        self.cursor.execute("SELECT value FROM meta WHERE key = ?", (key,))
        row = self.cursor.fetchone()
        return row[0] if row else None

    # MEMBERS

    def fetch_all_members(self) -> list[dict]:
        self.cursor.execute(
            """
            SELECT
                uuid,
                username,
                guild_rank,
                last_online,
                playtime,
                weekly,
                weekly_streak,
                contributed,
                contribution_rank,
                joined_guild,
                left_guild,
                total_guild_raids,
                last_updated_timestamp
            FROM members
            """
        )

        rows = self.cursor.fetchall()

        return [
            {
                "uuid": row[0],
                "username": row[1],
                "guild_rank": row[2],
                "last_online": row[4],
                "playtime": row[5],
                "weekly": row[6],
                "weekly_streak": row[7],
                "contributed": row[8],
                "contribution_rank": row[9],
                "joined_guild": row[10],
                "left_guild": row[11],
                "total_guild_raids": row[12],
                "last_updated_timestamp": row[13],
            }
            for row in rows
        ]
    
    def fetch_all_current_members(self) -> dict[str, dict]:
        self.cursor.execute(
            """
            SELECT
                uuid,
                username,
                guild_rank,
                last_online,
                playtime,
                weekly,
                weekly_streak,
                contributed,
                contribution_rank,
                joined_guild,
                left_guild,
                total_guild_raids,
                last_updated_timestamp
            FROM members WHERE left_guild = 0
            """
        )

        rows = self.cursor.fetchall()

        return {row[0]:
            {
                "username": row[1],
                "guild_rank": row[2],
                "last_online": row[3],
                "playtime": row[4],
                "weekly": row[5],
                "weekly_streak": row[6],
                "contributed": row[7],
                "contribution_rank": row[8],
                "joined_guild": row[9],
                "left_guild": row[10],
                "total_guild_raids": row[11],
                "last_updated_timestamp": row[12],
            }
            for row in rows
        }


    def fetch_member(self, uuid: str) -> dict | None:
        self.cursor.execute(
            """
            SELECT
                uuid,
                username,
                guild_rank,
                last_online,
                playtime,
                weekly,
                weekly_streak,
                contributed,
                contribution_rank,
                joined_guild,
                left_guild,
                total_guild_raids,
                last_updated_timestamp
            FROM members
            WHERE uuid = ?
            """,
            (uuid,)
        )

        row = self.cursor.fetchone()

        if row is None:
            return None

        return {
            "uuid": row[0],
            "username": row[1],
            "guild_rank": row[2],
            "last_online": row[3],
            "playtime": row[4],
            "weekly": row[5],
            "weekly_streak": row[6],
            "contributed": row[7],
            "contribution_rank": row[8],
            "joined_guild": row[9],
            "left_guild": row[10],
            "total_guild_raids": row[11],
            "last_updated_timestamp": row[12],
        }


    # MEMBER GUILD RAIDS

    def fetch_all_member_guild_raids(self) -> dict[str, dict]:
        self.cursor.execute(
            """
            SELECT
                uuid,
                total,
                notg,
                nol,
                tcc,
                tna,
                wtp,
                aspects,
                next_aspect,
                latest_timestamp
            FROM member_guild_raids
            """
        )

        rows = self.cursor.fetchall()

        return {row[0]:
            {
                "total": row[1],
                "notg": row[2],
                "nol": row[3],
                "tcc": row[4],
                "tna": row[5],
                "wtp": row[6],
                "aspects": row[7],
                "next_aspect": row[8],
                "latest_timestamp": row[9],
            }
            for row in rows
        }


    def fetch_member_guild_raids(self, uuid: str) -> dict:
        self.cursor.execute(
            """
            SELECT
                uuid,
                total,
                notg,
                nol,
                tcc,
                tna,
                wtp,
                aspects,
                next_aspect,
                latest_timestamp
            FROM member_guild_raids
            WHERE uuid = ?
            """,
            (uuid,)
        )

        row = self.cursor.fetchone()

        if row is None:
            return {
            "uuid": uuid,
            "total": 0,
            "notg": 0,
            "nol": 0,
            "tcc": 0,
            "tna": 0,
            "wtp": 0,
            "aspects": 0,
            "next_aspect": 0,
            "latest_timestamp": 0,
        }

        return {
            "uuid": row[0],
            "total": row[1],
            "notg": row[2],
            "nol": row[3],
            "tcc": row[4],
            "tna": row[5],
            "wtp": row[6],
            "aspects": row[7],
            "next_aspect": row[8],
            "latest_timestamp": row[9],
        }


    # GUILD RAID HISTORY

    def fetch_all_guild_raid_history(self) -> list[dict]:
        self.cursor.execute(
            """
            SELECT
                id,
                raid,
                party_member1,
                party_member2,
                party_member3,
                party_member4,
                timestamp
            FROM guild_raid_history
            ORDER BY timestamp DESC
            """
        )

        rows = self.cursor.fetchall()

        return [
            {
                "id": row[0],
                "raid": row[1],
                "party_member1": row[2],
                "party_member2": row[3],
                "party_member3": row[4],
                "party_member4": row[5],
                "timestamp": row[6],
            }
            for row in rows
        ]



    #TODO: ADD ALL OTHER FUNCTIONS FOR THIS THING
    #CHORE: AAAAAAAAAAAAAAAARHG
    # I think I have to escalate this to it's own file
    # If I were to add bot logic in here it might get crowded
    # We'll see ig


class APIMember:
    def __init__(self, member, memberdata, rank):
        self.uuid = member
        self.username = memberdata['username']
        self.guild_rank = rank

        self.aspects = None
        self.next_aspect = None
        if not memberdata['lastJoin'] is None:
            self.last_online = int(datetime.datetime.fromisoformat(memberdata['lastJoin'].replace("Z", "+00:00")).timestamp())
        else:
            self.last_online = 0
        
        if not memberdata['restrictions']['main_access']:
            self.playtime = memberdata['globalData']['playtime']
            self.total_guild_raids = memberdata['globalData']['guildRaids']['total']
            self.notg_completions = memberdata['globalData']['guildRaids']['list']['Nest of the Grootslangs']
            self.nol_completions = memberdata['globalData']['guildRaids']['list']["Orphion's Nexus of Light"]
            self.tcc_completions = memberdata['globalData']['guildRaids']['list']['The Canyon Colossus']
            self.tna_completions = memberdata['globalData']['guildRaids']['list']['The Nameless Anomaly']
            self.wtp_completions = memberdata['globalData']['guildRaids']['list']['The Wartorn Palace']
        else:
            self.playtime = None
            self.total_guild_raids = None
            self.notg_completions = None
            self.nol_completions = None
            self.tcc_completions = None
            self.tna_completions = None
            self.wtp_completions = None
        
        if not memberdata['restrictions']['weekly_access']:
            self.weekly = memberdata['weekly']['completed']
            self.weekly_streak = memberdata['weekly']['streak']
        else:
            self.weekly = None
            self.weekly_streak = None
        
        self.contributed = memberdata['contributed']
        self.contribution_rank = memberdata['contributionRank']
        self.joined_guild = int(datetime.datetime.fromisoformat(memberdata['joined'].replace("Z", "+00:00")).timestamp())
        self.left_guild = 0

    def update_member_database(self):
        db.update_members(self.uuid, self.username, self.guild_rank, self.last_online, self.playtime, self.weekly, self.weekly_streak, self.contributed, self.contribution_rank, self.joined_guild, self.left_guild, self.total_guild_raids)

    def update_member_guild_raids(self):
        db.update_member_guild_raids(self.uuid, self.total_guild_raids, self.notg_completions, self.nol_completions, self.tcc_completions, self.tna_completions, self.wtp_completions, self.aspects, self.next_aspect)



def get_completed_graids(member: APIMember):
    prev_graids_result = db.fetch_member_guild_raids(member.uuid)
    prev_graids: list[int] = [prev_graids_result[raid] for raid in ['notg', 'nol', 'tcc', 'tna', 'wtp']]
    current_graids_result: list[int | None] = [member.notg_completions, member.nol_completions, member.tcc_completions, member.tna_completions, member.wtp_completions].copy()
    current_graids: list[int] = []
    for i, graid in enumerate(current_graids_result):
        if graid is None:
            current_graids.append(0)
        else:
            current_graids.append(graid)
    completed_graids = [current_graid - prev_graids[i] for i, current_graid in enumerate(current_graids)]

    new_aspects = sum(completed_graids)
    new_aspects += prev_graids_result["next_aspect"]

    aspect_to_carry_over = new_aspects % 2 #Amount of raids to complete for next aspect reward

    aspects_to_reward = new_aspects // 2

    db.update_member_guild_raids(member.uuid, aspects=aspects_to_reward, next_aspect=aspect_to_carry_over)


    completed_graids_dict = {
        'notg': completed_graids[0],
        'nol': completed_graids[1],
        'tcc': completed_graids[2],
        'tna': completed_graids[3],
        'wtp': completed_graids[4]
    }

    to_pop = []
    for graid, amount in completed_graids_dict.items():
        if amount == 0:
            to_pop.append(graid)
    for raid in to_pop:
        completed_graids_dict.pop(raid)
    return completed_graids_dict



class APIQueries(commands.Cog):
    def __init__(self, passed_bot):
        self.bot = passed_bot
    
    @app_commands.command(name="set_graid_channel")
    async def set_channel_for_graids(self, interaction: discord.Interaction, channel:discord.TextChannel, role: discord.Role):
        role_id = db.get_meta('api_queries_role_id')
        if not role_id is None:
            if interaction.user.get_role(int(role_id)) is None: # type: ignore pylint: disable=line-too-long
                return await interaction.response.send_message(
                    content="You don't have permission to use this command"
                    )
        db.set_meta('graid_message_channel', str(channel.id))
        db.set_meta('guild_id', str(channel.guild))
        db.set_meta('api_queries_role_id', str(role.id))
        await interaction.response.send_message(content='channel and role set!', ephemeral=True)
    
    @app_commands.command(name="test_graids")
    async def fetch_guild_endpoint(self, interaction: discord.Interaction):
        data = {
  "uuid": "bb5dacca-9ed4-4018-8b17-70a931ee6ddb",
  "name": "The Gambling Addicts",
  "prefix": "TGAS",
  "level": 72,
  "xpPercent": 65,
  "territories": 0,
  "wars": 10657,
  "raids": 2843,
  "created": "2025-06-08T10:12:28.745000Z",
  "members": {
    "total": 78,
    "owner": {
      "6b9f8102-9942-4870-a570-424a6f8cba1a": {
        "username": "DarkerGEN",
        "legacyName": "DarkerGEN",
        "online": True,
        "lastJoin": "2026-05-11T17:46:36.035000Z",
        "server": "EU37",
        "contributed": 1512228101,
        "contributionRank": 1,
        "joined": "2026-02-13T14:11:06.020000Z",
        "weekly": {},
        "globalData": {
          "contentCompletion": 2626,
          "wars": 674,
          "totalLevel": 2253,
          "mobsKilled": 356450,
          "chestsFound": 6100,
          "dungeons": {
            "total": 99,
            "list": {
              "Decrepit Sewers": 35,
              "Infested Pit": 5,
              "Galleon's Graveyard": 3,
              "Ice Barrows": 2,
              "Undergrowth Ruins": 5,
              "Timelost Sanctum": 1,
              "Underworld Crypt": 1,
              "Sand-Swept Tomb": 1,
              "Corrupted Sand-Swept Tomb": 1,
              "Corrupted Ice Barrows": 7,
              "Corrupted Galleon's Graveyard": 2,
              "Eldritch Outlook": 8,
              "Corrupted Infested Pit": 15,
              "Corrupted Decrepit Sewers": 5,
              "Corrupted Lost Sanctuary": 6,
              "Fallen Factory": 2
            }
          },
          "raids": {
            "total": 253,
            "list": {
              "The Canyon Colossus": 74,
              "Nest of the Grootslangs": 151,
              "The Nameless Anomaly": 18,
              "Orphion's Nexus of Light": 10
            }
          },
          "worldEvents": 23,
          "lootruns": 5,
          "caves": 155,
          "completedQuests": 176,
          "raidStats": {
            "damageTaken": 18177436,
            "damageDealt": 1746451163,
            "healthHealed": 75937169,
            "deaths": 260,
            "buffsTaken": 681,
            "gambitsUsed": 241
          },
          "pvp": {
            "kills": 0,
            "deaths": 0
          },
          "guildRaids": {
            "total": 69,
            "list": {
              "The Canyon Colossus": 16,
              "Orphion's Nexus of Light": 7,
              "Nest of the Grootslangs": 38,
              "The Nameless Anomaly": 8,
              "The Wartorn Palace": 0
            }
          },
          "playtime": 1791.75
        },
        "restrictions": {
          "online_status": False,
          "main_access": False,
          "weekly_access": True
        }
      }
    },
    "chief": {},
    "strategist": {
      "02ef6488-a20e-43a0-b539-7e1012f2e8d3": {
        "username": "Wardje2008",
        "legacyName": "Wardje2008",
        "online": False,
        "lastJoin": "2026-05-10T19:45:32.778000Z",
        "server": None,
        "contributed": 1476549086,
        "contributionRank": 2,
        "joined": "2026-02-13T20:23:06.147000Z",
        "weekly": {},
        "globalData": {
          "contentCompletion": 2775,
          "wars": 961,
          "totalLevel": 1707,
          "mobsKilled": 322531,
          "chestsFound": 2776,
          "dungeons": {
            "total": 143,
            "list": {
              "Decrepit Sewers": 28,
              "Infested Pit": 24,
              "Underworld Crypt": 21,
              "Ice Barrows": 5,
              "Corrupted Sand-Swept Tomb": 6,
              "Timelost Sanctum": 5,
              "Galleon's Graveyard": 3,
              "Sand-Swept Tomb": 17,
              "Undergrowth Ruins": 3,
              "Corrupted Infested Pit": 3,
              "Fallen Factory": 1,
              "Eldritch Outlook": 8,
              "Corrupted Decrepit Sewers": 2,
              "Corrupted Lost Sanctuary": 3,
              "Corrupted Underworld Crypt": 2,
              "Corrupted Ice Barrows": 6,
              "Corrupted Undergrowth Ruins": 2,
              "Corrupted Galleon's Graveyard": 4
            }
          },
          "raids": {
            "total": 237,
            "list": {
              "Orphion's Nexus of Light": 25,
              "Nest of the Grootslangs": 178,
              "The Canyon Colossus": 26,
              "The Nameless Anomaly": 7,
              "The Wartorn Palace": 1
            }
          },
          "worldEvents": 72,
          "lootruns": 6,
          "caves": 235,
          "completedQuests": 245,
          "raidStats": {
            "damageTaken": 19061121,
            "damageDealt": 1097952262,
            "healthHealed": 347984898,
            "deaths": 103,
            "buffsTaken": 694,
            "gambitsUsed": 211
          },
          "pvp": {
            "kills": 0,
            "deaths": 0
          },
          "guildRaids": {
            "total": 58,
            "list": {
              "The Canyon Colossus": 4,
              "Orphion's Nexus of Light": 5,
              "Nest of the Grootslangs": 45,
              "The Nameless Anomaly": 4,
              "The Wartorn Palace": 0
            }
          },
          "playtime": 1043.67
        },
        "restrictions": {
          "online_status": False,
          "main_access": False,
          "weekly_access": True
        }
      },
      "a60e592b-cee5-4708-a729-7e7b49e32455": {
        "username": "MrDafty18",
        "legacyName": "MrDafty18",
        "online": False,
        "lastJoin": "2026-05-07T13:49:37.987000Z",
        "server": None,
        "contributed": 214543420,
        "contributionRank": 11,
        "joined": "2026-03-24T17:44:38.922000Z",
        "weekly": {},
        "globalData": {
          "contentCompletion": 900,
          "wars": 0,
          "totalLevel": 650,
          "mobsKilled": 104150,
          "chestsFound": 1805,
          "dungeons": {
            "total": 9,
            "list": {
              "Underworld Crypt": 4,
              "Corrupted Sand-Swept Tomb": 4,
              "Eldritch Outlook": 1
            }
          },
          "raids": {
            "total": 134,
            "list": {
              "The Canyon Colossus": 31,
              "Orphion's Nexus of Light": 13,
              "The Nameless Anomaly": 10,
              "Nest of the Grootslangs": 78,
              "The Wartorn Palace": 2
            }
          },
          "worldEvents": 15,
          "lootruns": 4,
          "caves": 54,
          "completedQuests": 41,
          "raidStats": {
            "damageTaken": 10549729,
            "damageDealt": 932703577,
            "healthHealed": 56294381,
            "deaths": 97,
            "buffsTaken": 347,
            "gambitsUsed": 214
          },
          "pvp": {
            "kills": 0,
            "deaths": 0
          },
          "guildRaids": {
            "total": 40,
            "list": {
              "The Canyon Colossus": 11,
              "Orphion's Nexus of Light": 1,
              "Nest of the Grootslangs": 27,
              "The Nameless Anomaly": 1,
              "The Wartorn Palace": 0
            }
          },
          "playtime": 245
        },
        "restrictions": {
          "online_status": False,
          "main_access": False,
          "weekly_access": True
        }
      }
    },
    "captain": {
      "81cb3734-1397-45d7-a98f-46e4e14e3cca": {
        "username": "JUNI_0",
        "legacyName": "JUNI_0",
        "online": False,
        "lastJoin": "2026-05-10T04:20:06.177000Z",
        "server": None,
        "contributed": 598862494,
        "contributionRank": 4,
        "joined": "2025-06-13T13:41:38.124000Z",
        "weekly": {},
        "globalData": {
          "contentCompletion": 2280,
          "wars": 157,
          "totalLevel": 1630,
          "mobsKilled": 366371,
          "chestsFound": 4682,
          "dungeons": {
            "total": 134,
            "list": {
              "Decrepit Sewers": 29,
              "Underworld Crypt": 9,
              "Timelost Sanctum": 6,
              "Infested Pit": 33,
              "Eldritch Outlook": 4,
              "Sand-Swept Tomb": 4,
              "Ice Barrows": 3,
              "Undergrowth Ruins": 7,
              "Galleon's Graveyard": 2,
              "Fallen Factory": 2,
              "Corrupted Sand-Swept Tomb": 8,
              "Corrupted Galleon's Graveyard": 6,
              "Corrupted Lost Sanctuary": 11,
              "Corrupted Decrepit Sewers": 6,
              "Corrupted Infested Pit": 1,
              "Corrupted Underworld Crypt": 1,
              "Corrupted Ice Barrows": 1,
              "Corrupted Undergrowth Ruins": 1
            }
          },
          "raids": {
            "total": 390,
            "list": {
              "Nest of the Grootslangs": 229,
              "The Canyon Colossus": 104,
              "Orphion's Nexus of Light": 29,
              "The Nameless Anomaly": 28
            }
          },
          "worldEvents": 45,
          "lootruns": 3,
          "caves": 141,
          "completedQuests": 119,
          "raidStats": {
            "damageTaken": 52838319,
            "damageDealt": 2570688289,
            "healthHealed": 1347017024,
            "deaths": 99,
            "buffsTaken": 1093,
            "gambitsUsed": 920
          },
          "pvp": {
            "kills": 0,
            "deaths": 0
          },
          "guildRaids": {
            "total": 141,
            "list": {
              "The Canyon Colossus": 42,
              "Orphion's Nexus of Light": 6,
              "Nest of the Grootslangs": 85,
              "The Nameless Anomaly": 8,
              "The Wartorn Palace": 0
            }
          },
          "playtime": 667.17
        },
        "restrictions": {
          "online_status": False,
          "main_access": False,
          "weekly_access": True
        }
      },
      "df3e130e-5619-4a82-91c0-163dc952877c": {
        "username": "Jacobs0811",
        "legacyName": "Jacobs0811",
        "online": False,
        "lastJoin": "2026-05-10T21:11:42.088000Z",
        "server": None,
        "contributed": 433225031,
        "contributionRank": 6,
        "joined": "2026-02-13T20:25:13.542000Z",
        "weekly": {},
        "globalData": {
          "contentCompletion": 2269,
          "wars": 278,
          "totalLevel": 1067,
          "mobsKilled": 172431,
          "chestsFound": 1917,
          "dungeons": {
            "total": 169,
            "list": {
              "Decrepit Sewers": 25,
              "Underworld Crypt": 31,
              "Ice Barrows": 4,
              "Infested Pit": 50,
              "Sand-Swept Tomb": 5,
              "Undergrowth Ruins": 7,
              "Timelost Sanctum": 3,
              "Galleon's Graveyard": 1,
              "Fallen Factory": 1,
              "Corrupted Infested Pit": 5,
              "Corrupted Lost Sanctuary": 5,
              "Eldritch Outlook": 8,
              "Corrupted Decrepit Sewers": 5,
              "Corrupted Underworld Crypt": 3,
              "Corrupted Sand-Swept Tomb": 4,
              "Corrupted Ice Barrows": 5,
              "Corrupted Undergrowth Ruins": 3,
              "Corrupted Galleon's Graveyard": 4
            }
          },
          "raids": {
            "total": 163,
            "list": {
              "Nest of the Grootslangs": 151,
              "The Canyon Colossus": 4,
              "Orphion's Nexus of Light": 2,
              "The Nameless Anomaly": 3,
              "The Wartorn Palace": 3
            }
          },
          "worldEvents": 47,
          "lootruns": 2,
          "caves": 257,
          "completedQuests": 217,
          "raidStats": {
            "damageTaken": 10996120,
            "damageDealt": 476127902,
            "healthHealed": 148582396,
            "deaths": 38,
            "buffsTaken": 483,
            "gambitsUsed": 199
          },
          "pvp": {
            "kills": 0,
            "deaths": 0
          },
          "guildRaids": {
            "total": 52,
            "list": {
              "The Canyon Colossus": 4,
              "Orphion's Nexus of Light": 0,
              "Nest of the Grootslangs": 47,
              "The Nameless Anomaly": 1,
              "The Wartorn Palace": 0
            }
          },
          "playtime": 625.67
        },
        "restrictions": {
          "online_status": False,
          "main_access": False,
          "weekly_access": True
        }
      },
    }
  },
  "online": 2,
  "banner": {
    "base": "BLUE",
    "tier": 6,
    "structure": "futuristicBanner2",
    "layers": [
      {
        "colour": "WHITE",
        "pattern": "CIRCLE_MIDDLE"
      },
      {
        "colour": "LIGHT_BLUE",
        "pattern": "GRADIENT_UP"
      },
      {
        "colour": "BLACK",
        "pattern": "GRADIENT"
      },
      {
        "colour": "BLACK",
        "pattern": "TRIANGLES_BOTTOM"
      },
      {
        "colour": "BLACK",
        "pattern": "SQUARE_BOTTOM_LEFT"
      }
    ]
  },
  "seasonRanks": {
    "25": {
      "rating": 125850,
      "finalTerritories": 0
    },
    "26": {
      "rating": 594306,
      "finalTerritories": 0
    },
    "27": {
      "rating": 824897,
      "finalTerritories": 0
    },
    "28": {
      "rating": 1784365,
      "finalTerritories": 9
    },
    "29": {
      "rating": 388966,
      "finalTerritories": 0
    },
    "30": {
      "rating": 31308,
      "finalTerritories": 0
    }
  },
  "ranking": {
    "grootslangSrGuilds": 52,
    "orphionSrGuilds": 58,
    "guildTotalRaids": 61,
    "namelessSrGuilds": 65,
    "colossusSrGuilds": 73
  }
}
        await interaction.response.defer()
        #TODO: implement guild global data handling
        previous_members = db.fetch_all_current_members()
        completed_graids: dict[str, dict[str, int]] = {
            "notg": {},
            "nol": {},
            "tcc": {},
            "tna": {},
            "wtp": {},
        }
        for rank, rank_members in data['members'].items():
            if not rank in {"owner", "chief", "strategist", "captain", "recruiter", "recruit"}: # all guild ranks, will need updating in case of update
                continue
            for guild_member, member_data in rank_members.items():
                member = APIMember(guild_member, member_data, rank)
                if previous_members.get(guild_member) is None:
                    member.update_member_database()
                    member.update_member_guild_raids()
                    continue
                if previous_members[guild_member]['total_guild_raids'] < member.total_guild_raids:
                    player_completed_raids = get_completed_graids(member)
                    for raid, amount in player_completed_raids.items():
                        completed_graids[raid][member.uuid] = amount
                    member.update_member_guild_raids()
                member.update_member_database()

        guild = interaction.guild
        if not guild is None:
            await send_discord_graids_completed_message(completed_graids=completed_graids, guild=guild)
            await interaction.followup.send("it worked!")
        else:
            return



async def send_discord_graids_completed_message(completed_graids: dict[str, dict[str, int]], guild: discord.Guild):
    channel_id: int = int(db.get_meta("graid_message_channel")) #type: ignore
    channel = guild.get_channel(channel_id)
    if channel is None:
        return
    if isinstance(channel, (discord.ForumChannel, discord.CategoryChannel)):
        return

    embeds = []
    for raid, players in completed_graids.items():
        description = ""
        image = None
        colour = discord.Color.default()
        raid_name = raid
        if not len(players) > 0:
            continue
        for player, amount in players.items():
            playerdata = db.fetch_member(player)
            if not playerdata is None:
                username: str = playerdata['username']
                name = guild.get_member_named(username) if not guild is None else None
                playername = name.mention if not name is None else username
            else:
                username = player
                playername = player
            spaces_amount = 16 - len(username)
            spaces = " " * spaces_amount
            player_description = "".join((f'{playername}\u200b', spaces, f' | {amount}'))
            description = f'{description}\n{player_description}'
            match raid:
                case "notg":
                    image = "https://cdn.wynncraft.com/nextgen/raids/Nest%20of%20the%20Grootslangs.webp"
                    colour = discord.Color.dark_green()
                    raid_name = "Nest of the Grootslangs"
                case "nol":
                    image = "https://cdn.wynncraft.com/nextgen/raids/Orphion's%20Nexus%20of%20Light.webp"
                    colour = discord.Color.yellow()
                    raid_name = "Orphion's Nexus of Light"
                case "tcc":
                    image = "https://cdn.wynncraft.com/nextgen/raids/The%20Canyon%20Colossus.webp"
                    colour = discord.Color.blue()
                    raid_name = "The Canyon Colossus"
                case "tna":
                    image = "https://cdn.wynncraft.com/nextgen/raids/The%20Nameless%20Anomaly.webp"
                    colour = discord.Color.dark_purple()
                    raid_name = "The Nameless Anomaly"
                case "wtp":
                    image = "https://cdn.wynncraft.com/nextgen/raids/The%20Wartorn%20Palace.webp"
                    colour = discord.Color.brand_red()
                    raid_name = "The Wartorn Palace"
        embed = discord.Embed(title=raid_name, description=description, colour=colour, timestamp=datetime.datetime.now())
        embed.set_thumbnail(url=image)

        #commented out till this can be cleared using the api, manual command would be too cumbersome
        """aspect_reward_string = ""
        half_aspects_string = ""
        guild_raids_from_db = db.fetch_all_member_guild_raids()
        for member, data in guild_raids_from_db.items():
            playerdata = db.fetch_member(member)
            if not playerdata is None:
                username: str = playerdata['username']
                name = guild.get_member_named(username) if not guild is None else None
                playername = name.mention if not name is None else username
            else:
                username = member
                playername = member
            if data["aspects"] > 0:
                aspect_reward_string = f'{aspect_reward_string}\n{playername} | {data["aspects"]}'
            if data["next_aspect"] > 0:
                half_aspects_string = f'{half_aspects_string}\n{playername}'
                


        embed.add_field(name="aspects to reward", value=aspect_reward_string)
        embed.add_field(name="needs to complete another raid\nto get an aspect", value=half_aspects_string)"""


        embeds.append(embed)
    
    if len(embeds) > 0:
        await channel.send(embeds=embeds)






@tasks.loop(minutes=2)
async def fetch_guild_endpoint():
    data = api_handler.get_endpoint_data(api_handler.construct_guild_endpoint_url())

    #TODO: implement guild global data handling
    previous_members = db.fetch_all_current_members()
    completed_graids: dict[str, dict[str, int]] = {
        "notg": {},
        "nol": {},
        "tcc": {},
        "tna": {},
        "wtp": {},
    }
    for rank, rank_members in data['members'].items():
        if not rank in {"owner", "chief", "strategist", "captain", "recruiter", "recruit"}: # all guild ranks, will need updating in case of update
            continue
        for guild_member, member_data in rank_members.items():
            member = APIMember(guild_member, member_data, rank)
            if previous_members.get(guild_member) is None:
                member.update_member_database()
                member.update_member_guild_raids()
                continue
            if previous_members[guild_member]['total_guild_raids'] < member.total_guild_raids:
                player_completed_raids = get_completed_graids(member)
                for raid, amount in player_completed_raids.items():
                    completed_graids[raid][member.uuid] = amount
                member.update_member_guild_raids()
            member.update_member_database()
        
        guild_id: int = int(db.get_meta("guild_id")) #type: ignore
        guild = bot.get_guild(guild_id)
        if guild is None:
            return
        await send_discord_graids_completed_message(completed_graids=completed_graids, guild=guild)












def main():
    global api_handler, db
    api_handler = APIHandler()
    db = DataBaseHandler()

    



async def setup(global_bot):
    main()
    await global_bot.add_cog(APIQueries(bot))

    

if __name__ == '__main__':
    main()
    #print(api_handler.get_endpoint_data("https://api.wynncraft.com/v3/player/Jacobs0811?fullResult"))
    #api_handler.dump_endpoint_data(api_handler.construct_guild_endpoint_url())
    test = fetch_guild_endpoint()

