__id__ = "$Id$"

"""
Show some data in a Listbox
"""

import Base
import appuifw
import e32
import urllib
import time
import simplejson

class ListdataView(Base.TabView):

    def __init__(self, parent):
        Base.TabView.__init__(self, parent)
        self.name = "Data list"
        self.tabs.append((u"Main", MainTab(self)))
        self.servicelist = [] # The list downloaded from the server
        self.servicekeys = {} # The keywords from the list for easier access

    def activate(self):
        Base.TabView.activate(self)
        appuifw.app.menu = [(u"Close", self.close)]
        if len(self.servicelist) == 0:
            self.get_servicelist()
            # TODO: ask here which services should be activated
            self.update_tabs()
            #Base.TabView.activate(self)
        self.views[self.current_tab].activate()

    def update_tabs(self):
        self.tabs = self.tabs[:1] # Save only MainTab
        for service in self.servicelist:
            self.tabs.append((service["keyword"], 
                              DataView(self, service["keyword"])))
        Base.TabView.activate(self)

    def ask_services_to_activate(self):
        pass

    def get_servicelist(self):
        """Download the list of available services from the server"""
        ip = appuifw.InfoPopup()
        ip.show(u"Getting the list of available services...", (50, 50), 60000, 100, appuifw.EHLeftVTop)
        params = {}
        # TODO: geo stuff here too
        data, response = self.Main.comm._send_request("get_servicelist", params)
        ip.hide()
        if "status" in data and data["status"] == "ok" and \
           "servicelist" in data:
            self.servicelist = data["servicelist"]
            keys = {}
            for item in self.servicelist:
                keys[item["keyword"]] = item
                item["updated"] = time.time()
            self.servicekeys = keys
        elif "status" in data and "message" in data and \
           data["status"].startswith("error"):
            appuifw.note(u"%s" % data["message"], 'error')
        else:
            appuifw.note(u"Unknown error", 'error')
            print data

class MainTab(Base.View):
    """Show the list of available services."""

    def __init__(self, parent):
        Base.View.__init__(self, parent)
        self.active = False
        self.fontheight = 15
        self.lineheight = 17
        self.font = (u"Series 60 Sans", self.fontheight)

    def activate(self):
        appuifw.app.menu = [
                            (u"Update services", self.parent.get_servicelist),
                            (u"Close", self.parent.close),
                            ]
        appuifw.app.screen = "normal"
        self.canvas = appuifw.Canvas(redraw_callback=self.update)
        appuifw.app.body = self.canvas
    
    def update(self, dummy=(0,0,0,0)):
        start = 40
        color = 0x000000
        self.canvas.text((3,start), u"Enabled services:", font=self.font, fill=color)
        start = start + self.lineheight
        for service in self.parent.servicelist:
            start = start + self.lineheight
            self.canvas.text((3,start), service["title"], font=self.font, fill=color)

class DataView(Base.View):

    def __init__(self, parent, key):
        Base.View.__init__(self, parent)
        self.datalist = []
        self.key = key
        self.listbox = None
        self.updated = 0
        
    def activate(self):
        appuifw.app.menu = [
                            (u"Update list", self.get_datalist),
                            (u"Search", lambda: appuifw.note(u"Sorry, not implemented", "info")),
                            (u"Close", self.parent.close),
                            ]
        if len(self.datalist) == 0:
            self.get_datalist()
            pass
        self.menu_entries = []
        for item in self.datalist:
            self.menu_entries.append((item["title"], item["titleextra"]))
        # TODO: use set_list instead of creating a new listbox
        if len(self.menu_entries) > 0:
            self.listbox = appuifw.Listbox(self.menu_entries, self.handle_select)
            appuifw.app.body = self.listbox
        else:
            appuifw.note(u"List '%s' is empty" % (self.key), 'error')
            self.parent.current_tab = 0
            self.parent.activate()

    def handle_select(self):
        #i = self.listbox.current()
        choises = [u"Open in Browser"]
        choise = appuifw.popup_menu(choises, u"Select action:")
        if choise is not None:
            self.open_browser()

    def get_datalist(self):
        """Download the list of available services from the server"""
        ip = appuifw.InfoPopup()
        ip.show(u"Getting the data...", (50, 50), 60000, 10, appuifw.EHLeftVTop)
        params = {"key" : self.key}
        geo = self.Main.get_geolocation_params()
        if "lat" in geo and "lon" in geo:
            params["lat"] = geo["lat"] # Already str type
            params["lon"] = geo["lon"]
        params["geolocation"] = simplejson.dumps(geo)
        data, response = self.Main.comm._send_request("get_service", params)
        ip.hide()
        if "datalist" in data:
            self.datalist = data["datalist"]
            self.updated = time.time()
            self.activate()
        elif "status" in data and "message" in data and \
           data["status"].startswith("error"):
            appuifw.note(u"%s" % data["message"], 'error')
        else:
            appuifw.note(u"Unknown error", 'error')
            print data

    def open_browser(self):
        baseurl = self.parent.servicekeys[self.key]["urlpattern"]
        url = baseurl % urllib.quote(self.datalist[self.listbox.current()]["urlfiller"].encode("utf8"))
        browser_param = '4 %s' % url
        browser = 'BrowserNG.exe'
        # the space between ' and " seems to be important so don't miss it!
        e32.start_exe(browser, ' "%s"' % browser_param, 1)

"""
Example get_servicelist response:
  
{
 "status": "ok", 
 "message": "Found 2 services", 
 "servicelist": [
  {
   "urlpattern": "http://www.omatlahdot.fi/omatlahdot/web?stopid=%s&Submit=Hae&command=quicksearch&view=mobile", 
   "description": "HKL-omatl\u00e4hd\u00f6t", 
   "keyword": "Hkl", 
   "title": "HKL"
  }, 
  {
   "urlpattern": "http://wapedia.mobi/fi/%s", 
   "description": "Wikipedia-artikkelit (wapedia.mobi)", 
   "keyword": "Wiki", 
   "title": "Wikipedia"
  }
 ]
}
"""

