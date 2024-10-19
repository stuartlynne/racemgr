import sys
from threading import Thread, Event
from queue import Queue
import traceback
import argparse
import signal
from time import sleep

from .threadex import ThreadEx
from .live import LiveThread
from .wsserver import WSServer, Passings
from .flaskserver import FlaskServer

from .utils import log


__version__ = "0.2.0"


StopEvent = Event()


def raceMain():

    def sigintHandler(signal, frame):
        log('SIGINT received %s' % (signal,), )
        StopEvent.set()


    signal.signal(signal.SIGINT, lambda signal, frame: sigintHandler(signal, frame))
    #log('RaceMgr version %s' % __version__)
    #while True:
    #    log('Sleeping 2')
    #    sleep(2)

    parser = argparse.ArgumentParser(description="Export start lists for a RaceDB competition.")
    parser.add_argument('--crossmgr', type=str, default='localhost', help='CrossMgr host')
    parser.add_argument('--port', type=int, default=11001, help='Flask port')
    parser.add_argument('--wsserver', type=int, default=11002, help='WSServer port')

    args = parser.parse_args()

    StopEvent.clear()
    ClientQueue = Queue()

    threads = []

    passings = Passings(stopEvent=StopEvent, clientQueue=ClientQueue)
    threads.append(passings)

    threads.append(LiveThread(stopEvent=StopEvent, crossmgr=args.crossmgr, clientQueue=ClientQueue))

    wsserver = WSServer(stopEvent=StopEvent, port=args.wsserver, passings=passings, )
    passings.wsserver = wsserver
    threads.append(wsserver)

    flaskserver = FlaskServer(stopEvent=StopEvent, webport=args.port, dataport=args.wsserver,  )
    threads.append(flaskserver)

    [v.start() for v in threads]

    log("Threads started, waiting for StopEvent")
    try:
        StopEvent.wait()
    except KeyboardInterrupt:
        log("KeyboardInterrupt, stopping threads")
        pass
    log("StopEvent received, stopping threads")

    flaskserver.shutdown()

    for t in threads:
        log("Checking thread: %s" % t.name)
        if t.is_alive():
            t.stop()
            log("Stopping thread: %s" % t.name)
            t.stop()
            log("Joining thread: %s" % t.name)
            t.join()
            log("Joined thread: %s" % t.name)

if __name__ == '__main__':
    raceMain()




