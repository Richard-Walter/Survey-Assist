#! python3

""" This program reads in a GSI file from a Leica 'Total Station' and displays the file
in a clearer, more user-friendly format.  You can then execute queries on this data to extract relevant information.
It also checks for survey errors in a survey, and contains some utilities to help with CompNet.

VERSION HISTORY
---------------
v1.0 Initial Release

NOTES
------
Compnet uses only observations:  slope distance, horizontal and vertical angle, target height, station height.  GSI Coordinates are not used

KNOWN BUGS
-Sometimes a GSI is loaded yet the taskbar says please select a GSI.  You can't delete lines or export csv.
-Importing SD card - sometimes it says files transferred, but nothing actually transferred.  I could put a check that files exists after copying?

"""

# TODO re-create Job tracker when hiding, creating and tracking a job.
# Todo - fix sync errors when a manual entry is made whilst job tracker is open and a previous job is then updated

from openpyxl.styles import Border, Side
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.formatting.rule import DataBarRule
from openpyxl.styles import Font
from openpyxl.styles import Alignment
import tkinter.messagebox
import logging.config
from job_tracker import *
from tkinter import filedialog
from GSI import *
from GSI import GSIDatabase, CorruptedGSIFileError, GSIFileContents
from decimal import *
from compnet import CRDCoordinateFile, ASCCoordinateFile, STDCoordinateFile, CoordinateFile, FixedFile
from utilities import *
from survey_files import *
from shutil import copyfile
from distutils.dir_util import copy_tree

todays_date = Today.todays_date

gui_app = None


class MenuBar(tk.Frame):
    filename_path = ""

    def __init__(self, master):
        super().__init__(master)

        self.master = master

        # for importing rali survey
        self.ts_used = ""
        self.compnet_working_dir = ""

        # check is user settings directory and/or file exists on the users computer
        if not os.path.isdir(UserConfiguration.user_settings_directory):
            os.makedirs(UserConfiguration.user_settings_directory)

        if not os.path.exists(UserConfiguration.user_settings_file_path):
            shutil.copy(UserConfiguration.default_user_settings_path, UserConfiguration.user_settings_file_path)

            tk.messagebox.showinfo("User Settings", "A new user_settings file has been created in C:\SurveyAssist.\n\nPlease configure "
                                                    "your user settings before continuing by updating this file.\n\n"
                                                    "USER_SD_ROOT:  This is the root directory when you insert a SD card into your "
                                                    "computer\n\n"
                                                    "USB_ROOT:  This is the root directory when you plug in a usb device (e.g. to "
                                                    "transfer 1200 gps data)\n\n"
                                                    "USER_INITIALS: Required for Job Tracker"
                                                    "\n\nSurvey Assist will need to be re-started")

            os.startfile("c:/SurveyAssist/user_settings.ini")
            exit()

        self.user_config = UserConfiguration()
        self.monitoring_job_dir = os.path.join(survey_config.root_job_directory, survey_config.current_year, survey_config.default_survey_type)
        self.query_dialog_box = None
        self.filename_path = ""
        self.compnet_working_dir = ""

        self.menu_bar = tk.Menu(self.master)
        self.master.config(menu=self.menu_bar)

        # File Menu
        self.file_sub_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.file_sub_menu.add_command(label="Open GSI...", command=self.choose_gsi_file)
        self.file_sub_menu.add_command(label="Create Dated Directory...", command=lambda: self.new_dated_directory(False))
        self.file_sub_menu.add_command(label="Choose Dated Directory...", command=self.choose_dated_directory)
        self.file_sub_menu.add_command(label="Choose Compnet Job Directory...", command=self.choose_compnet_directory)
        self.file_sub_menu.add_command(label="Create Job Directory...", command=self.new_job_directoy)
        self.file_sub_menu.add_command(label="Import SD Data", command=self.import_sd_data)
        self.file_sub_menu.add_separator()
        self.file_sub_menu.add_command(label="Monitoring - Create (beta)", command=self.monitoring_create)
        self.file_sub_menu.add_command(label="Monitoring - Update Coordinates", command=self.monitoring_update_coords, state="disabled")
        self.file_sub_menu.add_command(label="Monitoring - Update Labels", command=self.monitoring_update_labels, state="disabled")
        self.file_sub_menu.add_command(label="Monitoring - Rename Updated Files", command=self.monitoring_rename_updated_files, state="disabled")
        self.file_sub_menu.add_separator()
        # self.file_sub_menu.add_command(label="Job Diary", command=self.job_diary)
        self.file_sub_menu.add_command(label="Settings", command=self.configure_survey)

        self.menu_bar.add_cascade(label="File", menu=self.file_sub_menu)

        # Edit menu
        self.edit_sub_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.edit_sub_menu.add_command(label="Delete all 2D Orientation Shots", command=self.delete_orientation_shots)
        self.edit_sub_menu.add_command(label="Change point name...", command=self.change_point_name)
        self.edit_sub_menu.add_command(label="Change target height...", command=self.change_target_height)
        self.edit_sub_menu.add_command(label="(BETA) Change station height...", command=self.change_station_height)
        self.edit_sub_menu.add_separator()
        self.edit_sub_menu.add_command(label="(BETA) Prism Constant - Fix single...", command=self.prism_constant_update_manually)
        self.edit_sub_menu.add_command(label="(BETA) Prism Constant - Fix batch ...", command=self.prism_constant_update_batch)

        self.menu_bar.add_cascade(label="Edit Survey", menu=self.edit_sub_menu, state="disabled")

        # Check menu
        self.check_sub_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.check_sub_menu.add_command(label="Check Control Naming ", command=self.check_control_naming)
        self.check_sub_menu.add_command(label="Check Prism Constants", command=self.check_prism_constants)
        self.check_sub_menu.add_command(label="Check Target Heights", command=self.check_target_heights)
        self.check_sub_menu.add_command(label="Check FL-FR", command=self.check_FLFR)
        self.check_sub_menu.add_command(label="Check Tolerances (3D)", command=self.check_3d_survey)
        self.check_sub_menu.add_command(label="Check All", command=self.check_3d_all)
        self.check_sub_menu.add_separator()
        self.check_sub_menu.add_command(label="Check Double Doubles", command=self.check_2d_doubles)
        self.check_sub_menu.add_separator()
        self.check_sub_menu.add_command(label="Compare with a similar survey...", command=self.compare_survey)
        self.check_sub_menu.add_separator()
        self.check_sub_menu.add_command(label="Query GSI...", command=self.display_query_input_box)
        self.menu_bar.add_cascade(label="Check Survey", menu=self.check_sub_menu, state="disabled")

        # Compnet menu
        self.compnet_sub_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.compnet_sub_menu.add_command(label="Setup New Compnet Job ...", command=self.create_compnet_job_folder)
        self.compnet_sub_menu.add_command(label="Update Fixed File...", command=self.update_fixed_file)
        self.compnet_sub_menu.add_command(label="Weight STD File ...", command=self.weight_STD_file)
        self.compnet_sub_menu.add_separator()
        self.compnet_sub_menu.add_command(label="Compare CRD Files...", command=self.compare_crd_files)
        self.compnet_sub_menu.add_command(label="Create control only GSI", command=self.create_control_only_gsi)
        self.compnet_sub_menu.add_command(label="Combine/Re-order GSI Files", command=self.combine_gsi_files)

        self.menu_bar.add_cascade(label="Compnet", menu=self.compnet_sub_menu)

        # Utilities menu
        self.utility_sub_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.utility_sub_menu.add_command(label="Export CSV", command=self.export_csv)
        self.utility_sub_menu.add_command(label="Create popup CSV from .ASC file", command=self.create_CSV_from_ASC)
        self.utility_sub_menu.add_command(label="Create popup CSV from .CRD file", command=self.create_CSV_from_CRD)
        self.utility_sub_menu.add_command(label="Copy todays GPS to GNSS temp directory", command=self.copy_gps_to_gnss_temp)
        self.utility_sub_menu.add_command(label="Create printable list of change points", command=self.create_list_of_change_points)

        self.menu_bar.add_cascade(label="Utilities", menu=self.utility_sub_menu)

        # Job Tracker
        self.job_tracker_sub_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.job_tracker_sub_menu.add_command(label="Track/Create a Job", command=self.job_tracker_open)
        self.job_tracker_sub_menu.add_command(label="Open in excel", command=self.job_tracker_open_excel)
        self.job_tracker_sub_menu.add_command(label="Hide", command=self.job_tracker_hide)
        self.menu_bar.add_cascade(label="Job Tracker", menu=self.job_tracker_sub_menu)

        # Help menu
        self.help_sub_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.help_sub_menu.add_command(label="Manual", command=self.open_manual)
        self.help_sub_menu.add_command(label="About", command=self.display_about_dialog_box)
        self.help_sub_menu.add_separator()
        self.help_sub_menu.add_command(label="Log File", command=self.open_log)

        self.menu_bar.add_cascade(label="Help", menu=self.help_sub_menu)

        # Exit menu
        self.menu_bar.add_command(label="Exit", command=self.client_exit)

    def choose_gsi_file(self):

        try:

            if survey_config.todays_dated_directory == "":
                intial_directory = self.monitoring_job_dir

            else:
                intial_directory = os.path.join(survey_config.todays_dated_directory, "TS")

            MenuBar.filename_path = tk.filedialog.askopenfilename(initialdir=intial_directory, title="Select file", filetypes=[("GSI Files", ".gsi")])
            # survey_config.update(SurveyConfiguration.section_file_directories, 'last_used', os.path.dirname(MenuBar.filename_path))

            if not MenuBar.filename_path:  # user cancelled
                return

            logger.info("OPENING UP A GSI FILE: " + MenuBar.filename_path)

            GUIApplication.refresh()
            self.enable_menus()
        except Exception as ex:
            print("Problem opening up the GSI file\n\n" + str(ex))
            logger.exception("An unexpected error has occurred\n\nProblem opening up the GSI file\n\n" + str(ex))
            tk.messagebox.showerror("Survey Assist", "An unexpected error has occurred\n\nProblem opening up the GSI file\n\n" + str(ex))
            return

    def new_dated_directory(self, choose_date=True, folder_selected=None):

        try:
            # default path for the file dialog to open too
            default_path = os.path.join(survey_config.root_job_directory, survey_config.current_year, survey_config.default_survey_type)
            if folder_selected is None:
                folder_selected = filedialog.askdirectory(parent=self.master, initialdir=default_path, title='Please select the job directory')

            if os.path.exists(folder_selected):
                if choose_date is True:
                    self.choose_date()

                CreateDatedDirectoryWindow(self, folder_selected)
        except Exception as ex:
            print("Unexpected error has occurred\n\n" + str(ex))
            logger.exception("An unexpected error has occurred\n\nnew_dated_directory()\n\n" + str(ex))
            tk.messagebox.showerror("Survey Assist", "An unexpected error has occurred\n\nnew_dated_directory()\n\n" + str(ex))
            return

    def choose_date(self):
        # Let user choose the date, rather than the default todays date
        cal_root = tk.Toplevel()
        cal = CalendarWindow(cal_root, todays_date)
        self.master.wait_window(cal_root)
        # active_date = cal.get_selected_date()

    def open_calender(self, parent):
        cal_root = tk.Toplevel()
        CalendarWindow(cal_root, todays_date)
        parent.wait_window(cal_root)

    def choose_dated_directory(self):

        try:
            # ask user to slect the root dated directory
            dated_directory_path = filedialog.askdirectory(parent=self.master, initialdir=self.monitoring_job_dir, title='Please select the '
                                                                                                                         'dated directory')
            if dated_directory_path:

                # check to see if it has a dated directory structure
                # check if file is in the edited directory of a dated file format folder
                if (os.path.isdir(dated_directory_path + '/TS')) & (os.path.isdir(dated_directory_path + '/GPS')) & (
                        os.path.isdir(dated_directory_path + '/OUTPUT')):

                    survey_config.todays_dated_directory = dated_directory_path
                else:
                    tk.messagebox.showwarning("Survey Assist", "The directory you have selected doesn't appear to be a valid dated directory.")
                    return
        except Exception as ex:
            print("Unexpected error has occurred\n\n" + str(ex))
            logger.exception("An unexpected error has occurred\n\nchoose_dated_directory()\n\n" + str(ex))
            tk.messagebox.showerror("Survey Assist", "An unexpected error has occurred\n\nchoose_dated_directory()\n\n" + str(ex))
            return

    def choose_compnet_directory(self):

        compnet_monitoring_dir = os.path.join(survey_config.compnet_data_dir, survey_config.current_year, survey_config.default_survey_type)
        self.compnet_working_dir = filedialog.askdirectory(parent=self.master, initialdir=compnet_monitoring_dir,
                                                           title='Please select a compnet job directory')

    def new_job_directoy(self):

        initial_dir = os.path.join(survey_config.root_job_directory, survey_config.current_year, survey_config.default_survey_type)
        os.startfile(initial_dir)

    def import_sd_data(self):

        user_sd_directory = self.user_config.user_sd_root
        usb_root_directory = self.user_config.usb_root
        rail_monitoring_files = None
        is_rail_survey = False

        please_wait_screen = None

        todays_dated_directory = survey_config.todays_dated_directory

        # reset todays dated directory if not today and let user choose
        if todays_date not in todays_dated_directory:
            todays_dated_directory = ""
        import_root_directory = todays_dated_directory

        # lets first check if user SD or USB directory exists
        if not SDCard.user_SD_dir_exists(user_sd_directory):

            # lets check the usb drive for 1200 series GPS's
            if not SDCard.user_SD_dir_exists(usb_root_directory):

                tk.messagebox.showinfo("IMPORT SD DATA", "Can't find your SD card drive.\n\nPlease select your SD drive.")

                user_sd_directory = tkinter.filedialog.askdirectory(parent=self.master, initialdir='C:\\', title='Please choose your SD card drive')

                if user_sd_directory:
                    self.user_config.update(UserConfiguration.section_file_directories, 'user_sd_root', user_sd_directory)
                    self.user_config.user_sd_root = user_sd_directory
                else:  # user hit cancel
                    return
            else:
                user_sd_directory = usb_root_directory

        # create the SD Card
        sd_card = SDCard(user_sd_directory)

        # check to see if survey files from today were found
        if not sd_card.get_list_all_todays_files():

            survey_config.current_rail_monitoring_file_name

            user_answer = tk.messagebox.askyesnocancel("IMPORT SD DATA", "Couldn't find any survey files with todays date."
                                                                         "\n\nAre you trying to import a rail survey (" +
                                                       survey_config.current_rail_monitoring_file_name +") ?\n\n"
                                                                         "YES           -  IMPORT RAIL SURVEY\n"
                                                                         "NO            - IMPORT FILES MANUALLY\n"
                                                                         "CANCEL    - INSERT SD CARD AND TRY_AGAIN\n\n"
                                                                         "Otherwise, please make sure you have inserted the SD Card into your"
                                                                         " computer, and check your SD card path in user_settings.ini is correct.")

            if user_answer is None:  # user selected cancel

                return

            elif user_answer is False:  # user wants to copy files over manually
                os.startfile('c:')
                return

            else:  # user selected yes to importing rail survey

                ImportRailMonitoringFileWindow(self.master)
                ts_used = self.ts_used
                rail_monitoring_files = sd_card.get_rail_survey_files()

                if not rail_monitoring_files:
                    tk.messagebox.showinfo("IMPORT SD DATA", "Couldn't find any rail monitoring survey files.\n\nPlease check the settings.ini file "
                                                             "and make sure 'current_rail_monitoring_file_name' is correct.\n\n"
                                                             "Also, check user_settings.ini and make sure the root SD directory is configured "
                                                             "properly.\n\nRestart Survey Assist after making any changes.")

                    # # open up explorer
                    # os.startfile("settings.ini")
                    # os.startfile("c:/SurveyAssist/user_settings.ini")

                    return
                else:
                    is_rail_survey = True

        # check if todays directory exists.  If not, get user to choose.
        if not todays_dated_directory:
            import_root_directory = tkinter.filedialog.askdirectory(parent=self.master, initialdir=self.monitoring_job_dir,
                                                                    title='Choose the job root directory where you would like to import the SD data '
                                                                          'to')
            # check that the user has choosen a dated directory
            folders = []
            files = os.listdir(import_root_directory)
            for f in files:
                if os.path.isdir(os.path.join(import_root_directory, f)):
                    folders.append(f)

            if all(x in folders for x in ['GPS', 'TS', 'OUTPUT', 'OTHER']):

                survey_config.todays_dated_directory = import_root_directory

            else:
                tk.messagebox.showerror("COPYING SD DATA", "The root job folder is not a dated dirctory.  Please try re-importing")
                return

        if not import_root_directory:
            # user has closed down the ask directory so exit import sd
            return

        # lets copy files over to the dated directory but confirm with user first
        filename_paths = set([file.filepath for file in sd_card.get_list_all_todays_files()])
        filenames_txt_list = ""
        confirm_msg = "The following " + str(len(filename_paths)) + " files will be copied over to " + import_root_directory + "\n\n"

        for full_file_name in sorted(filename_paths):
            filenames_txt_list += os.path.basename(full_file_name) + '\n'

        confirm_msg += filenames_txt_list + "\nHit 'Cancel' to copy files over manually"

        if tk.messagebox.askokcancel(message=confirm_msg):
            import_path = ""

            # user wants to copy over the files.
            try:

                # First, lets display to the user a busy cursor to show that something is happening
                please_wait_screen = PleaseWaitScreen(self)

                if sd_card.get_todays_gps_files():
                    for file in sd_card.get_todays_gps_files():
                        import_path = os.path.join(import_root_directory, 'GPS', file.basename)
                        if os.path.isdir(file.filepath):
                            shutil.copytree(file.filepath, import_path)
                        else:
                            shutil.copy(file.filepath, import_path)

                elif sd_card.get_todays_ts_15_files():

                    for file in sd_card.get_todays_ts_15_files():
                        import_path = os.path.join(import_root_directory, 'TS', 'TS15', file.basename)
                        if os.path.isdir(file.filepath):
                            shutil.copytree(file.filepath, import_path)
                        else:
                            shutil.copy(file.filepath, import_path)

                        if file.file_suffix.upper() == File.GSI_FILE_SUFFIX:
                            # Check and copy over gsi to edited diretory if it exists
                            self.copy_over_gsi_to_edited_directory(file, import_path, is_rail_survey)

                elif sd_card.get_todays_ts_60_files():
                    for file in sd_card.get_todays_ts_60_files():
                        import_path = os.path.join(import_root_directory, 'TS', 'TS60', file.basename)
                        if os.path.isdir(file.filepath):
                            shutil.copytree(file.filepath, import_path)
                        else:
                            shutil.copy(file.filepath, import_path)

                        if file.file_suffix.upper() == File.GSI_FILE_SUFFIX:
                            # Check and copy over gsi to edited directory if it exists
                            self.copy_over_gsi_to_edited_directory(file, import_path, is_rail_survey)

                elif sd_card.get_todays_ms_60_files():
                    for file in sd_card.get_todays_ms_60_files():
                        import_path = os.path.join(import_root_directory, 'TS', 'MS60', file.basename)
                        if os.path.isdir(file.filepath):
                            shutil.copytree(file.filepath, import_path)
                        else:
                            shutil.copy(file.filepath, import_path)

                        if file.file_suffix.upper() == File.GSI_FILE_SUFFIX:
                            # Check and copy over gsi to edited diretory if it exists
                            self.copy_over_gsi_to_edited_directory(file, import_path, is_rail_survey)

                elif rail_monitoring_files:
                    for file in rail_monitoring_files:

                        import_path = os.path.join(import_root_directory, 'TS', ts_used, file.basename)
                        if os.path.isdir(file.filepath):
                            shutil.copytree(file.filepath, import_path)
                        else:
                            shutil.copy(file.filepath, import_path)

                        if file.file_suffix.upper() == File.GSI_FILE_SUFFIX:
                            # Check and copy over gsi to edited directory if it exists
                            self.copy_over_gsi_to_edited_directory(file, import_path, is_rail_survey)
                else:
                    # This should not be reachable as there should be at least one file.
                    logger.exception("Importing SD Data\n\nThis should not be reachable.  Investigate\n\n")
                    tk.messagebox.showerror("COPYING SD DATA", "Unexpected error has occurred: .\n\nPlease notify the developer.")

                    # open up explorer
                    os.startfile('c:')

            except FileExistsError as ex:
                print(ex)
                logger.exception("Importing SD Data\n\nFileExistsError\n\n" + str(ex))
                tk.messagebox.showerror("COPYING SD DATA", "File aready exists: " + file.filepath + '\n\nat:\n\n ' + import_path + '.\n\nPlease '
                                                                                                                                   'check and copy files over manually')
                # open up explorer
                os.startfile('c:')

            except IOError as ex:
                print(ex)
                logger.exception("Importing SD Data\n\nIOError\n\n" + str(ex))
                # Most likely not a dated directory
                tk.messagebox.showerror("COPYING SD DATA", "Problem copying files across.   This is most likely because the destination folder "
                                                           "chosen doesn't have a dated folder structure (i.e GPS, OTHER, OUTPUT, "
                                                           "TS directories. \n\nPlease copy files over manually.")

                # open up explorer
                os.startfile('c:')

            except Exception as ex:
                print(ex)
                logger.exception("Importing SD Data\n\nException\n\n" + str(ex))
                tk.messagebox.showerror("COPYING SD DATA", "Problem copying files across.  Please copy files over manually.\n\n" + str(ex))

                # open up explorer
                os.startfile('c:')

            else:

                # Display message to user that the files have transferred over and can remove SD card
                please_wait_screen.destroy()
                tk.messagebox.showinfo("COPYING SD DATA", "SD Card transfer is complete.  It is now safe to remove the SD card.")
            finally:
                # self.master.configure(cursor="")    # reset cursor
                please_wait_screen.destroy()
                self.master.deiconify()
        else:
            # user wants to transfer files over manually.
            # open up explorer
            os.startfile('c:')

    def copy_over_sd_files(self):
        pass

    def copy_over_gsi_to_edited_directory(self, gsi_file, import_path, is_rail_survey):

        ts_root_dir = str(Path(import_path).parent.parent)
        print(ts_root_dir)

        if is_rail_survey:
            edited_filename_path = ts_root_dir + '/EDITING/' + gsi_file.basename_no_ext + '_' + self.ts_used + '_' + Today.todays_date_reversed + '_EDITED.GSI'
        else:
            edited_filename_path = ts_root_dir + '/EDITING/' + gsi_file.basename_no_ext + '_EDITED.GSI'
        shutil.copy(gsi_file.filepath, edited_filename_path)

    def get_gsi_file(self, date, gsi_directory):

        gsi_filenames = []
        # date is in the 201214 format
        for filename in os.listdir(gsi_directory):

            if date in filename:
                if Path(filename).suffix.upper() == '.GSI':
                    gsi_filenames.append(filename)
        return gsi_filenames

    def monitoring_create(self):

        try:
            if not MenuBar.filename_path:
                self.choose_gsi_file()

            if not MenuBar.filename_path:  # user cancelled
                return

            csv_dict = {}

            station_list_dict = gsi.get_list_of_station_setups(gsi.formatted_lines)

            for line_number, station_name in station_list_dict.items():

                coordinate_dict = OrderedDict()

                station_shots_dict = gsi.get_all_shots_from_a_station_including_setup(station_name, line_number)

                # Create a csv for each of the station shots
                for formatted_line in station_shots_dict.values():

                    if gsi.is_station_setup(formatted_line):
                        continue

                    coordinate_dict[formatted_line['Point_ID']] = [formatted_line['Point_ID'], formatted_line['Easting'], formatted_line['Northing'],
                                                                   formatted_line['Elevation']]

                csv_dict[station_name] = coordinate_dict

            # csv_file_dict = {k: list(v) for (k, v) in groupby(csv_line, lambda x: x[0])}

            # export monitoring files
            for station_name, coordinate_list in csv_dict.items():
                monitoring_files_dir = os.path.join(os.getcwd(), 'Monitoring Files')
                out_csv = os.path.join(monitoring_files_dir, station_name + '.csv')

                with open(out_csv, 'w', newline='') as my_file:
                    wr = csv.writer(my_file)
                    for coordinates in coordinate_list.values():
                        wr.writerow(coordinates)

            tk.messagebox.showinfo("Create Monitoring Files", "Monitoring files have been created at " + monitoring_files_dir)

        except Exception as ex:
            print("Problem opening up the GSI file\n\n" + str(ex))
            logger.exception("An unexpected error has occurred\n\nProblem opening up the GSI file\n\n" + str(ex))
            tk.messagebox.showerror("Survey Assist", "An unexpected error has occurred\n\nProblem opening up the GSI file\n\n" + str(ex))
            return

    def monitoring_update_coords(self):
        pass

    def monitoring_update_labels(self):
        pass

    def monitoring_rename_updated_files(self):
        pass

    @staticmethod
    def format_gsi_file():

        gui_app.status_bar.status['text'] = 'Working ...'

        try:

            gsi.format_gsi(MenuBar.filename_path)

        except FileNotFoundError:

            # Do nothing: User has hit the cancel button
            gui_app.status_bar.status['text'] = 'Please choose a GSI File'

        except CorruptedGSIFileError as ex:

            # Most likely an corrupted GSI file was selected
            tk.messagebox.showerror("FORMATTING GSI", 'Error reading GSI File:\n\nThis file is a corrupted or incorrect GSI file\n\n' + str(ex))

            gui_app.status_bar.status['text'] = 'Please choose a GSI File'

        except Exception as ex:

            # Most likely an incorrect file was chosen
            logger.exception('Error has occurred. ')

            tk.messagebox.showerror("ERROR", 'Error reading GSI File:\n\nPlease make sure file is not opened '
                                             'by another program.  If problem continues please contact Richard Walter\n\n' + str(ex))

    @staticmethod
    def create_and_populate_database():
        try:
            database.create_db()
            database.populate_table(gsi.formatted_lines)
        except Exception as ex:
            print("Problem opening up the GSI file\n\n" + str(ex))
            logger.exception("An unexpected error has occurred\n\ncreate_and_populate_database()\n\n" + str(ex))
            tk.messagebox.showerror("Survey Assist", "An unexpected error has occurred\n\ncreate_and_populate_database()\n\n" + str(ex))
            return

    @staticmethod
    def update_database():
        try:
            database.populate_table(gsi.formatted_lines)
        except Exception as ex:
            print("Problem opening up the GSI file\n\n" + str(ex))
            logger.exception("An unexpected error has occurred\n\nupdate_database()\n\n" + str(ex))
            tk.messagebox.showerror("Survey Assist", "An unexpected error has occurred\n\nupdate_database()\n\n" + str(ex))
            return

    @staticmethod
    def update_gui():
        try:

            gui_app.list_box.populate(gsi.formatted_lines)
            gui_app.status_bar.status['text'] = MenuBar.filename_path
        except Exception as ex:
            print("Problem opening up the GSI file\n\n" + str(ex))
            logger.exception("An unexpected error has occurred\n\nupdate_gui()\n\n" + str(ex))
            tk.messagebox.showerror("Survey Assist", "An unexpected error has occurred\n\nupdate_gui()\n\n" + str(ex))
            return

    def check_3d_survey(self):

        errors, error_points, subject, = "", "", ""
        error_line_numbers = []
        subject = "Checking Survey Tolerances"

        try:
            errors, error_points = gsi.check_3D_survey(database.conn, survey_config)
            error_text = "The following points are outside the specified survey tolerance:\n"
            specified_tolerance_txt = "\n\nThe current tolerance is E:" + survey_config.easting_tolerance + "  N:" + \
                                      survey_config.northing_tolerance + "  H: " + survey_config.height_tolerance

            if not errors:
                error_text = "Survey is within the specified tolerance.  Well done!" + specified_tolerance_txt
            else:
                error_text += errors + specified_tolerance_txt

            # display error dialog box
            print(error_text)
            tkinter.messagebox.showinfo(subject, error_text)
            # CustomDialogBox(self.master, error_text)

        except Exception as ex:
            logger.exception('Error creating executing SQL query\n\n' + str(ex))
            tk.messagebox.showerror("Error", 'Error checking survey tolerance:\n\n' + str(ex))

        # highlight any error points
        error_point_set = set(error_points)

        for line_number, current_gsi_line in enumerate(gsi.formatted_lines, start=1):
            if current_gsi_line['Point_ID'] in error_point_set:
                error_line_numbers.append(line_number)

        gui_app.list_box.populate(gsi.formatted_lines, error_line_numbers)

    def check_control_naming(self):

        try:
            error_text, error_line_numbers = gsi.check_control_naming()

            # display error dialog box
            tkinter.messagebox.showinfo("Checking GSI Naming", error_text)
            gui_app.list_box.populate(gsi.formatted_lines, error_line_numbers)

        except Exception as ex:
            logger.exception('Error checking station naming\n\n' + str(ex))
            tk.messagebox.showerror("Error", 'Error checking control naming:\n\n' + str(ex))

    def check_prism_constants(self):

        try:
            error_text, error_line_numbers = gsi.check_prism_constants()

            # display error dialog box
            tkinter.messagebox.showinfo("Checking Prism Constants", error_text)
            gui_app.list_box.populate(gsi.formatted_lines, error_line_numbers)

        except Exception as ex:
            logger.exception('Error checking prism constants\n\n' + str(ex))
            tk.messagebox.showerror("Error", 'Error checking prism constants:\n\n' + str(ex))

    def check_target_heights(self):

        try:
            error_text, error_line_numbers = gsi.check_target_heights()

            # display error dialog box
            tkinter.messagebox.showinfo("Checking Target Heights", error_text)
            gui_app.list_box.populate(gsi.formatted_lines, error_line_numbers)

        except Exception as ex:
            logger.exception('Error checking target heights\n\n' + str(ex))
            tk.messagebox.showerror("Error", 'Error checking target heights:\n\n' + str(ex))

    def check_FLFR(self, display='YES'):

        try:

            error_line_number_list = []
            dialog_text_set = set()
            points_no_2nd_face = []
            points_no_2nd_face_text = ""

            formatted_gsi_lines_analysis = []

            for gsi_line_number, line in enumerate(gsi.formatted_lines, start=0):

                if GSI.is_station_setup(line):
                    station_name = line['Point_ID']
                    obs_from_station_dict = gsi.get_all_shots_from_a_station_including_setup(station_name, gsi_line_number)
                    points_no_2nd_face, analysed_lines = self.anaylseFLFR(copy.deepcopy(obs_from_station_dict))

                    # add the analysis lines for this station
                    for aline in analysed_lines:
                        formatted_gsi_lines_analysis.append(aline)

                        # for each station setup add 'STN->Point_ID' for each error found
                        for key, field_value in aline.items():
                            if '*' in field_value:
                                if aline['Point_ID'] in points_no_2nd_face:
                                    points_no_2nd_face_text += "         " + station_name + "  --->  " + aline['Point_ID'] + '\n'
                                else:
                                    dialog_text_set.add("         " + station_name + "  --->  " + aline['Point_ID'] + '\n')
                                break

            # check for tagged values so line error can be determined
            for index, line_dict in enumerate(formatted_gsi_lines_analysis):

                for key, field_value in line_dict.items():

                    if '*' in field_value:
                        error_line_number_list.append(index + 1)
                        break

            if dialog_text_set:
                dialog_text = " The following shots exceed the FL_FR tolerance:\n\n"

                for line in sorted(dialog_text_set):
                    dialog_text += line
            else:
                dialog_text = " FL-FR shots are within specified tolerance."

            if points_no_2nd_face_text:
                dialog_text += "\n\n The following points only have one face:\n\n"
                dialog_text += points_no_2nd_face_text

            # display dialog box
            tkinter.messagebox.showinfo("Checking FL-FR", dialog_text)

            if display == 'NO':  # don't display results to user - just a popup dialog to let them know there is an issue
                pass
            else:
                gui_app.list_box.populate(formatted_gsi_lines_analysis, error_line_number_list)

        except Exception as ex:
            print("Problem opening up the GSI file\n\n" + str(ex))
            logger.exception("An unexpected error has occurred\n\ncheck_FLFR()\n\n" + str(ex))
            tk.messagebox.showerror("Survey Assist", "An unexpected error has occurred\n\ncheck_FLFR()\n\n" + str(ex))
            return

    def anaylseFLFR(self, obs_from_station_dict):

        precision = survey_config.precision_value

        points_no_2nd_face = []
        analysed_lines = []
        analysed_line_blank_values_dict = {'Point_ID': ' ', 'Timestamp': ' ', 'Horizontal_Angle': ' ',
                                           'Vertical_Angle': ' ', 'Slope_Distance': ' ',
                                           'Horizontal_Dist': ' ', 'Height_Diff': ' ', 'Prism_Constant': ' ',
                                           'Easting': ' ', 'Northing': ' ', 'Elevation': ' ', 'STN_Easting': '',
                                           'STN_Northing': '', 'STN_Elevation': '', 'Target_Height': ' ',
                                           'STN_Height': ' '}

        line_already_compared = -1

        # create an ordered list of obs
        obs_from_station_list = []
        for dict in obs_from_station_dict.values():
            obs_from_station_list.append(dict)
        sorted_obs_from_station_list = sorted(obs_from_station_list, key=lambda i: i['Point_ID'])

        for index, formatted_line_dict in enumerate(sorted_obs_from_station_list):

            obs_line_1_dict = formatted_line_dict

            if GSI.is_station_setup(formatted_line_dict):
                # dont analyse stn setup - append to start of list
                analysed_lines.insert(0, formatted_line_dict)
                continue

            # check to see if line has already compared
            if index == line_already_compared:
                continue

            # if not at the end of the dictionary ( could use try except IndexError )
            try:

                # if index < len(sorted_obs_from_station_list):
                obs_line_2_dict = sorted_obs_from_station_list[index + 1]

            except IndexError:  # end of dictionary reached

                pass
            else:

                # points match - lets analyse
                if obs_line_1_dict['Point_ID'] == obs_line_2_dict['Point_ID']:

                    for key, obs_line_1_field_value_str in obs_line_1_dict.items():

                        obs_line_2_field_value_str = obs_line_2_dict[key]

                        # default type
                        if key == 'Timestamp':
                            # time_difference = get_time_differance(obs_line_1_field_value_str,
                            #                                       obs_line_2_field_value_str)
                            obs_line_2_dict[key] = ' '
                        elif key in ('Horizontal_Angle', 'Vertical_Angle'):
                            field_type = FIELD_TYPE_ANGLE
                            obs_line_1_field_value = get_numerical_value_from_string(obs_line_1_field_value_str, field_type, precision)

                            obs_line_2_field_value = get_numerical_value_from_string(obs_line_2_field_value_str, field_type, precision)
                            if key == 'Horizontal_Angle':
                                angular_diff = decimalize_value(angular_difference(obs_line_1_field_value, obs_line_2_field_value, 180), '3dp')
                            else:  # key is vertical angle:
                                obs_angular_diff = angular_difference(obs_line_2_field_value, obs_line_1_field_value, 0)
                                angular_diff = decimalize_value(angular_difference(obs_angular_diff, -360.00, 0), '3dp')

                            angle_dms = angle_decimal2DMS(angular_diff)
                            obs_line_2_dict[key] = GSI.format_angles(angle_dms, '3dp')  # make 3dp precision for 4dp shots so it formats correctly

                        elif key == 'Prism_Constant':
                            obs_line_2_dict[key] = str(int(obs_line_1_dict[key]) - int(obs_line_1_dict[key]))
                        elif key == 'Point_ID':
                            pass
                        else:  # field should be a float
                            field_type = FIELD_TYPE_FLOAT
                            obs_line_1_field_value = get_numerical_value_from_string(obs_line_1_field_value_str, field_type, precision)

                            obs_line_2_field_value = get_numerical_value_from_string(obs_line_2_field_value_str, field_type, precision)
                            if (obs_line_1_field_value != "") and (obs_line_2_field_value != ""):
                                float_diff_str = str(decimalize_value(obs_line_1_field_value - obs_line_2_field_value, precision))
                                float_diff_str = self.check_diff_exceed_tolerance(key, float_diff_str)
                                obs_line_2_dict[key] = float_diff_str

                else:
                    # probably an orientation shot, or a shot that doesn't have a double - make blank and tag
                    points_no_2nd_face.append(obs_line_1_dict['Point_ID'])
                    blank_line_dict = analysed_line_blank_values_dict.copy()
                    blank_line_dict['Point_ID'] = obs_line_1_dict['Point_ID']
                    blank_line_dict['Timestamp'] = '*'
                    analysed_lines.append(blank_line_dict)
                    continue

                blank_line_dict = analysed_line_blank_values_dict.copy()
                blank_line_dict['Point_ID'] = obs_line_1_dict['Point_ID']
                analysed_lines.append(blank_line_dict)
                analysed_lines.append(obs_line_2_dict)
                line_already_compared = index + 1

            # else:
            #     # end of the dictionary reached - do not analyse but add as it hasnt been compared
            #     analysed_lines.append(obs_line_1_dict)
            #     pass

        return points_no_2nd_face, analysed_lines

    def check_diff_exceed_tolerance(self, key, float_diff_str):

        float_diff = float(float_diff_str)

        # get flfr tolerances from config
        flfr_height_tolerance = float(survey_config.flfr_height_tolerance)
        flfr_northings_tolerance = float(survey_config.flfr_northing_tolerance)
        flfr_eastings_tolerance = float(survey_config.flfr_easting_tolerance)

        if key == 'Elevation':
            if abs(float_diff) > flfr_height_tolerance:
                # add a tag
                float_diff_str = '*' + float_diff_str
        elif key == 'Easting':
            if abs(float_diff) > flfr_eastings_tolerance:
                # add a tag
                float_diff_str = '*' + float_diff_str
        elif key == 'Northing':
            if abs(float_diff) > flfr_height_tolerance:
                # add a tag
                float_diff_str = '*' + float_diff_str

        return float_diff_str

    def check_3d_all(self):

        if not MenuBar.filename_path:
            tk.messagebox.showinfo("Check Survey", "Please open up a GSI file first.")
            return

        self.check_FLFR('NO')
        self.check_control_naming()
        self.check_prism_constants()
        self.check_target_heights()
        self.check_3d_survey()

    def change_target_height(self):

        selected_items = gui_app.list_box.list_box_view.selection()

        if not selected_items:
            # no lines selected
            tkinter.messagebox.showinfo("Updating Target Height", "Please select at least one line to update")
            return

        for selected_item in selected_items:
            line_number = gui_app.list_box.list_box_view.item(selected_item)['values'][0]

            # Check to make sure that the selected line is not a STN setup
            if gsi.is_station_setup(gsi.get_formatted_line(line_number)):
                tk.messagebox.showinfo("Updating Target Height", "Please select lines that contain only target heights, NOT a station height")
                return
            elif gsi.is_orientation_shot(gsi.get_formatted_line(line_number)):
                tk.messagebox.showinfo("Updating Target Height", "Please select lines that contain only target heights, NOT an orientation line")
                return

        TargetHeightWindow(self.master)

    def change_station_height(self):

        # Check that only 1 line is selected and that it is a station height
        selected_items = gui_app.list_box.list_box_view.selection()

        for selected_item in selected_items:
            line_number = gui_app.list_box.list_box_view.item(selected_item)['values'][0]

            # Check to make sure that the selected line is a STN setup
            if not gsi.is_station_setup(gsi.get_formatted_line(line_number)):
                tk.messagebox.showinfo("Updating Station Height", "Please select a line that contains only station setup")
                return

        if len(selected_items) > 1:
            tkinter.messagebox.showinfo("Updating Station Height", "Please select only ONE station height to update at a time")
            return
        elif not selected_items:
            # no lines selected
            tkinter.messagebox.showinfo("Updating Station Height", "Please select at least one line to update")
            return

        StationHeightWindow(self.master)

    def change_point_name(self):
        PointNameWindow(self.master)

    def prism_constant_update_manually(self):

        try:
            line_numbers_to_ammend = []
            selected_items = gui_app.list_box.list_box_view.selection()

            # lets get a list of line numbers to ammend
            if selected_items:
                for selected_item in selected_items:
                    line_numbers_to_ammend.append(gui_app.list_box.list_box_view.item(selected_item)['values'][0])
            else:
                # no lines selected
                tkinter.messagebox.showinfo("Updating Prism Constant", "Please select at least one line to update")
                return

            pcu = PrismConstantUpdate(self.master, line_numbers_to_ammend)
            pcu.build_fix_single_window()
        except Exception as ex:
            print("Problem opening up the GSI file\n\n" + str(ex))
            logger.exception("An unexpected error has occurred\n\nprism_constant_update_manually()\n\n" + str(ex))
            tk.messagebox.showerror("Survey Assist", "An unexpected error has occurred\n\nprism_constant_update_manually()\n\n" + str(ex))
            return

    def prism_constant_update_batch(self):
        try:
            pcu = PrismConstantUpdate(self.master)
            pcu.build_batch_file_window()
        except Exception as ex:
            print("Problem opening up the GSI file\n\n" + str(ex))
            logger.exception("An unexpected error has occurred\n\nprism_constant_update_batch()\n\n" + str(ex))
            tk.messagebox.showerror("Survey Assist", "An unexpected error has occurred\n\nprism_constant_update_batch()\n\n" + str(ex))
            return

    def check_2d_doubles(self):

        error_text = ""
        dialog_text = ""

        try:
            if not MenuBar.filename_path:
                tk.messagebox.showinfo("Survey Assist", "Please open up a GSI file first.")
                return

            # All the shots from each station should have 2 points with 4 shots each.  Lets check for that.
            # First, lets get a lits of the station setups so we can get all the shots from each setup
            station_points_dict = gsi.get_list_of_station_setups(gsi.formatted_lines)
            for gsi_stn_line_number, station_name in station_points_dict.items():

                # reset the below list for each station setup
                point_id_list = []
                more_than_4_shots_list = []
                doubles_list = []

                station_shots_dict = gsi.get_all_shots_from_a_station_including_setup(station_name, gsi_stn_line_number)

                # lets go through all shots except station setup and orientation shots and count frequency of Point ID's
                for gsi_line_number, formatted_line in station_shots_dict.items():
                    if gsi.is_station_setup(formatted_line) or gsi.is_orientation_shot(formatted_line):
                        continue
                    else:
                        point_id_list.append(formatted_line['Point_ID'])

                # Lets check the frequency of points from this setup
                point_id_frequency = Counter(point_id_list)

                for point_id, count in point_id_frequency.items():
                    if count > 3:  # point has been shot 4 or more times
                        doubles_list.append(point_id)
                    # elif count > 4:   # point has been shot more than 4 times - let user know
                    #     more_than_4_shots_list.append(point_id)

                    else:  # just a normal double radiation
                        continue

                # Lets check to see the frequency of doubles for this setup.  There should be two double doubles.
                if len(doubles_list) == 0:
                    error_text += station_name + ":  No double doubles were found for this setup\n"
                elif len(doubles_list) == 1:
                    error_text += station_name + ":  Only one double double was found for this setup:\n              " + doubles_list[0] + "\n"
                elif len(doubles_list) > 2:
                    qty = str(len(doubles_list))
                    error_text += station_name + ":  " + qty + " double doubles were found for this setup:\n"
                    for point_id in doubles_list:
                        error_text += "              " + point_id + "\n"

            # Lets check to see if any errors found and report back to user

            if error_text:
                dialog_text = "The following potential issues were found with this survey:\n\n"
                dialog_text += error_text
            else:
                dialog_text = "Looks Good!\n\n2 double doubles from each station were found."
            tkinter.messagebox.showinfo("Check 2D Doubles", dialog_text)
            gui_app.list_box.populate(gsi.formatted_lines)

        except Exception as ex:

            logger.exception("An unexpected error has occurred\n\ncheck_2d_doubles()\n\n" + str(ex))
            tk.messagebox.showerror("Survey Assist", "An unexpected error has occurred\n\ncheck_2d_doubles()\n\n" + str(ex))
            return

    def compare_survey(self):
        try:
            if not MenuBar.filename_path:
                tk.messagebox.showinfo("Compare Survey", "Please open up a GSI file first.")
                return

            points_pc_diff_dict = {}
            points_target_height_diff_dict = {}
            old_point_ids = set()
            new_point_ids = set()

            old_survey_filepath = tk.filedialog.askopenfilename(parent=self.master, initialdir=self.monitoring_job_dir,
                                                                title="Please choose a similar survey", filetypes=[("GSI Files", ".GSI")])

            if not old_survey_filepath:  # user cancelled
                return

            old_survey_gsi = GSI(logger, survey_config)
            old_survey_gsi.format_gsi(old_survey_filepath)
            old_survey_formatted_lines_except_setups = old_survey_gsi.get_all_lines_except_setup()
            old_point_compare_dict = OrderedDict()

            line_number_errors = set()

            dialog_subject = "Survey Comparision"
            all_good_text = "Point naming, prism constants and target heights match between surveys "
            error_text = "A difference between the two surveys was found:\n\n"

            # Create a dictionary of points and their prism constant.
            # ASSUMPTION: prism constant for an old survey with no errors should be the same for the same point ID
            for index, formatted_line in enumerate(old_survey_formatted_lines_except_setups):
                # add a unique point ID so we are not overwritting point_id with potential different values
                old_point_compare_dict[formatted_line['Point_ID'] + str(index)] = {'old_point_id': formatted_line['Point_ID'],
                                                                                   'Prism_Constant': formatted_line['Prism_Constant'],
                                                                                   'Target_Height': formatted_line['Target_Height']}
                old_point_ids.add(formatted_line['Point_ID'])

            # for each point and its corresponding PC in old survey, check to see it matches PC in current survey
            for old_compare_values_list in old_point_compare_dict.values():

                for line_number, current_gsi_line in enumerate(gsi.formatted_lines, start=1):

                    # check to see if point id is a control point and skip if true
                    if gsi.is_station_setup(current_gsi_line):
                        continue

                    current_point_id = current_gsi_line['Point_ID']
                    current_PC = current_gsi_line['Prism_Constant']
                    current_target_height = current_gsi_line['Target_Height']

                    new_point_ids.add(current_point_id)

                    if old_compare_values_list['old_point_id'] == current_point_id:

                        # Compare PC - they should be the same.  If not report to user
                        if old_compare_values_list['Prism_Constant'] != current_PC:
                            points_pc_diff_dict[current_point_id] = {'current_pc': current_PC, 'old_pc': old_compare_values_list['Prism_Constant']}
                            line_number_errors.add(line_number)

                        # Compare target height - they should be the same.  If not report to user
                        print(current_point_id + "  " + old_compare_values_list['Target_Height'])
                        if old_compare_values_list['Target_Height'] != current_target_height:
                            points_target_height_diff_dict[current_point_id] = {'current_target_height': current_target_height,
                                                                                'old_target_height': old_compare_values_list['Target_Height']}
                            line_number_errors.add(line_number)

            # get list of points if any, that are different between the two surveys
            diff_points = sorted((new_point_ids.difference(old_point_ids)))

            # check if any errors found
            if points_pc_diff_dict or points_target_height_diff_dict or diff_points:

                if points_pc_diff_dict:

                    error_text += 'DIFFERENCES IN PRISM CONSTANT:\n\n'
                    for point, differences_dict in points_pc_diff_dict.items():
                        error_text += ' ' + point + ' ----> current PC: ' + differences_dict['current_pc'] + '  old PC: ' + differences_dict[
                            'old_pc'] + '\n'

                if points_target_height_diff_dict:

                    error_text += '\nDIFFERENCES IN TARGET HEIGHT:\n\n'
                    for point, differences_dict in points_target_height_diff_dict.items():
                        error_text += ' ' + point + ' ---> current height: ' + differences_dict['current_target_height'] + '  old height: ' + \
                                      differences_dict['old_target_height'] + '\n'

                if diff_points:
                    error_text += '\nThe following list of points were not found in the compared survey:\n\n'
                    for point in diff_points:
                        error_text += "  " + point + '\n'

                        # add line numbers where point_id is found in current gsi
                        point_line_number_errors = gsi.get_point_name_line_numbers(point)
                        for line_number in point_line_number_errors:
                            line_number_errors.add(line_number)

                display_text = error_text + '\nThese differences will be highlighted in yellow'

            else:
                display_text = all_good_text

            tkinter.messagebox.showinfo(dialog_subject, display_text)
            gui_app.list_box.populate(gsi.formatted_lines, list(line_number_errors))

        except Exception as ex:
            print("Problem opening up the GSI file\n\n" + str(ex))
            logger.exception("An unexpected error has occurred\n\ncompare_survey()\n\n" + str(ex))
            tk.messagebox.showerror("Survey Assist", "An unexpected error has occurred\n\ncompare_survey()\n\n" + str(ex))
            return

    def export_csv(self):
        try:
            gsi.export_csv(MenuBar.filename_path)
        except Exception as ex:
            print("Problem opening up the GSI file\n\n" + str(ex))
            logger.exception("An unexpected error has occurred\n\nexport_csv()\n\n" + str(ex))
            tk.messagebox.showerror("Survey Assist", "An unexpected error has occurred\n\nexport_csv()\n\n" + str(ex))
            return

    def display_query_input_box(self):

        QueryDialogWindow(self.master)

    def create_compnet_job_folder(self):

        gsi_filepath = ""
        compnet_raw_dir = survey_config.compnet_raw_dir
        compnet_data_dir = survey_config.compnet_data_dir

        if not gsi_filepath:
            gsi_filepath = tk.filedialog.askopenfilename(parent=self.master, initialdir=survey_config.todays_dated_directory,
                                                         title="Choose the GSI file you want Compnet to process...", filetypes=[("GSI Files",
                                                                                                                                 ".GSI")])
        if not gsi_filepath:
            return  # user hit cancel

        # Copy GSI over to raw directory
        dst = os.path.join(compnet_raw_dir, os.path.basename(gsi_filepath))

        try:
            copyfile(gsi_filepath, dst)
        except Exception as ex:
            print(ex)
            tkinter.messagebox.showinfo("Creating Compnet Jobs Files", compnet_raw_dir + " directory does not exist")
            return

        # Create the Job directory path and then create compnet job directory
        current_path = compnet_data_dir
        base_path = os.path.dirname(os.path.normpath(gsi_filepath))
        dir_list = base_path.split(os.sep)
        current_year_found = False

        # ['C:', 'Users', 'Richard', 'PycharmProjects', 'Survey Assist', 'Survey Data', '2020', 'MONITORING', 'A9 ARTC']
        try:
            for index, dir_name in enumerate(dir_list):

                if current_year_found:
                    current_path = os.path.join(current_path, dir_name)
                    if dir_name.isdigit() and len(dir_name) == 6:  # stop when the dated directory is found e.g. 200413
                        break
                elif dir_name == survey_config.current_year:
                    current_year_found = True
                    current_path = os.path.join(current_path, dir_name)
                else:
                    continue

            os.makedirs(current_path)

        except FileExistsError:
            print("Directory ", current_path, " already exists")
            tkinter.messagebox.showinfo("Creating Compnet Jobs Files", "Directory " + current_path + " already exists")
            return
        except Exception as ex:
            print(ex)
            tkinter.messagebox.showinfo("Creating Compnet Jobs Files", current_path + " directory does not exist")
            return
        else:

            self.compnet_working_dir = current_path
            # inform user of creating directories
            tkinter.messagebox.showinfo("Creating Compnet Jobs Files", 'The GSI file has been copied over to the C:\LS\RAW DATA directory. The '
                                                                       'following compnet job directory was also created:\n\n' + current_path)

    def update_fixed_file(self):

        CompnetUpdateFixedFileWindow(self.master)

    def weight_STD_file(self):

        CompnetWeightSTDFileWindow(self.master)

    def compare_crd_files(self):

        CompnetCompareCRDFWindow(self.master)

    def create_control_only_gsi(self):

        CompnetCreateControlOnlyGSI()

    def combine_gsi_files(self):

        CombineGSIFilesWindow(self.master)

    def create_CSV_from_ASC(self):

        try:
            asc_file_path = tk.filedialog.askopenfilename(parent=self.master, initialdir=self.monitoring_job_dir, title="Please select an .asc file",
                                                          filetypes=[("ASC Files", ".ASC")])

            if not asc_file_path:  # user cancel
                return

            # Create the CSV
            csv_file = []
            csv_file.append("POINT,EASTING,NORTHING,ELEVATION\n")
            comma = ','

            # Get the coordinates from the ASC
            asc_coordinate_file = ASCCoordinateFile(asc_file_path)
            coordinate_dict = asc_coordinate_file.coordinate_dictionary

            for point, coordinates in coordinate_dict.items():
                easting = coordinates['Eastings']
                northing = coordinates['Northings']
                elevation = ""
                try:
                    elevation = coordinates['Elevation']
                except Exception:
                    pass  # elevation may not exist in some coordinate
                finally:

                    csv_line = ""

                    # add coordinates to the CSV

                    csv_line += point + comma
                    csv_line += easting + comma
                    csv_line += northing + comma
                    csv_line += elevation + '\n'

                    csv_file += csv_line

            # Write out file
            with open("C:\SurveyAssist\Temp_ASC_CSV.csv", "w") as f:
                for line in csv_file:
                    f.write(line)

            # Launch excel
            if asc_file_path:
                os.system("start EXCEL.EXE C:\SurveyAssist\Temp_ASC_CSV.csv")

        except PermissionError:
            tk.messagebox.showerror("Survey Assist", "Please close the previous popup CSV and try again. ")

        except Exception as ex:

            logger.exception("An unexpected error has occurred\n\ncreate_CSV_from_ASC()\n\n" + str(ex))
            tk.messagebox.showerror("Survey Assist", "An unexpected error has occurred\n\ncreate_CSV_from_ASC()\n\n" + str(ex))
            return

    def create_CSV_from_CRD(self):

        try:
            initial_directory = os.path.join(survey_config.todays_dated_directory, "OUTPUT")
            crd_file_path = tk.filedialog.askopenfilename(parent=self.master, initialdir=initial_directory,
                                                          title="Please select a .CRD file",
                                                          filetypes=[("CRD Files", ".CRD")])
            if not crd_file_path:  # user cancelled
                return

            # Create the CSV
            csv_file = []
            csv_file.append("POINT,EASTING,NORTHING,ELEVATION\n")
            comma = ','

            # Get the coordinates from the CRD
            crd_coordinate_file = CRDCoordinateFile(crd_file_path)
            coordinate_dict = crd_coordinate_file.coordinate_dictionary

            for point, coordinates in coordinate_dict.items():
                easting = coordinates['Eastings']
                northing = coordinates['Northings']
                elevation = ""
                try:
                    elevation = coordinates['Elevation']
                except Exception:
                    pass  # elevation may not exist in some coordinate
                finally:

                    csv_line = ""

                    # add coordinates to the CSV

                    csv_line += point + comma
                    csv_line += easting + comma
                    csv_line += northing + comma
                    csv_line += elevation + '\n'

                    csv_file += csv_line

            # Write out file
            try:
                with open("C:\SurveyAssist\Temp_CRD_CSV.csv", "w") as f:
                    for line in csv_file:
                        f.write(line)

                # Launch excel
                os.system("start EXCEL.EXE C:\SurveyAssist\Temp_CRD_CSV.csv")

            except PermissionError:
                tk.messagebox.showerror("Survey Assist", "Please close the previous popup CSV and try again. ")
            except Exception as ex:
                tk.messagebox.showerror("Error creating the CSV", str(ex))


        except Exception as ex:
            print("Problem opening up the GSI file\n\n" + str(ex))
            logger.exception("An unexpected error has occurred\n\ncreate_CSV_from_CRD()\n\n" + str(ex))
            tk.messagebox.showerror("Survey Assist", "An unexpected error has occurred\n\ncreate_CSV_from_CRD()\n\n" + str(ex))
            return

    def copy_compnet_job_to_dated_directory(self):

        try:
            # Get user to choose the compnet working directory if not already done so
            if not self.compnet_working_dir:
                self.choose_compnet_directory()

                if not self.compnet_working_dir:  # user cancelled
                    tk.messagebox.showinfo("Copying Compnet Job Files", "A Compnet job directory must be selected before continuing.")
                    return

            # Get user to choose the current dated directory if not already done so
            if not survey_config.todays_dated_directory:
                self.choose_dated_directory()

                if not survey_config.todays_dated_directory:  # user cancelled
                    tk.messagebox.showinfo("Copying Compnet Job Files", "A dated directory must be selected before continuing.")
                    return

            # we want to copy the files into a Compnet folder created in the Output directory of the selected dated directory
            output_dir = os.path.join(survey_config.todays_dated_directory, 'OUTPUT')
            dest_compnet_fpath = os.path.join(output_dir, "COMPNET")

            confirm_msg = "All files in the compnet job at " + self.compnet_working_dir + " will be copied over to the following directory: \n\n" + \
                          dest_compnet_fpath + "\n\nAre you sure you want to continue?"

            if tk.messagebox.askokcancel("Copying Compnet Job Files", confirm_msg):

                os.makedirs(os.path.dirname(dest_compnet_fpath), exist_ok=True)
                copy_tree(self.compnet_working_dir, dest_compnet_fpath)

                # we also want to copy the CRD file to the OUTPUT folder
                for basename in os.listdir(dest_compnet_fpath):
                    if basename.endswith('.CRD'):
                        pathname = os.path.join(dest_compnet_fpath, basename)
                        if os.path.isfile(pathname):
                            shutil.copy2(pathname, output_dir)

                tk.messagebox.showinfo("Copying Compnet Job Files", "Compnet job files successfully copied over.")

            else:  # cancel the copying of files
                return
        except Exception as ex:
            print("An unexpected error has occurred\n\ncopy_compnet_job_to_dated_directory()\n\n" + str(ex))
            logger.exception("An unexpected error has occurred\n\ncopy_compnet_job_to_dated_directory()\n\n" + str(ex))
            tk.messagebox.showerror("Copying Compnet Job Files", "AN unexpected error has occured.\n\n" + str(ex))

    def copy_gps_to_gnss_temp(self):

        try:
            if not os.path.exists(survey_config.gnss_temp_dir):
                os.makedirs(survey_config.gnss_temp_dir)

            gnss_dir_path = tk.filedialog.askdirectory(parent=self.master, initialdir=survey_config.gnss_temp_dir,
                                                       title="Please choose the temp GNSS job directory")

            if not gnss_dir_path:  # use cancelled the dialog box
                return

            confirm_msg = "All GPS files in " + gnss_dir_path + " will be deleted before copying across todays GNSS files.\n\nAre you sure " \
                                                                "you want to continue?"

            if tk.messagebox.askokcancel("Copy GPS files to GNSS Temp", confirm_msg):

                todays_dated_directory = survey_config.todays_dated_directory

                if not todays_dated_directory:
                    todays_GPS_directory = tk.filedialog.askdirectory(parent=self.master, initialdir=survey_config.root_job_directory,
                                                                      title="Please choose the GPS directory containing the GPS files you wish to "
                                                                            "transfer ")
                else:
                    todays_GPS_directory = os.path.join(todays_dated_directory, 'GPS')

                if not todays_GPS_directory:
                    return  # user cancelled

                # remove existing files in the temp directory
                # for filename in os.listdir(gnss_dir_path):
                #     filepath = os.path.join(gnss_dir_path, filename)
                #     os.remove(filepath)
                shutil.rmtree(gnss_dir_path)

                # copy over GPS files
                # for file in os.listdir(todays_GPS_directory):
                #     shutil.copyfile(os.path.join(file, todays_GPS_directory), os.path.join(gnss_dir_path, file))
                copy_tree(todays_GPS_directory, gnss_dir_path)

                tk.messagebox.showinfo("Copying GPS files", "GPS files successfully copied over.")

            else:  # cancel the copying of files
                return
        except Exception as ex:
            print("An unexpected error has occurred\n\ncopy_gps_to_gnss_temp()\n\n" + str(ex))
            logger.exception("An unexpected error has occurred\n\ncopy_gps_to_gnss_temp()\n\n" + str(ex))
            tk.messagebox.showerror("Copying GPS files", "AN unexpected error has occured.\n\n" + str(ex))

    def create_list_of_change_points(self):
        try:
            change_point_list_text = ""

            if not MenuBar.filename_path:
                self.choose_gsi_file()

            if not MenuBar.filename_path:  # no gsi open
                return

            change_points = gsi.get_change_points()
            # change_points = []

            # get a list of stations
            control_points_dict = gsi.get_list_of_station_setups(gsi.formatted_lines)

            # # determine change points. First create a point id list
            # point_id_list = []
            # for formatted_line in gsi.formatted_lines:
            #     point_id_list.append(formatted_line['Point_ID'])
            #
            # point_id_frequency = Counter(point_id_list)
            #
            # # if point_id occurs more than 4 times its probably a change point
            # for point_id, count in point_id_frequency.items():
            #     if count > 3:
            #         if point_id in control_points_dict.values():
            #             continue  # dont add stations to change point list
            #         else:
            #             change_points.append(point_id)

            # determine the change points for each station setup
            for line_number, control_name in control_points_dict.items():
                shots_from_station = gsi.get_all_shots_from_a_station_including_setup(control_name, line_number)

                station_change_points = set()

                for formatted_line in shots_from_station.values():
                    if gsi.is_station_setup(formatted_line):  # should only ever be one
                        change_point_list_text += "@" + control_name + '\n'
                    elif formatted_line['Point_ID'] in change_points:
                        station_change_points.add(formatted_line['Point_ID'])

                # formatted the file to write out
                for change_point in sorted(station_change_points):
                    change_point_list_text += "   " + change_point + '\n'

            # Write out file
            try:
                with open("C:\SurveyAssist\change_point_list.txt", "w") as f:
                    f.write(change_point_list_text)
            except Exception as ex:
                tk.messagebox.showerror("Error creating the change point list", str(ex))

            # Launch text file
            os.startfile("C:\SurveyAssist\change_point_list.txt")

        except Exception as ex:
            print("Problem opening up the GSI file\n\n" + str(ex))
            logger.exception("An unexpected error has occurred\n\ncreate_list_of_change_points()\n\n" + str(ex))
            tk.messagebox.showerror("Survey Assist", "An unexpected error has occurred\n\ncreate_list_of_change_points()\n\n" + str(ex))
            return

    @staticmethod
    def job_diary():

        root = tk.Toplevel()
        JobDiaryWindow(root)

    def configure_survey(self):

        ConfigDialogWindow(self.master)

    def re_display_gsi(self):
        try:
            gui_app.refresh()
        except Exception as ex:
            print("Problem opening up the GSI file\n\n" + str(ex))
            logger.exception("An unexpected error has occurred\n\nre_display_gsi()\n\n" + str(ex))
            tk.messagebox.showerror("Survey Assist", "An unexpected error has occurred\n\nre_display_gsi()\n\n" + str(ex))
            return

    def job_tracker_open_excel(self):

        try:
            self.job_tracker_filepath = os.path.join(survey_config.root_job_directory, survey_config.current_year, survey_config.job_tracker_filename)
            os.startfile(self.job_tracker_filepath)

        except FileNotFoundError as ex:
            print("Couldn't find the Job Tracker Spreadsheet:\n\n" + self.job_tracker_filepath)
            logger.exception("An unexpected error has occurred\n\nbtn_job_tracker()\n\n" + str(ex))
            tk.messagebox.showerror("Survey Assist", "Couldn't find the Job Tracker Spreadsheet:\n\n" + self.job_tracker_filepath)
            return

    def job_tracker_hide(self):

        try:
            if gui_app.job_tracker_bar is not None:
                gui_app.job_tracker_bar.hide_job_tracker_bar()

        except FileNotFoundError as ex:

            logger.exception("An unexpected error has occurred\n\njob_tracker_hide()\n\n" + str(ex))
            return

    def job_tracker_open(self):

        try:
            gui_app.job_tracker_bar = JobTrackerBar(gui_app.main_window, self.user_config.user_initials)
            gui_app.job_tracker_bar.pack(fill="x")
            gui_app.job_tracker_bar.show_job_tracker_bar()

        except FileNotFoundError as ex:
            print("Couldn't find the Job Tracker Spreadsheet:\n\n" + self.job_tracker_filepath)
            logger.exception("An unexpected error has occurred\n\nbtn_job_tracker()\n\n" + str(ex))
            tk.messagebox.showerror("Survey Assist", "Couldn't find the Job Tracker Spreadsheet:\n\n" + self.job_tracker_filepath)
            return

    def open_manual(self):
        try:
            os.startfile("Survey Assist Manual.docx")
        except Exception as ex:
            print("Problem opening up Manual\n\n" + str(ex))
            logger.exception("An unexpected error has occurred\n\nopen_manual()\n\n" + str(ex))
            tk.messagebox.showerror("Survey Assist", "An unexpected error has occurred\n\nopen_manual()\n\n" + str(ex))
            return

    def open_log(self):
        try:
            os.startfile("Survey Assist.log")
        except Exception as ex:
            print("Problem opening log\n\n" + str(ex))
            logger.exception("An unexpected error has occurred\n\nopen_log()\n\n" + str(ex))
            tk.messagebox.showerror("Survey Assist", "An unexpected error has occurred\n\nopenlog()\n\n" + str(ex))
            return

    @staticmethod
    def clear_query():
        try:
            gui_app.list_box.populate(gsi.formatted_lines)
        except Exception as ex:
            print("Problem opening up the GSI file\n\n" + str(ex))
            logger.exception("An unexpected error has occurred\n\nclear_query()\n\n" + str(ex))
            tk.messagebox.showerror("Survey Assist", "An unexpected error has occurred\n\nclear_query()\n\n" + str(ex))
            return

    def enable_menus(self):

        self.menu_bar.entryconfig("Check Survey", state="normal")
        self.menu_bar.entryconfig("Edit Survey", state="normal")

    def disable_menus(self):

        self.menu_bar.entryconfig("Check Survey", state="disabled")
        self.menu_bar.entryconfig("Edit Survey", state="disabled")

    @staticmethod
    def display_about_dialog_box():

        about_me_text = "This program imports survey data, reads in a GSI file and displays the data in a clearer, more user-friendly format." \
                        " \n\nYou can then edit this GSI and change point names, target heights and prism constants.,  You can also check the " \
                        "survey for errors - such as incorrect station labelling, incorrect prism constants and out-of-tolerance survey errors. " \
                        "\n\n" \
                        "This program also assists with Compnet - combining gsi files, copying over fixed files, comparing CRD files, and " \
                        "stripping out the GSI leaving just the control stations for easier analysis of problems.\n\n" \
                        "Written by Richard Walter 2019"

        tkinter.messagebox.showinfo("About Survey Assist", about_me_text)

    @staticmethod
    def client_exit():
        # logger.info("Exiting the application")
        exit()

    @staticmethod
    def delete_orientation_shots():

        deleted_lines = []  # used to display to user after deletion

        try:

            with open(MenuBar.filename_path, "r") as gsi_file:

                line_list = list(gsi_file)  # puts all lines in a list

                counter = 1  # this is used to keep track so the correct line is deleted

                for orientation_line_number in ListBoxFrame.orientation_line_numbers:
                    deleted_lines.append(line_list[int(orientation_line_number) - counter])

                    del line_list[int(orientation_line_number) - counter]
                    counter += 1

            # rewrite the line_list from list contents/elements:
            with open(MenuBar.filename_path, "w") as gsi_file:
                for line in line_list:
                    gsi_file.write(line)

            print("deleted lines are: \n\n" + str(deleted_lines))

            # rebuild database and GUI
            GUIApplication.refresh()

            msg_deleted_lines = str(len(deleted_lines)) + " 2D orientation shots have been deleted"

            # display deleted lines dialog box
            tkinter.messagebox.showinfo("2D Orientation Shots", msg_deleted_lines)

        except FileNotFoundError:

            # Do nothing: User has hit the cancel button
            gui_app.status_bar.status['text'] = 'Please choose a GSI File'

        except CorruptedGSIFileError:

            # Most likely an corrupted GSI file was selected
            tk.messagebox.showerror("LOADING GSI", 'Error reading GSI File:\n\nThis file is a corrupted or incorrect GSI file')

            gui_app.status_bar.status['text'] = 'Please choose a GSI File'

        except Exception as ex:

            # Most likely an incorrect file was chosen
            logger.exception('Error has occurred. ')

            tk.messagebox.showerror("ERROR", 'Error reading GSI File:\n\nPlease make sure file is not opened '
                                             'by another program.  If problem continues please contact Richard Walter\n\n' + str(ex))


class ConfigDialogWindow:
    # dialog_w = 300
    # dialog_h = 240

    def __init__(self, master):

        self.master = master

        self.sorted_stn_file_path = survey_config.sorted_station_config
        self.current_rail_monitoring_name = survey_config.current_rail_monitoring_file_name

        #  Lets build the dialog box
        self.dialog_window = tk.Toplevel(master)
        self.dialog_window.title("Survey Configuration")

        # self.dialog_window.geometry(MainWindow.position_popup(master, ConfigDialog.dialog_w, ConfigDialog.dialog_h))

        # tk.Label(self.dialog_window, text="Precision:").grid(row=0, column=0, padx=5, pady=(15, 5), sticky='w')
        # self.precision = tk.StringVar()
        # self.precision_entry = ttk.Combobox(self.dialog_window, textvariable=self.precision, state='readonly')
        # self.precision_entry['values'] = SurveyConfiguration.precision_value_list
        #
        # self.precision_entry.current(
        #     SurveyConfiguration.precision_value_list.index(survey_config.precision_value))
        # self.precision_entry.bind("<<ComboboxSelected>>")
        # self.precision_entry.grid(row=0, column=1, padx=5, pady=(15, 5), sticky='w')

        tk.Label(self.dialog_window, text="Easting Tolerance: ").grid(row=1, column=0, padx=5, pady=(20, 5), sticky='w')
        self.entry_easting = tk.Entry(self.dialog_window)
        self.entry_easting.insert(tkinter.END, survey_config.easting_tolerance)
        self.entry_easting.grid(row=1, column=1, padx=10, pady=(20, 5), sticky='w', )

        tk.Label(self.dialog_window, text="Northing Tolerance: ").grid(row=2, column=0, padx=5, pady=5, sticky='w')
        self.entry_northing = tk.Entry(self.dialog_window)
        self.entry_northing.insert(tkinter.END, survey_config.northing_tolerance)
        self.entry_northing.grid(row=2, column=1, padx=10, pady=5, sticky='w')

        tk.Label(self.dialog_window, text="Height Tolerance: ").grid(row=3, column=0, padx=5, pady=5, sticky='w')
        self.entry_height = tk.Entry(self.dialog_window)
        self.entry_height.insert(tkinter.END, survey_config.height_tolerance)
        self.entry_height.grid(row=3, column=1, padx=10, pady=5, sticky='w')

        self.sorted_station_file_lbl = tk.Label(self.dialog_window, text="Sorted station file: ").grid(row=4, column=0,padx=10, pady=10, sticky='w')
        self.sorted_station_file_btn = tk.Button(self.dialog_window, text=os.path.basename(self.sorted_stn_file_path), command=self.select_sorted_stn_file)
        self.sorted_station_file_btn.grid(row=4, column=1, padx=10, pady=10, sticky='w')

        self.current_rail_monitoring_file_lbl = tk.Label(self.dialog_window, text="Rail Monitoring Name: ").grid(row=5, column=0,padx=10, pady=10,
                                                                                                          sticky='w')
        self.current_rail_monitoring_file_entry = tk.Entry(self.dialog_window)
        self.current_rail_monitoring_file_entry.grid(row=5, column=1, padx=10, pady=10, sticky='w')
        self.current_rail_monitoring_file_entry.insert(tk.END, self.current_rail_monitoring_name)

        save_b = tk.Button(self.dialog_window, text="Save", width=10, command=self.save)
        save_b.grid(row=6, column=0, padx=10, pady=20, sticky='nesw')

        cancel_b = tk.Button(self.dialog_window, text="Cancel", width=10, command=self.cancel)
        cancel_b.grid(row=6, column=1, padx=20, pady=20, sticky='nesw')

        self.dialog_window.geometry(MainWindow.position_popup(master, 330, 270))

    def select_sorted_stn_file(self):

        self.sorted_stn_file_path = tk.filedialog.askopenfilename(parent=self.master, title='Please select the sorted station file',
                                                                  filetypes=[("Text Files", ".TXT")])
        if self.sorted_stn_file_path != "":
            self.sorted_station_file_btn.config(text=os.path.basename(self.sorted_stn_file_path))
        self.dialog_window.lift()  # bring window to the front again

    def save(self):

        global survey_config

        precision_dictionary = {}
        survey_tolerance_dictionary = {}
        configuration_dictionary = {}
        file_directory_dictionary = {}

        # precision_dictionary['instrument_precision'] = self.precision_entry.get()
        survey_tolerance_dictionary['eastings'] = self.entry_easting.get()
        survey_tolerance_dictionary['northings'] = self.entry_northing.get()
        survey_tolerance_dictionary['height'] = self.entry_height.get()
        configuration_dictionary['sorted_station_config'] = self.sorted_stn_file_path
        file_directory_dictionary['current_rail_monitoring_file_name'] = self.current_rail_monitoring_file_entry.get().strip()

        input_error = False

        # Check monitoring file name entered
        if not file_directory_dictionary['current_rail_monitoring_file_name']:
            tkinter.messagebox.showinfo("Survey Config", "Please enter a name for the current monitoring file")
            logger.info("no current monitoring name entered")
            self.dialog_window.destroy()

            # re-display query dialog
            ConfigDialogWindow(self.master)

            return

        # check to make sure number is entered
        for value in survey_tolerance_dictionary.values():

            try:
                float(value)

            except ValueError:

                input_error = True

                break

        if input_error:

            tkinter.messagebox.showinfo("Survey Config", "Please enter a numerical tolerance value")
            logger.info("Invalid tolerance configuration value entered")
            self.dialog_window.destroy()

            # re-display query dialog
            ConfigDialogWindow(self.master)
        else:

            self.dialog_window.destroy()

            # update config file
            for key, value in precision_dictionary.items():
                survey_config.update(SurveyConfiguration.section_instrument, key, value)

            for key, value in survey_tolerance_dictionary.items():
                survey_config.update(SurveyConfiguration.section_survey_tolerances, key, value)

            for key, value in configuration_dictionary.items():
                survey_config.update(SurveyConfiguration.section_config_files, key, value)

            for key, value in file_directory_dictionary.items():
                survey_config.update(SurveyConfiguration.section_file_directories, key, value)

            survey_config = SurveyConfiguration()

            tkinter.messagebox.showinfo("Survey Config", "Settings updated.\n\nPlease RE-START Survey Assist")

    def cancel(self):

        self.dialog_window.destroy()


class QueryDialogWindow:

    def __init__(self, master):

        self.master = master

        #  Lets build the dialog box
        self.dialog_window = tk.Toplevel(master)
        self.dialog_window.title("SQL Query")

        # self.dialog_window.geometry(self.center_screen())
        self.dialog_window.geometry(MainWindow.position_popup(master, 330,
                                                              150))

        tk.Label(self.dialog_window, text="Build an SQL 'where' statement:").grid(row=0, padx=5, pady=5)
        tk.Label(self.dialog_window, text="Select column:").grid(row=1, sticky="W", padx=5, pady=5)
        tk.Label(self.dialog_window, text="Enter a column value:").grid(row=2, sticky="W", padx=5, pady=2)

        # column entry is where the user selects the column he wants to perform a query on
        self.column = tk.StringVar()
        self.column_entry = ttk.Combobox(self.dialog_window, width=18, textvariable=self.column, state='readonly')
        self.column_entry['values'] = gsi.query_column_names
        self.column_entry.bind("<<ComboboxSelected>>", self.column_entry_cb_callback)
        self.column_entry.grid(row=1, column=1, padx=5, pady=5)

        # column value is the value associated with the selected column
        self.column_value = tk.StringVar()
        self.column_value_entry = ttk.Combobox(self.dialog_window, width=18, textvariable=self.column_value,
                                               state='disabled')
        self.column_value_entry.grid(row=2, column=1, padx=5, pady=2)

        ok_b = tk.Button(self.dialog_window, text="OK", width=10, command=self.ok)
        ok_b.grid(row=3, column=0, pady=10)

        cancel_b = tk.Button(self.dialog_window, text="Cancel", width=10, command=self.cancel)
        cancel_b.grid(row=3, column=1, pady=10)

    def column_entry_cb_callback(self, event):

        # Set the values for the column_value combobox now that the column name has been selected
        # It removes any duplicate values and then orders the result.
        self.column_value_entry['values'] = sorted(set(gsi.get_column_values(self.column_entry.get())))

        self.column_value_entry.config(state='readonly')

    def ok(self):

        column_entry = self.column_entry.get()
        column_value_entry = self.column_value_entry.get()

        if column_entry == "":
            tkinter.messagebox.showinfo("GSI Query", "Please enter valid search data")
            logger.info(
                "Invalid data entered.  Column Name was {}: column value was {}".format(column_entry,
                                                                                        column_value_entry))

            # re-display query dialog
            QueryDialogWindow(self.master)
            return

        query_results = self.execute_sql_query(database.TABLE_NAME, column_entry, column_value_entry)
        print(query_results)

        self.dialog_window.destroy()
        self.repopulate_list_box(query_results)

    def cancel(self):
        self.dialog_window.destroy()

    @staticmethod
    def execute_sql_query(database_table, column_name, column_value):

        sql_query_text = "SELECT * FROM {} WHERE {}=?".format(database_table, column_name)

        try:
            with database.conn:

                cur = database.conn.cursor()
                cur.execute(sql_query_text, (column_value,))
                rows = cur.fetchall()

            return rows

        except Exception as ex:
            logger.exception('Error creating executing SQL query:  {}'.format(sql_query_text))
            tk.messagebox.showerror("Error", 'Error executing this query:\nPlease contact the developer of this program\n\n' + str(ex))

    @staticmethod
    def repopulate_list_box(query_results):

        line_number = 0

        if query_results is not None:

            # Remove any previous data first
            gui_app.list_box.list_box_view.delete(*gui_app.list_box.list_box_view.get_children())

            for query_result in query_results:
                query_list = list(query_result)
                print(query_list)
                line_number += 1
                query_list.insert(0, line_number)
                gui_app.list_box.list_box_view.insert("", "end", values=query_list)

        # disable the ability to delete line as the line # doesnt match the GSI file in a query
        gui_app.list_box.list_box_view.unbind('<Delete>')


class StatusBar(tk.Frame):

    def __init__(self, master):
        super().__init__(master)

        self.master = master
        self.frame = tk.Frame(master)
        self.status = tk.Label(master, text='Welcome to Survey Assist', relief=tk.SUNKEN, anchor=tk.W)


class WorkflowBar(tk.Frame):

    def __init__(self, master):
        super().__init__(master)

        self.master = master
        self.frame = tk.Frame(self.master)
        self.frame.pack(side='top', anchor=tk.W, fill=tk.X)
        self.frame.configure(background='#FFDEAC')

        # new job workflow
        self.workflow_lbl = tk.Label(self.frame, text='NEW JOB:')
        self.workflow_lbl.configure(background='#FFDEAC')
        self.btn_diary = tk.Button(self.frame, text="Job Diary", command=MenuBar.job_diary)
        self.btn_diary.configure(background='#FCF1E1')
        self.btn_create_directory_today = tk.Button(self.frame, text="Create Dated Directory",
                                                    command=lambda: gui_app.menu_bar.new_dated_directory(False))
        self.btn_create_directory_today.configure(background='#FCF1E1')
        self.btn_import_sd_data = tk.Button(self.frame, text="Import SD Data", command=lambda: gui_app.menu_bar.import_sd_data())
        self.btn_import_sd_data.configure(background='#FCF1E1')
        self.btn_open_gsi = tk.Button(self.frame, text="Open GSI", command=lambda: gui_app.menu_bar.choose_gsi_file())
        self.btn_open_gsi.configure(background='#FCF1E1')
        self.lbl_edit_gsi = tk.Label(self.frame, text="Edit GSI", borderwidth=2, relief="groove", padx=4, pady=4)
        self.lbl_edit_gsi.configure(background='#FCF1E1')
        self.btn_check_survey = tk.Button(self.frame, text="Check Survey", command=lambda: gui_app.menu_bar.check_3d_all())
        self.btn_check_survey.configure(background='#FCF1E1')
        self.btn_compare_survey = tk.Button(self.frame, text="Compare Survey", command=lambda: gui_app.menu_bar.compare_survey())
        self.btn_compare_survey.configure(background='#FCF1E1')
        self.btn_export_csv = tk.Button(self.frame, text="Export GSI", command=lambda: gui_app.menu_bar.export_csv())
        self.btn_export_csv.configure(background='#FCF1E1')

        # Compnet workflow
        self.compnet_workflow_lbl = tk.Label(self.frame, text='COMPNET:')
        self.compnet_workflow_lbl.configure(background='#FFDEAC')
        self.btn_compnet_new_job = tk.Button(self.frame, text="Setup New Job", command=lambda: gui_app.menu_bar.create_compnet_job_folder())
        self.btn_compnet_new_job.configure(background='#FCF1E1')
        self.btn_update_fixed_file = tk.Button(self.frame, text="Update Fixed File", command=lambda: gui_app.menu_bar.update_fixed_file())
        self.btn_update_fixed_file.configure(background='#FCF1E1')
        self.btn_weight_std_file = tk.Button(self.frame, text="Weight STD File", command=lambda: gui_app.menu_bar.weight_STD_file())
        self.btn_weight_std_file.configure(background='#FCF1E1')
        self.btn_copy_job_to_dated_directory = tk.Button(self.frame, text="Copy Job to Dated Directory", command=lambda:
        gui_app.menu_bar.copy_compnet_job_to_dated_directory())
        self.btn_copy_job_to_dated_directory.configure(background='#FCF1E1')
        self.btn_csv_from_crd = tk.Button(self.frame, text="Popup CSV from CRD", command=lambda: gui_app.menu_bar.create_CSV_from_CRD())
        self.btn_csv_from_crd.configure(background='#FCF1E1')

        # Redisplay observations button
        self.btn_re_display_gsi = tk.Button(self.frame, text="Re-display GSI", command=lambda: gui_app.menu_bar.re_display_gsi())
        self.btn_re_display_gsi.configure(background='#FCF1E1')

        # pack new job workflow
        self.workflow_lbl.pack(padx=2, pady=5, side='left')
        self.btn_diary.pack(padx=5, pady=5, side='left')
        self.btn_create_directory_today.pack(padx=5, pady=5, side='left')
        self.btn_import_sd_data.pack(padx=5, pady=5, side='left')
        self.btn_open_gsi.pack(padx=5, pady=5, side='left')
        self.lbl_edit_gsi.pack(padx=5, pady=5, side='left')
        self.btn_check_survey.pack(padx=5, pady=5, side='left')
        self.btn_compare_survey.pack(padx=5, pady=5, side='left')
        self.btn_export_csv.pack(padx=5, pady=5, side='left')

        # pack compnet workflow
        self.compnet_workflow_lbl.pack(padx=(25, 2), pady=5, side='left')
        self.btn_compnet_new_job.pack(padx=5, pady=5, side='left')
        self.btn_update_fixed_file.pack(padx=5, pady=5, side='left')
        self.btn_weight_std_file.pack(padx=5, pady=5, side='left')
        self.btn_copy_job_to_dated_directory.pack(padx=5, pady=5, side='left')
        self.btn_csv_from_crd.pack(padx=5, pady=5, side='left')

        # pack re-display observations
        self.btn_re_display_gsi.pack(padx=(30, 10), pady=5, side='right')

    def show_workflow_bar(self):
        self.frame.pack(side='top', anchor=tk.W, fill=tk.X)

    def hide_workflow_bar(self):
        self.frame.pack_forget()


class JobTrackerBar(tk.Frame):

    def __init__(self, master, user_initials):
        super().__init__(master)

        self.master = master
        self.frame = tk.Frame(self.master)
        self.frame.pack(side='top', anchor=tk.W, fill=tk.X)
        self.frame.configure(background='#d9f2d8')
        self.user_initials = user_initials
        self.todays_date = datetime.datetime.today().strftime('%d/%m/%Y')
        self.job_tracker_filepath = os.path.join(survey_config.root_job_directory, survey_config.current_year, survey_config.job_tracker_filename)
        self.job_tracker_backup_filepath = os.path.join(survey_config.root_job_directory, survey_config.current_year,
                                                        survey_config.job_tracker_filename)

        self.job_tracker = JobTracker(self.job_tracker_filepath, logger)

        # Create widgets
        self.jt_lbl = tk.Label(self.frame, text='JOB TRACKER:')
        self.jt_lbl.configure(background='#d9f2d8')

        self.jt_date_lbl = tk.Label(self.frame, text='Survey Date:')
        self.jt_date_lbl.configure(background='#d9f2d8')

        self.jt_date_btn = tk.Button(self.frame, text=self.todays_date, command=self.choose_date)
        self.jt_date_btn.configure(background='#ffffff')
        self.jt_initials_lbl = tk.Label(self.frame, text='Initials:')
        self.jt_initials_lbl.configure(background='#d9f2d8')
        self.jt_user_entry = tk.Entry(self.frame, width=8)
        self.jt_user_entry.insert(tk.END, user_initials)
        # self.jt_user_lbl.configure(background='#d9f2d8')

        # check boxes
        self.calcs_checkbox_var = tk.StringVar()
        self.results_checkbox_var = tk.StringVar()
        self.checked_checkbox_var = tk.StringVar()
        self.sent_checkbox_var = tk.StringVar()
        self.xml_checkbox_var = tk.StringVar()

        self.jt_calcs_checkbox = tk.Checkbutton(self.frame, text='Calcs', variable=self.calcs_checkbox_var, onvalue='1', offvalue='')
        self.jt_calcs_checkbox.configure(background='#d9f2d8')
        self.jt_results_checkbox = tk.Checkbutton(self.frame, text='Results', variable=self.results_checkbox_var, onvalue='1', offvalue='')
        self.jt_results_checkbox.configure(background='#d9f2d8')
        self.jt_checked_checkbox = tk.Checkbutton(self.frame, text='Checked', variable=self.checked_checkbox_var, onvalue='1', offvalue='')
        self.jt_checked_checkbox.configure(background='#d9f2d8')
        self.jt_sent_checkbox = tk.Checkbutton(self.frame, text='Sent', variable=self.sent_checkbox_var, onvalue='1', offvalue='')
        self.jt_sent_checkbox.configure(background='#d9f2d8')
        self.jt_xml_checkbox = tk.Checkbutton(self.frame, text='XML', variable=self.xml_checkbox_var, onvalue='1', offvalue='')
        self.jt_xml_checkbox.configure(background='#d9f2d8')

        # notes label and entry
        text = 'Outstanding/Notes'
        self.jt_notes_label = tk.Label(self.frame, text='Outstanding/Notes: ')
        self.jt_notes_label.configure(background='#d9f2d8')
        self.jt_notes_entry = tk.Entry(self.frame, width=40)

        # save button
        self.jt_btn_save_job = tk.Button(self.frame, text="Save Job", command=self.save_job_to_excel)
        self.jt_btn_save_job.configure(background='#ffffff')

        # Combobox
        self.job_name = tk.StringVar()
        self.jt_job_name_combo = ttk.Combobox(self.frame, width=35, textvariable=self.job_name, postcommand=self.get_latest_combobox_values)

        self.jt_job_name_combo['values'] = self.get_combobox_values()
        self.jt_job_name_combo.bind("<<ComboboxSelected>>", self.cb_callback)

        self.jt_job_name_combo.current(0)

        # open in excel button
        self.jt_btn_open_in_excel = tk.Button(self.frame, text="Open in Excel", command=self.open_in_excel)
        self.jt_btn_open_in_excel.configure(background='#ffffff')

        # pack job tracker widgets
        self.jt_lbl.pack(padx=5, pady=5, side='left')
        self.jt_job_name_combo.pack(padx=5, pady=5, side='left')
        self.jt_date_lbl.pack(padx=(15, 0), pady=5, side='left')
        self.jt_date_btn.pack(padx=5, pady=5, side='left')
        self.jt_initials_lbl.pack(padx=(15, 0), pady=5, side='left')
        self.jt_user_entry.pack(padx=0, pady=5, side='left')
        self.jt_calcs_checkbox.pack(padx=(15, 0), pady=5, side='left')
        self.jt_results_checkbox.pack(padx=(15, 0), pady=5, side='left')
        self.jt_checked_checkbox.pack(padx=(15, 0), pady=5, side='left')
        self.jt_sent_checkbox.pack(padx=(15, 0), pady=5, side='left')
        self.jt_xml_checkbox.pack(padx=(15, 0), pady=5, side='left')
        self.jt_notes_label.pack(padx=(15, 0), pady=5, side='left')
        self.jt_notes_entry.pack(padx=(15, 0), pady=5, side='left')

        self.jt_btn_save_job.pack(padx=(50, 0), pady=5, side='left')
        self.jt_btn_open_in_excel.pack(padx=(15, 15), pady=5, side='right')

    def cb_callback(self, event):

        # get job details and populate job tracker widget
        survey_job = self.job_tracker.get_job(self.jt_job_name_combo.get())

        if survey_job:
            self.jt_date_btn.configure(text=survey_job.survey_date)
            # self.jt_user_entry.configure(text=survey_job.initials)

            if survey_job.calcs == '1':
                self.jt_calcs_checkbox.select()
            else:
                self.jt_calcs_checkbox.deselect()

            if survey_job.results == '1':
                self.jt_results_checkbox.select()
            else:
                self.jt_results_checkbox.deselect()

            if survey_job.checked == '1':
                self.jt_checked_checkbox.select()
            else:
                self.jt_checked_checkbox.deselect()

            if survey_job.sent == '1':
                self.jt_sent_checkbox.select()
            else:
                self.jt_sent_checkbox.deselect()

            if survey_job.xml == '1' or survey_job.xml == '2':
                self.jt_xml_checkbox.select()
            else:
                self.jt_xml_checkbox.deselect()

            self.jt_notes_entry.delete(0, tk.END)
            self.jt_notes_entry.insert(0, survey_job.notes)

            self.jt_user_entry.delete(0, tk.END)
            self.jt_user_entry.insert(0, survey_job.initials)

        else:  # user has selected to create a new job
            self.jt_date_btn.configure(text=self.todays_date)
            self.jt_calcs_checkbox.deselect()
            self.jt_results_checkbox.deselect()
            self.jt_checked_checkbox.deselect()
            self.jt_sent_checkbox.deselect()
            self.jt_xml_checkbox.deselect()
            # self.jt_user_entry.configure(text=self.user_initials)
            self.jt_notes_entry.delete(0, tk.END)
            self.jt_notes_entry.insert(0, "")
            self.jt_user_entry.delete(0, tk.END)
            self.jt_user_entry.insert(0, self.user_initials)

    def get_latest_combobox_values(self):

        self.job_tracker = JobTracker(self.job_tracker_filepath, logger)
        self.jt_job_name_combo['values'] = self.get_combobox_values()
        # self.jt_job_name_combo.bind("<<ComboboxSelected>>", self.cb_callback)

    def get_combobox_values(self):

        # self.job_tracker = JobTracker(self.job_tracker_filepath, logger)
        job_names = self.job_tracker.get_job_names()

        if not job_names:  # problem has occurred.  Disable job tracker

            job_names.insert(0, "<<ERROR>>")

            self.jt_btn_save_job.configure(state='disabled')

            raise Exception("No Job Names Found")

        else:
            job_names.insert(0, "<<Enter New Job>>")

        return job_names[0:30]  # only return the 30 most recent jobs as the list gets too large

    def choose_date(self):

        # Let user choose the date, rather than the default todays date
        cal_root = tk.Toplevel()
        cal = CalendarWindow(cal_root, todays_date)
        self.master.wait_window(cal_root)
        survey_date = cal.get_selected_date()  # e.g. '200610'
        self.jt_date_btn['text'] = survey_date[4:6] + "/" + survey_date[2:4] + "/" + survey_date[0:2]

    def show_job_tracker_bar(self):
        self.frame.pack(side='top', anchor=tk.W, fill=tk.X)

    def hide_job_tracker_bar(self):
        self.frame.pack_forget()
        gui_app.job_tracker_bar = None

    def open_in_excel(self):
        try:
            os.startfile(self.job_tracker_filepath)

        except FileNotFoundError as ex:
            print("Couldn't find the Job Tracker Spreadsheet:\n\n" + self.job_tracker_filepath)
            logger.exception("An unexpected error has occurred\n\nbtn_job_tracker()\n\n" + str(ex))
            tk.messagebox.showerror("Survey Assist", "Couldn't find the Job Tracker Spreadsheet:\n\n" + self.job_tracker_filepath)
            return

    def save_job_to_excel(self):

        two_color_scale_rule = ColorScaleRule(start_type='num', start_value=0, start_color='FFFFFF', end_type='num', end_value=1,
                                              end_color='70AD47')

        xml_two_color_scale_rule = ColorScaleRule(start_type='num', start_value=1, start_color='70AD47', end_type='num', end_value=2,
                                                  end_color='FFFF00')

        green_font = Font(color='00B050')
        yellow_font = Font(color='FFFF00')

        border = Border(bottom=Side(border_style='thin', color='000000'))

        try:
            job_name = self.jt_job_name_combo.get()
            job_date = self.jt_date_btn['text']

            selected_job_index = self.jt_job_name_combo.current()

            if job_name == "<<Enter New Job>>":
                tk.messagebox.showerror("Survey Assist", "Please enter a job name")
                return

            print(self.jt_job_name_combo.current())

            # try and read in the job tracker spreadsheet
            workbook = load_workbook(self.job_tracker_filepath, read_only=False, keep_vba=True)
            actions_sheet = workbook["Actions"]

            # create a new job tracker in case excel has been updated in between selecting job and saving job
            self.job_tracker = JobTracker(self.job_tracker_filepath, logger)

            # max cell range based on the number of job tracker jobs
            max_range_cell = str((11 + len(self.job_tracker.get_job_names())))
            cell_range = "J11:J" + max_range_cell
            print('Cell Range ' + cell_range)

            # check to see if we are adding a new job or updating an old one.
            if self.jt_job_name_combo.current() == -1:  # user is creating a new job

                # insert blank row at row 11 and populate
                actions_sheet.insert_rows(idx=11)
                actions_sheet["A11"].value = self.jt_job_name_combo.get()

                self.update_job_date(actions_sheet["B11"], job_date)
                self.update_user(actions_sheet["C11"], self.jt_user_entry.get())

                # apply 2-scale conditional formatting to check boxes
                actions_sheet.conditional_formatting.add("D11:G11", two_color_scale_rule)
                actions_sheet.conditional_formatting.add("H11", xml_two_color_scale_rule)

                # apply font to the checkboxes
                actions_sheet["D11"].font = green_font
                actions_sheet["D11"].border = border
                actions_sheet["E11"].font = green_font
                actions_sheet["E11"].border = border
                actions_sheet["F11"].font = green_font
                actions_sheet["F11"].border = border
                actions_sheet["G11"].font = green_font
                actions_sheet["G11"].border = border
                actions_sheet["H11"].font = yellow_font
                actions_sheet["H11"].border = border

                self.update_checkbox_values(actions_sheet, "11")

                actions_sheet["I11"] = self.jt_notes_entry.get()

                # % Complete - add formula and update all subsequent row formulas as it doesn't update when inserting a row for some reason
                for row in range(11, 11 + len(self.job_tracker.get_job_names())):
                    percentage_complete_cell = 'J' + str(row)
                    # actions_sheet[percentage_complete_cell] = '=SUM(D' + str(row) + ':H' + str(row) +')'
                    cell_forumula = '=IF(SUM(D' + str(row) + ': H' + str(row) + ') > 5, REPT("g", 10), (REPT("g", SUM(D' + str(row) + ': H' + str(
                        row) + ') * 2)))'
                    actions_sheet[percentage_complete_cell] = cell_forumula

                    # Change font
                    actions_sheet[percentage_complete_cell].font = Font(color="4472C4", name="Webdings")

                # self.update_conditional_formatting(actions_sheet)

            else:  # updating an existing job

                excel_row_to_update = -1

                # The excel might have been updated by another user.  We need to match the job name and date to get the current index.
                for index, row in enumerate(actions_sheet.iter_rows(min_row=11, max_row=100, min_col=1, max_col=2), start=11):
                    row_job_name = row[0].value.strip()
                    row_job_date = row[1].value

                    # sometimes excel job date is stored as a string or a datetime object.
                    if isinstance(row_job_date, datetime.datetime):
                        row_job_date = row_job_date.strftime('%d/%m/%Y')
                    else:
                        row_job_date = row_job_date.strip()

                    if job_name == row_job_name and job_date == row_job_date:
                        excel_row_to_update = str(index)
                        selected_job_index = int(excel_row_to_update)-10  # required to set the combo box value after a refresh
                        break

                # current_job_selected_line = self.jt_job_name_combo.current()
                # excel_row_to_update = str(10 + current_job_selected_line)

                self.update_job_date(actions_sheet["B" + excel_row_to_update], self.jt_date_btn['text'])
                self.update_user(actions_sheet["C" + excel_row_to_update], self.jt_user_entry.get())
                self.update_checkbox_values(actions_sheet, excel_row_to_update)
                actions_sheet["I" + excel_row_to_update] = self.jt_notes_entry.get()
                # self.update_conditional_formatting(actions_sheet)

            workbook.save(filename=self.job_tracker_filepath)
            workbook.close()

            # reset combo box after update
            self.job_tracker = JobTracker(self.job_tracker_filepath, logger)
            self.jt_job_name_combo['values'] = self.get_combobox_values()
            self.jt_calcs_checkbox.deselect()
            self.jt_results_checkbox.deselect()

            if selected_job_index == -1:  # new job created
                self.jt_job_name_combo.current(1)
            else:
                self.jt_job_name_combo.current(selected_job_index)

            self.cb_callback(None)

        except FileNotFoundError as ex:

            logger.exception('Job Tracker excel spreadsheet not found\n\n' + str(ex))

            tk.messagebox.showerror("ERROR", "Unable to find the Job Tracker Spreadsheet at the following location:\n\n" + self.job_tracker_filepath)

        except PermissionError as ex:

            logger.exception('Job Tracker excel spreadsheet currently in use\n\n' + str(ex))

            tk.messagebox.showinfo("Survey Assist", "The Job Tracker Excel Spreadsheet is currently open.  Please close it down and try again.")

        except Exception as ex:

            # Most likely an incorrect file was chosen
            logger.exception('Error has occurred in JobTracker init().\n\n' + str(ex))

            tk.messagebox.showerror("ERROR", 'An unexpected error has occurred reading the excel Job Tracker.  Please contact the developer')

            gui_app.menu_bar.job_tracker_sub_menu.entryconfig("Track/Create a Job", state="disabled")
            gui_app.job_tracker_bar.hide_job_tracker_bar()

        else:
            tk.messagebox.showinfo("Survey Assist", 'Job Saved')

    def update_job_date(self, cell, date_string):

        cell.value = date_string
        cell.alignment = Alignment(horizontal='center')

    def update_user(self, cell, user_initials):

        cell.value = user_initials
        cell.font = Font(color='FF0000')
        cell.alignment = Alignment(horizontal='center')

    def update_checkbox(self, cell, value, font=Font(color='00B050')):

        cell.value = value
        cell.font = font
        cell.alignment = Alignment(horizontal='center')

    def update_checkbox_values(self, actions_sheet, row):

        if self.calcs_checkbox_var.get() == '1':
            self.update_checkbox(actions_sheet["D" + row], 1)
        else:
            self.update_checkbox(actions_sheet["D" + row], "")

        if self.results_checkbox_var.get() == '1':
            self.update_checkbox(actions_sheet["E" + row], 1)
        else:
            self.update_checkbox(actions_sheet["E" + row], "")

        if self.checked_checkbox_var.get() == '1':
            self.update_checkbox(actions_sheet["F" + row], 1)
        else:
            self.update_checkbox(actions_sheet["F" + row], "")

        if self.sent_checkbox_var.get() == '1':
            self.update_checkbox(actions_sheet["G" + row], 1)
        else:
            self.update_checkbox(actions_sheet["G" + row], "")

        if self.xml_checkbox_var.get() == '1':
            self.update_checkbox(actions_sheet["H" + row], 1, Font(color='FFFF00'))
        else:
            self.update_checkbox(actions_sheet["H" + row], "", Font(color='FFFF00'))

    def update_conditional_formatting(self, actions_sheet):

        rule = DataBarRule(start_type='num', start_value=0, end_type='num', end_value=5, color="FF638EC6",
                           showValue=False, minLength=0, maxLength=100)
        max_range_cell = str((10 + len(self.job_tracker.get_job_names())))
        cell_range = "J11:J" + max_range_cell
        print('Cell Range ' + cell_range)
        actions_sheet.conditional_formatting.add(cell_range, rule)


class MainWindow(tk.Frame):

    def __init__(self, master):
        super().__init__(master)

        self.master = master

    @staticmethod
    def position_popup(master, popup_w, popup_h):
        offset_x = 20
        offset_y = 20

        master_x = master.winfo_x()
        master_y = master.winfo_y()

        pop_up_x = master_x + offset_x
        pop_up_y = master_y + offset_y

        master.update_idletasks()

        return '{}x{}+{}+{}'.format(popup_w, popup_h, pop_up_x, pop_up_y)


class ListBoxFrame(tk.Frame):
    orientation_line_numbers = []

    def __init__(self, master):
        super().__init__(master)

        self.master = master
        self.stn_tag = 'STN'
        self.orientation_tag = 'ORI'
        self.highlight_tag = 'HIGHLIGHT'

        self.treeview_column_names = gsi.column_names.copy()
        self.treeview_column_names.insert(0, "#")
        print(self.treeview_column_names)

        # Use Treeview to create list of capture survey shots
        self.list_box_view = ttk.Treeview(master, columns=self.treeview_column_names, selectmode='extended',
                                          show='headings', )

        # Add scrollbar
        vsb = ttk.Scrollbar(self.list_box_view, orient='vertical', command=self.list_box_view.yview)
        vsb.pack(side='right', fill='y')
        # hsb = ttk.Scrollbar(self.list_box_view, orient='horizontal', command=self.list_box_view.xview)
        # hsb.pack(side='bottom', fill='x')
        self.list_box_view.configure(yscrollcommand=vsb.set)
        # self.list_box_view.configure(xscrollcommand=hsb.set)

        # set column headings
        for column_name in self.treeview_column_names:
            self.list_box_view.heading(column_name, text=column_name)
            if column_name == "#":
                self.list_box_view.column(column_name, width=20, stretch=True)
            else:
                self.list_box_view.column(column_name, width=80, stretch=True)

        # On mouse-click event
        # self.list_box_view.bind('<Button-1>', self.selected_row)

        # on delete-keyboard event
        # self.list_box_view.bind('<Delete>', self.delete_selected_row)
        self.list_box_view.bind('<Delete>', self.delete_selected_rows)

        self.list_box_view.pack(fill="both", expand=True)

    def populate(self, formatted_lines, highlight_lines=[]):

        # re-bind gui in case its been remove e.g. Query results will unbind the deletion of lines
        self.list_box_view.bind('<Delete>', self.delete_selected_rows)

        # Remove any previous data first
        self.list_box_view.delete(*self.list_box_view.get_children())
        ListBoxFrame.orientation_line_numbers = []

        line_number = 0

        # Build Display List which expands on the formatted lines from GSI class containing value for all fields
        for formatted_line in formatted_lines:

            tag = ""  # Used to display STN setup rows with a color

            complete_line = []
            line_number += 1

            # add line number first
            complete_line.append(line_number)

            # iterate though column names and find value, assign value if doesnt exist and append to complete list
            for column_name in gsi.column_names:

                gsi_value = formatted_line.get(column_name, "")
                complete_line.append(gsi_value)

                # add STN tag if line is a station setup
                if column_name == gsi.GSI_WORD_ID_DICT['84'] and gsi_value != "":
                    tag = self.stn_tag  # add STN tag if line is a station setup

                elif column_name == gsi.GSI_WORD_ID_DICT['32'] and gsi_value == "":
                    tag = self.orientation_tag

                elif line_number in highlight_lines:
                    tag = self.highlight_tag

            if tag == self.orientation_tag:
                ListBoxFrame.orientation_line_numbers.append(line_number)

            self.list_box_view.insert("", "end", values=complete_line, tags=(tag,))

        # color station setup and the remaining rows
        # self.list_box_view.tag_configure(self.stn_tag, background='#ffe793')
        self.list_box_view.tag_configure(self.stn_tag, background='#FFE793')
        self.list_box_view.tag_configure(self.stn_tag, background='#FFE793')
        # self.list_box_view.tag_configure(self.orientation_tag, background='#d1fac5')
        self.list_box_view.tag_configure(self.orientation_tag, background='#D1FAC5')
        # self.list_box_view.tag_configure(self.highlight_tag, background='#ffff00')
        self.list_box_view.tag_configure(self.highlight_tag, background='#FFFF00')
        # self.list_box_view.tag_configure("", background='#eaf7f9')
        self.list_box_view.tag_configure("", background='#EAF7F9')

    def delete_selected_rows(self, event):

        selected_items = self.list_box_view.selection()
        line_numbers_to_delete = []

        # build list of line numbers to delete
        for selected_item in selected_items:
            line_numbers_to_delete.append(self.list_box_view.item(selected_item)['values'][0])

        try:
            # get gsi file so lines can be deleted
            with open(MenuBar.filename_path, "r") as gsi_file:

                gsi_line_list = list(gsi_file)  # puts all lines in a list

                for index, line_number in enumerate(line_numbers_to_delete, start=1):
                    del gsi_line_list[line_number - index]

                print(gsi_line_list)

            # rewrite the line_list from list contents/elements:
            with open(MenuBar.filename_path, "w") as gsi_file:
                for line in gsi_line_list:
                    gsi_file.write(line)

        except FileNotFoundError:

            # Do nothing: User has hit the cancel button
            gui_app.status_bar.status['text'] = 'Please choose a GSI File'

        except CorruptedGSIFileError as ex:

            # Most likely an corrupted GSI file was selected
            tk.messagebox.showerror("ERROR", 'Error reading GSI File:\n\nThis file is a corrupted or '
                                             'incorrect GSI file\n\n' + str(ex))

            gui_app.status_bar.status['text'] = 'Please choose a GSI File'

        except Exception as ex:

            # Most likely an incorrect file was chosen
            logger.exception('Error has occurred.\n\n' + str(ex))

            tk.messagebox.showerror("ERROR", 'Error reading GSI File:\n\nPlease make sure file is not opened '
                                             'by another program.  If problem continues please contact Richard Walter')
            #
            # # rebuild database and GUI
        GUIApplication.refresh()


class CreateDatedDirectoryWindow:

    def __init__(self, master, selected_directory):
        self.master = master
        self.selected_directory = selected_directory
        self.active_date = todays_date
        #  Lets build the dialog box
        self.dialog_window = tk.Toplevel(master)
        self.dialog_window.title("DATED DIERCTORY")

        container = tk.Frame(self.dialog_window, width=230, height=120)

        question_text = "Create dated folder for the " + todays_date.upper() + "?\n\n"
        self.question_lbl = tk.Label(container, text=question_text)
        self.ok_btn = tk.Button(container, text='OK', command=lambda: self.create_directory(todays_date))
        self.change_date_btn = tk.Button(container, text='Change date', command=self.change_date)

        self.question_lbl.grid(row=1, column=1, columnspan=2, sticky='nesw', padx=30, pady=(20, 5))
        self.ok_btn.grid(row=2, column=1, sticky='nesw', padx=(30, 5), pady=(0, 10))
        self.change_date_btn.grid(row=2, column=2, sticky='nesw', padx=(5, 30), pady=(0, 10))

        container.pack(fill="both", expand=True)

        # self.dialog_window.geometry(MainWindow.position_popup(master, 270, 140))

    def create_directory(self, active_date):

        new_directory_path = os.path.join(self.selected_directory, active_date)

        if os.path.exists(new_directory_path) == False:

            self.dialog_window.destroy()
            os.makedirs(os.path.join(self.selected_directory, active_date))
            os.makedirs(os.path.join(os.path.join(self.selected_directory, active_date), 'OTHER'))
            os.makedirs(os.path.join(os.path.join(self.selected_directory, active_date), 'GPS'))
            os.makedirs(os.path.join(os.path.join(self.selected_directory, active_date), 'OUTPUT'))
            os.makedirs(os.path.join(os.path.join(self.selected_directory, active_date), 'TS'))
            os.makedirs(os.path.join(os.path.join(self.selected_directory, active_date), 'TS', 'TS60'))
            os.makedirs(os.path.join(os.path.join(self.selected_directory, active_date), 'TS', 'MS60'))
            os.makedirs(os.path.join(os.path.join(self.selected_directory, active_date), 'TS', 'TS15'))
            os.makedirs(os.path.join(os.path.join(self.selected_directory, active_date), 'TS', 'EDITING'))

            create_dated_folder = os.path.join(self.selected_directory)
            tk.messagebox.showinfo("Create directory", "Dated directory created in:\n\n" + create_dated_folder)
            # survey_config.update(SurveyConfiguration.section_file_directories, 'todays_dated_directory', new_directory_path)
            survey_config.todays_dated_directory = new_directory_path

        else:
            self.dialog_window.destroy()
            tk.messagebox.showwarning("DATED FOLDER EXISTS", "A dated folder for this date already exists")

    def change_date(self):
        cal_root = tk.Toplevel()
        cal = CalendarWindow(cal_root, todays_date)
        self.master.wait_window(cal_root)
        self.create_directory(cal.get_selected_date())


class ImportRailMonitoringFileWindow:

    def __init__(self, master):
        self.master = master

        #  Lets build the dialog box
        self.dialog_window = tk.Toplevel(master)
        self.dialog_window.title("Import Rail Survey")

        self.sorting_lbl = tk.Label(self.dialog_window, text="Select the total station used:")

        self.ts_id = tk.StringVar()
        self.ts_id.set("TS60")
        self.ts_used = ""
        self.radio_no_sort = tk.Radiobutton(self.dialog_window, text="TS60", value="TS60", var=self.ts_id)
        self.radio_sort_auto = tk.Radiobutton(self.dialog_window, text="MS60", value="MS60", var=self.ts_id)
        self.radio_sort_config = tk.Radiobutton(self.dialog_window, text="TS15", value="TS15", var=self.ts_id)
        self.import_btn = tk.Button(self.dialog_window, text="IMPORT RAIL SURVEY", command=self.set_ts_id)

        self.sorting_lbl.grid(row=0, column=1, sticky='w', columnspan=3, padx=50, pady=(20, 2))
        self.radio_no_sort.grid(row=1, column=1, sticky='w', columnspan=3, padx=70, pady=2)
        self.radio_sort_auto.grid(row=2, column=1, sticky='w', columnspan=3, padx=70, pady=2)
        self.radio_sort_config.grid(row=3, column=1, sticky='w', columnspan=3, padx=70, pady=(2, 1))
        self.import_btn.grid(row=4, column=1, sticky='w', columnspan=1, padx=50, pady=(20, 20))

        self.dialog_window.geometry(MainWindow.position_popup(master, 260, 210))
        # self.dialog_window.attributes('-topmost', 'true')
        self.master.wait_window(self.dialog_window)

    def set_ts_id(self):
        gui_app.menu_bar.ts_used = self.ts_id.get()

        self.dialog_window.destroy()


class PointNameWindow:

    def __init__(self, master):

        self.master = master

        # create point name input dialog box
        self.dialog_window = tk.Toplevel(self.master)

        self.lbl = tk.Label(self.dialog_window, text="Enter a new name for this point")
        self.new_point_name_entry = tk.Entry(self.dialog_window)
        self.btn1 = tk.Button(self.dialog_window, text="UPDATE", command=self.change_point_name)

        self.lbl.grid(row=0, column=1, padx=(20, 2), pady=20)
        self.new_point_name_entry.grid(row=0, column=2, padx=(2, 2), pady=20)
        self.btn1.grid(row=0, column=3, padx=(10, 20), pady=20)

        self.new_point_name_entry.focus()

        self.master.wait_window(self.dialog_window)

    def change_point_name(self):
        try:
            # set the new target height hte user has entered
            new_point_name = self.new_point_name_entry.get().strip()
            print(new_point_name)

            if len(new_point_name) < 16:

                line_numbers_to_ammend = []

                # build list of line numbers to amend
                selected_items = gui_app.list_box.list_box_view.selection()

                if selected_items:
                    for selected_item in selected_items:
                        line_numbers_to_ammend.append(gui_app.list_box.list_box_view.item(selected_item)['values'][0])

                    # update each line to amend with new target height and coordinates
                    for line_number in line_numbers_to_ammend:
                        gsi.update_point_name(line_number, new_point_name)

                    if "EDITED" not in MenuBar.filename_path:
                        amended_filepath = MenuBar.filename_path[:-4] + "_EDITED.gsi"
                    else:
                        amended_filepath = MenuBar.filename_path

                    # create a new ammended gsi file
                    with open(amended_filepath, "w") as gsi_file:
                        for line in gsi.unformatted_lines:
                            gsi_file.write(line)

                    self.dialog_window.destroy()

                    # rebuild database and GUI
                    MenuBar.filename_path = amended_filepath
                    GUIApplication.refresh()
            else:
                # notify user that no lines were selected
                tk.messagebox.showinfo("INPUT ERROR", "Point names must be less than 15 characters in length.")
        except Exception as ex:
            print("Problem opening up the GSI file\n\n" + str(ex))
            logger.exception("An unexpected error has occurred\n\nchange_point_name()\n\n" + str(ex))
            tk.messagebox.showerror("Survey Assist", "An unexpected error has occurred\n\nchange_point_name()\n\n" + str(ex))
            return


class PrismConstantUpdate:

    def __init__(self, master, line_numbers_to_amend=None):

        # self.survey_config = SurveyConfiguration()  # need to create this as opening a new gsi of 4dp wont update precision of the gsi.config
        self.master = master
        self.line_numbers_to_amend = line_numbers_to_amend
        self.point_name = ""

        self.config_files_path = os.path.join(os.getcwd(), 'Config Files')
        self.dialog_window = tk.Toplevel(self.master)
        self.dialog_window.title("Update Prism Constants")
        self.pc_type_label = tk.Label(self.dialog_window, text="Please select the prism constant: ")
        self.pc_batch_label = tk.Label(self.dialog_window, text="Please select the prism constant batch file to process: ")
        self.prism_constant_selected = ""
        self.pc_batch_file_selected = ""
        self.pc_column = tk.StringVar()
        self.pc_column_entry = ttk.Combobox(self.dialog_window, width=32, textvariable=self.pc_column, state='readonly')

        self.pc_column_entry['values'] = sorted(list(gsi.PC_DICT_REAL_VALUES.keys()))

    def build_fix_single_window(self):

        self.dialog_window.geometry(MainWindow.position_popup(self.master, 260, 120))
        self.pc_type_label.grid(row=0, column=1, columnspan=2, padx=25, pady=5)
        self.pc_column_entry.grid(row=1, column=1, columnspan=2, padx=25, pady=5)

        ok_b = tk.Button(self.dialog_window, text="OK", width=10, command=self.ok)
        ok_b.grid(row=3, column=1, padx=(25, 3), pady=10)

        cancel_b = tk.Button(self.dialog_window, text="Cancel", width=10, command=self.cancel)
        cancel_b.grid(row=3, column=2, padx=(3, 25), pady=10)

    def build_batch_file_window(self):

        # first lets build a list of batch files options for the user to choose from
        pc_batch_file_list = []

        files = os.listdir(self.config_files_path)
        for filename in files:
            if 'PC_BATCH_FILE' in filename:
                pc_batch_file_list.append(filename)

        self.dialog_window.geometry(MainWindow.position_popup(self.master, 340, 130))
        self.pc_batch_label.grid(row=0, column=1, columnspan=2, padx=25, pady=5)
        self.pc_column_entry.grid(row=1, column=1, columnspan=2, padx=25, pady=5)
        self.pc_column_entry['values'] = pc_batch_file_list

        run_pc_batch_file_btn = tk.Button(self.dialog_window, text="Update", width=10, command=self.run_pc_batch_file)
        run_pc_batch_file_btn.grid(row=3, column=1, padx=(25, 3), pady=10)

        cancel_b = tk.Button(self.dialog_window, text="Cancel", width=10, command=self.cancel)
        cancel_b.grid(row=3, column=2, padx=(3, 25), pady=10)

    def ok(self):
        self.prism_constant_selected = self.pc_column_entry.get()

        if not self.prism_constant_selected:
            tk.messagebox.showinfo("Updating Prism Constant", "Please select a prism type if you want to update")
            self.dialog_window.lift()

            return

        self.dialog_window.destroy()

        self.point_name = gsi.get_formatted_line(self.line_numbers_to_amend[0])['Point_ID']

        # ask user if he wishes  to update all shots to this mark
        update_all_shots_to_mark = tk.messagebox.askquestion('Update Prism Constants', 'Would you like to update all shots to this mark?')

        if update_all_shots_to_mark == 'yes':
            self.line_numbers_to_amend = gsi.get_point_name_line_numbers(self.point_name)

        # update each line to amend with coordinates
        for line_number in self.line_numbers_to_amend:
            corrections = self.get_prism_constant_corrections(line_number, self.prism_constant_selected)
            if corrections.get('error', ""):
                # something unexpected went wrong
                tk.messagebox.showinfo("Updating Prism Constant", "An unexpected has occurred during update.")
                return

            gsi.pc_change_update_coordinates(line_number, corrections)

        self.create_updated_pc_gsi_file(self.line_numbers_to_amend)

    def run_pc_batch_file(self):
        lines_amended = []
        point_names_not_found_in_batch_file = set()
        self.pc_batch_file_selected = self.pc_column_entry.get()

        if not self.pc_batch_file_selected:
            tk.messagebox.showinfo("Updating Prism Constant", "Please select a prism constant batch file to process")
            self.dialog_window.lift()

            return

        # lets create a dictionary as a pc lookup from batch file
        point_pc_lookup_dict = OrderedDict()
        pc_batch_file_path = os.path.join(self.config_files_path, self.pc_batch_file_selected)
        with open(pc_batch_file_path) as csvfile:
            csv_file = csv.reader(csvfile)
            for row in csv_file:
                point_pc_lookup_dict[row[0]] = row[1]

        # update coordinates for each line
        for line_number, formatted_line in enumerate(gsi.formatted_lines, start=1):
            if gsi.is_station_setup(formatted_line):
                continue  # can't update pc of a setup

            point_name = formatted_line['Point_ID']
            try:
                old_prism_constant = formatted_line['Prism_Constant']
                new_prism_constant = point_pc_lookup_dict[point_name]
            except KeyError:
                # tk.messagebox.showwarning("Updating Prism Constant", "Couldn't find the following point name in the pc batch file\n\n" + point_name)
                point_names_not_found_in_batch_file.add(point_name)
                continue
            else:
                # if PC is the same then skip
                if old_prism_constant == str(gsi.PC_DICT_GSI_VALUES[new_prism_constant]):
                    continue

                corrections = self.get_prism_constant_corrections(line_number, new_prism_constant)
                if corrections.get('error', ""):
                    # something unexpected went wrong
                    tk.messagebox.showinfo("Updating Prism Constant", "An unexpected has occurred during update.")
                    return

                gsi.pc_change_update_coordinates(line_number, corrections)
                lines_amended.append(line_number)

                print("Line amended " + str(line_number) + ":   old PC = " + old_prism_constant + "  new PC = " + str(gsi.PC_DICT_GSI_VALUES[
                                                                                                                          new_prism_constant]))

        # display to user any points not found in batch file
        points_dialog_msg = ""
        for point in sorted(point_names_not_found_in_batch_file):
            points_dialog_msg += point + "\n"

        tk.messagebox.showwarning("Updating Prism Constant", "Warning:  Couldn't find the following point names in the pc batch file:\n\n" +
                                  points_dialog_msg)

        self.create_updated_pc_gsi_file(lines_amended)

        self.dialog_window.destroy()

    def cancel(self):
        self.dialog_window.destroy()

    def create_updated_pc_gsi_file(self, lines_amended=None):

        if "PCUpdated" not in MenuBar.filename_path:

            amended_filepath = MenuBar.filename_path[:-4] + "_PCUpdated.gsi"
        else:
            amended_filepath = MenuBar.filename_path

        # create a new amended gsi file
        with open(amended_filepath, "w") as gsi_file:
            for line in gsi.unformatted_lines:
                gsi_file.write(line)

        self.dialog_window.destroy()

        # rebuild database and GUI
        MenuBar.filename_path = amended_filepath
        MenuBar.format_gsi_file()
        MenuBar.create_and_populate_database()
        gui_app.list_box.populate(gsi.formatted_lines, lines_amended)
        gui_app.status_bar.status['text'] = MenuBar.filename_path

    def get_prism_constant_corrections(self, line_number, prism_constant_selected):

        precision = survey_config.precision_value
        formatted_line = gsi.get_formatted_line(line_number)
        corrections_dict = OrderedDict()

        try:

            old_pc = int(formatted_line['Prism_Constant'])
            new_pc = float(gsi.PC_DICT_REAL_VALUES[prism_constant_selected])

            if old_pc == gsi.PC_DICT_GSI_VALUES[prism_constant_selected]:  # PC is the same - notify user
                tk.messagebox.showinfo("Update Prism Constant",
                                       "The new prism constant is the same as the old one.  Please select a different prism constant if you want to "
                                       "update")
                return
            if old_pc == 0:
                old_pc = float(0.000)
            else:
                old_pc = float(old_pc) / 1000

            adjusted_distance = new_pc - old_pc

            stn_line_number, stn_formatted_line = gsi.get_station_from_line_number(line_number)
            stn_easting = float(stn_formatted_line['STN_Easting'])
            stn_northing = float(stn_formatted_line['STN_Northing'])
            stn_height = float(stn_formatted_line['STN_Elevation'])

            old_easting = float(formatted_line['Easting'])
            old_northing = float(formatted_line['Northing'])
            old_height = float(formatted_line['Elevation'])
            old_slant_distance = float(formatted_line['Slope_Distance'])

            new_slant_distance = float(old_slant_distance + adjusted_distance)
            cos_theta_east = (old_easting - stn_easting) / old_slant_distance
            cost_thea_north = (old_northing - stn_northing) / old_slant_distance
            sin_theta = (old_height - stn_height) / old_slant_distance
            new_east = stn_easting + (cos_theta_east * new_slant_distance)
            new_north = stn_northing + (cost_thea_north * new_slant_distance)
            new_height = stn_height + (sin_theta * new_slant_distance)
            new_horizontal_distance = math.sqrt((new_east - stn_easting) ** 2 + (new_north - stn_northing) ** 2)
            new_height_difference = abs(stn_height - new_height)

            new_slant_distance = str(decimalize_value(new_slant_distance, precision))
            new_east = str(decimalize_value(new_east, precision))
            new_north = str(decimalize_value(new_north, precision))
            new_height = str(decimalize_value(new_height, precision))
            new_horizontal_distance = str(decimalize_value(new_horizontal_distance, precision))
            new_height_difference = str(decimalize_value(new_height_difference, precision))

            # old_pc = str(int(divmod(old_pc * 1000, 1)[0])).zfill(3)
            new_pc = str(int(divmod(new_pc * 1000, 1)[0])).zfill(3).lstrip("0")

            corrections_dict = {'Prism_Constant': new_pc, 'Easting': new_east, 'Northing': new_north, 'Elevation': new_height,
                                'Slope_Distance': new_slant_distance, 'Horizontal_Dist': new_horizontal_distance,
                                'Height_Diff': new_height_difference}


        except ValueError as ex:  # this will happen if it is an orientation shot

            print("unexpected error updating prism constants\n\n" + str(ex))
        except Exception as ex:
            corrections_dict['error'] = 'yes'
            print("unexpected error updating prism constants\n\n" + str(ex))
        finally:

            return corrections_dict


class ChangeHeightWindow:

    def __init__(self):

        self.precision = survey_config.precision_value

    @staticmethod
    def get_entered_height(entry_widget):  # e.g. self.new_target_height_entry

        # Check to see if number was entered correctly
        entered_target_height = "ERROR"

        try:
            entered_target_height = round(float(entry_widget.get()), 3)

        except ValueError:

            # Ask user to re-enter a a numerical target height
            tk.messagebox.showerror("INPUT ERROR", "Please enter a valid number to 3 decimal places")

        else:
            print(entered_target_height)

        return entered_target_height


class TargetHeightWindow(ChangeHeightWindow):

    def __init__(self, master):

        super().__init__()

        self.master = master

        self.new_stn_coordinates = OrderedDict()

        # create target height input dialog box
        self.dialog_window = tk.Toplevel(self.master)

        self.lbl = tk.Label(self.dialog_window, text="Enter new target height for this shot:  ")
        self.new_target_height_entry = tk.Entry(self.dialog_window)
        self.btn1 = tk.Button(self.dialog_window, text="UPDATE", command=self.fix_target_height)

        self.lbl.grid(row=0, column=1, padx=(20, 2), pady=20)
        self.new_target_height_entry.grid(row=0, column=2, padx=(2, 2), pady=20)
        self.btn1.grid(row=0, column=3, padx=(10, 20), pady=20)

        self.new_target_height_entry.focus()

        self.master.wait_window(self.dialog_window)

    def fix_target_height(self):

        station_setup_dic = gsi.get_list_of_station_setups(gsi.formatted_lines)
        stn_setup_elevation_updated = set()

        try:
            # set the new target height the user has entered
            new_target_height = self.get_entered_height(self.new_target_height_entry)
            self.dialog_window.destroy()

            if new_target_height != 'ERROR':

                line_numbers_to_ammend = []

                # build list of line numbers to amend
                # selected_items = gui_app.list_box_view.selection()
                selected_items = gui_app.list_box.list_box_view.selection()

                for selected_item in selected_items:
                    line_number = gui_app.list_box.list_box_view.item(selected_item)['values'][0]

                    line_numbers_to_ammend.append(line_number)

                # update each line to amend with new target height and coordinates
                for line_number in line_numbers_to_ammend:
                    point_id = gsi.get_formatted_line(line_number)['Point_ID']
                    corrections = self.get_target_height_corrections(line_number, new_target_height)
                    gsi.update_target_height(line_number, corrections)

                    # update station setup coordinates if this is a shot to a station
                    for stn_gsi_line_number, stn_point_id in station_setup_dic.items():
                        stn_formatted_line_number = stn_gsi_line_number + 1

                        # if shot is to a station and it the station setup elevation hasn't already been updated
                        if point_id == stn_point_id and point_id not in stn_setup_elevation_updated:
                            new_elevation = str(decimalize_value(corrections['83'], self.precision))
                            gsi.update_station_elevation(stn_formatted_line_number, new_elevation)
                            stn_setup_elevation_updated.add(point_id)

                if "TgtUpdated" not in MenuBar.filename_path:

                    amended_filepath = MenuBar.filename_path[:-4] + "_TgtUpdated.gsi"
                else:
                    amended_filepath = MenuBar.filename_path

                # create a new ammended gsi file
                with open(amended_filepath, "w") as gsi_file:
                    for line in gsi.unformatted_lines:
                        gsi_file.write(line)

                # self.dialog_window.destroy()

                # rebuild database and GUI
                MenuBar.filename_path = amended_filepath
                GUIApplication.refresh()
                tk.messagebox.showinfo("Survey Assist", "Target Height Updated")
            else:
                return  # User entered an incorrect target height.  Try again

        except Exception as ex:
            print("Problem fixing target height\n\n" + str(ex))
            logger.exception("An unexpected error has occurred\n\nfix_target_height()\n\n" + str(ex))
            tk.messagebox.showerror("Survey Assist", "An unexpected error has occurred\n\nfix_target_height()\n\n" + str(ex))
            return

    def get_target_height_corrections(self, line_number, new_target_height):

        # update target height and Z coordinate for this line
        formatted_line = gsi.get_formatted_line(line_number)

        new_target_height = float(new_target_height)
        old_tgt_height = formatted_line['Target_Height']

        old_elevation = float(formatted_line['Elevation'])

        if old_tgt_height == '':
            old_tgt_height = 0.000
        elif old_tgt_height == '0':
            old_tgt_height = 0.000
        else:
            old_tgt_height = float(old_tgt_height)

        target_height_difference = new_target_height - old_tgt_height
        new_elevation = old_elevation - target_height_difference

        old_height_difference = float(formatted_line['Height_Diff'])
        new_height_difference = old_height_difference - target_height_difference

        new_height_difference = str(decimalize_value(new_height_difference, '3dp'))
        new_elevation = str(decimalize_value(new_elevation, self.precision))
        new_target_height = str(decimalize_value(new_target_height, '3dp'))

        return {'33': new_height_difference, '83': new_elevation, '87': new_target_height}


class StationHeightWindow(ChangeHeightWindow):

    def __init__(self, master):

        super().__init__()

        self.new_stn_coordinates = OrderedDict()
        self.master = master

        # create station height input dialog box
        self.dialog_window = tk.Toplevel(self.master)

        self.lbl = tk.Label(self.dialog_window, text="Enter new station height for this setup:  ")
        self.new_station_height_entry = tk.Entry(self.dialog_window)
        self.btn1 = tk.Button(self.dialog_window, text="UPDATE", command=self.change_station_height)

        self.lbl.grid(row=0, column=1, padx=(20, 2), pady=20)
        self.new_station_height_entry.grid(row=0, column=2, padx=(2, 2), pady=20)
        self.btn1.grid(row=0, column=3, padx=(10, 20), pady=20)

        self.new_station_height_entry.focus()
        self.master.wait_window(self.dialog_window)

    def change_station_height(self):

        try:
            new_station_height = self.get_entered_height(self.new_station_height_entry)
            self.dialog_window.destroy()

            if new_station_height != 'ERROR':

                # Get user selected line number - should only be one selected line when updating station height
                selected_line = gui_app.list_box.list_box_view.selection()[0]
                stn_line_number = gui_app.list_box.list_box_view.item(selected_line)['values'][0]

                station_formatted_line = gsi.get_formatted_line(stn_line_number)

                station_setup_dic = gsi.get_list_of_station_setups(gsi.formatted_lines)

                # Determine difference in station height from old to new
                old_stn_height = float(station_formatted_line['STN_Height'])
                stn_height_diff = round(new_station_height - old_stn_height, 3)
                new_station_height = str(decimalize_value(new_station_height, 3))

                # get all shots including station
                station_shots_dict = gsi.get_all_shots_from_a_station_including_setup(station_formatted_line['Point_ID'], stn_line_number - 1)

                # update all shots from this station
                for gsi_line_number, formatted_line in station_shots_dict.items():
                    formatted_line_number = gsi_line_number + 1
                    point_id = formatted_line['Point_ID']

                    if gsi.is_station_setup(formatted_line):  # should be a station but double check
                        gsi.update_station_height(formatted_line_number, str(new_station_height))
                    elif gsi.is_orientation_shot(formatted_line):
                        continue
                    else:  # update the elevation and height difference
                        old_point_easting = formatted_line['Easting']
                        old_point_northing = formatted_line['Northing']
                        old_point_elevation = float(formatted_line['Elevation'])
                        new_point_elevation = old_point_elevation + float(stn_height_diff)
                        new_point_elevation = str(decimalize_value(new_point_elevation, self.precision))
                        gsi.update_elevation(formatted_line_number, new_point_elevation)

                        old_height_diff = float(formatted_line['Height_Diff'])
                        height_diff = old_height_diff + float(stn_height_diff)
                        height_diff = str(decimalize_value(height_diff, self.precision))
                        gsi.update_height_diff(formatted_line_number, height_diff)

                        # add stn point_ID coordinates to a stn coordinate list if not already there
                        for gsi_line_number, stn_point_id in station_setup_dic.items():

                            formatted_line_number = gsi_line_number + 1

                            if point_id == stn_point_id:

                                stn_coordinates = self.new_stn_coordinates.get(
                                    formatted_line_number)  # retrieve previous stn coordinates if they exist
                                if stn_coordinates:
                                    continue
                                else:
                                    self.new_stn_coordinates[formatted_line_number] = [float(old_point_easting), float(old_point_northing),
                                                                                       float(new_point_elevation)]

                # Update stations setup coordinates that have been shot from this station
                for formatted_line_number, coordinate_list in self.new_stn_coordinates.items():

                    formatted_line = gsi.get_formatted_line(formatted_line_number)

                    if gsi.is_station_setup(formatted_line):  # should be a station but double check
                        new_elevation = str(decimalize_value(coordinate_list[2], self.precision))
                        gsi.update_station_elevation(formatted_line_number, new_elevation)
                    else:
                        raise Exception("Unexpected error changing station height")

                if "STNUpdated" not in MenuBar.filename_path:

                    amended_filepath = MenuBar.filename_path[:-4] + "_STNUpdated.gsi"
                else:
                    amended_filepath = MenuBar.filename_path

                # create a new ammended gsi file
                with open(amended_filepath, "w") as gsi_file:
                    for line in gsi.unformatted_lines:
                        gsi_file.write(line)

                self.dialog_window.destroy()

                # rebuild database and GUI
                MenuBar.filename_path = amended_filepath
                GUIApplication.refresh()
                tk.messagebox.showinfo("Survey Assist", "Station Height Updated")
            else:
                # User entered an incorrect station height.  Try again
                return
        except Exception as ex:
            print("Problem updating station height\n\n" + str(ex))
            logger.exception("An unexpected error has occurred\n\nupdate_station_height()\n\n" + str(ex))
            tk.messagebox.showerror("Survey Assist", "An unexpected error has occurred\n\nupdate_station_height()\n\n" + str(ex))
            return

    def update_all_shot_elevations_from_station(self, line_number, station, elevation_diff):

        change_coordinates_dict = OrderedDict()

        # get all shots including station
        station_shots_dict = gsi.get_all_shots_from_a_station_including_setup(station, line_number - 1)

        for gsi_line_number, formatted_line in station_shots_dict.items():
            formatted_line_number = gsi_line_number + 1

            if gsi.is_station_setup(formatted_line):  # we dont update the elevation for a station setup
                continue
            else:  # update the elevation
                point_easting = formatted_line['Easting']
                point_northing = formatted_line['Northing']
                old_point_elevation = float(formatted_line['Elevation'])
                new_point_elevation = old_point_elevation + elevation_diff
                new_point_elevation = str(decimalize_value(new_point_elevation, self.precision))
                gsi.update_elevation(formatted_line_number, new_point_elevation)

                # add new coordinates to change dictionary
                change_coordinates_dict[formatted_line_number] = [float(point_easting), float(point_northing), float(new_point_elevation)]

        return change_coordinates_dict


class CompnetUpdateFixedFileWindow:
    coordinate_file_path = ""
    fixed_file_path = ""

    def __init__(self, master):

        self.master = master
        self.outliers_dict = {}

        #  Lets build the dialog box
        self.dialog_window = tk.Toplevel(master)
        self.dialog_window.title("UPDATE FIXED FILE")

        container = tk.Frame(self.dialog_window, width=200, height=120)

        # Update Fixed File GUI
        self.fixed_btn = tk.Button(container, text='(1) Choose Fixed File: ', command=self.get_fixed_file_path)
        self.coord_btn = tk.Button(container, text='(2) Choose Coordinate File: ',
                                   command=self.get_coordinate_file_path)
        self.update_btn = tk.Button(container, text='(3) UPDATE FIXED FILE ', command=self.update_fixed_file)

        self.fixed_btn.grid(row=2, column=1, sticky='nesw', padx=60, pady=(20, 3))
        self.coord_btn.grid(row=3, column=1, sticky='nesw', padx=60, pady=3)
        self.update_btn.grid(row=4, column=1, sticky='nesw', padx=60, pady=(3, 20))

        container.pack(fill="both", expand=True)

        self.dialog_window.geometry(MainWindow.position_popup(master, 240, 180))

    def update_fixed_file(self):

        try:

            # open up fixed file & update the fixed file's easting/northings from the coordinate file
            fixed_file = FixedFile(self.fixed_file_path)
            coordinate_type = self.coordinate_file_path.split(".")[-1].upper()
            coordinate_file = CoordinateFile.getCordinateFile(self.coordinate_file_path, coordinate_type)
            stations_updated = fixed_file.update(coordinate_file)
            stations_not_updated = set(fixed_file.get_stations()).difference(stations_updated)

        except Exception as ex:
            print(ex, type(ex))
            logger.exception("An unexpected error has occurred\n\nupdate_fixed_file()\n\n" + str(ex))
            tk.messagebox.showerror("Error", "Have you selected both files?\n\nIf problem persists, please see "
                                             "Richard.  Check coordinates are MGA56\n\n" + str(ex))

        else:

            msg_body = str(len(stations_updated)) + ' station coordinates have been updated.\n\n'

            if stations_updated:  # display to user

                for station in sorted(stations_updated):
                    msg_body += station + '\n'

            if stations_not_updated:  # display to user

                msg_body += '\nWARNING: The following fixed file stations were not found in the coordintate file:\n\n'

                for station in sorted(stations_not_updated):
                    msg_body += station + '\n'

            tkinter.messagebox.showinfo("Update Fixed File", msg_body)

            self.dialog_window.destroy()

    def get_fixed_file_path(self):

        self.fixed_file_path = tk.filedialog.askopenfilename(parent=self.master, initialdir=gui_app.menu_bar.compnet_working_dir,
                                                             title="Please select a compnet fixed file", filetypes=[("FIX Files", ".FIX")])
        if self.fixed_file_path != "":
            self.fixed_btn.config(text=os.path.basename(self.fixed_file_path))
            gui_app.menu_bar.compnet_working_dir = self.fixed_file_path
        self.dialog_window.lift()  # bring window to the front again

    def get_coordinate_file_path(self):
        self.coordinate_file_path = tk.filedialog.askopenfilename(parent=self.master, initialdir=survey_config.todays_dated_directory,
                                                                  title="Please select a coordinate file", filetypes=[("Coordinate Files",
                                                                                                                       ".asc .CRD .STD")])
        if self.coordinate_file_path != "":
            self.coord_btn.config(text=os.path.basename(self.coordinate_file_path))
        self.dialog_window.lift()  # bring window to the front again


class CompnetWeightSTDFileWindow:

    def __init__(self, master):
        self.master = master

        self.compnet_working_directory = gui_app.menu_bar.compnet_working_dir
        self.std_file_path = ""

        #  Lets build the dialog box
        self.dialog_window = tk.Toplevel(master)
        self.dialog_window.title("WEIGHT STD FILE")

        container = tk.Frame(self.dialog_window, width=200, height=120)

        self.defualt_weight_sve = tk.StringVar(container, value='0.01')
        self.defualt_weight_svn = tk.StringVar(container, value='0.01')
        self.defualt_weight_svel = tk.StringVar(container, value='0.01')

        self.choose_btn = tk.Button(container, text="(1) Choose STD (weighted) File", command=self.get_STD_file_path)
        self.set_weighting_lbl = tk.Label(container, text="(2) Set Weighting:")
        self.entry_east = tk.Entry(container, width=5, textvariable=self.defualt_weight_sve)
        self.entry_east_lbl = tk.Label(container, text="Easting")
        self.entry_north = tk.Entry(container, width=5, textvariable=self.defualt_weight_svn)
        self.entry_north_lbl = tk.Label(container, text="Northing")
        self.entry_elevation = tk.Entry(container, width=5, textvariable=self.defualt_weight_svel)
        self.entry_elevation_lbl = tk.Label(container, text="Elevation")
        self.update_btn = tk.Button(container, text="(3) UPDATE", command=self.update_STD_file, anchor='w')

        self.choose_btn.grid(row=1, column=1, columnspan=3, sticky='nesw', padx=40, pady=(20, 3))
        self.set_weighting_lbl.grid(row=2, column=1, columnspan=3, sticky='nsw', padx=40, pady=(10, 3))
        self.entry_east.grid(row=3, column=1, sticky='nesw', padx=(60, 2), pady=3)
        self.entry_east_lbl.grid(row=3, column=2, sticky='nesw', padx=(2, 40), pady=3)
        self.entry_north.grid(row=4, column=1, sticky='nesw', padx=(60, 2), pady=3)
        self.entry_north_lbl.grid(row=4, column=2, sticky='nesw', padx=(2, 40), pady=3)
        self.entry_elevation.grid(row=5, column=1, sticky='nesw', padx=(60, 2), pady=3)
        self.entry_elevation_lbl.grid(row=5, column=2, sticky='nesw', padx=(2, 40), pady=3)
        self.update_btn.grid(row=6, column=1, columnspan=3, sticky='nesw', padx=40, pady=(10, 3))

        container.pack(fill="both", expand=True)

        self.dialog_window.geometry(MainWindow.position_popup(master, 260,
                                                              220))

    def get_STD_file_path(self):

        self.std_file_path = tk.filedialog.askopenfilename(parent=self.master, initialdir=gui_app.menu_bar.compnet_working_dir,
                                                           title="Select file", filetypes=[("STD Files", ".STD")])
        if self.std_file_path != "":
            self.choose_btn.config(text=os.path.basename(self.std_file_path))

            gui_app.menu_bar.compnet_working_dir = os.path.dirname(self.std_file_path)

        self.dialog_window.lift()  # bring window to the front again

    def update_STD_file(self):
        try:
            if self.std_file_path != "":
                updated_std_contents = []
                weight_dict = {}

                # build the weighted dictionary
                weight_dict['Easting'] = self.entry_east.get()
                weight_dict['Northing'] = self.entry_north.get()
                weight_dict['Elevation'] = self.entry_elevation.get()

                std_file = STDCoordinateFile(self.std_file_path)

                try:
                    updated_std_contents = std_file.update_weighting(weight_dict)
                except InvalidOperation:
                    tkinter.messagebox.showinfo("Update STD File", "Please double check all weightings are a number")
                    self.dialog_window.lift()
                else:
                    # write out file
                    with open(self.std_file_path, "w") as std_file:
                        for line in updated_std_contents:
                            std_file.write(line)
                    tkinter.messagebox.showinfo("Update STD File", "STD file has been updated")
                    self.dialog_window.destroy()
            else:
                # user hasn't choosen a file
                tkinter.messagebox.showinfo("Update STD File", "Please choose an STD file")
                self.dialog_window.lift()

        except Exception as ex:
            print("Problem opening up the GSI file\n\n" + str(ex))
            logger.exception("An unexpected error has occurred\n\nupdate_STD_file()\n\n" + str(ex))
            tk.messagebox.showerror("Survey Assist", "An unexpected error has occurred\n\nupdate_STD_file()\n\n" + str(ex))
            return


class CompnetCompareCRDFWindow:
    crd_file_path_1 = ""
    crd_file_path_2 = ""

    def __init__(self, master):

        self.master = master
        self.outliers_dict = {}

        #  Lets build the dialog box
        self.dialog_window = tk.Toplevel(master)
        self.dialog_window.title("Compnet Assist")
        # self.dialog_window.geometry(self.center_screen())
        # self.dialog_window.attributes("-topmost", True)

        # Compare CRD Files GUI
        self.compare_crd_files_lbl = tk.Label(self.dialog_window, text='\nCOMPARE CRD FILES\n', font=('Helvetica',
                                                                                                      14, 'bold'))
        self.tolE_lbl = tk.Label(self.dialog_window, text='Tolerance E: ')
        self.entry_tolE = tk.Entry(self.dialog_window)
        self.entry_tolE.insert(tk.END, '0.001')

        self.tolN_lbl = tk.Label(self.dialog_window, text='Tolerance N: ')
        self.entry_tolN = tk.Entry(self.dialog_window)
        self.entry_tolN.insert(tk.END, '0.001')

        self.tolH_lbl = tk.Label(self.dialog_window, text='Tolerance H: ')
        self.entry_tolH = tk.Entry(self.dialog_window)
        self.entry_tolH.insert(tk.END, '0.001')

        self.crd_file_1_btn = tk.Button(self.dialog_window, text='(1) Choose CRD File 1: ',
                                        command=lambda: self.get_crd_file_path(1))
        self.crd_file_2_btn = tk.Button(self.dialog_window, text='(2) Choose CRD File 2: ',
                                        command=lambda: self.get_crd_file_path(2))

        self.compare_crd_btn = tk.Button(self.dialog_window, text='(3) COMPARE FILES ', state=tk.DISABLED,
                                         command=self.compare_crd_files_outliers)
        # self.compare_result_lbl = tk.Label(self.dialog_window, text=' ')

        self.compare_crd_files_lbl.grid(row=0, column=1, columnspan=2, padx=50, pady=2)
        self.tolE_lbl.grid(row=1, column=1, sticky='nesw', padx=(25, 5), pady=3)
        self.entry_tolE.grid(row=1, column=2, sticky='nesw', padx=(5, 25), pady=2)
        self.tolN_lbl.grid(row=2, column=1, sticky='nesw', padx=(25, 5), pady=3)
        self.entry_tolN.grid(row=2, column=2, sticky='nesw', padx=(5, 25), pady=3)
        self.tolH_lbl.grid(row=3, column=1, sticky='nesw', padx=(25, 5), pady=3)
        self.entry_tolH.grid(row=3, column=2, sticky='nesw', padx=(5, 25), pady=3)

        self.crd_file_1_btn.grid(row=5, column=1, columnspan=2, sticky='nesw', padx=25, pady=(25, 3))
        self.crd_file_2_btn.grid(row=6, column=1, columnspan=2, sticky='nesw', padx=25, pady=3)
        self.compare_crd_btn.grid(row=7, column=1, columnspan=2, sticky='nesw', padx=25, pady=(3, 25))
        # self.compare_result_lbl.grid(row=8, column=1, columnspan=2, sticky='nesw', padx=25, pady=15)

        self.dialog_window.geometry(MainWindow.position_popup(master, 310,
                                                              300))

    def compare_crd_files_outliers(self):

        self.outliers_dict = {}

        # Tolerances - let user decide in GUI???

        tol_E = float(self.entry_tolE.get())
        tol_N = float(self.entry_tolN.get())
        tol_H = float(self.entry_tolH.get())

        print(tol_E, tol_N, tol_H)

        common_points = []
        uncommon_points = []

        try:

            # open up the two CRD files and compare common values for outliers
            coordinate_file1 = CRDCoordinateFile(self.crd_file_path_1)
            coordinate_file2 = CRDCoordinateFile(self.crd_file_path_2)

            # find common points between files
            for key in coordinate_file1.coordinate_dictionary.keys():
                if key in coordinate_file2.coordinate_dictionary:
                    common_points.append(key)
                else:
                    uncommon_points.append(key)

            # Lets check for outliers for common points

            for point in common_points:
                cf1_E = float(coordinate_file1.coordinate_dictionary[point]['Eastings'])
                cf1_N = float(coordinate_file1.coordinate_dictionary[point]['Northings'])
                cf2_E = float(coordinate_file2.coordinate_dictionary[point]['Eastings'])
                cf2_N = float(coordinate_file2.coordinate_dictionary[point]['Northings'])

                diff_E = cf1_E - cf2_E
                diff_N = cf1_N - cf2_N
                if abs(diff_E) > tol_E:
                    self.outliers_dict[point + ' - Easting'] = '{0:.3f}'.format(round(diff_E, 3))
                if abs(diff_N) > tol_N:
                    self.outliers_dict[point + ' - Northing'] = '{0:.3f}'.format(round(diff_N, 3))

                try:
                    # check and see if elevation data exists
                    cf1_H = float(coordinate_file1.coordinate_dictionary[point]['Elevation'])
                    cf2_H = float(coordinate_file2.coordinate_dictionary[point]['Elevation'])
                    diff_H = cf1_H - cf2_H

                    if abs(diff_H) > tol_H:
                        self.outliers_dict[point + ' - Elevation'] = '{0:.3f}'.format(round(diff_H, 3))
                except (ValueError, KeyError) as ex:
                    # elevation probably doesnt exist in this coordinate file
                    print(ex)
                    pass

        except Exception as ex:
            print(ex, type(ex))
            # self.compare_result_lbl.config(text='ERROR - See Richard\n')
            tk.messagebox.showerror("Error", ex + '\n\n Please see RIchard if problem persists')

        else:

            msg_body = 'Points that exceed tolerance are:\n\n'

            if self.outliers_dict:
                for point in sorted(self.outliers_dict, key=lambda k: k):
                    msg_body += point + ': ' + self.outliers_dict[point] + '\n'
            else:  # no outliers
                msg_body = " \nThere are no points that exceed the specified tolerance\n"

            # Display to the user points that are uncommon
            if uncommon_points:

                msg = '\n\nThe following points were not found in the 2nd file:\n\n'
                for point in uncommon_points:
                    msg += point + '\n'

                msg_body += msg

            top = tk.Toplevel()
            top.title("COMPARE CRD's")
            # top.geometry('400x600')

            msg = tk.Message(top, text=msg_body)
            msg.grid(row=1, column=1, padx=50, pady=10)

    def get_crd_file_path(self, file_path_number):

        parent_dated_directory = Path(survey_config.todays_dated_directory).parent

        if file_path_number == 1:
            self.crd_file_path_1 = tk.filedialog.askopenfilename(parent=self.master, initialdir=survey_config.todays_dated_directory,
                                                                 title="Select CRD file",
                                                                 filetypes=[("CRD Files", ".CRD")])

            if self.crd_file_path_1 != "":
                self.crd_file_1_btn.config(text=os.path.basename(self.crd_file_path_1))
            self.dialog_window.lift()  # bring window to the front again

        elif file_path_number == 2:
            self.crd_file_path_2 = tk.filedialog.askopenfilename(parent=self.master, initialdir=parent_dated_directory, title="Select CRD file",
                                                                 filetypes=[("CRD Files", ".CRD")])

            if self.crd_file_path_2 != "":
                self.crd_file_2_btn.config(text=os.path.basename(self.crd_file_path_2))
            self.dialog_window.lift()  # bring window to the front again
        else:
            tk.messagebox.showerror("Error", "No filepath no exists: " + str(file_path_number))

        if all([self.crd_file_path_1 != "", self.crd_file_path_2 != ""]):
            # enablebutton
            self.compare_crd_btn.configure(state=tk.NORMAL)


class CompnetCreateControlOnlyGSI:

    def __init__(self):

        self.outliers_dict = {}
        self.strip_non_control_shots()

    def strip_non_control_shots(self):

        # let user choose GSI file
        gsi_file_path = tk.filedialog.askopenfilename(initialdir=survey_config.compnet_raw_dir,
                                                      title="Select GSI file", filetypes=[("GSI Files", ".GSI")])

        try:
            # create a new stripped GSI
            old_gsi = GSI(logger, survey_config)
            old_gsi.format_gsi(gsi_file_path)
            control_only_filename = old_gsi.create_control_only_gsi()

            # Update GUI
            MenuBar.filename_path = control_only_filename
            GUIApplication.refresh()
            gui_app.menu_bar.enable_menus()

        except FileNotFoundError as ex:

            # most likely no file choosen or incorrect GSI
            print(ex, type(ex))

            tk.messagebox.showerror("ERROR", 'No GSI FIle Selected.  Please open a GSI file first')

            gui_app.status_bar.status['text'] = 'Please choose a GSI File'

        except Exception as ex:
            print("Problem opening up the GSI file\n\n" + str(ex))
            logger.exception("An unexpected error has occurred\n\nstrip_non_control_shots()\n\n" + str(ex))
            tk.messagebox.showerror("Survey Assist", "An unexpected error has occurred\n\nstrip_non_control_shots()\n\n" + str(ex))
            return


class CombineGSIFilesWindow:

    def __init__(self, master):

        self.master = master

        self.gsi_contents = ""
        self.sorted_station_list_filepath = ""
        self.combined_gsi_file_path = ""

        #  Lets build the dialog box

        self.dialog_window = tk.Toplevel(master)
        self.dialog_window.title("Combine and reorder GSI files")

        self.sorting_lbl = tk.Label(self.dialog_window, text="1)  SORTING OPTIONS:")

        self.radio_option = tk.StringVar()
        self.radio_option.set("1")
        self.radio_no_sort = tk.Radiobutton(self.dialog_window, text="Don't Sort", value="1",
                                            var=self.radio_option, command=self.disable_config_button)
        self.radio_sort_auto = tk.Radiobutton(self.dialog_window, text="Sort alphabetically", value="2",
                                              var=self.radio_option, command=self.disable_config_button)
        self.radio_sort_config = tk.Radiobutton(self.dialog_window, text="Sort based on config file", value="3",
                                                var=self.radio_option, command=self.enable_config_button)
        self.sorted_file_btn = tk.Button(self.dialog_window, text='CHANGE SORTING CONFIG FILE', state="disabled", command=self.open_config_file)
        current_config_label_txt = os.path.basename(survey_config.sorted_station_config)
        self.current_config_label = tk.Label(self.dialog_window, text=current_config_label_txt, state="disabled")
        self.files_btn = tk.Button(self.dialog_window, text="2)  CHOOSE GSI'S AND COMBINE       ",
                                   command=self.select_and_combine_gsi_files)

        self.sorting_lbl.grid(row=0, column=1, sticky='w', columnspan=3, padx=60, pady=(20, 2))
        self.radio_no_sort.grid(row=1, column=1, sticky='w', columnspan=3, padx=70, pady=2)
        self.radio_sort_auto.grid(row=2, column=1, sticky='w', columnspan=3, padx=70, pady=2)
        self.radio_sort_config.grid(row=3, column=1, sticky='w', columnspan=3, padx=70, pady=(2, 1))
        self.sorted_file_btn.grid(row=4, column=1, sticky='w', columnspan=3, padx=70, pady=(2, 2))
        self.current_config_label.grid(row=5, column=1, sticky='w', columnspan=3, padx=70, pady=(1, 2))
        self.files_btn.grid(row=6, column=1, sticky='w', columnspan=3, padx=60, pady=(20, 20))

        self.dialog_window.geometry(MainWindow.position_popup(master, 320, 280))

        # self.dialog_window.attributes('-topmost', 'true')

    def enable_config_button(self):

        # enable button and label
        self.sorted_file_btn.config(state="normal")
        self.current_config_label.config(state="normal")

    def disable_config_button(self):

        # enable button and label
        self.sorted_file_btn.config(state="disabled")
        self.current_config_label.config(state="disabled")

    def open_config_file(self):

        self.sorted_station_list_filepath = tk.filedialog.askopenfilename(parent=self.master,
                                                                          title="Please select the sorted station configuration file",
                                                                          filetypes=[("TXT Files", ".txt")])
        if self.sorted_station_list_filepath != "":
            survey_config.update(SurveyConfiguration.section_config_files, 'sorted_station_config', self.sorted_station_list_filepath)
            survey_config.sorted_station_config = self.sorted_station_list_filepath
            self.current_config_label.config(text=os.path.basename(self.sorted_station_list_filepath))

        self.dialog_window.lift()  # bring window to the front again

    def select_and_combine_gsi_files(self):

        # determine sorting method
        radio_button_selection = self.radio_option.get()
        current_date = datetime.date.today().strftime('%d%m%y')
        # combined_gsi_filename_suffix = '_' + current_date + "_COMBINED.gsi"
        combined_gsi_filename_suffix = "_COMBINED.gsi"

        # prompt if user choose to sort by config and the sorted station configuration file if it doesn't exist
        if radio_button_selection == "3":

            if not os.path.exists(survey_config.sorted_station_config):
                tk.messagebox.showerror("Combining GSI Files", "Can't find the station configuration file.\n\n"
                                                               "Please select one and then select GSI files to combine")
                self.open_config_file()

        try:
            gsi_filenames = list(
                tk.filedialog.askopenfilenames(parent=self.master, initialdir=survey_config.todays_dated_directory, title="Please select GSI files "
                                                                                                                          "to combine",
                                               filetypes=[("GSI Files", ".gsi")]))
            if gsi_filenames:

                first_gsi_basename = gsi_filenames[0][:-4]  # remove the .GSI
                self.combined_gsi_file_path = first_gsi_basename + combined_gsi_filename_suffix

                for filename in gsi_filenames:
                    gsi_file = GSIFileContents(filename)
                    self.gsi_contents += gsi_file.get_filecontents()

                self.write_out_combined_gsi(self.gsi_contents, self.combined_gsi_file_path)

                # no sorting
                if radio_button_selection == "1":
                    # file is already written out as it is used for options 2 and 3
                    pass
                elif radio_button_selection == "2":
                    sorted_filecontents = self.sort_alphabetically()
                    self.write_out_combined_gsi(sorted_filecontents, self.combined_gsi_file_path)
                elif radio_button_selection == "3":
                    sorted_filecontents = self.sort_by_config()
                    self.write_out_combined_gsi(sorted_filecontents, self.combined_gsi_file_path)
                else:
                    tk.messagebox.showerror("Error", "no radio button option choosed")

        except Exception as ex:

            print(ex)
            logger.exception("An unexpected error has occurred\n\nselect_and_combine_gsi_files()\n\n" + str(ex))
            tk.messagebox.showerror("Error", "Error combining files.\n\n" + str(ex))

        else:

            if gsi_filenames:
                tk.messagebox.showinfo("Success", "The gsi files have been combined:\n\n" + self.combined_gsi_file_path)
                # display results to the user
                MenuBar.filename_path = self.combined_gsi_file_path
                GUIApplication.refresh()
                gui_app.menu_bar.enable_menus()



            else:
                pass
        finally:
            # close window
            self.dialog_window.destroy()

    def sort_alphabetically(self):

        sorted_filecontents = ""

        # create a temporary gsi

        unsorted_combined_gsi = GSI(logger, survey_config)
        unsorted_combined_gsi.format_gsi(self.combined_gsi_file_path)

        # lets check and provide a warning to the user if duplicate stations are detected
        stations_names_dict = unsorted_combined_gsi.get_list_of_station_setups(unsorted_combined_gsi.formatted_lines)
        station_set = unsorted_combined_gsi.get_set_of_station_setups()
        if len(stations_names_dict) != len(station_set):
            tk.messagebox.showwarning("WARNING", 'Warning - Duplicate station names detected!')

        # need to sort this by station name
        stations_sorted_by_name = OrderedDict(sorted(stations_names_dict.items(), key=lambda x: x[1]))

        # create a temporary unsorted and unformatted gsi file to work with
        with open(self.combined_gsi_file_path, 'r') as f_temp_combined_gsi:
            unsorted_combined_gsi_txt = f_temp_combined_gsi.readlines()

        # create the sorted filecontents to write out
        for line_number, station_name in stations_sorted_by_name.items():

            line_numbers = unsorted_combined_gsi.get_all_shots_from_a_station_including_setup(station_name, line_number)

            for line in sorted(line_numbers):
                text_line = unsorted_combined_gsi_txt[line]

                # test if text line has no '\' at start then add one
                if not text_line.endswith('\n'):
                    text_line += '\n'

                sorted_filecontents += text_line

        return sorted_filecontents

    def sort_by_config(self):

        sorted_filecontents = ""
        config_station_list = []
        stations_not_found_from_config_list = []

        # create a temporary gsi
        unsorted_combined_gsi = GSI(logger, survey_config)
        unsorted_combined_gsi.format_gsi(self.combined_gsi_file_path)

        # lets check and provide a error to the user if station names in combine GSI contain a duplicate
        stations_names_dict = unsorted_combined_gsi.get_list_of_station_setups(unsorted_combined_gsi.formatted_lines)
        station_set = unsorted_combined_gsi.get_set_of_station_setups()

        if len(stations_names_dict) != len(station_set):
            tk.messagebox.showwarning("WARNING", 'Warning - Duplicate station names detected in the combined gsi!')

        # need to sort this by station name
        stations_sorted_by_name_dict = OrderedDict(sorted(stations_names_dict.items(), key=lambda x: x[1]))
        stations_sorted_by_name = stations_sorted_by_name_dict.values()

        # create a temporary unsorted and unformatted gsi file to work with
        with open(self.combined_gsi_file_path, 'r') as f_temp_combined_gsi:
            unsorted_combined_gsi_txt = f_temp_combined_gsi.readlines()

        # open up file and read in lines.  store each line removing any whitespace as station. Ignore blanks lines '\n'
        with open(survey_config.sorted_station_config, 'r') as f_config_station_list:
            for line in f_config_station_list:
                config_station_list.append(line.rstrip())

        # check that station is in the unordered combined gsi
        for config_station in config_station_list:

            if config_station in stations_sorted_by_name:

                # create new dic so that that stations sorted by name so key is station and not line number
                line_key_stations_sorted_by_name_dict = dict(map(reversed, stations_sorted_by_name_dict.items()))
                line_number = line_key_stations_sorted_by_name_dict[config_station]
                station_name = config_station

                # create the sorted filecontents to write out
                line_numbers = unsorted_combined_gsi.get_all_shots_from_a_station_including_setup(station_name,
                                                                                                  line_number)

                for line in sorted(line_numbers):
                    text_line = unsorted_combined_gsi_txt[line]

                    # test if text line has no '\' at start then add one
                    if not text_line.endswith('\n'):
                        text_line += '\n'

                    sorted_filecontents += text_line

                # remove station from stations_sorted by name so that only the remaining ones not found are added
                del stations_sorted_by_name_dict[line_number]

            else:

                stations_not_found_from_config_list.append(config_station)

        print(stations_not_found_from_config_list)

        # add stations not found to the end of the contents file
        for line_number, station_name in stations_sorted_by_name_dict.items():

            line_numbers = unsorted_combined_gsi.get_all_shots_from_a_station_including_setup(station_name,
                                                                                              line_number)

            for line in sorted(line_numbers):
                text_line = unsorted_combined_gsi_txt[line]

                # test if text line has no '\' at start then add one
                if not text_line.endswith('\n'):
                    text_line += '\n'

                sorted_filecontents += text_line

        return sorted_filecontents

    def write_out_combined_gsi(self, gsi_contents, file_path):

        with open(file_path, 'w') as f_update:
            f_update.write(gsi_contents)


#  Job Diary and its dependencies was written by Chris Kelly
class JobDiaryWindow:

    def __init__(self, parent):

        self.master = parent

        self.type_path = os.path.join(survey_config.root_job_directory, survey_config.current_year)
        self.job_path = os.path.join(survey_config.root_job_directory, survey_config.current_year, survey_config.default_survey_type)

        self.types = sorted([f for f in os.listdir(self.type_path) if os.path.isdir(os.path.join(self.type_path, f))])
        self.jobs = sorted([f for f in os.listdir(self.job_path) if os.path.isdir(os.path.join(self.job_path, f))])

        self.job_type = tk.StringVar()
        self.job_name = tk.StringVar()
        self.job_date = tk.StringVar()
        self.job_description = tk.StringVar()
        self.ID = tk.StringVar()

        self.active_date = []

        self.TS15 = tk.IntVar()
        self.TS60 = tk.IntVar()
        self.MS60 = tk.IntVar()
        self.TDA = tk.IntVar()
        self.other_instrument = tk.IntVar()

        self.RTK = tk.IntVar()
        self.static = tk.IntVar()

        self.manual = tk.IntVar()
        self.photos = tk.IntVar()

        self.menu_bar = tk.Menu(self.master)

        self.menu_bar.add_command(label='New Record', command=self.new_record)
        self.menu_bar.add_command(label='Edit Record', command=self.edit_record)
        self.menu_bar.add_command(label='Save Record', command=self.save_record)
        self.menu_bar.add_command(label='Delete Record', command=self.delete_record)
        self.menu_bar.add_command(label='Exit', command=self.master.destroy)

        self.master.config(menu=self.menu_bar)

        self.top_frame = tk.Frame(self.master)
        self.top_frame.pack(side=tk.TOP, fill=tk.X)

        self.ID_label = tk.Label(self.top_frame, width=10, textvariable=self.ID)
        self.ID_label.pack(side=tk.LEFT)
        self.ID.set('--')

        self.job_type_box = ttk.Combobox(self.top_frame, textvariable=self.job_type, width=25)
        self.job_type_box.pack(side=tk.LEFT)
        self.job_type_box.bind('<<ComboboxSelected>>', self.refresh_jobs)

        self.job_name_box = ttk.Combobox(self.top_frame, textvariable=self.job_name, width=25)
        self.job_name_box.pack(side=tk.LEFT)

        self.job_date_btn = ttk.Button(self.top_frame, textvariable=self.job_date, comman=self.open_calender)
        self.job_date_btn.pack(side=tk.LEFT)
        self.job_date.set(datetime.datetime.now().strftime('%d/%m/%Y'))
        self.active_date.append(datetime.datetime.now().strftime('%d/%m/%Y'))

        self.chk_RTK = tk.Checkbutton(self.top_frame, text='RTK', variable=self.RTK)
        self.chk_static = tk.Checkbutton(self.top_frame, text='STATIC', variable=self.static)

        self.chk_TS15 = tk.Checkbutton(self.top_frame, text='TS 15', variable=self.TS15)
        self.chk_TS60 = tk.Checkbutton(self.top_frame, text='TS 60', variable=self.TS60)
        self.chk_MS60 = tk.Checkbutton(self.top_frame, text='MS 60', variable=self.MS60)
        self.chk_TDA = tk.Checkbutton(self.top_frame, text='TDA', variable=self.TDA)

        self.chk_other = tk.Checkbutton(self.top_frame, text='OTHER', variable=self.other_instrument)
        self.chk_manual = tk.Checkbutton(self.top_frame, text='MANUAL', variable=self.manual)
        self.chk_photos = tk.Checkbutton(self.top_frame, text='PHOTOS', variable=self.photos)

        self.chk_static.pack(side=tk.LEFT)
        self.chk_RTK.pack(side=tk.LEFT)
        self.chk_TS15.pack(side=tk.LEFT)
        self.chk_TS60.pack(side=tk.LEFT)
        self.chk_MS60.pack(side=tk.LEFT)
        self.chk_TDA.pack(side=tk.LEFT)
        self.chk_other.pack(side=tk.LEFT)
        self.chk_manual.pack(side=tk.LEFT)
        self.chk_photos.pack(side=tk.LEFT)

        self.EntryFrame = tk.Frame(self.master)
        self.EntryFrame.pack(side=tk.TOP, fill=tk.X)

        ent_lbl = tk.Label(self.EntryFrame, text='Job Description...', width=25)
        ent_lbl.pack(side=tk.LEFT)

        self.Entry = tk.Entry(self.EntryFrame, textvariable=self.job_description)
        self.Entry.pack(side=tk.TOP, fill=tk.X)

        self.bottom_frame = tk.Frame(self.master)
        self.bottom_frame.pack(side=tk.TOP, fill=tk.Y, expand=True)

        self.diary_entries = ttk.Treeview(self.bottom_frame,
                                          columns=('ID', 'Date', 'Job Name', 'Description', 'Job Type'),
                                          displaycolumns=('Date', 'Job Name', 'Description', 'Job Type'),
                                          selectmode='browse')
        self.diary_entries.heading('ID', text='ID')
        self.diary_entries.heading('Date', text='Date')
        self.diary_entries.heading('Job Name', text='Job Name')
        self.diary_entries.heading('Description', text='Description')
        self.diary_entries.heading('Job Type', text='Job Type')
        self.diary_entries.pack(side=tk.LEFT, expand=True, fill='both')

        self.yscrollbar = ttk.Scrollbar(self.bottom_frame, orient='vertical', command=self.diary_entries.yview)
        self.diary_entries.configure(yscrollcommand=self.yscrollbar.set)
        self.yscrollbar.pack(side=tk.LEFT, expand=True, fill='both', anchor='w')
        self.yscrollbar.configure(command=self.diary_entries.yview)

        self.diary_entries.bind("<<TreeviewSelect>>", self.activate_record)

        self.master.geometry(MainWindow.position_popup(self.master, 1100, 700))

        self.backup_diary()

        self.read_diary()
        self.populate_diary()
        self.populate_type()
        self.populate_jobs()

        self.disable_checks()

        self.new_or_edited = 'Edited'

    def backup_diary(self):

        diary_backup = survey_config.diary_backup
        diary_directory = survey_config.diary_directory

        if os.path.exists(diary_backup) == False:
            os.mkdir(diary_backup)
        date_string = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        save_name = os.path.join(diary_backup,
                                 os.path.basename(diary_directory).split('.')[0] + '_' + date_string + '.csv')
        print(save_name)
        shutil.copyfile(diary_directory, save_name)

    def read_diary(self):
        with open(survey_config.diary_directory) as csvfile:
            reader = csv.DictReader(csvfile)
            keys = reader.fieldnames
            r = csv.reader(csvfile)
            self.diary_data = ([OrderedDict(zip(keys, row)) for row in r])

        for i, item in enumerate(self.diary_data):
            item['RECID'] = i

    def populate_diary(self):
        self.diary_entries.delete(*self.diary_entries.get_children())
        for item in self.diary_data:
            try:
                self.diary_entries.insert('', 'end', iid=item['RECID'], text=item['RECID'], values=list(item.values()))
            except:
                pass

    def refresh_jobs(self, event):
        path = os.path.join(survey_config.root_job_directory, survey_config.current_year, self.job_type.get())
        self.jobs = sorted([f for f in os.listdir(path) if os.path.isdir(os.path.join(path, f))])
        self.populate_jobs()

    def populate_type(self):
        self.job_type_box['values'] = self.types
        self.job_type_box.current(0)
        if self.job_type.get() in self.job_type_box['values']:
            self.job_type_box.set(self.job_type.get())

    def populate_jobs(self):
        self.job_name_box['values'] = self.jobs
        try:
            self.job_name_box.current(0)
            if self.job_name.get() in self.job_name_box['values']:
                self.job_name_box.set(self.job_name.get())
        except:
            pass

    def open_calender(self):
        cal_root = tk.Toplevel()
        Cal = CalendarWindow(cal_root, self.active_date, format='%d/%m/%Y')
        self.master.wait_window(cal_root)
        self.job_date.set(self.active_date[0])

    def activate_record(self, event):
        selected_record = self.diary_entries.item(self.diary_entries.focus())['values']

        self.clear_records()

        self.ID.set(selected_record[0])
        self.job_date.set(selected_record[1])
        self.job_description.set(selected_record[3])

        if selected_record[2] in self.job_name_box['values']:
            self.job_name_box.set(selected_record[2])
        else:
            self.job_name_box.set('')

        if selected_record[4] in self.job_type_box['values']:
            self.job_type_box.set(selected_record[4])
        else:
            self.job_type_box.set('')

        if selected_record[5] == 1: self.chk_static.select()
        if selected_record[6] == 1: self.chk_RTK.select()
        if selected_record[7] == 1: self.chk_TS15.select()
        if selected_record[8] == 1: self.chk_TS60.select()
        if selected_record[9] == 1: self.chk_MS60.select()
        if selected_record[10] == 1: self.chk_TDA.select()
        if selected_record[11] == 1: self.chk_other.select()
        if selected_record[12] == 1: self.chk_manual.select()
        if selected_record[13] == 1: self.chk_photos.select()

        self.disable_checks()

    def disable_checks(self):

        self.job_name_box.configure(state=tk.DISABLED)
        self.job_type_box.configure(state=tk.DISABLED)
        self.Entry.configure(state=tk.DISABLED)
        self.job_date_btn.configure(state=tk.DISABLED)

        self.chk_TS15.configure(state=tk.DISABLED)
        self.chk_TS60.configure(state=tk.DISABLED)
        self.chk_MS60.configure(state=tk.DISABLED)
        self.chk_TDA.configure(state=tk.DISABLED)

        self.chk_RTK.configure(state=tk.DISABLED)
        self.chk_static.configure(state=tk.DISABLED)
        self.chk_manual.configure(state=tk.DISABLED)
        self.chk_photos.configure(state=tk.DISABLED)
        self.chk_other.configure(state=tk.DISABLED)

    def enable_checks(self):

        self.job_name_box.configure(state=tk.NORMAL)
        self.job_type_box.configure(state=tk.NORMAL)
        self.Entry.configure(state=tk.NORMAL)
        self.job_date_btn.configure(state=tk.NORMAL)

        self.chk_TS15.configure(state=tk.NORMAL)
        self.chk_TS60.configure(state=tk.NORMAL)
        self.chk_MS60.configure(state=tk.NORMAL)
        self.chk_TDA.configure(state=tk.NORMAL)

        self.chk_RTK.configure(state=tk.NORMAL)
        self.chk_static.configure(state=tk.NORMAL)
        self.chk_manual.configure(state=tk.NORMAL)
        self.chk_photos.configure(state=tk.NORMAL)
        self.chk_other.configure(state=tk.NORMAL)

    def clear_records(self):

        self.job_date.set('')
        self.job_description.set('')
        self.job_name_box.set('')
        self.job_type_box.set('')

        self.chk_TS15.deselect()
        self.chk_TS60.deselect()
        self.chk_MS60.deselect()
        self.chk_TDA.deselect()

        self.chk_RTK.deselect()
        self.chk_static.deselect()
        self.chk_manual.deselect()
        self.chk_photos.deselect()
        self.chk_other.deselect()

        self.enable_checks()

    def edit_record(self):
        self.new_or_edited = 'Edited'
        self.enable_checks()

    def new_record(self):
        self.clear_records()
        self.job_date.set(datetime.datetime.today().strftime('%d/%m/%Y'))
        if len(self.diary_data) < 1:
            id = 1
        else:
            id = max([int(i['RECID']) for i in self.diary_data]) + 1
        self.ID.set(str(id))
        self.new_or_edited = 'New'

    def save_record(self):

        if self.new_or_edited == 'New':
            self.diary_data.append(OrderedDict((('RECID', int(self.ID.get())), ('Date', self.job_date.get()),
                                                ('Job', self.job_name.get()),
                                                ('Description', self.job_description.get()),
                                                ('Job Type', self.job_type.get()),
                                                ('Static', self.static.get()), ('RTK', self.RTK.get()),
                                                ('TCRA A', self.TS15.get()),
                                                ('TCRA B', self.TS60.get()), ('TCRA JH', self.MS60.get()),
                                                ('TDA', self.TDA.get()), ('Other', self.other_instrument.get()),
                                                ('Manual', self.manual.get()),
                                                ('Photos', self.photos.get()))))

        elif self.new_or_edited == 'Edited':
            for i, Item in enumerate(self.diary_data):
                if Item['RECID'] == int(self.ID.get()):
                    self.diary_data[i] = OrderedDict((('RECID', self.ID.get()), ('Date', self.job_date.get()),
                                                      ('Job', self.job_name.get()),
                                                      ('Description', self.job_description.get()),
                                                      ('Job Type', self.job_type.get()),
                                                      ('Static', self.static.get()), ('RTK', self.RTK.get()),
                                                      ('TCRA A', self.TS15.get()),
                                                      ('TCRA B', self.TS60.get()),
                                                      ('TCRA JH', self.MS60.get()), ('TDA', self.TDA.get()),
                                                      ('Other', self.other_instrument.get()),
                                                      ('Manual', self.manual.get()),
                                                      ('Photos', self.photos.get())))
                    break

        self.populate_diary()
        self.disable_checks()
        self.write_csv()

    def delete_record(self):
        for i, Item in enumerate(self.diary_data):
            if Item['RECID'] == int(self.ID.get()):
                del self.diary_data[i]
        self.populate_diary()
        self.disable_checks()
        self.write_csv()

    def write_csv(self):

        diary_directory = survey_config.diary_directory

        try:
            if os.path.exists(diary_directory):
                with open(diary_directory) as csvfile:
                    reader = csv.DictReader(csvfile)
                    Header = reader.fieldnames
                os.remove(diary_directory)
            else:

                tk.messagebox.showwarning("NO DATA DIARY CSV FOUND",
                                          "No csv data diary could be found @ [" + diary_directory + "]")
                return
            with open(diary_directory, 'w') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=Header, delimiter=",", lineterminator="\n")
                writer.writeheader()
                for Item in self.diary_data:
                    writer.writerow(Item)
        except:
            today = datetime.datetime.today()
            dt = today.strftime('%d%m%Y')
            tk.messagebox.showwarning("ERROR WRITING CSV FILE",
                                      "Error trying to save diary data. A backup was made @ [" + os.path.join(
                                          os.path.split(diary_directory)[0], 'DiaryErr_bkup_' + dt + '.csv') + "]")


class CalendarWindow:
    def __init__(self, parent, date_holder, format='%y%m%d'):
        self.date_holder = date_holder
        self.format = format
        self.parent = parent
        self.cal = calendar.TextCalendar(calendar.SUNDAY)
        self.year = datetime.datetime.today().year
        self.month = datetime.datetime.today().month
        self.wid = []
        self.day_selected = datetime.datetime.today().day
        self.month_selected = self.month
        self.year_selected = self.year
        self.day_name = calendar.day_name[datetime.datetime.today().weekday()]

        self.setup(self.year, self.month)

    def clear(self):
        for w in self.wid[:]:
            w.grid_forget()
            self.wid.remove(w)

    def go_prev(self):
        if self.month > 1:
            self.month -= 1
        else:
            self.month = 12
            self.year -= 1
        self.clear()
        self.setup(self.year, self.month)

    def go_next(self):
        if self.month < 12:
            self.month += 1
        else:
            self.month = 1
            self.year += 1

        self.clear()
        self.setup(self.year, self.month)

    def get_selected_date(self):
        return self.date_holder

    def selection(self, day, name):
        self.day_selected = day
        self.month_selected = self.month
        self.year_selected = self.year
        self.day_name = name
        self.date_selected = str(self.day_selected) + '/' + str(self.month) + '/' + str(self.year)
        self.date_holder = datetime.datetime.strptime(
            str(self.day_selected) + '/' + str(self.month) + '/' + str(self.year), '%d/%m/%Y').strftime(
            self.format)
        todays_date = datetime.datetime.today().strftime('%y%m%d')
        self.clear()
        self.setup(self.year, self.month)

    def setup(self, y, m):
        left = tk.Button(self.parent, text='<', command=self.go_prev)
        self.wid.append(left)
        left.grid(row=0, column=1)

        header = tk.Label(self.parent, height=2, text='{}   {}'.format(calendar.month_abbr[m], str(y)))
        self.wid.append(header)
        header.grid(row=0, column=2, columnspan=3)

        right = tk.Button(self.parent, text='>', command=self.go_next)
        self.wid.append(right)
        right.grid(row=0, column=5)

        days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        for num, name in enumerate(days):
            t = tk.Label(self.parent, text=name[:3])
            self.wid.append(t)
            t.grid(row=1, column=num)

        for w, week in enumerate(self.cal.monthdayscalendar(y, m), 2):
            for d, day in enumerate(week):
                if day:
                    dn = calendar.day_name[
                        datetime.datetime.strptime(str(day) + '/' + str(m) + '/' + str(y), '%d/%m/%Y').weekday()]

                    b = tk.Button(self.parent, width=2, height=1, text=day,
                                  command=lambda day=day, dn=dn: self.selection(day, dn))
                    self.wid.append(b)
                    b.grid(row=w, column=d, sticky='nsew')

        sel = tk.Label(self.parent, height=2,
                       text='{} {} {} {}'.format(self.day_name, calendar.month_name[self.month_selected],
                                                 self.day_selected, self.year_selected))
        self.wid.append(sel)
        sel.grid(row=8, column=0, columnspan=7)

        ok = tk.Button(self.parent, width=5, text='OK', command=self.kill_and_save)

        self.wid.append(ok)

        ok.grid(row=9, column=2, columnspan=3, pady=10)

    def kill_and_save(self):
        self.parent.destroy()


class GUIApplication(tk.Frame):

    def __init__(self, master, *args, **kwargs):
        super().__init__(master, *args, **kwargs)

        # see fixed_map method for the reason for this style inclusion
        self.style = ttk.Style()
        self.style.map('Treeview', foreground=self.fixed_map('foreground'),
                  background=self.fixed_map('background'))

        self.menu_bar = MenuBar(master)
        self.status_bar = StatusBar(master)
        self.main_window = MainWindow(master)
        self.status_bar.status.pack(side="bottom", fill="x")
        self.menu_bar.pack(side="top", fill="x")

        self.workflow_bar = WorkflowBar(self.main_window)
        self.workflow_bar.pack(fill="x")

        self.job_tracker_bar = None
        # try:
        #     self.job_tracker_bar = JobTrackerBar(self.main_window, self.menu_bar.user_config.user_initials)
        #     self.job_tracker_bar.pack(fill="x")
        # except Exception as ex:
        #
        #     self.menu_bar.job_tracker_sub_menu.entryconfig("Create new Job", state="disabled")
        #     self.menu_bar.job_tracker_sub_menu.entryconfig("Track a Job", state="disabled")
        #     logger.exception('Error has occurred creating Job Tracker object.\n\n' + str(ex))

        # self.job_tracker_bar.hide_job_tracker_bar()
        self.list_box = ListBoxFrame(self.main_window)
        self.list_box.pack(fill="both")
        self.main_window.pack(fill="both", expand=True)

    def fixed_map(self, option):
        # Fix for setting text colour for Tkinter 8.6.9
        # From: https://core.tcl.tk/tk/info/509cafafae
        #
        # Returns the style map for 'option' with any styles starting with
        # ('!disabled', '!selected', ...) filtered out.

        # style.map() returns an empty list for missing options, so this
        # should be future-safe.
        return [elm for elm in self.style.map('Treeview', query_opt=option) if
                elm[:2] != ('!disabled', '!selected')]

    @staticmethod
    def refresh():
        MenuBar.format_gsi_file()
        MenuBar.create_and_populate_database()
        MenuBar.update_gui()

def main():
    global gui_app
    global gsi
    global survey_config
    global database
    global logger

    # Create main window
    root = tk.Tk()
    # root.geometry("1600x1000")
    root.state('zoomed')
    root.title("SURVEY ASSIST")
    root.wm_iconbitmap(r'icons\analyser.ico')

    survey_config = SurveyConfiguration()

    # Setup logger
    logger = logging.getLogger('Survey Assist - v1.0 ')
    configure_logger()
    gsi = GSI(logger, survey_config)
    gui_app = GUIApplication(root)
    database = GSIDatabase()

    logger.info('************************* STARTED APPLICATION - User: ' + gui_app.menu_bar.user_config.user_initials + ' *************************')

    root.mainloop()

def configure_logger():
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

    # Writes debug messages to the log
    file_handler = logging.FileHandler('Survey Assist.log')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    # Display debug messages to the console
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

if __name__ == "__main__":
    main()
