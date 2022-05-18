class FormatException(Exception):
    def __init__(self, line, lineNumber, messagePrefix):
        self.line = line.strip()
        self.lineNumber = lineNumber
        self.message = messagePrefix + "\n" + "Please check line {0}:'{1}'".format(lineNumber, line)
        super().__init__(self.message)
        


class NoZPosMatch(FormatException):
    def __init__(self, line, lineNumber, message="Could not find the value for Z Position in a valid format"):
        super().__init__(line, lineNumber, message)

class NoHeightMatch(FormatException):
    def __init__(self, line, lineNumber, message="Could not find the value for Height in a valid format"):
        super().__init__(line, lineNumber, message)

class NotVerbose(FormatException):
    def __init__(self, line, lineNumber, message="Could not find comments, the GCODE if probably not verbose"):
        super().__init__(line, lineNumber, message)

