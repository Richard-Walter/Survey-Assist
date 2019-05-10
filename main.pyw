""" This program reads in a GSI file from a Leica Total Station and displays the file
in a clearer, more user-friendly format.  You can then execute database queries on this data"""

import tkinter as tk
from tkinter import ttk
import logging.config
from tkinter import filedialog
import tkinter.messagebox
from GSI import GSI
from GSIDatabase import GSIDatabase
from GSIExceptions import *
import threading

# logger = logging.getLogger(__name__)
logger = logging.getLogger('GSIQuery')

# Create GSI and Database objects
gsi = GSI(logger)
database = GSIDatabase(GSI.GSI_WORD_ID_DICT, logger)

gui_app = None


class MenuBar(tk.Frame):

    def __init__(self, master):

        # tk.Frame.__init__(self, master)
        super().__init__(master)
        self.master = master
        self.frame = tk.Frame(master)
        # self.gsi = None
        self.query_dialog_box = None

        self.filename_path = ""

        # creating a menu instance
        self.menu_bar = tk.Menu(self.master)
        self.master.config(menu=self.menu_bar)

        # create the file Menu with a command
        file_sub_menu = tk.Menu(self.menu_bar, tearoff=0)
        file_sub_menu.add_command(label="Open...", command=self.browse_and_format_gsi_file)
        file_sub_menu.add_command(label="Exit", command=self.client_exit)

        # added "file" to our Main menu
        self.menu_bar.add_cascade(label="File", menu=file_sub_menu)

        # create the Query object and command
        self.query_sub_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.query_sub_menu.add_command(label="Query GSI...", command=self.display_query_input_box)
        self.query_sub_menu.add_command(label="Clear Query", command=self.clear_query)

        # create the Help object and command
        self.help_sub_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.help_sub_menu.add_command(label="About", command=self.display_about_dialog_box)

        # added "Query" and "Help" to our menu:  Query disabled until GSI file is loaded
        self.menu_bar.add_cascade(label="Query", menu=self.query_sub_menu, state="disabled")
        self.menu_bar.add_cascade(label="Help", menu=self.help_sub_menu)

    def browse_and_format_gsi_file(self):

        self.filename_path = tk.filedialog.askopenfilename()

        gui_app.status_bar.status['text'] = 'Working ...'

        try:

            gsi.format_gsi(self.filename_path)

            database.create_db()
            database.populate_table(gsi.formatted_lines)

            # update the GUI
            gui_app.list_box.populate(gsi.formatted_lines)
            gui_app.status_bar.status['text'] = self.filename_path
            self.enable_query_menu()

        except FileNotFoundError:

            # Do nothing: User has hit the cancel button
            gui_app.status_bar.status['text'] = 'Please choose a GSI File'

        except CorruptedGSIFileError:

            # Open Dialog warning of incorrect or corrupted GSI file
            tk.messagebox.showerror("Error", 'Error reading GSI File:\nIt appears this file is a corrupted or '
                                             'incorrect GSI file')

            gui_app.status_bar.status['text'] = 'Please choose a GSI File'

        except Exception:

            # Critical Error
            logger.exception('Critical Error has occurred')
            tk.messagebox.showerror("Critical Error", 'Critical Error has Occurred:\nCheck the log files or '
                                                      'contact author')

    def display_query_input_box(self):

        QueryDialog(self.master)

    @staticmethod
    def clear_query():

        gui_app.list_box.populate(gsi.formatted_lines)

    def enable_query_menu(self):
        self.menu_bar.entryconfig("Query", state="normal")

    def disable_query_menu(self):
        self.query_sub_menu.entryconfig("Query", state="disabled")

    @staticmethod
    def display_about_dialog_box():

        about_me_text = """Written by Richard Walter 2019\n\n Contact Chris Kelly for help :)\n\n """
        tkinter.messagebox.showinfo("About GSI Query", about_me_text)

    @staticmethod
    def client_exit():
        exit()


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

        self.column = tk.StringVar()
        self.column_entry = ttk.Combobox(self.dialog_window, width=18, textvariable=self.column, state='readonly')
        self.column_entry['values'] = gsi.column_names
        self.column_entry.bind("<<ComboboxSelected>>", self.column_entry_cb_callback)
        self.column_entry.grid(row=1, column=1, padx=5, pady=5)

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

        return f'{dialog_w}x{dialog_h}+{x}+{y}'

    def column_entry_cb_callback(self, event):

        # Set the values for the column_value combobox now that the column has been decided
        self.column_value_entry['values'] = sorted(set(self.get_column_values(self.column_entry.get())))

        print(f"Sorted unique column values are:  {self.column_value_entry['values']}")
        self.column_value_entry.config(state='readonly')

    # TODO this method probably best put in GSI class

    @staticmethod
    def get_column_values(column_name):

        column_values = []

        for line in gsi.formatted_lines:

            try:
                # column_value = line['Prism_Constant']
                column_value = line[column_name]
                column_values.append(column_value)
            except KeyError:
                pass  # column value doesn't exist for this line...continue

        return column_values

    def ok(self):

        column_entry = self.column_entry.get()
        column_value_entry = self.column_value_entry.get()

        if column_entry is "":
            tkinter.messagebox.showinfo("GSI Query", "Please enter valid search data")
            logger.info(
                f"Invalid query data entered.  Column Name was {column_entry}: column value was {column_value_entry}")
            # re-display query dialog
            QueryDialog(self.master)
            return

        query_results = self.execute_sql_query(database.TABLE_NAME, column_entry,column_value_entry)

        self.dialog_window.destroy()

        # Re-populate List Box with results
        if query_results is not None:

            print(query_results)

            # Remove any previous data first
            gui_app.list_box.list_box_view.delete(*gui_app.list_box.list_box_view.get_children())

            for query_result in query_results:
                gui_app.list_box.list_box_view.insert("", "end", values=query_result)

    def cancel(self):
        self.dialog_window.destroy()

    @staticmethod
    def execute_sql_query(database_table, column_name, column_value):
        sql_query_text = f'SELECT * FROM {database_table} WHERE {column_name}="{column_value}"'

        try:
            with database.conn:

                cur = database.conn.cursor()
                cur.execute(sql_query_text)
                rows = cur.fetchall()

                for row in rows:
                    print(row)

            return rows

        except Exception:
            logger.exception(f'Error creating executing SQL query:  {sql_query_text}')
            tk.messagebox.showerror("Error", 'Error executing this query:\nPlease contact the developer of this '
                                             'program')


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

    def __init__(self, master):
        super().__init__(master)

        self.master = master

        # Use Treeview to create list of survey shots
        self.list_box_view = ttk.Treeview(master, columns=gsi.column_names, selectmode='browse', show='headings')

        # Add scrollbar
        vsb = ttk.Scrollbar(self.list_box_view, orient='vertical', command=self.list_box_view.yview)
        vsb.pack(side='right', fill='y')
        hsb = ttk.Scrollbar(self.list_box_view, orient='horizontal', command=self.list_box_view.xview)
        hsb.pack(side='bottom', fill='x')
        self.list_box_view.configure(yscrollcommand=vsb.set)
        self.list_box_view.configure(xscrollcommand=hsb.set)

        # set column headings
        for column_name in gsi.column_names:
            self.list_box_view.heading(column_name, text=column_name)
            self.list_box_view.column(column_name, width=120, stretch=False)

            # On mouse-click event
        self.list_box_view.bind('<Button-1>', self.selected_row)

        # self.list_box.grid(row=1, column=0, columnspan=2)
        self.list_box_view.pack(fill="both", expand=True)

    def populate(self, formatted_lines):

        # Remove any previous data first
        self.list_box_view.delete(*self.list_box_view.get_children())

        # Build Display List which expands on the formatted lines from GSI class containing value for all fields
        for formatted_line in formatted_lines:

            tag = ""

            complete_line = []

            # iterate though column names and find value, assign value if doesnt exist and append to complete list
            for column_name in gsi.column_names:
                # empty string if column doesn't exist
                gsi_value = formatted_line.get(column_name, "")
                complete_line.append(gsi_value)

                # add STN tag if line is a station setup
                if column_name == gsi.GSI_WORD_ID_DICT['84']:  # A station setupt must contain value for STN_easting
                    tag = 'STN'
            # add complete line
            self.list_box_view.insert("", "end", values=complete_line, tags=(tag,))
            # print(complete_line)

    def selected_row(self, a):

        cur_item = self.list_box_view.focus()
        print(self.list_box_view.item(cur_item)['values'])


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
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

    file_handler = logging.FileHandler('GSIQuery.log')
    file_handler.setLevel(logging.ERROR)
    file_handler.setFormatter(formatter)

    # Display debug messages to the console
    stream_handler = logging.StreamHandler()
    # stream_handler.setLevel(logging.INFO)
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
    root.geometry("1936x1000")
    root.title("GSI Query")
    root.wm_iconbitmap(r'icons\analyser.ico')
    gui_app = GUIApplication(root)
    root.mainloop()
    logger.info('Application Ended')


if __name__ == "__main__":
    main()
