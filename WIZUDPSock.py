#!/usr/bin/python

import socket


class WIZUDPSock:
    # def __init__(self, port, peerport):
    def __init__(self, port, peerport, ipaddr=None, localport=None):
        self.sock = None
        # self.localport = randint(52000, 53000)
        self.localport = port if localport is None else localport  # 0 = OS assigns an available port automatically
        self.peerport = peerport
        self.ipaddr = ipaddr

    def open(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # socket rcv buffer size
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 524288)  # 512 KB
        # print('getsockopt SO_RCVBUF:', self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF))

        try:
            # self.sock.bind(("", self.localport))
            self.sock.bind((self.ipaddr, self.localport))
            self.sock.setblocking(False)
        except OSError:
            self.sock.close()
            self.sock = None
            raise

    def sendto(self, msg):
        assert self.sock is not None, "sendto() called before open()"
        self.sock.sendto(msg, ("255.255.255.255", self.peerport))
        # self.sock.sendto(msg, ("192.168.50.255", self.peerport))

    def recvfrom(self):
        assert self.sock is not None, "recvfrom() called before open()"
        data, addr = self.sock.recvfrom(4096)
        return data, addr

    def close(self):
        if self.sock is not None:
            self.sock.close()
            self.sock = None
