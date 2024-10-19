import sys 
import json
import time
import datetime
import operator
import websocket
import traceback

from .threadex import ThreadEx
from .utils import log


#-----------------------------------------------------------------------
#
# This program connects to CrossMgr's "announcer" websocket and shows
# a top 5 for each category of a live race.
#
# A good way to see it in action is to start CrossMgr then do "Tools|Simulation".
# Then start LiveRaceUpdate.py on the same machine.
# It processes the baseline and update messages from CrossMgr to show the top 5
# for each category (similar to the Announcer screen).
# The program can be used as a basis for real time external interfaces to
# CrossMgr like leaderboards, etc.
#
# There is no "polling" in the interface.
#
# Rather, after any race changes, CrossMgr sends an update message over the websocket.
# An update message is in RAM format (Remove, Add, Modify) (like CRUD, but everything renamed and no "R" ;).
# CrossMgr doesn't send an event on every race change, rather, it waits a second or two and
# bundles everyting one message.  This improves performance and eliminates update "nervousness".
#
# Of course, an update message can only be applied *if* you are on the current
# version of the race data.  This is indicated by the versionCount.
# If your local versionCount is one less than the update's versionCount, it can be
# applied safely.
# If not, you need to request a new baseline.  This retrieves all the information.
#
# There is an incredible amount of data in the "info" and "categoryDetails".
# I suggest printing it out to see what it there.
# This program only uses name and team from "info", and uses the name and pos fields in "categoryDetails".
# There is a ton more in there including gaps, status etc.
#
# This program is basically "fire and forget".  It will respond to updates when new race data
# is received, and calls "onChange".  Just like the Announcer screen in CrossMgr, it will also update
# for reference information changes, for example, if you correct a misspelled name or team.
#

PORT_NUMBER = 8765 + 1    # CrossMgr announter port.

riders = {}

def applyRAM( dest, ram ):
    # Apply the RAM information (RAM = Remove, Add, Modify).
    # It is only safe to apply the RAM update *if* the update versionCount is one greater than the last versionCount.
    # Otherwise if it necessary to request a new baseline.
    
    # First apply Add and Modify, which are key/object pairs.
    dest.update( ram['a'] )
    dest.update( ram['m'] )
    # Then apply Deletes, which are an array of keys to delete.
    for k in ram['r']:
        dest.pop( k, None )    # Use pop instead of del (safer).

def hhmmss( raceTime ):
    seconds = round(raceTime)
    minutes = seconds // 60
    hours = seconds // 3600
    return '%02d:%02d' % (minutes, seconds % 60)

def lap_position_str(lap_position):
    if lap_position == 1:
        return 'LEADER'
    elif lap_position == 2:
        return '2nd'
    elif lap_position == 3:
        return '3rd'
    else:
        return '%dth' % lap_position


class SynchronizedRaceData:
    def __init__( self, crossmgr='localhost', port=PORT_NUMBER, clientQueue=None, ):
        self.info = {}                    # Reference data accessed by bib number.
        self.categoryDetails = {}        # Category details accessed by category name.  Includes current position of all participats.
        
        self.clientQueue = clientQueue
        self.raceName = ''                # Name of current race.
        self.versionCount = -1            # Current version of the local race.

        self.wsurl = 'ws://' + crossmgr + ':' + str(PORT_NUMBER) + '/'

        self.riderCategories = {}
        self.last_racetime = {}
        self.passings = []
        self.last_index = 0
        self.keepalives = 0

        self.showFlag = False

    #def wsserverSend(self, message):
    #    log("SynchronizedRaceData.wssend: %s" % (message,))
    #    self.clientQueue.put(message)
    
    def clientQueuePut(self, dataType, message):
        try:
            log("SynchronizedRaceData.clientQueue[%s] %s PUT" % (dataType, message,))
            self.clientQueue.put((dataType, message))
        except Exception as e:
            log("SynchronizedRaceData.clientQueue[%s] %s PUT FAILED" % (dataType, e,))
            print(traceback.format_exc(), file=sys.stderr)

    def setRaceState( self, message, reset=False ):
        self.raceName = message['reference']['raceName']
        self.versionCount = message['reference']['versionCount']
        self.raceIsRunning = message['reference']['raceIsRunning']
        self.raceIsUnstarted = message['reference']['raceIsUnstarted']
        self.raceIsFinished = message['reference']['raceIsFinished']
        self.timestamp = message['reference']['timestamp']
        self.tNow = message['reference']['tNow']
        self.curRaceTime = message['reference']['curRaceTime']
        if reset:
            self.riderCategories = {}
            self.last_racetime = {}
            self.passings = []
            self.last_index = -1
            self.clientQueuePut('baseline', '')

        #self.clientQueuePut('categoryDetails', self.categoryDetails.keys())
        for k, v in self.categoryDetails.items():
            if k == 'All': continue
            for bib in v['pos']:
                self.riderCategories[str(bib)] = k
        log('setRaceState: riderCategories: %s' % (self.riderCategories))
        for k, v in self.info.items():
            log('setRaceState: bib: %s' % (k))
            bib = k
            riderCat = self.riderCategories[bib]
            v['raceCat'] = riderCat

        if True:
            try:
                for i, (k, v) in enumerate(self.categoryDetails.items()):
                    log('cat[%d][%20s] offset: %s %s laps: %s bibs: %s' % (i, k, v['startOffset'], v['gender'], v['laps'], v['pos']))
                for i, (k, v) in enumerate(self.info.items()):
                    #log('info[%d][%4s] %s ' % (i, k, v['interp']))
                    #log('info[%d][%4s] %s ' % (i, k, v['raceTimes']))
                    log('info[%d][%20s][%4s] %s ' % (i, v['raceCat'], k, v['raceTimes'][:self.find_last_false(v['interp'])]))
            except Exception as e:
                log('setRaceState: error: %s' % (e))
                print(traceback.format_exc(), file=sys.stderr)
                exit(1)
    
    def processBaseline( self, message ):
        # XXX
        self.info = message['info']
        self.categoryDetails = message['categoryDetails']
        self.setRaceState( message, reset=True )
        self.baselinePending = False
    
    def processRAM( self, message ):
        applyRAM( self.info, message['infoRAM'] )
        applyRAM( self.categoryDetails, message['categoryRAM'] )
        self.setRaceState( message, reset=False )

    def printTop( self ):
        # Example "do something" with the results.
        showTop = 5
        print( '********* Top {} Leaders ********* {}'.format(showTop, datetime.datetime.now()), file=sys.stderr )
        # Sort the categoryDetails by "iSort" so they come out in the same order as CrossMgr.
        for cat in sorted( self.categoryDetails.values(), key=operator.itemgetter('iSort') ):
            if cat['iSort'] == 0:    # Ignore the 'All' category has iSort=0.
                continue
            print( cat['name'], file=sys.stderr )
            for rank, bib in enumerate(cat['pos'][:showTop], 1):
                # Get the reference information for this bib number.
                r = self.info.get(str(bib), {})    # Access as a string, not an integer.
                print( '{}. {:4d}: {} {} ({})'.format( rank, bib, r.get('FirstName', ''), r.get('LastName', ''), r.get('Team','') ), file=sys.stderr)
    
    def find_last_false(self, arr):
        try:
            # Reverse the list and find the first True, then calculate the original index
            return len(arr) - 1 - arr[::-1].index(False)
        except ValueError:
            # If there's no True value, return -1 or any value indicating "not found"
            return -1
    def find_last_true(self, arr):
        try:
            # Reverse the list and find the first True, then calculate the original index
            return len(arr) - 1 - arr[::-1].index(True)
        except ValueError:
            # If there's no True value, return -1 or any value indicating "not found"
            return -1

    # Example usage
    #boolean_array = [False, True, False, True, False]
    #print(find_last_true(boolean_array))  # Output: 3


    def generate_leaders(self, sorted_passings):
        leaders = {}
        leader_laps = {}
        lap_counts = {}
        lap_positions = {}
        new_sorted_passings = []
        firstFlag = True
        for index, (bib, seconds, name, lap, raceCat) in enumerate(sorted_passings):

            if raceCat not in leaders:
                leaders[raceCat] = []

            if raceCat not in leader_laps:
                leader_laps[raceCat] = 0

            if raceCat not in lap_positions:
                lap_positions[raceCat] = {}

            if lap not in lap_positions[raceCat]:
                lap_positions[raceCat][lap] = 0
            if bib not in lap_counts:
                lap_counts[bib] = 0

            lap_counts[bib] += 1
            if lap != lap_counts[bib]:
                print("Lap mismatch: %d != %d" % (lap, lap_counts[bib]), file=sys.stderr)
                continue

            leaderFlag = False
            if lap > len(leaders[raceCat]):
                leaders[raceCat].append((bib, seconds, lap))
                leader_laps[raceCat] = lap
                leaderFlag = True
                lap_positions[raceCat][lap] = 1
            else:
                lap_positions[raceCat][lap] += 1
            lap_position = lap_positions[raceCat][lap]
            

            tdstr = hhmmss(seconds)

            if firstFlag:
                firstFlag = False
                new_sorted_passings.append(json.dumps({
                    "type": "definition",
                    "title": self.raceName,
                    "headers": ('Bib', 'Note', 'Time', 'Gap', 'Lap', 'Name', 'Wave' ),
                }))
            tdstr = hhmmss(seconds)
            down = str(lap - leader_laps[raceCat]) if lap < leader_laps[raceCat] else ''
            new_sorted_passings.append(json.dumps({
                "type": "row",
                "row": [bib, lap_position_str(lap_position), tdstr, down, lap, name, raceCat, ],
            }))

        return new_sorted_passings

    # Example input
    #sorted_race_times = [
    #    ('100', 10), ('200', 11), ('300', 12), ('200', 20),
    #    ('300', 21), ('100', 22), ('100', 30), ('200', 31), ('300', 32)
    #]

    # Generate the leaders list
    #leaders = generate_leaders(sorted_race_times)
    #print(leaders)


    def printRecent( self ):
        # Example "do something" with the results.
        showTop = 5
        #print('info.keys: %s' % (self.info.keys()), file=sys.stderr)
        #print('info: %s' % (self.info), file=sys.stderr)

        #print('-------------------', file=sys.stderr)
        #print('categoryDetails: %s' % (self.categoryDetails), file=sys.stderr)
        #return
        passings = []
        for bib, data in self.info.items():
            #print('bib: %s data: %s' % (bib, data), file=sys.stderr)
            if data['status'] != 'Finisher':
                print('bib: %s status: %s NOT FINISHER' % (bib, data['status']), file=sys.stderr)    
                continue
            bib = int(bib)
            if data['raceCat'] not in self.categoryDetails:
                print('raceCat: %s not in categoryDetails' % (data['raceCat']), file=sys.stderr)
                continue
            startOffset = self.categoryDetails[data['raceCat']]['startOffset']

            raceTimes = data['raceTimes']
            raceCat = data['raceCat']

            interp = data['interp']
            #print('interp: %s' % (str(interp)), file=sys.stderr)
            last_interp = self.find_last_false(interp)
            FirstName = data['FirstName']
            LastName = data['LastName']
            name = f"{LastName},{FirstName}"
            for lap in range(1, last_interp + 1, 1):
                #raceCat = self.riderCategories[bib]
                try:
                    passings.append((bib, raceTimes[lap], name, lap, self.riderCategories[str(bib)]))
                except Exception as e:
                    log('error: %s' % (e))
                    print(traceback.format_exc(), file=sys.stderr)

        sorted_passings = sorted(passings, key=lambda x: x[1])
        sorted_passings = self.generate_leaders(sorted_passings)
        index = 0
        laps = 0
        position = 1
        for passing in sorted_passings:

            log('passing: %s' % (str(passing)))
            #bib, lap_position, tdstr, lap, down, name, raceCat = passing

            if index > self.last_index:
                self.clientQueuePut('recorded', passing)
                self.last_index = index
            index = index + 1
            position += 1

        return

    def onChange( self ):
        # Called after any change.  Subclass to specialize.
        #print( 'onChange', file=sys.stderr )
        #self.printTop()
        self.printRecent()

    
    def onMessage( self, ws, btext ):
        #print( btext, file=sys.stderr )
        try:
            message = json.loads( btext )
        except Exception as e:
            print( 'Error decoding message: %s' % (e), file=sys.stderr )
            print( traceback.format_exc(), file=sys.stderr )
            return

        log('message: %s' % ({k: len(message[k]) for k in message.keys()}))
        summary = {}
        for k in ['categoryRAM', 'infoRAM']:
            if k in message:
                summary[k] = {'a':len(message[k]['a']), 'm':len(message[k]['m']), 'r':len(message[k]['r'])}
            
        if 'reference' in message:
            log('message: reference: %s' % (message['reference']))
            self.curRaceTime = message['reference']['curRaceTime']
            self.clientQueuePut('race_time', json.dumps({'type': 'race_time', 'time': hhmmss(self.curRaceTime),}))

        if self.showFlag:
            self.showFlag = False
            log('message: cmd: %s' % (message['cmd']))
            log('message: reference: %s' % (message['reference']))


        #applyRAM( self.info, message['infoRAM'] )
        #applyRAM( self.categoryDetails, message['categoryRAM'] )

        print( "message: keys: %s" % (summary), file=sys.stderr)
        #print( "message: %s" % (message), file=sys.stderr)
        if False:
            for k, v in message.items():
                if k == 'info':
                    for kk, vv in v.items():
                        print('Riders: %s' % (riders.keys()), file=sys.stderr)
                        print('Rider: %s' % (kk), file=sys.stderr)
                        if kk not in riders:
                            #riders[kk] = {'name':vv['FirstName'] + ' ' + vv['LastName'], 'team':vv['Team'], 'raceTimes':vv['RaceTimes']}
                            riders[kk] = {}
                        #else:
                        #    riders[kk]['raceTimes'] = vv['RaceTimes']
                        print( "message: [%s:%s] %s" % (k, kk, vv), file=sys.stderr)
                        #print("", file=sys.stderr)
                    continue
                continue
                if isinstance(v, dict):
                    for kk, vv in v.items():
                        if isinstance(vv, dict):
                            for kkk, vvv in vv.items():
                                print( "message: [%s:%s:%s] %s" % (k, kk, kkk, vvv), file=sys.stderr)
                                print("", file=sys.stderr)
                #else
                #print( "message: %s: %s" % (k, v), file=sys.stderr)
                print('riders: %s' % (riders), file=sys.stderr)
                for k, v in riders:
                    print('[%d] %s' % (k, riders['raceTimes'], ), file=sys.stderr)

        if 'cmd' not in message:
            print('onMessage: cmd not in message', file=sys.stderr)
            return
        
        if message['cmd'] == 'ram':
            if not self.baselinePending:
                # If the versionCount or raceName is out of sync.  Request a full update.
                if self.versionCount + 1 != message['reference']['versionCount'] or self.raceName != message['reference']['raceName']:
                    ws.send( json.dumps({'cmd':'send_baseline', 'raceName':message['reference']['raceName']}).encode() )
                    self.baselinePending = True    # Set flag to ignore incremental updates until we get the new baseline.
                else:
                    # Otherwise, it is safe to apply this update.
                    self.processRAM( message )
                    self.onChange()
            
        elif message['cmd'] == 'baseline':
            self.processBaseline( message )
            self.onChange()
    
    def onException( self, e ):
        # Called after connection exceptions.  Subclass to specialize.
        print( e, file=sys.stderr )
    
    def eventLoop( self, stopEvent=None ):
        try:
            log("SynchronizedRaceData.eventLoop crossmgr: %s" % (self.wsurl))
            ws = websocket.create_connection( self.wsurl )
            #print('ws timeout: %s' % (ws.gettimeout()), file=sys.stderr)
            ws.settimeout(4)
            ws.send( json.dumps({'cmd':'send_baseline', 'raceName':'CurrentResults'}).encode() )
            while not stopEvent.is_set():
                try:
                    self.onMessage( ws, ws.recv() )
                except websocket.WebSocketTimeoutException:
                    #print('timeout', file=sys.stderr)
                    pass
                #ws.send( json.dumps({'keepalive': self.keepalives,}).encode() )
                #self.keepalives += 1
            return
        except Exception as e:
            log("SynchronizedRaceData.eventLoop exception: %s" % (e))
            print(traceback.format_exc(), file=sys.stderr)
            #self.onException( e )
            time.sleep( 1 )
        finally:
            pass
        

class LiveThread( ThreadEx ):
    def __init__( self, stopEvent=None, crossmgr='192.168.40.12', clientQueue=None, ):

        log("LiveThread.__init__ crossmgr: %s" % (crossmgr if crossmgr else "None"))
        self.crossmgr = crossmgr
        self.clientQueue = clientQueue
        self.rd = SynchronizedRaceData(crossmgr=self.crossmgr, clientQueue=self.clientQueue)

        super(LiveThread, self).__init__(stopEvent=stopEvent, name='LiveThread')

        
    def work( self ):
        self.rd.eventLoop(stopEvent=self.stopEvent)


if __name__ == '__main__':
    rd = SynchronizedRaceData(crossmgr='192.168.40.12')
    rd.eventLoop()    # Never returns.
