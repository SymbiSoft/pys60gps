# -*- coding: utf8 -*-
# $Id$

# DO NOT remove this
SIS_VERSION = "0.3.18"
APP_TITLE = u"PyS60GPS"

import appuifw
import e32
# appuifw.app.orientation = 'portrait'
import time

class Logger:
    def __init__ (self, filename = 'C:\\data\\pys60gps.log'):
        self.fname = filename
    def write(self, obj):
        timestamp = time.strftime("%Y%m%d-%H%M%S\r\n")
        log = open(self.fname, 'at')
        log.write(timestamp)
        log.write(obj)
        log.write("\r\n")
        log.close()
    def flush(self):
        pass


#### STARTUP "splash screen"
def startup_screen(dummy=(0, 0, 0, 0)):
    pass
    
def draw_startup_screen(canvas, text):
    canvas.clear()
    canvas.text((10, 50), u"Starting up", font=(u"Series 60 Sans", 30), fill=0x333333)
    canvas.text((10, 70), u"TODO: insert pretty startup picture here", font=(u"Series 60 Sans", 12), fill=0xff3333)
    canvas.text((10, 100), u"Importing modules", font=(u"Series 60 Sans", 20), fill=0x3333ff)
    canvas.text((10, 115), text, font=(u"Series 60 Sans", 15), fill=0x3333ff)
    e32.ao_sleep(0.01) # Wait until the canvas has been drawn

canvas = appuifw.Canvas(redraw_callback=startup_screen)
appuifw.app.body = canvas
draw_startup_screen(canvas, u"sys, os, btsocket, sysinfo, re")
import sys

my_log = Logger()
#sys.stderr = sys.stdout = my_log

import os
try:
    import btsocket # pys60 > 1.9
except:
    import socket as btsocket
import sysinfo
import re
draw_startup_screen(canvas, u"time, copy")
import time
import copy
draw_startup_screen(canvas, u"zipfile")
import zipfile
draw_startup_screen(canvas, u"positioning, location")
import positioning
import location
draw_startup_screen(canvas, u"key_codes, graphics, audio")
import key_codes
import graphics
import audio
draw_startup_screen(canvas, u"LatLongUTMconversios")
import LatLongUTMconversion
draw_startup_screen(canvas, u"Calculate")
import Calculate
draw_startup_screen(canvas, u"simplejson")
import simplejson
draw_startup_screen(canvas, u"locationtools")
import locationtools

draw_startup_screen(canvas, u"pys60gpstools")
import pys60gpstools

draw_startup_screen(canvas, u"Comm")
import Comm

draw_startup_screen(canvas, u"TrackView")
import TrackView; reload(TrackView)

draw_startup_screen(canvas, u"SimpleChatView")
from SimpleChatView import SimpleChatView

draw_startup_screen(canvas, u"TwitterView")
from TwitterView import TwitterView

draw_startup_screen(canvas, u"ImageGalleryView")
from ImageGalleryView import ImageGalleryView

draw_startup_screen(canvas, u"PlokView")
from PlokView import PlokView

draw_startup_screen(canvas, u"ListdataView")
from ListdataView import ListdataView

draw_startup_screen(canvas, u"TestView")
import TestView; reload(TestView)

draw_startup_screen(canvas, u"MiscView")
from MiscView import SysinfoView, SysInfoTab, E32InfoTab, MemTab, GsmTab, \
                     WlanTab, GpsView, GpsInfoTab, GpsSpeedTab, WlanView


class GpsApp:
    __id__ = u'$Id$'
    __version__ = __id__

    def __init__(self):
        self.startgmtime = time.time() + time.altzone # Startup time
        appuifw.app.title = u"Pys60Gps"
        self.Main = self # This is the base of all views, tabs etc.
        self.lock = e32.Ao_lock()
        appuifw.app.exit_key_handler = self.exit_key_handler
        self.running = True
        self.focus = True
        appuifw.app.focus = self.focus_callback # Set up focus callback
        self.ip = appuifw.InfoPopup()

        self.read_position_running = False
        self.downloading_pois_test = False # TEMP
        # Create a directory to contain all gathered and downloaded data. Note '\\' in the first argument.
        self.datadir = os.path.join(u"C:\\Data", u"Pys60Gps")
        if not os.path.exists(self.datadir):
            os.makedirs(self.datadir)
        # Create a directory for temporary data
        self.cachedir = u"D:\\Pys60Gps"
        if not os.path.exists(self.cachedir):
            os.makedirs(self.cachedir)
        # Configuration/settings
        self.config_file = os.path.join(self.datadir, "settings.ini")
        self.config = {} # TODO: read these from a configuration file
        self.apid = None # Default access point id
        self.apo = None # Default access point 
        self.read_config()
        #if self.config.has_key("apid"):
        #    self._select_access_point(self.config["apid"])
        # Center meridian
        self.ask_accesspoint()
        #self.select_access_point()
        self.LongOrigin = None
        # Some counters
        self.counters = {"cellid": 0,
                         "wlan": 0,
                         "bluetooth": 0,
                         "track": 0,
                         "delivery": 0,
                         }
        self.scanning = {"wlan":False,
                         "bluetooth":False,
                         }
        # FIXME: temporarely here, these should be in settings
        # Track simplification parameters
        self.LIMITS = {
            'max_linediff': 5.0, # meters
            'min_dist': 10.0, # meters
            'max_dist': 1000.0, # meters
            'min_time': 0.0, # seconds
            'max_time': 60.0, # seconds
            'max_anglediff': 30.0, # degrees
            'max_dist_estimate': 50.0, # meters        
        }

        # Data-repository
        self.data = {}
        self.data["gsm_location"] = [] # GSM-cellid history list (location.gsm_location())
        self.data["wlan"] = [] # wlan scan history list (wlantools.scan())
        self.data["bluetooth"] = [] # Bluetooth scan history list (lightblue.finddevices())
        # New simplified style: TODO remove old ones and rename new ones to old name
        self.data["cellid_new"] = [] # GSM-cellid history list (location.gsm_location())
        self.data["wlan_new"] = [] # Wlan scan history list (wlantools.scan())
        self.data["bluetooth_new"] = [] # Bluetooth scan history list (lightblue.finddevices())
        self.data["track_new"] = [] # Position history list (positioning.position())
        self.data["delivery_new"] = [] # All data to be sent to the server
        # GPS-position
        self.pos = {} # Contains always the latest position-record
        self.simple_pos = {} # Contains always the latest position-record
        self.trackcalc = {} # Contains handle_trkpt()'s result dict
        self.data["position"] = [] # Position history list (positioning.position())
        self.pos_estimate = {} # Contains estimated location, calculated from the latest history point
        self.data["position_debug"] = [] # latest "max_debugpoints" 
        # POIs
        self.data["pois_private"] = []
        self.data["pois_downloaded"] = []
        self.data["pois_downloaded_new"] = []
        self.key = u""
        # Timers
        # TODO put all started timers here so they can be cancelled when leaving program
        #self.timers = {}
        self.comm = Comm.Comm(self.config["host"],
                              self.config["script"],
                              username=self.config["username"],
                              password=self.config["password"])
        # temporary solution to handle speed data (to be removed/changed)
        self.speed_history = []
        # Put all menu entries and views as tuples into a sequence
        self.menu_entries = []
        self.menu_entries.append(((u"Track"), TrackView.TrackView(self)))
        plokcomm = Comm.Comm(self.config["plokhost"], 
                             self.config["plokscript"],
                             username=self.config["username"],
                             password=self.config["plokpassword"])
        self.menu_entries.append(((u"Images"), ImageGalleryView(self, plokcomm)))
        self.menu_entries.append(((u"Latest Ploks"), PlokView(self, plokcomm)))
        self.menu_entries.append(((u"Plok.in chat"), SimpleChatView(self, plokcomm)))
        self.menu_entries.append(((u"Nearby"), ListdataView(self)))
        self.menu_entries.append(((u"Opennetmap.org chat"), SimpleChatView(self, self.comm)))
        # self.menu_entries.append(((u"Twitter"), TwitterView(self)))
        self.menu_entries.append(((u"Sysinfo"), SysinfoView(self)))
        self.menu_entries.append(((u"Tests"), TestView.TestView(self)))
        self.menu_entries.append(((u"WLAN"), WlanView(self)))
        self.menu_entries.append(((u"GPS Info"), GpsView(self)))
        # Create main menu from that sequence
        self.main_menu = [item[0] for item in self.menu_entries]
        # Create list of views from that sequence
        self.views = [item[1] for item in self.menu_entries]
        # Create a listbox from main_menu and set select-handler
        self.listbox = appuifw.Listbox(self.main_menu, self.handle_select)
        self.activate()
        #print self.read_log_cache_filenames("track")

    def get_sis_version(self):
        # self.get_geolocation_params()
        return SIS_VERSION

    def select_access_point(self, apid = None):
        if self.apid == None:
            self.apid = btsocket.select_access_point()
        if self.apid:
            self.apo = btsocket.access_point(self.apid)
            btsocket.set_default_access_point(self.apo)
            #self.apo.start()

    def ask_accesspoint(self):
        """One more version to select access point"""
        ap_dict = btsocket.access_points()    # 'iapid' and 'name' in dict
        sel_item = appuifw.popup_menu([i['name'] for i in ap_dict],
                                      u"Select network to use")
        if sel_item != None:    # != Cancel
            if self.apo:
                self.apo.stop()      
            self.apid = ap_dict[sel_item]['iapid']
            self.apo = btsocket.access_point(self.apid)
            btsocket.set_default_access_point(self.apo)

    def _select_access_point(self, apid = None):
        """
        Shortcut for btsocket.select_access_point() 
        TODO: save selected access point to the config
        TODO: allow user to change access point later
        """
        if apid is not None:
            self.apid = apid
        else:
            access_points = btsocket.access_points()
            sort_key = "iapid"
            decorated = [(dict_[sort_key], dict_) for dict_ in access_points]
            decorated.sort()
            access_points = [dict_ for (key, dict_) in decorated]
            ap_names = [dict_["name"] for dict_ in access_points]
            ap_ids = [dict_["iapid"] for dict_ in access_points]
            selected = appuifw.selection_list(ap_names, search_field=1)
            #print selected, ap_names[selected], ap_ids[selected]
            if selected is not None:
                self.apid = ap_ids[selected]
        if self.apid:
            self.apo = btsocket.access_point(self.apid)
            btsocket.set_default_access_point(self.apo)
            self.config["apid"] = self.apid
            self.save_config()
            self._update_menu()
            return self.apid

    def read_config(self):
        data = {}
        try:
            f = open(self.config_file, "rt")
            data = eval(f.read())
            #data = f.read()
            f.close()
        except:
            appuifw.note(u"Can't open saved settings. Generating new one with predefined values.", 'error')
            # raise
        # List here ALL POSSIBLE configuration keys, so they will be initialized
        defaults = {
            "max_speed_history_points" : 200,
            "min_trackpoint_distance" : 1000, # meters
            "estimated_error_radius" : 50, # meters
            "max_estimation_vector_distance" : 10, # meters
            "max_trackpoints" : 300,
            "max_debugpoints" : 120,
            "min_cellid_time" : 20,
            "max_cellid_time" : 600,
            "max_cellid_dist" : 500,
            "min_wlan_time" : 6,
            "max_wlan_time" : 600,
            "max_wlan_dist" : 100,
            "max_wlan_speed" : 60,
            "track_debug" : False,
            "username" : None,
            "password" : u"",
            "group" : None,
            "apid" : None,
            "host" : u"opennetmap.org",
            "script" : u"/api/",
            "plokhost" : u"www.plok.in", # Temporary solution to handle 2 different Comm-servers
            "plokscript" : u"/api/",
            "plokpassword" : u"",
        }
        # List here all configuration keys, which must be defined before use
        # If a config key has key "function", it's called to define value
        # TODO: make some order for these
        mandatory = {
            "username" : {"querytext" : u"Give nickname", 
                          "valuetype" : "text", 
                          "default" : u'',
                          "canceltext" : u'Nickname is mandatory',
                          },
            "group"    : {"querytext" : u"Give group name (cancel for default group)", 
                          "valuetype" : "text", 
                          "default" : u'',
                          "canceltext" : None,
                          },
#            "apid"    : {"querytext" : u"Select default access point (cancel for no default access point)", 
#                          "valuetype" : "function",
#                          "default" : u'',
#                          "canceltext" : None,
#                          "function" : self._select_access_point,
#                          },
        }
        # Loop all possible keys (found from defaults)
        for key in defaults.keys():
            if data.has_key(key): # Use the value found from the data
                defaults[key] = data[key]
            elif mandatory.has_key(key) and defaults[key] is None: # Ask mandatory values from the user
                value = None
                if mandatory[key].has_key("function"): # if defined, call the "function"
                    appuifw.note(mandatory[key]["querytext"], 'info')
                    value = mandatory[key]["function"]() # "function" must return a value
                else:
                    while value is None:
                        value = appuifw.query(mandatory[key]["querytext"], 
                                              mandatory[key]["valuetype"], 
                                              mandatory[key]["default"])
                        if value is None and mandatory[key]["canceltext"]: 
                            appuifw.note(mandatory[key]["canceltext"], 'error')
                        elif value is None: # If canceltext is u"", change value None to u""
                            value = u""
                defaults[key] = value
        self.config = defaults
        self.save_config()
        
    def save_config(self):
        f = open(self.config_file, "wt")
        f.write(repr(self.config))
        f.close()

    def reset_config(self):
        if appuifw.query(u'Confirm configuration reset', 'query') is True:
            os.remove(self.config_file)
            # TODO: create combined exit handler
            self.save_log_cache("track")
            self.save_log_cache("cellid") 
            self.save_log_cache("wlan") 
            appuifw.note(u"You need to restart program now.", 'info')
            self.running = False
            self.lock.signal()
            appuifw.app.exit_key_handler = None
            appuifw.app.set_tabs([u"Back to normal"], lambda x: None)

    def set_scan_config(self, profile):
        """
        First attempt to make more easily changeable scanning profile.
        TODO: a form to create and manage profiles (for advanged users) 
        """
        profiles = {}
        profiles["lazy"] = {
            "max_cellid_time" : 600,
            "max_cellid_dist" : 500,
            "min_wlan_time" : 6,
            "max_wlan_time" : 3600,
            "max_wlan_dist" : 10000,
        }
        profiles["turbo"] = {
            "max_cellid_time" : 180,
            "max_cellid_dist" : 100,
            "min_wlan_time" : 6,
            "max_wlan_time" : 60,
            "max_wlan_dist" : 50,
        }
        for key in profiles[profile]:
            self.config[key] = profiles[profile][key]
        self.save_config()
        self._update_menu()

    # FIXME: part of this is also in WlanView
    def get_geolocation_params(self):
        """
        Find all gps, gsm and wlan signals currently available.
        """
        geolocation = {"version" : "0.0.2"}
        # Try to get gps location
        simple_pos = self.simple_pos
        if pys60gpstools.has_fix(simple_pos):
            geolocation["lat"] = "%.6f" % pos['lat']
            geolocation["lon"] = "%.6f" % pos['lon']
        # Try to scan wlan base stations
        wlan_devices = []
        try:
            import wlantools
            wlan_devices = wlantools.scan(False)
        except Exception, error:
            if e32.in_emulator():
                time.sleep(1)
                import random
                wlan_devices = [
                    {'Capability': 1, 'BeaconInterval': 100, 'SecurityMode': 'Open', 
                     'SSID': u'MyWLAN', 'BSSID': u'00:02:72:43:57:E1', 'ConnectionMode': 'Infrastructure', 
                     'SupportedRates': u'82848B96', 'Channel': 11, 'RxLevel': random.randint(-100, -50)}, 
                    {'Capability': 17, 'BeaconInterval': 100, 'SecurityMode': 'WpaPsk', 
                     'SSID': u'RMWLAN', 'BSSID': u'00:02:72:43:56:87', 'ConnectionMode': 'Infrastructure', 
                     'SupportedRates': u'82848B96', 'Channel': 11, 'RxLevel': random.randint(-100, -50)},
                ]
        # DSU-sort by RxLevel
        decorated  = [(i['RxLevel'], i) for i in wlan_devices]
        decorated.sort()
        decorated.reverse()
        wlan_devices = [item for (name, item) in decorated]
        wlan_list = ["%(BSSID)s,%(RxLevel)s" % (w) for w in wlan_devices]
        geolocation["wlanids"] = ";".join(wlan_list)
        # Try to get cellid (note the symbian bug, 
        # cellid is not available when the radio is on!)
        # TODO: use cached gsm_location
        gsm_location = location.gsm_location()
        if gsm_location and len(gsm_location) > 0:
            geolocation["cellids"] = "%s,%s" % (":".join([str(x) for x in gsm_location]),
                                           sysinfo.signal_dbm())
        # print geolocation
        return geolocation

    # FIXME: part of this is also in WlanView
    # DEPRECATED
    def temp_get_radio_params(self):
        if e32.in_emulator():
            time.sleep(1)
            import random
            wlan_devices = [
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
        else:
            try:
                import wlantools
                wlan_devices = wlantools.scan(False)
            except Exception, error:
                appuifw.note(u"No wlantools.", 'error')
                return {"error":unicode(error)}
        # DSU-sort by RxLevel
        decorated  = [(i['RxLevel'], i) for i in wlan_devices]
        decorated.sort()
        decorated.reverse()
        wlan_devices = [item for (name, item) in decorated]
        wlan_list = [w['BSSID'] for w in wlan_devices]
        params = {"wlan_ids" : ",".join(wlan_list)}
        gsm_location = location.gsm_location()
        if gsm_location and len(gsm_location) > 0:
            params["cellid"] = ",".join([str(x) for x in gsm_location])
        return params


    def download_pois_new(self, simple_pos = None):
        """
        Download geojson objects from the internet using Comm-module.
        """
        self.downloading_pois_test = True
        self.key = appuifw.query(u"Keyword", "text", self.key)
        if self.key is None: 
            self.downloading_pois_test = False
            return
        # if self.key == 'loctest':
        #     wlan_ids = ",".join([x['SSID'] for x in wlantools.scan()]) # or something
        params = self.temp_get_radio_params()
        params.update({"key" : self.key,
                  "username" : str(self.config["username"]),
                  "group" : str(self.config["group"]),
                  "pys60gps_version" : self.get_sis_version(),
                  })
        if simple_pos == None:
            # Try current pos
            if pys60gpstools.has_fix(self.simple_pos):
                simple_pos = self.simple_pos
            # Try latest pos in tracklog
            elif (len(self.data["track_new"]) > 0 and \
                  pys60gpstools.has_fix(self.data["track_new"][-1])):
                simple_pos = self.data["track_new"][-1]
            else:
                appuifw.note(u"Can't download POIs, position unknown.", 'error')
                return
        params["lat"] = "%.6f" % simple_pos['lat']
        params["lon"] = "%.6f" % simple_pos['lon']
        # Testing
        #params["lat"] = "60.275"
        #params["lon"] = "24.98"
        e32.ao_sleep(0.05) # let the querypopup disappear
        self.ip.show(u"Downloading...", (50, 50), 60000, 100, appuifw.EHLeftVTop)
        data, response = self.comm._send_request("get_pois", params)
        self.ip.hide()
        geometries = []
        if data["status"].startswith("error"): 
            appuifw.note(u"Error occurred: %s" % data["message"], 'error')
        elif "geojson" in data:
            if "type" in data["geojson"] and data["geojson"]["type"] ==  "GeometryCollection":
                geometries = data["geojson"]["geometries"]
            else:
                geometries = data["geojson"]
            # appuifw.note(u"Got %s objects!" % len(geometries), 'info')
        else:
            appuifw.note(u"Did not find geojson from response. Maybe wrong keyword or no objects in neighbourhood?", 'error')
        #print geometries
        self.data["pois_downloaded_new"] = []
        for g in geometries:
            p = {}
            if 'title' in g['properties']:
                p['text'] = g['properties']['title']
            else:
                p['text'] = u''
            p['lon'], p['lat'] = g["coordinates"]
            locationtools.set_fake_utm(p, self.LongOrigin)
            self.data["pois_downloaded_new"].append(p)
        #appuifw.note(u"pois %d" %len(self.data["pois_downloaded_new"]), 'error')
        self.downloading_pois_test = False
        #self.data["pois_downloaded_new"] = geometries

    def _update_menu(self):
        """Update main view's left menu."""
        if self.read_position_running == True:
            gps_onoff = u"OFF"
        else:
            gps_onoff = u"ON"

        profile_menu = (u"Scan profile", (
            (u"Lazy", lambda:self.set_scan_config("lazy")),
            (u"Turbo", lambda:self.set_scan_config("turbo")),
        ))
        
        set_scan_params_menu = (u"Set scan params", (
            # CELL ID settings
            (u"max_cellid_time (%d)" % self.config["max_cellid_time"], 
                lambda:self.set_config_var(u"max_cellid_time", "number", "max_cellid_time")),
                
            (u"min_cellid_time (%d)" % self.config["min_cellid_time"], 
                lambda:self.set_config_var(u"min_cellid_time", "number", "min_cellid_time")),
                
            (u"max_cellid_dist (%d)" % self.config["max_cellid_dist"], 
                lambda:self.set_config_var(u"max_cellid_dist ", "number", "max_cellid_dist")),
                
            (u"max_wlan_time (%d)" % self.config["max_wlan_time"], 
                lambda:self.set_config_var(u"max_wlan_time ", "number", "max_wlan_time")),
                
            (u"min_wlan_time (%d)" % self.config["min_wlan_time"], 
                lambda:self.set_config_var(u"Estimation ", "number", "estimated_error_radius")),
                
            (u"max_wlan_dist (%d)" % self.config["max_wlan_dist"], 
                lambda:self.set_config_var(u"max_wlan_dist ", "number", "max_wlan_dist")),

            (u"max_wlan_speed (%d) km/h" % self.config["max_wlan_speed"], 
                lambda:self.set_config_var(u"max_wlan_speed ", "number", "max_wlan_speed")),

        ))

        set_menu = (u"Set", (
#            (u"Toggle debug", self.toggle_debug),
            (u"Max trackpoints (%d)" % self.config["max_trackpoints"], 
                lambda:self.set_config_var(u"Max points", "number", "max_trackpoints")),
            (u"Trackpoint dist (%d)" % self.config["min_trackpoint_distance"], 
                lambda:self.set_config_var(u"Trackpoint dist", "number", "min_trackpoint_distance")),
            (u"Est.vector dist (%d)" % self.config["max_estimation_vector_distance"], 
                lambda:self.set_config_var(u"Trackpoint dist", "number", "max_estimation_vector_distance")),
#            (u"Estimation circle (%d)" % self.config["estimated_error_radius"], 
#                lambda:self.set_config_var(u"Estimation circle", "number", "estimated_error_radius")),

            (u"Username (%s)" % self.config["username"], 
                lambda:self.set_config_var(u"Nickname", "text", "username")),
            (u"Password (%s)" % u"*****", 
                lambda:self.set_config_var(u"Password", "code", "password")),
#            (u"Group (%s)" % self.config["group"], 
#                lambda:self.set_config_var(u"Group", "text", "group")),
            (u"Host (%s)" % self.config["host"], 
                lambda:self.set_config_var(u"Host[:port]", "text", "host")),
            #(u"Script (%s)" % self.config["script"], 
            #    lambda:self.set_config_var(u"Script", "text", "script")),
            (u"Access point" , # TODO: show the name instead of apid 
                lambda:self.ask_accesspoint()),
            #(u"Access point (%s)" % self.config["apid"], # TODO: show the name instead of apid 
            #    lambda:self._select_access_point()),
        ))
            
        plok_menu = (u"Plok", (
            (u"PlokHost (%s)" % self.config["plokhost"], 
                lambda:self.set_config_var(u"PlokHost[:port]", "text", "plokhost")),
            #(u"PlokScript (%s)" % self.config["plokscript"], 
            #    lambda:self.set_config_var(u"PlokScript", "text", "plokscript")),
            (u"Plok Password (*****)", 
                lambda:self.set_config_var(u"Plok Password", "code", "plokpassword")),
        ))
            

        # Remember 30 menu items totally at MOST!
        appuifw.app.menu = [
            (u"Select",self.handle_select),
            (u"GPS %s" % (gps_onoff),self.start_read_position),
            profile_menu,
            set_scan_params_menu,
            set_menu,
            plok_menu,
            (u"Reset config", self.reset_config),
            (u"Send data",self.send_delivery_data),
            (u"Reboot",self.reboot),
            (u"Version", lambda:appuifw.note("Version: " + self.get_sis_version() + 
                                             "\n" + self.__version__, 'info')),
            (u"Exit", self.lock.signal),
            ]
        if not self.comm.sessionid:
            appuifw.app.menu.insert(2, (u"Login",self.login))
            
    def activate(self):
        """Set main menu to app.body and left menu entries."""
        # Use exit_key_handler of current class
        appuifw.app.exit_key_handler = self.exit_key_handler
        appuifw.app.body = self.listbox
        self._update_menu()
        appuifw.app.screen = 'normal'

    def log(self, logtype, text):
        """
        Append a log entry to the log.
        TODO: NOT IMPLEMENTED YET
        """
        pass

    def focus_callback(self, bg):
        """Callback for appuifw.app.focus"""
        self.focus = bg

    def set_config_var(self, text, valuetype, key):
        """Set a configuration parameter."""
        if key not in self.config:
            appuifw.note(u"Configutation key '%s' is not defined" % (key), 'error')
            return
        value = appuifw.query(text, valuetype, self.config[key])
        if value is not None:
            self.config[key] = value
            self.save_config()
            self._update_menu()
        else: 
            # TODO: Instead ASK here if user wants to reset this configuration parameter.
            # defaults need to be global then?
            appuifw.note(u"Setting configutation key '%s' cancelled" % (key), 'info')

    def toggle_debug(self):
        self.config["track_debug"] = not self.config["track_debug"] # Toggle true <-> false
        self.save_config()

    def send_file_over_bluetooth(self, filename):
        """
        Send a file over bluetooth. 
        filename is the full path to the file.
        """
        if e32.in_emulator():
            appuifw.note(u"Bluetooth is not supported in emulator", 'error')
            return # Emulator crashes after this
        try:
            bt_addr, services = btsocket.bt_obex_discover()
            service = services.values()[0]
            # Upload the file
            btsocket.bt_obex_send_file(bt_addr, service, filename)
            appuifw.note(u"File '%s' sent" % filename)
            return True
        except Exception, error:
            appuifw.note(unicode(error), 'error')
            return False
            # raise

    def stop_read_position(self):
        positioning.stop_position()
        # Put the last point to the log if it is not there already
        if len(self.data["track_new"]) > 0 \
           and self.data["track_new"][-1]['gpstime'] != self.simple_pos['gpstime']:
            self.simple_pos['reason'] = 'Last'
            self.append_simple_pos(self.simple_pos)
        self.flush_all()


    def start_read_position(self):
        """
        Start or stop reading position.
        """
        if self.read_position_running == True:
            self.stop_read_position()
            self.read_position_running = False
            self._update_menu() # NOTE: this messes up the menu if this function is called from outside of the main view!
            self.ip.show(u"Stopping GPS...", (50, 50), 3000, 100, appuifw.EHLeftVTop)
            return
        self.read_position_running = True
        self.data["trip_distance"] = 0.0 # TODO: set this up in __init__ and give change to reset this
        positioning.set_requestors([{"type":"service", 
                                     "format":"application", 
                                     "data":"test_app"}])
        positioning.position(course=1,satellites=1, callback=self.read_position, interval=500000, partial=1) 
        self._update_menu() # NOTE: this messes up the menu if this function is called from outside of the main view!
        self.ip.show(u"Starting GPS...", (50, 50), 3000, 100, appuifw.EHLeftVTop)


    def _get_log_cache_filename(self, logname):
        return os.path.join(self.cachedir, u"%s.json" % logname)

    def append_log_cache(self, logname, data, delivery = True):
        """
        Append json'ized data to named log cache file.
        If "delivery" is True, append data also to list which contents
        will be flushed to a file and sent to the server (if sending is
        enabled. 
        """
        if delivery:
            self.append_delivery_data(data)
        filename = self._get_log_cache_filename(logname)
        f = open(filename, "at")
        f.write(simplejson.dumps(data) + "\n")
        f.close()

    def append_delivery_data(self, data):
        """
        Append data item into the delivery list.
        If the length of delivery list is big enough, flush data into a zipfile.
        """
        delivery_key = "delivery_new"
        max_data_items = 25
        self.data[delivery_key].append(data)
        # Flush delivery data into a zip file
        if len(self.data[delivery_key]) >= max_data_items:
            self.flush_delivery_data()

    def clear_all_data(self):
        """
        Flush all pending delivery data objects to files and 
        then clear self.data. 
        """
        self.flush_delivery_data()
        for key in self.data.keys():
            if isinstance(self.data[key], list):
                self.data[key] = []
        
    def flush_delivery_data(self):
        # FIXME: docstring
        # FIXME: errorhandling
        delivery_key = "delivery_new"
        if len(self.data[delivery_key]) > 0:
            filename = os.path.join(self.datadir, "delivery.zip")
            if os.path.isfile(filename):
                mode = "a"
            else:
                mode = "w"
            current_time = time.time()
            now = time.localtime(current_time)[:6]
            name = time.strftime("delivery-%Y%m%d-%H%M%S.json", 
                                 time.localtime(current_time))
            file = zipfile.ZipFile(filename, mode)
            info = zipfile.ZipInfo(name)
            info.date_time = now
            info.compress_type = zipfile.ZIP_DEFLATED
            json_data = []
            while len(self.data[delivery_key]) > 0:
                data = self.data[delivery_key].pop(0)
                json_data.append(simplejson.dumps(data))
            file.writestr(info, "\n".join(json_data))
            file.close()

    def send_delivery_data(self, ask_first = False, ask_login = False):
        """
        Send all delivery data to the server using 
        Comm-module's _send_multipart_request().
        If ask_first is True, ask user first.
        """
        # TODO: errorhandling
        # FIXME: this is messy
        self.flush_delivery_data() 
        filename = os.path.join(self.datadir, "delivery.zip")
        if os.path.isfile(filename):
            # FIXME: this asking should be in another function
            if ask_first:
                query = u"You have some unsent data, would you like send it now?"
                if appuifw.query(query, 'query') == None:
                    return
            # Ask for login, if there is no sessionid
            if ask_login and not self.comm.sessionid:
                # This query is disabled
                # if appuifw.query(u"You have no active session, would you like to login first?", 'query'):
                self.login()

            deliverydir = os.path.join(self.datadir, "delivery")
            if not os.path.isdir(deliverydir):
                os.makedirs(deliverydir)
            tempfile = "delivery.zip-%d" % (time.time())
            temppath = os.path.join(deliverydir, tempfile)
            os.rename(filename, temppath)
            data, response = self.temp_fileupload(temppath)
            # TODO: in the future:
            # self.comm.fileupload(params, files)
            if response.status == 200:
                # TODO: remove file only if also checksum matches:
                # and data["md5"] == md5(temppath)
                # TODO: create function which handles it
                os.remove(temppath)
                # Successfully sent, check if there are any old files 
                # laying in deliverydir 
                unsent_files = os.listdir(deliverydir)
                if len(unsent_files) == 0:
                    message = u"Send status %s %s" % (response.status, data["message"])
                    self.ip.show(message, (50, 50), 5000, 100, appuifw.EHLeftVTop)
                else:
                    message = u"%s, do you like to send %d unsent files now aswell?" % (
                                       data["message"], len(unsent_files))
                    if appuifw.query(message, 'query'):
                        for delivery in unsent_files:
                            temppath = os.path.join(deliverydir, delivery)
                            self.ip.show(u"Sending %s" % (temppath), (50, 50), 60000, 100, appuifw.EHLeftVTop)
                            data, response = self.temp_fileupload(temppath)
                            if response.status == 200:
                                os.remove(temppath) 
                            else:
                                break
                            self.ip.hide()
            else:
                message = u"Send status %s %s" % (response.status, data["message"])
                appuifw.note(message, 'info')
        elif ask_first is False:
            message = u"Not found: %s" % filename
            appuifw.note(message, 'info')

    def login(self):
        """
        Perform login using Comm-module. 
        Query password if is not found in settings.
        """
        if ("password" not in self.config or 
            not self.config["password"]): # is "", False, None
            if appuifw.query(u"Password is not set! Would you like to set it now?", 'query'):
                self.set_config_var(u"Password", "code", "password")
                appuifw.note(u"Perform login again now.", 'info')
            else:
                appuifw.note(u"You can set it in\nSet->Password menu", 'info')
        else:
            self.ip = appuifw.InfoPopup()
            self.ip.show(u"Logging in...", (50, 50), 60000, 100, appuifw.EHLeftVTop)
            data, response = self.comm.login(self.config["username"], 
                                             self.config["password"])
            # Check we got valid response
            if isinstance(data, dict) is False:
                appuifw.note(u"Invalid response from web server!", 'error')
            elif data["status"].startswith("error"):
                appuifw.note(u"%s" % data["message"], 'error')
            self.ip.hide()
            message = u"%s" % (data["message"])
            self.ip.show(message, (50, 50), 5000, 10, appuifw.EHLeftVTop)
            #appuifw.note(message, 'info')

    # TODO: check is this relevant
    def check_for_unsent_delivery_data(self):
        """
        Check if there is any unsent data laying around 
        and send it if user wants to
        """
        pass

    # TODO: put this in Comm/OnmComm-module
    def temp_fileupload(self, filepath):
        f = open(filepath, 'rb')
        filedata = f.read()
        f.close()
        # Create "files"-list which contains all files to send
        files = [("file1", "delivery.zip", filedata)]
        params = {"username" : str(self.config["username"]),
                  "group" : str(self.config["group"]),
                  "pys60gps_version" : self.get_sis_version(),
                  }
        # if "md5" in data and data["md5"] == md5.new(filedata
        self.ip.show(u"Uploading file...", (50, 50), 60000, 10, appuifw.EHLeftVTop)
        data, response = self.comm._send_multipart_request("fileupload", 
                                                           params, files)
        self.ip.hide()
        # FIXME: temporary testing solution
        import md5
        filedata_md5 = md5.new(filedata).hexdigest()
        try:
            if filedata_md5 == data["md5"]:
                ok = "success"
            else:
                ok = "failed"
        except:
            ok = "exception"
        self.ip.show(u"MD5 check: %s" % (ok), (50, 50), 3000, 10, appuifw.EHLeftVTop)
        return data, response

    def save_log_cache(self, logname, namepattern = "-%Y%m%d"):
        """
        Save cached log data to persistent disk (C:).
        Default namepattern can be overridden.
        """
        cache_filename = self._get_log_cache_filename(logname)
        cache_filename_tmp = cache_filename + u".tmp" # FIXME: unique name here
        if not os.path.isfile(cache_filename): return # cache file was not found
        try:
            os.rename(cache_filename, cache_filename_tmp)
            log_dir = os.path.join(self.datadir, logname) # use separate directories
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            log_filename = os.path.join(log_dir, logname + time.strftime(namepattern + ".json", time.localtime(time.time())))
            fout = open(log_filename, "at")
            fin = open(cache_filename_tmp, "rt")
            data = fout.write(fin.read())
            fin.close()
            os.remove(cache_filename_tmp)
            fout.close()
        except:
            pass # Failed. TODO: error logging here
            raise

#    def read_log_cache_filenames(self, logname):
#        """Get a list of cache files."""
#        log_dir = os.path.join(self.datadir, logname) # use separate directories
#        if os.path.isdir(log_dir):
#            files = os.listdir(log_dir)
#            selected = appuifw.multi_selection_list(files, style="checkbox", search_field=1)
#            return files 
#        else:
#            return []


    # TODO: put this into some generic tool module
    def get_iso_systime(self):
        """
        Return current system time in ISO format, 
        e.g. 2008-10-08T16:29:30+03
        """
        return time.strftime(u"%Y-%m-%dT%H:%M:%S", 
                             time.localtime(time.time())) + self._get_timezone()

    # TODO: put this into some generic tool module
    def _get_timezone(self):
        """Return timezone with prefix, e.g. +0300"""
        if time.altzone <= 0: prefix = "+"
        else: prefix = "-"
        hours = ("%2d" % (abs(time.altzone / (60 * 60)))).replace(" ", "0")
        mins = ("%2d" % (abs(time.altzone / 60) % 60)).replace(" ", "0")
        if int(mins) > 0:
            return "%s%s%s" % (prefix, hours, mins)
        else:
            return "%s%s" % (prefix, hours)

    # TODO: check and test this
    def simplify_position(self, pos, isotime=False):
        """
        Extract common values from a positioning's position object.
        NOTE: some values may be in certain situations NaN:s,
        """
        data = {}
        if not pos: return data
        if pos.has_key("systime"):
            if (time.time() - pos["systime"]) > 1: # If position is more than 1 seconds old
                data["gpsage"] = time.time() - pos["systime"]
            if isotime:
                data["systime"] = time.strftime(u"%Y-%m-%dT%H:%M:%S", time.localtime(pos["systime"])) + self._get_timezone()
            else:
                data["systime"] = pos["systime"]
        if pos.has_key("position"):
            if (pos["position"].has_key("latitude") 
                  and -90 <= pos["position"]["latitude"] <= 90):        
                data["lat"] = pos["position"]["latitude"]
                data["lon"] = pos["position"]["longitude"]
            if (pos["position"].has_key("altitude") 
                  and pos["position"]["altitude"] > -10000):        
                data["alt_m"] = pos["position"]["altitude"]
        if pos.has_key("course"):
            if pos["course"].has_key("speed"): 
                data["speed_kmh"] = pos["course"]["speed"] * 3.6
            if pos["course"].has_key("heading"): 
                data["heading"] = pos["course"]["heading"]
        if pos.has_key("satellites"):
            if pos["satellites"].has_key("time"):
                if isotime:
                    data["gpstime"] = time.strftime(u"%Y-%m-%dT%H:%M:%SZ", 
                                                    time.localtime(pos["satellites"]["time"]))
                else:
                    data["gpstime"] = pos["satellites"]["time"]
            try:
                data["hdop"] = pos["satellites"]["horizontal_dop"]
                data["vdop"] = pos["satellites"]["vertical_dop"]
                data["tdop"] = pos["satellites"]["time_dop"]
            except:
                pass
            data["satellites"] = "%d/%d"  % (pos["satellites"]["used_satellites"], 
                                             pos["satellites"]["satellites"])
        return data


    def gsmscan(self):
        """
        Read gsm_location/cellid changes and save them to the gsm history list.
        """
        # Return immediately if there is not good and fresh position info
        if not self.simple_pos or \
           pys60gpstools.has_fix(self.simple_pos) is False or \
           (time.time() - self.simple_pos['systime']) > 3: 
            return
        # Take the latest position and append gsm data into it if necessary
        simple_pos = copy.deepcopy(self.simple_pos)
        l = location.gsm_location()
        if e32.in_emulator(): # Do some random cell changes if in emulator
            import random
            if random.random() < 0.05:
                l = ('244','123','29000',random.randint(1,2**24))
        # NOTE: gsm_location() may return None in certain circumstances!
        if l is not None and len(l) == 4:
            data = {}
            gsm_location = {'cellid': l}
            # Add new gsm_location if it differs from the previous one (or there is not previous)
            # TODO: if the distance to the latest point exceeds 
            # some configurable limit (e.g. 1000 meters), then append a new point too
            dist_time_flag = False
            dist = 0
            if len(self.data["gsm_location"]) > 0:
                p0 = self.data["gsm_location"][-1] # use the latest saved point in history
                # Time difference between current and the latest saved position
                timediff = simple_pos['gpstime'] - p0['gpstime']
                # Distance between current and the latest saved position
                if pys60gpstools.has_fix(simple_pos) and pys60gpstools.has_fix(p0):
                    dist = Calculate.distance(p0['lat'],
                                              p0['lon'],
                                              simple_pos['lat'],
                                              simple_pos['lon'],
                                             )
                # NOTE: pos["position"]["latitude"] may be a NaN!
                # NaN >= 500 is True
                # NaN > 500 is False in Python 2.2!!!
                # Check that at least min_cellid_time secods have passed
                # and distance is greater than max_cellid_dist meters
                #  or max_cellid_time has passed from the latest point 
                # to save new point
                if ((timediff > self.config["min_cellid_time"]) and
                     (dist > self.config["max_cellid_dist"]) or
                     (timediff > self.config["max_cellid_time"])):
                    dist_time_flag = True
            
            if (len(self.data["gsm_location"]) == 0
                or (len(self.data["gsm_location"]) > 0 and 
                   (l != self.data["gsm_location"][-1]['gsm']['cellid']))
                or dist_time_flag):
                data = self.archive_simple_pos(simple_pos)
                cell = {"cellid" : "%s,%s,%s,%s" % (l)}
                try: # This needs some capability (ReadDeviceData?)
                    cell["signal_bars"] = sysinfo.signal_bars()
                    cell["signal_dbm"] = sysinfo.signal_dbm()
                except:
                    #data["signal_bars"] = None
                    #data["signal_dbm"] = None
                    pass
                # We put this gsm cellid in a list, because in the future there may be several (like in wlan)
                data["gsmlist"] = [cell]
                simple_pos["gsm"] = gsm_location
                simple_pos["text"] = l[3]
                self.append_log_cache("cellid", data)
                self.data["gsm_location"].append(simple_pos)
                self.counters["cellid"] = self.counters["cellid"] + 1
                # save cached cellids to a permanent file after n lines
                if self.counters["cellid"] % 4 == 0:
                    self.save_log_cache("cellid")
                # Remove the oldest records if the length exceeds limit
                # TODO: make limit configurable
                if len(self.data["gsm_location"]) > 50:
                    self.data["gsm_location"].pop(0)
            return data

    def auto_wlanscan(self):
        """
        Do automatically _wlanscan() if certain contitions are met.
        """
        simple_pos = self.simple_pos
        if pys60gpstools.has_fix(simple_pos) is False:
            return # Do not save scan automatically, if there is no fix
        dist_time_flag = False
        dist = 0
        if len(self.data["wlan"]) > 0:
            p0 = self.data["wlan"][-1] # use the latest saved point in history
            # Time difference between current and the latest saved position
            timediff = simple_pos["gpstime"] - p0["gpstime"]
            # Distance between current and the latest saved position
            if pys60gpstools.has_fix(p0): # obsolete "if"
                dist = Calculate.distance(p0['lat'],
                                          p0['lon'],
                                          simple_pos['lat'],
                                          simple_pos['lon'],
                                         )
            # NOTE: pos["lat"] may be a NaN!
            # NaN >= 500 is True
            # NaN > 500 is False in Python 2.2!!!
            if ((dist > self.config["max_wlan_dist"] 
                or timediff > self.config["max_wlan_time"])
                and timediff > 6
                and pos["course"]["speed"]*3.6 < self.config["max_wlan_speed"]):
                dist_time_flag = True
        if ((len(self.data["wlan"]) == 0
            or dist_time_flag)):
            # Start wlanscan in background
            e32.ao_sleep(0.01, self._wlanscan)

    def _wlanscan(self):
        """
        Scan all available wlan networks if wlantools-module is present.
        """
        # TODO: add lock here or immediate return if previous scan is still active / hanged
        try:
            import wlantools
        except Exception, error:
            return {"error":unicode(error)}
        if self.scanning["wlan"]:
            return {"error" : u"WLAN scan already running!"}
        self.scanning["wlan"] = True
        starttime = time.clock()
        wlan_devices = wlantools.scan(False)
        duration = time.clock() - starttime
        pos = copy.deepcopy(self.pos)
        for w in wlan_devices:
            # Lowercase all keys and Remove possible null-characters, hidden SSID shows as nulls
            for k,v in w.items():
                del w[k]
                w[k.lower()] = (u"%s" % v).replace('\x00', '')
        # s60 seems to cache wlan scans so do not save 
        # new scan point if previous scan resulted exactly the same wlan list
        try:  self.wlan_devices_latest # First test if "latest" exists
        except: self.wlan_devices_latest = None # TODO: this should be done in init
        # Save new scan point always if latest's result was empty  
        if (wlan_devices != []):
            if (self.wlan_devices_latest == wlan_devices):
                self.scanning["wlan"] = False
                return {"info":u"WLAN scan too fast, skipping this one!"}
        self.wlan_devices_latest = wlan_devices
        data = self.simplify_position(pos, isotime=True)
        #data["comment"] = u""
        data["duration"] = duration
        data["wlanlist"] = wlan_devices
        #    data["comment"] = appuifw.query(u"No GPS fix, add text comment", "text", u"")
        if 'systime' not in data:
            # FIXME: create function to get ISO systime string
            # TODO: use above function here and everywhere
            data["systime"] = self.get_iso_systime()
        self.append_log_cache("wlan", data)
        if self.counters["wlan"] % 5 == 0:
            self.save_log_cache("wlan")
        # Add a pos to be drawn on the canvas
        pos["text"] = u"%d" % len(wlan_devices)
        self.data["wlan"].append(pos)
        if len(self.data["wlan"]) > 100:
            self.data["wlan"].pop(0)
        self.scanning["wlan"] = False
        return data

    def wlanscan(self, comment = None):
        data = self._wlanscan()
        if "error" in data:
            appuifw.note(data["error"], 'error')
            return {}
        elif "info" in data:
            appuifw.note(data["info"], 'info')
            return {}
        if not pys60gpstools.has_fix(self.simple_pos): # TODO: move this interaction to some other function, e.g in tracktab
            data["comment"] = appuifw.query(u"No GPS fix, add text comment", "text", u"")
        return data            


    def bluetoothscan(self):
        """
        Scan all available bluetooth networks if lightblue-module is present.
        """
        # TODO: add lock here or immediate return if previous scan is still active / hanged
        # FIXME: remove all appuifw stuff -- in future this may be called from non-UI-thread
        try:
            import lightblue
        except Exception, error:
            appuifw.note(unicode(error), 'error')
            return False
        if self.scanning["bluetooth"]:
            appuifw.note(u"Bluetooth scan already running!", 'error')
            return False
        self.scanning["bluetooth"] = True
        simple_pos = copy.deepcopy(self.simple_pos)
        if not pys60gpstools.has_fix(simple_pos): # TODO: move this interaction to some other function, e.g in tracktab
            # Query this before, because finddevices() may take several minutes
            comment = appuifw.query(u"No GPS fix, add text comment", "text", u"")
        else:
            comment = u""
        starttime = time.clock()
        bt_devices = lightblue.finddevices()
        data = self.archive_simple_pos(simple_pos)
        data["duration"] = time.clock() - starttime
        if comment != u"": data["comment"] = comment
        btlist = []
        for d in bt_devices:
            #(major_serv, major_dev, minor_dev) = lightblue.splitclass(d[2])
            bt = {u'class' : u"%d,%d,%d" % lightblue.splitclass(d[2]),
                  u'mac' : d[0],
                  u'name' : d[1],
                 }
            btlist.append(bt)
        data["btlist"] = btlist
        self.append_log_cache("bluetooth", data)
        if self.counters["bluetooth"] % 1 == 0:
            self.save_log_cache("bluetooth")
        # Add a pos to be drawn on the canvas
        pos["text"] = u"%d" % len(data["btlist"])
        self.data["bluetooth"].append(pos)
        self.scanning["bluetooth"] = False
        return data


    def archive_simple_pos(self, simple_pos):
        """
        Remove unnecessary keys from simple_pos and convert gpstime
        to ISO-time.
        """
        data = simple_pos.copy()
        data['time'] = time.strftime(u"%Y-%m-%dT%H:%M:%SZ", 
                                     time.localtime(data['gpstime']))
        for key in ['systime', 'gpstime', 'x', 'y', 'e', 'n', 'z']:
            if key in data:
                del data[key]
        return data

    def append_simple_pos(self, simple_pos):
        data = self.archive_simple_pos(simple_pos)
        self.append_log_cache("track", data)
        if self.counters["track"] % 3 == 0: 
            self.save_log_cache("track")

    def read_position(self, pos):
        """
        positioning.position() callback.
        Save the latest position object to the self.pos.
        Keep latest n position objects in the data["position"] list.
        """
        # Convert deep and verbose position dict to a flat and simple one
        simple_pos = pys60gpstools.simplify_position(pos)
        # Add system time too
        simple_pos["systime"] = time.time()
        # Save pos to tracklog
        if pys60gpstools.has_fix(simple_pos):
            if not self.LongOrigin: # Set center meridian
                self.LongOrigin = simple_pos['lon']
            # Saving all pos dicts takes a lot of storage, 
            # let handle_trkpt() decide should this pos be saved in tracklog
            self.trackcalc = \
                locationtools.handle_trkpt(simple_pos, 
                                           self.data["track_new"], 
                                           self.LIMITS, self.LongOrigin)
            # If trackpoint was saved, put it into log file too
            if 'reason' in simple_pos: 
                self.append_simple_pos(simple_pos)
        
        # Save original pos object for debugging purposes
        #if self.config["track_debug"]:
        if True:
            self.data["position_debug"].append(pos)
            #if len(self.data["position_debug"]) > self.config["max_debugpoints"]:
            # FIXME: Using trackpoint limit here too (there is no room for extra settings in menu)
            if len(self.data["position_debug"]) > self.config["max_trackpoints"]:
                self.data["position_debug"].pop(0)
        # Calculate the distance between the newest and 
        # the previous pos and add it to trip_distance
        try:
            if simple_pos['gpstime'] - self.simple_pos['gpstime'] < 120:
                d = math.sqrt((self.simple_pos["e"] - simple_pos["e"])**2 \
                            + (self.simple_pos["n"] - simple_pos["n"])**2)
                self.data["trip_distance"] = self.data["trip_distance"] + d
                self.data["dist_2_latest"] = d
        except: # FIXME: check first do both positions exist and has_fix(), then
            pass
        # Save always the new pos to global self.pos for use in elsewhere
        self.simple_pos = simple_pos

        #####################################################################
        # Backwards compatibility
        pos["systime"] = time.time()
        pos["gsm_location"] = location.gsm_location()

        # Save the new pos to global (current) self.pos
        self.pos = pos
        # Read gsm-cell changes
        self.gsmscan()
        # Scan wlan's automatically
        self.auto_wlanscan()
        # TODO: remove/rewrite
        # Experimental speed history, to be rewritten
        speed_key = (u'%d'%time.time())[:-1]
         # If speed_history is empty add the first item or key has changed (every 10th second)
        if len(self.speed_history) == 0 or self.speed_history[-1]["key"] != speed_key:
            self.speed_history.append({"key":speed_key, 
                                       "speedmax":pos["course"]["speed"],
                                       "speedmin":pos["course"]["speed"],
                                       "time":pos["satellites"]["time"],
                                       })
        else:
            if pos["course"]["speed"] < self.speed_history[-1]["speedmin"]:
                self.speed_history[-1]["speedmin"] = pos["course"]["speed"]
            if pos["course"]["speed"] > self.speed_history[-1]["speedmax"]:
                self.speed_history[-1]["speedmax"] = pos["course"]["speed"]
        if len(self.speed_history) >= self.config["max_speed_history_points"]:
            x = self.speed_history.pop(0)

    def run(self):
        self.lock.wait()
        self.close()

    def reboot(self):
        """
        Reboots the phone by calling Starter.exe
        """
        if appuifw.query(u"Reboot phone", 'query'):
            try:
                e32.start_exe(u'Z:\\System\\Programs\\Starter.exe', '', 0)
            except:
                appuifw.note(u"Not supported in this model.", 'error')

    def handle_select(self):
        self.views[self.listbox.current()].activate()

    def handle_content(self, arg):
        appuifw.note(u"Chosen: %s " % arg, 'info')

    def exit_key_handler(self):
        if appuifw.query(u"Quit program", 'query') is True:
            self.running = False
            self.lock.signal()

    def flush_all(self):
        self.save_log_cache("track")
        self.save_log_cache("cellid") 
        self.save_log_cache("wlan")
        self.flush_delivery_data()
        
        
    def close(self):
        self.stop_read_position()
        #appuifw.note(u"Saving debug", 'info')
        #filename = os.path.join(self.datadir, u"position_debug.json")
        #f = open(filename, "wt")
        #f.write(simplejson.dumps(self.data["position_debug"], indent=1) + "\n")
        #f.close()
        appuifw.app.exit_key_handler = None
        self.running = False
        self.flush_all()
        self.send_delivery_data(True, True)
        appuifw.app.set_tabs([u"Back to normal"], lambda x: None)

# Exception harness for test versions
try:
    oldbody = appuifw.app.body
    myApp = GpsApp()
    myApp.run()
    appuifw.app.body = oldbody
    myApp.stop_read_position()
except:
    # Exception harness
    positioning.stop_position()
    import sys
    import traceback
    import e32
    import appuifw
    appuifw.app.screen = "normal"               # Restore screen to normal size.
    appuifw.app.focus = None                    # Disable focus callback.
    body = appuifw.Text()
    appuifw.app.body = body                     # Create and use a text control.
    exitlock = e32.Ao_lock()
    def exithandler(): exitlock.signal()
    appuifw.app.exit_key_handler = exithandler  # Override softkey handler.
    appuifw.app.menu = [(u"Exit", exithandler)] # Override application menu.
    body.set(unicode("\n".join(traceback.format_exception(*sys.exc_info()))))
    try:
        body.add(u"\n".join(App.log))
    except:
        pass
        #body.set(unicode("\n".join(traceback.format_exception(*sys.exc_info()))))
    exitlock.wait()                             # Wait for exit key press.
    
positioning.stop_position()
e32.ao_sleep(1)
# For SIS-packaged version uncomment this:
# appuifw.app.set_exit()
