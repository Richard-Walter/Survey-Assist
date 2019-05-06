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
        self.query_sub_menu.add_command(label="Query GSI...", command=self.client_exit)
        self.query_sub_menu.add_command(label="Clear Query", command=self.client_exit)

        # create the Help object and command
        self.help_sub_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.help_sub_menu.add_command(label="About", command=self.display_about_dialog_box)

        # added "Query" and "Help" to our menu:  Query disabled until GSI file is loaded
        self.menu_bar.add_cascade(label="Query", menu=self.query_sub_menu, state="disabled")
        self.menu_bar.add_cascade(label="Help", menu=self.help_sub_menu)

    def browse_and_format_gsi_file(self):

        self.filename_path = tk.filedialog.askopenfilename()
        print(self.filename_path)

        try:

            gsi.format_gsi(self.filename_path)

            database.create_db()
            database.populate_table(gsi.formatted_lines)

            # Populate listBox
            gui_app.list_box.populate()

        except CorruptedGSIFileError:

            # Open Dialog warning of incorrect or corrupted GSI file
            tk.messagebox.showerror("Error", 'Error reading GSI File:\nIt appears this file is a corrupted or '
                                             'incorrect GSI file')
        except Exception:

            # Critical Error
            logger.exception('Critical Error has occurred')
            tk.messagebox.showerror("Critical Error", 'Critical Error has Occurred:\nCheck the log files or '
                                                      'contact author')

        self.enable_query_menu()

    @staticmethod
    def display_about_dialog_box():

        about_me_text = """Written by Richard Walter 2019\n\n Contact Chris Kelly for help\n\n                  haha"""

        tkinter.messagebox.showinfo("About GSI Query", about_me_text)

    def enable_query_menu(self):
        self.menu_bar.entryconfig("Query", state="normal")

    def disable_query_menu(self):
        self.query_sub_menu.entryconfig("Query", state="disabled")

    @staticmethod
    def client_exit():
        exit()


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
