# -*- coding: utf8 -*-
# $Id$
import Base
import appuifw
import key_codes
import e32
import os
import simplejson
from HelpView import HelpView
from CommWrapper import CommWrapper
import codecs
import inbox

if e32.pys60_version_info[:2] >= (1, 9):
    import mktimefix as time
else:
    import time

from UglyKML import UglyAndHackyKMLExporterButHeyItWorks

QUICKNOTE_PREFIX = u'quicknote-'

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
        self.quicknotedir = os.path.join(self.Main.datadir, u'quicknote')
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
            (u"Quick note",self.create_simple_memo),
            (u"Export Tracks",self.export_tracks),
            (u"Send notes",self.send_notes),
            (u"Export SMS",self.export_sms),
            (u"Help",self.help.activate),
            (u"Close", self.parent.activate),
        ]
        appuifw.app.body = self.text
        self.text.add(u"Select action from the menu\nValitse menusta toiminto\n")

    def create_simple_memo(self):
        """
        Create an object which contains all possible information
        of user's current environment and may contain
        one (audio, video or photo) file attachment.
        """
        data = {}
        # Create timestamps:
        # TODO: to a function
        current_time = time.time() # -> epoch timestamp
        current_gmtime = time.mktime(time.gmtime()) # -> epoch timestamp
        timezone_offset = abs(int(current_time - current_gmtime)) # e.g. EET -> 7200
        if (current_time - current_gmtime) < 0:
            prefix = '-'
        else:
            prefix = '+'
        timezone_offset_hours = timezone_offset / 60 / 60
        timezone_offset_minutes = (timezone_offset / 60) % 60
        tz_str = u'%s%02d' % (prefix, timezone_offset_hours)
        if timezone_offset_minutes != 0:
            tz_str += u':%02d' % timezone_offset_minutes

        data['localtime'] = time.strftime("%Y-%m-%dT%H:%M:%S" + tz_str,
                                          time.localtime(current_time))
        data['gmtime'] = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                          time.localtime(current_gmtime))
        if self.Main.last_fix:
            data['position'] = self.Main.last_fix.copy()
        else:
            data['position'] = None
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
        data['text'] = appuifw.query(u"New quick note:", "text", u"")
        if data['text']:
            filename = QUICKNOTE_PREFIX + time.strftime("%Y%m%dT%H%M%S.json")
            filename = os.path.join(self.Main.datadir, filename)
            f = open(filename, "wt")
            f.write(simplejson.dumps(data))
            f.close()
        else:
            appuifw.note(u"Cancelled", 'info')

    def send_notes(self):
        quicknote_files = []
        i = 0
        # Create dir for sent quicknotes
        if not os.path.exists(self.quicknotedir):
            os.makedirs(self.quicknotedir)
        for file in os.listdir(self.Main.datadir):
            if file.startswith(QUICKNOTE_PREFIX):
                filename = os.path.join(self.Main.datadir, file)
                f = open(filename, 'rb')
                filedata = f.read()
                f.close()
                # Create "files"-list which contains all files to send
                quicknote_files.append(("quicknote_file%d" % i, file, filedata))
                i += 1
                newfilename = os.path.join(self.quicknotedir, file)
                os.rename(filename, newfilename)

        #appuifw.note(u'%d' % len(quicknote_files), 'info')
        if quicknote_files:
            params = {"operation" : "send_quicknote_files",
                      "sender" : self.Main.config["username"].encode("utf-8"),
                      }
            data, response = self.cw.send_request("send_quicknote_files",
                                                  params = params,
                                                  files = quicknote_files,
                                                  infotext = u"Uploading quick notes...")
            if "status" in data and data["status"] == "ok":
                notetype = "info"
            else:
                notetype = "error"
            appuifw.note(data["message"], notetype)


    def export_sms(self):
        """
        Dump all messages from inbox and sent messages to 2 files.
        Don't know what happens if there are binaries (MMS, bluetooth files).
        """
        def _jsonize_msg(box, i):
            j = {
                'address': box.address(i),
                'time': box.time(i),
                'isotime': time.strftime('%Y%m%dT%H%M%S', time.localtime(box.time(i))),
                'content': box.content(i),
            }
            return simplejson.dumps(j)
        # Dump sent sms
        box = inbox.Inbox(inbox.ESent)
        msg = box.sms_messages()
        filename = 'sms_sent_' + time.strftime("%Y%m%dT%H%M%S.json")
        filename = os.path.join(self.Main.datadir, filename)
        appuifw.note(u"Dumping sent SMS to %s" % filename, 'info')
        f = codecs.open(filename, 'w', 'utf8')
        for i in msg:
            f.write(_jsonize_msg(box, i) + '\n')
        f.close()

        # Dump recieved sms
        box = inbox.Inbox()
        msg = box.sms_messages()
        filename = 'sms_in_' + time.strftime("%Y%m%dT%H%M%S.json")
        filename = os.path.join(self.Main.datadir, filename)
        appuifw.note(u"Dumping recieved SMS to %s" % filename, 'info')
        f = codecs.open(filename, 'w', 'utf8')
        for i in msg:
            f.write(_jsonize_msg(box, i) + '\n')
        f.close()
        appuifw.note(u"Done", 'info')

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
            self.text.add(u"Adding %s\n" % trackfiles[i])
            kmlexporter.filepaths.append(trackfiles[i])
        e32.ao_sleep(1.0)
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
