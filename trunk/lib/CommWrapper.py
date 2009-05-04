import time
import appuifw
#import e32
#import Comm
#import socket
#import simplejson
#import os
#import re

class CommWrapper:

    def __init__(self, comm, username=None, password=None):
        self.comm = comm
        self.username = username or comm.username
        self.password = password or comm.password
        self.log = []
        self.login_tries = 0
        self.login_failed = False

    def _check_username_password(self):
        error = {"status" : "error", 
                 "message" : "Login failed, username and/or password is missing."}
        if self.username is None:
            self.username = appuifw.query(u"Username for %s" % self.comm.host, 
                                          "text", u"")
            if self.username is None:
                return error, None
        if self.password is None:
            self.password = appuifw.query(u"Password for %s@%s" % 
                                          (self.username, self.comm.host), 
                                          "code", u"")
            if self.password is None:
                return error, None
    
    def login(self):
        """
        Perform login to the server. Request username and password if they
        are not already set.
        """
        data, response = self.comm.login(self.username, self.password)
        self.login_tries += 1
        if ("status" in data 
            and data["status"].startswith("error")):
            appuifw.note(data["message"], 'error')
            self.login_failed = True
        return data, response

    def send_request(self, operation, 
                           params={}, 
                           files=[], 
                           infotext=u"",
                           filename=None,
                           require_session=True):
        if require_session:
            if self.comm.sessionid is None:
                self._check_username_password()
                ip = appuifw.InfoPopup()
                if infotext:
                    ip.show(u"Logging in %s@%s" % (self.username, self.comm.host), 
                            (50, 50), 180000, 10, appuifw.EHLeftVTop)
                starttime = time.clock()
                data, response = self.login()
                duration = time.clock() - starttime
                self.add_log(data, operation, duration)
                ip.hide()
                if data["status"].startswith("error"):
                    return data, response
        return self._send_request(operation, params, files, filename, infotext)

    def _send_request(self, operation, 
                            params={}, 
                            files=[], 
                            filename=None,
                            infotext=u""):
        ip = appuifw.InfoPopup()
        starttime = time.clock()
        if infotext:
            ip.show(infotext, (50, 50), 180000, 10, appuifw.EHLeftVTop)
        if len(files) == 0:
            data, response = self.comm._send_request(operation, params, filename)
        else:
            # files-list contains a list of 3-element tuples, e.g.
            # files = [("filefield's name", "filename.ext", filedata)]
            data, response = self.comm._send_multipart_request(operation, params, files)
        duration = time.clock() - starttime
        ip.hide()
        #print self.comm.sessionid, data
        #print type(data)
        if isinstance(data, dict):
            if "status" in data and data["status"].startswith("error"):
                if "message" not in data:
                    data["message"] = u"Unknown error in response"
                appuifw.note(u"%s" % data["message"], 'error')
        elif filename is None:
            appuifw.note(u"Invalid response from server", 'error')
        else: # Data was e.g. binary data (a file)
            data = {"status" : u"unknown", "message" : "binary data"}
        self.add_log(data, operation, duration)
        #print self.log
        return data, response
        
    def add_log(self, data, operation, duration):
        # TODO: add max log entries
        # TODO: implement a log viewer
        self.log.append({
            "status" : data["status"],
            "message" : data["message"],
            "time" : time.time(),
            "duration" : duration,
            "operation" : operation,
            "keys" : ",".join(data.keys()),
        })
