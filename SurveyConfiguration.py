from configparser import ConfigParser


class SurveyConfiguration:
    section_instrument = 'INSTRUMENT'
    section_survey_tolerances = 'SURVEY_TOLERANCES'
    precision_value_list = ['3dp', '4dp']
    default_instrument_values = {
        'instrument_precision': '3dp'
    }

    default_survey_tolerance_values = {
        'eastings': '0.010',
        'northings': '0.010',
        'height': '0.015'
    }

    def __init__(self):
        self.config_file_path = './settings.ini'

        self.config_parser = ConfigParser()
        self.precision_value = '3dp'

        # read in config file
        self.config_parser.read(self.config_file_path)
        self.precision_value = self.config_parser.get(SurveyConfiguration.section_instrument,
                                                      'instrument_precision')
        self.easting_tolerance = self.config_parser.get(SurveyConfiguration.section_survey_tolerances, 'eastings')
        self.northing_tolerance = self.config_parser.get(SurveyConfiguration.section_survey_tolerances, 'northings')
        self.height_tolerance = self.config_parser.get(SurveyConfiguration.section_survey_tolerances, 'height')

    def update(self, section, key, value):
        pass

    def create_config_file(self, instrument_values, survey_tolerance_values):
        self.config_parser[SurveyConfiguration.section_instrument] = instrument_values

        self.config_parser[SurveyConfiguration.section_survey_tolerances] = survey_tolerance_values

        with open(self.config_file_path, 'w') as f:
            self.config_parser.write(f)
