import Base
import appuifw
import key_codes
import e32
import time
from HelpView import HelpView
from CommWrapper import CommWrapper

class SimpleChatView(Base.View):
    """
    TODO: 
    - automatic update
    - save font size in settings
    - send "limit" parameter, allow user define it from menu
    - net chat, too
    """
    def __init__(self, parent, comm = None):
        Base.View.__init__(self, parent)
        if comm is None:
            self.comm = self.Main.comm
        else:
            self.comm = comm
        self.cw = CommWrapper(self.comm)
        self.chatmessages = []
        if "simplechat_fontsize" in self.Main.config:
            self.fontsize = self.Main.config["simplechat_fontsize"]
        else:
            self.fontsize = 14
        self.delimiter = u">>> "
        self.text = appuifw.Text(u"")
        self.text.bind(key_codes.EKeySelect, self.send_chatmessage)
        self.help = HelpView(self, 
            u"""To chat with a member of your community choose "Send message" and start typing.
             
When you have finished, choose "OK" and your message will be sent immediately.
""")

    def get_chatmessages(self):
        data, response = self.cw.send_request("get_simplechatmessages", 
                                              infotext=u"Loading chatmessages")
        if (data["status"] == "ok" and 
              "chatmessages" in data):
            self.chatmessages = data["chatmessages"]
        self.update_message_view()

    def send_chatmessage(self):
        # First try to find inline message
        text = self.get_message()
        # If not found, ask with appuifw.query
        if not text:
            text = appuifw.query(u"Message (max 80 chr)", "text", u"")
            if not text:
                return
        params = {"text": text,
                  "sender" : self.comm.username}
        data, response = self.cw.send_request("send_simplechatmessage", 
                                              infotext=u"Sending message...",
                                              params=params)
        if (data["status"] == "ok" and 
            "chatmessages" in data):
            self.chatmessages = data["chatmessages"]
        else:
            if message in "data":
                message = data["message"]
            else:
                message = u"Unknown error in response"
            appuifw.note(message, 'error')
        self.update_message_view()

    def add_text(self, textarea, timestamp, user, text):
        textarea.font = (u"dense", self.fontsize)
        textarea.style = appuifw.STYLE_BOLD
        textarea.color = (200,0,0)
        textarea.add(u"%s: " % (user)) # NOTE: must be unicode here
        textarea.style = 0
        textarea.add(u"%s\n" % (timestamp)) # NOTE: must be unicode here
        textarea.color = (0,0,0)
        textarea.add(u">> %s\n" % (text))
    
    def get_message(self):
        parts = self.text.get().split(self.delimiter)
        #appuifw.note(u"%d" % len(parts), 'error')
        if len(parts) > 1:
            message = parts[-1].strip()
        else:
            self.update_message_view()
            message = None
        # Avoid crash when T9 is on and the last word is underlined
        self.text.add(u"\n") 
        return message

    def update_message_view(self):
        new_text = appuifw.Text(u"")
        #self.text.clear()
        self.menu_entries = []
        for chatmessage in self.chatmessages:
            self.add_text(new_text,
                          chatmessage["sendtime"], 
                          chatmessage["sender"], chatmessage["text"])
        new_text.font = (u"dense", int(self.fontsize/4*3))
        new_text.add(u"--- Localtime: %s ---\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
        new_text.font = (u"dense", self.fontsize)
        appuifw.app.body = self.text = new_text
        self.text.bind(key_codes.EKeySelect, self.send_chatmessage)
        new_text.add(self.delimiter)

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
        
