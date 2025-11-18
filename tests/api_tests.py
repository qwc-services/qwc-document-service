import os
import unittest
from urllib.parse import urlparse, parse_qs, urlencode

from flask import Response, json
from flask.testing import FlaskClient
from flask_jwt_extended import JWTManager, create_access_token

import server
JWTManager(server.app)


class ApiTestCase(unittest.TestCase):
    """Test case for server API"""

    def setUp(self):
        server.app.testing = True
        self.app = FlaskClient(server.app, Response)

    def tearDown(self):
        pass

    def jwtHeader(self, identity="test"):
        with server.app.test_request_context():
            access_token = create_access_token(identity)
        return {'Authorization': 'Bearer {}'.format(access_token)}

    def test_getdocument_pdf(self):
        params = {
            "TEST_PARAM": "FooBarBaz"
        }
        response = self.app.get('/test_report.pdf?' + urlencode(params), headers=self.jwtHeader())
        self.assertEqual(200, response.status_code, "Status code is not OK")
        self.assertTrue(isinstance(response.data, bytes), "Response is not a valid PDF")

    def test_getdocument_html(self):
        params = {
            "TEST_PARAM": "FooBarBaz"
        }
        response = self.app.get('/test_report.html?' + urlencode(params), headers=self.jwtHeader())

        success = False
        try:
            html = response.data.decode("utf-8")
            success = "<html" in html and "FooBarBaz" in html
        except Exception as e:
            print(e)
            success = False

        self.assertEqual(200, response.status_code, "Status code is not OK")
        self.assertTrue(success, "Response is not a valid HTML")

    def test_getdocument_csv(self):
        params = {
            "TEST_PARAM": "FooBarBaz"
        }
        response = self.app.get('/test_report.csv?' + urlencode(params), headers=self.jwtHeader())

        success = False
        try:

            csv = response.data.decode("utf-8")
            success = "FooBarBaz" in csv
        except Exception as e:
            print(e)
            success = False
        self.assertEqual(200, response.status_code, "Status code is not OK")
        self.assertTrue(success, "Response is not a valid CSV")

    def test_getdocument_bad_format(self):
        params = {
            "TEST_PARAM": "FooBarBaz"
        }
        response = self.app.get('/test_report.badformat?' + urlencode(params), headers=self.jwtHeader())
        self.assertEqual(400, response.status_code, "Status code is 400")

    def test_getdocument_xlsx(self):
        params = {
            "TEST_PARAM": "FooBarBaz"
        }
        response = self.app.get('/test_report.xlsx?' + urlencode(params), headers=self.jwtHeader())
        self.assertEqual(200, response.status_code, "Status code is not OK")
        self.assertTrue(isinstance(response.data, bytes), "Response is not a valid XLSX")

    def test_getdocument_404(self):
        response = self.app.get('/missing_report', headers=self.jwtHeader())
        self.assertEqual(404, response.status_code, "Status code is 404")

    def test_country_report_html(self):
        params = {
            "feature": 5
        }
        response = self.app.get('/Country.html?' + urlencode(params), headers=self.jwtHeader())
        success = False
        html = None
        try:
            html = response.data.decode("utf-8")
            success = "<html" in html
        except:
            success = False
        self.assertEqual(200, response.status_code, "Status code is not OK")
        self.assertTrue(success, "Response is not a valid HTML")
        self.assertTrue("Country name: Peru" in html, "Cannot find 'Country name: Peru' in generated HTML")
        self.assertTrue("Population: Less than one billion" in html, "Cannot find 'Population: Less than one billion' in generated HTML")


    def test_country_aggregated_report_html(self):
        params = {
            "feature": "4,5,6"
        }
        response = self.app.get('/Country.html?' + urlencode(params), headers=self.jwtHeader())
        success = False
        html = None
        try:
            html = response.data.decode("utf-8")
            success = "<html" in html
        except:
            success = False
        self.assertEqual(200, response.status_code, "Status code is not OK")
        self.assertTrue(success, "Response is not a valid HTML")
        self.assertTrue("Country name: Bolivia" in html, "Cannot find 'Country name: Bolivia' in generated HTML")
        self.assertTrue("Country name: Peru" in html, "Cannot find 'Country name: Peru' in generated HTML")
        self.assertTrue("Country name: Argentina" in html, "Cannot find 'Country name: Argentina' in generated HTML")

    def test_country_aggregated_all_report_html(self):
        params = {
            "feature": "*"
        }
        response = self.app.get('/Country.html?' + urlencode(params), headers=self.jwtHeader())
        success = False
        html = None
        try:
            html = response.data.decode("utf-8")
            success = "<html" in html
        except:
            success = False
        self.assertEqual(200, response.status_code, "Status code is not OK")
        self.assertTrue(success, "Response is not a valid HTML")
        self.assertEqual(html.count("Country name: "), 255, "Generated HTML does not contain the expected number of countries")

    def test_country_aggregated_single_report_bad_html(self):
        params = {
            "feature": "4,5,6",
            "single_report": 1
        }
        response = self.app.get('/Country.html?' + urlencode(params), headers=self.jwtHeader())
        success = False
        html = None
        try:
            error = response.data.decode("utf-8")
        except:
            success = False
        self.assertEqual(500, response.status_code, "Request didn't fail with internal server error")
        self.assertEqual(error, "Failed to compile report")

    def test_country_aggregated_single_report_html(self):
        params = {
            "feature": "4,5,6",
            "single_report": 1
        }
        response = self.app.get('/Country_single.html?' + urlencode(params), headers=self.jwtHeader())
        success = False
        html = None
        try:
            html = response.data.decode("utf-8")
            success = "<html" in html
        except:
            success = False
        self.assertEqual(200, response.status_code, "Status code is not OK")
        self.assertTrue(success, "Response is not a valid HTML")
        self.assertEqual(html.count("Country name: "), 3, "Generated HTML does not contain the expected number of countries")
        self.assertTrue("Bolivia" in html, "Response does not contain Bolivia")
        self.assertTrue("Peru" in html, "Response does not contain Peru")
        self.assertTrue("Argentina" in html, "Response does not contain Argentina")

    def test_point_report_unpermitted_subreport_html(self):
        params = {
            "feature": "1"
        }
        response = self.app.get('subdir/Point.html?' + urlencode(params), headers=self.jwtHeader())
        success = False
        html = None
        try:
            html = response.data.decode("utf-8")
            success = "<html" in html
        except:
            success = False
        self.assertEqual(200, response.status_code, "Status code is not OK")
        self.assertTrue(success, "Response is not a valid HTML")
        self.assertTrue("Point description: Example Point" in html, "Response does not contain 'Point description: Example Point'")
        self.assertTrue("Country name:" not in html, "Response contains 'Country name:'")

    def test_point_report_permitted_subreport_html(self):
        params = {
            "feature": "1",
            "COUNTRY_ID": "5"
        }
        response = self.app.get('subdir/Point.html?' + urlencode(params), headers=self.jwtHeader("admin"))
        success = False
        html = None
        try:
            html = response.data.decode("utf-8")
            success = "<html" in html
        except:
            success = False
        self.assertEqual(200, response.status_code, "Status code is not OK")
        self.assertTrue(success, "Response is not a valid HTML")
        self.assertTrue("Point description: Example Point" in html, "Response does not contain 'Point description: Example Point'")
        self.assertTrue("Country name: Peru" in html, "Response does not contain 'Country name: Peru'")

    def test_point_report_precompiled_permit_subreports_html(self):
        params = {
            "feature": "1",
            "COUNTRY_ID": "5"
        }
        os.environ['PERMIT_SUBREPORTS'] = '1'
        response = self.app.get('subdir/Point.html?' + urlencode(params), headers=self.jwtHeader("admin"))
        del os.environ['PERMIT_SUBREPORTS']
        success = False
        html = None
        try:
            html = response.data.decode("utf-8")
            success = "<html" in html
        except:
            success = False
        self.assertEqual(200, response.status_code, "Status code is not OK")
        self.assertTrue(success, "Response is not a valid HTML")
        self.assertTrue("Point description: Example Point" in html, "Response does not contain 'Point description: Example Point'")
        self.assertTrue("Country name: Peru" in html, "Response does not contain 'Country name: Peru'")

    def test_static_report_html(self):
        params = {
        }
        response = self.app.get('Static.html?' + urlencode(params), headers=self.jwtHeader("admin"))
        success = False
        html = None
        try:
            html = response.data.decode("utf-8")
            success = "<html" in html
        except:
            success = False
        self.assertEqual(200, response.status_code, "Status code is not OK")
        self.assertTrue(success, "Response is not a valid HTML")
        self.assertTrue("Static text" in html, "Response does not contain 'Static text'")
