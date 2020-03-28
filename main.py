#! python3

""" This program reads in a GSI file from a Leica 'Total Station' and displays the file
in a clearer, more user-friendly format.  You can then execute queries on this data to extract relevant information.
It also checks for survey errors in a survey, and contains some utilities to help with CompNet.

NOTE: For 3.4 compatibility
    i) Replaced f-strings with.format method.
    ii) had to use an ordered dictionary"""

# TODO add change target height
# TODO improve the display output when checking survey

import tkinter as tk
import re
import os
from tkinter import ttk
import logging.config
from tkinter import filedialog
from collections import Counter
from collections import OrderedDict

import tkinter.messagebox
from GSI import GSI
from SurveyConfiguration import SurveyConfiguration
from GSIDatabase import GSIDatabase
from GSIExceptions import *

import datetime

logger = logging.getLogger('Survey Assist')

gsi = None
database = GSIDatabase(GSI.GSI_WORD_ID_DICT, logger)

# This is the main GUI object that allows access to all the GUI's components
gui_app = None


class MenuBar(tk.Frame):
    filename_path = ""

    def __init__(self, master):
        super().__init__(master)

        self.master = master

        self.query_dialog_box = None
        self.filename_path = ""

        self.menu_bar = tk.Menu(self.master)
        self.master.config(menu=self.menu_bar)

        # File Menu
        file_sub_menu = tk.Menu(self.menu_bar, tearoff=0)
        file_sub_menu.add_command(label="Open...", command=self.choose_gsi_file)
        # file_sub_menu.add_command(label="Exit", command=self.client_exit)
        self.menu_bar.add_cascade(label="File", menu=file_sub_menu)

        # Query menu
        self.query_sub_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.query_sub_menu.add_command(label="Query GSI...", command=self.display_query_input_box)
        self.query_sub_menu.add_command(label="Clear Query", command=self.clear_query)
        self.menu_bar.add_cascade(label="Query", menu=self.query_sub_menu, state="disabled")

        # Check menu
        self.check_sub_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.check_sub_menu.add_command(label="Check Tolerances (3D only)",
                                        command=self.check_3d_survey)
        self.check_sub_menu.add_command(label="Check Control Naming (3D only) ", command=self.check_control_naming)
        self.check_sub_menu.add_command(label="Check All (3D only)",
                                        command=self.check_3d_all)
        self.check_sub_menu.add_separator()
        self.check_sub_menu.add_command(label="Compare Prism Constants to another survey ... ",
                                        command=self.compare_survey)
        self.menu_bar.add_cascade(label="Check Survey", menu=self.check_sub_menu, state="disabled")

        # Delete menu
        self.delete_sub_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.delete_sub_menu.add_command(label="All 2D Orientation Shots", command=self.delete_orientation_shots)
        self.menu_bar.add_cascade(label="Delete...", menu=self.delete_sub_menu, state="disabled")

        # Compnet menu
        self.compnet_sub_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.compnet_sub_menu.add_command(label="Update Fixed File...", command=self.update_fixed_file)
        self.compnet_sub_menu.add_command(label="Compare CRD Files...", command=self.compare_crd_files)
        self.compnet_sub_menu.add_command(label="Strip Non-control Shots", command=self.strip_non_control_shots)
        self.compnet_sub_menu.add_command(label="Combine/Re-order GSI Files", command=self.combine_gsi_files)

        self.menu_bar.add_cascade(label="Compnet", menu=self.compnet_sub_menu)

        # Config menu
        self.menu_bar.add_command(label="Config", command=self.configure_survey)

        # About menu
        self.menu_bar.add_command(label="About", command=self.display_about_dialog_box)

        # Exit menu
        self.menu_bar.add_command(label="Exit", command=self.client_exit)

    def choose_gsi_file(self):

        # global filename_path
        MenuBar.filename_path = tk.filedialog.askopenfilename(filetypes=[("GSI Files", ".gsi")])
        MenuBar.format_gsi_file()
        MenuBar.create_and_populate_database()
        MenuBar.update_gui()
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

        control_points = gsi.get_set_of_control_points()
        change_points = gsi.get_change_points()
        points = change_points + control_points

        print('CONTROL POINTS: ' + str(control_points))
        print('CHANGE POINTS: ' + str(change_points))
        print('POINTS: ' + str(points))

        sql_query_columns = 'Point_ID, Easting, Northing, Elevation'
        sql_where_column = 'Point_ID'

        sql_query_text = ""

        error_text = ""
        error_subject = "Error found in Survey"

        try:
            with database.conn:

                sql_query_text = "SELECT {} FROM GSI WHERE {}=?".format(sql_query_columns, sql_where_column)

                cur = database.conn.cursor()

                # Check if points are outisde of tolerance e.g. 10mm
                errors = []

                for point in points:

                    # create a list of eastings, northings and height and check min max value of each
                    eastings = []
                    northings = []
                    elevation = []
                    point_id = ""
                    error_text = ""

                    print('Survey mark is: ' + point)
                    cur.execute(sql_query_text, (point,))
                    rows = cur.fetchall()

                    for row in rows:
                        print(row)
                        point_id = row[0]

                        # create a list of eastings, northings and height and check min max value of each

                        if row[1] == '':
                            print(
                                'This line for point : ' + point + ' is probably a station setup.  Do not check tolerances for this point')

                        else:

                            eastings.append(row[1])
                            northings.append(row[2])
                            elevation.append(row[3])

                        # print(point_id, max(eastings), min(eastings), max(northings), min(northings), max(elevation),
                        #       min(elevation))

                    try:
                        # Check Eastings
                        east_diff = float(max(eastings)) - float(min(eastings))

                        if east_diff > float(survey_config.easting_tolerance):
                            error_text = 'Point ' + point_id + ' is out of tolerance: E ' + str(round(
                                east_diff,
                                3)) + 'm\n'
                            errors.append(error_text)
                            print(error_text)

                        # Check Northings
                        north_diff = float(max(northings)) - float(min(northings))

                        if north_diff > float(survey_config.northing_tolerance):
                            error_text = 'Point ' + point_id + ' is out of tolerance: N ' + str(round(
                                north_diff,
                                3)) + 'm\n'
                            errors.append(error_text)
                            print(error_text)

                        # Check Elevation
                        height_diff = float(max(elevation)) - float(min(elevation))

                        if height_diff > float(survey_config.height_tolerance):
                            error_text = 'Point ' + point_id + ' is out of tolerance in height: ' + \
                                         str(round(
                                             height_diff,
                                             3)) + 'm \n'
                            errors.append(error_text)
                            print(error_text)

                    except ValueError:
                        print('Value error at point : ' + point)
                        pass

                # display any error messages in pop up dialog

                error_text = ""

                for error in errors:
                    error_text += error

                if not errors:
                    error_text = "Survey is within the specified tolerance.  Well done!"
                    error_subject = "CHECKING SURVEY IS WITHIN TOLERANCE"

                # display error dialog box
                tkinter.messagebox.showinfo(error_subject, error_text)

        except Exception:
            logger.exception('Error creating executing SQL query:  {}'.format(sql_query_text))
            tk.messagebox.showerror("Error", 'Error executing this query:\nPlease contact the developer of this '
                                             'program or see log file for further information')

    def check_control_naming(self):

        station_setups = gsi.get_set_of_control_points()

        print('STATION SETUP LIST: ' + str(station_setups))

        # sql_query_columns = 'Point_ID'
        # sql_where_column = 'Point_ID'

        stn_shots_not_in_setup = []
        shots_to_stations = []

        line_number_errors = []
        error_text = ""
        error_subject = "POTENTIAL SURVEY ERROR"
        all_good_subject = "CHECKING FOR CONTROL NAMING MISTAKES"

        shots_to_stations_message = "The number of times each station was shot is shown below.\nIn most cases they " \
                                    "should be all even numbers:\n\n"

        line_number = 0

        try:
            # First, lets check all shots that are labelled 'STN' and make sure that it in the station setup list.
            for formatted_line in gsi.formatted_lines:

                line_number += 1
                point_id = formatted_line['Point_ID']

                # Check to see if this point is a shot to a STN
                if 'STN' in point_id:

                    # Check to see if this shot is in the list of station setups.
                    if point_id not in station_setups:
                        stn_shots_not_in_setup.append(point_id)
                        line_number_errors.append(line_number)

                    # Also want to track of how many times each station is shot so this info can be displayed to user
                    # check to see if point id is a station setup
                    if not formatted_line['STN_Easting']:
                        shots_to_stations.append(formatted_line['Point_ID'])

            print("STATION SHOTS THAT ARE NOT IN SETUP:")
            print(stn_shots_not_in_setup)

            print("COUNT OF SHOTS TO STATIONS:")
            print(Counter(shots_to_stations))

            # Display message to user of the station shots not found in station setups.
            if stn_shots_not_in_setup:

                error_text = "Possible point labelling error with the following control shots: \n\n"

                for shot in stn_shots_not_in_setup:
                    error_text += shot + "\n"

            print(error_text)

            if not error_text:
                error_text = "Control naming looks good!\n"
                error_subject = all_good_subject

            # Create and display no. of times each station was shot;'
            counter = Counter(shots_to_stations)
            for key, value in sorted(counter.items()):
                shots_to_stations_message += str(key) + '  ' + str(value) + '\n'

            error_text += '\n\n' + shots_to_stations_message

            # display error dialog box
            tkinter.messagebox.showinfo(error_subject, error_text)
            gui_app.list_box.populate(gsi.formatted_lines, line_number_errors)

        except Exception:
            logger.exception('Error checking station naming')
            tk.messagebox.showerror("Error", 'Error executing this query:\nPlease contact the developer of this '
                                             'program or see log file for further information')

    def check_3d_all(self):

        self.check_3d_survey()
        self.check_control_naming()

    def compare_survey(self):

        points_diff_PC_dict = {}

        old_survey_filepath = tk.filedialog.askopenfilename()
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

        QueryDialog(self.master)

    def update_fixed_file(self):

        CompnetUpdateFixedFileWindow(self.master)

    def compare_crd_files(self):

        CompnetCompareCRDFWindow(self.master)

    def strip_non_control_shots(self):

        CompnetStripNonControlShots()

    def combine_gsi_files(self):

        CombineGSIFilesWindow(self)

    def configure_survey(self):

        global survey_config

        survey_config = SurveyConfiguration()

        ConfigDialog(self.master)

    @staticmethod
    def clear_query():

        gui_app.list_box.populate(gsi.formatted_lines)

    def enable_menus(self):

        self.menu_bar.entryconfig("Query", state="normal")
        self.menu_bar.entryconfig("Check Survey", state="normal")
        self.menu_bar.entryconfig("Delete...", state="normal")
        # self.menu_bar.entryconfig("Compnet", state="normal")

    def disable_menus(self):

        self.menu_bar.entryconfig("Query", state="disabled")
        self.menu_bar.entryconfig("Check Survey", state="disabled")
        self.menu_bar.entryconfig("Delete...", state="disabled")

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

                for orientation_line_number in ListBox.orientation_line_numbers:
                    deleted_lines.append(line_list[int(orientation_line_number) - counter])

                    del line_list[int(orientation_line_number) - counter]
                    counter += 1

            # rewrite the line_list from list contents/elements:
            with open(MenuBar.filename_path, "w") as gsi_file:
                for line in line_list:
                    gsi_file.write(line)

            print("deleted lines are: \n\n" + str(deleted_lines))

            # rebuild database and GUI
            MenuBar.format_gsi_file()
            MenuBar.update_database()
            MenuBar.update_gui()

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


class ConfigDialog:
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

        self.precision_entry.current(SurveyConfiguration.precision_value_list.index(survey_config.precision_value))
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
        self.sorted_station_file_btn.grid(row=4, column=1, padx=5, pady=10, sticky='w')

        save_b = tk.Button(self.dialog_window, text="Save", width=10, command=self.save)
        save_b.grid(row=5, column=0, padx=5, pady=20, sticky='nesw')

        cancel_b = tk.Button(self.dialog_window, text="Cancel", width=10, command=self.cancel)
        cancel_b.grid(row=5, column=1, padx=5, pady=20, sticky='nesw')

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
            ConfigDialog(self.master)
        else:

            self.dialog_window.destroy()
            survey_config.create_config_file(precision_dictionary, survey_tolerance_dictionary,
                                             configuration_dictionary)

            survey_config = SurveyConfiguration()

    def cancel(self):

        self.dialog_window.destroy()


class QueryDialog:

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
            QueryDialog(self.master)
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


class ListBox(tk.Frame):
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
        ListBox.orientation_line_numbers = []

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
                ListBox.orientation_line_numbers.append(line_number)

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
        MenuBar.format_gsi_file()
        MenuBar.update_database()
        MenuBar.update_gui()


class CompnetUpdateFixedFileWindow:
    coordinate_file_path = ""
    fixed_file_path = ""

    def __init__(self, master):

        self.master = master
        self.outliers_dict = {}

        #  Lets build the dialog box
        self.dialog_window = tk.Toplevel(master)
        self.dialog_window.title("Compnet Assist")

        container = tk.Frame(self.dialog_window, width=100, height=100)

        # Update Fixed File GUI
        self.update_fixed_file_lbl = tk.Label(container, text='\nUPDATE FIXED FILE\n', font=('Helvetica',
                                                                                             14, 'bold'))
        self.fixed_btn = tk.Button(container, text='(1) Choose Fixed File: ', command=self.get_fixed_file_path)
        self.coord_btn = tk.Button(container, text='(2) Choose Coordinate File: ',
                                   command=self.get_coordinate_file_path)
        self.update_btn = tk.Button(container, text='(3) UPDATE FIXED FILE ', command=self.update_fixed_file)
        # self.fixed_result_lbl = tk.Label(container, text=' ', font=('Helvetica',
        #                                                             12, 'bold'))
        # self.blank_lbl = tk.Label(self.dialog_window, text='')

        self.update_fixed_file_lbl.grid(row=0, column=1, padx=50, pady=2)
        self.fixed_btn.grid(row=1, column=1, sticky='nesw', padx=25, pady=3)
        self.coord_btn.grid(row=2, column=1, sticky='nesw', padx=25, pady=3)
        self.update_btn.grid(row=3, column=1, sticky='nesw', padx=25, pady=3)
        # self.fixed_result_lbl.grid(row=4, sticky='nesw', column=1, padx=25, pady=15)

        container.pack(fill="both", expand=True)

        self.dialog_window.geometry(MainWindow.position_popup(master, 300,
                                                              220))

    def update_fixed_file(self):

        try:

            # open up fixed file & update the fixed file's easting/northings from the coordinate file
            fixed_file = FixedFile(self.fixed_file_path)
            coordinate_file = CoordinateFile(self.coordinate_file_path)
            stations_updated = fixed_file.update(coordinate_file)
            stations_not_updated = set(fixed_file.get_stations()).difference(stations_updated)

        except Exception as ex:
            print(ex, type(ex))
            tk.messagebox.showerror("Error", "Have you selected both files?\n\nIf problem persists, please see "
                                             "Richard.  Check coordinates are MGA 56 ")

        else:

            msg_body = str(len(stations_updated)) + ' station coordinates have been updated.\n\n'

            if stations_updated:  # display to user

                for station in stations_updated:
                    msg_body += station + '\n'

            if stations_not_updated:  # display to user

                msg_body += '\nWARNING: The following fixed file stations were not found in the coordintate file:\n\n'

                for station in stations_not_updated:
                    msg_body += station + '\n'

            tkinter.messagebox.showinfo("Update Fixed File", msg_body)

    def get_fixed_file_path(self):
        self.fixed_file_path = tk.filedialog.askopenfilename(parent=self.master, filetypes=[("FIX Files", ".FIX")])
        if self.fixed_file_path != "":
            self.fixed_btn.config(text=os.path.basename(self.fixed_file_path))
        self.dialog_window.lift()  # bring window to the front again

    def get_coordinate_file_path(self):
        self.coordinate_file_path = tk.filedialog.askopenfilename(parent=self.master, filetypes=[("Coordinate Files",
                                                                                                  ".asc .CRD .STD")])
        if self.coordinate_file_path != "":
            self.coord_btn.config(text=os.path.basename(self.coordinate_file_path))
        self.dialog_window.lift()  # bring window to the front again


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
        self.entry_tolE.insert(tk.END, '0.005')

        self.tolN_lbl = tk.Label(self.dialog_window, text='Tolerance N: ')
        self.entry_tolN = tk.Entry(self.dialog_window)
        self.entry_tolN.insert(tk.END, '0.005')

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

        print(tol_E, tol_N)

        common_points = []
        uncommon_points = []

        try:

            # open up the two CRD files and compare common values for outliers
            coordinate_file1 = CoordinateFile(self.crd_file_path_1)
            coordinate_file2 = CoordinateFile(self.crd_file_path_2)

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
                    self.outliers_dict[point] = "  Easting: " + '{0:.3f}'.format(round(diff_E, 3))
                if abs(diff_N) > tol_N:
                    self.outliers_dict[point] = "  Northing: " + '{0:.3f}'.format(round(diff_N, 3))

        except Exception as ex:
            print(ex, type(ex))
            # self.compare_result_lbl.config(text='ERROR - See Richard\n')
            tk.messagebox.showerror("Error", ex)

        else:

            # self.compare_result_lbl.config(text='SUCCESS')

            # display results to user
            # msg_header = "EASTING TOLERANCE = " + str(tol_E) + "\nNORTHING TOLERANCE = " + str(tol_N) +"\n\n"

            msg_body = 'POINTS THAT EXCEED TOLERANCE:\n\n'

            if self.outliers_dict:
                for point in sorted(self.outliers_dict, key=lambda k: k):
                    msg_body += point + ': ' + self.outliers_dict[point] + '\n'
            else:  # no outliers
                msg_body = " \nThere are no points that exceed the specified tolerance\n"

            # Display to the user points that are uncommon
            if uncommon_points:

                msg = '\n\nTHE FOLLOWING POINTS WERE NOT FOUND IN THE 2ND FILE\n\n'
                for point in uncommon_points:
                    msg += point + '\n'

                msg_body += msg

            top = tk.Toplevel()
            top.title("COMPARE CRD's")
            # top.geometry('400x600')

            msg = tk.Message(top, text=msg_body)
            msg.grid(row=1, column=1, padx=30, pady=10)

    def get_crd_file_path(self, file_path_number):

        if file_path_number is 1:
            self.crd_file_path_1 = tk.filedialog.askopenfilename(parent=self.master, filetypes=[("CRD Files", ".CRD")])

            if self.crd_file_path_1 != "":
                self.crd_file_1_btn.config(text=os.path.basename(self.crd_file_path_1))
            self.dialog_window.lift()  # bring window to the front again

        elif file_path_number is 2:
            self.crd_file_path_2 = tk.filedialog.askopenfilename(parent=self.master, filetypes=[("CRD Files", ".CRD")])

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
            MenuBar.format_gsi_file()
            MenuBar.create_and_populate_database()
            MenuBar.update_gui()
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
        self.dialog_window.title("COMBINE GSI FILES")

        self.radio_option = tk.StringVar()
        self.radio_option.set("1")
        self.radio_no_sort = tk.Radiobutton(self.dialog_window, text="Don't Sort", value="1",
                                            var=self.radio_option, command=self.disable_config_button)
        self.radio_sort_auto = tk.Radiobutton(self.dialog_window, text="Sort alphabetically", value="2",
                                              var=self.radio_option, command=self.disable_config_button)
        self.radio_sort_config = tk.Radiobutton(self.dialog_window, text="Sort based on config file", value="3",
                                                var=self.radio_option, command=self.enable_config_button)
        self.sorted_file_btn = tk.Button(self.dialog_window, text='Change sorted config file', state="disabled",
                                         command=self.open_config_file)
        current_config_label_txt = os.path.basename(survey_config.sorted_station_config)
        self.current_config_label = tk.Label(self.dialog_window, text=current_config_label_txt, state="disabled")
        self.files_btn = tk.Button(self.dialog_window, text='Choose GSI files to combine/re-order',
                                   command=self.select_and_combine_gsi_files)

        self.radio_no_sort.grid(row=1, column=1, sticky='w', columnspan=3, padx=60, pady=(20, 2))
        self.radio_sort_auto.grid(row=2, column=1, sticky='w', columnspan=3, padx=60, pady=2)
        self.radio_sort_config.grid(row=3, column=1, sticky='w', columnspan=3, padx=60, pady=(2, 10))
        self.sorted_file_btn.grid(row=4, column=1, sticky='w', columnspan=3, padx=60, pady=(10, 2))
        self.current_config_label.grid(row=5, column=1, sticky='w', columnspan=3, padx=60, pady=(1, 2))
        self.files_btn.grid(row=6, column=1, sticky='nesw', columnspan=3, padx=60, pady=(20, 20))

        self.dialog_window.geometry(MainWindow.position_popup(master, 280,
                                                              240))
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
                MenuBar.format_gsi_file()
                MenuBar.create_and_populate_database()
                MenuBar.update_gui()
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

        # Todo refactor this method passing stations sorted by name and unsorted_combined_gsi
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


class GUIApplication(tk.Frame):

    def __init__(self, master, *args, **kwargs):
        super().__init__(master, *args, **kwargs)

        self.status_bar = StatusBar(master)
        self.menu_bar = MenuBar(master)
        self.main_window = MainWindow(master)
        self.list_box = ListBox(self.main_window)

        self.status_bar.status.pack(side="bottom", fill="x")
        self.menu_bar.pack(side="top", fill="x")

        self.main_window.pack(fill="both", expand=True)


class FixedFile:

    def __init__(self, fixed_file_path):

        self.fixed_file_path = fixed_file_path
        self.fixed_file_contents = None
        self.station_list = []
        self.updated_file_contents = ""

        with open(fixed_file_path, 'r') as f_orig:
            self.fixed_file_contents = f_orig.readlines()

    def get_stations(self):
        for line in self.fixed_file_contents:
            station = FixedFile.get_station(line)
            if station != "UNKNOWN":
                self.station_list.append(station)
        return self.station_list

    @staticmethod
    def get_station(line):

        station = "UNKNOWN"

        # Line number is at the start of a string and contains digits followed by whiespace
        re_pattern = re.compile(r'"\w+"')
        match = re_pattern.search(line)

        # strip of quotation marks and add to station list
        if match is not None:
            station = match.group()[1:-1]

        return station

    @staticmethod
    def get_line_number(line):

        line_number = "???"

        # Line number is at the start of a line
        re_pattern = re.compile(r'^\d+\s')

        match = re_pattern.search(line)

        if match:
            line_number = match.group().strip()

        return line_number

    # updates the fixed file and returns a list of stations that were found and updated in the coordinate file
    def update(self, coordinate_file):

        stations_updated = []

        for line in self.fixed_file_contents:

            # Get coordinates for this station if exists in the coordinate file
            station = self.get_station(line)

            coordinate_dict = coordinate_file.get_point_coordinates(station)

            # update fixed_file coordinate if a match was found
            if coordinate_dict:
                easting = coordinate_dict['Eastings']
                northing = coordinate_dict['Northings']

                updated_line = self.get_line_number(line) + ' ' + easting + '  ' + northing + ' "' + station + '"\n'
                self.updated_file_contents += updated_line
                stations_updated.append(station)

            else:
                self.updated_file_contents += line

        # update fixed file with updated contents
        with open(self.fixed_file_path, 'w') as f_update:
            f_update.write(self.updated_file_contents)

        return stations_updated


class CoordinateFile:
    re_pattern_easting = re.compile(r'\b\d{6}\.\d{4}')
    re_pattern_northing = re.compile(r'\b\d{7}\.\d{4}')
    re_pattern_point_crd = re.compile(r'\b\S+\b')
    re_pattern_point_std = re.compile(r'"\S+"')
    re_pattern_point_asc = re.compile(r'@#\S+')

    def __init__(self, coordinate_file_path):

        self.file_contents = None
        self.coordinate_dictionary = {}

        try:
            with open(coordinate_file_path, 'r') as f_orig:

                self.file_contents = f_orig.readlines()

        except Exception as ex:
            print(ex, type(ex))

        else:

            # remove first 12 lines which contain header text if it is a CRD file
            # remove the first 10 to check 'DESCRIPTION' exists in the header
            if coordinate_file_path[-3:] == 'CRD':
                del self.file_contents[0: 10]
                if 'DESCRIPTION' in self.file_contents[0]:

                    # remove 'description' line plus following blank space'
                    del self.file_contents[0:2]

                else:
                    raise Exception('CRD file Header should contain only 12 rows')

                # build coordinate dictionary
                self.build_coordinate_dictionary('CRD')

            elif coordinate_file_path[-3:] == 'STD':

                # build coordinate dictionary
                self.build_coordinate_dictionary('STD')

            # remove first 12 lines which contain header text if it is a CRD file
            # remove the first 10 to check '@%Projection set' exists in the header
            elif coordinate_file_path[-3:] == 'asc':
                del self.file_contents[0: 3]
                if '@%Projection set' in self.file_contents[0]:
                    del self.file_contents[0]
                # build coordinate dictionary
                else:
                    raise Exception('Unsupported file type')

                self.build_coordinate_dictionary('ASC')

    def get_point_coordinates(self, point):

        if point in self.coordinate_dictionary.keys():
            return self.coordinate_dictionary[point]

    def build_coordinate_dictionary(self, file_type):

        for coordinate_contents_line in self.file_contents:

            point_coordinate_dict = {}
            point_match = None

            try:
                # grab easting and northing for this station
                easting_match = self.re_pattern_easting.search(coordinate_contents_line)
                northing_match = self.re_pattern_northing.search(coordinate_contents_line)

                if file_type == 'CRD':

                    point_match = self.re_pattern_point_crd.search(coordinate_contents_line)

                elif file_type == 'STD':

                    point_match = self.re_pattern_point_std.search(coordinate_contents_line)

                elif file_type == 'ASC':

                    point_match = self.re_pattern_point_asc.search(coordinate_contents_line)

                point_name = point_match.group()
                point_name = point_name.replace('"', '')  # for *STD files
                point_name = point_name.replace('@#', '')  # for *asc files

                point_coordinate_dict['Eastings'] = easting_match.group()
                point_coordinate_dict['Northings'] = northing_match.group()

                self.coordinate_dictionary[point_name] = point_coordinate_dict

            except ValueError:
                # probabaly a blank line
                pass
            except Exception as ex:
                print(ex)


class GSIFile:

    def __init__(self, gsi_file_path):
        self.fixed_file_path = gsi_file_path
        self.gsi_file_contents = None

        with open(gsi_file_path, 'r') as f_orig:
            self.gsi_file_contents = f_orig.read()
            print(self.gsi_file_contents)

    def get_filecontents(self):
        return self.gsi_file_contents


def configure_logger():
    logger.setLevel(logging.ERROR)
    formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

    # Writes debug messages to the log
    file_handler = logging.FileHandler('GSIQuery.log')
    file_handler.setLevel(logging.ERROR)
    file_handler.setFormatter(formatter)

    # Display debug messages to the console
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.ERROR)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.info('Started Application')


def main():
    global gui_app
    global gsi
    global survey_config

    # Setup logger
    configure_logger()

    # Create main window
    root = tk.Tk()
    root.geometry("1600x1000")
    root.title("SURVEY ASSIST - Written by Richard Walter")
    root.wm_iconbitmap(r'icons\analyser.ico')

    gsi = GSI(logger)
    gui_app = GUIApplication(root)

    survey_config = SurveyConfiguration()

    # Setup default survey configuration
    root.mainloop()


if __name__ == "__main__":
    main()
