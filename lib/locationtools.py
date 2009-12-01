# -*- coding: utf8 -*-
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
    return Calculate.distance(pos1['lat'], pos1['lon'],
                              pos2['lat'], pos2['lon'])


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
    # Calculate fake n and e values (fake because we don't use 
    # valid long_origin but first pos' long)
    set_fake_utm(pos, long_origin)
    # New trackpoint if tracklog is empty or has only 1 point yet
    if len(tracklog) <= 1:
        pos['reason'] = u"Startpoint"
        tracklog.append(pos)
        return 1
    # Now we have for sure at least 1 trackpoint in log list
    pos_last = tracklog[-1]
    # New trackpoint max_time has been exceeded
    timediff = pos['gpstime'] - pos_last['gpstime']
    if timediff >= limits['max_time']:
        pos['reason'] = u"Timediff %.2f" % (timediff)
        tracklog.append(pos)
        return 2
    # New trackpoint if dist between this and latest saved exceeds threshold
    last_dist = pos_distance(pos, pos_last)
    if last_dist >= limits['max_dist']:
        pos['reason'] = u"Distance %2.2f>%.2f" % (last_dist,
                                                  limits['max_dist'])
        tracklog.append(pos)
        return 3
    # New trackpoint if max_trackdiff far from line between 2 latest points
    dist_line = pos_distance_from_line(pos_last, tracklog[-2], pos)
    if dist_line >= limits['max_trackdiff']:
        pos['reason'] = u"Distline %2.2f>%.2f" % (dist_line,
                                                  limits['max_trackdiff'])
        tracklog.append(pos)
        return 4
    # New trackpoint if turning
    if 'course' in pos_last and 'course' in pos:
        anglediff = Calculate.anglediff(pos_last['course'], pos["course"])
        if anglediff > limits['max_anglediff'] and last_dist > limits['min_dist']:
            pos['reason'] = u"Anglediff %2.2f>%.2f" % (anglediff,
                                                       limits['max_anglediff'])
            tracklog.append(pos)
            return 5
    # New trackpoint if too far from estimated point
    if 'course' in pos_last and 'course' in pos and \
       'speed' in pos_last and 'speed' in pos:
        dist_project = pos_last['speed'] * timediff # speed * seconds = distance in meters
        lat, lon = Calculate.newlatlon(pos_last["lat"], pos_last["lon"], 
                                       dist_project, pos_last["course"])
        pos_estimate = {'lat': lat, 'lon': lon}
        set_fake_utm(pos_estimate, long_origin)
        dist_estimate = Calculate.distance(pos_estimate['lat'], pos_estimate['lon'],
                                           pos['lat'], pos['lon'])
        if dist_estimate > 50.0:
            pos['reason'] = u"Distestimate %2.1f>%.2f" % (dist_estimate, 50)
            tracklog.append(pos)
            return 6
    return 0
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
    TRACKLOG = []
    LOSTFIX = True
    LONG_ORIGIN = None

    # Track simplification parameters
    LIMITS = {
        'max_trackdiff': 10.0, # meters
        'min_dist': 10.0, # meters
        'max_dist': 1000.0, # meters
        'min_time': 0.0, # seconds
        'max_time': 60.0, # seconds
        'max_anglediff': 30.0, # degrees
    }
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
    for POS in POSLOG:
        if handle_trkpt(POS, TRACKLOG, LIMITS, LONG_ORIGIN):
            pass
            #print POS['reason']
    POS['reason'] = "Last"
    TRACKLOG.append(POS) # add last one
    sys.stderr.write('TRACKLOG len: %d\n' % len(TRACKLOG))
    # print "<!--Tracklog len %d-->" % len(TRACKLOG)
    import track2kml
    print track2kml.header()
    print track2kml.start_placemark("All")
    for POS in _get_poslist():
        if pys60gpstools.has_fix(POS):
            print "%(lon).6f,%(lat).6f" % POS
    PLACEMARKS = []
    print track2kml.end_placemark()
    print track2kml.start_placemark("Reduced", 'ffffffff')
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
    print "\n".join(PLACEMARKS).encode("utf8")
    print track2kml.footer()
