import sqlite3
import os
from GSI import GSI
import sys

DATABASE_NAME = 'GSI_database.db'
TABLE_NAME = 'GSI'


class GSIDatabase:

    def __init__(self):

        try:
            self.conn = sqlite3.connect(DATABASE_NAME)
            self.c = self.conn.cursor()
            self.create_db()

        except Exception as e:
            print("Error creating database: " + str(e))
            print("Deleting old database")
            self.conn.close()

            try:
                os.remove(DATABASE_NAME)
                sys.exit()
            except PermissionError as pe:
                print("Database in use.  Unable to delete until it is closed: " + str(e))

    def create_db(self):

        # This database contains just one table - GSI Table
        # Dynamically create the string to create database table
        create_table_string = f'CREATE TABLE {TABLE_NAME}('

        for name in GSI.GSI_WORD_ID_DICT.values():
            create_table_string += name
            create_table_string += " text, "

        create_table_string = create_table_string.rstrip(', ')
        create_table_string += ")"
        print(create_table_string)

        self.c.execute(create_table_string)

    def table_data_entry(self, dict_gsi_line):

        """Build INSERT statement
        e.g. c.execute("INSERT INTO stuffToPlot (Point_Number, STN_Easting, STN_Northing) VALUES (?, ?, ?)",(Point_Number, STN_Easting, STN_Northing))"""

        keys = ', '.join(dict_gsi_line.keys())  # e.g. Point_Number, STN_Easting, STN_Northing
        question_marks = ', '.join(list('?'*len(dict_gsi_line)))    # e.g. ?, ?, ?, ?
        values = tuple(dict_gsi_line.values())
        sql = f'INSERT INTO {TABLE_NAME} ({keys}) VALUES ({question_marks})'

        print(f'keys are: {keys}')
        print(f'question marks are: {question_marks}')
        print(f'SQL statement is: {sql}')
        print(f'values are: {values}')

        # Insert a formatted line of GSI data
        with self.conn:
            self.conn.execute(sql, values)
