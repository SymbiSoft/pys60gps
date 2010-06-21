# -*- coding: utf8 -*-
# $Id$
import Base
import appuifw
import key_codes
import e32
import time
import os
import simplejson
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
            (u"Memo",self.create_memo),
            (u"Export Tracks",self.export_tracks),
            (u"Help",self.help.activate),
            (u"Close", self.parent.activate),
        ]
        appuifw.app.body = self.text
        self.text.add(u"Select from the menu\nValitse menusta\n'Export Tracks'\n")

    def create_memo(self):
        """
        Create an object which contains all possible information
        of user's current environment and may contain 
        one (audio, video or photo) file attachment.
        """
        memotypes = [
            u'NOTE',
            u'TODO',
            u'MEMO',
        ]
        privacy = [
            u'PRIVATE',
            u'PUBLIC',
        ]
        attachmenttypes = [
            u'AUDIO',
            u'PHOTO',
            u'VIDEO',
        ]
        data = {}
        current_time = time.time()
        data['time'] = current_time
        data['timestring'] = time.strftime("%Y%m%dT%H%M%S", 
                                           time.localtime(current_time))
        # Do not use, if there is ongoing positioning request, it will be killed
#        try:
#            import positioning
#            positioning.select_module(positioning.default_module())
#            positioning.set_requestors([{"type":"service",
#                                         "format":"application",
#                                         "data":"test_app"}])
#            data['position'] = positioning.last_position()
#        except:
#            data['position'] = {}
        data['position'] = self.Main.last_fix.copy()
        try:
            import wlantools
            data['wlan_devices'] = wlantools.scan(False)
        except Exception, error:
            data['wlan_devices'] = {}
        try:
            import location
            data['gsm_location'] = location.gsm_location()
            import sysinfo
            data['gsm_signal_dbm'] = sysinfo.signal_dbm()
        except Exception, error:
            data['gsm_location'] = {}
            data['gsm_signal_dbm'] = None
        choice = appuifw.popup_menu(memotypes, u"Select type (or cancel)")
        if choice is None:
            appuifw.note(u"Cancelled", 'info')
            return
        data['type'] = memotypes[choice]
        data['text'] = appuifw.query(u"New %s:" % (memotypes[choice]), "text", u"")
        data['keywords'] = appuifw.query(u"Addidional keywords:", "text", u"")
        choice = appuifw.popup_menu(privacy, u"Select privacy")
        if choice is not None:
            data['privacy'] = privacy[choice]
        choice = appuifw.popup_menu(attachmenttypes, u"Attach something (or cancel)")
        if choice is None:
            appuifw.note(u"Cancelled", 'info')
        else:
            appuifw.note(u"Not implemented", 'info')
        filename = time.strftime("note-%Y%m%dT%H%M%S.json")
        filename = os.path.join(self.Main.datadir, filename)
        f = open(filename, "wt")
        f.write(simplejson.dumps(data))
        f.close()


    def export_tracks(self):
        """
        Show select dialog for tracks to export and then convert
        selected tracks to KML format. Finally zip KML->KMZ file and save
        it to the root of the memory card and try to send it using bluetooth.
        """
        trackdir = os.path.join(self.Main.datadir, "track")
        trackfiles = []
        if os.path.isdir(trackdir):
            for file in os.listdir(trackdir):
                if file.endswith(".json"):
                    trackfiles.append(os.path.join(trackdir, file))
        items = [t[-13:-5] for t in trackfiles] # Get YYYYmmdd part from filename
        selected = appuifw.multi_selection_list(items, style="checkbox", search_field=1)
        if not selected:
            appuifw.note(u"None selected", 'info')
            return
        kmlexporter = UglyAndHackyKMLExporterButHeyItWorks()
        self.text.add(u"%d files selected. Processing may take a few minutes if you selected many files.\n")
        for i in selected:
            kmlexporter.filepaths.append(trackfiles[i])
        for f in kmlexporter.readfiles():
            self.text.add(u"Processing: " + f + u"\n")
            e32.ao_sleep(0.1)
            e32.ao_yield()
        self.text.add(u"Files converted, trying to send via bluetooth.\n")
        if len(selected) > 1:
            zipfile = u"track-%s-%s.kmz" % (items[selected[0]], items[selected[-1]])
        else:
            zipfile = u"track-%s.kmz" % (items[selected[0]])
        zipfile = os.path.join(self.Main.datadir, zipfile)
        kmlexporter.get_zip(zipfile)
        if self.Main.send_file_over_bluetooth(zipfile) is False:
            appuifw.note(u"Sending failed. File is saved here: %s" % zipfile, 'error')
        self.text.add(u"Google Earth file is saved in phone's memorycard:\n%s\n" % zipfile)
        self.text.add(u"You you have GoogleMaps for S60 installed in your phone, you can use phone's file manager to open saved file in it.")
