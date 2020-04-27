import re
from decimal import Decimal
from collections import OrderedDict


class CoordinateFile:
    re_pattern_easting = re.compile(r'\b\d{6}\.\d{4}')
    re_pattern_northing = re.compile(r'\b\d{7}\.\d{4}')
    re_pattern_elevation = re.compile(r'\b\d{1,3}\.\d{3,4}')
    re_pattern_point_crd = re.compile(r'\b\S+\b')
    re_pattern_point_std = re.compile(r'"\S+"')
    re_pattern_point_asc = re.compile(r'@#\S+')

    def __init__(self, coordinate_file_path, file_type):

        self.file_contents = None
        self.file_type = file_type
        self.coordinate_dictionary = OrderedDict()

        try:
            with open(coordinate_file_path, 'r') as f_orig:

                self.file_contents = f_orig.readlines()

        except Exception as ex:
            print(ex, type(ex))

        else:
            self.format_coordinate_file()
            self.build_coordinate_dictionary(file_type)

    @staticmethod
    def getCordinateFile(filepath, filetype):
        if filetype.upper() == 'ASC':
            return ASCCoordinateFile(filepath)
        elif filetype.upper() == 'CRD':
            return CRDCoordinateFile(filepath)
        elif filetype.upper() == 'STD':
            return STDCoordinateFile(filepath)
        else:
            return CoordinateFile(filepath)

    # Override if the coordinate file needs to be formatted before searching for coordinates
    def format_coordinate_file(self):
        pass

    def get_point_coordinates(self, point):

        if point in self.coordinate_dictionary.keys():
            return self.coordinate_dictionary[point]

    def build_coordinate_dictionary(self, file_type):

        for coordinate_contents_line in self.file_contents:

            point_coordinate_dict = {}
            point_name = ""

            try:
                # grab easting and northing for this station
                easting_match = self.re_pattern_easting.search(coordinate_contents_line)
                northing_match = self.re_pattern_northing.search(coordinate_contents_line)
                elevation_match = self.re_pattern_elevation.search(coordinate_contents_line)

                if file_type == 'CRD':

                    point_match = self.re_pattern_point_crd.search(coordinate_contents_line)
                    point_name = point_match.group()

                elif file_type == 'STD':

                    point_match = self.re_pattern_point_std.search(coordinate_contents_line)
                    point_name = point_match.group().replace('"', '')

                elif file_type == 'ASC':

                    point_match = self.re_pattern_point_asc.search(coordinate_contents_line)
                    point_name = point_match.group().replace('@#', '')

                # point_name = point_match.group()
                # point_name = point_name.replace('"', '')  # for STD files
                # point_name = point_name.replace('@#', '')  # for asc files

                point_coordinate_dict['Eastings'] = easting_match.group()
                point_coordinate_dict['Northings'] = northing_match.group()

                # grab the elevation coordinate if required by the fixed file
                try:
                    point_coordinate_dict['Elevation'] = elevation_match.group()
                except ValueError:
                    # elevation doesnt exist in this coordinate file
                    pass
                except AttributeError:
                    # elevation doesnt exist in this coordinate file
                    pass
                finally:
                    self.coordinate_dictionary[point_name] = point_coordinate_dict

            except ValueError:
                # probabaly a blank line
                pass


class CRDCoordinateFile(CoordinateFile):

    def __init__(self, coordinate_file_path):
        super().__init__(coordinate_file_path, 'CRD')

    def format_coordinate_file(self):

        del self.file_contents[0: 10]
        if 'DESCRIPTION' in self.file_contents[0]:
            # remove 'description' line plus following blank space'
            del self.file_contents[0:2]

        else:
            raise Exception('CRD file Header should contain only 12 rows')


class ASCCoordinateFile(CoordinateFile):

    def __init__(self, coordinate_file_path):
        super().__init__(coordinate_file_path, 'ASC')

    def format_coordinate_file(self):

        updated_asc_file = []

        for line in self.file_contents:
            # need to remove  the 22.3### REF 34 info so the coorindate file can find the elevation properly
            # problem is sometimes RED isnt in the file
            if '@%' not in line:
                line_list = line.split()
                stripped_line_list = line_list[0:self.getIndexElevation(line) + 1]
                updated_asc_file.append('   '.join(stripped_line_list))

        self.file_contents = updated_asc_file

        # del self.file_contents[0: 3]
        # if '@%Projection set' in self.file_contents[0]:
        #     del self.file_contents[0]
        # else:
        #     raise Exception('Unsupported file type')

    def getIndexElevation(self, line):

        northing_value = CoordinateFile.re_pattern_northing.search(line).group()

        for index, data in enumerate(line.split()):
            if northing_value == data:
                # the next index must be elevation
                return index + 1


class STDCoordinateFile(CoordinateFile):

    def __init__(self, coordinate_file_path):
        super().__init__(coordinate_file_path, 'STD')

        self.updated_std_contents = ""

    def update_weighting(self, weight_dict):

        easting = Decimal(weight_dict['Easting'])
        northing = Decimal(weight_dict['Northing'])
        elevation = Decimal(weight_dict['Elevation'])

        for line in self.file_contents:
            line_sections = line.split()

            if len(line_sections) == 6:  # no elevation data
                line_sections[3] = str(easting)
                line_sections[4] = str(northing)

            elif len(line_sections) == 8:  # elevation data
                line_sections[4] = str(easting)
                line_sections[5] = str(northing)
                line_sections[6] = str(elevation)
            else:
                raise Exception("It appears that the coordinate file is no formatted properly")

            self.updated_std_contents += " ".join(line_sections) + '\n'

        print(self.updated_std_contents)

        return self.updated_std_contents


class FixedFile:

    def __init__(self, fixed_file_path):

        self.fixed_file_path = fixed_file_path
        self.fixed_file_contents = None
        self.station_list = []
        self.updated_file_contents = ""

        with open(fixed_file_path, 'r') as f_orig:
            self.fixed_file_contents = f_orig.readlines()

    def get_stations(self):
        for line in self.fixed_file_contents:
            station = FixedFile.get_station(line)
            if station != "UNKNOWN":
                self.station_list.append(station)
        return self.station_list

    # 2D or 3D adjustment
    def get_dimension(self):

        line_list = self.fixed_file_contents[0].split()
        dimension = '2D'

        return '2D' if len(line_list) == 4 else '3D'

    @staticmethod
    def get_station(line):

        station = "UNKNOWN"

        # Line number is at the start of a string and contains digits followed by whiespace
        re_pattern = re.compile(r'"\w+"')
        match = re_pattern.search(line)

        # strip of quotation marks and add to station list
        if match is not None:
            station = match.group()[1:-1]

        return station

    @staticmethod
    def get_line_number(line):

        line_number = "???"

        # Line number is at the start of a line
        re_pattern = re.compile(r'^\d+\s')

        match = re_pattern.search(line)

        if match:
            line_number = match.group().strip()

        return line_number

    # updates the fixed file and returns a list of stations that were found and updated in the coordinate file
    def update(self, coordinate_file):

        stations_updated = []
        elevation = ""

        for line in self.fixed_file_contents:

            # Get coordinates for this station if exists in the coordinate file
            station = self.get_station(line)

            coordinate_dict = coordinate_file.get_point_coordinates(station)

            # update fixed_file coordinate if a match was found
            if coordinate_dict:
                easting = coordinate_dict['Eastings']
                northing = coordinate_dict['Northings']
                try:
                    elevation = coordinate_dict['Elevation']
                except Exception:
                    pass  # elevation may not exist in some coordinate files

                updated_line = self.get_line_number(line) + ' ' + easting + '  ' + northing + '  ' + elevation + ' "' + \
                               station + '"\n'
                self.updated_file_contents += updated_line
                stations_updated.append(station)

            else:
                self.updated_file_contents += line

        # update fixed file with updated contents
        with open(self.fixed_file_path, 'w') as f_update:
            f_update.write(self.updated_file_contents)

        return stations_updated
