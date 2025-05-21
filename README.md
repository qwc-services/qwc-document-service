[![](https://github.com/qwc-services/qwc-document-service/workflows/build/badge.svg)](https://github.com/qwc-services/qwc-document-service/actions)
[![docker](https://img.shields.io/docker/v/sourcepole/qwc-document-service?label=Docker%20image&sort=semver)](https://hub.docker.com/r/sourcepole/qwc-document-service)

Document service
================

The document service delivers reports from the Jasper reporting service with permission control.

Report source files (`*.jrxml`) must be placed below the `report_dir` (see config below).

The reports are then referenced by their template name, which corresponds to their path below `report_dir`, without extension.

For instance `report_dir` is `/path/to/report/dir`, then the template name for

     /path/to/report/dir/topic/myreport.jrxml

is `topic/myreport`.

The request format is

    http://localhost:5018/<template>.<ext>?<key>=<value>&...

where

* `ext` is a supported report format (`pdf`, `html`, `csv`, `docx`, `ods`, `odt`, `pptx`, `rtf`, `xlsx`, `xml`). If not specified, `pdf` is assumed.
* Query KVPs are passed to the Jasper as report parameters.

Example request:

    http://localhost:5018/topic/myreport.pdf?FEATURE_ID=1

If your report uses a PostgresSQL data adapter, use the name of the desired PG service connection as data adapter name in the report, and the connection will be automatically looked up from the `pg_service.conf` file. Alternatively, you can set the name of the desired PG service connection as `datasource` of in the service resource configuration, see below.

You can generically pass the generic `feature` query parameter, which will be resolved to the report feature parameter configured in the report query string. You can pass:

- A single or a comma-separated list of feature ids, i.e.

      http://localhost:5018/topic/myreport.pdf?feature=1,3,6,9

- `*` to specify all features of the report datasource, i.e.

      http://localhost:5018/topic/myreport.pdf?feature=*

If multiple feature ids are specified, an aggregated report for all specified features will be returned.

Alternatively, provided `FEATURE_ID` is defined as a list in your report, you can pass `single_report=true`, and the entire list of feature ids will be passed to the report, which can i.e. render them in a table.

To map `feature` to the report feature parameter, and to resolve `feature=*`, the table name, primary key column and report feature parameter will be extracted, if possible, from the report query string, which is expected to be of the form

    SELECT <...> FROM <table_name> WHERE <pk_column> = $P{<FEATURE_PARAM_NAME>}

For more complex queries, you'll need to define `table`, `primary_key` and `parameter_name` in the report resource configuration, see below. Note that the value(s) of the `feature` query parameters are expected to be primary keys of the records of the table specified in the report query string.

If your report includes external resources (i.e. images), place these below the `report_dir` and, add a `REPORT_DIR` parameter of type `java.lang.String` in the `.jrxml` and use `$P{REPORT_DIR}` in the resource location expression, for example:

    $P{REPORT_DIR} + "mysubfolder/myimage.png"

If you may have a very large amount of input data, the report generation might result in a very large output file. This can lead to an Out-of-memory exception. To handle this, a "Virtualizer" could be used, which will cut the report into different files and save them on the hard drive during the generation process. The result generally makes the generation of the report a bit slower but it will solve the memory exception. To use a "JRSwapFileVirtualizer" for report generation, the `virtualizer` configuration has to be set (see example below).

If your report requires extra fonts, place the `*.ttfs` below the `src/fonts` directory (when running locally) resp. mount them inside the `/srv/qwc_service/fonts/` when running as docker container. Font names must respect the following naming convention:

- Regular: `<FontName>.ttf` or `<FontName>-Regular.ttf`
- Bold: `<FontName>-Bold.ttf`
- Italic: `<FontName>-Italic.ttf`
- BoldItalic: `<FontName>-BoldItalic.ttf`

Set `FLASK_DEBUG=1` to get additional logging output.

Configuration
-------------

The static config files are stored as JSON files in `$CONFIG_PATH` with subdirectories for each tenant,
e.g. `$CONFIG_PATH/default/*.json`. The default tenant name is `default`.

### JSON config

* [JSON schema](schemas/qwc-document-service.json)
* File location: `$CONFIG_PATH/<tenant>/documentConfig.json`

Example:
```json
{
  "$schema": "https://raw.githubusercontent.com/qwc-services/qwc-document-service/master/schemas/qwc-document-service.json",
  "service": "document",
  "config": {
    "report_dir": "/path/to/report/dir",
    "max_memory": "1024M",
    "virtualizer": {
      "swapfile_blocksize": 4096,
      "swapfile_mingrowcount" : 100,
      "virtualizer_maxsize": 1
    }
  },
  "resources": {
    "document_templates": [
      {
        "template": "demo",
        "datasource": "<pgservice_name>",
        "table": "<table_name>",
        "primary_key": "<primary_key_column_name>",
        "parameter_name": "<report_parameter_name>"
      }
    ]
  }
}
```

### Environment variables

Config options in the config file can be overridden by equivalent uppercase environment variables.

### Permissions

- [JSON schema](https://github.com/qwc-services/qwc-services-core/blob/master/schemas/qwc-services-permissions.json)
- File location: `$CONFIG_PATH/<tenant>/permissions.json`

Example:

```
{
  "$schema": "https://raw.githubusercontent.com/qwc-services/qwc-services-core/master/schemas/qwc-services-permissions.json",
  "users": [
    {
      "name": "demo",
      "groups": ["demo"],
      "roles": []
    }
  ],
  "groups": [
    {
      "name": "demo",
      "roles": ["demo"]
    }
  ],
  "roles": [
    {
      "role": "public",
      "permissions": {
        "document_templates": [
          "demo",
          "another demo"
        ]
      }
    },
    {
      "role": "demo",
      "permissions": {
        "document_templates": []
      }
    }
  ]
}
```

Usage
-----

API documentation:

    http://localhost:5018/api/

Request format:

    http://localhost:5018/<template>?<key>=<value>&...

Example:

    http://localhost:5018/BelasteteStandorte.pdf

Arbitrary parameters can be appended to the request:

    http://localhost:5018/BelasteteStandorte.pdf?feature=123

The format of the report is extracted from the template name, i.e.

    http://localhost:5018/BelasteteStandorte.xls?feature=123

If no extension is present in the template name, PDF is used as format.

Docker usage
------------

To run this docker image you will need a running jasper reporting service.

The following steps explain how to download a jasper reporting service docker image and how to run the `qwc-document-service` with `docker-compose`.

**Step 1: Clone qwc-docker**

    git clone https://github.com/qwc-services/qwc-docker
    cd qwc-docker

**Step 2: Create docker-compose.yml file**

    cp docker-compose-example.yml docker-compose.yml

**Step 3: Start docker containers**

    docker-compose up qwc-document-service

For more information please visit: https://github.com/qwc-services/qwc-docker

Development
-----------

Install requirements:

    uv sync
    wget -P src/libs -i libs.txt

Start local service:

    CONFIG_PATH=/PATH/TO/CONFIGS/ uv run src/server.py


Testing
-------

Run all tests:

    FLASK_DEBUG=1 PYTHONPATH=$PWD/src FONT_DIR=$PWD/tests/fonts CONFIG_PATH=$PWD/tests/config/ uv run test.py
