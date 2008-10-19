# -*- coding: iso-8859-1 -*-
# $Id$

import httplib

"""
A scripted web client that will post data to a site as if from a 
form using ENCTYPE="multipart/form-data". This is typically used 
to upload files, but also gets around a server's (e.g. ASP's) 
limitation on the amount of data that can be accepted via a 
standard POST (application/x-www-form-urlencoded).
http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/146306
"""

__version__ = u'$Id$'
user_agent = "http_poster.py"

def post_multipart(host, selector, fields, files, headers={}):
    """
    Post fields and files to an http host as multipart/form-data.
    fields is a sequence of (name, value) elements for regular form fields.
    files is a sequence of (name, filename, value) elements for data to be uploaded as files
    Return the server's response page.
    """
    content_type, body = encode_multipart_formdata(fields, files)
    h = httplib.HTTPConnection(host)
    if not headers.has_key('User-Agent'):
        headers['User-Agent'] = user_agent
    if not headers.has_key('Content-Type'):
        headers['Content-Type'] = content_type
    h.request('POST', selector, body, headers)
    res = h.getresponse()
    status, reason, data = res.status, res.reason, res.read()
    h.close()
    return status, reason, data

def encode_multipart_formdata(fields, files):
    """
    fields is a sequence of (name, value) elements for regular form fields.
    files is a sequence of (name, filename, value) elements for data to be uploaded as files
    Return (content_type, body) ready for httplib.HTTP instance
    """
    BOUNDARY = '----------ThIs_Is_tHe_bouNdaRY_$'
    CRLF = '\r\n'
    L = []
    # FIXME: key/value should be value.encode('latin-1') :d here or something
    # Really FIXME: if some of elements in L is unicode, resulting
    # string is also unicode and if it contains non valid charachters
    # Join() raises an exception
    for (key, value) in fields:
        L.append('--' + BOUNDARY)
        L.append('Content-Disposition: form-data; name="%s"' % key)
        L.append('')
        L.append("%s" % value) # DO NOT put value directly to L
    for (key, filename, value) in files:
        L.append('--' + BOUNDARY)
        L.append('Content-Disposition: form-data; name="%s"; filename="%s"' % (key, filename))
        L.append('Content-Type: %s' % get_content_type(filename))
        L.append('')
        L.append("%s" % value) # DO NOT put value directly to L
    L.append('--' + BOUNDARY + '--')
    L.append('')
    body = CRLF.join(L)
    content_type = 'multipart/form-data; boundary=%s' % BOUNDARY
    return content_type, body

def get_content_type(filename):
    # FIXME Some kind of contenttype guessing here!
    return 'application/octet-stream'
    #return mimetypes.guess_type(filename)[0] or 'application/octet-stream'

if __name__ == "__main__":
    import time
    import sys
    host = "http://127.0.0.1:8000"
    script = "/dump/"
    if len(sys.argv) <= 2:  # Print error if less than 2 arguments
        print "Usage %s <URL> <filename>" % sys.argv[0]
        print "Example:\n%s http://%s%s file.xml" % (sys.argv[0], host, script)
        sys.exit()
    # Parse host and script variables
    url = sys.argv[1]
    urlparts = url.split('/')
    if len(urlparts) >= 3:
        host = urlparts[2]
        script = "/%s" % "/".join(urlparts[3:])
    # Read file
    filename = sys.argv[2]
    f=open(filename, 'r')
    filedata = f.read()
    f.close()
    
    # Create "files"-list which contains all files to send
    #files = [("plokfile", filename, plokdata)]
    files = [("file1", filename, filedata)]
    fields = [("param1", "foo"), ("param2", "bar")]
    try:
        ret = post_multipart(host, script, fields, files)
        print ret[0]
        print ret[2]
    except:
        raise
