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
import Comm

####################################
# FIXME: move these to an own module
# These are currently in pys60gps.pu and TrackView.py
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
        # FIXME: Main.start_read_position() updates also app.menu
        if self.Main.read_position_running == False:
            self.Main.start_read_position()

        appuifw.app.menu = [#(u"Update", self.update),
                            (u"Stop GPS", self.stop_gps)
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
        self.canvas.bind(key_codes.EKey3, lambda: self.toggle("wlan"))
        self.canvas.bind(key_codes.EKey4, self.Main.wlanscan)
        self.canvas.bind(key_codes.EKey6, self.Main.bluetoothscan)

        appuifw.app.menu.insert(0, (u"Stop GPS", self.stop_gps))
        appuifw.app.menu.insert(0, (u"Send track via bluetooth", self.send_track))
        appuifw.app.menu.insert(0, (u"Send cellids via bluetooth", self.send_cellids))
        appuifw.app.menu.insert(0, (u"Send debug track via bluetooth", self.send_debug))
        appuifw.app.menu.insert(0, (u"Set meters/pixel", 
                                    lambda:self.set_meters_per_px(appuifw.query(u"Meters","number", self.meters_per_px))))
        appuifw.app.menu.insert(0, (u"Clear all data", self.Main.clear_all_data))
        appuifw.app.menu.insert(0, (u"Add POI", self.save_poi))
        appuifw.app.menu.insert(0, (u"Download", self.download_pois_new))
        e32.ao_sleep(0.1)
        self.update()

    def stop_gps(self):
        positioning.stop_position()
        self.Main.read_position_running = False

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

