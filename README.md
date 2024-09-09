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

If your report includes external resources (i.e. images), place these below the `report_dir` and, add a `REPORT_DIR` parameter of type `java.lang.String` in the `.jrxml` and use `$P{REPORT_DIR}` in the resource location expression, for example:

    $P{REPORT_DIR} + "mysubfolder/myimage.png"

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
    "report_dir": "/path/to/report/dir"
  },
  "resources": {
    "document_templates": [
      {
        "template": "demo",
        "datasource": "<pgservice_name>"
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

Create a virtual environment:

    python3 -m venv .venv

Activate virtual environment:

    source .venv/bin/activate

Install requirements:

    pip install -r requirements.txt

Start local service:

    CONFIG_PATH=/PATH/TO/CONFIGS/ python src/server.py


Testing
-------

Run all tests:

    python test.py
