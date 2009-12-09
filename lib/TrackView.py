# -*- coding: utf8 -*-
# $Id$

import appuifw
import e32
import time
import sys
import os
import re
import time
import copy
import key_codes
import graphics
import sysinfo
import simplejson
import PositionHelper
import pys60gpstools
import locationtools

ARROW_POINTS = [(-0.0,  0.0), ( 0.0,  0.0), ( 1.0, 20.0), ( 5.0, 15.0),
                ( 0.0, 25.0), (-5.0, 15.0), (-1.0, 20.0),
                ]

import math
def rotate(points, xoff, yoff, angle, zoom):
    """
    Rotate polygon which is defined in points.
    """

    # Convert integer angle to radians for math.sin() and math.cos().
    angle_rad = angle * 2 * math.pi / 360.0

    # Rotate, scale and transpose points.
    rot_points = []
    for point in points:
        # Get original point coordinates.
        x, y = point

        # Rotate
        rot_x = math.cos(angle_rad) * x - math.sin(angle_rad) * y
        rot_y = math.sin(angle_rad) * x + math.cos(angle_rad) * y

        # Scale
        rot_x *= zoom
        rot_y *= zoom

        # Transpose
        rot_x += xoff
        rot_y += yoff

        # Append new point coordinates to a list.
        rot_points.append((rot_x, rot_y))
    return rot_points


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
    simple_center_pos = {}
    toggables = {"track":True,
                 "cellid":False,
                 "wlan":False,
                }
    canvas = None

    def resize_cb(self, dummy=(0,0,0,0)):
        if self.canvas:
            self.ui = graphics.Image.new(self.canvas.size)
            self.center_x = self.canvas.size[0]/2
            self.center_y = self.canvas.size[1]/2
        

    def activate(self):
        self.init_ram = sysinfo.free_ram()
        self.active = True
        appuifw.app.exit_key_handler = self.handle_close
        self.canvas = appuifw.Canvas(redraw_callback=self.update,
                                     resize_callback=self.resize_cb)
        self.center_x = self.canvas.size[0]/2
        self.center_y = self.canvas.size[1]/2
        #self.resize_cb()
        self.ui = graphics.Image.new(self.canvas.size)
        appuifw.app.body = self.canvas
        appuifw.app.screen = "normal"
        # FIXME: Main.start_read_position() updates also app.menu
        if self.Main.read_position_running == False:
            self.Main.start_read_position()

        appuifw.app.menu = [#(u"Update", self.update),
                            (u"Stop GPS", self.stop_gps),
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

        # appuifw.app.menu.insert(0, (u"Stop GPS", self.stop_gps))
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
        self.Main.stop_read_position()
        #positioning.stop_position()
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
        if not self.simple_center_pos:
            if not self.Main.simple_pos: # empty position, no gps connected since start
                appuifw.note(u"No GPS", 'error')
                return
            if pys60gpstools.has_fix(self.Main.simple_pos):
                self.simple_center_pos = copy.deepcopy(self.Main.simple_pos)
            elif len(self.Main.data["track_new"]) > 0 and \
                 pys60gpstools.has_fix(self.Main.data["track_new"][-1]):
                self.simple_center_pos = copy.deepcopy(self.Main.data["track_new"][-1])
            else:
                appuifw.note(u"No FIX", 'error')
                return
        move_m = self.meters_per_px * 50
        if (1,0) == (x,y):
            # direction = u"east"
            self.simple_center_pos["e"] = self.simple_center_pos["e"] + move_m
            # TODO: calc lat and lon here too
        elif (0,1) == (x,y):
            # direction = u"south"
            self.simple_center_pos["n"] = self.simple_center_pos["n"] - move_m
            # TODO: calc lat and lon here too
        elif (-1,0) == (x,y):
            # direction = u"west"
            self.simple_center_pos["e"] = self.simple_center_pos["e"] - move_m
            # TODO: calc lat and lon here too
        elif (0,-1) == (x,y):
            # direction = u"north"
            self.simple_center_pos["n"] = self.simple_center_pos["n"] + move_m
            # TODO: calc lat and lon here too
        self.update()

    def center(self):
        """
        Reset center_pos so current position is the center again.
        """
        self.simple_center_pos = {}
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
        name = appuifw.query(u"Name", "text", u"")
        if name is None:
            name = time.strftime(u"%Y%m%d-%H%M%S")
        filename = u"trackdebug-%s.json" % name
        filename = os.path.join(self.Main.datadir, filename)
        f = open(filename, "wt")
        d = self.Main.data["position_debug"]
        while len(d) > 0:
            f.write(simplejson.dumps(d.pop(0))+"\n")
        f.close()
        self.Main.send_file_over_bluetooth(filename)

    def save_poi(self):
        """
        Saves a point to the "pois" list.
        """
        # TODO: put POIs to the global data dictionary
        if not self.Main.simple_pos: # empty position, no gps connected yet
            appuifw.note(u"No GPS", 'error')
            return
        
        simple_pos = self.Main.simple_pos
        # Default name is gps timestamp (UTC) with timezone info (time.altzone)
        ts = unicode(time.strftime(u"%H:%M:%SZ ", time.localtime(simple_pos["gpstime"])))
        simple_pos["text"] = appuifw.query(u"Name", "text", ts)
        if simple_pos["text"] is not None: # user did not press Cancel
            self.Main.data["pois_private"].append(simple_pos)
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

    def _calculate_canvas_xy_new(self, image, meters_per_px, p0, p):
        """
        Calculcate x- and y-coordiates for point p.
        p0 is the center point of the image.
        """
        if 'e' not in p: return
        if 'e' not in p0: return
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

    def draw_point_estimation(self, pos):
        if len(self.Main.data["position"]) > 0 and 'pos_estimate' in self.Main.trackcalc:
            pe = self.Main.trackcalc['pos_estimate']
            err_radius = self.Main.config["estimated_error_radius"] # meters
            ell_r = err_radius / self.meters_per_px 
            self._calculate_canvas_xy_new(self.ui, self.meters_per_px, self.simple_pc, pe)
            if 'x' in pe:
                self.ui.ellipse([(pe["x"]+self.center_x-ell_r,pe["y"]+self.center_y-ell_r),
                                 (pe["x"]+self.center_x+ell_r,pe["y"]+self.center_y+ell_r)], outline=0x9999ff)
            # Draw accurancy circle
            # FIXME: this doesn't draw the circle to the current position, instead to the map center
            if 'hacc' in pos:
                acc_radius = pos['hacc']
                if acc_radius > 0:
                    acc_r = acc_radius / self.meters_per_px 
                    self.ui.ellipse([(self.center_x-acc_r,self.center_y-acc_r),
                                     (self.center_x+acc_r,self.center_y+acc_r)], outline=0xccffcc)

    def draw_course_arrow(self, pos):
        if pys60gpstools.has_fix(pos) and 'course' in pos:
            p = copy.deepcopy(pos)
            self._calculate_canvas_xy_new(self.ui, self.meters_per_px, self.simple_pc, p)
            xoff = self.ui.size[0] / 2
            yoff = self.ui.size[1] / 2
            if 'x' in p:
                xoff = xoff + p['x']
            if 'y' in p:
                yoff = yoff + p['y']
            zoom = 2.0
            angle = (p['course'] + 180) % 360
            rot_points = rotate(ARROW_POINTS, xoff, yoff, angle, zoom)
            self.ui.polygon(rot_points, fill = 0xffff00, outline = 0x999900,
                           width = 1)

    def draw_points(self, points, color):
        for p in points:
            self._calculate_canvas_xy_new(self.ui, self.meters_per_px, self.simple_pc, p)
            if p.has_key("x"):
                self.ui.text(([p["x"]+self.center_x+10, p["y"]+self.center_y+5]), u"%s" % p["text"], font=(u"Series 60 Sans", 10), fill=0xccccff)
                self.ui.point([p["x"]+self.center_x, p["y"]+self.center_y], outline=color, width=self.poi_width)

    # Draw track if it exists
    def draw_track_new(self):
        # TODO: all of these loops to a function
        track = self.Main.data["track_new"]
        if len(track) > 0:
            p1 = track[-1]
        lines_drawn = 0
        for i in range(len(track)-1, -1, -1): # draw trackpoints backwards
            p = track[i]
            self._calculate_canvas_xy_new(self.ui, self.meters_per_px, self.simple_pc, p)
            max_timediff = 120 # seconds
            timediff = abs(p["gpstime"] - p1["gpstime"])
            # Draw only lines which are inside canvas/screen
            # FIXME: no hardcoded values here
            if (p.has_key("x") 
               and p1.has_key("x") 
               and (-self.center_x < p["x"] < self.center_x or -self.center_x < p1["x"] < self.center_x) 
               and (-self.center_y < p["y"] < self.center_y or -self.center_y < p1["y"] < self.center_y) 
               and timediff <= max_timediff):
                self.ui.point([p["x"]+self.center_x, p["y"]+self.center_y], outline=0x888800, width=5)
                self.ui.line([p["x"]+self.center_x, p["y"]+self.center_y,
                              p1["x"]+self.center_x, p1["y"]+self.center_y], outline=0x008888, width=3)
                lines_drawn = lines_drawn + 1
            p1 = p

    def draw_statusbar(self, pos):
        """Draw a red, yellow or green colored dot depending GPS state."""
        # FIXME: do this better
        x1 = self.canvas.size[0] - 55    # x location
        y1 = 35     # y location
        
        if self.Main.read_position_running:
            if pys60gpstools.has_fix(pos):
                self.ui.point((x1, y1), outline=0x00ff00, width=10)
            else:
                self.ui.point((x1, y1), outline=0xffff00, width=10)
        else:
            self.ui.point((x1, y1), outline=0xff0000, width=10)
        if self.Main.downloading_pois_test:
            self.ui.point((x1+10, y1), outline=0xffff00, width=10)
        font = (u"Series 60 Sans", 12)
        self.ui.text((x1, y1+20), u"%s" % (time.strftime("%H:%M:%S")), 
                        font=font, fill=0x999999)


    def draw_texts(self, pos):
        """Draw some informative texts on the Track canvas."""
        helpfont_size = 12
        text_x = 105
        text_y = 3
        helpfont = (u"Series 60 Sans", helpfont_size)

        text_y += helpfont_size
        self.ui.text((text_x, text_y), u"Track: %d/%d" % (
                        len(self.Main.data["track_new"]), 
                        len(self.Main.data["position_debug"]), 
                        ), 
                        font=helpfont, fill=0x999999)
        try:
            e_text = u"E %.2f" % self.simple_center_pos["e"]
            text_y += helpfont_size
            self.ui.text((text_x,text_y), e_text, font=helpfont, fill=0x999999)
        except:
            pass
        #text_y = self.canvas.size[0] - 50
        ram = sysinfo.free_ram()
        text_y += helpfont_size
        self.ui.text((text_x, text_y), u"Mem %d kB" % (ram/1024), 
                        font=helpfont, fill=0x999999)
        text_y += helpfont_size
        self.ui.text((text_x, text_y), u"Diff %d kB" % ((ram-self.init_ram)/1024), 
                        font=helpfont, fill=0x999999)
        text_y += helpfont_size
        self.ui.text((text_x, text_y), u"%d B" % (ram), 
                        font=helpfont, fill=0x999999)
        

    def draw_tracklogbars(self, pos):
        helpfont_size = 12
        text_y = 3
        helpfont = (u"Series 60 Sans", helpfont_size)
        # TODO: this track calculation to own function
        barfont = (u"Series 60 Sans", 10)
        def barbarbar(barsize, text, val, max):
            """
            Draw a bar which shows the how the relation 
            between val and max value.
            """
            if max == 0:
                return
            (x1, y1, x2, y2) = barsize
            barwidth = x2 - x1
            # Outline
            self.ui.rectangle((x1, y1, x2, y2), outline=0x80f080)
            # Fillings
            fill_w = val / max * barwidth
            if val < max:
                color = 0x80ff80
            else:
                color = 0xff8080
            self.ui.rectangle((x1, y1, fill_w, y2), fill=color)
            self.ui.text((x1, y2 - 1), text % (val, max), 
                        font=barfont, fill=0x999999)
        # Draw several bars, which indicate how close is the saving
        # of next track log point
        if self.Main.trackcalc:
            tc = self.Main.trackcalc
            x1 = 2
            barwidth = 100
            x2 = x1 + barwidth
            bars = [
                ('timediff', u"Time: %.1f/%.1f m", 'max_time'),
                ('lastdist', u"Dist: %.1f/%.1f m", 'max_dist'),
                ('linedist', u"Line: %.1f/%.1f m", 'max_linediff'),
                ('estimatedist', u"Est.: %.1f/%.1f m", 'max_dist_estimate'),
            ]
            for bar in bars:
                if bar[0]  in tc:
                    text_y += helpfont_size
                    barbarbar((x1, text_y - helpfont_size, x2, text_y),
                              bar[1], tc[bar[0]], self.Main.LIMITS[bar[2]])


    def draw_speedinfo(self, pos):
        # FIXME: do this better
        try:
            if self.Main.data["trip_distance"] >= 1000.0:
                trip = u"%.2f km" % (self.Main.data["trip_distance"] / 1000)
            else:
                trip = u"%.1f m" % (self.Main.data["trip_distance"])
            y = self.canvas.size[1] - 10
            # Speed may be missing
            self.ui.text((2, y), u"%.1f m/s %s" % (pos["speed"], trip), 
                         font=(u"Series 60 Sans", 18), fill=0x000000)
        except:
            pass


    def draw_scalebar(self):
        """Draw the scale bar."""
        sb_width = 50 # pixels
        x1 = self.canvas.size[0] - 55    # x location
        y1 = 10     # y location
        scale_value = sb_width * self.meters_per_px
        if scale_value > 1000: 
            scale_text = u"%.1f km" % (scale_value / 1000.0)
        else:
            scale_text = u"%d m" % (scale_value)
        if self.meters_per_px >= 1:
            mppx_text = u"%d m/px" % self.meters_per_px
        else:
            mppx_text = u"%d cm/px" % (self.meters_per_px * 100)
        self.ui.text((x1 + 5, y1 + 3), scale_text, font=(u"Series 60 Sans", 10), fill=0x333333)
        self.ui.text((x1 + 5, y1 + 17), mppx_text, font=(u"Series 60 Sans", 10), fill=0x333333)
        self.ui.line([x1, y1 + 5, x1 + sb_width, y1 + 5], outline=0x0000ff, width=1)
        self.ui.line([x1, y1, x1, y1 + 10], outline=0x0000ff, width=1)
        self.ui.line([x1 + sb_width, y1, x1 + sb_width, y1 + 10], outline=0x0000ff, width=1)


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
        center_x = self.center_x
        center_y = self.center_y
        #self.center_y = center_y = 120
        # TODO: cleanup here!
        self.ui.clear()
        # Print some information about track
        mdist = self.Main.config["min_trackpoint_distance"]
        helpfont = (u"Series 60 Sans", 12)
        # Draw crosshair
        self.ui.line([center_x-ch_l, center_y, center_x+ch_l, center_y], outline=0x0000ff, width=1)
        self.ui.line([center_x, center_y-ch_l, center_x, center_y+ch_l], outline=0x0000ff, width=1)
        # TODO: draw arrow
        # Test polygon
        # self.ui.polygon([15,15,100,100,100,15,50,10], outline=0x0000ff, width=4)
        j = 0
        pos = self.Main.pos # the current position during this update()
        simple_pos = self.Main.simple_pos # the current position during this update()
        # simple_pc is the current center point
        if self.simple_center_pos:
            self.simple_pc = simple_pc = self.simple_center_pos
        else:
            self.simple_pc = simple_pc = self.Main.last_fix
        # plot pois size relative to zoom level
        self.poi_width = 20 / self.meters_per_px 
        if self.poi_width < 1: self.poi_width = 1
        if self.poi_width > 10: self.poi_width = 10
        
        self.draw_point_estimation(pos)
        self.draw_course_arrow(simple_pos)
        self.draw_points(self.Main.data["gsm_location"], 0x9999ff)
        self.draw_points(self.Main.data["wlan"], 0x0000ff)
        self.draw_track_new()
        self.draw_statusbar(simple_pos)
        self.draw_texts(simple_pos)
        self.draw_tracklogbars(simple_pos)
        self.draw_scalebar()
        self.draw_points(self.Main.data["pois_downloaded_new"], 0x990000)
        self.draw_points(self.Main.data["pois_private"], 0x000099)
        self.draw_speedinfo(simple_pos)

        # Plot debug points
        pd = self.Main.data["position_debug"]
        for i in range(len(pd)-1, -1, -1):
            j = j + 1
            if j > 60: break # draw only last x debug points
            p = pys60gpstools.simplify_position(pd[i])
            if pys60gpstools.has_fix(p):
                locationtools.set_fake_utm(p, self.Main.LongOrigin)
            self._calculate_canvas_xy_new(self.ui, self.meters_per_px, 
                                          self.simple_pc, p)
            if 'x' in p:
                self.ui.point([p["x"]+self.center_x, p["y"]+self.center_y], 
                              outline=0x000066, width=3)

        self.canvas.blit(self.ui)
        if self.active and self.Main.focus:
            self.t.after(0.5, self.update)
