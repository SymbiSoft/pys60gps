# -*- coding: iso-8859-15 -*-
# $Id$
# Copyright Aapo Rista 2006 - 2009

"""
Generic session handling and communication module.

Comm offers two internal POST-request functions: plain and multipart, latter
allows posting file attachments.

In addition login() and logout() calls are provided. After successful login() 
Comm keeps sessionid and uses it until logout is performed.

All other functions should be defined in deriving class.

All API functions should return decoded data (dict) and HTTPResponse object.
Data should have at least keys

data = {
    "status" : 'ok' | 'error', 
    "message" : 'Clear text explanation',
}

Server should return raw JSON.

csetconv is used to ensure all param keys and values are UTF8 encoded.

TODO:
- support for gzipped response (and request) to reduce 
  the amount of transferred data 
- support for encrypted response and request
"""

import httplib
import urllib
import sys
#import time
#import re
#import md5

# import sha
import http_poster
import csetconv
import pys60_json as json
from pys60_json import ReadException

def rpc_name():
    """Return the name of calling function."""
    return sys._getframe(1).f_code.co_name

def parse_json_response(json_data, response):
    """Decode JSON response and return the data in a dictionary."""
    #json_data = response.read()
    try:
        data = json.read(json_data)
    except ReadException, error:
        message = "%s[...]" % str(error)[:100]
        data = {"status" : "error", "message" : message}
    except:
        message = "Unprocessed error (server status code %s)" \
                % response.status
        data = {"status" : "error", "message" : message}
    return data

class Comm:
    """Base class for all HTTP-communication classes."""
    
    __id__ = u'$Id$'

    def __init__(self, host, script, useragent = None):
        try: # Parse revision and last change date
            ida = self.__id__.split(u" ")
            self.revision = ida[2]
            self.lastchangeddate = ida[3]
        except IndexError:
            self.revision = u'undefined'
            self.lastchangeddate = u'undefined'
        if useragent is None:
            self.useragent = 'Comm.py/%s/%s' % (self.revision, 
                                                self.lastchangeddate)
        self.host = host
        self.script = script
        # self.url = "http://%s%s" % (host, script)
        self.sessionid = None
        
    def _send_request(self, operation, params):
        """
        Send HTTP POST request to the server using httplib, 
        return decoded data and a HTTPResponse object.
        """
        params['operation'] = operation
        # convert all params-values to utf-8, keys should be ASCII
        for key in params.keys():
            params[key] = csetconv.to_utf8(params[key])
        params = urllib.urlencode(params)
        headers = {"Content-type": "application/x-www-form-urlencoded",
                   "User-Agent": self.useragent,
                   }
        # Send session id in headers as a cookie
        if self.sessionid != None:
            headers["Cookie"] = "sessionid=%s;" % self.sessionid
        conn = httplib.HTTPConnection(self.host)
        try:
            conn.request("POST", self.script, params, headers)
        except: # socket.gaierror, error: FIXME: handle errors here
            raise
        response = conn.getresponse()
        data = response.read()
        data = parse_json_response(data, response)
        conn.close()
        return data, response

    def _send_multipart_request(self, operation, params, files):
        """
        Send multipart HTTP-request to the server using http_poster.
        Request can contain file attachments.
        Return decoded response data and a HTTPResponse object.
        """
        params['operation'] = operation
        param_list = []
        # convert all params keys and values to utf-8, 
        # post_multipart expects a list of tuples
        for key in params.keys():
            params[key] = csetconv.to_utf8(params[key])
        #for key in params.keys():
        #    param_list.append((csetconv.to_utf8(key), 
        #                       csetconv.to_utf8(params[key])))
        headers = {"User-Agent": self.useragent, }
        if self.sessionid != None:
            headers["Cookie"] = "sessionid=%s;" % self.sessionid
        data, response  = http_poster.post_multipart(self.host, self.script, 
                                                     params, files, headers)
        data = parse_json_response(data, response)
        return data, response
 
    def login(self, username, password):
        """
        Do login with given username and password.
        Return decoded response data and a HTTPResponse object.
        """
        params = {'username': username, 'password' : password}
        data, response = self._send_request(rpc_name(), params)
        if "status" in data and data["status"] == "ok":
            self.sessionid = data["sessionid"]
        else:
            self.sessionid = None
        return data, response

    # TODO: login_sha()
    def login_sha(self, login, shapw):
        """
        Send login and sha encoded password to the server.
        Return decoded response data and a HTTPResponse object.
        """
        # TODO: consider how to get salt from the server
        pass

    def logout(self):
        """
        End current session.
        Return decoded response data and a HTTPResponse object.
        """
        if self.sessionid is None:
            return {"status" : "error", 
                    "message" : "Session is not active"}, None
        params = {} # Session id is in cookie
        data, response = self._send_request(rpc_name(), params)
        if "status" in data and data["status"] == "ok":
            self.sessionid = None
        return data, response

    def sessioninfo(self):
        """
        Get some information of session from the server.
        Return decoded response data and a HTTPResponse object.
        """
        params = {}
        data, response = self._send_request(rpc_name(), params)
        return data, response

if __name__ == '__main__':
    SERVER = u"localhost:8000"
    SCRIPT = u'/api/'
    COMM = Comm(SERVER, SCRIPT)
    DATA, RESPONSE = COMM.login(u"user", u"password")
    print DATA
    DATA, RESPONSE = COMM.logout()
    print DATA
