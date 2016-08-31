import unittest
from proxy import *


class TestParseHTTPHead(unittest.TestCase):
    def test_basic_parse_get(self):
        data = ''.join([
            'GET http://www.google.com:8080 HTTP/1.1\r\n',
            'Proxy-Connection: keep-alive\r\n'
            'Host: www.google.com\r\n',
            '\r\n'
        ]).encode()
        request = HTTPRequest(data)
        self.assertEqual('GET', request.method)
        self.assertEqual('8080', request.port)
        self.assertEqual('www.google.com', request.hostname)
        self.assertEqual('HTTP/1.1', request.version)
        self.assertEqual('/', request.build_url())
        headers = {'proxy-connection': ('Proxy-Connection', 'keep-alive'),
                   'host': ('Host', 'www.google.com')}
        self.assertDictEqual(headers, request.headers)

    def test_build_url(self):
        data = ''.join([
            'GET http://www.baidu.com/hello?a=b#xxx HTTP/1.1\r\n',
            '\r\n'
        ]).encode()
        request = HTTPRequest(data)
        self.assertEqual('GET', request.method)
        self.assertEqual('80', request.port)
        self.assertEqual('www.baidu.com', request.hostname)
        self.assertEqual('HTTP/1.1', request.version)
        self.assertEqual('/hello?a=b#xxx', request.build_url())
        headers = {}
        self.assertDictEqual(headers, request.headers)


    def test_parse_post(self):
        data = ''.join([
            'POST http://www.baidu.com/ HTTP/1.1\r\n',
            '\r\n',
            'a=1&b=2\r\n',
            'hello=world\r\n'
            '\r\n'
        ]).encode()
        request = HTTPRequest(data)
        self.assertEqual('a=1&b=2\r\nhello=world\r\n\r\n', request.body)


if __name__ == '__main__':
    unittest.main()