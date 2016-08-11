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
        self.method, url, self.proto = contents[0].split(' ')
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

    def 


class Proxy:
    def server(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((HOST, PORT))
        s.listen(10)
        conn, addr = s.accept()
        print('Connected by', addr)
        while True:
            data = conn.recv(1024)
            if not data:
                break
            request = HTTPRequest(data)
            d = connect_www()
            conn.sendall(d)
        conn.close()

    def connect(self):
        pass
        


def connect_www():
    HOST = "10.74.120.140"
    PORT = 8000
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((HOST, PORT))
    s.send(b"GET / HTTP/1.1\r\nHost: 10.74.120.140\r\n\r\n")
    data = s.recv(4096)    
    recv_data = data
    while len(data):
        data = s.recv(4096)
        recv_data += data
    s.close()
    print(recv_data.decode('utf-8'))
    return recv_data

def proxy_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, PORT))
    s.listen(1)
    conn, addr = s.accept()
    print('Connected by', addr)
    while True:
        data = conn.recv(1024)
        if not data:
            break
        h = HTTPRequest(data)
        print(h)
        d = connect_www()
        conn.sendall(d)
    conn.close()





if __name__ == '__main__':
    proxy_server()
