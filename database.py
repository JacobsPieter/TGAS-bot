import sqlite3
import datetime


class Database:

    def __init__(self, path="database.db"):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        self._create_tables()

    def _create_tables(self):

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS members (
            uuid TEXT PRIMARY KEY,
            username TEXT,
            contribution INTEGER,
            last_updated INTEGER
        )
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS contribution_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT,
            contribution INTEGER,
            timestamp INTEGER
        )
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS raid_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT,
            raid_name TEXT,
            completions INTEGER,
            timestamp INTEGER
        )
        """)

        self.conn.commit()


    def update_member_contribution(self, uuid, username, new_contribution):

        now = int(datetime.datetime.now().timestamp())

        self.cursor.execute(
            "SELECT contribution FROM members WHERE uuid = ?",
            (uuid,)
        )

        row = self.cursor.fetchone()

        if row is None:
            # new member

            self.cursor.execute("""
            INSERT INTO members (uuid, username, contribution, last_updated)
            VALUES (?, ?, ?, ?)
            """, (uuid, username, new_contribution, now))

            self.cursor.execute("""
            INSERT INTO contribution_history (uuid, contribution, timestamp)
            VALUES (?, ?, ?)
            """, (uuid, new_contribution, now))

        else:
            old_contribution = row["contribution"]

            if new_contribution != old_contribution:

                self.cursor.execute("""
                UPDATE members
                SET contribution = ?, last_updated = ?
                WHERE uuid = ?
                """, (new_contribution, now, uuid))

                self.cursor.execute("""
                INSERT INTO contribution_history (uuid, contribution, timestamp)
                VALUES (?, ?, ?)
                """, (uuid, new_contribution, now))

        self.conn.commit()

    def get_latest_contribution(self, uuid):

        self.cursor.execute("""
        SELECT contribution
        FROM contribution_history
        WHERE uuid = ?
        ORDER BY timestamp DESC
        LIMIT 1
        """, (uuid,))

        row = self.cursor.fetchone()

        if row:
            return row["contribution"]

        return None



    def update_raid_stat(self, uuid, raid_name, completions):

        now = int(datetime.datetime.now().timestamp())

        self.cursor.execute("""
        SELECT completions
        FROM raid_history
        WHERE uuid = ? AND raid_name = ?
        ORDER BY timestamp DESC
        LIMIT 1
        """, (uuid, raid_name))

        row = self.cursor.fetchone()

        if row is None or row["completions"] != completions:

            self.cursor.execute("""
            INSERT INTO raid_history (uuid, raid_name, completions, timestamp)
            VALUES (?, ?, ?, ?)
            """, (uuid, raid_name, completions, now))

            self.conn.commit()

    


    def get_latest_raid_completions(self, uuid, raid_name):
        self.cursor.execute("""
        SELECT completions
        FROM raid_history
        WHERE uuid = ? AND raid_name = ?
        ORDER BY timestamp DESC
        LIMIT 1
        """, (uuid, raid_name))

        row = self.cursor.fetchone()

        if row:
            return row["completions"]

        return None