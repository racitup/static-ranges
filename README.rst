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
all static and media files served from the same WSGI application. Probably not production ready.

If you are looking to deploy a WSGI application in production, please look at a mature web server like nginx or apache. These support byte-ranges out of the box and just need to be configured to serve your static and media file directories.
For nginx for example, look at the root, and location directives.

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

    from dj_static import Cling, MediaCling
    from static_ranges import Ranges

    application = Ranges(Cling(MediaCling(application)))

Optionally you can disable support which will send the ``Accept-Ranges: none`` header using:

.. code:: python

    application = Ranges(Cling(MediaCling(application)), enable=False)
