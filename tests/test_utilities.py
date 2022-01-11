#!/usr/bin/env python
import sys
import os
from unittest import TestCase
'''
try:
    import srd
except ModuleNotFoundError as ex:
    if "No module named 'srd'" in str(ex):
        sys.path.append("..")
        try:
            import srd
        except ModuleNotFoundError as ex2:
            if "No module named 'srd'" in str(ex2):
                "Error: The srd module is missing."
                exit(1)
            else:
                print("Unknown error (in ..) \"{}\"".format(str(ex2)))
                raise ex
    else:
        print("Unknown error (in .) \"{}\"".format(str(ex)))
        raise ex
'''
from srd import (
    fractionToFloat,
    noParens,
    splitNotInParens,
    unitStrToValue,
)

def prerr(msg):
    sys.stderr.write("{}\n".format(msg))
    sys.stderr.flush()


class TestUtilities(TestCase):
    def test_parsing_utilities(self):
        # self.assertTrue()
        Challenge = "1/2 (100 XP)"
        parts = ["1/2", "(100 XP)"]
        unitStr = "100 XP"
        prerr("* testing splitNotInParens...")
        self.assertEqual(splitNotInParens(Challenge), parts)
        prerr("* testing fractionToFloat...")
        self.assertEqual(fractionToFloat(parts[0]), .5)
        prerr("* testing noParens...")
        self.assertEqual(noParens(parts[1]), unitStr)
        prerr("* testing unitStrToValue...")
        self.assertEqual(unitStrToValue(unitStr), 100)
        prerr("* testing unitStrToValue with a comma...")
        self.assertEqual(unitStrToValue("1,000"), 1000)


if __name__ == "__main__":
    print("Error: You ran a test module"
          " but nose should have imported it instead.")
    print("Run tests from {} via:"
          "".format(os.path.realpath("..")))
    print("python3 -m nose")
    print("#or:")
    print("python -m nose")
