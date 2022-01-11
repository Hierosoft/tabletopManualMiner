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

try:
    input = raw_input
except NameError:
    # Python 3
    pass

# TODO:
'''
from srd import (
    objDict,
    ltannoDict,
)
'''

nonDataTypeNames = ['builtin_function_or_method', 'method']


def objDict(o):
    result = {}
    for k in dir(o):
        if k.startswith("__"):
            continue
        v = getattr(o, k)
        if type(v).__name__ in nonDataTypeNames:
            continue
        result[k] = v
    return result


def ltannoDict(ltanno):
    return objDict(ltanno)


class BBox:
    def __init__(self, bbox):
        """
        bbox: tuple of (x1, x1, x2, y2)
        """
        self.x1 = bbox[0]
        self.y1 = bbox[1]
        self.x2 = bbox[2]
        self.y2 = bbox[3]

    def toTuple(self):
        return (self.x1, self.y1, self.x2, self.y2)


def clean_frag_text(text):
    # It may be odd like:
    # "around \r  the \r  bend" (not actual example but spacing is)
    # Therefore:
    return " ".join(text.split()).strip()
    # ^ (strip with no param automatically uses any group of
    #    whitespaces as a single delimiter)


def clean_frag(frag):
    frag['text'] = clean_frag_text(frag['text'])


def same_style(frag1, frag2):
    """
    Is same fontname and size.
    """
    ffn = frag2['fontname']
    ffs = frag2['size']
    return (ffs == frag1['size']) and (ffn == frag1['fontname'])


def frag_dict(text, fontname, size):
    return {
        'text': text,
        'fontname': fontname,
        'size': size,
    }


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


class DocChunk:
    def __init__(self, pageid, column, bbox, text, fontName=None,
                 fontSize=None, fragments=None, annotations=None):
        """
        Sequential arguments:
        bbox -- The bounding box of the text in cartesian coordinates
            (larger is further toward the top of the document) in the
            format (x1, y1, x2, y2).

        Keyword arguments:
        fontName -- Only set if all fragments have same fontname.
        fontSize -- Only set if all fragments have same font size.
        fragments -- frag_dict representing parts of the chunk
            (usually words) that differ in font size or font name.
        annotations -- LTAnno objects (defined in pdfminer.layout)
        """
        self.pageid = pageid
        self.column = column
        self.bbox = BBox(bbox)
        self.text = text
        self.fontSize = fontSize
        self.fontName = fontName
        self.fragments = fragments
        self.annotations = annotations

        self.pageN = None  # Set this later based on the visible number.

    @staticmethod
    def fromDict(d):
        pageid = d['pageid']
        column = d['column']
        bbox = d['bbox']  # bbox is a list or tuple at this point.
        text = d['text']
        fontName = d['fontname']
        fontSize = d['size']
        fragments = d['fragments']
        annotations = d['annotations']
        chunk = DocChunk(pageid, column, bbox, text, fontName=fontName,
                         fontSize=fontSize, fragments=fragments,
                         annotations=annotations)
        return chunk

    def toDict(self):
        return {
            'text': self.text,
            'page': self.pageN,
            'pageid': self.pageid,
            'fontname': self.fontName,
            'size': self.fontSize,
            'bbox': self.bbox.toTuple(),
            'column': self.column,
            'fragments': self.fragments,
            'annotations': self.annotations,
        }


    def groupFragments(self):
        """
        Combine fragments that are in a row and share the same fontname
        and size.
        """
        fragments = []
        thisFrag = None
        for fragment in self.fragments:
            if (thisFrag is None) or (not same_style(fragment, thisFrag)):
                if thisFrag is not None:
                    # Append the finished fragment.
                    clean_frag(thisFrag)
                    fragments.append(thisFrag)
                thisFrag = frag_dict(
                    fragment['text'],
                    fragment['fontname'],
                    fragment['size'],
                )
            else:
                thisFrag['text'] += fragment['text']

        if thisFrag is not None:
            # Append the last fragment.
            clean_frag(thisFrag)
            fragments.append(thisFrag)
        self.fragments = fragments

    def oneStyle(self, fontname, size, decimalPlaces=2, index=None):
        """
        The DocChunk only has one fragment (or you specified index)
        and it is in the specified style.

        Keyword arguments:
        decimalPlaces -- Round sizes to the given number of decimal
            places before comparing them.
        index -- Check only at this index (allows fragments to contain
            more than one fragment).
        """
        if index is None:
            if len(self.fragments) != 1:
                return False
            index = 0
        frag = self.fragments[index]
        fSize = round(frag['size'], decimalPlaces)
        size = round(size, decimalPlaces)
        '''
        if size != fSize:
            print("size {} != {}".format(fSize, size))
        if fontname != frag['fontname']:
            print("fontname {} is not {}"
                  "".format(frag['fontname'], fontname))
        '''
        return (frag['fontname'] == fontname) and (fSize == size)

    def startStyle(self, fontname, size, decimalPlaces=2):
        return self.oneStyle(
            fontname,
            size,
            decimalPlaces=decimalPlaces,
            index=0,
        )


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
