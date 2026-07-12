import datetime
import utils.database as db


class APIMember:
    def __init__(self, member, memberdata, rank, database: db.UpdatingTable):
        self.uuid = member
        self.username = memberdata['username']
        self.guild_rank = rank
        self.db = database

        if not memberdata['lastJoin'] is None:
            self.last_online = datetime.datetime.fromisoformat(memberdata['lastJoin'].replace("Z", "+00:00"))
        else:
            self.last_online = 0
        
        if not memberdata['restrictions']['main_access']:
            self.playtime = memberdata['globalData']['playtime']
            self.total_guild_raids = memberdata['globalData']['currentGuildRaids']['total']
            self.notg_completions = memberdata['globalData']['currentGuildRaids']['list']['Nest of the Grootslangs']
            self.nol_completions = memberdata['globalData']['currentGuildRaids']['list']["Orphion's Nexus of Light"]
            self.tcc_completions = memberdata['globalData']['currentGuildRaids']['list']['The Canyon Colossus']
            self.tna_completions = memberdata['globalData']['currentGuildRaids']['list']['The Nameless Anomaly']
            self.wtp_completions = memberdata['globalData']['currentGuildRaids']['list']['The Wartorn Palace']
            self.wars = memberdata['globalData'].get('wars', 0)
        else:
            self.playtime = 0
            self.total_guild_raids = 0
            self.notg_completions = 0
            self.nol_completions = 0
            self.tcc_completions = 0
            self.tna_completions = 0
            self.wtp_completions = 0
            self.wars = 0
        
        if not memberdata['restrictions']['guild_high_ranked_access']:
            self.weekly = memberdata['weekly']['completed']
            self.weekly_streak = memberdata['weekly']['streak']
        else:
            self.weekly = 0
            self.weekly_streak = 0
        
        self.contributed = memberdata['contributed']
        self.contribution_rank = memberdata['contributionRank']
        self.joined_guild = datetime.datetime.fromisoformat(memberdata['joined'].replace("Z", "+00:00"))
        self.left_guild = False

    def update_member_database(self):
        prev_db_res = self.db.fetchone('uuid', self.uuid)
        if not prev_db_res is None:
            prev_total_graids: int = prev_db_res['total_guild_raids']
            prev_total_wars: int = prev_db_res['wars']
        else:
            prev_total_graids = 0
            prev_total_wars = 0

        self.db.update(
            'uuid',
            self.uuid,
            columns={
                'username': self.username,
                'guild_rank': self.guild_rank,
                'last_seen': self.last_online,
                'playtime': self.playtime,
                'weekly': self.weekly,
                'weekly_streak': self.weekly_streak,
                'contributed': self.contributed,
                'contribution_rank': self.contribution_rank,
                'joined_guild': self.joined_guild,
                'left_guild': self.left_guild,
                'total_guild_raids': self.total_guild_raids if prev_total_graids <= self.total_guild_raids else prev_total_graids,
                'wars': self.wars if prev_total_wars <= self.wars else prev_total_wars
            })

    def update_member_guild_raids(self):
        prev_db_res = self.db.fetchone('uuid', self.uuid)
        if not prev_db_res is None:
            total: int = prev_db_res['total'] if not prev_db_res['total'] is None else 0
            notg: int = prev_db_res['notg'] if not prev_db_res['notg'] is None else 0
            nol: int = prev_db_res['nol'] if not prev_db_res['nol'] is None else 0
            tcc: int = prev_db_res['tcc'] if not prev_db_res['tcc'] is None else 0
            tna: int = prev_db_res['tna'] if not prev_db_res['tna'] is None else 0
            wtp: int = prev_db_res['wtp'] if not prev_db_res['wtp'] is None else 0
        else:
            total = 0
            notg = 0
            nol = 0
            tcc = 0
            tna = 0
            wtp = 0
        self.db.update(
            'uuid',
            self.uuid,
            columns={
                'total': self.total_guild_raids if total <= self.total_guild_raids else 0,
                'notg': self.notg_completions if notg <= self.notg_completions else 0,
                'nol': self.nol_completions if nol <= self.nol_completions else 0,
                'tcc': self.tcc_completions if tcc <= self.tcc_completions else 0,
                'tna': self.tna_completions if tna <= self.tna_completions else 0,
                'wtp': self.wtp_completions if wtp <= self.wtp_completions else 0,
            })
