__id__ = "$Id$"

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

import random
def scan():
    return [
{'Capability': 1025, 'BeaconInterval': 100, 'SecurityMode': 'Open', 
 'SSID': u'linksys', 'BSSID': u'00:14:BF:A5:1D:4B', 'ConnectionMode': 'Infrastructure', 
 'SupportedRates': u'82848B9624B0486C', 'Channel': 8, 'RxLevel': random.randint(-100, -50)}, 
{'Capability': 1, 'BeaconInterval': 100, 'SecurityMode': 'Open', 
 'SSID': u'MyWLAN', 'BSSID': u'00:02:72:43:57:E1', 'ConnectionMode': 'Infrastructure', 
 'SupportedRates': u'82848B96', 'Channel': 11, 'RxLevel': random.randint(-100, -50)}, 
{'Capability': 17, 'BeaconInterval': 100, 'SecurityMode': 'WpaPsk', 
 'SSID': u'RMWLAN', 'BSSID': u'00:02:72:43:56:87', 'ConnectionMode': 'Infrastructure', 
 'SupportedRates': u'82848B96', 'Channel': 11, 'RxLevel': random.randint(-100, -50)},
{'Capability': 1041, 'BeaconInterval': 100, 'SecurityMode': 'WpaPsk', 
 'SSID': u'', 'BSSID': u'00:13:D3:79:99:8F', 'ConnectionMode': 'Infrastructure', 
 'SupportedRates': u'82848B96', 'Channel': 11, 'RxLevel': random.randint(-100, -50)}
 ]


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
            import location
            if e32.in_emulator():
                wlan_devices = scan()
            else:
                import wlantools
                wlan_devices = wlantools.scan(False)
        except:
            appuifw.note(u"No wlantools available!", 'error')
            return None
        ip = appuifw.InfoPopup()
        ip.show(u"Getting WLAN location...", (50, 50), 60000, 100, appuifw.EHLeftVTop)
        wlan_list = [w['BSSID'] for w in wlan_devices]
        params = {"wlan_ids" : ",".join(wlan_list)}
        gsm_location = location.gsm_location()
        #print gsm_location
        #print type(gsm_location)
        if gsm_location and len(gsm_location) > 0:
            params["cellid"] = ",".join([str(x) for x in gsm_location])
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
        pos = self.Main.pos
        if self.Main.has_fix(pos):
            try:
                #lat = pos["position"]["latitude"]
                #lon = pos["position"]["longitude"]
                params["lat"] = u"%.6f" % pos["position"]["latitude"]
                params["lon"] = u"%.6f" % pos["position"]["longitude"]
            except:
                pass
        if not params:
            try:
                appuifw.note(u"No GPS FIX, using wlan coordinates", 'error')
                latlon = self.temp_wlan_locate()
                if latlon:
                    params["lat"], params["lon"] = ["%s" % x for x in latlon]
            except:
                params["lat"] = "60.175"
                params["lon"] = "24.93"
                appuifw.note(u"No WLAN FIX, using default coordinates %(lat)s,%(lon)s" % params, 'error')
                raise
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
