import sqlite3
import os


class GSIDatabase:

    DATABASE_NAME = 'GSI_database.db'
    DATABASE_PATH = 'GSI Files\\GSI_database.db'
    TABLE_NAME = 'GSI'

    def __init__(self, gsi_word_id_dict, logger):

        self.gsi_word_id_dict = gsi_word_id_dict
        self.logger = logger
        self.conn = None

        self.logger.debug(os.getcwd())

    def create_db(self):

        try:

            # Remove old database if exists
            if os.path.isfile(GSIDatabase.DATABASE_PATH):
                os.remove(GSIDatabase.DATABASE_PATH)

            # Create database and empty table
            self.conn = sqlite3.connect(GSIDatabase.DATABASE_PATH)

            with self.conn:
                self.create_table()

        except PermissionError:
            self.logger.exception("Database in use.  Unable to delete until it is closed")

            # Clear table contents - this can happen if another GSI file is opened within the applicaton
            self.conn.execute(f'DELETE FROM {GSIDatabase.TABLE_NAME}')

        except Exception:
            self.logger.exception("Error creating database: ")
            # self.conn.close()

    def create_table(self):

        # # Drop table if exists.  This can happen if another GSI file is opened within the applicaton
        # self.conn.execute(f'DROP TABLE IF EXISTS {TABLE_NAME}')

        # This database contains just one table - GSI Table.  Lets create the SQL command
        create_table_string = f'CREATE TABLE {GSIDatabase.TABLE_NAME}('

        for name in self.gsi_word_id_dict.values():
            create_table_string += name
            create_table_string += " text, "

        create_table_string = create_table_string.rstrip(', ')
        create_table_string += ")"

        self.logger.info('SQL Create Table query: ' + create_table_string)

        with self.conn:
            self.conn.execute(create_table_string)

    def populate_table(self, formatted_lines):

        for formatted_line in formatted_lines:
            """Build INSERT statement
            e.g. c.execute("INSERT INTO stuffToPlot (Point_Number, STN_Easting, STN_Northing) 
            VALUES (?, ?, ?)",(Point_Number, STN_Easting, STN_Northing))"""

            keys = ', '.join(formatted_line.keys())  # e.g. Point_Number, STN_Easting, STN_Northing
            question_marks = ', '.join(list('?' * len(formatted_line)))  # e.g. ?, ?, ?, ?
            values = tuple(formatted_line.values())
            sql = f'INSERT INTO {GSIDatabase.TABLE_NAME} ({keys}) VALUES ({question_marks})'

            # print(f'keys are: {keys}')
            # print(f'question marks are: {question_marks}')
            # print(f'values are: {values}')

            self.logger.info(f'SQL statement is: {sql}')

            # Insert a formatted line of GSI data into database
            with self.conn:
                self.conn.execute(sql, values)
