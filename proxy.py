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
    async def server(self, reader, writer):
        data = await reader.read(4096)
        message = data.decode()
        print(message)
        request = HTTPRequest(data)
        if request.method == 'CONNECT':
            await self.connect_data(request, reader, writer)
        else:
            await self.get_data(request, writer)

    async def connect_data(self, request, client_reader, client_writer):
        reader, writer = await asyncio.open_connection(request.url, 443, ssl=True)
        msg = 'HTTP/1.1 200 Connection Established\r\n\r\n'
        print('===========================')
        client_writer.write(msg.encode('latin-1'))
        while True:
            data = await client_reader.read()
            if not data:
                client_writer.close()
                writer.close()
                break
            writer.write(data)
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                client_writer.write(data)

    async def get_data(self, request, client):
        url = request.url
        reader, writer = await asyncio.open_connection('10.74.120.140', 80)
        # reader, writer = await asyncio.open_connection(url.netloc, 80)
        msg = '{} {} HTTP/1.1\r\n{}'.format(request.method, url.path, request.content)
        writer.write(msg.encode('latin-1'))
        while True:
            data = await reader.read(4096)
            if not data:
                client.close()
                writer.close()
                break
            client.write(data)


if __name__ == '__main__':
    proxy = Proxy()
    loop = asyncio.get_event_loop()
    coro = asyncio.start_server(proxy.server, HOST, PORT, loop=loop)
    server = loop.run_until_complete(coro)

    # Serve requests until Ctrl+C is pressed
    print('Serving on {}'.format(server.sockets[0].getsockname()))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass

    # Close the server
    server.close()
    loop.run_until_complete(server.wait_closed())
    loop.close()
