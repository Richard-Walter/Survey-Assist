""" This program reads in a GSI file from a Leica Total Station and displays the file
in a clearer, more user-friendly format.  You can then execute database queries on this data"""

import tkinter as tk
import os


# TODO Add logging and unit testing


class MenuBar(tk.Frame):

    def __init__(self, master):

        tk.Frame.__init__(self, master)

        self.master = master
        self.frame = tk.Frame(master)

        # creating a menu instance
        menu = tk.Menu(self.master)
        self.master.config(menu=menu)

        # create the file Menu with a command
        file = tk.Menu(menu,  tearoff=0)
        file.add_command(label="Open...", command=self.client_exit)
        file.add_command(label="Exit", command=self.client_exit)

        # added "file" to our Main menu
        menu.add_cascade(label="File", menu=file)

        # create the Query object and command
        query = tk.Menu(menu,  tearoff=0)
        query.add_command(label="Query GSI...", command=self.client_exit)

        # added "file" to our menu
        menu.add_cascade(label="Query", menu=query)

    @staticmethod
    def client_exit():
        exit()


class StatusBar(tk.Frame):

    def __init__(self, master):

        tk.Frame.__init__(self, master)

        self.master = master
        self.frame = tk.Frame(master)

        status_bar = tk.Label(master, text='Welcome to GSI Query', relief=tk.SUNKEN, anchor=tk.W)


class MainWindow(tk.Frame):

    def __init__(self, master):

        tk.Frame.__init__(self, master)

        self.master = master
        self.frame = tk.Frame(master)


class GUIApplication(tk.Frame):

    def __init__(self, master, *args, **kwargs):

        tk.Frame.__init__(self, master, *args, **kwargs)

        self.master = master
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


# db = GSIDatabase()

# Test files
test_file_names = ['A9_ARTC_902_2.GSI', 'ERROR.GSI', 'HCCUL180219.GSI']
os.chdir('.\\GSI Files')
# gsi = GSI(test_file_names[2], db)




