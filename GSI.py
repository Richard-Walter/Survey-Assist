from GSIExceptions import *


class GSI:
    GSI_WORD_ID_DICT = {'11': 'Point_ID', '19': 'Timestamp', '21': 'Horizontal_Angle', '22': 'Vertical_Angle',
                        '31': 'Slope_Distance', '32': 'Horizontal_Distance', '33': 'Height_Difference',
                        '51': 'Prism_Constant', '81': 'Easting',
                        '82': 'Northing', '83': 'Elevation', '84': 'STN_Easting', '85': 'STN_Northing',
                        '86': 'STN_Elevation', '87': 'Target_Height', '88': 'Instrument_Height'}

    def __init__(self, logger):

        self.logger = logger
        self.filename = None
        self.formatted_lines = None
        self.column_names = list(GSI.GSI_WORD_ID_DICT.values())

    def format_gsi(self, filename):

        with open(filename, "r") as f:

            self.filename = filename

            # Create new list of formatted GSI lines each time this function is called
            self.formatted_lines = []

            for line in f:

                formatted_line = {}  # dictionary of ID and ID value e.g. {'Point_ID': 'A', 'STN_Easting': '2858012',..

                # Work with the first field '11' separately - its unique and can contain spaces and alphanumerics
                field_eleven_value = line[8:24].lstrip('0')

                if field_eleven_value == "":
                    formatted_line[GSI.GSI_WORD_ID_DICT['11']] = "0"
                else:
                    formatted_line[GSI.GSI_WORD_ID_DICT['11']] = line[8:24].lstrip('0')

                remaining_line = line[24:]

                field_list = remaining_line.split()  # returns lists of fields e.g. [22.324+0000000009042520, .....
                self.logger.debug('Field List: ' + str(field_list))

                # match the 2-digit identification with the key in the dictionary and format its corresponding value
                for field in field_list:

                    two_digit_id = field[0:2]

                    try:
                        field_name = GSI.GSI_WORD_ID_DICT[two_digit_id]
                        self.logger.debug(two_digit_id + '  ' + field_name)

                        # Strip off unnecessary digits to make the number readable
                        field_value = field[7:].lstrip('0')

                        # apply special formatting rules to particular fields
                        if two_digit_id == '51':
                            field_value = self.format_prism_constant(field_value)

                        elif two_digit_id == '19':
                            field_value = self.format_timestamp(field_value)

                        elif two_digit_id in ('21', '22'):  # horizontal or vertical angles
                            field_value = self.format_angles(field_value)

                        elif two_digit_id in ('31', '32', '33', '87', '88'):    # distances
                            field_value = self.format_3dp(field_value)

                        elif field_value == "":

                            field_value = 'N/A'

                        formatted_line[field_name] = field_value

                    except KeyError:
                        self.logger.exception(
                            f"File doesn't appear to be a valid GSI file.  Missing Key ID: {field_value}")
                        raise CorruptedGSIFileError

                self.logger.info('Formatted Line: ' + str(formatted_line))
                self.formatted_lines.append(formatted_line)

    def format_timestamp(self, timestamp):

        try:

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

        except ValueError:
            self.logger.exception(f'Incorrect angle {angle}- cannot be formatted properly ')

        else:
            angle = f'{degrees.zfill(3)}° {minutes}\' {seconds}"'

        return angle

    @staticmethod
    def format_prism_constant(constant):

        constant = constant[3:].lstrip("0")

        if constant == "":
            return "0"
        return constant

    @staticmethod
    def format_3dp(number):

        try:

            return f'{int(number)*0.001:.3f}'

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
