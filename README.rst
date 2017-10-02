static-ranges
=============

WSGI middleware for handling HTTP byte-ranges, i.e.

- Request header: ``Range: bytes=0-1``
- Response header: ``Accept-Ranges: bytes`` or ``none``
- Response status: ``206 Partial Content`` or ``416 Requested range not satisfiable`` with Content-Range of *
- Response header: ``Content-Range: bytes 0-1/2333748``
- Response header: ``Content-Length: 2``

Implemented originally for use with waitress or gunicorn, django, dj-static and static3 because
Safari requires byte-range support when requesting HTML5 videos.

Status and caveats
------------------

static-ranges has been developed as a quick way to get an app up and running on Heroku for testing with
all static and media files served from the same place. Probably not production ready.

static-ranges only supports single ranges (or overlapping ranges that condense to a single range) but that
probably covers 99.9% of usage.

Install
-------

It is available from pypi like so:

.. code:: shell

    $ pip install static-ranges

Usage
-----

Wrap your application in wsgi.py with Ranges as the outermost layer, for example:

.. code:: python

    from static_ranges import Ranges

    application = Ranges(Cling(MediaCling(application)))

Optionally you can disable support which will send the ``Accept-Ranges: none`` header using:

.. code:: python

    application = Ranges(Cling(MediaCling(application)), enable=False)
