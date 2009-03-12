# $Id$

# DO NOT remove this
SIS_VERSION = "0.3.10"
APP_TITLE = u"PyS60GPS"

import appuifw
import e32
appuifw.app.orientation = 'portrait'
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
draw_startup_screen(canvas, u"sys, os, socket, sysinfo, re")
import sys

my_log = Logger()
#sys.stderr = sys.stdout = my_log

import os
import socket
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
draw_startup_screen(canvas, u"PositionHelper")
import PositionHelper
draw_startup_screen(canvas, u"Comm")
import Comm
draw_startup_screen(canvas, u"TopWindow")
import TopWindow

draw_startup_screen(canvas, u"SimpleChatView")
from SimpleChatView import SimpleChatView

draw_startup_screen(canvas, u"ImageGalleryView")
from ImageGalleryView import ImageGalleryView

draw_startup_screen(canvas, u"WikipediaView")
from WikipediaView import WikipediaView


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
        self.apid = None # Default access point
        self.read_config()
        if self.config.has_key("apid"):
            self._select_access_point(self.config["apid"])
        # Center meridian
        self.LongOrigin = None
        # Some counters
        self.counters = {"cellid":0,
                         "wifi":0,
                         "bluetooth":0,
                         "track":0,
                         "delivery":0,
                         }
        self.scanning = {"wifi":False,
                         "bluetooth":False,
                         }
        # Data-repository
        self.data = {}
        self.data["gsm_location"] = [] # GSM-cellid history list (location.gsm_location())
        self.data["wifi"] = [] # Wifi scan history list (wlantools.scan())
        self.data["bluetooth"] = [] # Bluetooth scan history list (lightblue.finddevices())
        # New simplified style: TODO remove old ones and rename new ones to old name
        self.data["cellid_new"] = [] # GSM-cellid history list (location.gsm_location())
        self.data["wifi_new"] = [] # Wifi scan history list (wlantools.scan())
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
        self.menu_entries.append(((u"Track"), TrackView(self)))
        self.menu_entries.append(((u"Simple chat"), SimpleChatView(self)))
        self.menu_entries.append(((u"Images"), ImageGalleryView(self)))
        self.menu_entries.append(((u"GPS Info"), GpsView(self)))
        self.menu_entries.append(((u"Sysinfo"), SysinfoView(self)))
        self.menu_entries.append(((u"WLAN"), WlanView(self)))
        self.menu_entries.append(((u"Wikipedia"), WikipediaView(self)))
        # Create main menu from that sequence
        self.main_menu = [item[0] for item in self.menu_entries]
        # Create list of views from that sequence
        self.views = [item[1] for item in self.menu_entries]
        # Create a listbox from main_menu and set select-handler
        self.listbox = appuifw.Listbox(self.main_menu, self.handle_select)
        self.comm = Comm.Comm(self.config["host"], self.config["script"])
        self.activate()
        self.beep = self.get_tone(freq=440, duration=500, volume=1.0)
        #print self.read_log_cache_filenames("track")

    def get_sis_version(self):
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
            "min_wifi_time" : 6,
            "max_wifi_time" : 600,
            "max_wifi_dist" : 100,
            "max_wifi_speed" : 60,
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
            "min_wifi_time" : 6,
            "max_wifi_time" : 3600,
            "max_wifi_dist" : 10000,
        }
        profiles["turbo"] = {
            "max_cellid_time" : 180,
            "max_cellid_dist" : 100,
            "min_wifi_time" : 6,
            "max_wifi_time" : 60,
            "max_wifi_dist" : 50,
        }
        for key in profiles[profile]:
            self.config[key] = profiles[profile][key]
        self.save_config()
        self._update_menu()

    def download_pois_new(self, pos = None):
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
        params = {"key" : self.key,
                  "username" : str(self.config["username"]),
                  "group" : str(self.config["group"]),
                  "pys60gps_version" : self.get_sis_version(),
                  }
        if pos == None:
            if self.has_fix(self.pos):
                pos = self.pos
            elif (len(self.data["position"]) > 0 and self.has_fix(self.data["position"][-1])):
                pos = self.data["position"][-1]
            else:
                appuifw.note(u"Can't download POIs, position unknown.", 'error')
                return
        params["lat"] = "%.6f" % pos["position"]["latitude"]
        params["lon"] = "%.6f" % pos["position"]["longitude"]
        # Testing
        # params["lat"] = "60.275"
        # params["lon"] = "24.98"
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
        for geom in geometries:
            lon, lat = geom["coordinates"]
            (z, e, n) = self._WGS84_UTM(lat, lon, LongOrigin=None)
            geom["coordinates_en"] = [e, n]
        self.downloading_pois_test = False
        self.data["pois_downloaded_new"] = geometries

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
                
            (u"max_wifi_time (%d)" % self.config["max_wifi_time"], 
                lambda:self.set_config_var(u"max_wifi_time ", "number", "max_wifi_time")),
                
            (u"min_wifi_time (%d)" % self.config["min_wifi_time"], 
                lambda:self.set_config_var(u"Estimation ", "number", "estimated_error_radius")),
                
            (u"max_wifi_dist (%d)" % self.config["max_wifi_dist"], 
                lambda:self.set_config_var(u"max_wifi_dist ", "number", "max_wifi_dist")),

            (u"max_wifi_speed (%d) km/h" % self.config["max_wifi_speed"], 
                lambda:self.set_config_var(u"max_wifi_speed ", "number", "max_wifi_speed")),

        ))

        set_menu = (u"Set", (
            (u"Toggle debug", self.toggle_debug),
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
            (u"Send data",self.send_delivery_data),
            (u"Login",self.login),
            (u"Reboot",self.reboot),
            (u"Version", lambda:appuifw.note("Version: " + self.get_sis_version() + 
                                             "\n" + self.__version__, 'info')),
            (u"Close", self.lock.signal),
            ]

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
            bt_addr, services = socket.bt_obex_discover()
            service = services.values()[0]
            # Upload the file
            socket.bt_obex_send_file(bt_addr, service, filename)
            appuifw.note(u"File '%s' sent" % filename)
        except Exception, error:
            appuifw.note(unicode(error), 'error')
            raise

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
            name = time.strftime("delivery-%Y%m%d-%H%M%S.json", time.localtime(current_time))
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
                if appuifw.query(u"You have no active session, would you like to login first?", 'query'):
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

    # TODO: rename gsmscan ? (alike wifiscan, btscan)
    def read_gsm_location(self):
        """
        Read gsm_location/cellid changes and save them to the gsm history list.
        """
        if not self.pos: return
        # Take the latest position and append gsm data into it if necessary
        # TODO: is it necessary to save cellid if there is no fix? 
        pos = copy.deepcopy(self.pos)
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
                timediff = pos["satellites"]["time"] - p0["satellites"]["time"]
                # Distance between current and the latest saved position
                if self.has_fix(pos):
                    dist = Calculate.distance(p0["position"]["latitude"],
                                              p0["position"]["longitude"],
                                              pos["position"]["latitude"],
                                              pos["position"]["longitude"],
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
                data = self.simplify_position(pos, isotime=True)
                cell = {"cellid" : "%s,%s,%s,%s" % (l)}
                try: # This needs some capability (ReadDeviceData?)
                    cell["signal_bars"] = sysinfo.signal_bars()
                    cell["signal_dbm"] = sysinfo.signal_dbm()
                except:
                    #data["signal_bars"] = None
                    #data["signal_dbm"] = None
                    pass
                # We put this gsm cellid in a list, because in the future there may be several (like in wifi)
                data["gsmlist"] = [cell]
                pos["gsm"] = gsm_location
                pos["text"] = l[3]
                self.append_log_cache("cellid", data)
                self.data["gsm_location"].append(pos)
                self.counters["cellid"] = self.counters["cellid"] + 1
                # save cached cellids to a permanent file after n lines
                if self.counters["cellid"] % 4 == 0:
                    self.save_log_cache("cellid")
                # Remove the oldest records if the length exceeds limit
                # TODO: make limit configurable
                if len(self.data["gsm_location"]) > 50:
                    self.data["gsm_location"].pop(0)
            return data

    def auto_wifiscan(self):
        """
        Do automatically _wifiscan() if certain contitions are met.
        """
        pos = self.pos
        if self.has_fix(pos) is False:
            return # Do not save scan automatically, if there is no fix
        dist_time_flag = False
        dist = 0
        if len(self.data["wifi"]) > 0:
            p0 = self.data["wifi"][-1] # use the latest saved point in history
            # Time difference between current and the latest saved position
            timediff = pos["satellites"]["time"] - p0["satellites"]["time"]
            # Distance between current and the latest saved position
            if self.has_fix(pos): # obsolete "if"
                dist = Calculate.distance(p0["position"]["latitude"],
                                          p0["position"]["longitude"],
                                          pos["position"]["latitude"],
                                          pos["position"]["longitude"],
                                         )
            # NOTE: pos["position"]["latitude"] may be a NaN!
            # NaN >= 500 is True
            # NaN > 500 is False in Python 2.2!!!
            if ((dist > self.config["max_wifi_dist"] 
                or timediff > self.config["max_wifi_time"])
                and timediff > 6
                and pos["course"]["speed"]*3.6 < self.config["max_wifi_speed"]):
                dist_time_flag = True
        if ((len(self.data["wifi"]) == 0
            or dist_time_flag)):
            # Start wifiscan in background
            e32.ao_sleep(0.01, self._wifiscan)

    def _wifiscan(self):
        """
        Scan all available wifi networks if wlantools-module is present.
        """
        # TODO: add lock here or immediate return if previous scan is still active / hanged
        try:
            import wlantools
        except Exception, error:
            return {"error":unicode(error)}
        if self.scanning["wifi"]:
            return {"error" : u"Wifi scan already running!"}
        self.scanning["wifi"] = True
        starttime = time.clock()
        wlan_devices = wlantools.scan(False)
        duration = time.clock() - starttime
        pos = copy.deepcopy(self.pos)
        for w in wlan_devices:
            # Lowercase all keys and Remove possible null-characters, hidden SSID shows as nulls
            for k,v in w.items():
                del w[k]
                w[k.lower()] = (u"%s" % v).replace('\x00', '')
        # s60 seems to cache wifi scans so do not save 
        # new scan point if previous scan resulted exactly the same wifi list
        try:  self.wlan_devices_latest # First test if "latest" exists
        except: self.wlan_devices_latest = None # TODO: this should be done in init
        # Save new scan point always if latest's result was empty  
        if (wlan_devices != []):
            if (self.wlan_devices_latest == wlan_devices):
                self.scanning["wifi"] = False
                return {"info":u"Wifi scan too fast, skipping this one!"}
        self.wlan_devices_latest = wlan_devices
        data = self.simplify_position(pos, isotime=True)
        #data["comment"] = u""
        data["duration"] = duration
        data["wifilist"] = wlan_devices
        #if not self.has_fix(pos): # TODO: move this interaction to some other function, e.g in tracktab
        #    data["comment"] = appuifw.query(u"No GPS fix, add text comment", "text", u"")
        if not data.has_key("systime"):
            # FIXME: create function to get ISO systime string
            # TODO: use above function here and everywhere
            data["systime"] = self.get_iso_systime()
        self.append_log_cache("wifi", data)
        if self.counters["wifi"] % 5 == 0:
            self.save_log_cache("wifi")
        # Add a pos to be drawn on the canvas
        pos["text"] = u"%d" % len(wlan_devices)
        self.data["wifi"].append(pos)
        if len(self.data["wifi"]) > 100:
            self.data["wifi"].pop(0)
        self.scanning["wifi"] = False
        return data

    def wifiscan(self, comment = None):
        data = self._wifiscan()
        if "error" in data:
            appuifw.note(data["error"], 'error')
            return {}
        elif "info" in data:
            appuifw.note(data["info"], 'info')
            return {}
        if not self.has_fix(self.pos): # TODO: move this interaction to some other function, e.g in tracktab
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
        pos = copy.deepcopy(self.pos)
        if not self.has_fix(pos): # TODO: move this interaction to some other function, e.g in tracktab
            # Query this before, because finddevices() may take several minutes
            comment = appuifw.query(u"No GPS fix, add text comment", "text", u"")
        else:
            comment = u""
        starttime = time.clock()
        bt_devices = lightblue.finddevices()
        data = self.simplify_position(pos, isotime=True)
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

    def _calculate_UTM(self, pos, LongOrigin=None):
        """
        Calculate UTM coordinates and append them to pos. 
        pos["position"]["latitude"] and 
        pos["position"]["longitude"] must exist and be float.
        """
        if self.LongOrigin:
             LongOrigin = self.LongOrigin
        try:
            (pos["position"]["z"], 
             pos["position"]["e"], 
             pos["position"]["n"]) = self._WGS84_UTM(pos["position"]["latitude"],
                                                     pos["position"]["longitude"],
                                                     LongOrigin)
            return True
        except:
            # TODO: line number and exception text here too?
            self.log(u"exception", u"Failed to LLtoUTM()")
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

    def has_fix(self, pos):
        """Return True if pos has a fix."""
        if pos.has_key("position") and  pos["position"].has_key("latitude") and str(pos["position"]["latitude"]) != "NaN":
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
        if self.config["track_debug"]:
            self.data["position_debug"].append(pos)
            if len(self.data["position_debug"]) > self.config["max_debugpoints"]:
                self.data["position_debug"].pop(0)
            # TODO:
            # self.data["position_debug"].append(pos)
        if self.has_fix(pos):
            if not self.LongOrigin: # Set center meridian
                self.LongOrigin = pos["position"]["longitude"]
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
            if pos["position"]["horizontal_accuracy"] > mindist: # horizontal_accuracy may be NaN
                mindist = pos["position"]["horizontal_accuracy"]
            if len(self.data["position"]) > 0:
                p0 = self.data["position"][-1] # use the latest saved point in history
                if len(self.data["position"]) > 1:
                    p1 = self.data["position"][-2] # used to calculate estimation line
                else:
                    p1 = None
                # Distance between current and the latest saved position
                dist = Calculate.distance(p0["position"]["latitude"],
                                          p0["position"]["longitude"],
                                          pos["position"]["latitude"],
                                          pos["position"]["longitude"],
                                         )
                # Difference of heading between current and the latest saved position
                anglediff = Calculate.anglediff(p0["course"]["heading"], pos["course"]["heading"])
                # Time difference between current and the latest saved position
                timediff = pos["satellites"]["time"] - p0["satellites"]["time"]
                
                # Project a location estimation point (pe) using speed and heading from the latest saved point
                pe = {}
                # timediff = time.time() - p0['systime']
                dist_project = p0["course"]["speed"] * timediff # speed * seconds = distance in meters
                lat, lon = Calculate.newlatlon(p0["position"]["latitude"], p0["position"]["longitude"], 
                                               dist_project, p0["course"]["heading"])
                pe["position"] = {}
                pe["position"]["latitude"] = lat
                pe["position"]["longitude"] = lon
                self.Main._calculate_UTM(pe)
                self.pos_estimate = pe
                # This calculates the distance between the current point and the estimated point.
                # Perhaps ellips could be more optime?
                dist_estimate = Calculate.distance(pe["position"]["latitude"],
                                          pe["position"]["longitude"],
                                          pos["position"]["latitude"],
                                          pos["position"]["longitude"],
                                         )
                # This calculates the distance of the current point from the estimation vector
                # In the future this will be an alternate to the estimation circle
                if p0.has_key("course") and p0["course"].has_key("speed") and p0["course"].has_key("heading"):
                    dist_line  = distance_from_vector(p0["position"]["e"], p0["position"]["n"],
                                                      p0["course"]["speed"]*3.6, p0["course"]["heading"],
                                                      pos["position"]["e"],pos["position"]["n"])
                if p1 and p0.has_key("course") and p0["course"].has_key("speed") and p0["course"].has_key("heading") \
                 and p1.has_key("course") and p1["course"].has_key("speed") and p1["course"].has_key("heading"):
                    dist_line  = distance_from_line(p0["position"]["e"], p0["position"]["n"],
                                                    p1["position"]["e"], p1["position"]["n"],
                                                    pos["position"]["e"],pos["position"]["n"])
                                         
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
                self.append_log_cache("track", data)
                self.counters["track"] = self.counters["track"] + 1
                # save cellids after n lines
                if self.counters["track"] % 10 == 0: 
                    self.save_log_cache("track")
                # If data["position"] is too long, remove some of the oldest points
                if len(self.data["position"]) > self.config["max_trackpoints"]:
                    self.data["position"].pop(0) # pop twice to reduce the number of points
        # Calculate the distance between the newest and the previous pos and add it to trip_distance
        try: # TODO: do not add if time between positions is more than e.g. 120 sec
            if pos["satellites"]["time"] - self.pos["satellites"]["time"] < 120:
                #d = Calculate.distance(self.pos["position"]["latitude"],self.pos["position"]["longitude"],
                #                       pos["position"]["latitude"], pos["position"]["longitude"])
                # This should be cheaper
                d = math.sqrt((self.pos["position"]["e"] - pos["position"]["e"])**2 + (self.pos["position"]["n"] - pos["position"]["n"])**2)
                self.data["trip_distance"] = self.data["trip_distance"] + d
                self.data["dist_2_latest"] = d
                #self.data["debug"] = u"E:%.1f N:%.1f" % (abs(self.pos["position"]["e"] - pos["position"]["e"]), abs(self.pos["position"]["n"] - pos["position"]["n"]))
        except: # FIXME: check first do both positions exist and has_fix(), then 
            pass
        # Save the new pos to global (current) self.pos
        self.pos = pos
        # Read gsm-cell changes
        self.read_gsm_location()
        # Scan wifi's automatically
        self.auto_wifiscan()
        # TODO: wifiscan() here if it is time to do it
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
            e32.start_exe(u'Z:\\System\\Programs\\Starter.exe', '', 0)

    def handle_select(self):
        self.views[self.listbox.current()].activate()

    def handle_content(self, arg):
        appuifw.note(u"Chosen: %s " % arg, 'info')

    def exit_key_handler(self):
        if appuifw.query(u"Quit program", 'query') is True:
            self.running = False
            self.lock.signal()

    def close(self):
        positioning.stop_position()
        appuifw.app.exit_key_handler = None
        self.running = False
        self.flush_delivery_data()
        self.save_log_cache("track")
        self.save_log_cache("cellid") 
        self.save_log_cache("wifi")
        self.send_delivery_data(True, True)
        appuifw.app.set_tabs([u"Back to normal"], lambda x: None)

    def get_tone(self, freq=440, duration=1000, volume=0.5):
        from struct import pack
        from math import sin, pi
        f = open('D:\\tmptone.au', 'wb')    # temp file
        f.write('.snd' + pack('>5L', 24, 8*duration, 2, 8000, 1))  #header
        for i in range(duration*8):
            sin_i = sin(i * 2*pi*freq/8000)  # sine wave
            f.write(pack('b', volume*127*sin_i))
        f.close()
        # now play the file
        s = audio.Sound.open('D:\\tmptone.au')
        return s
    
    def play_tone(self):
        if self.beep.state() == audio.EPlaying:
            return
            #sound_barf.stop()
        self.beep.play()

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

############## Sysinfo VIEW START ##############
class SysinfoView(BaseTabbedView):
    def __init__(self, parent):
        self.name = "SysinfoView"
        self.parent = parent
        self.Main = parent.Main
        self.init_ram = sysinfo.free_ram()
        self.tabs = []
        self.tabs.append((u"Gsm", GsmTab(self)))
        self.tabs.append((u"Wifi", WifiTab(self)))
        self.tabs.append((u"E32", E32InfoTab(self)))
        self.tabs.append((u"Mem", MemTab(self)))
        self.tabs.append((u"SysInfo", SysInfoTab(self)))
        self.current_tab = 0

    def close(self):
        try:
            for tab in self.tabs:
                tab[1].t.cancel()
        except:
            print dir(tab[1])
            pass
        appuifw.app.set_tabs([u"Back to normal"], lambda x: None)
        # Activate previous (calling) view
        self.parent.activate()

class SysInfoTab(BaseInfoTab):
    def _get_lines(self):
        lines = []
        lines.append(u"Time: %s" % time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time())))
        try:
            #lines.append(u"Battery: %s" % sysinfo.battery())
            #lines.append(u"Signal bars: %d" % sysinfo.signal_bars())
            #lines.append(u"Signal DBM: %.1f" % sysinfo.signal_dbm())
            lines.append(u"Profile: %s" % sysinfo.active_profile())
            lines.append(u"Twips: %d x %d" % sysinfo.display_twips())
            lines.append(u"Pixels: %d x %d" % sysinfo.display_pixels())
            lines.append(u"IMEI: %s" % sysinfo.imei())
            lines.append(u"Os version: %d.%d.%d" % sysinfo.os_version())
            lines.append(u"Sw version: %s" % sysinfo.sw_version())
        except:
            lines.append(u"sysinfo not functional")
        return lines

class E32InfoTab(BaseInfoTab):
    def _get_lines(self):
        lines = []
        lines.append(u"Pys60: %d.%d.%d %s %d" % e32.pys60_version_info)
        lines.append(u"S60: %d.%d" % e32.s60_version_info)
        lines.append(u"Name: %s" % appuifw.app.full_name())
        lines.append(u"UID: %s" % appuifw.app.uid())
        lines.append(u"Inactive: %d sec" % e32.inactivity())
        return lines

class MemTab(BaseInfoTab):
    """Show some information about memory."""
    def _get_lines(self):
        lines = [u"Free drivespace:"]
        drives = sysinfo.free_drivespace()
        for d in drives.keys():
            lines.append(u"%s %d kB" % (d, drives[d]/1024))
        lines.append(u"Init RAM: %d kB" % (self.parent.init_ram/1024))
        lines.append(u"Free RAM: %d kB" % (sysinfo.free_ram()/1024))
        lines.append(u"Total RAM: %d kB" % (sysinfo.total_ram()/1024))
        return lines

class GsmTab(BaseInfoTab):
    """Show a few last gsm-cellid's."""
    def _get_lines(self):
        lines = [u"GSM-cells: %d lines" % len(self.Main.data["gsm_location"])]
        last = self.Main.data["gsm_location"][-13:]
        last.reverse()
        for l in last:
            try:
                lines.append(u"%s" % time.strftime("%H:%M:%S ", time.localtime(l["systime"]))
                           + u"%s,%s,%s,%s" % (l['gsm']["cellid"]))
            except:
                lines.append(u"Error in gsm data")
        return lines

class WifiTab(BaseInfoTab):
    """Show a few last wifi's."""
    def _get_lines(self):
        lines = [u"Wifis: %d lines" % len(self.Main.data["wifi"])]
        last = self.Main.data["wifi"][-13:]
        last.reverse()
        for l in last:
            try:
                lines.append(u"%s" % time.strftime("%H:%M:%S ", time.localtime(l["systime"]))
                            + u"  %s wifis found" % (l['text']))
            except:
                lines.append(u"Error in gsm data")
        return lines
############## Sysinfo VIEW END ###############

############## GPS VIEW START ##############
class GpsView(BaseTabbedView):
    def __init__(self, parent):
        self.name = "GpsView"
        self.parent = parent
        self.Main = parent.Main
        self.tabs = []
        self.tabs.append((u"Gps", GpsInfoTab(self)))
        self.tabs.append((u"Speed", GpsSpeedTab(self)))
        self.current_tab = 0

    def activate(self):
        BaseTabbedView.activate(self)
        if self.Main.read_position_running == False:
            self.Main.start_read_position()

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

class GpsInfoTab(BaseInfoTab):

    def update(self, dummy=(0, 0, 0, 0)):
        self.t.cancel()
        lines = self._get_lines()
        self.canvas.clear()
        if self.Main.pos and time.time() - self.Main.pos["systime"] > 1:
            textcolor = 0xb0b0b0 # use gray font color if position is older than 1 sec
        else: 
            textcolor = 0x000000
        self.blit_lines(lines, color=textcolor)
        if self.active:
            self.t.after(0.5, self.update)

    def _get_lines(self):
        lines = []
        pos = self.Main.pos
        try:
            p = pos["position"]
            c = pos["course"]
            s = pos["satellites"]
        except:
            lines.append(u"GPS-data not available")
            lines.append(u"Use main screens GPS-menu")
            return lines
        # Position-data
        if str(p["altitude"]) != "NaN":
            lines.append(u"Altitude: %d m" % (p["altitude"]))
        if str(p["latitude"]) != "NaN":
            lines.append(u"Lat: %.5f " % (p["latitude"]))
        if str(p["longitude"]) != "NaN":
            lines.append(u"Lon: %.5f " % (p["longitude"]))
        if p.has_key("e"):
            lines.append(u"E: %.3f N: %.3f" % (p["e"],p["n"]))
        if str(p["horizontal_accuracy"]) != "NaN" and str(p["vertical_accuracy"]) != "NaN":
            lines.append(u"Accuracy (Hor/Ver): %.1f/%.1f " % (p["horizontal_accuracy"],p["vertical_accuracy"]))
        # Course-data
        if str(c["speed"]) != "NaN":
            lines.append(u"Speed: %.1f m/s %.1f km/h" % (c["speed"], c["speed"]*3.6))
        if str(c["heading"]) != "NaN":
            lines.append(u"Heading: %.1f " % (c["heading"]))
        if str(c["speed_accuracy"]) != "NaN":
            lines.append(u"Accuracy (speed): %.1f " % (c["speed_accuracy"]))
        if str(c["heading_accuracy"]) != "NaN":
            lines.append(u"Accuracy (heading): %.1f " % (c["heading_accuracy"]))
        # Satellites-data
        if str(s["time"]) != "NaN":
            lines.append(u"GPS-Time: %s" % time.strftime("%Y-%m-%d %H:%M:%SZ", time.localtime(s["time"])))
        lines.append(u"Sys-Time: %s" % time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time())))
        lines.append(u"Satellites: %s/%s" % (s["used_satellites"],s["satellites"]))
        lines.append(u"DOP (H/V/T) %.1f/%.1f/%.1f" % (s["horizontal_dop"],s["vertical_dop"],s["time_dop"]))
        return lines

class TrackView(BaseTabbedView):
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
                 "wifi":False,
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
        self.canvas.bind(key_codes.EKeySelect, self.save_poi)
        self.canvas.bind(key_codes.EKey1, lambda: self.toggle("track"))
        self.canvas.bind(key_codes.EKey2, lambda: self.toggle("cellid"))
        self.canvas.bind(key_codes.EKey3, lambda: self.toggle("wifi"))
        self.canvas.bind(key_codes.EKey4, self.Main.wifiscan)
        self.canvas.bind(key_codes.EKey6, self.Main.bluetoothscan)

        appuifw.app.menu.insert(0, (u"Send track via bluetooth", self.send_track))
        appuifw.app.menu.insert(0, (u"Send cellids via bluetooth", self.send_cellids))
        appuifw.app.menu.insert(0, (u"Send debug track via bluetooth", self.send_debug))
        appuifw.app.menu.insert(0, (u"Set meters/pixel", 
                                    lambda:self.set_meters_per_px(appuifw.query(u"Meters","number", self.meters_per_px))))
        appuifw.app.menu.insert(0, (u"Add POI", self.save_poi))
        appuifw.app.menu.insert(0, (u"Download", self.download_pois_new))
        e32.ao_sleep(0.1)
        if self.Main.read_position_running == False:
            self.Main.start_read_position()
        self.update()

    def download_pois_new(self):
        self.active = False # FIXME: this shoud be inactive only when query dialog is open
        # Perhaps self.Main.download_pois_test() could take "this" as an argument: 
        # self.Main.download_pois_test(self)
        # and when query is open, Main could set view.active = False
        self.Main.download_pois_new()
        self.active = True
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
            self.center_pos["position"]["e"] = self.center_pos["position"]["e"] + move_m
            # TODO: calc lat and lon here too
        elif (0,1) == (x,y):
            # direction = u"south"
            self.center_pos["position"]["n"] = self.center_pos["position"]["n"] - move_m
            # TODO: calc lat and lon here too
        elif (-1,0) == (x,y):
            # direction = u"west"
            self.center_pos["position"]["e"] = self.center_pos["position"]["e"] - move_m
            # TODO: calc lat and lon here too
        elif (0,-1) == (x,y):
            # direction = u"north"
            self.center_pos["position"]["n"] = self.center_pos["position"]["n"] + move_m
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
    
    def send_track(self):
        # TODO: create also function to send via HTTP
        """
        Send saved track to the other bluetooth device.
        """
        wpts = []
        trkpts = []
        for p in self.Main.data["pois_private"]:
            wpts.append(self._make_gpx_trkpt(p, "wpt"))
        for p in self.Main.data["position"]:
            trkpts.append(self._make_gpx_trkpt(p))
        if p:
            last_time = time.strftime(u"%Y%m%dT%H%M%SZ", time.localtime(p["satellites"]["time"]))
            filename = u"trackpoints-%s.gpx" % last_time
            last_isotime = time.strftime(u"%Y-%m-%dT%H:%M:%SZ", time.localtime(p["satellites"]["time"]))
        else:
            filename = u"trackpoints-notime.gpx"
        filename = os.path.join(self.Main.datadir, filename)
        f = open(filename, "wt")
        data = """<?xml version='1.0'?><gpx creator="Pys60Gps" version="0.1" xmlns="http://www.topografix.com/GPX/1/1" xmlns:gpslog="http://FIXME.FI" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="FIXME FIXME FIXME http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd"><metadata> <time>%s</time></metadata>%s
<trk><trkseg>%s
</trkseg></trk></gpx>
""" % (last_isotime, 
       u"\n".join(wpts).encode('utf-8'),
       u"\n".join(trkpts).encode('utf-8'))
        f.write(data)
        f.close()
        self.Main.send_file_over_bluetooth(filename)

    def _make_gpx_trkpt(self, p, type = "trkpt"):
        """Temporary function to help to make trkpt:s"""
        if p.has_key("text"):
            name = u"\n <name>%s</name>" % p["text"]
        else: 
            name = u""
        return """<%s lat="%.6f" lon="%.6f">
 <ele>%.1f</ele>
 <time>%s</time>%s
</%s>""" % (type,
            p["position"]["latitude"],
            p["position"]["longitude"],
            p["position"]["altitude"],
            time.strftime(u"%Y-%m-%dT%H:%M:%SZ", time.localtime(p["satellites"]["time"])),
            name,
            type,
           )

    def send_cellids(self):
        trkpts = []
        p = None
        gsm = self.Main.data["gsm_location"]
        lengsm = len(gsm) # Save the length 
        i = 0
        if lengsm == 1: # Save the first point 
            trkpts.append(PositionHelper._make_xml_cellpt(gsm[0], gsm[0]))
        for i in range(1,lengsm): # Save points 1..last
            trkpts.append(PositionHelper._make_xml_cellpt(gsm[i-1], gsm[i]))
        if lengsm > 0:
            last_time = time.strftime(u"%Y%m%dT%H%M%SZ", time.localtime(gsm[i]["satellites"]["time"]))
            filename = u"cellids-%s.txt" % last_time
        else:
            filename = u"cellids-notime.txt"
        filename = os.path.join(self.Main.datadir, filename)

        # TODO: Try/except here
        f = open(filename, "wt")
        data = u"\n".join(trkpts).encode('utf-8')
        f.write(data)
        f.close()
        # If writing to a file was successful (we are here) remove all saved cellpoints from the list
        self.Main.data["gsm_location"] = self.Main.data["gsm_location"][lengsm:] 
        self.Main.send_file_over_bluetooth(filename)

    def send_debug(self):
        """
        Send saved position data to the other bluetooth device.
        """
        # jsonize only one pos per time, otherwise out of memory or takes very long time
        points = []
        for p in self.Main.data["position_debug"]:
            points.append(simplejson.dumps(p))
        data = "\n".join(points)
        name = appuifw.query(u"Name", "text", u"")
        if name is None:
            name = u"latest" # TODO: strftimestamp here
        filename = u"trackdebug-%s.txt" % name
        filename = os.path.join(self.Main.datadir, filename)
        f = open(filename, "wt")
        f.write(data)
        f.close()
        self.Main.send_file_over_bluetooth(filename)

    def save_poi(self):
        """
        Saves a point to the "pois" list.
        """
        # TODO: put POIs to the global data dictionary
        if not self.Main.pos: # empty position, no gps connected yet
            appuifw.note(u"No GPS", 'error')
            return
        
        pos = self.Main.pos
        # Default name is gps timestamp (UTC) with timezone info (time.altzone)
        ts = unicode(time.strftime(u"%H:%M:%SZ ", time.localtime(pos["satellites"]["time"])))
        # print pos
        pos["text"] = appuifw.query(u"Name", "text", ts)
        if pos["text"] is not None: # user did not press Cancel
            self.Main.data["pois_private"].append(pos)
        else:  # user pressed cancel -> no POI
            pass
            #pos["text"] = u"" # empty text
        
    def _calculate_canvas_xy(self, image, meters_per_px, p0, p):
        """
        Calculcate x- and y-coordiates for point p.
        p0 is the center point of the image.
        """
        # is image neccessary?
        if not p.has_key("position") or not p["position"].has_key("e"): return
        if not p0.has_key("position") or not p0["position"].has_key("e"): return
        p["x"] = int((-p0["position"]["e"] + p["position"]["e"]) / meters_per_px)
        p["y"] = int((p0["position"]["n"] - p["position"]["n"]) / meters_per_px)

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
            acc_radius = pos["position"]["horizontal_accuracy"]
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
            #self.ui.text(([10, 230]), u"%.1f km/h %.1f' %s" % (pos["course"]["speed"]*3.6, pos["course"]["heading"],  trip),
            # TODO: replace ' with hex representation of degree sign (ASCII b0, UNICODE ?) 
            self.ui.text(([10, 230]), u"%.1f m/s %.1f' %s" % (pos["course"]["speed"], pos["course"]["heading"],  trip), 
                                      font=(u"Series 60 Sans", 18), fill=0x000000)
        
        ##############################################        
        # TESTING direction line
        if len(self.Main.data["position"]) > 0 and self.Main.data["position"][-1]["course"].has_key("speed"):
            # Copy latest saved position from history
            p = copy.deepcopy(self.Main.data["position"][-1])
            self._calculate_canvas_xy(self.ui, self.meters_per_px, pc, p)
            # Project new point from latest point, heading and speed
            p1 = {}
            p1["position"] = {}
            x, y = project_point(p["position"]["e"], p["position"]["n"], p["course"]["speed"]*20, p["course"]["heading"])
            p1["position"]["e"], p1["position"]["n"] = x, y
            try:
                self._calculate_canvas_xy(self.ui, self.meters_per_px, pc, p1)
                x0, y0 = p["x"], p["y"]
                x, y = p1["x"], p1["y"]
            except:
                x0, y0 = 0, 0
                x, y = 0, 0
            #x,y = project_point(x0, y0, p["course"]["speed"]*3.6, p["course"]["heading"])
            self.ui.line([x0+center_x, y0+center_y, x+center_x, y+center_y], outline=0xffff99, 
                          width=1+(self.Main.config["max_estimation_vector_distance"]/self.meters_per_px/2))
            #dist  = distance_from_vector(p["position"]["e"], p["position"]["n"],
            #                             p["course"]["speed"]*3.6, p["course"]["heading"],
            #                             pos["position"]["e"],pos["position"]["n"])
            dist = self.Main.data["dist_line"]
            s=50
            i=15
            try:
                d = math.sqrt((p["position"]["e"] - pos["position"]["e"])**2 + (p["position"]["n"] - pos["position"]["n"])**2)
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
        if self.Main.has_fix(pos) and pos["course"]["heading"] and pos["course"]["speed"]:
            p = copy.deepcopy(pos)
            self._calculate_canvas_xy(self.ui, self.meters_per_px, pc, p)
            try:
                p1 = {}
                p1["position"] = {}
                p1["position"]["e"], p1["position"]["n"] = project_point(p["position"]["e"], p["position"]["n"], 
                                                                         50*self.meters_per_px, p["course"]["heading"])
#                                                                         p["course"]["speed"]*20, p["course"]["heading"])
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
        # Draw Wifi points
        for p in self.Main.data["wifi"]:
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
            timediff = abs(p["satellites"]["time"] - p1["satellites"]["time"])
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
                if not p.has_key("seen") and Calculate.distance(pos["position"]["latitude"],
                                      pos["position"]["longitude"],
                                      p["position"]["latitude"],
                                      p["position"]["longitude"],
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
            new_pc = {"coordinates_en" : [pc["position"]["e"], pc["position"]["n"]]}
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
        
        if self.center_pos and self.center_pos["position"].has_key("e"):
            self.ui.text((2,75), u"E %.2f" % self.center_pos["position"]["e"], font=helpfont, fill=0x999999)

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

class GpsSpeedTab(BaseInfoTab):
    def update(self, dummy=(0, 0, 0, 0)):
        """
        Print current speed with BIG font.
        Print some kind of speed history.
        TODO: This really needs some cleanup.
        """
        self.canvas.clear()
        if self.Main.pos:
            pos = self.Main.pos
        else:
            self.canvas.text(([10, 130]), u"No GPS", font=(u"Series 60 Sans", 30), fill=0xff0000)
            return

        speed_kmh = pos["course"]["speed"] * 3.6
        if speed_kmh > 100:
            format = u"%d"
        else:
            format = u"%.1f"
        self.canvas.text(([10, 30]), u"%.1f m/s" % pos["course"]["speed"], font=(u"Series 60 Sans", 30), fill=0x000000)
        self.canvas.text(([10, 230]), format % speed_kmh, font=(u"Series 60 Sans", 100), fill=0x000000)
        self.canvas.text(([200, 200]), u"km", font=(u"Series 60 Sans", 30), fill=0x000000)
        self.canvas.text(([200, 200]), u"____", font=(u"Series 60 Sans", 30), fill=0x000000)
        self.canvas.text(([200, 230]), u"h", font=(u"Series 60 Sans", 30), fill=0x000000)
        speed_0 = 140
        speed_50 = 90
        speed_100 = 40
        i = 0
        # Draw the speed graph
        for p in self.Main.speed_history:
            speed_min = speed_0 - p["speedmin"] * 3.6
            speed_max = speed_0 - 1 - p["speedmax"] * 3.6 # at least 1 px height
            self.canvas.line([i, speed_min, i, speed_max], outline=0x0000ff, width=2)
            i = i + 1
        self.canvas.line([0, speed_0, 200, speed_0], outline=0x999999, width=1)
        self.canvas.text(([5, speed_0+5]), u"0 km/h", font=(u"Series 60 Sans", 10), fill=0x333333)
        self.canvas.line([0, speed_50, 200, speed_50], outline=0x999999, width=1)
        self.canvas.text(([5, speed_50+5]), u"50 km/h", font=(u"Series 60 Sans", 10), fill=0x333333)
        self.canvas.line([0, speed_100, 200, speed_100], outline=0x999999, width=1)
        self.canvas.text(([5, speed_100+5]), u"100 km/h", font=(u"Series 60 Sans", 10), fill=0x333333)
        if self.active:
            self.t.cancel()
            self.t.after(0.5, self.update)

class WlanView(BaseTabbedView):
    
    def __init__(self, parent):
        self.name = "SysinfoView"
        self.parent = parent
        self.Main = parent.Main
        self.wlans = []
        self.active = False
        self.fontheight = 15
        self.lineheight = 17
        self.font = (u"Series 60 Sans", self.fontheight)

    def scan(self):
        if e32.in_emulator():
            time.sleep(1)
            import random
            self.wlans = [
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
                self.wlans = wlantools.scan(False)
            except Exception, error:
                appuifw.note(u"No wlantools.", 'error')
                return {"error":unicode(error)}
        # DSU-sort by RxLevel
        decorated  = [(i['RxLevel'], i) for i in self.wlans]
        decorated.sort()
        decorated.reverse()
        self.wlans = [item for (name, item) in decorated]

    def activate(self):
        self.active = True
        appuifw.app.exit_key_handler = self.close
        self.canvas = appuifw.Canvas(redraw_callback=self.update)
        appuifw.app.body = self.canvas
        appuifw.app.screen = "normal"
        appuifw.app.menu = [
                            (u"Scan", self.scan),
                            (u"Update", self.update),
                            (u"Close", self.close),
                            ]
        self.scan()
        self.update()

    def _get_lines(self):
        lines = []
        for wlan in self.wlans:
            lines.append(u"%d %s %s" % (wlan["RxLevel"], wlan["BSSID"], wlan["SSID"]))
        return lines

    def update(self, dummy=(0, 0, 0, 0)):
        """
        Simply call self.blit_lines(lines) to draw some lines of text to the canvas.
        This should be overriden in the deriving class if more complex operations are wanted.
        Start a new timer to call update again after a short while.
        """
        lines = self._get_lines()
        self.canvas.clear()
        self.blit_lines(lines)

    def blit_lines(self, lines, color=0x000000):
        """
        Draw some lines of text to the canvas.
        """
        self.canvas.clear()
        start = 0
        for l in lines:
            start = start + self.lineheight
            self.canvas.text((3,start), l, font=self.font, fill=color)

    def close(self):
        # Activate previous (calling) view
        self.parent.activate()

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
