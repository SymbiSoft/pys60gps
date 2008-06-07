# -*- coding: iso-8859-15 -*-
# $Id: gui_test.py 712 2008-06-02 20:33:54Z arista $

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

class GuiApp:
    __version__ = u'$Id: gui_test.py 712 2008-06-02 20:33:54Z arista $'

    def __init__(self):
        self.lock = e32.Ao_lock()
        appuifw.app.exit_key_handler = self.exit_key_handler
        self.running = True
        self.focus = True
        appuifw.app.focus = self.focus_callback # Set up focus callback
        self.read_position_running = False
        # Data-repository
        self.data = {}
        # GSM-cellid
        self.gsm_location = {}
        #self.gsm_location_history = []
        self.data["gsm_location"] = []
        # GPS-position
        self.pos = {} # TODO: rename to gps_position
        self.pos_history = [] # TODO: rename to gps_position_history
        self.pos_history_debug = []
        self.data["position"] = []
        self.data["position_debug"] = []
        # temporary solution to handle speed data (to be removed/changed)
        self.speed_history = []
        self.max_speed_history_points = 100
        self.min_trackpoint_distance = 100 # meters
        self.max_trackpoints = 200
        self.track_debug = False
        # Put all menu entries and views as tuples into a sequence
        self.menu_entries = []
        self.menu_entries.append(((u"GPS"), GpsView(self)))
        self.menu_entries.append(((u"Sysinfo"), SysinfoView(self)))
        self.menu_entries.append(((u"List View"), ListView(self)))
        self.menu_entries.append(((u"Text View"), TextView(self)))
        # Create main menu from that sequence
        self.main_menu = [item[0] for item in self.menu_entries]
        # Create list of views from that sequence
        self.views = [item[1] for item in self.menu_entries]
        # Create a listbox from main_menu and set select-handler
        self.listbox = appuifw.Listbox(self.main_menu, self.handle_select)
        self.activate()

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
            (u"GPS",self.start_read_position),
            (u"Max trackpoints (%d)" % self.max_trackpoints, 
                  lambda:self.set_max_trackpoints(appuifw.query(u"Max points","number", self.max_trackpoints))),
            (u"Set trackpoint dist (%d)" % self.min_trackpoint_distance, 
                  lambda:self.set_trackpoint_distance(appuifw.query(u"Trackpoint dist","number", self.min_trackpoint_distance))),
            set_trackpoint_distance_menu,
            (u"Toggle debug",self.toggle_debug),
            (u"Reboot",self.reboot),
            (u"Version", lambda:appuifw.note(self.__version__, 'info')),
            (u"Close", self.lock.signal),
            ]
        appuifw.app.screen = 'normal'

    def focus_callback(self, bg):
        """Callback for """
        self.focus = bg

    def set_trackpoint_distance(self, distance):
        if distance is not None:
            self.min_trackpoint_distance = distance

    def set_max_trackpoints(self, max):
        if max and max > 0:
            self.max_trackpoints = max

    def toggle_debug(self):
        self.track_debug = not self.track_debug # Toggle true <-> false

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
        pos = self.pos # TODO: take this from self.data["position"][-1]
        l = location.gsm_location()
        if e32.in_emulator(): # Do some random cell changes if in emulator
            import random
            if random.random() < 0.05:
                l = ('244','123','29000',random.randint(1,2**24))
        # NOTE: gsm_location() may return None in certain circumstances
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
                self.data["gsm_location"].append(pos)
            elif len(self.data["gsm_location"]) == 0: # ...or the history is empty: append the 1st record
                pos["gsm"] = gsm_location
                self.data["gsm_location"].append(pos)
            # TODO: if the distance to the latest point exceeds 
            # some configurable limit (e.g. 1000 meters), then append a new point too
            
            # Remove the oldest records if the length exceeds limit
            # TODO: make limit configurable
            if len(self.data["gsm_location"]) > 100:
                self.data["gsm_location"].pop()
                self.data["gsm_location"].pop()

    def read_position(self, pos):
        """
        Save the latest position object to the self.pos.
        Keep latest n position objects in the pos_history list.
        TODO: Save the track data (to a file) for future use.
        """
        if self.track_debug:
            self.pos_history_debug.append(pos)
            # TODO:
            # self.data["position_debug"].append(pos)
        pos["systime"] = time.time()
        if str(pos["position"]["latitude"]) != "NaN":
            # Calculate UTM coordinates for future use
            (z, pos["position"]["e"], pos["position"]["n"]) = LatLongUTMconversion.LLtoUTM(23, pos["position"]["latitude"],
                                                                                               pos["position"]["longitude"])
            # print pos["position"]["e"], pos["position"]["n"]
            # Calculate distance between the current pos and the latest history pos
            if len(self.pos_history) > 0:
                dist = Calculate.distance(self.pos_history[-1]["position"]["latitude"],
                                          self.pos_history[-1]["position"]["longitude"],
                                          pos["position"]["latitude"],
                                          pos["position"]["longitude"],
                                         )
            else:
                self.pos_history.append(pos)
                dist = 0
            # If the dinstance exceeds the treshold, save the position object to the history list
            # TODO: Use Calculate.estimatediff() or something similar to conclude 
            # TODO: if there is a need to save new history point.
            if dist > self.min_trackpoint_distance:
                self.pos_history.append(pos)
        # Read gsm-cell changes
        self.read_gsm_location()
        # If pos_history is too big remove some of the oldest points
        if len(self.pos_history) > self.max_trackpoints:
            self.pos_history.pop(0)
            self.pos_history.pop(0) # pop twice to reduce the number of points
        self.pos = pos
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
        if len(self.speed_history) >= self.max_speed_history_points:
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
class BaseView:
    """
    Base class for all tabbed views
    """

    def __init__(self, PrevView):
        """
        __init__ must be defined in derived class.
        """
        raise "__init__() method has not been defined!"
        self.name = "BaseView"
        self.PrevView = PrevView
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
        self.PrevView.activate()
################### BASE VIEW END #########################

############## List TAB START ##############
class BaseInfoTab:
    def __init__(self, PrevView, **kwargs):
        self.t = e32.Ao_timer()
        self.PrevView = PrevView
        self.active = False
        self.fontheight = 15
        self.lineheight = 17
        self.font = (u"Series 60 Sans", self.fontheight)
        #self.init_ram

    def _get_lines(self):
        raise "_get_lines() must be implemented"

    def activate(self):
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
        pass

    def update(self, dummy=(0, 0, 0, 0)):
        self.t.cancel()
        lines = self._get_lines()
        self.canvas.clear()
        self.blit_lines(lines)
        self.t = e32.Ao_timer()
        if self.active:
            self.t.after(0.5, self.update)
        else:
            self.t.cancel()

    def blit_lines(self, lines, color=0x000000):
        self.canvas.clear()
        start = 0
        for l in lines:
            start = start + self.lineheight
            self.canvas.text((3,start), l, font=self.font, fill=color)

    def handle_close(self):
        self.active = False
        self.t.cancel()
        self.PrevView.close()

############## Sysinfo VIEW START ##############
class SysinfoView(BaseView):
    def __init__(self, PrevView):
        self.name = "SysinfoView"
        self.PrevView = PrevView
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
        self.PrevView.activate()

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
        lines.append(u"Init RAM: %d kB" % (self.PrevView.init_ram/1024))
        lines.append(u"Free RAM: %d kB" % (sysinfo.free_ram()/1024))
        lines.append(u"Total RAM: %d kB" % (sysinfo.total_ram()/1024))
        return lines

class GsmTab(BaseInfoTab):
    """Show a few last gsm-cellid's."""
    def _get_lines(self):
        lines = [u"GSM-cells: %d lines" % len(self.PrevView.PrevView.data["gsm_location"])]
        last = self.PrevView.PrevView.data["gsm_location"][-13:]
        last.reverse()
        for l in last:
            lines.append(u"%s" % time.strftime("%H:%M:%S ", time.localtime(l["systime"]))
                       + u"%s,%s,%s,%s" % (l['gsm']["cellid"]))
        return lines
############## Sysinfo VIEW END ###############

############## GPS VIEW START ##############
class GpsView(BaseView):
    def __init__(self, PrevView):
        self.name = "GpsView"
        self.PrevView = PrevView
        self.tabs = []
        self.tabs.append((u"Gps", GpsInfoTab(self)))
        self.tabs.append((u"Track", GpsTrackTab(self)))
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
        self.PrevView.activate()

class GpsInfoTab(BaseInfoTab):

    def _get_lines(self):
        lines = []
        pos = self.PrevView.PrevView.pos
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

class GpsTrackTab(BaseInfoTab):
    """
    Print the track on the canvas.
    TODO: flickering exists if there is over 40 trackpoints to draw. 
    TODO: Use Image and blit to avoid flickering.
    """
    meters_per_px = 5
    pois = []
    zoom_levels = [1,2,3,5,8,12,16,20,30,50,80,100,150,250,400,600,1000,2000,5000,10000]
    zoom_index = 3
            
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
    
    def activate_extra(self):
        """
        Add extra menu item to the menu, bind key pressings etc.
        See class BaseInfoTab.
        """
        self.canvas.bind(key_codes.EKeyHash, lambda: self.change_meters_per_px(1))
        self.canvas.bind(key_codes.EKeyStar, lambda: self.change_meters_per_px(-1))
        self.canvas.bind(key_codes.EKeySelect, self.save_poi)
        appuifw.app.menu.insert(0, (u"Send track via bluetooth", self.send_track))
        appuifw.app.menu.insert(0, (u"Send debug track via bluetooth", self.send_debug))
        appuifw.app.menu.insert(0, (u"Set meters/pixel", 
                                    lambda:self.set_meters_per_px(appuifw.query(u"Meters","number", self.meters_per_px))))
        appuifw.app.menu.insert(0, (u"Add POI", self.save_poi))

    def send_track(self):
        # TODO: create also function to send via HTTP
        """
        Send saved track to the other bluetooth device.
        """
        wpts = []
        trkpts = []
        for p in self.pois:
            wpts.append(self._make_gpx_trkpt(p, "wpt"))
        for p in self.PrevView.PrevView.pos_history:
            trkpts.append(self._make_gpx_trkpt(p))
        if p:
            last_time = time.strftime(u"%Y%m%dT%H%M%SZ", time.localtime(p["satellites"]["time"]))
            # TODO: use directory "c:\\data\\Pys60Gps" instead
            filename = u"c:\\data\\trackpoints-%s.gpx" % last_time
            last_isotime = time.strftime(u"%Y-%m-%dT%H:%M:%SZ", time.localtime(p["satellites"]["time"]))
        else:
            filename = u"c:\\data\\trackpoints-notime.gpx"
        f = open(filename, "wt")
        data = """<?xml version='1.0'?><gpx creator="Pys60Gps" version="0.1" xmlns="http://www.topografix.com/GPX/1/1" xmlns:gpslog="http://FIXME.FI" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="FIXME FIXME FIXME http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd"><metadata> <time>%s</time></metadata>%s
<trk><trkseg>%s
</trkseg></trk></gpx>
""" % (last_isotime, 
       u"\n".join(wpts).encode('utf-8'),
       u"\n".join(trkpts).encode('utf-8'))
        f.write(data)
        f.close()
        if e32.in_emulator():
            return # Emulator crashes after this
        try:
            bt_addr,services = socket.bt_obex_discover()
            service = services.values()[0]
            # Upload the track file
            socket.bt_obex_send_file(bt_addr, service, filename)
            appuifw.note(u'Trackfile sent')
        except Exception, error:
            print error
            appuifw.note(unicode(error), 'error')

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

    def send_debug(self):
        """
        Send saved position data to the other bluetooth device.
        """
        import json
        # TODO: jsonize only one pos per time, otherwise out of memory
        data = json.write(self.PrevView.PrevView.pos_history_debug)
        name = appuifw.query(u"Name", "text", u"")
        if name is None:
            name = u"latest" # TODO: strftimestamp here
        filename = u"c:\\data\\pos-%s.json" % name
        f = open(filename, "wt")
        f.write(data)
        f.close()
        if e32.in_emulator():
            return # Emulator crashes after this
        try:
            bt_addr,services = socket.bt_obex_discover()
            service = services.values()[0]
            # Upload the track file
            socket.bt_obex_send_file(bt_addr, service, filename)
            appuifw.note(u'Debug sent')
        except Exception, error:
            print error
            appuifw.note(unicode(error), 'error')

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



    def save_poi(self):
        """
        Saves a point to the "pois" list.
        """
        if not self.PrevView.PrevView.pos: # empty position, no gps connected yet
            appuifw.note(u"No GPS", 'error')
            return
        
        pos = self.PrevView.PrevView.pos
        # Default name is gps timestamp (UTC) with timezone info (time.altzone)
        ts = unicode(time.strftime(u"%H:%M:%S ", time.localtime(pos["satellites"]["time"] - time.altzone)))
        # print pos
        pos["text"] = appuifw.query(u"Name", "text", ts)
        if pos["text"] is not None: # user did not press Cancel
            self.pois.append(pos)
        else:  # user pressed cancel -> no POI
            pass
            #pos["text"] = u"" # empty text
        
    def calc_xy(self, **kwargs):
        """
        Calculates the xy-position of all points on the canvas.
        """
        p0 = kwargs["center"]
        # KLUDGE: p0 doesn't have "e" if there is no fix, use latest history point instead
        if not p0["position"].has_key("e"):
            p0 = kwargs["track"][-1]
        lines = []
        track = []
        #track.append(p0)
        pois = []

        p0["x"] = int(kwargs["canvas_size"][0]/2)
        p0["y"] = int(kwargs["canvas_size"][1]/2)
        for p in kwargs["track"]: # TODO: make a function for this
            # FIXME: this crashes if there is no fix
            x = int((-p0["position"]["e"] + p["position"]["e"]) / kwargs["meters_per_px"])
            y = int((p0["position"]["n"] - p["position"]["n"]) / kwargs["meters_per_px"])
            # TODO: Update current p instead creating new one
            p1 = {"e":p["position"]["e"], "n":p["position"]["n"], 'x':x, 'y':y}
            p["x"] = x
            p["y"] = y
            track.append(p1)
            lines.append(u"%d %d %d %d" % (p["position"]["n"], p["position"]["e"], x, y))
        for p in kwargs["pois"]: # TODO: make a function for this
            x = int((-p0["position"]["e"] + p["position"]["e"]) / kwargs["meters_per_px"])
            y = int((p0["position"]["n"] - p["position"]["n"]) / kwargs["meters_per_px"])
            # TODO: Update current p instead creating new one
            p["x"] = x
            p["y"] = y
            p1 = {"e":p["position"]["e"], "n":p["position"]["n"], 'x':x, 'y':y, "text":p["text"]}
            pois.append(p1)
        return lines, track, pois

    # TODO finish this
    def _update_canvas_xy(self, meters_per_px, centerpoint, pointlist):
        p0 = centerpoint
        for p in pointlist:
            x = int((-p0["position"]["e"] + p["position"]["e"]) / meters_per_px)
            y = int((p0["position"]["n"] - p["position"]["n"]) / meters_per_px)
            p["x"] = x
            p["y"] = y
            p1 = {"e":p["position"]["e"], "n":p["position"]["n"], 'x':x, 'y':y, "text":p["text"]}

    def update(self, dummy=(0, 0, 0, 0)):
        """
        Draw all elements (texts, points, track, pois etc) to the canvas.
        Start a timer to launch new update after a while.
        """
        poi_r = 5 # POI circles radius
        ch_l = 10 # Crosshair length
        # TODO: determine center from canvas width/height
        center_x = 120
        center_y = 120
        self.t.cancel()
        lines, track, pois = self._get_lines()
        #lines = lines[-10:] # pick only last lines
        #lines.reverse() 
        self.canvas.clear()
        #self.blit_lines(lines, 0xcccccc) # debugging, contains UTM and canvas XY coordinates
        # Print some information about track
        # Ugh, this self.PrevView.PrevView. -notation is very ugly
        mdist = self.PrevView.PrevView.min_trackpoint_distance
        helpfont = (u"Series 60 Sans", 12)
        self.canvas.text((2,15), u"%d m between points" % mdist, font=helpfont, fill=0x999999)
        self.canvas.text((2,27), u"%d/%d points in history" % 
             (len(self.PrevView.PrevView.pos_history), self.PrevView.PrevView.max_trackpoints), font=helpfont, fill=0x999999)
        
        self.canvas.text((2,39), u"Press joystick to save a POI", font=helpfont, fill=0x999999)
        self.canvas.text((2,51), u"Press * or # to zoom", font=helpfont, fill=0x999999)
        self.canvas.text((2,63), u"Debug %s" % self.PrevView.PrevView.track_debug, font=helpfont, fill=0x999999)
        # Draw scale bar
        self.draw_scalebar(self.canvas)
        # Draw crosshair
        self.canvas.line([center_x-ch_l, center_y, center_x+ch_l, center_y], outline=0x0000ff, width=1)
        self.canvas.line([center_x, center_y-ch_l, center_x, center_y+ch_l], outline=0x0000ff, width=1)
        # Draw track if it exists
        if len(track) > 0:
            p = track[0]
        for t in track:
            self.canvas.point([t["x"]+center_x, t["y"]+center_y], outline=0xff0000, width=5)
            self.canvas.line([t["x"]+center_x, t["y"]+center_y, 
                              p["x"]+center_x, p["y"]+center_y], outline=0x00ff00, width=2)
            p = t
        # Draw POIs if there are any
        for t in pois:
            try:
                self.canvas.point([t["x"]+center_x, t["y"]+center_y], outline=0x0000ff, width=5)
                self.canvas.ellipse([(t["x"]+center_x-poi_r,t["y"]+center_y-poi_r),
                                     (t["x"]+center_x+poi_r,t["y"]+center_y+poi_r)], outline=0x0000ff)
                self.canvas.text(([t["x"]+130, t["y"]+125]), 
                                   u"%s" % t["text"], font=(u"Series 60 Sans", 10), fill=0x000000)
            except:
                print t
                raise
        self.t = e32.Ao_timer()
        if self.active and self.PrevView.PrevView.focus:
            self.t.after(0.5, self.update)
        else:
            self.t.cancel()

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
        self.canvas.text((scale_bar_x + 5, 18), scale_text, font=(u"Series 60 Sans", 10), fill=0x333333)
        self.canvas.text((scale_bar_x + 5, 32), u"%d m/px" % self.meters_per_px, font=(u"Series 60 Sans", 10), fill=0x333333)
        self.canvas.line([scale_bar_x, 20, scale_bar_x + scale_bar_width, 20], outline=0x0000ff, width=1)
        self.canvas.line([scale_bar_x, 15, scale_bar_x, 25], outline=0x0000ff, width=1)
        self.canvas.line([scale_bar_x + scale_bar_width, 15, scale_bar_x + scale_bar_width, 25], outline=0x0000ff, width=1)
        
    def _get_lines(self):
        lines = []
        track = []
        pois = [] # Points Of Interests
        # TODO: Check this
        try:
            points = self.PrevView.PrevView.pos_history # This self.PrevView.PrevView notation is ugly
        except:
            lines.append(u"GPS-data not available")
            lines.append(u"Use main screens GPS-menu")
            return lines, track, []# pois
            
        lines.append(u"Track length: %d" % len(track))
        if len(points) > 0:
            lines, track, pois = self.calc_xy(canvas_size=(240,240),
                             meters_per_px=self.meters_per_px,
                             center=(self.PrevView.PrevView.pos), # Latest point to the center of canvas
                             track=self.PrevView.PrevView.pos_history,
                             pois=self.pois
                            )
        lines.append(u"Track length: %d" % len(track))
        return lines, track, pois

class GpsSpeedTab(BaseInfoTab):
    def update(self, dummy=(0, 0, 0, 0)):
        """
        Print current speed with BIG font.
        Print some kind of speed history.
        TODO: This really needs some cleanup.
        """
        self.canvas.clear()
        if self.PrevView.PrevView.pos:
            pos = self.PrevView.PrevView.pos
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
        for p in self.PrevView.PrevView.speed_history:
            speed_min = speed_0 - p["speedmin"] * 3.6
            speed_max = speed_0 - 1 - p["speedmax"] * 3.6 # at least 1 px height
            self.canvas.line([i, speed_min, i, speed_max], outline=0x0000ff, width=3)
            i = i + 2
        self.canvas.line([0, speed_0, 200, speed_0], outline=0x999999, width=1)
        self.canvas.text(([5, speed_0+5]), u"0 km/h", font=(u"Series 60 Sans", 10), fill=0x333333)
        self.canvas.line([0, speed_50, 200, speed_50], outline=0x999999, width=1)
        self.canvas.text(([5, speed_50+5]), u"50 km/h", font=(u"Series 60 Sans", 10), fill=0x333333)
        self.canvas.line([0, speed_100, 200, speed_100], outline=0x999999, width=1)
        self.canvas.text(([5, speed_100+5]), u"100 km/h", font=(u"Series 60 Sans", 10), fill=0x333333)
        #i = 0
        #for p in self.PrevView.PrevView.pos_history:
        #    speed_kmh = p["course"]["speed"] * 3.6
        #    self.canvas.point([i, int(speed_0-speed_kmh)], outline=0xff0000, width=2)
        #    i = i + 2

        self.t = e32.Ao_timer()
        if self.active:
            self.t.after(0.5, self.update)
        else:
            self.t.cancel()
        
    def _get_lines(self):
        lines = []
        track = []
        #pois = self.pois # [] # Points Of Interests
        # TODO: Check this
        try:
            points = self.PrevView.PrevView.pos_history # This self.PrevView.PrevView notation is ugly
        except:
            lines.append(u"GPS-data not available")
            lines.append(u"Use main screens GPS-menu")
            return lines, track, []# pois
            
        lines.append(u"Track length: %d" % len(track))
        if len(points) > 0:
            lines, track, pois = self.calc_xy(canvas_size=(240,240),
                             meters_per_px=self.meters_per_px,
                             center=(self.PrevView.PrevView.pos), # Latest point to the center of canvas
                             track=self.PrevView.PrevView.pos_history,
                             pois=self.pois
                            )
        lines.append(u"Track length: %d" % len(track))
        return lines, track, pois



############## List VIEW START ##############
class ListView(BaseView):
    def __init__(self, PrevView):
        self.name = "ListView"
        self.PrevView = PrevView
        self.tabs = []
        self.tabs.append((u"Single", SingleListTab(self)))
        self.tabs.append((u"Double", DoubleListTab(self)))
        self.current_tab = 0

class SingleListTab:
    def __init__(self, PrevView):
        self.PrevView = PrevView
        self.list = [(u"1st (the first)"),
                     (u"2nd (the second)"),
                     (u"3rd (the third)")]
        for i in range(4,10):
            self.list.append((u"%sst" % i))
        self.body = appuifw.Listbox(self.list, self.handle_select)
        #appuifw.popup_menu()
        self.menu = [(u"Multi selection list", self.multi_selection_list),
                     (u"Close", self.handle_close)]

    def activate(self):
        self.active = True
        appuifw.app.body = self.body
        appuifw.app.menu = self.menu
        appuifw.app.exit_key_handler = self.handle_close

    def handle_select(self):
        appuifw.note(u"Chosen: %s " % self.body.current(),'info')

    def multi_selection_list(self):
        L = [
            u"Antipasti misti",
            u"Insalata verde",
            u"Caprese",
            u"Insalata con caprino",
            u"Lumache al gorgonzola e aglio",
            u"Capesante al forno",
            u"Pesce spada affumicato con pomodorini",
            u"Crostino con gamberoni",
            u"Carpaccio con rucola e asiago",
            u"Crema di scorzanera",
            u"Risotto ai funghi porcini",
            u"Risotto alla veronese",
            u"Risotto con caprino e aglio",
            u"Garganelli con melanzane",
            u"Rotolo di pasta con ricotta e spinaci",
            u"Strozzapreti con pancetta e gorgonzola",
            u"Linguine alle vongole",
            u"Coregono al burro e salvia",
            u"Spiedino del mare e risotto allo spumante",
            u"Galletto gratinato al gorgonzola con due salse",
            u"Rotolo d'agnello e polenta con salsa alla liquirizia",
            u"Saltimbocca di vitello con caponata",
            u"Filetto di manzo al pepe verde",
            u"Tiramisù alla Papà Giovanni",
            u"Misto di formaggi",
            u"Frutti di bosco marinati alla grappa con spumone",
            u"Gelato",
             ]
        selected = appuifw.multi_selection_list(L , style='checkbox', search_field=1)

    def handle_close(self):
        self.active = False
        self.PrevView.close()

class DoubleListTab:
    def __init__(self, PrevView):
        self.PrevView = PrevView
        self.list = [(u"1st", u"the first"),
                     (u"2nd", u"the second"),
                     (u"3rd", u"the third"),
                     (u"4th", u"the fourth")
                     ]
        #for i in range(4,10):
        #    self.list.append((u"%sth" % i))
        self.body = appuifw.Listbox(self.list, self.handle_select)
        self.menu = [(u"Close", self.handle_close)]

    def activate(self):
        self.active = True
        appuifw.app.body = self.body
        appuifw.app.menu = self.menu
        appuifw.app.exit_key_handler = self.handle_close

    def handle_select(self):
        appuifw.note(u"Chosen: %s " % self.body.current(),'info')
        pass

    def handle_close(self):
        self.active = False
        self.PrevView.close()


############## List VIEW END ###############

################### BASE VIEW START #######################
class TextView:
    """Base class for all Text views"""

    def __init__(self, PrevView):
        """__init__ must be defined in derived class.
        Set all tabs here."""
        self.name = "BaseView"
        self.PrevView = PrevView
        self.menu = [(u"Choose font", self.choose_font),
                     (u"Choose color", self.choose_color),
                     (u"Choose style", self.choose_style),
                     (u"Choose size", self.choose_size),
                     (u"Close", self.handle_close),
                     ]
        self.body = appuifw.Text(u"Use menus ")
        #self.fonts = appuifw.available_fonts()
        self.fonts = [u"annotation",
                      u"title",
                      u"legend",
                      u"symbol",
                      u"dense",
                      u"normal",
                      ]
        self.colors = [(u"red",0xff0000),
                       (u"green",0x00ff00),
                       (u"blue",0x0000ff),
                       (u"yellow",0xffff00),
                       (u"black",0x000000),
                      ]
        self.styles = [(u"Normal",0),
                       (u"Bold",appuifw.STYLE_BOLD),
                       (u"Underlined",appuifw.STYLE_UNDERLINE),
                       (u"Italic", appuifw.STYLE_ITALIC),
                       (u"Strikethrough", appuifw.STYLE_STRIKETHROUGH),
                       ]
        self.sizes = [3, 6, 9, 12, 15, 18, 24, 30, 40, 60, 80, 100, 140]
        self.font = (self.fonts[0], None)

    def activate(self):
        """Set main menu to app.body and left menu entries."""
        appuifw.app.menu = self.menu
        appuifw.app.exit_key_handler = self.exit_key_handler
        appuifw.app.body = self.body

    def choose_font(self):
        selected = appuifw.selection_list(self.fonts, search_field=1)
        if selected != None:
            self.font = (str(self.fonts[selected]), None)
            self.body.font = self.font
            self.body.add(self.fonts[selected] + u"\n")

    def choose_color(self):
        selected = appuifw.selection_list([item[0] for item in self.colors], search_field=1)
        if selected != None:
            self.color = self.colors[selected][1]
            self.body.color = self.color
            self.body.add(self.colors[selected][0] + u"\n")

    # \ | []
    def choose_size(self):
        selected = appuifw.selection_list([unicode(item) for item in self.sizes])
        if selected != None:
            self.font = (self.font[0], self.sizes[selected])
            self.body.font = self.font
            self.body.add(u"%d px\n" % self.sizes[selected])

    def choose_style(self):
        selected = appuifw.multi_selection_list([item[0] for item in self.styles])
        if selected is None: return
        style = 0
        style_names = []
        for i in selected:
            style = style | self.styles[i][1]
            style_names.append(self.styles[i][0])
        self.style = style
        self.body.style = self.style
        self.body.add(','.join(style_names) + u"\n")

    def exit_key_handler(self):
        self.handle_close()

    def handle_close(self):
        # Activate previous (calling) view
        self.PrevView.activate()
################### BASE VIEW END #########################

oldbody = appuifw.app.body
myApp = GuiApp()
myApp.run()
positioning.stop_position()
# Just testing workaround:
# http://sourceforge.net/tracker/index.php?func=detail&aid=1458010&group_id=154155&atid=790646
#e32.ao_sleep(0, myApp.run)
#e32.ao_sleep(1)
appuifw.app.body = oldbody
#e32.ao_sleep(1)
# For SIS-packaged version uncomment this:
#appuifw.app.set_exit()
