# -*- coding: utf-8 -*-
import os
import sqlite3
import logging.config
from collections import OrderedDict
from collections import Counter
from SurveyConfigurationWindow import SurveyConfigurationWindow

import re


class GSI:
    GSI_WORD_ID_DICT = OrderedDict([('11', 'Point_ID'), ('19', 'Timestamp'), ('21', 'Horizontal_Angle'),
                                    ('22', 'Vertical_Angle'), ('31', 'Slope_Distance'), ('32', 'Horizontal_Dist'),
                                    ('33', 'Height_Diff'), ('51', 'Prism_Constant'), ('81', 'Easting'),
                                    ('82', 'Northing'), ('83', 'Elevation'), ('84', 'STN_Easting'),
                                    ('85', 'STN_Northing'), ('86', 'STN_Elevation'), ('87', 'Target_Height'),
                                    ('88', 'STN_Height')])

    # REGULAR EXPRESSION LOOKUP
    REGULAR_EXPRESSION_LOOKUP = OrderedDict([('11', r'\*11\d*\+\w+'), ('19', r''), ('21', r''),
                                             ('22', r''), ('31', r''), ('32', r''),
                                             ('33', r''), ('51', r''), ('81', r''),
                                             ('82', r''), ('83', r'83\.{2}\d{2}\+(\d*\.)?\d+'), ('84', r''),
                                             ('85', r''), ('86', r''), ('87', r'87\.{2}\d{2}\+\d+'),
                                             ('88', r'')])

    def __init__(self, logger):

        self.logger = logger
        self.filename = None
        self.column_names = list(GSI.GSI_WORD_ID_DICT.values())
        self.column_ids = list(GSI.GSI_WORD_ID_DICT.keys())
        self.survey_config = SurveyConfigurationWindow()
        self.formatted_lines = []
        self.unformatted_lines = []
        self.survey_config = SurveyConfigurationWindow()

    def update_target_height(self, line_number, corrections):

        # corrections takes the form of a dictionary e.g. {'83': new_height, '87': new_target_height}

        self.survey_config = SurveyConfigurationWindow()

        unformatted_line = self.get_unformatted_line(line_number)

        for field_id, new_value in corrections.items():

            re_pattern = re.compile(GSI.REGULAR_EXPRESSION_LOOKUP[field_id])
            match = re_pattern.search(unformatted_line)

            org_field_value = match.group()

            # Lets build the new field value.First lets build the prefix e.g.87..10+  or 83
            re_pattern = re.compile(r'\d{2}..\d{2}\+')
            prefix = re_pattern.search(org_field_value).group()

            # remove the decimal from the new value  e.g. 1.543 -> 1543
            new_value = new_value.replace(".", "")

            # 4dp precision &elevation only - add decimal at second last digit e.g 2013493 ->201349.3
            if self.survey_config.precision_value == '4dp' and prefix[:2] == '83':
                new_value = new_value[:-1] + '.' + new_value[-1:]
                # There are 18 chars in the suffix so we need to fill the new value with leading zeros
                new_field_value_suffix = new_value.zfill(18)
            else:
                # There are 16 chars in the suffix so we need to fill the new value with leading zeros
                new_field_value_suffix = new_value.zfill(16)

            # lets combine the prefix with the suffix to create the new field value to replace the old one
            new_field_value = prefix + new_field_value_suffix

            # now replace the old value with the new one
            unformatted_line = unformatted_line.replace(org_field_value, new_field_value)

        # update the raw gsi lines
        self.unformatted_lines[line_number - 1] = unformatted_line

    def get_unformatted_line(self, line_number):

        return self.unformatted_lines[line_number - 1]

    def get_formatted_line(self, line_number):

        return self.formatted_lines[line_number - 1]

    def format_gsi(self, filename):

        self.survey_config = SurveyConfigurationWindow()

        with open(filename, "r") as f:

            self.filename = filename

            # Create new list of formatted & unformatted GSI lines each time this function is called
            self.formatted_lines = []
            self.unformatted_lines = []

            try:
                for line in f:

                    self.unformatted_lines.append(line)

                    """ Need to create dictionary of ID's & value's e.g. {'Point_ID': 'A', 'STN_Easting': '2858012', 
                    .. """

                    # First - create default empty string if no field
                    formatted_line = OrderedDict([('Point_ID', ''), ('Timestamp', ''), ('Horizontal_Angle', ''),
                                                  ('Vertical_Angle', ''), ('Slope_Distance', ''),
                                                  ('Horizontal_Dist', ''), ('Height_Diff', ''),
                                                  ('Prism_Constant', ''), ('Easting', ''), ('Northing', ''),
                                                  ('Elevation', ''), ('STN_Easting', ''), ('STN_Northing', ''),
                                                  ('STN_Elevation', ''), ('Target_Height', ''),
                                                  ('STN_Height', '')])

                    # flag for station setup line
                    stn_setup = False

                    # Work with the first field '11' separately - its unique and can contain spaces and alphanumerics
                    field_value = self.format_point_id(line[8:24].lstrip('0'))

                    formatted_line[GSI.GSI_WORD_ID_DICT['11']] = field_value

                    # Create remaining list of fields e.g. [21.324+0000000006854440, 22.324+0000000009042520, ...
                    remaining_line = line[24:]
                    field_list = remaining_line.split()
                    # field_list = [line[i:i + 24] for i in range(0, len(line), 24)]

                    # match the 2-digit identification with the key in the dictionary and format its corresponding value
                    for field in field_list:

                        two_digit_id = field[0:2]

                        # Strip off unnecessary digits and spaces to make the number readable
                        field_value = field[7:].rstrip().lstrip('0')

                        # apply special formatting rules to particular fields
                        if two_digit_id == '19':
                            field_value = self.format_timestamp(field_value)

                        elif two_digit_id in ('21', '22'):  # horizontal or vertical angles
                            field_value = self.format_angles(field_value)

                        elif two_digit_id == '51':
                            field_value = self.format_prism_constant(field_value)

                        # distance and coordinates
                        elif two_digit_id in ('31', '32', '33', '81', '82', '83', '84', '85', '86', '87', '88'):
                            field_value = self.format_number(field_value)

                            # Check to see if this line is a station setup
                            if two_digit_id == "84":
                                stn_setup = True

                            #  if STN setup then set STN height to 0 if height is empty string
                            if two_digit_id == '88' and field_value == "":
                                field_value = '0.000'

                            # set target height to 0 rather than empty string if line is not a station setup
                            elif two_digit_id == '87' and field_value == "" and not stn_setup:
                                field_value = '0.000'

                        elif field_value == "":

                            field_value = 'N/A'

                        field_name = GSI.GSI_WORD_ID_DICT[two_digit_id]
                        formatted_line[field_name] = field_value

                    self.formatted_lines.append(formatted_line)
                    self.logger.info('Formatted Line: ' + str(formatted_line))

                    stn_setup = False

            except KeyError:
                self.logger.exception(
                    "File doesn't appear to be a valid GSI file.  Missing Key ID: {}".format(field_value))
                raise CorruptedGSIFileError

    @staticmethod
    def format_point_id(point_id_field):

        return "0" if point_id_field == "" else point_id_field

    def format_timestamp(self, timestamp):

        try:

            minute = timestamp[-2:]
            hour = timestamp[-4:-2]

        except ValueError:
            # self.logger.exception(f'Incorrect timestamp {timestamp}- cannot be formatted properly')
            self.logger.exception('Incorrect timestamp {}- cannot be formatted properly'.format(timestamp))

        else:
            timestamp = '{}:{}'.format(hour, minute)

        return timestamp

    def format_angles(self, angle):

        degrees = '000'
        minutes = '00'
        seconds = '00'

        if self.survey_config.precision_value == '3dp':

            if len(angle) != 0:
                seconds = angle[-3:-1]
                minutes = angle[-5:-3]
                degrees = angle[:-5]

        else:  # survey is 4 dp

            if len(angle) != 3:
                seconds = angle[-5:-1]
                minutes = angle[-7:-5]
                degrees = angle[:-7]

        return '{}° {}\' {}"'.format(degrees.zfill(3), minutes, seconds)

    @staticmethod
    def format_prism_constant(constant):

        constant = constant[3:].lstrip("0")

        if constant == "":
            return "0"
        return constant

    def format_number(self, number):

        try:
            if self.survey_config.precision_value == '3dp':
                return '{:.3f}'.format(float(number) * 0.001)

            else:  # survey is 4 dp
                return '{:.4f}'.format(float(number) * 0.001)

        # return empty string if not a number
        except ValueError:
            return number

    def get_column_values(self, column_name):

        column_values = []

        for line in self.formatted_lines:

            try:
                column_value = line[column_name]
                column_values.append(column_value)
            except KeyError:
                pass  # column value doesn't exist for this line...continue

        return column_values

    def get_set_of_control_points(self):

        control_points = set()

        for formatted_line in self.formatted_lines:

            # check to see if point id is a control point by see if STN_Easting exists
            if formatted_line['STN_Easting']:
                control_points.add(formatted_line['Point_ID'])

        return sorted(control_points)

    # returns dictionary of control points along with their line number
    def get_list_of_control_points(self):

        control_points = OrderedDict()
        control_points_list = []

        for line_number, formatted_line in enumerate(self.formatted_lines):

            # check to see if point id is a control point by see if STN_Easting exists
            if formatted_line['STN_Easting']:
                control_points[line_number] = formatted_line['Point_ID']
                control_points_list.append(control_points)

        return control_points

    # returns gsi lines containing all shots except setups from GSI
    def get_all_lines_except_setup(self):

        shot_points = []

        for formatted_line in self.formatted_lines:

            # check to see if point id is a control point by see if STN_Easting exists
            if not formatted_line['STN_Easting']:
                shot_points.append(formatted_line)

        return shot_points

    # returns a dict containing formatted lines and their line number
    def get_all_shots_from_a_station_including_setup(self, station_name, gsi_line_number=None):

        single_station_formatted_lines = {}
        station_found = False

        if gsi_line_number is None:
            gsi_line_number = 0

        for index, formatted_line in enumerate(self.formatted_lines[gsi_line_number:]):

            if station_found:

                # still in the named station setup
                if not formatted_line['STN_Easting']:
                    single_station_formatted_lines[gsi_line_number + index] = formatted_line

                # exit as we have come to the next station setup
                else:
                    break

            # find the line that contains the station
            if formatted_line['STN_Easting'] and formatted_line['Point_ID'] == station_name:
                single_station_formatted_lines[gsi_line_number] = formatted_line
                station_found = True

        return single_station_formatted_lines

    @staticmethod
    def is_control_point(formatted_line):

        if formatted_line['STN_Easting']:
            return True

        return False

    def get_change_points(self):

        change_points = set()

        # list of point_IDs used for determining change points
        point_id_list = []

        for formatted_line in self.formatted_lines:
            point_id_list.append(formatted_line['Point_ID'])

        # if point ID occurs 8 times then it probably is a change point be a change point
        point_id_frequency = Counter(point_id_list);

        for point_id, count in point_id_frequency.items():
            if count > 7:
                change_points.add(point_id)

        return sorted(change_points)

    # Create a new GSI with suffix that contains only control.  ALl other shots are removed from the GSI

    def create_control_only_gsi(self):

        control_only_gsi_file_contents = ''
        control_only_filename = self.filename[:-4] + '_CONTROL_ONLY.gsi'
        control_points = self.get_set_of_control_points()

        with open(self.filename, "r") as f_orig:

            # Create new list of formatted GSI lines each time this function is called
            gsi_orig_filecontents = f_orig.readlines()

        # Loop through and original gsi and find all shots that are control
        for line in gsi_orig_filecontents:
            for control in control_points:
                if control in line:
                    control_only_gsi_file_contents += line

        print(control_only_gsi_file_contents)

        # write out new GSI
        with open(control_only_filename, 'w') as f_stripped:
            f_stripped.write(control_only_gsi_file_contents)

        return control_only_filename

    def check_control_naming(self):

        station_setups = self.get_set_of_control_points()

        print('STATION SETUP LIST: ' + str(station_setups))

        stn_shots_not_in_setup = []
        shots_to_stations = []

        line_number_errors = []
        error_text = ""

        shots_to_stations_message = "The number of times each station was shot is shown below.\nIn most cases they " \
                                    "should be all even numbers:\n\n"

        line_number = 0

        # First, lets check all shots that are labelled 'STN' and make sure that it in the station setup list.
        for formatted_line in self.formatted_lines:

            line_number += 1
            point_id = formatted_line['Point_ID']

            # Check to see if this point is a shot to a STN
            if 'STN' in point_id:

                # Check to see if this shot is in the list of station setups.
                if point_id not in station_setups:
                    stn_shots_not_in_setup.append(point_id)
                    line_number_errors.append(line_number)

                # Also want to track of how many times each station is shot so this info can be displayed to user
                # check to see if point id is a station setup
                if not formatted_line['STN_Easting']:
                    shots_to_stations.append(formatted_line['Point_ID'])

        print("STATION SHOTS THAT ARE NOT IN SETUP:")
        print(stn_shots_not_in_setup)

        print("COUNT OF SHOTS TO STATIONS:")
        print(Counter(shots_to_stations))

        # Display message to user of the station shots not found in station setups.
        if stn_shots_not_in_setup:

            error_text = "Possible point labelling error with the following control shots: \n\n"

            for shot in stn_shots_not_in_setup:
                error_text += shot + "\n"

        print(error_text)

        if not error_text:
            error_text = "Control naming looks good!\n"

        # Create and display no. of times each station was shot;'
        counter = Counter(shots_to_stations)
        for key, value in sorted(counter.items()):
            shots_to_stations_message += str(key) + '  ' + str(value) + '\n'

        error_text += '\n\n' + shots_to_stations_message

        return error_text, line_number_errors

    def check_3D_survey(self, conn):

        control_points = self.get_set_of_control_points()
        change_points = self.get_change_points()
        points = change_points + control_points

        print('CONTROL POINTS: ' + str(control_points))
        print('CHANGE POINTS: ' + str(change_points))
        print('POINTS: ' + str(points))

        sql_query_columns = 'Point_ID, Easting, Northing, Elevation'
        sql_where_column = 'Point_ID'

        error_points = []


        with conn:

            sql_query_text = "SELECT {} FROM GSI WHERE {}=?".format(sql_query_columns, sql_where_column)

            cur = conn.cursor()

            # Check if points are outisde of tolerance e.g. 10mm
            errors = []

            for point in points:

                # create a list of eastings, northings and height and check min max value of each
                eastings = []
                northings = []
                elevation = []
                point_id = ""
                error_text = ""

                print('Survey mark is: ' + point)
                cur.execute(sql_query_text, (point,))
                rows = cur.fetchall()

                for row in rows:
                    print(row)
                    point_id = row[0]

                    # create a list of eastings, northings and height and check min max value of each

                    if row[1] == '':
                        pass  # should be a station setup

                    else:

                        eastings.append(row[1])
                        northings.append(row[2])
                        elevation.append(row[3])

                    # print(point_id, max(eastings), min(eastings), max(northings), min(northings), max(elevation),
                    #       min(elevation))

                try:

                    # Check Eastings
                    east_diff = float(max(eastings)) - float(min(eastings))

                    if east_diff > float(self.survey_config.easting_tolerance):
                        error_text = point_id + ' is out of tolerance in Easting: ' + str(round(
                            east_diff,
                            3)) + 'm\n'
                        errors.append(error_text)
                        error_points.append(point)
                        print(error_text)

                    # Check Northings
                    north_diff = float(max(northings)) - float(min(northings))

                    if north_diff > float(self.survey_config.northing_tolerance):
                        error_text = point_id + ' is out of tolerance Northing: ' + str(round(
                            north_diff,
                            3)) + 'm\n'
                        errors.append(error_text)
                        error_points.append(point)
                        print(error_text)

                    # Check Elevation
                    height_diff = float(max(elevation)) - float(min(elevation))

                    if height_diff > float(self.survey_config.height_tolerance):
                        error_text = point_id + ' is out of tolerance in height: ' + \
                                     str(round(
                                         height_diff,
                                         3)) + 'm \n'
                        errors.append(error_text)
                        error_points.append(point)
                        print(error_text)

                except ValueError:
                    print('Value error at point : ' + point)

        return errors, error_points

# def main():
#
#     # testing
#     gsi = GSI(logging.getLogger('CompNet Assist'))
#     gsi.format_gsi('C:/Users/rjwal_000/PycharmProjects/CompNetAssist/Files/A9_ARTC_902_2.GSI')
#     gsi.create_control_only_gsi()
#
# if __name__ == "__main__":
#
#         main()
class GSIDatabase:
    DATABASE_NAME = 'GSI_database.db'
    DATABASE_PATH = 'GSI Files\\GSI_database.db'
    TABLE_NAME = 'GSI'

    def __init__(self, ):

        self.gsi_word_id_dict = GSI.GSI_WORD_ID_DICT
        self.logger = logging.getLogger('Survey Assist')
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

        # add isSTN and isCP columns
        # create_table_string += "isSTN text, isCP text"

        create_table_string = create_table_string.rstrip(', ')
        create_table_string += ")"

        self.logger.info('SQL Create Table query: ' + create_table_string)

        with self.conn:
            self.conn.execute(create_table_string)

    def close_database(self):

        self.conn.close()

    def populate_table(self, gsi_formatted_lines):

        # formatted_lines = checkIsSTNandIsCP(gsi_formatted_lines)

        values_list = []

        for formatted_line in gsi_formatted_lines:
            # Build list of values
            gsi_values = list(formatted_line.values())
            values = tuple(gsi_values)
            values_list.append(values)

        # Build SQL statement
        question_marks = ', '.join(list('?' * len(self.gsi_word_id_dict)))  # e.g. ?, ?, ?, ?
        sql = 'INSERT INTO {} VALUES ({})'.format(GSIDatabase.TABLE_NAME, question_marks)

        self.logger.info('SQL statement is: {}'.format(sql))
        self.logger.info('SQL values are: {}'.format(str(values_list)))

        # Insert a formatted line of GSI data into database
        with self.conn:
            self.conn.executemany(sql, values_list)


class CorruptedGSIFileError(Exception):
    """Raised when a GSI file can't be read properly"""

    def __init__(self, msg="GSI file can't be read properly"):
        # Error message thrown is saved in msg
        self.msg = msg


class GSIFile:

    def __init__(self, gsi_file_path):
        self.fixed_file_path = gsi_file_path
        self.gsi_file_contents = None

        with open(gsi_file_path, 'r') as f_orig:
            self.gsi_file_contents = f_orig.read()
            print(self.gsi_file_contents)

    def get_filecontents(self):
        return self.gsi_file_contents
