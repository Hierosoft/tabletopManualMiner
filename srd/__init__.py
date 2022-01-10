#!/usr/bin/env python3

import os
import platform
import sys

def prerr(msg):
    sys.stderr.write("{}\n".format(msg))
    sys.stderr.flush()

from pdfdetails import PDFPageDetailedAggregator

try:
    from pprint import pprint
    from pdfminer.pdfparser import PDFParser
    from pdfminer.pdfdocument import PDFDocument
    from pdfminer.pdfpage import PDFPage
    from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
    from pdfminer.layout import LAParams
except ModuleNotFoundError:
    prerr("You must first install the following module for Python:")
    prerr("  pdfminer")
    exit(1)

from io import StringIO

profile = None
if platform.system() == "Windows":
    profile = os.environ['USERPROFILE']
else:
    profile = os.environ['HOME']


def generateMeta(path, pageid=None):
    """
    This function is based on code from
    lindblandro's Oct 4 '13 at 10:33 answer
    edited by slushy Feb 4 '14 at 23:41
    at <https://stackoverflow.com/a/19179114>
    on <https://stackoverflow.com/questions/15737806/extract-text-using-
    pdfminer-and-pypdf2-merges-columns>.
    """
    fp = open(path, 'rb')
    parser = PDFParser(fp)
    doc = PDFDocument(parser)
    # doc.initialize('password')  # leave empty for no password

    rsrcmgr = PDFResourceManager()
    laparams = LAParams()
    device = PDFPageDetailedAggregator(
        rsrcmgr,
        laparams=laparams,
        colStarts=[57.6, 328.56],
    )
    interpreter = PDFPageInterpreter(rsrcmgr, device)

    for page in PDFPage.create_pages(doc):
        if (pageid is None) or (pageid==page.pageid):
            # print("page: {}".format(dir(page)))
            interpreter.process_page(page)
            device.get_result()  # receive LTPage (runs receive_layout)
            if pageid is not None:
                break

    pprint(device.rows)


def main():
    srcName = "SRD-OGL_V5.1.pdf"
    srcPath = os.path.join(profile, "Nextcloud", "Tabletop",
                           "Campaigns", "publishing", srcName)
    if not os.path.isfile(srcPath):
        srcPath = os.path.join(os.path.realpath("."), srcName)
    print("srcPath: {}".format(srcPath))
    if not os.path.isfile(srcPath):
        print("{} is missing. Download it and"
              " run this from that directory."
              "".format(srcPath))
    generateMeta(srcPath, pageid=None)


if __name__ == "__main__":
    main()
