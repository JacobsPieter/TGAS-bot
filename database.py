"""
Database module for Wynncraft Guild Discord Bot

Provides a SQLite database interface for storing and managing guild member data,
contribution history, and raid completion statistics. This module handles all
database operations including member tracking, contribution monitoring, and
raid statistics management.

The database consists of three main tables:
- members: Current member information (UUID, username, contribution, last_updated)
- contribution_history: Historical contribution changes for tracking progress
- raid_history: Raid completion statistics for each member

Usage:
    db = Database("path/to/database.db")
    db.update_member_contribution(uuid, username, contribution)
    latest_contribution = db.get_latest_contribution(uuid)
"""

import sqlite3
import datetime


class Database:
    """
    A database manager for storing and managing guild member data,
    contribution history, and raid completion statistics.
    
    This class provides an interface to a SQLite database with three main tables:
    - members: Stores current member information including UUID, username, and contribution
    - contribution_history: Tracks historical contribution changes for each member
    - raid_history: Records raid completion statistics for each member
    
    Attributes:
        conn (sqlite3.Connection): SQLite database connection
        cursor (sqlite3.Cursor): Database cursor for executing queries
    """

    def __init__(self, path="database.db"):
        """
        Initialize the database connection and create required tables.
        
        Args:
            path (str, optional): Path to the SQLite database file. Defaults to "database.db".
        """
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        self._create_tables()

    def _create_tables(self):
        """
        Create the required database tables if they don't already exist.
        
        Creates three tables:
        - members: Stores current member information
        - contribution_history: Tracks historical contribution changes
        - raid_history: Records raid completion statistics
        """
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
        """
        Update a member's contribution and record the change in history.
        
        If the member doesn't exist, they are added to the database. If the contribution
        has changed from the previous value, both the current member record and the
        contribution history are updated.
        
        Args:
            uuid (str): The member's unique identifier
            username (str): The member's username
            new_contribution (int): The new contribution value
        """
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
        """
        Get the most recent contribution value for a member.
        
        Args:
            uuid (str): The member's unique identifier
            
        Returns:
            int: The latest contribution value, or 0 if no records exist
        """
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

        return 0



    def update_raid_stat(self, uuid, raid_name, completions):
        """
        Update a member's raid completion statistics.
        
        Only updates if the completion count has changed from the last recorded value.
        
        Args:
            uuid (str): The member's unique identifier
            raid_name (str): The name of the raid
            completions (int): The new completion count
        """
        now = int(datetime.datetime.now().timestamp())

        self.cursor.execute("""
        SELECT completions
        FROM raid_history
        WHERE uuid = ? AND raid_name = ?
        ORDER BY timestamp DESC
        LIMIT 1
        """, (uuid, raid_name))

        row = self.cursor.fetchone()

        if row is None or row["completions"] < completions:

            self.cursor.execute("""
            INSERT INTO raid_history (uuid, raid_name, completions, timestamp)
            VALUES (?, ?, ?, ?)
            """, (uuid, raid_name, completions, now))

            self.conn.commit()




    def get_latest_raid_completions(self, uuid, raid_name):
        """
        Get the most recent completion count for a specific raid by a member.
        
        Args:
            uuid (str): The member's unique identifier
            raid_name (str): The name of the raid
            
        Returns:
            int: The latest completion count, or 0 if no records exist
        """
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

        return 0
