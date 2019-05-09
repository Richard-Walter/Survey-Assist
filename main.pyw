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
from tkinter import simpledialog

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
        self.query_sub_menu.add_command(label="Clear Query", command=self.client_exit)

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
            gui_app.list_box.populate()
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

        global logger

        query_dialog_box = QueryDialog(self.master)

        # sql_query = simpledialog.askstring("Input", "Please enter an SQL Query statement", parent=self.master,
        #                                    initialvalue="whateveryouwant")

        # sql_query = query_dialog_box.sql_entry_text
        #
        # print(sql_query)
        # logger.info('SQL Query: ' + sql_query)

    def enable_query_menu(self):
        self.menu_bar.entryconfig("Query", state="normal")

    def disable_query_menu(self):
        self.query_sub_menu.entryconfig("Query", state="disabled")

    @staticmethod
    def display_about_dialog_box():

        about_me_text = """Written by Richard Walter 2019\n\n Contact Chris Kelly for help\n\n                  haha"""
        tkinter.messagebox.showinfo("About GSI Query", about_me_text)

    @staticmethod
    def client_exit():
        exit()


class QueryDialog:

    def __init__(self, master):

        self.sql_entry_text = ""

        #  Lets build the dialog box
        self.dialog_window = tk.Toplevel(master)
        self.dialog_window.title("SQL Query")
        self.dialog_window.geometry("350x150")

        tk.Label(self.dialog_window, text="Lets build an SQL 'where' statement:").grid(row=0, padx=5, pady=5)
        tk.Label(self.dialog_window, text="Select column:").grid(row=1, sticky="W", padx=5, pady=5)
        tk.Label(self.dialog_window, text="Enter a column value:").grid(row=2, sticky="W", padx=5, pady=2)

        self.column = tk.StringVar()
        self.column_entry = ttk.Combobox(self.dialog_window, width=12, textvariable=self.column, state='readonly')
        self.column_entry['values'] = (1, 2, 4, 42, 100)
        self.column_entry.grid(row=1, column=1, padx=5, pady=5)
        # self.column_entry.current(0)

        self.column_value = tk.StringVar()
        self.column_value_entry = ttk.Combobox(self.dialog_window, width=12, textvariable=self.column_value,
                                               state='readonly')
        self.column_entry['values'] = (0, 11,22, 33, 44)
        self.column_value_entry.grid(row=2, column=1, padx=5, pady=2)
        # self.column_entry.current(0)

        ok_b = tk.Button(self.dialog_window, text="OK", command=self.ok)
        ok_b.grid(row=3, column=0, pady=10)

        cancel_b = tk.Button(self.dialog_window, text="Cancel", command=self.cancel)
        cancel_b.grid(row=3, column=1, pady=10)

    def ok(self):

        self.sql_entry_text = self.column_entry.get() + " " + self.column_value_entry.get()

        print("SQL text is", self.sql_entry_text)
        logger.info('SQL Query: ' + self.sql_entry_text)

        self.dialog_window.destroy()

    def cancel(self):
        self.sql_entry_text = ""
        self.dialog_window.destroy()


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
        self.list_box = ttk.Treeview(master, columns=gsi.column_names, selectmode='browse', show='headings')

        # Add scrollbar
        vsb = ttk.Scrollbar(self.list_box, orient='vertical', command=self.list_box.yview)
        vsb.pack(side='right', fill='y')
        hsb = ttk.Scrollbar(self.list_box, orient='horizontal', command=self.list_box.xview)
        hsb.pack(side='bottom', fill='x')
        self.list_box.configure(yscrollcommand=vsb.set)
        self.list_box.configure(xscrollcommand=hsb.set)

        # set column headings
        for column_name in gsi.column_names:
            self.list_box.heading(column_name, text=column_name)
            self.list_box.column(column_name, width=120, stretch=False)

            # On mouse-click event
        self.list_box.bind('<Button-1>', self.selected_row)

        # self.list_box.grid(row=1, column=0, columnspan=2)
        self.list_box.pack(fill="both", expand=True)

    def populate(self):

        # Remove any previous data first
        self.list_box.delete(*self.list_box.get_children())

        # Build Display List which expands on the formatted lines from GSI class containing value for all fields
        for formatted_line in gsi.formatted_lines:

            complete_line = []

            # iterate though column names and find value, assign value if doesnt exist and append to complete list
            for column_name in gsi.column_names:
                # empty string if column doesn't exist
                gsi_value = formatted_line.get(column_name, "")
                complete_line.append(gsi_value)

            # add complete line
            self.list_box.insert("", "end", values=complete_line)
            print(complete_line)

    def selected_row(self, a):

        cur_item = self.list_box.focus()
        print(self.list_box.item(cur_item)['values'])


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
