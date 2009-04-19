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

    def __init__(self, parent):       
        Base.View.__init__(self, parent)
        self.active = False
        self.show_images = True
        self.ploklist = []
    
    def get_ploklist(self):
        params = {'operation': 'get_files_newest', 'thumb_size' : '44'}
        if len(self.ploklist) > 0:
            params["lastid"] = self.ploklist[0]["id"]
        # TODO: really use this lastid stuff
        params = urllib.urlencode({'operation': 'get_files_newest'})
        url = "http://www.plok.in/api/test.php"
        ip = appuifw.InfoPopup()
        ip.show(u"Loading latest ploks...", (50, 50), 60000, 100, appuifw.EHLeftVTop)
        f = urllib.urlopen("%s?%s" % (url, params))
        data = simplejson.loads(f.read())
        f.close()
        self.ploklist = data["ploklist"]
        # ip.hide()
        ip.show(u"Dumping images", (50, 50), 60000, 100, appuifw.EHLeftVTop)
        for plok in self.ploklist:
            filename = "D:\\icon-%(id)s.jpg" % plok
            if not os.path.isfile(filename):
                f = open(filename, "wb")
                f.write(base64.decodestring(plok["image_base64"]))
                f.close()
        ip.hide()

    def get_plok(self, id):
        params = urllib.urlencode({'operation': 'get_file', 
                                   'id' : id, 
                                   'image_size' : '240'})
        url = "http://www.plok.in/api/test.php"
        ip = appuifw.InfoPopup()
        ip.show(u"Loading plok...", (50, 50), 60000, 100, appuifw.EHLeftVTop)
        filename = u"D:\\plok-%s.jpg" % id
        if not os.path.isfile(filename):
            urllib.urlretrieve("%s?%s" % (url, params), filename)
        ip.hide()
        lock=e32.Ao_lock()
        content_handler = appuifw.Content_handler(lock.signal)
        content_handler.open(filename)
        lock.wait()

    def update_ploklist(self):
        self.get_ploklist()
        self.fill_items()
        self.listbox.redraw_list()
        
    def fill_items(self):
        # FIXME: check that these keys exist
        pattern = u"%(sender)s %(isotime)s\n%(title)s"
        self.items = [ pattern % (plok) for plok in self.ploklist ]
        self.images = [ "D:\\icon-%(id)s.jpg" % plok for plok in self.ploklist ]

    def item_selected(self):
        item = self.listbox.current()
        plok = self.ploklist[item]
        self.get_plok(plok["id"])

    def handle_close(self):
        self.active = False
        self.parent.activate()

    def activate(self):
        self.active = True
        appuifw.app.screen = "full"
        appuifw.app.menu = [(u"Update list", self.update_ploklist),
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
                                     title=u"Latest ploks")
        
        appuifw.app.body = self.listbox
