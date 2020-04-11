from configparser import ConfigParser
import os

class UserConfiguration:
    section_file_directories = 'FILE DIRECTORIES'
    user_settings_directory = r"c:/SurveyAssist"

    if not os.path.isdir(user_settings_directory):
        os.makedirs(user_settings_directory)

    def __init__(self):

        # read in config file
        self.config_file_path = 'c:/SurveyAssist/user_settings.ini'
        self.config_parser = ConfigParser()
        self.config_parser.read(self.config_file_path)

        # FILE DIRECTORIES
        self.user_sd_root = self.config_parser.get(UserConfiguration, 'user_sd_root')

    def update(self, section, key, value):
        self.config_parser.set(section, key, value)

        with open(self.config_file_path, 'w+') as f:
            self.config_parser.write(f)
