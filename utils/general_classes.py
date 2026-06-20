import datetime


class APIMember:
    def __init__(self, member, memberdata, rank, db):
        self.uuid = member
        self.username = memberdata['username']
        self.guild_rank = rank
        self.db = db

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
            self.playtime = None
            self.total_guild_raids = None
            self.notg_completions = None
            self.nol_completions = None
            self.tcc_completions = None
            self.tna_completions = None
            self.wtp_completions = None
            self.wars = None
        
        if not memberdata['restrictions']['guild_high_ranked_access']:
            self.weekly = memberdata['weekly']['completed']
            self.weekly_streak = memberdata['weekly']['streak']
        else:
            self.weekly = None
            self.weekly_streak = None
        
        self.contributed = memberdata['contributed']
        self.contribution_rank = memberdata['contributionRank']
        self.joined_guild = datetime.datetime.fromisoformat(memberdata['joined'].replace("Z", "+00:00"))
        self.left_guild = False

    def update_member_database(self):
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
                'total_guild_raids': self.total_guild_raids,
                'wars': self.wars
            })

    def update_member_guild_raids(self):
        self.db.update(
            'uuid',
            self.uuid,
            columns={
                'total': self.total_guild_raids,
                'notg': self.notg_completions,
                'nol': self.nol_completions,
                'tcc': self.tcc_completions,
                'tna': self.tna_completions,
                'wtp': self.wtp_completions,
            })