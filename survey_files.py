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

# Total station instruments
TS60 = 'TS60'
MS60 = 'MS60'
TS15 = 'TS15'


class SDCard:

    def __init__(self, sd_root_dir):
        self.sd_root_dir = sd_root_dir

        self.sd_folder_list = next(os.walk(self.sd_root_dir))[1]
        self.sd_file_list = next(os.walk(self.sd_root_dir))[2]

        self.dbx_directory_path = os.path.join(self.sd_root_dir, 'DBX')
        self.gsi_directory_path = os.path.join(self.sd_root_dir, 'Gsi')
        self.dbx_files = self.get_dbx_files()
        self.gsi_files = self.get_gsi_files()

        self.todays_gps_files = self.get_todays_gps_files()
        self.todays_ts_60_files = self.get_todays_ts_60_files()
        self.todays_ms_60_files = self.get_todays_ms_60_files()
        self.todays_ts_15_files = self.get_todays_ts_15_files()

    def get_dbx_files(self):

        dbx_file_list = []

        if os.path.isdir(self.dbx_directory_path):
            # search through all files and folders in the DBX directory
            for filename in os.listdir(self.dbx_directory_path):
                if os.path.isdir(filename):
                    dbx_file_list.append(SurveyFolder.build_survey_folder(filename))
                else:  # is a file
                    dbx_file_list.append(SingleFile.build_survey_file(filename))

        return dbx_file_list

    def get_gsi_files(self):

        gsi_file_list = []

        if os.path.isdir(self.gsi_directory_path):
            # search through all files and folders in the DBX directory
            for filename in os.listdir(self.gsi_directory_path):
                gsi_file_list.append(GSIFile(filename))

        return gsi_file_list

    def get_todays_gps_files(self):

        todays_gps_files = set()

        for file in self.dbx_files:
            if file.file_type == File.GPS_FILE:
                todays_gps_files.add((file))

        return todays_gps_files

    def get_todays_ts_60_files(self):

        ts_60_files = set()

        for file in self.dbx_files:
            if file.file_type == File.TS_FILE:
                if file.ts_instrument == TS60:
                    ts_60_files.add((file))

        return ts_60_files

    def get_todays_ms_60_files(self):

        ms_60_files = set()

        for file in self.dbx_files:
            if file.file_type == File.TS_FILE:
                if file.ts_instrument == MS60:
                    ms_60_files.add((file))

        return ms_60_files

    def get_todays_ts_15_files(self):

        ts_15_files = set()

        for file in self.dbx_files:
            if file.file_type == File.TS_FILE:
                if file.ts_instrument == TS15:
                    ts_15_files.add((file))

        return ts_15_files

    def get_list_all_files(self):

        return list(self.todays_gps_files) + list(self.todays_ts_60_files) + list(self.todays_ms_60_files) + list(self.todays_ts_15_files)


# base class for single files and folders
class File:
    GPS_FILE = 'GPS'
    GSI_FILE = 'GSI'
    TS_FILE = 'TS'

    def __init__(self, filepath):
        self.filepath = filepath
        self.basename = os.path.basename(self.filepath)
        self.root_dir = Path(self.filepath).parent
        self.file_type = ""


class Folder(File):
    GPS_FILE = 'GPS'
    GSI_FILE = 'GSI'

    def __init__(self, filepath):
        super().__init__(filepath)


class SingleFile(File):
    GPS_FILE = 'GPS'
    GSI_FILE = 'GSI'

    def __init__(self, filepath):
        super().__init__(filepath)
        self.basename_no_ext = self.basename[:-4]
        self.file_suffix = Path(self.filepath).suffix.upper()

    @staticmethod
    def build_survey_file(filepath):

        file_type = Path(filepath).suffix.upper()

        if file_type == SingleFile.GPS_FILE:
            return GPSFile(filepath)
        elif file_type == SingleFile.GSI_FILE:
            return GSIFile(filepath)


class GSIFile(SingleFile):

    def __init__(self, filepath):
        super().__init__(filepath)
        self.filepath = filepath
        self.file_type = File.TS_FILE


class GPSFile(SingleFile):

    def __init__(self, filepath):
        super().__init__(filepath)
        self.filepath = filepath
        self.file_type = File.GPS_FILE


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
        self.file_type = File.TS_FILE

    def get_ts_instrument(self):

        if any(x in self.basename for x in ts60_id_list):
            self.ts_instrument = TS60
        elif any(x in self.basename for x in ts15_id_list):
            self.ts_instrument = TS15
        elif any(x in self.basename for x in ms60_id_list):
            self.ts_instrument = MS60
        else:
            self.ts_instrument = ""

        return self.ts_instrument


class GPSFolder(Folder):

    def __init__(self, filepath):
        super().__init__(filepath)
        self.file_type = File.GPS_FILE
