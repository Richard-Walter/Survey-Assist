class GSIFile:

    def __init__(self, gsi_file_path):
        self.fixed_file_path = gsi_file_path
        self.gsi_file_contents = None

        with open(gsi_file_path, 'r') as f_orig:
            self.gsi_file_contents = f_orig.read()
            print(self.gsi_file_contents)

    def get_filecontents(self):
        return self.gsi_file_contents
