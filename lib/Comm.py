# -*- coding: iso-8859-15 -*-
# $Id: Comm.py 1374 2007-04-13 05:22:01Z arista $
# Copyright Aapo Rista 2006 - 2009

"""Generic session handling and communication module."""

# python native imports
import time
import httplib
import urllib
import sys
import re
import md5
import sha

import http_poster
import csetconv
import pys60_json as json

# Seems obsolete:

############## URLLIB STUFF START #################################
# Override urrlib's default useragent header
#class AppURLopener(urllib.FancyURLopener):
#    __version__ = u'$Id: Comm.py 1374 2007-04-13 05:22:01Z arista $' # DO NOT modify Id-string
#    def __init__(self, *args):
#        try: # Parse revision and last change date
#            ida = self.__version__.split(u" ")
#            self.revision = ida[2]
#            self.lastchangeddate = ida[3]
#        except:
#            self.revision = u'undefined'
#            self.lastchangeddate = u'undefined'
#        self.version = 'Plok.In/%s/%s' % (self.revision, self.lastchangeddate)
#        urllib.FancyURLopener.__init__(self, *args)

#urllib._urlopener = AppURLopener()
############## URLLIB STUFF END ###################################

# TODO: Change _send*request()-functions to return result unmodified
#       and put xml-parsing to client functions.
# TODO: Change Plok-texts from this file to some more generic

class Comm:
    """
    Comm is a base class for subclass which handles all 
    communication (RPC-calls) to the server. 
    Comm offers 2 methods to send data to the HTTP-server:
    Comm._send_request and Comm._send_multipart_request.
    
    All RPC-calls return XML. Consult documentation for details.
    See example methods below. 
    
    After successful login() Comm keeps session id and uses it
    until logout is performed.
    """

    __id__ = u'$Id: Comm.py 1374 2007-04-13 05:22:01Z arista $'

    def __init__(self, host, script, useragent=None):
        try: # Parse revision and last change date
            ida = self.__id__.split(u" ")
            self.revision = ida[2]
            self.lastchangeddate = ida[3]
        except:
            self.revision = u'undefined'
            self.lastchangeddate = u'undefined'
        if useragent is None:
            self.ua = 'Comm.py/%s/%s' % (self.revision, self.lastchangeddate)
        self.host = host
        self.script = script
        self.url = "http://%s%s" % (host, script)
        self.sessionid = None
        
    def rpc_name(self):
        """
        Return the name of caller function.
        It is used when making a remote procedure call (RPC) to Plok-server. 
        """
        return sys._getframe(1).f_code.co_name
    
    def _send_request(self, operation, params):
        # NOTE: TEMPORARY TEST HERE:
        ##############################################################
        #return self._send_multipart_request(operation, params, {})
        ###############################################################
        """
        Send HTTP-request to the server using httplib and 
        return a HTTPResponse object.
        """
        params['operation'] = operation
        # convert all params-values to utf-8
        for key in params.keys():
            params[key] = csetconv.to_utf8(params[key])
        params = urllib.urlencode(params)
        # print params
        headers = {"Content-type": "application/x-www-form-urlencoded",
                   "User-Agent": self.ua,
                   }
        # Send session id in headers as a cookie
        if self.sessionid != None:
            headers["Cookie"] = "sessionid=%s;" % self.sessionid
        conn = httplib.HTTPConnection(self.host)
        try:
            conn.request("POST", self.script, params, headers)
        except:
            raise
        response = conn.getresponse()
        conn.close()
        #print response.read()
        #print response.getheaders()
        return response

    def _send_multipart_request(self, operation, params, files):
        """
        Send multipart HTTP-request to the server using http_poster.
        Request can contain file attachments.
        Return parsed request in an array.
        NOTE: please unicode only! All params must be unicode!
        """
        params['operation'] = operation
        param_list = []
        for key in params.keys():
            param_list.append((csetconv.to_utf8(key), csetconv.to_utf8(params[key])))
        headers = {"User-Agent": self.ua,
                  }
        if self.sessionid != None:
            headers["Cookie"] = "sessionid=%s;" % self.sessionid
        response  = http_poster.post_multipart(self.host, self.script, param_list, files, headers)
        #print response.read()
        #print response.getheaders()
        return response
 
    
    def login(self, username, password):
        """
        Do login with given username and password.
        """
        params = {'username': username, 'password' : password}
        response = self._send_request(self.rpc_name(), params)
        json_data = response.read()
        data = json.read(json_data)
        if "status" in data and data["status"] == "ok":
            self.sessionid = data["sessionid"]
        else:
            self.sessionid = None
        return data

    # TODO: login_sha()
    def login_md5(self, login, md5pw):
        """
        Send login and md5 encoded password to the server and
        return session id (32 hex) if login was successful. 
        Otherwise return error.
        """
        pass

    def logout(self):
        """
        End current session.
        """
        # TODO: Here we might want to check if sessionid exists
        params = {} # Session id is in cookie
        response = self._send_request(self.rpc_name(), params)
        json_data = response.read()
        data = json.read(json_data)
        if "status" in data and data["status"] == "ok":
            self.sessionid = None
        return data

    def sessioninfo(self):
        params = {}
        response = self._send_request(self.rpc_name(), params)
        json_data = response.read()
        data = json.read(json_data)
        return data


if __name__ == '__main__':
    server = u"localhost:8000"
    script = u'/api/'
    comm = Comm(server, script)
    x = comm.login(u"user", u"password")
    print x
    x = comm.logout()
    print x
