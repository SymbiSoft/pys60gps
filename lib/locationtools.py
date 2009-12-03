# -*- coding: utf8 -*-
# $Id: TrackView.py 226 2009-12-02 10:21:37Z aapris $
"""
Reduce the number of trackpoints to save.

Full dump of GPS data may take a few megabytes of storage per hour.
This module contains functions to help to reduce unnecessary
trackpoints from original tracklog.

After reduction tracklog may contain e.g. only from 1/60 to 5/60
of original trackpoints, but the track still remains pretty accurate.
Reduced trackpoints can be restored later by interpolating.

Most functions handle pos dictionaries having keys defined below:

pos = {
    # Mandatory keys
    'gpstime': 1259317554.0,
    'lat': 60.274858047640997,
    'lon': 24.986528557189999,
    # Optional
    'course': 55.709999084472699,
    'speed': 1.7200000286102299,
    # Example extra keys
    'ele': 37.5,
    'tdop': 2.1199998855590798,
    'vdop': 2.6800000667571999,
    'hdop': 1.5900000333786,
    'sacc': 1.4299999475479099,
    'hacc': 27.335233688354499,
    'vacc': 64.5,
    'cacc': 10.6499996185303,
    'sat': 7,
    'satinview': 11,
}

"""

import sys
import time
import math

import pys60gpstools

import Calculate
import LatLongUTMconversion

# Trigonometric functions
RAD = math.pi / 180


def project_point(x0, y0, dist, angle):
    """Project a new point from point x0,y0 to given direction and angle."""
    y1 = y0 + math.cos(angle * RAD) * dist
    x1 = x0 + math.cos((90 - angle) * RAD) * dist
    return x1, y1


def slope(x0, y0, x1, y1):
    """Calculate the slope of the line joining two points."""
    if x0 == x1:
        return 0
    return 1.0 * (y0 - y1) / (x0 - x1)


def intercept(x, y, a):
    """Return the y-value (c) where the line intercepts y-axis."""
    return y - a * x

def distance(a, b, c, m, n):
    """"""
    return abs(a * m + b * n + c) / math.sqrt(a ** 2 + b ** 2)


def distance_from_vector(x0, y0, dist, angle, x, y):
    """
    Project a new point using x0,y0,dist,angle and return the distance how far
    point x,y is from line between x0,y0 and the projected point.
    """
    x1, y1 = project_point(x0, y0, dist, angle)
    a = slope(x0, y0, x1, y1)
    c = intercept(x0, y0, a)
    dist = distance(a, -1, c, x, y)
    return dist


def distance_from_line(x0, y0, x1, y1, x, y):
    """Return the distance from line x0,y0,x1,y1 to point x,y."""
    a = slope(x0, y0, x1, y1)
    c = intercept(x0, y0, a)
    return distance(a, -1, c, x, y)


def set_fake_utm(pos, long_origin=None):
    """
    Save "fake" UTM coordinates to pos. Those are used in
    triginometic calculations later.
    """
    if long_origin is None:
        long_origin = pos['lon']
    (pos["z"],
     pos["e"],
     pos["n"]) = LatLongUTMconversion.LLtoUTM(23, # Wgs84
                                              pos['lat'], pos['lon'],
                                              long_origin)


# Helpers
def pos_distance(pos1, pos2):
    """Return distance between two pos objects, calculated from lat/lon."""
    try:
        return Calculate.distance(pos1['lat'], pos1['lon'],
                                  pos2['lat'], pos2['lon'])
    except:
        print "exception in Calculate.distance:", \
               pos1['lat'], pos1['lon'], pos2['lat'], pos2['lon']
        return 0.0


def pos_distance_from_line(p1, p2, pos):
    """
    Return pos' distance from line (p1,p2), calculated from
    fake UTM coordinates.
    """
    return distance_from_line(p1["e"], p1["n"],
                              p2["e"], p2["n"],
                              pos["e"], pos["n"])


# Handler
def handle_trkpt(pos, tracklog, limits, long_origin):
    """
    Compare pos to 1-2 latest points in tracklog and append pos to it
    if certain conditions are met.
    """
    res = {}
    # Calculate fake n and e values (fake because we don't use 
    # valid long_origin but first pos' long)
    set_fake_utm(pos, long_origin)
    # New trackpoint if tracklog is empty or has only 1 point yet
    if len(tracklog) <= 1:
        pos['reason'] = u"Start"
        tracklog.append(pos)
        return res
    # If only 3 satellites are used, increase limits a lot
    if 'sat' in POS and POS['sat'] == 3:
        limits = limits.copy() # Create local copy which will be altered
        limits['max_dist'] = limits['max_dist'] * 5
        limits['max_linediff'] = limits['max_linediff'] * 5
        limits['max_anglediff'] = 361
        limits['max_dist_estimate'] = limits['max_dist_estimate'] * 10
    # Now we have for sure at least 1 trackpoint in log list
    pos_last = tracklog[-1]
    # New trackpoint max_time has been exceeded
    res['timediff'] = pos['gpstime'] - pos_last['gpstime']
    if res['timediff'] >= limits['max_time'] and 'reason' not in pos:
        pos['reason'] = u"Timediff %.2f" % (res['timediff'])
        tracklog.append(pos)
        #return res
    # New trackpoint if dist between this and latest saved exceeds threshold
    res['lastdist'] = pos_distance(pos, pos_last)
    if res['lastdist'] >= limits['max_dist'] and 'reason' not in pos:
        pos['reason'] = u"Distance %2.2f>%.2f" % (res['lastdist'],
                                                  limits['max_dist'])
        tracklog.append(pos)
        #return res
    # New trackpoint if max_linediff far from line between 2 latest points
    res['linedist'] = pos_distance_from_line(pos_last, tracklog[-2], pos)
    if res['linedist'] >= limits['max_linediff'] and 'reason' not in pos:
        pos['reason'] = u"Distline %2.2f>%.2f" % (res['linedist'],
                                                  limits['max_linediff'])
        tracklog.append(pos)
        #return res
    # New trackpoint if turning
    if 'course' in pos_last and 'course' in pos:
        res['coursediff'] = Calculate.anglediff(pos_last['course'], 
                                                pos["course"])
        if res['coursediff'] > limits['max_anglediff'] and \
           res['lastdist'] > limits['min_dist'] and \
           'reason' not in pos:
            pos['reason'] = u"Anglediff %2.2f>%.2f" % (res['coursediff'],
                                                    limits['max_anglediff'])
            tracklog.append(pos)
            #return res
    # New trackpoint if too far from estimated point
    # Estimated point is calculated from latest point's course and speed
    if 'course' in pos_last and 'course' in pos and \
       'speed' in pos_last and 'speed' in pos and \
       'reason' not in pos:
        # speed * seconds = distance in meters
        dist_project = pos_last['speed'] * res['timediff']
        lat, lon = Calculate.newlatlon(pos_last["lat"], pos_last["lon"], 
                                       dist_project, pos_last["course"])
        pos_estimate = {'lat': lat, 'lon': lon}
        set_fake_utm(pos_estimate, long_origin)
        res['estimatedist'] = Calculate.distance(pos_estimate['lat'], 
                                                 pos_estimate['lon'],
                                                 pos['lat'], pos['lon'])
        res['pos_estimate'] = pos_estimate
        if res['estimatedist'] > limits['max_dist_estimate']:
            pos['reason'] = u"Estimate %2.1f>%.2f" % (res['estimatedist'], 
                                                  limits['max_dist_estimate'])
            tracklog.append(pos)
            #return res
    return res
    # TODO:
    # - speed diff?
    # - estimation cicrle?
    # - dynamic limits?


def _get_poslist():
    """
    Read the raw track data (1 trackpoint per line in json-format) from file.
    """
    import simplejson
    simple_list = []
    trackjson = open(sys.argv[1], "rt")
    for line in trackjson:
        pos = simplejson.loads(line)
        simple_list.append(pys60gpstools.simplify_position(pos))
    trackjson.close()
    return simple_list

if __name__ == '__main__':
    POSLOG = []
    LOSTFIX = True
    LONG_ORIGIN = None

    for POS in _get_poslist():
        if pys60gpstools.has_fix(POS):
            if LOSTFIX == True:
                POS["segstart"] = True
            POSLOG.append(POS)
            LOSTFIX = False
        else:
            LOSTFIX = True
        #print LOSTFIX
    if POSLOG:
        LONG_ORIGIN = POSLOG[0]['lon']
    # Track simplification parameters
    LIMITS = {
        'max_linediff': 10.0, # meters
        'min_dist': 10.0, # meters
        'max_dist': 1000.0, # meters
        'min_time': 0.0, # seconds
        'max_time': 60.0, # seconds
        'max_anglediff': 30.0, # degrees
        'max_dist_estimate': 50.0, # meters        
    }
    # TRACK1
    TRACKLOG = []
    for POS in POSLOG:
        handle_trkpt(POS, TRACKLOG, LIMITS, LONG_ORIGIN)
    sys.stderr.write('TRACKLOG1 len: %d\n' % len(TRACKLOG))

    LIMITS = {
        'max_linediff': 3.0, # meters
        'min_dist': 5.0, # meters
        'max_dist': 1000.0, # meters
        'min_time': 0.0, # seconds
        'max_time': 60.0, # seconds
        'max_anglediff': 30.0, # degrees
        'max_dist_estimate': 20.0, # meters        
    }
    # TRACK1
    TRACKLOG2 = []
    for POS in POSLOG:
        handle_trkpt(POS, TRACKLOG2, LIMITS, LONG_ORIGIN)
    sys.stderr.write('TRACKLOG2 len: %d\n' % len(TRACKLOG2))
    
    # print "<!--Tracklog len %d-->" % len(TRACKLOG)
    import track2kml
    print track2kml.header()
    print track2kml.start_placemark("All", 'ffffffff')
    for POS in _get_poslist():
        if pys60gpstools.has_fix(POS):
            print "%(lon).6f,%(lat).6f <!-- %(sat)d/%(satinview)d %(hdop).1f-->" % POS
    PLACEMARKS = []
    print track2kml.end_placemark()
    print track2kml.start_placemark("Red", 'ff0000ff')
    for POS in TRACKLOG:
        print "%(lon).6f,%(lat).6f" % POS
        #print POS
        des = time.strftime(u"%H:%M:%S ", time.localtime(POS['gpstime']))
        des += u"%(speed).1f m/s %(course).1f° %(hdop).1f" % POS
        PLACEMARKS.append(track2kml.placemark({
            'name': "%s" % POS['reason'][:1],
            'description': des,
            'coordinates': "%(lon).6f,%(lat).6f" % POS,
        }))
    print track2kml.end_placemark()
    print track2kml.start_placemark("Blue", 'ffff0000')
    for POS in TRACKLOG2:
        print "%(lon).6f,%(lat).6f" % POS
        #print POS
        des = time.strftime(u"%H:%M:%S ", time.localtime(POS['gpstime']))
        des += u"%(speed).1f m/s %(course).1f° %(hdop).1f" % POS
        PLACEMARKS.append(track2kml.placemark({
            'name': "%s" % POS['reason'][:1],
            'description': des,
            'coordinates': "%(lon).6f,%(lat).6f" % POS,
        }))
    print track2kml.end_placemark()
    print "\n".join(PLACEMARKS).encode("utf8")
    print track2kml.footer()
