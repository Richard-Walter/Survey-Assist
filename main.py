#! python3

""" This program reads in a GSI file from a Leica 'Total Station' and displays the file
in a clearer, more user-friendly format.  You can then execute queries on this data to extract relevant information.
It also checks for survey errors in a survey, and contains some utilities to help with CompNet.

NOTE: For 3.4 compatibility
    i) Replaced f-strings with.format method.
    ii) had to use an ordered dictionary"""

# TODO check angles over 60 should go into muinutes/degrees, FL-FR highlight and tag errors based on tolerances
# TODO integrate Job diary/dated directory functionality
# TODO Create an extra gui bar: survey config, redisplay obs???  or can we let user seelct config if updating PC
# TODO automate the transfer of files of SD card to the job folder (know location based on created dated directory


import tkinter as tk
from tkinter import ttk
import logging.config
from tkinter import filedialog

import tkinter.messagebox
from GSI import *
from SurveyConfiguration import SurveyConfiguration
from GSI import GSIDatabase, CorruptedGSIFileError, GSIFile
from decimal import *

import datetime

from compnet import CRDCoordinateFile, ASCCoordinateFile, STDCoordinateFile, CoordinateFile, FixedFile
from utilities import *


class MenuBar(tk.Frame):
    filename_path = ""

    def __init__(self, master):
        super().__init__(master)

        self.master = master
        self.survey_config = SurveyConfiguration()
        self.query_dialog_box = None
        self.filename_path = ""
        self.compnet_working_dir = ""

        self.menu_bar = tk.Menu(self.master)
        self.master.config(menu=self.menu_bar)

        # File Menu
        file_sub_menu = tk.Menu(self.menu_bar, tearoff=0)
        file_sub_menu.add_command(label="Open...", command=self.choose_gsi_file)
        # file_sub_menu.add_command(label="Exit", command=self.client_exit)
        self.menu_bar.add_cascade(label="File", menu=file_sub_menu)

        # Edit menu
        self.edit_sub_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.edit_sub_menu.add_command(label="Delete all 2D Orientation Shots", command=self.delete_orientation_shots)
        self.edit_sub_menu.add_command(label="Change target height...", command=self.change_target_height)

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
        self.check_sub_menu.add_command(label="Compare Prism Constants to a similar survey...",
                                        command=self.compare_survey)
        self.menu_bar.add_cascade(label="Check Survey", menu=self.check_sub_menu, state="disabled")

        # Query menu
        self.query_sub_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.query_sub_menu.add_command(label="Query GSI...", command=self.display_query_input_box)
        self.query_sub_menu.add_command(label="Clear Query", command=self.clear_query)
        self.menu_bar.add_cascade(label="Query", menu=self.query_sub_menu, state="disabled")

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
        self.utility_sub_menu.add_command(label="Create temporary CSV from .ASC file",
                                          command=self.create_CSV_from_ASC)
        self.menu_bar.add_cascade(label="Utilities", menu=self.utility_sub_menu)

        # Config menu
        self.menu_bar.add_command(label="Config", command=self.configure_survey)

        # About menu
        self.menu_bar.add_command(label="About", command=self.display_about_dialog_box)

        # Exit menu
        self.menu_bar.add_command(label="Exit", command=self.client_exit)

    def choose_gsi_file(self):

        # global filename_path
        last_used_directory = survey_config.last_used_file_dir

        MenuBar.filename_path = tk.filedialog.askopenfilename(initialdir=last_used_directory, title="Select file",
                                                              filetypes=[("GSI Files", ".gsi")])
        survey_config.update(SurveyConfiguration.section_file_directories, 'last_used', os.path.dirname(
            MenuBar.filename_path))

        GUIApplication.refresh()
        self.enable_menus()

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
            tkinter.messagebox.showinfo("Checking Naming", error_text)


        except Exception:
            logger.exception('Error checking station naming')
            tk.messagebox.showerror("Error", 'Error executing this query:\nPlease contact the developer of this '
                                             'program or see log file for further information')

    def check_FLFR(self, display='YES'):

        error_line_number_list = []
        formatted_gsi_lines_analysis = []

        for gsi_line_number, line in enumerate(gsi.formatted_lines, start=0):
            if GSI.is_control_point(line):
                station_name = line['Point_ID']
                obs_from_staton_dict = gsi.get_all_shots_from_a_station_including_setup(station_name, gsi_line_number)
                analysed_lines, errors_by_line_number = self.anaylseFLFR(obs_from_staton_dict)

                # add the anaysis lines for this station
                for line in analysed_lines:
                    formatted_gsi_lines_analysis.append(line)

        if display == 'NO':  # don't display results to user - just a popup dialog to let them know there is an issue
            pass
        else:
            gui_app.list_box.populate(formatted_gsi_lines_analysis, error_line_number_list)

    def anaylseFLFR(self, obs_from_station_dict):

        precision = survey_config.precision_value

        # def AnalyseObservations(self, ObsDictA, ObsDictB):
        #     ResultList = collections.OrderedDict()
        #     for Code in ObAnalysisCodes:
        #         if not ObsDictA[Code] == '' and not ObsDictB[Code] == '':
        #             ValA = float(ObsDictA[Code])
        #             ValB = float(ObsDictB[Code])
        #             if Code == '21':
        #                 Result = AngularDifference(ValA, ValB, 180)
        #                 Result = self.ValueFormatter(str(Deci2DMS(Result, self.UnitType)), '22', True)
        #             elif Code == '22':
        #                 Result = AngularDifference(ValA, ValB, 360)
        #                 Result = self.ValueFormatter(str(Deci2DMS(Result, self.UnitType)), '22', True)
        #             else:
        #                 if self.UnitType in ['TDA', 'TS60']:
        #                     Result = round(max([ValA, ValB]) - min([ValA, ValB]), 4)
        #                 else:
        #                     Result = round(max([ValA, ValB]) - min([ValA, ValB]), 3)
        #                 if self.Limit_FLFR < Result: Result = '*' + str(Result)
        #         else:
        #             Result = ''
        #         ResultList[CODE_LIST[Code]] = Result
        #     return ResultList

        analysed_lines = []
        analysed_line_blank_values_dict = {'Point_ID': ' ', 'Timestamp': ' ', 'Horizontal_Angle': ' ',
                                           'Vertical_Angle': ' ', 'Slope_Distance': ' ',
                                           'Horizontal_Dist': ' ', 'Height_Diff': ' ', 'Prism_Constant': ' ',
                                           'Easting': ' ', 'Northing': ' ', 'Elevation': ' ', 'STN_Easting': '',
                                           'STN_Northing': '', 'STN_Elevation': '', 'Target_Height': ' ',
                                           'STN_Height': ' '}
        errors_by_line_number = []
        line_already_compared = -1

        for index, (line_number, formatted_line_dict) in enumerate(obs_from_station_dict.items(), start=1):

            obs_line_1_dict = formatted_line_dict
            obs_line_2_dict = None

            if GSI.is_control_point(formatted_line_dict):
                # dont analyse stn setup
                analysed_lines.append(formatted_line_dict)
                continue

            # check to see if line has already compared
            if line_number == line_already_compared:
                continue

            # if not at the end of the dictionary ( could use try except IndexError )
            length = len(obs_from_station_dict)
            if index < len(obs_from_station_dict):
                obs_line_2_dict = obs_from_station_dict[line_number + 1]

                # points match - lets analyse
                if obs_line_1_dict['Point_ID'] == obs_line_2_dict['Point_ID']:

                    for key, obs_line_1_field_value_str in obs_line_1_dict.items():

                        obs_line_2_field_value_str = obs_line_2_dict[key]

                        # default type
                        field_type = FIELD_TYPE_FLOAT
                        if key == 'Timestamp':
                            time_difference = get_time_differance(obs_line_1_field_value_str,
                                                                  obs_line_2_field_value_str)
                            obs_line_2_dict[key] = time_difference
                        elif key in ('Horizontal_Angle', 'Vertical_Angle'):
                            field_type = FIELD_TYPE_ANGLE
                            obs_line_1_field_value = get_numerical_value_from_string(obs_line_1_field_value_str,
                                                                                     field_type, precision)

                            obs_line_2_field_value = get_numerical_value_from_string(obs_line_2_field_value_str,
                                                                                     field_type, precision)
                            angular_diff = decimalize_value(angular_difference(obs_line_1_field_value,
                                                                               obs_line_2_field_value, 180), precision)
                            obs_line_2_dict[key] = GSI.format_angles(angle_decimal2DMS(angular_diff), precision)

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
                            if (obs_line_1_field_value!= "") and (obs_line_2_field_value!= ""):

                                float_diff_str = str(decimalize_value(obs_line_1_field_value - obs_line_2_field_value,
                                                                      precision))
                                obs_line_2_dict[key] = float_diff_str

                else:
                    analysed_lines.append(formatted_line_dict)
                    continue

                blank_line_dict = analysed_line_blank_values_dict.copy()
                blank_line_dict['Point_ID'] = obs_line_1_dict['Point_ID']
                analysed_lines.append(blank_line_dict)
                analysed_lines.append(obs_line_2_dict)
                line_already_compared = line_number + 1

            else:
                # end of the dictionary reached - do not analyse but add as it hasnt been compared
                analysed_lines.append(obs_line_1_dict)
                pass

        return analysed_lines, errors_by_line_number

    def check_3d_all(self):

        self.check_FLFR('NO')
        self.check_control_naming()
        self.check_3d_survey()

    def change_target_height(self):
        TargetHeightWindow(self.master)

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

    def configure_survey(self):

        global survey_config

        survey_config = SurveyConfiguration()

        ConfigDialogWindow(self.master)

    @staticmethod
    def clear_query():

        gui_app.list_box.populate(gsi.formatted_lines)

    def enable_menus(self):

        self.menu_bar.entryconfig("Query", state="normal")
        self.menu_bar.entryconfig("Check Survey", state="normal")
        self.menu_bar.entryconfig("Edit Survey", state="normal")

        # self.menu_bar.entryconfig("Compnet", state="normal")

    def disable_menus(self):

        self.menu_bar.entryconfig("Query", state="disabled")
        self.menu_bar.entryconfig("Check Survey", state="disabled")
        self.menu_bar.entryconfig("Edit Survey", state="disabled")

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
            survey_config.create_config_file(precision_dictionary, survey_tolerance_dictionary,
                                             configuration_dictionary)

            survey_config = SurveyConfiguration()

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
                    amended_filepath = MenuBar.filename_path + "_TgtUpdated.gsi"
                else:
                    amended_filepath = MenuBar.filename_path

                # create a new ammended gsi file
                with open(amended_filepath, "w") as gsi_file:
                    for line in gsi.unformatted_lines:
                        gsi_file.write(line)

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
        self.survey_config = SurveyConfiguration()
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
        print(self.survey_config.fixed_file_dir)
        self.fixed_file_path = tk.filedialog.askopenfilename(parent=self.master,
                                                             initialdir=self.survey_config.fixed_file_dir,
                                                             title="Select file", filetypes=[("FIX Files", ".FIX")])
        if self.fixed_file_path != "":
            self.fixed_btn.config(text=os.path.basename(self.fixed_file_path))
            gui_app.menu_bar.compnet_working_dir = self.fixed_file_path
        self.dialog_window.lift()  # bring window to the front again

    def get_coordinate_file_path(self):
        self.coordinate_file_path = tk.filedialog.askopenfilename(parent=self.master,
                                                                  initialdir=os.path.dirname(
                                                                      self.survey_config.last_used_file_dir),
                                                                  title="Select file",
                                                                  filetypes=[("Coordinate Files", ".asc .CRD .STD")])
        if self.coordinate_file_path != "":
            self.coord_btn.config(text=os.path.basename(self.coordinate_file_path))
        self.dialog_window.lift()  # bring window to the front again


class CompnetWeightSTDFileWindow:

    def __init__(self, master):
        self.master = master
        self.survey_config = SurveyConfiguration()

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
        self.survey_config = SurveyConfiguration()

        self.last_used_directory = self.survey_config.last_used_file_dir

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
            gsi_filenames = list(tk.filedialog.askopenfilenames(parent=self.master, filetypes=[("GSI Files", ".gsi")]))
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
        stations_names_dict = unsorted_combined_gsi.get_list_of_control_points()
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
        stations_names_dict = unsorted_combined_gsi.get_list_of_control_points()
        station_set = unsorted_combined_gsi.get_set_of_control_points()

        if len(stations_names_dict) != len(station_set):
            tk.messagebox.showwarning("WARNING", 'Warning - Duplicate station names detected in gsi!')

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
                tk.messagebox.showwarning("WARNING",
                                          'Warning - Duplicate station names detected in configuration file!')

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


class GUIApplication(tk.Frame):

    def __init__(self, master, *args, **kwargs):
        super().__init__(master, *args, **kwargs)

        self.status_bar = StatusBar(master)
        self.menu_bar = MenuBar(master)
        self.main_window = MainWindow(master)
        self.list_box = ListBoxFrame(self.main_window)

        self.status_bar.status.pack(side="bottom", fill="x")
        self.menu_bar.pack(side="top", fill="x")

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

    # Setup logger
    logger = logging.getLogger('Survey Assist')
    configure_logger()

    gsi = GSI(logger)
    gui_app = GUIApplication(root)
    database = GSIDatabase()

    survey_config = SurveyConfiguration()

    # Setup default survey configuration
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
