import sys
import traceback

from websocket_server import WebsocketServer
from threading import Thread, Event
from queue import Empty
from time import sleep

from .threadex import ThreadEx
from .utils import log

class Passings(ThreadEx):

    def __init__(self, stopEvent=None, clientQueue=None):
        log("Passings.__init__")
        super(Passings, self).__init__(stopEvent=stopEvent, name="Passings")
        self.stopEvent = stopEvent
        self.clientQueue = clientQueue

        self.wsserver = None
        self.passings = []
        self.clients = []

    # Send a client a message
    def sendClient(self, client, data):
        log("Passings.sendClient client: %s data: %s" % (client, data))
        self.wsserver.send_message(client, str(data))

    # Add a new client to the list, send all current data
    def new_client(self, client):
        self.clients.append(client)
        for r in self.passings:
            self.sendClient(client, r)

    def client_left(self, client, ):
        print("Client(%d) disconnected" % client['id'])
        if client in self.clients:
            self.clients.remove(client)

    # reset
    def reset(self):
        self.passings = []

    # Called from run() to process the message queue
    def work(self):
        #log("Passings.work")
        try:
            message = self.clientQueue.get(block=False, timeout=0)
            log("Passings.work message: %s" % (str(message)))
            dataType, data = message
            if dataType == 'baseline':
                self.passings = []
            elif dataType in ['recorded', 'race_time', ]:
            #elif dataType in ['recorded', ]:
                self.passings.append(data)
                for client in self.clients:
                    self.sendClient(client, data)
        except Empty:
            log("Passings.work Empty")
            sleep(2)
            return

class WSServer(ThreadEx):

    dataTypes = ['test', 'recorded', 'expected', 'passing',]
    def __init__(self, stopEvent=None, host='0.0.0.0', port=11002, passings=None):
        log("WSServer.__init__ host: %s port: %d" % (host, port))
        super(WSServer, self).__init__(stopEvent=stopEvent, name="WSServer")
        self.host = host
        self.port = port
        self.stopEvent = stopEvent
        self.passings = passings
        self.clients = {}
        self.dataClients = {k:[] for k in self.dataTypes}

        self.server = WebsocketServer(host=host, port=port)
        self.server.set_fn_new_client(self.new_client)
        self.server.set_fn_client_left(self.client_left)
        self.server.set_fn_message_received(self.message_received)


    # Called for every client connecting (after handshake)
    def new_client(self, client, server):
        print("New client connected and was given id %d" % client['id'], file=sys.stderr)
        #server.send_message_to_all("Hey all, a new client has joined us")
        self.clients[client['id']] = client
        self.passings.new_client(client)

        #self.dataClients['passing'].append(client)
        #log("WSServer.send dataClients: %s" % self.dataClients['passing'])


    # Called for every client disconnecting
    def client_left(self, client, server):
        print("Client disconnected %s" % client)
        print("Client(%d) disconnected" % client['id'])
        self.passings.client_left(client)
        if client['id'] in self.clients:
            del self.clients[client['id']]

    
    # Called when a client sends a message
    def message_received(self, client, server, message):
        log("WSServer.message_received client[%s] %s" % (client['id'], message))
        #if len(message) > 200:
        #    message = message[:200]+'..'
        #print("Client(%d) said: %s" % (client['id'], message), file=sys.stderr)
        #if message == 'keepalive':
        #client['handler'].send_message('test recv')
        #    self.server.send_message(client, 'keepalive')

    def send_message(self, client, message):
        self.server.send_message(client, message)

    def send(self, dataType, data):
        log("WSServer.send dataType: %s data: %s" % (dataType, data))
        if dataType not in self.dataTypes:
            log("WSSever.send: Invalid data type: %s" % dataType, file=sys.stderr)
            return
        log("WSServer.send dataClients: %s" % ([(k, len(self.dataClients[k])) for k in self.dataClients.keys()]))
        for client in self.dataClients[dataType]:
            log("WSServer.send client: %s" % client['id'])
            self.server.send_message(client, data)

    def stop(self):
        log("WSServer.stop")
        self.server.shutdown()

    def work(self):
        log("WSServer.work")

        # XXX how stop this server when self.stopEvent is set?
        self.server.run_forever()

