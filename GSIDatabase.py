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
            # self.conn.execute(f'DELETE FROM {GSIDatabase.TABLE_NAME}')
            self.conn.execute('DELETE FROM {}'.format(GSIDatabase.TABLE_NAME))

        except Exception:
            self.logger.exception("Error creating database: ")
            # self.conn.close()

    def create_table(self):

        # This database contains just one table - GSI Table.  Lets create the SQL command
        # create_table_string = f'CREATE TABLE {GSIDatabase.TABLE_NAME}('
        create_table_string = 'CREATE TABLE {}('.format(GSIDatabase.TABLE_NAME)

        for name in self.gsi_word_id_dict.values():
            create_table_string += name
            create_table_string += " text, "

        create_table_string = create_table_string.rstrip(', ')
        create_table_string += ")"

        self.logger.info('SQL Create Table query: ' + create_table_string)

        with self.conn:
            self.conn.execute(create_table_string)

    def populate_table(self, formatted_lines):

        values_list = []

        for formatted_line in formatted_lines:

            # Build list of values
            values = tuple(formatted_line.values())
            values_list.append(values)

        # Build SQL statement
        question_marks = ', '.join(list('?' * len(self.gsi_word_id_dict)))  # e.g. ?, ?, ?, ?
        sql = 'INSERT INTO {} VALUES ({})'.format(GSIDatabase.TABLE_NAME, question_marks)

        self.logger.info('SQL statement is: {}'.format(sql))
        self.logger.info('SQL values are: {}'.format(str(values_list)))

        # Insert a formatted line of GSI data into database
        with self.conn:
            self.conn.executemany(sql, values_list)
