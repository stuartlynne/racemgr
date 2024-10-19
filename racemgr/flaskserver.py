import os
import json
import sys
import asyncio
import argparse
import time
from datetime import timedelta
import datetime
import signal
import traceback


from werkzeug.serving import make_server
from flask import Flask, render_template, render_template_string, Response, request
import logging
from flask.logging import default_handler

from .threadex import ThreadEx
from .utils import log

#def get_host_info():
#    try:
#        host_name = socket.gethostname()
#        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#        s.connect(('10.0.0.0', 0))
#        host_ip = s.getsockname()[0]
#        #host_ip = socket.gethostbyname(host_name)
#        host_info = '%s (%s)' % (host_name, host_ip)
#        log('get_host_info: host_info: %s' % host_info)
#        return host_info
#    except Exception as e:
#        log('get_host_info: Error: %s' % e)
#        return ''


class FlaskServer(ThreadEx):
    #app1 = Flask(__name__)

    def index(self):
        return render_template('index.html', ws_port=self.dataport)

    def __init__(self, stopEvent=None, webport=None, dataport=None ):
        super(FlaskServer, self).__init__(stopEvent=stopEvent, name='FlaskServer')
        self.app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
        #self.hostInfo = get_host_info()

        self.dataport = dataport
        self.webport = webport
        # this gets rid of the werkzeug logging which defaults to logging GET requests
        wlog = logging.getLogger('werkzeug')
        wlog.setLevel(logging.ERROR)

        self.app.add_url_rule('/', 'root', self.index)

        self.server = make_server('0.0.0.0', self.webport, self.app)

    def work(self):
        log('FlaskSever.run: Starting server', )
        self.server.serve_forever()
        log('FlaskSever.run: server started', )

    def shutdown(self):
        log('FlaskSever.Stopping server', )
        self.server.shutdown()
        self.server.server_close()
        #self.ctx.pop()

def main():

    sigintEvent = Event()
    changeEvent = Event()
    stopEvent = Event()
    sigintEvent.clear()
    changeEvent.clear()
    stopEvent.clear()

    def sigintHandler(signal, frame):
        log('SIGINT received %s' % (signal,), )
        sigintEvent.set()
        changeEvent.set()

    signal.signal(signal.SIGINT, lambda signal, frame: sigintHandler(signal, frame))

    server = FlaskServer()
    server.start()

    while changeEvent.wait():
        changeEvent.clear()
        if sigintEvent.is_set():
            stopEvent.set()
            log('Shutting down server', )
            server.shutdown()
            log('Server shutdown', )
            break

if __name__ == '__main__':

    main()

