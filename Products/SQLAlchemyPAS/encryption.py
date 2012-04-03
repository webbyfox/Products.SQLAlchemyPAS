from zope.interface import Interface, implements
import hashlib
#from md5 import md5
#import sha 

class IEncryptionPolicy(Interface):

    def encryptPassword(password):
        """ return encrypted password """

class NoEncryption(object):

    implements(IEncryptionPolicy)

    def encryptPassword(self, password):
        return password


class MD5HexEncryption(object):

    implements(IEncryptionPolicy)

    def encryptPassword(self, password):
        return hashlib.md5(password).hexdigest()


class SHAHexEncryption(object):

    implements(IEncryptionPolicy)

    def encryptPassword(self, password):
        return hashlib.sha1(password).hexdigest()
    