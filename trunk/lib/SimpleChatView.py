import Base
import appuifw
import key_codes
import e32
import time
from HelpView import HelpView

class SimpleChatView(Base.View):
    """
    TODO: 
    - automatic update
    - save font size in settings
    - send "limit" parameter, allow user define it from menu
    - net chat, too
    """
    def __init__(self, parent):
        Base.View.__init__(self, parent)
        self.chatmessages = []
        if "simplechat_fontsize" in self.Main.config:
            self.fontsize = self.Main.config["simplechat_fontsize"]
        else:
            self.fontsize = 14
        self.delimiter = u">>> "
        self.t = appuifw.Text(u"")
        self.t.bind(key_codes.EKeySelect, self.send_chatmessage)
        self.help = HelpView(self, 
            u"""To chat with a member of your community choose "Send message" and start typing.
             
When you have finished, choose "OK" and your message will be sent immediately.
""")

    def get_chatmessages(self):
        ip = appuifw.InfoPopup()
        ip.show(u"Loading chatmessages", (50, 50), 60000, 100, appuifw.EHLeftVTop)
        data, response = self.Main.comm._send_request("get_simplechatmessages", {})
        ip.hide()
        # Check we got valid response
        if isinstance(data, dict) is False:
            appuifw.note(u"Invalid response from server", 'error')
        elif data["status"].startswith("error"):
            if "message" not in data:
                data["message"] = u"Unknown error in response"
            appuifw.note(u"%s" % data["message"], 'error')
        elif (data["status"] == "ok" and 
              "chatmessages" in data):
            self.chatmessages = data["chatmessages"]
        else:
            appuifw.note(u"Unknown error in response", 'error') 
        self.update_message_view()

    def send_chatmessage(self):
        # First try to find inline message
        text = self.get_message()
        # If not found, ask with appuifw.query
        if not text:
            text = appuifw.query(u"Message (max 80 chr)", "text", u"")
            if not text:
                return
        ip = appuifw.InfoPopup()
        ip.show(u"Sending message", (50, 50), 60000, 100, appuifw.EHLeftVTop)
        data, response = self.Main.comm._send_request("send_simplechatmessage", 
                                                      {"text": text,
                                                       "sender" : self.Main.config["username"]})
        ip.hide()
        # Check we got valid response
        if isinstance(data, dict) is False:
            appuifw.note(u"Invalid response from server", 'error')
        elif data["status"].startswith("error"):
            if "message" not in data:
                data["message"] = u"Unknown error in response"
            appuifw.note(u"%s" % data["message"], 'error')
        elif (data["status"] == "ok" and 
              "chatmessages" in data):
            self.chatmessages = data["chatmessages"]
        else:
            appuifw.note(u"Unknown error in response", 'error') 
        self.update_message_view()

    def add_text(self, timestamp, user, text):
        self.t.font = (u"dense", self.fontsize)
        self.t.style = appuifw.STYLE_BOLD
        self.t.color = (200,0,0)
        self.t.add(u"%s: " % (user)) # NOTE: must be unicode here
        self.t.style = 0
        self.t.add(u"%s\n" % (timestamp)) # NOTE: must be unicode here
        self.t.color = (0,0,0)
        self.t.add(u">> %s\n" % (text))
    
    def get_message(self):
        parts = self.t.get().split(self.delimiter)
        #appuifw.note(u"%d" % len(parts), 'error')
        if len(parts) > 1:
            message = parts[-1].strip()
        else:
            self.update_message_view()
            message = None
        # Avoid crash when T9 is on and the last word is underlined
        self.t.add(u"\n") 
        return message

    def update_message_view(self):
        self.t.clear()
        self.menu_entries = []
        for chatmessage in self.chatmessages:
            self.add_text(chatmessage["sendtime"], 
                          chatmessage["sender"], chatmessage["text"])
        self.t.font = (u"dense", int(self.fontsize/4*3))
        self.t.add(u"--- Localtime: %s ---\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
        self.t.font = (u"dense", self.fontsize)
        self.t.add(self.delimiter)
        appuifw.app.body = self.t

    def activate(self):
        """Set main menu to app.body and left menu entries."""
        Base.View.activate(self)
        if len(self.chatmessages) == 0:
            self.get_chatmessages()
        self.update_message_view()
        appuifw.app.menu = [
            (u"Send chat message",self.send_chatmessage),
            (u"Refresh chat",self.get_chatmessages),
            (u"Increase font size", lambda:self.set_fontsize(2)),
            (u"Decrease font size", lambda:self.set_fontsize(-2)),
            (u"Set font size", self.set_fontsize),
            (u"Help",self.help.activate),
            (u"Close", self.parent.activate),
        ]

    def set_fontsize(self, fs = 0):
        if fs == 0:
            fs = appuifw.query(u"Font size","number", self.fontsize)
        else:
            fs = self.fontsize + fs
        if fs:
            if fs < 6: fs = 6
            if fs > 32: fs = 32
            self.fontsize = fs
            self.update_message_view()
            # FIXME this doesn't unfortunately work: 
            # settings.ini will be overwritten in every start 
            #self.Main.config["simplechat_fontsize"] = fs
            #self.Main.save_config()
        
