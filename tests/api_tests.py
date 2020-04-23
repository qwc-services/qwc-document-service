import os
import unittest
from urllib.parse import urlparse, parse_qs, urlencode

from flask import Response, json
from flask.testing import FlaskClient
from flask_jwt_extended import JWTManager, create_access_token

os.environ["JASPER_SERVICE_URL"] = "http://localhost:6000"

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

    def test_getdocument(self):
        params = {
            'x': 123,
            'y': 456,
            'foo': 'bar'
        }
        response = self.app.get('/test_template?' + urlencode(params), headers=self.jwtHeader())
        self.assertEqual(200, response.status_code, "Status code is not OK")

        response_data = json.loads(response.data)
        data = json.loads(response.data)
        self.assertRegex(data['path'], r'^[\w-]+/Blank_A4/$', 'Report template name mismatch')
        self.assertEqual('GET', data['method'], 'Method mismatch')
        jasper_params = data['params']
        for param in params.keys():
            self.assertTrue(param in jasper_params, "Parameter %s missing in response" % param)
            self.assertEqual(jasper_params[param], str(params[param]), "Parameter %s mismatch" % param)
        self.assertTrue('format' in jasper_params, "Parameter %s missing in response" % 'format')
        self.assertEqual(jasper_params['format'], 'pdf', "Parameter %s mismatch" % 'format')

    def test_getdocument_xls(self):
        params = {
            'x': 123,
            'y': 456,
            'foo': 'bar'
        }
        response = self.app.get('/test_template.xls?' + urlencode(params), headers=self.jwtHeader())
        self.assertEqual(200, response.status_code, "Status code is not OK")

        response_data = json.loads(response.data)
        data = json.loads(response.data)
        self.assertRegex(data['path'], r'^[\w-]+/Blank_A4/$', 'Report template name mismatch')
        self.assertEqual('GET', data['method'], 'Method mismatch')
        jasper_params = data['params']
        for param in params.keys():
            self.assertTrue(param in jasper_params, "Parameter %s missing in response" % param)
            self.assertEqual(jasper_params[param], str(params[param]), "Parameter %s mismatch" % param)
        self.assertTrue('format' in jasper_params, "Parameter %s missing in response" % 'format')
        self.assertEqual(jasper_params['format'], 'xls', "Parameter %s mismatch" % 'format')
