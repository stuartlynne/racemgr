  
  
  
import sys              
import datetime
getTimeNow = datetime.datetime.now                                                       

def log(s):
    print('%s %s' % (getTimeNow().strftime('%H:%M:%S'), s.rstrip()), file=sys.stderr)
