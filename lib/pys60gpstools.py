# -*- coding: utf8 -*-
"""
Miscancellous functions to manipulate PyS60's positioning dicts.

Positioning.position() function returns dicts like this:
{'position': {'vertical_accuracy': 64.5, 'horizontal_accuracy': 27.335233688354499, 'altitude': 37.5, 'longitude': 24.986528557189999, 'latitude': 60.274858047640997}, 'course': {'speed': 1.7200000286102299, 'heading': 55.709999084472699, 'heading_accuracy': 10.6499996185303, 'speed_accuracy': 1.4299999475479099}, 'satellites': {'horizontal_dop': 1.5900000333786, 'used_satellites': 7, 'vertical_dop': 2.6800000667571999, 'time': 1259317554.0, 'satellites': 11, 'time_dop': 2.1199998855590798}}

However, this is a bit too verbose (long variable names), so
simplify_position() function converts above dict to one like below:

{'gpstime': 1259317554.0, 'tdop': 2.1199998855590798, 'vdop': 2.6800000667571999, 'hdop': 1.5900000333786, 'sacc': 1.4299999475479099,
 'lat': 60.274858047640997, 'ele': 37.5, 'course': 55.709999084472699, 'satinview': 11, 'cacc': 10.6499996185303, 'lon': 24.986528557189999, 'vacc': 64.5, 'sat': 7, 'speed': 1.7200000286102299, 'hacc': 27.335233688354499}

Now you can use pos['lat'] instead of pos['position']['latitude'].
"""

import sys
import time

# Dictionary key mappings
pos_gpx_map = {}
pos_gpx_map['satellites'] = {
    'horizontal_dop' : 'hdop',
    'used_satellites' : 'sat',
    'vertical_dop' : 'vdop',
    'time_dop' : 'tdop',
    'satellites' : 'satinview',
    'time' : 'gpstime',
}

pos_gpx_map['position'] = {
    'altitude' : 'ele',
    'latitude' : 'lat',
    'longitude' : 'lon',
    'vertical_accuracy' : 'vacc',
    'horizontal_accuracy' : 'hacc',
}

pos_gpx_map['course'] = {
    'speed' : 'speed',
    'heading' : 'course',
    'heading_accuracy' : 'cacc', # course accuracy
    'speed_accuracy' : 'sacc',
}

def isnan(n):
    """
    Return True if n is float and one of NaN, Inf or -Inf.
    Note: this is probably non-portable kludge, which is ment to work
    when sys.platform == 'symbian_s60'

    >>> inf = 1e300000
    >>> nan = inf/inf
    >>> isnan(nan)
    True
    >>> isnan(inf)
    True
    >>> isnan(-inf)
    True
    >>> isnan(1.2345)
    False
    >>> isnan("foo bar")
    False
    >>> isnan(42)
    False    
    """
    if isinstance(n, float) and str(n).lower() in ['nan', 'inf', '-inf']:
        return True
    else:
        return False

def isfloat(n):
    """Return True if n is a real float."""
    if isinstance(n, float) and str(n).lower() not in ['nan', 'inf', '-inf']:
        return True
    else:
        return False
    
def has_fix(pos):
    """
    Return True if pos has lat and lon keys and both are real floats
    (not NaN or Inf).
    Lat and lon may be something like 2.04788006273e-314 
    in some weird situations?
    """
    if 'lat' in pos and isfloat(pos['lat']) and \
       'lon' in pos and isfloat(pos['lon']) and \
       abs(pos['lat']) > 2e-10:
        return True
    else:
        return False

def simplify_position(pos, include_nans=False):
    """Convert PyS60's position dict to simplier dict and return it."""
    new_pos = {}
    for section in pos.keys(): # [satellites, position, course]
        if section in pos_gpx_map:
            # Loop all keys in pos_gpx_map and convert them to fit flat style
            for key in pos_gpx_map[section].keys():
                if key in pos[section] and \
                       (not isnan(pos[section][key]) or \
                        include_nans == True):
                    new_pos[pos_gpx_map[section][key]] = pos[section][key]
    return new_pos

def _test():
    print "FIXME: Not implemented yet"

if __name__=='__main__':
    _test()
