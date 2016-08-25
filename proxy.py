import asyncio
import socket
import select
import urllib

from urllib.parse import urlparse


HOST = ''                 # Symbolic name meaning all available interfaces
PORT = 8765               # Arbitrary non-privileged port


class HTTPRequest:
    charset = 'utf-8'
    configs = {}

    def __init__(self, request):
        self.request = request.decode('utf-8')
        contents = self.request.split('\r\n')
        self.method, url, self.proto = contents[0].split()
        if self.method == 'CONNECT':
            self.url = url.split(':')[0]
        else:
            self.url = urlparse(url)
        self.content = '\r\n'.join(contents[1:])

    def __str__(self):
        return self.request


class Proxy:
    def __init__(self, loop):
        self.loop = loop

    async def server(self, reader, writer):
        data = await reader.read(4096)
        message = data.decode()
        request = HTTPRequest(data)
        print(request)
        if request.method == 'CONNECT':
            await self.connect_data(request, reader, writer)
        else:
            await self.get_data(request, writer)

    async def connect_data(self, request, client_reader, client_writer):
        reader, writer = await asyncio.open_connection(request.url, 443)
        msg = 'HTTP/1.1 200 Connection Established\r\n\r\n'
        client_writer.write(msg.encode())
        client = client_writer.get_extra_info('socket')
        server = writer.get_extra_info('socket')
        self.loop.add_reader(client, self.client_read, server, client)
        self.loop.add_reader(server, self.server_read, server, client)

    def client_read(self, server, client):
        try:
            data = client.recv(4096)
            if not data:
                print('remove client_read')
                self.loop.remove_reader(client)
                return
            server.send(data)
        except Exception as e:
            print('client read exception: {}'.format(e))
            self.loop.remove_reader(client)

    def server_read(self, server, client):
        try:
            data = server.recv(4096)
            if not data:
                print('remove server_read')
                self.loop.remove_reader(server)
                return
            client.send(data)
        except Exception as e:
            print('server read exception: {}'.format(e))
            self.loop.remove_reader(server)


    async def get_data(self, request, client):
        url = request.url
        reader, writer = await asyncio.open_connection(url.netloc, 80)
        msg = '{} {} HTTP/1.1\r\n{}'.format(request.method, url.path, request.content)
        writer.write(msg.encode('latin-1'))
        while True:
            data = await reader.read(4096)
            if not data:
                client.close()
                writer.close()
                break
            client.write(data)

    def read(self, server, client):
        data = server.recv(4096)
        if not data:
            self.loop.remove_reader(server)
            return
        client.write(data)


    def run(self):
        coro = asyncio.start_server(self.server, HOST, PORT, loop=self.loop)
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
    proxy = Proxy(loop)
    proxy.run()
