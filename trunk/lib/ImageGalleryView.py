import Base
import time
import os
import re
import appuifw
import key_codes
import e32
import graphics
import http_poster
import socket
import simplejson
import Comm

class ImageGalleryView(Base.View):

    def __init__(self, parent):
        Base.View.__init__(self, parent)
        self.active = False
        self.host = appuifw.query(u"Plok host", "text", u"www.plok.in")
        if not self.host:
            self.host = u"test.plok.in"
        self.comm = Comm.Comm(self.host, "/api/test.php")
        #self.comm = Comm.Comm("10.0.2.2:8880", "/api/test.php")
        # TODO: create way to change these
        self.tags = [u"action",u"animals",u"architecture",u"nature",u"object",u"people",u"traffic",u"view"]
        #self.visibilities = [u"PUBLIC",u"RESTRICTED:community",u"RESTRICTED:friends",u"RESTRICTED:family",u"PRIVATE"]
        self.visibilities = [u"PUBLIC",u"RESTRICTED",u"PRIVATE"]
        self.extensions = ["jpg", "png"]
        self.directories = ["C:\\Data\\Images", "E:\\Images"]
        # Other stuff
        self.last_caption = u""
        self.updating = False
        self.current_img = -1
        self.image_metadatafile = os.path.join(self.Main.datadir, "imagedata.txt")
        self.IMG_LIST = [] # Contains the metadata all images found
        self.IMG_NEW_LIST = [] # Contains 
        self.IMG_NAMES = {}
        #self.extensions = ["jpg", "mp4", "3gp", "wav", "amr"]
        self.p_ext = re.compile(r"\.("+"|".join(self.extensions)+")$", re.IGNORECASE)
        self.gmtime = time.time() + time.altzone # FIXME: altzone is broken (finland, normaltime, elisa)
        self.t = e32.Ao_timer()

    def activate(self):
        #Base.View.activate(self)
        if not self.comm.sessionid:
            self.password = appuifw.query(u"Password", "text", u"")
            if self.password:
                data, response = self.comm.login(self.Main.config["username"], self.password)
                appuifw.note(u"%s" % data["message"], 'info')

        self.timer = e32.Ao_timer()
        self.current_img = -1
        appuifw.app.exit_key_handler = self.handle_close
        self.imagemenu = []
        appuifw.app.screen = "large"
        self.canvas = appuifw.Canvas(redraw_callback=self.update)
        appuifw.app.body = self.canvas
        self.canvas.bind(key_codes.EKeyLeftArrow,lambda: self.next_image(-1))
        self.canvas.bind(key_codes.EKeyRightArrow,lambda: self.next_image(1))
        self.canvas.bind(key_codes.EKeyUpArrow,lambda: self.next_image(0))
        self.canvas.bind(key_codes.EKey0,lambda: self.sync_server())
        self.imagemenu.append((u"0. Synchronize", lambda: self.sync_server()))
        self.canvas.bind(key_codes.EKey1,lambda: self.ask_caption())
        self.imagemenu.append((u"1. Caption", lambda: self.ask_caption()))
        self.canvas.bind(key_codes.EKey2,lambda: self.ask_tags())
        self.imagemenu.append((u"2. Tags", lambda: self.ask_tags()))
        self.canvas.bind(key_codes.EKey3,lambda: self.toggle_visibility())
        self.imagemenu.append((u"3. Visibility", lambda: self.toggle_visibility()))
        self.canvas.bind(key_codes.EKeyBackspace,lambda: self.delete_current())
        self.imagemenu.append((u"C. Delete", lambda: self.delete_current()))
        self.canvas.bind(key_codes.EKeySelect,lambda: self.show_current())
        self.imagemenu.append((u"Show", lambda: self.show_current()))
        self.timer = e32.Ao_timer()
        self.load_image_metadata()
        self.timer.after(0.01, self.update_filelist)
        self.update()

    def _update_menu(self):
        """Update left options key to fit current context"""
        if self.current_img < 0:
            sort_menu=(u"Sort images by", (
                (u"time",lambda:self.sort_filelist("gmtime")),
                (u"filesize",lambda:self.sort_filelist("filesize")),
            ))
            appuifw.app.menu = [(u"Update images", self.update_filelist),
                                sort_menu,
                                (u"Search images", self.search_filelist),
                                (u"Close", self.handle_close),
                                ]
        else: # Some image is currently open
            default = [(u"Close", self.handle_close),]
            menu = default + self.imagemenu
            appuifw.app.menu = menu

    def handle_close(self):
        """
        Cancel timer and call parent view's close().
        """
        self.save_image_metadata() # FIXME: this probably is not mandatory here, save after change instead?
        self.active = False
        del(self.canvas) # Delete canvas and activate parent TODO: perhaps not needed?
        self.parent.activate()

    def next_image(self, direction):
        if len(self.IMG_LIST) == 0: 
            appuifw.note(u"No images", 'error')
            self.current_img = -1
            return
        if direction == 0:
            self.current_img = -1
        elif direction < 0:
            if self.current_img <= 0: self.current_img = len(self.IMG_LIST) - 1
            else: self.current_img = self.current_img - 1
        elif direction > 0:
            if self.current_img >= len(self.IMG_LIST) - 1: self.current_img = 0
            else: self.current_img = self.current_img + 1
        self.update()

    def exit_key_handler(self):
        if True or appuifw.query(u"Quit program", 'query') is True:
            self.save_image_metadata()
            self.running = False
            #self.lock.signal()

    def save_image_metadata(self):
        """Image cache saving"""
        #appuifw.note(u"Saving metadata of %d images to %s" % (len(self.IMG_LIST), self.image_metadatafile), 'conf')
        for i in self.IMG_LIST:
            if i.has_key("small"): # Delete image instances from IMG_LIST
                del(i["small"])
        f = open(self.image_metadatafile, "wt")
        f.write(repr(self.IMG_LIST))
        f.close()
        # print "Saved metadata of %d images to %s" % (len(self.IMG_LIST), self.image_metadatafile)

    def load_image_metadata(self):
        """Load cached image metadata from file if found"""
        if os.path.isfile(self.image_metadatafile):
            f = open(self.image_metadatafile, "rt")
            self.IMG_LIST = eval(f.read())
            f.close()
            missing = [] # Save the index of missing images to a list
            for j in range(len(self.IMG_LIST)):
                i = self.IMG_LIST[j]
                if not os.path.isfile(i["path"]):
                    missing.append(j)
                    appuifw.note(u"File %s was missing" % (i["path"]), 'error')
                else:
                    self.IMG_NAMES[i["path"]] = i    
                # TODO: check here also if image exists! Remove from the list if not!
            missing.sort()
            missing.reverse()
            for j in missing:
                self.IMG_LIST.pop(j)
            #print "Read metadata of %d images from %s.\nMissing %d" % (len(self.IMG_LIST), self.image_metadatafile, len(missing))
        else:
            pass
            #print "Cached metadata %s not found" % (self.image_metadatafile)

    def update(self, dummy=(0, 0, 0, 0)):
        if self.updating is True: return
        self.updating = True
        lheight = 16
        font = (u"Series 60 Sans", 14)
        self.canvas.clear(0x000000)
        #self.canvas.text((5, 20), u"PyS60 Image gallery", font=(u"Series 60 Sans", 20))
        #self.canvas.text((5, 200), u"Free RAM: %d kB" % (sysinfo.free_ram()/1024), font=font)
        if self.current_img < 0:
            l = 15
            self.canvas.text((5, l), u"%d total images" % (len(self.IMG_NAMES.keys())), font=font, fill=0xccccff)
            l = l + lheight
            self.canvas.text((5, l), u"%d NEW images" % (len(self.IMG_NEW_LIST)), font=font, fill=0xccccff)
            l = l + lheight
            self.canvas.text((5, l), u"Press left/right to view images", font=font, fill=0xccccff)
            l = l + lheight
            self.canvas.text((5, l), u"Press 1 to set image caption", font=font, fill=0xccccff)
            l = l + lheight
            self.canvas.text((5, l), u"Press 2 to set image tags", font=font, fill=0xccccff)
            l = l + lheight
            self.canvas.text((5, l), u"Press 3 to toggle image visibility", font=font, fill=0xccccff)
            l = l + lheight
            self.canvas.text((5, l), u"Press up to come back to this screen", font=font, fill=0xccccff)
            l = l + lheight
            self.canvas.text((5, l), u"Press 'enter' to view original image", font=font, fill=0xccccff)
        elif len(self.IMG_LIST) > 0:
            i = self.IMG_LIST[self.current_img]
            l = 15
            self.canvas.text((120, l), u"File %d/%d" % (self.current_img+1, len(self.IMG_LIST)), font=font, fill=0xccccff)
            if i.has_key("filesize"):
                self.canvas.text((5, l), u"Size %.1f kB" % (i["filesize"]/1024), font=font, fill=0xccccff)
            l = l + lheight
            if i.has_key("gmtime"):
                filetime = u"" + time.strftime("File time: %Y-%m-%dT%H:%M:%SZ ", time.localtime(i["gmtime"]))
                self.canvas.text((5, l), filetime, font=font, fill=0xccccff)
            self.canvas.text((5, 80), u"Loading...", font=font, fill=0xccccff)
            # Show metadata
            textline = 180
            lineheight = 16
            margin = 6
            # shortcut key area
            self.canvas.rectangle((margin-1, textline-15, margin+7, textline + lineheight*3+5), fill=0x101010)
            # image metadata area
            width = self.canvas.size[0] - margin
            self.canvas.rectangle((margin+8, textline-15, width, textline + lineheight*3+5), fill=0x202020)
            # Write caption
            if "caption" in i: text = i["caption"]
            else: text = u""
            self.canvas.text((margin, textline), u"1 %s" % (text), font=font, fill=0xccccff)
            textline = textline + lineheight
            # Write tags
            if "tags" in i: text = i["tags"]
            else: text = u""
            self.canvas.text((margin, textline), u"2 %s" % (text), font=font, fill=0xccccff)
            textline = textline + lineheight
            # Write visibility
            if "visibility" in i: text = i["visibility"]
            else: text = u""
            self.canvas.text((margin, textline), u"3 %s" % (text), font=font, fill=0xccccff)
            textline = textline + lineheight
            # Sync text
            if "status" in i: text = i["status"]
            else: text = u"not sync'ed"
            self.canvas.text((margin, textline), u"0 Sync with server (%s)" % text, font=font, fill=0xccccff)
            textline = textline + lineheight
            # Show image
            thumbs = self.find_thumbnails(i["path"])
            if i.has_key("small"):
                small = i["small"]
            elif thumbs.has_key("170x128"): # pregenerated thumbnail was found
                try:
                    small = graphics.Image.open(thumbs["170x128"]["path"])
                except:
                    small = graphics.Image.new((170,128))
            else: # generate and save thumbnail
                i["small"] = self.save_thumbnail(i["path"], (170, 128))
                small = i["small"]
                #image = graphics.Image.open(i["path"])
                #small = image.resize((170, 128), keepaspect=1)
                #del(image)
            try:
                self.canvas.blit(small, target=(5, 35))
            except:
                appuifw.note(u"Could not show thumbnail", 'error')
                raise
            #del(small)
        else:
            self.canvas.text((5, 80), u"No images", font=font, fill=0xccccff)
        self._update_menu()
        self.updating = False
        
    def blit_image(self, canvas, img, data):
        self.canvas.clear()
        self.update()
        self.canvas.blit(img, target=(5, 30))
        self.canvas.text((100, 10), u"%.1f kB" % (data["filesize"]/1024), font=(u"Series 60 Sans", 10), fill=0x333333)
        if "caption" in data:
            canvas.text((5, 100), data["caption"], font=(u"Series 60 Sans", 10), fill=0xccccff)
        e32.ao_sleep(0.01) # Wait until the canvas has been drawn

    def store_filenames_cb(self, arg, dirname, names):
        # Do not check folders like "_PAlbTN"
        if dirname.startswith("_"): return
        for name in names:
            if self.p_ext.search(name):
                IMG = {}
                IMG["visibility"] = "PRIVATE"
                IMG["path"] = os.path.join(dirname,name) # Full path
                stat = os.stat(IMG["path"])
                IMG["filesize"] = stat[6] # File size in bytes
                IMG["gmtime"] = stat[8] # Modification time
                if IMG["filesize"] == 0:
                    appuifw.note(u"Deleting 0 file", 'info')
                    del self.IMG_NAMES[IMG["path"]]
                if self.IMG_NAMES.has_key(IMG["path"]): 
                    continue # Already found
                # Ignore images older than ...
                #if IMG["gmtime"] < self.gmtime-10*24*60*60: continue #print "wanha", IMG["path"], gmtime-IMG["gmtime"]
                #f = open(IMG["path"], "rb")
                #idata = f.read()
                #f.close()
                # Calculate md5sum
                #IMG["md5"] = md5.new(idata).hexdigest() # md5sum
                if IMG["filesize"] > 0:
                    self.IMG_LIST.append(IMG)
                    self.IMG_NEW_LIST.append(IMG)
                    self.IMG_NAMES[IMG["path"]] = IMG

    def update_filelist(self):
        for dir in self.directories:
            if os.path.isdir(dir):
                os.path.walk(dir, self.store_filenames_cb, None)

    def _get_thumbnail_path_components(self, imagefilename):
        # Path and filename settings
        basename = os.path.basename(imagefilename)
        dirname = os.path.dirname(imagefilename)
        thumbbasedir = os.path.join(dirname, "_PAlbTN")
        return basename, dirname, thumbbasedir

    def find_thumbnails(self, imagefilename):
        """Find all pregenerated thumbnail files for 'imagefilename'."""
        basename, dirname, thumbbasedir = self._get_thumbnail_path_components(imagefilename)
        thumbnails_available = {}
        if not os.path.isdir(thumbbasedir):
            return thumbnails_available # There was no "_PAlbTN", so there are no thumbnails either
        thumbinstances = os.listdir(thumbbasedir) # Thumbnails are saved into directories like "56x42", "170x120" etc
        for thumb in thumbinstances:
            thumbinstance = os.path.join(thumbbasedir, thumb, basename + "_" + thumb) # E.g. "030820083076.jpg_170x128"
            if os.path.isfile(thumbinstance):
                width, height = thumb.split("x") # e.g. "178x120" -> (178, 120)
                thumbnails_available[thumb] = {"path":thumbinstance, "width":width, "height":height}
        return thumbnails_available
    
    def save_thumbnail(self, imagefilename, size=(170,128)):
        """
        Create resized version of imagefilename and save it into _PAlbTN-thumbnail directory.
        Return generated image instance.
        """
        basename, dirname, thumbbasedir = self._get_thumbnail_path_components(imagefilename)
        try: # TODO: dummy try/except here for now, in the future error logging here
            image = graphics.Image.open(imagefilename)
        except:
            appuifw.note(u"Could not open %s" % (imagefilename), 'error')
            self.delete_current()
            self.current_img = 0
            #self.IMG_LIST.pop(self.current_img)
            return
            #appuifw.note(u"TODO: ask here if user wants to delete it.", 'info')
            #raise
        thumb = "%dx%d" % (size)
        thumbdir = os.path.join(thumbbasedir, thumb)
        if not os.path.isdir(thumbdir):
            os.makedirs(thumbdir)
        thumbinstance = os.path.join(thumbdir, basename + "_" + thumb) # E.g. "030820083076.jpg_170x128"
        small = image.resize(size, keepaspect=1)
        small.save(thumbinstance, format="JPEG", quality=60)
        return small

    def ask_caption(self):
        if self.current_img < 0 or len(self.IMG_LIST) == 0: 
            appuifw.note(u"No image selected", 'error')
            return
        if self.IMG_LIST[self.current_img].has_key("caption"):
            old_caption = self.IMG_LIST[self.current_img]["caption"]
        else: old_caption = self.last_caption
        caption = appuifw.query(u"Caption", "text", old_caption)
        if caption is not None:
            self.IMG_LIST[self.current_img]["caption"] = caption
            self.last_caption = caption

    def ask_tags(self):
        """Test function to select file tags from a selection list."""
        if self.current_img < 0 or len(self.IMG_LIST) == 0: 
            appuifw.note(u"No image selected", 'error')
            return
        # TODO: editable tags
        selected = appuifw.multi_selection_list(self.tags, style="checkbox", search_field=1)
        # appuifw.note(u"Selected %s" % str(selected), 'conf')
        self.IMG_LIST[self.current_img]["tags"] = ','.join([self.tags[i] for i in selected]) # Ah, I love python
        self.update()

    def toggle_visibility(self):
        """Test function to select file tags from a selection list."""
        if self.current_img < 0 or len(self.IMG_LIST) == 0: 
            appuifw.note(u"No image selected", 'error')
            return
        try:
            i = self.visibilities.index(self.IMG_LIST[self.current_img]["visibility"])
        except:
            i = 0
        if i < len(self.visibilities)-1:
            i = i + 1
        else:
            i = 0
        self.IMG_LIST[self.current_img]["visibility"] = self.visibilities[i]
        self.update()

    def update_metadata(self):
        """Send image to the server. Initial/test version."""
        if self.current_img >= 0:
            current_img = self.IMG_LIST[self.current_img]
            current_img["status"] = u"synchronizing"
            params = {"operation" : "update_file",
                      "sender" : self.Main.config["username"].encode("utf-8"), 
                      }
            for key in ["caption", "tags", "visibility", "id"]:
                if key in current_img:
                    params[key] = current_img[key].encode("utf-8")
            ip = appuifw.InfoPopup()
            ip.show(u"Updating metadata...", (50, 50), 60000, 100, appuifw.EHLeftVTop)
            data, response = self.comm._send_request("update_file", params)
            ip.hide()
            #print data, type(data)
            if "status" in data and data["status"] == "ok":
                current_img["status"] = u"synchronized"
                notetype = "info"
            else:
                current_img["status"] = u"sync failed"
                notetype = "error"
            appuifw.note(data["message"], notetype)

    def sync_server(self):
        """Send image to the server. Initial/test version."""
        if self.current_img >= 0:
            current_img = self.IMG_LIST[self.current_img]
            # TODO: split this function to upload the file or update metadata
            if "id" in current_img:
                self.update_metadata()
                return
            if "status" in current_img and current_img["status"] == u"synchronized":
                appuifw.note(u"Already uploaded", 'info')
                return
            if self.Main.apid == None:
                self.Main.apid = socket.select_access_point()
            if self.Main.apid:
                self.apo = socket.access_point(self.Main.apid)
                socket.set_default_access_point(self.apo)
                self.apo.start()
                
            if appuifw.query(u'Send image really? There is no undo.', 'query') is None:
                return
            current_img["status"] = u"synchronizing"
            filename = current_img["path"]
            f=open(filename, 'r')
            filedata = f.read()
            f.close()
            # Create "files"-list which contains all files to send
            files = [("newfile", os.path.basename(filename), filedata)]
            params = {"operation" : "send_file",
                      "sender" : self.Main.config["username"].encode("utf-8"), 
                      }
            for key in ["caption", "tags", "visibility"]:
                if key in current_img:
                    params[key] = current_img[key].encode("utf-8")
                      
            ip = appuifw.InfoPopup()
            ip.show(u"Uploading file...", (50, 50), 60000, 100, appuifw.EHLeftVTop)
            data, response = self.comm._send_multipart_request("send_file", 
                                                               params, files)
            ip.hide()
            # print data, type(data)
            if "status" in data and data["status"] == "ok":
                current_img["status"] = u"synchronized"
                notetype = "info"
            else:
                current_img["status"] = u"sync failed"
                notetype = "error"
            if "id" in data:
                current_img["status"] = data["id"]
                current_img["id"] = data["id"]
            appuifw.note(data["message"], notetype)

    def delete_current(self):
        """Delete current image permanently."""
        if (self.current_img >= 0 and 
           appuifw.query(u'Delete current image %d/%d permanently?' % (self.current_img+1, len(self.IMG_LIST)), 'query') is True):
            os.remove(self.IMG_LIST[self.current_img]["path"])
            self.IMG_LIST.pop(self.current_img)
            self.current_img = self.current_img - 1
            e32.ao_sleep(0.05) # let the query popup disappear before update
            self.update()

    def show_current(self):
        """Call function which shows current original image file"""
        if self.current_img >= 0:
            self.show_file(self.IMG_LIST[self.current_img]["path"])
            self.update()

    def show_file(self, path):
        """
        Show current image with content_handler. 
        Return False if file was not found, otherwise return True.
        """
        if not os.path.isfile(path):
            appuifw.note(u"File %s not found" % (path), 'error')
            return False
        else:
            lock=e32.Ao_lock()
            content_handler = appuifw.Content_handler(lock.signal)
            content_handler.open(path)
            lock.wait()
            return True

    def sort_filelist(self, key):
        appuifw.note(u"Sorry, sorting by %s is not implemented yet" % (key), 'info')

    def search_filelist(self):
        search = appuifw.query(u"Search string", "text", u"")
        p_search = re.compile(search, re.IGNORECASE)
        found = 0
        for i in range(len(self.IMG_LIST)):
            if self.IMG_LIST[i].has_key("caption") and p_search.search(self.IMG_LIST[i]["caption"]):
                found = found + 1
        appuifw.note(u"Sorry, searching is not implemented yet. But %d found anyway!" % (found), 'info')

    # TODO:
    def search_without_caption(self):
        """Return a list of photos without caption"""
        pass
