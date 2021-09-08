#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# A python script to provide a simple HTTP UI to remote control a studio Mikrotik router
# James Turner 2021
import datetime
import os
import shlex
import signal
import socket
import subprocess
import sys
import threading
import time
import zipfile
import getopt
from validator_collection import validators, checkers, errors
import textwrap
from terminaltables import AsciiTable


from HTTPServerSuite import HttpServerCreator, HTTPRequestHandlerRTP, HTTPTools


# Custom Exception used to trigger/detect a shutdown request (via SIGINT or SIGKILL)
class Shutdown(Exception):
    pass

# Provides a means of controlling a Mikroktik router by passing in commands via ssh
class SSHController(object):
    def __init__(self, deviceIpAddress, username, password=None, tcpPort=22) -> None:
        super().__init__()
        self.deviceIpAddress = deviceIpAddress
        self.tcpPort = tcpPort
        self.username = username
        self.password = password


    # Sends a command to a device (Mikrotik router) via SSH
    # Optionally, if it receives a response back from the device, it will call the callback method specified in onSuccess
    # with the router response and time in the form on (response)

    # If the onFailure callback method is specified, this will be called if an Exception is raised

    # NOTE: By default this method is blocking unless callbackMethod is set, in which case ssh will be called as
    # a seperate thread and execution will return immediately back to the caller

    # NOte: This works from the command line: ssh kabulctrl@192.168.3.2 ':put "$[/system clock get time]"'
    # Tested using the following:
    # sendCommand(':put "$[/system clock get time], $[/system clock get date]";/tool traceroute address=8.8.8.8 count=1')
    # Note: Because the Mikrotik command itself contains double quotes, single quotes were used ot wrap the string passed
    # to sendCommand()
    def sendCommand(self, commandString, timeout=5, onSuccess=None, onFailure=None):
        try:
            # Create the command string that would be written on the command line
            # NOTE: commandString is enclosed in single quotes
            cmds = f"ssh {self.username}@{self.deviceIpAddress} '{commandString}'"
            # Split the string using shlex.split() into a list of args compatible with subprocess.check_output
            args = shlex.split(cmds)
            if onSuccess is None:
                # Simply run the command and return the response to the caller
                # Note this will be a blocking call, as the target will have to respond OR the timeout
                # expire before execution returns to the caller
                response = subprocess.check_output(args, timeout=timeout)
                return response
            else:
                # Otherwise run the command in a separate thread. This will make the method non-blocking
                # When the target does respond, the response will be sent back by calling the method
                # specified in callbackMethod
                def runAsThread():
                    # Run the command
                    try:
                        response = subprocess.check_output(args, timeout=timeout)
                        # Send the response back to the caller via its callback method
                        onSuccess(response)
                    except Exception as e:
                        if onFailure is not None:
                            # Trap the Exception and pass it back to the caller
                            onFailure(e)

                # Run the command as a seperate thread
                threading.Thread(target=runAsThread, args=()).start()
                return None
        except Exception as e:
            raise Exception(f"SSHController.sendCommand() commandString: {commandString}, error: {e}")



class PublicHTTPRequestHandler(HTTPRequestHandlerRTP):
    def apiGETEndpoints(self):
        try:
            getMappings = {}
            self.addEndpoint(getMappings, "", self.renderIndexPage, contentType='text/html')
            self.addEndpoint(getMappings, "api", self.renderApiIndexPage, contentType='text/html')
            self.addEndpoint(getMappings, "api/sshcmd", self.sendCommandViaSSH, contentType='text/html',
                             requiredKeys=["deviceAddress", "username", "commandString"])
            return getMappings
        except Exception as e:
            raise Exception(f"apiGETEndpoints(), {e}")

    def apiPOSTEndpoints(self):
        # Access parent object via server attribute
        parent = self.server.parentObject
        try:
            postMappings = {}
            # Sample POST endpoints inherited from isptest code. Left here by way of an example
            # self.addEndpoint(postMappings, "log", self.addMessageToLog, requiredKeys=["message"], optionalKeys=["logToDisk"])
            # self.addEndpoint(postMappings, "alert", self.alertUser, requiredKeys=["title", "body"])
            return postMappings
        except Exception as e:
            raise Exception(f"apiPOSTEndpoints() {e}")


    def apiDELETEEndpoints(self):
        # Access parent object via server attribute
        parent = self.server.parentObject
        try:
            deleteMappings = {}
        except Exception as e:
            raise Exception(f"apiDELETEEndpoints() {e}")
        return deleteMappings

    def renderApiIndexPage(self):
        # Access parent object via server attribute
        parent = self.server.parentObject
        try:
            body = f"<h1>Index page for studiocontroller API (@{parent.listenAddr}:{parent.listenPort})</h1>"\
                           f"{self.listEndpoints()}"
            response = self.htmlWrap(title=f"Index page for studiocontroller API (@{parent.listenAddr}:{parent.listenPort})",
                                     body=body)
            return response
        except Exception as e:
            raise Exception(f"renderIndexPage() {parent.__class__.__name__}({self.client_address}), {e}")

    def renderIndexPage(self):
        # Access parent object via server attribute
        parent = self.server.parentObject
        try:
            # Attempt to import the index.html page
            htmlFile = importFile("html/index.html", archiveName=parent.externalResourcesDict["pyzArchiveName"])
            ### Insert any dynamic content
            # Get a handle on the dict containing the button-to-script mappings
            controllerDefinitions = parent.externalResourcesDict["controllerDefinitions"]
            htmlFile = HTTPTools.insertAfter(htmlFile, "<currentTime>", datetime.datetime.now().strftime("%H:%M:%S"))

            # Populate the javascript
            infoText = "<!-- Generated by studiocontroller.py:PublicHTTPRequestHandler.renderIndexPage() -->\n"

            # Create a series of auto-running javascript processes that will poll the scripts defined in
            # controllerDefinitions["statusFieldMappings"]. The resultant javascript code will be inserted into the
            # registerPollers() method (the skeleton of which is declared in html/index.html
            # Dynamically render the registerPollers() code for all status fields defined in controllerDefinitions["statusFieldMappings"]
            registerPollersJS = f"\nwindow.setInterval(sendCmd, " \
                                f"{controllerDefinitions['statusFieldMappings'][1]['polling_interval_ms']}, " \
                                f"'{controllerDefinitions['deviceAddress']}', " \
                                f"'{controllerDefinitions['deviceSshUsername']}', " \
                                f"'{controllerDefinitions['statusFieldMappings'][1]['target_cmd_string']}', " \
                                f"'{controllerDefinitions['statusFieldMappings'][1]['id']}');"

            # Iterates over controllerDefinitions['statusFieldMappings'] creating a line of javascript for each
            # field listed. If the "polling_interval_ms" or "target_cmd_string" keys are None, the field will
            # be ignored.
            # Returns a list of strings, each of which is a line of valid javascript registering an
            # autotimes Javascript function call
            def renderPollertJS():
                try:
                    pollersJS = []
                    for field in controllerDefinitions['statusFieldMappings']:
                        # Check to see if this field is to be registered as one that will auto-refresh
                        if field["target_cmd_string"] is not None and field["polling_interval_ms"] is not None:
                            # This is an auto-refreshing field
                            pollersJS.append(f"\nwindow.setInterval(sendCmd, " \
                                f"{field['polling_interval_ms']}, " \
                                f"'{controllerDefinitions['deviceAddress']}', " \
                                f"'{controllerDefinitions['deviceSshUsername']}', " \
                                f"'{field['target_cmd_string']}', " \
                                f"'{field['id']}');")
                    # Return the list of javascript strings (one for each of the (not-being-ignored) status fields)
                    return pollersJS
                except Exception as e:
                    raise Exception(f"renderPollertJS() {e}")


            # Render a list of javascript window.setInterval() method calls for each of the statusFieldMappings
            registerPollersJS = "\n".join(renderPollertJS())

            # Insert the javascript method code into the html template
            htmlFile = HTTPTools.insertAfter(htmlFile, "##INSERT_POLLERS", registerPollersJS)

            # Create the status fields defined in controllerDefinitions["statusFieldMappings"] (as an HTML table)
            statusFieldHTML = '<table border="1"> ' + "\n".join([
                f"""<tr><td>{field["label"]}</td><td style="min-width:200px" id="{field["id"]}">&nbsp;</td></tr>"""
                for field in controllerDefinitions["statusFieldMappings"]
            ]) + "</table>"
            # Insert the status fields into the html
            htmlFile = HTTPTools.insertAfter(htmlFile, "<statusFields>", statusFieldHTML)

            # Create html for all buttons defined in controllerDefinitions["buttonScriptMappings"]
            # These will call a javascript method: sendCmd(targetAddr, username, commandString, destFieldID)
            # as previously defined in html/index.html
            buttonsHtml = infoText + "\n".join([
                                                   f"""<button onclick="sendCmd('{controllerDefinitions['deviceAddress']}', '{controllerDefinitions['deviceSshUsername']}', '{button["target_cmd_string"]}', '{button["response_field_id"]}')">{button["label"]}</button>"""
                                                   for button in controllerDefinitions["buttonScriptMappings"]])

            htmlFile = HTTPTools.insertAfter(htmlFile, "<routerSelectors>", buttonsHtml)

            return htmlFile
        except Exception as e:
            raise Exception(f"renderIndexPage() {parent.__class__.__name__}({self.client_address}), {e}, {type(e)}")

    def sendCommandViaSSH(self, deviceAddress, username, commandString):
        try:
            # Create a device
            rtr = SSHController(deviceAddress, username)
            # Send the commandString to the device
            response = rtr.sendCommand(commandString)
            # return f"Device response of type {type(response)}: {response.decode('utf-8')}"
            return response.decode('utf-8')

        except Exception as e:
            raise Exception(f"sendCommandViaSSH() {e}")


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

# Extracts a file from a zip archive
# Based on an answer here: https://stackoverflow.com/a/62604682
# Allows non-python files incorporated into the zipapp .pyz archive to be extracted at run-time
# If returnAsBytes==True, the imported file will be returned as a bytestring
# elif returnAsLines==True, the the imported file will have it's newlines stripped and each line returned as a list
# else (default) the imported file will be returned as a UTF8 string
# Ascii can be returned if the function is called with returnStringType='ascii'
def retrieveFileFromArchive(archiveName, filepath, returnAsBytes=False, returnAsLines=False, returnStringType='utf-8'):
    try:
        with zipfile.ZipFile(archiveName) as zf:
            with zf.open(filepath) as f:
                if returnAsBytes:
                    # Return as a bytes object (return the imported file, untouched)
                    return f.read()
                elif returnAsLines:
                    # Return as a list of lines
                    return f.read().decode(returnStringType).splitlines()
                else:
                    # Return as a contiguous string (containing newlines)
                    return f.read().decode(returnStringType)
    except Exception as e:
        raise Exception(f"retrieveFileFromArchive() couldn't import {filepath} from {archiveName}, {type(e)}:{e}")

# Utility method to import a file from disk
# if returnAsLines==True, the the imported file will have it's newlines stripped and each line returned as a list
# else (default) the imported file will be returned as a UTF8 string
def importFileFromDisk(filepath, returnAsLines=False):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            if returnAsLines:
                # Return as a list of lines
                return f.read().splitlines()
            else:
                # Return as a bytes object (return the imported file, untouched)
                return f.read()

    except Exception as e:
        raise Exception(f"importFileFromDisk() {e}")

# This is a wrapper for retrieveFileFromArchive() and importFileFromDisk()
# It's purpose is to retrieve a requested file either from the file system, or (if archiveName is not None),
# from a zipped archive (which is expected to be an executable Python archive created by zipapp)
# (i.e. archiveName is the name of a zip archive (or path) that *does* exist in the filesystem
# WHY BOTHER:
#   The distribution version of studiocontroller will be parcelled up using zipapp into a single executable archive file
# (with a .pyz extension). To aid development, it would also be helpful to be able to retrieve non-archived files that
# are saved normally in the files system.
#   This function will therefore determine the location of the requested file to allow the callers of this method
#   'not to care' how or where it came from
def importFile(filepath, archiveName=None, returnAsLines=False):
    try:
    # # Attempt to import an external data file from within the pyz zipped archive
    # Or, if that fails, just get the file from the file system in the usual way
    # fileToImport = "index.html"
        try:
            # Attempt, in the first instance to locate and import the file located in archiveName
            return retrieveFileFromArchive(archiveName, filepath, returnAsLines=returnAsLines)
        except Exception as e:
            logToFile(f"importFile() retrieveFileFromArchive failed for file {filepath} in archive {archiveName}. "
                      f"Trying importFileFromDisk() method instead")
            # Importing from an archive failed, so see if the file can be imported from the file system
            try:
                return importFileFromDisk(filepath, returnAsLines=returnAsLines)
            except Exception as e2:
                raise Exception(f"retrieveFileFromArchive() failed with error ({e}), so did importFileFromDisk() ({e2})")
    except Exception as e:
        raise Exception(f"importFile() {e}")

# Function to monitor the existing log file size to if they've reached the threshold. If so, rename them
# to a new file with a date added to the filename. The file extension will be preserved
# Returns True is archival occurred (i.e source file was larger than the threshold), False if not, or
# raises an Exception on error
def archiveLogs(file, maxSize):
    # Determine size of existing log file
    # check to see if the file exists at all
    if os.path.isfile(file):
        # File does exist, so check the size
        try:
            if os.path.getsize(file) > maxSize:
                # separate the filename and the extension
                nameNoExtension, fileExtension = os.path.splitext(file)
                # File is larger than the max threshold so rename it
                archivedFilenameSuffix = "_ending_at_" + datetime.datetime.now().strftime("%d-%m-%y_%H-%M-%S")
                os.rename(file, nameNoExtension+archivedFilenameSuffix+fileExtension)
                # Message.addMessage("Auto archived " + file)
                return True
            else:
                return False
        except Exception as e:
            # Message.addMessage("ERR:Utils.archiveLogs() " + str(e))
            raise Exception("archiveLogs() " + str(e))
            # return None
    else:
        return None


# Appends logMessage to logfileName
# If the log file gets larger than logfileMaxSize_MB, it will be automatically archived
def logToFile(logMessage, logfileName="studiocontroller_log.txt", logfileMaxSize_MB=1):
    try:
        timeNow = datetime.datetime.now().strftime('%d/%m/%y %H:%M:%S')
        print(f"{timeNow}: {logMessage}")
        # Check the filesize before writing. If too large, archive it
        archiveLogs(logfileName, (logfileMaxSize_MB * 1024 * 1024))
        # Open file for appending (using 'with' means that the OS will take care of closing it)
        with open(logfileName, "a+") as fh:
            # Append logMessage to the file
            fh.write(f"{datetime.datetime.now().strftime('%d/%m/%y %H:%M:%S')}: {logMessage}\n")
    except Exception as e:
        # If writing to disk fails, write to stderr instead
        try:
            sys.stderr.write(f"ERR:isptestlauncher.logToFile(): {logfileName}, "
                             f"{timeNow}, {logMessage}\n")
        except:
            # Fail silently
            pass

# Define signal handler functions
def sigintHandler(signum, frame):
    try:
        raise Exception("SIGINT")
    except Exception as e:
        raise Shutdown(e)

def sigtermHandler(signum, frame):
    try:
        raise Exception("SIGKILL")
    except Exception as e:
        raise Shutdown(e)

# Returns the IP address of the network interface currently used as the default route to the internet (if no args supplied)
# Alternatively, for a supplied destination ip address, it will return ip address of the interface that, according to the OS
# routing table will be used to send from.
def get_ip(ipAddrToTest = '10.255.255.255'):
    # Lifted from here https://stackoverflow.com/questions/166506/finding-local-ip-addresses-using-pythons-stdlib
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect((ipAddrToTest, 1))
        IP = s.getsockname()[0]
    except:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def main():
    # Specify the version number of this script
    thisVersion = "1.0"
    # Specify the defaault HTTP Server listen port
    httpServerDefaultPort = 10000

    #### Check for minimum python version
    if (testPythonVersion(3, 8)):
        # Python version check passed
        pass

    else:
        # Python version not satisfied so exit
        exit(1)

    #### Python version validated, so now parse the command line arguments

    # -c specifies the confog file containing the button/script definitions
    configFileName = None

    # Specify the default ip address and port that the public HTTP server will listen on
    # This is a tuple of IP address and TCP port
    # If the IP address is None, the OS will determine the listen address
    # If no network cards are available, localhost will be used
    httpServerAddr = (get_ip(), httpServerDefaultPort)

    # Placeholder for the switches/args passed to this script
    argv = None

    # Create a dict of shared object to be shared between all the threads
    sharedObjects = {}

    # Predefine some button/(GPI) and Mikrotik script definitions definitions

    # buttonScriptMappings contains a list of buttons, their corresponding ssh command strings and the id of the field
    # that will be populated with the response of that command
    # "label": The label that will be diaplayed on the html button
    # "target_cmd_string": The command string that will be sent to the device (via SSH)
    # "response_field_id": The javascript html dom ID where the result/output of the command will be displayed

    # statusFieldMappings contains a list of labelled status fields that will be populated automatically by running the
    # ssh command string contained in target_cmd_string. Polling will occur at a period set by polling_interval_ms
    # If "target_cmd_string" and polling_interval_ms are initialised as None, they will be ignored and *wont* be set
    # to auto poll (but these field id's will still have been created so can be modified on the page)"
    sharedObjects["controllerDefinitions"] = {
        "deviceAddress": "192.168.3.2",
        "deviceSshUsername": "kabulctrl",
        "buttonScriptMappings": [
            {
                "label": "Route via 4G",
                "target_cmd_string": "system script run route_via_4g",
                "response_field_id": "cmd_response"
            },
            {
                "label": "Route via adhoc WiFi",
                "target_cmd_string": "system script run route_via_adhoc_wifi",
                "response_field_id": "cmd_response"
            },
            {
                "label": "Route via adhoc cabled connection",
                "target_cmd_string": "system script run route_via_adhoc_cable",
                "response_field_id": "cmd_response"
            },
            {
                "label": "Get Router Identity",
                "target_cmd_string": "system script run get_identity",
                "response_field_id": "cmd_response"
            }
        ],
        "statusFieldMappings": [
            {
                "label": "Current cmd status",
                "target_cmd_string": None,
                "id": "cmd_response",
                "polling_interval_ms": None
            },
            {
                "label": "Current Router Clock",
                "target_cmd_string": ':put "$[/system clock get time]"',
                "id": "uTik_timeOfDay",
                "polling_interval_ms": 5000
            }
        ]
    }

    #### Pre-render some tables that can be displayed in the help-text
    #### The first and second columns of the help tables are also used to seed getopt in order to parse the
    #### incoming command line args

    # Create a dummy table in order to just get the max width of the *third* column (val will be used to wrap the text)
    # shown in the helptext
    columnMaxWidth = AsciiTable([["x:", "python-interpreter-path= ", "z"]]).column_max_width(2)

    # Specify the mandatory switches/long options that can (or should be) passed. Helptext will be used
    mandatorySwitches = [
        ["-c", "--config-file", '\n'.join(textwrap.wrap(
            f"The config file containing the mappings between the web gui buttons and the "
            f"corresponding Mikrotik scripts that should be run when they are pressed", columnMaxWidth))]
    ]
    # Specify any optional switches
    optionalSwitches = [["-h", "--help", '\n'.join(textwrap.wrap(f"Show help"))],
                        ["-p", "--public-http", '\n'.join(textwrap.wrap(f"Specifies a user selected ip address:port "
                                                                        f"combination, or just a port that the HTTP "
                                                                        f"server will listen on. By default, the web "
                                                                        f"server will listen on "
                                                                        f"{httpServerAddr[0]}:"
                                                                        f"{httpServerAddr[1]}. "
                                                                        f"Examples are: -p 192.168.3.50:10000 or "
                                                                        f"-p 10000. Port values need to be > 1024"))]]

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

    # Define the helptext that will be displayed
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

            # Store the first element of sys.argv (sys.argv[0]). This is the filename of the Python script itself
            # If the program is being run via a .pyz file *which itself is a file containing a zip archive), we'll
            # need the name of the archive so that we can extract the html file templates from it at run-time

            # Create a key in sharedObjects to capture the name of this python executable archive file
            sharedObjects["pyzArchiveName"] = sys.argv[0]

            # Parse the switches (and long parameters)
            opts, args = getopt.getopt(sys.argv[1:], getoptSwitches, getoptLongOptions)

            # iterate over all supplied options
            for opt, arg in opts:
                if opt in ("-c", "--config-file"):
                    if checkers.is_on_filesystem(arg):
                        configFileName = arg
                    else:
                        raise Exception(f"Supplied config-file doesn't exist: ({arg}).")

                if opt in ("-p", "--public-http"):
                    # Set a user-specified public HTTP port or address:port combination
                    # check for two parameters separated by a colon
                    if len(arg.split(':')) == 2:
                        ipAddr = str(arg.split(':')[0])
                        ipPort = int(arg.split(':')[1])
                        # Validate supplied IP address
                        try:
                            # Validate supplied IP address
                            try:
                                validators.ip_address(ipAddr)
                            except (errors.EmptyValueError, errors.InvalidIPAddressError) as e:
                                raise Exception(f"ip address {e}")
                            # Validate supplied port no
                            try:
                                validators.integer(int(ipPort), minimum=1024, maximum=65535)
                            except Exception as e:
                                raise Exception(f"tcp port {e}")
                            # ipAddr and ipPort validated so capture the values
                            httpServerAddr = (ipAddr, int(ipPort))

                        except Exception as e:
                            raise Exception(
                                f"-p Invalid Public HTTP server address:port combination supplied: [{arg}], {e}")
                    else:
                        # Only a port no supplied, use the previously OS-determined IP address
                        try:
                            # Validate supplied port no
                            try:
                                validators.integer(int(arg), minimum=1024, maximum=65535)
                            except Exception as e:
                                raise Exception(f"tcp port {e}")
                            # port no validated, so capture and reassign to httpServerAddr tuple
                            # Note(1), tuple elements can't be modified once assigned
                            # Note(2) the OS assigned address was established the top of main()
                            httpServerAddr = (httpServerAddr[0], int(arg))
                        except Exception as e:
                            raise Exception(f"-p Invalid Public HTTP port supplied [{arg}], {e}")
                    print(f"User specified Public HTTP server listen addr: {httpServerAddr[0]}:{httpServerAddr[1]}")
    except Exception as e:
        print(f"Error parsing args: {e}. \nUse -h or --help for help")
        exit(1)

    ####### Main code starts
    # # Create a threading.Event object that will be monitored by all threads NOTE USED YET
    # shutdownFlag = threading.Event
    # Register signal handlers
    signal.signal(signal.SIGINT, sigintHandler)  # Ctrl-C (keyboard interrupt)
    signal.signal(signal.SIGTERM, sigtermHandler)  # KILL

    # # Attempt to import an external data file from within the pyz zipped archive
    # Or, if that fails, just get the file from the file system in the usual way
    # fileToImport = "index.html"
    # try:
    #     print(f"Importing {fileToImport}")
    #     print(f"Extracted file: {retrieveFileFromArchive(sys.argv[0], fileToImport)}")
    #
    # except Exception as e:
    #     pass
    #     print(f"couldn't extract {fileToImport} from {sys.argv[0]}, {type(e)}:{e}, trying to import as a normal file")
    #     try:
    #         f = importFile(fileToImport)
    #         print(f"Normal import:{f}, {type(f)}")
    #     except Exception as e2:
    #         pass
    #         print(f"couldn't import {fileToImport} from {sys.argv[0]}, {type(e)}:{e2}")

    print("studiocontroller starting....")
    logToFile("studiocontroller starting....")

    # Start a web server
    print(f"start web server using: {httpServerAddr}")
    try:
        # Create a web server
        httpServer = HttpServerCreator(httpServerAddr[1], PublicHTTPRequestHandler,
                                              listenAddr=httpServerAddr[0],
                                              serverName=f"PublicHTTP({httpServerAddr[1]})",
                                              externalResourcesDict=sharedObjects,
                                                loggingMethod=logToFile)
        logToFile(f"Public HTTP server started on {httpServerAddr[0]}:{httpServerAddr[1]}")
        # Update sharedObjects dict with the HTTP Server address
        sharedObjects["httpServerAddr"] = httpServerAddr
    except Exception as e:
        logToFile("Failed to start public HTTP Server")


    # Provides a clean shutdown of all threads
    def shutdown():
        try:
            # Stop the HTTP server
            try:
                logToFile("Stopping HTTP server")
                httpServer.stopServing()
            except Exception as e:
                raise Exception(f"ERR: Failed to stop privateHTTP {e}")
        except Exception as e:
            logToFile(f"shutdown() {e}")

    # # Endless loop - until a shutdown Exception is raised or some other error occurs
    # try:
    #     rtr = SSHController("192.168.3.2", "kabulctrl")
    # except Exception as e:
    #     raise Exception(f"Create SSH Controller {e}")
    #     exit(1)
    #
    # def routerCallback(response=None, timestamp=None, exception=None):
    #     print(f"routerCallback() {timestamp}: {response}, exception: {exception}")

    while True:
        try:
            # print(".")
            # rtr.sendCommand(':put "$[/system clock get time]"', callbackMethod=routerCallback)
            time.sleep(2)
        except Shutdown as e:
            logToFile(f"shutting down {e}")
            break
        except Exception as e:
            logToFile(f"Fatal error, shutting down: {e}")
            break
    try:
        shutdown()
        logToFile("studiocontroller exited successfully")
        exit(0)
    except Exception as e:
        logToFile(f"ERR: Shutdown error {e}")
        exit(1)

if __name__ == '__main__':
    main()


