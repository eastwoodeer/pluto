import asyncio
import socket
import select
import urllib

from urllib.parse import urlparse


HOST = ''                 # Symbolic name meaning all available interfaces
PORT = 8765               # Arbitrary non-privileged port
CRLF = '\r\n'

class HTTPRequest(object):
    charset = 'utf-8'
    configs = {}
    port = 80

    def __init__(self, request):
        self.request = request.decode(self.charset)
        contents = self.request.split(CRLF)
        self.method, url, self.proto = contents[0].split()
        self.url = urlparse(url)
        if self.method == 'CONNECT':
            self.hostname, self.port = url.split(':')
        else:
            if ':' in self.url.netloc:
                self.hostname, self.port = self.url.netloc.split(':')
            else:
                self.hostname = self.url.netloc
        self.content = CRLF.join(contents[1:])

    def __str__(self):
        return self.request


class Connection(object):
    def __init__(self, reader, writer):
        self.closed = False
        self.reader = reader
        self.writer = writer
        self.socket = writer.get_extra_info('socket')

    def recv(self, bytes=8192):
        return self.socket.recv(bytes)

    def send(self, data):
        return self.socket.send(data)

    async def read(self, bytes=8192):
        return await self.reader.read(bytes)

    def write(self, data):
        self.writer.write(data)

    def close(self):
        self.writer.close()
        self.closed = True


class Client(Connection):
    def __str__(self):
        return 'Client closed: {}'.format(self.closed)


class Server(Connection):
    def __str__(self):
        return 'Server closed: {}'.format(self.closed)


class ProxyError(Exception):
    pass


class ProxyConnectionFailed(ProxyError):

    def __init__(self, host, port, reason):
        self.host = host
        self.port = port
        self.reason = reason

    def __str__(self):
        return 'ProxyConnectionFailed: %s:%s: %s' % (self.host, self.port, self.reason)


class Proxy(object):
    def __init__(self, loop):
        self.loop = loop
        # self.server = None

    async def connect(self, request):
        try:
            r, w = await asyncio.open_connection(request.hostname, request.port)
            return Server(r, w)
        except Exception as e:
            raise ProxyConnectionFailed(request.hostname, request.port, repr(e))

    async def server(self, reader, writer):
        self.client = Client(reader, writer)
        data = await self.client.read()
        if not data:
            self.client.close()
            return
        request = HTTPRequest(data)
        print(request)
        await self.process_request(request)

    async def process_request(self, request):
        try:
            self.server = await self.connect(request)
        except ProxyConnectionFailed as e:
            print(e)
            self.client.close()
            return
        if request.method == 'CONNECT':
            self.client.write('HTTP/1.1 200 Connection Established\r\n\r\n'.encode())
        else:
            if request.url.query:
                path = '?'.join([request.url.path, request.url.query])
            else:
                path = request.url.path
            msg = '{} {} HTTP/1.1\r\n{}'.format(request.method,
                                                path,
                                                request.content)
            self.server.write(msg.encode())
        self.loop.add_reader(self.client.socket, self.client_read)
        self.loop.add_reader(self.server.socket, self.server_read)

    def client_read(self):
        try:
            data = self.client.recv()
            if not data:
                self.loop.remove_reader(self.client.socket)
                return
            self.server.write(data)
        except Exception as e:
            print('client read exception: {}'.format(e))
            self.loop.remove_reader(self.client.socket)
            self.client.close()

    def server_read(self):
        try:
            data = self.server.recv()
            if not data:
                self.loop.remove_reader(self.server.socket)
                return
            self.client.write(data)
        except Exception as e:
            print('server read exception: {}'.format(e))
            self.loop.remove_reader(self.server.socket)
            self.server.close()


class Pluto(object):
    def __init__(self, loop):
        self.loop = loop

    async def start(self, reader, writer):
        proxy = Proxy(self.loop)
        await proxy.server(reader, writer)

    def run(self):
        coro = asyncio.start_server(self.start, HOST, PORT, loop=self.loop)
        server = self.loop.run_until_complete(coro)
        print('Serving on {}'.format(server.sockets[0].getsockname()))
        try:
            self.loop.run_forever()
        except KeyboardInterrupt:
            pass
        server.close()
        self.loop.run_until_complete(server.wait_closed())
        self.loop.close()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    server = Pluto(loop)
    server.run()
