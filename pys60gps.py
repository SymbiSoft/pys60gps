# -*- coding: iso-8859-15 -*-
# $Id$

# TODO: import topwindow and splashscreen here
import sys
import os.path
import appuifw
appuifw.app.orientation = 'portrait'
import e32
import socket
import sysinfo
import time
import positioning
import location
import key_codes
import graphics
import LatLongUTMconversion
import Calculate
import pys60_json as json


class GpsApp:
    __version__ = u'$Id$'

    def __init__(self):
        self.Main = self # This is the base of all views, tabs etc.
        self.lock = e32.Ao_lock()
        appuifw.app.exit_key_handler = self.exit_key_handler
        self.running = True
        self.focus = True
        appuifw.app.focus = self.focus_callback # Set up focus callback
        self.read_position_running = False
        # Configuration/settings
        self.config = {} # TODO: read these from a configuration file
        # TODO: self.config = self.read_config()
        self.config["max_speed_history_points"] = 200
        self.config["min_trackpoint_distance"] = 300 # meters
        self.config["estimated_error_radius"] = 20 # meters
        self.config["max_trackpoints"] = 500
        self.config["max_debugpoints"] = 500
        self.config["track_debug"] = False
        # Create a directory to contain all gathered and downloaded data
        self.datadir = os.path.join(u"c:", u"data", u"Pys60Gps")
        if not os.path.exists(self.datadir):
            os.makedirs(self.datadir)
        # Data-repository
        self.data = {}
        self.data["gsm_location"] = [] # GSM-cellid history list (location.gsm_location())
        # GPS-position
        self.pos = {} # Contains always the latest position-record
        self.data["position"] = [] # Position history list (positioning.position())
        self.pos_estimate = {} # Contains estimated location, calculated from the latest history point
        self.data["position_debug"] = [] # latest "max_debugpoints" 
        # POIs
        self.data["pois_private"] = []
        self.data["pois_downloaded"] = []
        # Test poi
        self.key = u""
        pos = {"position": {}}
        pos["position"]["latitude"] = 61.448268
        pos["position"]["longitude"] = 23.854067
        pos["systime"] = time.time()
        pos["text"] = u"Hervanta"
        self._calculate_UTM(pos)
        self.data["pois_downloaded"].append(pos)
        pos = {"position": {}}
        pos["position"]["latitude"] = 60.170704
        pos["position"]["longitude"] = 24.941435
        pos["systime"] = time.time()
        pos["text"] = u"Hki assa"
        self._calculate_UTM(pos)
        self.data["pois_downloaded"].append(pos)
        # temporary solution to handle speed data (to be removed/changed)
        self.speed_history = []
        self.min_trackpoint_distance = 300 # TODO: REMOVE
        self.max_trackpoints = 500 # TODO: REMOVE
        self.track_debug = False # TODO: REMOVE
        # Put all menu entries and views as tuples into a sequence
        self.menu_entries = []
        self.menu_entries.append(((u"Track"), TrackView(self)))
        self.menu_entries.append(((u"GPS"), GpsView(self)))
        self.menu_entries.append(((u"Sysinfo"), SysinfoView(self)))
        # Create main menu from that sequence
        self.main_menu = [item[0] for item in self.menu_entries]
        # Create list of views from that sequence
        self.views = [item[1] for item in self.menu_entries]
        # Create a listbox from main_menu and set select-handler
        self.listbox = appuifw.Listbox(self.main_menu, self.handle_select)
        self.activate()

    def download_pois(self):
        """
        Test function for downloading POI-object from the internet
        """
        import urllib
        self.key = appuifw.query(u"Keyword", "text", self.key)
        if self.key is None: self.key = u""
        params = {'key': self.key}
        if (len(self.data["position"]) > 0):
            pos = self.data["position"][-1]
            params["lat"] = pos["position"]["latitude"]
            params["lon"] = pos["position"]["longitude"]
        else:
            appuifw.note(u"Can't download POIs, current position unknown.", 'error')
            return
        params = urllib.urlencode(params)
        try: # FIXME: hardcoded url TODO: centralized communication to the server
            f = urllib.urlopen("http://www.plok.in/poi.php", params)
            jsondata = f.read() 
            # print jsondata.decode("utf-8")
            # NOTE: all strings in "pois" are now plain utf-8 encoded strings
            # so they are not valid arguments for canvas.text() or appuifw.note() !
            pois = json.read(jsondata) 
            f.close()
            for pos in pois:
                self._calculate_UTM(pos)
                pos["text"] = pos["text"].decode("utf-8")
            self.data["pois_downloaded"] = pois
        except Exception, error:
            appuifw.note(unicode(error), 'error')
            raise

    def activate(self):
        """Set main menu to app.body and left menu entries."""
        # Use exit_key_handler of current class
        appuifw.app.exit_key_handler = self.exit_key_handler
        appuifw.app.body = self.listbox
        tp_values = [10,20,50,100,200,500,1000,5000,10000]
        tp_menu_entries = [ (u'%s meters' % v, lambda:self.set_trackpoint_distance(v)) for v in tp_values ]
        # We need to convert list to a tuple for appuifw.app.menu
        set_trackpoint_distance_menu=(u"Trackpoint dist (broken)", tuple(tp_menu_entries))
        appuifw.app.menu = [
            (u"Select",self.handle_select),
            (u"GPS",self.start_read_position), # TODO: add GPS on/off to the menu
            (u"Max trackpoints (%d)" % self.max_trackpoints, 
                  lambda:self.set_max_trackpoints(appuifw.query(u"Max points","number", self.max_trackpoints))),
            (u"Set trackpoint dist (%d)" % self.min_trackpoint_distance, 
                  lambda:self.set_trackpoint_distance(appuifw.query(u"Trackpoint dist","number", self.min_trackpoint_distance))),
            (u"Set estimation error (%d)" % self.config["estimated_error_radius"], 
                  lambda:self.set_estimate_error(appuifw.query(u"Estimate error","number", self.config["estimated_error_radius"]))),
            set_trackpoint_distance_menu,
            (u"Toggle debug",self.toggle_debug),
            (u"Reboot",self.reboot),
            (u"Version", lambda:appuifw.note(self.__version__, 'info')),
            (u"Close", self.lock.signal),
            ]
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

    def set_trackpoint_distance(self, distance):
        if distance is not None:
            self.min_trackpoint_distance = distance
            self.config["min_trackpoint_distance"] = distance

    def set_max_trackpoints(self, max):
        if max and max > 0:
            self.max_trackpoints = max
            self.config["max_trackpoints"] = max

    def set_estimate_error(self, meters):
        if meters and meters >= 0:
            self.config["estimated_error_radius"] = meters

    def toggle_debug(self):
        self.track_debug = not self.track_debug # Toggle true <-> false

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
            appuifw.note(u"Stopping GPS...", 'info')
            return
        self.read_position_running = True
        positioning.set_requestors([{"type":"service", 
                                     "format":"application", 
                                     "data":"test_app"}])
        positioning.position(course=1,satellites=1, callback=self.read_position, interval=1000000, partial=1) 
        appuifw.note(u"Starting GPS...", 'info')

    def read_gsm_location(self):
        """
        Read gsm_location/cellid changes and save them to the gsm history list.
        """
        # Take the latest position and append gsm data into it if neccessary
        pos = self.pos 
        if not pos: return
        l = location.gsm_location()
        if e32.in_emulator(): # Do some random cell changes if in emulator
            import random
            if random.random() < 0.05:
                l = ('244','123','29000',random.randint(1,2**24))
        # NOTE: gsm_location() may return None in certain circumstances!
        if l is not None and len(l) == 4:
            gsm_location = {'cellid': l}
            try: # This needs some capability (ReadDeviceData?)
                gsm_location["signal_bars"] = sysinfo.signal_bars()
                gsm_location["signal_dbm"] = sysinfo.signal_dbm()
            except:
                gsm_location["signal_bars"] = None
                gsm_location["signal_dbm"] = None
            # Append gsm_location if current differs from the last saved...
            if len(self.data["gsm_location"]) > 0 and l != self.data["gsm_location"][-1]['gsm']['cellid']:
                pos["gsm"] = gsm_location
                pos["text"] = l[3]
                self.data["gsm_location"].append(pos)
            elif len(self.data["gsm_location"]) == 0: # ...or the history is empty: append the 1st record
                pos["gsm"] = gsm_location
                pos["text"] = l[3]
                self.data["gsm_location"].append(pos)
            # TODO: if the distance to the latest point exceeds 
            # some configurable limit (e.g. 1000 meters), then append a new point too
            
            # Remove the oldest records if the length exceeds limit
            # TODO: make limit configurable
            if len(self.data["gsm_location"]) > 200:
                self.data["gsm_location"].pop()
                self.data["gsm_location"].pop()

    def _calculate_UTM(self, pos):
        """
        Calculate UTM coordinates and append them to pos. 
        pos["position"]["latitude"] and pos["position"]["longitude"] must exist and be float.
        """
        try:
            (pos["position"]["z"], 
             pos["position"]["e"], 
             pos["position"]["n"]) = LatLongUTMconversion.LLtoUTM(23, # Wgs84
                                                                  pos["position"]["latitude"],
                                                                  pos["position"]["longitude"])
            return True
        except:
            # TODO: line number and exception text here too?
            self.log(u"exception", u"Failed to LLtoUTM()")
            return False
    
    def read_position(self, pos):
        """
        positioning.position() callback.
        Save the latest position object to the self.pos.
        Keep latest n position objects in the data["position"] list.
        TODO: Save the track data (to a file) automatically for future use.
        """
        if self.track_debug:
            self.data["position_debug"].append(pos)
            if len(self.data["position_debug"]) > self.config["max_debugpoints"]:
                self.data["position_debug"].pop(0)
            # TODO:
            # self.data["position_debug"].append(pos)
        pos["systime"] = time.time()
        if str(pos["position"]["latitude"]) != "NaN":
            self._calculate_UTM(pos)
            # Calculate distance between the current pos and the latest history pos
            dist = 0
            dist_estimate = 0
            if len(self.data["position"]) > 0:
                p0 = self.data["position"][-1] # use the latest saved point in history
                # Distance between current and the latest saved position
                dist = Calculate.distance(p0["position"]["latitude"],
                                          p0["position"]["longitude"],
                                          pos["position"]["latitude"],
                                          pos["position"]["longitude"],
                                         )
                # Project a location estimation point using speed and heading from the latest saved point
                p = {}
                timediff = time.time() - p0['systime']
                dist_project = p0['course']['speed'] * timediff # speed * seconds = distance in meters
                lat, lon = Calculate.newlatlon(p0["position"]["latitude"], p0["position"]["longitude"], 
                                               dist_project, p0['course']['heading'])
                p["position"] = {}
                p["position"]["latitude"] = lat
                p["position"]["longitude"] = lon
                self.Main._calculate_UTM(p)
                #(z, p["position"]["e"], p["position"]["n"]) = LatLongUTMconversion.LLtoUTM(23, p["position"]["latitude"],
                #                                                                               p["position"]["longitude"])
                self.pos_estimate = p
                # This calculates the distance between current point and estimation.
                # Perhaps ellips could be more optime?
                dist_estimate = Calculate.distance(p["position"]["latitude"],
                                          p["position"]["longitude"],
                                          pos["position"]["latitude"],
                                          pos["position"]["longitude"],
                                         )
            else: # Always append the first point with fix
                self.data["position"].append(pos)
            # If the dinstance exceeds the treshold, save the position object to the history list
            if dist > self.min_trackpoint_distance or dist_estimate > self.config["estimated_error_radius"]:
                self.data["position"].append(pos)
            
        # If data["position"] is too big remove some of the oldest points
        if len(self.data["position"]) > self.config["max_trackpoints"]:
            self.data["position"].pop(0)
            self.data["position"].pop(0) # pop twice to reduce the number of points
        self.pos = pos
        # Read gsm-cell changes
        self.read_gsm_location()

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
        self.running = False
        appuifw.app.exit_key_handler = None
        appuifw.app.set_tabs([u"Back to normal"], lambda x: None)

################### BASE VIEW START #######################

# TODO: move these to separate file
class BaseView:
    """
    Base class for all tabbed views
    """

    def __init__(self, parent):
        """
        __init__ must be defined in derived class.
        """
        raise "__init__() method has not been defined!"
        self.name = "BaseView"
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
class SysinfoView(BaseView):
    def __init__(self, parent):
        self.name = "SysinfoView"
        self.parent = parent
        self.Main = parent.Main
        self.init_ram = sysinfo.free_ram()
        self.tabs = []
        self.tabs.append((u"Gsm", GsmTab(self)))
        self.tabs.append((u"SysInfo", SysInfoTab(self)))
        self.tabs.append((u"E32", E32InfoTab(self)))
        self.tabs.append((u"Mem", MemTab(self)))
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
        lines.append(u"Battery: %s" % sysinfo.battery())
        lines.append(u"Signal bars: %d" % sysinfo.signal_bars())
        lines.append(u"Signal DBM: %.1f" % sysinfo.signal_dbm())
        lines.append(u"Profile: %s" % sysinfo.active_profile())
        lines.append(u"Twips: %d x %d" % sysinfo.display_twips())
        lines.append(u"Pixels: %d x %d" % sysinfo.display_pixels())
        lines.append(u"IMEI: %s" % sysinfo.imei())
        lines.append(u"Os version: %d.%d.%d" % sysinfo.os_version())
        lines.append(u"Sw version: %s" % sysinfo.sw_version())
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
############## Sysinfo VIEW END ###############

############## GPS VIEW START ##############
class GpsView(BaseView):
    def __init__(self, parent):
        self.name = "GpsView"
        self.parent = parent
        self.Main = parent.Main
        self.tabs = []
        self.tabs.append((u"Gps", GpsInfoTab(self)))
        self.tabs.append((u"Speed", GpsSpeedTab(self)))
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

class GpsInfoTab(BaseInfoTab):

    def update(self, dummy=(0, 0, 0, 0)):
        self.t.cancel()
        lines = self._get_lines()
        self.canvas.clear()
        if self.Main.pos and time.time() - self.Main.pos["systime"] < 3:
            textcolor = 0x000000
        else: # use gray font color if position is too old (3 sec)
            textcolor = 0xb0b0b0
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
            lines.append(u"GPS-Time: %s" % time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(s["time"] - time.altzone)))
        lines.append(u"Sys-Time: %s" % time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time())))
        lines.append(u"Satellites: %s/%s" % (s["used_satellites"],s["satellites"]))
        lines.append(u"DOP (H/V/T) %.1f/%.1f/%.1f" % (s["horizontal_dop"],s["vertical_dop"],s["time_dop"]))
        return lines

class TrackView(BaseView):
    def __init__(self, parent):
        self.name = "GpsView"
        self.parent = parent
        self.Main = parent.Main
        self.tabs = []
#        self.tabs.append((u"Gps", GpsInfoTab(self)))
        self.tabs.append((u"Track", GpsTrackTab(self)))
#        self.tabs.append((u"Speed", GpsSpeedTab(self)))
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
    TODO: flickering exists if there is over 40 trackpoints to draw. 
    TODO: Use Image and blit to avoid flickering.
    """
    meters_per_px = 5
    #pois = []
    # Are zoom_levels below 1.0 needeed?
    zoom_levels = [1,2,3,5,8,12,16,20,30,50,80,100,150,250,400,600,1000,2000,5000,10000]
    zoom_index = 3

    def activate(self):
        self.active = True
        appuifw.app.exit_key_handler = self.handle_close
        self.canvas = appuifw.Canvas(redraw_callback=self.update)
        self.ui = graphics.Image.new(self.canvas.size)
        appuifw.app.body = self.canvas
        appuifw.app.screen = "normal"
        appuifw.app.menu = [(u"Update", self.update),
                            (u"Close", self.handle_close),
                            ]
        self.canvas.bind(key_codes.EKeyHash, lambda: self.change_meters_per_px(1))
        self.canvas.bind(key_codes.EKeyStar, lambda: self.change_meters_per_px(-1))
        self.canvas.bind(key_codes.EKeySelect, self.save_poi)
        appuifw.app.menu.insert(0, (u"Send track via bluetooth", self.send_track))
        appuifw.app.menu.insert(0, (u"Send cellids via bluetooth", self.send_cellids))
        appuifw.app.menu.insert(0, (u"Send debug track via bluetooth", self.send_debug))
        appuifw.app.menu.insert(0, (u"Set meters/pixel", 
                                    lambda:self.set_meters_per_px(appuifw.query(u"Meters","number", self.meters_per_px))))
        appuifw.app.menu.insert(0, (u"Add POI", self.save_poi))
        appuifw.app.menu.insert(0, (u"POIs Download", self.Main.download_pois))
        self.update()

    def set_meters_per_px(self, px):
        """
        Set the scale of the track. Minimum is 1.
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
            trkpts.append(self._make_xml_cellpt(gsm[0], gsm[0]))
        for i in range(1,lengsm): # Save points 1..last
            trkpts.append(self._make_xml_cellpt(gsm[i-1], gsm[i]))
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

    def _make_xml_cellpt(self, p, p2):
        """Temporary function to help to make cellpoints"""
        att = {}
        att["lat"] = u"%.6f" % (p["position"]["latitude"])
        att["lon"] = u"%.6f" % (p["position"]["longitude"])
        att["alt"] = u"%.1f" % (p["position"]["altitude"])
        att["time"] = time.strftime(u"%Y-%m-%dT%H:%M:%SZ", time.localtime(p["satellites"]["time"]))
        att["cellfrom"] = u"%s,%s,%s,%s" % (p["gsm"]["cellid"])
        att["cellto"] = u"%s,%s,%s,%s" % (p2["gsm"]["cellid"])
        att["signalfrom"] = u"%.1f" % (p["gsm"]["signal_dbm"])
        att["signalto"] = u"%.1f" % (p2["gsm"]["signal_dbm"])
        att["speed_kmh"] = u"%.2f" % (p["course"]["speed"] * 3.6)
        att["heading"] = u"%.2f" % (p["course"]["heading"])
        att["dop"] = u"%.2f;%.2f;0" % (p["satellites"]["horizontal_dop"], p["satellites"]["vertical_dop"])
        cellpt = "<cellpt " + " ".join([ '%s="%s"' % (k, att[k]) for k in att.keys() ]) + "></cellpt>"
        return cellpt
        # return """<cellpt lat="%(lat)s" lon="%(lon)s" alt="%(alt)s" speed_kmph="%(speed_kmh)s" heading="%(heading)s" time="%(time)s" cellfrom="%(cellfrom)s" cellto="%(cellto)s  signalfrom="%(signalfrom)s" signalto="%(signalto)s" dop="%(dop)s"></cellpt>""" % att

    def send_debug(self):
        """
        Send saved position data to the other bluetooth device.
        """
        # jsonize only one pos per time, otherwise out of memory or takes very long time
        points = []
        for p in self.Main.data["position_debug"]:
            points.append(json.write(p))
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
        ts = unicode(time.strftime(u"%H:%M:%S ", time.localtime(pos["satellites"]["time"] - time.altzone)))
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
        #if not p.has_key("position") or not p["position"].has_key("e"): return
        #if not p0.has_key("position") or p0["position"].has_key("e"): return
        if not p.has_key("position") or not p["position"].has_key("e"): return
        if not p0.has_key("position") or not p0["position"].has_key("e"): return
        p["x"] = int((-p0["position"]["e"] + p["position"]["e"]) / meters_per_px)
        p["y"] = int((p0["position"]["n"] - p["position"]["n"]) / meters_per_px)

    def update(self, dummy=(0, 0, 0, 0)):
        """
        Draw all elements (texts, points, track, pois etc) to the canvas.
        Start a timer to launch new update after a while.
        """
        self.t.cancel()
        poi_r = 5 # POI circles radius
        ch_l = 10 # Crosshair length
        # TODO: determine center from canvas width/height
        center_x = 120
        center_y = 120
        # TODO: cleanup here!
        # TODO: do separate functions for these instead
        #lines, track, pois = self._get_lines()
        self.ui.clear()
        # Print some information about track
        mdist = self.Main.min_trackpoint_distance
        helpfont = (u"Series 60 Sans", 12)
        # Draw crosshair
        # TODO: draw arrow
        self.ui.line([center_x-ch_l, center_y, center_x+ch_l, center_y], outline=0x0000ff, width=1)
        self.ui.line([center_x, center_y-ch_l, center_x, center_y+ch_l], outline=0x0000ff, width=1)
        # Test polygon
        # self.ui.polygon([15,15,100,100,100,15,50,10], outline=0x0000ff, width=4)
        j = 0
        #print len(self.Main.data["position_debug"])
        #if len(track) > 0:
        #    p0 = track[0]
        p0 = self.Main.pos # the center point
        # New style: use main apps data structures directly and _calculate_canvas_xy() to get pixel xy.
        # TODO: to a function
        for i in range(len(self.Main.data["position_debug"])-1, -1, -1):
            j = j + 1
            if j > 20: break # draw only last x debug points
            p = self.Main.data["position_debug"][i]
            self._calculate_canvas_xy(self.ui, self.meters_per_px, p0, p)
            try:
                self.ui.point([p["x"]+center_x, p["y"]+center_y], outline=0xffff00, width=7)
            except: 
                pass
            
        # Draw track if it exists
        # TODO: to a function
        track = self.Main.data["position"]
        if len(self.Main.data["position"]) > 0:
            p1 = self.Main.data["position"][-1]
        for i in range(len(self.Main.data["position"])-1, -1, -1): # draw trackpoints backwards
            p = self.Main.data["position"][i]
            self._calculate_canvas_xy(self.ui, self.meters_per_px, p0, p)
            # TODO: check that x and y exist
            self.ui.point([p["x"]+center_x, p["y"]+center_y], outline=0xff0000, width=5)
            self.ui.line([p["x"]+center_x, p["y"]+center_y, 
                          p1["x"]+center_x, p1["y"]+center_y], outline=0x00ff00, width=2)
            p1 = p
        # Draw POIs if there are any
        # TODO: to a function
        for p in self.Main.data["pois_private"]:
            self._calculate_canvas_xy(self.ui, self.meters_per_px, p0, p)
            if p.has_key("x"):
                self.ui.point([p["x"]+center_x, p["y"]+center_y], outline=0x0000ff, width=5)
                self.ui.ellipse([(p["x"]+center_x-poi_r,p["y"]+center_y-poi_r),
                                 (p["x"]+center_x+poi_r,p["y"]+center_y+poi_r)], outline=0x0000ff)
                # There is a bug in image.text (fixed in 1.4.4?), so text must be drawn straight to the canvas
                # self.ui.text(([t["x"]+130, t["y"]+125]), u"%s" % t["text"], font=(u"Series 60 Sans", 10), fill=0x000000)
        for p in self.Main.data["pois_downloaded"]:
            self._calculate_canvas_xy(self.ui, self.meters_per_px, p0, p)
            if p.has_key("x"):
                self.ui.point([p["x"]+center_x, p["y"]+center_y], outline=0xff00ff, width=5)
                self.ui.ellipse([(p["x"]+center_x-poi_r,p["y"]+center_y-poi_r),
                                 (p["x"]+center_x+poi_r,p["y"]+center_y+poi_r)], outline=0x0000ff)
        for p in self.Main.data["gsm_location"]:
            self._calculate_canvas_xy(self.ui, self.meters_per_px, p0, p)
            if p.has_key("x"):
                self.ui.point([p["x"]+center_x, p["y"]+center_y], outline=0x0000ff, width=5)
                self.ui.ellipse([(p["x"]+center_x-poi_r,p["y"]+center_y-poi_r),
                                 (p["x"]+center_x+poi_r,p["y"]+center_y+poi_r)], outline=0x0000ff)
        ##############################################        
        # Testing the point estimation 
        # TODO: to a function
        if len(self.Main.data["position"]) > 0: 
            pc = self.Main.pos
            p0 = self.Main.data["position"][-1] # use the latest saved point in history
            p = self.Main.pos_estimate
            err_radius = self.Main.config["estimated_error_radius"] # meters
            ell_r = err_radius / self.meters_per_px 
            self._calculate_canvas_xy(self.ui, self.meters_per_px, self.Main.pos, p)
            if p.has_key("x"):
                self.ui.ellipse([(p["x"]+center_x-ell_r,p["y"]+center_y-ell_r),
                                 (p["x"]+center_x+ell_r,p["y"]+center_y+ell_r)], outline=0x9999ff)
            # Draw accurancy circle
            acc_radius = pc["position"]["horizontal_accuracy"]
            if acc_radius > 0:
                acc_r = acc_radius / self.meters_per_px 
                self.ui.ellipse([(center_x-acc_r,center_y-acc_r),
                                     (center_x+acc_r,center_y+acc_r)], outline=0xccffcc)
            # see kludge part below:
            #self.ui.text(([10, 220]), u"%.1f km/h %.1f°" % (pc['course']['speed']*3.6, pc['course']['heading']), 
            #                          font=(u"Series 60 Sans", 20), fill=0x000000)
        ###########################################
        # Draw scale bar
        # see kludge part below
        # self.draw_scalebar(self.ui)

        # KLUDGE: image.text() workarounds, remove when the bug is fixed! (1.4.4?)
        self.canvas.blit(self.ui)
        self.canvas.text((2,15), u"%d m between points" % mdist, font=helpfont, fill=0x999999)
        self.canvas.text((2,27), u"%d/%d points in history" % 
             (len(self.Main.data["position"]), self.Main.max_trackpoints), font=helpfont, fill=0x999999)
        
        self.canvas.text((2,39), u"Press joystick to save a POI", font=helpfont, fill=0x999999)
        self.canvas.text((2,51), u"Press * or # to zoom", font=helpfont, fill=0x999999)
        self.canvas.text((2,63), u"Debug %s" % self.Main.track_debug, font=helpfont, fill=0x999999)
        for p in self.Main.data["pois_private"]: # TODO: Remove this when image.text is fixed
            if p.has_key("x"):
                self.canvas.text(([p["x"]+130, p["y"]+125]), u"%s" % p["text"], font=(u"Series 60 Sans", 10), fill=0x000066)
        for p in self.Main.data["pois_downloaded"]: # TODO: Remove this when image.text is fixed
            if p.has_key("x"):
                self.canvas.text(([p["x"]+130, p["y"]+125]), u"%s" % p["text"], font=(u"Series 60 Sans", 10), fill=0x666600)
        for p in self.Main.data["gsm_location"]: # TODO: Remove this when image.text is fixed
            if p.has_key("x"):
                self.canvas.text(([p["x"]+130, p["y"]+125]), u"%s" % p["text"], font=(u"Series 60 Sans", 10), fill=0x000066)
        scale_bar_width = 50 # pixels
        scale_bar_x = 150    # x location
        scale_bar_y = 20     # y location
        scale_value = scale_bar_width * self.meters_per_px
        if scale_value > 1000: 
            scale_text = u"%.1f km" % (scale_value / 1000.0)
        else:
            scale_text = u"%d m" % (scale_value)
        self.canvas.text((scale_bar_x + 5, 18), scale_text, font=(u"Series 60 Sans", 10), fill=0x333333)
        self.canvas.text((scale_bar_x + 5, 32), u"%d m/px" % self.meters_per_px, font=(u"Series 60 Sans", 10), fill=0x333333)
        self.canvas.line([scale_bar_x, 20, scale_bar_x + scale_bar_width, 20], outline=0x0000ff, width=1)
        self.canvas.line([scale_bar_x, 15, scale_bar_x, 25], outline=0x0000ff, width=1)
        self.canvas.line([scale_bar_x + scale_bar_width, 15, scale_bar_x + scale_bar_width, 25], outline=0x0000ff, width=1)
        if len(self.Main.data["position"]) > 0: 
            self.canvas.text(([10, 220]), u"%.1f km/h %.1f°" % (pc['course']['speed']*3.6, pc['course']['heading']), 
                                      font=(u"Series 60 Sans", 20), fill=0x000000)
        # KLUDGE part ends
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
        canvas.text((scale_bar_x + 5, 18), scale_text, font=(u"Series 60 Sans", 10), fill=0x333333)
        canvas.text((scale_bar_x + 5, 32), u"%d m/px" % self.meters_per_px, font=(u"Series 60 Sans", 10), fill=0x333333)
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

# TODO: add exception harness for test versions
oldbody = appuifw.app.body
myApp = GpsApp()
myApp.run()
positioning.stop_position()
appuifw.app.body = oldbody
# For SIS-packaged version uncomment this:
# appuifw.app.set_exit()
