from configparser import ConfigParser
import os
import shutil


class UserConfiguration:
    section_file_directories = 'FILE DIRECTORIES'
    user_settings_directory = r"c:/SurveyAssist"
    user_settings_file_path = r"c:/SurveyAssist/user_settings.ini"
    default_user_settings_path = r"default_user_settings.ini"

    if not os.path.isdir(user_settings_directory):
        os.makedirs(user_settings_directory)

    if not os.path.exists(user_settings_file_path):
        shutil.copy(default_user_settings_path, user_settings_file_path)

    def __init__(self):

        # read in config file
        self.config_file_path = 'c:/SurveyAssist/user_settings.ini'
        self.config_parser = ConfigParser()
        self.config_parser.read(self.config_file_path)

        # FILE DIRECTORIES
        self.user_sd_root = self.config_parser.get(UserConfiguration.section_file_directories, 'user_sd_root')

    def update(self, section, key, value):
        self.config_parser.set(section, key, value)

        with open(self.config_file_path, 'w+') as f:
            self.config_parser.write(f)
