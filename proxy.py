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
        self.url = urlparse(url)
        for config in contents[1:]:
            if not config: continue
            k, v = config.split(':', maxsplit=1)
            self.configs[k] = v.strip()


class Proxy:
    async def server(self, reader, writer):
        data = await reader.read(4096)
        message = data.decode()
        print(message)
        request = HTTPRequest(data)
        await self.get_data(request, writer)


    async def get_data(self, request, writer):
        url = request.url
        # r, w = await asyncio.open_connection('10.74.120.140', 8000)
        r, w = await asyncio.open_connection(url.hostname, 80)
        msg = 'GET {} HTTP/1.1\r\nHost: {}\r\n\r\n'.format(url.path, url.netloc)
        w.write(msg.encode('latin-1'))
        while True:
            data = await r.read(4096)
            if not data:
                writer.close()
                w.close()
                break
            writer.write(data)


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
