Document service
================

The document service delivers reports from the Jasper reporting service with permission control.


Dependencies
------------

* Permission service (`PERMISSION_SERVICE_URL`)
* [Jasper reporting service](https://github.com/qwc-services/jasper-reporting-service/)


Configuration
-------------

Environment variables:

| Variable             | Description                | Default value                 |
|----------------------|----------------------------|-------------------------------|
| `JASPER_SERVICE_URL` | Jasper Reports service URL | http://localhost:8002/reports |
| `JASPER_TIMEOUT`     | Timeout (s)                | 60                            |


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

See also jasper-reporting-service README.


Development
-----------

Create a virtual environment:

    virtualenv --python=/usr/bin/python3 .venv

Activate virtual environment:

    source .venv/bin/activate

Install requirements:

    pip install -r requirements.txt

Start local service:

    CONFIG_PATH=/PATH/TO/CONFIGS/ python server.py


Testing
-------

Run all tests:

    python test.py
