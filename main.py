#! python3

""" This program reads in a GSI file from a Leica 'Total Station' and displays the file
in a clearer, more user-friendly format.  You can then execute queries on this data to extract relevant information.
It also checks for survey errors in a survey, and contains some utilities to help with CompNet.

NOTE: For 3.4 compatibility
    i) Replaced f-strings with.format method.
    ii) had to use an ordered dictionary"""

# TODO for some of the errors, open up user settings and allow use to change values
# TODO PC changes single and batch

import shutil
import tkinter.messagebox
import datetime
import logging.config
from tkinter import filedialog
from GSI import *
from configurations import UserConfiguration, SurveyConfiguration
from GSI import GSIDatabase, CorruptedGSIFileError, GSIFile
from decimal import *
from pathlib import Path
from compnet import CRDCoordinateFile, ASCCoordinateFile, STDCoordinateFile, CoordinateFile, FixedFile
from utilities import *

# TODO for testing only - remove
todays_date = '200121'
# todays_date = '200414'
# todays_date = datetime.datetime.today().strftime('%y%m%d')

todays_day = todays_date[-2:]
todays_month = todays_date[-4:-2]
todays_year = todays_date[-6:-4]
todays_date_reversed = todays_day + todays_month + todays_year
todays_date_month_day_format = todays_month + todays_day

gui_app = None


class MenuBar(tk.Frame):
    filename_path = ""

    def __init__(self, master):
        super().__init__(master)

        self.master = master

        # for importing rali survey
        self.ts_used = ""

        # # remove todays_dated_directory value in case its old
        # survey_config.todays_dated_directory = ""
        self.user_config = UserConfiguration()
        self.monitoring_job_dir = os.path.join(survey_config.root_job_directory, survey_config.current_year,
                                               survey_config.default_survey_type)
        self.query_dialog_box = None
        self.filename_path = ""
        self.compnet_working_dir = ""

        self.menu_bar = tk.Menu(self.master)
        self.master.config(menu=self.menu_bar)

        # File Menu
        self.file_sub_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.file_sub_menu.add_command(label="Open...", command=self.choose_gsi_file)
        self.file_sub_menu.add_command(label="Create Dated Directory...",
                                       command=lambda: self.new_dated_directory(False))
        self.file_sub_menu.add_command(label="Create Job Directory...", command=self.new_job_directoy)
        self.file_sub_menu.add_command(label="Import SD Data", command=self.import_sd_data)
        self.file_sub_menu.add_separator()
        self.file_sub_menu.add_command(label="Monitoring - Create", command=self.monitoring_create, state="disabled")
        self.file_sub_menu.add_command(label="Monitoring - Update Coords", command=self.monitoring_update_coords,
                                       state="disabled")
        self.file_sub_menu.add_command(label="Monitoring - Update Labels", command=self.monitoring_update_labels,
                                       state="disabled")
        self.file_sub_menu.add_command(label="Monitoring - Rename Updated Files",
                                       command=self.monitoring_rename_updated_files, state="disabled")

        self.menu_bar.add_cascade(label="File", menu=self.file_sub_menu)

        # Edit menu
        self.edit_sub_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.edit_sub_menu.add_command(label="Delete all 2D Orientation Shots", command=self.delete_orientation_shots)
        self.edit_sub_menu.add_command(label="Change point name...", command=self.change_point_name)
        self.edit_sub_menu.add_command(label="Change target height...", command=self.change_target_height)
        self.edit_sub_menu.add_separator()
        self.edit_sub_menu.add_command(label="Prism Constant - Fix single...", command=self.prism_constant_fix_single,
                                       state="disabled")
        self.edit_sub_menu.add_command(label="Prism Constant - Fix batch ...", command=self.prism_constant_fix_batch,
                                       state="disabled")

        self.menu_bar.add_cascade(label="Edit Survey", menu=self.edit_sub_menu, state="disabled")

        # Check menu
        self.check_sub_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.check_sub_menu.add_command(label="Check Tolerances (3D only)",
                                        command=self.check_3d_survey)
        self.check_sub_menu.add_command(label="Check Control Naming (3D only) ", command=self.check_control_naming)
        self.check_sub_menu.add_command(label="Check FL-FR ", command=self.check_FLFR)
        self.check_sub_menu.add_command(label="Check All (3D only)",
                                        command=self.check_3d_all)
        self.check_sub_menu.add_separator()
        self.check_sub_menu.add_command(label="Compare Prism Constants to similar survey...",
                                        command=self.compare_survey)
        self.check_sub_menu.add_command(label="Query GSI...", command=self.display_query_input_box)
        self.menu_bar.add_cascade(label="Check Survey", menu=self.check_sub_menu, state="disabled")

        # Export CSV
        self.menu_bar.add_command(label="Export CSV", command=self.export_csv, state="disabled")

        # Compnet menu
        self.compnet_sub_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.compnet_sub_menu.add_command(label="Update Fixed File...", command=self.update_fixed_file)
        self.compnet_sub_menu.add_command(label="Weight STD File ...", command=self.weight_STD_file)
        self.compnet_sub_menu.add_command(label="Compare CRD Files...", command=self.compare_crd_files)
        self.compnet_sub_menu.add_command(label="Strip Non-control Shots", command=self.strip_non_control_shots)
        self.compnet_sub_menu.add_command(label="Combine/Re-order GSI Files", command=self.combine_gsi_files)

        self.menu_bar.add_cascade(label="Compnet", menu=self.compnet_sub_menu)

        # Utilities menu
        self.utility_sub_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.utility_sub_menu.add_command(label="Create temporary CSV from .ASC file", command=self.create_CSV_from_ASC)
        self.menu_bar.add_cascade(label="Utilities", menu=self.utility_sub_menu)

        # Job Diary
        self.menu_bar.add_command(label="Job diary", command=self.job_diary)

        # Config menu
        self.menu_bar.add_command(label="Config", command=self.configure_survey)

        # Re-display GSI
        self.menu_bar.add_command(label="Re-display GSI", command=self.re_display_gsi, state="disabled")

        # Help menu
        self.help_sub_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.help_sub_menu.add_command(label="Manual", command=self.open_manual)
        self.help_sub_menu.add_command(label="About", command=self.display_about_dialog_box)
        self.menu_bar.add_cascade(label="Help", menu=self.help_sub_menu)

        # Exit menu
        self.menu_bar.add_command(label="Exit", command=self.client_exit)

    def choose_gsi_file(self):

        if survey_config.todays_dated_directory == "":

            intial_directory = self.monitoring_job_dir

        else:
            intial_directory = os.path.join(survey_config.todays_dated_directory, "TS")

        MenuBar.filename_path = tk.filedialog.askopenfilename(initialdir=intial_directory, title="Select file",
                                                              filetypes=[("GSI Files", ".gsi")])
        survey_config.update(SurveyConfiguration.section_file_directories, 'last_used', os.path.dirname(
            MenuBar.filename_path))

        GUIApplication.refresh()
        self.enable_menus()
        gui_app.workflow_bar.hide_workflow_bar()

    def new_dated_directory(self, choose_date=True, folder_selected=None):

        # default path for the file dialog to open too
        default_path = os.path.join(survey_config.root_job_directory, survey_config.current_year, survey_config.default_survey_type)
        if folder_selected is None:
            folder_selected = filedialog.askdirectory(parent=self.master, initialdir=default_path, title='Please select the job directory')

        if os.path.exists(folder_selected):
            if choose_date is True:
                self.choose_date()

            CreateDatedDirectoryWindow(self, folder_selected)

    def choose_date(self):
        # Let user choose the date, rather than default to todays date
        cal_root = tk.Toplevel()
        cal = CalendarWindow(cal_root, todays_date)
        self.master.wait_window(cal_root)
        active_date = cal.get_selected_date()

    def open_calender(self, parent):
        cal_root = tk.Toplevel()
        cal = CalendarWindow(cal_root, todays_date)
        parent.wait_window(cal_root)

    def new_job_directoy(self):

        initial_dir = os.path.join(survey_config.root_job_directory, survey_config.current_year, survey_config.default_survey_type)
        os.startfile(initial_dir)

    def import_sd_data(self):


        ts60_id_list = survey_config.ts60_id_list.split()
        ts15_id_list = survey_config.ts15_id_list.split()
        ms60_id_list = survey_config.ms60_id_list.split()

        user_sd_directory = self.user_config.user_sd_root
        usb_root_directory = self.user_config.usb_root
        todays_dated_directory = survey_config.todays_dated_directory
        import_root_directory = todays_dated_directory
        current_rail_monitoring_file_name = survey_config.current_rail_monitoring_file_name

        todays_gps_filename_paths = set()
        ts_60_filename_paths = set()
        ts_15_filename_paths = set()
        ms_60_filename_paths = set()

        is_rail_survey = False

        # lets first check if user SD directory exists
        if not os.path.exists(user_sd_directory):
            # lets check the usb drive for 1200 series GPS's
            if not os.path.exists(usb_root_directory):

                tk.messagebox.showinfo("IMPORT SD DATA", "Can't find your SD card drive.  Press OK to select your SD drive.")
                user_sd_directory = tkinter.filedialog.askdirectory(parent=self.master, initialdir='C:\\',
                                                                    title='Please choose the SD card drive')
                # store SD drive location for future use
                self.user_config.update(UserConfiguration.section_file_directories, 'user_sd_root', user_sd_directory)
            else:
                user_sd_directory = usb_root_directory

        # First determine if SD card contains any folders and\or files
        print(next(os.walk(user_sd_directory))[0])  # root
        sd_folder_list = next(os.walk(user_sd_directory))[1]  # folders in root
        sd_file_list = next(os.walk(user_sd_directory))[2]  # files in root

        dbx_directory_path = os.path.join(user_sd_directory, 'DBX')
        gsi_directory_path = os.path.join(user_sd_directory, 'Gsi')

        # check to see if SD card contains only files.
        if not sd_folder_list:

            #  Most probably a GPSE unit which contains only files where some have no date
            for filename in sd_file_list:
                # GPSE for some readon incldues files that have no date.  Lets just copy them all over.
                if 'GPSE' in filename:
                    # add all files in directory to copy
                    for filename in os.listdir(user_sd_directory):
                        todays_gps_filename_paths.add(os.path.join(user_sd_directory, filename))

        # Check if DBX and GSI folders exist since there should be a DBX and GSI folder for VIVA and GPS 1200 SD cards
        elif os.path.isdir(dbx_directory_path) and os.path.isdir(gsi_directory_path):

            try:
                # serach through all files and folders in the DBX directory
                for filename in os.listdir(dbx_directory_path):

                    # we are only interest in files or folders with todays date in it
                    if todays_date_reversed in filename:

                        if 'GPS' in filename:
                            # add file or folder to copy
                            todays_gps_filename_paths.add(os.path.join(dbx_directory_path, filename))

                        # check to see if any of the files are TS files.  If so,, determine their ID

                        elif any(x in filename for x in ts60_id_list):
                            # add file or folder to copy
                            ts_60_filename_paths.add(os.path.join(dbx_directory_path, filename))

                            # search for corresponding GSI file/s
                            gsi_filenames = self.get_gsi_file(todays_date_reversed, gsi_directory_path)
                            if gsi_filenames:
                                for gsi_filename in gsi_filenames:
                                        ts_60_filename_paths.add(os.path.join(gsi_directory_path, gsi_filename))

                        elif any(x in filename for x in ts15_id_list):
                            ts_15_filename_paths.add(os.path.join(dbx_directory_path, filename))

                            # search for corresponding GSI file/s
                            gsi_filenames = self.get_gsi_file(todays_date_reversed, gsi_directory_path)
                            if gsi_filenames:
                                for gsi_filename in gsi_filenames:
                                    ts_15_filename_paths.add(os.path.join(gsi_directory_path, gsi_filename))

                        elif any(x in filename for x in ms60_id_list):
                            ms_60_filename_paths.add(os.path.join(dbx_directory_path, filename))

                            # search for corresponding GSI file/s
                            gsi_filenames = self.get_gsi_file(todays_date_reversed, gsi_directory_path)
                            if gsi_filenames:
                                for gsi_filename in gsi_filenames:
                                    ms_60_filename_paths.add(os.path.join(gsi_directory_path, gsi_filename))

                    # check for 1200 GSP default files that only have the daymonth suffix
                    elif 'Default' in filename and todays_date_month_day_format in filename:
                        todays_gps_filename_paths.add(os.path.join(dbx_directory_path, filename))

                        # GSPE has i25 and m25 with no date.  No choice but to copy these over even if they are not from today.
                        for filename in os.listdir(dbx_directory_path):

                            if filename[-3:] == 'i25' or filename[-3:] == 'm25':
                                todays_gps_filename_paths.add(os.path.join(dbx_directory_path, filename))

            except FileNotFoundError as ex:
                tk.messagebox.showinfo("IMPORT SD DATA", str(ex) + "\n\nPlease copy over the files over manually")
                # open up explorer
                os.startfile('c:')
                return


        # create a list of all filename paths found having todays date
        all_todays_filename_paths = list(todays_gps_filename_paths) + list(ts_60_filename_paths) + list(ts_15_filename_paths) + \
                                    list(ms_60_filename_paths)

        # check to see if user is trying import a rail survey - these files have no date and have to be treated differently
        if not all_todays_filename_paths:

            msg_box_question = tk.messagebox.askyesno("IMPORT SD DATA", "Couldn't find any survey files with todays date.  Please choose:\n\n"
                                                                        "YES - to import a rail monitoring file\n"
                                                                        "NO - to copy over the files manually\n")

            if msg_box_question:
                ImportRailMonitoringFileWindow(self.master)
                ts_used = self.ts_used
                print(ts_used)

                try:
                    # copy over rail dbx and gsi
                    for gsi_filename in os.listdir(gsi_directory_path):
                        if current_rail_monitoring_file_name in gsi_filename:

                            # find the corresponding dbx file and determine the TS ID
                            for dbx_filename in os.listdir(dbx_directory_path):
                                if current_rail_monitoring_file_name in dbx_filename:
                                    if 'MS60' == ts_used:
                                        ms_60_filename_paths.add(os.path.join(dbx_directory_path, dbx_filename))
                                        ms_60_filename_paths.add(os.path.join(gsi_directory_path, gsi_filename))
                                    if 'TS60' == ts_used:
                                        ts_60_filename_paths.add(os.path.join(dbx_directory_path, dbx_filename))
                                        ts_60_filename_paths.add(os.path.join(gsi_directory_path, gsi_filename))
                                    if 'TS15' == ts_used:
                                        ts_15_filename_paths.add(os.path.join(dbx_directory_path, dbx_filename))
                                        ts_15_filename_paths.add(os.path.join(gsi_directory_path, gsi_filename))

                    is_rail_survey = True

                except FileNotFoundError as ex:
                    tk.messagebox.showinfo("IMPORT SD DATA", 'Cannot find the specified path ' + gsi_directory_path + "\n\nPlease copy over the "
                                                                                                                        "files over manually")
                    # open up explorer
                    os.startfile('c:')
                    return

            else:
                # copy files manually.  open up explorer
                os.startfile('c:')
                return

        # create a list of all filenamepaths found having todays date
        all_todays_filename_paths = list(todays_gps_filename_paths) + list(ts_60_filename_paths) + list(ts_15_filename_paths) + \
                                    list(ms_60_filename_paths)

        # check again to see if we found any rail surveys
        if not all_todays_filename_paths:

            tk.messagebox.showinfo("IMPORT SD DATA", "Couldn't find any survey files with todays date. Please copy over manually")

            # open up explorer
            os.startfile('c:')
            return

        # check if todays directory exists.  If not, get user to choose.
        if not todays_dated_directory:
            import_root_directory = tkinter.filedialog.askdirectory(parent=self.master, initialdir=self.monitoring_job_dir,
                                                                    title='Choose the job directory where you would like to import the SD data to')
            survey_config.todays_dated_directory = import_root_directory

        if not import_root_directory:
            # user has closed down the ask directory so exit import sd
            return

        # lets copy files over to the dated directory but confirm with user first

        filenames_txt_list = ""
        confirm_msg = "The following files will be copied over to " + import_root_directory + "\n\n"

        for filename_path in sorted(all_todays_filename_paths):
            filenames_txt_list += os.path.basename(filename_path) + '\n'

        confirm_msg += filenames_txt_list + "\nHit 'Cancel' to copy file over manually"

        ok = tk.messagebox.askokcancel(message=confirm_msg)

        if ok:
            import_path = ""

            try:
                if all_todays_filename_paths:
                    for file_path in todays_gps_filename_paths:
                        import_path = os.path.join(import_root_directory, 'GPS', os.path.basename(file_path))
                        if os.path.isdir(file_path):
                            shutil.copytree(file_path, import_path)
                        else:
                            shutil.copy(file_path, import_path)

                    for file_path in ts_15_filename_paths:
                        import_path = os.path.join(import_root_directory, 'TS', 'TS15', os.path.basename(file_path))
                        if os.path.isdir(file_path):
                            shutil.copytree(file_path, import_path)
                        else:
                            shutil.copy(file_path, import_path)

                        # Check and copy over gsi to edited diretory if it exists
                        self.copy_over_gsi_to_edited_directory(file_path, import_path, is_rail_survey)

                    for file_path in ts_60_filename_paths:
                        import_path = os.path.join(import_root_directory, 'TS', 'TS60', os.path.basename(file_path))
                        if os.path.isdir(file_path):
                            shutil.copytree(file_path, import_path)
                        else:
                            shutil.copy(file_path, import_path)

                        # check and copy over gsi to edited diretory if it exists
                        self.copy_over_gsi_to_edited_directory(file_path, import_path, is_rail_survey)

                    for file_path in ms_60_filename_paths:
                        import_path = os.path.join(import_root_directory, 'TS', 'MS60', os.path.basename(file_path))
                        if os.path.isdir(file_path):
                            shutil.copytree(file_path, import_path)
                        else:
                            shutil.copy(file_path, import_path)

                        # Check and copy over gsi to edited diretory if it exists
                        self.copy_over_gsi_to_edited_directory(file_path, import_path, is_rail_survey)

            except FileExistsError as ex:
                print(ex)
                tk.messagebox.showerror("COPYING SD DATA", "File aready exists: " + file_path + '\n\nat ' + import_path)

                # open up explorer
                os.startfile('c:')

            except IOError as ex:
                print(ex)
                # Most likely not a dated directory
                tk.messagebox.showerror("COPYING SD DATA", "Problem copying files across.   This is most likely because the destination folder "
                                                           "chosen doesn't have a dated folder structure (i.e GPS, OTHER, OUTPUT, "
                                                           "TS directories. \n\nPlease copy files over manually.")

                # open up explorer
                os.startfile('c:')

            except Exception as ex:
                print(ex)
                tk.messagebox.showerror("COPYING SD DATA", "Problem copying files across.  Please copy files over manually.")

                # open up explorer
                os.startfile('c:')
        else:
            # open up explorer
            os.startfile('c:')

    def copy_over_gsi_to_edited_directory(self, file_path, import_path, is_rail_survey):


        # if GSI file make a copy and place it in the edited folder
        if Path(file_path).suffix.upper() == '.GSI':

            gsi_filename = os.path.basename(file_path)
            gsi_filename_no_ext = gsi_filename[:-4]
            ts_root_dir = str(Path(import_path).parent.parent)
            print(ts_root_dir)

            if is_rail_survey:
                edited_filename_path = ts_root_dir + '/EDITING/' + gsi_filename_no_ext + '_' + self.ts_used + '_' + todays_date_reversed + '_EDITED.GSI'
            else:
                edited_filename_path = ts_root_dir + '/EDITING/' + gsi_filename_no_ext + '_EDITED.GSI'
            shutil.copy(file_path, edited_filename_path)

    def get_gsi_file(self, date, gsi_directory):

        gsi_filenames = []
        # date is in the 201214 format
        for filename in os.listdir(gsi_directory):

            if date in filename:
                if Path(filename).suffix.upper() == '.GSI':
                    gsi_filenames.append(filename)
        return gsi_filenames

    def monitoring_create(self):
        pass

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

        except CorruptedGSIFileError:

            # Most likely an corrupted GSI file was selected
            tk.messagebox.showerror("ERROR", 'Error reading GSI File:\n\nThis file is a corrupted or '
                                             'incorrect GSI file')

            gui_app.status_bar.status['text'] = 'Please choose a GSI File'

        except Exception:

            # Most likely an incorrect file was chosen
            logger.exception('Error has occurred. ')

            tk.messagebox.showerror("ERROR", 'Error reading GSI File:\n\nPlease make sure file is not opened '
                                             'by another program.  If problem continues please contact Richard Walter')

    @staticmethod
    def create_and_populate_database():
        database.create_db()
        database.populate_table(gsi.formatted_lines)

    @staticmethod
    def update_database():

        database.populate_table(gsi.formatted_lines)

    @staticmethod
    def update_gui():
        gui_app.list_box.populate(gsi.formatted_lines)
        gui_app.status_bar.status['text'] = MenuBar.filename_path

    def check_3d_survey(self):

        errors, error_points, subject, = "", "", ""
        error_line_numbers = []
        subject = "Checking Tolerances"

        try:
            errors, error_points = gsi.check_3D_survey(database.conn)
            error_text = ""

            for error in errors:
                error_text += error

            if not errors:
                error_text = "Survey is within the specified tolerance.  Well done!"

            # display error dialog box
            tkinter.messagebox.showinfo(subject, error_text)

        except Exception:
            logger.exception('Error creating executing SQL query')
            tk.messagebox.showerror("Error", 'Error executing this query:\nPlease contact the developer of this '
                                             'program or see log file for further information')

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


        except Exception:
            logger.exception('Error checking station naming')
            tk.messagebox.showerror("Error", 'Error executing this query:\nPlease contact the developer of this '
                                             'program or see log file for further information')

    def check_FLFR(self, display='YES'):

        error_line_number_list = []
        dialog_text_set = set()
        dialog_text = "\n"
        formatted_gsi_lines_analysis = []

        for gsi_line_number, line in enumerate(gsi.formatted_lines, start=0):

            if GSI.is_control_point(line):
                station_name = line['Point_ID']
                obs_from_station_dict = gsi.get_all_shots_from_a_station_including_setup(station_name, gsi_line_number)
                analysed_lines = self.anaylseFLFR(copy.deepcopy(obs_from_station_dict))

                # add the analysis lines for this station
                for aline in analysed_lines:
                    formatted_gsi_lines_analysis.append(aline)

                    # for each station setup add 'STN->Point_ID' for each error found
                    for key, field_value in aline.items():
                        if '*' in field_value:
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
            dialog_text = " FL-FR shots are within specified tolerance"

        # display dialog box
        tkinter.messagebox.showinfo("Checking FL-FR", dialog_text)

        if display == 'NO':  # don't display results to user - just a popup dialog to let them know there is an issue
            pass
        else:
            gui_app.list_box.populate(formatted_gsi_lines_analysis, error_line_number_list)

    def anaylseFLFR(self, obs_from_station_dict):

        precision = survey_config.precision_value

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

            if GSI.is_control_point(formatted_line_dict):
                # dont analyse stn setup - append to start of list
                analysed_lines.insert(0, formatted_line_dict)
                continue

            # check to see if line has already compared
            if index == line_already_compared:
                continue

            # if not at the end of the dictionary ( could use try except IndexError )
            if index < len(sorted_obs_from_station_list):
                obs_line_2_dict = sorted_obs_from_station_list[index + 1]

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
                            obs_line_1_field_value = get_numerical_value_from_string(obs_line_1_field_value_str,
                                                                                     field_type, precision)

                            obs_line_2_field_value = get_numerical_value_from_string(obs_line_2_field_value_str,
                                                                                     field_type, precision)
                            angular_diff = decimalize_value(angular_difference(obs_line_1_field_value,
                                                                               obs_line_2_field_value, 180), precision)
                            angle_dms = angle_decimal2DMS(angular_diff)
                            obs_line_2_dict[key] = GSI.format_angles(angle_dms, precision)

                        elif key == 'Prism_Constant':
                            obs_line_2_dict[key] = str(int(obs_line_1_dict[key]) - int(obs_line_1_dict[key]))
                        elif key == 'Point_ID':
                            pass
                        else:  # field should be a float
                            field_type = FIELD_TYPE_FLOAT
                            obs_line_1_field_value = get_numerical_value_from_string(obs_line_1_field_value_str,
                                                                                     field_type, precision)

                            obs_line_2_field_value = get_numerical_value_from_string(obs_line_2_field_value_str,
                                                                                     field_type, precision)
                            if (obs_line_1_field_value != "") and (obs_line_2_field_value != ""):
                                float_diff_str = str(decimalize_value(obs_line_1_field_value - obs_line_2_field_value,
                                                                      precision))
                                float_diff_str = self.check_diff_exceed_tolerance(key, float_diff_str)
                                obs_line_2_dict[key] = float_diff_str

                else:
                    # probably an orientation shot, or a shot that doesn't have a double - make blank
                    blank_line_dict = analysed_line_blank_values_dict.copy()
                    blank_line_dict['Point_ID'] = obs_line_1_dict['Point_ID']
                    analysed_lines.append(blank_line_dict)
                    continue

                blank_line_dict = analysed_line_blank_values_dict.copy()
                blank_line_dict['Point_ID'] = obs_line_1_dict['Point_ID']
                analysed_lines.append(blank_line_dict)
                analysed_lines.append(obs_line_2_dict)
                line_already_compared = index + 1

            else:
                # end of the dictionary reached - do not analyse but add as it hasnt been compared
                analysed_lines.append(obs_line_1_dict)
                pass

        return analysed_lines

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

        self.check_FLFR('NO')
        self.check_control_naming()
        self.check_3d_survey()

    def change_target_height(self):
        TargetHeightWindow(self.master)

    def change_point_name(self):
        PointNameWindow(self.master)

    def prism_constant_fix_single(self):
        pass

    def prism_constant_fix_batch(self):
        pass

    def compare_survey(self):

        last_used_directory = survey_config.last_used_file_dir

        points_diff_PC_dict = {}

        old_survey_filepath = tk.filedialog.askopenfilename(parent=self.master, initialdir=last_used_directory,
                                                            filetypes=[("GSI Files", ".GSI")])
        old_survey_gsi = GSI(logger)
        old_survey_gsi.format_gsi(old_survey_filepath)
        old_survey_formatted_lines_except_setups = old_survey_gsi.get_all_lines_except_setup()
        old_point_PC_dict = OrderedDict()

        line_number_errors = []

        dialog_subject = "Prism Constant Comparision"
        dialog_text = "Prism constants match between surveys "
        error_text = "Prism constants mismatch (yellow highlight) found between the two surveys. "

        # Create a dictionary of points and their prism constant.
        # ASSUMPTION: prism constant for an old survey with no errors should be the same for the same point ID
        for formatted_line in old_survey_formatted_lines_except_setups:
            old_point_PC_dict[formatted_line['Point_ID']] = formatted_line['Prism_Constant']

        print(old_point_PC_dict)

        # for each point and its corresponding PC in old survey, check to see it matches PC in current survey
        for old_point_ID, old_PC in old_point_PC_dict.items():

            for line_number, current_gsi_line in enumerate(gsi.formatted_lines, start=1):

                # check to see if point id is a control point and skip if true
                if gsi.is_control_point(current_gsi_line):
                    continue

                current_point_ID = current_gsi_line['Point_ID']
                current_PC = current_gsi_line['Prism_Constant']

                if old_point_ID == current_point_ID:

                    # Compare PC - they should be the same.  If not report to user
                    if old_PC != current_PC:
                        points_diff_PC_dict[current_point_ID] = {'current pc': current_PC, 'old_pc': old_PC}
                        line_number_errors.append(line_number)
                        dialog_text = error_text

        tkinter.messagebox.showinfo(dialog_subject, dialog_text)
        gui_app.list_box.populate(gsi.formatted_lines, line_number_errors)

        print(points_diff_PC_dict)

    def export_csv(self):

        gsi.export_csv(MenuBar.filename_path)

    def display_query_input_box(self):

        QueryDialogWindow(self.master)

    def update_fixed_file(self):

        CompnetUpdateFixedFileWindow(self.master)

    def weight_STD_file(self):

        CompnetWeightSTDFileWindow(self.master)

    def compare_crd_files(self):

        CompnetCompareCRDFWindow(self.master)

    def strip_non_control_shots(self):

        CompnetStripNonControlShots()

    def combine_gsi_files(self):

        CombineGSIFilesWindow(self)

    def create_CSV_from_ASC(self):

        UtilityCreateCSVFromASCWindow(self)

    @staticmethod
    def job_diary():

        root = tk.Toplevel()
        JobDiaryWindow(root)

    def configure_survey(self):

        ConfigDialogWindow(self.master)

    def re_display_gsi(self):
        gui_app.refresh()

    def open_manual(self):
        pass

    @staticmethod
    def clear_query():

        gui_app.list_box.populate(gsi.formatted_lines)

    def enable_menus(self):

        self.menu_bar.entryconfig("Check Survey", state="normal")
        self.menu_bar.entryconfig("Edit Survey", state="normal")
        self.menu_bar.entryconfig("Re-display GSI", state="normal")
        self.menu_bar.entryconfig("Export CSV", state="normal")

    def disable_menus(self):

        self.menu_bar.entryconfig("Check Survey", state="disabled")
        self.menu_bar.entryconfig("Edit Survey", state="disabled")
        self.menu_bar.entryconfig("Re-display GSI", state="disabled")
        self.menu_bar.entryconfig("Export CSV", state="disabled")

    @staticmethod
    def display_about_dialog_box():

        about_me_text = "This program reads a GSI file from a Leica Total " \
                        "Station and displays the data in a clearer, more user-friendly format." \
                        " \n\nYou can then execute queries on this data to extract relevant information, or check for" \
                        " errors in a survey, such as incorrect station labelling, prism constants and tolerance " \
                        "errors. \n\n" \
                        "This program also assists with Compnet - combining gsi files, copying over fixed files, " \
                        "comparing CRD files, and " \
                        "stripping out GSI leaving just the control stations for easier analysis of problems\n\n" \
                        "Written by Richard Walter 2019"

        tkinter.messagebox.showinfo("About Survey Assist", about_me_text)

    @staticmethod
    def client_exit():
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
            tk.messagebox.showerror("ERROR", 'Error reading GSI File:\n\nThis file is a corrupted or '
                                             'incorrect GSI file')

            gui_app.status_bar.status['text'] = 'Please choose a GSI File'

        except Exception:

            # Most likely an incorrect file was chosen
            logger.exception('Error has occurred. ')

            tk.messagebox.showerror("ERROR", 'Error reading GSI File:\n\nPlease make sure file is not opened '
                                             'by another program.  If problem continues please contact Richard Walter')


class ConfigDialogWindow:
    # dialog_w = 300
    # dialog_h = 240

    def __init__(self, master):

        self.master = master

        self.sorted_stn_file_path = survey_config.sorted_station_config

        #  Lets build the dialog box
        self.dialog_window = tk.Toplevel(master)
        self.dialog_window.title("Survey Configuration")

        # self.dialog_window.geometry(MainWindow.position_popup(master, ConfigDialog.dialog_w, ConfigDialog.dialog_h))

        tk.Label(self.dialog_window, text="Precision:").grid(row=0, column=0, padx=5, pady=(15, 5), sticky='w')
        self.precision = tk.StringVar()
        self.precision_entry = ttk.Combobox(self.dialog_window, textvariable=self.precision, state='readonly')
        self.precision_entry['values'] = SurveyConfiguration.precision_value_list

        self.precision_entry.current(
            SurveyConfiguration.precision_value_list.index(survey_config.precision_value))
        self.precision_entry.bind("<<ComboboxSelected>>")
        self.precision_entry.grid(row=0, column=1, padx=5, pady=(15, 5), sticky='w')

        tk.Label(self.dialog_window, text="Easting Tolerance: ").grid(row=1, column=0, padx=5, pady=5, sticky='w')
        self.entry_easting = tk.Entry(self.dialog_window)
        self.entry_easting.insert(tkinter.END, survey_config.easting_tolerance)
        self.entry_easting.grid(row=1, column=1, padx=5, pady=5, sticky='w', )

        tk.Label(self.dialog_window, text="Northing Tolerance: ").grid(row=2, column=0, padx=5, pady=5, sticky='w')
        self.entry_northing = tk.Entry(self.dialog_window)
        self.entry_northing.insert(tkinter.END, survey_config.northing_tolerance)
        self.entry_northing.grid(row=2, column=1, padx=5, pady=5, sticky='w')

        tk.Label(self.dialog_window, text="Height Tolerance: ").grid(row=3, column=0, padx=5, pady=5, sticky='w')
        self.entry_height = tk.Entry(self.dialog_window)
        self.entry_height.insert(tkinter.END, survey_config.height_tolerance)
        self.entry_height.grid(row=3, column=1, padx=5, pady=5, sticky='w')

        self.sorted_station_file_lbl = tk.Label(self.dialog_window, text="Sorted station file: ").grid(row=4, column=0,
                                                                                                       padx=5,
                                                                                                       pady=10,
                                                                                                       sticky='w')
        self.sorted_station_file_btn = tk.Button(self.dialog_window, text=os.path.basename(self.sorted_stn_file_path),
                                                 command=self.select_sorted_stn_file)
        self.sorted_station_file_btn.grid(row=4, column=1, padx=20, pady=10, sticky='w')

        save_b = tk.Button(self.dialog_window, text="Save", width=10, command=self.save)
        save_b.grid(row=5, column=0, padx=5, pady=20, sticky='nesw')

        cancel_b = tk.Button(self.dialog_window, text="Cancel", width=10, command=self.cancel)
        cancel_b.grid(row=5, column=1, padx=20, pady=20, sticky='nesw')

    def select_sorted_stn_file(self):

        self.sorted_stn_file_path = tk.filedialog.askopenfilename(parent=self.master, filetypes=[("Text Files",
                                                                                                  ".TXT")])
        if self.sorted_stn_file_path != "":
            self.sorted_station_file_btn.config(text=os.path.basename(self.sorted_stn_file_path))
        self.dialog_window.lift()  # bring window to the front again

    def save(self):

        global survey_config

        precision_dictionary = {}
        survey_tolerance_dictionary = {}
        configuration_dictionary = {}
        file_directory_dictionary = {}

        precision_dictionary['instrument_precision'] = self.precision_entry.get()
        survey_tolerance_dictionary['eastings'] = self.entry_easting.get()
        survey_tolerance_dictionary['northings'] = self.entry_northing.get()
        survey_tolerance_dictionary['height'] = self.entry_height.get()
        configuration_dictionary['sorted_station_config'] = self.sorted_stn_file_path

        input_error = False

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
            gui_app.menu_bar.survey_config.create_config_file(precision_dictionary, survey_tolerance_dictionary,
                                             configuration_dictionary)

            gui_app.menu_bar.survey_config = SurveyConfiguration()

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
        self.column_entry['values'] = gsi.column_names
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

    # def center_screen(self):
    #
    #     dialog_w = 350
    #     dialog_h = 150
    #
    #     ws = self.master.winfo_width()
    #     hs = self.master.winfo_height()
    #     x = int((ws / 2) - (dialog_w / 2))
    #     y = int((hs / 2) - (dialog_w / 2))
    #
    #     return '{}x{}+{}+{}'.format(dialog_w, dialog_h, x, y)

    def column_entry_cb_callback(self, event):

        # Set the values for the column_value combobox now that the column name has been selected
        # It removes any duplicate values and then orders the result.
        self.column_value_entry['values'] = sorted(set(gsi.get_column_values(self.column_entry.get())))

        self.column_value_entry.config(state='readonly')

    def ok(self):

        column_entry = self.column_entry.get()
        column_value_entry = self.column_value_entry.get()

        if column_entry is "":
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

        except Exception:
            logger.exception('Error creating executing SQL query:  {}'.format(sql_query_text))
            tk.messagebox.showerror("Error", 'Error executing this query:\nPlease contact the developer of this '
                                             'program')

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

        self.workflow_lbl = tk.Label(self.frame, text='NEW JOB WORKFLOW:')
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

        self.workflow_lbl.pack(padx=2, pady=5, side='left')
        self.btn_diary.pack(padx=5, pady=5, side='left')
        self.btn_create_directory_today.pack(padx=5, pady=5, side='left')
        self.btn_import_sd_data.pack(padx=5, pady=5, side='left')
        self.btn_open_gsi.pack(padx=5, pady=5, side='left')

    def show_workflow_bar(self):
        self.frame.pack(side='top', anchor=tk.W, fill=tk.X)

    def hide_workflow_bar(self):
        self.frame.pack_forget()


class MainWindow(tk.Frame):

    def __init__(self, master):
        super().__init__(master)

        self.master = master

    @staticmethod
    def position_popup(master, popup_w, popup_h):
        master.update_idletasks()
        mx = master.winfo_x()
        my = master.winfo_y()
        mw = master.winfo_width()
        mh = master.winfo_height()

        offset_x = 100
        offset_y = 100

        x = mx + offset_x
        y = my + offset_y

        return '{}x{}+{}+{}'.format(popup_w, popup_h, x, y)


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
        hsb = ttk.Scrollbar(self.list_box_view, orient='horizontal', command=self.list_box_view.xview)
        hsb.pack(side='bottom', fill='x')
        self.list_box_view.configure(yscrollcommand=vsb.set)
        self.list_box_view.configure(xscrollcommand=hsb.set)

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
                if column_name == gsi.GSI_WORD_ID_DICT['84'] and gsi_value is not "":
                    tag = self.stn_tag  # add STN tag if line is a station setup

                elif column_name == gsi.GSI_WORD_ID_DICT['32'] and gsi_value is "":
                    tag = self.orientation_tag

                elif line_number in highlight_lines:
                    tag = self.highlight_tag

            if tag == self.orientation_tag:
                ListBoxFrame.orientation_line_numbers.append(line_number)

            self.list_box_view.insert("", "end", values=complete_line, tags=(tag,))

        # color station setup and the remaining rows
        self.list_box_view.tag_configure(self.stn_tag, background='#ffe793')
        self.list_box_view.tag_configure(self.orientation_tag, background='#d1fac5')
        self.list_box_view.tag_configure(self.highlight_tag, background='#ffff00')
        self.list_box_view.tag_configure("", background='#eaf7f9')

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

        except CorruptedGSIFileError:

            # Most likely an corrupted GSI file was selected
            tk.messagebox.showerror("ERROR", 'Error reading GSI File:\n\nThis file is a corrupted or '
                                             'incorrect GSI file')

            gui_app.status_bar.status['text'] = 'Please choose a GSI File'

        except Exception:

            # Most likely an incorrect file was chosen
            logger.exception('Error has occurred. ')

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
            gui_app.menu_bar.survey_config.update(SurveyConfiguration.section_file_directories, 'todays_dated_directory', new_directory_path)
            gui_app.menu_bar.todays_dated_directory = new_directory_path

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


class TargetHeightWindow:

    def __init__(self, master):

        self.master = master

        self.precision = survey_config.precision_value

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

        # set the new target height hte user has entered
        new_target_height = self.get_entered_target_height()

        if new_target_height is not 'ERROR':

            line_numbers_to_ammend = []

            # build list of line numbers to amend
            # selected_items = gui_app.list_box_view.selection()
            selected_items = gui_app.list_box.list_box_view.selection()

            if selected_items:
                for selected_item in selected_items:
                    line_numbers_to_ammend.append(gui_app.list_box.list_box_view.item(selected_item)['values'][0])

                # update each line to amend with new target height and coordinates
                for line_number in line_numbers_to_ammend:
                    corrections = self.get_corrections(line_number, new_target_height)
                    gsi.update_target_height(line_number, corrections)

                if "TgtUpdated" not in MenuBar.filename_path:

                    amended_filepath = MenuBar.filename_path[:-4] + "_TgtUpdated.gsi"
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
                tk.messagebox.showinfo("INPUT ERROR", "Please select a line first that you want to change target "
                                                      "height")

    def get_corrections(self, line_number, new_target_height):

        # correction_list = []

        # update target height and Z coordinate for this line
        formatted_line = gsi.get_formatted_line(line_number)

        new_target_height = float(new_target_height)
        old_tgt_height = formatted_line['Target_Height']
        try:
            old_height = float(formatted_line['Elevation'])
        except ValueError:
            tk.messagebox.showinfo("TARGET HEIGHT SELECTION ERROR", "Please select a line that contains a target "
                                                                    "height. "
                                                                    "If problem persists, please see Richard")

        if old_tgt_height == '':
            old_tgt_height = 0.000
        elif old_tgt_height == '0':
            old_tgt_height = float(0.000)
        else:
            old_tgt_height = float(old_tgt_height)

        new_height = old_height - (new_target_height - old_tgt_height)

        old_height = str(decimalize_value(old_height, self.precision))
        new_height = str(decimalize_value(new_height, self.precision))
        old_tgt_height = str(decimalize_value(old_tgt_height, '3dp'))  # target height is always 3dp
        new_target_height = str(decimalize_value(new_target_height, '3dp'))

        return {'83': new_height, '87': new_target_height}

    def get_entered_target_height(self):

        # Check to see if number was entered correctly
        entered_target_height = "ERROR"

        try:
            entered_target_height = round(float(self.new_target_height_entry.get()), 3)

        except ValueError:

            # Ask user to re-enter a a numerical target height
            tk.messagebox.showerror("INPUT ERROR", "Please enter a valid number to 3 decimal places")

        else:
            print(entered_target_height)

        self.dialog_window.destroy()

        return entered_target_height


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

        self.dialog_window.geometry(MainWindow.position_popup(master, 270,
                                                              140))

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
            tk.messagebox.showerror("Error", "Have you selected both files?\n\nIf problem persists, please see "
                                             "Richard.  Check coordinates are MGA 56 ")

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
        print(survey_config.fixed_file_dir)
        self.fixed_file_path = tk.filedialog.askopenfilename(parent=self.master,
                                                             initialdir=survey_config.fixed_file_dir,
                                                             title="Select file", filetypes=[("FIX Files", ".FIX")])
        if self.fixed_file_path != "":
            self.fixed_btn.config(text=os.path.basename(self.fixed_file_path))
            gui_app.menu_bar.compnet_working_dir = self.fixed_file_path
        self.dialog_window.lift()  # bring window to the front again

    def get_coordinate_file_path(self):
        self.coordinate_file_path = tk.filedialog.askopenfilename(parent=self.master,
                                                                  initialdir=os.path.dirname(
                                                                      survey_config.last_used_file_dir),
                                                                  title="Select file",
                                                                  filetypes=[("Coordinate Files", ".asc .CRD .STD")])
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
        current_compnet_dir = gui_app.menu_bar.compnet_working_dir

        self.std_file_path = tk.filedialog.askopenfilename(parent=self.master,
                                                           initialdir=current_compnet_dir,
                                                           title="Select file", filetypes=[("STD Files", ".STD")])
        if self.std_file_path != "":
            self.choose_btn.config(text=os.path.basename(self.std_file_path))

            gui_app.menu_bar.compnet_working_dir = os.path.dirname(self.std_file_path)

        self.dialog_window.lift()  # bring window to the front again

    def update_STD_file(self):

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


class UtilityCreateCSVFromASCWindow:

    def __init__(self, master):
        self.master = master

        self.last_used_directory = survey_config.last_used_file_dir

        #  Lets build the dialog box
        self.dialog_window = tk.Toplevel(master)
        self.dialog_window.title("CREATE TEMP CSV")

        container = tk.Frame(self.dialog_window, width=200, height=120)

        self.choose_btn = tk.Button(container, text="Choose *ASC File", command=self.create_csv_file)
        self.choose_btn.grid(row=1, column=1, sticky='nesw', padx=20, pady=20)
        container.pack(fill="both", expand=True)

        self.dialog_window.geometry(MainWindow.position_popup(master, 150, 70))

    def create_csv_file(self):

        asc_file_path = tk.filedialog.askopenfilename(parent=self.master,
                                                      initialdir=self.last_used_directory,
                                                      title="Select file", filetypes=[("ASC Files", ".ASC")])
        # Create the CSV
        csv_file = []
        csv_file.append("POINT,EASTING,NORTHING,ELEVATION\n")
        comma = ','

        # Get the coordinates from the ASC
        asc_coordinate_file = ASCCoordinateFile(asc_file_path)
        coordinate_dict = asc_coordinate_file.coordinate_dictionary

        for point, coordinates in sorted(coordinate_dict.items()):
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
        with open("temp_create_csv.csv", "w") as f:
            for line in csv_file:
                f.write(line)

        self.dialog_window.destroy()

        # Launch excel
        if asc_file_path:
            os.system("start EXCEL.EXE temp_create_csv.csv")


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

    # def center_screen(self):
    #
    #     dialog_w = 400
    #     dialog_h = 300
    #
    #     ws = self.master.winfo_width()
    #     hs = self.master.winfo_height()
    #     x = int((ws / 2) - (dialog_w / 2))
    #     y = int((hs / 2) - (dialog_w / 2))
    #
    #     return '{}x{}+{}+{}'.format(dialog_w, dialog_h, x, y)

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

        last_used_directory = survey_config.last_used_file_dir

        if file_path_number is 1:
            self.crd_file_path_1 = tk.filedialog.askopenfilename(parent=self.master, initialdir=last_used_directory,
                                                                 filetypes=[("CRD Files", ".CRD")])

            if self.crd_file_path_1 != "":
                self.crd_file_1_btn.config(text=os.path.basename(self.crd_file_path_1))
            self.dialog_window.lift()  # bring window to the front again

        elif file_path_number is 2:
            self.crd_file_path_2 = tk.filedialog.askopenfilename(parent=self.master, initialdir=last_used_directory,
                                                                 filetypes=[("CRD Files", ".CRD")])

            if self.crd_file_path_2 != "":
                self.crd_file_2_btn.config(text=os.path.basename(self.crd_file_path_2))
            self.dialog_window.lift()  # bring window to the front again
        else:
            tk.messagebox.showerror("Error", "No filepath no exists: " + str(file_path_number))

        if all([self.crd_file_path_1 != "", self.crd_file_path_2 != ""]):
            # enablebutton
            self.compare_crd_btn.configure(state=tk.NORMAL)


class CompnetStripNonControlShots:

    def __init__(self):

        self.outliers_dict = {}
        self.strip_non_control_shots()

    def strip_non_control_shots(self):

        # let user choose GSI file
        gsi_file_path = MenuBar.filename_path

        try:
            # create a new stripped GSI
            old_gsi = GSI(logger)
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
            # most likely incorrect GSI
            print(ex, type(ex))


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
        self.sorted_file_btn = tk.Button(self.dialog_window, text='CHANGE SORTING CONFIG FILE', state="disabled",
                                         command=self.open_config_file)
        current_config_label_txt = os.path.basename(survey_config.sorted_station_config)
        self.current_config_label = tk.Label(self.dialog_window, text=current_config_label_txt, state="disabled")
        self.files_btn = tk.Button(self.dialog_window, text="2)  CHOOSE GSI'S TO COMBINE       ",
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

        self.sorted_station_list_filepath = tk.filedialog.askopenfilename(parent=self.master, filetypes=[("TXT Files",
                                                                                                          ".txt")])
        if self.sorted_station_list_filepath != "":
            survey_config.update(SurveyConfiguration.section_config_files, 'sorted_station_config',
                                 self.sorted_station_list_filepath)
            self.current_config_label.config(text=os.path.basename(self.sorted_station_list_filepath))

        self.dialog_window.lift()  # bring window to the front again

    def select_and_combine_gsi_files(self):

        # determine sorting method
        radio_button_selection = self.radio_option.get()

        current_date = datetime.date.today().strftime('%d%m%y')

        combined_gsi_filename = "COMBINED_" + current_date + ".gsi"

        print(combined_gsi_filename)

        file_path = ""

        try:
            gsi_filenames = list(tk.filedialog.askopenfilenames(parent=self.master, initialdir = survey_config.todays_dated_directory, filetypes=[("GSI Files",
                                                                                                                                 ".gsi")]))
            if gsi_filenames:
                self.combined_gsi_directory = os.path.dirname(gsi_filenames[0])
                self.combined_gsi_file_path = os.path.join(self.combined_gsi_directory, combined_gsi_filename)

                for filename in gsi_filenames:
                    gsi_file = GSIFile(filename)
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
            tk.messagebox.showerror("Error", "Error combining files.\n\nIf problem persists see "
                                             "Richard")

        else:

            if gsi_filenames:
                tk.messagebox.showinfo("Success",
                                       "The gsi files have been combined:\n\n" + self.combined_gsi_file_path)
                # display results to the user
                MenuBar.filename_path = self.combined_gsi_file_path
                GUIApplication.refresh()
                gui_app.menu_bar.enable_menus()

                # close window
                self.dialog_window.destroy()

            else:
                pass

    def sort_alphabetically(self):

        sorted_filecontents = ""

        # create a temporary gsi

        unsorted_combined_gsi = GSI(logger)
        unsorted_combined_gsi.format_gsi(self.combined_gsi_file_path)

        # lets check and provide a warning to the user i
        stations_names_dict = unsorted_combined_gsi.get_list_of_control_points(unsorted_combined_gsi.formatted_lines)
        station_set = unsorted_combined_gsi.get_set_of_control_points()
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

        # stations_line_number_list = unsorted_combined_gsi.get_set_of_control_points()
        # sorted_stations_line_numbers = sorted(stations_line_number_list)

        # # old way but does not allow for duplicate stations which in theory shouldn't exist
        # for index, station_line_number in enumerate(sorted_stations_line_numbers):
        #
        #     line_number = int(station_line_number)
        #
        #     if index < (len(sorted_stations_line_numbers)-1):
        #
        #         for number in range(sorted_stations_line_numbers[index+1]-line_number):
        #
        #             sorted_filecontents += unsorted_combined_gsi_txt[line_number+int(number)]

        return sorted_filecontents

    def sort_by_config(self):

        sorted_filecontents = ""
        config_station_list = []
        stations_not_found_from_config_list = []

        # create a temporary gsi
        unsorted_combined_gsi = GSI(logger)
        unsorted_combined_gsi.format_gsi(self.combined_gsi_file_path)

        # lets check and provide a error to the user if station names in combine GSI contain a duplicate
        stations_names_dict = unsorted_combined_gsi.get_list_of_control_points(unsorted_combined_gsi.formatted_lines)
        station_set = unsorted_combined_gsi.get_set_of_control_points()

        if len(stations_names_dict) != len(station_set):
            # todo uncomment below
            pass
            # tk.messagebox.showwarning("WARNING", 'Warning - Duplicate station names detected in gsi!')

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
            if len(config_station_list) != len(set(config_station_list)):
                tk.messagebox.showwarning("WARNING", 'Warning - Duplicate station names detected in configuration file!')

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

        self.master.geometry(MainWindow.position_popup(self.master, 1100, 900))

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

        self.status_bar = StatusBar(master)
        self.menu_bar = MenuBar(master)
        self.main_window = MainWindow(master)
        self.status_bar.status.pack(side="bottom", fill="x")
        self.menu_bar.pack(side="top", fill="x")

        self.workflow_bar = WorkflowBar(self.main_window)
        self.list_box = ListBoxFrame(self.main_window)
        self.workflow_bar.pack(fill="x")
        self.list_box.pack(fill="both")
        self.main_window.pack(fill="both", expand=True)

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
    root.geometry("1600x1000")
    root.title("SURVEY ASSIST - Written by Richard Walter")
    root.wm_iconbitmap(r'icons\analyser.ico')

    survey_config = SurveyConfiguration()

    # Setup logger
    logger = logging.getLogger('Survey Assist')
    configure_logger()

    gsi = GSI(logger)
    gui_app = GUIApplication(root)
    database = GSIDatabase()



    root.mainloop()


def configure_logger():
    logger.setLevel(logging.ERROR)
    formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

    # Writes debug messages to the log
    file_handler = logging.FileHandler('Survey Assist.log')
    file_handler.setLevel(logging.ERROR)
    file_handler.setFormatter(formatter)

    # Display debug messages to the console
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.ERROR)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.info('Started Application')


if __name__ == "__main__":
    main()
