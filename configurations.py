from configparser import ConfigParser
import shutil


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
        'fixed_file_dir': 'c:/LS/Data/'
    }

    def __init__(self):
        self.config_file_path = 'Config Files/settings.ini'

        self.config_parser = ConfigParser()
        self.precision_value = '3dp'  # default value

        # read in config file
        self.config_parser.read(self.config_file_path)

        # INSTRUMENT PRECISION
        self.precision_value = self.config_parser.get(SurveyConfiguration.section_instrument, 'instrument_precision')
        self.ts60_id_list = self.config_parser.get(SurveyConfiguration.section_instrument, 'ts60_id_list')
        self.ms60_id_list = self.config_parser.get(SurveyConfiguration.section_instrument, 'ms60_id_list')
        self.ts15_id_list = self.config_parser.get(SurveyConfiguration.section_instrument, 'ts15_id_list')
        self.ts16_id_list = self.config_parser.get(SurveyConfiguration.section_instrument, 'ts16_id_list')

        # SURVEY TOLERANCES
        self.easting_tolerance = self.config_parser.get(SurveyConfiguration.section_survey_tolerances, 'eastings')
        self.northing_tolerance = self.config_parser.get(SurveyConfiguration.section_survey_tolerances, 'northings')
        self.height_tolerance = self.config_parser.get(SurveyConfiguration.section_survey_tolerances, 'height')
        self.flfr_easting_tolerance = self.config_parser.get(SurveyConfiguration.section_survey_tolerances, 'flfr_eastings')
        self.flfr_northing_tolerance = self.config_parser.get(SurveyConfiguration.section_survey_tolerances, 'flfr_northings')
        self.flfr_height_tolerance = self.config_parser.get(SurveyConfiguration.section_survey_tolerances, 'flfr_height')

        self.sorted_station_config = self.config_parser.get(SurveyConfiguration.section_config_files, 'sorted_station_config')
        self.monitoring_file_search_keys = self.config_parser.get(SurveyConfiguration.section_config_files, 'monitoring_file_search_keys')
        self.prism_constants_names = self.config_parser.get(SurveyConfiguration.section_config_files, 'prism_constants_names')

        # FILE DIRECTORIES
        self.last_used_file_dir = ""
        self.compnet_data_dir = self.config_parser.get(SurveyConfiguration.section_file_directories, 'compnet_data_dir')
        self.compnet_raw_dir = self.config_parser.get(SurveyConfiguration.section_file_directories, 'compnet_raw_dir')
        self.gnss_temp_dir = self.config_parser.get(SurveyConfiguration.section_file_directories, 'gnss_temp_dir')
        self.root_job_directory = self.config_parser.get(SurveyConfiguration.section_file_directories, 'root_job_directory')
        self.diary_directory = self.config_parser.get(SurveyConfiguration.section_file_directories, 'diary_directory')
        self.diary_backup = self.config_parser.get(SurveyConfiguration.section_file_directories, 'diary_backup')
        self.current_year = self.config_parser.get(SurveyConfiguration.section_file_directories, 'current_year')
        self.default_survey_type = self.config_parser.get(SurveyConfiguration.section_file_directories, 'default_survey_type')
        self.todays_dated_directory = ""
        self.current_rail_monitoring_file_name = self.config_parser.get(SurveyConfiguration.section_file_directories,
                                                                        'current_rail_monitoring_file_name')
        self.job_tracker_filename = self.config_parser.get(SurveyConfiguration.section_file_directories, 'job_tracker_filename')

    def update(self, section, key, value):
        self.config_parser.set(section, key, value)

        with open(self.config_file_path, 'w+') as f:
            self.config_parser.write(f)


class UserConfiguration:
    section_file_directories = 'FILE DIRECTORIES'
    section_user_profile = 'PROFILE'
    user_settings_directory = r"c:/SurveyAssist"
    user_settings_file_path = r"c:/SurveyAssist/user_settings.ini"
    default_user_settings_path = r"Config Files/default_user_settings.ini"

    def __init__(self):

        # read in config file
        self.config_file_path = 'c:/SurveyAssist/user_settings.ini'
        self.config_parser = ConfigParser()
        self.config_parser.read(self.config_file_path)

        # File Directories and User Profile
        try:
            self.user_sd_root = self.config_parser.get(UserConfiguration.section_file_directories, 'user_sd_root')
            self.usb_root = self.config_parser.get(UserConfiguration.section_file_directories, 'usb_root')
            self.user_initials = self.config_parser.get(UserConfiguration.section_user_profile, 'user_initials')

        except Exception:

            # Copy over default user settings if we have a new user
            shutil.copy(UserConfiguration.default_user_settings_path, UserConfiguration.user_settings_file_path)
            self.user_sd_root = self.config_parser.get(UserConfiguration.section_file_directories, 'user_sd_root')
            self.usb_root = self.config_parser.get(UserConfiguration.section_file_directories, 'usb_root')
            self.user_initials = self.config_parser.get(UserConfiguration.section_user_profile, 'user_initials')

    def update(self, section, key, value):
        self.config_parser.set(section, key, value)

        with open(self.config_file_path, 'w+') as f:
            self.config_parser.write(f)
