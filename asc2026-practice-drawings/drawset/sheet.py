"""
Sheet framework: ARCH D (36" x 24") border + vertical title block on the right.

Every sheet module exposes  SHEETS = [(number, title, draw_function), ...]
draw_function(sh: Sheet) draws inside sh.area (paper inches).
"""
from __future__ import annotations

from reportlab.pdfgen.canvas import Canvas

from .cad import (FONT, FONT_B, FONT_I, LW, PT, TXT, Paper, View, north_arrow, scale_bar,
                  view_title)

SHEET_W, SHEET_H = 36.0, 24.0
MARGIN_L, MARGIN_R, MARGIN_T, MARGIN_B = 1.0, 0.375, 0.375, 0.375
TB_W = 3.1  # title block width

PROJECT = {
    "name1": "CEDAR PRAIRIE ELEMENTARY SCHOOL",
    "name2": "TWO-STORY CLASSROOM ADDITION",
    "address": "1400 PRAIRIE AVENUE, CEDAR PRAIRIE, ILLINOIS",
    "owner": "CEDAR PRAIRIE COMMUNITY SCHOOL DISTRICT",
    "number": "2026-117",
    "issue": "BID SET",
    "date": "SEPTEMBER 15, 2026",
}

DISCIPLINE = {
    "G": "GENERAL", "C": "CIVIL", "S": "STRUCTURAL", "A": "ARCHITECTURAL", "AD": "ARCHITECTURAL",
}


class Sheet(Paper):
    def __init__(self, c: Canvas, number: str, title: str, index: int = 0, total: int = 0):
        super().__init__(c)
        self.number = number
        self.title = title
        self.index = index
        self.total = total
        # drawing area (inside border, left of title block)
        self.x0 = MARGIN_L + 0.12
        self.y0 = MARGIN_B + 0.12
        self.x1 = SHEET_W - MARGIN_R - TB_W - 0.12
        self.y1 = SHEET_H - MARGIN_T - 0.12
        self.area = (self.x0, self.y0, self.x1, self.y1)

    @property
    def w(self):
        return self.x1 - self.x0

    @property
    def h(self):
        return self.y1 - self.y0

    def view(self, ox, oy, scale, mx=0.0, my=0.0, rot=0.0) -> View:
        return View(self.c, ox, oy, scale, mx, my, rot)

    def cells(self, cols, rows, x0=None, y0=None, x1=None, y1=None, gutter=0.0, lines=True):
        """Split (part of) the drawing area into a grid of detail cells.
        Returns list of dicts (row-major from top-left): {x, y, w, h} (lower-left, size)."""
        X0 = self.x0 if x0 is None else x0
        Y0 = self.y0 if y0 is None else y0
        X1 = self.x1 if x1 is None else x1
        Y1 = self.y1 if y1 is None else y1
        cw = (X1 - X0) / cols
        ch = (Y1 - Y0) / rows
        out = []
        for r in range(rows):
            for k in range(cols):
                x = X0 + k * cw
                y = Y1 - (r + 1) * ch
                out.append({"x": x + gutter / 2, "y": y + gutter / 2, "w": cw - gutter,
                            "h": ch - gutter})
        if lines:
            for k in range(1, cols):
                self.line((X0 + k * cw, Y0), (X0 + k * cw, Y1), lw="fine")
            for r in range(1, rows):
                self.line((X0, Y0 + r * ch), (X1, Y0 + r * ch), lw="fine")
        return out

    def merge_cells(self, cells, idxs):
        xs = [cells[i]["x"] for i in idxs] + [cells[i]["x"] + cells[i]["w"] for i in idxs]
        ys = [cells[i]["y"] for i in idxs] + [cells[i]["y"] + cells[i]["h"] for i in idxs]
        return {"x": min(xs), "y": min(ys), "w": max(xs) - min(xs), "h": max(ys) - min(ys)}

    def view_title(self, x, y, num, title, scale=None, sheet=None, width=None, note=None):
        view_title(self, x, y, num, title, scale, sheet, width, note)

    def north_arrow(self, x, y, size=0.7, rot=0.0):
        north_arrow(self, x, y, size, rot)

    def scale_bar(self, x, y, scale, feet_total=None):
        scale_bar(self, x, y, scale, feet_total)

    # ------------------------------------------------------------------------------
    def frame(self):
        """Border + title block. Called by the builder before the sheet's draw function."""
        c = self.c
        # outer trim line and border
        self.rect(MARGIN_L, MARGIN_B, SHEET_W - MARGIN_L - MARGIN_R, SHEET_H - MARGIN_T - MARGIN_B,
                  lw="border")
        tbx = SHEET_W - MARGIN_R - TB_W
        self.line((tbx, MARGIN_B), (tbx, SHEET_H - MARGIN_T), lw="heavy")
        x = tbx + 0.12
        W = TB_W - 0.24
        top = SHEET_H - MARGIN_T
        y = top - 0.15

        # practice banner
        self.rect(tbx, top - 0.55, TB_W, 0.55, lw=None, fill="g80")
        self.text((tbx + TB_W / 2, top - 0.2), "ESTIMATING PRACTICE SET", size=TXT["sub"],
                  font=FONT_B, anchor="c", valign="mid", color="white")
        self.text((tbx + TB_W / 2, top - 0.40), "FICTIONAL PROJECT - NOT FOR CONSTRUCTION",
                  size=TXT["small"], font=FONT_B, anchor="c", valign="mid", color="white")
        y = top - 0.75

        # architect block
        self.text((x, y), "ARCHITECT", size=TXT["tiny"], font=FONT_B, valign="top")
        y -= 0.13
        self.text((x, y), "PRAIRIE LINE STUDIO (PRACTICE)", size=TXT["label"], font=FONT_B,
                  valign="top")
        y -= 0.14
        self.mtext((x, y), ["ARCHITECTURE  |  PLANNING", "TRAINING DOCUMENTS FOR ESTIMATING EDUCATION"],
                   size=TXT["tiny"], valign="top")
        y -= 0.3
        self.line((tbx, y), (tbx + TB_W, y), lw="thin")
        y -= 0.1
        self.text((x, y), "CONSULTANTS", size=TXT["tiny"], font=FONT_B, valign="top")
        y -= 0.13
        for role, firm in (("STRUCTURAL", "KEYSTONE STRUCTURAL (PRACTICE)"),
                           ("CIVIL", "MEADOWLINE CIVIL (PRACTICE)"),
                           ("MEP", "NOT INCLUDED IN THIS SET")):
            self.text((x, y), role, size=TXT["tiny"], font=FONT_B, valign="top")
            self.text((x + 0.75, y), firm, size=TXT["tiny"], valign="top")
            y -= 0.12
        y -= 0.06
        self.line((tbx, y), (tbx + TB_W, y), lw="thin")

        # project block
        y -= 0.12
        self.text((x, y), "PROJECT", size=TXT["tiny"], font=FONT_B, valign="top")
        y -= 0.16
        self.text((x, y), PROJECT["name1"], size=TXT["label"] * 1.08, font=FONT_B, valign="top")
        y -= 0.17
        self.text((x, y), PROJECT["name2"], size=TXT["label"], font=FONT_B, valign="top")
        y -= 0.15
        self.text((x, y), PROJECT["address"], size=TXT["tiny"], valign="top")
        y -= 0.17
        self.text((x, y), "OWNER", size=TXT["tiny"], font=FONT_B, valign="top")
        y -= 0.12
        self.text((x, y), PROJECT["owner"], size=TXT["tiny"] * 1.05, valign="top")
        y -= 0.2
        self.line((tbx, y), (tbx + TB_W, y), lw="thin")

        # key plan
        y -= 0.1
        self.text((x, y), "KEY PLAN", size=TXT["tiny"], font=FONT_B, valign="top")
        kp_h = 0.85
        self._key_plan(x + 0.15, y - 0.15 - kp_h, W - 0.3, kp_h)
        y -= kp_h + 0.3
        self.line((tbx, y), (tbx + TB_W, y), lw="thin")

        # issue / revisions table
        y -= 0.1
        self.text((x, y), "ISSUES / REVISIONS", size=TXT["tiny"], font=FONT_B, valign="top")
        y -= 0.14
        cols = [(0.3, "NO."), (1.65, "DESCRIPTION"), (0.9, "DATE")]
        cx = x
        for wcol, h in cols:
            self.text((cx, y), h, size=TXT["tiny"], font=FONT_B, valign="top")
            cx += wcol
        rows = [("-", "ISSUED FOR BID", "09/15/2026")]
        for i in range(5):
            y -= 0.14
            self.line((x, y), (x + W, y), lw="hair")
            if i < len(rows):
                cx = x
                for (wcol, _), val in zip(cols, rows[i]):
                    self.text((cx, y - 0.02), val, size=TXT["tiny"], valign="top")
                    cx += wcol
        y -= 0.2
        self.line((tbx, y), (tbx + TB_W, y), lw="thin")

        # seal placeholder
        y -= 0.1
        sh = 1.05
        self.rect(x + 0.4, y - sh, W - 0.8, sh, lw="fine", dash="dashed")
        self.mtext((x + W / 2, y - sh / 2), ["NO PROFESSIONAL SEAL", "PRACTICE DOCUMENT ONLY",
                                             "DO NOT USE FOR CONSTRUCTION"],
                   size=TXT["tiny"], anchor="c", valign="mid", color="g50")
        y -= sh + 0.15
        self.line((tbx, y), (tbx + TB_W, y), lw="thin")

        # project data rows
        y -= 0.06
        data = [("PROJECT NO.", PROJECT["number"]), ("ISSUE", PROJECT["issue"]),
                ("DATE", PROJECT["date"]), ("DRAWN BY", "PLS"), ("CHECKED BY", "PLS")]
        for k, val in data:
            self.text((x, y), k, size=TXT["tiny"], font=FONT_B, valign="top")
            self.text((x + 0.9, y), val, size=TXT["tiny"], valign="top")
            y -= 0.13
        y -= 0.05
        self.line((tbx, y), (tbx + TB_W, y), lw="thin")

        # sheet title + number block (bottom)
        bot = MARGIN_B
        num_h = 1.05
        self.line((tbx, bot + num_h), (tbx + TB_W, bot + num_h), lw="heavy")
        self.text((x, bot + num_h - 0.1), "SHEET NUMBER", size=TXT["tiny"], font=FONT_B,
                  valign="top")
        self.text((tbx + TB_W / 2, bot + 0.32), self.number, size=40, font=FONT_B, anchor="c",
                  valign="base")
        if self.total:
            self.text((tbx + TB_W - 0.1, bot + 0.1), f"{self.index} OF {self.total}",
                      size=TXT["tiny"], anchor="r", valign="base")
        # title area between data rows and number
        title_top = y - 0.08
        self.text((x, title_top), "SHEET TITLE", size=TXT["tiny"], font=FONT_B, valign="top")
        lines = self.title.split("\n")
        avail = title_top - 0.15 - (bot + num_h)
        sz = 12.5 if len(lines) <= 2 else 11
        self.mtext((tbx + TB_W / 2, bot + num_h + avail / 2), lines, size=sz, font=FONT_B,
                   anchor="c", valign="mid", leading=sz * 1.2, width=W)

    def _key_plan(self, x, y, w, h):
        # tiny diagram of the existing school + addition (shaded)
        # model extents: existing x -320..-36, y -60..120; addition 0..150, 0..72
        mx0, mx1, my0, my1 = -330, 160, -70, 130
        s = min(w / (mx1 - mx0), h / (my1 - my0))
        ox = x + (w - (mx1 - mx0) * s) / 2
        oy = y + (h - (my1 - my0) * s) / 2

        def P(px, py):
            return (ox + (px - mx0) * s, oy + (py - my0) * s)

        def R(x0, y0, x1, y1, **kw):
            a = P(x0, y0)
            b = P(x1, y1)
            self.rect(a[0], a[1], b[0] - a[0], b[1] - a[1], **kw)

        R(-320, -60, -36, 120, lw="fine", fill="g05")
        self.text(P(-178, 30), "EXISTING SCHOOL", size=TXT["tiny"] * 0.9, anchor="c", valign="mid",
                  color="g50")
        R(-36, 30, 0, 42, lw="fine", fill="g40")
        R(0, 0, 150, 72, lw="thin", fill="g40")
        self.text(P(75, 36), "ADDITION", size=TXT["tiny"] * 0.9, font=FONT_B, anchor="c",
                  valign="mid", color="white")
        north_arrow(self, x + w - 0.08, y + h - 0.2, size=0.22)
