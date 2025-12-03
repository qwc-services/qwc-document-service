import configparser
import freetype
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

        self.ByteArrayOutputStream = jpype.JPackage('java').io.ByteArrayOutputStream
        self.ManagementFactory = jpype.JPackage('java').lang.management.ManagementFactory
        self.DriverManager = jpype.JPackage('java').sql.DriverManager
        self.ArrayList = jpype.JPackage('java').util.ArrayList
        self.JasperCompileManager = jpype.JPackage('net').sf.jasperreports.engine.JasperCompileManager
        self.JasperExportManager = jpype.JPackage('net').sf.jasperreports.engine.JasperExportManager
        self.JasperFillManager = jpype.JPackage('net').sf.jasperreports.engine.JasperFillManager
        self.JREmptyDataSource = jpype.JPackage('net').sf.jasperreports.engine.JREmptyDataSource
        self.JRParameter = jpype.JPackage('net').sf.jasperreports.engine.JRParameter
        self.JRSubreport = jpype.JPackage('net').sf.jasperreports.engine.JRSubreport
        self.JasperReport = jpype.JPackage('net').sf.jasperreports.engine.JasperReport
        self.SimpleJasperReportsContext = jpype.JPackage('net').sf.jasperreports.engine.SimpleJasperReportsContext
        self.JRSwapFileVirtualizer = jpype.JPackage('net').sf.jasperreports.engine.fill.JRSwapFileVirtualizer
        self.SimpleFontFace = jpype.JPackage('net').sf.jasperreports.engine.fonts.SimpleFontFace
        self.FontFamily = jpype.JPackage('net').sf.jasperreports.engine.fonts.FontFamily
        self.SimpleFontFamily = jpype.JPackage('net').sf.jasperreports.engine.fonts.SimpleFontFamily
        self.JRLoader = jpype.JPackage('net').sf.jasperreports.engine.util.JRLoader
        self.JRSwapFile = jpype.JPackage('net').sf.jasperreports.engine.util.JRSwapFile
        self.SimpleExporterInput = jpype.JPackage('net').sf.jasperreports.export.SimpleExporterInput
        self.SimpleExporterInputItem = jpype.JPackage('net').sf.jasperreports.export.SimpleExporterInputItem
        self.SimpleHtmlExporterOutput = jpype.JPackage('net').sf.jasperreports.export.SimpleHtmlExporterOutput
        self.SimpleOutputStreamExporterOutput = jpype.JPackage('net').sf.jasperreports.export.SimpleOutputStreamExporterOutput
        self.SimpleWriterExporterOutput = jpype.JPackage('net').sf.jasperreports.export.SimpleWriterExporterOutput
        self.SimpleXmlExporterOutput = jpype.JPackage('net').sf.jasperreports.export.SimpleXmlExporterOutput
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
            try:
                ft_face = freetype.Face(fontpath)
                font_name = ft_face.family_name.decode('utf-8')
                is_bold = bool(ft_face.style_flags & freetype.FT_STYLE_FLAG_BOLD)
                is_italic = bool(ft_face.style_flags & freetype.FT_STYLE_FLAG_ITALIC)
                face = "Regular"
                if is_bold and is_italic:
                    face = "BoldItalic"
                elif is_bold:
                    face = "Bold"
                elif is_italic:
                    face = "Italic"
                custom_fonts[font_name] = custom_fonts.get(font_name, {})
                custom_fonts[font_name][face] = fontpath
            except:
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

    def fill_report(self, template, fill_params, resources, single_report, tmpdir, permitted_resources):
        """ Compile a report (or subreport), resolving the datasource, mapping parameter values, and processing permitted subreports.

            :param template str: The report template name
            :param fill_params dict: Report fill parameters
            :param resources dict: Resource configuration
            :param single_report bool: Whether to produce single report, passing the array of feature IDs, instead of producing one report per feature
            :param tmpdir str: Tempdir in which to write processed .jrxml sources and compiled .jasper reports
            :param list permitted_resources: Document template permissions
        """

        self.logger.info("Processing report %s" % template)

        # Compile jrxml if jasper does not exist, or if subreports need to be filtered
        report_file = os.path.join(self.report_dir, template + ".jasper")
        report_dir = self.report_dir
        if not os.path.isfile(report_file) or not self.permit_subreports:
            report_file = self.compile_report(template, tmpdir, permitted_resources)
            report_dir = tmpdir
            if not report_file:
                return None
        else:
            self.logger.info("Using precompiled *.jasper report files")
        jasper_report = self.JRLoader.loadObjectFromFile(report_file)

        # Get the template resource configuration
        resource = next((x for x in resources if x["template"] == template), {})

        # Read datasource from resource or from default data adapter
        datasource = resource.get("datasource", self.jasper_prop_value(jasper_report.getProperty("com.jaspersoft.studio.data.defaultdataadapter")))
        self.logger.info("Report datasource is " + datasource)

        # Extract primary key and table name from resource or from query
        data_param = None
        if datasource and datasource != "NO_DATA_ADAPTER":
            query = self.jasper_prop_text_value(jasper_report.getQuery())
            data_table = resource.get("table")
            data_pkey = resource.get("primary_key")
            data_param = resource.get("parameter_name")

            if query and data_table is None or data_pkey is None:
                statement = re.sub(r"\s+", " ", query)
                m = re.search(r'(["A-Za-z0-9_.]+)\s+WHERE', statement)
                if m:
                    data_table = m.group(1)
                m = re.search(r'(["A-Za-z0-9_.]+)\s*=\s*\$P\{(\w+)\}', statement)
                if m:
                    data_pkey = m.group(1).strip('"')
                    data_param = m.group(2)
            if query and (data_table is None or data_pkey is None or data_param is None):
                self.logger.error("Unable to extract table name/primary key/parameter from query, please define them manually in the resource entry")
                return None
            self.logger.info("Data table=%s, PK=%s, param=%s " % (data_table, data_pkey, data_param))

            # Resolve feature parameter
            if fill_params.get("feature") == "*":
                db = db_engine.db_engine("postgresql:///?service=" + str(datasource))
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

        # Iterate over parameters, cast fill parameters to java types
        for param in jasper_report.getParameters():
            name = param.getName();
            klass = param.getValueClass()
            if name in fill_params:
                if name == data_param:
                    if single_report:
                        nestedKlass = param.getNestedType()
                        if not nestedKlass:
                            self.logger.error("Compiling with single_report=true, but %s is not defined as an array parameter" % data_param)
                            return None
                        data_param_list = self.ArrayList()
                        for value in fill_params[data_param]:
                            data_param_list.add(jpype.JClass(nestedKlass)(value))
                        fill_params[data_param] = data_param_list
                    else:
                        fill_params[data_param] = [jpype.JClass(klass)(entry) for entry in fill_params[name]]
                else:
                    fill_params[name] = jpype.JClass(klass)(fill_params[name])

        # Collect subreport datasources and inject them into fill_params
        opened_connections = []
        self.collect_subreport_params(jasper_report, fill_params, opened_connections, report_dir, os.path.dirname(report_file))

        # Fill report
        conn = self.resolve_datasource(datasource, report_file, opened_connections)

        self.logger.info("Filling report %s" % template)
        self.logger.info("Report parameters: %s" % str(fill_params))
        # Compile, fill and export report
        jasper_prints = self.ArrayList()
        try:
            if data_param is not None and data_param in fill_params:
                if not single_report:
                    feature_ids = fill_params[data_param]
                    for feature_id in feature_ids:
                        fill_params[data_param] = feature_id
                        jasper_prints.add(self.SimpleExporterInputItem(self.JasperFillManager.getInstance(self.jContext).fill(jasper_report, fill_params, conn)))
                else:
                    jasper_prints.add(self.SimpleExporterInputItem(self.JasperFillManager.getInstance(self.jContext).fill(jasper_report, fill_params, conn)))
            else:
                jasper_prints.add(self.SimpleExporterInputItem(self.JasperFillManager.getInstance(self.jContext).fill(jasper_report, fill_params, conn)))
        except Exception as e:
            self.logger.error("Exception compiling/filling report: %s" % e)
            self.logger.debug(traceback.format_exc())
            self.print_memory_usage()

        # Cleanup connections
        for conn in opened_connections:
            conn.close()

        return jasper_prints

    def compile_report(self, template, tmpdir, permitted_resources):
        # Copy to temp dir
        report_filename = os.path.join(self.report_dir, template + ".jrxml")
        temp_report_filename = os.path.join(tmpdir, template + ".jrxml")
        os.makedirs(os.path.dirname(temp_report_filename), exist_ok=True)

        # Parse report
        with open(report_filename) as fh:
            doc = ElementTree.parse(fh)
        if not doc:
            self.logger.error("Failed to read report %s" % report_filename)
            return None
        root = doc.getroot()
        namespace = {'jasper': 'http://jasperreports.sourceforge.net/jasperreports'}

        # Iterate over subreports, filter out unpermitted reports, compile permitted reports
        subreports = root.findall(".//jasper:subreport", namespace)
        for subreport in subreports:
            connectionExpression = subreport.find("./jasper:connectionExpression", namespace)
            subreportExpression = subreport.find("./jasper:subreportExpression", namespace)
            subreport_filename = self.evaluate_subreport_expression(subreportExpression.text, tmpdir, os.path.dirname(temp_report_filename))
            subreport_template = os.path.relpath(subreport_filename, tmpdir)[:-7]
            self.logger.info("Subreport filename %s" % subreport_filename)
            self.logger.info("Subreport template %s" % subreport_template)
            if os.path.exists(os.path.join(self.report_dir, subreport_template + ".jrxml")):
                if self.permit_subreports or subreport_template in permitted_resources:
                    subreportExpression.text = '"%s"' % subreport_filename
                    subreport_jasper = self.compile_report(subreport_template, tmpdir, permitted_resources)
                    if not subreport_jasper:
                        return None
                else:
                    self.logger.info("Filtering out unpermitted subreport %s" % subreport_template)
                    subreportExpression.text = ""
            else:
                self.logger.warning("Subreport path does not exist: %s" % subreport_filename)
                return None

        # Write modified jrxml
        self.logger.info("Saving filtered report to %s" % temp_report_filename)
        ElementTree.register_namespace("", "http://jasperreports.sourceforge.net/jasperreports")
        ElementTree.ElementTree(root).write(temp_report_filename)

        self.logger.info("Compiling %s" % temp_report_filename)
        output_name = temp_report_filename[:-6] + ".jasper"
        self.JasperCompileManager.getInstance(self.jContext).compileToFile(temp_report_filename, output_name)
        return output_name


    def collect_subreport_params(self, jasper_report, fill_params, opened_connections, report_dir, parent_dir):
        for band in jasper_report.getAllBands():
            for element in band.getElements():
                if isinstance(element, self.JRSubreport):
                    subreport_expression = self.jasper_prop_text_value(element.getExpression())
                    if not subreport_expression:
                        continue
                    subreport_file = self.evaluate_subreport_expression(subreport_expression, report_dir, parent_dir)
                    self.logger.info("Collecting params of %s" % subreport_file)
                    subreport_conn = self.jasper_prop_text_value(element.getConnectionExpression())
                    subreport = self.JRLoader.loadObjectFromFile(subreport_file)
                    subreport_datasource = self.jasper_prop_value(subreport.getProperty("com.jaspersoft.studio.data.defaultdataadapter"))
                    for param in subreport.getParameters():
                        name = param.getName();
                        klass = param.getValueClass()
                        if name in fill_params:
                            fill_params[name] = jpype.JClass(klass)(fill_params[name])
                    m = re.match(r'^\$P\{(\w+)\}$', subreport_conn or "")
                    if m:
                        fill_params[m.group(1)] = self.resolve_datasource(subreport_datasource, subreport_file, opened_connections)
                    self.collect_subreport_params(subreport, fill_params, opened_connections, subreport_file, os.path.dirname(subreport_file))

    def jasper_prop_value(self, prop):
        return str(prop) if prop else None

    def jasper_prop_text_value(self, prop):
        return str(prop.getText()) if prop else None

    def evaluate_subreport_expression(self, expr, report_dir, parent_dir):
        expr = expr.replace('$P{REPORT_DIR}', '"%s"' % report_dir)
        parts = re.findall(r'(["\'])(.*?)\1', expr) or []
        path = ("".join(p[1] for p in parts))
        if not os.path.isabs(path):
            path = os.path.join(parent_dir, path)
        return path

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

        self.logger.info("Requested report template %s format %s" % (template, format))

        resources = (config.resources() or {}).get('document_templates', [])

        self.report_dir = config.get('report_dir', '/reports').rstrip('/')
        if not os.path.isabs(self.report_dir):
            self.report_dir = os.path.abspath(self.report_dir)
        self.permit_subreports = config.get('permit_subreports', False)
        self.logger.info("Report dir is '%s'" % self.report_dir)
        self.logger.info("permit_subreports: %d" % self.permit_subreports)

        if template not in permitted_resources:
            self.logger.info("Missing permissions for template '%s'", template)
            return 404, "Missing or restricted template: %s" % template

        report_filename = os.path.abspath(os.path.join(self.report_dir, template))
        if not (os.path.isfile(report_filename + ".jrxml") or (self.permit_subreports and os.path.isfile(report_filename + ".jasper"))):
            self.logger.info("Template '%s' not found", template)
            return 404, "Missing or restricted template: %s" % template

        # Set resource dir in fill_params
        fill_params["REPORT_DIR"] = self.report_dir.rstrip("/") + "/"
        fill_params["ROOT_DIR"] = self.report_dir.rstrip("/") + "/"

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

        # Fill report
        jasperPrints = self.fill_report(template, fill_params, resources, single_report, tmpdir, permitted_resources)
        shutil.rmtree(tmpdir)

        if jasperPrints is None:
            return 500, "Failed to compile report"

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
            return 500, "Failed to export report"

        self.print_memory_usage()

        return 200, result
