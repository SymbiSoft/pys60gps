# http://blogs.forum.nokia.com/blog/marcelo-barros-de-almeidas-forum-nokia-blog/2010/02/22/fixing-mktime-for-pys60-2.0
# mktimefix.py stub module
from time import *
#from calendar import timegm
import calendar
# fix for mktime
mktime = lambda time_tuple: calendar.timegm(time_tuple) + timezone

