""" This program reads in a GSI file from a Leica Total Station and displays the file
in a clearer, more user-friendly format.  You can then execute database queries on this data"""

import tkinter as tk
from tkinter import filedialog
import tkinter.messagebox
from GSI import GSI
from GSIDatabase import GSIDatabase
from GSIExceptions import *
import sqlite3

# Create GSI and Database objects
gsi = GSI()
database = GSIDatabase(GSI.GSI_WORD_ID_DICT)

# TODO Add logging and unit testing


class MenuBar(tk.Frame):

    def __init__(self, master):

        # tk.Frame.__init__(self, master)
        super().__init__(master)
        self.master = master
        self.frame = tk.Frame(master)
        self.gsi = None

        self.filename_path = ""

        # creating a menu instance
        self.menu_bar = tk.Menu(self.master)
        self.master.config(menu=self.menu_bar)

        # create the file Menu with a command
        file_sub_menu = tk.Menu(self.menu_bar,  tearoff=0)
        file_sub_menu.add_command(label="Open...", command=self.browse_and_format_gsi_file)
        file_sub_menu.add_command(label="Exit", command=self.client_exit)

        # added "file" to our Main menu
        self.menu_bar.add_cascade(label="File", menu=file_sub_menu)

        # create the Query object and command
        self.query_sub_menu = tk.Menu(self.menu_bar,  tearoff=0)
        self.query_sub_menu.add_command(label="Query GSI...", command=self.client_exit)
        self.query_sub_menu.add_command(label="Clear Query", command=self.client_exit)

        # self.disable_query_menu()

        # added "Query" to our menu:  Disabled until GSI file is loaded
        self.menu_bar.add_cascade(label="Query", menu=self.query_sub_menu, state="disabled")

    # TODO add try catch logic for various scenarios
    def browse_and_format_gsi_file(self):

        self.filename_path = tk.filedialog.askopenfilename()
        print(self.filename_path)

        try:
            gsi.format_gsi(self.filename_path)
            database.create_db()
            database.create_table()
            database.populate_table(gsi.formatted_lines)

        except CorruptedGSIFileError:

            # Open Dialog warning of incorrect or corrupted GSI file
            tk.messagebox.showerror("Error", 'Error reading GSI File - It appears this file is a corrupted or '
                                            'incorrect GSI file')

        # except sqlite3.OperationalError:
        #
        #     # Most likely table GSI already exists


        self.enable_query_menu()

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

        # status_bar = tk.Label(master, text='Welcome to GSI Query', relief=tk.SUNKEN, anchor=tk.W)


class MainWindow(tk.Frame):

    def __init__(self, master):

        super().__init__(master)

        self.master = master
        self.frame = tk.Frame(master)


class GUIApplication(tk.Frame):

    def __init__(self, master, *args, **kwargs):

        super().__init__(master, *args, **kwargs)

        self.status_bar = StatusBar(master)
        self.menu_bar = MenuBar(master)
        self.main_window = MainWindow(master)

        self.status_bar.pack(side="bottom", fill="x")
        self.menu_bar.pack(side="top", fill="x")
        self.main_window.pack(fill="both", expand=True)


def main():

    # Create main window
    root = tk.Tk()
    root.geometry("1400x1000")
    root.title("GSI Query")
    root.wm_iconbitmap(r'icons\analyser.ico')
    GUIApplication(root).pack(side="top", fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
