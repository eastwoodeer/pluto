import socket
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

    def __str__(self):
        return '''
method: {}
url: {}
Accept-Encoding: {}
'''.format(self.method, self.url, self.configs['Accept-Encoding'])


class Proxy:
    def server(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((HOST, PORT))
        s.listen(10)

        while True:
            conn, addr = s.accept()
            print('Connected by', addr)
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                request = HTTPRequest(data)
                data = self.send(request)
                conn.sendall(data)
            conn.close()

    def send(self, request):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        url = request.url
        port = 80
        if ';' in url:
            port = url.split(':')[1]
        # s.connect((url.netloc, port))
        s.connect(('10.74.120.140', 8000))
        msg = 'GET {} HTTP/1.1\r\nHost: {}\r\n\r\n'.format(url.path, url.netloc)
        s.send(msg.encode('utf-8'))
        data = s.recv(4096)
        recv_data = data
        while len(data):
            data = s.recv(4096)
            recv_data += data
        return recv_data


if __name__ == '__main__':
    proxy = Proxy()
    proxy.server()
