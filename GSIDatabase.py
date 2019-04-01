import sqlite3
import os

DATABASE_NAME = 'GSI_database.db'
DATABASE_PATH = 'GSI Files\\GSI_database.db'
TABLE_NAME = 'GSI'


class GSIDatabase:

    def __init__(self, gsi_word_id_dict):

        self.gsi_word_id_dict = gsi_word_id_dict
        self.conn = None
        self.c = None

        print(os.getcwd())

    def create_db(self):

        try:

            # os.chdir('.\\GSI Files')

            # Remove old database if exists
            print(os.path.isfile(DATABASE_PATH))
            if os.path.isfile(DATABASE_PATH):
                os.remove(DATABASE_PATH)

            # Create database
            self.conn = sqlite3.connect(DATABASE_PATH)
            self.c = self.conn.cursor()

        except PermissionError as pe:
            print("Database in use.  Unable to delete until it is closed: " + str(pe))

        except Exception as e:
            print("Error creating database: " + str(e))
            # self.conn.close()

    def create_table(self):

        # Drop table if exists.  This can happen if another GSI file is opened within the applicaton
        self.c.execute(f'DROP TABLE IF EXISTS {TABLE_NAME}')

        # This database contains just one table - GSI Table
        # Dynamically create the string to create database table
        create_table_string = f'CREATE TABLE {TABLE_NAME}('

        for name in self.gsi_word_id_dict.values():
            create_table_string += name
            create_table_string += " text, "

        create_table_string = create_table_string.rstrip(', ')
        create_table_string += ")"
        print(create_table_string)

        self.c.execute(create_table_string)

    def populate_table(self, formatted_lines):

        for formatted_line in formatted_lines:

            """Build INSERT statement
            e.g. c.execute("INSERT INTO stuffToPlot (Point_Number, STN_Easting, STN_Northing) VALUES (?, ?, ?)",(Point_Number, STN_Easting, STN_Northing))"""

            keys = ', '.join(formatted_line.keys())  # e.g. Point_Number, STN_Easting, STN_Northing
            question_marks = ', '.join(list('?'*len(formatted_line)))    # e.g. ?, ?, ?, ?
            values = tuple(formatted_line.values())
            sql = f'INSERT INTO {TABLE_NAME} ({keys}) VALUES ({question_marks})'

            print(f'keys are: {keys}')
            print(f'question marks are: {question_marks}')
            print(f'SQL statement is: {sql}')
            print(f'values are: {values}')

            # Insert a formatted line of GSI data
            with self.conn:
                self.conn.execute(sql, values)
