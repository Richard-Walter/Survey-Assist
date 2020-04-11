from configparser import ConfigParser


class UserConfiguration:


    section_file_directories = 'FILE DIRECTORIES'

    def __init__(self):

        # @ todo create a c:/SurveyAssist/user_settings.ini if one doesnt exist

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

