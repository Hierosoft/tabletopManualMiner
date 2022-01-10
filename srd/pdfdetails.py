#!/usr/bin/env python3

import math

try:
    # from PDFPageDetailedAggregator:
    from pdfminer.pdfdocument import PDFDocument, PDFNoOutlines
    from pdfminer.pdfparser import PDFParser
    from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
    from pdfminer.converter import PDFPageAggregator
    from pdfminer.layout import LTPage, LTChar, LTAnno, LAParams, LTTextBox, LTTextLine
except ModuleNotFoundError:
    prerr("You must first install the following module for Python:")
    prerr("  pdfminer")
    exit(1)

class PDFPageDetailedAggregator(PDFPageAggregator):
    """
    This class is based on PDFPageDetailedAggregator from
    lindblandro's Oct 4 '13 at 10:33 answer
    edited by slushy Feb 4 '14 at 23:41
    at <https://stackoverflow.com/a/19179114>
    on <https://stackoverflow.com/questions/15737806/extract-text-using-
    pdfminer-and-pypdf2-merges-columns>.
    """

    def __init__(self, rsrcmgr, pageno=1, laparams=None,
                 colStarts=None):
        PDFPageAggregator.__init__(self, rsrcmgr, pageno=pageno, laparams=laparams)
        self.rows = []
        self.colStarts = colStarts
        if self.colStarts is not None:
            print("columns: {}".format(len(self.colStarts)))
        self.page_number = 0

    def receive_layout(self, ltpage):
        def render(item, page_number):
            if isinstance(item, LTPage) or isinstance(item, LTTextBox):
                for child in item:
                    render(child, page_number)
            elif isinstance(item, LTTextLine):
                child_str = ''
                for child in item:
                    if isinstance(child, (LTChar, LTAnno)):
                        child_str += child.get_text()
                child_str = ' '.join(child_str.split()).strip()
                if child_str:
                    col = None
                    cols = 0
                    if self.colStarts is not None:
                        cols = len(self.colStarts)
                    if (cols is None) or (cols == 1):
                        col = 0
                    elif (cols == 2):
                        col = 0
                        col2Min = math.floor(self.colStarts[1])
                        if item.bbox[0] >= col2Min:
                            col = 1  # Index [1] is column 2.
                    else:
                        raise ValueError("Only a list of length 1 (same as None) or 2"
                                         " is implemented for \"colStarts\".")
                    row = (page_number, col, item.bbox[0], item.bbox[1], item.bbox[2], item.bbox[3], child_str)
                    # ^ bbox: (x1, y1, x2, y2)
                    # ^ row: (pageid, x1, y1, x2, y2, child_str)
                    #         0       1   2   3   4   5
                    self.rows.append(row)
                for child in item:
                    render(child, page_number)
            return
        render(ltpage, self.page_number)
        self.page_number += 1
        self.rows = sorted(self.rows, key = lambda r: (r[0], r[1], -r[2]))
        self.result = ltpage
