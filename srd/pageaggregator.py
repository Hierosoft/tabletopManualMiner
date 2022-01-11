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
    prerr("To use the aggregator (required for generating chunks.json)"
          " you must first install the following module for Python:")
    prerr("  pdfminer")
    exit(1)

try:
    input = raw_input
except NameError:
    # Python 3
    pass

# TODO:
from srd import (
    objDict,
    BBox,
    DocChunk,
    clean_frag_text,
    clean_frag,
    same_style,
    frag_dict,
)


def ltannoDict(ltanno):
    return objDict(ltanno)


'''
class DocFragment:
    def __init__(self, text, fontname, size):
        self.text = text
        self.fontname = fontname
        self.size = size

    def sameStyle(self, fragment):
        """
        Is same fontname and size.
        """
        ffn = fragment.fontname
        ffs = fragment.size
        return (ffs == self.size) and (ffn == self.fontname)

    def clean(self):
        self.text = clean_frag_text(self.text)
'''


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
        self.chunks = []
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
                fontSize = None
                fontName = None
                fontSizes = []
                fontNames = []
                warnings = []
                parts = []
                fragments = []
                annotations = []
                for child in item:
                    strp = None
                    if isinstance(child, LTChar):
                        child_str += child.get_text()
                        strp = child.get_text().strip()
                        # and (len(strp) > 0)
                        if fontName is not None:
                            if fontName != child.fontname:
                                warnings.append("mixed fontName")
                        if fontSize is not None:
                            if fontSize != child.size:
                                warnings.append("mixed fontSize")
                        fontName = child.fontname
                        fontSize = child.size
                        frag = frag_dict(
                            child.get_text(),
                            child.fontname,
                            child.size,
                        )
                        fragments.append(frag)
                        # fontNames.append(fontName)
                        # fontSizes.append(fontSize)
                        parts.append(strp)
                    elif isinstance(child, LTAnno):
                        child_str += child.get_text()
                        strp = child.get_text().strip()
                        annotations.append(ltannoDict(child))


                child_str = ' '.join(child_str.split()).strip()
                if child_str:
                    if len(warnings) > 0:
                        """
                        print("Warnings in \"{}\":"
                              " {}: fonts {} sizes {} parts {}"
                              "".format(child_str, warnings, fontNames,
                                        fontSizes, parts))
                        input("Press enter to continue...")
                        """
                        fontSize = None
                        fontName = None
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
                    # if isinstance(child, LTChar):
                    '''
                    try:
                        fontName = child.fontname
                        fontSize = child.size
                        # Avoid "AttributeError:
                        # 'LTAnno' object has no attribute 'fontname'"
                    except AttributeError as ex:
                        print("dir(LTTextLine): {}".format(dir(LTTextLine)))
                        print("dir(child): {}".format(dir(child)))
                        raise ex
                    '''

                    chunk = DocChunk(
                        page_number,
                        col,
                        item.bbox,
                        child_str,
                        fontName=fontName,
                        fontSize=fontSize,
                        fragments=fragments,
                        annotations=annotations,
                    )
                    chunk.groupFragments()
                    self.chunks.append(chunk)
                for child in item:
                    render(child, page_number)
            return
        render(ltpage, self.page_number)
        self.page_number += 1
        self.chunks = sorted(self.chunks, key = lambda f: (f.pageid, f.column, -f.bbox.y1))
        self.result = ltpage
