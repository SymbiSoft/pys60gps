#!/usr/bin/env python

"""
Convert lines json-formatted gps-data to some standard format (KML, GPX).
"""

import os
import sys
import time
import re
import zipfile
import simplejson

def header():
    return """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>"""

def footer():
    return """</Document>
</kml>"""

def start_folder(name):
    return """<Folder>
 <name>%s</name>
 <visibility>1</visibility>
 <open>0</open>""" % name

def end_folder():
    return """ </Folder>"""


def start_placemark(name):
    return """ <Placemark>
  <name>%s</name>
  <description></description>
  <Style>
   <LineStyle>
   <width>3</width>
   <color>ffffff00</color>
   </LineStyle>
  </Style>
  <LineString>
  <extrude>1</extrude>
  <tessellate>1</tessellate>
  <altitudeMode>relative</altitudeMode>
  <coordinates>""" % name

def end_placemark():
    return """  </coordinates>
  </LineString>
 </Placemark>"""

"""
TODO: flush buffer after e.g. 1000 lines
TODO: flush buffer to a zip file, use zipfile: http://effbot.org/librarybook/zipfile.htm
TODO: put those start/end-functions inside the class
"""

class UglyAndHackyKMLExporterButHeyItWorks:
    """
    Read and parse JSON-files and output XML (KML, GPX)
    """
    def __init__(self):
        self.isotime_pattern = re.compile(r'^(\d{4})-?(\d{2})-?(\d{2})[tT ]?(\d{2})?:?(\d{2})?:?(\d{2})?([+Z-])?(\d{2})?:?(\d{2})?')
        self.folder = []
        self.start_folder_flag = 0
        self.lasttime = 0 # epochtime
        # split track if delay between to trackpoints exceeds this:
        self.splittrack_sec = 120 
        self.buf = []
        self.buf.append(header())
        self.filepaths = []

    def readfiles(self):
        """
        Call self.readfile() for every file in filelist.
        and end KML file after this by calling several times 
        end_*() functions and once footer().
        """
        for filepath in self.filepaths:
            self.readfile(filepath)
        self.buf.append(end_placemark())
        self.buf.append(end_folder())
        self.buf.append(end_folder())
        self.buf.append(end_folder())
        self.buf.append(footer())

    def readfile(self, filepath):
        """
        Read all lines from file and call self.handle_trackpoint() for
        every of them.
        """
        f = open(filepath, "rt")
        for line in f.readlines():
            linedata = simplejson.loads(line)
            self.handle_trackpoint(linedata)

    def handle_trackpoint(self, linedata):
        """
        Append trackpoint to the KML file, usually into <coordinates> block.
        Close and open <Folder> and <Placemark>s if neccessary.
        """
        if "lat" not in linedata or \
           "lon" not in linedata:
            return
        if "hdop" in linedata and linedata["hdop"] > 3:
            print linedata["hdop"]
            return
        tt, tzone = self.parse_isotime(linedata["gpstime"])
        currenttime = time.mktime(tt);
        ts = time.strftime("%Y%m%dT%H%M%SZ", tt)
        # Start new placemark if there is too much delay between 2 trackpoints
        if currenttime - self.splittrack_sec > self.lasttime and \
           self.lasttime > 0:
            self.buf.append(end_placemark())
            self.buf.append(start_placemark(ts))
        self.lasttime = currenttime
        oldfolder = self.folder[:]
        self.folder = [tt[0], tt[1], tt[2]]
        if oldfolder and self.folder and oldfolder[-1] != self.folder[-1]:
            self.buf.append(end_placemark())
            self.buf.append(end_folder())
            oldfolder.pop()
            self.folder.pop()
        if oldfolder and self.folder and oldfolder[-1] != self.folder[-1]:
            self.buf.append(end_folder())
            oldfolder.pop()
            self.folder.pop()
        if oldfolder and self.folder and oldfolder[-1] != self.folder[-1]:
            self.buf.append(end_folder())
            oldfolder.pop()
            self.folder.pop()
        self.folder = [tt[0], tt[1], tt[2]]
        while (len(oldfolder) < len(self.folder)):
            oldfolder.append(self.folder[len(oldfolder)])
            self.buf.append(start_folder("-".join(["%02d" % i for i in oldfolder])))
            self.start_folder_flag = 1
        if self.start_folder_flag:
            self.buf.append(start_placemark(ts))
            self.start_folder_flag = 0
        if "alt_m" not in linedata: linedata["alt_m"] = 0
        if "speed_kmh" not in linedata: linedata["speed_kmh"] = 0
        if "heading" not in linedata: linedata["heading"] = 0
        if "hdop" not in linedata: linedata["hdop"] = 0
        if "vdop" not in linedata: linedata["vdop"] = 0
        if "tdop" not in linedata: linedata["tdop"] = 0
        if "satellites" not in linedata: linedata["satellites"] = "0/0"
        format = "  %(lon).6f,%(lat).6f,%(alt_m).1f <!-- %(gpstime)s,%(speed_kmh).2f,%(heading).2f,%(hdop).1f,%(vdop).1f,%(tdop).1f,%(satellites)s -->"
        try:
            self.buf.append(format % linedata)
        except:
            print linedata
            raise

    def parse_isotime(self, tstr):
        """
        Parse ISO datetime.
        Return time tuple and timezone in seconds
        """
        m = self.isotime_pattern.search(tstr)
        if m is not None:
            (Y,m,d,H,M,S,Z,zh,zm) = m.group(1,2,3,4,5,6,7,8,9)
            Y = int(Y)
            m = int(m)
            d = int(d)
            if H is None: H = 0
            else: H = int(H)
            if M is None: M = 0
            else: M = int(M)
            if S is None: S = 0
            else: S = int(S)
            if Z == 'Z' or Z is None: tz = 0
            else:
                tz = 0
                if zh is not None: tz = int(zh) * 60 * 60
                if zm is not None: tz = tz + int(zm) * 60
                if Z == '+': tz = -1 * tz
            return (Y,m,d,H,M,S,0,1,0), tz


def zipall(buf):
    filename = "all.kmz"
    name = "all.kml"
    now = time.localtime(time.time())[:6]
    file = zipfile.ZipFile(filename, "w")
    info = zipfile.ZipInfo(name)
    info.date_time = now
    info.compress_type = zipfile.ZIP_DEFLATED
    file.writestr(info, "\n".join(buf))
    # Some ways to write buffered data to zip file
    # http://stackoverflow.com/questions/297345/create-a-zip-file-from-a-generator-in-python
    # http://docs.python.org/library/stringio.html
    file.close()


if __name__=="__main__":
    kmlexporter = UglyAndHackyKMLExporterButHeyItWorks()
    kmlexporter.filepaths = sys.argv[1:]
    kmlexporter.readfiles()
    #print "\n".join(kmlexporter.buf)
    #print len(kmlexporter.buf)
    zipall(kmlexporter.buf)



