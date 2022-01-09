#!/usr/bin/env python3
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

    def __init__(self, rsrcmgr, pageno=1, laparams=None):
        PDFPageAggregator.__init__(self, rsrcmgr, pageno=pageno, laparams=laparams)
        self.rows = []
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
                    row = (page_number, item.bbox[0], item.bbox[1], item.bbox[2], item.bbox[3], child_str) # bbox == (x1, y1, x2, y2)
                    self.rows.append(row)
                for child in item:
                    render(child, page_number)
            return
        render(ltpage, self.page_number)
        self.page_number += 1
        self.rows = sorted(self.rows, key = lambda x: (x[0], -x[2]))
        self.result = ltpage
