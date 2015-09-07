import xmpp
import sys
import time
import threading
import multiprocessing
import Queue

class NetworkingClient:
    def __init__(self, server="", port=5222):
        self.server = server
        self.port = port
        self.jid = xmpp.JID
        self.secret = None
        self.client = xmpp.Client
        self.msg_handler = None
        self.listening_process = None
        self.stop_all_processes = False
        self.lock = multiprocessing.RLock()

        #### vars for blocking
        self.messages = Queue.Queue()

    # TODO check if valid jid?
    def set_credentials(self, jid=None, username=None, domain=None, resource=None, secret=None):
        if jid is not None:
            pass
        else:
            self.jid = xmpp.JID(node=username, domain=domain, resource=resource)
            self.secret = secret

    # connects and initialize the client for business
    # does it in multiple steps:
    # 1. tcp connection
    # 2. xmpp user authentication
    # 3. sends presence to server
    # 4. registers event handlers
    def connect(self):
        # step 1
        if self.server is not None:
            # TODO client debug flag
            self.client = xmpp.Client(server=self.server, port=self.port, debug=[])
            con = self.client.connect(server=(self.server, self.port))
            if not con:
                # TODO exception
                print "No connection made", con
                sys.exit(0)
            else:
                print "connected with: " + con
                # step 2
                self.authenticate()
                # step 3
                self.client.sendInitPresence()
                # step 4
                self._register_handlers()

    def authenticate(self):
        if self.jid is not None:
            auth = self.client.auth(self.jid.getNode(), self.secret, self.jid.getResource())
            if not auth:
                print "could not authenticate"
                sys.exit(0)
            else:
                print "authenticated using: " + auth

    def _register_handlers(self):
        self.client.RegisterHandler("message", self.blocking_on_message)

    def disconnect(self):
        self.lock.acquire()
        self.stop_all_processes = True
        self.lock.release()
        # sleeping 1 sec before disconnect, this removes errors that can happen on older servers
        time.sleep(1)
        self.client.disconnect()
        print "disconnected"

    # TODO timestamp/time-to-live for discarding old messages
    def send_message(self, to, sender, message="", subject=""):
        msg = xmpp.Message()
        if to is not None and to != "":
            msg.setTo(to)
            msg.setFrom(sender)
            msg.setBody(message)
            msg.setSubject(subject)
            msg.setID(1)
            if self.client.connected:
                self.client.send(msg)
        else:
            # TODO exception on wrong to parameter
            pass

    # TODO check on recipientList er en liste
    def send_mass_messages(self, recipientList, sender, message="", subject=""):
        for s in recipientList:
            self.send_message(to=s, sender=sender, message=message, subject=subject)

    # raises TypeError exception if handlers aren't setup properly
    def on_message(self, client, msg):
        # TODO checking message type and dealing with them, f.x. if msg.type == "chat" do x
        self.lock.acquire()
        self.msg_handler(msg)
        self.lock.release()

    # TODO might need a generic add handler method, to support building addons
    def register_message_handler(self, obj):
        self.msg_handler = obj.message_received

    def _listen(self, timeout=1):
        print "entering listen method"
        self.lock.acquire()
        stopped = self.stop_all_processes
        self.lock.release()
        while stopped is not True:
            self.client.Process(timeout)
            time.sleep(0.3)
            self.lock.acquire()
            stopped = self.stop_all_processes
            self.lock.release()

    def start_listening(self):
        print "starting new thread"
        thread = threading.Thread(target=self._listen)
        thread.setDaemon(True)
        thread.start()

    def id(self):
        return str(self.jid)
 ##########################Stuff for blocking########################################

    def _blocking_listen(self, timeout=1.0):
        print "entering listen method"
        # TODO remove busy waiting
        while True:
            self.client.Process(timeout)

    def blocking_listen_start(self):
        print "spawning process"
        thread = threading.Thread(target=self._blocking_listen)
        thread.setDaemon(True)
        thread.start()

    def blocking_on_message(self, dispatcher, msg):
        self.lock.acquire()
        self.messages.put(msg)
        self.lock.release()

    def block_check_for_messages(self):
        self.lock.acquire()
        result = not self.messages.empty()
        self.lock.release()
        return result

    def block_pop_message(self):
        return self.messages.get()
