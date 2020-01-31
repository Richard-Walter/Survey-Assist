#! python3

""" This program reads in a GSI file from a Leica 'Total Station' and displays the file
in a clearer, more user-friendly format.  You can then execute queries on this data to extract relevant information.
It also checks for survey errors in a 3D survey.

NOTE: For 3.4 compatibility
    i) Replaced f-strings with.format method.
    ii) had to use an ordered dictionary"""

import tkinter as tk
from tkinter import ttk
import logging.config
from tkinter import filedialog
from collections import Counter

import tkinter.messagebox
from GSI import GSI
from GSIDatabase import GSIDatabase
from GSIExceptions import *

logger = logging.getLogger('GSIQuery')
gsi = GSI(logger)
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
        self.menu_bar.add_cascade(label="Query", menu=self.query_sub_menu, state="disabled")  # disabled initially

        # Check menu
        self.check_sub_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.check_sub_menu.add_command(label="Check Tolerances", command=self.check_3d_survey)
        self.check_sub_menu.add_command(label="Check Control Naming ", command=self.check_control_naming)

        self.menu_bar.add_cascade(label="3D Survey", menu=self.check_sub_menu, state="disabled")  # disabled
        # initially

        # Delete menu
        self.check_sub_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.check_sub_menu.add_command(label="All 2D Orientation Shots", command=self.delete_orientation_shots)
        self.menu_bar.add_cascade(label="Delete...", menu=self.check_sub_menu, state="disabled")  # disabled
        # initially

        # Help menu
        self.help_sub_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.help_sub_menu.add_command(label="About", command=self.display_about_dialog_box)
        self.menu_bar.add_cascade(label="Help", menu=self.help_sub_menu)

        # Exit menu
        self.menu_bar.add_command(label="Exit", command=self.client_exit)

    def choose_gsi_file(self):

        # global filename_path
        MenuBar.filename_path = tk.filedialog.askopenfilename()
        MenuBar.format_gsi_file()
        MenuBar.create_and_populate_database()
        MenuBar.update_gui()
        self.enable_query_menu()
        self.enable_3d_survey_menu()
        self.enable_delete_menu()

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

        control_points = gsi.get_control_points()
        change_points = gsi.get_change_points()
        points = change_points + control_points

        print('CONTROL POINTS: ' + str(control_points))
        print('CHANGE POINTS: ' + str(change_points))
        print('POINTS: ' + str(points))

        sql_query_columns = 'Point_ID, Easting, Northing, Elevation'
        sql_where_column = 'Point_ID'

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

                        if east_diff > 0.007:
                            error_text = 'Point ' + point_id + ' is out of tolerance: E ' + str(round(
                                east_diff,
                                3)) + 'm\n'
                            errors.append(error_text)
                            print(error_text)

                        # Check Northings
                        north_diff = float(max(northings)) - float(min(northings))

                        if north_diff > 0.007:
                            error_text = 'Point ' + point_id + ' is out of tolerance: N ' + str(round(
                                north_diff,
                                3)) + 'm\n'
                            errors.append(error_text)
                            print(error_text)

                        # Check Elevation
                        height_diff = float(max(elevation)) - float(min(elevation))

                        if height_diff > 0.015:
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
                    error_text = "Survey looks good!"
                    error_subject = "3D Survey Tolerance Analysis"

                # display error dialog box
                tkinter.messagebox.showinfo(error_subject, error_text)

        except Exception:
            logger.exception('Error creating executing SQL query:  {}'.format(sql_query_text))
            tk.messagebox.showerror("Error", 'Error executing this query:\nPlease contact the developer of this '
                                             'program or see log file for further information')

    def check_control_naming(self):

        station_setups = gsi.get_control_points()

        print('STATION SETUP LIST: ' + str(station_setups))

        sql_query_columns = 'Point_ID'
        sql_where_column = 'Point_ID'

        stn_shots_not_in_setup = []
        shots_to_stations = []

        line_number_errors = []
        error_text = ""
        error_subject = "POTENTIAL SURVEY ERROR"
        all_good_subject = "3D SURVEY"

        shots_to_stations_message = "The number of times each station was shot is shown below:\n\n"

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

    def display_query_input_box(self):

        QueryDialog(self.master)

    @staticmethod
    def clear_query():

        gui_app.list_box.populate(gsi.formatted_lines)

    def enable_query_menu(self):

        self.menu_bar.entryconfig("Query", state="normal")

    def enable_3d_survey_menu(self):

        self.menu_bar.entryconfig("3D Survey", state="normal")

    def enable_delete_menu(self):

        self.menu_bar.entryconfig("Delete...", state="normal")

    def disable_delete_menu(self):

        self.menu_bar.entryconfig("Delete...", state="normal")

    def disable_query_menu(self):

        self.query_sub_menu.entryconfig("Query", state="disabled")

    def disable_3d_survey_menu(self):

        self.query_sub_menu.entryconfig("3D Survey", state="disabled")

    @staticmethod
    def display_about_dialog_box():

        about_me_text = "Written by Richard Walter 2019\n\n This program reads a GSI file from a Leica Total " \
                        "Station and displays the data in a clearer, more user-friendly format." \
                        " \n\nYou can then execute queries on this data to extract relevant information, or check for" \
                        " errors in a 3D the survey, such as incorrect station labelling and tolerance errors. \n\n"

        tkinter.messagebox.showinfo("About GSI Query", about_me_text)

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


class QueryDialog:

    def __init__(self, master):

        self.master = master

        #  Lets build the dialog box
        self.dialog_window = tk.Toplevel(master)
        self.dialog_window.title("SQL Query")

        self.dialog_window.geometry(self.center_screen())

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

    def center_screen(self):

        dialog_w = 350
        dialog_h = 150

        ws = self.master.winfo_width()
        hs = self.master.winfo_height()
        x = int((ws / 2) - (dialog_w / 2))
        y = int((hs / 2) - (dialog_w / 2))

        return '{}x{}+{}+{}'.format(dialog_w, dialog_h, x, y)

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

                # for row in rows:
                #    print(row)

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
        self.status = tk.Label(master, text='Welcome to GSI Query', relief=tk.SUNKEN, anchor=tk.W)


class MainWindow(tk.Frame):

    def __init__(self, master):
        super().__init__(master)

        self.master = master


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
        self.list_box_view = ttk.Treeview(master, columns=self.treeview_column_names, selectmode='browse',
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
        self.list_box_view.bind('<Delete>', self.delete_selected_row)

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

    def delete_selected_row(self, event):

        line_number_values = self.list_box_view.item(self.list_box_view.focus(), 'values')

        if line_number_values:

            print("row to be deleted is " + line_number_values[0])

            # # delete row from list_box_view
            # self.list_box_view.delete(self.list_box_view.focus())

            # remove line from gsi, update database and rebuild list view
            print("removing line from GSI and rebuilding treeview")

            try:

                with open(MenuBar.filename_path, "r") as gsi_file:

                    line_list = list(gsi_file)  # puts all lines in a list

                del line_list[int(line_number_values[0]) - 1]  # delete regarding element

                # rewrite the line_list from list contents/elements:
                with open(MenuBar.filename_path, "w") as gsi_file:
                    for line in line_list:
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

            # rebuild database and GUI
            MenuBar.format_gsi_file()
            MenuBar.update_database()
            MenuBar.update_gui()


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

    # Setup logger
    configure_logger()

    # Create main window
    root = tk.Tk()
    root.geometry("1600x1000")
    root.title("GSI Query")
    root.wm_iconbitmap(r'icons\analyser.ico')
    gui_app = GUIApplication(root)
    root.mainloop()
    logger.info('Application Ended')


if __name__ == "__main__":
    main()
