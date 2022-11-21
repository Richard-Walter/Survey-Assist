from utilities import Today
from pathlib import Path
from configurations import *
import os

survey_config = SurveyConfiguration()

ts60_id_list = survey_config.ts60_id_list.split()
ts15_id_list = survey_config.ts15_id_list.split()
ms60_id_list = survey_config.ms60_id_list.split()
ts16_id_list = survey_config.ts16_id_list.split()

# Total station instruments
TS60 = 'TS60'
MS60 = 'MS60'
TS15 = 'TS15'
TS16 = 'TS16'


class SDCard:

    def __init__(self, sd_root_dir):
        self.sd_root_dir = sd_root_dir

        self.sd_folder_list = next(os.walk(self.sd_root_dir))[1]
        self.sd_file_list = next(os.walk(self.sd_root_dir))[2]

        self.dbx_directory_path = os.path.join(self.sd_root_dir, 'DBX')
        self.gsi_directory_path = os.path.join(self.sd_root_dir, 'Gsi')
        self.data_directory_path = os.path.join(self.sd_root_dir, 'Data')
        self.dbx_files = self.get_dbx_files()
        self.gsi_files = self.get_gsi_files()
        self.data_files = self.get_data_files()

        self.todays_gps_files = self.get_todays_gps_files()
        self.todays_ts_60_files = self.get_todays_ts_60_files()
        self.todays_ms_60_files = self.get_todays_ms_60_files()
        self.todays_ts_15_files = self.get_todays_ts_15_files()
        self.todays_ts_16_files = self.get_todays_ts_16_files()

        self.rail_monitoring_files = []

    def get_dbx_files(self):

        dbx_file_list = []

        if os.path.isdir(self.dbx_directory_path):
            # search through all files and folders in the DBX directory
            for filename in os.listdir(self.dbx_directory_path):
                full_filename = os.path.join(self.dbx_directory_path, filename)
                if os.path.isdir(full_filename):
                    dbx_file_list.append(SurveyFolder.build_survey_folder(full_filename))
                else:  # is a file
                    dbx_file_list.append(SingleFile.build_survey_file(full_filename))

        return self.filter_NoneTypes(dbx_file_list)  # remove any None Types found (i.e random files or rail surveys - These are handled seperately

    def get_gsi_files(self):

        gsi_file_list = []

        if os.path.isdir(self.gsi_directory_path):
            # search through all files and folders in the DBX directory
            for filename in os.listdir(self.gsi_directory_path):
                full_filename = os.path.join(self.gsi_directory_path, filename)
                gsi_file_list.append(GSIFile(full_filename))

        return self.filter_NoneTypes(gsi_file_list)

    def get_data_files(self):

        data_file_list = []

        if os.path.isdir(self.data_directory_path):
            # search through all files and folders in the Data directory
            for filename in os.listdir(self.data_directory_path):
                full_filename = os.path.join(self.data_directory_path, filename)
                data_file_list.append(GPSFile(full_filename))

        return self.filter_NoneTypes(data_file_list)

    def filter_NoneTypes(self, file_list):

        filtered_list = []
        for file in file_list:
            if file == None:
                continue
            else:
                filtered_list.append(file)

        return filtered_list

    def get_todays_gps_files(self):

        todays_gps_files = set()

        if self.dbx_files:

            for file in self.dbx_files:

                #frist, determine if it is a folder (GPS is viva type)
                if isinstance(file, GPSFolder):
                    if Today.todays_date_reversed in file.basename:
                        todays_gps_files.add(file)

                # its a single file (1200 series GPS)
                elif any(x in file.basename for x in ['GPSE', 'GPSF', 'GPSG', 'GPSH']):

                    if Today.todays_date_month_day_format in file.basename:

                        todays_gps_files.add(file)
                        todays_date_found = True

                    # some GPSE files (e.g. .i25, .m25) dont have a date.  Just grab them all
                    elif 'GPSE' in file.basename:
                        # if file.file_suffix.upper() in ['.I25', '.I23', '.M25', '.M23']:
                        if any(x in file.file_suffix.upper() for x in ['.I', '.M']):
                            # before adding these files, check that at least one other file in thei dierectory contains todays date
                            for dbxfile in self.dbx_files:
                                if Today.todays_date_month_day_format in dbxfile.basename:
                                    todays_gps_files.add(file)
                                    break

        if self.data_files:
            for file in self.data_files:

                if file.file_type == File.GPS_FILE and Today.todays_date_reversed in file.basename:
                    todays_gps_files.add(file)

        return todays_gps_files

    def get_todays_ts_60_files(self):

        ts_60_files = set()

        if self.dbx_files:

            for file in self.dbx_files:
                if file.file_type == File.TS_FILE and Today.todays_date_reversed in file.basename:
                    if file.ts_instrument == TS60:
                        ts_60_files.add((file))

                        # get corresponding GSI file
                        for file in self.gsi_files:
                            if Today.todays_date_reversed in file.basename:
                                ts_60_files.add(file)

        return ts_60_files

    def get_todays_ms_60_files(self):

        ms_60_files = set()

        if self.dbx_files:

            for file in self.dbx_files:
                if file.file_type == File.TS_FILE and Today.todays_date_reversed in file.basename:
                    if file.ts_instrument == MS60:
                        ms_60_files.add((file))

                        # get corresponding GSI file
                        for file in self.gsi_files:
                            if Today.todays_date_reversed in file.basename:
                                ms_60_files.add(file)

        return ms_60_files

    def get_todays_ts_15_files(self):

        ts_15_files = set()

        if self.dbx_files:

            for file in self.dbx_files:
                if file.file_type == File.TS_FILE and Today.todays_date_reversed in file.basename:
                    if file.ts_instrument == TS15:
                        ts_15_files.add((file))

                        # get corresponding GSI file
                        for file in self.gsi_files:
                            if Today.todays_date_reversed in file.basename:
                                ts_15_files.add(file)

        return ts_15_files

    def get_todays_ts_16_files(self):

        ts_16_files = set()

        if self.dbx_files:

            for file in self.dbx_files:
                if file.file_type == File.TS_FILE and Today.todays_date_reversed in file.basename:
                    if file.ts_instrument == TS16:
                        ts_16_files.add((file))

                        # get corresponding GSI file
                        for file in self.gsi_files:
                            if Today.todays_date_reversed in file.basename:
                                ts_16_files.add(file)

        return ts_16_files

    def get_list_all_todays_files(self):

        return list(self.todays_gps_files) + list(self.todays_ts_60_files) + list(self.todays_ms_60_files) + list(self.todays_ts_16_files) + list(
            self.todays_ts_15_files) + list(self.rail_monitoring_files)

    @staticmethod
    def user_SD_dir_exists(user_dir):
        if os.path.exists(user_dir):
            return True
        else:
            return False

    def get_rail_survey_files(self, longwall_area):

        rail_monitoring_files = set()

        for file in self.dbx_files:
            # if survey_config.current_rail_monitoring_file_name in file.basename:
            if longwall_area in file.basename and "MON" in file.basename:
                rail_monitoring_files.add(file)

                # get corresponding GSI file
                for file in self.gsi_files:
                    if ("MON" in file.basename) and (longwall_area in file.basename):
                        rail_monitoring_files.add(file)

        self.rail_monitoring_files = rail_monitoring_files

        return rail_monitoring_files


# base class for single files and folders
class File:
    GPS_FILE = 'GPS'
    GSI_FILE = 'GSI'
    TS_FILE = 'TS'

    GSI_FILE_SUFFIX = '.GSI'

    def __init__(self, filepath):
        self.filepath = filepath
        self.basename = os.path.basename(self.filepath)
        self.root_dir = Path(self.filepath).parent
        self.file_type = ""


class Folder(File):

    def __init__(self, filepath):
        super().__init__(filepath)
        self.file_suffix = ""


class SingleFile(File):

    def __init__(self, filepath):
        super().__init__(filepath)
        self.basename_no_ext = self.basename[:-4]
        self.file_suffix = Path(self.filepath).suffix.upper()

    @staticmethod
    def build_survey_file(filepath):
        file_type = Path(filepath).suffix.upper()

        if 'GPS' in os.path.basename(filepath):
            return GPSFile(filepath)


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
        elif any(x in basename for x in ts16_id_list):
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


class TSFolder(SurveyFolder):

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
        elif any(x in self.basename for x in ts16_id_list):
            self.ts_instrument = TS16
        else:
            self.ts_instrument = ""

        return self.ts_instrument


class GPSFolder(SurveyFolder):

    def __init__(self, filepath):
        super().__init__(filepath)
        self.file_type = File.GPS_FILE
