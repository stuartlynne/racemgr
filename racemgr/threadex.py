
import sys
import traceback
from time import sleep

from threading import Thread, Event
from queue import Empty

from .utils import log


class ThreadEx(Thread):

    def __init__(self, stopEvent=None, name=None):
        log("ThreadEx.__init__ name: %s" % (name if name else "None"))
        self.stopEvent = stopEvent
        super(ThreadEx, self).__init__(name=name)
        log("ThreadEx.__init__ done, name: %s" % (self.name))

    # Override this method in the subclass
    def work(self):
        sleep(1)
        pass

    def finalize(self):
        pass

    # Override this method in the subclass if needed
    # e.g. wssever.py
    def stop(self):
        pass

    def run(self):
        log("ThreadEx.run: %s" % self.getName())
        while not self.stopEvent.is_set():
            log("ThreadEx.run call work: %s" % self.getName())
            try:
                self.work()
            except Empty:
                log("ThreadEx.run Empty")
                sleep(2)
                continue
            except Exception as e:
                log("Exception in thread: %s XXXXXXXXXXXXXX" % e,)
                traceback.print_exc(file=sys.stderr)
                break
        self.finalize()

