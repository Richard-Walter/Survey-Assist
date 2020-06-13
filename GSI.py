# -*- coding: utf-8 -*-
import os
import sqlite3
import csv
import copy
import tkinter.messagebox
from tkinter import filedialog
import logging.config
from collections import OrderedDict
from collections import Counter

import re


class GSI:
    GSI_WORD_ID_DICT = OrderedDict([('11', 'Point_ID'), ('19', 'Timestamp'), ('21', 'Horizontal_Angle'),
                                    ('22', 'Vertical_Angle'), ('31', 'Slope_Distance'), ('32', 'Horizontal_Dist'),
                                    ('33', 'Height_Diff'), ('51', 'Prism_Constant'), ('81', 'Easting'),
                                    ('82', 'Northing'), ('83', 'Elevation'), ('84', 'STN_Easting'),
                                    ('85', 'STN_Northing'), ('86', 'STN_Elevation'), ('87', 'Target_Height'),
                                    ('88', 'STN_Height')])

    EXPORT_GSI_HEADER_FORMAT = ['UID', 'Point_ID', 'Easting', 'Northing', 'Elevation', 'Timestamp', 'STN_Easting', 'STN_Northing',
                                'STN_Height', 'STN_Elevation', 'Target_Height', 'Horizontal_Angle', 'Vertical_Angle', 'Slope_Distance',
                                'Horizontal_Dist', 'Prism_Constant', 'Height_Diff']

    # REGULAR EXPRESSION LOOKUP
    REGULAR_EXPRESSION_LOOKUP = OrderedDict([('11', r'\*11\d*\+\w+'), ('19', r''), ('21', r''),
                                             ('22', r''), ('31', r'31..\d\d\+\d*\.?\d?'), ('32', r'32..\d\d\+\d*\.?\d?'),
                                             ('33', r'33..\d\d[\+-]\d*\.?\d?'), ('51', r'51.{4}\+\d*\+\d{3}'),
                                             ('81', r'81..00\+\d*\.?\d?'), ('82', r'82..00\+\d*\.?\d?'), ('83', r'83..00\+\d*\.?\d?'),
                                             ('84', r'84..\d\d[\+-]\d*\.?\d?'), ('85', r'85..\d\d[\+-]\d*\.?\d?'), ('86', r'86..[\+-]\d*\.?\d?'),
                                             ('87', r'87\.{2}\d{2}\+\d+'), ('88', r'88..\d\d[\+-]\d*\.?\d?')])

    # PRISM CONSTANTS
    PC_DICT_REAL_VALUES = {'Big Joe': 0.0390, 'Big Joe 2': 0.0340, 'GLASS': 0.0240, 'Leica 360 Prism': 0.0231, 'Leica Circular Prism': 0.0000,
                           'Monitoring': 0.0089}
    PC_DICT_GSI_VALUES = {'Big Joe': 39, 'Big Joe 2': 34, 'GLASS': 24, 'Leica 360 Prism': 23, 'Leica Circular Prism': 0, 'Monitoring': 8}

    def __init__(self, logger, survey_config):

        self.logger = logger
        self.filename = None
        self.column_names = list(GSI.GSI_WORD_ID_DICT.values())
        self.column_ids = list(GSI.GSI_WORD_ID_DICT.keys())
        self.formatted_lines = []
        self.unformatted_lines = []
        self.survey_config = survey_config

    def update_target_height(self, line_number, corrections):

        # corrections takes the form of a dictionary e.g. {'33': new_height_difference, '83': new_elevation, '87': new_target_height}

        unformatted_line = self.get_unformatted_line(line_number)

        for field_id, new_value in corrections.items():

            re_pattern = re.compile(GSI.REGULAR_EXPRESSION_LOOKUP[field_id])
            match = re_pattern.search(unformatted_line)

            org_field_value = match.group()

            # Lets build the new field value.First lets build the prefix e.g.87..10+  or 83 or 33
            re_pattern = re.compile(r'\d{2}..\d{2}[\+,-]')
            prefix = re_pattern.search(org_field_value).group()

            # remove the decimal from the new value  e.g. 1.543 -> 1543
            new_value = new_value.replace(".", "")

            # 4dp precision & elevation only - add decimal at second last digit e.g 2013493 ->201349.3
            if self.survey_config.precision_value == '4dp' and prefix[:2] == '83':
                new_value = new_value[:-1] + '.' + new_value[-1:]
                # There are 18 chars in the suffix so we need to fill the new value with leading zeros
                new_field_value_suffix = new_value.zfill(18)

            elif prefix[:2] == '33':    # we need to add the sign to the prefix for height difference

                algebraic_sign = '+'
                if new_value[0] == '-':    # positive numbers don't contain a '+'
                    algebraic_sign = '-'
                    new_value = new_value[1:]  # remove the sign + or -
                prefix = prefix[:-1] + algebraic_sign

                new_field_value_suffix = new_value.zfill(16)
            else:
                # There are 16 chars in the suffix so we need to fill the new value with leading zeros
                new_field_value_suffix = new_value.zfill(16)

            # lets combine the prefix with the suffix to create the new field value to replace the old one
            new_field_value = prefix + new_field_value_suffix

            # now replace the old value with the new one
            unformatted_line = unformatted_line.replace(org_field_value, new_field_value)

        # update the raw gsi lines
        self.unformatted_lines[line_number - 1] = unformatted_line

    def update_station_height(self, stn_line_number, new_station_height):

        unformatted_line = self.get_unformatted_line(stn_line_number)

        re_pattern = re.compile(GSI.REGULAR_EXPRESSION_LOOKUP['88'])
        match = re_pattern.search(unformatted_line)

        org_field_value = match.group()

        # Lets build the new field value.First lets build the prefix e.g. 88..10+
        re_pattern = re.compile(r'\d{2}..\d{2}[\+-]')
        prefix = re_pattern.search(org_field_value).group()

        # remove the decimal from the new value  e.g. 0.413->0413
        new_station_height = new_station_height.replace(".", "")

        # There are 16 chars in the suffix so we need to fill the new value with leading zeros
        new_field_value_suffix = new_station_height.zfill(16)

        # lets combine the prefix with the suffix to create the new field value to replace the old one
        new_field_value = prefix + new_field_value_suffix

        # now replace the old value with the new one
        unformatted_line = unformatted_line.replace(org_field_value, new_field_value)

        # update the raw gsi lines
        self.unformatted_lines[stn_line_number - 1] = unformatted_line

    def update_station_elevation(self, stn_line_number, new_stn_elevation):

        unformatted_line = self.get_unformatted_line(stn_line_number)

        re_pattern = re.compile(GSI.REGULAR_EXPRESSION_LOOKUP['86'])
        match = re_pattern.search(unformatted_line)

        org_field_value = match.group()

        # Lets build the new field value.First lets build the prefix e.g. 86..+
        re_pattern = re.compile(r'\d{2}..[\+-]')
        prefix = re_pattern.search(org_field_value).group()

        # remove the decimal from the new value  e.g. 0.413->0413
        new_stn_elevation = new_stn_elevation.replace(".", "")

        # There are 16 chars in the suffix so we need to fill the new value with leading zeros
        new_field_value_suffix = new_stn_elevation.zfill(16)

        # lets combine the prefix with the suffix to create the new field value to replace the old one
        new_field_value = prefix + new_field_value_suffix

        # now replace the old value with the new one
        unformatted_line = unformatted_line.replace(org_field_value, new_field_value)

        # update the raw gsi lines
        self.unformatted_lines[stn_line_number - 1] = unformatted_line

    def update_point_name(self, line_number, new_point_name):

        unformatted_line = self.get_unformatted_line(line_number)

        re_pattern = re.compile(GSI.REGULAR_EXPRESSION_LOOKUP['11'])
        match = re_pattern.search(unformatted_line)

        org_point_id_value = match.group()

        # Lets build the new field value.
        # First lets build the prefix e.g.87..10+  or 83
        re_pattern = re.compile(r'\*\d{6}\+')
        prefix = re_pattern.search(org_point_id_value).group()

        # NOw, lets build the suffix.  There are 16 chars in the suffix so we need to fill the new value with leading zeros
        new_point_name_suffix = new_point_name.zfill(16)

        # lets combine the prefix with the suffix to create the new field value to replace the old one
        new_point_id_field_value = prefix + new_point_name_suffix

        # now replace the old value with the new one
        # unformatted_line = unformatted_line.replace(org_point_id_value, new_point_id_field_value)
        unformatted_line = new_point_id_field_value + unformatted_line[24:]

        # update the raw gsi lines
        self.unformatted_lines[line_number - 1] = unformatted_line

    def pc_change_update_coordinates(self, line_number, corrections):
        # e.g. corrections_dict = {'Prism_Constant': new_pc, 'Easting': new_east, 'Northing': new_north, 'Elevation': new_height,
        #                     'Slope_Distance': new_slant_distance, 'Horizontal_Dist': new_horizontal_distance,
        #                     'Height_Diff': new_height_difference}

        self.update_pc(line_number, corrections['Prism_Constant'])
        self.update_easting(line_number, corrections['Easting'])
        self.update_northing(line_number, corrections['Northing'])
        self.update_elevation(line_number, corrections['Elevation'])
        self.update_slope_distance(line_number, corrections['Slope_Distance'])
        self.update_horizontal_dist(line_number, corrections['Horizontal_Dist'])
        self.update_height_diff(line_number, corrections['Height_Diff'])

    def update_pc(self, line_number, new_pc):

        unformatted_line = self.get_unformatted_line(line_number)

        # lets find the original value
        re_pattern = re.compile(GSI.REGULAR_EXPRESSION_LOOKUP['51'])
        match = re_pattern.search(unformatted_line)
        old_pc_unformatted = match.group()

        # Lets build the new field value.
        # First lets build the prefix e.g.51..1.+
        re_pattern = re.compile(r'51.{4}\+')
        prefix = re_pattern.search(old_pc_unformatted).group()

        # lets build the middle part    e.g. +000000000007+
        re_pattern = re.compile(r'\+\d*\+')
        middle = re_pattern.search(old_pc_unformatted).group().lstrip('+')  # strip off + as this is included in prefix

        # lets build the suffix.  There are 3 chars in the suffix so we need to fill the new value with leading zeros
        suffix = new_pc.zfill(3)

        # lets combine the prefix with the suffix to create the new field value to replace the old one
        new_pc_unformatted = prefix + middle + suffix

        # now replace the old value with the new one
        unformatted_line = unformatted_line.replace(old_pc_unformatted, new_pc_unformatted)

        # update the raw gsi lines
        self.unformatted_lines[line_number - 1] = unformatted_line

    def update_easting(self, line_number, new_easting):

        # new easting must be converted from e.g.'1000.123' to  the 1234123  or 1234123.4 format
        new_easting = new_easting.replace(".", "")

        unformatted_line = self.get_unformatted_line(line_number)

        # lets find the original value
        re_pattern = re.compile(GSI.REGULAR_EXPRESSION_LOOKUP['81'])
        match = re_pattern.search(unformatted_line)
        old_easting_unformatted = match.group()

        # Lets build the new field value. First lets build the prefix e.g.81..00+
        re_pattern = re.compile(r'81..00\+')
        prefix = re_pattern.search(old_easting_unformatted).group()

        # lets build the suffix.
        if self.survey_config.precision_value == '4dp':
            new_easting = new_easting[:-1] + '.' + new_easting[-1:]
            suffix = new_easting.zfill(17)
        else:

            suffix = new_easting.zfill(16)

        # lets combine the prefix with the suffix to create the new field value to replace the old one
        new_easting_unformatted = prefix + suffix

        # now replace the old value with the new one
        unformatted_line = unformatted_line.replace(old_easting_unformatted, new_easting_unformatted)

        # update the raw gsi lines
        self.unformatted_lines[line_number - 1] = unformatted_line

    def update_northing(self, line_number, new_northing):

        # new northing must be converted from e.g.'1000.123' to  the 1234123  or 1234123.4 format
        new_northing = new_northing.replace(".", "")

        unformatted_line = self.get_unformatted_line(line_number)

        # lets find the original value
        re_pattern = re.compile(GSI.REGULAR_EXPRESSION_LOOKUP['82'])
        match = re_pattern.search(unformatted_line)
        old_northing_unformatted = match.group()

        # Lets build the new field value. First lets build the prefix e.g.82..00+
        re_pattern = re.compile(r'82..00\+')
        prefix = re_pattern.search(old_northing_unformatted).group()

        # lets build the suffix.
        if self.survey_config.precision_value == '4dp':
            new_northing = new_northing[:-1] + '.' + new_northing[-1:]
            suffix = new_northing.zfill(17)
        else:

            suffix = new_northing.zfill(16)

        # lets combine the prefix with the suffix to create the new field value to replace the old one
        new_northiing_unformatted = prefix + suffix

        # now replace the old value with the new one
        unformatted_line = unformatted_line.replace(old_northing_unformatted, new_northiing_unformatted)

        # update the raw gsi lines
        self.unformatted_lines[line_number - 1] = unformatted_line

    def update_elevation(self, line_number, new_elevation):

        # new elevation must be converted from e.g.'1000.123' to  the 1234123  or 1234123.4 format
        new_elevation = new_elevation.replace(".", "")

        unformatted_line = self.get_unformatted_line(line_number)

        # lets find the original value
        re_pattern = re.compile(GSI.REGULAR_EXPRESSION_LOOKUP['83'])
        match = re_pattern.search(unformatted_line)
        old_elevation_unformatted = match.group()

        # Lets build the new field value. First lets build the prefix e.g.83..00+
        re_pattern = re.compile(r'83..00\+')
        prefix = re_pattern.search(old_elevation_unformatted).group()

        # lets build the suffix.
        if self.survey_config.precision_value == '4dp':
            new_elevation = new_elevation[:-1] + '.' + new_elevation[-1:]
            suffix = new_elevation.zfill(17)
        else:

            suffix = new_elevation.zfill(16)

        # lets combine the prefix with the suffix to create the new field value to replace the old one
        new_elevation_unformatted = prefix + suffix

        # now replace the old value with the new one
        unformatted_line = unformatted_line.replace(old_elevation_unformatted, new_elevation_unformatted)

        # update the raw gsi lines
        self.unformatted_lines[line_number - 1] = unformatted_line

    def update_slope_distance(self, line_number, slope_distance):

        # new slope_distance must be converted from e.g.'1000.123' to  the 1234123  or 1234123.4 format
        slope_distance = slope_distance.replace(".", "")

        unformatted_line = self.get_unformatted_line(line_number)

        # lets find the original value
        re_pattern = re.compile(GSI.REGULAR_EXPRESSION_LOOKUP['31'])
        match = re_pattern.search(unformatted_line)
        old_slope_distance_unformatted = match.group()

        # Lets build the new field value. First lets build the prefix e.g.83..00+
        re_pattern = re.compile(r'31..\d\d\+')
        prefix = re_pattern.search(old_slope_distance_unformatted).group()

        # lets build the suffix.
        if self.survey_config.precision_value == '4dp':
            slope_distance = slope_distance[:-1] + '.' + slope_distance[-1:]
            suffix = slope_distance.zfill(17)
        else:

            suffix = slope_distance.zfill(16)

        # lets combine the prefix with the suffix to create the new field value to replace the old one
        new_slope_distance_unformatted = prefix + suffix

        # now replace the old value with the new one
        unformatted_line = unformatted_line.replace(old_slope_distance_unformatted, new_slope_distance_unformatted)

        # update the raw gsi lines
        self.unformatted_lines[line_number - 1] = unformatted_line

    def update_horizontal_dist(self, line_number, horizontal_dist):

        # new slope_distance must be converted from e.g.'1000.123' to  the 1234123  or 1234123.4 format
        horizontal_dist = horizontal_dist.replace(".", "")

        unformatted_line = self.get_unformatted_line(line_number)

        # lets find the original value
        re_pattern = re.compile(GSI.REGULAR_EXPRESSION_LOOKUP['32'])
        match = re_pattern.search(unformatted_line)
        old_horizontal_dist_unformatted = match.group()

        # Lets build the new field value. First lets build the prefix e.g.83..00+
        re_pattern = re.compile(r'32..\d\d\+')
        prefix = re_pattern.search(old_horizontal_dist_unformatted).group()

        # lets build the suffix.
        if self.survey_config.precision_value == '4dp':
            horizontal_dist = horizontal_dist[:-1] + '.' + horizontal_dist[-1:]
            suffix = horizontal_dist.zfill(17)
        else:

            suffix = horizontal_dist.zfill(16)

        # lets combine the prefix with the suffix to create the new field value to replace the old one
        new_horizontal_dist_unformatted = prefix + suffix

        # now replace the old value with the new one
        unformatted_line = unformatted_line.replace(old_horizontal_dist_unformatted, new_horizontal_dist_unformatted)

        # update the raw gsi lines
        self.unformatted_lines[line_number - 1] = unformatted_line

    def update_height_diff(self, line_number, height_diff):
        # NOTE: height diff can contain a + or - symbol in the unformatted string

        if height_diff[0] == '-':
            algebraic_sign = '-'
            height_diff = height_diff[1:]   # remove algebraic sign
        else:
            algebraic_sign = '+'

        # new slope_distance must be converted from e.g.'1000.123' to the 1234123  or 1234123.4 format
        height_diff = height_diff.replace(".", "")

        unformatted_line = self.get_unformatted_line(line_number)

        # lets find the original value
        re_pattern = re.compile(GSI.REGULAR_EXPRESSION_LOOKUP['33'])
        match = re_pattern.search(unformatted_line)
        old_height_diff_unformatted = match.group()

        # Lets build the new field value. First lets build the prefix e.g.33..00+ or 33..00-
        re_pattern = re.compile(r'33..\d\d[\+-]')
        prefix = re_pattern.search(old_height_diff_unformatted).group()
        prefix = prefix[:-1] + algebraic_sign

        # lets build the suffix.
        if self.survey_config.precision_value == '4dp':
            height_diff = height_diff[:-1] + '.' + height_diff[-1:]
            suffix = height_diff.zfill(17)
        else:

            suffix = height_diff.zfill(16)

        # lets combine the prefix with the suffix to create the new field value to replace the old one
        new_height_diff_unformatted = prefix + suffix

        # now replace the old value with the new one
        unformatted_line = unformatted_line.replace(old_height_diff_unformatted, new_height_diff_unformatted)

        # update the raw gsi lines
        self.unformatted_lines[line_number - 1] = unformatted_line

    def get_unformatted_line(self, unformatted_line_number):

        return self.unformatted_lines[unformatted_line_number - 1]

    def get_formatted_line(self, formatted_line_number):

        return self.formatted_lines[formatted_line_number - 1]

    def format_gsi(self, filename):

        # self.survey_config = SurveyConfiguration()

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

                        # Check if the field is '21' so that we can determine precision (3 or 4dp) based on field length
                        if two_digit_id == '21':
                            if len(field) == 24:
                                # self.survey_config.update(SurveyConfiguration.section_instrument, 'instrument_precision', '4dp')
                                self.survey_config.precision_value = '4dp'
                            else:
                                # self.survey_config.update(SurveyConfiguration.section_instrument, 'instrument_precision', '3dp')
                                self.survey_config.precision_value = '3dp'

                        # Strip off unnecessary digits and spaces to make the number readable
                        field_value = field[7:].rstrip().lstrip('0')
                        # special format for angles
                        angle_field_value = field[7:-1].rstrip()    # remove blank spaces and last element which is always a zero for some reason

                        # apply special formatting rules to particular fields
                        if two_digit_id == '19':
                            field_value = self.format_timestamp(field_value)

                        elif two_digit_id in ('21', '22'):  # horizontal or vertical angles
                            field_value = self.format_angles(angle_field_value, self.survey_config.precision_value)

                        elif two_digit_id == '51':
                            field_value = self.format_prism_constant(field_value)

                        # distance and coordinates
                        elif two_digit_id in ('31', '32', '33', '81', '82', '83', '84', '85', '86', '87', '88'):

                            if two_digit_id == '87':
                                # always format target height to 3 decimal places, even for 4dp precision
                                field_value = self.format_number(field_value, '3dp')
                            else:
                                field_value = self.format_number(field_value, self.survey_config.precision_value)

                            # Check to see if this line is a station setup
                            if two_digit_id == "84":
                                stn_setup = True

                            #  if STN setup then set STN height to 0 if height is empty string
                            if two_digit_id == '88' and field_value == "":
                                field_value = '0.000'

                            # set target height to 0 rather than empty string if line is not a station setup
                            elif two_digit_id == '87' and field_value == "" and not stn_setup:
                                field_value = '0.000'

                            # Height difference may contain a poistive or negative
                            if two_digit_id == "33":
                                if field_value == "":
                                    field_value = '0.000'
                                else:
                                    algebraic_sign = field[6]
                                    field_value = algebraic_sign + field_value

                        elif field_value == "":

                            field_value = 'N/A'

                        field_name = GSI.GSI_WORD_ID_DICT[two_digit_id]
                        formatted_line[field_name] = field_value

                    self.formatted_lines.append(formatted_line)
                    # self.logger.info('Formatted Line: ' + str(formatted_line))

                    stn_setup = False

            except KeyError:
                self.logger.exception( "File doesn't appear to be a valid GSI file.  Missing Key ID: {}".format(field_value))
                raise CorruptedGSIFileError

    @staticmethod
    def format_point_id(point_id_field):

        return "0" if point_id_field == "" else point_id_field

    def format_timestamp(self, timestamp):

        try:

            minute = timestamp[-2:]
            hour = timestamp[-4:-2]

        except ValueError:

            self.logger.exception('Incorrect timestamp {}- cannot be formatted properly'.format(timestamp))

        else:
            timestamp = '{}:{}'.format(hour, minute)

        return timestamp

    @staticmethod
    def format_angles(angle, precision):

        degrees = '000'
        minutes = '00'
        seconds = '00'

        if precision == '3dp':

            if len(angle) != 0:
                seconds = angle[-2:]
                minutes = angle[-4:-2]
                degrees = angle[-7:-4]

        else:  # survey is 4 dp

            if len(angle) != 3:
                seconds = angle[-4:]
                minutes = angle[-6:-4]
                degrees = angle[-9:-6]

        return '{}° {}\' {}"'.format(degrees.zfill(3), minutes, seconds)

    @staticmethod
    def format_prism_constant(constant):

        constant = constant[3:].lstrip("0")

        if constant == "":
            return "0"
        return constant

    def format_number(self, number, precision):

        try:
            if precision == '3dp':
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

    def get_set_of_station_setups(self):

        control_points = set()

        for formatted_line in self.formatted_lines:

            # check to see if point id is a control point by see if STN_Easting exists
            if formatted_line['STN_Easting']:
                control_points.add(formatted_line['Point_ID'])

        return sorted(control_points)

    # returns dictionary of station setups along with their gsi line number
    def get_list_of_station_setups(self, formatted_lines):

        station_setups = OrderedDict()
        station_setup_list = []

        for line_number, formatted_line in enumerate(formatted_lines):

            # check to see if point id is a control point by see if STN_Easting exists
            if formatted_line['STN_Easting']:
                station_setups[line_number] = formatted_line['Point_ID']
                station_setup_list.append(station_setups)

        return station_setups

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

        single_station_formatted_lines = OrderedDict()
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

    def get_station_from_line_number(self, line_number):

        # need to traverse backwards until we hit a station list
        while (line_number > 0):
            if self.is_station_setup(self.formatted_lines[line_number - 1]):
                return line_number, self.formatted_lines[line_number - 1]
            line_number -= 1

    @staticmethod
    def is_station_setup(formatted_line):

        if formatted_line['STN_Easting']:
            return True

        return False

    @staticmethod
    def is_orientation_shot(formatted_line):

        if not formatted_line['STN_Easting'] and not formatted_line['Slope_Distance']:
            return True

        return False

    def get_change_points(self):

        change_points = []
        control_points_dict = self.get_list_of_station_setups(self.formatted_lines)

        # First, create a list of all point_ids and there frequency of occurrence
        point_id_list = []
        for formatted_line in self.formatted_lines:
            point_id_list.append(formatted_line['Point_ID'])

        point_id_frequency = Counter(point_id_list)

        # Next, determine if point_id is change point - i.e. if it occurs more than 4 times its probably a change point
        for point_id, count in point_id_frequency.items():
            if count > 3:
                if point_id in control_points_dict.values():
                    continue  # don't add stations to change point list
                else:
                    change_points.append(point_id)

        return sorted(change_points)

    # Create a new GSI with suffix that contains only control.  ALl other shots are removed from the GSI
    def create_control_only_gsi(self):

        control_only_gsi_file_contents = ''
        control_only_filename = self.filename[:-4] + '_CONTROL_ONLY.gsi'
        control_points = self.get_set_of_station_setups()

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

    # lets check the survey and make sure the prism constant for a point_ID is the same throughout the survey
    def check_prism_constants(self):

        error_text = "WARNING!  The following Point ID's have more than one prism constant:\n\n"
        dialog_text = 'Prism constants for each Point ID are consistent throughout this survey'
        point_id_pc_dict = {}
        point_id_errors = []
        line_number_errors = []

        all_shots_except_setups = self.get_all_lines_except_setup()

        for formatted_line in all_shots_except_setups:
            point_id = formatted_line['Point_ID']
            pc = formatted_line['Prism_Constant']
            # add empty set if not already defined
            point_id_pc_dict.setdefault(point_id, set())

            # add pc to a set of pcs for this point-id
            point_id_pc_dict[point_id].add(pc)

        # check if the pc list for each point id contains only 1 prism constant.  If not - error found
        for point_id, pc_set in point_id_pc_dict.items():
            if len(pc_set) > 1:
                point_id_errors.append(point_id)

        # any errors?
        if point_id_errors:
            dialog_point_list_text = ""
            dialog_error_line_list_text = ""
            dialog_text = error_text

            # Lets add a list of points to that contains errors so we can notify the user
            for point_id in point_id_errors:
                dialog_point_list_text += point_id + '\n'
                dialog_error_line_list_text += '\n'

                for line_number, formatted_line in enumerate(self.formatted_lines):

                    line_number += 1
                    if point_id == formatted_line['Point_ID']:
                        if not self.is_station_setup(formatted_line):
                            line_number_errors.append(line_number)
                            dialog_error_line_list_text += 'Line ' + str(line_number) + ':  ' + formatted_line[
                                'Point_ID'] + '  --->  PC= ' + formatted_line['Prism_Constant'] + '\n'

            dialog_text += dialog_point_list_text + '\n' + dialog_error_line_list_text

        return dialog_text, line_number_errors

    # lets check the survey and make sure the target height for a point_ID is the same throughout the survey
    def check_target_heights(self):

        error_text = "WARNING!  The following Point ID's have more than one target height:\n\n"
        dialog_text = 'Target heights for each Point ID are consistent throughout this survey'
        point_id_target_height_dict = {}
        point_id_errors = []
        line_number_errors = []

        all_shots_except_setups = self.get_all_lines_except_setup()

        for formatted_line in all_shots_except_setups:
            point_id = formatted_line['Point_ID']
            target_height = formatted_line['Target_Height']
            # add empty set if not already defined
            point_id_target_height_dict.setdefault(point_id, set())

            # add target height to a set of target heights for this point-id
            point_id_target_height_dict[point_id].add(target_height)

        # check if the target height list for each point id contains only 1 target height.  If not - error found
        for point_id, target_height_set in point_id_target_height_dict.items():
            if len(target_height_set) > 1:
                point_id_errors.append(point_id)

        # any errors?
        if point_id_errors:
            dialog_point_list_text = ""
            dialog_error_line_list_text = ""
            dialog_text = error_text

            # Lets add a list of points tothat contains errors so we can notify the user
            for point_id in point_id_errors:
                dialog_point_list_text += point_id + '\n'
                dialog_error_line_list_text += '\n'

                for line_number, formatted_line in enumerate(self.formatted_lines):

                    line_number += 1
                    if point_id == formatted_line['Point_ID']:
                        if not self.is_station_setup(formatted_line):
                            line_number_errors.append(line_number)
                            dialog_error_line_list_text += 'Line No. ' + str(line_number) + ':  ' + formatted_line[
                                'Point_ID'] + '---> target height: ' + formatted_line['Target_Height'] + '\n'

            dialog_text += dialog_point_list_text + '\n' + dialog_error_line_list_text

        return dialog_text, line_number_errors

    def check_control_naming(self):

        unique_station_setups = self.get_set_of_station_setups()
        list_station_setups = self.get_list_of_station_setups(self.formatted_lines)

        print('STATION SETUP LIST: ' + str(unique_station_setups))

        stn_shots_not_in_setup = ""
        shots_to_stations = []
        shots_with_same_id_as_stn = ""

        line_number_errors = []
        dialog_text = ""

        shots_to_stations_message = "The number of times each station was shot is shown below.\nIn most cases they " \
                                    "should be all even numbers:\n\n"

        line_number = 0

        # First, lets check all shots that are labelled 'STN' and make sure that its in the station setup list.
        for formatted_line in self.formatted_lines:

            line_number += 1
            point_id = formatted_line['Point_ID']

            # Check to see if this point is a shot to a STN
            if 'STN' in point_id:

                # Check to see if this shot is in the list of station setups.
                if point_id not in unique_station_setups:
                    stn_shots_not_in_setup += "Line No. " + str(line_number) + ':   ' + point_id + '\n'
                    line_number_errors.append(line_number)

                # Also want to track of how many times each station is shot so this info can be displayed to user
                # check to see if point id is a station setup
                if not formatted_line['STN_Easting']:
                    shots_to_stations.append(formatted_line['Point_ID'])

        # Next lets check points from each setup - none of them should contain same point_id as the station name. i.e. station can't shoot to itself
        for line_number, stn_name in list_station_setups.items():
            all_shots_from_station = self.get_all_shots_from_a_station_including_setup(stn_name, line_number)
            for line_no, formatted_line in all_shots_from_station.items():
                if self.is_station_setup(formatted_line):
                    # ignore the station setup line
                    continue
                else:
                    # if stn_name in formatted_line['Point_ID']:
                    if stn_name == formatted_line['Point_ID']:
                        # error found in GSI
                        shots_with_same_id_as_stn += "Line No. " + str(line_no + 1) + ':      ' + stn_name + ' ---> ' + formatted_line[
                            'Point_ID'] + '\n'
                        line_number_errors.append(line_no + 1)

        # Display message to user of the station shots not found in station setups.
        if stn_shots_not_in_setup:

            dialog_text = "Possible point labelling error.  The following shots containing a 'STN' label do not appear in any station " \
                          "setups: \n\n"

            for shot in stn_shots_not_in_setup.splitlines(True):
                dialog_text += shot

        # Display message if shots from a station contain its point_id
        if shots_with_same_id_as_stn:
            dialog_text += "\nPossible point labelling error.  The following point IDs have the same name as the station:\n\n"

            for shot in shots_with_same_id_as_stn.splitlines(True):
                dialog_text += shot

        # Check if any errors found
        if not dialog_text:
            dialog_text = "Control naming looks good!\n"

        # Create and display no. of times each station was shot
        counter = Counter(shots_to_stations)
        for key, value in sorted(counter.items()):
            shots_to_stations_message += str(key) + '  ' + str(value) + '\n'

        # if shots to stations found (2D surveys typically have none)
        if len(counter) != 0:
            dialog_text += '\n\n' + shots_to_stations_message

        return dialog_text, line_number_errors

    def check_3D_survey(self, conn, survey_config):

        control_points = self.get_set_of_station_setups()
        change_points = self.get_change_points()
        points = change_points + control_points

        # First, lets determine is station set up is a 2D surey or 3D

        sql_query_columns = 'Point_ID, Easting, Northing, Elevation'
        sql_where_column = 'Point_ID'

        error_points_dict = OrderedDict()
        error_points = set()

        with conn:

            sql_query_text = "SELECT {} FROM GSI WHERE {}=?".format(sql_query_columns, sql_where_column)

            cur = conn.cursor()

            for point in points:

                # create a list of eastings, northings and height and check min max value of each
                eastings = []
                northings = []
                elevation = []
                point_id = ""
                error_text = ""

                print('Survey mark is: ' + point)
                cur.execute(sql_query_text, (point,))

                # get eastings, northings and height for each shot to this point_ID
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

                try:

                    # Check for differences
                    point_tolerances_errors_dict = {}       # Easting, Northing, Elevation
                    east_diff = float(max(eastings)) - float(min(eastings))
                    north_diff = float(max(northings)) - float(min(northings))
                    height_diff = float(max(elevation)) - float(min(elevation))

                    if east_diff > float(survey_config.easting_tolerance):
                        point_tolerances_errors_dict['Easting'] = 'E='+"{:.3f}".format(round(east_diff, 3)) + 'm  '

                    if north_diff > float(survey_config.northing_tolerance):
                        point_tolerances_errors_dict['Northing'] = 'N='+"{:.3f}".format(round(north_diff, 3)) + 'm  '

                    if height_diff > float(survey_config.height_tolerance):
                        point_tolerances_errors_dict['Height'] = 'H='+"{:.3f}".format(round(height_diff, 3)) + 'm'

                    # add to error dictionary if errors found:
                    if point_tolerances_errors_dict:
                        error_points_dict[point_id] = point_tolerances_errors_dict

                except ValueError:
                    print('Value error at point : ' + point)

            # create error message if exist
            if error_points_dict:

                for point_name, tolerance_errors in error_points_dict.items():
                    error_points.add(point_name)
                    point_text = (point_name + ':').ljust(10)
                    error_text += '\n '+ point_text
                    error_text += tolerance_errors.get('Easting', '')
                    error_text += tolerance_errors.get('Northing', '')
                    error_text += tolerance_errors.get('Height', '')

        return error_text, error_points

    def get_point_name_line_numbers(self, point_name):

        point_line_numbers = []

        for line_number, formatted_line in enumerate(self.formatted_lines, start=1):

            if self.is_station_setup(formatted_line):
                continue
            elif point_name == formatted_line['Point_ID']:
                point_line_numbers.append(line_number)

        return point_line_numbers

    def export_csv(self, gsi_file_path):

        if not gsi_file_path:
            tkinter.messagebox.showerror("ERROR", "Please open up a GSI file first before trying to export")
            return

        gsi_basename = os.path.basename(gsi_file_path)
        gsi_directory = os.path.dirname(gsi_file_path)  # this should return the editing directory
        ts_directory = os.path.dirname(gsi_directory)  # this should return the TS directory
        root_job_directory = os.path.dirname(ts_directory)  # this should return the job directory e.g. 200416

        # check if file is in the edited directory of a dated file format folder
        if (os.path.isdir(root_job_directory + '/TS')) & (os.path.isdir(root_job_directory + '/GPS')) & (os.path.isdir(root_job_directory + '/OUTPUT')):

            out_csv_file_path = os.path.join(root_job_directory, os.path.basename(os.path.splitext(gsi_basename)[0] + '_Sorted.csv'))
            out_gsi_file_path = os.path.join(root_job_directory, os.path.basename(os.path.splitext(gsi_basename)[0] + '_Sorted.gsi'))

        else:   # get user to choose the the directory to export
            root_job_directory = filedialog.askdirectory(initialdir=gsi_directory, title='PLEASE SELECT THE JOB DIRECTORY TO EXPORT THE CSV')
            if root_job_directory == "":
                return      # user cancelled the dialog box
            out_csv_file_path = os.path.join(root_job_directory, os.path.basename(os.path.splitext(gsi_basename)[0] + '_Sorted.csv'))
            out_gsi_file_path = os.path.join(root_job_directory, os.path.basename(os.path.splitext(gsi_basename)[0] + '_Sorted.gsi'))

        # csv_header_name = list(GSI.GSI_WORD_ID_DICT.values())
        csv_header_name = list(GSI.EXPORT_GSI_HEADER_FORMAT)

        export_formatted_lines = self.format_gsi_for_export()

        try:
            # Export the sorted GSI
            with open(out_gsi_file_path, "w") as gsi_file:
                for line in self.unformatted_lines:
                    gsi_file.write(line)

            # Export the csv file
            with open(out_csv_file_path, 'w', newline='') as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=csv_header_name)
                writer.writeheader()
                for export_formatted_line in export_formatted_lines:
                    writer.writerow(export_formatted_line)

        except IOError as ex:
            print(ex)
            self.logger.exception("An unexpected error has occurred\n\nGSI.py export_csv()\n\n" + str(ex))
            tkinter.messagebox.showerror("ERROR", "Please make sure file isnt already opened")

        except Exception as ex:
            print(ex)
            self.logger.exception("An unexpected error has occurred\n\nGSI.py export_csv()\n\n" + str(ex))
            tkinter.messagebox.showerror("ERROR", "Something went wrong exporting CSV.  Contact Richard\n\n" + str(ex))


        else:
            ok = tkinter.messagebox.askyesno("EXPORTING CSV", "A sorted GSI, along with a corresponding CSV file has been created in:\n\n " +
                                         os.path.dirname(out_csv_file_path) + "\n\nWould you like to open up the CSV file now in Excel?")

            # open up the file for the user
            if ok:
                os.startfile(out_csv_file_path)


    def format_gsi_for_export(self):

        uid_formatted_lines = self.create_formatted_lines_with_UID()
        export_formatted_lines = []

        for formatted_line in uid_formatted_lines:

            for key in GSI.EXPORT_GSI_HEADER_FORMAT:
                formatted_line[key] = formatted_line.pop(key)

            export_formatted_lines.append(formatted_line)

        return export_formatted_lines

    def create_formatted_lines_with_UID(self):

        uid_key = 'UID'
        uid_formatted_lines = []
        copy_formatted_lines = copy.deepcopy(self.formatted_lines)

        stations_names_dict = self.get_list_of_station_setups(copy_formatted_lines)

        for gsi_line_number, station_name in stations_names_dict.items():

            obs_from_station = self.get_all_shots_from_a_station_including_setup(station_name, gsi_line_number)

            obs_from_station_list = list(obs_from_station.values())

            # dont include setup in the sort by point ID - remove and add to uid_formatted_lines a
            station_setup_formatted_line = obs_from_station_list.pop(0)
            station_setup_formatted_line[uid_key] = ""
            uid_formatted_lines.append(station_setup_formatted_line)

            # sorted_formatted_lines = sorted(obs_from_station_list, key=lambda item: item.get("Point_ID"))
            obs_from_station_list.sort(key=lambda item: item.get("Point_ID"))

            unique_point_counter = 1
            stn_uid_formatted_lines = []

            for index, formatted_line_dict in enumerate(obs_from_station_list):

                point_id = formatted_line_dict['Point_ID']
                stn_point = station_name + '_' + point_id
                uid = ''

                if index == 0:
                    uid = stn_point + '_' + str(unique_point_counter)
                    formatted_line_dict[uid_key] = uid
                else:

                    previous_formatted_line_dict = obs_from_station_list[index - 1]

                    # points match
                    if previous_formatted_line_dict['Point_ID'] == formatted_line_dict['Point_ID']:
                        unique_point_counter += 1
                        uid = stn_point + '_' + str(unique_point_counter)
                        formatted_line_dict[uid_key] = uid
                    else:
                        # reset counter for next double observations
                        unique_point_counter = 1
                        uid = stn_point + '_' + str(unique_point_counter)
                        formatted_line_dict[uid_key] = uid

                # formatted_line_dict[uid_key] = uid

                stn_uid_formatted_lines.append(formatted_line_dict)

            uid_formatted_lines.extend(stn_uid_formatted_lines)

        return uid_formatted_lines


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
    DATABASE_PATH = 'GSI_database.db'
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
            self.logger.info("Database in use.  Unable to delete until it is closed")

            # Clear table contents - this can happen if another GSI file is opened within the applicaton
            # self.conn.execute(f'DELETE FROM {GSIDatabase.TABLE_NAME}')
            self.conn.execute('DELETE FROM {}'.format(GSIDatabase.TABLE_NAME))

        except Exception as ex:
            self.logger.exception("Error creating database: \n\n" + str(ex))
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

        # self.logger.info('SQL Create Table query: ' + create_table_string)

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

        # self.logger.info('SQL statement is: {}'.format(sql))
        # self.logger.info('SQL values are: {}'.format(str(values_list)))

        # Insert a formatted line of GSI data into database
        with self.conn:
            self.conn.executemany(sql, values_list)


class CorruptedGSIFileError(Exception):
    """Raised when a GSI file can't be read properly"""

    def __init__(self, msg="GSI file can't be read properly"):
        # Error message thrown is saved in msg
        self.msg = msg


class GSIFileContents:

    def __init__(self, gsi_file_path):
        self.fixed_file_path = gsi_file_path
        self.gsi_file_contents = None

        with open(gsi_file_path, 'r') as f_orig:
            self.gsi_file_contents = f_orig.read()
            print(self.gsi_file_contents)

    def get_filecontents(self):
        return self.gsi_file_contents
