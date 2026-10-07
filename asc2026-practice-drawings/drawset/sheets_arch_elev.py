"""A-201 / A-202 exterior elevations, A-301 building sections, A-311 / A-312 wall sections.

Everything is generated from drawset/model.py (grids, levels, wall layers, openings, rooms).
Elevations / sections are drawn in an (h, z) frame: h = horizontal paper direction in model
feet (sign chosen so the view reads correctly), z = architectural elevation in feet.

Coursing: every masonry datum (heads, sills, bands, parapet) is on the 8" module measured from
T.O. foundation wall 99'-4" (= finish grade at building).  3 brick courses = 8".
"""
from __future__ import annotations

import math

from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Polygon, box
from shapely.ops import unary_union

from . import model as M
from .cad import (FONT, FONT_B, FONT_I, LW, PT, SCREEN, TXT, Paper, View, break_line,
                  detail_callout, door_tag, fmt_elev, fmt_ftin, fmt_in, grid_bubble, keynote_tag,
                  level_marker, notes_block, room_tag, table, window_tag, wrap_lines)

IN = M.IN
LV = M.LEVELS
BOF, TOF, LEDGE, GRADE = LV["BOF"], LV["TOF"], LV["LEDGE"], LV["GRADE"]
L1, L2, ROOF, PARAPET = LV["L1"], LV["L2"], LV["ROOF"], LV["PARAPET"]
LINK_ROOF, LINK_PAR, EX_ROOF = LV["LINK_ROOF"], LV["LINK_PARAPET"], LV["EXIST_ROOF"]
OUT = M.EW_OUT                    # grid -> face of brick
CMUh = M.EW_IN                    # grid -> interior face of CMU
FX = M.EXIST_FACE_X

# ---- envelope datums (DESIGN.md 4 / 6) ----------------------------------------------------
BASE_TOP = 100 + 8 * IN           # FB-2 base band 99'-4" -> 100'-8" (6 courses)
CS2_BOT, CS2_TOP = 113 + 4 * IN, L2   # CS-2 band on L6x4x3/8 shelf angle
SOLDIER = 8 * IN
CS1_H, CS1_PROJ, CS1_LUG = 4 * IN, 1 * IN, 3 * IN   # CS-1: 4" high, 1" proj., MO + 3" each end
COPE_DROP = 4 * IN                # coping face leg laps 4" over the brick
COPE_UP = 5.5 * IN                # (3) layers 2x + 3/4" plywood + coping above T.O. masonry (8/A-501)
W0_SHELF = 114 + 1.875 * IN       # brick on corridor-end wall W0 bears on a shelf angle (12/A-501)
CURB_TOP = L1                     # SF-3 concrete curb 99'-4" -> 100'-0"
BASE_FLASH = L1                   # base through-wall flashing 8" above grade
VENT_H = 2 + 4 * IN               # W-A / W-B: intermediate rail above MO sill (awning vents below)
SF_TRANSOM = (107.0, 107 + 4 * IN)   # SF-1 / SF-3 transom bar (door head 7'-0")
FR = 2 * IN                       # aluminum frame sightline

# window frame location in the wall (matches A-501: inside face of frame = outside face of CMU)
FR_IN, FR_OUT = CMUh, CMUh + 4.5 * IN

# ---- roof (DESIGN 6a; A-103) ---------------------------------------------------------------
ROOF_DRAINS = [(15.0, 36.0), (52.5, 36.0), (97.5, 36.0), (135.0, 36.0)]
RTUS = [("RTU-1", 45.0, 57.0), ("RTU-2", 105.0, 57.0), ("RTU-3", 105.0, 15.0)]
RTU_W, RTU_D = 14.0, 7.0          # curb E-W x N-S
RTU_TOP = 134 + 6 * IN            # approximate top of unit (by Div. 23)
HATCH = (46.75, 27.0, 2.5, 3.0)   # center x, y, E-W, N-S
SCUPPER_X = -10.0                 # DESIGN 6a: link scupper / conductor head / downspout
DECK = 1.5 * IN
INS_MIN = 1.5 * IN                # tapered polyiso min. at drains (A-103)
COVER = 0.5 * IN
LINK_INS_MIN = 4.0 * IN           # (2) layers 2" polyiso at the low (scupper) side (12/A-501)


def roof_ins(x, y):
    """tapered polyiso thickness (ft) at plan point: 1/4":12 to the drain line y = 36,
    1/2":12 crickets (diamonds, ridge N-S) at mid-points between drains (A-103)."""
    dy = abs(y - 36.0)
    t = 0.25 * dy
    for i in range(3):
        xm = (ROOF_DRAINS[i][0] + ROOF_DRAINS[i + 1][0]) / 2
        cr = 0.5 * (8.4 - abs(x - xm)) - 0.45 * dy
        t = max(t, cr)
    return INS_MIN + t * IN


def roof_top(x, y):
    return ROOF + DECK + roof_ins(x, y) + COVER


# ---- brick expansion joints (DESIGN 6: 25'-0" max, within 4'-0" of each outside corner on one
# face, CMU control joints aligned, 24'-0" max).  Values = coordinate along the face (x for N/S
# faces, y for E/W faces).  Verified against model.OPENINGS by check_ej().
EJ = {
    "N": [19 + 8 * IN, 40 + 4 * IN, 60.0, 79 + 8 * IN, 100 + 4 * IN, 120.0, 138.0],
    "S": [12.0, 30.0, 44.0, 60.0, 79 + 8 * IN, 100 + 4 * IN, 120.0, 139 + 8 * IN],
    "E": [2.0, 25.0, 49.0, 70.0],
    "W": [2.0, 22.0, 46.0, 70.0],
    "LN": [-18.0],
    "LS": [-18.0],
}
LINTEL_BRG = 8 * IN

# ---------------------------------------------------------------------------------------------
# A-501 detail numbers used for callouts (see sheets_arch_details / sheets_arch_sched DETAIL_KEY)
# ---------------------------------------------------------------------------------------------
D_HEAD, D_JAMB, D_SILL = "1", "2", "3"
D_SF1_HEAD, D_SF1_SILL, D_SF1_JAMB = "4", "5", "6"
D_SF3 = "7"                       # SF-3 head & sill at curb
D_PARAPET, D_SHELF, D_BASE, D_EJ, D_LINKROOF, D_CURB, D_TIEIN = "8", "9", "10", "11", "12", "13", "14"


# =============================================================================================
# Faces
# =============================================================================================
class Face:
    """One exterior brick face.  a = coordinate along the face (x or y), h = sign * a."""

    def __init__(self, key, segs, sign, a0, a1, top, cs2=True, plane=0.0, voids=(), crop=False):
        self.crop = crop
        self.key, self.segs, self.sign = key, segs, sign
        self.a0, self.a1, self.top, self.cs2, self.plane = a0, a1, top, cs2, plane
        self.voids = list(voids)          # (a0, z0, a1, z1) areas without brick on this face

    def h(self, a):
        return self.sign * a

    def hr(self, a0, a1):
        return tuple(sorted((self.h(a0), self.h(a1))))

    @property
    def h0(self):
        return min(self.h(self.a0), self.h(self.a1))

    @property
    def h1(self):
        return max(self.h(self.a0), self.h(self.a1))

    def openings(self):
        out = []
        for o in M.OPENINGS:
            if o.wall in self.segs and o.kind in ("window", "storefront", "louver", "door"):
                if o.kind == "door" and o.frame == "SF":
                    continue      # door pair 100B is part of SF-1
                if self.crop and (o.hi < self.a0 or o.lo > self.a1):
                    continue
                out.append(o)
        return out

    def ej(self):
        return [a for a in EJ.get(self.key, []) if not self.crop or self.a0 <= a <= self.a1]

    def cropped(self, a0, a1):
        f = Face(self.key, self.segs, self.sign, a0, a1, self.top, self.cs2, self.plane,
                 self.voids, crop=True)
        return f


FACES = {
    "N": Face("N", ("N",), -1, -OUT, 150 + OUT, PARAPET, plane=72 + OUT),
    "S": Face("S", ("S",), +1, -OUT, 150 + OUT, PARAPET, plane=-OUT),
    "E": Face("E", ("E",), +1, -OUT, 72 + OUT, PARAPET, plane=150 + OUT),
    "W": Face("W", ("W1", "W2", "W0"), -1, -OUT, 72 + OUT, PARAPET, plane=-OUT,
              voids=[(30 - OUT, GRADE - 1, 42 + OUT, W0_SHELF)]),
    "LN": Face("LN", ("LN",), -1, FX, -OUT, LINK_PAR, cs2=False, plane=42 + OUT),
    "LS": Face("LS", ("LS",), +1, FX, -OUT, LINK_PAR, cs2=False, plane=30 - OUT),
}


def check_ej(verbose=False):
    """Validate EJ layout: clear of openings + lintel bearing, spacing, corner rule."""
    msgs = []
    for k, f in FACES.items():
        ops = f.openings()
        for a in f.ej():
            for o in ops:
                if o.type == "SF-3":
                    continue      # link EJ runs in the brick above the SF-3 head
                if o.lo - LINTEL_BRG - 0.3 * IN < a < o.hi + LINTEL_BRG + 0.3 * IN:
                    msgs.append(f"EJ {k} @ {a:.3f} conflicts with {o.id}")
        pts = sorted(f.ej())
        for a, b in zip(pts[:-1], pts[1:]):
            if b - a > 24.0 + 1e-6:
                msgs.append(f"EJ {k} spacing {b - a:.2f} > 24'")
    if verbose:
        print("\n".join(msgs) or "EJ layout OK")
    return msgs


# =============================================================================================
# Small drawing helpers
# =============================================================================================
def rings_of(g):
    out = []
    if g is None or g.is_empty:
        return out
    geoms = g.geoms if hasattr(g, "geoms") else [g]
    for p in geoms:
        if isinstance(p, Polygon) and not p.is_empty:
            out.append(list(p.exterior.coords))
            out += [list(r.coords) for r in p.interiors]
    return out


def to_h(g, sign):
    return affinity.scale(g, xfact=sign, yfact=1.0, origin=(0, 0)) if sign < 0 else g


def R(v, h0, z0, h1, z1, **kw):
    v.polygon([(h0, z0), (h1, z0), (h1, z1), (h0, z1)], **kw)


class Clip:
    """with Clip(v, rings): ...  -> clip drawing to the rings (even-odd)."""

    def __init__(self, v, rings):
        self.v, self.rings = v, rings

    def __enter__(self):
        self.v.c.saveState()
        self.v._clip_rings(self.rings)
        return self.v

    def __exit__(self, *a):
        self.v.c.restoreState()


def clip_rect_paper(c, x0, y0, x1, y1):
    c.saveState()
    p = c.beginPath()
    p.rect(x0 * PT, y0 * PT, (x1 - x0) * PT, (y1 - y0) * PT)
    c.clipPath(p, stroke=0, fill=0)


def running_bond(v, g, course, unit, z0=GRADE, h_ref=0.0, col=0.5, w="hair", heads=True,
                 fill=None):
    """Brick elevation hatch: bed joints every `course`, head joints every `unit` staggered by
    half a unit (running bond), clipped to shapely geometry g (h, z)."""
    if g is None or g.is_empty:
        return
    rings = rings_of(g)
    if fill is not None:
        v._fill_path(rings, fill)
    hx0, zz0, hx1, zz1 = g.bounds
    c = v.c
    with Clip(v, rings):
        c.setLineWidth(LW[w] if isinstance(w, str) else w)
        c.setStrokeColor(_col(col))
        c.setDash([])
        k0 = math.floor((zz0 - z0) / course) - 1
        k1 = math.ceil((zz1 - z0) / course) + 1
        for k in range(k0, k1 + 1):
            z = z0 + k * course
            if zz0 - course <= z <= zz1 + course:
                a, b = v.P((hx0, z)), v.P((hx1, z))
                c.line(a[0], a[1], b[0], b[1])
            if not heads:
                continue
            off = (k % 2) * unit / 2
            m0 = math.floor((hx0 - h_ref - off) / unit) - 1
            m1 = math.ceil((hx1 - h_ref - off) / unit) + 1
            for m in range(m0, m1 + 1):
                hh = h_ref + off + m * unit
                a, b = v.P((hh, z)), v.P((hh, z + course))
                c.line(a[0], a[1], b[0], b[1])


def vlines(v, g, step, h_ref=0.0, col=0.45, w="hair"):
    """vertical joint lines (soldier course) clipped to g"""
    if g is None or g.is_empty:
        return
    hx0, zz0, hx1, zz1 = g.bounds
    c = v.c
    with Clip(v, rings_of(g)):
        c.setLineWidth(LW[w] if isinstance(w, str) else w)
        c.setStrokeColor(_col(col))
        c.setDash([])
        m0 = math.floor((hx0 - h_ref) / step) - 1
        m1 = math.ceil((hx1 - h_ref) / step) + 1
        for m in range(m0, m1 + 1):
            hh = h_ref + m * step
            a, b = v.P((hh, zz0)), v.P((hh, zz1))
            c.line(a[0], a[1], b[0], b[1])


def stipple(v, g, step_in=0.045, col=0.45, r_pt=0.28, seed=0):
    """regular staggered dot pattern (cast stone / concrete in elevation), step in paper inches"""
    if g is None or g.is_empty:
        return
    hx0, zz0, hx1, zz1 = g.bounds
    st = v.paper_len(step_in)
    c = v.c
    with Clip(v, rings_of(g)):
        c.setFillColor(_col(col))
        j = 0
        z = zz0 + st * 0.3
        while z < zz1:
            hh = hx0 + (st / 2 if j % 2 else 0) + st * 0.17 * ((seed + j) % 3)
            while hh < hx1:
                p = v.P((hh, z))
                c.circle(p[0], p[1], r_pt, stroke=0, fill=1)
                hh += st
            z += st * 0.6
            j += 1


def _col(c):
    from .cad import color as _c
    return _c(c)


def mat_tag(v, target, at, text, size=TXT["small"], arrow=True):
    """material tag: boxed text at `at` (model) with leader to `target` (model)."""
    p = Paper(v.c)
    x, y = v.to_paper(at)
    w = p.text_width(text, size, FONT_B) + 0.08
    hgt = size / PT + 0.06
    tx, ty = v.to_paper(target)
    # leader from nearest box edge
    ex = x - w / 2 if tx < x - w / 2 else (x + w / 2 if tx > x + w / 2 else tx)
    ey = y - hgt / 2 if ty < y - hgt / 2 else (y + hgt / 2 if ty > y + hgt / 2 else ty)
    if abs(tx - ex) + abs(ty - ey) > 0.03:
        p.line((ex, ey), (tx, ty), lw="fine")
        if arrow:
            ang = math.atan2(ty - ey, tx - ex)
            L, W = 0.06, 0.018
            bx, by = tx - L * math.cos(ang), ty - L * math.sin(ang)
            p.polygon([(tx, ty), (bx - W * math.sin(ang), by + W * math.cos(ang)),
                       (bx + W * math.sin(ang), by - W * math.cos(ang))], lw="fine", fill="black")
        else:
            p.circle((tx, ty), 0.016, lw=None, fill="black")
    p.rect(x - w / 2, y - hgt / 2, w, hgt, lw="fine", fill="white")
    p.text((x, y), text, size=size, font=FONT_B, anchor="c", valign="mid")


def key_tag(v, at, n, target=None):
    if target is not None:
        p = Paper(v.c)
        a, b = v.to_paper(at), v.to_paper(target)
        p.line(a, b, lw="fine")
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        L, W = 0.06, 0.018
        bx, by = b[0] - L * math.cos(ang), b[1] - L * math.sin(ang)
        p.polygon([b, (bx - W * math.sin(ang), by + W * math.cos(ang)),
                   (bx + W * math.sin(ang), by - W * math.cos(ang))], lw="fine", fill="black")
    keynote_tag(v, at, n)


def small_bubble(v, at, label, r=0.1, size=TXT["tiny"]):
    p = Paper(v.c)
    x, y = v.to_paper(at)
    p.circle((x, y), r, lw="fine", fill="white")
    p.text((x, y), str(label), size=size, font=FONT_B, anchor="c", valign="mid")


def text_box(v, at, lines, size=TXT["small"], anchor="c", font=FONT, pad=0.03, color="black"):
    """multi-line text on a white mask (paper-sized)"""
    p = Paper(v.c)
    x, y = v.to_paper(at)
    if isinstance(lines, str):
        lines = lines.split("\n")
    w = max(p.text_width(s, size, font) for s in lines)
    lead = size * 1.2 / PT
    h = lead * len(lines)
    x0 = {"l": x, "c": x - w / 2, "r": x - w}[anchor]
    p.rect(x0 - pad, y - h / 2 - pad, w + 2 * pad, h + 2 * pad, lw=None, fill="white")
    p.mtext((x, y), lines, size=size, font=font, anchor=anchor, valign="mid", leading=size * 1.2,
            color=color)


def ftxt(L, denom=16):
    """feet -> 1'-0 9/16\" style text (cad.fmt_ftin drops the 0 inch before fractions)"""
    t = fmt_ftin(L, denom)
    if "'-" in t:
        ft, rest = t.split("'-", 1)
        if rest.startswith(("1/", "3/", "5/", "7/", "9/", "11/", "13/", "15/")) and " " not in rest:
            t = f"{ft}'-0 {rest}"
    return t


def dchain(v, pts, off=0.0, size=TXT["tiny"], denom=16):
    """dimension chain with alternating text flip for short segments (own text formatting)"""
    from reportlab.pdfbase.pdfmetrics import stringWidth as _sw
    flip = False
    for a, b in zip(pts[:-1], pts[1:]):
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L <= 1e-6:
            continue
        t = ftxt(L, denom)
        tw = v.paper_len(_sw(t, FONT, size) / PT)
        if tw > L * 0.92:
            flip = not flip
            v.dim(a, b, off, text=t, size=size, flip_text=flip,
                  text_offset=v.paper_len(0.035) if flip else None)
        else:
            flip = False
            v.dim(a, b, off, text=t, size=size)


def vdim_chain(v, h, zs, off, size=TXT["tiny"], labels=None):
    """vertical dimension chain at h through elevations zs; off > 0 puts it left of h"""
    pts = [(h, z) for z in sorted(set(round(z, 6) for z in zs))]
    dchain(v, pts, off, size=size)


def glass_marks(v, h0, z0, h1, z1, scale_paper=0.12):
    """conventional glass indication (two short diagonals) in the upper part of a lite"""
    w, hgt = h1 - h0, z1 - z0
    if w <= 0 or hgt <= 0:
        return
    L = min(v.paper_len(scale_paper), w * 0.35, hgt * 0.35)
    cx, cz = h0 + w * 0.62, z0 + hgt * 0.72
    for d in (-0.35, 0.35):
        a = (cx + d * L - L / 2, cz - L / 2)
        b = (cx + d * L + L / 2, cz + L / 2)
        v.line(a, b, lw="hair", color="g50")


# =============================================================================================
# Opening elevations
# =============================================================================================
def _frame_rect(v, h0, z0, h1, z1, lw_out="thin"):
    R(v, h0, z0, h1, z1, lw=lw_out, fill="white")
    R(v, h0 + FR, z0 + FR, h1 - FR, z1 - FR, lw="fine")


def _hmull(v, h0, h1, zc, w=FR):
    v.line((h0, zc - w / 2), (h1, zc - w / 2), lw="fine")
    v.line((h0, zc + w / 2), (h1, zc + w / 2), lw="fine")


def _vmull(v, hc, z0, z1, w=FR):
    v.line((hc - w / 2, z0), (hc - w / 2, z1), lw="fine")
    v.line((hc + w / 2, z0), (hc + w / 2, z1), lw="fine")


def _vent(v, h0, z0, h1, z1):
    """awning vent (top hinged, projecting out): lines from bottom corners to top center"""
    hm = (h0 + h1) / 2
    v.polyline([(h0, z0), (hm, z1), (h1, z0)], lw="hair", dash=[2, 1.5])


def _swing(v, h_hinge, h_latch, z0, z1):
    zm = (z0 + z1) / 2
    v.polyline([(h_latch, z1), (h_hinge, zm), (h_latch, z0)], lw="hair", dash=[2, 1.5])


def draw_window_elev(v, o, hl, hr, fine=False, tag=True, tag_at=None):
    """aluminum window / storefront / louver in elevation between hl..hr (h), o.sill..o.head"""
    zs, zh = o.sill, o.head
    t = o.type
    if t in ("W-A", "W-B"):
        _frame_rect(v, hl, zs, hr, zh)
        zr = zs + VENT_H
        _hmull(v, hl + FR, hr - FR, zr)
        cols = [hl, (hl + hr) / 2, hr] if t == "W-A" else [hl, hr]
        for hc in cols[1:-1]:
            _vmull(v, hc, zs + FR, zh - FR)
        for a, b in zip(cols[:-1], cols[1:]):
            a1 = a + (FR if a == hl else FR / 2)
            b1 = b - (FR if b == hr else FR / 2)
            _vent(v, a1, zs + FR, b1, zr - FR / 2)
            if fine:
                glass_marks(v, a1, zr + FR / 2, b1, zh - FR)
        lab_z = zr + (zh - zr) * 0.55
    elif t == "W-C":
        _frame_rect(v, hl, zs, hr, zh)
        n = 4
        for k in range(1, n):
            _hmull(v, hl + FR, hr - FR, zs + (zh - zs) * k / n)
        if fine:
            for k in range(n):
                glass_marks(v, hl + FR, zs + (zh - zs) * k / n, hr - FR, zs + (zh - zs) * (k + 1) / n)
        lab_z = zs + (zh - zs) * 0.62
    elif t == "SF-2":
        _frame_rect(v, hl, zs, hr, zh)
        for k in (1, 2):
            _vmull(v, hl + (hr - hl) * k / 3, zs + FR, zh - FR)
        if fine:
            for k in range(3):
                glass_marks(v, hl + (hr - hl) * k / 3, zs, hl + (hr - hl) * (k + 1) / 3, zh)
        lab_z = zs + (zh - zs) * 0.55
    elif t == "SF-3":
        _frame_rect(v, hl, zs, hr, zh)
        _hmull(v, hl + FR, hr - FR, sum(SF_TRANSOM) / 2, w=SF_TRANSOM[1] - SF_TRANSOM[0])
        for k in range(1, 6):
            _vmull(v, hl + (hr - hl) * k / 6, zs + FR, zh - FR)
        if fine:
            for k in range(6):
                glass_marks(v, hl + (hr - hl) * k / 6, zs, hl + (hr - hl) * (k + 1) / 6,
                            SF_TRANSOM[0])
        lab_z = (SF_TRANSOM[1] + zh) / 2
        if tag_at is None:
            tag_at = (hl + (hr - hl) * 3.5 / 6, lab_z)
    elif t == "SF-1":
        _frame_rect(v, hl, zs, hr, zh)
        hc = (hl + hr) / 2
        dl, dr = hc - 3.0 - 1 * IN, hc + 3.0 + 1 * IN       # door jamb mullion centerlines
        _vmull(v, dl, zs, zh - FR)
        _vmull(v, dr, zs, zh - FR)
        _hmull(v, hl + FR, hr - FR, sum(SF_TRANSOM) / 2, w=SF_TRANSOM[1] - SF_TRANSOM[0])
        # sidelite bottom rails (10") to match door bottom rail
        for a, b in ((hl + FR, dl - FR / 2), (dr + FR / 2, hr - FR)):
            v.line((a, zs + 10 * IN), (b, zs + 10 * IN), lw="fine")
        # door leaves (medium stile 4", top rail 4", bottom rail 10")
        z_top = SF_TRANSOM[0]
        for a, b, hinge in ((dl + FR / 2, hc, dl + FR / 2), (hc, dr - FR / 2, dr - FR / 2)):
            R(v, a, zs, b, z_top, lw="fine")
            R(v, a + 4 * IN, zs + 10 * IN, b - 4 * IN, z_top - 4 * IN, lw="hair")
            latch = b if hinge == a else a
            _swing(v, hinge, latch, zs, z_top)
            # offset pull
            hp = latch + (-6 * IN if latch == b else 6 * IN)
            v.line((hp, zs + 3.0), (hp, zs + 4.5), lw="thin")
        lab_z = (SF_TRANSOM[1] + zh) / 2
    elif t == "LV-1":
        R(v, hl, zs, hr, zh, lw="thin", fill="white")
        R(v, hl + FR, zs + FR, hr - FR, zh - FR, lw="fine")
        z = zs + FR + 4 * IN
        while z < zh - FR - 1 * IN:
            v.line((hl + FR, z), (hr - FR, z), lw="hair")
            z += 4 * IN
        lab_z = (zs + zh) / 2
    else:
        R(v, hl, zs, hr, zh, lw="thin")
        lab_z = (zs + zh) / 2
    if tag:
        at = tag_at or ((hl + hr) / 2, lab_z)
        if t == "LV-1":
            p = Paper(v.c)
            x, y = v.to_paper(at)
            p.rect(x - 0.15, y - 0.07, 0.3, 0.14, lw=None, fill="white")
        window_tag(v, at, t, size=TXT["tiny"] if len(t) > 3 else TXT["small"], r=0.105)


def draw_door_elev(v, o, hl, hr, hinge_h=None, tag=True):
    """hollow metal door + frame (F1 single / F3 pair) in elevation"""
    z0, zh = o.sill, o.head
    R(v, hl, z0, hr, zh, lw="thin", fill="white")             # frame outline (MO)
    fi0, fi1, ft = hl + 2 * IN, hr - 2 * IN, zh - 4 * IN        # frame opening
    v.polyline([(fi0, z0), (fi0, ft), (fi1, ft), (fi1, z0)], lw="fine")
    if o.pair:
        hm = (fi0 + fi1) / 2
        v.line((hm, z0), (hm, ft), lw="fine")
        _swing(v, fi0, hm, z0, ft)
        _swing(v, fi1, hm, z0, ft)
        for hh in (hm - 4 * IN, hm + 4 * IN):
            v.line((hh, z0 + 3.0), (hh, z0 + 3.4), lw="thin")
    else:
        hh = hinge_h if hinge_h is not None else fi0
        latch = fi1 if abs(hh - fi0) < abs(hh - fi1) else fi0
        _swing(v, hh, latch, z0, ft)
        hp = latch + (-4 * IN if latch == fi1 else 4 * IN)
        v.line((hp, z0 + 3.0), (hp, z0 + 3.4), lw="thin")
    if tag:
        door_tag(v, ((hl + hr) / 2, z0 + 5.6), o.id, size=TXT["tiny"])


# =============================================================================================
# Face renderer
# =============================================================================================
def _opening_void(o):
    """(a0, z0, a1, z1) area of the face taken by the opening (incl. stoop / curb below)."""
    z0 = o.sill
    if o.kind == "door" or o.type in ("SF-1", "SF-3"):
        z0 = GRADE - 0.01
    return (o.lo, z0, o.hi, o.head)


def face_regions(f: Face):
    """shapely regions (in a, z) of every material on the face"""
    full = box(f.a0, GRADE, f.a1, f.top)
    voids = [box(*vv) for vv in f.voids]
    ops = f.openings()
    holes = [box(*_opening_void(o)) for o in ops]
    sills = [box(o.lo - CS1_LUG, o.sill - CS1_H, o.hi + CS1_LUG, o.sill) for o in ops
             if o.type in ("W-A", "W-B", "SF-2")]
    sold = [box(o.lo, o.head, o.hi, o.head + SOLDIER) for o in ops
            if o.type in ("W-A", "W-B", "SF-2")]
    ov = 0.0 if f.crop else 1 * IN
    cope = box(f.a0 - ov, f.top - COPE_DROP, f.a1 + ov, f.top + COPE_UP)
    V = unary_union(voids + holes) if (voids or holes) else Polygon()
    base = box(f.a0, GRADE, f.a1, BASE_TOP).difference(V)
    cs2 = box(f.a0, CS2_BOT, f.a1, CS2_TOP).difference(V) if f.cs2 else Polygon()
    cs1 = unary_union(sills) if sills else Polygon()
    sol = unary_union(sold) if sold else Polygon()
    taken = unary_union([V, base, cs2, cs1, sol, cope])
    fb1 = full.difference(taken)
    return dict(full=full.difference(unary_union(voids)) if voids else full, fb1=fb1, base=base,
                cs2=cs2, cs1=cs1, sol=sol, cope=cope, voids=V, ops=ops)


def render_face(v, f: Face, fine=False, tags=True, ej_labels=True, door_tags=True):
    """draw one face (brick, bands, sills, soldiers, coping, openings, EJ)."""
    rg = face_regions(f)
    s = f.sign
    H = lambda g: to_h(g, s)
    full = H(rg["full"])
    if f.crop:
        v.c.saveState()
        v._clip_rings([[(f.h0, GRADE - 30), (f.h1, GRADE - 30), (f.h1, f.top + 30),
                        (f.h0, f.top + 30)]])
        try:
            return _render_face_body(v, f, rg, full, H, fine, tags, ej_labels, door_tags)
        finally:
            v.c.restoreState()
    return _render_face_body(v, f, rg, full, H, fine, tags, ej_labels, door_tags)


def _render_face_body(v, f, rg, full, H, fine, tags, ej_labels, door_tags):
    v.geom(full, lw=None, fill="white", stroke=False)
    if fine:
        running_bond(v, H(rg["fb1"]), 8 / 3 * IN, 8 * IN, col=0.66)
        running_bond(v, H(rg["base"]), 8 / 3 * IN, 8 * IN, col=0.35, fill="g10")
        v.geom(H(rg["sol"]), lw=None, fill="g10", stroke=False)
        vlines(v, H(rg["sol"]), 8 / 3 * IN, col=0.35)
    else:
        running_bond(v, H(rg["fb1"]), 8 * IN, 16 * IN, col=0.62)
        running_bond(v, H(rg["base"]), 8 / 3 * IN, 8 * IN, col=0.45, fill="g10", heads=False)
        v.geom(H(rg["sol"]), lw=None, fill="g10", stroke=False)
        vlines(v, H(rg["sol"]), 8 / 3 * IN, col=0.45)
    v.geom(H(rg["base"]), lw="fine", stroke=True)
    v.geom(H(rg["sol"]), lw="fine")
    for g in (rg["cs2"], rg["cs1"]):
        if not g.is_empty:
            v.geom(H(g), lw=None, fill="white", stroke=False)
            stipple(v, H(g), step_in=0.03 if not fine else 0.04, col=0.4, r_pt=0.22)
            v.geom(H(g), lw="fine")
    # concrete curbs / stoops below storefront and doors
    for o in rg["ops"]:
        hl, hr = f.hr(o.lo, o.hi)
        if o.type == "SF-3":
            g = box(hl, GRADE, hr, CURB_TOP)
            v.geom(g, lw="thin", fill="white")
            stipple(v, g, step_in=0.05, col=0.5, r_pt=0.25)
        elif o.kind == "door" or o.type == "SF-1":
            ext = 1.0 if o.pair or o.type == "SF-1" else 1.0
            R(v, hl - ext, GRADE, hr + ext, L1 - 0.5 * IN, lw="thin", fill="white")
    # openings
    for o in rg["ops"]:
        hl, hr = f.hr(o.lo, o.hi)
        if o.kind == "door":
            hinge = None
            if not o.pair:
                ha = f.h(o.lo + 2 * IN) if o.hinge == "lo" else f.h(o.hi - 2 * IN)
                hinge = ha
            draw_door_elev(v, o, hl, hr, hinge_h=hinge, tag=door_tags)
        else:
            draw_window_elev(v, o, hl, hr, fine=fine, tag=tags)
            if o.type in ("W-C", "LV-1"):
                # prefinished metal sill flashing
                v.line((hl - 1 * IN, o.sill - 1 * IN), (hr + 1 * IN, o.sill - 1 * IN), lw="fine")
    # coping
    cp = H(rg["cope"])
    v.geom(cp, lw="thin", fill="white")
    hx0, _, hx1, _ = cp.bounds
    v.line((hx0, f.top + COPE_UP - 1.2 * IN), (hx1, f.top + COPE_UP - 1.2 * IN), lw="hair")
    # outline of brick face
    v.geom(full, lw="med")
    # expansion joints
    for a in f.ej():
        hh = f.h(a)
        z_bot = GRADE
        if f.key in ("LN", "LS"):
            z_bot = M.OPENING_BY_ID["100A-SF1"].head
        v.line((hh, z_bot), (hh, f.top - COPE_DROP), lw="thin")
        if fine:
            v.line((hh + 0.375 * IN, z_bot), (hh + 0.375 * IN, f.top - COPE_DROP), lw="thin")
        if ej_labels:
            zl = f.top - COPE_DROP - v.paper_len(0.16)
            text_box(v, (hh, zl), "EJ", size=TXT["tiny"], font=FONT_B, pad=0.012)
    return rg


def draw_below_grade(v, f: Face, footing_x=None, extra=()):
    """dashed foundation wall + footing below grade along the face"""
    h0, h1 = f.h0, f.h1
    R(v, h0, TOF, h1, GRADE, lw="fine", dash="hidden", fill=None)
    R(v, h0 - 0.75, BOF, h1 + 0.75, TOF, lw="fine", dash="hidden")
    for hh in (footing_x or []):
        R(v, hh - 2.5, BOF - 16 * IN, hh + 2.5, BOF, lw="fine", dash="hidden")


def grade_line(v, h0, h1, z=GRADE):
    v.line((h0, z), (h1, z), lw="xheavy")
    # earth tick marks below grade
    p = Paper(v.c)
    (x0, y), (x1, _) = v.to_paper((h0, z)), v.to_paper((h1, z))
    xx = x0 + 0.04
    while xx < x1 - 0.05:
        p.line((xx, y - 0.012), (xx - 0.05, y - 0.06), lw="hair")
        xx += 0.09


def grid_bubbles(v, items, z_line_top, z_line_bot, z_bub, dia=0.34):
    """items: [(h, label)]; grid line from z_line_bot up to the bubble"""
    r = v.paper_len(dia / 2)
    for hh, lab in items:
        v.line((hh, z_line_bot), (hh, z_bub - r), lw="hair", dash="grid")
        grid_bubble(v, (hh, z_bub), lab, dia=dia, size=TXT["label"])


def lev_mark(v, h, z, label, side="r", below=False, h_from=None, value=None):
    """level datum: target symbol, bold label + elevation. below=True puts both texts under."""
    p = Paper(v.c)
    if h_from is not None:
        v.line((h_from, z), (h, z), lw="fine", dash="center")
    px, py = v.to_paper((h, z))
    r = 0.065
    p.circle((px, py), r, lw="thin", fill="white")
    c = v.c
    from reportlab.lib.colors import black as _blk
    c.setFillColor(_blk)
    for a0 in (0, 180):
        path = c.beginPath()
        path.moveTo(px * PT, py * PT)
        path.arcTo((px - r) * PT, (py - r) * PT, (px + r) * PT, (py + r) * PT, a0, 90)
        path.close()
        c.drawPath(path, stroke=0, fill=1)
    dx = 0.12 if side == "r" else -0.12
    anc = "l" if side == "r" else "r"
    val = value or fmt_elev(z)
    if below:
        p.text((px + dx, py - 0.03), label, size=TXT["small"], font=FONT_B, anchor=anc, valign="top")
        p.text((px + dx, py - 0.135), val, size=TXT["small"], anchor=anc, valign="top")
    else:
        p.text((px + dx, py + 0.035), label, size=TXT["small"], font=FONT_B, anchor=anc, valign="bot")
        p.text((px + dx, py - 0.03), val, size=TXT["small"], anchor=anc, valign="top")


def levels_column(v, h_mark, h_from, items, side="r"):
    """level datum markers. items: [(z, label)]; a level closer than 1/4\" (paper) above the
    previous one keeps its text above, the lower one moves below."""
    zs = sorted(items)
    for i, (z, lab) in enumerate(zs):
        below = False
        if i + 1 < len(zs) and v.L(zs[i + 1][0] - z) / PT < 0.3:
            below = True
        lev_mark(v, h_mark, z, lab, side=side, below=below, h_from=h_from)


def rtu_beyond(v, h0, h1, z_roof):
    R(v, h0 + 0.5, z_roof, h1 - 0.5, z_roof + 14 * IN, lw="fine", dash="hidden")
    R(v, h0 + 0.8, z_roof + 14 * IN, h1 - 0.8, RTU_TOP, lw="fine", dash="hidden")


def existing_fragment(v, h0, h1, z_top=EX_ROOF, label=True, brk_at=None, lab_at=None):
    """screened existing building face between h0 and h1, break line at brk_at"""
    R(v, h0, GRADE, h1, z_top, lw="thin", color="screen", fill="white")
    g = box(min(h0, h1), GRADE, max(h0, h1), z_top - 1.0)
    running_bond(v, g, 8 * IN, 16 * IN, col=0.8)
    R(v, h0, z_top - 1.0, h1, z_top + 0.33, lw="thin", color="screen", fill="g05")
    if brk_at is not None:
        p0, p1 = (brk_at, GRADE - 1.0), (brk_at, z_top + 2.0)
        v.line((brk_at, GRADE), (brk_at, z_top + 0.33), lw=3.0, color="white")
        break_line(v, p0, p1, zig=0.1)


# =============================================================================================
# Shared annotation for elevations
# =============================================================================================
LEVEL_ITEMS = [(TOF, "T.O. FOOTING"), (GRADE, "FIN. GRADE / T.O. FDN."), (L1, "LEVEL 1 FFE"),
               (L2, "LEVEL 2"), (ROOF, "ROOF (T.O. STEEL)"), (PARAPET, "T.O. PARAPET")]

ELEV_KEYNOTES = {
    1: "BRICK EXPANSION JOINT (EJ): 3/8\" OPEN JOINT W/ BACKER ROD + SEALANT, FULL HEIGHT FROM BRICK "
       "LEDGE TO UNDERSIDE OF COPING, THROUGH CS-2 BAND AND SHELF ANGLE. ALIGN CMU CONTROL JOINT. "
       f"SEE {D_EJ}/A-501.",
    2: "ROOFTOP UNIT BEYOND (DIV. 23) ON 14'-0\" x 7'-0\" CURB, SHOWN DASHED. SEE A-103.",
    3: "ROOF HATCH 30\"x36\" BEYOND, BELOW TOP OF PARAPET, SHOWN DASHED. SEE A-103.",
    4: "FINISH GRADE AT BUILDING 99'-4\" (CIVIL 711.83). SLOPE AWAY 5% MIN. FOR 10'-0\", SEE C-300.",
    5: "CONTINUOUS FOOTING, FOUNDATION WALL AND COLUMN FOOTINGS BELOW GRADE, SHOWN DASHED. SEE S-101 / S-301.",
    6: "CONCRETE STOOP / WALK AT EXTERIOR DOOR, TOP 1/2\" BELOW FFE, SLOPE 1/8\":12 AWAY. SEE C-200.",
    7: "ISOLATION JOINT AT EXISTING BUILDING: 3/4\" COMPRESSIBLE FILLER, BACKER ROD + SEALANT, FULL HEIGHT.",
    8: "SCUPPER, CONDUCTOR HEAD AND 4\"x4\" DOWNSPOUT (MF-1) AT x = -10'-0\" PER A-103; DISCHARGE TO "
       "SPLASH BLOCK. COORDINATE DOWNSPOUT STRAPS WITH SF-3 MULLIONS.",
    9: "8\" EXPOSED CONCRETE CURB UNDER SF-3 (99'-4\" TO 100'-0\"), RUBBED FINISH. SEE A-312.",
    10: "EXISTING BUILDING (NO WORK), SHOWN SCREENED.",
    11: "LINK PARAPET: T.O. MASONRY 116'-8\", MC-1 COPING. LINK ROOF T.O. STEEL 114'-0\".",
    12: "LOUVER LV-1 FURNISHED BY DIV. 23; OPENING, LOOSE LINTEL, MF-1 SILL FLASHING AND SEALANT BY GC.",
    13: "W-C STAIR STOREFRONT, TEMPERED GLAZING: INTERMEDIATE LANDING (107'-0\") BEYOND. CS-2 BAND AND "
        "SHELF ANGLE TERMINATE AT W-C JAMBS WITH END DAMS.",
    14: "CORRIDOR-END WALL ABOVE LINK ROOF: BRICK ON SHELF ANGLE AT 114'-1 7/8\"; EPDM BASE FLASHING "
        f"8\" MIN. W/ SS COUNTERFLASHING IN BRICK REGLET. SEE {D_LINKROOF}/A-501.",
    15: "LINK SHOWN IN SECTION AT EXISTING BUILDING FACE (x = -35'-6\"); EXISTING BUILDING IN FOREGROUND "
        "NOT SHOWN FOR CLARITY.",
}

GENERAL_ELEV_NOTES = [
    "ELEVATIONS ARE DRAWN TO THE FACE OF BRICK. ALL ELEVATIONS ARE ARCHITECTURAL DATUM: LEVEL 1 FFE "
    "100'-0\" = CIVIL 712.50 (NAVD88).",
    "OPENING SIZES ARE MASONRY OPENINGS (MO). HORIZONTAL OPENING LOCATIONS ARE DIMENSIONED ON A-101 / "
    "A-102; WINDOW AND STOREFRONT TYPES, FRAME ELEVATIONS AND GLAZING ON A-711.",
    "BRICK COURSING: 3 COURSES = 8\". SET OUT COURSING FROM T.O. FOUNDATION WALL 99'-4\". ALL HEADS, "
    "SILLS, BANDS AND PARAPETS ARE ON THE 8\" MODULE.",
    "FB-1 HATCH IS DRAWN AT A 3-COURSE (8\") MODULE FOR CLARITY; UNITS ARE MODULAR 3 5/8\" x 2 1/4\" x "
    "7 5/8\" LAID IN RUNNING BOND WITH 3/8\" CONCAVE JOINTS, TYPE N MORTAR.",
    "FB-2 SOLDIER COURSE (8\" HIGH) DIRECTLY ABOVE EVERY W-A, W-B AND SF-2 HEAD, LENGTH = MO WIDTH. "
    "FB-2 BASE BAND = 6 COURSES (99'-4\" TO 100'-8\") WHEREVER BRICK OCCURS AT GRADE.",
    "CS-1 SILL UNDER EVERY W-A, W-B AND SF-2: 4\" HIGH x 1\" PROJECTION, LENGTH = MO + 6\" (3\" "
    "BEARING EACH END). CS-2 BAND 8\" HIGH (113'-4\" TO 114'-0\") CONTINUOUS ON ALL MAIN FACES.",
    "BRICK EXPANSION JOINTS (EJ) AT 25'-0\" MAX. AND WITHIN 4'-0\" OF EACH OUTSIDE CORNER (ON ONE "
    "FACE); LOCATIONS ARE DIMENSIONED FROM GRID LINES BELOW EACH ELEVATION. CMU CONTROL JOINTS IN THE "
    "BACKUP ALIGN WITH EJ (24'-0\" MAX.).",
    "PROVIDE LOOSE STEEL LINTELS AT BRICK AND CMU BOND BEAM LINTELS OVER ALL OPENINGS PER S-302 LINTEL "
    "SCHEDULE. THROUGH-WALL FLASHING WITH END DAMS AND WEEPS @ 24\" O.C. AT BASE, LINTELS, SILLS AND "
    "SHELF ANGLES (SEE A-501).",
    "ROOFTOP EQUIPMENT AND ROOF HATCH ARE SHOWN DASHED FOR COORDINATION; SEE A-103. NO EQUIPMENT "
    "SCREENS IN CONTRACT.",
    "EXISTING CONSTRUCTION IS SHOWN SCREENED. FIELD VERIFY EXISTING ROOF AND GRADE ELEVATIONS AT THE "
    "TIE-IN BEFORE FABRICATION.",
    "SEALANT: SILICONE AT ALL WINDOW AND STOREFRONT PERIMETERS (BOTH SIDES), POLYURETHANE AT MASONRY "
    "EXPANSION / ISOLATION JOINTS, COLOR TO MATCH ADJACENT MATERIAL.",
]

MATERIALS = [
    ("FB-1", "FACE BRICK - FIELD: MODULAR (3 5/8\"x2 1/4\"x7 5/8\"), RUNNING BOND, ASTM C216 GRADE SW, "
             "TYPE FBS, VELOUR TEXTURE, RED RANGE."),
    ("FB-2", "FACE BRICK - ACCENT: MODULAR, SMOOTH, CHARCOAL. 6-COURSE BASE BAND AND 8\" SOLDIER "
             "COURSES ABOVE W-A / W-B / SF-2."),
    ("CS-1", "CAST STONE SILL (ASTM C1364), 4\" HIGH, 1\" PROJECTION, SLOPED WASH, DRIP, LUG ENDS."),
    ("CS-2", "CAST STONE BAND (ASTM C1364), 8\" HIGH x 3 5/8\" BED, ON L6x4x3/8 GALV. SHELF ANGLE."),
    ("MC-1", "PREFINISHED METAL COPING, 24 GA. GALV. STEEL, KYNAR 500, CONT. CLEATS, ON PT WOOD BLOCKING."),
    ("MF-1", "PREFINISHED SHEET METAL: SCUPPER, CONDUCTOR HEAD, DOWNSPOUT, W-C / LV-1 SILL FLASHING."),
    ("AL-1", "ALUMINUM WINDOWS / STOREFRONT, THERMALLY BROKEN, CLASS I CLEAR ANODIZED (A-711)."),
    ("HM", "HOLLOW METAL DOOR AND FRAME, PAINTED (A-701)."),
    ("CONC", "EXPOSED CONCRETE (SF-3 CURB, STOOPS), RUBBED FINISH."),
]


def material_legend(sh, x, y, width):
    sh.text((x, y), "EXTERIOR MATERIAL LEGEND", size=TXT["label"], font=FONT_B, valign="top",
            underline=True)
    yy = y - 0.3
    v = sh.view(0, 0, 1 / 8)
    sw_w, sw_h = 0.5, 0.2
    for tag, desc in MATERIALS:
        x0, y0 = x, yy - sw_h
        g = box(x0, y0, x0 + sw_w, y0 + sw_h)
        pv = sh.view(0, 0, 1.0 / 12.0 * 12)  # paper inches == model units
        if tag == "FB-1":
            running_bond(pv, g, 0.035, 0.07, z0=0, col=0.45)
        elif tag == "FB-2":
            pv.geom(g, lw=None, fill="g10", stroke=False)
            running_bond(pv, g, 0.028, 0.056, z0=0, col=0.35)
        elif tag in ("CS-1", "CS-2", "CONC"):
            stipple(pv, g, step_in=0.04, col=0.4)
        elif tag == "MC-1":
            pv.line((x0, y0 + sw_h * 0.55), (x0 + sw_w, y0 + sw_h * 0.55), lw="hair")
        elif tag == "AL-1":
            pv.line((x0 + sw_w / 2, y0), (x0 + sw_w / 2, y0 + sw_h), lw="fine")
        sh.rect(x0, y0, sw_w, sw_h, lw="thin")
        sh.text((x0 + sw_w + 0.1, yy - 0.02), tag, size=TXT["note"], font=FONT_B, valign="top")
        hgt = sh.mtext((x0 + sw_w + 0.65, yy - 0.01), desc, size=TXT["small"],
                       width=width - sw_w - 0.7, leading=TXT["small"] * 1.2)
        yy -= max(sw_h + 0.1, hgt + 0.08)
    # symbols
    yy -= 0.05
    sh.text((x, yy), "SYMBOLS", size=TXT["note"], font=FONT_B, valign="top")
    yy -= 0.25
    syms = [("win", "W-A", "WINDOW / STOREFRONT / LOUVER TYPE (A-711)"),
            ("door", "ST1-B", "DOOR NUMBER (A-701)"),
            ("key", "1", "KEYNOTE (THIS SHEET)"),
            ("ej", "EJ", "BRICK EXPANSION JOINT / CMU CONTROL JOINT"),
            ("lev", "", "LEVEL DATUM (ARCHITECTURAL ELEVATION)"),
            ("det", "", "DETAIL / WALL SECTION REFERENCE")]
    for kind, t, label in syms:
        vv = sh.view(x + 0.25, yy, 1 / 8)
        if kind == "win":
            window_tag(vv, (0, 0), t, size=TXT["small"], r=0.105)
        elif kind == "door":
            door_tag(vv, (0, 0), t, size=TXT["tiny"])
        elif kind == "key":
            keynote_tag(vv, (0, 0), t)
        elif kind == "ej":
            vv.line((0, -0.9), (0, 0.9), lw="thin")
            text_box(vv, (0, 0), "EJ", size=TXT["tiny"], font=FONT_B, pad=0.012)
        elif kind == "lev":
            level_marker(vv, 0, 0, "", side="r")
        else:
            p = Paper(sh.c)
            p.circle((x + 0.25, yy), 0.13, lw="thin", fill="white")
            p.line((x + 0.12, yy), (x + 0.38, yy), lw="fine")
            p.text((x + 0.25, yy + 0.055), "1", size=TXT["tiny"], font=FONT_B, anchor="c",
                   valign="mid")
            p.text((x + 0.25, yy - 0.06), "A-311", size=3.6 + 0.9, anchor="c", valign="mid")
        sh.text((x + 0.6, yy), label, size=TXT["small"], valign="mid")
        yy -= 0.27
    return y - yy


def keynote_list(sh, x, y, keys, width, title="ELEVATION KEYNOTES"):
    sh.text((x, y), title, size=TXT["label"], font=FONT_B, valign="top", underline=True)
    yy = y - 0.3
    for k in keys:
        t = ELEV_KEYNOTES[k]
        vv = sh.view(x + 0.12, yy - 0.06, 1 / 8)
        keynote_tag(vv, (0, 0), k)
        hgt = sh.mtext((x + 0.32, yy + 0.01), t, size=TXT["note"], width=width - 0.35)
        yy -= max(0.26, hgt + 0.07)
    return y - yy


def ej_chain(v, f: Face, grids, z):
    """horizontal dimension chain locating EJs from grid lines, below the elevation"""
    pts = sorted(set([round(f.h(a), 5) for a in f.ej()] + [round(f.h(g), 5) for _, g in grids]))
    dchain(v, [(hh, z) for hh in pts], 0.0, size=TXT["tiny"], denom=16)
    r = v.paper_len(0.085)
    for lab, g in grids:
        hh = f.h(g)
        v.line((hh, z - v.paper_len(0.05)), (hh, z - v.paper_len(0.12)), lw="hair")
        small_bubble(v, (hh, z - v.paper_len(0.12) - r), lab, r=0.085)
    for a in f.ej():
        hh = f.h(a)
        v.line((hh, z + v.paper_len(0.05)), (hh, z + v.paper_len(0.1)), lw="hair")
        v.text((hh, z + v.paper_len(0.11)), "EJ", size=TXT["tiny"], font=FONT_B, anchor="c",
               valign="bot")


# =============================================================================================
# A-201: North and South elevations
# =============================================================================================
EXIST_FRAG = 11.0       # length of existing-building fragment shown beyond the link


def ns_extents(fkey, S):
    """(h_min, h_max) of everything drawn in a N/S elevation incl. level text (model ft)"""
    f = FACES[fkey]
    lk = FACES["LN" if fkey == "N" else "LS"]
    txt = 1.15 / S
    if f.sign < 0:
        return f.h0 - 9.5 - txt, lk.h(FX) + EXIST_FRAG + 3.0 + txt
    return lk.h(FX) - EXIST_FRAG - 3.0 - txt, f.h1 + 9.5 + txt


def elevation_NS(v, fkey):
    f = FACES[fkey]
    s = f.sign
    lk = FACES["LN" if fkey == "N" else "LS"]
    X = f.h
    hx = lk.h(FX)
    brk = hx + (EXIST_FRAG if s < 0 else -EXIST_FRAG)
    existing_fragment(v, hx, brk, brk_at=brk)
    render_face(v, lk)
    rg = render_face(v, f)
    # roof items beyond (dashed)
    z_roof = ROOF + DECK + 10 * IN
    for name, x, y in RTUS:
        rtu_beyond(v, *f.hr(x - RTU_W / 2, x + RTU_W / 2), z_roof)
    hx_, hy_, hw_, hh_ = HATCH
    a, b = f.hr(hx_ - hw_ / 2, hx_ + hw_ / 2)
    R(v, a, z_roof, b, z_roof + 1.0, lw="fine", dash="hidden")
    # grade and below grade
    h_end = f.h0 if s < 0 else f.h1          # free (east) end of the building
    d = -1 if s < 0 else 1                    # outward direction at the free end
    grade_line(v, min(h_end + d * 3.0, brk - d * 3.0), max(h_end + d * 3.0, brk - d * 3.0))
    draw_below_grade(v, f, footing_x=[X(x) for x in M.GRID_X.values()])
    draw_below_grade(v, lk)
    # grids
    z_bub = RTU_TOP + 4.0
    grid_bubbles(v, [(X(x), k) for k, x in M.GRID_X.items()], 0, PARAPET + COPE_UP + 0.5, z_bub)
    grid_bubbles(v, [(lk.h(x), k) for k, x in M.LINK_GRID_X.items()], 0, LINK_PAR + 1.5,
                 LINK_PAR + 6.0, dia=0.3)
    # levels at the free end, link parapet beyond the existing fragment
    levels_column(v, h_end + d * 9.5, h_end + d * 0.6, LEVEL_ITEMS, side="r" if d > 0 else "l")
    lev_mark(v, brk - d * 3.0, LINK_PAR, "LINK T.O. PARAPET", side="l" if d > 0 else "r",
             h_from=lk.h(-OUT) - d * 0.5)
    # vertical dimensions at the free end
    dchain(v, [(h_end + d * 2.5, z) for z in (GRADE, L2, ROOF, PARAPET)], 0.0,
                size=TXT["tiny"], denom=16)
    v.dim((h_end + d * 5.0, GRADE), (h_end + d * 5.0, PARAPET), 0.0, size=TXT["tiny"])
    # opening heights at the window nearest the free end, and at W-C
    if s < 0:
        hj, ow = X(129.0), [o for o in rg["ops"] if o.id == "105-W1"][0]
        wc = [o for o in rg["ops"] if o.type == "W-C"][0]
        hc = X(148.5)
    else:
        hj, ow = X(149.3), [o for o in rg["ops"] if o.id == "115-W3"][0]
        wc = [o for o in rg["ops"] if o.type == "W-C"][0]
        hc = X(1.5)
    dchain(v, [(hj, z) for z in (L1, ow.sill, ow.head, L2, ow.sill + 14, ow.head + 14, ROOF)],
                0.0, size=TXT["tiny"], denom=16)
    dchain(v, [(hc, z) for z in (L1, wc.sill, wc.head, ROOF)], 0.0, size=TXT["tiny"], denom=16)
    # EJ locating dims
    zc = BOF - 3.4
    ej_chain(v, f, list(M.GRID_X.items()), zc)
    ej_chain(v, lk, list(M.LINK_GRID_X.items()) + [("1", 0.0)], zc)
    # ---- material tags ----
    mat_tag(v, (X(66.0), 127.4), (X(66.0), 127.4), "FB-1", arrow=False)
    mat_tag(v, (X(75.0), 123.75), (X(75.0), 127.4), "FB-2")
    mat_tag(v, (X(87.5), 118.2), (X(90.0), 115.2), "AL-1")
    mat_tag(v, (X(71.3), 102.5), (X(68.0), 101.5), "CS-1")
    mat_tag(v, (X(105.0), CS2_BOT + 0.3), (X(105.0), 111.7), "CS-2")
    mat_tag(v, (X(112.0), 100.2), (X(112.0), 97.7), "FB-2")
    mat_tag(v, (X(84.0), PARAPET + 0.1), (X(84.0), PARAPET + 2.8), "MC-1")
    # ---- keynotes ----
    key_tag(v, (X(79 + 8 * IN) - d * 2.4 * -1, 128.2), 1, target=(X(79 + 8 * IN), 128.2))
    key_tag(v, (X(56.0), RTU_TOP + 1.2), 2, target=(X(51.6), RTU_TOP - 0.4))
    key_tag(v, (X(41.0), 127.2), 3, target=(X(45.6), z_roof + 0.6))
    key_tag(v, (h_end - d * 4.0, GRADE - 2.0), 4, target=(h_end - d * 1.6, GRADE))
    key_tag(v, (X(68.0), 97.7), 5)
    key_tag(v, (lk.h(-26.0), GRADE - 2.0), 9, target=(lk.h(-26.0), GRADE + 0.35))
    key_tag(v, (hx - d * 2.6, 111.5), 7, target=(hx, 110.0))
    key_tag(v, (lk.h(-24.0), LINK_PAR + 2.6), 11, target=(lk.h(-24.0), LINK_PAR + 0.15))
    key_tag(v, ((hx + brk) / 2, 106.0), 10)
    wch = X(wc.c)
    kd = 1 if hc < wch else -1
    key_tag(v, (wch + kd * 4.6, 125.6), 13, target=(wch + kd * 1.6, 120.0))
    return f, lk, rg, brk


def draw_scupper(v, f, x=SCUPPER_X):
    """scupper through link north parapet + conductor head + downspout to splash block"""
    hh = f.h(x)
    zt = LINK_ROOF + DECK + LINK_INS_MIN + COVER
    R(v, hh - 6 * IN, zt, hh + 6 * IN, zt + 4 * IN, lw="thin", fill="white")      # scupper opening
    v.polygon([(hh - 9 * IN, zt - 2 * IN), (hh + 9 * IN, zt - 2 * IN), (hh + 6 * IN, zt - 16 * IN),
               (hh + 2 * IN, zt - 20 * IN), (hh - 2 * IN, zt - 20 * IN), (hh - 6 * IN, zt - 16 * IN)],
              lw="thin", fill="white")
    R(v, hh - 2 * IN, GRADE + 6 * IN, hh + 2 * IN, zt - 20 * IN, lw="thin", fill="white")
    z = zt - 20 * IN - 3.0
    while z > GRADE + 1.0:
        v.line((hh - 3 * IN, z), (hh + 3 * IN, z), lw="fine")
        z -= 4.0
    v.polygon([(hh - 2 * IN, GRADE + 6 * IN), (hh + 2 * IN, GRADE + 6 * IN),
               (hh + 8 * IN, GRADE + 1 * IN), (hh - 4 * IN, GRADE + 1 * IN)], lw="thin", fill="white")
    R(v, hh - 1.0, GRADE, hh + 1.5, GRADE + 2 * IN, lw="fine", fill="white")


def typical_bay(sh, v, x0=60.0, x1=90.0):
    """enlarged partial north elevation of one classroom bay with true coursing"""
    f = FACES["N"].cropped(x0 - 1.5, x1 + 1.5)
    X = f.h
    render_face(v, f, fine=True, ej_labels=True, door_tags=False)
    for a in (f.a0, f.a1):
        hh = X(a)
        break_line(v, (hh, GRADE - 1.0), (hh, PARAPET + COPE_UP + 1.0), zig=0.1)
    grade_line(v, X(f.a1) + 0.3, X(f.a0) - 0.3)
    grid_bubbles(v, [(X(60.0), "3"), (X(90.0), "4")], 0, PARAPET + COPE_UP + 0.4,
                 PARAPET + COPE_UP + 2.6, dia=0.28)
    ops = sorted([o for o in f.openings() if o.level == "L1"], key=lambda o: o.c)
    pts = [x0, x1] + [p for o in ops for p in (o.lo, o.hi)]
    zb = GRADE - 1.6
    dchain(v, [(X(p), zb) for p in sorted(pts)], 0.0, size=TXT["tiny"], denom=16)
    ejp = [x0, x1] + f.ej()
    dchain(v, [(X(p), zb - 1.7) for p in sorted(set(ejp))], 0.0, size=TXT["tiny"], denom=16)
    for a in f.ej():
        v.line((X(a), zb - 1.7 + v.paper_len(0.05)), (X(a), zb - 1.7 + v.paper_len(0.1)), lw="hair")
        v.text((X(a), zb - 1.7 + v.paper_len(0.11)), "EJ", size=TXT["tiny"], font=FONT_B,
               anchor="c", valign="bot")
    o = ops[0]
    # vertical chain (all masonry datums) at the left (east) side
    hz = X(f.a1) - 3.2
    zs = [GRADE, BASE_TOP, o.sill - CS1_H, o.sill, o.head, o.head + SOLDIER, CS2_BOT, L2,
          o.sill + 14 - CS1_H, o.sill + 14, o.head + 14, o.head + 14 + SOLDIER, PARAPET - COPE_DROP,
          PARAPET]
    dchain(v, [(hz, z) for z in zs], 0.0, size=TXT["tiny"], denom=16)
    levels_column(v, X(f.a0) + 3.0, X(f.a0) + 0.3,
                  [(GRADE, "GRADE"), (L1, "LEVEL 1"), (L2, "LEVEL 2"), (ROOF, "ROOF"),
                   (PARAPET, "T.O. PARAPET")], side="r")
    # notes
    mat_tag(v, (X(75.0), 109.7), (X(75.0), 111.6), "FB-2")
    mat_tag(v, (X(70.2), 102.5), (X(70.2), 101.4), "CS-1")
    mat_tag(v, (X(84.5), CS2_BOT + 0.3), (X(84.5), 111.6), "CS-2")
    mat_tag(v, (X(66.0), 100.2), (X(66.0), 101.4), "FB-2")
    mat_tag(v, (X(65.6), 127.5), (X(65.6), 127.5), "FB-1", arrow=False)
    mat_tag(v, (X(73.0), PARAPET + 0.15), (X(73.0), PARAPET + 2.6), "MC-1")


def draw_a201(sh):
    S = 1 / 8
    xc = (sh.x0 + sh.x1) / 2
    vs = []
    y_top = sh.y1 - 0.38
    for num, fkey, name in ((1, "N", "NORTH ELEVATION"), (2, "S", "SOUTH ELEVATION")):
        hmin, hmax = ns_extents(fkey, S)
        ox = xc - (hmin + hmax) / 2 * S
        oy = y_top - (RTU_TOP + 4.0 + 1.2 - L1) * S
        v = sh.view(ox, oy, S, mx=0.0, my=L1)
        f, lk, rg, brk = elevation_NS(v, fkey)
        if fkey == "N":
            draw_scupper(v, lk)
            key_tag(v, (lk.h(SCUPPER_X) + 2.8, 112.6), 8, target=(lk.h(SCUPPER_X) + 0.6, 113.3))
        else:
            key_tag(v, (f.h(50.0) - 3.2, 113.0), 12, target=(f.h(48.6), 111.6))
            st = [o for o in rg["ops"] if o.kind == "door"][0]
            key_tag(v, (f.h(st.hi) + 3.0, GRADE - 2.0), 6, target=(f.h(st.hi) + 0.6, GRADE + 0.3))
        ty = v.to_paper((0, BOF - 7.0))[1]
        tx = v.to_paper((min(f.h0, brk), 0))[0]
        sh.view_title(tx, ty, num, name, S, width=6.5)
        y_top = ty - 0.5
    # ---- bottom band: legend | typical bay | keynotes | notes ----
    top = y_top - 0.05
    sh.line((sh.x0, top + 0.17), (sh.x1, top + 0.17), lw="thin")
    material_legend(sh, sh.x0 + 0.3, top, 6.6)
    S3 = 3 / 16
    bx = sh.x0 + 7.5
    v3 = sh.view(bx + (91.5 + 5.5) * S3, sh.y0 + 0.95 + (L1 - (GRADE - 3.6)) * S3, S3,
                 mx=0.0, my=L1)
    typical_bay(sh, v3)
    sh.view_title(bx + 0.3, sh.y0 + 0.5, 3, "TYPICAL CLASSROOM BAY - ENLARGED ELEVATION", S3,
                  width=6.6, note="GRID 3-4, NORTH")
    keynote_list(sh, sh.x0 + 16.4, top, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13], 7.3)
    notes_block(sh, sh.x0 + 24.1, top, "GENERAL ELEVATION NOTES", GENERAL_ELEV_NOTES, 7.0)


# =============================================================================================
# Cut exterior wall (EW-1) for elevations / building sections
# =============================================================================================
FDN_IN, FDN_OUT = -4.1875 * IN, 11.8125 * IN    # 12" wall + 4" brick ledge (10/A-501)
FTG_C = (FDN_IN + FDN_OUT) / 2                   # footing centered on the foundation wall
FTG_W = 30 * IN


def _U(hg, se, u):
    return hg + se * u


CMU_SPANDREL_GAP = (112.0, L2)    # CMU stops at 112'-0" under the L2 spandrel on grid (9/A-501)


def ew_cut(v, hg, se, z_top, z_bot=BOF, cs2=False, coping=True, z_break=None, footing=True,
           holes=(), brick_from=LEDGE, cmu_from=GRADE, lw_cut="heavy", detail=False, cmu_gaps=()):
    """EW-1 cut in section. hg = h of the grid (CMU centerline), se = +1/-1 direction of the
    exterior in h. holes: [(z0, z1)] openings through the whole wall (windows)."""
    U = lambda u: hg + se * u
    zt = z_break if z_break is not None else z_top

    def band(u0, u1, z0, z1):
        a, b = sorted((U(u0), U(u1)))
        g = box(a, z0, b, z1)
        for (h0, h1) in holes:
            g = g.difference(box(a - 1, h0, b + 1, h1))
        return g

    hk = dict(spacing=0.03, w="hair")
    if footing and z_bot < TOF:
        g = band(FTG_C - FTG_W / 2, FTG_C + FTG_W / 2, BOF, TOF)
        v.geom(g, lw=lw_cut, fill="white", hatch="concrete", hatch_kw=dict(scale=0.6))
        # foundation wall + brick ledge haunch
        pts = [(U(FDN_IN), TOF), (U(FDN_OUT), TOF), (U(FDN_OUT), LEDGE), (U(EW_AIR_OUT), LEDGE),
               (U(EW_AIR_OUT), GRADE), (U(FDN_IN), GRADE)]
        v.polygon(pts, lw=lw_cut, fill="white", hatch="concrete", hatch_kw=dict(scale=0.6))
    # CMU
    g = band(-CMUh, CMUh, cmu_from, zt)
    for (c0, c1) in cmu_gaps:
        g = g.difference(box(U(-CMUh) - 1, c0, U(CMUh) + 1, c1))
    v.geom(g, lw=None, fill="white", hatch="ansi31", hatch_kw=hk, stroke=False)
    # insulation
    gi = band(CMUh, CMUh + 2 * IN, cmu_from, zt)
    v.geom(gi, lw="fine", fill="g15")
    # brick (with CS-2 band)
    gb = band(EW_AIR_OUT, OUT, brick_from, zt)
    gcs = Polygon()
    if cs2:
        gcs = band(EW_AIR_OUT, OUT, CS2_BOT, CS2_TOP)
        gb = gb.difference(gcs)
    v.geom(gb, lw=None, fill="white", hatch="ansi31", hatch_kw=dict(spacing=0.018, w="hair"),
           stroke=False)
    if not gcs.is_empty:
        v.geom(gcs, lw="thin", fill="white")
        stipple(v, gcs, step_in=0.025, col=0.4, r_pt=0.2)
    for gg in (g, gb):
        v.geom(gg, lw=lw_cut)
    if coping and z_break is None:
        # (2) layers PT blocking + coping
        a, b = sorted((U(-CMUh), U(OUT)))
        R(v, a, z_top, b, z_top + 5.0 * IN, lw="fine", fill="white", hatch="wood")
        v.polyline([(U(-CMUh - 1.3 * IN), z_top - 1.5 * IN), (U(-CMUh - 1.3 * IN), z_top + 5.0 * IN),
                    (U(OUT + 1.0 * IN), z_top + 5.4 * IN), (U(OUT + 1.0 * IN), z_top - COPE_DROP)],
                   lw="thin")
    if z_break is not None:
        a, b = sorted((U(-CMUh - 6 * IN), U(OUT + 6 * IN)))
        break_line(v, (a, z_break), (b, z_break), zig=0.08)


EW_AIR_OUT = M.EW_LAYERS[3][1]          # back of brick (+7 13/16")


def earth(v, h0, h1, z0, z1):
    """compacted earth / subgrade (light, sparse)"""
    g = box(min(h0, h1), z0, max(h0, h1), z1)
    v.geom(g, lw=None, hatch="earth", hatch_kw=dict(spacing=0.2, col=_col(0.55)), stroke=False)


# =============================================================================================
# A-202: East / West elevations, link elevations
# =============================================================================================
def elevation_E(v):
    f = FACES["E"]
    X = f.h
    # existing building beyond (screened) at both sides
    for h0, h1 in ((-OUT - 6.0, -OUT), (72 + OUT, 72 + OUT + 6.0)):
        R(v, h0, GRADE, h1, EX_ROOF, lw="thin", color="screen", fill="white")
        running_bond(v, box(h0, GRADE, h1, EX_ROOF - 1.0), 8 * IN, 16 * IN, col=0.8)
        R(v, h0, EX_ROOF - 1.0, h1, EX_ROOF + 0.33, lw="thin", color="screen", fill="g05")
        hb = h0 if h0 < 0 else h1
        break_line(v, (hb, GRADE - 1.0), (hb, EX_ROOF + 2.0), zig=0.1)
    rg = render_face(v, f)
    z_roof = ROOF + DECK + 10 * IN
    for name, x, y in RTUS:
        if name != "RTU-1":
            rtu_beyond(v, *f.hr(y - RTU_D / 2, y + RTU_D / 2), z_roof)
    a, b = f.hr(HATCH[1] - HATCH[3] / 2, HATCH[1] + HATCH[3] / 2)
    R(v, a, z_roof, b, z_roof + 1.0, lw="fine", dash="hidden")
    grade_line(v, f.h0 - 8.0, f.h1 + 8.0)
    draw_below_grade(v, f, footing_x=[X(y) for y in M.GRID_Y.values()])
    grid_bubbles(v, [(X(y), k) for k, y in M.GRID_Y.items()], 0, PARAPET + COPE_UP + 0.5,
                 RTU_TOP + 4.0)
    levels_column(v, f.h1 + 6.0 + 9.0, f.h1 + 0.6, LEVEL_ITEMS, side="r")
    # dims: overall + floor to floor at the north end; openings in piers
    dchain(v, [(f.h1 + 6.0 + 2.5, z) for z in (GRADE, L2, ROOF, PARAPET)], 0.0, size=TXT["tiny"],
                denom=16)
    v.dim((f.h1 + 6.0 + 5.0, GRADE), (f.h1 + 6.0 + 5.0, PARAPET), 0.0, size=TXT["tiny"])
    ow = M.OPENING_BY_ID["115-W4"]
    dchain(v, [(X(9.0), z) for z in (L1, ow.sill, ow.head, L2, ow.sill + 14, ow.head + 14, ROOF)],
                0.0, size=TXT["tiny"], denom=16)
    sf1, sf2 = M.OPENING_BY_ID["100-SF"], M.OPENING_BY_ID["200-W1"]
    dchain(v, [(X(42.8), z) for z in (L1, SF_TRANSOM[0], sf1.head, L2, sf2.sill, sf2.head, ROOF)],
                0.0, size=TXT["tiny"], denom=16)
    dr = M.OPENING_BY_ID["ST2-B"]
    dchain(v, [(X(48.6), z) for z in (L1, dr.head)], 0.0, size=TXT["tiny"], denom=16)
    ej_chain(v, f, list(M.GRID_Y.items()), BOF - 3.4)
    # tags
    mat_tag(v, (X(5.0), 127.4), (X(5.0), 127.4), "FB-1", arrow=False)
    mat_tag(v, (X(36.0), sf2.head + 0.35), (X(36.0), 127.3), "FB-2")
    mat_tag(v, (X(33.0), sf2.sill - 0.15), (X(27.0), 115.2), "CS-1")
    mat_tag(v, (X(60.0), CS2_BOT + 0.3), (X(60.0), 111.6), "CS-2")
    mat_tag(v, (X(60.0), 100.3), (X(60.0), 97.7), "FB-2")
    mat_tag(v, (X(62.0), PARAPET + 0.1), (X(62.0), PARAPET + 2.8), "MC-1")
    mat_tag(v, (X(32.4), 104.0), (X(27.0), 104.0), "AL-1")
    mat_tag(v, (X(46.0), 104.0), (X(52.5), 104.0), "HM")
    key_tag(v, (X(25.0) + 2.4, 128.2), 1, target=(X(25.0), 128.2))
    key_tag(v, (X(22.0), RTU_TOP + 1.0), 2, target=(X(18.0), RTU_TOP - 0.5))
    key_tag(v, (X(36.0), GRADE - 2.0), 6, target=(X(36.0), GRADE + 0.3))
    key_tag(v, (X(-OUT - 3.0), 106.0), 10)
    key_tag(v, (X(12.0), 97.7), 5)
    return f, rg


def link_section_cut(v, hs=-1, x_cut=FX + 0.5, detail=False):
    """link cut transversely (plane x = x_cut) for the west elevation / link section.
    hs: h = hs * y."""
    H = lambda y: hs * y
    # walls LN (y = 42, exterior +y) and LS (y = 30, exterior -y)
    for yg, ext in ((42.0, +1), (30.0, -1)):
        ew_cut(v, H(yg), hs * ext, LINK_PAR, lw_cut="heavy")
    # slab on grade + base
    a, b = sorted((H(30 + CMUh), H(42 - CMUh)))
    R(v, a, L1 - 5 * IN, b, L1, lw="heavy", fill="white", hatch="concrete",
      hatch_kw=dict(scale=0.6))
    R(v, a, L1 - 11 * IN, b, L1 - 5 * IN, lw="fine", fill="white", hatch="gravel",
      hatch_kw=dict(scale=0.5))
    earth(v, a, b, BOF, L1 - 11 * IN)
    # roof: beams (cut), deck, insulation, membrane
    for yg, ext in ((42.0, +1), (30.0, -1)):
        hb = H(yg - ext * (CMUh + 0.5 * IN + 2.0 * IN))
        ibeam(v, hb, LINK_ROOF - 2.5 * IN, 12 * IN, 4.0 * IN, lw="thin")
    zt = LINK_ROOF + DECK
    R(v, a, LINK_ROOF, b, zt, lw="thin", fill="g40")
    ins_lo, ins_hi = LINK_INS_MIN, LINK_INS_MIN + 0.25 * (12 - 2 * CMUh) * IN
    pN, pS = H(42 - CMUh), H(30 + CMUh)
    v.polygon([(pS, zt), (pN, zt), (pN, zt + ins_lo), (pS, zt + ins_hi)], lw="fine", fill="white",
              hatch="insul", hatch_kw=dict(spacing=0.07, w="hair", col=_col(0.4)))
    v.polyline([(pS, zt + ins_hi + COVER), (pN, zt + ins_lo + COVER)], lw="med")
    # base flashing up the parapets
    for pp, zz in ((pN, zt + ins_lo + COVER), (pS, zt + ins_hi + COVER)):
        v.line((pp, zz), (pp, LINK_PAR), lw="med")
    # joist beyond (12K1)
    jb0, jb1 = sorted((H(30 + CMUh + 0.6), H(42 - CMUh - 0.6)))
    joist_elev(v, jb0, jb1, LINK_ROOF, 12 * IN, panel=2.0)
    # ceiling
    R(v, a, 109.5 - 0.06, b, 109.5, lw="thin", fill="g30")
    return a, b


def ibeam(v, hc, z_top, d, bf, lw="thin", fill="white"):
    tf = max(0.4 * IN, d * 0.04)
    tw = max(0.25 * IN, d * 0.025)
    pts = [(hc - bf / 2, z_top), (hc + bf / 2, z_top), (hc + bf / 2, z_top - tf), (hc + tw / 2, z_top - tf),
           (hc + tw / 2, z_top - d + tf), (hc + bf / 2, z_top - d + tf), (hc + bf / 2, z_top - d),
           (hc - bf / 2, z_top - d), (hc - bf / 2, z_top - d + tf), (hc - tw / 2, z_top - d + tf),
           (hc - tw / 2, z_top - tf), (hc - bf / 2, z_top - tf)]
    v.polygon(pts, lw=lw, fill="black" if fill == "black" else "white")


def joist_elev(v, h0, h1, z_top, d, panel=2.0, lw="fine", color="black", seat=2.5 * IN):
    """open-web steel joist in elevation between bearings h0..h1 (top chord at z_top)"""
    ch = 1.5 * IN
    zb = z_top - d
    v.line((h0, z_top), (h1, z_top), lw=lw, color=color)
    v.line((h0, z_top - ch), (h1, z_top - ch), lw=lw, color=color)
    g0, g1 = h0 + 0.5, h1 - 0.5
    if g1 > g0:
        v.line((g0, zb), (g1, zb), lw=lw, color=color)
        v.line((g0, zb + ch), (g1, zb + ch), lw=lw, color=color)
        n = max(2, int(round((g1 - g0) / panel)))
        pts = []
        for i in range(n + 1):
            hh = g0 + (g1 - g0) * i / n
            pts.append((hh, zb + ch if i % 2 == 0 else z_top - ch))
        v.polyline([(h0, z_top - ch)] + pts + [(h1, z_top - ch)], lw="hair", color=color)
    # seats
    for hh, sgn in ((h0, 1), (h1, -1)):
        v.polyline([(hh, z_top), (hh, z_top - seat), (hh + sgn * 0.33, z_top - seat)], lw=lw,
                   color=color)


def elevation_W(v):
    f = FACES["W"]
    X = f.h
    rg = render_face(v, f)
    # roof flashing band on W0 between the link roof and the shelf angle
    a, b = sorted((X(30 + CMUh), X(42 - CMUh)))
    z_lr = LINK_ROOF + DECK + LINK_INS_MIN + COVER
    R(v, a, z_lr, b, W0_SHELF, lw="fine", fill="g20")
    # CMU X0 wall inside the link (interior elevation beyond) + cross-corridor doors 100A
    R(v, a, L1, b, 109.5, lw="fine", fill="white")
    d100 = M.OPENING_BY_ID["100A"]
    hl, hr = sorted((X(d100.lo), X(d100.hi)))
    draw_door_elev(v, d100, hl, hr, tag=False)
    door_tag(v, ((hl + hr) / 2, 104.8), "100A", size=TXT["tiny"])
    # link in section (plane x = -35'-6")
    la, lb = link_section_cut(v, hs=-1)
    z_roof = ROOF + DECK + 10 * IN
    for name, x, y in RTUS:
        if name != "RTU-2":
            rtu_beyond(v, *f.hr(y - RTU_D / 2, y + RTU_D / 2), z_roof)
    a2, b2 = f.hr(HATCH[1] - HATCH[3] / 2, HATCH[1] + HATCH[3] / 2)
    R(v, a2, z_roof, b2, z_roof + 1.0, lw="fine", dash="hidden")
    grade_line(v, f.h0 - 6.0, X(42 + OUT + 0.5))
    grade_line(v, X(30 - OUT - 0.5), f.h1 + 6.0)
    draw_below_grade(v, FACES["W"].cropped(42 + OUT, 72 + OUT), footing_x=[X(72.0)])
    draw_below_grade(v, FACES["W"].cropped(-OUT, 30 - OUT), footing_x=[X(0.0)])
    for hh, z in ((X(-OUT) + 1.0, EX_ROOF), (X(72 + OUT) - 1.0, EX_ROOF)):
        pass
    for h0, h1 in ((f.h0 - 7.0, f.h0 - 0.3), (f.h1 + 0.3, f.h1 + 7.0)):
        v.line((h0, EX_ROOF), (h1, EX_ROOF), lw="thin", color="screen", dash="phantom")
    text_box(v, (f.h0 - 3.8, EX_ROOF + 1.6), "EXIST. ROOF\n(FOREGROUND)", size=TXT["tiny"],
             color=SCREEN)
    grid_bubbles(v, [(X(y), k) for k, y in M.GRID_Y.items()], 0, PARAPET + COPE_UP + 0.5,
                 RTU_TOP + 4.0)
    levels_column(v, f.h1 + 6.0 + 9.0, f.h1 + 0.6,
                  LEVEL_ITEMS + [(LINK_PAR, "LINK T.O. PARAPET")], side="r")
    dchain(v, [(f.h1 + 6.0 + 2.5, z) for z in (GRADE, L2, ROOF, PARAPET)], 0.0, size=TXT["tiny"],
                denom=16)
    v.dim((f.h1 + 6.0 + 5.0, GRADE), (f.h1 + 6.0 + 5.0, PARAPET), 0.0, size=TXT["tiny"])
    ow = M.OPENING_BY_ID["101-W4"]
    dchain(v, [(X(61.6), z) for z in (L1, ow.sill, ow.head, L2, ow.sill + 14, ow.head + 14, ROOF)],
                0.0, size=TXT["tiny"], denom=16)
    sf2 = M.OPENING_BY_ID["200-W2"]
    dchain(v, [(X(49.5), z) for z in (W0_SHELF, sf2.sill, sf2.head, ROOF)], 0.0, size=TXT["tiny"],
                denom=16)
    dr = M.OPENING_BY_ID["ST1-B"]
    dchain(v, [(X(21.6), z) for z in (L1, dr.head)], 0.0, size=TXT["tiny"], denom=16)
    ej_chain(v, f, list(M.GRID_Y.items()), BOF - 3.4)
    # tags & keynotes
    mat_tag(v, (X(10.0), 127.4), (X(10.0), 127.4), "FB-1", arrow=False)
    mat_tag(v, (X(36.0), sf2.head + 0.35), (X(36.0), 127.3), "FB-2")
    mat_tag(v, (X(40.0), sf2.sill - 0.15), (X(46.0), 115.2) if False else (X(50.0), 117.0), "CS-1")
    mat_tag(v, (X(12.0), CS2_BOT + 0.3), (X(12.0), 111.6), "CS-2")
    mat_tag(v, (X(12.0), 100.3), (X(12.0), 97.7), "FB-2")
    mat_tag(v, (X(64.0), PARAPET + 0.1), (X(64.0), PARAPET + 2.8), "MC-1")
    key_tag(v, (X(46.0) - 2.4, 128.2), 1, target=(X(46.0), 128.2))
    key_tag(v, (X(22.0) - 3.2, GRADE - 2.0), 6, target=(X(dr.lo) + 0.4, GRADE + 0.3))
    key_tag(v, (X(30.0) + 4.0, 112.2), 14, target=(X(33.0), W0_SHELF - 0.2))
    key_tag(v, (X(36.0), 111.2), 15)
    key_tag(v, (X(28.0) + 2.6, LINK_PAR + 2.5), 11, target=(X(29.4), LINK_PAR + 0.1))
    key_tag(v, (X(57.0), 97.7), 5)
    return f, rg


def link_elevation(v, key):
    """enlarged link elevation (1/4"). Adjacent walls cut 6 1/2" in front of the link face."""
    f = FACES[key]
    X = f.h
    s = f.sign
    rg = render_face(v, f, fine=True)
    # columns behind (hidden)
    for xc in (M.LINK_GRID_X["L1"], M.LINK_GRID_X["L2"]):
        for dh in (-2.5 * IN, 2.5 * IN):
            v.line((X(xc) + dh, L1), (X(xc) + dh, LINK_ROOF - 12 * IN), lw="fine", dash="hidden")
    # main building wall cut (W1 / W2) at the inside corner
    se = -1 if s < 0 else 1           # exterior of W1/W2 is -x ; h = s*x
    ew_cut(v, X(0.0), s * -1, PARAPET, cs2=True, z_break=121.0)
    # existing wall cut (screened) + existing roof beyond
    he0, he1 = sorted((X(FX), X(FX - M.EXIST_WALL_T)))
    g = box(he0, GRADE - 2.0, he1, EX_ROOF + 0.7)
    v.geom(g, lw="thin", color="screen", fill="white", hatch="ansi37",
           hatch_kw=dict(spacing=0.05, col=SCREEN))
    hb = X(FX - 4.0)
    a, b = sorted((he0 if s > 0 else he1, hb))
    R(v, a, EX_ROOF - 1.2, b, EX_ROOF, lw="thin", color="screen", fill="g05")
    break_line(v, (hb, GRADE - 1.0), (hb, EX_ROOF + 1.5), zig=0.08)
    v.line((min(a, b), GRADE), (max(a, b), GRADE), lw="thin", color="screen")
    text_box(v, ((he0 + he1) / 2 + s * -2.2 * -1 if False else (a + b) / 2, EX_ROOF + 2.4),
             "EXIST.\nBLDG.", size=TXT["tiny"], color=SCREEN)
    # grade, footing
    gx0 = min(X(0.0) + s * -2.0 * -1, X(FX)) - 1.0
    ga, gb_ = sorted((X(0.0), X(FX)))
    grade_line(v, ga - 1.5, gb_ + 0.2)
    R(v, ga + 1.3, TOF, gb_, GRADE, lw="fine", dash="hidden")
    R(v, ga + 1.3, BOF, gb_, TOF, lw="fine", dash="hidden")
    if key == "LN":
        draw_scupper(v, f)
    # grids
    grid_bubbles(v, [(X(x), k) for k, x in M.LINK_GRID_X.items()] + [(X(0.0), "1")], 0,
                 LINK_PAR + 1.0, 122.5 if True else 0, dia=0.34)
    # vertical dims and levels beyond the existing-building fragment
    sf = [o for o in rg["ops"] if o.type == "SF-3"][0]
    hp = X(FX - 6.5)
    dchain(v, [(hp, z) for z in (GRADE, L1, SF_TRANSOM[0], SF_TRANSOM[1], sf.head, LINK_ROOF,
                                 LINK_PAR)], 0.0, size=TXT["tiny"])
    for z in (GRADE, L1, SF_TRANSOM[0], SF_TRANSOM[1], sf.head, LINK_ROOF, LINK_PAR):
        v.line((X(FX - 4.3), z), (hp - s * -0.3 * -1 if False else X(FX - 6.8), z), lw="hair")
    levels_column(v, X(FX - 10.0), X(FX - 7.2),
                  [(GRADE, "FIN. GRADE"), (L1, "LEVEL 1 FFE"), (sf.head, "SF-3 HEAD (MO)"),
                   (LINK_ROOF, "LINK ROOF (T.O. STL.)"), (LINK_PAR, "LINK T.O. PARAPET")],
                  side="r" if s < 0 else "l")
    # horizontal dims: piers, storefront bays
    xs = [FX, sf.lo] + [sf.lo + k * (sf.w / 6) for k in range(1, 6)] + [sf.hi, -OUT]
    dchain(v, [(X(x), GRADE - 2.2) for x in xs], 0.0, size=TXT["tiny"], denom=16)
    dchain(v, [(X(x), GRADE - 4.2) for x in (FX, sf.lo, sf.hi, -OUT)], 0.0, size=TXT["tiny"],
                denom=16)
    zc = GRADE - 6.2
    pts = sorted(set([X(x) for x in (FX, -18.0, 0.0)] + [X(x) for x in M.LINK_GRID_X.values()]))
    dchain(v, [(hh, zc) for hh in pts], 0.0, size=TXT["tiny"], denom=16)
    v.text((X(-18.0), zc + v.paper_len(0.11)), "EJ", size=TXT["tiny"], font=FONT_B, anchor="c",
           valign="bot")
    # tags / keynotes
    mat_tag(v, (X(-26.0), 112.0), (X(-26.0), 112.0), "FB-1", arrow=False)
    mat_tag(v, (X(-35.0), 100.3), (X(-31.0), 97.6), "FB-2")
    mat_tag(v, (X(-30.0), LINK_PAR + 0.1), (X(-30.0), LINK_PAR + 2.0), "MC-1")
    mat_tag(v, (X(-24.0), 104.0), (X(-24.0), 104.0), "AL-1", arrow=False)
    key_tag(v, (X(-22.0), GRADE - 1.0 + 0.2) if False else (X(-14.0), 98.2), 9,
            target=(X(-14.0), GRADE + 0.4))
    key_tag(v, (X(-15.5), 113.0), 1, target=(X(-18.0), 112.6))
    key_tag(v, (X(FX + 2.2), 113.2), 7, target=(X(FX), 112.4))
    if key == "LN":
        mat_tag(v, (X(SCUPPER_X) + 0.3, 111.6), (X(SCUPPER_X - 3.0), 111.6), "MF-1")
        key_tag(v, (X(SCUPPER_X - 2.2), 114.9), 8, target=(X(SCUPPER_X - 0.4), 114.4))
    return f, rg


def draw_a202(sh):
    S = 1 / 8
    # ---- left column: east and west elevations (1/8") ----
    colw = 15.6
    xl = sh.x0
    y_top = sh.y1 - 0.4
    for num, name, fn, key in ((1, "EAST ELEVATION", elevation_E, "E"),
                               (2, "WEST ELEVATION", elevation_W, "W")):
        f = FACES[key]
        hmin, hmax = f.h0 - 9.0, f.h1 + 6.0 + 9.0 + 1.15 / S
        ox = xl + colw / 2 - (hmin + hmax) / 2 * S
        oy = y_top - (RTU_TOP + 4.0 + 1.2 - L1) * S
        v = sh.view(ox, oy, S, mx=0.0, my=L1)
        fn(v)
        ty = v.to_paper((0, BOF - 7.0))[1]
        sh.view_title(v.to_paper((f.h0 - 6.0, 0))[0], ty, num, name, S, width=6.0)
        y_top = ty - 0.55
    keynote_list(sh, xl + 0.3, y_top - 0.1, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
                 colw - 0.6)
    # ---- right column: link elevations (1/4") ----
    S4 = 1 / 4
    xr0 = sh.x0 + colw + 0.2
    colw2 = sh.x1 - xr0
    sh.line((xr0 - 0.1, sh.y0), (xr0 - 0.1, sh.y1), lw="fine")
    y_top = sh.y1 - 0.35
    for num, name, key in ((3, "LINK NORTH ELEVATION", "LN"), (4, "LINK SOUTH ELEVATION", "LS")):
        f = FACES[key]
        hmin, hmax = min(f.h(0.0), f.h(FX - 10.0)), max(f.h(0.0), f.h(FX - 10.0))
        if f.sign < 0:
            hmin -= 2.0
            hmax += 0.5 + 1.25 / S4
        else:
            hmin -= 0.5 + 1.25 / S4
            hmax += 2.0
        ox = xr0 + colw2 / 2 - (hmin + hmax) / 2 * S4
        oy = y_top - (123.0 - L1) * S4
        v = sh.view(ox, oy, S4, mx=0.0, my=L1)
        link_elevation(v, key)
        ty = v.to_paper((0, GRADE - 7.6))[1]
        sh.view_title(v.to_paper((hmin, 0))[0], ty, num, name, S4, width=5.6,
                      note="ADJ. WALLS CUT 6 1/2\" IN FRONT OF LINK FACE")
        y_top = ty - 1.0
    sh.text((xr0 + 0.25, sh.y0 + 0.2), "SEE A-201 FOR EXTERIOR MATERIAL LEGEND, SYMBOLS AND GENERAL "
            "ELEVATION NOTES.", size=TXT["note"], font=FONT_B)


# =============================================================================================
# Building sections (A-301)
# =============================================================================================
SLAB2 = 6.25 * IN          # L2 composite slab (3" deck + 3 1/4" LW concrete)
SOG = 5 * IN
BASE6 = 6 * IN
BEAMS = {  # name: (d, bf) inches
    "W24x55": (23.57, 7.005), "W18x35": (17.70, 6.0), "W16x31": (15.88, 5.525),
    "W16x26": (15.69, 5.5), "W12x19": (12.16, 4.005), "W12x14": (11.91, 3.97), "W8x18": (8.14, 5.25),
}
JOIST_SEAT = 2.5 * IN
SPANDREL_OFF = CMUh + 0.5 * IN      # outer flange edge of spandrels: 1/2" inside face of CMU


def beam_cut(v, hc, z_top, name, lw="thin", label=None, lab_side=1):
    d, bf = BEAMS[name]
    ibeam(v, hc, z_top, d * IN, bf * IN, lw=lw)
    return d * IN


def room_at(level, x, y):
    from shapely.geometry import Point as _P
    for r in M.rooms(level):
        if r.shape.buffer(0.01).contains(_P(x, y)):
            return r
    return None


def sog(v, h0, h1, thick=()):
    """slab on grade + vapor retarder + CA-6; thick = [(hc, w)] thickened slabs"""
    a, b = sorted((h0, h1))
    g = box(a, L1 - SOG, b, L1)
    for hc, w in thick:
        g = g.union(box(hc - w / 2, L1 - 1.0, hc + w / 2, L1))
    v.geom(g, lw="thin", fill="white", hatch="concrete", hatch_kw=dict(scale=0.55))
    base = box(a, L1 - SOG - BASE6, b, L1 - SOG)
    for hc, w in thick:
        base = base.difference(box(hc - w / 2, L1 - 1.0, hc + w / 2, L1))
    v.geom(base, lw=None, hatch="gravel", hatch_kw=dict(scale=0.45), stroke=False)
    v.line((a, L1 - SOG), (b, L1 - SOG), lw="med", dash=[1.2, 0.8])


def ceiling(v, h0, h1, z, lw="thin"):
    a, b = sorted((h0, h1))
    R(v, a, z, b, z + 0.75 * IN, lw=lw, fill="g40")


def cmu_cut(v, hc, z0, z1, t=M.CMU_T, lw="heavy"):
    R(v, hc - t / 2, z0, hc + t / 2, z1, lw=lw, fill="white", hatch="ansi31",
      hatch_kw=dict(spacing=0.03, w="hair"))


def joist_cut(v, hc, z_top, d):
    """open-web joist cut transversely: top/bottom chord angles + web"""
    w, t = 2.5 * IN, 1.5 * IN
    R(v, hc - w / 2, z_top - t, hc + w / 2, z_top, lw="hair", fill="black")
    R(v, hc - w / 2, z_top - d, hc + w / 2, z_top - d + t, lw="hair", fill="black")
    v.line((hc, z_top - t), (hc, z_top - d + t), lw="hair")


def roof_build(v, pts_ins, deck_z=ROOF, lw="thin"):
    """roof assembly along a cut: pts_ins = [(h, t_ins)] sorted by h"""
    a, b = pts_ins[0][0], pts_ins[-1][0]
    R(v, a, deck_z, b, deck_z + DECK, lw="fine", fill="g40")
    top = [(h, deck_z + DECK + t) for h, t in pts_ins]
    v.polygon([(a, deck_z + DECK), (b, deck_z + DECK)] + top[::-1], lw="fine", fill="white",
              hatch="insul", hatch_kw=dict(spacing=0.07, w="hair", col=_col(0.4)))
    cov = [(h, z + COVER) for h, z in top]
    v.polygon(top + cov[::-1], lw="hair", fill="g20")
    v.polyline(cov, lw="med")
    return cov


def window_cut(v, hg, se, o, detail=False):
    """window / storefront cut through the glass in an EW-1 wall (any scale)"""
    U = lambda u: hg + se * u
    a, b = sorted((U(FR_IN), U(FR_OUT)))
    gm = U((FR_IN + FR_OUT) / 2)
    zs, zh = o.sill, o.head
    t = o.type
    fr_bot = zs + 0.25 * IN
    v.line((a, zs), (a, zh), lw="hair")
    v.line((b, zs), (b, zh), lw="hair")
    if t in ("W-A", "W-B", "SF-2", "W-C"):
        R(v, a, fr_bot, b, fr_bot + FR, lw="thin", fill="g60")
        R(v, a, zh - 0.5 * IN - FR, b, zh - 0.5 * IN, lw="thin", fill="g60")
        rails = []
        if t in ("W-A", "W-B"):
            rails = [zs + VENT_H]
        elif t == "W-C":
            rails = [zs + (zh - zs) * k / 4 for k in (1, 2, 3)]
        for zr in rails:
            R(v, a, zr - FR / 2, b, zr + FR / 2, lw="thin", fill="g60")
        v.line((gm, fr_bot + FR), (gm, zh - 0.5 * IN - FR), lw="fine")
        if t in ("W-A", "W-B", "SF-2"):
            # CS-1 sill (4" high, 1" projection) and interior stool
            cs = [(U(FR_OUT), zs), (U(OUT + CS1_PROJ), zs - 0.5 * IN), (U(OUT + CS1_PROJ), zs - CS1_H),
                  (U(EW_AIR_OUT), zs - CS1_H), (U(EW_AIR_OUT), zs - 0.5 * IN), (U(CMUh + 2 * IN), zs - 0.5 * IN),
                  (U(CMUh + 2 * IN), zs)]
            v.polygon(cs, lw="thin", fill="white")
            stipple(v, Polygon(cs), step_in=0.02 if not detail else 0.03, col=0.4, r_pt=0.18)
        if t != "W-C":
            st0, st1 = sorted((U(-CMUh - 1 * IN), U(FR_IN)))
            R(v, st0, zs, st1, zs + 0.75 * IN, lw="thin", fill="white")
    elif t in ("SF-1", "SF-3"):
        # threshold / curb, door or lite, transom bar, head
        R(v, a, zh - 0.5 * IN - FR, b, zh - 0.5 * IN, lw="thin", fill="g60")
        R(v, a, SF_TRANSOM[0], b, SF_TRANSOM[1], lw="thin", fill="g60")
        v.line((gm, SF_TRANSOM[1]), (gm, zh - 0.5 * IN - FR), lw="fine")
        if t == "SF-1":
            dl0, dl1 = sorted((U((FR_IN + FR_OUT) / 2 - 0.875 * IN), U((FR_IN + FR_OUT) / 2 + 0.875 * IN)))
            R(v, dl0, zs + 0.5 * IN, dl1, SF_TRANSOM[0] - 0.1 * IN, lw="thin", fill="white")
            R(v, a - 2 * IN, zs, b + 3 * IN, zs + 0.5 * IN, lw="fine", fill="g60")  # threshold
        else:
            R(v, a, zs + 0.25 * IN, b, zs + 0.25 * IN + 4 * IN, lw="thin", fill="g60")
            v.line((gm, zs + 4.25 * IN), (gm, SF_TRANSOM[0]), lw="fine")
    # loose lintel at brick (L5x3 1/2 LLV) for windows/doors with a head in the brick
    if t not in ("SF-3",):
        hl = [(U(7.375 * IN - 0 * IN), zh + 5 * IN), (U(7.375 * IN), zh), (U(10.875 * IN), zh)]
        v.polyline(hl, lw="thin" if not detail else "med")


def ew_section(v, hg, se, face_key, along, z_top=PARAPET, cs2=True, detail=False, **kw):
    """exterior wall cut at coordinate `along` on a face, with the openings it passes through"""
    f = FACES[face_key]
    ops = [o for o in f.openings() if o.lo < along < o.hi and o.kind != "door"]
    holes = []
    for o in ops:
        z0 = o.sill - (CS1_H if o.type in ("W-A", "W-B", "SF-2") else 0)
        if o.type in ("SF-1", "SF-3"):
            z0 = o.sill
        holes.append((z0, o.head))
    cs2_here = cs2 and not any(o.type == "W-C" for o in ops)
    if face_key in ("N", "S", "E") and not any(o.type == "W-C" for o in ops):
        kw.setdefault("cmu_gaps", [CMU_SPANDREL_GAP])
    ew_cut(v, hg, se, z_top, cs2=cs2_here, holes=holes, **kw)
    for o in ops:
        window_cut(v, hg, se, o, detail=detail)
    return ops


def rtu_elev(v, h0, h1, z_roof, label=None):
    R(v, h0, z_roof, h1, z_roof + 14 * IN, lw="fine", fill="white")
    R(v, h0 + 0.3, z_roof + 14 * IN, h1 - 0.3, RTU_TOP, lw="fine", fill="white")
    v.line((h0 + 0.3, RTU_TOP - 1.2), (h1 - 0.3, RTU_TOP - 1.2), lw="hair")
    if label:
        v.text(((h0 + h1) / 2, (z_roof + RTU_TOP) / 2 + 0.6), label, size=TXT["tiny"], font=FONT_B,
               anchor="c", valign="mid")
        v.text(((h0 + h1) / 2, (z_roof + RTU_TOP) / 2 - 0.6), "(DIV. 23)", size=TXT["tiny"],
               anchor="c", valign="mid")


def door_beyond(v, o, hl, hr):
    """interior door / frame elevation seen beyond in a section (light)"""
    z0, zh = o.sill, o.head
    R(v, hl, z0, hr, zh, lw="fine", fill="white")
    fi0, fi1, ft = hl + 2 * IN, hr - 2 * IN, zh - 4 * IN
    v.polyline([(fi0, z0), (fi0, ft), (fi1, ft), (fi1, z0)], lw="hair")
    if o.frame == "F2":
        # sidelite: 1'-0" glass beside the 3'-0" leaf
        if (o.side == "hi") == (hl < hr):
            hdl = fi0 + 3.0
            R(v, hdl + 2 * IN, z0 + 1.0, fi1, ft, lw="hair")
            v.line((hdl + 1 * IN, z0), (hdl + 1 * IN, ft), lw="hair")
        else:
            hdl = fi1 - 3.0
            R(v, fi0, z0 + 1.0, hdl - 2 * IN, ft, lw="hair")
            v.line((hdl - 1 * IN, z0), (hdl - 1 * IN, ft), lw="hair")
    elif o.pair:
        v.line(((fi0 + fi1) / 2, z0), ((fi0 + fi1) / 2, ft), lw="hair")


def sec_levels(v, h_mark, h_from, side="r", extra=()):
    items = [(TOF, "T.O. FOOTING"), (GRADE, "FIN. GRADE"), (L1, "LEVEL 1 FFE"), (L2, "LEVEL 2"),
             (ROOF, "ROOF (T.O. STEEL)"), (PARAPET, "T.O. PARAPET")] + list(extra)
    levels_column(v, h_mark, h_from, items, side=side)


def section_1(v):
    """TRANSVERSE BUILDING SECTION at x = 75 looking west (h = y)"""
    xc = 75.0
    # earth outside
    earth(v, -14.0, -OUT, BOF - 1.0, GRADE)
    earth(v, 72 + OUT, 86.0, BOF - 1.0, GRADE)
    grade_line(v, -14.0, -OUT)
    grade_line(v, 72 + OUT, 86.0)
    # slab on grade with thickened slabs under the corridor walls
    sog(v, CMUh, 72 - CMUh, thick=[(30.0, 2.0), (42.0, 2.0)])
    earth(v, CMUh + 1.5, 72 - CMUh - 1.5, BOF - 1.0, L1 - SOG - BASE6)
    # ---- beyond (x = 60 wall, casework, girders) -- light lines ----
    for y0, y1 in ((CMUh, 30 - CMUh), (42 + CMUh, 72 - CMUh)):
        for zf, zc in ((L1, 110.0), (L2, 124.0)):
            pass
    # girders on grid 3 beyond
    for (y0, y1, nm) in ((0.0, 30.0, "W24x55"), (30.0, 42.0, "W12x19"), (42.0, 72.0, "W24x55")):
        d = BEAMS[nm][0] * IN
        zt = L2 - SLAB2
        a0, a1 = max(y0, SPANDREL_OFF + 0.6) + 0.2, min(y1, 72 - SPANDREL_OFF - 0.6) - 0.2
        if nm == "W12x19":
            a0, a1 = y0 + 0.4, y1 - 0.4
        v.polyline([(a0, zt), (a0, zt - d), (a1, zt - d), (a1, zt)], lw="fine", color="g50")
        v.line((a0, zt - d + 0.6 * IN), (a1, zt - d + 0.6 * IN), lw="hair", color="g50")
    # casework in room 113 on the x = 60 wall (beyond): base, counter, wall cabinets, tall cab.
    for zf in (L1, L2):
        R(v, 4.0, zf + 4 * IN, 16.0, zf + 34.5 * IN, lw="fine", color="g40")
        R(v, 4.0, zf + 34.5 * IN, 16.0, zf + 36 * IN, lw="fine", color="g40")
        R(v, 7.0, zf + 54 * IN, 16.0, zf + 84 * IN, lw="fine", color="g40")
        R(v, 16.0, zf + 4 * IN, 19.0, zf + 84 * IN, lw="fine", color="g40")
        for yy in (8.0, 12.0):
            v.line((yy, zf + 4 * IN), (yy, zf + 34.5 * IN), lw="hair", color="g40")
            v.line((yy - 1.0, zf + 54 * IN), (yy - 1.0, zf + 84 * IN), lw="hair", color="g40")
        v.line((4.0, zf + 26 * IN), (16.0, zf + 26 * IN), lw="hair", color="g40")
    # RTU-1 beyond and roof hatch beyond
    rtu_elev(v, 57 - RTU_D / 2, 57 + RTU_D / 2, roof_top(45, 57) - COVER, label="RTU-1")
    hz = roof_top(46.75, 27.0)
    R(v, 25.5, hz, 28.5, hz + 1.0, lw="fine", fill="white")
    v.line((25.3, hz + 1.0), (28.7, hz + 1.0), lw="thin")
    # ---- interior CMU walls (cut) ----
    zb_l2 = L2 - SLAB2 - BEAMS["W18x35"][0] * IN
    zb_rf = ROOF - JOIST_SEAT - BEAMS["W18x35"][0] * IN
    for yg in (30.0, 42.0):
        cmu_cut(v, yg, L1, zb_l2)
        cmu_cut(v, yg, L2, zb_rf)
        beam_cut(v, yg, L2 - SLAB2, "W18x35")
        beam_cut(v, yg, ROOF - JOIST_SEAT, "W18x35")
    # ---- L2 floor ----
    a, b = -CMUh, 72 + CMUh
    R(v, a, L2 - SLAB2, b, L2, lw="thin", fill="white", hatch="concrete", hatch_kw=dict(scale=0.5))
    v.line((a, L2 - SLAB2 + 3 * IN), (b, L2 - SLAB2 + 3 * IN), lw="hair")
    for yy, nm in ((0.0, "W16x31"), (10.0, "W16x26"),
                   (20.0, "W16x26"), (52.0, "W16x26"), (62.0, "W16x26"), (72.0, "W16x31")):
        beam_cut(v, yy, L2 - SLAB2, nm)
    # ---- roof ----
    for yy in (SPANDREL_OFF + BEAMS["W16x26"][1] * IN / 2, 72 - SPANDREL_OFF - BEAMS["W16x26"][1] * IN / 2):
        beam_cut(v, yy, ROOF - JOIST_SEAT, "W16x26")
    jb = [(0.0 + SPANDREL_OFF + 0.2, 30.0 - 0.25, 22 * IN), (30.25, 41.75, 12 * IN),
          (42.25, 72.0 - SPANDREL_OFF - 0.2, 22 * IN)]
    for h0, h1, d in jb:
        joist_elev(v, h0, h1, ROOF, d, panel=2.0 if d > 1 else 1.5)
    ys = [CMUh + i * (72 - 2 * CMUh) / 72 for i in range(73)]
    roof_build(v, [(y, roof_ins(xc, y)) for y in ys])
    # parapet base flashing
    for yy in (CMUh, 72 - CMUh):
        v.line((yy, roof_top(xc, yy)), (yy, PARAPET), lw="med")
    # ---- exterior walls (cut, with W-A at both levels) ----
    ew_section(v, 0.0, -1, "S", xc)
    ew_section(v, 72.0, +1, "N", xc)
    # ---- ceilings + room names ----
    for lev, zf in (("L1", L1), ("L2", L2)):
        for y0, y1, yy in ((CMUh, 30 - CMUh, 15.0), (30 + CMUh, 42 - CMUh, 36.0), (42 + CMUh, 72 - CMUh, 57.0)):
            r = room_at(lev, xc, yy)
            ceiling(v, y0, y1, zf + r.clg_ht)
            room_tag(v, ({15.0: 25.5, 36.0: 36.0, 57.0: 57.0}[yy], zf + 5.2), r.name, r.num,
                     size=TXT["label"])
    # cubbies (CW-5) at the corridor walls - cut
    for zf in (L1, L2):
        R(v, 30 - CMUh - 1.25, zf + 4 * IN, 30 - CMUh, zf + 64 * IN, lw="thin", fill="white")
        R(v, 42 + CMUh, zf + 4 * IN, 42 + CMUh + 1.25, zf + 64 * IN, lw="thin", fill="white")
        for k in (1, 2, 3):
            z = zf + 4 * IN + k * 15 * IN
            v.line((30 - CMUh - 1.25, z), (30 - CMUh, z), lw="hair")
            v.line((42 + CMUh, z), (42 + CMUh + 1.25, z), lw="hair")
    return xc


def section_dims_1(v):
    # grid bubbles + grid dims
    zb = RTU_TOP + 3.5
    grid_bubbles(v, [(y, k) for k, y in M.GRID_Y.items()], 0, PARAPET + COPE_UP + 0.5, zb, dia=0.34)
    dchain(v, [(y, BOF - 2.2) for y in sorted(M.GRID_Y.values())], 0.0, size=TXT["small"])
    v.dim((-OUT, BOF - 4.4), (72 + OUT, BOF - 4.4), 0.0, size=TXT["small"])
    sec_levels(v, 72 + OUT + 12.0, 72 + OUT + 0.6, side="r")
    # floor-to-floor / overall
    dchain(v, [(72 + OUT + 4.0, z) for z in (L1, L2, ROOF, PARAPET)], 0.0, size=TXT["tiny"])
    v.dim((72 + OUT + 7.0, GRADE), (72 + OUT + 7.0, PARAPET), 0.0, size=TXT["tiny"])
    # ceiling heights (AFF)
    for yy, zf in ((20.5, L1), (20.5, L2), (39.5, L1), (39.5, L2)):
        r = room_at("L1" if zf == L1 else "L2", 75.0, yy)
        v.dim((yy, zf), (yy, zf + r.clg_ht), 0.0, size=TXT["tiny"],
              text=ftxt(r.clg_ht) + " CLG.")


def section_2(v):
    """LONGITUDINAL SECTION at y = 36 looking north (h = x)"""
    yc = 36.0
    # ---------------- existing building (screened) ----------------
    ex0 = FX - 12.0
    R(v, ex0, L1 - 4 * IN, FX - M.EXIST_WALL_T, L1, lw="thin", color="screen", fill="g05")
    R(v, ex0, EX_ROOF - 1.2, FX, EX_ROOF, lw="thin", color="screen", fill="g05")
    v.line((ex0, 109.5), (FX - M.EXIST_WALL_T, 109.5), lw="fine", color="screen")
    # existing wall at the enlarged opening: wall above new lintel
    R(v, FX - M.EXIST_WALL_T, 109 + 4 * IN, FX, EX_ROOF, lw="thin", color="screen", fill="white",
      hatch="ansi37", hatch_kw=dict(spacing=0.04, col=SCREEN))
    R(v, FX - M.EXIST_WALL_T, 109 + 4 * IN - 8 * IN, FX, 109 + 4 * IN, lw="thin", fill="g60")
    R(v, FX - M.EXIST_WALL_T, BOF + 0.6, FX, L1 - 4 * IN, lw="fine", color="screen", dash="hidden")
    break_line(v, (ex0, BOF), (ex0, EX_ROOF + 2.0), zig=0.1)
    v.mtext((ex0 + 5.0, 104.5), "EXISTING\nCORRIDOR", size=TXT["small"], anchor="c", valign="mid",
            color="screen")
    # ---------------- link ----------------
    sog(v, FX, -CMUh, thick=[(0.0, 2.0)])
    earth(v, FX + 1.0, -1.5, BOF - 1.0, L1 - SOG - BASE6)
    # beyond: LN wall interior face with SF-3, columns, parapet
    sf3 = M.OPENING_BY_ID["100A-SF1"]
    R(v, sf3.lo, sf3.sill, sf3.hi, sf3.head, lw="fine", fill="white")
    for k in range(1, 6):
        hh = sf3.lo + k * sf3.w / 6
        v.line((hh, sf3.sill), (hh, sf3.head), lw="hair")
    v.line((sf3.lo, SF_TRANSOM[0]), (sf3.hi, SF_TRANSOM[0]), lw="hair")
    v.line((sf3.lo, SF_TRANSOM[1]), (sf3.hi, SF_TRANSOM[1]), lw="hair")
    for xc_ in M.LINK_GRID_X.values():
        R(v, xc_ - 2.5 * IN, L1, xc_ + 2.5 * IN, 109.5, lw="fine", fill="white")
    zl = LINK_ROOF + DECK + LINK_INS_MIN + 0.25 * (42 - CMUh - yc) * IN + COVER
    R(v, FX, zl, -OUT, LINK_PAR, lw="fine")
    v.line((FX, LINK_PAR + COPE_UP), (-OUT, LINK_PAR + COPE_UP), lw="fine")
    # link roof cut (joists cut 5'-0" o.c.)
    for x in (-33.0, -28.0, -23.0, -13.0, -8.0, -3.0):
        joist_cut(v, x, LINK_ROOF, 12 * IN)
    joist_cut(v, -18.0, LINK_ROOF, 12 * IN)
    t = LINK_INS_MIN + 0.25 * (42 - CMUh - yc) * IN
    roof_build(v, [(FX + 0.2, t), (-OUT, t)], deck_z=LINK_ROOF)
    ceiling(v, FX + 0.3, -CMUh, 109.5)
    v.line((FX + 0.2, LINK_ROOF + DECK + t + COVER), (FX + 0.2, EX_ROOF + 1.6), lw="med")
    # ---------------- main building ----------------
    sog(v, CMUh, 150 - CMUh, thick=[])
    earth(v, 1.5, 150 - CMUh - 1.5, BOF - 1.0, L1 - SOG - BASE6)
    earth(v, 150 + OUT, 162.0, BOF - 1.0, GRADE)
    grade_line(v, 150 + OUT, 162.0)
    # beyond: B1 / B2 wall with doors, both levels
    for lev, zf in (("L1", L1), ("L2", L2)):
        for o in M.doors(lev):
            if o.wall in ("B1", "B2"):
                draw_d = o
                door_beyond(v, o, o.lo, o.hi)
                door_tag(v, (o.c, o.head + 0.9), o.id, size=TXT["tiny"])
    # beyond: RTUs, far (north) parapet
    for name, x, y in RTUS:
        if y > 36:
            rtu_elev(v, x - RTU_W / 2, x + RTU_W / 2, roof_top(x, y) - COVER, label=name)
    v.line((-OUT, PARAPET + COPE_UP), (150 + OUT, PARAPET + COPE_UP), lw="fine")
    # X0 partition with door pair 100A (cut), girder W12x19 on grid 1, W0 wall above
    d100 = M.OPENING_BY_ID["100A"]
    zb = L2 - SLAB2 - BEAMS["W12x19"][0] * IN
    cmu_cut(v, 0.0, d100.head, zb)
    R(v, -CMUh, d100.head - 4 * IN, CMUh, d100.head, lw="thin", fill="g60")
    R(v, -0.875 * IN, L1, 0.875 * IN, d100.head - 4 * IN, lw="thin", fill="white")
    beam_cut(v, 0.0, L2 - SLAB2, "W12x19")
    ew_section(v, 0.0, -1, "W", yc, footing=False, cmu_from=L2, brick_from=W0_SHELF)
    # shelf angle at W0 brick + link roof base flashing
    v.polyline([(-EW_AIR_OUT + 1.5 * IN, W0_SHELF + 4 * IN), (-EW_AIR_OUT + 1.5 * IN, W0_SHELF),
                (-OUT, W0_SHELF)], lw="med")
    v.line((-OUT, LINK_ROOF + DECK + t + COVER), (-OUT, W0_SHELF - 0.2 * IN), lw="med")
    # floors, ceilings
    R(v, CMUh, L2 - SLAB2, 150 + CMUh, L2, lw="thin", fill="white", hatch="concrete",
      hatch_kw=dict(scale=0.5))
    for x in M.GRID_X.values():
        if 0 < x < 150:
            beam_cut(v, x, L2 - SLAB2, "W12x19")
            beam_cut(v, x, ROOF, "W12x14")
    beam_cut(v, 150.0, L2 - SLAB2, "W12x19")
    beam_cut(v, 150 - SPANDREL_OFF - BEAMS["W12x14"][1] * IN / 2, ROOF, "W12x14")
    beam_cut(v, SPANDREL_OFF + BEAMS["W12x14"][1] * IN / 2, ROOF, "W12x14")
    for i in range(1, 30):
        x = i * 5.0
        if abs(x - round(x / 30) * 30) < 0.01:
            continue
        joist_cut(v, x, ROOF, 12 * IN)
    xs = [CMUh + i * (150 - 2 * CMUh) / 150 for i in range(151)]
    roof_build(v, [(x, roof_ins(x, yc)) for x in xs])
    for xx in (CMUh, 150 - CMUh):
        v.line((xx, roof_top(xx, yc)), (xx, PARAPET), lw="med")
    for lev, zf in (("L1", L1), ("L2", L2)):
        r = room_at(lev, 75.0, yc)
        ceiling(v, CMUh, 150 - CMUh, zf + r.clg_ht)
        room_tag(v, (75.0, zf + 4.6), r.name, r.num, size=TXT["label"])
    rl = room_at("L1", -18.0, yc)
    room_tag(v, (-24.0, L1 + 4.6), rl.name, rl.num, size=TXT["label"])
    # roof drains on the section line
    for i, (x, y) in enumerate(ROOF_DRAINS, 1):
        zt = roof_top(x, y)
        R(v, x - 0.6, ROOF - 0.9, x + 0.6, ROOF + DECK, lw="thin", fill="white")
        v.line((x, ROOF - 0.9), (x, L2 + 0.3), lw="fine", dash="hidden")
        ox = x + 2.0
        R(v, ox - 0.45, ROOF - 0.7, ox + 0.45, ROOF + DECK, lw="thin", fill="white")
        R(v, ox - 0.2, roof_top(ox, y), ox + 0.2, roof_top(ox, y) + 2 * IN, lw="fine", fill="white")
        v.text((x + 1.0, zt + 2.2), f"RD-{i} / OD-{i}", size=TXT["tiny"], font=FONT_B, anchor="c",
               valign="bot")
        v.line((x + 1.0, zt + 2.1), (x, zt + 0.15), lw="hair")
    # east wall with SF-1 / SF-2 and the entrance walk
    ew_section(v, 150.0, +1, "E", yc)
    R(v, 150 + OUT, L1 - 0.5 * IN - 5 * IN, 158.0, L1 - 0.5 * IN, lw="thin", fill="white",
      hatch="concrete", hatch_kw=dict(scale=0.5))
    # link walls are beyond / cut at the existing building: link footing at existing face (dashed)
    return yc


def section_3(v):
    """LINK SECTION at x = -18 looking east (h = -y)"""
    H = lambda y: -y
    f = FACES["W"].cropped(17.0, 53.0)
    rg = render_face(v, f)
    a, b = sorted((H(30 + CMUh), H(42 - CMUh)))
    z_lr = LINK_ROOF + DECK + LINK_INS_MIN + COVER
    R(v, a, z_lr, b, W0_SHELF, lw="fine", fill="g20")
    # X0 wall beyond inside the link + doors 100A
    R(v, a, L1, b, 109.5, lw="fine", fill="white")
    d100 = M.OPENING_BY_ID["100A"]
    hl, hr = sorted((H(d100.lo), H(d100.hi)))
    draw_door_elev(v, d100, hl, hr, tag=False)
    door_tag(v, ((hl + hr) / 2, 104.8), "100A", size=TXT["tiny"])
    for hh in (H(17.0), H(53.0)):
        break_line(v, (hh, GRADE - 2.0), (hh, PARAPET + 2.0), zig=0.1)
    # link cut at x = -18: storefront SF-3 through the mullion, HSS columns, curb
    earth(v, H(30 - OUT) + 0.01, H(17.0), BOF - 1.0, GRADE)
    earth(v, H(53.0), H(42 + OUT) - 0.01, BOF - 1.0, GRADE)
    sf = M.OPENING_BY_ID["100A-SF1"]
    for yg, ext, key in ((42.0, +1, "LN"), (30.0, -1, "LS")):
        se = -ext
        ew_section(v, H(yg), se, key, -18.0, z_top=LINK_PAR)
        # concrete curb (cut) under SF-3
        u0, u1 = sorted((H(yg) + se * -CMUh, H(yg) + se * OUT))
        R(v, u0, GRADE, u1, CURB_TOP, lw="heavy", fill="white", hatch="concrete",
          hatch_kw=dict(scale=0.5))
        # HSS 5x5 column on the cut plane
        R(v, H(yg) - 2.5 * IN, L1, H(yg) + 2.5 * IN, LINK_ROOF - 12 * IN, lw="thin", fill="g40")
        # lintel beam above the storefront (W8, see S-302) and roof beam (cut)
        ibeam(v, H(yg), sf.head + 8.14 * IN, 8.14 * IN, 5.25 * IN, lw="thin")
        beam_cut(v, H(yg - ext * (SPANDREL_OFF + 2.0 * IN)), LINK_ROOF - JOIST_SEAT, "W12x19")
    # slab, roof
    sog(v, H(30 + CMUh), H(42 - CMUh))
    earth(v, H(30 + CMUh) - 1.0, H(42 - CMUh) + 1.0, BOF - 1.0, L1 - SOG - BASE6)
    joist_elev(v, a + 0.6, b - 0.6, LINK_ROOF, 12 * IN, panel=1.5)
    ys = [30 + CMUh + i * (12 - 2 * CMUh) / 12 for i in range(13)]
    roof_build(v, [(H(y), LINK_INS_MIN + 0.25 * (42 - CMUh - y) * IN) for y in ys][::-1],
               deck_z=LINK_ROOF)
    for yy in (30 + CMUh, 42 - CMUh):
        tt = LINK_INS_MIN + 0.25 * (42 - CMUh - yy) * IN
        v.line((H(yy), LINK_ROOF + DECK + tt + COVER), (H(yy), LINK_PAR), lw="med")
    ceiling(v, a, b, 109.5)
    rl = room_at("L1", -18.0, 36.0)
    room_tag(v, (H(36.0), 108.1), rl.name, rl.num, size=TXT["small"])
    grade_line(v, H(17.0), H(30 - OUT))
    grade_line(v, H(42 + OUT), H(53.0))
    return f


def lnote(v, target, at, text, width=None, size=TXT["note"], shoulder=0.12, mask=True):
    """leader note: arrow at target (model), text block starting at `at` (model) with a short
    horizontal shoulder; text goes to the side the leader points to."""
    p = Paper(v.c)
    tx, ty = v.to_paper(target)
    ax, ay = v.to_paper(at)
    side = 1 if ax >= tx else -1
    bx = ax + side * shoulder
    lines = text.split("\n")
    if width:
        lines = wrap_lines(lines, size, FONT, width)
    lead = size * 1.18 / PT
    hgt = lead * len(lines)
    wmax = max(p.text_width(t, size) for t in lines)
    x0 = bx + 0.04 if side > 0 else bx - 0.04 - wmax
    if mask:
        p.rect(x0 - 0.02, ay - hgt / 2 - 0.02, wmax + 0.04, hgt + 0.04, lw=None, fill="white")
    p.polyline([(tx, ty), (ax, ay), (bx, ay)], lw="fine")
    ang = math.atan2(ty - ay, tx - ax)
    L, W = 0.06, 0.018
    hx, hy = tx - L * math.cos(ang), ty - L * math.sin(ang)
    p.polygon([(tx, ty), (hx - W * math.sin(ang), hy + W * math.cos(ang)),
               (hx + W * math.sin(ang), hy - W * math.cos(ang))], lw="fine", fill="black")
    p.mtext((x0, ay + hgt / 2 - lead * 0.12), lines, size=size, anchor="l", valign="top",
            leading=size * 1.18)


def ws_ref(v, h0, h1, z0, z1, num, sheet, bubble_at="top", sim=False):
    """wall section reference: dashed rectangle + detail bubble"""
    cx, cz = (h0 + h1) / 2, (z0 + z1) / 2
    detail_callout(v, (cx, cz), (abs(h1 - h0), z1 - z0), num, sheet,
                   bubble_dir=(1 if bubble_at != "left" else -1, 1), shape="rect")
    if sim:
        x, y = v.to_paper((max(h0, h1), z1))
        Paper(v.c).text((x + 0.47, y + 0.28), "SIM.", size=TXT["small"], font=FONT_B, valign="mid")


def notes_section_1(v):
    lnote(v, (10.0, roof_top(75, 10.0) - 0.1), (3.0, 135.2),
          "ROOF R-1: 60-MIL EPDM FULLY ADHERED / 1/2\" COVER BD. / TAPERED POLYISO 1/4\":12 "
          "(1 1/2\" MIN. AT DRAIN LINE, R-30 AVG.) / 1 1/2\" TYPE B DECK", width=3.4)
    lnote(v, (8.0, ROOF - 12 * IN), (11.0, 125.3), "22K6 JOISTS @ 5'-0\" O.C.")
    lnote(v, (36.5, ROOF - 6 * IN), (33.0, 125.6), "12K1 @ 5'-0\" O.C.")
    lnote(v, (61.0, ROOF - 12 * IN), (66.0, 125.2), "22K6 @ 5'-0\" O.C.")
    lnote(v, (16.0, L2 - 0.25), (18.5, 115.3), "F-2: 3 1/4\" LW CONC. ON 3\" COMP. DECK", width=None)
    lnote(v, (10.0, L2 - SLAB2 - 0.6), (13.0, 112.7), "W16x26 INFILL BEAM")
    lnote(v, (42.0, L2 - SLAB2 - 0.8), (47.0, 110.8), "W18x35 ON CMU (S-102)")
    lnote(v, (42.0, 108.0), (46.0, 108.6), "P1 8\" CMU TO U/S OF BEAM")
    lnote(v, (30.0, L1 - 0.8), (24.0, 97.4), "THICKENED SLAB 2'-0\"x1'-0\" (S-301)")
    lnote(v, (50.0, L1 - 0.2), (55.0, 97.4), "5\" SOG, 15-MIL V.R., 6\" CA-6 (F-1)")
    lnote(v, (43.3, 104.0), (47.5, 105.0), "CW-5 CUBBIES (A-601)")
    lnote(v, (13.0, L1 + 6.5), (18.5, 108.4), "CASEWORK BEYOND (A-601)")
    lnote(v, (22.0, L2 - SLAB2 - 1.6), (24.5, 110.7), "W24x55 GIRDER BEYOND")


def notes_section_2(v):
    lnote(v, (FX - M.EXIST_WALL_T / 2, 109.6), (FX - 9.0, 117.0),
          "ENLARGED OPENING IN EXIST. WALL; NEW STEEL LINTEL (S-302, AD101)", width=1.6)
    lnote(v, (FX + 0.2, 114.9), (FX + 4.0, 121.5), "LINK-TO-EXIST. ROOF TIE-IN, SEE 3/A-312",
          width=None)
    lnote(v, (-26.0, LINK_ROOF + 0.25), (-30.0, 119.0) if False else (-26.0, 119.2),
          "ROOF R-2, TAPERED TO SCUPPER (A-103)")
    lnote(v, (-23.0, LINK_ROOF - 0.5), (-28.5, 111.2), "12K1 @ 5'-0\" O.C.")
    lnote(v, (-12.0, 103.5), (-8.0, 102.0), "SF-3 BEYOND")
    lnote(v, (0.0, 103.0), (4.0, 102.6) if False else (6.0, 98.0), "P1 CMU, DOOR PAIR 100A")
    lnote(v, (15.0, roof_top(15.0, 36.0)), (20.0, 133.0), "ROOF R-1 (SEE SECTION 1)")
    lnote(v, (40.0, ROOF - 0.5), (40.0, 125.0) if False else (45.0, 124.9), "12K1 @ 5'-0\" O.C.")
    lnote(v, (60.0, ROOF - 0.6), (64.0, 126.0) if False else (70.0, 124.9), "W12x14 TIE ON GRID")
    lnote(v, (90.0, L2 - SLAB2 - 0.6), (96.0, 110.9), "W12x19 GIRDER (B-C) ON GRID (S-102)")
    lnote(v, (2.0, W0_SHELF + 0.1), (-6.0, 125.0), "EW-1 ABOVE LINK ROOF, BRICK ON SHELF ANGLE @ "
          "115'-4\" (14/A-501)", width=1.75)


def notes_section_3(v):
    lnote(v, (-42.0 - 0.55, 103.0), (-48.5, 104.6), "SF-3 ON 8\" CONC. CURB", width=None)
    lnote(v, (-42.0, 110.6), (-49.0, 111.6), "LINTEL BEAM (S-302)")
    lnote(v, (-30.0, 106.0), (-24.5, 106.8), "HSS 5x5x1/4 COL.")
    lnote(v, (-33.0, LINK_ROOF + 0.3), (-28.0, 112.4), "ROOF R-2: 1/4\":12 TO SCUPPER")
    lnote(v, (-35.0, LINK_ROOF - 0.5), (-28.0, 110.8), "12K1 JOIST")
    lnote(v, (-36.0, W0_SHELF - 0.3), (-28.0, 116.3), "BASE FLASHING & SHELF ANGLE",
          width=None)


ASSEMBLIES = [
    ["R-1", "MAIN ROOF", "60-MIL EPDM FULLY ADHERED; 1/2\" GYPSUM COVER BOARD; TAPERED POLYISO 1/4\":12 "
     "TO DRAIN LINE (A-103, R-30 AVG.); SELF-ADHERED VAPOR RETARDER; 1 1/2\" TYPE B DECK; K-JOISTS @ 5'-0\""],
    ["R-2", "LINK ROOF", "60-MIL EPDM; 1/2\" COVER BD.; (2) LAYERS 2\" POLYISO + TAPERED 1/4\":12 TO SCUPPER; "
     "1 1/2\" TYPE B DECK ON 12K1 @ 5'-0\" O.C."],
    ["F-1", "SLAB ON GRADE", "5\" CONC. (4,000 PSI) W/ 6x6-W2.9xW2.9 WWF; 15-MIL VAPOR RETARDER; 6\" CA-6 "
     "BASE; 2\" XPS PERIMETER INSUL. 2'-0\" DEEP"],
    ["F-2", "LEVEL 2 FLOOR", "3 1/4\" LW CONC. ON 3\" 20 GA. COMPOSITE DECK (6 1/4\" TOTAL) ON STEEL BEAMS"],
    ["EW-1", "EXTERIOR WALL", "3 5/8\" FACE BRICK, 2\" AIR SPACE, 2\" POLYISO, FLUID-APPLIED AIR/WATER "
     "BARRIER, 8\" REINF. CMU (15 1/4\" TOTAL)"],
]

SECTION_NOTES = [
    "SEE A-311 / A-312 FOR WALL SECTIONS AND A-501 FOR EXTERIOR DETAILS. STRUCTURAL MEMBERS ARE SHOWN "
    "FOR COORDINATION; SIZES, CONNECTIONS AND REINFORCING PER S-SHEETS.",
    "CEILING HEIGHTS PER ROOM FINISH SCHEDULE (A-801) AND RCPs (A-121 / A-122): CLASSROOMS 10'-0\", "
    "CORRIDORS AND LINK 9'-6\", TOILETS / WORKROOM 9'-0\" AFF.",
    "INTERIOR CMU PARTITIONS EXTEND TO UNDERSIDE OF DECK; WHERE A BEAM RUNS ALONG THE WALL (GRIDS B AND C) "
    "THE CMU STOPS AT THE UNDERSIDE OF THE BEAM WITH DEFLECTION ANCHORS.",
    "AT LEVEL 2 THE SPANDREL / GIRDER IS ON THE GRID WITHIN THE CMU BACKUP: CMU STOPS AT 112'-0\" AND "
    "RESUMES ON THE SLAB EDGE AT 114'-0\" (9/A-501). AT THE ROOF THE SPANDREL IS INBOARD (OUTER FLANGE "
    "1/2\" FROM INSIDE FACE OF CMU) AND THE CMU IS CONTINUOUS TO THE PARAPET (8/A-501).",
    "ROOF DRAINS, OVERFLOW DRAINS, LEADERS AND RTUs BY DIV. 22 / 23 (NOT IN THIS SET), SHOWN FOR "
    "COORDINATION. TAPERED INSULATION LAYOUT AND CRICKETS PER A-103.",
    "EXISTING CONSTRUCTION SHOWN SCREENED; FIELD VERIFY EXISTING FLOOR, ROOF AND OPENING ELEVATIONS.",
]


def hatch_legend(sh, x, y, items=None):
    sh.text((x, y), "MATERIAL INDICATIONS (IN SECTION)", size=TXT["label"], font=FONT_B, valign="top",
            underline=True)
    yy = y - 0.3
    items = items or [("concrete", "CONCRETE"), ("cmu", "CONCRETE MASONRY (CMU)"),
                      ("brick", "FACE BRICK"), ("insul", "RIGID INSULATION"),
                      ("gravel", "CA-6 GRANULAR BASE"), ("earth", "COMPACTED EARTH / SUBGRADE"),
                      ("wood", "PT WOOD BLOCKING"), ("steel", "STEEL (CUT)")]
    for k, label in items:
        r = (x, yy - 0.18, 0.5, 0.18)
        if k == "concrete":
            sh.rect(*r, lw="thin", fill="white", hatch="concrete", hatch_kw=dict(scale=0.6))
        elif k == "cmu":
            sh.rect(*r, lw="thin", fill="white", hatch="ansi31", hatch_kw=dict(spacing=0.03))
        elif k == "brick":
            sh.rect(*r, lw="thin", fill="white", hatch="ansi31", hatch_kw=dict(spacing=0.018))
        elif k == "insul":
            sh.rect(*r, lw="thin", fill="white", hatch="insul", hatch_kw=dict(spacing=0.07))
        elif k == "gravel":
            sh.rect(*r, lw="thin", fill="white", hatch="gravel", hatch_kw=dict(scale=0.45))
        elif k == "earth":
            sh.rect(*r, lw="thin", fill="white", hatch="earth", hatch_kw=dict(spacing=0.2))
        elif k == "wood":
            sh.rect(*r, lw="thin", fill="white", hatch="wood")
        elif k == "batt":
            sh.rect(*r, lw="thin", fill="g10")
        else:
            sh.rect(*r, lw="thin", fill="g40")
        sh.text((x + 0.62, yy - 0.09), label, size=TXT["small"], valign="mid")
        yy -= 0.26
    return y - yy


def draw_a301(sh):
    # ---- section 2 (top, 1/8") ----
    S2 = 1 / 8
    h0, h1 = FX - 12.0, 150 + OUT + 12.0 + 1.2 / S2
    ox = (sh.x0 + sh.x1) / 2 - (h0 + h1) / 2 * S2
    oy = sh.y1 - 0.4 - (RTU_TOP + 4.0 - L1) * S2
    v2 = sh.view(ox, oy, S2, mx=0.0, my=L1)
    section_2(v2)
    notes_section_2(v2)
    ws_ref(v2, 150 - 1.6, 150 + 2.4, BOF - 0.5, PARAPET + 1.5, 1, "A-312")
    grid_bubbles(v2, [(x, k) for k, x in M.GRID_X.items()] + [(x, k) for k, x in M.LINK_GRID_X.items()],
                 0, PARAPET + COPE_UP + 0.6, RTU_TOP + 2.8, dia=0.32)
    dchain(v2, [(x, BOF - 2.4) for x in [FX] + sorted(M.LINK_GRID_X.values()) + sorted(M.GRID_X.values())],
           0.0, size=TXT["tiny"])
    sec_levels(v2, 150 + OUT + 12.0, 150 + OUT + 0.6, side="r",
               extra=[(LINK_PAR, "LINK T.O. PARAPET")] if False else ())
    dchain(v2, [(150 + OUT + 4.0, z) for z in (L1, L2, ROOF, PARAPET)], 0.0, size=TXT["tiny"])
    v2.dim((150 + OUT + 7.0, GRADE), (150 + OUT + 7.0, PARAPET), 0.0, size=TXT["tiny"])
    for x in (66.0,):
        for lev, zf in (("L1", L1), ("L2", L2)):
            r = room_at(lev, x, 36.0)
            v2.dim((x, zf), (x, zf + r.clg_ht), 0.0, size=TXT["tiny"], text=ftxt(r.clg_ht) + " CLG.")
    ty = v2.to_paper((0, BOF - 6.0))[1]
    sh.view_title(v2.to_paper((h0, 0))[0], ty, 2, "LONGITUDINAL BUILDING SECTION", S2, width=7.5,
                  note="AT CORRIDOR, y = 36'-0\", LOOKING NORTH")
    # ---- section 1 (bottom left, 3/16") ----
    S1 = 3 / 16
    top = ty - 0.6
    ox1 = sh.x0 + 0.6 + 16.0 * S1
    oy1 = top - (RTU_TOP + 3.8 - L1) * S1
    v1 = sh.view(ox1, oy1, S1, mx=0.0, my=L1)
    section_1(v1)
    section_dims_1(v1)
    notes_section_1(v1)
    ws_ref(v1, 72 - 1.6, 72 + 2.6, BOF - 0.5, PARAPET + 1.0, 1, "A-311", sim=True)
    ws_ref(v1, -2.6, 1.6, BOF - 0.5, PARAPET + 1.0, 2, "A-311", sim=True)
    ty1 = v1.to_paper((0, BOF - 6.0))[1]
    sh.view_title(v1.to_paper((-14.0, 0))[0], ty1, 1, "TRANSVERSE BUILDING SECTION", S1, width=7.5,
                  note="AT x = 75'-0\", LOOKING WEST")
    # ---- section 3 (bottom right, 3/16") ----
    S3 = 3 / 16
    ox3 = sh.x0 + 21.6 + 55.0 * S3
    v3 = sh.view(ox3, oy1, S3, mx=0.0, my=L1)
    section_3(v3)
    notes_section_3(v3)
    ws_ref(v3, -42.0 - 1.4, -42.0 + 1.4 * 0 + 1.0, BOF - 0.5, LINK_PAR + 1.0, 2, "A-312", sim=True)
    grid_bubbles(v3, [(-42.0, "B"), (-30.0, "C")], 0, PARAPET + COPE_UP + 0.6, RTU_TOP + 3.5, dia=0.32)
    dchain(v3, [(-42.0, BOF - 2.2), (-30.0, BOF - 2.2)], 0.0, size=TXT["tiny"])
    sec_levels(v3, -17.0 + 9.0, -17.0 + 0.6, side="r",
               extra=[(LINK_ROOF + 0.001, ""), (LINK_PAR, "LINK T.O. PARAPET")][1:])
    ty3 = v3.to_paper((0, BOF - 6.0))[1]
    sh.view_title(v3.to_paper((-53.0, 0))[0], ty3, 3, "LINK SECTION", S3, width=5.0,
                  note="AT x = -18'-0\", LOOKING EAST")
    # ---- notes band ----
    top = min(ty1, ty3) - 0.6
    sh.line((sh.x0, top + 0.15), (sh.x1, top + 0.15), lw="thin")
    notes_block(sh, sh.x0 + 0.3, top, "BUILDING SECTION NOTES", SECTION_NOTES, 10.2)
    table(sh, sh.x0 + 11.0, top, [("MARK", 0.55), ("ASSEMBLY", 1.35), ("DESCRIPTION", 11.2)],
          ASSEMBLIES, row_h=0.2, size=TXT["small"], title="ASSEMBLY SCHEDULE (SECTIONS)",
          align=["c", "l", "l"])
    hatch_legend(sh, sh.x0 + 24.9, top)


# =============================================================================================
SHEETS = [
    ("A-201", "EXTERIOR ELEVATIONS", draw_a201),
    ("A-202", "EXTERIOR ELEVATIONS", draw_a202),
    ("A-301", "BUILDING SECTIONS", draw_a301),
]
