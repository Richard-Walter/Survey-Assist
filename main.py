""" This program reads in a GSI file from a Leica Total Station and displays the file
in a clearer, more user-friendly format.  You can then execute queries on this data"""

import os
import GSI

test_file_names = ['A9_ARTC_902_2.GSI', 'ERROR.GSI', 'HCCUL180219.GSI']

os.chdir('.\\GSI Files')

# TODO:  add database functinoality

gsi = GSI.GSI(test_file_names[2])



