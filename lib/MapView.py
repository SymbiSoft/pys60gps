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
                anglediff = Calculate.anglediff(p0["heading"], pos["heading"])
                # Time difference between current and the latest saved position
                timediff = pos["gpstime"] - p0["gpstime"]
                
                # Project a location estimation point (pe) using speed and heading from the latest saved point
                pe = {}
                # timediff = time.time() - p0['systime']
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
    meters_per_px = 5
    seen_counter = 0
    #pois = []
    # Are zoom_levels below 1.0 needeed?
    zoom_levels = [0.0675,0.125,0.25,0.5,1,2,3,5,8,12,16,20,30,50,80,100,150,250,400,600,1000,2000,5000,10000]
    zoom_index = 8
    center_pos = {}
    toggables = {"track":True,
                 "cellid":False,
                 "wlan":False,
                }

    def activate(self):
        self.active = True
        appuifw.app.exit_key_handler = self.handle_close
        self.canvas = appuifw.Canvas(redraw_callback=self.update)
        size = self.canvas.size
        self.center_x = size[0]
        self.center_y = size[1]
        self.ui = graphics.Image.new(self.canvas.size)
        appuifw.app.body = self.canvas
        appuifw.app.screen = "normal"
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
        if "e" not in p: return
        if "e" not in p0: return
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
        poi_r = 5 # POI circles radius
        ch_l = 10 # Crosshair length
        # TODO: determine center from canvas width/height
        center_x = 120
        center_y = 120
        # TODO: cleanup here!
        self.ui.clear()
        # Print some information about track
        mdist = self.Main.config["min_trackpoint_distance"]
        helpfont = (u"Series 60 Sans", 12)
        # Draw crosshair
        # TODO: draw arrow
        self.ui.line([center_x-ch_l, center_y, center_x+ch_l, center_y], outline=0x0000ff, width=1)
        self.ui.line([center_x, center_y-ch_l, center_x, center_y+ch_l], outline=0x0000ff, width=1)
        # Test polygon
        # self.ui.polygon([15,15,100,100,100,15,50,10], outline=0x0000ff, width=4)
        j = 0
        pos = self.Main.pos # the current position during this update()
        # pc is the current center point
        if self.center_pos:
            pc = self.center_pos
        else:
            pc = pos

        poi_width = 20 / self.meters_per_px # show pois relative to zoom level
        if poi_width < 1: poi_width = 1
        if poi_width > 10: poi_width = 10
        
        ##############################################        
        # Testing the point estimation 
        # TODO: to a function
        if len(self.Main.data["position"]) > 0: 
            pe = self.Main.pos_estimate
            err_radius = self.Main.config["estimated_error_radius"] # meters
            ell_r = err_radius / self.meters_per_px 
            self._calculate_canvas_xy(self.ui, self.meters_per_px, pc, pe)
            if pe.has_key("x"):
                self.ui.ellipse([(pe["x"]+center_x-ell_r,pe["y"]+center_y-ell_r),
                                 (pe["x"]+center_x+ell_r,pe["y"]+center_y+ell_r)], outline=0x9999ff)
            # Draw accurancy circle
            # FIXME: this doesn't draw the circle to the current position, instead to the map center
            acc_radius = pos["hor_acc"]
            if acc_radius > 0:
                acc_r = acc_radius / self.meters_per_px 
                self.ui.ellipse([(center_x-acc_r,center_y-acc_r),
                                 (center_x+acc_r,center_y+acc_r)], outline=0xccffcc)
            if self.Main.data["trip_distance"] >= 1000.0:
                trip = u"%.2f km" % (self.Main.data["trip_distance"] / 1000)
            else:
                trip = u"%.1f m" % (self.Main.data["trip_distance"])
            # TODO REMOVE:
            # trip = u"%.1f m" % (self.Main.data["trip_distance"])
            #self.ui.text(([10, 230]), u"%.1f km/h %.1f' %s" % (pos["speed"]*3.6, pos["heading"],  trip),
            # TODO: replace ' with hex representation of degree sign (ASCII b0, UNICODE ?) 
            self.ui.text(([10, 230]), u"%.1f m/s %.1f' %s" % (pos["speed"], pos["heading"],  trip), 
                                      font=(u"Series 60 Sans", 18), fill=0x000000)
        
        ##############################################        
        # TESTING direction line
        if len(self.Main.data["position"]) > 0 and "speed" in self.Main.data["position"][-1]:
            # Copy latest saved position from history
            p = copy.deepcopy(self.Main.data["position"][-1])
            self._calculate_canvas_xy(self.ui, self.meters_per_px, pc, p)
            # Project new point from latest point, heading and speed
            p1 = {}
            p1["position"] = {}
            x, y = project_point(p["e"], p["n"], p["speed"]*20, p["heading"])
            p1["e"], p1["n"] = x, y
            try:
                self._calculate_canvas_xy(self.ui, self.meters_per_px, pc, p1)
                x0, y0 = p["x"], p["y"]
                x, y = p1["x"], p1["y"]
            except:
                x0, y0 = 0, 0
                x, y = 0, 0
            #x,y = project_point(x0, y0, p["speed"]*3.6, p["heading"])
            self.ui.line([x0+center_x, y0+center_y, x+center_x, y+center_y], outline=0xffff99, 
                          width=1+(self.Main.config["max_estimation_vector_distance"]/self.meters_per_px/2))
            #dist  = distance_from_vector(p["e"], p["n"],
            #                             p["speed"]*3.6, p["heading"],
            #                             pos["e"],pos["n"])
            dist = self.Main.data["dist_line"]
            s=50
            i=15
            try:
                d = math.sqrt((p["e"] - pos["e"])**2 + (p["n"] - pos["n"])**2)
            except:
                d = -1
            self.ui.text((150, s), u"%.1f m (ldist)" % (dist), font=(u"Series 60 Sans", i), fill=0x000000)
            s = s + i
            self.ui.text((150, s), u"%.1f m (pdist)" % (abs(d)), font=(u"Series 60 Sans", i), fill=0x000000)
            if self.Main.data.has_key("dist_2_latest"):
                s = s + i
                self.ui.text((150, s), u"%.1f m" % (self.Main.data["dist_2_latest"]), font=(u"Series 60 Sans", i), fill=0x000000)
            
            
            #self.ui.text((160, s), u"%d %d %d %d" % (x0, y0, x, y), font=(u"Series 60 Sans", 10), fill=0x000000)

        # draw "heading arrow"
        ##############################################        
        if self.Main.has_fix(pos) and pos["heading"] and pos["speed"]:
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

        ##############################################        
        # Draw GSM points
        for p in self.Main.data["gsm_location"]:
            self._calculate_canvas_xy(self.ui, self.meters_per_px, pc, p)
            if p.has_key("x"):
                self.ui.text(([p["x"]+center_x+10, p["y"]+center_y+5]), u"%s" % p["text"], font=(u"Series 60 Sans", 10), fill=0xccccff)
                self.ui.point([p["x"]+center_x, p["y"]+center_y], outline=0x9999ff, width=poi_width)
        ##############################################        
        # Draw wlan points
        for p in self.Main.data["wlan"]:
            self._calculate_canvas_xy(self.ui, self.meters_per_px, pc, p)
            if p.has_key("x"):
                self.ui.text(([p["x"]+center_x+10, p["y"]+center_y+5]), u"%s" % p["text"], font=(u"Series 60 Sans", 10), fill=0x0000ff)
                self.ui.point([p["x"]+center_x, p["y"]+center_y], outline=0x0000ff, width=poi_width)

        # New style: use main apps data structures directly and _calculate_canvas_xy() to get pixel xy.
        # TODO: to a function
        ##############################################        
        for i in range(len(self.Main.data["position_debug"])-1, -1, -1):
            j = j + 1
            if j > 60: break # draw only last x debug points
            p = self.Main.data["position_debug"][i]
            self._calculate_canvas_xy(self.ui, self.meters_per_px, pc, p)
            try:
            #if self.Main.has_fix(p):
                self.ui.point([p["x"]+center_x, p["y"]+center_y], outline=0x000066, width=3)
            except: 
                pass
            
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
            if (p.has_key("x") 
               and p1.has_key("x") 
               and (-120 < p["x"] < 120 or -120 < p1["x"] < 120) 
               and (-120 < p["y"] < 120 or -120 < p1["y"] < 120) 
               and timediff <= max_timediff):
                self.ui.point([p["x"]+center_x, p["y"]+center_y], outline=0xff0000, width=5)
                self.ui.line([p["x"]+center_x, p["y"]+center_y, 
                              p1["x"]+center_x, p1["y"]+center_y], outline=0x00ff00, width=2)
                lines_drawn = lines_drawn + 1
            p1 = p
        # Debug: show how many track line parts has been drawn
        # self.ui.text(([130, 130]), u"%d" % lines_drawn, font=(u"Series 60 Sans", 10), fill=0x9999ff)
        # Draw POIs if there are any
        # TODO: to a function
        for p in self.Main.data["pois_private"]:
            self._calculate_canvas_xy(self.ui, self.meters_per_px, pc, p)
            if p.has_key("x"):
                self.ui.point([p["x"]+center_x, p["y"]+center_y], outline=0x0000ff, width=5)
                self.ui.ellipse([(p["x"]+center_x-poi_r,p["y"]+center_y-poi_r),
                                 (p["x"]+center_x+poi_r,p["y"]+center_y+poi_r)], outline=0x0000ff)
                # There is a bug in image.text (fixed in 1.4.4?), so text must be drawn straight to the canvas
                self.ui.text(([p["x"]+130, p["y"]+125]), u"%s" % p["text"], font=(u"Series 60 Sans", 10), fill=0x9999ff)

        # DEPRECATED, TODO: REMOVE
        for p in self.Main.data["pois_downloaded"]:
            self._calculate_canvas_xy(self.ui, self.meters_per_px, pc, p)
            if p.has_key("x"):
                # Add "seen" key if user was near enough to the point
                if not p.has_key("seen") and Calculate.distance(pos["lat"],
                                      pos["lon"],
                                      p["lat"],
                                      p["lon"],
                                      ) < 20: # temporary hardcoded
                                      # self.Main.config["estimated_error_radius"]
                    if not p.has_key("seen"): # play only the first time
                        #self.Main.play_tone()
                        self.seen_counter = self.seen_counter + 1
                    p["seen"] = 1

                    # TODO: say beep here!
                if p.has_key("seen"):
                    pointcolor = 0xcccccc
                    bordercolor = 0x999999
                else:
                    pointcolor = 0x660000
                    bordercolor = 0x0000ff
                self.ui.point([p["x"]+center_x, p["y"]+center_y], outline=pointcolor, width=poi_width)
                #self.ui.ellipse([(p["x"]+center_x-poi_r,p["y"]+center_y-poi_r),
                #                 (p["x"]+center_x+poi_r,p["y"]+center_y+poi_r)], outline=bordercolor)
                self.ui.text(([p["x"]+130, p["y"]+125]), u"%s" % p["text"], font=(u"Series 60 Sans", 10), fill=0x666600)

        for p in self.Main.data["pois_downloaded_new"]:
            new_pc = {"coordinates_en" : [pc["e"], pc["n"]]}
            self._calculate_canvas_xy_point(self.meters_per_px, new_pc, p)
            if "canvas_xy" in p:
                x, y = p["canvas_xy"]
                pointcolor = 0x660000
                bordercolor = 0x0000ff
                self.ui.point([x+center_x, y+center_y], outline=pointcolor, width=poi_width)
                #self.ui.ellipse([(p["x"]+center_x-poi_r,p["y"]+center_y-poi_r),
                #                 (p["x"]+center_x+poi_r,p["y"]+center_y+poi_r)], outline=bordercolor)
                if "title" in p["properties"]:
                    text = u"%s" % p["properties"]["title"]
                else:
                    text = u"%s" % p["properties"]["cnt"]
                self.ui.text(([x+130, y+125]), text, font=(u"Series 60 Sans", 10), fill=0x666600)
        
        ##############################################
        # Testing "status" bar. TODO: implement better, e.g. own function for status bar
        if self.Main.read_position_running:
            if self.Main.has_fix(pos):
                self.ui.point([10, 10], outline=0x00ff00, width=10)
            else:
                self.ui.point([10, 10], outline=0xffff00, width=10)
        else:
            self.ui.point([10, 10], outline=0xff0000, width=10)
        if self.Main.downloading_pois_test:
            self.ui.point([20, 10], outline=0xffff00, width=10)
                                      
        ###########################################
        # Draw scale bar
        self.draw_scalebar(self.ui)

        self.ui.text((2,15), u"%d m between points" % mdist, font=helpfont, fill=0x999999)
        self.ui.text((2,27), u"%d/%d points in history" % 
             (len(self.Main.data["position"]), self.Main.config["max_trackpoints"]), font=helpfont, fill=0x999999)
        
        self.ui.text((2,39), u"Press joystick to save a POI", font=helpfont, fill=0x999999)
        self.ui.text((2,51), u"Press * or # to zoom", font=helpfont, fill=0x999999)
        self.ui.text((2,63), u"Debug %s" % self.Main.config["track_debug"], font=helpfont, fill=0x999999)
        if self.seen_counter > 0:
            self.ui.text((100,63), u"Eaten %d" % self.seen_counter, font=helpfont, fill=0x999999)
        
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
