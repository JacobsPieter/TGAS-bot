import sqlite3
from enum import Enum
import datetime
import threading


# TODO: Sanitize all SQL queries

class Database:

    # This one should get changed every time a new input type for elements into the database gets added
    type DBInputType = str | int | float | datetime.datetime | bool

    # This should not EVER get changed! It is specific to sqlite! These won't change NO MATTER WHAT I DO!
    type DBcolumnType = str | int | float | bytes

    def __init__(
            self,
            db_path: str = '.\\persistent_data\\api_results.db'
            ) -> None:
        
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.db_lock = threading.Lock()

    class DBKeyType(Enum):
        STR = "TEXT"
        INT = "INTEGER"
        FLOAT = "REAL"


    def convert_db_types(self, input_field: DBInputType) -> tuple[DBcolumnType, DBKeyType]:
        if isinstance(input_field, str):
            return input_field, self.DBKeyType.STR
        elif isinstance(input_field, int):
            return input_field, self.DBKeyType.INT
        elif isinstance(input_field, float):
            return input_field, self.DBKeyType.FLOAT
        elif isinstance(input_field, datetime.datetime):
            return input_field.timestamp(), self.DBKeyType.FLOAT
        elif isinstance(input_field, bool):
            return 1 if input_field else 0, self.DBKeyType.INT
        elif input_field is None:
            raise TypeError('Input cannot be Nonetype')
        else:
            raise TypeError()
    
    def convert_db_input_columns(self, columns: dict[str, DBInputType]) -> dict[str, DBcolumnType]:
        return {key: self.convert_db_types(value)[0] for key, value in columns.items()}
    
    def run_migrations(self):
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]

        if version < 1:
            try:
                self.conn.execute("""
                    ALTER TABLE members
                    ADD COLUMN requested_tome_received
                    INTEGER DEFAULT 1
                """)
            except sqlite3.OperationalError:
                pass
            self.conn.execute("PRAGMA user_version = 1")

        if version < 2:
            try:
                self.conn.execute("""
                    DROP TABLE meta
                """)
            except sqlite3.OperationalError:
                pass
            self.conn.execute("PRAGMA user_version = 2")

        self.conn.commit()



class Table(Database):
    def __init__(self, name: str, path) -> None:
        self.name = name
        super().__init__(path)
        self.columns: dict

    def _create_table(
            self,
            name: str,
            primary_key: tuple[str, Database.DBKeyType],
            columns: dict[str, Database.DBKeyType],
            autoincrement: bool = False
            ):
    
        creation_text: str = f"CREATE TABLE IF NOT EXISTS {name}"

        keys: list = []

        primary_key_column_text = f"{primary_key[0]} {primary_key[1].value} PRIMARY KEY{" AUTOINCREMENT" if autoincrement and primary_key[1] == self.DBKeyType.INT else ""}"
        keys.append(primary_key_column_text)

        for column_name, column_type in columns.items():
            column_text = f"{column_name} {column_type.value}"
            keys.append(column_text)

        table_creation_text = f"{creation_text} (\n    {",\n    ".join(keys)}\n)"

        self.cursor.execute(table_creation_text)
        
        return self
    
    
    def fetchall(self):
        query = f"SELECT * FROM {self.name}"

        self.cursor.execute(query)

        rows = self.cursor.fetchall()

        fetched_list = [{column_name: row[column_name] for column_name in row.keys()} for row in rows]

        return fetched_list
    

    def fetchcolumns(self, columns: list[str]):
        query = f"SELECT\n    {",\n    ".join([column for column in columns])}\nFROM {self.name}"

        self.cursor.execute(query)

        rows = self.cursor.fetchall()

        fetched_list = [{column_name: row[column_name] for column_name in row.keys()} for row in rows]

        return fetched_list


    def fetchall_conditional(self, condition: str):
        query = f"SELECT * FROM {self.name} WHERE {condition}"

        self.cursor.execute(query)

        rows = self.cursor.fetchall()

        fetched_list = [{column_name: row[column_name] for column_name in row.keys()} for row in rows]

        return fetched_list
    

    def fetchcolumns_conditional(self, columns: list[str], condition: str):
        query = f"SELECT\n    {",\n    ".join([column for column in columns])}\nFROM {self.name} WHERE {condition}"

        self.cursor.execute(query)

        rows = self.cursor.fetchall()

        fetched_list = [{column_name: row[column_name] for column_name in row.keys()} for row in rows]

        return fetched_list


class TrackingTable(Table):
    def __init__(self, name: str, path):
        super().__init__(name, path)
        self.name = name
   
    def create(
            self,
            columns: dict[str, Database.DBInputType]
            ):
        
        columns["timestamp"] = datetime.datetime.now()
        
        typed_columns: dict[str, Database.DBKeyType] = {}
        for column_name, column_type in columns.items():
            typed_columns[column_name] = self.convert_db_types(column_type)[1]
        
        return super()._create_table(name=self.name, primary_key=("id", Database.DBKeyType.INT), columns=typed_columns, autoincrement=True)
    

    def fetchlast(self):
        query = f"SELECT * FROM {self.name} ORDER BY timestamp DESC"

        self.cursor.execute(query)

        row = self.cursor.fetchone()
        if row is None:
            return None
        
        fetched_list = {column_name: row[column_name] for column_name in row.keys()}

        return fetched_list

    

    def fetchlastcolumns(self, columns: list[str]):
        query = f"SELECT\n    {",\n    ".join([column for column in columns])}\nFROM {self.name} ORDER BY timestamp DESC"

        self.cursor.execute(query)

        row = self.cursor.fetchone()
        
        if row is None:
            return None

        fetched_list = {column_name: row[column_name] for column_name in row.keys()}

        return fetched_list
    

    def fetchlast_conditional(self, condition: str):
        query = f"SELECT * FROM {self.name} WHERE {condition} ORDER BY timestamp DESC"

        self.cursor.execute(query)

        row = self.cursor.fetchone()

        if row is None:
            return None

        fetched_list = {column_name: row[column_name] for column_name in row.keys()}

        return fetched_list


    def fetchlastcolumns_conditional(self, columns: list[str], condition: str):
        query = f"SELECT\n    {",\n    ".join([column for column in columns])}\nFROM {self.name} WHERE {condition} ORDER BY timestamp DESC"

        self.cursor.execute(query)

        row = self.cursor.fetchone()

        fetched_list = {column_name: row[column_name] for column_name in row.keys()}

        return fetched_list
    


    def update(self, columns: dict[str, Database.DBInputType]):
        """
        Warning: This method inserts NULL if a certain collumn hasn't been provided; use updatecolumns if you don't want this to happen
        """
        #TODO: Write rest of docstring

        columns["timestamp"] = datetime.datetime.now()

        db_columns = self.convert_db_input_columns(columns)

        query = (f"INSERT INTO {self.name} (\n{", ".join(db_columns.keys())}\n) VALUES (\n:{", :".join(db_columns.keys())}\n)")

        with self.db_lock:

            self.cursor.execute(query, db_columns)

            self.conn.commit()


    def updatecolumns(self, columns: dict[str, Database.DBInputType]):
        columns["timestamp"] = datetime.datetime.now()

        db_columns = self.convert_db_input_columns(columns)

        old_values = self.fetchlast()
        if old_values is None:
            query = (f"INSERT INTO {self.name} (\n{", ".join(db_columns.keys())}\n) VALUES (\n:{", :".join(db_columns.keys())}\n)")
            with self.db_lock:
                self.cursor.execute(query, db_columns)

                self.conn.commit()
            return

        new_values = {}
        for key, value in old_values.items():
            if key == "id":
                continue
            if not key in set(db_columns.keys()):
                new_values[key] = value
            else:
                new_values[key] = db_columns[key]
        
        query = (f"INSERT INTO {self.name} (\n{", ".join(new_values.keys())}\n) VALUES (\n:{", :".join(new_values.keys())}\n)")

        with self.db_lock:
            self.cursor.execute(query, new_values)

            self.conn.commit()
        




class UpdatingTable(Table):
    def __init__(self, name: str, path):
        super().__init__(name, path)
        self.name = name

    def create(
            self,
            primary_key: tuple[str, Database.DBInputType],
            columns: dict[str, Database.DBInputType]
            ):
        
        primary_key_db_typed = primary_key[0], self.convert_db_types(primary_key[1])[1]

        typed_columns: dict[str, Database.DBKeyType] = {}
        for column_name, column_type in columns.items():
            typed_columns[column_name] = self.convert_db_types(column_type)[1]
        
        return super()._create_table(name=self.name, primary_key=primary_key_db_typed, columns=typed_columns)


    def fetchone(self, primary_key_name: str, primary_key: Database.DBInputType) -> dict | None:
        query = f"SELECT * FROM {self.name} WHERE {primary_key_name} = ?"
        
        self.cursor.execute(query, (primary_key,))

        row = self.cursor.fetchone()

        if row is None:
            return None

        fetched_list = {column_name: row[column_name] for column_name in row.keys()}

        return fetched_list


    def fetchonecolumns(self, columns: list[str], primary_key_name: str, primary_key: Database.DBInputType) -> dict | None:
        query = f"SELECT\n    {",\n    ".join([column for column in columns])}\nFROM {self.name} WHERE {primary_key_name} = ?"
        
        self.cursor.execute(query, (primary_key,))

        row = self.cursor.fetchone()

        if row is None:
            return None

        fetched_list = {column_name: row[column_name] for column_name in row.keys()}

        return fetched_list




    def update(self, primary_key_name: str, primary_key: Database.DBInputType, columns: dict[str, Database.DBInputType | None]):
        columns[primary_key_name] = primary_key

        prev_data = self.fetchone(primary_key_name, primary_key)

        new_columns = {}
        for key, value in columns.items():
            if value is None and prev_data is not None:
                new_columns[key] = prev_data[key]
            elif value is None and prev_data is None:
                continue
            elif value is not None:
                new_columns[key] = columns[key]

        db_columns = self.convert_db_input_columns(new_columns)


        if prev_data is None:
            query = (f"INSERT INTO {self.name} (\n{", ".join(db_columns.keys())}\n) VALUES (\n:{", :".join(db_columns.keys())}\n)")

            with self.db_lock:
                self.cursor.execute(query, db_columns)

                self.conn.commit()
            return
        
        new_values = {}
        for key, value in prev_data.items():
            if not key in set(db_columns.keys()):
                new_values[key] = value
            else:
                new_values[key] = db_columns[key]

        query = (f"UPDATE {self.name}\nSET\n    {",\n    ".join((" = ".join((key, f":{key}")) for key in new_values if not key == primary_key_name))}\n WHERE {primary_key_name} = :{primary_key_name}")
        
        with self.db_lock:
            self.cursor.execute(query, new_values)
            
            self.conn.commit()



class MetaTable:
    def __init__(self, path):
        self.name = 'meta'
        self._table = Table(self.name, path=path)

    class ChannelUses(Enum):
        # Standard: MODULE_SUBMODULE_PROCESS_TYPE    = 'module_submodule_process_type_channel_id'
        # Examples: WYNNAPI_GRAIDS_TRACKING_SEND     = 'wynnapi_graids_tracking_send_channel_id'
        #           WYNNAPI_TOMES_REQUESTING_LIVE    = 'wynnapi_tomes_requesting_live_channel_id'
        #           ANNIHILATION_PARTIES_SIGNUP_LIVE = 'annihilation_parties_signup_live_channel_id'
        WYNNAPI_GRAIDS_TRACKING_SEND  = 'wynnapi_graids_tracking_send_channel_id'
        WYNNAPI_TOMES_REQUESTING_LIVE = 'wynnapi_tomes_requesting_live_channel_id'
        # Not yet connected to this system, will use this key when hooked up
        ANNIHILATION_PARTIES_SIGNUP_LIVE = 'annihilation_parties_signup_live_channel_id'

    class MessageIds(Enum):
        # Standard: MODULE_SUBMODULE_PROCESS_MESSAGENAME = 'module_submodule_process_messagename_message_id'
        # Examples: WYNNAPI_TOMES_REQUESTING_LAYOUTVIEW  = 'wynnapi_tomes_requesting_layoutview_message_id'
        #           ANNIHILATION_PARTIES_SIGNUP_EMBEDS   = 'annihilation_parties_signup_embeds_message_id'
        WYNNAPI_TOMES_REQUESTING_LAYOUTVIEW  = 'wynn_api_tomes_requesting_layoutview_message_id'
        # Not yet connected to this system, will use this key when hooked up
        ANNIHILATION_PARTIES_SIGNUP_EMBEDS   = 'annihilation_parties_signup_embeds_message_id'
    
    class RoleIds(Enum):
        """
        # Standard\n
        `SITUATION(_MODULE(_SUBMODULE(_PROCESS)))(_TYPE)_ROLENAME` = `'situation(_module(_submodule(_process)))(_type)_rolename_role_id'`\n
        # Values\n
        - GENERAL_GUILDMEMBER
        - GENERAL_HIGHRANK
        - SPECIFIC_ANNIHILATION_PING
        - SPECIFIC_ANNIHILATION_PARTIES_SIGNUP_PERMISSION
        ## Examples of new assignment\n
        ```
        GENERAL_GUILDMEMBER = 'general_guildmember_role_id'
        GENERAL_HIGHRANK = 'general_highrank_role_id'
        SPECIFIC_ANNIHILATION_PING = 'specific_annihilation_ping_role_id'
        SPECIFIC_ANNIHILATION_PARTIES_SIGNUP_PERMISSION = 'specific_annihilation_parties_signup_permission_role_id'
        ```
        """
        GENERAL_GUILDMEMBER = 'general_guildmember_role_id'
        GENERAL_HIGHRANK = 'general_highrank_role_id'
        #TODO: Update the keys to conform to the standard (will be some hard work there...)
        # Not yet connected to this system, will use this key when hooked up
        SPECIFIC_ANNIHILATION_PING = 'specific_annihilation_ping_role_id'
        SPECIFIC_ANNIHILATION_PARTIES_SIGNUP_PERMISSION = 'specific_annihilation_parties_signup_permission_role_id'

    class OtherKeys(Enum):
        # Standard: MODULE_SUBMODULE_PROCESS_NAME         = 'module_submodule_process_messagename_other'
        # Examples: WYNNAPI_TOMES_REQUESTING_WEEKLYSTREAK = 'wynnapi_tomes_requesting_weeklystreak_other'
        #           WYNNAPI_TOMES_REQUESTING_TIMEINTERVAL = 'wynnapi_tomes_requesting_timeinterval_other'
        WYNNAPI_TOMES_REQUESTING_WEEKLYSTREAK = 'wynnapi_tomes_requesting_weeklystreak_other'
        WYNNAPI_TOMES_REQUESTING_TIMEINTERVAL = 'wynnapi_tomes_requesting_timeinterval_other'
        # Not yet connected to this system, will use this key when hooked up
        ANNIHILATION_PARTIES_TRACKING_ID      = 'annihilation_parties_tracking_id_other'

    def create(self):
        return self._table._create_table(name=self.name, primary_key=('key', Database.DBKeyType.STR), columns={'value': Database.DBKeyType.STR}) #pylint: disable=protected-access


    #####################################################################################
    #####################################################################################
    ########                     Setting and fetching helpers                     #######
    #####################################################################################
    #####################################################################################
    
    def _setraw(self, key: str, value: str) -> None:
        query = f'INSERT INTO {self.name} (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value'
        self._table.cursor.execute(query, (key, value))
        self._table.conn.commit()

    def _fetchraw(self, key: str) -> str | None:
        query = f"SELECT value FROM {self.name} WHERE key = ?"
        self._table.cursor.execute(query, (key,))
        result = self._table.cursor.fetchone()
        return result[0] if result else None


    #####################################################################################
    #####################################################################################
    ########                      Getting and setting guilds                      #######
    #####################################################################################
    #####################################################################################

    # Only to be used as a helper for the function in discordutils.py
    def set_guild_id(self, g_id: int):
        self._setraw('guild_id', str(g_id))

    def get_guild_id(self) -> int | None:
        result = self._fetchraw('guild_id')
        if result is None:
            return None
        g_id = int(result)
        return g_id


    #####################################################################################
    #####################################################################################
    ########                     Getting and setting channels                     #######
    #####################################################################################
    #####################################################################################

    # Only to be used as a helper for the function in discordutils.py
    def set_channel_id(self, channel: ChannelUses, channel_id: int):
        self._setraw(channel.value, str(channel_id))

    def get_channel_id(self, channel: ChannelUses) -> int | None:
        result = self._fetchraw(channel.value)
        if result is None:
            return None
        channel_id = int(result)
        return channel_id


    ######################################################################################
    ######################################################################################
    ########          Getting and setting messages to keep after restarts          #######
    ######################################################################################
    ######################################################################################

    # Only to be used as a helper for the function in discordutils.py
    def set_message_id(self, message: MessageIds, message_id: int):
        self._setraw(message.value, str(message_id))

    def get_message_id(self, message: MessageIds) -> int | None:
        result = self._fetchraw(message.value)
        if result is None:
            return None
        message_id = int(result)
        return message_id


    ######################################################################################
    ######################################################################################
    ########                       Getting and setting roles                       #######
    ######################################################################################
    ######################################################################################

    # Only to be used as a helper for the function in discordutils.py
    def set_role_id(self, role: RoleIds, role_id: int):
        self._setraw(role.value, str(role_id))

    def get_role_id(self, role: RoleIds) -> int | None:
        result = self._fetchraw(role.value)
        if result is None:
            return None
        role_id = int(result)
        return role_id
    

    def set_other(self, other: OtherKeys, value):
        self._setraw(other.value, str(value))

    def get_other(self, other: OtherKeys) -> str | None:
        result = self._fetchraw(other.value)
        return result

if __name__ == "__main__":
    print("make it do something first maybe...")
    


    
