import configparser
import glob
import io
import jpype
import jpype.imports
from jpype.types import *
import os
import re
import shutil
import tempfile
import traceback
import uuid
from xml.etree import ElementTree
from flask import make_response, send_file
from sqlalchemy.sql import text as sql_text

from qwc_services_core.database import DatabaseEngine


db_engine = DatabaseEngine()


class ReportCompiler:
    """ Report compiler class. """
    def __init__(self, logger):
        """ Constructor.

            :param logger obj: Application logger
        """

        self.logger = logger

        self.DriverManager = jpype.JPackage('java').sql.DriverManager
        self.ArrayList = jpype.JPackage('java').util.ArrayList
        self.ManagementFactory = jpype.JPackage('java').lang.management.ManagementFactory
        self.SimpleJasperReportsContext = jpype.JPackage('net').sf.jasperreports.engine.SimpleJasperReportsContext
        self.SimpleFontFace = jpype.JPackage('net').sf.jasperreports.engine.fonts.SimpleFontFace
        self.FontFamily = jpype.JPackage('net').sf.jasperreports.engine.fonts.FontFamily
        self.SimpleFontFamily = jpype.JPackage('net').sf.jasperreports.engine.fonts.SimpleFontFamily
        self.JasperCompileManager = jpype.JPackage('net').sf.jasperreports.engine.JasperCompileManager
        self.JasperFillManager = jpype.JPackage('net').sf.jasperreports.engine.JasperFillManager
        self.JasperExportManager = jpype.JPackage('net').sf.jasperreports.engine.JasperExportManager
        self.JRSwapFile = jpype.JPackage('net').sf.jasperreports.engine.util.JRSwapFile
        self.JRSwapFileVirtualizer = jpype.JPackage('net').sf.jasperreports.engine.fill.JRSwapFileVirtualizer
        self.JRParameter = jpype.JPackage('net').sf.jasperreports.engine.JRParameter
        self.JREmptyDataSource = jpype.JPackage('net').sf.jasperreports.engine.JREmptyDataSource
        self.SimpleExporterInput = jpype.JPackage('net').sf.jasperreports.export.SimpleExporterInput
        self.SimpleExporterInputItem = jpype.JPackage('net').sf.jasperreports.export.SimpleExporterInputItem
        self.SimpleHtmlExporterOutput = jpype.JPackage('net').sf.jasperreports.export.SimpleHtmlExporterOutput
        self.SimpleOutputStreamExporterOutput = jpype.JPackage('net').sf.jasperreports.export.SimpleOutputStreamExporterOutput
        self.SimpleWriterExporterOutput = jpype.JPackage('net').sf.jasperreports.export.SimpleWriterExporterOutput
        self.SimpleXmlExporterOutput = jpype.JPackage('net').sf.jasperreports.export.SimpleXmlExporterOutput
        self.ByteArrayOutputStream = jpype.JPackage('java').io.ByteArrayOutputStream
        self.JRPdfExporter = jpype.JPackage('net').sf.jasperreports.engine.export.JRPdfExporter
        self.HtmlExporter = jpype.JPackage('net').sf.jasperreports.engine.export.HtmlExporter
        self.JRCsvExporter = jpype.JPackage('net').sf.jasperreports.engine.export.JRCsvExporter
        self.JRDocxExporter = jpype.JPackage('net').sf.jasperreports.engine.export.ooxml.JRDocxExporter
        self.JROdsExporter = jpype.JPackage('net').sf.jasperreports.engine.export.oasis.JROdsExporter
        self.JROdtExporter = jpype.JPackage('net').sf.jasperreports.engine.export.oasis.JROdtExporter
        self.JRPptxExporter = jpype.JPackage('net').sf.jasperreports.engine.export.ooxml.JRPptxExporter
        self.JRRtfExporter = jpype.JPackage('net').sf.jasperreports.engine.export.JRRtfExporter
        self.JRXlsxExporter = jpype.JPackage('net').sf.jasperreports.engine.export.ooxml.JRXlsxExporter
        self.JRXmlExporter = jpype.JPackage('net').sf.jasperreports.engine.export.JRXmlExporter
        self.DefaultJasperReportsContext = jpype.JPackage('net').sf.jasperreports.engine.DefaultJasperReportsContext

        self.DefaultJasperReportsContext.getInstance().setProperty("net.sf.jasperreports.compiler.temp.dir", "/tmp/");
        self.DefaultJasperReportsContext.getInstance().setProperty("net.sf.jasperreports.awt.ignore.missing.font", "true")
        self.DefaultJasperReportsContext.getInstance().setProperty("net.sf.jasperreports.default.font.name", "DejaVu Sans")

        self.jContext = self.SimpleJasperReportsContext()


        # Load custom fonts
        custom_fonts_dir = os.getenv("FONT_DIR", os.path.join(os.path.dirname(__file__), 'fonts'))
        self.logger.info("Looking for additional fonts in %s" % custom_fonts_dir)
        custom_fonts = {}
        for fontpath in glob.glob(os.path.join(custom_fonts_dir, "*.ttf")):
            filename = os.path.basename(fontpath)
            name, face = (filename[:-4] + "-Regular").split("-")[0:2]
            custom_fonts[name] = custom_fonts.get(name, {})
            custom_fonts[name][face] = fontpath

        fonts = self.ArrayList()
        for font_name, font_faces in custom_fonts.items():
            font_family = self.SimpleFontFamily(self.jContext)
            font_family.setName(font_name)
            font_family.setPdfEmbedded(True)
            font_family.setPdfEncoding("Identity-H")
            added_faces = []
            faces = {
                'Regular': font_family.setNormalFace,
                'Bold': font_family.setBoldFace,
                'Italic': font_family.setItalicFace,
                'BoldItalic': font_family.setBoldItalicFace
            }
            for face, setter in faces.items():
                if face in font_faces:
                    font_face = self.SimpleFontFace(self.jContext)
                    font_face.setTtf(font_faces[face])
                    setter(font_face)
                    added_faces.append(face)
            if added_faces:
                self.logger.info("Adding custom font %s with faces %s" % (font_name, ",".join(added_faces)))
                fonts.add(font_family)
        self.jContext.setExtensions(self.FontFamily, fonts)

        # Parse pgservices
        self.pgservices = {}
        pgservicefile = os.getenv("PGSERVICEFILE", os.path.expanduser("~/.pg_service.conf"))
        if os.path.isfile(pgservicefile):
            config = configparser.ConfigParser(interpolation=None)
            config.read(pgservicefile)
            for section in config.sections():
                self.pgservices[section] = dict(config.items(section))

    def resolve_datasource(self, datasource, report_filename, open_conns):
        """ Return a DB connection for a datasource name.

            The datasource name is expected to be the name of a pgservice definition.

            :param datasource str: The datasource name (pgservice definition name)
            :param report_filename str: The filename of the jrxml report were the datasource appears
            :param open_conns list: List to which append opened connections which need to be closed
        """
        if datasource == "NO_DATA_ADAPTER":
            return self.JREmptyDataSource()
        pgservice = self.pgservices.get(datasource)
        if not pgservice:
            self.logger.warning("Cannot resolve datasource %s for report %s to a pgservice" % (datasource, report_filename))
            return self.JREmptyDataSource()
        else:
            dbUrl = "jdbc:postgresql://{host}:{port}/{dbname}".format(
                host=pgservice.get("host"), port=pgservice.get("port"), dbname=pgservice.get("dbname")
            )
            dbUser = pgservice.get("user")
            dbPass = pgservice.get("password")
            self.logger.info("Resolved datasource %s to %s" % (datasource, dbUrl))
            conn = self.DriverManager.getConnection(dbUrl, dbUser, dbPass)
            self.logger.info("Connected to database %s" % (dbUrl))
            open_conns.append(conn)
            return conn

    def compile_report(self, report_filename, fill_params, tmpdir, resources, permitted_resources, single_report, compile_subreport=False):
        """ Compile a report (or subreport), resolving the datasource, mapping parameter values, and processing permitted subreports.

            :param report_filename str: The filename of the jrxml report source
            :param fill_params dict: Report fill parameters
            :param tmpdir str: Tempdir in which to write processed .jrxml sources and compiled .jasper reports
            :param resources dict: Resource configuration
            :param permitted_resources list: List of permitted resources
            :param single_report bool: Whether to produce single report, passing the array of feature IDs, instead of producing one report per feature
            :param compile_subreport bool: Whether a subreport is being compiled
        """

        self.logger.info("Processing report %s" % report_filename)
        reportdir_idx = len(os.path.abspath(self.report_dir)) + 1
        # Copy to temp dir
        temp_report_filename = os.path.join(tmpdir, report_filename[reportdir_idx:])
        self.logger.info("Copying report to %s" % temp_report_filename)
        os.makedirs(os.path.dirname(temp_report_filename), exist_ok=True)
        shutil.copyfile(report_filename, temp_report_filename)

        # Parse report
        with open(temp_report_filename) as fh:
            doc = ElementTree.parse(fh)
        if not doc:
            self.logger.error("Failed to read report %s" % temp_report_filename)
            return None
        root = doc.getroot()
        namespace = {'jasper': 'http://jasperreports.sourceforge.net/jasperreports'}

        # Extract default data adapter and subreports
        #  cut off leading /report_dir/ and trailing .jrxml
        template = report_filename[reportdir_idx:-6]
        self.logger.info("Report template name is %s" % template)
        resource = next((x for x in resources if x["template"] == template), None)
        data_table = None
        data_pkey = None
        data_param = None
        if resource and resource.get("datasource") is not None:
            datasource = resource.get("datasource")
        else:
            try:
                datasource = root.find("jasper:property[@name='com.jaspersoft.studio.data.defaultdataadapter']", namespace).get("value")
            except:
                datasource = None
        self.logger.info("Report datasource: %s" % datasource)
        if resource:
            data_table = resource.get("table")
            data_pkey = resource.get("primary_key")
            data_param = resource.get("parameter_name")

        # Try to extract primary key and table name
        if not compile_subreport and datasource and datasource != "NO_DATA_ADAPTER":
            queryString = root.find(".//jasper:queryString", namespace)
            if queryString is not None and data_table is None or data_pkey is None:
                statement = re.sub(r"\s+", " ", queryString.text)
                m = re.search(r'(["A-Za-z0-9_.]+)\s+WHERE', statement)
                if m:
                    data_table = m.group(1)
                m = re.search(r'(["A-Za-z0-9_.]+)\s*=\s*\$P\{(\w+)\}', statement)
                if m:
                    data_pkey = m.group(1).strip('"')
                    data_param = m.group(2)
                    self.logger.info("Data table=%s, PK=%s, param=%s " % (data_table, data_pkey, data_param))
            if queryString is not None and (data_table is None or data_pkey is None or data_param is None):
                self.logger.error("Unable to extract table name/primary key/parameter from query, please define them manually in the resource entry")
                return None

            # Resolve feature="*"
            if fill_params.get("feature") == "*":
                    db = db_engine.db_engine("postgresql:///?service="+ datasource)
                    self.logger.info("Resolving feature=*")
                    with db.connect() as conn:
                        query = sql_text("SELECT {pkey} from {table}".format(pkey=data_pkey, table=data_table))
                        result = conn.execute(query).mappings()
                        to_str_if_uuid = lambda value: str(value) if isinstance(value, uuid.UUID) else value
                        fill_params[data_param] = list([to_str_if_uuid(row[data_pkey]) for row in result])
                        self.logger.info("Changed feature=* to %s=%s" % (data_param, fill_params[data_param]))
                        del fill_params["feature"]
            elif fill_params.get("feature") is not None:
                fill_params[data_param] = fill_params["feature"].split(",")
                self.logger.info("Changed feature=%s to %s=%s" % (fill_params["feature"], data_param, fill_params[data_param]))
                if data_param != "feature":
                    del fill_params["feature"]
            elif fill_params.get(data_param) is not None:
                # data_param is expected to be an array
                fill_params[data_param] = [fill_params[data_param]]

        # Iterate over parameters, try to map parameters
        data_param_nested_class = None
        parameters = root.findall(".//jasper:parameter", namespace)
        for parameter in parameters:
            parameterName = parameter.get("name")
            if parameterName in fill_params:
                parameterClass = parameter.get("class")
                if parameterName == data_param:
                    data_param_nested_class = parameter.get("nestedType")
                if isinstance(fill_params[parameterName], list):
                    try:
                        fill_params[parameterName] = [jpype.JClass(parameterClass)(value) for value in fill_params[parameterName]]
                    except:
                        pass
                else:
                    try:
                        fill_params[parameterName] = jpype.JClass(parameterClass)(fill_params[parameterName])
                    except:
                        pass

        # Iterate over subreports, filter out unpermitted reports, compile permitted reports
        opened_connections = []
        subreports = root.findall(".//jasper:subreport", namespace)
        for subreport in subreports:
            connectionExpression = subreport.find("./jasper:connectionExpression", namespace)
            subreportExpression = subreport.find("./jasper:subreportExpression", namespace)
            subreport_filename = subreportExpression.text.strip('"').replace('$P{REPORT_DIR}', self.report_dir)
            subreport_filename = os.path.abspath(os.path.join(os.path.dirname(report_filename), subreport_filename))
            subreport_filename = subreport_filename[:-7] + ".jrxml"
            subreport_template = subreport_filename[reportdir_idx:-6]
            self.logger.info("Subreport filename %s" % subreport_filename)
            self.logger.info("Subreport template %s" % subreport_template)
            if os.path.exists(subreport_filename):
                if self.permit_subreports or subreport_template in permitted_resources:
                    subreport_result = self.compile_report(subreport_filename, fill_params, tmpdir, resources, permitted_resources, single_report, True)
                    if not subreport_result:
                        self.logger.info("Failed to compile subreport %s" % subreport_filename)
                        subreportExpression.text = ""
                    else:
                        subreport_output, subreport_datasource = subreport_result
                        subreportExpression.text = '"%s"' % subreport_output
                        # Extract subreport datasource param name
                        if connectionExpression is not None:
                            m = re.match(r'^\$P\{(\w+)\}$', connectionExpression.text)
                            if m:
                                fill_params[m.group(1)] = self.resolve_datasource(subreport_datasource, subreport_filename, opened_connections)
                else:
                    self.logger.info("Filtering out unpermitted subreport %s" % subreport_filename)
                    subreportExpression.text = ""
            else:
                self.logger.warning("Subreport path does not exist: %s" % subreport_filename)

        # Write modified jrxml
        ElementTree.register_namespace("", "http://jasperreports.sourceforge.net/jasperreports")
        ElementTree.ElementTree(root).write(temp_report_filename)

        result = None
        if compile_subreport:
            # Compile subreport
            output_name = temp_report_filename[:-6] + ".jasper"
            self.logger.info("Compiling subreport %s" % template)
            try:
                self.JasperCompileManager.getInstance(self.jContext).compileToFile(temp_report_filename, output_name)
                result = (output_name, datasource)
            except Exception as e:
                self.logger.error("Exception compiling report: %s" % e)
                self.logger.debug(traceback.format_exc())
                self.print_memory_usage()
        else:
            self.logger.info("Compiling report %s" % template)
            self.logger.info("Report parameters: %s" % str(fill_params))
            # Compile, fill and export report
            conn = self.resolve_datasource(datasource, report_filename, opened_connections)
            try:
                jasperReport = self.JasperCompileManager.getInstance(self.jContext).compile(temp_report_filename)
                jasperPrints = self.ArrayList()
                if data_param is not None and data_param in fill_params:
                    if not single_report:
                        feature_ids = fill_params[data_param]
                        for feature_id in feature_ids:
                            fill_params[data_param] = feature_id
                            jasperPrints.add(self.SimpleExporterInputItem(self.JasperFillManager.getInstance(self.jContext).fill(jasperReport, fill_params, conn)))
                    else:
                        data_param_list = self.ArrayList()
                        for value in fill_params[data_param]:
                            data_param_list.add(jpype.JClass(data_param_nested_class)(value))
                        fill_params[data_param] = data_param_list
                        jasperPrints.add(self.SimpleExporterInputItem(self.JasperFillManager.getInstance(self.jContext).fill(jasperReport, fill_params, conn)))
                else:
                    jasperPrints.add(self.SimpleExporterInputItem(self.JasperFillManager.getInstance(self.jContext).fill(jasperReport, fill_params, conn)))
                result = jasperPrints
            except Exception as e:
                self.logger.error("Exception compiling/filling report: %s" % e)
                self.logger.debug(traceback.format_exc())
                self.print_memory_usage()

        # Cleanup connections
        for conn in opened_connections:
            conn.close()

        return result

    def human_size(self, num):
        for unit in ("", "K", "M", "G", "T"):
            if abs(num) < 1024.0:
                return f"{num:3.1f}{unit}"
            num /= 1024.0
        return f"{num:.1f}P"

    def print_memory_usage(self):
        memory_mxbean = self.ManagementFactory.getMemoryMXBean()
        heap_memory_usage = memory_mxbean.getHeapMemoryUsage()
        non_heap_memory_usage = memory_mxbean.getNonHeapMemoryUsage()
        self.logger.debug("Memory usage: heap=%s / %s, non-heap=%s / %s" % (
            self.human_size(heap_memory_usage.getUsed()), self.human_size(heap_memory_usage.getMax()),
            self.human_size(non_heap_memory_usage.getUsed()), self.human_size(non_heap_memory_usage.getMax()))
        )

    def get_document(self, config, permitted_resources, tenant, template, fill_params, format):
        """Return report with specified template and format.

        :param obj config: Service config
        :param list permitted_resources: Document template permissions
        :param str tenant: The tenant name
        :param str template: Template ID
        :param dict fill_params: Report fill parameters
        :param str format: Document format
        """
        self.print_memory_usage()

        supported_formats = {
            "pdf": "application/pdf",
            "html": "text/html",
            "csv": "text/csv",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "ods": "application/vnd.oasis.opendocument.spreadsheet",
            "odt": "application/vnd.oasis.opendocument.text",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "rtf": "application/rtf",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "xml": "application/xml"
        }

        self.logger.info("Requested report template %s format %s" % (template, format))

        if not format in supported_formats:
            self.logger.warning("Unsupported format: %s" % format)
            return make_response("Unsupported format: %s" % format, 400)

        resources = (config.resources() or {}).get('document_templates', [])

        self.report_dir = config.get('report_dir', '/reports').rstrip('/')
        self.permit_subreports = config.get('permit_subreports', False)
        self.logger.info("Report dir is '%s'", self.report_dir)

        if template not in permitted_resources:
            self.logger.info("Missing permissions for template '%s'", template)
            return make_response("Missing or restricted template: %s" % template, 404)

        # Resolve template by matching filename
        report_filename = os.path.abspath(os.path.join(self.report_dir, template + ".jrxml"))
        if not os.path.isfile(report_filename):
            self.logger.info("Template '%s' not found", template)
            return make_response("Missing or restricted template: %s" % template, 404)

        # Set resource dir in fill_params
        fill_params["REPORT_DIR"] = self.report_dir + "/"

        # Set the tenant in fill_params
        fill_params["TENANT"] = tenant

        # Read/clear single_report param
        single_report = False
        if "single_report" in fill_params:
            single_report = fill_params.get("single_report", "").lower() in ["1","true"]
            del fill_params["single_report"]


        tmpdir = tempfile.mkdtemp()

        # Set virtualizer in fill_params
        virtualizerConfig = config.get('virtualizer')

        if virtualizerConfig:
            swapfileBlocksize = virtualizerConfig.get('swapfile_blocksize', 4096)
            swapfileMinGrowCount = virtualizerConfig.get('swapfile_mingrowcount', 100)
            virtualizerMaxsize = virtualizerConfig.get('virtualizer_maxsize', 5)

            swapFile = self.JRSwapFile(tmpdir, swapfileBlocksize, swapfileMinGrowCount)
            virtualizer = self.JRSwapFileVirtualizer(virtualizerMaxsize, swapFile, True)
            fill_params[self.JRParameter.REPORT_VIRTUALIZER] = virtualizer

        # Compile report
        jasperPrints = self.compile_report(report_filename, fill_params, tmpdir, resources, permitted_resources, single_report)
        shutil.rmtree(tmpdir)

        if jasperPrints is None:
            return make_response("Failed to compile report", 500)

        # Export report
        self.logger.info("Exporting report")
        exporter = None
        if format == "pdf":
            exporter = self.JRPdfExporter(self.jContext)
            output = self.SimpleOutputStreamExporterOutput
        if format == "html":
            exporter = self.HtmlExporter(self.jContext)
            output = self.SimpleHtmlExporterOutput
        elif format == "csv":
            exporter = self.JRCsvExporter(self.jContext)
            output = self.SimpleWriterExporterOutput
        elif format == "docx":
            exporter = self.JRDocxExporter(self.jContext)
            output = self.SimpleOutputStreamExporterOutput
        elif format == "ods":
            exporter = self.JROdsExporter(self.jContext)
            output = self.SimpleOutputStreamExporterOutput
        elif format == "odt":
            exporter = self.JROdtExporter(self.jContext)
            output = self.SimpleOutputStreamExporterOutput
        elif format == "pptx":
            exporter = self.JRPptxExporter(self.jContext)
            output = self.SimpleOutputStreamExporterOutput
        elif format == "rtf":
            exporter = self.JRRtfExporter(self.jContext)
            output = self.SimpleWriterExporterOutput
        elif format == "xlsx":
            exporter = self.JRXlsxExporter(self.jContext)
            output = self.SimpleOutputStreamExporterOutput
        elif format == "xml":
            exporter = self.JRXmlExporter(self.jContext)
            output = self.SimpleXmlExporterOutput

        try:
            exporter.setExporterInput(self.SimpleExporterInput(jasperPrints))
            outputStream = self.ByteArrayOutputStream()
            exporter.setExporterOutput(output(outputStream))
            exporter.exportReport()
            result = io.BytesIO(outputStream.toByteArray())
        except Exception as e:
            self.logger.error("Exception exporting report to %s: %s" % (format, e))
            return make_response("Failed to export report", 500)

        self.print_memory_usage()

        return send_file(
            result,
            download_name=os.path.splitext(os.path.basename(report_filename))[0] + "." + format,
            as_attachment=True,
            mimetype=supported_formats[format]
        )
