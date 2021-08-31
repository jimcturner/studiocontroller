#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# A python script to provide a simple HTTP UI to remote control a studio Mikrotik router
# James Turner 2021
import sys
import getopt

# Tests the current Python interpreter version
import textwrap

from terminaltables import AsciiTable


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

def main():
    thisVersion = "1.0"
    print(f"Supplied Arguments: {sys.argv}")
    #### Check for minimum python version
    if (testPythonVersion(3, 9)):
        # Python version check passed
        pass

    else:
        # Python version not satisfied so exit
        exit(1)

    #### Now parse the command line arguments
        # Placeholder for the switches/args passed to this script
        argv = None

        # Create a dummy table in order to just get the max width of the *third* column (val will be used to wrap the text)
        columnMaxWidth = AsciiTable([["x:", "python-interpreter-path= ", "z"]]).column_max_width(2)

        # Specify the mandatory switches/long options that can (or should be) passed. Helptext will be used
        mandatorySwitches = [
            ["-c", "--config-file", '\n'.join(textwrap.wrap(
                f"The config file containing the mappings between the web gui buttons and the"
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
        TL/DR This is a  Python script to generate the necessary bash scripts to install 
        the isptest application on a Raspberry Pi (or similar Linux distro)

        This is version v{thisVersion}

        Arguments supplied: {argv}

        {mandatorySwitchesFormattedAsTable}

        {optionalSwitchesFormattedAsTable}
            ''')

        try:
            # Get the command line args but strip off the first element as it only contains the name of this script
            argv = sys.argv[1:]
            if len(argv) == 0:
                print(f"ERR: ** No parameters supplied **\n\n"
                      f"{helpText}")
                exit(1)

            else:
                # Special case (display help)
                if argv[0] == '-h' or argv[0] == '--help':
                    print(helpText)
                    exit(0)

                print(f"Supplied args: {argv}")
                # Parse the switches (and long parameters)
                opts, args = getopt.getopt(argv, getoptSwitches, getoptLongOptions)

                # iterate over all supplied options
                for opt, arg in opts:
                    if opt in ("-c", "--config-file"):
                        if checkers.is_on_filesystem(arg):
                            configFileName = arg
                        else:
                            raise Exception(f"Supplied config-file doesn't exist: ({arg}).")
        except Exception as e:
            ##### GOT HERE


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main()


