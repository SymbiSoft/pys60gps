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
        #pos = (0,0,240,320)
        #self.lock.wait()
    
    def get_ploklist(self):
        
        params = urllib.urlencode({'operation': 'get_ploks_newest'})
        url = "http://www.plok.in/api/test.php"
        f = urllib.urlopen("%s?%s" % (url, params))
        data = simplejson.loads(f.read())
        f.close()
        self.ploklist = data["ploklist"]
        
        for plok in self.ploklist:
            imagefile = "D:\\%(id)s.jpg" % plok
            f = open(imagefile, "wb")
            f.write(base64.decodestring(plok["image_base64"]))
            f.close()

    def fill_items(self):
        self.items = [ u"%(sender)s %(isotime)s\n%(title)s" % (plok) for plok in self.ploklist ]
        self.images = [ "D:\\%(id)s.jpg" % plok for plok in self.ploklist ]

    def images_menu(self,val):
        self.show_images = val
        menu = []
        if val:
            menu += [(u"Hide images", lambda: self.images_menu(False))]
        else:
            menu += [(u"Show images", lambda: self.images_menu(True))]
        menu += [(u"About", self.about),
                 (u"Quit", self.close_app)]
        app.menu = menu
        self.update_list()
                    
    def item_selected(self):
        item = self.listbox.current()
        #note(u"%s" % item,"info")
        f = self.items[item]
        #self.update_list(f)

    def update_list(self,f=u""):
        if f:
            d = os.path.abspath( os.path.join(self.cur_dir,f) )
        else:
            d = self.cur_dir
        if os.path.isdir(d.encode('utf-8')):
            if f == u".." and len(self.cur_dir) == 3:
                self.cur_dir = u""
            else:
                self.cur_dir = d 
            self.fill_items()
            attrs = self.listbox.get_config()
            attrs['items'] = self.items
            attrs['title'] = u" " + self.cur_dir
            if self.show_images:
                attrs['images'] = self.images
                attrs['image_size'] = (44,44)
            else:
                attrs['images'] = []
                
            self.listbox.reconfigure(attrs)

    def handle_close(self):
        self.active = False
        self.parent.activate()

    def activate(self):
        self.active = True
        app.screen = "full"
        app.menu = [#(u"Hide images", lambda: self.images_menu(False)),
                    (u"Quit", self.close)]
        appuifw.app.exit_key_handler = self.handle_close
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
        
        app.body = self.listbox
