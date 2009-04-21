"""Miscellaneous screens"""

# $Id$

import appuifw
import e32
import time
import sys
import os
import socket
import sysinfo
import re
import time
import copy
import zipfile
import positioning
import location
import key_codes
import graphics
import audio
import LatLongUTMconversion
import Calculate
import simplejson
import PositionHelper

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
        self.tabs.append((u"Wlan", WlanTab(self)))
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

class WlanTab(BaseInfoTab):
    """Show a few last wlans."""
    def _get_lines(self):
        lines = [u"Wlans: %d lines" % len(self.Main.data["wlan"])]
        last = self.Main.data["wlan"][-13:]
        last.reverse()
        for l in last:
            try:
                lines.append(u"%s" % time.strftime("%H:%M:%S ", time.localtime(l["systime"]))
                            + u"  %s wlans found" % (l['text']))
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
