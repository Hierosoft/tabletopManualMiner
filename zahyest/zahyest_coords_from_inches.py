# -*- coding: utf-8 -*-
"""Convert inches to Zah Yest (Rodinia) coordinates

Assumptions:
- 0 degrees east is the leftmost point of land on Rodinia.
- at 35 degrees North, one inch covers 0.6179 degrees E, as 10 degrees
  is 6.184 in (See assumptions_text as shown in the GUI for the most
  up to date information).

MIT License: See https://github.com/Hierosoft/tabletopManualMiner

Near the middle (between top &amp; bottom), near the upper waypoints,
each 1{deg} E is .526 in. ((.487@top+.565@bottom)/2). For example, The
mountain site is 4.6857&quot; from the left, and 4.6857/.526 = 8.91{deg}E
(rounded).

* 3.591, 4.284 in = 38.79 N 5.74 E
* 4.591, 4.284 in = 38.79 N 7.50 E

(E result differs based on N due to the globe)
"""
# This should remain a self-contained file that is executable
#   from outside the tabletopManualMiner repo.
from __future__ import print_function
from __future__ import division
import sys
# import os

if sys.version_info.major >= 3:
    import tkinter as tk
else:
    import Tkinter as tk

DEG_SYMBOL_ASCII = "\xc2"  # Doesn't work in tkinter, though Python says
#   This is the character if you paste it.
DEG_SYMBOL = u"\xb0"
if sys.version_info.major < 3:
    # All of these commented result in
    #   ordinal not in range(128) in Python 2:
    # DEG_SYMBOL = u"\u00b0"
    # DEG_SYMBOL = u"\xb0"
    # DEG_SYMBOL = u'\u2103'  # stackoverflow.com/a/3215178/4541104
    # All commented below cause the whole line to become blank in
    #   Tkinter in Python 2:
    # DEG_SYMBOL = chr(176)  # doesn't work in Tkinter
    # DEG_SYMBOL = DEG_SYMBOL_ASCII  # doesn't work in Tkinter
    # DEG_SYMBOL = "º"  # Unicode degree symbol
    # Unicode almost works in Python 2 if 1st line of file is encoding
    #   but is degree symbol with underline (In Python 3 and Scribus
    #   it is the degree symbol).
    DEG_SYMBOL = "°"  # Extended ASCII
    # ^ extended ASCII pasted from rapidtables.com/code/text/ascii-table.html
    #   extended ASCII works in Python 2 if 1st line of file is encoding utf-8


inch_data = (
    (.808, 0.015),  # [0] is top-left
    (5.699, 0.015),  # [1] is top-right
    (0.025, 6.894),  # [2] is bottom-left
    (6.204, 6.894),  # [3] is bottom-right
)

degrees_data = (
    (0.0, 45.0),  # [0] is top-left
    (10.0, 45.0),  # [1] is top-right
    (0.0, 35.0),  # [2] is bottom-left
    (10.0, 35.0),  # [3] is bottom-right
)


class ReversiblePoly(object):
    def __init__(self):
        self.data = None
        self.inverse_cartesian = False

    @property
    def tl(self):
        return self.data[0]

    @property
    def tr(self):
        return self.data[1]

    @property
    def bl(self):
        return self.data[2]

    @property
    def br(self):
        return self.data[3]

    @property
    def bottom(self):
        if self.inverse_cartesian:
            return max(self.br[1], self.bl[1])
        return min(self.br[1], self.bl[1])

    @property
    def top(self):
        if self.inverse_cartesian:
            return min(self.tr[1], self.tl[1])
        return max(self.tr[1], self.tl[1])

    @property
    def left(self):
        return min(self.tl[0], self.bl[0])

    @property
    def right(self):
        return max(self.tr[0], self.br[0])

    @property
    def width(self):
        return self.right - self.left

    @property
    def width_at_bottom(self):
        return self.br[0] - self.bl[0]

    @property
    def height(self):
        if self.inverse_cartesian:
            return self.bottom - self.top
        return self.top - self.bottom

    def rightness(self, point):
        """Get rightness, accounting for non-flat right and left
        """
        x, y = point
        alpha = self.flat_downness(y)
        # Use alpha formula though this isn't color, just a location
        #   (the more down it is, the closer left is to bl[0])
        this_left = (alpha)*(self.bl[0]) + (1.0 - alpha)*(self.tl[0])
        this_right = (alpha)*(self.br[0]) + (1.0 - alpha)*(self.tr[0])
        this_width = this_right - this_left
        # (See <https://graphics.fandom.com/wiki/Alpha_blending>)
        return (x - this_left) / this_width

    def flat_downness(self, y, enable_upness=False):
        """Get the ratio of y between top and bottom.

        This assumes top and bottom are flat.
        Args:
            enable_upness (Optional[bool]): This exists so if
                flat_upness doesn't have to do 1-downness on a value
                that was already reversed once ("else" under "upness"
                doesn't have to reverse anything).
        """
        if enable_upness:
            if self.inverse_cartesian:
                # get reverse of downness to get upness
                return 1.0 - (y - self.top) / self.height
            # directly get enable_upness
            return ((y - self.bottom) / self.height)
        # else:  # downness
        if self.inverse_cartesian:
            return (y - self.top) / self.height
        # reverse of upness is downness
        return 1.0 - ((y - self.bottom) / self.height)

    def rational_to_point(self, point):
        """Convert a (rightness, downness) point to x, y in the quad.

        This assumes top and bottom are flat.
        """
        rightness, downness = point
        if self.inverse_cartesian:
            y = self.top + downness * self.height
        else:
            upness = 1.0 - downness
            y = self.bottom + upness * self.height
        alpha = self.flat_downness(y)
        # Use the alpha formula (This isn't color but principle is same)
        #   to get where left and right edges are at this y location in
        #   the quad.
        this_left = (alpha)*(self.bl[0]) + (1.0 - alpha)*(self.tl[0])
        this_right = (alpha)*(self.br[0]) + (1.0 - alpha)*(self.tr[0])
        this_width = this_right - this_left
        x = rightness * this_width + this_left
        return (x, y)

    def flat_upness(self, y):
        """Get the ratio of y between bottom and top.

        This assumes top and bottom are flat.
        """
        return self.flat_downness(y, enable_upness=True)


degpoly = ReversiblePoly()
degpoly.data = degrees_data

inpoly = ReversiblePoly()
inpoly.inverse_cartesian = True
inpoly.data = inch_data

assumptions_text = """at {bottom_deg_n}{deg}N:
{deg_bottom}{deg}E is mapped to {inches_bottom} inches""".format(
    bottom_deg_n=degpoly.bottom,
    deg_bottom=degpoly.width_at_bottom,
    inches_bottom=round(inpoly.width_at_bottom, 5),
    deg=DEG_SYMBOL,
)


def inches_to_degrees(inch_point, inpoly, degpoly):
    # inx, iny = inch_point
    # degx = None
    # degy = None
    # degpoly = ReversiblePoly()
    # degpoly.data = degrees_poly
    # inpoly = ReversiblePoly()
    # inpoly.data = inch_poly
    # upness = inpoly.flat_upness(inch_point[1])
    downness = inpoly.flat_downness(inch_point[1])
    rightness = inpoly.rightness(inch_point)
    return degpoly.rational_to_point((rightness, downness))


def main_cli():
    if len(sys.argv) < 3:
        raise ValueError("Provide x then y in inches.")
    x = float(sys.argv[1])
    y = float(sys.argv[2])
    e, n = inches_to_degrees((x, y), inpoly, degpoly)  # y is north
    print("{n}{deg}N  {e}{deg}E".format(
        n=n,
        e=e,
        deg=DEG_SYMBOL,
    ))


class MainApplication(tk.Frame):
    def __init__(self, root, *args, **kwargs):
        tk.Frame.__init__(self, root, *args, **kwargs)
        root.title("Zah Yest Coordinates")
        # winW = root.winfo_screenwidth()
        # winH = root.winfo_screenheight()
        more_tk_args = {
            "padx": 10,
            "pady": 10,
        }
        # root.geometry("%sx%s" % (winW//6, winH//10))
        # ^ setting height prevents expansion, so:
        # root.minsize(winW//4, winH//10)
        # ^ too wide on multi-monitor setups, so make it more automatic:
        biggest_label_text = "North is 1st in cartography"
        # fluff = 16  # this many characters accounts for window border
        fluff = more_tk_args['padx'] // 2 + more_tk_args['padx'] // 2 + 4
        biggest_label_text_expanded = \
            " "*(fluff//2) + biggest_label_text + " "*(fluff//2)
        self.root = root
        self.parent = root

        self.xInLabel = tk.Label(
            self,
            text=("x is first measurement"
                  "\n\nInches from left"
                  "\n(use corner not side as 0):"),
        )
        self.xInLabel.pack(**more_tk_args)
        self.xInVar = tk.StringVar(self)
        self.xInEntry = tk.Entry(self, textvariable=self.xInVar)
        self.xInEntry.pack(**more_tk_args)

        self.yInLabel = tk.Label(
            self,
            text="Inches from top\n(since Inkscape is inverse cartesian):",
        )
        self.yInLabel.pack(**more_tk_args)
        self.yInVar = tk.StringVar(self)
        self.yInEntry = tk.Entry(self, textvariable=self.yInVar)
        self.yInEntry.pack(**more_tk_args)
        # self.inLabel = tk.Label(
        #     self,
        #     text="y is inverted in Inkscape\n(map in appendix)",
        # )
        # self.inLabel.pack(**more_tk_args)

        self.assumptionsLabel = tk.Label(
            self,
            text="assuming "+assumptions_text,
        )
        self.assumptionsLabel.pack(**more_tk_args)

        self.outButton = tk.Button(
            self,
            text="=",
            command=self.calculateClicked,
        )
        self.outButton.pack(**more_tk_args)

        self.outVar = tk.StringVar(self)
        self.outEntry = tk.Entry(self, textvariable=self.outVar)
        self.outEntry.pack(**more_tk_args)
        self.outEntry.configure(
            state="readonly",  # tk.DISABLED,   # tk.NORMAL
        )
        self.outLabel = tk.Label(
            self,
            text=biggest_label_text_expanded,
        )
        self.outLabel.pack(**more_tk_args)

        self.statusVar = tk.StringVar(self)
        self.statusEntry = tk.Entry(
            self,
            textvariable=self.statusVar,
            state="readonly",
        )
        self.statusEntry.pack(
            side=tk.BOTTOM,
            anchor=tk.S,
            # expand=True,  # fill space not taken by parent still doesn't:
            fill=tk.X,
        )

    def setStatus(self, msg):
        self.statusVar.set(msg)

    def calculateClicked(self):
        self.setStatus("")
        try:
            x = float(self.xInVar.get().strip())
            y = float(self.yInVar.get().strip())
            e, n = inches_to_degrees((x, y), inpoly, degpoly)  # y is north.
            self.outVar.set("{n}{deg}N  {e}{deg}E".format(
                n=round(n, 2),
                e=round(e, 2),
                deg=DEG_SYMBOL,
            ))
        except Exception as ex:
            self.setStatus(str(ex))


if __name__ == "__main__":
    root = tk.Tk()
    MainApplication(root).pack(side="top", fill="both", expand=True)
    root.mainloop()
