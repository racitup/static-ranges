# -*- coding: utf-8 -*-
"""
WSGI middleware for handling HTTP byte-ranges
See https://github.com/racitup/static-ranges
"""

"""
BSD 2-Clause License

Copyright (c) 2017, Richard Case
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
import os


class RangeFileWrapper(object):
    """Creates new file_wrapper iterable objects"""

    def __init__(self, file_like, block_size, ranges):
        self.file_like, self.block_size, self.ranges = file_like, block_size, ranges
        if hasattr(self.file_like, 'close'):
            self.close = self.file_like.close

    def __iter__(self):
        if self.file_like.closed:
            self.file_like = open(self.file_like.name)
        return self.singlerange_file_wrapper(self.file_like, self.block_size, self.ranges)

    @staticmethod
    def singlerange_file_wrapper(file_like, block_size, ranges):
        rng = ranges[0]
        file_like.seek(rng[0])
        size = rng[1] - rng[0] + 1
        while size:
            chunk = min(block_size, size)
            if chunk:
                block = file_like.read(chunk)
                yield block
                size -= len(block)


class Ranges(object):
    """
    WSGI middleware that modifies static file responses with byte-range support
    Although multiple ranges are parsed, only single ranges are supported, i.e.
    Content-Type: multipart/byteranges; boundary=... is not supported.
    If multiple ranges condense down to a single range, that range will be sent.
    """
    header_range = 'HTTP_RANGE'
    header_accept_ranges = 'Accept-Ranges'
    header_content_range = 'Content-Range'
    header_content_length = 'Content-Length'
    status_206 = '206 Partial Content'
    status_416 = '416 Requested range not satisfiable'


    def __init__(self, application, enable=True):
        self.application = application
        self.enabled = enable

    @classmethod
    def parse_byteranges(cls, environ):
        """
        Outputs a list of tuples with ranges or the empty list
        According to the spec, start or end values can be omitted
        """
        r = []
        s = environ.get(cls.header_range, '').replace(' ','').lower()
        if s:
            l = s.split('=')
            if len(l) == 2:
                unit, vals = tuple(l)
                if unit == 'bytes' and vals:
                    gen_rng = ( tuple(rng.split('-')) for rng in vals.split(',') if '-' in rng )
                    for start, end in gen_rng:
                        if start or end:
                            r.append( (int(start) if start else None, int(end) if end else None) )
        return r

    @classmethod
    def check_ranges(cls, ranges, length):
        """Removes errored ranges"""
        result = []
        for start, end in ranges:
            if isinstance(start, int) or isinstance(end, int):
                if isinstance(start, int) and not (0 <= start < length):
                    continue
                elif isinstance(start, int) and isinstance(end, int) and not (start <= end):
                    continue
                elif start is None and end == 0:
                    continue
                result.append( (start,end) )
        return result

    @classmethod
    def convert_ranges(cls, ranges, length):
        """Converts to valid byte ranges"""
        result = []
        for start, end in ranges:
            if end is None:
                result.append( (start, length-1) )
            elif start is None:
                s = length - end
                result.append( (0 if s < 0 else s, length-1) )
            else:
                result.append( (start, end if end < length else length-1) )
        return result

    @classmethod
    def condense_ranges(cls, ranges):
        """Sorts and removes overlaps"""
        result = []
        if ranges:
            ranges.sort(key=lambda tup: tup[0])
            result.append(ranges[0])
            for i in range(1, len(ranges)):
                if result[-1][1] + 1 >= ranges[i][0]:
                    result[-1] = (result[-1][0], max(result[-1][1], ranges[i][1]))
                else:
                    result.append(ranges[i])
        return result

    @classmethod
    def valid_ranges(cls, ranges, length):
        ranges = cls.check_ranges(ranges, length)
        ranges = cls.convert_ranges(ranges, length)
        return cls.condense_ranges(ranges)

    def __call__(self, environ, start_response):

        def write_str(instr):
            """String buffer for old-style apps"""
            priv.str_buf += instr

        def print_start_response(*args):
            print("Resp: {}, {}, {}".format(*args))
            return start_response(*args)

        def response_range_cb(instat, inheaders, exc_info=None):
            priv.start_response_args = (instat, inheaders, exc_info)
            return write_str

        def dummy_file_wrapper(file_like, block_size):
            priv.file_like, priv.block_size = file_like, block_size
            priv.file_size = os.fstat(file_like.fileno()).st_size
            priv.ranges = self.valid_ranges(priv.request_ranges, priv.file_size)

        def response_idle_cb(instat, inheaders, exc_info=None):
            inheaders.append( (self.header_accept_ranges, 'bytes') )
            return start_response(instat, inheaders, exc_info)

        def response_disabled_cb(instat, inheaders, exc_info=None):
            inheaders.append( (self.header_accept_ranges, 'none') )
            return start_response(instat, inheaders, exc_info)

        if self.enabled:
            # private thread-safe variable container
            priv = lambda: None

            priv.str_buf = ""
            priv.request_ranges = self.parse_byteranges(environ)

            if not priv.request_ranges:
                return self.application(environ, response_idle_cb)

            # replace the file_wrapper so we can get the file-like object & size for static files
            # take a copy to prevent later errors in gunicorn
            newenv = environ.copy()
            newenv['wsgi.file_wrapper'] = dummy_file_wrapper

            body = self.application(newenv, response_range_cb)

            if priv.str_buf or not hasattr(priv, 'file_size'):
                # we won't execute the range if old-style string output or not a static file
                write_out = response_idle_cb(*priv.start_response_args)
                if priv.str_buf:
                    write_out(priv.str_buf)
                return body
            elif len(priv.ranges) == 1:
                rng = priv.ranges[0]
                extra_headers = [
                    (self.header_content_range,  'bytes {}-{}/{}'.format(rng[0], rng[1], priv.file_size)),
                    (self.header_content_length, '{}'.format(rng[1] - rng[0] + 1)),
                ]
                start_response(self.status_206, priv.start_response_args[1] + extra_headers, priv.start_response_args[2])
                return RangeFileWrapper(priv.file_like, priv.block_size, priv.ranges)
            else:
                extra_headers = [
                    (self.header_content_range,  'bytes */{}'.format(priv.file_size)),
                    (self.header_content_length, '0'),
                ]
                start_response(self.status_416, priv.start_response_args[1] + extra_headers, priv.start_response_args[2])
                if hasattr(priv.file_like, 'close'):
                    priv.file_like.close()
                return (b'',)

        else:
            return self.application(environ, response_disabled_cb)

########## Tests

import unittest
class RangeTests(unittest.TestCase):

    def full(self, environ, length):
        ranges = Ranges.parse_byteranges(environ)
        return Ranges.valid_ranges(ranges, length)

    def test_parse(self):
        e = {'RANGE': 'bytes=400-400'}
        self.assertEqual(Ranges.parse_byteranges(e), [])
        e = {'HTTP_RANGE': 'byte=400-400'}
        self.assertEqual(Ranges.parse_byteranges(e), [])
        e = {'HTTP_RANGE': 'bytes'}
        self.assertEqual(Ranges.parse_byteranges(e), [])
        e = {'HTTP_RANGE': 'bytes-400-400'}
        self.assertEqual(Ranges.parse_byteranges(e), [])
        e = {'HTTP_RANGE': '   bytes    =    200   -   '}
        self.assertEqual(Ranges.parse_byteranges(e), [(200,None)])
        e = {'HTTP_RANGE': '   bytes    =    200   =   '}
        self.assertEqual(Ranges.parse_byteranges(e), [])
        e = {'HTTP_RANGE': '   bytes    =    200   - 300   ,    -      350,   '}
        self.assertEqual(Ranges.parse_byteranges(e), [(200,300), (None,350)])
        e = {'HTTP_RANGE': 'bytes= g - h '}
        self.assertRaises(ValueError, Ranges.parse_byteranges, e)
        e = {'HTTP_RANGE': 'bytes=400-,-1,-666,0-0,0-1,0-499, 234 - 345 , 345 - 234  ,  4 - , - 50'}
        self.assertEqual(Ranges.parse_byteranges(e), [ (400,None),(None,1),(None,666),(0,0),(0,1),(0,499),(234,345),(345,234),(4,None),(None,50) ])

    def test_check(self):
        length = 500
        r = [ (400,None),(None,1),(None,666),(0,0),(0,1),(0,567),(234,345),(345,234),(4,None),(None,0),(567,None) ]
        self.assertEqual(Ranges.check_ranges(r, length), [ (400,None),(None,1),(None,666),(0,0),(0,1),(0,567),(234,345),(4,None) ])
        r = [ (666,None) ]
        self.assertEqual(Ranges.check_ranges(r, length), [])
        r = [ (345,234) ]
        self.assertEqual(Ranges.check_ranges(r, length), [])
        r = [ (None,0) ]
        self.assertEqual(Ranges.check_ranges(r, length), [])

    def test_convert(self):
        length = 500
        r = [ (400,None),(None,1),(None,666),(0,0),(0,1),(0,567),(234,345),(345,234),(4,None),(567,None) ]
        self.assertEqual(Ranges.convert_ranges(r, length), [ (400,499),(499,499),(0,499),(0,0),(0,1),(0,499),(234,345),(345,234),(4,499),(567,499) ])
        r = [(200,None)]
        self.assertEqual(Ranges.convert_ranges(r, length), [(200,499)])
        r = [(None,234)]
        self.assertEqual(Ranges.convert_ranges(r, length), [(266,499)])
        r = [(None,789)]
        self.assertEqual(Ranges.convert_ranges(r, length), [(0,499)])

    def test_condense(self):
        r = [ (400,499),(499,499),(10,499),(0,0),(0,1),(2,3),(234,345),(4,499) ]
        self.assertEqual(Ranges.condense_ranges(r), [(0,499)])
        r = [ (400,498),(467,497),(299,327),(0,0),(0,1),(499,499),(234,345) ]
        self.assertEqual(Ranges.condense_ranges(r), [(0,1),(234,345),(400,499)])

    def test_full(self):
        length = 500
        e = {'HTTP_RANGE': 'bytes=400-,-1,-666,0-0,0-1,0-499, 234 - 345 , 4 - , - 50, -0, 456  - 3'}
        self.assertEqual(self.full(e, length), [(0,499)])
        e = {'HTTP_RANGE': 'bytes=400-,-1,-47,0-0,0-1, 234 - 345 , 444 - , - 50, -0, 456  - 3'}
        self.assertEqual(self.full(e, length), [(0,1),(234,345),(400,499)])
        e = {'HTTP_RANGE': 'bytes=400-,-1,-47,0-0,0-1,0-499, 234 - 345 , 4 - , - 50, -0, 456  - 3'}
        self.assertEqual(self.full(e, length), [(0,499)])
