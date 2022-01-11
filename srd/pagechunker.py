#!/usr/bin/env python3
from srd.pageaggregator import (
    PDFPageDetailedAggregator,
    DocChunk,
)

from srd import (
    prerr,
)

import sys

try:
    from pprint import pprint
    from pdfminer.pdfparser import PDFParser
    from pdfminer.pdfdocument import PDFDocument
    from pdfminer.pdfpage import PDFPage
    from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
    from pdfminer.layout import LAParams
except ModuleNotFoundError:
    prerr("To run pagechunker (which generates chunks.json)"
          " you must first install the following module for Python:")
    prerr("  pdfminer")
    exit(1)

'''
from io import (
    StringIO,
)
'''


def setAllPageNumbers(device, pageid, pageNumberStr):
    pageN = None
    try:
        pageN = int(pageNumberStr)
    except ValueError as ex:
        raise ValueError("WARNING: The page number for page id"
                         " {} is unknown since the last text"
                         " on the page is not an integer:"
                         " \"{}\""
                         "".format(pageid, pageNumberStr))
        return

    for chunk in device.chunks:
        if chunk.pageid == pageid:
            chunk.pageN = pageN


def generateChunks(path, pageid=None, colStarts=None, max_pageid=None):
    '''
    This function is based on code from
    lindblandro's Oct 4 '13 at 10:33 answer
    edited by slushy Feb 4 '14 at 23:41
    at <https://stackoverflow.com/a/19179114>
    on <https://stackoverflow.com/questions/15737806/extract-text-using-
    pdfminer-and-pypdf2-merges-columns>.
    '''
    global indent
    fp = open(path, 'rb')
    parser = PDFParser(fp)
    doc = PDFDocument(parser)
    # doc.initialize('password')  # leave empty for no password

    rsrcmgr = PDFResourceManager()
    laparams = LAParams()
    device = PDFPageDetailedAggregator(
        rsrcmgr,
        laparams=laparams,
        colStarts=colStarts,
    )
    interpreter = PDFPageInterpreter(rsrcmgr, device)

    UNKNOWN = 0
    CONTEXT_MONSTERS = 1
    CONTEXT_APPENDIX_A = 2

    for page in PDFPage.create_pages(doc):
        if (pageid is None) or (pageid==page.pageid):
            # print("page: {}".format(dir(page)))
            # ^ page: ['INHERITABLE_ATTRS', '__class__', '__delattr__', '__dict__', '__dir__', '__doc__', '__eq__', '__format__', '__ge__', '__getattribute__', '__gt__', '__hash__', '__init__', '__init_subclass__', '__le__', '__lt__', '__module__', '__ne__', '__new__', '__reduce__', '__reduce_ex__', '__repr__', '__setattr__', '__sizeof__', '__str__', '__subclasshook__', '__weakref__', 'annots', 'attrs', 'beads', 'contents', 'create_pages', 'cropbox', 'debug', 'doc', 'get_pages', 'lastmod', 'mediabox', 'pageid', 'resources', 'rotate']
            progressTotalStr = ""
            percentStr = ""
            if max_pageid is not None:
                progressTotalStr = "/" + str(max_pageid)
                percent = float(page.pageid) / float(max_pageid) * 100
                percentStr = " ({}%)".format(int(percent))
                sys.stderr.write("\r")  # overwrite
            sys.stderr.write("Reading pageid {}{}{}    "
                             "".format(page.pageid, progressTotalStr,
                                       percentStr))
            sys.stderr.flush()
            interpreter.process_page(page)
            device.get_result()  # receive LTPage (runs receive_layout)
            # NOTE: There is no point in iterating chunks here,
            # because the list stored in device.chunks will grow on each
            # iteration and the page numbers are not distinguished yet.
            if pageid is not None:
                break
    sys.stderr.write("\n")
    sys.stderr.flush()

    # pprint(device.rows)
    prevChunk = None
    pageN = None

    for chunk in device.chunks:
        if prevChunk is not None:
            if prevChunk.pageid != chunk.pageid:
                setAllPageNumbers(device, prevChunk.pageid,
                                  prevChunk.text)
                # Assume that the last text on the page is the (visible)
                # page number if it is a number.
                # print("page {} ended with {}"
                #       "".format(prevChunk.pageid, prevChunk.text))
                # ^ usually the page number is 1 higher than the pageid.
        prevChunk = chunk

    if prevChunk is not None:
        setAllPageNumbers(device, prevChunk.pageid, prevChunk.text)

    return device.chunks
