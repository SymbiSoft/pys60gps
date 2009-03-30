# $Id$

import Base

import base64
import httplib
import urllib
import time

import appuifw
import key_codes
import e32

from HelpView import HelpView
import simplejson

class TwitterView(Base.View):
    def __init__(self, parent):
        Base.View.__init__(self, parent)
        self.host = 'twitter.com'
        self.username = u""
        self.password = u""
        self.friends_timeline = []
        self.fontsize = 14
        self.delimiter = u">>> "
        self.t = appuifw.Text(u"")
        self.t.bind(key_codes.EKeySelect, self.send_statusupdate)
        self.help = HelpView(self, 
            u"""To send status update choose "Send message" and start typing.
             
When you have finished, choose "OK" and your message will be sent immediately.
""")

    def _get_http_headers(self):
        base64string = base64.encodestring('%s:%s' % (self.username, 
                                                      self.password))[:-1]
        authheader =  "Basic %s" % base64string
        headers = {}
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["Authorization"] = authheader
        return headers



    def get_friends_timeline(self):
        ip = appuifw.InfoPopup()
        ip.show(u"Loading friends_timeline", (50, 50), 60000, 100, appuifw.EHLeftVTop)
        params = {}
        headers = self._get_http_headers()
        params = urllib.urlencode(params)
        conn = httplib.HTTPConnection(self.host)
        service = '/statuses/friends_timeline.json'
        conn.request("POST", service, params, headers)
        response = conn.getresponse()
        json = response.read()
        conn.close()
        # try except here
        data = simplejson.loads(json)
        ip.hide()
        # Check we got valid response
        if "error" in data:
            appuifw.note(u"%s" % data["error"], 'error')
        else:
            #data.reverse()
            self.friends_timeline = data
        self.update_message_view()

    def send_statusupdate(self):
        # First try to find inline message
        text = self.get_message()
        # If not found, ask with appuifw.query
        if not text:
            text = appuifw.query(u"Message (max 80 chr)", "text", u"")
            if not text:
                return
        ip = appuifw.InfoPopup()
        ip.show(u"Sending status update", (50, 50), 60000, 100, appuifw.EHLeftVTop)
        headers = self._get_http_headers()
        params = {}
        params["status"] = text.encode("utf8")
        params["source"] = "pys60gps"
        params = urllib.urlencode(params)
        conn = httplib.HTTPConnection(self.host)
        service = '/statuses/update.json'
        conn.request("POST", service, params, headers)
        response = conn.getresponse()
        json = response.read()
        conn.close()
        # try except here
        data = simplejson.loads(json)
        ip.hide()
        # Check we got valid response
        if "error" in data:
            appuifw.note(u"%s" % data["error"], 'error')
        elif "text" in data:
            appuifw.note(u"Status sent: %s" % data["text"], 'info')
        else:
            print data
        
    def add_text(self, timestamp, user, text):
        self.t.font = (u"dense", self.fontsize)
        self.t.style = appuifw.STYLE_BOLD
        self.t.color = (200,0,0)
        self.t.add(u"%s: " % (user)) # NOTE: must be unicode here
        self.t.style = 0
        self.t.add(u"%s\n" % (timestamp)) # NOTE: must be unicode here
        self.t.color = (0,0,0)
        self.t.add(u">> %s\n" % (text))
    
    def get_message(self):
        parts = self.t.get().split(self.delimiter)
        #appuifw.note(u"%d" % len(parts), 'error')
        if len(parts) > 1:
            message = parts[-1].strip()
        else:
            self.update_message_view()
            message = None
        # Avoid crash when T9 is on and the last word is underlined
        self.t.add(u"\n") 
        return message

    def update_message_view(self):
        self.t.clear()
        self.menu_entries = []
        for message in self.friends_timeline:
            self.add_text(message["created_at"], 
                          message["user"]["screen_name"], message["text"])
        self.t.font = (u"dense", int(self.fontsize/4*3))
        #self.t.add(u"--- Localtime: %s ---\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
        #self.t.font = (u"dense", self.fontsize)
        #self.t.add(self.delimiter)
        appuifw.app.body = self.t
        self.t.set_pos(0)

    def activate(self):
        """Set main menu to app.body and left menu entries."""
        Base.View.activate(self)
        if not self.username:
            value = appuifw.query(u"Enter you Twitter username", "text", self.username)
            if value is not None:
                self.username = value
        if not self.password:
            value = appuifw.query(u"Enter you Twitter password", "code", self.password)
            if value is not None:
                self.password = value

        if len(self.friends_timeline) == 0:
            self.get_friends_timeline()
        self.update_message_view()
        appuifw.app.menu = [
            (u"Send status update",self.send_statusupdate),
            (u"Refresh friends timeline",self.get_friends_timeline),
            (u"Increase font size", lambda:self.set_fontsize(2)),
            (u"Decrease font size", lambda:self.set_fontsize(-2)),
            (u"Set font size", self.set_fontsize),
            (u"Help",self.help.activate),
            (u"Close", self.parent.activate),
        ]

    def set_fontsize(self, fs = 0):
        if fs == 0:
            fs = appuifw.query(u"Font size","number", self.fontsize)
        else:
            fs = self.fontsize + fs
        if fs:
            if fs < 6: fs = 6
            if fs > 32: fs = 32
            self.fontsize = fs
            self.update_message_view()
            # FIXME this doesn't unfortunately work: 
            # settings.ini will be overwritten in every start 
            #self.Main.config["chat_fontsize"] = fs
            #self.Main.save_config()
        
