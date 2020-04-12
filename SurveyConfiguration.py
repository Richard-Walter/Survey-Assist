from configparser import ConfigParser


class SurveyConfiguration:

    section_instrument = 'INSTRUMENT'
    section_survey_tolerances = 'SURVEY_TOLERANCES'
    section_config_files = 'CONFIGURATION'
    section_file_directories = 'FILE DIRECTORIES'

    precision_value_list = ['3dp', '4dp']
    default_instrument_values = {
        'instrument_precision': '3dp'
    }

    default_survey_tolerance_values = {
        'eastings': '0.010',
        'northings': '0.010',
        'height': '0.015',
    }

    default_flfr_survey_tolerance_values = {
        'flfr_eastings': '0.005',
        'flfr_northings': '0.005',
        'flfr_height': '0.005',
    }

    default_file_directories_values = {
        'last_used': 'GSIFiles/',
        'fixed_file_dir': 'c:/LS/Data/'
    }

    def __init__(self):
        self.config_file_path = './settings.ini'

        self.config_parser = ConfigParser()
        self.precision_value = '3dp'

        # read in config file
        self.config_parser.read(self.config_file_path)

        # INSTRUMENT PRECISION
        self.precision_value = self.config_parser.get(SurveyConfiguration.section_instrument, 'instrument_precision')

        # SURVEY TOLERANCES
        self.easting_tolerance = self.config_parser.get(SurveyConfiguration.section_survey_tolerances, 'eastings')
        self.northing_tolerance = self.config_parser.get(SurveyConfiguration.section_survey_tolerances, 'northings')
        self.height_tolerance = self.config_parser.get(SurveyConfiguration.section_survey_tolerances, 'height')
        self.flfr_easting_tolerance = self.config_parser.get(SurveyConfiguration.section_survey_tolerances, 'flfr_eastings')
        self.flfr_northing_tolerance = self.config_parser.get(SurveyConfiguration.section_survey_tolerances, 'flfr_northings')
        self.flfr_height_tolerance = self.config_parser.get(SurveyConfiguration.section_survey_tolerances, 'flfr_height')

        self.sorted_station_config = self.config_parser.get(SurveyConfiguration.section_config_files, 'sorted_station_config')

        # FILE DIRECTORIES
        self.last_used_file_dir = self.config_parser.get(SurveyConfiguration.section_file_directories, 'last_used')
        self.fixed_file_dir = self.config_parser.get(SurveyConfiguration.section_file_directories, 'fixed_file_dir')
        self.root_job_directory = self.config_parser.get(SurveyConfiguration.section_file_directories, 'root_job_directory')
        self.diary_directory = self.config_parser.get(SurveyConfiguration.section_file_directories, 'diary_directory')
        self.diary_backup = self.config_parser.get(SurveyConfiguration.section_file_directories, 'diary_backup')
        self.current_year = self.config_parser.get(SurveyConfiguration.section_file_directories, 'current_year')
        self.default_survey_type = self.config_parser.get(SurveyConfiguration.section_file_directories, 'default_survey_type')
        self.todays_dated_directory = self.config_parser.get(SurveyConfiguration.section_file_directories, 'todays_dated_directory')



    def update(self, section, key, value):

        self.config_parser.set(section, key, value)

        with open(self.config_file_path, 'w+') as f:
            self.config_parser.write(f)


    def create_config_file(self, instrument_values, survey_tolerance_values, configuration_values):
        self.config_parser[SurveyConfiguration.section_instrument] = instrument_values

        self.config_parser[SurveyConfiguration.section_survey_tolerances] = survey_tolerance_values

        self.config_parser[SurveyConfiguration.section_config_files] = configuration_values

        with open(self.config_file_path, 'w') as f:
            self.config_parser.write(f)
