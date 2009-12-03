# -*- coding: utf8 -*-
# $Id$
import Base
import appuifw
import key_codes
import e32
import time
import os
from HelpView import HelpView
from CommWrapper import CommWrapper
from UglyKML import UglyAndHackyKMLExporterButHeyItWorks

class TestView(Base.View):
    """
    This is container for misc tests.
    """
    def __init__(self, parent, comm = None):
        Base.View.__init__(self, parent)
        if comm is None:
            self.comm = self.Main.comm
        else:
            self.comm = comm
        self.cw = CommWrapper(self.comm)
        self.fontsize = 14
        self.delimiter = u">>> "
        self.text = appuifw.Text(u"")
        #self.text.bind(key_codes.EKeySelect, self.send_chatmessage)
        self.help = HelpView(self, 
            u"""Check what is in the menu""")

    def add_text(self, textarea, timestamp, user, text):
        textarea.font = (u"dense", self.fontsize)
        textarea.style = appuifw.STYLE_BOLD
        textarea.color = (200,0,0)
        textarea.add(u"%s: " % (user)) # NOTE: must be unicode here
        textarea.style = 0
        textarea.add(u"%s\n" % (timestamp)) # NOTE: must be unicode here
        textarea.color = (0,0,0)
        textarea.add(u">> %s\n" % (text))
    
    def activate(self):
        """Set main menu to app.body and left menu entries."""
        Base.View.activate(self)
        appuifw.app.menu = [
            (u"Export Tracks",self.export_tracks),
            (u"Help",self.help.activate),
            (u"Close", self.parent.activate),
        ]
        appuifw.app.body = self.text

    def export_tracks(self):
        trackdir = os.path.join(self.Main.datadir, "track")
        trackfiles = []
        if os.path.isdir(trackdir):
            for file in os.listdir(trackdir):
                if file.endswith(".json"):
                    trackfiles.append(os.path.join(trackdir, file))
        items = [t[-13:-5] for t in trackfiles]
        selected = appuifw.multi_selection_list(items, style="checkbox", search_field=1)
        if not selected:
            appuifw.note(u"None selected", 'info')
        kmlexporter = UglyAndHackyKMLExporterButHeyItWorks()
        for i in selected:
            kmlexporter.filepaths.append(trackfiles[i])
        for f in kmlexporter.readfiles():
            self.text.add(f + u"\n")
            e32.ao_sleep(0.1)
            e32.ao_yield()
        if len(selected) > 1:
            zipfile = u"E:\\track-%s-%s.kmz" % (items[selected[0]], items[selected[-1]])
        else:
            zipfile = u"E:\\track-%s.kmz" % (items[selected[0]])
        kmlexporter.get_zip(zipfile)
        if self.Main.send_file_over_bluetooth(zipfile) is False:
            appuifw.note(u"Sending failed. File is saved here: %s" % zipfile, 'error')
