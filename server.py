import os
import sys
from urllib.parse import urlencode

from flask import Flask, Response, abort, request, stream_with_context, jsonify
from flask_restplus import Api, Resource, fields, reqparse
import requests

from qwc_services_core.api import CaseInsensitiveArgument
from qwc_services_core.app import app_nocache
from flask_jwt_extended import jwt_optional, get_jwt_identity
from qwc_services_core.jwt import jwt_manager
from qwc_services_core.tenant_handler import TenantHandler
from qwc_services_core.runtime_config import RuntimeConfig
from qwc_services_core.permissions_reader import PermissionsReader


# Flask application
app = Flask(__name__)
app_nocache(app)
api = Api(app, version='1.0', title='Document service API',
          description="""API for QWC Document service.

The document service delivers reports from the Jasper reporting service.
          """,
          default_label='Document operations', doc='/api/')
app.config.SWAGGER_UI_DOC_EXPANSION = 'list'

# disable verbose 404 error message
app.config['ERROR_404_HELP'] = False

auth = jwt_manager(app, api)

tenant_handler = TenantHandler(app.logger)
config_handler = RuntimeConfig("document", app.logger)


def get_document(tenant, template, format):
    """Return report with specified template and format.

    :param str template: Template ID
    :param str format: Document format
    """
    config = config_handler.tenant_config(tenant)
    jasper_service_url = config.get(
        'jasper_service_url', 'http://localhost:8002/reports')
    jasper_timeout = config.get("jasper_timeout", 60)

    resources = config.resources().get('document_templates', [])
    permissions_handler = PermissionsReader(tenant, app.logger)
    permitted_resources = permissions_handler.resource_permissions(
        'document_templates', get_jwt_identity()
    )
    if template in permitted_resources:
        resource = list(filter(
            lambda entry: entry.get("template") == template, resources))
        if len(resource) != 1:
            app.logger.info("Template '%s' not found in config", template)
            abort(404)
        jasper_template = resource[0]['report_filename']

        # http://localhost:8002/reports/BelasteteStandorte/?format=pdf&p1=v1&..
        url = "%s/%s/" % (jasper_service_url, jasper_template)
        params = {"format": format}
        for k, v in request.args.lists():
            params[k] = v

        app.logger.info("Forward request to %s?%s" %
                        (url, urlencode(params)))

        response = requests.get(url, params=params, timeout=jasper_timeout)
        r = Response(
            stream_with_context(response.iter_content(chunk_size=16*1024)),
            content_type=response.headers['content-type'],
            status=response.status_code)
        return r
    else:
        app.logger.info("Missing permissions for template '%s'", template)
        abort(404)


# routes
@api.route('/<template>')
@api.param('template', 'The report template')
class Document(Resource):
    @api.doc('document')
    @jwt_optional
    def get(self, template):
        """Request document

        Return report with specified template.

        The extension is inferred from the template name, and defaults to PDF.

        Query parameters are passed to the reporting engine.
        """
        tenant = tenant_handler.tenant()
        pos = template.rfind('.')
        if pos != -1:
            format = template[pos + 1:]
            template = template[:pos]
        else:
            format = 'pdf'
        return get_document(tenant, template, format)


""" readyness probe endpoint """
@app.route("/ready", methods=['GET'])
def ready():
    return jsonify({"status": "OK"})


""" liveness probe endpoint """
@app.route("/healthz", methods=['GET'])
def healthz():
    return jsonify({"status": "OK"})


# local webserver
if __name__ == '__main__':
    print("Starting GetDocument service...")
    app.run(host='localhost', port=5018, debug=True)
