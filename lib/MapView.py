# $Id: pys60gps.py 167 2009-03-28 05:35:32Z aapris $

# DO NOT remove this
SIS_VERSION = "0.3.13"
APP_TITLE = u"Map"

import appuifw
appuifw.app.orientation = 'portrait'
import e32
import time
import sys
import os
import socket
import sysinfo
import re
import time
import copy
import positioning
import location
import key_codes
import graphics
import audio
import LatLongUTMconversion
import Calculate
import simplejson

####################################
# FIXME: move these to an own module
import math
rad=math.pi/180

def project_point(x0, y0, dist, angle):
    """Project a new point from point x0,y0 to given direction and angle."""
    # TODO: check that the docstring is correct
    # TODO: check that alghorithm below is correct
    y1 = y0 + math.cos(angle * rad) * dist
    x1 = x0 + math.cos((90 - angle) * rad) * dist
    return x1, y1

def slope(x0, y0, x1, y1):
    """Calculate the slope of the line joining two points."""
    if x0 == x1: return 0
    return 1.0*(y0-y1)/(x0-x1)

def intercept(x, y, a):
    """Return the y-value (c) where the line intercepts y-axis."""
    # TODO: check that the docstring is correct
    return y-a*x

def distance(a,b,c,m,n):
    return abs(a*m+b*n+c)/math.sqrt(a**2+b**2)

def distance_from_vector(x0, y0, dist, angle, x, y):
    x1, y1 = project_point(x0, y0, dist, angle)
    a = slope(x0, y0, x1, y1)
    c = intercept(x0, y0, a)
    dist = distance(a, -1, c, x, y)
    return dist

def distance_from_line(x0, y0, x1, y1, x, y):
    a = slope(x0, y0, x1, y1)
    c = intercept(x0, y0, a)
    dist = distance(a, -1, c, x, y)
    return dist
####################################



class GpsApp:
    __id__ = u'$Id: pys60gps.py 167 2009-03-28 05:35:32Z aapris $'

    def __init__(self):
        self.startgmtime = time.time() + time.altzone # Startup time
        appuifw.app.title = APP_TITLE
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
        self.datadir = os.path.join(u"C:\\Data", APP_TITLE)
        if not os.path.exists(self.datadir):
            os.makedirs(self.datadir)
        # Create a directory for temporary data
        self.cachedir = os.path.join(u"D:\\Data", APP_TITLE)
        if not os.path.exists(self.cachedir):
            os.makedirs(self.cachedir)
        # Configuration/settings
        self.config_file = os.path.join(self.datadir, "settings.ini")
        self.config = {} # TODO: read these from a configuration file
        self.apid = None # Default access point
        self.read_config()
        if self.config.has_key("apid"):
            self._select_access_point(self.config["apid"])
        # Center meridian
        self.LongOrigin = None
        # Some counters
        self.counters = {"cellid":0,
                         "wlan":0,
                         "bluetooth":0,
                         "track":0,
                         "delivery":0,
                         }
        self.scanning = {"wlan":False,
                         "bluetooth":False,
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

        # temporary solution to handle speed data (to be removed/changed)
        self.speed_history = []
        # Put all menu entries and views as tuples into a sequence
        self.menu_entries = []
        self.menu_entries.append(((u"Map"), MapView(self)))
        # Create main menu from that sequence
        self.main_menu = [item[0] for item in self.menu_entries]
        # Create list of views from that sequence
        self.views = [item[1] for item in self.menu_entries]
        # Create a listbox from main_menu and set select-handler
        self.listbox = appuifw.Listbox(self.main_menu, self.handle_select)
        #self.comm = Comm.Comm(self.config["host"], self.config["script"])
        self.activate()

    def get_sis_version(self):
        self.get_geolocation_params()
        return SIS_VERSION

    def _select_access_point(self, apid = None):
        """
        Shortcut for socket.select_access_point() 
        TODO: save selected access point to the config
        TODO: allow user to change access point later
        """
        if apid is not None:
            self.apid = apid
        else:
            access_points = socket.access_points()
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
            self.apo = socket.access_point(self.apid)
            socket.set_default_access_point(self.apo)
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
            "url" : u"http://www.plok.in/poi.php",
            "host" : u"opennetmap.org",
            "script" : u"/api/",
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
            #(u"Toggle debug", self.toggle_debug),
            (u"Max trackpoints (%d)" % self.config["max_trackpoints"], 
                lambda:self.set_config_var(u"Max points", "number", "max_trackpoints")),
            (u"Trackpoint dist (%d)" % self.config["min_trackpoint_distance"], 
                lambda:self.set_config_var(u"Trackpoint dist", "number", "min_trackpoint_distance")),
            (u"Est.vector dist (%d)" % self.config["max_estimation_vector_distance"], 
                lambda:self.set_config_var(u"Trackpoint dist", "number", "max_estimation_vector_distance")),
            (u"Estimation circle (%d)" % self.config["estimated_error_radius"], 
                lambda:self.set_config_var(u"Estimation circle", "number", "estimated_error_radius")),

            (u"Nickname (%s)" % self.config["username"], 
                lambda:self.set_config_var(u"Nickname", "text", "username")),
            (u"Password (%s)" % u"*****", 
                lambda:self.set_config_var(u"Password", "code", "password")),
            (u"Group (%s)" % self.config["group"], 
                lambda:self.set_config_var(u"Group", "text", "group")),
            (u"URL (%s)" % self.config["url"], 
                lambda:self.set_config_var(u"Url (for server connections)", "text", "url")),
            (u"Host (%s)" % self.config["host"], 
                lambda:self.set_config_var(u"Host[:port]", "text", "host")),
            (u"Script (%s)" % self.config["script"], 
                lambda:self.set_config_var(u"Script", "text", "script")),
            (u"Access point (%s)" % self.config["apid"], # TODO: show the name instead of apid 
                lambda:self._select_access_point()),
        ))
            

            
        appuifw.app.menu = [
            (u"Select",self.handle_select),
            (u"GPS %s" % (gps_onoff),self.start_read_position),
            profile_menu,
            set_scan_params_menu,
            set_menu,
            (u"Reset config", self.reset_config),
            #(u"Send data",self.send_delivery_data),
            #(u"Login",self.login),
            #(u"Reboot",self.reboot),
            (u"Version", lambda:appuifw.note("Version: " + self.get_sis_version() + 
                                             "\n" + self.__id__, 'info')),
            (u"Close", self.lock.signal),
            ]

    def activate(self):
        """Set main menu to app.body and left menu entries."""
        # Use exit_key_handler of current class
        appuifw.app.exit_key_handler = self.exit_key_handler
        appuifw.app.body = self.listbox
        self._update_menu()
        appuifw.app.screen = 'normal'

    def focus_callback(self, bg):
        """Callback for appuifw.app.focus"""
        self.focus = bg

    def set_config_var(self, text, valuetype, key):
        """Set a configuration parameter."""
        if not self.config.has_key(key):
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


    def start_read_position(self):
        """
        Start or stop reading position.
        """
        if self.read_position_running == True:
            positioning.stop_position()
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
        A-GPS
        {'satellites': {
            'horizontal_dop': 1.73000001907349, 
            'used_satellites': 5, 
            'vertical_dop': 2.4300000667572, 
            'time': 1238307393.0, 
            'satellites': 10, 
            'time_dop': 1.41999995708466
          }, 
         'position': {
            'latitude': 60.274933736198, 
            'longitude': 24.98598373369, 
            'altitude': 38.0, 
            'vertical_accuracy': 32.0, 
            'horizontal_accuracy': 24.07493019104
          }, 
         'course': {
            'speed': 0.0299999993294477, 
            'heading': 345.089996337891, 
            'heading_accuracy': 359.989990234375, 
            'speed_accuracy': 1.75
          }
        }
        Bluetooth GPS:
        {'satellites': {'horizontal_dop': 2.0, 'used_satellites': 5, 'vertical_dop': 2.29999995231628, 'time': 1238308011.00095, 'satellites': 10, 'time_dop': NaN}, 
         'position': {'latitude': 60.2749416666667, 'altitude': 47.2000007629395, 'vertical_accuracy': 18.3999996185303, 'longitude': 24.986165, 'horizontal_accuracy': 16.0}, 
         'course': {'speed': 0.13374400138855, 'heading': 139.300003051758, 'heading_accuracy': NaN, 'speed_accuracy': NaN}}

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
        def check_keys(pos, keys, data, mainkey):
            if mainkey in pos:
                for (new, old) in keys:
                    try:
                        if old in pos[mainkey] and self.is_nan(pos[mainkey][old]) == False:
                            data[new] = pos[mainkey][old]
                    except:
                        print  mainkey, pos[mainkey], type(pos[mainkey]), new, old
                        raise
        keys = [
            ("lat", "latitude"),
            ("lon", "longitude"),
            ("alt_m", "altitude"),
            ("hor_acc", "horizontal_accuracy"),
            ("ver_acc", "vertical_accuracy"),
        ]
        check_keys(pos, keys, data, "position")
        keys = [
            ("speed", "speed"),
            ("heading", "heading"),
            ("head_acc", "heading_accuracy"),
            ("spd_acc", "speed_accuracy"),
        ]
        check_keys(pos, keys, data, "course")
        keys = [
            ("hdop", "horizontal_dop"),
            ("vdop", "vertical_dop"),
            ("tdop", "time_dop"),
            ("sat_used", "used_satellites"),
            ("gpstime", "time"),
            ("sat", "satellites"),
        ]
        check_keys(pos, keys, data, "satellites")
        return data

    def _calculate_UTM(self, pos, LongOrigin=None):
        """
        Calculate UTM coordinates and append them to pos. 
        pos["lat"] and 
        pos["lon"] must exist and be float.
        """
        if self.LongOrigin:
             LongOrigin = self.LongOrigin
        try:
            (pos["z"], 
             pos["e"], 
             pos["n"]) = self._WGS84_UTM(pos["lat"],  pos["lon"], LongOrigin)
            return True
        except:
            # TODO: log errors
            return False

    def _WGS84_UTM(self, lat, lon, LongOrigin=None):
        """
        Calculate UTM coordinates.
        Return lat, lon and pseudo zone. 
        """
        if self.LongOrigin:
             LongOrigin = self.LongOrigin
        return LatLongUTMconversion.LLtoUTM(23, # Wgs84
                                            lat, lon, LongOrigin)

    def is_nan(self, num):
        return str(num) == "NaN"

    def has_fix(self, pos):
        """Return True if pos has a fix."""
        if "lat" in pos and self.is_nan(pos["lat"]) == False:
            return True
        else:
            return False

    def read_position(self, pos):
        """
        positioning.position() callback.
        Save the latest position object to the self.pos.
        Keep latest n position objects in the data["position"] list.
        TODO: Save the track data (to a file) automatically for future use.
        """
        pos["systime"] = time.time()
        pos = self.simplify_position(pos, isotime=False)
        if self.config["track_debug"]:
            self.data["position_debug"].append(pos)
            if len(self.data["position_debug"]) > self.config["max_debugpoints"]:
                self.data["position_debug"].pop(0)
            # TODO:
            # self.data["position_debug"].append(pos)
        if "lon" in pos:
            if not self.LongOrigin: # Set center meridian
                self.LongOrigin = pos["lon"]
            self._calculate_UTM(pos)
            # Calculate distance between the current pos and the latest history pos
            dist = 0
            dist_estimate = 0
            dist_line = 0
            anglediff = 0
            timediff = 0
            minanglediff = 30 # FIXME: hardcoded value, make configurable
            mindist = 10 # FIXME: hardcoded value, make configurable
            # Maximum time between points in seconds
            maxtimediff = 60 # FIXME: hardcoded value, make configurable
            if pos["hor_acc"] > mindist: # horizontal_accuracy may be NaN
                mindist = pos["hor_acc"]
            if len(self.data["position"]) > 0:
                p0 = self.data["position"][-1] # use the latest saved point in history
                if len(self.data["position"]) > 1:
                    p1 = self.data["position"][-2] # used to calculate estimation line
                else:
                    p1 = None
                # Distance between current and the latest saved position
                dist = Calculate.distance(p0["lat"],
                                          p0["lon"],
                                          pos["lat"],
                                          pos["lon"],
                                         )
                # Difference of heading between current and the latest saved position
                if "heading" in pos and "heading" in p0:
                    anglediff = Calculate.anglediff(p0["heading"], pos["heading"])
                # Time difference between current and the latest saved position
                timediff = pos["gpstime"] - p0["gpstime"]
                
                # Project a location estimation point (pe) using speed and heading from the latest saved point
                pe = {}
                # timediff = time.time() - p0['systime']
                try:
                    dist_project = p0["speed"] * timediff # speed * seconds = distance in meters
                    lat, lon = Calculate.newlatlon(p0["lat"], p0["lon"], 
                                                   dist_project, p0["heading"])
                    pe["position"] = {}
                    pe["lat"] = lat
                    pe["lon"] = lon
                    self.Main._calculate_UTM(pe)
                    self.pos_estimate = pe
                    # This calculates the distance between the current point and the estimated point.
                    # Perhaps ellips could be more optime?
                    dist_estimate = Calculate.distance(pe["lat"],
                                              pe["lon"],
                                              pos["lat"],
                                              pos["lon"],
                                             )
                except:
                    pass
                # This calculates the distance of the current point from the estimation vector
                # In the future this will be an alternate to the estimation circle
                if "speed" in p0 and "heading" in p0:
                    dist_line  = distance_from_vector(p0["e"], p0["n"],
                                                      p0["speed"]*3.6, p0["heading"],
                                                      pos["e"],pos["n"])
                if p1 and "speed" in p0 and "heading" in p0 and \
                   "speed" in p1 and "heading" in p1:
                    dist_line  = distance_from_line(p0["e"], p0["n"],
                                                    p1["e"], p1["n"],
                                                    pos["e"],pos["n"])
                                         
            else: # Always append the first point with fix
                self.data["position"].append(pos)
            self.data["dist_line"] = dist_line
            # If the dinstance exceeds the treshold, save the position object to the history list
            # TODO: think which is the best order of these (most probable to the first place)
            if   (dist > self.config["min_trackpoint_distance"]) \
              or (dist_line > self.config["max_estimation_vector_distance"]) \
              or ((dist > mindist) and (dist_estimate > self.config["estimated_error_radius"])) \
              or ((dist > mindist) and (anglediff > minanglediff)) \
              or (timediff > maxtimediff): 
                self.data["position"].append(pos)
                #####################################################
                data = self.simplify_position(pos, isotime=True)
                try: del data["systime"]
                except: pass
                self.counters["track"] = self.counters["track"] + 1
                # If data["position"] is too long, remove some of the oldest points
                if len(self.data["position"]) > self.config["max_trackpoints"]:
                    self.data["position"].pop(0) # pop twice to reduce the number of points
        # Calculate the distance between the newest and the previous pos and add it to trip_distance
        try: # TODO: do not add if time between positions is more than e.g. 120 sec
            if pos["gpstime"] - self.pos["gpstime"] < 120:
                #d = Calculate.distance(self.pos["lat"],self.pos["lon"],
                #                       pos["lat"], pos["lon"])
                # This should be cheaper
                d = math.sqrt((self.pos["e"] - pos["e"])**2 + (self.pos["n"] - pos["n"])**2)
                self.data["trip_distance"] = self.data["trip_distance"] + d
                self.data["dist_2_latest"] = d
                #self.data["debug"] = u"E:%.1f N:%.1f" % (abs(self.pos["e"] - pos["e"]), abs(self.pos["n"] - pos["n"]))
        except: # FIXME: check first do both positions exist and has_fix(), then 
            pass
        # Save the new pos to global (current) self.pos
        self.pos = pos

    def run(self):
        self.lock.wait()
        self.close()

    def handle_select(self):
        self.views[self.listbox.current()].activate()

    def exit_key_handler(self):
        if appuifw.query(u"Quit program", 'query') is True:
            self.running = False
            self.lock.signal()

    def close(self):
        positioning.stop_position()
        appuifw.app.exit_key_handler = None
        self.running = False
        appuifw.app.set_tabs([u"Back to normal"], lambda x: None)


################### BASE VIEW START #######################

# TODO: move these to separate file
class BaseTabbedView:
    """
    Base class for all tabbed views
    """

    def __init__(self, parent):
        """
        __init__ must be defined in derived class.
        """
        raise "__init__() method has not been defined!"
        self.name = "BaseTabbedView"
        self.parent = parent
        self.Main = parent.Main
        self.tabs = []
        self.current_tab = 0
        self.tabs.append((u"Some", SomeTab(self)))
        self.tabs.append((u"Other", OtherTab(self)))

    def activate(self):
        """Set main menu to app.body and left menu entries."""
        # Use exit_key_handler of current class
        appuifw.app.exit_key_handler = self.exit_key_handler
        # Create tab name list from tabs sequence
        self.tab_menu = [item[0] for item in self.tabs]
        # Put all views to another sequence
        self.views = [item[1] for item in self.tabs]
        appuifw.app.set_tabs(self.tab_menu, self.handle_tab)
        appuifw.app.activate_tab(self.current_tab)
        self.views[self.current_tab].activate()

    def handle_tab(self, index):
        self.current_tab = index
        self.views[index].activate()

    def exit_key_handler(self):
        self.close()

    def close(self):
        appuifw.app.set_tabs([u"Back to normal"], lambda x: None)
        # Activate previous (calling) view
        self.parent.activate()
################### BASE VIEW END #########################

############## List TAB START ##############
class BaseInfoTab:
    def __init__(self, parent, **kwargs):
        """
        Initialize timer and set up some common variables.
        """
        self.t = e32.Ao_timer()
        self.parent = parent
        self.Main = parent.Main
        self.active = False
        self.fontheight = 15
        self.lineheight = 17
        self.font = (u"Series 60 Sans", self.fontheight)

    def _get_lines(self):
        raise "_get_lines() must be implemented"

    def activate(self):
        """
        Set up exit_key_handler, canvas, left menu for this tab
        and finally call self.update() to draw the screen.
        """
        self.active = True
        appuifw.app.exit_key_handler = self.handle_close
        self.canvas = appuifw.Canvas(redraw_callback=self.update)
        appuifw.app.body = self.canvas
        appuifw.app.screen = "normal"
        appuifw.app.menu = [(u"Update", self.update),
                            (u"Close", self.handle_close),
                            ]
        self.activate_extra()
        self.update()

    def activate_extra(self):
        """
        Override this in deriving class 
        if you want to do some extra stuff during activate()
        e.g. add extra items to the menu.
        """
        pass

    def update(self, dummy=(0, 0, 0, 0)):
        """
        Simply call self.blit_lines(lines) to draw some lines of text to the canvas.
        This should be overriden in the deriving class if more complex operations are wanted.
        Start a new timer to call update again after a short while.
        """
        self.t.cancel()
        lines = self._get_lines()
        self.canvas.clear()
        self.blit_lines(lines)
        if self.active:
            self.t.after(0.5, self.update)

    def blit_lines(self, lines, color=0x000000):
        """
        Draw some lines of text to the canvas.
        """
        self.canvas.clear()
        start = 0
        for l in lines:
            start = start + self.lineheight
            self.canvas.text((3,start), l, font=self.font, fill=color)

    def handle_close(self):
        """
        Cancel timer and call parent view's close().
        """
        self.active = False
        self.t.cancel()
        self.parent.close() # Exit this tab set

class MapView(BaseTabbedView):
    def __init__(self, parent):
        self.name = "GpsView"
        self.parent = parent
        self.Main = parent.Main
        self.tabs = []
        self.tabs.append((u"Track", GpsTrackTab(self)))
        self.current_tab = 0

    def close(self):
        # debug stuff
        try:
            for tab in self.tabs:
                tab[1].t.cancel()
        except:
            print dir(tab[1])
            pass
        appuifw.app.set_tabs([u"Back to normal"], lambda x: None)
        # Activate previous (caller) view
        self.parent.activate()

class GpsTrackTab(BaseInfoTab):
    """
    Print the track on the canvas.
    """
    meters_per_px = 4
    seen_counter = 0
    #pois = []
    # Are zoom_levels below 1.0 needeed?
    zoom_levels = [1,2,4,8,16]
    zoom_index = 2
    center_pos = {}
    toggables = {"track":True,
                 "cellid":False,
                 "wlan":False,
                }

    road = [[23.8189071,61.496515],[23.8181604,61.4969451],[23.8178534,61.4971083],[23.8174415,61.4972926],[23.8169227,61.4975052],[23.8164887,61.4976613],[23.8157248,61.4978988],[23.8147459,61.4981721],[23.8128524,61.4986614],[23.8116937,61.4989932],[23.8112645,61.4991242],[23.8108096,61.499288],[23.8103891,61.4994437],[23.8098655,61.4996444],[23.8095136,61.4998],[23.8091789,61.4999638],[23.8086896,61.5002464],[23.8085009,61.500357],[23.8082875,61.5004898],[23.8078227,61.5008484],[23.8075113,61.5010882],[23.8066733,61.5017676]]

    def __init__(self, parent):
        BaseInfoTab.__init__(self, parent)
        import LatLongUTMconversion
        # hevanta
        self.map = graphics.Image.open(u"E:\\Images\\hervanta.png")
        self.topleft = (23.799271, 61.509515)
        self.bottomright = (23.887824, 61.434418)
        self.mappixelmeters = 4.0
        self.width, self.height = 1175, 2095
        # Hervanta 2
        self.topleft = (23.783069, 61.505614) # MMPLL,1
        self.bottomright = (23.895754, 61.505747) # MMPLL,3
        self.mappixelmeters = 4.0
        self.width, self.height = 1500,2000

        
        # helsinki
        #self.map = graphics.Image.open(u"E:\\data\\helsinki.png")
        #self.topleft = (24.935635, 60.282121) # MMPLL,1
        #self.bottomright = (25.036795, 60.177069) # MMPLL,3
        #self.mappixelmeters = 4.0
        #self.width, self.height = 1445, 2905
    
    def update_canvas_size(self, size):
        self.size = size

    def activate(self):
        appuifw.app.screen = "large"
        self.active = True
        appuifw.app.exit_key_handler = self.handle_close
        self.canvas = appuifw.Canvas(redraw_callback=self.update, 
                                     resize_callback=self.update_canvas_size)
        self.size = self.canvas.size
        self.center_x = self.size[0] / 2
        self.center_y = self.size[1] / 2
        self.ui = graphics.Image.new(self.canvas.size)
        appuifw.app.body = self.canvas
        #appuifw.app.screen = "normal"
        appuifw.app.menu = [(u"Update", self.update),
                            (u"Close", self.handle_close),
                            ]
        self.canvas.bind(key_codes.EKeyHash, lambda: self.change_meters_per_px(1))
        self.canvas.bind(key_codes.EKeyStar, lambda: self.change_meters_per_px(-1))
        self.canvas.bind(key_codes.EKey0, self.center)
        self.canvas.bind(key_codes.EKeyRightArrow, lambda: self.move(1, 0))
        self.canvas.bind(key_codes.EKeyLeftArrow, lambda: self.move(-1, 0))
        self.canvas.bind(key_codes.EKeyUpArrow, lambda: self.move(0, -1))
        self.canvas.bind(key_codes.EKeyDownArrow, lambda: self.move(0, 1))
        #self.canvas.bind(key_codes.EKeySelect, self.save_poi)
        self.canvas.bind(key_codes.EKey1, lambda: self.toggle("track"))
        self.canvas.bind(key_codes.EKey2, lambda: self.toggle("cellid"))
        self.canvas.bind(key_codes.EKey3, lambda: self.toggle("wlan"))
        #self.canvas.bind(key_codes.EKey4, self.Main.wlanscan)
        #self.canvas.bind(key_codes.EKey6, self.Main.bluetoothscan)

        #appuifw.app.menu.insert(0, (u"Send track via bluetooth", self.send_track))
        #appuifw.app.menu.insert(0, (u"Send cellids via bluetooth", self.send_cellids))
        #appuifw.app.menu.insert(0, (u"Send debug track via bluetooth", self.send_debug))
        appuifw.app.menu.insert(0, (u"Set meters/pixel", 
                                    lambda:self.set_meters_per_px(appuifw.query(u"Meters","number", self.meters_per_px))))
        #appuifw.app.menu.insert(0, (u"Add POI", self.save_poi))
        #appuifw.app.menu.insert(0, (u"Download", self.download_pois_new))
        e32.ao_sleep(0.1)
        if self.Main.read_position_running == False:
            self.Main.start_read_position()
        self.update()


    def toggle(self, key):
        """
        Toggle (make visible/invisible) things on the canvas.
        """
        if self.toggables.has_key(key):
            self.toggables[key] = not self.toggables[key]
            appuifw.note(u"Toggle %s is not implemented yet!" % key, 'error')
        else:
            appuifw.note(u"Togglekey %s is not found!" % key, 'error')
        
    def move(self, x, y):
        """
        TODO: make map movable
        If there is not previous center point, 
        create a new center from current point,
        points per pixel and direction
        """
        if not self.center_pos:
            if not self.Main.pos: # empty position, no gps connected since start
                appuifw.note(u"No GPS", 'error')
                return
            if self.Main.has_fix(self.Main.pos):
                self.center_pos = copy.deepcopy(self.Main.pos)
            elif len(self.Main.data["position"]) > 0 and self.Main.has_fix(self.Main.data["position"][-1]):
                self.center_pos = copy.deepcopy(self.Main.data["position"][-1])
            else:
                appuifw.note(u"No FIX", 'error')
                return
        move_m = self.meters_per_px * 50
        if (1,0) == (x,y):
            # direction = u"east"
            self.center_pos["e"] = self.center_pos["e"] + move_m
            # TODO: calc lat and lon here too
        elif (0,1) == (x,y):
            # direction = u"south"
            self.center_pos["n"] = self.center_pos["n"] - move_m
            # TODO: calc lat and lon here too
        elif (-1,0) == (x,y):
            # direction = u"west"
            self.center_pos["e"] = self.center_pos["e"] - move_m
            # TODO: calc lat and lon here too
        elif (0,-1) == (x,y):
            # direction = u"north"
            self.center_pos["n"] = self.center_pos["n"] + move_m
            # TODO: calc lat and lon here too
        self.update()

    def center(self):
        """
        Reset center_pos so current position is the center again.
        """
        self.center_pos = {}
        self.update()

    def set_meters_per_px(self, px):
        """
        Set the scale of the track. Minimum is 0.
        """
        if px and px > 0:
            self.meters_per_px = px
        else:
            pass

    def change_meters_per_px(self, px):
        """
        Increase or decrease the zoom level of the track by 1.
        """
        if px < 0 and self.zoom_index > 0:
            self.zoom_index = self.zoom_index - 1
        if px > 0 and self.zoom_index < len(self.zoom_levels) - 1:
            self.zoom_index = self.zoom_index + 1
        self.meters_per_px = self.zoom_levels[self.zoom_index]
        self.update()
    
    def _calculate_canvas_xy(self, image, meters_per_px, p0, p):
        """
        Calculcate x- and y-coordiates for point p.
        p0 is the center point of the image.
        """
        # is image neccessary?
        if "e" not in p or "e" not in p0:
            return
        p["x"] = int((-p0["e"] + p["e"]) / meters_per_px)
        p["y"] = int((p0["n"] - p["n"]) / meters_per_px)

    def _calculate_canvas_xy_point(self, meters_per_px, p0, p):
        """
        NEW STYLE 
        Calculcate (pseudo UTM) x- and y-coordiates for point p.
        p0 is the center point of the image.
        """
        # is image neccessary?
        if ("coordinates_en" in p0 and 
            "coordinates_en" in p):
            e, n = p["coordinates_en"]
            e0, n0 = p0["coordinates_en"]
            x = int((-e0 + e) / meters_per_px)
            y = int((n0 - n) / meters_per_px)
            p["canvas_xy"] = [x, y]


    def update(self, dummy=(0, 0, 0, 0)):
        """
        Draw all elements (texts, points, track, pois etc) to the canvas.
        Start a timer to launch new update after a while.
        pos is always the latest position object
        p0 is the center point position object TODO: refactor p0 -> pc (position center)
        p is temporary position object e.g. in for loop
        """
        self.t.cancel()
        pos = self.Main.pos # the current position during this update()
        poi_r = 5 # POI circles radius
        ch_l = 10 # Crosshair length
        # canvas center point
        center_x = self.size[0] / 2
        center_y = self.size[1] / 2
        # pc is the current center point
        if self.center_pos:
            pc = self.center_pos
        else:
            pc = pos
        
        # TODO: cleanup here!
        self.ui.clear()
        ##########################################################################
        (lon, lat) = self.topleft
        (z, e1, n1) = LatLongUTMconversion.LLtoUTM(23, lat, lon, self.Main.LongOrigin)
        if "lat" in pc:
            lat, lon = pc["lat"], pc["lon"]
            (z, e2, n2) = LatLongUTMconversion.LLtoUTM(23, lat, lon, self.Main.LongOrigin)
            cen = ((e2-e1)/self.mappixelmeters, (n1 - n2)/self.mappixelmeters)
            
            blit = [cen[0]-self.size[0]/2, cen[1]-self.size[1]/2, 
                    cen[0]+self.size[0]/2, cen[1]+self.size[1]/2]
            blit = [int(x) for x in blit]
            self.ui.blit(self.map, source=blit)
        # Plot liikenneympyrä in hervanta
        p_ympy = {
            "lon" : 23.852382, 
            "lat" : 61.447862,
        }
        self.Main._calculate_UTM(p_ympy, self.Main.LongOrigin)
        #print p_ympy, "=========================================="
        if "lat" in pc:
            self._calculate_canvas_xy(self.ui, self.meters_per_px, pc, p_ympy)
            print p_ympy["y"], p_ympy["x"]
            self.ui.point([p_ympy["x"], p_ympy["y"]], outline=0x00ff00, width=20)
        ##########################################################################
        # Print some information about track
        mdist = self.Main.config["min_trackpoint_distance"]
        helpfont = (u"Series 60 Sans", 12)
        # Draw crosshair
        # TODO: draw arrow
        self.ui.line([center_x-ch_l, center_y, center_x+ch_l, center_y], outline=0xff0000, width=1)
        self.ui.line([center_x, center_y-ch_l, center_x, center_y+ch_l], outline=0xff0000, width=1)
        # Test polygon
        # self.ui.polygon([15,15,100,100,100,15,50,10], outline=0x0000ff, width=4)
        j = 0

        poi_width = 20 / self.meters_per_px # show pois relative to zoom level
        if poi_width < 1: poi_width = 1
        if poi_width > 10: poi_width = 10
        

        # draw "heading arrow"
        ##############################################        
        if self.Main.has_fix(pos) and "heading" in pos and pos["heading"] and pos["speed"]:
            p = copy.deepcopy(pos)
            self._calculate_canvas_xy(self.ui, self.meters_per_px, pc, p)
            try:
                p1 = {}
                p1["position"] = {}
                p1["e"], p1["n"] = project_point(p["e"], p["n"], 
                                       50*self.meters_per_px, p["heading"])
#                                                                         p["speed"]*20, p["heading"])
                self._calculate_canvas_xy(self.ui, self.meters_per_px, pc, p1)
                x0, y0 = p["x"], p["y"]
                x, y = p1["x"], p1["y"]
                self.ui.line([x0+center_x, y0+center_y, x+center_x, y+center_y], outline=0x0000ff, width=2)
            except:
                # Probably speed or heading was missing?
                pass
        # Here we contruct MULTILINESTRING and draw it on the canvas
        a = [[[23.8189071,61.496515],[23.8181604,61.4969451],[23.8178534,61.4971083],[23.8174415,61.4972926],[23.8169227,61.4975052],[23.8164887,61.4976613],[23.8157248,61.4978988],[23.8147459,61.4981721],[23.8128524,61.4986614],[23.8116937,61.4989932],[23.8112645,61.4991242],[23.8108096,61.499288],[23.8103891,61.4994437],[23.8098655,61.4996444],[23.8095136,61.4998],[23.8091789,61.4999638],[23.8086896,61.5002464],[23.8085009,61.500357],[23.8082875,61.5004898],[23.8078227,61.5008484],[23.8075113,61.5010882],[23.8066733,61.5017676]]]
        a=[]
        a.append([[23.8569805,61.445878],[23.8568088,61.4460503],[23.8560191,61.4467231],[23.8544227,61.4480441],[23.8543111,61.4481795],[23.8542682,61.4483354]])
        a.append([[23.8541051,61.4483026],[23.854148,61.4481836],[23.8542682,61.4480359],[23.8559162,61.4467026],[23.8559934,61.446637],[23.8567487,61.4460257],[23.8569805,61.445878]])
#        a.append([[23.8542682,61.4483354],[23.8554416,61.4487317],[23.8563167,61.4489395],[23.8574033,61.4492056]])
#        a.append([[23.8542682,61.4483354],[23.854251,61.4484338],[23.8541995,61.449164]])
#        a.append([[23.8526447,61.4479423],[23.8541051,61.4483026],[23.8542682,61.4483354]])
#        a.append([[23.8539678,61.4491476],[23.8540536,61.4484256],[23.8541051,61.4483026]])
#        a.append([[23.8584223,61.4500516],[23.8576957,61.4498684],[23.8566012,61.4495923],[23.8544079,61.4493525]])
#        a.append([[23.8541995,61.449164],[23.8541395,61.4495619]])
#        a.append([[23.8544079,61.4493525],[23.8542622,61.4493423],[23.8526895,61.4492321]])
#        a.append([[23.8558481,61.4513298],[23.8534621,61.4507761],[23.8541144,61.4500869],[23.8544079,61.4493525]])
#        a.append([[23.8539079,61.449538],[23.8539678,61.4491476]])
#        a.append([[23.8559162,61.4467026],[23.8560191,61.4467231],[23.8572837,61.447037],[23.8593958,61.4475281],[23.8618734,61.4480954],[23.8629114,61.4483347],[23.8642671,61.4486473],[23.8706254,61.4500804]])
#        a.append([[23.8543865,61.4462053],[23.8557988,61.446558],[23.8559934,61.446637]])
#        a.append([[23.8563167,61.4489395],[23.8564358,61.4488429]])
#        a.append([[23.8525648,61.4478365],[23.8534579,61.4470249],[23.8543865,61.4462053],[23.8556263,61.445127],[23.8565948,61.4442868],[23.8577437,61.443308],[23.8589397,61.4422705]])
#        a.append([[23.8541395,61.4495619],[23.8541051,61.4497629],[23.854088,61.4498532],[23.8540365,61.4500091],[23.8539249,61.4501649],[23.8536931,61.4504152],[23.853264,61.4508213],[23.8521482,61.451896],[23.8517019,61.4523266],[23.8514015,61.4526056],[23.8510324,61.4528681]])
#        a.append([[23.8493971,61.4460641],[23.8511578,61.4464799],[23.8534579,61.4470249]])
#        a.append([[23.8507846,61.4527847],[23.8511672,61.4525401],[23.8514505,61.4522909],[23.8516,61.4521407],[23.851909,61.4518372],[23.8529722,61.4507515],[23.8535816,61.4501649],[23.8537704,61.4499475],[23.8538476,61.4497999],[23.8538905,61.4496563],[23.8539079,61.449538]])
#        a.append([[23.8543865,61.4462053],[23.8520184,61.4456276],[23.8508378,61.4453505],[23.8506771,61.4453004],[23.8505793,61.4452436],[23.8505235,61.4451768],[23.8504257,61.4451468],[23.8503414,61.4451258]])
#        a.append([[23.8523983,61.4479879],[23.8523381,61.4479689],[23.8523091,61.4479398],[23.8522866,61.4479156],[23.8523119,61.4478791],[23.8523467,61.447854],[23.8524107,61.4478319],[23.8524926,61.4478294],[23.8525648,61.4478365],[23.8526042,61.4478581],[23.8526469,61.4478831],[23.8526471,61.4479197],[23.8526447,61.4479423],[23.8525956,61.447973],[23.8525351,61.4479924],[23.8524583,61.4479976],[23.8523983,61.4479879]])
#        a.append([[23.8518713,61.4483911],[23.8526581,61.4485724]])
#        a.append([[23.8577902,61.4465317],[23.8572837,61.447037]])
#        a.append([[23.8613198,61.4504791],[23.8609697,61.4504984],[23.8605615,61.4504873],[23.8595935,61.4502531],[23.8589046,61.45008],[23.8576212,61.4497651],[23.8570243,61.4496187],[23.8574033,61.4492056]])
#        a.append([[23.847458,61.4531703],[23.8477585,61.4526493],[23.848076,61.452231],[23.8482906,61.4519438],[23.8485223,61.4516444],[23.8490841,61.4509456],[23.8508879,61.449217],[23.8511068,61.4490127],[23.8511973,61.4489388],[23.8518713,61.4483911],[23.8523983,61.4479879]])
#        a.append([[23.8526895,61.4492321],[23.8516082,61.449041],[23.8511973,61.4489388]])
#        a.append([[23.8574033,61.4492056],[23.8575599,61.4492347],[23.8593517,61.4496303],[23.8601326,61.4497553],[23.86122,61.4500201],[23.8611911,61.450301],[23.8613198,61.4504791]])
#        a.append([[23.8442711,61.4460179],[23.8451406,61.4462214],[23.8468258,61.4465979],[23.847008,61.4466388],[23.8495542,61.4472332],[23.8523119,61.4478791]])
#        a.append([[23.8598987,61.4433507],[23.8593837,61.4438348],[23.8569805,61.445878]])
#        a.append([[23.8556263,61.445127],[23.8570586,61.445494],[23.8576503,61.4450048]])
#        a.append([[23.8469499,61.443098],[23.8499422,61.4438032],[23.8530929,61.4445399],[23.8537354,61.4446837],[23.8556263,61.445127]])
#        a.append([[23.8576212,61.4497651],[23.8556321,61.4513626]])
#        a.append([[23.8624866,61.4524105],[23.8610095,61.4525702],[23.8577453,61.4518467],[23.8556321,61.4513626],[23.853264,61.4508213],[23.8529722,61.4507515]])
#        a.append([[23.8576957,61.4498684],[23.8558481,61.4513298],[23.8578289,61.4517746]])
#        a.append([[23.8523033,61.4519533],[23.8534621,61.4507761]])
#        a.append([[23.8529722,61.4507515],[23.8513674,61.4503165],[23.8519824,61.4497244]])
#        a.append([[23.8548741,61.4402315],[23.8552102,61.4411043],[23.8555675,61.4418409],[23.8557063,61.4419712],[23.8558215,61.4421156],[23.855897,61.4422106],[23.8559328,61.442279],[23.8559526,61.442355],[23.8559169,61.4424309],[23.8555553,61.4427918],[23.8545619,61.4438271],[23.8540835,61.4443225],[23.8537354,61.4446837]])
#        a.append([[23.8504692,61.4399323],[23.8507246,61.4401579],[23.8509919,61.4403562],[23.8513329,61.4406161],[23.8516186,61.4408276],[23.8518674,61.4410743],[23.8519898,61.4412051],[23.8520794,61.4413167],[23.8522914,61.4415942],[23.8524296,61.4418586],[23.8526075,61.4421106],[23.8527061,61.4424401],[23.8528444,61.4427882],[23.853001,61.4431494],[23.8531208,61.4435151],[23.8532591,61.4439689],[23.8532867,61.4442156],[23.8532775,61.4443962],[23.8532499,61.4444447],[23.8530929,61.4445399],[23.8530379,61.4446297],[23.8528259,61.4448411],[23.8524757,61.4451848],[23.8520184,61.4456276],[23.8511578,61.4464799],[23.8510656,61.4465195],[23.8508721,61.4465504],[23.8500242,61.446709],[23.8498491,61.4468675],[23.8497016,61.4470261],[23.8495542,61.4472332],[23.8494159,61.4473301],[23.8492132,61.4474975],[23.848992,61.4475944],[23.8489367,61.4476428],[23.8489459,61.4477309],[23.8489973,61.4479528],[23.8490289,61.4481538],[23.8489644,61.4482992],[23.8488906,61.4485018],[23.8487806,61.4486194],[23.8486602,61.4487396],[23.848439,61.4489599],[23.8483099,61.4490771],[23.8481257,61.4492682],[23.8473423,61.4500743],[23.8472317,61.45018],[23.8471119,61.450246],[23.8468999,61.4504046],[23.8466235,61.4506733],[23.8462548,61.4510477],[23.8458862,61.4514265],[23.8456969,61.4516934],[23.8456558,61.4517744],[23.8454438,61.4520607],[23.8451765,61.4522897],[23.8449558,61.4525317],[23.8447936,61.4526838]])
#        a.append([[23.8532499,61.4444447],[23.8540835,61.4443225]])
#        a.append([[23.8478778,61.442281],[23.8506482,61.442928],[23.8531208,61.4435151],[23.8545619,61.4438271],[23.8565948,61.4442868]])
#        a.append([[23.8622385,61.4506688],[23.8621011,61.4507714],[23.861157,61.4505499],[23.8605047,61.4505335],[23.8595259,61.4503114],[23.8584223,61.4500516]])
#        a.append([[23.8565948,61.4442868],[23.8580049,61.4446765],[23.8576503,61.4450048]])
#        a.append([[23.8576503,61.4450048],[23.8577159,61.4450179]])
#        a.append([[23.8577159,61.4450179],[23.8583688,61.4451576]])
#        a.append([[23.8487806,61.4486194],[23.8508879,61.449217]])
#        a.append([[23.8583688,61.4451576],[23.8591516,61.4449776],[23.860405,61.4453094],[23.8604337,61.445389],[23.8605231,61.4454775],[23.8607914,61.4456424],[23.8609574,61.4457706],[23.8609479,61.4460228]])
#        a.append([[23.8593958,61.4475281],[23.8609479,61.4460228]])
#        a.append([[23.8593517,61.4496303],[23.8589046,61.45008]])
#        a.append([[23.8618734,61.4480954],[23.8601326,61.4497553],[23.8595935,61.4502531],[23.8595259,61.4503114],[23.8578289,61.4517746],[23.8577453,61.4518467]])
#        a.append([[23.8521482,61.451896],[23.8523033,61.4519533],[23.8512601,61.4530468],[23.8511616,61.4531809],[23.8507147,61.4538764],[23.8506771,61.4539343],[23.8502355,61.4546133],[23.848931,61.4576263],[23.8486252,61.4583406],[23.8487058,61.4584378],[23.8487382,61.4584821],[23.8487867,61.4585482]])
#        a.append([[23.8503402,61.4514513],[23.8512758,61.4516851],[23.851909,61.4518372],[23.8521482,61.451896]])
#        a.append([[23.8591516,61.4449776],[23.859147,61.4449065],[23.8593007,61.4447577],[23.8594428,61.4446806],[23.8595185,61.4446711]])
#        a.append([[23.8500242,61.446709],[23.8497868,61.4467714],[23.8494821,61.4470432]])
#        a.append([[23.8555553,61.4427918],[23.8577437,61.443308]])
#        a.append([[23.8508638,61.4520009],[23.8512758,61.4516851]])
#        a.append([[23.8475239,61.4444497],[23.8488921,61.4447822],[23.8503414,61.4451258]])
#        a.append([[23.8494821,61.4470432],[23.8492153,61.4473096]])
#        a.append([[23.8595185,61.4446711],[23.8598925,61.444354],[23.8603514,61.4441347],[23.8610631,61.4438698],[23.8614732,61.4435846],[23.8615982,61.4435315],[23.8618475,61.4435148],[23.8628776,61.4436367]])
#        a.append([[23.8492153,61.4473096],[23.8490362,61.4474727],[23.8489509,61.4475909],[23.8489367,61.4476428]])
#        a.append([[23.8493971,61.4460641],[23.8479641,61.4457193],[23.8464599,61.4453609]])
#        a.append([[23.8427437,61.4472507],[23.8430411,61.4472206],[23.8432573,61.4472034],[23.8435187,61.4471904],[23.8437169,61.447212],[23.8443477,61.4472378],[23.8445279,61.4472637],[23.8450776,61.4473756],[23.8453929,61.4474575],[23.8460778,61.4475867],[23.8466184,61.4476254],[23.8471591,61.4477331],[23.8476006,61.4477633],[23.8482044,61.4478193],[23.8486099,61.4479011],[23.8489973,61.4479528]])
#        a.append([[23.8610083,61.4449605],[23.8606863,61.4451988],[23.860405,61.4453094]])
#        a.append([[23.8446247,61.4402759],[23.8451088,61.4403949],[23.8488682,61.4412953],[23.8490666,61.4413401],[23.8515874,61.4419115],[23.8522962,61.4420681],[23.8526075,61.4421106],[23.853122,61.4421017],[23.8555675,61.4418409],[23.8561737,61.4417573],[23.8568585,61.4417748],[23.8589397,61.4422705]])
#        a.append([[23.8510324,61.4528681],[23.8508379,61.4529958]])
#        a.append([[23.8512601,61.4530468],[23.8503475,61.4527843],[23.8492093,61.4524632],[23.848076,61.452231]])
#        a.append([[23.8505759,61.45293],[23.8507846,61.4527847]])
#        a.append([[23.8508379,61.4529958],[23.8506455,61.4531312],[23.8498189,61.4536536],[23.8493744,61.4539374]])
#        a.append([[23.8488921,61.4447822],[23.8499422,61.4438032]])
#        a.append([[23.8354071,61.4473496],[23.8383307,61.4480495],[23.8386529,61.448242],[23.838814,61.4485115],[23.8414611,61.4491219],[23.8434801,61.4495986],[23.8468999,61.4504046],[23.8490841,61.4509456]])
#        a.append([[23.8491023,61.4538798],[23.8496001,61.4535763],[23.8503898,61.4530431],[23.8505759,61.45293]])
#        a.append([[23.8503733,61.4541808],[23.8505333,61.4539443],[23.8507147,61.4538764],[23.8510251,61.4539454],[23.8551092,61.4548539],[23.8563263,61.4550771],[23.8618293,61.456324]])
#        a.append([[23.8506482,61.442928],[23.8515874,61.4419115]])
#        a.append([[23.8610083,61.4449605],[23.8611709,61.4448129],[23.8614877,61.4446511],[23.862124,61.4444356],[23.8627527,61.4441355],[23.8628096,61.4440131],[23.8628776,61.4436367],[23.8630245,61.4432881],[23.8631805,61.4430518],[23.8634018,61.4427993],[23.8637513,61.4425628],[23.8643056,61.4422714],[23.865068,61.4419768],[23.8658406,61.4417703],[23.8670057,61.4415889],[23.8673652,61.4415716],[23.8679815,61.4415443],[23.8689665,61.4415741],[23.8696841,61.4416813],[23.8703994,61.4418443],[23.8709884,61.4420344],[23.8714627,61.4422153],[23.8719328,61.4424895],[23.8721528,61.4426422],[23.8723645,61.4428556],[23.8724404,61.4429155],[23.8726512,61.4431475],[23.8727917,61.443462],[23.8728684,61.4439059],[23.8728436,61.4442101],[23.8727094,61.4444913],[23.8725912,61.4446536],[23.8724412,61.4448273]])
#        a.append([[23.8610083,61.4449605],[23.8611639,61.4450703],[23.8613975,61.4451735],[23.8617508,61.4452705],[23.8621861,61.4453266],[23.862967,61.4453233],[23.8631812,61.4452969],[23.8636579,61.4451895],[23.8640587,61.4450591],[23.8641277,61.4450092],[23.8641726,61.4449765],[23.8641347,61.4448576],[23.8638998,61.4445802],[23.8636098,61.444411],[23.8632848,61.4442862],[23.8629888,61.4442261],[23.8627527,61.4441355]])
#        a.append([[23.8598987,61.4433507],[23.8599244,61.4432317],[23.8606265,61.4423888],[23.8609458,61.4421403]])
#        a.append([[23.8609458,61.4421403],[23.8607993,61.4423923],[23.8600189,61.4432604],[23.8598987,61.4433507]])
#        a.append([[23.8393674,61.4476312],[23.8417963,61.4482027],[23.8439899,61.4486687],[23.8458748,61.4488645],[23.8483099,61.4490771]])
#        a.append([[23.8613198,61.4504791],[23.8616992,61.450628],[23.8687684,61.4522424]])
#        a.append([[23.8494256,61.4518833],[23.8485223,61.4516444]])
#        a.append([[23.8592549,61.4412509],[23.8587565,61.4411959],[23.8582773,61.4410951],[23.8578747,61.4409943],[23.8575488,61.4408385],[23.8569162,61.4408385],[23.8563987,61.4410035],[23.8558236,61.4410768],[23.8552102,61.4411043],[23.8545009,61.4411501],[23.8542134,61.4412142],[23.8536575,61.4411776],[23.8533124,61.4411593],[23.8528907,61.4410401],[23.8524882,61.441031],[23.8519898,61.4412051]])
#        a.append([[23.847008,61.4466388],[23.8479641,61.4457193],[23.8488921,61.4447822]])
#        a.append([[23.8589397,61.4422705],[23.8594182,61.4415817],[23.8592549,61.4412509],[23.8588626,61.4404782],[23.8587502,61.4402568],[23.8584114,61.4401787],[23.8576759,61.4399849],[23.8573907,61.4400148],[23.8555192,61.4401797],[23.85517,61.440211],[23.8548741,61.4402315]])
#        a.append([[23.8589397,61.4422705],[23.8606265,61.4423888],[23.8607993,61.4423923],[23.8617847,61.4425112],[23.8627126,61.4426815],[23.8634018,61.4427993]])
#        a.append([[23.8624035,61.4393303],[23.8623001,61.4394786],[23.8622354,61.4396208],[23.8622453,61.4397571],[23.8622613,61.4400225],[23.8622354,61.4401647],[23.86191,61.4408298],[23.8609297,61.4419772],[23.8606056,61.4422979],[23.860335,61.4423031],[23.8591068,61.4422228]])
#        a.append([[23.8510251,61.4539454],[23.8510628,61.4540213],[23.8516682,61.4552387],[23.8519428,61.4562927]])
#        a.append([[23.8510628,61.4540213],[23.8506771,61.4539343]])
#        a.append([[23.8558194,61.4407599],[23.8555192,61.4401797]])
#        a.append([[23.8466673,61.4467618],[23.8470484,61.4472395],[23.847274,61.4473928],[23.8473876,61.447603],[23.8476006,61.4477633]])
#        a.append([[23.8569162,61.4408385],[23.8574146,61.4405819]])
#        a.append([[23.8575488,61.4408385],[23.8574146,61.4405819],[23.8574866,61.4404271]])
#        a.append([[23.8650022,61.458232],[23.8654876,61.4571693],[23.8664356,61.4551848],[23.8671737,61.4540856],[23.8687015,61.4521537],[23.8622385,61.4506688]])
#        a.append([[23.8493744,61.4539374],[23.8503733,61.4541808],[23.8497755,61.4554108],[23.8487991,61.4576085],[23.8484137,61.4584871],[23.8483833,61.4585564]])
#        a.append([[23.8539935,61.4395793],[23.854029,61.4396804],[23.8540654,61.4397402],[23.8541227,61.43979],[23.8542374,61.439805],[23.8543676,61.4398025],[23.8545552,61.439795],[23.8547636,61.439795],[23.854873,61.4398149],[23.8549512,61.4398747],[23.85517,61.440211]])
#        a.append([[23.8640123,61.4470854],[23.863523,61.4477213],[23.8630767,61.4481684],[23.8629114,61.4483347]])
#        a.append([[23.8573907,61.4400148],[23.857544,61.4403446],[23.8574866,61.4404271]])
#        a.append([[23.8588626,61.4404782],[23.8580754,61.440559]])
#        a.append([[23.8400374,61.4504056],[23.842226,61.4508821],[23.8456969,61.4516934],[23.848076,61.452231]])
#        a.append([[23.8493744,61.4539374],[23.848913,61.4542215],[23.8485878,61.4544605],[23.848347,61.4547178],[23.8481871,61.4549782],[23.8478223,61.4558212],[23.8473958,61.4568744],[23.8469135,61.4581351],[23.8467182,61.4585523],[23.8466238,61.4587327],[23.8463031,61.4593522]])
#        a.append([[23.8493744,61.4539374],[23.8491023,61.4538798],[23.8476966,61.4535405]])
#        a.append([[23.8463119,61.4441869],[23.8475239,61.4444497]])
#        a.append([[23.844645,61.4471302],[23.8449965,61.4470655],[23.845411,61.4470268],[23.846249,61.4467727],[23.8466673,61.4467618],[23.8468258,61.4465979]])
#        a.append([[23.8479627,61.4549332],[23.84812,61.4546797],[23.8483716,61.4543898],[23.8486951,61.4541496],[23.8491023,61.4538798]])
#        a.append([[23.8518252,61.4384607],[23.8520977,61.4390954],[23.8523779,61.4397364],[23.8525113,61.4400426]])
#        a.append([[23.8628427,61.4396784],[23.8625423,61.44006],[23.862302,61.440536],[23.8619844,61.4409504],[23.8609458,61.4421403]])
#        a.append([[23.863274,61.4464459],[23.8638728,61.4464006],[23.8645486,61.4463666],[23.8650407,61.4462646],[23.8654912,61.4461002],[23.8659892,61.4458282],[23.866333,61.445627],[23.866339,61.4454853],[23.8663568,61.4452019],[23.8663034,61.4450546],[23.8660129,61.4448307],[23.8654971,61.444519],[23.8651829,61.4442838],[23.865011,61.4440344],[23.865011,61.443802],[23.8651474,61.4436008],[23.865343,61.4434336],[23.8660011,61.4430766],[23.866754,61.442779],[23.8672875,61.442677],[23.8678684,61.4426463]])
#        a.append([[23.8537048,61.4389311],[23.8539935,61.4395793],[23.8523779,61.4397364],[23.8504692,61.4399323]])
#        a.append([[23.8584114,61.4401787],[23.8587181,61.4398488],[23.8589098,61.4397571],[23.8598491,61.4396197],[23.8602708,61.4396472],[23.8609226,61.439748],[23.8615168,61.4397113],[23.8622453,61.4397571]])
#        a.append([[23.8520802,61.4567725],[23.8519428,61.4562927]])
#        a.append([[23.8490666,61.4413401],[23.8502817,61.44012],[23.8504692,61.4399323],[23.8496967,61.4393437],[23.8489242,61.438755]])
#        a.append([[23.8421042,61.4443997],[23.844959,61.4450537],[23.8464599,61.4453609]])
#        a.append([[23.848864,61.4553103],[23.8497755,61.4554108]])
#        a.append([[23.8417963,61.4482027],[23.8427437,61.4472507],[23.8432213,61.4467942],[23.844959,61.4450537],[23.8457583,61.4442959],[23.8463119,61.4441869],[23.8461274,61.4438808],[23.8469049,61.4431346],[23.8469499,61.443098],[23.8476288,61.4424111],[23.847784,61.4423666],[23.8478778,61.442281],[23.8488682,61.4412953]])
#        a.append([[23.8471902,61.4533436],[23.8472932,61.4532944],[23.8473791,61.4532411],[23.847458,61.4531703]])
#        a.append([[23.847458,61.4531703],[23.8474306,61.4532493],[23.8474392,61.4533272],[23.8474477,61.4533806]])
#        a.append([[23.8537048,61.4389311],[23.8520977,61.4390954],[23.8496967,61.4393437],[23.8482481,61.439495]])
#        a.append([[23.8476966,61.4535405],[23.8475765,61.4535323],[23.8474735,61.4535528]])
#        a.append([[23.8475164,61.4534421],[23.8475937,61.4534954],[23.8476966,61.4535405]])
#        a.append([[23.8502817,61.44012],[23.8499297,61.4401173],[23.8496067,61.4401092],[23.849308,61.4400881],[23.8489262,61.4400193],[23.8485168,61.439895],[23.8482513,61.4398077],[23.8480687,61.4397998],[23.8479359,61.4397971],[23.8477976,61.4397495],[23.8476316,61.4396887],[23.8474048,61.4396411],[23.8470839,61.4396278],[23.8467685,61.4396966],[23.8464532,61.4397733],[23.8461489,61.439813],[23.8457837,61.4398606],[23.8455403,61.4399214],[23.845402,61.4400193],[23.8453411,61.4401198],[23.8452803,61.4402335],[23.8452139,61.4403102],[23.8451088,61.4403949]])
#        a.append([[23.8530782,61.4585171],[23.8523447,61.4571059],[23.8520802,61.4567725],[23.8505888,61.456579],[23.8500544,61.4577584],[23.848931,61.4576263],[23.8487991,61.4576085]])
#        a.append([[23.8475078,61.4535036],[23.8474735,61.4535528],[23.8474048,61.4535774],[23.8473207,61.4535968],[23.8471834,61.4536009],[23.8470632,61.4535763],[23.8469928,61.4535282],[23.8469585,61.4534626],[23.8470014,61.4534093],[23.8470787,61.4533724],[23.8471902,61.4533436],[23.8473447,61.4533478],[23.8474477,61.4533806],[23.8475164,61.4534421],[23.8475078,61.4535036]])
#        a.append([[23.8656266,61.4471047],[23.8649739,61.4479261],[23.8642671,61.4486473]])
#        a.append([[23.8630245,61.4432881],[23.8644215,61.4435925],[23.8644343,61.4438918],[23.8644981,61.4440444],[23.8646323,61.4442032],[23.8654243,61.4447314],[23.8655265,61.4448627],[23.8655584,61.4449818],[23.8655457,61.4451039]])
#        a.append([[23.8469049,61.4431346],[23.8435928,61.4429801],[23.8430008,61.4435313]])
#        a.append([[23.8473207,61.4535968],[23.8472349,61.4536337],[23.8471748,61.4536789],[23.8471061,61.4537363]])
#        a.append([[23.8474159,61.4551489],[23.848864,61.4553103]])
#        a.append([[23.8467628,61.4533507],[23.8468916,61.4533712],[23.8470787,61.4533724]])
#        a.append([[23.8641277,61.4450092],[23.8644893,61.4452048],[23.8647265,61.4453408],[23.8648747,61.4453833],[23.8650999,61.4453918],[23.8654379,61.4453124],[23.8658114,61.4452303],[23.8663568,61.4452019]])
#        a.append([[23.8471061,61.4537363],[23.8470976,61.4536378],[23.8470632,61.4535763]])
#        a.append([[23.8469585,61.4534626],[23.8468898,61.4534134],[23.8467628,61.4533507]])
#        a.append([[23.8452817,61.4582408],[23.8451959,61.4581629],[23.8451272,61.458085],[23.8450843,61.4579702],[23.8450929,61.4578881],[23.8451015,61.4577651],[23.8457967,61.45626],[23.8464195,61.4550364],[23.8471061,61.4537363]])
#        a.append([[23.8312618,61.4497862],[23.8327456,61.450135],[23.8381127,61.4513532],[23.8388123,61.4515139],[23.8412646,61.4521047],[23.843256,61.45257],[23.8467628,61.4533507]])
#        a.append([[23.8459855,61.4593235],[23.8460542,61.4591799],[23.8463148,61.4586589],[23.8463873,61.4585306],[23.8465941,61.4581124],[23.8471625,61.4568595],[23.8475562,61.4557883],[23.8479627,61.4549332]])
        
#        if self.Main.LongOrigin:
#            #print self.Main.LongOrigin
#            for road in a:
#                for i in range(0, len(road) - 1):
#                    x = road[i]
#                    x2 = road[i+1]
#                    p = {"lat": x[1], "lon": x[0]}
#                    self.Main._calculate_UTM(p)
#                    self._calculate_canvas_xy(self.ui, self.meters_per_px, pc, p)
#                    p2 = {"lat": x2[1], "lon": x2[0]}
#                    self.Main._calculate_UTM(p2)
#                    self._calculate_canvas_xy(self.ui, self.meters_per_px, pc, p2)
#                    #self.ui.point([p["x"]+center_x, p["y"]+center_y], outline=0x0ff000, width=5)
#                    self.ui.line([p["x"]+center_x, p["y"]+center_y, 
#                                  p2["x"]+center_x, p2["y"]+center_y], outline=0x000099, width=2)
#                    
#                    #self.ui.point([p["x"]+center_x, p["y"]+center_y], outline=0x000000, width=5)
#                #print p
        
        # Draw wlan points
        for p in self.Main.data["wlan"]:
            self._calculate_canvas_xy(self.ui, self.meters_per_px, pc, p)
            if p.has_key("x"):
                self.ui.text(([p["x"]+center_x+10, p["y"]+center_y+5]), u"%s" % p["text"], font=(u"Series 60 Sans", 10), fill=0x0000ff)
                self.ui.point([p["x"]+center_x, p["y"]+center_y], outline=0x0000ff, width=poi_width)
            
        # Draw track if it exists
        # TODO: all of these loops to a function
        track = self.Main.data["position"]
        if len(self.Main.data["position"]) > 0:
            p1 = self.Main.data["position"][-1]
        lines_drawn = 0
        for i in range(len(self.Main.data["position"])-1, -1, -1): # draw trackpoints backwards
            p = self.Main.data["position"][i]
            self._calculate_canvas_xy(self.ui, self.meters_per_px, pc, p)
            max_timediff = 120 # seconds
            timediff = abs(p["gpstime"] - p1["gpstime"])
            # Draw only lines which are inside canvas/screen
            # FIXME: no hardcoded values here
            #w = self.size[0] / 2 # is this same than center_x
            #h = self.size[0] / 2
            #print w, center_x
            if ("x" in p 
               and "x" in p1 
               and (-center_x < p["x"] < center_x or -center_x < p1["x"] < center_x) 
               and (-center_y < p["y"] < center_y or -center_y < p1["y"] < center_y) 
               and timediff <= max_timediff):
                self.ui.point([p["x"]+center_x, p["y"]+center_y], outline=0xff0000, width=5)
                self.ui.line([p["x"]+center_x, p["y"]+center_y, 
                              p1["x"]+center_x, p1["y"]+center_y], outline=0x00ff00, width=2)
                lines_drawn = lines_drawn + 1
            p1 = p

        ##############################################
        # Testing "status" bar. TODO: implement better, e.g. own function for status bar
        if self.Main.read_position_running:
            if self.Main.has_fix(pos):
                self.ui.point([10, 10], outline=0x00ff00, width=10)
            else:
                self.ui.point([10, 10], outline=0xffff00, width=10)
        else:
            self.ui.point([10, 10], outline=0xff0000, width=10)
                                      
        ###########################################
        # Draw scale bar
        self.draw_scalebar(self.ui)
        if "hdop" in pos:
            self.ui.text((2,40), u"%.1f" % (pos["hdop"]), font=helpfont, fill=0x999999)
        self.ui.text((2,51), u"Press * or # to zoom", font=helpfont, fill=0x999999)
        
        if self.center_pos and "e" in self.center_pos:
            self.ui.text((2,75), u"E %.2f" % self.center_pos["e"], font=helpfont, fill=0x999999)

        self.canvas.blit(self.ui)
        if self.active and self.Main.focus:
            self.t.after(0.5, self.update)

    def draw_scalebar(self, canvas):
        """Draw the scale bar"""
        scale_bar_width = 50 # pixels
        scale_bar_x = 150    # x location
        scale_bar_y = 20     # y location
        scale_value = scale_bar_width * self.meters_per_px
        if scale_value > 1000: 
            scale_text = u"%.1f km" % (scale_value / 1000.0)
        else:
            scale_text = u"%d m" % (scale_value)
        if self.meters_per_px >= 1:
            mppx_text = u"%d m/px" % self.meters_per_px
        else:
            mppx_text = u"%d cm/px" % (self.meters_per_px * 100)
        canvas.rectangle((scale_bar_x-5, scale_bar_y-15, scale_bar_x+scale_bar_width+10, scale_bar_y+15), fill=0xe0e0e0)
        canvas.text((scale_bar_x + 5, 18), scale_text, font=(u"Series 60 Sans", 10), fill=0x333333)
        canvas.text((scale_bar_x + 5, 32), mppx_text, font=(u"Series 60 Sans", 10), fill=0x333333)
        canvas.line([scale_bar_x, 20, scale_bar_x + scale_bar_width, 20], outline=0x0000ff, width=1)
        canvas.line([scale_bar_x, 15, scale_bar_x, 25], outline=0x0000ff, width=1)
        canvas.line([scale_bar_x + scale_bar_width, 15, scale_bar_x + scale_bar_width, 25], outline=0x0000ff, width=1)

# Exception harness for test versions
try:
    oldbody = appuifw.app.body
    myApp = GpsApp()
    myApp.run()
    appuifw.app.body = oldbody
    positioning.stop_position()
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
