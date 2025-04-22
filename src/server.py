import glob
import jpype
import os
import requests
import multiprocessing
import shutil
import tempfile
import traceback

from flask import Flask, Response, request, jsonify, make_response, Blueprint
from flask_restx import Api, Resource

from qwc_services_core.app import app_nocache
from qwc_services_core.auth import auth_manager, optional_auth, get_identity
from qwc_services_core.tenant_handler import (
    TenantHandler, TenantPrefixMiddleware, TenantSessionInterface)
from qwc_services_core.runtime_config import RuntimeConfig
from qwc_services_core.permissions_reader import PermissionsReader
from report_compiler import ReportCompiler


# Flask application
app = Flask(__name__)
mounted_app = Blueprint('mounted_app', __name__, url_prefix=os.getenv('SERVICE_MOUNTPOINT', '/'))

app_nocache(app)
api = Api(mounted_app, version='1.0', title='Document service API',
          description="""API for QWC Document service.

The document service delivers reports from the Jasper reporting service.
          """,
          default_label='Document operations', doc='/api/')
app.config.SWAGGER_UI_DOC_EXPANSION = 'list'

# disable verbose 404 error message
app.config['ERROR_404_HELP'] = False

app.register_blueprint(mounted_app)

auth = auth_manager(app, api)

tenant_handler = TenantHandler(app.logger)
app.wsgi_app = TenantPrefixMiddleware(app.wsgi_app)
app.session_interface = TenantSessionInterface()

config_handler = RuntimeConfig("document", app.logger)

def get_identity_or_auth(config):
    identity = get_identity()
    if not identity and config.get("basic_auth_login_url"):
        # Check for basic auth
        auth = request.authorization
        if auth:
            headers = {}
            if tenant_handler.tenant_header:
                # forward tenant header
                headers[tenant_handler.tenant_header] = tenant_handler.tenant()
            for login_url in ogc_service.basic_auth_login_url:
                app.logger.debug(f"Checking basic auth via {login_url}")
                data = {'username': auth.username, 'password': auth.password}
                resp = requests.post(login_url, data=data, headers=headers)
                if resp.ok:
                    json_resp = json.loads(resp.text)
                    app.logger.debug(json_resp)
                    return json_resp.get('identity')
            # Return WWW-Authenticate header, e.g. for browser password prompt
            # raise Unauthorized(
            #     www_authenticate='Basic realm="Login Required"')
    return identity


def get_document_worker(config, permitted_resources, tenant, template, args, format):
    result = None

    try:
        app.logger.debug("Starting JVM")
        libdir = os.path.join(os.path.dirname(__file__), 'libs')
        classpath = glob.glob(os.path.join(libdir, '*.jar'))
        classpath.append(libdir)

        max_memory = config.get('max_memory', '1024M')
        app.logger.info("The maximum Java heap size is set to '%s'", max_memory)

        tmpdir = tempfile.mkdtemp()
        jpype.startJVM("-DJava.awt.headless=true", "-Xmx" + max_memory, "-Djava.util.logging.config.file=" + os.path.join(libdir, "logging.properties"), classpath=classpath)
        jpype.java.lang.System.setOut(jpype.java.io.PrintStream(jpype.java.io.File(os.path.join(tmpdir, "stdout"))))
        jpype.java.lang.System.setErr(jpype.java.io.PrintStream(jpype.java.io.File(os.path.join(tmpdir, "stderr"))))

        report_compiler = ReportCompiler(app.logger)
        result = report_compiler.get_document(config, permitted_resources, tenant, template, dict(request.args), format)

    except Exception as e:
        app.logger.debug(str(e))
        app.logger.debug(traceback.format_exc())
        result = make_response("Failed to compile report", 500)
    finally:
        if jpype.isJVMStarted():
            jpype.shutdownJVM()
            app.logger.debug("Shutdown JVM")

    try:
        with open(os.path.join(tmpdir, "stdout")) as fh:
            app.logger.debug("JVM stdout:\n" + fh.read())
    except:
        pass
    try:
        with open(os.path.join(tmpdir, "stderr")) as fh:
            app.logger.debug("JVM stderr:\n" + fh.read())
    except:
        pass
    shutil.rmtree(tmpdir)

    return result


# routes
@api.route('/<path:template>')
@api.param('template', 'The report template')
class Document(Resource):
    @api.doc('document')
    @optional_auth
    def get(self, template):
        """Return report with specified template.

        The extension is inferred from the template name, and defaults to PDF.

        Query parameters are passed to the reporting engine.
        """
        tenant = tenant_handler.tenant()
        config = config_handler.tenant_config(tenant)
        identity = get_identity_or_auth(config)
        permissions_handler = PermissionsReader(tenant, app.logger)
        permitted_resources = permissions_handler.resource_permissions(
            'document_templates', identity
        )

        pos = template.rfind('.')
        if pos != -1:
            format = template[pos + 1:]
            template = template[:pos]
        else:
            format = 'pdf'

        with multiprocessing.Pool(1) as pool:
            result = pool.apply(get_document_worker, args=(config, permitted_resources, tenant, template, dict(request.args), format))

        return result


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
    app.run(host='localhost', port=5020, debug=True)
