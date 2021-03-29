import os
import unittest
from urllib.parse import urlparse, parse_qs, urlencode

from flask import Response, json
from flask.testing import FlaskClient
from flask_jwt_extended import JWTManager, create_access_token

import server


class ApiTestCase(unittest.TestCase):
    """Test case for server API"""

    def setUp(self):
        server.app.testing = True
        self.app = FlaskClient(server.app, Response)
        JWTManager(server.app)

    def tearDown(self):
        pass

    def jwtHeader(self):
        with server.app.test_request_context():
            access_token = create_access_token('test')
        return {'Authorization': 'Bearer {}'.format(access_token)}

    def test_getdocument_pdf(self):
        params = {
            "format": "pdf",
            "MaxOrderID": "10800"
        }
        response = self.app.get('/demo?' + urlencode(params), headers=self.jwtHeader())
        self.assertEqual(200, response.status_code, "Status code is not OK")
        self.assertTrue(isinstance(response.data, bytes), "Response is not a valid PDF")

    def test_getdocument_html(self):
        params = {
            "format": "html",
            "MaxOrderID": "10800"
        }
        response = self.app.get('/demo?' + urlencode(params), headers=self.jwtHeader())

        success = False
        try:
            html = response.data.decode("utf-8")
            success = html.startswith("<html")
        except Exception as e:
            print(e)
            success = False

        self.assertEqual(200, response.status_code, "Status code is not OK")
        self.assertTrue(success, "Response is not a valid HTML")

    def test_getdocument_csv(self):
        params = {
            "format": "csv",
            "MaxOrderID": "10800"
        }
        response = self.app.get('/demo?' + urlencode(params), headers=self.jwtHeader())

        success = False
        try:

            csv = response.data.decode("utf-8")
            success = True
        except Exception as e:
            print(e)
            success = False
        self.assertEqual(200, response.status_code, "Status code is not OK")
        self.assertTrue(success, "Response is not a valid CSV")

    def test_getdocument_xls(self):
        params = {
            "format": "xls",
            "MaxOrderID": "10800"
        }
        response = self.app.get('/demo?' + urlencode(params), headers=self.jwtHeader())
        self.assertEqual(200, response.status_code, "Status code is not OK")
        self.assertTrue(isinstance(response.data, bytes), "Response is not a valid XLS")

    def test_getdocument_xlsx(self):
        params = {
            "format": "xlsx",
            "MaxOrderID": "10800"
        }
        response = self.app.get('/demo?' + urlencode(params), headers=self.jwtHeader())
        self.assertEqual(200, response.status_code, "Status code is not OK")
        self.assertTrue(isinstance(response.data, bytes), "Response is not a valid XLSX")

    def test_getdocument_404(self):
        response = self.app.get('/test', headers=self.jwtHeader())
        self.assertEqual(404, response.status_code, "Status code is not OK")
