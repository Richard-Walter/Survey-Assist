import sqlite3
import os

DATABASE_NAME = 'GSI_database.db'


class GSIDatabase:

    def __init__(self, gsi):

        self.gsi = gsi

        try:
            self.conn = sqlite3.connect(DATABASE_NAME)
            self.c = self.conn.cursor()
            self.create_db(gsi)

        except Exception as e:
            print("Error creating database: " + str(e))
            print("Deleting old database")
            self.conn.close()
            os.remove(DATABASE_NAME)

    def create_db(self, gsi):

        # This database contains just one table - GSI Table
        print(gsi.GSI_WORD_ID_DICT['11'])

        # Dynamically create the string to create database table
        create_table_string = "CREATE TABLE GSI("

        for name in gsi.GSI_WORD_ID_DICT.values():
            create_table_string += name
            create_table_string += " text, "

        create_table_string = create_table_string.rstrip(', ')
        create_table_string += ")"
        print(create_table_string)

        self.c.execute(create_table_string)



