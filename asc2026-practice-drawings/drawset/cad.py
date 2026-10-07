"""
Core 2D drafting toolkit on top of reportlab.

Conventions
-----------
* Paper space units are INCHES measured from the lower-left corner of the sheet.
* Model space units are FEET. A View maps model feet -> paper inches with a drawing scale
  expressed as paper inches per model foot (1/8" = 1'-0"  ->  scale = 1/8).
* Text sizes are given in POINTS on paper (6.75 pt = 3/32").
* Line weights are given by name (see LW) or as a float in points.

Typical use
-----------
    v = sheet.view(ox=2.0, oy=3.0, scale=1/8, mx=0, my=0)   # model (0,0) at paper (2", 3")
    v.line((0, 0), (30, 0), lw="heavy")
    v.dim((0, 0), (30, 0), offset=-4)                          # dimension 4' below
    v.text((15, 15), "CLASSROOM", size=TXT["label"], anchor="c")
"""
from __future__ import annotations

import math
import random
from fractions import Fraction
from typing import Iterable, Sequence

from reportlab.lib.colors import Color, black, white
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

try:  # shapely is used for wall unions and hatching of complex shapes
    from shapely.geometry import (GeometryCollection, LineString, MultiPolygon,
                                  Point, Polygon, box)
    from shapely.ops import unary_union
except Exception:  # pragma: no cover
    Polygon = None

PT = 72.0  # points per inch

# ----------------------------------------------------------------------------------------
# Pens / text
# ----------------------------------------------------------------------------------------
LW = {
    "hair": 0.2,
    "xfine": 0.3,
    "fine": 0.4,
    "thin": 0.55,
    "med": 0.8,
    "heavy": 1.15,
    "xheavy": 1.6,
    "cut": 1.6,
    "border": 2.2,
}

TXT = {
    "tiny": 4.5,
    "small": 5.6,
    "note": 6.75,     # 3/32"
    "label": 8.0,
    "room": 9.0,      # 1/8"
    "sub": 10.5,
    "title": 13.5,    # 3/16"
    "big": 18.0,      # 1/4"
    "huge": 28.0,
}

FONT = "Helvetica"
FONT_B = "Helvetica-Bold"
FONT_I = "Helvetica-Oblique"
FONT_BI = "Helvetica-BoldOblique"

GRAY = {k: Color(v, v, v) for k, v in {
    "g05": 0.95, "g10": 0.90, "g15": 0.85, "g20": 0.80, "g30": 0.70, "g40": 0.60,
    "g50": 0.50, "g60": 0.40, "g70": 0.30, "g80": 0.20}.items()}
SCREEN = Color(0.55, 0.55, 0.55)  # used for existing / background linework
RED = Color(0.78, 0.1, 0.1)


def lw(w) -> float:
    if w is None:
        return 0.0
    return LW[w] if isinstance(w, str) else float(w)


def color(c):
    if c is None:
        return None
    if isinstance(c, str):
        if c in GRAY:
            return GRAY[c]
        return {"black": black, "white": white, "screen": SCREEN, "red": RED}[c]
    if isinstance(c, (int, float)):
        return Color(c, c, c)
    return c


DASHES = {
    "hidden": [3, 2],
    "dashed": [4, 2.5],
    "center": [12, 2, 2, 2],
    "phantom": [12, 2, 2, 2, 2, 2],
    "dot": [0.6, 1.6],
    "long": [8, 3],
    "demo": [3, 1.6],
    "grid": [14, 3, 2.5, 3],
    "property": [16, 3, 3, 3, 3, 3],
}

# ----------------------------------------------------------------------------------------
# Number formatting
# ----------------------------------------------------------------------------------------

def ftin(feet: float = 0, inches: float = 0) -> float:
    """Build a length in feet from feet + inches (inches may be fractional)."""
    return feet + inches / 12.0


def fmt_ftin(feet: float, denom: int = 16, zero_inch: bool = True) -> str:
    """Format feet as architectural feet-inches:  12.375 -> 12'-4 1/2"."""
    neg = feet < 0
    total_in = abs(feet) * 12.0
    whole_in = math.floor(total_in + 1e-9)
    frac = Fraction(round((total_in - whole_in) * denom), denom)
    if frac >= 1:
        whole_in += 1
        frac = Fraction(0)
    ft = int(whole_in // 12)
    inch = int(whole_in % 12)
    s_in = str(inch)
    if frac:
        s_in = (f"{inch} " if inch else "") + f"{frac.numerator}/{frac.denominator}"
    if ft == 0 and not zero_inch:
        out = f'{s_in}"'
    else:
        out = f"{ft}'-{s_in}\""
    return ("-" if neg else "") + out


def fmt_in(inches: float, denom: int = 16) -> str:
    """Format a length given in inches:  7.625 -> 7 5/8"."""
    whole = math.floor(inches + 1e-9)
    frac = Fraction(round((inches - whole) * denom), denom)
    if frac >= 1:
        whole += 1
        frac = Fraction(0)
    if frac and whole:
        return f'{whole} {frac.numerator}/{frac.denominator}"'
    if frac:
        return f'{frac.numerator}/{frac.denominator}"'
    return f'{whole}"'


def fmt_elev(feet: float) -> str:
    """Architectural elevation:  114.0 -> 114'-0"."""
    return fmt_ftin(feet, 16)


def scale_label(scale: float) -> str:
    """Return the conventional scale label for a scale given in paper-inches per foot."""
    table = {
        1 / 16: '1/16" = 1\'-0"', 3 / 32: '3/32" = 1\'-0"', 1 / 8: '1/8" = 1\'-0"',
        3 / 16: '3/16" = 1\'-0"', 1 / 4: '1/4" = 1\'-0"', 3 / 8: '3/8" = 1\'-0"',
        1 / 2: '1/2" = 1\'-0"', 3 / 4: '3/4" = 1\'-0"', 1.0: '1" = 1\'-0"',
        1.5: '1 1/2" = 1\'-0"', 3.0: '3" = 1\'-0"', 6.0: '6" = 1\'-0"', 12.0: "FULL SIZE",
        1 / 10: '1" = 10\'', 1 / 20: '1" = 20\'', 1 / 30: '1" = 30\'', 1 / 40: '1" = 40\'',
        1 / 50: '1" = 50\'', 1 / 60: '1" = 60\'', 1 / 100: '1" = 100\'', 1 / 200: '1" = 200\'',
    }
    for k, v in table.items():
        if abs(k - scale) < 1e-9:
            return v
    return f"1\" = {1 / scale:.0f}'"


# ----------------------------------------------------------------------------------------
# Low level geometry helpers
# ----------------------------------------------------------------------------------------

def vsub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def vadd(a, b):
    return (a[0] + b[0], a[1] + b[1])


def vmul(a, k):
    return (a[0] * k, a[1] * k)


def vlen(a):
    return math.hypot(a[0], a[1])


def vnorm(a):
    L = vlen(a)
    return (a[0] / L, a[1] / L) if L else (0.0, 0.0)


def vperp(a):  # left normal
    return (-a[1], a[0])


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def rect_pts(x, y, w, h):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


# ----------------------------------------------------------------------------------------
# Paper: drawing directly in paper inches
# ----------------------------------------------------------------------------------------
class Paper:
    """Drawing primitives in paper inches. A View subclasses this with a transform."""

    def __init__(self, c: Canvas):
        self.c = c

    # -- transform hooks (identity for paper) --
    def P(self, p):
        """model/paper point -> canvas points"""
        return (p[0] * PT, p[1] * PT)

    def L(self, d):
        """length in local units -> canvas points"""
        return d * PT

    # -- state helpers --
    def _stroke(self, w="thin", dash=None, col="black", cap=0, join=0):
        c = self.c
        c.setLineWidth(lw(w))
        c.setStrokeColor(color(col))
        c.setLineCap(cap)
        c.setLineJoin(join)
        if dash is None:
            c.setDash([])
        else:
            c.setDash(DASHES[dash] if isinstance(dash, str) else dash)

    # -- primitives --
    def line(self, p1, p2, lw="thin", dash=None, color="black", cap=0):
        self._stroke(lw, dash, color, cap)
        a, b = self.P(p1), self.P(p2)
        self.c.line(a[0], a[1], b[0], b[1])

    def polyline(self, pts, lw="thin", dash=None, color="black", closed=False, fill=None, join=0):
        pts = list(pts)
        if len(pts) < 2:
            return
        self._stroke(lw, dash, color, join=join)
        path = self.c.beginPath()
        q = self.P(pts[0])
        path.moveTo(*q)
        for p in pts[1:]:
            q = self.P(p)
            path.lineTo(*q)
        if closed:
            path.close()
        if fill is not None:
            self.c.setFillColor(color_fill(fill))
        self.c.drawPath(path, stroke=1 if lw is not None and lw != 0 else 0,
                        fill=1 if fill is not None else 0)

    def polygon(self, pts, lw="thin", dash=None, color="black", fill=None, hatch=None,
                hatch_kw=None, stroke=True, join=0):
        """Closed polygon. fill = gray name/float/Color. hatch = pattern name (see hatch())."""
        pts = list(pts)
        if fill is not None:
            self._fill_path([pts], fill)
        if hatch:
            self.hatch([pts], hatch, **(hatch_kw or {}))
        if stroke and lw:
            self.polyline(pts, lw=lw, dash=dash, color=color, closed=True, join=join)

    def rect(self, x, y, w, h, **kw):
        self.polygon(rect_pts(x, y, w, h), **kw)

    def circle(self, c, r, lw="thin", color="black", fill=None, dash=None):
        self._stroke(lw, dash, color)
        q = self.P(c)
        if fill is not None:
            self.c.setFillColor(color_fill(fill))
        self.c.circle(q[0], q[1], self.L(r), stroke=1 if lw else 0, fill=1 if fill is not None else 0)

    def arc(self, c, r, a0, a1, lw="thin", color="black", dash=None):
        """Arc centered at c, radius r, from angle a0 to a1 (degrees, CCW)."""
        self._stroke(lw, dash, color)
        q = self.P(c)
        R = self.L(r)
        ext = a1 - a0
        self.c.arc(q[0] - R, q[1] - R, q[0] + R, q[1] + R, startAng=a0, extent=ext)

    def _fill_path(self, rings, fill, even_odd=True):
        c = self.c
        path = c.beginPath()
        for ring in rings:
            ring = list(ring)
            if len(ring) < 3:
                continue
            q = self.P(ring[0])
            path.moveTo(*q)
            for p in ring[1:]:
                q = self.P(p)
                path.lineTo(*q)
            path.close()
        c.setFillColor(color_fill(fill))
        c.drawPath(path, stroke=0, fill=1, fillMode=1 if even_odd else 0)

    def _clip_rings(self, rings):
        c = self.c
        path = c.beginPath()
        for ring in rings:
            ring = list(ring)
            if len(ring) < 3:
                continue
            q = self.P(ring[0])
            path.moveTo(*q)
            for p in ring[1:]:
                q = self.P(p)
                path.lineTo(*q)
            path.close()
        c.clipPath(path, stroke=0, fill=0, fillMode=1)

    # -- hatching --
    def hatch(self, rings, pattern="ansi31", spacing=None, angle=None, w="hair",
              col="black", scale=1.0, seed=1):
        """Hatch the area bounded by one or more rings (even-odd, so inner rings are holes).

        rings   : list of point lists (local units, e.g. model feet for a View)
        pattern : 'ansi31' (45 deg lines, masonry/CMU), 'ansi32' (steel), 'ansi37' (cross hatch),
                  'brick' (dense 45 deg), 'concrete', 'earth', 'gravel', 'sand', 'insul' (rigid X),
                  'dots', 'horiz', 'vert', 'grid' (square grid, spacing = cell size), 'plank',
                  'carpet', 'tile' (rect grid), 'wood' (end grain), 'solid' (fill with col)
        spacing : paper inches between hatch lines (defaults per pattern)
        angle   : degrees (defaults per pattern)
        scale   : multiplies default spacing (paper based)
        For 'grid'/'tile'/'plank' the spacing is in LOCAL units (feet) so it is true to scale;
        pass spacing=(sx, sy) for rectangular tiles.
        """
        c = self.c
        if not rings:
            return
        allp = [self.P(p) for ring in rings for p in ring]
        if not allp:
            return
        xs = [p[0] for p in allp]
        ys = [p[1] for p in allp]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        if x1 - x0 < 0.01 or y1 - y0 < 0.01:
            return
        c.saveState()
        self._clip_rings(rings)
        c.setLineWidth(lw(w))
        c.setStrokeColor(color(col))
        c.setFillColor(color(col))
        c.setDash([])
        c.setLineCap(0)
        rnd = random.Random(seed)

        def lines_at(ang_deg, sp_pt, offset=0.0, dash=None):
            if dash:
                c.setDash(dash)
            a = math.radians(ang_deg)
            d = (math.cos(a), math.sin(a))
            n = (-d[1], d[0])
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            R = math.hypot(x1 - x0, y1 - y0) / 2 + sp_pt
            k = int(R / sp_pt) + 1
            for i in range(-k, k + 1):
                o = i * sp_pt + offset
                px, py = cx + n[0] * o, cy + n[1] * o
                c.line(px - d[0] * R, py - d[1] * R, px + d[0] * R, py + d[1] * R)
            if dash:
                c.setDash([])

        P = pattern
        if P == "solid":
            c.setFillColor(color_fill(col))
            c.rect(x0 - 1, y0 - 1, x1 - x0 + 2, y1 - y0 + 2, stroke=0, fill=1)
        elif P in ("ansi31", "brick", "ansi32", "ansi37", "horiz", "vert", "diag"):
            sp = (spacing or {"ansi31": 0.0625, "brick": 0.035, "ansi32": 0.0625,
                              "ansi37": 0.0625, "horiz": 0.0625, "vert": 0.0625,
                              "diag": 0.0625}[P]) * scale * PT
            ang = angle if angle is not None else {"horiz": 0, "vert": 90}.get(P, 45)
            lines_at(ang, sp)
            if P == "ansi37":
                lines_at(ang + 90, sp)
            if P == "ansi32":
                lines_at(ang, sp, offset=sp * 0.25)
        elif P == "insul":
            sp = (spacing or 0.05) * scale * PT
            lines_at(45, sp)
            lines_at(-45, sp)
        elif P in ("concrete", "sand", "dots", "gravel", "earth", "carpet"):
            area = (x1 - x0) * (y1 - y0)
            dens = {"concrete": 1 / 14.0, "sand": 1 / 6.0, "dots": 1 / 30.0,
                    "gravel": 1 / 40.0, "earth": 1 / 60.0, "carpet": 1 / 9.0}[P] / (scale * scale)
            n = int(min(area * dens, 25000))
            if P == "concrete":
                for _ in range(n):
                    x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
                    c.circle(x, y, 0.25, stroke=0, fill=1)
                for _ in range(max(1, n // 9)):
                    x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
                    s = rnd.uniform(1.4, 2.6) * scale
                    a = rnd.uniform(0, 2 * math.pi)
                    path = c.beginPath()
                    for j in range(3):
                        aa = a + j * 2 * math.pi / 3
                        px, py = x + s * math.cos(aa), y + s * math.sin(aa)
                        if j == 0:
                            path.moveTo(px, py)
                        else:
                            path.lineTo(px, py)
                    path.close()
                    c.drawPath(path, stroke=1, fill=0)
            elif P in ("sand", "dots", "carpet"):
                r = {"sand": 0.22, "dots": 0.35, "carpet": 0.18}[P]
                for _ in range(n):
                    c.circle(rnd.uniform(x0, x1), rnd.uniform(y0, y1), r, stroke=0, fill=1)
            elif P == "gravel":
                for _ in range(n):
                    rr = rnd.uniform(0.6, 1.5) * scale
                    c.circle(rnd.uniform(x0, x1), rnd.uniform(y0, y1), rr, stroke=1, fill=0)
            elif P == "earth":
                sp = (spacing or 0.12) * scale * PT
                yy = y0
                row = 0
                while yy < y1 + sp:
                    xx = x0 - (row % 2) * sp
                    while xx < x1 + sp:
                        for j in range(3):
                            o = j * sp * 0.18
                            c.line(xx + o, yy, xx + o + sp * 0.45, yy + sp * 0.45)
                        xx += sp
                    yy += sp * 0.6
                    row += 1
        elif P in ("grid", "tile", "plank"):
            # true-to-scale tile grids. spacing in local units (feet)
            if isinstance(spacing, (tuple, list)):
                sx, sy = spacing
            else:
                sx = sy = spacing or 1.0
            sx_pt, sy_pt = self.L(sx), self.L(sy)
            ang = angle or 0
            if ang == 0:
                ox, oy = self.P((0, 0))
                i0 = math.floor((x0 - ox) / sx_pt)
                i1 = math.ceil((x1 - ox) / sx_pt)
                j0 = math.floor((y0 - oy) / sy_pt)
                j1 = math.ceil((y1 - oy) / sy_pt)
                for j in range(j0, j1 + 1):
                    y = oy + j * sy_pt
                    c.line(x0, y, x1, y)
                if P == "plank":
                    for j in range(j0, j1 + 1):
                        shift = (j % 3) * sx_pt / 3.0
                        for i in range(i0 - 1, i1 + 1):
                            x = ox + i * sx_pt + shift
                            c.line(x, oy + j * sy_pt, x, oy + (j + 1) * sy_pt)
                else:
                    for i in range(i0, i1 + 1):
                        x = ox + i * sx_pt
                        c.line(x, y0, x, y1)
            else:
                lines_at(ang, sy_pt)
                lines_at(ang + 90, sx_pt)
        elif P == "wood":
            # blocking / end grain: box X
            c.line(x0, y0, x1, y1)
            c.line(x0, y1, x1, y0)
        elif P == "steel":
            c.setFillColor(color_fill(col))
            c.rect(x0 - 1, y0 - 1, x1 - x0 + 2, y1 - y0 + 2, stroke=0, fill=1)
        c.restoreState()

    # -- text --
    def text(self, p, s, size=TXT["note"], font=FONT, anchor="l", valign="base", rot=0.0,
             color="black", underline=False):
        """Single-line text. anchor: l/c/r; valign: base/mid/top/bot."""
        c = self.c
        q = self.P(p)
        c.saveState()
        c.translate(q[0], q[1])
        if rot:
            c.rotate(rot)
        c.setFont(font, size)
        c.setFillColor(color_fill(color))
        w = stringWidth(s, font, size)
        dx = {"l": 0, "c": -w / 2, "r": -w}[anchor]
        dy = {"base": 0, "mid": -size * 0.35, "top": -size * 0.72, "bot": size * 0.0}[valign]
        c.drawString(dx, dy, s)
        if underline:
            c.setLineWidth(max(0.4, size * 0.06))
            c.setStrokeColor(color_fill(color))
            c.line(dx, dy - size * 0.18, dx + w, dy - size * 0.18)
        c.restoreState()
        return w / PT  # width in inches

    def mtext(self, p, lines, size=TXT["note"], font=FONT, leading=None, anchor="l",
              valign="top", rot=0.0, color="black", width=None):
        """Multi-line text block. `lines` is a list or a string ('\n' separated).
        If `width` (paper inches) is given, long lines are word-wrapped.
        Returns the block height in paper inches."""
        if isinstance(lines, str):
            lines = lines.split("\n")
        if width:
            lines = wrap_lines(lines, size, font, width)
        lead = leading or size * 1.3
        c = self.c
        q = self.P(p)
        c.saveState()
        c.translate(q[0], q[1])
        if rot:
            c.rotate(rot)
        c.setFillColor(color_fill(color))
        n = len(lines)
        if valign == "top":
            y = -size * 0.75
        elif valign == "mid":
            y = (n - 1) * lead / 2 - size * 0.35
        else:  # bottom
            y = (n - 1) * lead
        for ln in lines:
            f = font
            if ln.startswith("**") and ln.endswith("**"):
                ln = ln[2:-2]
                f = FONT_B
            c.setFont(f, size)
            w = stringWidth(ln, f, size)
            dx = {"l": 0, "c": -w / 2, "r": -w}[anchor]
            c.drawString(dx, y, ln)
            y -= lead
        c.restoreState()
        return n * lead / PT

    def text_width(self, s, size=TXT["note"], font=FONT):
        return stringWidth(s, font, size) / PT


def color_fill(c):
    return color(c)


def wrap_lines(lines, size, font, width_in):
    out = []
    maxw = width_in * PT
    for ln in lines:
        bold = ln.startswith("**") and ln.endswith("**")
        core = ln[2:-2] if bold else ln
        f = FONT_B if bold else font
        if stringWidth(core, f, size) <= maxw:
            out.append(ln)
            continue
        # keep hanging indent for numbered notes  "12. text"
        indent = ""
        m = 0
        while m < len(core) and core[m] == " ":
            m += 1
        words = core.split(" ")
        cur = ""
        first = True
        lead_tok = words[0] if words else ""
        if lead_tok.rstrip(".").isdigit() or (len(lead_tok) <= 3 and lead_tok.endswith(".")):
            indent = " " * (len(lead_tok) + 2)
        for wd in words:
            trial = (cur + " " + wd) if cur else wd
            if stringWidth(trial, f, size) <= maxw or not cur:
                cur = trial
            else:
                out.append(("**" + cur + "**") if bold else cur)
                cur = indent + wd
                first = False
        if cur:
            out.append(("**" + cur + "**") if bold else cur)
    return out


# ----------------------------------------------------------------------------------------
# View: model-space window on a sheet
# ----------------------------------------------------------------------------------------
class View(Paper):
    """Model-space view. Model point (mx, my) lands at paper point (ox, oy) inches.

    scale = paper inches per model foot (1/8 for 1/8"=1'-0", 1/30 for 1"=30').
    rot   = optional rotation of the model in degrees (CCW) about (mx, my).
    """

    def __init__(self, c: Canvas, ox, oy, scale, mx=0.0, my=0.0, rot=0.0):
        super().__init__(c)
        self.ox, self.oy, self.s, self.mx, self.my = ox, oy, scale, mx, my
        self.rot = math.radians(rot)
        self._cr, self._sr = math.cos(self.rot), math.sin(self.rot)

    def P(self, p):
        x, y = p[0] - self.mx, p[1] - self.my
        if self.rot:
            x, y = x * self._cr - y * self._sr, x * self._sr + y * self._cr
        return ((self.ox + x * self.s) * PT, (self.oy + y * self.s) * PT)

    def to_paper(self, p):
        q = self.P(p)
        return (q[0] / PT, q[1] / PT)

    def L(self, d):
        return d * self.s * PT

    def paper_len(self, inches):
        """paper inches -> model feet at this view's scale"""
        return inches / self.s

    # -- shapely geometry drawing --
    def geom(self, g, lw="thin", color="black", fill=None, hatch=None, hatch_kw=None,
             dash=None, stroke=True):
        """Draw a shapely Polygon/MultiPolygon/LineString (model coords)."""
        if g is None or g.is_empty:
            return
        if isinstance(g, (MultiPolygon, GeometryCollection)):
            for sub in g.geoms:
                self.geom(sub, lw, color, fill, hatch, hatch_kw, dash, stroke)
            return
        if isinstance(g, Polygon):
            rings = [list(g.exterior.coords)] + [list(r.coords) for r in g.interiors]
            if fill is not None:
                self._fill_path(rings, fill)
            if hatch:
                self.hatch(rings, hatch, **(hatch_kw or {}))
            if stroke and lw:
                for r in rings:
                    self.polyline(r, lw=lw, color=color, dash=dash, closed=True)
            return
        if isinstance(g, LineString):
            self.polyline(list(g.coords), lw=lw, color=color, dash=dash)
            return
        if hasattr(g, "geoms"):
            for sub in g.geoms:
                self.geom(sub, lw, color, fill, hatch, hatch_kw, dash, stroke)

    # -- dimensions --
    def dim(self, p1, p2, offset=0.0, text=None, size=TXT["small"], ext=True, tick="arch",
            lw_="fine", denom=8, text_offset=None, gap=None, ext_beyond=None, flip_text=False,
            prefix="", suffix=""):
        """Aligned dimension between p1 and p2. offset (model ft) measured along the LEFT normal
        of p1->p2. Text defaults to the measured length in ft-in."""
        d = vsub(p2, p1)
        L = vlen(d)
        if L < 1e-6:
            return
        u = vnorm(d)
        n = vperp(u)
        a = vadd(p1, vmul(n, offset))
        b = vadd(p2, vmul(n, offset))
        sgn = 1 if offset >= 0 else -1
        gp = gap if gap is not None else self.paper_len(0.04)
        eb = ext_beyond if ext_beyond is not None else self.paper_len(0.06)
        if ext and abs(offset) > gp:
            for p, q in ((p1, a), (p2, b)):
                e0 = vadd(p, vmul(n, sgn * gp))
                e1 = vadd(q, vmul(n, sgn * eb))
                self.line(e0, e1, lw="hair")
        # dimension line (extends slightly past ticks)
        ov = self.paper_len(0.05)
        self.line(vadd(a, vmul(u, -ov)), vadd(b, vmul(u, ov)), lw=lw_)
        tk = self.paper_len(0.05)
        for q in (a, b):
            if tick == "arch":
                t = vnorm(vadd(u, n))
                self.line(vadd(q, vmul(t, -tk)), vadd(q, vmul(t, tk)), lw="med")
            elif tick == "dot":
                self.circle(q, self.paper_len(0.016), lw=None, fill="black")
            elif tick == "arrow":
                self._arrowhead(q, u if q is a else vmul(u, -1))
        s = text if text is not None else fmt_ftin(L, denom)
        s = prefix + s + suffix
        ang = math.degrees(math.atan2(u[1], u[0]))
        if self.rot:
            ang += math.degrees(self.rot)
        if ang > 90.01 or ang < -89.99:
            ang -= 180
        mid = lerp(a, b, 0.5)
        to = text_offset if text_offset is not None else self.paper_len(0.035)
        tsign = 1
        # place text on the outward side of the dim line consistently (above for horizontal)
        nn = n if (ang == math.degrees(math.atan2(u[1], u[0]))) else vmul(n, -1)
        if flip_text:
            nn = vmul(nn, -1)
        tp = vadd(mid, vmul(nn, to * tsign))
        # if text wider than the dimension, push it outside to the right
        tw = self.paper_len(stringWidth(s, FONT, size) / PT)
        if tw > L * 0.92 and not flip_text:
            tp = vadd(b, vmul(u, tw / 2 + self.paper_len(0.06)))
            tp = vadd(tp, vmul(nn, to))
        elif flip_text:
            tp = vadd(mid, vmul(nn, to + self.paper_len(0.075)))
        self.text(tp, s, size=size, anchor="c", valign="bot", rot=ang)

    def dim_chain(self, pts, offset, **kw):
        """Continuous chain of dimensions through successive points (all on one line).
        Text of segments too short for their label alternates to the far side of the line."""
        size = kw.get("size", TXT["small"])
        denom = kw.get("denom", 8)
        flip = False
        for a, b in zip(pts[:-1], pts[1:]):
            L = vlen(vsub(b, a))
            if L <= 1e-6:
                continue
            tw = self.paper_len(stringWidth(kw.get("text") or fmt_ftin(L, denom), FONT, size) / PT)
            if tw > L * 0.92:
                flip = not flip
                kk = dict(kw)
                kk["flip_text"] = flip
                kk["text_offset"] = self.paper_len(0.035) if flip else None
                self.dim(a, b, offset, **kk)
            else:
                flip = False
                self.dim(a, b, offset, **kw)

    def _arrowhead(self, tip, direction, size_in=0.07, filled=True):
        u = vnorm(direction)
        n = vperp(u)
        L = self.paper_len(size_in)
        W = L * 0.32
        base = vsub(tip, vmul(u, L))
        pts = [tip, vadd(base, vmul(n, W)), vsub(base, vmul(n, W))]
        self.polygon(pts, lw="fine", fill="black" if filled else None)

    def leader(self, pts, text=None, size=TXT["note"], arrow="arrow", text_side=None, lines=None,
               font=FONT, width=None):
        """Leader polyline: pts[0] is the arrow end, pts[-1] is where the text goes.
        Text is placed to the left/right of the last point depending on direction."""
        self.polyline(pts, lw="fine")
        if arrow == "arrow":
            self._arrowhead(pts[0], vsub(pts[0], pts[1]))
        elif arrow == "dot":
            self.circle(pts[0], self.paper_len(0.02), lw=None, fill="black")
        if text is None and lines is None:
            return
        last, prev = pts[-1], pts[-2]
        side = text_side or ("r" if last[0] >= prev[0] else "l")
        pad = self.paper_len(0.04)
        tp = (last[0] + pad, last[1]) if side == "r" else (last[0] - pad, last[1])
        content = lines if lines is not None else text
        if isinstance(content, str) and "\n" not in content and width is None:
            self.text(tp, content, size=size, anchor="l" if side == "r" else "r", valign="mid",
                      font=font)
        else:
            self.mtext(tp, content, size=size, anchor="l" if side == "r" else "r", valign="mid",
                       font=font, width=width)


# ----------------------------------------------------------------------------------------
# Symbols (drawn through a View so they sit at model points, but sized in paper inches)
# ----------------------------------------------------------------------------------------

def grid_bubble(v: View, center, label, dia=0.42, size=None):
    r = v.paper_len(dia / 2)
    v.circle(center, r, lw="thin", fill="white")
    v.text(center, str(label), size=size or TXT["sub"], font=FONT_B, anchor="c", valign="mid")


def grid_line(v: View, p_start, p_end, label, bubble_at=("start", "end"), dia=0.42, ext=0.0):
    """Draws a grid line with bubbles beyond the ends. ext = extra model length past ends."""
    u = vnorm(vsub(p_end, p_start))
    r = v.paper_len(dia / 2)
    a = vsub(p_start, vmul(u, ext))
    b = vadd(p_end, vmul(u, ext))
    v.line(a, b, lw="fine", dash="grid")
    if "start" in bubble_at:
        grid_bubble(v, vsub(a, vmul(u, r)), label, dia)
    if "end" in bubble_at:
        grid_bubble(v, vadd(b, vmul(u, r)), label, dia)


def room_tag(v: View, at, name, number, size=TXT["room"], area=None, box=True, lines2=None):
    """Room name (one or two lines) over a boxed room number."""
    names = name.split("\n") if isinstance(name, str) else list(name)
    lead = size * 1.15 / PT
    y = at[1]
    k = len(names)
    top = v.to_paper(at)
    # paper-space drawing for legibility
    p = Paper(v.c)
    px, py = top
    for i, nm in enumerate(names):
        p.text((px, py + (k - i) * lead - lead * 0.25), nm, size=size, font=FONT_B, anchor="c",
               valign="base")
    if number:
        w = p.text_width(number, size * 0.95, FONT) + 0.10
        h = size * 1.25 / PT
        p.rect(px - w / 2, py - h + 0.02, w, h, lw="fine", fill="white")
        p.text((px, py - h / 2 + 0.02), number, size=size * 0.95, anchor="c", valign="mid")
    if area:
        p.text((px, py - size * 1.7 / PT), area, size=size * 0.75, anchor="c", valign="top")


def door_tag(v: View, at, text, size=TXT["small"]):
    p = Paper(v.c)
    x, y = v.to_paper(at)
    w = max(0.26, p.text_width(text, size) + 0.07)
    h = 0.13
    p.rect(x - w / 2, y - h / 2, w, h, lw="fine", fill="white")
    p.text((x, y), text, size=size, anchor="c", valign="mid")


def window_tag(v: View, at, text, size=TXT["small"], r=0.11):
    p = Paper(v.c)
    x, y = v.to_paper(at)
    rr = max(r, (p.text_width(text, size) + 0.06) / 1.7)
    pts = [(x + rr * math.cos(math.radians(a)), y + rr * math.sin(math.radians(a)))
           for a in range(0, 360, 60)]
    p.polygon(pts, lw="fine", fill="white")
    p.text((x, y), text, size=size, anchor="c", valign="mid")


def wall_tag(v: View, at, text, size=TXT["small"]):
    p = Paper(v.c)
    x, y = v.to_paper(at)
    w = max(0.15, (p.text_width(text, size) + 0.06) / 2 + 0.03)
    h = 0.09
    pts = [(x - w, y), (x - w + h, y + h), (x + w - h, y + h), (x + w, y), (x + w - h, y - h),
           (x - w + h, y - h)]
    p.polygon(pts, lw="fine", fill="white")
    p.text((x, y), text, size=size, anchor="c", valign="mid")


def keynote_tag(v: View, at, n, size=TXT["small"], leader_to=None):
    p = Paper(v.c)
    x, y = v.to_paper(at)
    if leader_to is not None:
        v.leader([leader_to, at], arrow="arrow")
    d = 0.09
    p.polygon([(x, y + d * 1.3), (x + d * 1.3, y), (x, y - d * 1.3), (x - d * 1.3, y)], lw="fine",
              fill="white")
    p.text((x, y), str(n), size=size * 0.92, anchor="c", valign="mid")


def section_mark(v: View, p1, p2, num, sheet, look="left", r=0.17, tail=True):
    """Section cut line p1->p2 with bubbles at both ends. `look` = 'left'/'right' of p1->p2."""
    u = vnorm(vsub(p2, p1))
    n = vperp(u) if look == "left" else vmul(vperp(u), -1)
    v.line(p1, p2, lw="med", dash="phantom")
    for q in (p1, p2):
        _section_bubble(v, q, n, num, sheet, r)


def _section_bubble(v: View, q, n, num, sheet, r=0.17):
    p = Paper(v.c)
    x, y = v.to_paper(q)
    # direction in paper space
    qq = v.to_paper(vadd(q, n))
    nd = vnorm((qq[0] - x, qq[1] - y))
    # pointer triangle
    tip = (x + nd[0] * r * 1.75, y + nd[1] * r * 1.75)
    side = vperp(nd)
    a = (x + side[0] * r, y + side[1] * r)
    b = (x - side[0] * r, y - side[1] * r)
    p.polygon([a, tip, b], lw="fine", fill="black")
    p.circle((x, y), r, lw="thin", fill="white")
    p.line((x - r, y), (x + r, y), lw="fine")
    p.text((x, y + r * 0.45), str(num), size=TXT["small"], font=FONT_B, anchor="c", valign="mid")
    p.text((x, y - r * 0.47), str(sheet), size=TXT["tiny"], anchor="c", valign="mid")


def elevation_mark(v: View, at, num, sheet, direction=(0, 1), r=0.17):
    """Single interior/exterior elevation bubble pointing in model `direction`."""
    _section_bubble(v, at, vnorm(direction), num, sheet, r)


def detail_callout(v: View, center, radius_ft, num, sheet, bubble_dir=(1, 1), shape="circle",
                   size=None):
    """Dashed circle (or rect when shape='rect' and radius_ft=(w,h)) around an area + bubble."""
    p = Paper(v.c)
    if shape == "circle":
        v.circle(center, radius_ft, lw="fine", dash="dashed")
        edge = vadd(center, vmul(vnorm(bubble_dir), radius_ft))
    else:
        w, h = radius_ft
        v.rect(center[0] - w / 2, center[1] - h / 2, w, h, lw="fine", dash="dashed")
        edge = (center[0] + w / 2 * (1 if bubble_dir[0] >= 0 else -1),
                center[1] + h / 2 * (1 if bubble_dir[1] >= 0 else -1))
    x, y = v.to_paper(edge)
    bd = vnorm(bubble_dir)
    bx, by = x + bd[0] * 0.28, y + bd[1] * 0.28
    p.line((x, y), (bx - bd[0] * 0.17, by - bd[1] * 0.17), lw="fine")
    r = 0.17
    p.circle((bx, by), r, lw="thin", fill="white")
    p.line((bx - r, by), (bx + r, by), lw="fine")
    p.text((bx, by + r * 0.45), str(num), size=TXT["small"], font=FONT_B, anchor="c", valign="mid")
    p.text((bx, by - r * 0.47), str(sheet), size=TXT["tiny"], anchor="c", valign="mid")


def level_marker(v: View, x, elev, label, side="r", length=None, value_text=None, line=True,
                 x_line_from=None):
    """Elevation datum marker for sections/elevations: target symbol at (x, elev) with text.
    If x_line_from is given a thin datum line is drawn from x_line_from to x."""
    p = Paper(v.c)
    if x_line_from is not None and line:
        v.line((x_line_from, elev), (x, elev), lw="fine", dash="center")
    px, py = v.to_paper((x, elev))
    r = 0.065
    p.circle((px, py), r, lw="thin", fill="white")
    path = p.c.beginPath()
    p.c.setFillColor(black)
    # quarter fills
    for a0 in (0, 180):
        path = p.c.beginPath()
        path.moveTo(px * PT, py * PT)
        path.arcTo((px - r) * PT, (py - r) * PT, (px + r) * PT, (py + r) * PT, a0, 90)
        path.close()
        p.c.drawPath(path, stroke=0, fill=1)
    dx = 0.12 if side == "r" else -0.12
    anc = "l" if side == "r" else "r"
    p.text((px + dx, py + 0.035), label, size=TXT["small"], font=FONT_B, anchor=anc, valign="bot")
    p.text((px + dx, py - 0.03), value_text or fmt_elev(elev), size=TXT["small"], anchor=anc,
           valign="top")


def spot_elev(v: View, at, text, size=TXT["small"], marker="x"):
    p = Paper(v.c)
    x, y = v.to_paper(at)
    d = 0.03
    if marker == "x":
        p.line((x - d, y - d), (x + d, y + d), lw="fine")
        p.line((x - d, y + d), (x + d, y - d), lw="fine")
    else:
        p.circle((x, y), d, lw="fine")
    p.text((x + 0.04, y + 0.02), text, size=size, anchor="l", valign="bot")


def break_line(v: View, p1, p2, zig=0.12):
    """Straight break line with a single zig-zag in the middle (zig in paper inches)."""
    d = vsub(p2, p1)
    u = vnorm(d)
    n = vperp(u)
    m = lerp(p1, p2, 0.5)
    z = v.paper_len(zig)
    pts = [p1, vsub(m, vmul(u, z * 0.6)), vadd(vsub(m, vmul(u, z * 0.2)), vmul(n, z)),
           vsub(vadd(m, vmul(u, z * 0.2)), vmul(n, z)), vadd(m, vmul(u, z * 0.6)), p2]
    v.polyline(pts, lw="fine")


def north_arrow(p: Paper, x, y, size=0.6, rot=0.0):
    c = p.c
    c.saveState()
    c.translate(x * PT, y * PT)
    c.rotate(rot)
    R = size * PT / 2
    c.setLineWidth(LW["thin"])
    c.setStrokeColor(black)
    c.circle(0, 0, R, stroke=1, fill=0)
    path = c.beginPath()
    path.moveTo(0, R * 1.15)
    path.lineTo(R * 0.38, -R * 0.55)
    path.lineTo(0, -R * 0.25)
    path.close()
    c.setFillColor(black)
    c.drawPath(path, stroke=1, fill=1)
    path = c.beginPath()
    path.moveTo(0, R * 1.15)
    path.lineTo(-R * 0.38, -R * 0.55)
    path.lineTo(0, -R * 0.25)
    path.close()
    c.setFillColor(white)
    c.drawPath(path, stroke=1, fill=1)
    c.setFillColor(black)
    c.setFont(FONT_B, TXT["sub"])
    c.drawCentredString(0, R * 1.3, "N")
    c.restoreState()
    p.text((x, y - size / 2 - 0.12), "PLAN NORTH", size=TXT["tiny"], anchor="c", valign="top")


def scale_bar(p: Paper, x, y, scale, feet_total=None, divisions=None):
    """Graphic scale bar at paper (x,y) for a scale in paper-inches per foot."""
    if feet_total is None:
        # choose a nice length about 2.5" long
        target = 2.5 / scale
        for nice in (1, 2, 4, 5, 8, 10, 16, 20, 32, 40, 50, 64, 80, 100, 120, 150, 200, 300, 400):
            if nice >= target * 0.7:
                feet_total = nice
                break
        else:
            feet_total = target
    divisions = divisions or 4
    L = feet_total * scale
    h = 0.06
    for i in range(divisions):
        x0 = x + L * i / divisions
        p.rect(x0, y, L / divisions, h, lw="fine", fill="black" if i % 2 == 0 else "white")
    for i in range(divisions + 1):
        x0 = x + L * i / divisions
        val = feet_total * i / divisions
        p.text((x0, y + h + 0.03), f"{val:g}'", size=TXT["tiny"], anchor="c", valign="bot")


def view_title(p: Paper, x, y, num, title, scale=None, sheet=None, width=None, note=None):
    """View title: bubble with number (and sheet), heavy underline, title & scale text.
    (x, y) = left end of the underline."""
    r = 0.19
    p.circle((x + r, y + 0.02), r, lw="thin")
    if sheet:
        p.line((x, y + 0.02), (x + 2 * r, y + 0.02), lw="fine")
        p.text((x + r, y + 0.02 + r * 0.45), str(num), size=TXT["label"], font=FONT_B, anchor="c",
               valign="mid")
        p.text((x + r, y + 0.02 - r * 0.47), str(sheet), size=TXT["tiny"], anchor="c", valign="mid")
    else:
        p.text((x + r, y + 0.02), str(num), size=TXT["sub"], font=FONT_B, anchor="c", valign="mid")
    tx = x + 2 * r + 0.08
    w = p.text((tx, y + 0.05), title.upper(), size=TXT["sub"], font=FONT_B, anchor="l", valign="bot")
    L = max(width or 0, w + 0.15)
    p.line((tx, y + 0.01), (tx + L, y + 0.01), lw="xheavy")
    if scale is not None:
        st = scale if isinstance(scale, str) else ("SCALE: " + scale_label(scale))
        p.text((tx, y - 0.04), st, size=TXT["small"], anchor="l", valign="top")
    if note:
        p.text((tx + L, y - 0.04), note, size=TXT["small"], anchor="r", valign="top")


def table(p: Paper, x, y, cols, rows, row_h=0.16, size=TXT["small"], header_size=None,
          header_fill="g15", title=None, font=FONT, wrap=False, align=None, lw_grid="fine",
          header_rows=1, max_lines=3):
    """Simple schedule/table in paper space. (x, y) is the TOP-LEFT corner.
    cols : list of (header_text, width_in)
    rows : list of lists of cell strings
    align: list of 'l'/'c'/'r' per column (default 'c' except first 'l')
    Returns total height (inches)."""
    hs = header_size or size
    widths = [w for _, w in cols]
    W = sum(widths)
    cy = y
    if title:
        p.rect(x, cy - row_h * 1.25, W, row_h * 1.25, lw="thin", fill="g30")
        p.text((x + W / 2, cy - row_h * 0.62), title, size=hs * 1.15, font=FONT_B, anchor="c",
               valign="mid")
        cy -= row_h * 1.25
    # header (allow multi-line headers with \n)
    hlines = max(len(str(h).split("\n")) for h, _ in cols)
    hh = row_h * max(1, hlines) * 0.85 + row_h * 0.3
    p.rect(x, cy - hh, W, hh, lw="thin", fill=header_fill)
    xx = x
    for (h, w) in cols:
        p.mtext((xx + w / 2, cy - hh / 2), str(h).split("\n"), size=hs, font=FONT_B, anchor="c",
                valign="mid", leading=hs * 1.1)
        xx += w
    segs = [[cy, cy - hh]]
    cy -= hh
    al = align or (["l"] + ["c"] * (len(cols) - 1))
    for r in rows:
        if r is None:
            continue
        is_sep = isinstance(r, str)
        if is_sep:  # section separator row (no vertical grid lines through it)
            p.rect(x, cy - row_h, W, row_h, lw="fine", fill="g05")
            p.text((x + 0.05, cy - row_h / 2), r, size=size, font=FONT_B, anchor="l", valign="mid")
            cy -= row_h
            segs.append(None)
            continue
        # compute wrapped line counts
        cells = []
        nl = 1
        for (h, w), cell in zip(cols, r):
            s = "" if cell is None else str(cell)
            ls = s.split("\n")
            if wrap:
                ls = wrap_lines(ls, size, font, w - 0.06)
            ls = ls[:max_lines]
            nl = max(nl, len(ls))
            cells.append(ls)
        rh = row_h if nl == 1 else row_h * (0.25 + 0.78 * nl)
        xx = x
        for (h, w), ls, a in zip(cols, cells, al):
            tx = {"l": xx + 0.04, "c": xx + w / 2, "r": xx + w - 0.04}[a]
            p.mtext((tx, cy - rh / 2), ls, size=size, font=font, anchor=a, valign="mid",
                    leading=size * 1.12)
            xx += w
        p.line((x, cy - rh), (x + W, cy - rh), lw=lw_grid)
        if segs and segs[-1] is not None:
            segs[-1][1] = cy - rh
        else:
            segs.append([cy, cy - rh])
        cy -= rh
    # verticals (skipping separator rows) + outline
    H = y - cy
    for sg in segs:
        if sg is None:
            continue
        xx = x
        for w in widths[:-1]:
            xx += w
            p.line((xx, sg[0]), (xx, sg[1]), lw=lw_grid)
    p.rect(x, cy, W, H, lw="thin")
    return H


def notes_block(p: Paper, x, y, title, notes, width, size=TXT["note"], numbered=True,
                title_size=None, leading=None):
    """Titled list of general notes, word-wrapped to `width`. Returns height used."""
    ts = title_size or TXT["label"]
    p.text((x, y), title.upper(), size=ts, font=FONT_B, anchor="l", valign="top", underline=True)
    cy = y - ts * 1.6 / PT
    lead = leading or size * 1.28
    i = 0
    for n in notes:
        if n.startswith("##"):
            cy -= 0.04
            p.text((x, cy), n[2:].strip(), size=size, font=FONT_B, valign="top")
            cy -= lead / PT
            i = 0
            continue
        i += 1
        label = f"{i}." if numbered else "-"
        lw_in = p.text_width("00. ", size)
        ls = wrap_lines([n], size, FONT, width - lw_in)
        p.text((x, cy), label, size=size, valign="top")
        for ln in ls:
            p.text((x + lw_in, cy), ln.strip(), size=size, valign="top")
            cy -= lead / PT
        cy -= lead * 0.25 / PT
    return y - cy
