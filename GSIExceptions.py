# GSI Query user-defined exceptions


class CorruptedGSIFileError(Exception):

    """Raised when a GSI file can't be read properly"""

    def __init__(self, msg="GSI file can't be read properly"):

        # Error message thrown is saved in msg
        self.msg = msg
