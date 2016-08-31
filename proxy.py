import argparse
import asyncio
import logging
import socket

from urllib.parse import urlparse


log = logging.getLogger(__name__)

CRLF, COLON, SPACE = '\r\n', ':', ' '

class HTTPRequest(object):
    charset = 'utf-8'

    def __init__(self, request):
        self.body = None
        self.headers = {}
        self.port = '80'
        self.request = request.decode(self.charset)
        contents = self.request.split(CRLF)
        request, headers = contents[0], contents[1:]
        self.parse_request_info(request)
        self.parse_request_headers(headers)

    def parse_request_info(self, request):
        self.method, url, self.version = request.split()
        self.url = urlparse(url)
        if self.method == 'CONNECT':
            self.hostname, self.port = url.split(COLON)
        else:
            if COLON in self.url.netloc:
                self.hostname, self.port = self.url.netloc.split(COLON)
            else:
                self.hostname = self.url.netloc

    def parse_request_headers(self, contents):
        self.content = CRLF.join(contents)
        for index, line in enumerate(contents):
            if not line:
                if contents[index+1]:
                    self.body = CRLF.join(contents[index+1:])
                break
            parts = line.split(COLON, maxsplit=1)
            name = parts[0].strip()
            value = parts[1].strip()
            self.headers[name.lower()] = (name, value)

    def build_header(self, k, v):
        return '{}: {}\r\n'.format(k, v)

    def build_url(self):
        url = self.url.path
        if url == '':
            url = '/'
        if self.url.query:
            url += '?{}'.format(self.url.query)
        if self.url.fragment:
            url += '#{}'.format(self.url.fragment)
        return url

    def build(self, delete_headers=[], add_headers=[]):
        req = ' '.join([self.method, self.build_url(), self.version])
        req += CRLF
        for k in self.headers:
            if k not in delete_headers:
                name, value = self.headers[k]
                req += self.build_header(name, value)
        for header in add_headers:
            name, value = header
            req += self.build_header(name, value)
        req += CRLF
        if self.body:
            req += self.body
        return req.encode()

    def del_headers(self, *names):
        for name in names:
            del self.headers[name]
        self.build(self.headers)
        print(self.content)

    def add_header(self, name, value):
        if name not in self.headers:
            self.headers[name] = value
        self.build(self.headers)

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

    async def start_server(self, reader, writer):
        self.client = Client(reader, writer)
        data = await self.client.read()
        if not data:
            self.client.close()
            return
        request = HTTPRequest(data)
        log.info('{} {}'.format(request.method, request.build_url()))
        log.debug(request)
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
            self.server.queue(request.build(
                delete_headers=['proxy-connection', 'connection'],
                add_headers=[('Connection', 'Close')]
            ))
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
        await proxy.start_server(reader, writer)

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
                        format='%(asctime)s - %(levelname)s - %(message)s')
    hostname = args.hostname
    port = int(args.port)

    loop = asyncio.get_event_loop()
    server = Pluto(loop, hostname, port)
    server.run()


if __name__ == '__main__':
    main()
