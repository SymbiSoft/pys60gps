import Base
import appuifw
import key_codes
import e32
import TopWindow
import graphics
import time
import re
import os
import urllib

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
            appuifw.note(u"No Wikipedia articles available", 'error')
            self.parent.activate()
            return
        self.listbox = appuifw.Listbox(self.menu_entries, self.handle_select)
        appuifw.app.body = self.listbox

    def temp_wlan_locate(self):
        try:
            import wlantools
        except:
            return None
        ip = appuifw.InfoPopup()
        ip.show(u"WLAN LOCATE...", (50, 50), 60000, 100, appuifw.EHLeftVTop)
        wlan_devices = wlantools.scan(False)
        wlan_list = [w['BSSID'] for w in wlan_devices]
        params = {"wlan_ids" : ",".join(wlan_list)}
        data, response = self.Main.comm._send_request("get_wlan_01", params)
        ip.hide()
        #print data
        if "status" in data and data["status"] == "ok":
            lon, lat = data["geojson"]["geometries"][0]["coordinates"]
            return lat, lon
        else:
            return None
            

    def handle_select(self):
        i = self.listbox.current()
        choises = [u"Open in browser"] # , u"Show image"]
        test = appuifw.popup_menu(choises, u"Select action:")
        if test is not None:
            if test == 0:
                import e32
                #baseurl = 'http://fi.wikipedia.org/wiki/%s'
                baseurl = u"http://wapedia.mobi/fi/%s"
                # Wapedia understands only quoted utf8 characters
                url = baseurl % urllib.quote(self.wikipedialist[i]["title"].replace(" ", "_").encode("utf8"))
                #print url
                browser_param = '4 %s' % url
                browser = 'BrowserNG.exe'
                # the space between ' and " seems to be important so don't miss it!
                e32.start_exe(browser, ' "%s"' % browser_param, 1)
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
        except:
            pass
        if not params:
            try:
                appuifw.note(u"No GPS FIX, using wlan coordinates", 'error')
                params["lat"], params["lon"] = ["%s" % x for x in self.temp_wlan_locate()]
            except:
                params["lat"] = "60.175"
                params["lon"] = "24.93"
                appuifw.note(u"No WLAN FIX, using default coordinates %(lat)s,%(lon)s" % params, 'error')
                #raise
        #print params
        ip = appuifw.InfoPopup()
        ip.show(u"Loading nearby Wikipedia titles...", (50, 50), 60000, 100, appuifw.EHLeftVTop)
        data, response = self.Main.comm._send_request("get_wikipedia", params)
        ip.hide()
        if data["status"] == "ok" and "data" in data:
            self.wikipedialist = data["data"]
        else:
            try:
                message = data["message"]
            except:
                message = u"unknown error"
            appuifw.note(u"Error: %s" % message, 'error')
