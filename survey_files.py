import os
import shutil
import logging.config
from collections import OrderedDict
from utilities import Today
from pathlib import Path
from configurations import UserConfiguration, SurveyConfiguration

survey_config = SurveyConfiguration()

ts60_id_list = survey_config.ts60_id_list.split()
ts15_id_list = survey_config.ts15_id_list.split()
ms60_id_list = survey_config.ms60_id_list.split()


class SDCard:

    def __init__(self, sd_root_dir):
        self.sd_root_dir = sd_root_dir

        self.sd_folder_list = next(os.walk(self.sd_root_dir))[1]
        self.sd_file_list = next(os.walk(self.sd_root_dir))[2]

        self.dbx_directory_path = os.path.join(self.sd_root_dir, 'DBX')
        self.gsi_directory_path = os.path.join(self.sd_root_dir, 'Gsi')
        self.dbx_files = self.get_dbx_files()
        self.gsi_files = self.get_gsi_files()


    def get_dbx_files(self):

        dbx_file_list = []

        if os.path.isdir(self.dbx_directory_path):
            # search through all files and folders in the DBX directory
            for filename in os.listdir(self.dbx_directory_path):
                if os.path.isdir(filename):
                    dbx_file_list.append(SurveyFolder.build_survey_folder(filename))
                else:   # is a file
                    dbx_file_list.append(File.build_survey_file(filename))

        return dbx_file_list


    def get_gsi_files(self):

        gsi_file_list = []

        if os.path.isdir(self.gsi_directory_path):
            # search through all files and folders in the DBX directory
            for filename in os.listdir(self.gsi_directory_path):
                    gsi_file_list.append(GSIFile(filename))

        return gsi_file_list



class Folder:

    def __init__(self, filepath):
        self.filepath = filepath
        self.basename = os.path.basename(self.filepath)
        self.root_dir = Path(self.filepath).parent


class File:

    GPS_FILE = 'GPS'
    GSI_FILE = 'GSI'

    def __init__(self, filepath):
        self.filepath = filepath
        self.basename = os.path.basename(self.filepath)
        self.basename_no_ext = self.basename[:-4]
        self.file_suffix = Path(self.filepath).suffix.upper()
        self.root_dir = Path(self.filepath).parent

        
    @staticmethod
    def build_survey_file(filepath):

        file_type = Path(filepath).suffix.upper()

        if file_type == File.GPS_FILE:
            return GPSFile(filepath)
        elif file_type == File.GSI_FILE:
            return GSIFile(filepath)


class GSIFile(File):

    def __init__(self, filepath):
        super().__init__(filepath)
        self.filepath = filepath
        self.file_type = 'GPS'


class GPSFile(File):

    def __init__(self, filepath):
        super().__init__(filepath)
        self.filepath = filepath
        self.file_type = 'GSI'


class SurveyFolder(Folder):
    GPS_FOLDER = 'GPS_FOLDER'
    TS_FOLDER = 'TS_FOLDER'

    def __init__(self, filepath):
        super().__init__(filepath)
        self.filepath = filepath

    @staticmethod
    def get_folder_type(basename):

        if 'GPS' in basename:
            return SurveyFolder.GPS_FOLDER
        elif any(x in basename for x in ts60_id_list):
            return SurveyFolder.TS_FOLDER
        elif any(x in basename for x in ts15_id_list):
            return SurveyFolder.TS_FOLDER
        elif any(x in basename for x in ms60_id_list):
            return SurveyFolder.TS_FOLDER
        else:
            return ""

    @staticmethod
    def build_survey_folder(filepath):

        folder_type = SurveyFolder.get_folder_type(os.path.basename(filepath))
        if folder_type == SurveyFolder.GPS_FOLDER:
            return GPSFolder(filepath)
        elif folder_type == SurveyFolder.TS_FOLDER:
            return TSFolder(filepath)


class TSFolder(Folder):

    def __init__(self, filepath):
        super().__init__(filepath)
        self.folder_type = SurveyFolder.TS_FOLDER
        self.ts_instrument = self.get_ts_instrument()


    def get_ts_instrument(self):

        if any(x in self.basename for x in ts60_id_list):
            self.ts_instrument = 'TS_60'
        elif any(x in self.basename for x in ts15_id_list):
            self.ts_instrument = 'TS_15'
        elif any(x in self.basename for x in ms60_id_list):
            self.ts_instrument = 'MS_60'
        else:
            self.ts_instrument = ""

        return self.ts_instrument


class GPSFolder(Folder):

    def __init__(self, filepath):
        super().__init__(filepath)
        self.folder_type = SurveyFolder.GPS_FOLDER
