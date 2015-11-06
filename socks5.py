
from gevent import monkey; monkey.patch_all()
import socket
import threading
import thread
import time
import struct
import sys, traceback

def runThread(f, args):
    thread.start_new_thread(f, args)

def recvFull(conn, length):
    s = ''
    while length > 0:
        cs = conn.recv(length)
        if len(cs) == 0:
            raise socket.error(-1, "peer closed")
        length -= len(cs)
        s += cs
    return s

class Server(threading.Thread):
    def __init__(self, port):
        threading.Thread.__init__(self)
        self.daemon = True
        self._port = port
        self._s = self._initListen()

    def _initListen(self):
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', self._port))
        s.listen(socket.SOMAXCONN)
        return s

    def run(self):
        socket.setdefaulttimeout(8)

        while True:
            self._acceptOneConn()
        print "server exit!"

    def _acceptOneConn(self):
        conn, addr = self._s.accept()
        print "accepted one connection from", conn.getpeername()
        try:
            self._handClientConn(conn)
        except Exception as e:
            print e
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            conn.close()

    def _handClientConn(self, clientConn):
        serverConn = self._handshake(clientConn)
        print "_handshake complete", clientConn.getpeername(), 'connect to', serverConn.getpeername()

        runThread(self._transfer, (clientConn, serverConn))
        runThread(self._transfer, (serverConn, clientConn))

    def _handshake(self, clientConn):
        self._negotiateMethod(clientConn)
        serverConn = self._negotiateCmd(clientConn)
        return serverConn

    def _negotiateMethod(self, clientConn):
        s = recvFull(clientConn, 2)
        ver, nmethod = struct.unpack("2B", s)
        if(ver != 0x05):
            raise socket.error(-1, "ver not supported")
        if(nmethod == 0):
            raise socket.error(-1, "nmethod is 0")

        s = recvFull(clientConn, nmethod)
        for c in s:
            if ord(c) == 0x00:
                clientConn.sendall(struct.pack("2B", 0x05, 0x00))
                return
            else:
                print "don't support method %d" %ord(c)
        raise socket.error(-1, "all method can't be supported")

    def _negotiateCmd(self, clientConn):
        s = recvFull(clientConn, 4)
        ver, cmd, rsv, atyp = struct.unpack("4B", s)
        host = None
        if(ver != 0x05):
            raise socket.error(-1, "ver not supported")
        if cmd != 0x01:
            raise socket.error(-1, "cmd not supported")
        if atyp == 0x01:
            s = recvFull(clientConn, 4)
            host = socket.inet_ntoa(s)
            #host, = struct.unpack("!I", s)
            #print type(host)
        elif atyp == 0x03:
            s = recvFull(clientConn, 1)
            domainLength, = struct.unpack("B", s)
            host = recvFull(clientConn, domainLength)
        else:
            raise socket.error(-1, "atyp not supported")
        s = recvFull(clientConn, 2)
        port, = struct.unpack("!H", s)
        try:
            #serverConn = socket.create_connection((host, port))
            serverConn = socket.socket()
            serverConn.connect((host, port))
        except:
            print "host: {0}, port: {1}".format(host, port)
            raise
        s = struct.pack("4BIH", 0x05, 0x00, 0x00, 0x01, 0, 0)
        clientConn.sendall(s)

        return serverConn

    def _transfer(self, conn1, conn2):
        try:
            while True:
                s = conn1.recv(1024)
                if len(s) == 0:
                    break
                s = s.replace('Connection: keep-alive', 'Connection: close')
                conn2.sendall(s)
                #print conn1.getpeername(), s
        except socket.error as e:
            pass
        conn2.close()
        conn1.close()

if __name__ == '__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_NOFILE, (10240, 10240))

    s = Server(10001)
    s.start()

    time.sleep(3600)