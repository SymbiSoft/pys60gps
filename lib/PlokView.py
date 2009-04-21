import Base
import time
import os
import re
from appuifw import *
import appuifw
import key_codes
import e32
import graphics
import socket
import urllib
import simplejson
import base64
import sysinfo
from canvaslistbox import CanvasListBox

class PlokView(Base.View):

    def __init__(self, parent, comm=None):
        Base.View.__init__(self, parent)
        self.active = False
        if comm is not None:
            self.comm = comm
        else:
            self.host = appuifw.query(u"Host", "text", u"www.plok.in")
            if not self.host:
                self.host = u"test.plok.in"
            self.comm = Comm.Comm(self.host, "/api/")
        self.show_images = True
        self.ploklist = []
        self.cachedir = u"D:\\plokcache"
        self.clear_cache()
        if not os.path.isdir(self.cachedir):
            os.makedirs(self.cachedir)

    def clear_cache(self):
        if os.path.isdir(self.cachedir):
            for f in os.listdir(self.cachedir):
                if f.endswith("jpg"):
                    os.unlink(os.path.join(self.cachedir, f))
    
    def get_ploklist(self):
        params = {'thumb_size' : '44'}
        if len(self.ploklist) > 0:
            params["lastid"] = self.ploklist[0]["id"]
        ip = appuifw.InfoPopup()
        ip.show(u"Loading latest ploks...", (50, 50), 60000, 100, appuifw.EHLeftVTop)
        data, response = self.comm._send_request("get_files_newest", params)
        # FIXME: error handling missing here
        self.ploklist = data["filelist"]
        # ip.hide()
        ip.show(u"Dumping images", (50, 50), 60000, 100, appuifw.EHLeftVTop)
        for plok in self.ploklist:
            # FIXME: check there is space on D
            # FIXME: error handling missing here
            filename = os.path.join(self.cachedir, "icon-%(id)s.jpg" % plok)
            if not os.path.isfile(filename):
                try:
                    f = open(filename, "wb")
                    f.write(base64.decodestring(plok["image_base64"]))
                    f.close()
                except Exception, error:
                    appuifw.note(unicode(error), 'error')
                    if appuifw.query(u'Try to clear cache', 'query') is True:
                        self.clear_cache()
                    return
        ip.hide()

    def get_plok(self, id):
        params = {'id' : id, 
                  'image_size' : '240'}
        ip = appuifw.InfoPopup()
        ip.show(u"Loading plok...", (50, 50), 60000, 100, appuifw.EHLeftVTop)
        filename = os.path.join(self.cachedir, "plok-%(id)s-%(image_size)s.jpg" % params)
        if not os.path.isfile(filename):
            data, response = self.comm._send_request("get_file", 
                                                     params, filename=filename)
        ip.hide()
        try:
            lock=e32.Ao_lock()
            content_handler = appuifw.Content_handler(lock.signal)
            content_handler.open(filename)
            lock.wait()
        except:
            appuifw.note(u"Could not show file!", 'error')

    def update_ploklist(self):
        self.get_ploklist()
        self.fill_items()
        self.listbox.redraw_list()
        
    def fill_items(self):
        # FIXME: check that these keys exist
        pattern = u"%(sender)s %(time)s\n%(title)s"
        self.items = [ pattern % (plok) for plok in self.ploklist ]
        self.images = [ os.path.join(self.cachedir, "icon-%(id)s.jpg" % plok) for plok in self.ploklist ]

    def item_selected(self):
        item = self.listbox.current()
        plok = self.ploklist[item]
        self.get_plok(plok["id"])

    def handle_close(self):
        self.active = False
        self.parent.activate()

    def activate(self):
        self.active = True
        if self.comm.sessionid:
            logged_in = u" (Logged in)"
        else:
            logged_in = u" (Not logged in)"
        appuifw.app.screen = "full"
        #self.canvas = appuifw.Canvas()
        #self.canvas.text((5, 50), u"Loading...", font=(u"Series 60 Sans", 30), fill=0xccffcc)
        #e32.ao_sleep(0.01)
        appuifw.app.menu = [(u"Update list", self.update_ploklist),
                            (u"Clear file cache", self.clear_cache),
                            (u"Quit", self.close)]
        appuifw.app.exit_key_handler = self.handle_close
        if len(self.ploklist) == 0:
            self.get_ploklist()
        self.fill_items()
        pos = (0,0) + sysinfo.display_pixels()
        self.listbox = CanvasListBox(items=self.items,
                                     cbk=self.item_selected,
                                     images=self.images,
                                     position=pos,
                                     margins=[6,2,2,2],
                                     selection_border_color=(124,104,238),
                                     font_name=(u"Series 60 Sans", 12),
                                     title_font=(u"Series 60 Sans", 16),
                                     image_size=(44,44),
                                     title=u"Latest ploks%s" % logged_in)
        
        appuifw.app.body = self.listbox
