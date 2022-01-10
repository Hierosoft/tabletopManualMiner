#!/usr/bin/env python3

import os
import platform
import sys
import json
import csv

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

alphabetUpper = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

profile = None
if platform.system() == "Windows":
    profile = os.environ['USERPROFILE']
else:
    profile = os.environ['HOME']


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


def noParens(s):
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1]
    return s


def generateMeta(path, pageid=None, colStarts=None, max_pageid=None):
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
        colStarts=colStarts,
    )
    interpreter = PDFPageInterpreter(rsrcmgr, device)

    UNKNOWN = 0
    CONTEXT_MONSTERS = 1
    CONTEXT_APPENDIX_A = 2
    context = UNKNOWN

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
            sys.stderr.write("{}{}{}    "
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
    context = UNKNOWN
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

    monsterLetterHeadings = []
    for letter in alphabetUpper:
        monsterLetterHeadings.append("Monsters ({})".format(letter))
    monster = None
    monsters = []
    for chunk in device.chunks:
        if "Monsters (A)" in chunk.text:
            # frag font: 'DXJJCX+GillSans-SemiBold' 21.474000000000046
            if context != CONTEXT_MONSTERS:
                context = CONTEXT_MONSTERS
                print("Found Monsters: \"{}\" p. {} id {} font {} size {}"
                      "".format(chunk.text, chunk.pageN, chunk.pageid, chunk.fontName, chunk.fontSize))
                '''
                for frag in chunk.fragments:
                    print("- \"{}\"".format(frag.text))
                    print("  font: '{}' {}"
                          "".format(frag.fontname, frag.size))
                '''
        elif "Appendix PH-A:" in chunk.text:
            # frag font: 'DXJJCX+GillSans-SemiBold' 30.922559999999976
            if context != CONTEXT_APPENDIX_A:
                context = CONTEXT_APPENDIX_A
                print("Found end of Monsters: \"{}\" page {} id {} font {} size {}"
                      "".format(chunk.text, chunk.pageN, chunk.pageid, chunk.fontName, chunk.fontSize))
                print("Section: \"{}\"".format(chunk.text))
                '''
                for frag in chunk.fragments:
                    print("- \"{}\"".format(frag.text))
                    print("  font: '{}' {}"
                          "".format(frag.fontname, frag.size))
                '''
        # Known SRD 5.1 styles:
        #
        isOneFrag = len(chunk.fragments) == 1
        statName = None
        oneFrag = None
        if isOneFrag:
            oneFrag = chunk.fragments[0]
        statHeaders = ["STR", "CHA", "CON", "DEX", "WIS", "INT"]
        NameHeader = 'name'
        if context == CONTEXT_MONSTERS:
            if statName is not None:
                if monster is not None:
                    # such as challenge
                    # font: 'LUFRKP+Calibri' 13.116719999999987
                    if statName == "INT":
                        print("- found stats")
                        parts = chunk.text.split()
                        if len(parts) != 12:
                            raise ValueError("Expected 12 parts"
                                             " (6 like \"stat (mod)\")"
                                             " after INT but got: "
                                             "\"{}\""
                                             "".format(statName))
                        offset = 0
                        for statH in statHeaders:
                            monster[statH] = int(parts[0+offset])
                            statTitle = statH.title() + "Mod"
                            statMod = int(noParens(parts[1+offset]))
                            monster[statTitle] = statMod
                            offset += 2
                    elif statName in statHeaders:
                        # Do nothing for each header (Wait for next row)
                        pass
                    else:
                        print("- found \"{}\"".format(statName))
                        monster[statName] = chunk.text
                else:
                    print("WARNING: A stat was not under a monster in"
                          " \"{}\"".format(chunk.text))
                statName = None
            elif chunk.oneStyle('WWROEK+Calibri-Bold', 16.1399):
                # ^ Actually 16.139999999999986, but take advantage of
                #   oneStyle's default rounding.
                if monster is not None:
                    monsters.append(monster)
                monster = {
                    NameHeader: chunk.text
                }
                print("{}:".format(monster[NameHeader].strip()))
            elif chunk.oneStyle('DXJJCX+GillSans-SemiBold', 16.60656):
                # Monster type subsection
                if monster is not None:
                    monsters.append(monster)
                    monster = None
                print("Monsters of type: \"{}\"".format(chunk.text))
                for frag in chunk.fragments:
                    print("- \"{}\"".format(frag.text))
                    print("  font: '{}' {}"
                          "".format(frag.fontname, frag.size))
                monster = None
            elif chunk.startStyle('WWROEK+Calibri-Bold', 13.2348):
                # 13.234800000000064
                if monster is None:
                    print("Unknown stat: \"{}\"".format(chunk.text))
                    print("  len(fragments): {}"
                          "".format(len(chunk.fragments)))
                    for frag in chunk.fragments:
                        print("  - unknown fragment \"{}\""
                              "".format(frag.text))
                        print("    font: '{}' {}"
                              "".format(frag.fontname, frag.size))
                else:
                    statName = chunk.fragments[0].text
                    if len(chunk.fragments) == 2:
                        monster[statName] = chunk.fragments[1].text
                    else:
                        # statName = chunk.text
                        print("Unparsed stat: \"{}\""
                              "".format(chunk.text))
                        print("  len(fragments): {}"
                              "".format(len(chunk.fragments)))
                        for frag in chunk.fragments:
                            print("  - unknown fragment \"{}\""
                                  "".format(frag.text))
                            print("    font: '{}' {}"
                                  "".format(frag.fontname, frag.size))

            elif monster is not None:
                print("Unknown chunk: \"{}\"".format(chunk.text))
                print("  len(fragments): {}"
                      "".format(len(chunk.fragments)))
                for frag in chunk.fragments:
                    print("  - unknown fragment \"{}\""
                          "".format(frag.text))
                    print("    font: '{}' {}"
                          "".format(frag.fontname, frag.size))
        prevChunk = chunk

    if monster is not None:
        monsters.append(monster)
    jsonName = 'monsters.json'
    jsonPath = os.path.realpath(jsonName)
    with open(jsonPath, 'w') as outs:
        json.dump(monsters, outs, indent=2)  # sort_keys=True)
        # If there are errors, ensure only simple types not classes are
        # stored in the object.
    print("* wrote \"{}\"".format(jsonPath))
    tableHeaders = [NameHeader, "Challenge", "Languages", "Armor Class", "Hit Points", "Saving Throws", "Speed", "Skills", "Senses"]
    csvName = 'monsters.csv'
    csvPath = os.path.realpath(csvName)
    with open(csvPath, 'w') as outs:
        writer = csv.writer(outs)
        writer.writerow(tableHeaders)
        for monster in monsters:
            row = []
            for header in tableHeaders:
                got = monster.get(header)
                row.append(got)
            writer.writerow(row)
    print("* wrote \"{}\"".format(csvPath))


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
    generateMeta(
        srcPath,
        pageid=None,
        colStarts=[57.6, 328.56],
        max_pageid=1694,
    )


if __name__ == "__main__":
    main()
