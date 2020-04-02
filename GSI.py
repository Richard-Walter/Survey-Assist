# -*- coding: utf-8 -*-

from GSIExceptions import *
from collections import OrderedDict
from collections import Counter
from SurveyConfiguration import SurveyConfiguration

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
        self.formatted_lines = None
        self.column_names = list(GSI.GSI_WORD_ID_DICT.values())
        self.column_ids = list(GSI.GSI_WORD_ID_DICT.keys())
        self.survey_config = SurveyConfiguration()
        self.formatted_lines = []
        self.unformatted_lines = []

    def update_target_height(self, line_number, corrections):

        # corrections takes the form of a dictionary e.g. {'83': new_height, '87': new_target_height}

        self.survey_config = SurveyConfiguration()

        unformatted_line = self.get_unformatted_line(line_number)

        for field_id, new_value in corrections.items():
            # todo and a try statement in case match.group fails

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

        self.survey_config = SurveyConfiguration()

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
    def get_all_shots_from_a_station_including_setup(self, station_name, line_number=None):

        single_station_formatted_lines = {}
        station_found = False

        if line_number is None:
            line_number = 0

        for index, formatted_line in enumerate(self.formatted_lines[line_number:]):

            if station_found:

                # still in the named station setup
                if not formatted_line['STN_Easting']:
                    single_station_formatted_lines[line_number + index] = formatted_line

                # exit as we have come to the next station setup
                else:
                    break

            # find the line that contains the station
            if formatted_line['STN_Easting'] and formatted_line['Point_ID'] == station_name:
                single_station_formatted_lines[line_number] = formatted_line
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
