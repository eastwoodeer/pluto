import argparse
import asyncio
import logging
import socket

from urllib.parse import urlparse


log = logging.getLogger(__name__)

CRLF, COLON, SPACE = '\r\n', ':', ' '

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
            self.hostname, self.port = url.split(COLON)
        else:
            if COLON in self.url.netloc:
                self.hostname, self.port = self.url.netloc.split(COLON)
            else:
                self.hostname = self.url.netloc
        self.content = CRLF.join(contents[1:])

    def __str__(self):
        return self.request


class Connection(object):
    def __init__(self, reader, writer):
        self.buffer = b''
        self.closed = False
        self.reader = reader
        self.writer = writer
        self.socket = writer.get_extra_info('socket')

    def buffer_size(self):
        return len(self.buffer)

    def has_buffer(self):
        return self.buffer_size() > 0

    def queue(self, data):
        self.buffer += data

    def recv(self, bytes=8192):
        return self.socket.recv(bytes)

    def send(self, data):
        return self.socket.send(data)

    async def read(self, bytes=8192):
        return await self.reader.read(bytes)

    def write(self, data):
        self.writer.write(data)

    def flush(self):
        sent = self.send(self.buffer)
        self.buffer = self.buffer[sent:]

    def close(self):
        self.writer.close()
        self.closed = True


class Client(Connection):
    def __str__(self):
        return 'Client'


class Server(Connection):
    def __str__(self):
        return 'Server'


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
        self.https_connection_established = CRLF.join([
            'HTTP/1.1 200 Connection Established',
            'Proxy-agent: proxy.py',
            CRLF]).encode()

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
        log.debug(request)
        log.info('{} {} {}'.format(request.method,
                                   request.hostname,
                                   request.url.path))
        await self.process_request(request)

    async def process_request(self, request):
        try:
            self.server = await self.connect(request)
        except ProxyConnectionFailed as e:
            log.debug(e)
            self.client.close()
            return
        if request.method == 'CONNECT':
            self.client.queue(self.https_connection_established)
        else:
            if request.url.query:
                path = '?'.join([request.url.path, request.url.query])
            else:
                path = request.url.path
            msg = '{} {} HTTP/1.1\r\n{}'.format(request.method,
                                                path,
                                                request.content)
            self.server.queue(msg.encode())
        self.loop.add_reader(self.client.socket, self.read, self.client, self.server)
        self.loop.add_reader(self.server.socket, self.read, self.server, self.client)
        self.loop.add_writer(self.client.socket, self.write, self.client)
        self.loop.add_writer(self.server.socket, self.write, self.server)

    def write(self, writer):
        try:
            writer.flush()
        except Exception as e:
            log.debug('{} write exception: {}'.format(writer, e))
            self.loop.remove_writer(writer.socket)
            # TODO: need to close this?
            writer.close()

    def read(self, reader, writer):
        try:
            data = reader.recv()
            if not data:
                self.loop.remove_reader(reader.socket)
                reader.close()
                return
            writer.queue(data)
        except Exception as e:
            log.debug('{} read exception: {}'.format(reader, e))
            self.loop.remove_reader(reader.socket)
            reader.close()


class Pluto(object):
    def __init__(self, loop, hostname, port):
        self.loop = loop
        self.hostname = hostname
        self.port = port

    async def start(self, reader, writer):
        proxy = Proxy(self.loop)
        await proxy.server(reader, writer)

    def run(self):
        coro = asyncio.start_server(self.start, self.hostname,
                                    self.port, loop=self.loop)
        server = self.loop.run_until_complete(coro)
        log.info('Serving on {}'.format(server.sockets[0].getsockname()))
        try:
            self.loop.run_forever()
        except KeyboardInterrupt:
            pass
        server.close()
        self.loop.run_until_complete(server.wait_closed())
        self.loop.close()


def main():
    parser = argparse.ArgumentParser(description='proxy.py: coding for fun')
    parser.add_argument('--hostname', default='127.0.0.1', help='Default: 127.0.0.1')
    parser.add_argument('--port', default='8765', help='Default: 8765')
    parser.add_argument('--log-level', default='INFO',
                        help='DEBUG, INFO, WARNING, ERROR, CRITICAL')
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level),
                        format='%(asctime)s - %(levelname)s - pid:%(process)d - %(message)s')
    hostname = args.hostname
    port = int(args.port)

    loop = asyncio.get_event_loop()
    server = Pluto(loop, hostname, port)
    server.run()


if __name__ == '__main__':
    main()
