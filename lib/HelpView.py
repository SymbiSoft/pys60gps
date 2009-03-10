import Base
import appuifw
import key_codes
import e32
import time

class HelpView(Base.View):
    def __init__(self, parent, text = u""):
        Base.View.__init__(self, parent)
        self.t = appuifw.Text(u"")
        #self.fontsize = 14
        self.set_text(text)

    def activate(self):
        """Set main menu to app.body and left menu entries."""
        Base.View.activate(self)
        appuifw.app.menu = [
            (u"Close", self.parent.activate),
        ]
        appuifw.app.body = self.t

    def set_text(self, text):
        self.t.clear()
        self.t.style = appuifw.STYLE_BOLD
        self.t.color = (0,0,0)
        self.t.add(text) # NOTE: must be unicode here
