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
    
    def login(self):
        if self.username is None:
            self.username = appuifw.query(u"Username for %s" % self.comm.host, "text", u"")
            if self.username is None:
                return
        if self.password is None:
            self.password = appuifw.query(u"Password for %s@%s" % (self.username, self.comm.host), "code", u"")
            if self.password is None:
                return
        params = {"username" : self.username,
                  "password" : self.password}
        return self._send_request("login", params=params,
                                  infotext=u"Logging in..."
                                  )

    def send_request(self, operation, 
                           params={}, 
                           files=[], 
                           infotext=u"",
                           require_session=True):
        if require_session:
            if self.comm.sessionid is None:
                data, response = self.login()
        return self.send_request(operation, params, files, infotext)

    def _send_request(self, operation, 
                            params={}, 
                            files=[], 
                            infotext=u""):
        ip = appuifw.InfoPopup()
        starttime = time.clock()
        if infotext:
            ip.show(infotext, (50, 50), 180000, 10, appuifw.EHLeftVTop)
        if len(files) == 0:
            data, response = self.comm._send_request(operation, params)
        else:
            # files-list contains a list of 3-element tuples, e.g.
            # files = [("filefield's name", "filename.ext", filedata)]
            data, response = self.comm._send_multipart_request(operation, params, files)
        duration = time.clock() - starttime
        ip.hide()
        if isinstance(data, dict) is False:
            appuifw.note(u"Invalid response from server", 'error')
        elif "status" in data and data["status"].startswith("error"):
            if "message" not in data:
                data["message"] = u"Unknown error in response"
            appuifw.note(u"%s" % data["message"], 'error')
        self.add_log(data, duration)
        #print self.log
        return data, response
        
    def add_log(self, data, duration):
        self.log.append({
            "status" : data["status"],
            "message" : data["message"],
            "time" : time.time(),
            "duration" : duration,
            "keys" : ",".join(data.keys()),
        })
