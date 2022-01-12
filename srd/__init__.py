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
nonSimpleTypeNames = ['builtin_function_or_method', 'method']

'''
Anything heading with the same style as a subcategory but is on one of
the following pages is not a subcategory but still ends the previous
subcategory (Use page numbers instead of strings to avoid license
infringement):
'''
nonSubcategoryPages = [320, 395]

'''
A value in subcatEndStrings changes the subcategory of the current
creature to None if the current creature is under the subcategory
specified in the key--Handle situations where the subcategory ends
without warning (The next creature is even in alphabetical order of the
creature names in the subcategory by chance even though the
alphabetical order actually escaped the nested list of subcategorized
creatures and the creature name is there because it comes after the
previous subcategory):
'''
subcatEndStrings = {
    'Animated Objects': 'monstrosity,',
    'Dinosaurs': 'monstrosity (',
    'Dragons, Metallic': 'monstrosity,',
    'Elementals': 'humanoid (',
    'Genies': 'undead,',
    'Giants': 'aberration,',
    'Golems': 'monstrosity,',
    'Skeletons': 'chaotic evil',
    'Sphinxes': 'fey,',
}

'''
The first creature on each of the following pages sets the subcategory
to None (Use page numbers instead of strings to avoid license
infringement):
'''
subcatEndPages = [332, 336, 339]
doneSubcatEndPages = {}
for n in subcatEndPages:
    doneSubcatEndPages[n] = False

def assertPlainDict(d):
    for k,v in d.items():
        if type(v).__name__ in nonSimpleTypeNames:
            prerr()
            prerr("Bad dict item ({} is a {}):"
                  "".format(k, type(v).__name__))
            for k,v in d.items():
                prerr("{}: {}".format(k, v))
            raise ValueError("^ not a plain dict")


def dented(s):
    '''
    Replace \n with \n+indent (the global indent).
    '''
    if s is None:
        return None
    return s.replace("\n", "\n" + indent)


def pdent(msg):
    '''
    Write msg+newline to stdout but indent using the global 'indent'.
    '''
    sys.stdout.write("{}{}\n".format(indent, dented(msg)))
    sys.stdout.flush()


def edent(msg):
    '''
    Write msg+newline to stderr but indent using the global 'indent'.
    '''
    sys.stderr.write("{}{}\n".format(indent, dented(msg)))
    sys.stderr.flush()


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
        if type(v).__name__ in nonSimpleTypeNames:
            continue
        result[k] = v
    return result


def objDump(cls):
    return "{}".format(objDict(cls))


def chunkToDict(chunk):
    return chunk.toDict()


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
        chunk.pageN = d.get("pageN")
        return chunk

    def toDict(self):
        return {
            'text': self.text,
            'pageid': self.pageid,
            'pageN': self.pageN,
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


def dictToChunk(chunkD):
    # return DocChunk.fromDict(chunkD)
    # ^ Commented so pageaggregator and hence pdfminer isn't required
    #   unless chunks.json is not generated yet.

    pageid = chunkD['pageid']
    column = chunkD['column']
    bbox = chunkD['bbox']
    text = chunkD['text']
    fontName = chunkD.get('fontname')
    fontSize = chunkD.get('size')
    fragments = chunkD['fragments']
    annotations = chunkD['annotations']

    chunk = DocChunk(
        pageid,
        column,
        bbox,
        text,
        fontName=fontName,
        fontSize=fontSize,
        fragments=fragments,
        annotations=annotations,
    )
    chunk.pageN = chunkD['pageN']
    # ^ The code below doesn't fix it since it is None not missing!

    for k,v in chunkD.items():
        if not hasattr(chunk, k):
            # If not already handled above
            setattr(chunk, k, v)
    '''
    chunk.fragments = chunkD['fragments']
    chunk.annotations = chunkD['annotations']
    '''
    return chunk


def ltannoDump(ltanno):
    # return "{}".format(ltanno)
    return objDump(ltanno)


def ltannosDump(ltannos):
    if ltannos is None:
        return "None"
    result = "["
    delim = ""
    for ltanno in ltannos:
        if isinstance(ltanno, dict):
            result += delim + json.dumps(ltanno)
        else:
            result += delim + ltannoDump(ltanno)
        delim = ", "
    result += "]"
    return result


def chunkDump(chunk):
    if not hasattr(chunk, 'text'):
        # sys.stderr.write("chunkDump is converting a non-chunk...")
        # sys.stderr.flush()
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


def replaceMultiple(s, needles, newStr):
    '''
    Replace every needle in needles with newStr.
    '''
    for needle in needles:
        s = s.replace(needles, newStr)
    return s


def unitStrToPair(s, debugTB=None, allowInt=False, ignores=","):
    '''
    Convert a string like "100 XP" or "1 ft" to a tuple of (int,str).
    '''
    parts = s.split(" ")
    if len(parts) == 2:
        vStr = parts[0]
        v = None
        if allowInt:
            try:
                v = int(replaceMultiple(vStr, ignores, ""))
            except ValueError:
                v = float(replaceMultiple(vStr, ignores, ""))
        else:
            v = float(replaceMultiple(vStr, ignores, ""))
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
            for endSC, ender in subcatEndStrings.items():
                '''
                See the comment at the subcatEndStrings declaration for
                why this loop exists.
                '''
                if endSC != subcategory:
                    if ender in chunk.text:
                        creatureMsg = ""
                        if monster is not None:
                            creatureMsg = " for " + monster[NameHeader]
                        '''
                        pdent("Not ending Subcategory since {}"
                              " was found{} but in {} not {}"
                              "".format(ender, creatureMsg, subcategory,
                                        endSC))
                        '''
                    continue
                '''
                pdent("Checking for subcategory ender {} in {}"
                      "".format(ender, chunk.text))
                '''
                indent = "  "
                if ender in chunk.text:
                    pdent("End Subcategory since {} was found in {}"
                          "".format(ender, subcategory))
                    if monster is not None:
                        monster[SubCategoryHeader] = None
                        '''
                        Do NOT end the creature. Rather than a category
                        (which would end a creature), ender may just be
                        a property that indicates the creature has no
                        category.
                        '''
                    subcategory = None
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
                if chunk.pageN in subcatEndPages:
                    subcategory = None
                monster = {
                    NameHeader: chunk.text,
                    ContextHeader: context,
                    SubCategoryHeader: subcategory,
                    'pageN': chunk.pageN,
                }
                subContext = NameHeader
                indent = "    "
                pdent("Name {}:".format(monster[NameHeader].strip()))
            elif (chunk.oneStyle('DXJJCX+GillSans-SemiBold', 16.60656)
                  and (chunk.pageN not in nonSubcategoryPages)):
                '''
                NOTE: A monster can end with a category name,
                subcategory name (this case), or heading equivalent to
                subcategory (below), so see all instances of
                monsters.append for other examples of creature endings.
                '''
                # Monster type subsection
                if monster is not None:
                    monsters.append(monster)
                    monster = None
                indent = "  "
                if chunk.pageN not in nonSubcategoryPages:
                    pdent("Subcategory {}.{}"
                          "".format(context, chunkDump(chunk)))
                    for frag in chunk.fragments:
                        pdent("- \"{}\"".format(frag['text']))
                        pdent("  font: '{}' {}"
                              "".format(frag['fontname'], frag['size']))
                    monster = None
                    subcategory = chunk.text
            elif chunk.oneStyle('DXJJCX+GillSans-SemiBold', 16.60656):
                '''
                It is in nonSubcategoryPages (because the previous
                elif wasn't the case) so end the previous
                subcategory without starting a new one.
                '''
                if monster is not None:
                    monsters.append(monster)
                    monster = None
                subcategory = None
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
            elif chunk.startStyle('DXJJCX+GillSans-SemiBold', 21.4740):
                # such as "Monsters (B)"
                if monster is not None:
                    monsters.append(monster)
                    monster = None
                indent = ""
                subcategory = None
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
            if (pair[0] is None) or (pair[1] != 'XP'):
                raise ValueError("A string in the format \"(# XP)\" was"
                                 " expected after # [CR] in Challenge,"
                                 " but instead there was \"{}\""
                                 " resulting in {}"
                                 "".format(parts[1], pair))
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
    for monster in monsters:
        assertPlainDict(monster)
    with open(jsonPath, 'w') as outs:
        json.dump(monsters, outs, indent=2)  # sort_keys=True)
        # If there are errors, ensure only simple types not classes are
        # stored in the object.
    print("* wrote \"{}\"".format(jsonPath))
    tableHeaders = [NameHeader, "CR", "XP", "Languages", ContextHeader,
                    SubCategoryHeader, "Armor Class", "pageN",
                    "Hit Points", "Saving Throws", "Speed", "Skills",
                    "Senses"]
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
        prerr("* The chunk list \"{}\" was already created,"
              " so reading \"{}\" will be skipped if the list is ok."
              "".format(chunksPath, srcPath))
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
                if chunk['pageN'] != chunks[i].pageN:
                    raise RuntimeError("dictToChunk lost pageN.")
                if chunks[i].pageN is None:
                    raise RuntimeError("dictToChunk received no pageN.")
    if chunks is None:
        from srd.pagechunker import generateChunks
        chunks = generateChunks(
            srcPath,
            pageid=None,
            colStarts=[57.6, 328.56],
            max_pageid=1694,
        )
        for i in range(len(chunks)):
            chunk = chunks[i]
            chunks[i] = chunkToDict(chunk)
            if chunks[i]['pageN'] != chunks[i].pageN:
                raise RuntimeError("chunkToDict lost pageN.")
            if chunk.pageN is None:
                raise RuntimeError("chunkToDict received no pageN.")
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
            if chunk['pageN'] != chunks[i].pageN:
                raise RuntimeError("dictToChunk lost pageN.")
            if chunks[i].pageN is None:
                raise RuntimeError("dictToChunk received no pageN.")

    prerr("* processing chunks...")
    processChunks(chunks)
    prerr("* done processing chunks.")
'''
if __name__ == "__main__":
    main()
'''
