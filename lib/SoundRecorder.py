import os
import time
import appuifw
import e32
import audio
import key_codes

class SoundRecorder():
    __id__ = u'$Id: p2pfusion-mobile.py 1455 2009-04-23 13:29:17Z 08rista $'

    def __init__(self, soundfile = u"E:\\testsound.wav"):
        self.lock = e32.Ao_lock()
        self.running = True
        self.recording = False
        self.time = 0.0
        self.focus = True
        appuifw.app.focus = self.focus_callback # Set up focus callback
        self.canvas = None
        self.sound = None
        self.timer = e32.Ao_timer()
        self.soundfile = soundfile

    def focus_callback(self, bg):
        """Callback for appuifw.app.focus"""
        self.focus = bg

    def exit_key_handler(self):
        if appuifw.query(u"Quit program", 'query') is True:
            self.running = False
            self.timer.cancel()
            self.lock.signal()

    def activate(self):
        self.canvas = appuifw.Canvas(redraw_callback=self.update, resize_callback=self.update)
        self.canvas.bind(key_codes.EKeySelect, self.record)
        self.canvas.bind(key_codes.EKeyBackspace, self.delete)
        
        appuifw.app.body = self.canvas
        appuifw.app.exit_key_handler = self.exit_key_handler
        
    def run(self):
        self.activate()
        self.lock.wait()

    def delete(self):
        # TODO: offer undo option, move file at first to .old or something
        if self.sound:
            self.sound.stop()
        if os.path.isfile(self.soundfile):   
            os.unlink(self.soundfile)
        self.sound = None
    
    def update(self, dummy=(0, 0, 0, 0)):
        if self.canvas is None: return # Canvas is not initialized yet
        self.canvas.clear()
        self.canvas.text((5, 20), u"PyS60 Sound Recorder", font=(u"Series 60 Sans", 20))
        self.canvas.text((5, 40), u"%s" % time.strftime("%H:%M:%S"), font=(u"Series 60 Sans", 20))
        progress = u"0.0"
        if self.sound is None:
            state = u"NO SOUND"
        elif self.sound.state() == audio.ENotReady:
            state = u"NOT READY" 
        elif self.sound.state() == audio.EPlaying:
            state = u"PLAY" 
            cur = self.sound.current_position() / 1000000.0
            dur = self.sound.duration() / 1000000.0
            per = cur / dur * 100
            progress = u"%.1f s / %.1f s (%d %%)" % (cur, dur, per)
        elif self.sound.state() == audio.ERecording:
            state = u"RECORD" 
            progress = u"%.1f s" % (self.sound.current_position() / 1000000.0)
        elif self.sound.state() == audio.EOpen:
            state = u"STOP/PAUSE" 
            #duration = u"%.1f s" % (self.sound.duration() / 1000000.0)
            duration = u"%.1f s" % (self.sound.duration())
        self.canvas.text((5, 60), state, font=(u"Series 60 Sans", 20))
        self.canvas.text((5, 80), progress, font=(u"Series 60 Sans", 20))
        self.timer.cancel()
        self.timer.after(0.1, self.update)

    def record(self):
        if self.sound is None:
            if os.path.isfile(self.soundfile):
                choice = appuifw.popup_menu([u"Play", u"Replace", u"Append"], u"Sound file exists:")
                if choice is None:
                    return
                elif choice == 1:
                    self.delete()
            self.sound = audio.Sound.open(self.soundfile)
            self.sound.record()
        elif self.sound.state() == audio.ERecording or self.sound.state() == audio.EPlaying:
            self.sound.stop()
        elif self.sound.state() == audio.EOpen:
            self.sound.play()

if __name__=='__main__':
    old_body = appuifw.app.body
    myApp = SoundRecorder()
    myApp.run()
    appuifw.app.body = old_body
