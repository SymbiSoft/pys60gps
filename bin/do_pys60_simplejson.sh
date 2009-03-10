#!/bin/bash
# Aapo Rista 2009
# Usage: download and extract simplejson 2.0.9 and execute this file in 
# the directory which contains FILES listed below:

FILES="decoder.py encoder.py scanner.py __init__.py"
TARGET=simplejson.py
TEST_SCRIPT=test_simplejson.py

# File header
echo "'''
PyS60 1.4.x compatible simplejson

2009 Created by Aapo Rista (ispired by Marcelo Barros) from 
simplejson 2.0.x with an ugly shell script. (But hey, it works!)
'''

from __future__ import generators
basestring = (unicode, str)

" > ${TARGET}

grep -h -e ^__author__ ${FILES} | sort -u >> ${TARGET}
# Unify imports
grep -h -e ^import ${FILES} | sort -u >> ${TARGET}

# Remove docstrings and imports
perl -ne 'push(@l, $_);END{$a=join("", @l); $a=~s/r?""".*?"""//msg;print $a}' \
   decoder.py encoder.py scanner.py __init__.py | \
   grep -v \
        -e ^from \
        -e ^import \
        -e ^__author__ \
        >> ${TARGET}

# Python 2.2 does not support ::-notation (every other item of a list)
perl -i -pe 's/_BYTES = .*\]$/_BYTES = "00008FF70000000000000FF700000000".decode("hex")/' ${TARGET}
# Delele all single line __all__ definitions
perl -i -pe 's/^__all__ = .*\]$//' ${TARGET}

# Thats it!

# Very simple test case:
echo '
import simplejson
data = { 
"foo" : u"\xe4", 
"bar" : 3.14159,
"baz" : "hello!",
}   
    
json = simplejson.dumps(data)
print json, data["foo"]
data = simplejson.loads(json)
print data, data["foo"]
' > ${TEST_SCRIPT}
