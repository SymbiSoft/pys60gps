# $Id$

import pyDes
import marshal
import os

class SecretManager:
    def __init__(self, basedir=u"/tmp", realm=u""):
        self.master_password = None
        self.password_dir = os.path.join(basedir, "secretmanager")
        if not os.path.isdir(self.password_dir):
            os.makedirs(self.password_dir)
        if not realm:
            realm = u"secret"
        self.secret_file = os.path.join(self.password_dir, u"%s.enc" % realm)
        self.crypto = None
        self.passwords = {}
        self.padmode = pyDes.PAD_PKCS5
    
    def initialize_des(self):
        self.crypto = pyDes.triple_des(self.master_password)

    def load(self):
        f = open(self.secret_file, "rb")
        self.passwords = marshal.loads(self.crypto.decrypt(f.read(), padmode=self.padmode))
        f.close()

    def save(self):
        f = open(self.secret_file, "wb")
        f.write(self.crypto.encrypt(marshal.dumps(self.passwords), padmode=self.padmode))
        f.close()

if __name__ == '__main__':
    p = SecretManager(realm=u"plok")
    p.master_password = "1234567812345678"
    p.initialize_des()
    p.passwords["twitteri"] = "jjeejee"
    p.save()
    p.load()
    print p.passwords
