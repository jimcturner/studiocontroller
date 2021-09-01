#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# A python script to provide a simple HTTP UI to remote control a studio Mikrotik router
# James Turner 2021
import sys
import zipfile
import getopt
from validator_collection import validators, checkers, errors
import textwrap
from terminaltables import AsciiTable

# Tests the current Python interpreter version
def testPythonVersion(majorVersionNo, minorVersionNumber):
    # If the major and minor version number is not satisfied
    # i.e the installed version is < than majorVersionNo.minorVersionNumber (eg 3.6) it will
    # call exit() with an error message
    import sys
    # Get current Python version
    version = sys.version_info
    def printErrorMessage():
        print("You're not running a latest enough version of Python.\r")
        print("This is v" +\
              str(version[0]) + "." + str(version[1]) + ". This script requires at least v" +\
              str(majorVersionNo) + "." + str(minorVersionNumber) + "\r")
        print("\r")
        print("Hint: Python3 *might* be installed. Try re-running using 'python3 [args]'\r")
        print("or else, try python [tab] which (on OSX and Linux) should list the possible\r")
        print("versions of the Python interpreter installed on this system.\r")


    # print("you're running Python version " + str(int(version[0])) + "." + str(int(version[1])) + "\r")
    # Check major release version):
    if int(version[0]) < majorVersionNo:
        # Major version doesn't meet requirements
        printErrorMessage()
        return False
    else:
        # Major version is okay, now check minor version
        if int(version[1]) < minorVersionNumber:
            # Minor version doesn't meet requirements
            printErrorMessage()
            return False
        # Else Installed Python version satisfies minimum requirements
        return True

def retrieveFileFromArchive(archiveName, filepath, returnAsBytes=False, returnAsLines=False):
    try:
        with zipfile.ZipFile(archiveName) as zf:
            with zf.open(filepath) as f:
                if returnAsBytes:
                    # Return as a bytes object (return the imported file, untouched)
                    return f.read()
                elif returnAsLines:
                    # Return as a list of lines
                    return f.read().decode('utf-8').splitlines()
                else:
                    # Return as a contiguous string (containing newlines)
                    return f.read().decode('utf-8')


    except Exception as e:
        print(f"retrieveFileFromArchive() couldn't import {filepath} from {archiveName}, {type(e)}:{e}")

def main():
    # Specify the version number of this script
    thisVersion = "1.0"

    #### Check for minimum python version
    if (testPythonVersion(3, 8)):
        # Python version check passed
        pass

    else:
        # Python version not satisfied so exit
        exit(1)

    #### Python version validated, so now parse the command line arguments
    # Placeholder for the switches/args passed to this script
    argv = None

    # Create a dummy table in order to just get the max width of the *third* column (val will be used to wrap the text)
    columnMaxWidth = AsciiTable([["x:", "python-interpreter-path= ", "z"]]).column_max_width(2)

    # Specify the mandatory switches/long options that can (or should be) passed. Helptext will be used
    mandatorySwitches = [
        ["-c", "--config-file", '\n'.join(textwrap.wrap(
            f"The config file containing the mappings between the web gui buttons and the "
            f"corresponding Mikrotik scripts that should be run when they are pressed", columnMaxWidth))]
    ]
    # Specify any optional switches
    optionalSwitches = [["-h", "--help", '\n'.join(textwrap.wrap(f"Show help"))]]

    # Create an ascii table of mandatory switches that will be displayed as part of the help page
    table = AsciiTable(mandatorySwitches)
    table.title = "Mandatory args"
    table.inner_heading_row_border = False
    mandatorySwitchesFormattedAsTable = table.table

    # Create an ascii table of optional switches that will be displayed as part of the help page
    table = AsciiTable(optionalSwitches)
    table.title = "Optional args"
    table.inner_heading_row_border = False
    optionalSwitchesFormattedAsTable = table.table

    # Create an option string (from the first column of switches[] that can be passed to getopt
    # Note the ':' suffix (denotes to getopt that this switch will be followed by a value)
    getoptSwitches = "".join([f"{str(x[0]).replace('-', '')}:" for x in mandatorySwitches + optionalSwitches])
    # Create a long options list of strings (from the second column of switches[] that can be passed to getopt
    # Note the '=' suffix (denotes to getopt that this switch will be followed by a value)
    getoptLongOptions = [f"{str(x[1]).replace('--', '')}=" for x in mandatorySwitches + optionalSwitches]

    configFileName = None

    helpText = textwrap.dedent(f'''\
TL/DR This is a Python script to run Mikrotik scripts via a user friendly web gui

This is version v{thisVersion}

Arguments supplied: {argv}

{mandatorySwitchesFormattedAsTable}

{optionalSwitchesFormattedAsTable}
        ''')

    try:
        # Get the command line args (note: the first element as it only contains the name of this script)
        if len(sys.argv) < 1:
            print(f"ERR: ** No parameters supplied **\n\n"
                  f"{helpText}")
            exit(1)

        else:
            # Special case (display help)
            if sys.argv[1] == '-h' or sys.argv[1] == '--help':
                print(helpText)
                exit(0)

            print(f"Supplied args: {sys.argv[1:]}")
            # Parse the switches (and long parameters)
            opts, args = getopt.getopt(sys.argv[1:], getoptSwitches, getoptLongOptions)

            # iterate over all supplied options
            for opt, arg in opts:
                if opt in ("-c", "--config-file"):
                    if checkers.is_on_filesystem(arg):
                        configFileName = arg
                    else:
                        raise Exception(f"Supplied config-file doesn't exist: ({arg}).")
    except Exception as e:
        print(f"Error parsing args: {e}. \nUse -h or --help for help")
        exit(1)



    # Attempt to import an external data file from within the pyz zipped archive
    fileToImport = "index.html"
    try:

        print(f"Importing {fileToImport}")
        print(f"Imported file: {retrieveFileFromArchive(sys.argv[0], fileToImport)}")

    except Exception as e:
        print(f"couldn't import {fileToImport} from {sys.argv[0]}, {type(e)}:{e}")




    print ("DONE!!!!")



# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main()


