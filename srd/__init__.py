#!/usr/bin/env python3

if __name__ == "__main__":
    print("You must import the srd module instead of running it.")
    exit(1)

import os
import platform
import sys
import json
import csv

def prerr(msg):
    sys.stderr.write("{}\n".format(msg))
    sys.stderr.flush()

from srd.pdfdetails import (
    PDFPageDetailedAggregator,
    DocChunk,
)

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

from io import (
    StringIO,
    BufferedWriter,
)

alphabetUpper = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

profile = None
if platform.system() == "Windows":
    profile = os.environ['USERPROFILE']
else:
    profile = os.environ['HOME']

modulePath = os.path.dirname(os.path.realpath(__file__))
dataPath = os.path.join(modulePath, "data")
if not os.path.isdir(dataPath):
    os.mkdir(dataPath)
    print("(* created dataPath: {}".format(dataPath))

chunksName = "chunks.json"
chunksPath = os.path.join(dataPath, chunksName)
indent = ""


def dented(s):
    '''
    Replace \n with \n + the global indent.
    '''
    if s is None:
        return None
    return s.replace("\n", "\n" + indent)


def pdent(msg):
    '''
    print, but indent using the global 'indent'.
    '''
    sys.stdout.write("{}{}\n".format(indent, dented(msg)))
    sys.stdout.flush()


def edent(msg):
    '''
    write to stderr, but indent using the global 'indent'.
    '''
    sys.stderr.write("{}{}\n".format(indent, dented(msg)))
    sys.stderr.flush()


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


def strCount(v):
    '''
    If v is a string, the result is 1. If it is a list, the result is
    len(v).
    '''
    if isinstance(v, str):
        return 1
    elif isinstance(v, list):
        return len(v)
    raise TypeError("Type {} isn't implemented in stringCount."
                    "".format(type(v).__name__))


def objDict(o):
    result = {}
    for k in dir(o):
        if k.startswith("__"):
            continue
        v = getattr(o, k)
        if isinstance(v, BufferedWriter):
            continue
        result[k] = v
    return result


def ltannoDict(ltanno):
    return objDict(ltanno)


def objDump(cls):
    return "{}".format(objDict(cls))


def chunkDict(chunk):
    return chunk.toDict()


def dictToChunk(chunkD):
    return DocChunk.fromDict(chunkD)


def ltannoDump(ltanno):
    # return "{}".format(ltanno)
    return objDump(ltanno)


def ltannosDump(ltannos):
    if ltannos is None:
        return "None"
    result = "["
    delim = ""
    for ltanno in ltannos:
        result += delim + ltannoDump(ltanno)
        delim = ", "
    result += "]"
    return result


def chunkDump(chunk):
    if not hasattr(chunk, 'text'):
        chunk = dictToChunk(chunk)
    return ("\"{}\" p. {} pageid={} font={} size={} annotations={}"
            "".format(chunk.text, chunk.pageN, chunk.pageid,
                      chunk.fontName, chunk.fontSize,
                      ltannosDump(chunk.annotations)))


def fractionToFloat(s, allowInt=False):
    '''
    Convert the fraction string containing "/" to a
    float, or if allowInt, to an int if isn't a fraction.
    '''
    parts = s.split("/")
    if len(parts) == 2:
        return float(parts[0]) / float(parts[1])
    elif len(parts) == 1:
        if allowInt:
            return int(s)
        return float(s)
    raise ValueError("The fractionToFloat function only recognizes"
                     " numbers with only one (or no) '/'.")


def floatToFraction(f):
    parts = f.as_integer_ratio()
    if parts[1] == 1:
        return str(parts[0])
    return str(parts[0]) + "/" + str(parts[1])


def unitStrToPair(s, debugTB=None, allowInt=False):
    '''
    Convert a string like "100 XP" or "1 ft" to a tuple of (int,str).
    '''
    parts = s.split(" ")
    if len(parts) == 2:
        vStr = parts[0]
        v = None
        if allowInt:
            try:
                v = int(vStr)
            except ValueError:
                v = float(vStr)
        return v, parts[1]
    # elif len(parts) == 1:
    #     return int(s)
    fSuffix = ""
    if debugTB is not None:
        fSuffix = " (called by {})".format(debugTB)
    raise ValueError("The unitStrToPair function{} only recognizes"
                     "number+unit strings separated by only one space.")


def unitStrToValue(s, allowInt=False):
    return unitStrToPair(s, "unitStrToValue", allowInt=allowInt)[0]


def splitNotInParens(s, delimiters=" \r\n\t", pairs=[('(', ')'),]):
    ender = None
    result = ""
    results = []
    inSpace = False
    for c in s:
        if ender is None:
            for pair in pairs:
                if c == pair[0]:
                    ender = pair[1]
        elif c == ender:
            ender = None
        if (c in delimiters) and (ender is None):
            if not inSpace:
                results.append(result)
                result = ""
                inSpace = True
        elif inSpace:
            inSpace = False
            result += c
        else:
            result += c
    results.append(result)
    return results


def generateMeta(path, pageid=None, colStarts=None, max_pageid=None):
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


def processChunks(chunks):
    global indent
    monsterLetterHeadings = []
    for letter in alphabetUpper:
        monsterLetterHeadings.append("Monsters ({})".format(letter))
    monster = None
    monsters = []
    statHeaders = ["STR", "CHA", "CON", "DEX", "WIS", "INT"]
    categoryMarks = {  # expected categories
        'Monster': {
            'start': "Monsters (A)",  # frag font: 'DXJJCX+GillSans-SemiBold' 21.474000000000046
            'end': "Appendix PH-A:",  # frag font: 'DXJJCX+GillSans-SemiBold' 30.922559999999976
        },
        'Creature': {
            'start': ["Appendix MM-A:", "Miscellaneous", "Creatures"],
            'end': "Appendix MM-B:",
        },
        'NPC': {
            'start': ["Appendix MM-B:", "Nonplayer", "Characters"],
            'end': ["5.1", "403"],
        },
    }
    creatureTypes = ['Monster', 'Creature', 'NPC']
    for k,o in categoryMarks.items():
        o['startCount'] = 0
        o['endCount'] = 0
    subcategory = None
    context = None
    prevChunk = None

    for chunk in chunks:
        startIsComplete = False
        endIsComplete = False
        newContext = None
        for tryContext,mk in categoryMarks.items():
            if strCount(mk['end']) == 1:
                if mk['end'] in chunk.text:
                    endIsComplete = True
                    mk['endCount'] += 1
                    newContext = None
                    context = None
            else:
                if mk['endCount'] < strCount(mk['end']):
                    if mk['end'][mk['endCount']] in chunk.text:
                        mk['endCount'] += 1
                        if mk['endCount'] == strCount(mk['end']):
                            endIsComplete = True
                            newContext = None
                            context = None
            if endIsComplete:
                if monster is not None:
                    monsters.append(monster)
                    monster = None
            # Keep the cases separate since the start of one may be the
            # same text box as the end of the previous one.
            if strCount(mk['start']) == 1:
                if mk['start'] in chunk.text:
                    startIsComplete = True
                    mk['startCount'] += 1
                    newContext = tryContext
            else:
                if mk['startCount'] < strCount(mk['start']):
                    if mk['start'][mk['startCount']] in chunk.text:
                        mk['startCount'] += 1
                        if mk['startCount'] == strCount(mk['start']):
                            startIsComplete = True
                            newContext = tryContext

        if newContext is not None:
            if context is not None:
                raise RuntimeError("\"{}\" was found before"
                                   "\"{}\" ended."
                                   "".format(newContext, context))

        if newContext is not None:
            if endIsComplete:
                subcategory = None  # When category ends so does sub
                if context is not None:
                    context = None
                    indent = "  "
                    pdent("End of {} was inferred from {}"
                          "".format(newContext, chunkDump(chunk)))
                    indent = ""
                    pdent("Section: \"{}\"".format(chunk.text))
                    '''
                    for frag in chunk.fragments:
                        pdent("- \"{}\"".format(frag['text']))
                        pdent("  font: '{}' {}"
                              "".format(frag['fontname'], frag['size']))
                    '''
            # Keep the cases separate since the start of one can mark
            # the end of another.
            if startIsComplete:
                subcategory = None  # When category starts sub ends
                if context != newContext:
                    context = newContext
                    indent = ""
                    pdent("Category '{}' was inferred from {}"
                          "".format(newContext, chunkDump(chunk)))
                    '''
                    for frag in chunk.fragments:
                        pdent("- \"{}\"".format(frag['text']))
                        pdent("  font: '{}' {}"
                              "".format(frag['fontname'], frag['size']))
                    '''

        isOneFrag = len(chunk.fragments) == 1
        statName = None
        oneFrag = None
        if isOneFrag:
            oneFrag = chunk.fragments[0]

        # Known SRD 5.1 styles are represented by the params of
        # the oneStyle and startStyle calls below.

        NameHeader = 'ClassName'  # a.k.a. Name, such as "Spy"
        ContextHeader = 'Category'
        SubCategoryHeader = 'Subcategory'
        prevStatName = None
        if context in creatureTypes:
            subContext = None
            if statName is not None:
                # such as Challenge
                # font: 'LUFRKP+Calibri' 13.116719999999987
                if monster is not None:
                    if statName == "INT":
                        pdent("- found stats")
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
                        pdent("- found \"{}\"".format(statName))
                        monster[statName] = chunk.text
                else:
                    pdent("WARNING: A stat was not under a monster in"
                          " \"{}\"".format(chunk.text))
                prevStatName = statName
                statName = None
            elif chunk.oneStyle('WWROEK+Calibri-Bold', 16.1399):
                # ^ Actually 16.139999999999986, but take advantage of
                #   oneStyle's default rounding.
                # ClassName (Creature, NPC, or Monster name):
                if monster is not None:
                    monsters.append(monster)
                monster = {
                    NameHeader: chunk.text,
                    ContextHeader: context,
                    SubCategoryHeader: subcategory,
                }
                subContext = NameHeader
                indent = "    "
                pdent("Name {}:".format(monster[NameHeader].strip()))
            elif chunk.oneStyle('DXJJCX+GillSans-SemiBold', 16.60656):
                # Monster type subsection
                if monster is not None:
                    monsters.append(monster)
                    monster = None
                indent = "  "
                pdent("Subcategory {}.{}"
                      "".format(context, chunk.text))
                for frag in chunk.fragments:
                    pdent("- \"{}\"".format(frag['text']))
                    pdent("  font: '{}' {}"
                          "".format(frag['fontname'], frag['size']))
                monster = None
                subcategory = chunk.text
                # NOTE: A monster can end with a category name too
                # (See endIsComplete)!
            elif chunk.startStyle('WWROEK+Calibri-Bold', 13.2348):
                # 13.234800000000064
                # Stat
                if monster is None:
                    pdent("Unknown stat: \"{}\"".format(chunk.text))
                    pdent("  len(fragments): {}"
                          "".format(len(chunk.fragments)))
                    for frag in chunk.fragments:
                        pdent("  - unknown fragment \"{}\""
                              "".format(frag['text']))
                        pdent("    font: '{}' {}"
                              "".format(frag['fontname'], frag['size']))
                else:
                    statName = chunk.fragments[0]['text']
                    if len(chunk.fragments) == 2:
                        monster[statName] = chunk.fragments[1]['text']
                    else:
                        # statName = chunk.text
                        pdent("Unparsed stat: \"{}\""
                              "".format(chunk.text))
                        pdent("  len(fragments): {}"
                              "".format(len(chunk.fragments)))
                        for frag in chunk.fragments:
                            pdent("  - unknown fragment \"{}\""
                                  "".format(frag['text']))
                            pdent("    font: '{}' {}"
                                  "".format(frag['fontname'],
                                            frag['size']))

            elif monster is not None:
                pdent("Unknown chunk after {}: \"{}\""
                      "".format(prevStatName, chunk.text))
                pdent("  len(fragments): {}"
                      "".format(len(chunk.fragments)))
                for frag in chunk.fragments:
                    appendMsg = ""
                    if prevStatName is not None:
                        monster[NameHeader]
                        appendMsg = (" appended to {}"
                                     "".format(monster[NameHeader]))
                    pdent("  - unknown fragment \"{}\"{}"
                          "".format(frag['text'], appendMsg))
                    pdent("    font: '{}' {}"
                          "".format(frag['fontname'], frag['size']))
                prevStatName = None
            if chunk.text == "Ghost":
                '''
                This should never happen. It is the last creature in
                the subcategory, so the subcategory end code should
                append this creature.
                '''
                if subContext != NameHeader:
                    pdent("Found undetected creature: {}"
                          "".format(chunkDump(chunk)))
        prevChunk = chunk

    if monster is not None:
        monsters.append(monster)
    jsonName = 'creatures.json'
    jsonPath = os.path.join(dataPath, jsonName)
    for monster in monsters:
        crxp = monster.get('Challenge')
        if crxp is not None:
            parts = splitNotInParens(crxp)
            try:
                monster['CR'] = fractionToFloat(parts[0])
                XPs = noParens(parts[1])
            except IndexError as ex:
                print("splitNotInParens didn't split \"{}\" in two"
                      " (a string formatted like \"# (# XP)\""
                      " was expected)"
                      "".format(crxp))
                raise ex
            try:
                pair = unitStrToPair(XPs)
            except Exception as ex:
                print("Couldn't finish parsing \"{}\" in \"{}\""
                      " (expected a string formatted like"
                      " \"# XP\" after # [CR] in \"{}\")"
                      "".format(XPs, parts[1], crxp))
                raise ex
            if pair[1] != 'XP':
                raise ValueError("A string in the format \"(# XP)\" was"
                                 " expected after # [CR] in Challenge,"
                                 " but instead there was \"{}\"."
                                 "".format(parts[1]))
            monster['XP'] = pair[0]
        else:
            monster['CR'] = -1
            monster['XP'] = -1
            print("WARNING: {} \"{}\" is missing 'Challenge'"
                  "".format(monster.get(ContextHeader),
                            monster.get(NameHeader)))
    monsters = sorted(monsters, key = lambda o: o['CR'])
    for monster in monsters:
        monster['CR'] = floatToFraction(monster['CR'])
    with open(jsonPath, 'w') as outs:
        json.dump(monsters, outs, indent=2)  # sort_keys=True)
        # If there are errors, ensure only simple types not classes are
        # stored in the object.
    print("* wrote \"{}\"".format(jsonPath))
    tableHeaders = [NameHeader, "CR", "XP", "Languages", ContextHeader,
                    SubCategoryHeader, "Armor Class", "Hit Points",
                    "Saving Throws", "Speed", "Skills", "Senses"]
    tableHeaders += statHeaders
    csvName = 'creatures.csv'
    csvPath = os.path.join(dataPath, csvName)
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

    chunks = None
    if os.path.isfile(chunksPath):
        prerr("* The chunk list from \"{}\" was already created."
              "".format(srcPath))
        prerr("  * loading \"{}\"".format(chunksPath))
        try:
            with open(chunksPath, 'r') as ins:
                chunks = json.load(ins)
        except json.decoder.JSONDecodeError as ex:
            prerr(str(ex))
            prerr("  * deleting bad \"{}\"".format(chunksPath))
            os.remove(chunksPath)
            chunks = None
        if chunks is not None:
            for i in range(len(chunks)):
                chunk = chunks[i]
                chunks[i] = dictToChunk(chunk)
    if chunks is None:
        chunks = generateMeta(
            srcPath,
            pageid=None,
            colStarts=[57.6, 328.56],
            max_pageid=1694,
        )
        for i in range(len(chunks)):
            chunk = chunks[i]
            chunks[i] = chunkDict(chunk)
        # pre-save test:
        for chunk in chunks:
            print("* testing conversion of chunk {}"
                  "".format(chunkDump(chunk)))
            jsonStr = json.dumps(chunk)
        sys.stderr.write("  * saving \"{}\"...".format(chunksPath))
        sys.stderr.flush()
        with open(chunksPath, 'w') as outs:
            json.dump(chunks, outs, indent=2)
        sys.stderr.write("OK\n")
        sys.stderr.flush()
        for i in range(len(chunks)):
            chunk = chunks[i]
            # It is a dict now whether saved or loaded due to use in
            # json save or load.
            chunks[i] = dictToChunk(chunk)
    prerr("* processing chunks...")
    processChunks(chunks)
    prerr("* done processing chunks.")
'''
if __name__ == "__main__":
    main()
'''
