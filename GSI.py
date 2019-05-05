from GSIExceptions import *


class GSI:
    GSI_WORD_ID_DICT = {'11': 'Point_Number', '19': 'Timestamp', '21': 'Horizontal_Angle', '22': 'Vertical_Angle',
                        '31': 'Slope_Distance', '32': 'Horizontal_Distance', '33': 'Height_Difference',
                        '51': 'Prism_Offset', '81': 'Easting',
                        '82': 'Northing', '83': 'Elevation', '84': 'STN_Easting', '85': 'STN_Northing',
                        '86': 'STN_Elevation', '87': 'Target_Height', '88': 'Instrument_Height'}

    def __init__(self, logger):

        self.logger = logger
        self.filename = None
        self.formatted_lines = []
        self.column_names = list(GSI.GSI_WORD_ID_DICT.values())

    def format_gsi(self, filename):

        with open(filename, "r") as f:

            self.filename = filename

            # Iterating through the file:
            for line in f:
                stripped_line = line.strip('*')  # First character in each line should begin with *
                field_list = stripped_line.split()  # returns 23-24 digit field e.g. 22.324+0000000009042520
                self.logger.debug('Field List: ' + str(field_list))

                # dictionary consisting of Word ID and formatted line
                formatted_line = {}

                # match the 2-digit identification with the key in the dictionary
                for field in field_list:

                    two_digit_id = field[0:2]

                    try:
                        field_name = GSI.GSI_WORD_ID_DICT[two_digit_id]
                        self.logger.debug(two_digit_id + '  ' + field_name)

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
                            # print("This field has no value")
                            field_value = 'N/A'

                        # print(field_value)
                        formatted_line[field_name] = field_value

                    except KeyError:
                        self.logger.exception(
                            f'File doesn\'t appear to be a valid GSI file.  Missing Key ID: {field_value}')
                        raise CorruptedGSIFileError

                self.logger.info('Formatted Line: ' + str(formatted_line))
                self.formatted_lines.append(formatted_line)

    def format_timestamp(self, timestamp):

        try:
            # print(timestamp)
            minute = timestamp[-2:]
            hour = timestamp[-4:-2]

        except ValueError:
            self.logger.exception(f'Incorrect timestamp {timestamp}- cannot be formatted properly')

        else:
            timestamp = f'{hour}:{minute}'

        return timestamp

    def format_angles(self, angle):

        if len(angle) == 0:
            angle = '00000000'
        try:
            seconds = angle[-3:-1]
            minutes = angle[-5:-3]
            degrees = angle[:-5]
            # print(degrees, minutes, seconds)

        except ValueError:
            self.logger.exception(f'Incorrect angle {angle}- cannot be formatted properly ')

        else:
            angle = f'{degrees.zfill(3)}° {minutes}\' {seconds}"'

        return angle

    @staticmethod
    def format_prism_constant(constant):

        return constant[3:]
