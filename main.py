""" This program reads in a GSI file from a Leica Total Station and displays the file
in a clearer, more user-friendly format.  You can then execute queries on this data"""

import os
import sys

test_file_names = ['A9_ARTC_902_2.GSI', 'ERROR.GSI', 'HCCUL180219.GSI']

os.chdir('.\\GSI Files')

gsi_word_id_dict = {'11': 'Point Number', '19': 'Timestamp', '21': 'Horizontal Angle', '22': 'Vertical Angle',
                    '31': 'Slope Distance', '32': 'Horizontal Distance', '33': 'Height Difference',
                    '51': 'Prism Offset', '81': 'Easting',
                    '82': 'Northing', '83': 'Elevation', '84': 'STN Easting', '85': 'STN Northing',
                    '86': 'STN Elevation', '87': 'Target Height', '88': 'Instrument Height'}

# Reading Files:
with open(test_file_names[0], "r") as f:
    # Iterating through the file:
    for line in f:
        stripped_line = line.strip('*')  # First character in each line should begin with *
        field_list = stripped_line.split()  # returns 23-24 digit field e.g. 22.324+0000000009042520
        print(field_list)

        # match the 2-digit identification with the key in the dictionary
        for field in field_list:

            two_digit_ID = field[0:2]

            try:
                field_name = gsi_word_id_dict[two_digit_ID]
                print(two_digit_ID + '  ' + field_name)

                field_value = field[7:].lstrip('0')

                if field_value == "":
                    #     print("THis field has no value")
                    field_value = 'N/A'

                print(field_value)

            except KeyError as e:
                print("This file doesn't appear to be a valid GSI file")
                print('Missing Key ID:  ' + str(e))
                sys.exit()

# TODO: format the timestamp and prism constant fields.