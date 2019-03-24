import sys

gsi_word_id_dict = {'11': 'Point Number', '19': 'Timestamp', '21': 'Horizontal Angle', '22': 'Vertical Angle',
                    '31': 'Slope Distance', '32': 'Horizontal Distance', '33': 'Height Difference',
                    '51': 'Prism Offset', '81': 'Easting',
                    '82': 'Northing', '83': 'Elevation', '84': 'STN Easting', '85': 'STN Northing',
                    '86': 'STN Elevation', '87': 'Target Height', '88': 'Instrument Height'}


class GSI:

    def __init__(self, filename):

        self.filename = filename
        self.format_gsi()

    def format_gsi(self):

        with open(self.filename, "r") as f:
            # Iterating through the file:
            for line in f:
                stripped_line = line.strip('*')  # First character in each line should begin with *
                field_list = stripped_line.split()  # returns 23-24 digit field e.g. 22.324+0000000009042520
                print(field_list)

                # match the 2-digit identification with the key in the dictionary
                for field in field_list:

                    two_digit_id = field[0:2]

                    try:
                        field_name = gsi_word_id_dict[two_digit_id]
                        print(two_digit_id + '  ' + field_name)

                        # Strip off unnecessary digits
                        field_value = field[7:].lstrip('0')

                        if two_digit_id == '51':
                            # print("This field has no value")
                            field_value = self.format_prism_constant(field_value)

                        # Format timestamp
                        elif two_digit_id == '19':
                            field_value = self.format_timestamp(field_value)

                        # Format horizontal or vertical angles
                        # elif two_digit_id == '21' or two_digit_id == '22':
                        elif two_digit_id in ('21', '22'):
                            field_value = self.format_angles(field_value)

                        elif field_value == "":
                            # print("THis field has no value")
                            field_value = 'N/A'

                        print(field_value)

                    except KeyError as e:
                        print("This file doesn't appear to be a valid GSI file")
                        print('Missing Key ID:  ' + str(e))
                        sys.exit()

    # TODO: format the timestamp

    @staticmethod
    def format_timestamp(timestamp):
        # timestamp += 'a'
        return timestamp

    @staticmethod
    def format_angles(angle):

        if len(angle) == 0:
            angle = '00000000'
        try:
            seconds = angle[-3:-1]
            minutes = angle[-5:-3]
            degrees = angle[:-5]
            print(degrees, minutes, seconds)

        except ValueError as ex:
            print("Incorrect angle - cannot be formated properly " + str(ex))

        else:
            angle = f'{degrees.zfill(3)}° {minutes}\' {seconds}"'

        return angle

    @staticmethod
    def format_prism_constant(constant):

        return constant[3:]
