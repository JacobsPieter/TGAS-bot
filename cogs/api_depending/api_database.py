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



class Table(Database):
    def __init__(self, name: str, path) -> None:
        self.name = name
        super().__init__(path)
        self.columns: dict

    def create_table(
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
        
        return super().create_table(name=self.name, primary_key=("id", Database.DBKeyType.INT), columns=typed_columns, autoincrement=True)
    

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
        
        return super().create_table(name=self.name, primary_key=primary_key_db_typed, columns=typed_columns)


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



if __name__ == "__main__":
    print("make it do something first maybe...")
    


    
