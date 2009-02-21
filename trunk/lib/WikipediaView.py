import Base
import appuifw
import key_codes
import e32
import TopWindow
import graphics
import time
import re
import os

class WikipediaView(Base.View):
    
    def __init__(self, parent):
        Base.View.__init__(self, parent)
        self.wikipedialist = [] # Contains the metadata all images found
        self.listbox = None

    def activate(self):
        Base.View.activate(self)
        appuifw.app.menu = [(u"Update images", self.update_wikipedialist),
                            #(u"Close", self.handle_close),
                            ]
        
        # Update always that's why True... 
        if True or len(self.wikipedialist) == 0:
            self.update_wikipedialist()
        #appuifw.note(u"%d" % len(self.wikipedialist), 'error')
        self.menu_entries = []
        now = time.time()
        for wikipediaitem in self.wikipedialist:
            self.menu_entries.append(((u"%s" % wikipediaitem["title"], 
                                       u"%d m %s" % (wikipediaitem["distance"], wikipediaitem["type"]))))
        if len(self.menu_entries) == 0:
            appuifw.note(u"No files available", 'error')
            self.parent.activate()
            return
        self.listbox = appuifw.Listbox(self.menu_entries, self.handle_select)
        appuifw.app.body = self.listbox

    def handle_select(self):
        i = self.listbox.current()
        choises = [u"Open in browser", u"Show image"]
        test = appuifw.popup_menu(choises, u"Select action:")
        if test is not None:
            if test == 0:
                import e32
                url = '4 http://fi.wikipedia.org/wiki/%s' % self.wikipedialist[i]["title"].replace(" ", "_") 
                b = 'BrowserNG.exe'
                 # the space between ' and " seems to be important so don't miss it!
                e32.start_exe(b, ' "%s"' % url, 1)
            elif test == 1:
                appuifw.note(u"%s Not implemented" % choises[test], 'error')
            else:
                appuifw.note(u"Not implemented: %s" % choises[test], 'error')
        #group_id = self.grouplist[i]["group_id"]
        #self.contentview.activate(group_id)


    def update_wikipedialist(self):
        params = {
                  }
        #if self.Main.has_fix(self.Main.pos):
        try:
            params["lat"] = u"%.6f" % self.Main.pos["position"]["latitude"]
            params["lon"] = u"%.6f" % self.Main.pos["position"]["longitude"]
        #else:
        except:
            appuifw.note(u"No GPS FIX, using default coordinates", 'error')
            params["lat"] = "60.175"
            params["lon"] = "24.93"
        data, response = self.Main.comm._send_request("get_wikipedia", params)
        if data["status"] == "ok" and "data" in data:
            self.wikipedialist = data["data"]
        else:
            try:
                message = data["message"]
            except:
                message = u"unknown error"
            appuifw.note(u"Error: %s" % message, 'error')
