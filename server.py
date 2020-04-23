import os
import sys
from urllib.parse import urlencode

from flask import Flask, Response, abort, request, stream_with_context
from flask_restplus import Api, Resource, fields, reqparse
import requests

from qwc_services_core.api import CaseInsensitiveArgument
# from qwc_services_core.app import app_nocache
from qwc_services_core.auth import auth_manager, optional_auth, get_auth_user
from qwc_services_core.permission import PermissionClient


# Flask application
app = Flask(__name__)
# app_nocache(app)
api = Api(app, version='1.0', title='Document service API',
          description="""API for SO!MAP Document service.

The document service delivers reports from the Jasper reporting service.
          """,
          default_label='Document operations', doc='/api/')
app.config.SWAGGER_UI_DOC_EXPANSION = 'list'

# disable verbose 404 error message
app.config['ERROR_404_HELP'] = False

auth = auth_manager(app, api)

JASPER_SERVICE_URL = os.environ.get('JASPER_SERVICE_URL',
                                    'http://localhost:8002/reports')
try:
    JASPER_TIMEOUT = int(os.environ.get('JASPER_TIMEOUT', 60))
except:
    JASPER_TIMEOUT = 60

permission = PermissionClient()


def get_document(template, format):
    """Return report with specified template and format.

    :param str template: Template ID
    :param str format: Document format
    """
    permissions = permission.document_permissions(
        template, get_auth_user()
    )
    app.logger.info(permissions)
    if permissions:
        jasper_template = os.path.splitext(
            permissions['report_filename']
        )[0]
        # http://localhost:8002/reports/BelasteteStandorte/?format=pdf&p1=v1&..
        url = "%s/%s/" % (JASPER_SERVICE_URL, jasper_template)
        params = {"format": format}
        for k, v in request.args.lists():
            params[k] = v

        app.logger.info("Forward request to %s?%s" %
                        (url, urlencode(params)))

        response = requests.get(url, params=params, timeout=JASPER_TIMEOUT)
        r = Response(
            stream_with_context(response.iter_content(chunk_size=16*1024)),
            content_type=response.headers['content-type'],
            status=response.status_code)
        return r
    else:
        abort(404)


# routes
@api.route('/<template>')
@api.param('template', 'The report template')
class Document(Resource):
    @api.doc('document')
    @optional_auth
    def get(self, template):
        """Request document

        Return report with specified template.

        The extension is inferred from the template name, and defaults to PDF.

        Query parameters are passed to the reporting engine.
        """
        pos = template.rfind('.')
        if pos != -1:
            format = template[pos + 1:]
            template = template[:pos]
        else:
            format = 'pdf'
        return get_document(template, format)


# local webserver
if __name__ == '__main__':
    print("Starting GetDocument service...")
    app.run(host='localhost', port=5018, debug=True)
