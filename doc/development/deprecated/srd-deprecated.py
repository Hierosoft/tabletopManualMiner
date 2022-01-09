#!/usr/bin/env python3

import os
import platform
import sys

def prerr(msg):
    sys.stderr.write("{}\n".format(msg))
    sys.stderr.flush()

try:
    # from convert_pdf_to_txt:
    from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
    from pdfminer.converter import TextConverter
    from pdfminer.layout import LAParams
    from pdfminer.pdfpage import PDFPage

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


def convert_pdf_to_txt(path, pageid=None):
    """
    This function scrambles the text. There may be values for LAParams
    that fix it but that seems difficult so see getMonters instead.

    This function is based on convert_pdf_to_txt(path) from
    RattleyCooper's Oct 21 '14 at 19:47 answer
    edited by Trenton McKinney Oct 4 '19 at 4:10
    on <https://stackoverflow.com/a/26495057>.

    Keyword arguments:
    pageid -- Only process this page id.
    """
    rsrcmgr = PDFResourceManager()
    retstr = StringIO()
    codec = 'utf-8'
    laparams = LAParams()
    try:
        device = TextConverter(rsrcmgr, retstr, codec=codec, laparams=laparams)
    except TypeError as ex:
        if ("codec" in str(ex)) and ("unexpected keyword" in str(ex)):
            device = TextConverter(rsrcmgr, retstr, laparams=laparams)
    fp = open(path, 'rb')
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    password = ""
    maxpages = 0
    caching = True
    pagenos = set()

    for page in PDFPage.get_pages(fp, pagenos, maxpages=maxpages, password=password,caching=caching, check_extractable=True):
        # print("page: {}".format(dir(page)))
        if (pageid is None) or (pageid == page.pageid):
            print("page.pageid: {}".format(page.pageid))
            interpreter.process_page(page)
            if pageid is not None:
                break

    text = retstr.getvalue()
    print(text)

    fp.close()
    device.close()
    retstr.close()
    return text


def main():
    srcName = "SRD-OGL_V5.1.pdf"
    srcPath = os.path.join(profile, "Nextcloud", "Tabletop",
                           "Campaigns", "publishing", srcName)
    if not os.path.isfile(srcPath):
        srcPath = os.path.join(os.path.realpath("."), srcName)
    print("srcPath: {}".format(srcPath))
    getMonsters(srcPath, pageid=100)


if __name__ == "__main__":
    main()
