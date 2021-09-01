#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# A set of classes and functions required to create an HTTP Server
# These originally started life in isptest

# Define a custom HTTPRequestHandler class to handle HTTP GET, POST requests
import json
import textwrap
import threading
from abc import abstractmethod
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer, HTTPServer
from urllib.parse import parse_qs, urlparse, parse_qsl, urlencode

# Provides a set of class methods useful for HTTP Request processing functions
class HTTPTools(object):
    # This function is designed to take the key/value pairs sent as a query at the end of a URL
    # It will then reformat the dictionary so that it can be passed straight into an existing
    # function/method as a set of kwargs
    # It's expecting to be fed from the output of urllib.parse.parse_qs()
    # parse_qs will return a key and value. However, the value will always be as a list,
    #  even if there is only a single value associated with that key.
    # Therefore we need to reformat the query_components so that they appear as key:value
    # NOT key:[value]
    # Additionally, test vfor presence of boolean values and convert them from strings to bools as expected
    # by the destination function/method
    @classmethod
    def mapURLQueryToFnArgs(cls, query_componentsDict):
        # Take a shallow copy of the incoming dict
        functionArgsDict = dict(query_componentsDict)
        # Iterate over all the key/value pairs
        for key in functionArgsDict:
            # Iterate over each of the values in the list associated with each key and convert from strings to normal
            # Python types, based on the contents
            for listItem in range(len(functionArgsDict[key])):
                # Values will be a list
                # Test to see if this is a boolean val. If so, recast as a bool (since all
                # incoming values are strings)
                if functionArgsDict[key][listItem] in ["False", "false", "No", "no"]:
                    functionArgsDict[key][listItem] = False
                elif functionArgsDict[key][listItem] in ["True", "true", "Yes", "yes"]:
                    functionArgsDict[key][listItem] = True
                else:
                    # Test if the value is an integer
                    if str(functionArgsDict[key][listItem]).isnumeric():
                        # only values 0-9 present, so cast as an integer
                        functionArgsDict[key][listItem] = int(functionArgsDict[key][listItem])
                    else:
                        # See if the value is float by trying to cast it as a float (this will fail, if it's not)
                        try:
                            functionArgsDict[key][listItem] = float(functionArgsDict[key][listItem])
                        except:
                            # Casting as a float failed, so ignore
                            pass

            # Finally, test to see if there is only a single value corresponding with that key
            # i.e does the list only contain a single element?
            if len(functionArgsDict[key]) == 1:
                # If so, get rid of the list encompassing the value and assign the
                # value directly to the key instead
                functionArgsDict[key] = functionArgsDict[key][0]

        return functionArgsDict

    # Simple shortcut function to remove a list[] of keys from the supplied dictionary
    # If the searched-for key is missing, it will be ignored
    # NOTE: It acts on the src dictionary (a bit like a C function)
    # Returns a list of the keys that were actually removed
    @classmethod
    def removeMultipleDictKeys(cls, dictToBeModified, keysToBeRemoved):
        # List returned by function to contain a list of the keys that were actually removed
        keysRemoved = []
        for k in keysToBeRemoved:
            if k in dictToBeModified:
                # Delete key k from the dict
                dictToBeModified.pop(k, None)
                # Record the deletion
                keysRemoved.append(k)
        return keysRemoved

    # Shortcut function to create a subset of the supplied dictionary containing only wantedKeys[]
    # If the wanted keys are missing from sourceDict, they will be ignored
    # Answer from here: https://stackoverflow.com/a/5352649
    @classmethod
    def extractWantedKeysFromDict(cls, sourceDict, wantedKeys):
        filteredDict = dict((k, sourceDict[k]) for k in wantedKeys if k in sourceDict)
        return filteredDict

    # Renders a nested dict of dicts as an html table
    # columnTitles is a list of string representing the column titles
    # columnKeys is list of keys to be picked from the nested dict within each key of srcDict
    @classmethod
    def createHTMLTable(cls, srcDict, title, columnTitles, columnKeys):
        tableData = f'<table border="1">'
        # Create title row
        tableData += f"<tr><td>{title}</tr></td>"
        # Create table column headings
        if len(columnTitles) > 0:
            tableData += f"<tr><td>{'</td><td>'.join(columnTitles)}</td></tr>"
        # Extract values from srcDict to create the data rows
        if len(columnKeys) > 0:
            # Iterate over srcDict to create the rows
            for row in srcDict:
                tableData += f"<tr><td><a href={row}>{row}</a></td>"  # The srcDict key itself should be the first cell data
                if len(columnKeys) > 0:
                    for key in columnKeys:
                        if key in srcDict[row]:
                            cellData = srcDict[row][key]
                        else:
                            cellData = f"key {key} missing"
                        tableData += f'<td>{cellData}</td>'
                tableData += f"</tr>"
        tableData += f"</table>"
        return tableData


class HTTPRequestHandlerRTP(BaseHTTPRequestHandler):
    # For JSON, use contentType='application/json'
    # For plain text use contentType='text/plain'
    def _set_response(self, responseCode=200, contentType='text/html'):
        self.send_response(responseCode)
        self.send_header('Content-type', contentType)
        self.end_headers()

    # Sends a '301 redirect' message back to the requester, along with the url to be directed to
    def redirect(self, targetURL, responseCode=301):
        self.send_response(responseCode)
        self.send_header('Location', targetURL)
        self.end_headers()

    # Re-encodes the incoming string as UTF-8 and terminates with a '/n' character
    def formatHttpResponseAsUTF8(self, input):
        output = (str(input) + "\n").encode('utf-8')
        return output

    # Wraps the supplied strings (title, head, body) in html boilerplate
    # useBootstrap makes it look pretty
    def htmlWrap(self, title="", head="", body="", useBootstrap=True):
        simpleHtml = textwrap.dedent(f'''\
            <html>
                <head>
                    <meta charset="utf-8"/>
                    <title>{title}</title>
                    <!--[if lt IE 9]>
                    <script src="//html5shim.googlecode.com/svn/trunk/html5.js"></script>
                    {head}
                    <![endif]-->
                </head>
                <body>
                {body}
                </body>
            </html>
        ''')

        # Cribbed from here:- https://github.com/lewagon/bootstrap-boilerplate
        bootStrapHtml = textwrap.dedent(f'''\
            <html>
                <head>
                    <meta charset="utf-8"/>
                    <meta http-equiv="X-UA-Compatible" content="IE=edge">
                    <meta name="viewport" content="width=device-width, initial-scale=1">

                    <title>{title}</title>

                    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css">
                    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.8.1/css/fontawesome.min.css">

                    <!-- HTML5 Shim and Respond.js IE8 support of HTML5 elements and media queries -->
                    <!-- Leave those next 4 lines if you care about users using IE8 -->
                    <!--[if lt IE 9]>
                    <script src="https://oss.maxcdn.com/html5shiv/3.7.2/html5shiv.min.js"></script>
                    <script src="https://oss.maxcdn.com/respond/1.4.2/respond.min.js"></script>
                    <![endif]-->
                    {head}
                </head>
                <body>
                {body}
                <!-- Including Bootstrap JS (with its jQuery dependency) so that dynamic components work -->
                <script src="https://code.jquery.com/jquery-1.12.4.min.js" integrity="sha256-ZosEbRLbNQzLpnKIkEdrPv7lOy9C27hHQ+Xp8a4MxAQ=" crossorigin="anonymous"></script>
                <script src="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/js/bootstrap.min.js"></script>
                </body>
            </html>
        ''')
        if useBootstrap:
            return bootStrapHtml
        else:
            return simpleHtml


    # Override log_message() to return *nothing*, otherwise the HTTP server will continually log all HTTP requests
    # See here: https://stackoverflow.com/a/3389505
    def log_message(self, format, *args):
        try:
            # Access parent Rtp Stream object methods via server attribute
            parent = self.server.parentObject
            # parent.postMessage(f"DBUG: HTTPRequestHandlerRTP({self.client_address}).log_message() {format%args}", logToDisk=False)
            pass
        except Exception as e:
            pass


    # Override log_error(), otherwise the HTTP server will continually log all HTTP errors to stderr
    # See here: https://stackoverflow.com/a/3389505
    def log_error(self, format, *args):
        try:
            # Access parent HTTP Server logging method (optionally specified when the HTTP Server was created)
            # Note: This might not have actually been set. If not, fail silently
            self.server.parentLogger(f"ERR: HTTPRequestHandlerRTP({self.client_address}).log_error() {format % args}")
        except:
            # Fail silently
            pass

    # Utility method for populating the getMappings{}, postMappings{} and deleteMappings{} dicts in
    # apiGETEndpoints(), apiPOSTEndpoints() and apiDELETEEndpoints() respectively
    # The advsntahe of using this method over mamnually adding the keys to the dicts is that it guarantees that all the
    # required keys expected by do_GET(), do_POST() and do_DELETE() will be present
    # targetDict: the dictionary to be populated
    # path: the HTTP url path that will be matched. This is used as the key for the dictionary
    # targetMethod: The method that will be called when the url path is requested
    # methodArgs: a list of args required by the method but that are not to be supplied in the HTTP request
    # requiredKeys: A list of args required by the method that *are* supplied in the HTTP request (passed in as args, not kwargs)
    # optionalKeys: A list of optional keys that will be accepted by the target method (passed in as kwargs)
    # contentType: The return type that the target method is expected to return and therefore instruct how the
    #               do_GET(), doPOST() and do_DELETE() methods will encode the data back to the requester
    # Available contentsTypes are:-
    #   'application/json'  -- The output of the target method will be encoded as json (the default)
    #   'text/plain' -- encode http response as text/plain (used to send text files)
    #   'text/html' -- encode http response as html
    #   'application/python-pickle' -- The target method will return a bytes object, don't encode the response, send as is
    #                                   (this can be used to send raw bytes over HTTP)
    # If contentType is not specified, do_GET() will *currently* attempt to encode the method
    # response as json. This suits methods that return dicts and lists
    def addEndpoint(self, targetDict, path, targetMethod,
                    methodArgs=[], requiredKeys=[], optionalKeys=[], contentType=None):
        # add the path (and keys) to the target dictionary
        targetDict[path] = {"targetMethod": targetMethod, "args": methodArgs, "reqKeys": requiredKeys,
                     "optKeys": optionalKeys, "contentType": contentType}

    @abstractmethod
    # Acts a repository for the GET endpoints provided by the HTTP API
    def apiGETEndpoints(self):
        # Access parent Rtp Stream object methods via server attribute
        parent = self.server.parentObject
        # A dictionary to map incoming GET URLs to an existing RtpGenerator method
        # The "args" key contains a list with the preset values that will be passed to targetMethod()
        # "optKeys" is a list of keys that  targetMethod will accept as a kwarg
        # "reqKeys" is a list of mandatory args (not kwargs) required the target method
        # "contentType" is an additional key that specifies the type of data returned by targetMethod (if known)
        # The default behaviour of do_GET() will be to try and encode all targetMethod() return values as json
        # Some methods (eg getEventsListAsJson()) already return json, so there is no need to re-encode it
        # Additionally, the /report generation methods return plaintext so the "contentType" key is a means of
        # signalling to do_GET() how to handle the returned values
        # For ease, don't populate this method by hand. Instead, use the addEndpoint() method (less error prone)
        getMappings = {
            "/url": {"targetMethod": None, "args": [], "reqKeys": [],
                     "optKeys": [], "contentType": 'application/json'}
        }
        return getMappings



    @abstractmethod
    # Acts a repository for the POST endpoints provided by the  HTTP API
    def apiPOSTEndpoints(self):
        # Access parent Rtp Stream object methods via server attribute
        parent = self.server.parentObject
        # A dictionary to map incoming POST URLs to an existing RtpGenerator method
        # The keys/values within the POST data will be mapped to the keys listed in "args"[] and "kwargs"[]
        # "reqKeys"[] lists the mandatory parameters expected by targetMethod()
        # "optKeys"[] lists the optional key/value parameters that targetMethod() will accept
        # {"url path":
        #   {
        #       "targetMethod":target method/function,
        #       "reqKeys":[required arg1, required arg2..],    <---*only* the values are passed to the mapped function (i.e args)
        #       "optKeys":[optional arg1, arg2..]    <------the key/value pairs are passed to the function (i.e kwargs)
        #   }
        postMappings = {
            "/url": {"targetMethod": None, "reqKeys": [], "optKeys": []}
        }
        return postMappings

    @abstractmethod
    # Acts a repository for the DELETE endpoints provided by the HTTP API
    def apiDELETEEndpoints(self):
        # Access parent Rtp Stream object methods via server attribute
        parent = self.server.parentObject
        deleteMappings = {"/delete": {"targetMethod": None, "reqKeys": [], "optKeys": []}}
        return deleteMappings

    # Shortcut method to take raw POST or GET Query data (*as unicode*, of the form key1=value1&key2=value2...
    # (TIP use .decode('UTF-8') to convert an ASCII string to unicode)
    # It will then return two items a list of args and a dict of kwargs that can be passed straight to a function/method.
    # Required args are contained within a list, and optional args as a dict
    # The parameters should be passed to the target method as follows reVal = myFunc(*requiredArgs, **optionalArgs)
    # The '*' and '**' will expand out the requiredArgsList and optionalArgsDict respectively
    # Additionally, it will check to see that all the keys in rawKeysValuesString have been used.
    # If not, it will raise an Exception
    def convertKeysToMethodArgs(self, rawKeysValuesString, requiredArgKeysList, optionalArgKeysList):
        # parse the rawKeysValuesString and convert to a dict
        post_data_dict = parse_qs(rawKeysValuesString)
        # 'Pythonize' post_data_dict to convert it from all strings to ints/bools etc
        # and reduce values of single length lists to a single value
        parsedPostDataDict = HTTPTools.mapURLQueryToFnArgs(post_data_dict)
        # Create list of mandatory args. *This will fail* if not al the keys are present in post_data_dict
        try:
            requiredArgsList = [parsedPostDataDict[key] for key in requiredArgKeysList]
        except Exception as e:
            raise Exception(f"convertKeysToMethodArgs() mandatory keys missing {e}, "
                            f"mandatory keys are: {requiredArgKeysList}")
        # Now create a sub-dict of the just the optional keys
        optionalArgsDict = HTTPTools.extractWantedKeysFromDict(parsedPostDataDict, optionalArgKeysList)
        # Finally remove the 'expected' keys from parsedPostDataDict to see if any unexpected keys are left over
        HTTPTools.removeMultipleDictKeys(parsedPostDataDict, requiredArgKeysList + optionalArgKeysList)
        if len(parsedPostDataDict) > 0:
            raise Exception(f"convertKeysToMethodArgs() unexpected keys provided {parsedPostDataDict}."\
                            f" Permitted optional keys are: {optionalArgKeysList},"\
                            f"mandatory keys are: {requiredArgKeysList}")
        return requiredArgsList, optionalArgsDict

    # Shows the available endpoints
    def listEndpoints(self):
        # Get HTML rendered tables of all the types of endpoints
        getEndpoints = HTTPTools.createHTMLTable(self.apiGETEndpoints(), 'GET', ['Path', 'Required keys', 'Optional keys'], ['reqKeys', 'optKeys'])
        postEndpoints = HTTPTools.createHTMLTable(self.apiPOSTEndpoints(), 'POST',
                                              ['Path', 'Required keys', 'Optional keys'], ['reqKeys', 'optKeys'])
        deleteEndpoints = HTTPTools.createHTMLTable(self.apiDELETEEndpoints(), 'DELETE',
                                                ['Path', 'Required keys', 'Optional keys'], ['reqKeys', 'optKeys'])

        # Create an output string
        helpText = f"<h3>Available  API endpoints:" \
                   f"{getEndpoints}<br><br>" \
                   f"{postEndpoints}<br><br>" \
                   f"{deleteEndpoints}<br><br>"

        return helpText


    @abstractmethod
    # render HTML index page
    def renderIndexPage(self):
        # Access parent Rtp Stream object via server attribute
        parent = self.server.parentObject
        response = f"<html>Index page for {parent.__class__.__name__}</html>"
        return response


    # Http server methods
    def do_GET(self):
        # Access parent Rtp Stream object via server attribute
        parent = self.server.parentObject
        # Get the dict of url/method mappings
        getMappings = self.apiGETEndpoints()
        try:
            # syncSourceID = parent.syncSourceIdentifier
            # Does the URL match any of those key entries in in getMappings{}?
            # Create a version of the URL that doesn't include any ?key=value suffixes
            # pathMinusQuery = str(self.path).split('?')[0]
            # Split of the URL and query (?key=value suffixes)
            urlDecoded = urlparse(self.path)
            path = urlDecoded.path
            query = urlDecoded.query
            # Utils.Message.addMessage(f"path:{path}, Query:{query}")

            # Strip off leading / from path (if present), and just keep the string *after* the leading '/'
            if path[0] == "/" and len(path) > 1:
                path = path[1:]
            else:
                # If the string only contains a '/' character, refashion the string as an empty string
                # (this represents the 'root' or index page of the Http server)
                path = ""

            # Test the path to see if it is recognised
            if path in getMappings:
                # Extract the method to be called
                fn = getMappings[path]["targetMethod"]
                # Extract the 'preset' method arguments (these are args not supplied via the http request)
                nonApiArgs = getMappings[path]["args"]
                # Extract the 'optional' method arguments list (i.e the kwarg keys that targetMethod() would accept)
                optionalArgKeys = getMappings[path]["optKeys"]
                # Extract the 'required' method arguments supplied via the HTTP GET api
                requiredArgKeys = getMappings[path]["reqKeys"]
                # UNCOMMENT THIS
                # Extract the 'contentType' (this will be 'None', if not specifed when endpoints added using addEndpoint())
                contentType = getMappings[path]["contentType"]

                # Parse query to create a list of optional parameters to be passed to targetMethod()
                requiredArgs, optionalKwargs = self.convertKeysToMethodArgs(query, requiredArgKeys, optionalArgKeys)
                # append requiredArgs to the 'preset/default' args to get a list of mandatory args (not kwargs) required
                # by the target function
                # self.log_error(f"args:{nonApiArgs}, requiredArgs:{requiredArgs}, optionalArgs:{optionalKwargs}, path:{path}, query:{query}")
                # Create a composite list of the 'nonAPI supplied' args and the 'api supplied' args
                args = nonApiArgs + requiredArgs
                # self.log_error(f"GET fn:{fn}, args:{args}, optKeys:{optionalKArgs}")
                # Execute the specified method, expanding out the parameter list
                retVal = fn(*args, **optionalKwargs)

                # Test the contentType expected to be returned by fn() and set headers/encode as JSON accordingly
                if contentType == 'text/html' or contentType == 'text/plain':
                    response = retVal.encode('utf-8')
                    # Create the headers using the content type specified in the getMappings{} dict
                    self._set_response(contentType=contentType)

                elif contentType in ['application/json', 'application/python-pickle']:
                    # Return value of fn() already encoded as JSON (or in Pickle format), pass it on as-is
                    response = retVal
                    # Set the headers
                    self._set_response(contentType=contentType)

                else:
                    # NOTE: I ran into a problem with massive nested data structures - (eg Events Lists for asll streams
                    # as provided by getEventsAsJson() because json.dumps() seems to be exponentially complex for
                    # nested structures. To get around this, getEventsAsJson() now performs its own json serialisation
                    # in a deliberately throttled way

                    # The code below was an earlier attempt to fix this. The code is kept, beacuse it might still be
                    # useful
                    # # We don't know the format, so encode as JSON as a default
                    # # NOTE: We don't know how long the response will be so it is safest to NOT to use json.dumps()
                    # # to render our returned string because json.dumps can run out of memory for really big nested
                    # # objects (see https://stackoverflow.com/questions/24239613/memoryerror-using-json-dumps/)
                    # # or else, causes a massive spike in CPU usage which can cause non-existent glitches to appear in
                    # # the received streams.
                    #

                    # # Instead, we call iterencode() and convert the response to json in chunks
                    # # NOTE: This means that we have to write our own custom json serialiser - because the standard
                    # # JSONEncoder cannot handle datetime.datetime or datetime.timedelta objects
                    # # The downside is that this is slower than using json.dumps(), but should be more dependable
                    #
                    # # Create an instance of our custom json encoder class
                    # jsonEncoder = RtpJsonEncoder()
                    #
                    # # response = "".join([str(chunk).encode('utf-8') for chunk in ])
                    # response = b""
                    # for chunk in jsonEncoder.iterencode(retVal):
                    #     response += chunk.encode('utf-8')
                    #     # deliberately throttle the rate at which the the response can be constructed
                    #     # time.sleep(0.001)
                    # Create the json encoded response
                    response = (json.dumps(retVal, sort_keys=False, indent=4, default=str) + "\n").encode('utf-8')

                    # Set the headers
                    self._set_response(contentType='application/json')

            else:
                # path not recognised
                raise Exception(f"Path not recognised {self.path}")

            # Write the response back to the client
            self.wfile.write(response)
        except Exception as e:
            try:
                self.send_error(404,f"{parent.__class__.__name__}(server: {self.server.server_address}, client:{self.client_address}) "
                                    f"HttpRequestHandler.do_GET() {self.path}, {e}")
            except:
                pass

    def do_POST(self):
        # Access parent Rtp Stream object via server attribute
        parent = self.server.parentObject
        # Get the dict of url/method mappings
        postMappings = self.apiPOSTEndpoints()
        retVal = None  # Captures the return value of the mapped method (if there is one)
        try:
            # syncSourceID = parent.syncSourceIdentifier
            # Split off the URL and query (?key=value suffixes)
            urlDecoded = urlparse(self.path)
            path = urlDecoded.path
            query = urlDecoded.query
            # self.log_error(f"************do_POST: path:{path}, query:{query}")

            # Strip off leading / from path (if present), and just keep the string *after* the leading '/'
            if path[0] == "/" and len(path) > 1:
                path = path[1:]
            else:
                # If the string only contains a '/' character, refashion the string as an empty string
                # (this represents the 'root' or index page of the Http server)
                path = ""

            # Does the URL match any of those in postMappings{}?
            if path in postMappings:
                # Extract the target function
                fn = postMappings[path]["targetMethod"]
                # Extract the mandatory args for the mapped-to method
                requiredArgKeys = postMappings[path]["reqKeys"]
                # Extract optional args (kwargs) for the mapped-to method
                optionalArgKeys = postMappings[path]["optKeys"]

                # Get POST data (*from the body* of the message, not the query)
                # Gets the size of data
                try:
                    content_length = int(self.headers['Content-Length'])
                except Exception as e:
                    content_length = 0  # Body is empty
                    # raise Exception(f"empty message body or no 'Content-Length' field, {e}")
                # Get the data itself as a string ?foo=bar&x=y etc.. NOTE: Arrives as UTF-8, so have to decode back to unicode
                post_data_raw = self.rfile.read(content_length).decode('UTF-8')
                # Examine the supplied keys, divide them up between requiredArgKeys, optionalArgKeys and then
                # generate a list and a dict that can be expanded using * and ** to be used as method parameters
                # Will raise an Exception if unexpected keys are present or mandatory keys are missing
                requiredArgs, optionalArgs = self.convertKeysToMethodArgs(post_data_raw, requiredArgKeys,
                                                                          optionalArgKeys)
                # Execute the specified method, expanding out the parameter list
                retVal = fn(*requiredArgs, **optionalArgs)
                response = self.formatHttpResponseAsUTF8(f"{type(parent)}({self.client_address}) do_POST() {self.path}, retVal:{retVal}")
                # Set headers
                self._set_response()
            else:
                raise Exception(f"Unrecognised path {self.path}")
            # Write the response back to the client
            self.wfile.write(response)

        except Exception as e:
            try:
                self.send_error(404,f"{parent.__class__.__name__}(server: {self.server.server_address}, client:{self.client_address}) "
                                    f"HttpRequestHandler.do_POST() {self.path}, {e}")
            except:
                pass

    def do_DELETE(self):
        # Access parent Rtp Stream object via server attribute
        parent = self.server.parentObject
        # Get the dict of url/method mappings
        deleteMappings = self.apiDELETEEndpoints()
        retVal = None  # Captures the return value of the mapped method (if there is one)
        try:
            # syncSourceID = parent.syncSourceIdentifier
            # Split off the URL and query (?key=value suffixes)
            urlDecoded = urlparse(self.path)
            path = urlDecoded.path
            query = urlDecoded.query

            # Strip off leading / from path (if present), and just keep the string *after* the leading '/'
            if path[0] == "/" and len(path) > 1:
                path = path[1:]
            else:
                # If the string only contains a '/' character, refashion the string as an empty string
                # (this represents the 'root' or index page of the Http server)
                path = ""

            # Does the URL match any of those in postMappings{}?
            if path in deleteMappings:
                # Extract the target function
                fn = deleteMappings[path]["targetMethod"]

                # Extract the mandatory args for the mapped-to method
                requiredArgKeys = deleteMappings[path]["reqKeys"]
                # Extract optional args (kwargs) for the mapped-to method
                optionalArgKeys = deleteMappings[path]["optKeys"]
                # Get DELETE data (*from the body* of the message, not the query)
                # Gets the size of data
                try:
                    content_length = int(self.headers['Content-Length'])
                except Exception as e:
                    content_length = 0 # Body is empty
                    # raise Exception(f"empty message body or no 'Content-Length' field, {e}")

                # Get the data itself as a string ?foo=bar&x=y etc.. NOTE: Arrives as UTF-8, so have to decode back to unicode
                delete_data_raw = self.rfile.read(content_length).decode('UTF-8')
                # Examine the supplied keys, divide them up between requiredArgKeys, optionalArgKeys and then
                # generate a list and a dict that can be expanded using * and ** to be used as method parameters
                # Will raise an Exception if unexpected keys are present or mandatory keys are missing
                requiredArgs, optionalArgs = self.convertKeysToMethodArgs(delete_data_raw, requiredArgKeys,
                                                                          optionalArgKeys)

                # Execute the specified method, expanding out the parameter list
                retVal = fn(*requiredArgs, **optionalArgs)
                response = self.formatHttpResponseAsUTF8(
                    f"{type(parent)}({self.client_address}) do_DELETE() {self.path}, retVal:{retVal}")
                # Set headers
                self._set_response()
            else:
                raise Exception(f"Unrecognised path {self.path}")

            # Write the response back to the client
            self.wfile.write(response)

        except Exception as e:
            try:
                # This commonly fails on app shutdown because the HTTP Server itself has been shutdown whilst
                # the do_DELETE() is being processed
                self.send_error(404,f"{parent.__class__.__name__}(server: {self.server.server_address}, client:{self.client_address}) "
                                    f"HttpRequestHandler.do_DELETE() {self.path}, {e}")
            except:
                pass


# Define a custom HTTPServer. This will allow access to the associated object that created it,
# from the server (and httpHandler)
# Note this inherits from ThreadingHTTPServer in an attempt to make it 'Google Chrome proof'
class CustomHTTPServer(ThreadingHTTPServer):
    def __init__(self, *args, **kwargs):
        # Because HTTPServer is an old-style class, super() can't be used.
        HTTPServer.__init__(self, *args, **kwargs)
        self.parentObject = None

    # Provide a setter method to allow the server to have access to the instance of the object that created it
    # The reason not to have this set by the Constructor method is that I didn't want to modify the existing
    # constructor method of HTTPServer
    def setParentObjectInstance(self, parentObjectInstance):
        self.parentObject = parentObjectInstance

    # Provides a means for instantiator of the CustomHTTPServer to specify a callback method that can be used
    # to provide message logging. If provided, this method will be called within the
    # HTTPRequestHandlerRTP.logError() methof (which itself overrides that of ThreadingHTTPServer.log_error())
    def setLoggingMethod(self, loggerMethod):
        self.parentLogger = loggerMethod


# Creates a threaded HTTP Server with a single call (involes Utils.CustomHTTPServer)
# eg myWebserver = HttpServerCreator(11000, myHttpRequestHandler, listenAddr="127.0.0.1")
class HttpServerCreator(object):
    # Creates the HTTP server thread
    # If listenAddr is not specified, the OS will decide which interface to listen on (based on the default route in the
    # routing table)
    # externalResourcesDict is an optional dict of resources that the HTTP server might want access to
    # serverName is an optional friendly name that will be given to the http server thread
    # overrideParentObject allows the caller to specify the object instance who is the 'parent' of the
    # instatiated HttpServerCreator object. This will allow the RequestHandler class (which contains do_GET() etc methods)
    # access to all the methods/vars of the class that first created it
    # The RequestHandler can access the parent class methods using 'self.server.parentObject' from within the
    # handler itself
    def __init__(self, listenPort, requestHandler, listenAddr=None, serverName=None, externalResourcesDict=None,
                 overrideParentObject=None):
        self.listenPort = listenPort
        self.requestHandler = requestHandler
        self.listenAddr = listenAddr
        self.externalResourcesDict = externalResourcesDict
        self.serverName = serverName
        # If no name supplied, set a default name using the port no
        if serverName is None:
            self.serverName = f"HttpServerCreator({listenPort})"
        try:
            # Create an http server
            self.httpd = CustomHTTPServer((listenAddr, listenPort), self.requestHandler)

            if overrideParentObject is None:
                # Pass this object instance to the server (so that the dynamically created instances of
                # httpRequestHandler will have access to the parent object)
                self.httpd.setParentObjectInstance(self)
            else:
                self.httpd.setParentObjectInstance(overrideParentObject)
            # Start the server as a thread (otherwise __init__() would block
            self.httpdServerThread = threading.Thread(target=self.httpd.serve_forever, daemon=False,
                                                      name=serverName)
            self.httpdServerThread.start()
        except Exception as e:
            raise Exception(f"httpServerCreator.__init__() {e}")

    # Stops the HTTP Server
    def stopServing(self):
        try:
            # Wrap the call to shutdown() inside another thread
            threading.Thread(target=self.httpd.shutdown, daemon=True).start()
            # Confirm that the thread has ended, if not, raise an Exception
            self.httpdServerThread.join(timeout=2)
            if self.httpdServerThread.is_alive():
                raise Exception("Failed to stop")

        except Exception as e:
            raise Exception(f"HttpServerCreator.stopServing() {e}")

