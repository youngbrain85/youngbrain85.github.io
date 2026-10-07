"""
S-series structural sheets: general notes, foundation plan, second floor framing plan,
roof framing plan (incl. link roof), foundation details, masonry & steel details, schedules.

Structural system (see DESIGN.md section 7):
* Steel frame (HSS columns embedded in the CMU walls, composite floor, K-joist roof) with
  ordinary reinforced masonry shear walls (exterior CMU backup, stair and elevator walls).
* Exterior CMU backup is continuous 99'-4" to 131'-4" (48 courses).  To keep it continuous the
  perimeter beams on grids A and D and the girders / ties on grids 1 and 6 are set 7 1/2"
  inboard of the grid (inside face of CMU + 13/16" clear to flange tip).
* All framing members are defined once below (L2_MEMBERS, ROOF_MEMBERS, joists) and used both
  to draw the plans and to generate the S-401 beam / joist schedules, so quantities agree.
"""
from __future__ import annotations

import math
from collections import OrderedDict

from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from . import model as M
from . import plans as PL
from .cad import (FONT, FONT_B, FONT_I, TXT, Paper, View, _section_bubble, break_line,
                  detail_callout, fmt_ftin, fmt_in, grid_bubble, keynote_tag, level_marker,
                  notes_block, table, vadd, vlen, vmul, vnorm, vperp, vsub, wrap_lines)

IN = M.IN
SCALE = 1 / 8
CMUh = M.CMU_T / 2

# ----------------------------------------------------------------------------------------
# Elevations (feet, architectural datum)
# ----------------------------------------------------------------------------------------
EL_TOF = M.LEVELS["TOF"]            # 96'-4"
EL_BOF = M.LEVELS["BOF"]            # 95'-4"
EL_LEDGE = M.LEVELS["LEDGE"]        # 99'-0"
EL_TOW = M.LEVELS["GRADE"]          # 99'-4"
EL_L1 = M.LEVELS["L1"]
EL_L2 = M.LEVELS["L2"]              # T.O. slab 114'-0"
SLAB2_T = 6.25 * IN                 # 3" deck + 3 1/4" LW topping
EL_TOS2 = EL_L2 - SLAB2_T           # 113'-5 3/4"
EL_ROOF = M.LEVELS["ROOF"]          # T.O. joist top chord / deck bearing 128'-0"
EL_ROOF_BM = EL_ROOF - 2.5 * IN     # T.O. beams supporting joists (2 1/2" seats)
EL_LINK = M.LEVELS["LINK_ROOF"]     # 114'-0"
EL_TOF_INT = 98 + 8 * IN            # interior F1 top of footing
EL_PIT = 95.0                       # T.O. elevator pit slab
EL_COL_TOP = EL_ROOF_BM             # T.O. column cap plate

OFF = 7.5 * IN                      # perimeter steel offset inboard of grid
XG = M.GRID_X
YG = M.GRID_Y
X1, X6 = 0.0, 150.0
XO1, XO6 = X1 + OFF, X6 - OFF       # offset perimeter lines on grids 1 / 6
YOD, YOA = 0.0 + OFF, 72.0 - OFF    # offset perimeter lines on grids D / A

ST1 = PL.stair_geom("ST-1")
ST2 = PL.stair_geom("ST-2")
Y_HDR1 = ST1["f_hi"]                # stair 1 opening edge (top riser line at L2)
Y_HDR2 = ST2["f_lo"]                # stair 2 opening edge

# foundation wall / footing offsets from grid (+ toward exterior), feet
FW_IN, FW_OUT, FW_LEDGE = -4.5 * IN, 11.5 * IN, 7.5 * IN
CF_IN, CF_OUT = -11.5 * IN, 18.5 * IN

# elevator hoistway / pit
HX0, HX1, HY0, HY1 = 21 + CMUh, 30 - CMUh, 21 + CMUh, 30 - CMUh      # pit inside faces
PIT_WALL = 1.0
MAT = (HX0 - PIT_WALL - 1.0, HY0 - PIT_WALL - 1.0, HX1 + PIT_WALL + 3.0, HY1 + PIT_WALL + 3.0)

# ----------------------------------------------------------------------------------------
# Columns
# ----------------------------------------------------------------------------------------
COL_TYPES = OrderedDict([
    ("C1", dict(size="HSS6x6x3/8", b=0.5, bp="PL 3/4\"x12\"x12\"", rods="(4) 3/4\" DIA. x 1'-3\"",
                rod_g="8\" x 8\"", base=EL_TOW, fdn="F2", desc="GRIDS A & D (IN EXT. CMU)")),
    ("C2", dict(size="HSS6x6x1/2", b=0.5, bp="PL 3/4\"x12\"x12\"", rods="(4) 3/4\" DIA. x 1'-3\"",
                rod_g="8\" x 8\"", base=EL_TOF_INT + 1.5 * IN, fdn="F1",
                desc="GRIDS B & C, INTERIOR (IN CORRIDOR CMU)")),
    ("C3", dict(size="HSS6x6x1/2", b=0.5, bp="PL 3/4\"x12\"x12\"", rods="(4) 3/4\" DIA. x 1'-3\"",
                rod_g="8\" x 8\"", base=EL_TOW, fdn="F1",
                desc="GRIDS B & C AT EXT. WALLS (GRIDS 1 & 6)")),
    ("C4", dict(size="HSS5x5x1/4", b=5 / 12, bp="PL 1\"x12\"x12\"", rods="(4) 3/4\" DIA. x 1'-6\"",
                rod_g="8\" x 8\"", base=EL_TOW, fdn="F3", desc="LINK (MOMENT BASE)")),
])


def columns():
    out = []
    for gy in ("A", "B", "C", "D"):
        for gx in ("1", "2", "3", "4", "5", "6"):
            x, y = XG[gx], YG[gy]
            if gy in ("A", "D"):
                t = "C1"
            elif gx in ("1", "6"):
                t = "C3"
            else:
                t = "C2"
            fdn = COL_TYPES[t]["fdn"]
            top = EL_COL_TOP
            if gx == "2" and gy == "C":
                fdn = "PIT"
            out.append(dict(grid=f"{gx}/{gy}", x=x, y=y, type=t, fdn=fdn, top=top))
    for gx, x in M.LINK_GRID_X.items():
        for gy, y in (("C", 30.0), ("B", 42.0)):
            out.append(dict(grid=f"{gx}/{gy}", x=x, y=y, type="C4",
                            fdn="F3E" if gx == "L1" else "F3", top=EL_LINK - 12 * IN))
    return out


# ----------------------------------------------------------------------------------------
# Framing members
# ----------------------------------------------------------------------------------------
WT = {"W24x55": 55, "W18x35": 35, "W16x31": 31, "W16x26": 26, "W12x19": 19, "W12x14": 14,
      "W12x26": 26, "W8x10": 10, "W8x18": 18, "W16x40": 40, "HSS8x8x1/2": 48.85, "C8x11.5": 11.5,
      "L4x4x1/4": 6.6, "W10x22": 22}


def _m(size, p1, p2, studs=0, camber="", role="", tos=None, note=""):
    return dict(size=size, p1=p1, p2=p2, studs=studs, camber=camber, role=role, tos=tos,
                note=note)


def l2_members():
    """Level 2 composite floor framing (T.O. slab 114'-0", T.O. steel 113'-5 3/4")."""
    m = []
    xs = [XO1, 30.0, 60.0, 90.0, 120.0, XO6]
    bays = list(zip(xs[:-1], xs[1:]))
    gx = [XO1, 30.0, 60.0, 90.0, 120.0, XO6]
    # spandrels (A, D) - offset inboard
    for a, b in bays:
        m.append(_m("W16x31", (a, YOD), (b, YOD), 16, "", "SPANDREL"))
        m.append(_m("W16x31", (a, YOA), (b, YOA), 16, "", "SPANDREL"))
    # corridor beams on B and C (on grid, column to column)
    for a, b in zip([0.0, 30.0, 60.0, 90.0, 120.0], [30.0, 60.0, 90.0, 120.0, 150.0]):
        m.append(_m("W18x35", (a, 30.0), (b, 30.0), 20, "", "BEAM B/C"))
        m.append(_m("W18x35", (a, 42.0), (b, 42.0), 20, "", "BEAM B/C"))
    # girders on numbered grids
    for x in gx:
        m.append(_m("W24x55", (x, YOD), (x, 30.0), 24, '3/4"', "GIRDER"))
        m.append(_m("W24x55", (x, 42.0), (x, YOA), 24, '3/4"', "GIRDER"))
    for x in (30.0, 60.0, 90.0, 120.0, XO6):
        m.append(_m("W12x19", (x, 30.0), (x, 42.0), 8, "", "GIRDER B-C"))
    # grid 1 between C and B carries EW-1 (W0) above the link roof: on grid
    m.append(_m("W16x31", (0.0, 30.0), (0.0, 42.0), 0, "", "GIRDER B-C",
                note="SUPPORTS EW-1 ABOVE"))
    # infill beams
    for y in (10.0, 20.0, 52.0, 62.0):
        for a, b in bays:
            if y == 10.0 and a == XO1:
                m.append(_m("W16x26", (12.0, y), (b, y), 14, "", "INFILL"))
                continue
            if y == 62.0 and b == XO6:
                m.append(_m("W16x26", (a, y), (138.0, y), 14, "", "INFILL"))
                continue
            m.append(_m("W16x26", (a, y), (b, y), 22, '3/4"', "INFILL"))
    # stair headers
    m.append(_m("W16x26", (XO1, Y_HDR1), (30.0, Y_HDR1), 18, '1/2"', "HEADER", note="STAIR 1"))
    m.append(_m("W16x26", (120.0, Y_HDR2), (XO6, Y_HDR2), 18, '1/2"', "HEADER", note="STAIR 2"))
    # stair trimmers (x = 12 and x = 138 lines)
    for a, b in ((YOD, Y_HDR1), (Y_HDR1, 20.0), (20.0, 30.0)):
        m.append(_m("W12x19", (12.0, a), (12.0, b), 0, "", "TRIMMER"))
    for a, b in ((42.0, 52.0), (52.0, Y_HDR2), (Y_HDR2, YOA)):
        m.append(_m("W12x19", (138.0, a), (138.0, b), 0, "", "TRIMMER"))
    # elevator hoistway framing (supports L2 hoistway CMU)
    m.append(_m("W12x19", (21.0, 20.0), (21.0, 30.0), 0, "", "HOISTWAY"))
    m.append(_m("W12x19", (21.0, 21.0), (30.0, 21.0), 0, "", "HOISTWAY"))
    # beams under L2 toilet-room CMU walls B41 / B49
    for x in (41.0, 49.0):
        m.append(_m("W12x19", (x, 10.0), (x, 20.0), 0, "", "UNDER CMU"))
        m.append(_m("W12x19", (x, 20.0), (x, 30.0), 0, "", "UNDER CMU"))
    return m


def roof_members():
    """Main roof steel (T.O. joists / deck bearing 128'-0")."""
    m = []
    xs = [XO1, 30.0, 60.0, 90.0, 120.0, XO6]
    bays = list(zip(xs[:-1], xs[1:]))
    for a, b in bays:
        m.append(_m("W16x26", (a, YOD), (b, YOD), 0, "", "EDGE BEAM", EL_ROOF_BM))
        m.append(_m("W16x26", (a, YOA), (b, YOA), 0, "", "EDGE BEAM", EL_ROOF_BM))
    for a, b in zip([0.0, 30.0, 60.0, 90.0, 120.0], [30.0, 60.0, 90.0, 120.0, 150.0]):
        m.append(_m("W18x35", (a, 30.0), (b, 30.0), 0, "", "JOIST BEAM", EL_ROOF_BM))
        m.append(_m("W18x35", (a, 42.0), (b, 42.0), 0, "", "JOIST BEAM", EL_ROOF_BM))
    for x in [XO1, 30.0, 60.0, 90.0, 120.0, XO6]:
        for a, b in ((YOD, 30.0), (30.0, 42.0), (42.0, YOA)):
            m.append(_m("W12x14", (x, a), (x, b), 0, "", "TIE", EL_ROOF))
    # elevator hoist beam (MRL elevator; 5,000 lb rated) bearing on hoistway walls
    m.append(_m("W10x22", (21.0 - 0.5, 25.5), (30.0 + 0.5, 25.5), 0, "", "HOIST BEAM", 126.0,
                note="HOIST BEAM"))
    return m


def link_members():
    """Link roof steel (T.O. steel 114'-0")."""
    m = []
    for y, yb in ((30.0, 30.0 + OFF), (42.0, 42.0 - OFF)):
        m.append(_m("W12x19", (-35.0, yb), (-18.0, yb), 0, "", "LINK BEAM", EL_LINK))
        m.append(_m("W12x19", (-18.0, yb), (0.0, yb), 0, "", "LINK BEAM", EL_LINK))
        m.append(_m("HSS8x8x1/2", (-35.0, y), (-18.0, y), 0, "", "SF HEAD", 110.0))
        m.append(_m("HSS8x8x1/2", (-18.0, y), (0.0, y), 0, "", "SF HEAD", 110.0))
    for x in (-35.0, -18.0):
        m.append(_m("W8x18", (x, 30.0 + OFF), (x, 42.0 - OFF), 0, "", "LINK TIE", EL_LINK))
    for x in LINK_PURLINS:
        m.append(_m("W8x10", (x, 30.0 + OFF), (x, 42.0 - OFF), 0, "", "PURLIN", EL_LINK))
    return m


LINK_PURLINS = [-35.0 + 17 / 3, -35.0 + 34 / 3, -12.0, -6.0, -1.5]

# roof joists ------------------------------------------------------------------------------
RD = [(15.0, 36.0), (52.5, 36.0), (97.5, 36.0), (135.0, 36.0)]
OD = [(x + 2.0, y) for x, y in RD]
RTUS = [("RTU-1", 45.0, 57.0), ("RTU-2", 105.0, 57.0), ("RTU-3", 105.0, 15.0)]
CURB_W, CURB_D = 14.0, 7.0
HATCH = (46.75, 27.0, 2.5, 3.0)   # center x, y, E-W, N-S


def _joist_xs():
    xs = []
    for k in range(1, 30):
        x = 5.0 * k
        if abs(x % 30.0) < 1e-6:
            continue
        xs.append(x)
    return xs


def roof_joists():
    """list of dict(x, y0, y1, type, special)"""
    out = []
    rtu_x = {}
    for name, cx, cy in RTUS:
        for x in _joist_xs():
            if cx - CURB_W / 2 < x < cx + CURB_W / 2:
                rtu_x.setdefault((x, "N" if cy > 36 else "S"), name)
    for x in _joist_xs():
        out.append(dict(x=x, y0=YOD, y1=30.0, type="22K6",
                        special=rtu_x.get((x, "S"))))
        out.append(dict(x=x, y0=42.0, y1=YOA, type="22K6",
                        special=rtu_x.get((x, "N"))))
        xc = x
        if abs(x - 15.0) < 1e-6 or abs(x - 135.0) < 1e-6:
            xc = x - 1.0      # shifted clear of roof drains RD-1 / RD-4
        out.append(dict(x=xc, y0=30.0, y1=42.0, type="12K1", special=None,
                        shifted=(xc != x)))
    return out


# ----------------------------------------------------------------------------------------
# Generic drawing helpers
# ----------------------------------------------------------------------------------------

def _plan_view(sh):
    """same placement as A-101 / A-102 so the plans overlay"""
    ox = sh.x0 + 0.35 + 66 * SCALE
    oy = sh.y1 - 0.35 - 91 * SCALE
    return sh.view(ox, oy, SCALE)


def _ptxt(c, at, s, size=TXT["small"], anchor="c", valign="mid", rot=0.0, font=FONT, bg=True,
          pad=0.018, color="black"):
    """paper-space text with an optional white mask behind it (at = paper inches)"""
    p = Paper(c)
    w = p.text_width(s, size, font)
    h = size / 72.0
    if bg:
        dx = {"l": 0, "c": -w / 2, "r": -w}[anchor]
        dy = {"mid": -h * 0.5, "base": -h * 0.22, "top": -h * 0.95, "bot": -h * 0.22}[valign]
        corners = [(dx - pad, dy - pad), (dx + w + pad, dy - pad), (dx + w + pad, dy + h + pad),
                   (dx - pad, dy + h + pad)]
        a = math.radians(rot)
        ca, sa = math.cos(a), math.sin(a)
        pts = [(at[0] + x * ca - y * sa, at[1] + x * sa + y * ca) for x, y in corners]
        p.polygon(pts, lw=None, fill="white", stroke=False)
    p.text(at, s, size=size, anchor=anchor, valign=valign, rot=rot, font=font, color=color)
    return w


def _vtxt(v, at, s, size=TXT["small"], anchor="c", valign="mid", rot=0.0, font=FONT, bg=True,
          color="black"):
    return _ptxt(v.c, v.to_paper(at), s, size, anchor, valign, rot, font, bg, color=color)


def _tag_box(v, at, s, size=TXT["small"], font=FONT_B, shape="rect"):
    p = Paper(v.c)
    x, y = v.to_paper(at)
    w = p.text_width(s, size, font) + 0.08
    h = size / 72.0 + 0.06
    if shape == "rect":
        p.rect(x - w / 2, y - h / 2, w, h, lw="fine", fill="white")
    elif shape == "round":
        r = h / 2
        p.rect(x - w / 2, y - h / 2, w, h, lw="fine", fill="white")
        p.circle((x - w / 2, y), r * 0.001, lw=None)
    elif shape == "hex":
        d = h / 2
        pts = [(x - w / 2 - d * 0.6, y), (x - w / 2, y + d), (x + w / 2, y + d),
               (x + w / 2 + d * 0.6, y), (x + w / 2, y - d), (x - w / 2, y - d)]
        p.polygon(pts, lw="fine", fill="white")
    elif shape == "circle":
        r = max(w, h) / 2
        p.circle((x, y), r, lw="fine", fill="white")
    p.text((x, y), s, size=size, font=font, anchor="c", valign="mid")


def _col_tag(v, at, s, size=TXT["tiny"]):
    p = Paper(v.c)
    x, y = v.to_paper(at)
    r = 0.075
    p.circle((x, y), r, lw="fine", fill="white")
    p.text((x, y), s, size=size, font=FONT_B, anchor="c", valign="mid")


def _sec_cut(v, a, b, num, sheet, r=0.15):
    """single-ended section cut: heavy line a->b, bubble at a looking toward b's left"""
    v.line(a, b, lw="med")
    d = vnorm(vsub(b, a))
    _section_bubble(v, a, vperp(d), num, sheet, r=r)


def _sec_cut2(v, a, b, num, sheet, look_dir, r=0.15):
    """cut line a-b with bubble at a; pointer toward look_dir (model unit vector)"""
    v.line(a, b, lw="med", dash="phantom")
    _section_bubble(v, a, look_dir, num, sheet, r=r)


def _grids(v, ytop=88.5, ybot=-16.0, xw=-14.0, xe=166.0, link=True, link_y=(21.0, 51.0),
           dia=0.42):
    for lab, x in M.GRID_X.items():
        v.line((x, ybot), (x, ytop), lw="hair", dash="grid")
        grid_bubble(v, (x, ybot - v.paper_len(dia / 2)), lab, dia)
        grid_bubble(v, (x, ytop + v.paper_len(dia / 2)), lab, dia)
    for lab, y in M.GRID_Y.items():
        west = lab in ("A", "D")
        x0 = xw if west else M.EXIST_FACE_X
        v.line((x0, y), (xe, y), lw="hair", dash="grid")
        if west:
            grid_bubble(v, (xw - v.paper_len(dia / 2), y), lab, dia)
        grid_bubble(v, (xe + v.paper_len(dia / 2), y), lab, dia)
    if link:
        d2 = dia * 0.85
        for lab, x in M.LINK_GRID_X.items():
            v.line((x, link_y[0]), (x, link_y[1]), lw="hair", dash="grid")
            grid_bubble(v, (x, link_y[1] + v.paper_len(d2 / 2)), lab, d2)
            grid_bubble(v, (x, link_y[0] - v.paper_len(d2 / 2)), lab, d2)


def _grid_dims(v, top=79.5, top2=83.5, east=157.0, east2=161.0, link_y=None):
    gx = list(M.GRID_X.values())
    v.dim_chain([(x, top) for x in gx], 0, size=TXT["small"], ext=False)
    for x in gx:
        v.line((x, top - 1.2), (x, top2 + 0.8), lw="hair")
    v.dim((0, top2), (150, top2), 0, size=TXT["small"], ext=False)
    gy = sorted(M.GRID_Y.values())
    v.dim_chain([(east, y) for y in gy], 0, size=TXT["small"], ext=False)
    for y in gy:
        v.line((east - 1.2, y), (east2 + 0.8, y), lw="hair")
    v.dim((east2, 0), (east2, 72), 0, size=TXT["small"], ext=False)
    if link_y is not None:
        pts = [(M.EXIST_FACE_X, link_y), (-35.0, link_y), (-18.0, link_y), (0.0, link_y)]
        v.dim_chain(pts, 0, size=TXT["tiny"], ext=False)
        for p in pts:
            v.line((p[0], link_y - 0.9), (p[0], link_y + 0.9), lw="hair")


def _column(v, x, y, b, fill="black"):
    v.rect(x - b / 2, y - b / 2, b, b, lw="thin", fill=fill)


def _existing(v, y0=-8.0, y1=80.0, footing=True, label=True):
    """existing building fragment west of the link (screened)"""
    fx = M.EXIST_FACE_X
    xc = -60.0
    g = box(fx - M.EXIST_WALL_T, y0, fx, y1).difference(box(fx - 2, 30 + CMUh, fx + 0.1, 42 - CMUh))
    v.geom(g, lw="thin", color="screen", fill="g10", hatch="ansi31",
           hatch_kw=dict(spacing=0.05, col="screen"))
    if footing:
        v.rect(fx - M.EXIST_WALL_T / 2 - 1.0, y0, 2.0, y1 - y0, lw="fine", dash="hidden",
               color="screen")
    for yy in (30 - CMUh, 42 + CMUh):
        v.line((xc, yy), (fx - 1, yy), lw="fine", color="screen")
    break_line(v, (xc, y0), (xc, y1), zig=0.12)
    v.line((xc, y0), (fx - 1, y0), lw="fine", color="screen")
    v.line((xc, y1), (fx - 1, y1), lw="fine", color="screen")
    if label:
        v.mtext((xc + 11.5, 58), ["EXISTING BUILDING", "1-STORY, OCCUPIED", "(NO STRUCTURAL WORK", "EXCEPT AS NOTED)"],
                size=TXT["small"], font=FONT_B, anchor="c", valign="mid", color="screen")


def _beam(v, p1, p2, label=None, lw="heavy", gap=0.045, size=TXT["tiny"], side=1, dash=None,
          color="black", lab_at=0.5, lab_off=0.075):
    """beam centerline with small end gaps (simple connections) + label along the member."""
    d = vsub(p2, p1)
    L = vlen(d)
    u = vnorm(d)
    g = v.paper_len(gap)
    a = vadd(p1, vmul(u, g))
    b = vsub(p2, vmul(u, g))
    v.line(a, b, lw=lw, dash=dash, color=color)
    if label:
        n = vperp(u)
        if u[0] < -1e-9 or (abs(u[0]) < 1e-9 and u[1] < 0):
            n = vmul(n, -1)
        mid = vadd(p1, vmul(d, lab_at))
        at = vadd(mid, vmul(n, side * v.paper_len(lab_off)))
        ang = math.degrees(math.atan2(u[1], u[0]))
        if ang > 90.01 or ang < -89.99:
            ang -= 180
        _vtxt(v, at, label, size=size, rot=ang, bg=True)


def _mlabel(mm, short=False):
    s = mm["size"]
    if mm.get("studs"):
        s += f" [{mm['studs']}]"
    if mm.get("camber"):
        s += f" c={mm['camber']}"
    return s


def _deck_arrow(v, at, direction="ns", length=0.75, label=None, size=TXT["tiny"]):
    """deck span symbol: double-headed arrow along the span with a cross bar"""
    p = Paper(v.c)
    x, y = v.to_paper(at)
    L = length / 2
    if direction == "ns":
        a, b = (x, y - L), (x, y + L)
        c1, c2 = (x - 0.09, y), (x + 0.09, y)
    else:
        a, b = (x - L, y), (x + L, y)
        c1, c2 = (x, y - 0.09), (x, y + 0.09)
    p.line(a, b, lw="thin")
    p.line(c1, c2, lw="thin")
    for tip, other in ((a, b), (b, a)):
        u = vnorm(vsub(tip, other))
        nrm = vperp(u)
        base = vsub(tip, vmul(u, 0.08))
        p.polygon([tip, vadd(base, vmul(nrm, 0.03)), vsub(base, vmul(nrm, 0.03))], lw="fine",
                  fill="black")
    if label:
        lines = label if isinstance(label, list) else [label]
        if direction == "ns":
            p.mtext((x + 0.06, y - 0.02), lines, size=size, anchor="l", valign="top",
                    leading=size * 1.15)
        else:
            p.mtext((x, y - 0.05), lines, size=size, anchor="c", valign="top", leading=size * 1.15)


def _legend_line(p, x, y, kind, label, w=0.5, size=TXT["small"]):
    """single legend row at paper (x, y) (y = row center)"""
    if kind == "fdnwall":
        p.rect(x, y - 0.05, w, 0.1, lw="heavy", fill="g30")
    elif kind == "footing":
        p.rect(x, y - 0.06, w, 0.12, lw="fine", dash="hidden")
    elif kind == "ts":
        p.rect(x, y - 0.045, w, 0.09, lw="fine", dash=[2, 1.2])
    elif kind == "cmu":
        p.rect(x, y - 0.03, w, 0.06, lw="fine", fill="white", hatch="ansi31",
               hatch_kw=dict(spacing=0.03, col="g50"))
    elif kind == "cj":
        p.line((x, y), (x + w, y), lw="fine", dash="long")
    elif kind == "col":
        p.rect(x + w / 2 - 0.035, y - 0.035, 0.07, 0.07, lw="thin", fill="black")
    elif kind == "beam":
        p.line((x, y), (x + w, y), lw="heavy")
    elif kind == "joist":
        p.line((x, y), (x + w, y), lw="fine")
    elif kind == "bridging":
        p.line((x, y), (x + w, y), lw="hair", dash="hidden")
    elif kind == "opening":
        p.rect(x, y - 0.06, w, 0.12, lw="thin")
        p.line((x, y - 0.06), (x + w, y + 0.06), lw="hair")
        p.line((x, y + 0.06), (x + w, y - 0.06), lw="hair")
    elif kind == "depress":
        p.rect(x, y - 0.06, w, 0.12, lw="fine", fill="g10", hatch="dots",
               hatch_kw=dict(scale=0.6))
    elif kind == "existing":
        p.rect(x, y - 0.05, w, 0.1, lw="thin", color="screen", fill="g10", hatch="ansi31",
               hatch_kw=dict(spacing=0.05, col="screen"))
    elif kind == "wall_light":
        p.rect(x, y - 0.04, w, 0.08, lw="hair", fill="g15")
    p.text((x + w + 0.12, y), label, size=size, valign="mid")


# ----------------------------------------------------------------------------------------
# Foundation geometry
# ----------------------------------------------------------------------------------------

def _ring_band(lo, hi):
    """band between offsets lo..hi (ft, + exterior) around the L1 exterior wall outline"""
    P = M.outline_poly("L1")
    outer = P.buffer(hi, join_style=2, mitre_limit=10) if hi > 0 else P.buffer(hi, join_style=2)
    inner = P.buffer(lo, join_style=2, mitre_limit=10) if lo > 0 else P.buffer(lo, join_style=2)
    g = outer.difference(inner)
    g = g.difference(box(-300, -500, M.EXIST_FACE_X, 500))
    a = abs(min(lo, 0))
    g = g.difference(box(M.EXIST_FACE_X - 0.5, 30 + a + 1e-3, M.EXIST_FACE_X + a + 0.01, 42 - a - 1e-3))
    return g


def fdn_wall_geom():
    return _ring_band(FW_IN, FW_OUT)


def cf1_geom():
    return _ring_band(CF_IN, CF_OUT)


def footing_rects():
    """[(mark, shapely box, column dict)]"""
    out = []
    for c in columns():
        x, y = c["x"], c["y"]
        f = c["fdn"]
        if f == "F1":
            out.append(("F1", box(x - 3.5, y - 3.5, x + 3.5, y + 3.5), c))
        elif f == "F2":
            out.append(("F2", box(x - 2.5, y - 2.5, x + 2.5, y + 2.5), c))
        elif f == "F3":
            out.append(("F3", box(x - 2.0, y - 2.0, x + 2.0, y + 2.0), c))
        elif f == "F3E":
            out.append(("F3E", box(x - 0.5, y - 2.5, x + 4.0, y + 2.5), c))
    return out


def ts_walls():
    hoist = {"E21", "E21H", "S2b", "C3"}
    return [w for w in M.interior_walls("L1") if M.WALL_TYPES[w.type]["mat"] == "cmu"
            and w.id not in hoist]


def ts_geom():
    parts = []
    for w in ts_walls():
        p1, p2 = w.p1, w.p2
        ls = LineString(M._extend(p1, p2, 1.0))
        parts.append(ls.buffer(1.0, cap_style=2, join_style=2))
    g = unary_union(parts)
    g = g.difference(fdn_wall_geom().buffer(0.001))
    g = g.difference(box(HX0 - PIT_WALL, HY0 - PIT_WALL, HX1 + PIT_WALL, HY1 + PIT_WALL))
    return g


def pit_wall_geom():
    o = box(HX0 - PIT_WALL, HY0 - PIT_WALL, HX1 + PIT_WALL, HY1 + PIT_WALL)
    i = box(HX0, HY0, HX1, HY1)
    return o.difference(i)


STAIR_FTG = {
    "ST-1": (ST1["up"][0] - 0.5, ST1["f_hi"] - 1.0, ST1["x1"], ST1["f_hi"] + 1.0),
    "ST-2": (ST2["x0"], ST2["f_lo"] - 1.0, ST2["up"][1] + 0.5, ST2["f_lo"] + 1.0),
}
WOM_BOX = (140.0, 30 + CMUh, 150 - CMUh, 42 - CMUh)


def _cj_lines():
    """slab-on-grade control joint segments (max 15'-0" each way), clipped to room slabs"""
    segs = []
    for r in M.rooms("L1"):
        if r.num in ("108",):
            continue
        g = M.clear_room_poly(r)
        if g.is_empty:
            continue
        xs = [p[0] for p in r.poly]
        ys = [p[1] for p in r.poly]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        nx = math.ceil((x1 - x0) / 15.0 - 1e-6)
        ny = math.ceil((y1 - y0) / 15.0 - 1e-6)
        for i in range(1, nx):
            x = x0 + (x1 - x0) * i / nx
            ln = LineString([(x, y0 - 1), (x, y1 + 1)]).intersection(g)
            segs.append(ln)
        for j in range(1, ny):
            y = y0 + (y1 - y0) * j / ny
            ln = LineString([(x0 - 1, y), (x1 + 1, y)]).intersection(g)
            segs.append(ln)
    return segs


# ----------------------------------------------------------------------------------------
# S-101 FOUNDATION PLAN
# ----------------------------------------------------------------------------------------
FDN_NOTES = [
    "SEE S-001 FOR GENERAL STRUCTURAL NOTES, DESIGN CRITERIA AND SPECIAL INSPECTIONS. SEE S-301 FOR FOUNDATION DETAILS AND S-401 FOR FOOTING AND COLUMN SCHEDULES.",
    "FOOTINGS ARE DESIGNED FOR AN ASSUMED NET ALLOWABLE SOIL BEARING PRESSURE OF 3,000 PSF ON UNDISTURBED NATIVE SOIL OR ENGINEERED FILL. THE OWNER'S TESTING AGENCY SHALL VERIFY BEARING AT EVERY FOOTING EXCAVATION BEFORE PLACING CONCRETE.",
    "T.O. FOOTING = 96'-4\" (BOTTOM 95'-4\", 4'-0\" BELOW FINISH GRADE FOR FROST) UNLESS NOTED. INTERIOR F1 FOOTINGS: T.O.F. = 98'-8\". FINISH FLOOR 100'-0\" = CIVIL 712.50.",
    "CF-1 = 2'-6\" x 1'-0\" CONTINUOUS FOOTING UNDER ALL EXTERIOR WALLS, CENTERED UNDER THE FOUNDATION WALL (11 1/2\" INSIDE / 1'-6 1/2\" OUTSIDE OF GRID). CF-1 IS CONTINUOUS THROUGH F2 / F1 / F3 COLUMN FOOTINGS.",
    "FOUNDATION WALLS: 1'-0\" ABOVE BRICK LEDGE (99'-0\") / 1'-4\" BELOW, INSIDE FACE 4 1/2\" INSIDE OF GRID. T.O. WALL 99'-4\" UNLESS NOTED. OMIT BRICK LEDGE AT STOREFRONTS AND EXTERIOR DOORS.",
    "TS-1 = 2'-0\" WIDE x 1'-0\" DEEP THICKENED SLAB CENTERED UNDER EVERY LEVEL 1 INTERIOR CMU WALL (P1 / P2). CONTINUOUS THROUGH DOOR OPENINGS. HOISTWAY CMU BEARS ON ELEVATOR PIT WALLS.",
    "SLAB ON GRADE: 5\" CONCRETE (4,000 PSI) WITH 6x6-W2.9xW2.9 WWF (FLAT SHEETS, CHAIRED 1 1/2\" FROM TOP) ON 15-MIL VAPOR RETARDER ON 6\" COMPACTED CA-6 BASE. T.O. SLAB = 100'-0\" UNLESS NOTED.",
    "SAWCUT CONTROL JOINTS (SHOWN DASHED) 1 1/4\" DEEP WITHIN 12 HOURS OF FINISHING; MAX. PANEL 15'-0\" EACH WAY, ASPECT RATIO 1.5 MAX. ALIGN JOINTS WITH CORNERS OF WALLS AND OPENINGS. SEE 4/S-301.",
    "PERIMETER INSULATION: 2\" XPS (R-10) VERTICAL ON INSIDE FACE OF FOUNDATION WALL TO 2'-0\" BELOW T.O. SLAB, SEE 1/S-301.",
    "COLUMN MARKS AND BASE PLATES PER S-401. GROUT BASE PLATES WITH 1 1/2\" NON-SHRINK GROUT. SET ANCHOR RODS WITH TEMPLATES.",
    "COORDINATE ALL SLEEVES, BLOCKOUTS, UNDERSLAB PIPING, FLOOR DRAINS AND EMBEDDED ITEMS WITH ARCHITECTURAL AND MEP TRADES. LOWER FOOTINGS AT PIPE CROSSINGS PER 5/S-301.",
    "EXISTING BUILDING IS OCCUPIED: PROTECT EXISTING FOUNDATIONS, WALLS AND UTILITIES. UNDERPINNING IS NOT ANTICIPATED; SEE 9/S-301.",
]

FDN_KEYNOTES = OrderedDict([
    (1, "EXISTING EXTERIOR WALL AND FOOTING (ASSUMED 2'-0\" WIDE, BOTTOM 95'-4\"). VERIFY DEPTH AND PROJECTION BY TEST PIT BEFORE EXCAVATING LINK FOOTINGS; SEE 9/S-301."),
    (2, "NEW 11'-4\" OPENING IN EXISTING WALL WITH STEEL LINTEL AND TEMPORARY SHORING, SEE 12/S-302 AND AD101 (SUMMER RECESS ONLY)."),
    (3, "ELEVATOR PIT: T.O. PIT SLAB 95'-0\", 12\" WALLS, 14\" MAT, 24\"x24\"x24\" SUMP. COLUMN 2/C BEARS ON PIT WALL CORNER (F1 OMITTED). SEE 6/S-301."),
    (4, "1/4\" SLAB DEPRESSION FOR WALK-OFF CARPET WOM-1, 10'-0\" x CORRIDOR WIDTH (VERIFY EXTENT WITH A-111)."),
    (5, "LOWER CF-1 / STEP FOOTING AT PIPE CROSSING (STORM LEADERS x = 52'-6\" & 97'-6\", SANITARY x = 52'-0\"), SEE 5/S-301."),
    (6, "8\" EXPOSED CONCRETE CURB UNDER LINK STOREFRONT SF-3, T.O. CURB 100'-0\", SEE 8/S-301."),
    (7, "STAIR FOOTING STF-1 AT BOTTOM FLIGHT, EMBED PLATES FOR STRINGERS, SEE 7/S-301."),
    (8, "SLEEVE FOUNDATION WALL FOR 6\" FIRE AND 2\" DOMESTIC WATER ENTRY AT x = 45'-0\" (COORDINATE WITH CIVIL / DIV. 22)."),
    (9, "STOREFRONT SF-1 ENTRANCE: OMIT BRICK LEDGE, SLAB EDGE THICKENED AT THRESHOLD, SEE 1/S-301 SIM."),
])


def _s101_plan(sh, v):
    # existing building
    _existing(v)
    # slab-on-grade outline (inside face of exterior CMU), light
    slab = M.outline_poly("L1").buffer(-M.EW_IN, join_style=2).difference(
        box(-300, -500, M.EXIST_FACE_X, 500))
    v.geom(slab, lw="hair", color="g50")
    # WOM depression
    x0, y0, x1, y1 = WOM_BOX
    v.rect(x0, y0, x1 - x0, y1 - y0, lw="fine", fill="g10", hatch="dots",
           hatch_kw=dict(scale=0.7))
    # control joints
    for g in _cj_lines():
        if g.is_empty:
            continue
        v.geom(g, lw="fine", dash="long", color="g40")
    # interior CMU walls (L1) shown light for reference
    walls = PL.wall_geoms("L1")
    cmu_int = unary_union([w.poly() for w in M.interior_walls("L1")
                           if M.WALL_TYPES[w.type]["mat"] == "cmu"])
    holes = unary_union([PL._opening_box(o) for o in PL._cut_openings("L1")
                         if o.wall not in M.EXT_SEGS])
    v.geom(cmu_int.difference(holes), lw="hair", color="g50", fill="white", hatch="ansi31",
           hatch_kw=dict(spacing=0.04, col="g50"))
    if walls["stud"] is not None:
        v.geom(walls["stud"], lw="hair", color="g50", fill="g10")
    # thickened slabs
    v.geom(ts_geom(), lw="fine", dash=[2.2, 1.3])
    # footings (hidden)
    v.geom(cf1_geom(), lw="fine", dash="hidden")
    for mark, g, c in footing_rects():
        v.geom(g.difference(fdn_wall_geom()), lw="fine", dash="hidden")
    # stair footings
    for k, (a, b, c_, d) in STAIR_FTG.items():
        v.rect(a, b, c_ - a, d - b, lw="fine", dash="hidden")
    # elevator pit mat + sump
    mx0, my0, mx1, my1 = MAT
    v.rect(mx0, my0, mx1 - mx0, my1 - my0, lw="fine", dash="hidden")
    v.rect(22.0, 22.0, 2.0, 2.0, lw="fine", dash="hidden")
    v.line((22.0, 22.0), (24.0, 24.0), lw="hair")
    v.line((22.0, 24.0), (24.0, 22.0), lw="hair")
    # foundation walls + pit walls (cut)
    fw = fdn_wall_geom()
    v.geom(fw, lw="heavy", fill="g30")
    v.geom(pit_wall_geom(), lw="heavy", fill="g30")
    # brick ledge line (omitted at storefronts / doors)
    ledge = M.outline_poly("L1").buffer(FW_LEDGE, join_style=2, mitre_limit=10).exterior
    cuts = [box(-34.0, 25, -2.0, 47)]   # SF-3 link storefronts
    for o in M.OPENINGS:
        if o.wall in M.EXT_SEGS and (o.kind == "door" or o.type in ("SF-1",)) and o.level == "L1":
            cuts.append(M.opening_cut_box(o, depth=4.0))
    lg = LineString(ledge.coords).difference(unary_union(cuts)).difference(
        box(-300, -500, M.EXIST_FACE_X + 0.01, 500))
    v.geom(lg, lw="fine")
    # columns
    for c in columns():
        _column(v, c["x"], c["y"], COL_TYPES[c["type"]]["b"])


def _s101_annot(sh, v):
    cols = columns()
    # footing tags + T.O.F.
    for mark, g, c in footing_rects():
        x, y = c["x"], c["y"]
        if c["type"] == "C1":
            ty = y + (-1.75 if y > 36 else 1.75)
            _tag_box(v, (x + 1.75, ty), mark, size=TXT["small"])
        elif c["type"] in ("C2", "C3"):
            sx = 1 if c["x"] < 140 else -1
            sy = 1 if c["y"] > 36 else -1
            if c["type"] == "C2":
                _tag_box(v, (x + 2.0, y + 2.3 * sy), mark, size=TXT["small"])
                _vtxt(v, (x - 0.4, y + 1.2 * sy), "T.O.F. 98'-8\"", size=TXT["tiny"],
                      anchor="r")
            else:
                _tag_box(v, (x + 2.0 * sx, y + 2.3 * sy), mark, size=TXT["small"])
        else:  # link
            _tag_box(v, (x + (2.6 if mark == "F3E" else 0.0), y + (3.2 if y > 36 else -3.2)),
                     mark, size=TXT["small"])
    # column type tags
    for c in cols:
        x, y = c["x"], c["y"]
        if c["type"] == "C4":
            _col_tag(v, (x - 1.6, y + (1.4 if y > 36 else -1.4)), c["type"])
            continue
        dy = 1.3 if c["y"] in (72.0, 42.0) else -1.3
        if c["y"] == 72.0:
            dy = -1.25
        if c["y"] == 0.0:
            dy = 1.25
        if c["y"] == 42.0:
            dy = -1.25
        if c["y"] == 30.0:
            dy = 1.25
        _col_tag(v, (x - 1.25, y + dy), c["type"])
    # wall / footing labels
    _vtxt(v, (75.0, 74.6), "12\" FDN. WALL W/ 4\" BRICK LEDGE ON CF-1 (TYP.)", size=TXT["tiny"])
    _vtxt(v, (75.0, -2.5), "12\" FDN. WALL W/ 4\" BRICK LEDGE ON CF-1 (TYP.)", size=TXT["tiny"])
    _vtxt(v, (152.9, 15.0), "CF-1 (TYP.)", size=TXT["tiny"], rot=90)
    # TS-1 labels
    for at, rot in (((75.0, 43.4), 0), ((105.0, 28.6), 0), ((60.6, 57.0), 90), ((120.6, 15.0), 90),
                    ((35.5, 12.6), 0)):
        _vtxt(v, at, "TS-1", size=TXT["tiny"], rot=rot)
    # slab tags
    for at in ((15.0, 64.0), (75.0, 22.5), (105.0, 64.0)):
        _vtxt(v, at, "5\" SOG, T.O. SLAB 100'-0\"", size=TXT["small"], font=FONT_B)
        _vtxt(v, (at[0], at[1] - 1.5), "W/ 6x6-W2.9xW2.9 WWF (TYP.)", size=TXT["tiny"])
    # elevator pit
    _vtxt(v, (25.5, 27.6), "ELEV. PIT", size=TXT["tiny"], font=FONT_B, bg=False)
    _vtxt(v, (25.5, 26.4), "T.O. 95'-0\"", size=TXT["tiny"], bg=False)
    _vtxt(v, (23.0, 24.6), "SUMP", size=TXT["tiny"], bg=False)
    # stair footings
    for k in ("ST-1", "ST-2"):
        a, b, c_, d = STAIR_FTG[k]
        _vtxt(v, ((a + c_) / 2, (b + d) / 2), "STF-1", size=TXT["tiny"], font=FONT_B)
    # WOM
    _vtxt(v, (145.0, 38.6), "1/4\" DEPR.", size=TXT["tiny"], font=FONT_B)
    _vtxt(v, (145.0, 37.4), "T.O. 99'-11 3/4\"", size=TXT["tiny"])
    # link curb
    _vtxt(v, (-26.0, 40.2), "8\" CURB, T.O. 100'-0\"", size=TXT["tiny"])
    _vtxt(v, (-26.0, 31.8), "8\" CURB, T.O. 100'-0\"", size=TXT["tiny"])
    _vtxt(v, (-9.0, 36.0), "5\" SOG", size=TXT["small"], font=FONT_B)

    # dimensions specific to the foundation plan
    v.dim((HX0, 19.0), (HX1, 19.0), 0, size=TXT["tiny"], ext=False)
    v.dim((MAT[0], 17.4), (MAT[2], 17.4), 0, size=TXT["tiny"], ext=False)
    for xx in (MAT[0], MAT[2]):
        v.line((xx, 17.0), (xx, MAT[1]), lw="hair")
    for xx in (HX0, HX1):
        v.line((xx, 18.6), (xx, HY0), lw="hair")
    v.dim((140.0, 28.6), (150.0 - CMUh, 28.6), 0, size=TXT["tiny"], ext=False)
    # link dims
    _grid_dims(v, link_y=47.0)

    # section cuts to S-301
    _sec_cut(v, (75.0, 77.0), (75.0, 69.5), 1, "S-301")
    _sec_cut(v, (135.0, -5.0), (135.0, 2.5), 1, "S-301")
    _sec_cut(v, (90.0, 50.5), (90.0, 46.0), 2, "S-301")
    _sec_cut(v, (100.0, 25.5), (100.0, 32.8), 3, "S-301")
    detail_callout(v, (75.0, 15.0), 2.0, 4, "S-301", bubble_dir=(1, -1))
    _sec_cut(v, (19.0, 25.5), (26.0, 25.5), 6, "S-301")
    _sec_cut(v, (9.0, 12.0), (9.0, 18.5), 7, "S-301")
    _sec_cut(v, (-26.0, 46.0), (-26.0, 39.5), 8, "S-301")
    _sec_cut(v, (-40.5, 26.0), (-32.0, 26.0), 9, "S-301")

    # keynotes
    keynote_tag(v, (-44.0, 46.0), 1, leader_to=(-36.9, 46.0))
    keynote_tag(v, (-44.0, 36.0), 2, leader_to=(-36.6, 36.0))
    keynote_tag(v, (17.0, 28.0), 3, leader_to=(21.5, 26.0))
    keynote_tag(v, (145.0, 34.0), 4)
    for x, yk, ya in ((52.5, 77.5, 73.5), (97.5, 77.5, 73.5), (52.0, -6.0, -1.6)):
        keynote_tag(v, (x + 3.0, yk), 5, leader_to=(x, ya))
        v.line((x, ya - 1.0 if ya > 36 else ya + 1.0), (x, ya + (1.0 if ya > 36 else -1.0)),
               lw="thin", dash="hidden")
    keynote_tag(v, (-26.0, 50.0), 6, leader_to=(-23.0, 43.0))
    keynote_tag(v, (-30.0, 22.0), 6, leader_to=(-26.0, 29.0))
    keynote_tag(v, (4.0, 13.0), 7, leader_to=(7.0, 15.9))
    keynote_tag(v, (141.0, 50.0), 7, leader_to=(140.0, 56.1))
    keynote_tag(v, (45.0, -6.0), 8, leader_to=(45.0, -0.5))
    keynote_tag(v, (157.0, 26.0), 9, leader_to=(151.0, 32.0))


def _bottom_panel_rule(sh, top):
    sh.line((sh.x0, top + 0.12), (sh.x1, top + 0.12), lw="thin")


def _keynote_list(sh, x, y, notes, width, title="KEYNOTES"):
    sh.text((x, y), title, size=TXT["label"], font=FONT_B, valign="top", underline=True)
    yy = y - 0.27
    for k, t in notes.items():
        vv = sh.view(x + 0.12, yy - 0.06, 1 / 8)
        keynote_tag(vv, (0, 0), k)
        ls = wrap_lines([t], TXT["note"], FONT, width - 0.35)
        sh.mtext((x + 0.32, yy + 0.01), ls, size=TXT["note"])
        yy -= 0.12 * len(ls) + 0.07
    return y - yy


def s101(sh):
    v = _plan_view(sh)
    _s101_plan(sh, v)
    _grids(v)
    _s101_annot(sh, v)
    # title
    ty = v.to_paper((0, -21.5))[1] - 0.1
    sh.view_title(sh.x0 + 0.4, ty, 1, "FOUNDATION PLAN", SCALE, width=6.0)
    sh.north_arrow(sh.x0 + 8.2, ty + 0.2, 0.55)
    sh.scale_bar(sh.x0 + 9.2, ty - 0.05, SCALE, 32)
    top = ty - 0.55
    _bottom_panel_rule(sh, top)
    notes_block(sh, sh.x0 + 0.3, top, "FOUNDATION PLAN NOTES", FDN_NOTES, 10.4)
    _keynote_list(sh, sh.x0 + 11.2, top, FDN_KEYNOTES, 8.6)
    # legend
    lx = sh.x0 + 20.35
    sh.text((lx, top), "LEGEND", size=TXT["label"], font=FONT_B, valign="top", underline=True)
    yy = top - 0.32
    for kind, lab in (("fdnwall", "CONCRETE FOUNDATION WALL / PIT WALL (CUT)"),
                      ("footing", "FOOTING BELOW (HIDDEN)"),
                      ("ts", "TS-1 THICKENED SLAB (2'-0\" x 1'-0\")"),
                      ("cmu", "LEVEL 1 CMU WALL ABOVE (REFERENCE)"),
                      ("cj", "SAWCUT CONTROL JOINT"),
                      ("col", "STEEL COLUMN (SEE S-401)"),
                      ("depress", "SLAB DEPRESSION"),
                      ("existing", "EXISTING CONSTRUCTION")):
        _legend_line(sh, lx, yy, kind, lab)
        yy -= 0.215
    vv = sh.view(lx + 0.25, yy, 1 / 8)
    _tag_box(vv, (0, 0), "F1", size=TXT["small"])
    sh.text((lx + 0.62, yy), "FOOTING MARK (SEE S-401)", size=TXT["small"], valign="mid")
    yy -= 0.215
    _col_tag(vv, (0, -0.215 / SCALE), "C1")
    sh.text((lx + 0.62, yy), "COLUMN MARK (SEE S-401)", size=TXT["small"], valign="mid")
    yy -= 0.24
    vv = sh.view(lx + 0.25, yy, 1 / 8)
    _section_bubble(vv, (0, 0), (0, -1), 1, "S-301", r=0.15)
    sh.text((lx + 0.62, yy), "SECTION / DETAIL REFERENCE", size=TXT["small"], valign="mid")
    # footing summary
    fx = sh.x0 + 25.4
    rows = [["CF-1", "2'-6\" x 1'-0\" CONT.", "96'-4\""],
            ["F1", "7'-0\" x 7'-0\" x 1'-8\"", "98'-8\" / 96'-4\" EXT."],
            ["F2", "5'-0\" x 5'-0\" x 1'-4\"", "96'-4\""],
            ["F3", "4'-0\" x 4'-0\" x 1'-4\"", "96'-4\""],
            ["F3E", "4'-6\" x 5'-0\" x 1'-4\" ECC.", "96'-8\""],
            ["TS-1", "2'-0\" x 1'-0\" THK. SLAB", "-"],
            ["STF-1", "2'-0\" x 1'-4\" THK. SLAB", "-"],
            ["PIT", "14\" MAT, 12\" WALLS", "95'-0\" (PIT SLAB)"]]
    table(sh, fx, top, [("MARK", 0.6), ("SIZE (W x L x T)", 2.4), ("T.O. FOOTING", 1.7)], rows,
          row_h=0.19, size=TXT["small"], title="FOOTING SUMMARY (SEE S-401)",
          align=["c", "l", "c"])



# ----------------------------------------------------------------------------------------
# Framing plan helpers
# ----------------------------------------------------------------------------------------

def _walls_light(v, level):
    g = PL.wall_geoms(level)
    for k in ("cmu", "brick", "insul"):
        v.geom(g[k], lw="hair", color="g50", fill="g10")
    if g["stud"] is not None:
        v.geom(g["stud"], lw="hair", color="g50", fill="g05")


def _opening(v, x0, y0, x1, y1, lines=None, size=TXT["tiny"], lw="thin"):
    v.rect(x0, y0, x1 - x0, y1 - y0, lw=lw, fill="white")
    v.line((x0, y0), (x1, y1), lw="hair")
    v.line((x0, y1), (x1, y0), lw="hair")
    if lines:
        P = Paper(v.c)
        px, py = v.to_paper(((x0 + x1) / 2, (y0 + y1) / 2))
        lead = size * 1.2 / 72
        n = len(lines)
        for k, ln in enumerate(lines):
            _ptxt(v.c, (px, py + (n - 1) * lead / 2 - k * lead), ln, size=size,
                  font=FONT_B if k == 0 else FONT)


def _col_marks(v, cols, size=TXT["tiny"]):
    for c in cols:
        x, y = c["x"], c["y"]
        if c["type"] == "C4":
            _col_tag(v, (x - 1.6, y + (1.4 if y > 36 else -1.4)), c["type"])
            continue
        dy = {72.0: -1.25, 0.0: 1.25, 42.0: -1.25, 30.0: 1.25}[y]
        dx = -1.25 if x < 149 else -1.4
        _col_tag(v, (x + dx, y + dy), c["type"])


def _draw_members(v, members, size=TXT["tiny"], labels=True, lab=None):
    lab = lab or {}
    for k, mm in enumerate(members):
        p1, p2 = mm["p1"], mm["p2"]
        horiz = abs(p1[1] - p2[1]) < 1e-9
        side = 1
        y = p1[1]
        if horiz and (abs(y - YOA) < 1e-6 or abs(y - 42.0) < 1e-6 and mm["role"].startswith("BEAM")):
            side = -1
        if horiz and abs(y - 42.0) < 1e-6 and mm["role"] in ("JOIST BEAM",):
            side = -1
        if not horiz and abs(p1[0] - XO1) < 1e-6:
            side = -1
        cfg = lab.get(k, {})
        text = cfg.get("text", _mlabel(mm)) if labels else None
        if cfg.get("hide"):
            text = None
        _beam(v, p1, p2, text, size=cfg.get("size", size), side=cfg.get("side", side),
              lab_at=cfg.get("at", 0.5), lw=cfg.get("lw", "heavy"), dash=cfg.get("dash"))


def _plan_title_block(sh, v, num, title, notes, keynotes, legend_rows, notes_title,
                      extra=None):
    ty = v.to_paper((0, -21.5))[1] - 0.1
    sh.view_title(sh.x0 + 0.4, ty, num, title, SCALE, width=6.4)
    sh.north_arrow(sh.x0 + 8.2, ty + 0.2, 0.55)
    sh.scale_bar(sh.x0 + 9.2, ty - 0.05, SCALE, 32)
    top = ty - 0.55
    _bottom_panel_rule(sh, top)
    notes_block(sh, sh.x0 + 0.3, top, notes_title, notes, 10.4)
    _keynote_list(sh, sh.x0 + 11.2, top, keynotes, 8.6)
    lx = sh.x0 + 20.35
    sh.text((lx, top), "LEGEND", size=TXT["label"], font=FONT_B, valign="top", underline=True)
    yy = top - 0.32
    for kind, labtxt in legend_rows:
        _legend_line(sh, lx, yy, kind, labtxt)
        yy -= 0.215
    vv = sh.view(lx + 0.25, yy, 1 / 8)
    _col_tag(vv, (0, 0), "C1")
    sh.text((lx + 0.62, yy), "COLUMN MARK (SEE S-401)", size=TXT["small"], valign="mid")
    yy -= 0.24
    vv = sh.view(lx + 0.25, yy, 1 / 8)
    _deck_arrow(vv, (0, 0), "ew", length=0.42)
    sh.text((lx + 0.62, yy), "DECK SPAN DIRECTION", size=TXT["small"], valign="mid")
    yy -= 0.24
    vv = sh.view(lx + 0.25, yy, 1 / 8)
    _section_bubble(vv, (0, 0), (0, -1), 1, "S-302", r=0.15)
    sh.text((lx + 0.62, yy), "SECTION / DETAIL REFERENCE", size=TXT["small"], valign="mid")
    if extra:
        extra(sh, sh.x0 + 25.4, top)
    return top


# ----------------------------------------------------------------------------------------
# S-102 SECOND FLOOR FRAMING PLAN
# ----------------------------------------------------------------------------------------
L2_NOTES = [
    "T.O. SLAB = 114'-0\"; T.O. STEEL = 113'-5 3/4\" UNLESS NOTED. SEE S-001 FOR LOADS AND MATERIALS, S-302 FOR DETAILS AND S-401 FOR BEAM AND COLUMN SCHEDULES.",
    "D1 = 3\" x 20 GA. GALVANIZED (G60) COMPOSITE STEEL FLOOR DECK, 3-SPAN MIN., WITH 3 1/4\" LIGHTWEIGHT CONCRETE TOPPING (110 PCF, 3,500 PSI), 6 1/4\" TOTAL, REINFORCED WITH 6x6-W2.9xW2.9 WWF 1\" BELOW TOP. DECK UNSHORED.",
    "BEAM DESIGNATION: W16x26 [22] c=3/4\" = SHAPE [NUMBER OF 3/4\" DIA. x 5 1/2\" HEADED STUD ANCHORS, EQUALLY SPACED] CAMBER AT MIDSPAN. BEAMS WITHOUT 'c' SHALL NOT BE CAMBERED; ERECT CAMBER UP.",
    "PERIMETER BEAMS ON GRIDS A AND D AND GIRDERS ON GRIDS 1 AND 6 ARE CENTERED 7 1/2\" INBOARD OF GRID SO THE EXTERIOR CMU IS CONTINUOUS; CONNECT TO COLUMNS WITH STIFFENED SEATS, SEE 5/S-302.",
    "ALL BEAM CONNECTIONS ARE SIMPLE SHEAR (SINGLE PLATE OR DOUBLE ANGLE, 3/4\" A325-N BOLTS), DESIGNED BY THE FABRICATOR'S ENGINEER FOR 60% OF THE TOTAL UNIFORM LOAD CAPACITY (AISC TABLE 3-6), MIN. 10 KIPS. NO MOMENT CONNECTIONS: LATERAL SYSTEM IS REINFORCED MASONRY SHEAR WALLS.",
    "SLAB EDGE AT EXTERIOR WALLS = INSIDE FACE OF CMU (3 13/16\" INSIDE GRID) WITH 3/8\" BENT PLATE POUR STOP AND 1/2\" COMPRESSIBLE JOINT, SEE 4/S-302.",
    "DECK ATTACHMENT: 5/8\" PUDDLE WELDS 36/4 PATTERN AT EVERY SUPPORT, #10 TEK SIDE-LAP SCREWS @ 24\" O.C.; WELD DECK @ 12\" O.C. ALONG PERIMETER AND OPENINGS.",
    "LEVEL 2 CMU WALLS BEAR ON THE BEAMS / SLAB SHOWN; WHERE A WALL IS NOT OVER A BEAM PROVIDE (2) #4 CONTINUOUS IN THE SLAB UNDER THE WALL. SEE 6 & 7/S-302 FOR TOP OF WALL.",
    "FRAME ALL DECK OPENINGS LARGER THAN 12\" (MEP) WITH L3x3x1/4 BETWEEN BEAMS; COORDINATE SIZES AND LOCATIONS WITH MEP.",
    "STAIR FRAMING AND LANDINGS ARE DELEGATED DESIGN BY THE STAIR FABRICATOR; HEADERS AND TRIMMERS SHOWN SUPPORT THE STAIR AT LEVEL 2.",
]

L2_KEYNOTES = OrderedDict([
    (1, "STAIR 1 OPENING: W12x19 TRIMMERS ON x = 12'-0\" AND W16x26 HEADER AT TOP RISER (y = 15'-10 7/8\"). L2 LANDING (y = 15'-10 7/8\" TO GRID C) IS D1 SLAB."),
    (2, "STAIR 2 OPENING: W12x19 TRIMMERS ON x = 138'-0\" AND W16x26 HEADER AT TOP RISER (y = 56'-1 3/16\"). L2 LANDING (GRID B TO HEADER) IS D1 SLAB."),
    (3, "ELEVATOR HOISTWAY - NO SLAB. W12x19 FRAMING SUPPORTS LEVEL 2 HOISTWAY CMU. RAIL BRACKET EMBEDS IN GROUTED CMU BY ELEVATOR MFR."),
    (4, "W16x31 ON GRID 1 (ON GRID, NOT OFFSET) SUPPORTS EW-1 WALL ABOVE THE LINK ROOF; CMU BEARS ON 3/8\" CAP PL. SEE 4/S-302 SIM."),
    (5, "W12x19 UNDER LEVEL 2 TOILET-ROOM CMU WALLS (x = 41'-0\" AND 49'-0\")."),
    (6, "LEVEL 2 CMU WALL ON SLAB: (2) #4 CONT. IN SLAB UNDER WALL (y = 12'-0\")."),
    (7, "LINK ROOF BELOW, T.O. STEEL 114'-0\". SEE S-103."),
    (8, "L7x4x7/16 (LLH) SHELF ANGLE AT 113'-4\" CONT. AROUND BUILDING (EXCEPT AT W-C), SUPPORTS FACE BRICK AND CS-2 BAND, SEE 4/S-302."),
])


def _l2_label_cfg(members):
    cfg = {}
    for k, mm in enumerate(members):
        p1, p2 = mm["p1"], mm["p2"]
        if mm["role"] == "INFILL" and abs(p1[0] - 30.0) < 1e-6 and p1[1] < 30:
            cfg[k] = dict(at=0.8)
        if mm["role"] == "TRIMMER" or mm["role"] == "HOISTWAY":
            cfg[k] = dict(text=mm["size"])
        if mm["role"] == "UNDER CMU":
            cfg[k] = dict(text=mm["size"])
        if mm["role"] == "HEADER":
            cfg[k] = dict(at=0.62 if p1[0] < 60 else 0.3)
        if mm["role"] == "GIRDER B-C":
            cfg[k] = dict(text=_mlabel(mm) + (" (ON GRID)" if mm.get("note") else ""))
    return cfg


def s102(sh):
    v = _plan_view(sh)
    _existing(v, footing=False)
    # link roof below
    v.rect(M.EXIST_FACE_X, 30 - M.EW_OUT, 36.0, 12 + 2 * M.EW_OUT, lw="fine", dash="hidden")
    _vtxt(v, (-18.0, 36.0), "LINK ROOF BELOW (SEE S-103)", size=TXT["small"], font=FONT_B)
    _walls_light(v, "L2")
    # slab edge (inside face of exterior CMU)
    slab = M.outline_poly("L2").buffer(-M.EW_IN, join_style=2)
    v.geom(slab, lw="thin")
    # shelf angle line (outside face of CMU)
    sa = M.outline_poly("L2").buffer(M.EW_IN + 1.0 * IN, join_style=2, mitre_limit=10)
    wc_cut = unary_union([M.opening_cut_box(o, 4.0) for o in M.OPENINGS if o.type == "W-C"])
    v.geom(LineString(sa.exterior.coords).difference(wc_cut), lw="fine", dash="center")
    # openings
    _opening(v, ST1["x0"], ST1["y0"], ST1["x1"], ST1["f_hi"], ["STAIR 1", "OPENING"])
    _opening(v, ST2["x0"], ST2["f_lo"], ST2["x1"], ST2["y1"], ["STAIR 2", "OPENING"])
    _opening(v, HX0, HY0, HX1, HY1, ["ELEV.", "NO SLAB"])
    # framing
    mem = l2_members()
    _draw_members(v, mem, size=TXT["tiny"], lab=_l2_label_cfg(mem))
    for c in columns():
        _column(v, c["x"], c["y"], COL_TYPES[c["type"]]["b"])
    _col_marks(v, [c for c in columns() if c["type"] != "C4"])
    # deck span arrows
    for a in (0.0, 30.0, 60.0, 90.0, 120.0):
        if a > 0:
            _deck_arrow(v, (a + 7.0, 5.0), "ns", 0.55, "D1")
        _deck_arrow(v, (a + 23.0 if a != 30 else a + 25.5, 25.0 if a != 0 else 25.0), "ns", 0.55,
                    "D1") if a not in (0.0,) else _deck_arrow(v, (a + 8.0, 25.0), "ns", 0.55, "D1")
        _deck_arrow(v, (a + 22.0, 36.0), "ns", 0.55, "D1")
        _deck_arrow(v, (a + 22.0 if a != 120 else a + 7.0, 67.0), "ns", 0.55, "D1")
    # grids / dims
    _grids(v, link=False)
    _grid_dims(v)
    # dims at stair / elevator openings
    v.dim((-4.0, 0.0), (-4.0, Y_HDR1), 0, size=TXT["tiny"], ext=True)
    for yy in (0.0, Y_HDR1):
        v.line((-4.8, yy), (-1.2, yy), lw="hair")
    v.dim((136.0, Y_HDR2), (136.0, 72.0), 0, size=TXT["tiny"], ext=False)
    v.dim((0.0, -4.5), (12.0, -4.5), 0, size=TXT["tiny"], ext=True)
    v.dim((138.0, 76.5), (150.0, 76.5), 0, size=TXT["tiny"], ext=True)
    v.dim((XO6, 76.5), (150.0, 76.5), 1.6, size=TXT["tiny"], ext=False, text='7 1/2"')
    # elevation notes
    _vtxt(v, (45.0, 66.8), "T.O. SLAB 114'-0\"", size=TXT["small"], font=FONT_B)
    _vtxt(v, (45.0, 65.6), "T.O. STEEL 113'-5 3/4\" (TYP.)", size=TXT["tiny"])
    # references
    _sec_cut(v, (75.0, 77.0), (75.0, 69.0), 4, "S-302")
    _sec_cut(v, (105.0, -5.0), (105.0, 3.0), 4, "S-302")
    detail_callout(v, (60.0, 72.0), 1.6, 5, "S-302", bubble_dir=(1, 1))
    detail_callout(v, (90.0, 20.0), 1.6, 10, "S-302", bubble_dir=(1, -1))
    # keynotes
    keynote_tag(v, (4.0, 21.0), 1, leader_to=(6.0, 15.4))
    keynote_tag(v, (141.0, 50.0), 2, leader_to=(143.0, 56.6))
    keynote_tag(v, (17.0, 27.0), 3, leader_to=(21.6, 26.0))
    keynote_tag(v, (-5.5, 26.0), 4, leader_to=(0.0, 33.0))
    keynote_tag(v, (45.0, 14.0), 5, leader_to=(41.0, 15.5))
    keynote_tag(v, (35.0, 15.5), 6, leader_to=(36.0, 12.0))
    keynote_tag(v, (-28.0, 46.0), 7, leader_to=(-26.0, 42.6))
    keynote_tag(v, (115.0, 76.5), 8, leader_to=(112.0, 72.5))
    keynote_tag(v, (156.0, 9.0), 8, leader_to=(150.5, 12.0))

    legend = [("beam", "STEEL BEAM / GIRDER (SIMPLE CONNECTIONS)"),
              ("col", "STEEL COLUMN BELOW / ABOVE"),
              ("opening", "OPENING IN FLOOR (NO DECK)"),
              ("wall_light", "LEVEL 2 CMU / WALLS ABOVE (REFERENCE)"),
              ("cj", "SHELF ANGLE AT 113'-4\" (CENTER LINE)")]

    def extra(sh, x, top):
        rows = []
        cnt = OrderedDict()
        for mm in mem:
            key = (mm["size"], mm["role"])
            L = vlen(vsub(mm["p2"], mm["p1"]))
            c = cnt.setdefault(key, [0, 0.0, mm["studs"], mm["camber"]])
            c[0] += 1
            c[1] += L
        for (size, role), (n, L, st, cb) in cnt.items():
            rows.append([size, role.title(), str(n), f"{L:,.0f}'"])
        table(sh, x, top, [("SIZE", 0.95), ("USE", 1.6), ("QTY", 0.5), ("TOTAL LF", 0.85)], rows,
              row_h=0.17, size=TXT["small"], title="LEVEL 2 MEMBER SUMMARY",
              align=["l", "l", "c", "r"])
        sh.text((x, top - 0.17 * (len(rows) + 2.6) - 0.05), "SEE S-401 FOR FULL BEAM SCHEDULE.",
                size=TXT["tiny"], valign="top")

    _plan_title_block(sh, v, 1, "SECOND FLOOR FRAMING PLAN", L2_NOTES, L2_KEYNOTES, legend,
                      "SECOND FLOOR FRAMING NOTES", extra)


# ----------------------------------------------------------------------------------------
# S-103 ROOF FRAMING PLAN (+ LINK ROOF)
# ----------------------------------------------------------------------------------------
RF_NOTES = [
    "T.O. JOIST TOP CHORD / ROOF DECK BEARING = 128'-0\" (STRUCTURE FLAT; ROOF SLOPE BY TAPERED INSULATION, SEE A-103). T.O. BEAMS SUPPORTING JOISTS = 127'-9 1/2\" (2 1/2\" SEATS). T.O. W12x14 TIES = 128'-0\". LINK ROOF T.O. STEEL = 114'-0\".",
    "R1 = 1 1/2\" TYPE B (WIDE RIB) 20 GA. GALVANIZED (G60) ROOF DECK, 3-SPAN MIN. ATTACH 36/7 PATTERN WITH 5/8\" PUDDLE WELDS (OR 0.145\" PAF) AT EVERY SUPPORT, #10 TEK SIDE-LAP SCREWS @ 12\" O.C.; 36/9 PATTERN WITHIN 10'-0\" OF ROOF EDGES.",
    "JOISTS: SJI K-SERIES, 22K6 @ 5'-0\" O.C. (GRIDS A-B AND C-D), 12K1 @ 5'-0\" O.C. (B-C). BEAR 2 1/2\" MIN. ON STEEL; WELD EACH SEAT (2) 1/8\" x 1\" FILLETS. DESIGN FOR NET UPLIFT OF 20 PSF (32 PSF WITHIN 10'-0\" OF EDGES).",
    "BRIDGING: HORIZONTAL BRIDGING ROWS AS SHOWN (MIN. PER SJI), ANCHORED TO BEAMS OR WALLS AT ENDS; DIAGONAL BOLTED BRIDGING NOT REQUIRED (SPANS < 40'-0\").",
    "JOISTS MARKED * SHALL BE DESIGNED BY THE JOIST MANUFACTURER FOR THE RTU LOADS SHOWN (OPERATING WEIGHT ON CURB) PLUS UNIFORM LOADS (SPECIAL KCS OR ADD-LOAD DESIGN).",
    "RTU CURBS (7'-0\" x 14'-0\") BY DIV. 23; SUPPORT FRAMES (L4x4x1/4) AND DUCT OPENINGS (L3x3x1/4) BY GC, SEE 11/S-302. ROOF DRAINS BY PLUMBING (SHOWN FOR COORDINATION); FRAME SUMP OPENINGS PER 11/S-302 SIM.",
    "EDGE BEAMS ON GRIDS A AND D AND TIES ON GRIDS 1 AND 6 ARE 7 1/2\" INBOARD OF GRID. DECK EDGE AT INSIDE FACE OF CMU ON CONT. L3x3x1/4 ANCHORED TO TOP BOND BEAM; CMU PARAPET CONTINUOUS TO 131'-4\", SEE 9/S-302.",
    "TOP OF LEVEL 2 INTERIOR CMU WALLS: BRACE TO JOISTS / DECK PER 6 & 7/S-302. CMU UNDER BEAMS STOPS AT THE COURSE BELOW THE BEAM WITH 1\" MIN. DEFLECTION JOINT.",
    "SNOW: Pf = 22 PSF (MIN. pm = 20 Is), DRIFTS AT PARAPETS AND AT THE LINK LOWER ROOF PER S-001. DO NOT STOCKPILE ROOFING MATERIALS ON JOISTS BETWEEN PANEL POINTS.",
]

RF_KEYNOTES = OrderedDict([
    (1, "RTU CURB 7'-0\" x 14'-0\" ON L4x4x1/4 SUPPORT FRAME; DUCT OPENINGS FRAMED WITH L3x3x1/4. SEE 11/S-302. RTU-1 / RTU-2 = 3,200 LB, RTU-3 = 2,400 LB OPERATING."),
    (2, "ROOF HATCH 2'-6\" x 3'-0\" (A-103): L4x4x1/4 FRAME BETWEEN JOISTS, SEE 11/S-302 SIM."),
    (3, "ROOF DRAIN RD / OVERFLOW DRAIN OD (BY PLUMBING). FRAME DECK OPENING; HOLD SUMP 9\" CLEAR OF JOISTS."),
    (4, "12K1 SHIFTED 1'-0\" WEST TO CLEAR RD-1 / RD-4 (SPACING 4'-0\" / 6'-0\")."),
    (5, "W10x22 ELEVATOR HOIST BEAM, T.O.S. 126'-0\", 5,000 LB RATED; BEAR ON GROUTED HOISTWAY CMU WITH PL 1/2x6x8. LABEL CAPACITY ON BEAM."),
    (6, "LINK ROOF SCUPPER AT x = -10'-0\" (BY ARCH., A-103); 12\" WIDE OPENING IN PARAPET WITH LOOSE LINTEL L4x3 1/2x5/16."),
    (7, "LINK STRUCTURE IS INDEPENDENT OF THE EXISTING BUILDING: 1\" GAP AT EXISTING FACE, ROOF EXPANSION JOINT BY ARCH. DO NOT ATTACH TO EXISTING."),
    (8, "HSS8x8x1/2 STOREFRONT HEAD BEAM BELOW (T.O.S. 110'-0\") ON LINES C AND B BETWEEN LINK COLUMNS; SUPPORTS CMU / BRICK ABOVE SF-3, SEE 13/S-302."),
    (9, "TOP OF CMU PARAPET 131'-4\" WITH 2-#5 BOND BEAM; COPING BLOCKING BY ARCH."),
])


def _draw_joists(v):
    js = roof_joists()
    for j in js:
        g = v.paper_len(0.035)
        v.line((j["x"], j["y0"] + g), (j["x"], j["y1"] - g), lw="thin")
        if j.get("special"):
            v.line((j["x"], j["y0"] + g), (j["x"], j["y1"] - g), lw="med")
            yy = j["y0"] + 2.6 if j["y0"] > 36 else j["y1"] - 2.6
            _vtxt(v, (j["x"], yy), "*", size=TXT["label"], font=FONT_B, bg=True)
    # bridging rows
    for (y0, y1, n) in ((YOD, 30.0, 3), (42.0, YOA, 3), (30.0, 42.0, 1)):
        for k in range(1, n + 1):
            y = y0 + (y1 - y0) * k / (n + 1)
            for a, b in zip([XO1, 30.0, 60.0, 90.0, 120.0], [30.0, 60.0, 90.0, 120.0, XO6]):
                v.line((a + 0.3, y), (b - 0.3, y), lw="hair", dash="hidden")
    return js


def _rtu_frame(v, name, cx, cy):
    x0, x1 = cx - CURB_W / 2, cx + CURB_W / 2
    y0, y1 = cy - CURB_D / 2, cy + CURB_D / 2
    v.rect(x0, y0, CURB_W, CURB_D, lw="thin", dash="dashed", fill=None)
    jw = 5.0 * math.floor(x0 / 5.0)
    je = 5.0 * math.ceil(x1 / 5.0)
    for y in (y0, y1):
        v.line((jw, y), (je, y), lw="med")
    for x in (x0, x1):
        v.line((x, y0), (x, y1), lw="med")
    # duct openings between joists
    js = [5.0 * k for k in range(int(jw / 5) + 1, int(je / 5))]
    for a, b in list(zip(js[:-1], js[1:]))[:2]:
        v.rect(a + 1.0, cy - 1.0, 3.0, 2.0, lw="fine")
        v.line((a + 1.0, cy - 1.0), (a + 4.0, cy + 1.0), lw="hair")
        v.line((a + 1.0, cy + 1.0), (a + 4.0, cy - 1.0), lw="hair")
    _vtxt(v, (cx, y1 + 1.0), f"{name} CURB", size=TXT["tiny"], font=FONT_B)


def _roof_drains(v):
    for i, (x, y) in enumerate(RD):
        v.circle((x, y), 0.75, lw="thin", fill="white")
        v.circle((x, y), 0.3, lw="fine")
        _vtxt(v, (x, y + 1.6), f"RD-{i + 1}", size=TXT["tiny"])
    for i, (x, y) in enumerate(OD):
        v.circle((x, y), 0.75, lw="thin", fill="white", dash="hidden")
        v.circle((x, y), 0.3, lw="fine")
        _vtxt(v, (x + 0.2, y - 1.6), f"OD-{i + 1}", size=TXT["tiny"])


def _link_roof(v, labels=True):
    mem = [mm for mm in link_members() if mm["role"] != "SF HEAD"]
    cfg = {}
    for k, mm in enumerate(mem):
        if mm["role"] == "PURLIN":
            cfg[k] = dict(text="W8x10", size=TXT["tiny"])
        if mm["role"] == "LINK TIE":
            cfg[k] = dict(text="W8x18", size=TXT["tiny"])
    for k, mm in enumerate(mem):
        if mm["role"] == "LINK BEAM":
            side = 1 if mm["p1"][1] < 36 else -1
            _beam(v, mm["p1"], mm["p2"], mm["size"] if labels else None, size=TXT["tiny"],
                  side=side)
        else:
            _beam(v, mm["p1"], mm["p2"], cfg[k]["text"] if labels else None, size=TXT["tiny"],
                  side=-1 if mm["role"] == "LINK TIE" else 1, lab_at=0.5)
    # HSS head beams below (dashed, just outside the roof beams)
    for y in (30.0, 42.0):
        for a, b in ((-35.0, -18.0), (-18.0, 0.0)):
            yy = y + (-0.45 if y < 36 else 0.45)
    for c in columns():
        if c["type"] == "C4":
            _column(v, c["x"], c["y"], COL_TYPES["C4"]["b"])
    # link parapet outline (EW-1 piers + storefront line)
    v.rect(M.EXIST_FACE_X + 1 / 12, 30 - M.EW_OUT, 36.0 - 1 / 12, 12 + 2 * M.EW_OUT, lw="fine")


def s103(sh):
    v = _plan_view(sh)
    _existing(v, footing=False)
    _walls_light(v, "L2")
    # roof edge (inside face of parapet CMU) and parapet outline
    P = M.outline_poly("L2")
    v.geom(P.buffer(-M.EW_IN, join_style=2), lw="thin")
    v.geom(P.buffer(M.EW_OUT, join_style=2, mitre_limit=10), lw="thin")
    # link
    _link_roof(v)
    for x0 in (-33.0,):
        pass
    _deck_arrow(v, (-26.5, 36.0), "ew", 0.5, "R1")
    _deck_arrow(v, (-9.0, 36.0), "ew", 0.5, "R1")
    # scupper
    v.rect(-10.5, 42.0 + M.EW_IN, 1.0, M.EW_OUT - M.EW_IN, lw="thin", fill="white")
    _vtxt(v, (-10.0, 44.4), "SCUPPER", size=TXT["tiny"])
    # joists, bridging, beams
    js = _draw_joists(v)
    mem = roof_members()
    cfg = {}
    for k, mm in enumerate(mem):
        if mm["role"] == "TIE":
            cfg[k] = dict(text="W12x14")
        if mm["role"] == "HOIST BEAM":
            cfg[k] = dict(text="W10x22 HOIST BM", dash="hidden", lw="med", side=-1)
        if mm["role"] == "EDGE BEAM":
            cfg[k] = dict(at=0.3)
        if mm["role"] == "JOIST BEAM":
            cfg[k] = dict(at=0.3)
    _draw_members(v, mem, size=TXT["tiny"], lab=cfg)
    for c in columns():
        if c["type"] != "C4":
            _column(v, c["x"], c["y"], COL_TYPES[c["type"]]["b"])
    _col_marks(v, columns())
    # joist labels (one per bay & zone)
    for a in (0.0, 30.0, 60.0, 90.0, 120.0):
        _vtxt(v, (a + 17.5, 57.0 if a not in (30.0, 90.0) else 66.0), "22K6 @ 5'-0\" O.C.",
              size=TXT["tiny"], font=FONT_B)
        _vtxt(v, (a + 17.5, 15.0 if a not in (90.0,) else 24.5), "22K6 @ 5'-0\" O.C.",
              size=TXT["tiny"], font=FONT_B)
        _vtxt(v, (a + 7.5 if a != 0 else a + 22.5, 38.5), "12K1 @ 5'-0\" O.C.",
              size=TXT["tiny"], font=FONT_B)
    # RTUs, hatch, drains
    for name, cx, cy in RTUS:
        _rtu_frame(v, name, cx, cy)
    hx, hy, hw, hd = HATCH
    _opening(v, hx - hw / 2, hy - hd / 2, hx + hw / 2, hy + hd / 2)
    for y in (hy - hd / 2, hy + hd / 2):
        v.line((45.0, y), (50.0, y), lw="med")
    for x in (hx - hw / 2, hx + hw / 2):
        v.line((x, hy - hd / 2), (x, hy + hd / 2), lw="med")
    _roof_drains(v)
    # deck arrows
    for a in (0.0, 30.0, 60.0, 90.0, 120.0):
        _deck_arrow(v, (a + 7.5, 6.0), "ew", 0.5, "R1")
        _deck_arrow(v, (a + 7.5, 66.0), "ew", 0.5, "R1")
    # grids / dims
    _grids(v)
    _grid_dims(v, link_y=48.0)
    _vtxt(v, (75.0, 69.2), "T.O. JOIST 128'-0\" / T.O. BEAM 127'-9 1/2\" (TYP.)", size=TXT["tiny"])
    _vtxt(v, (75.0, 74.6), "T.O. PARAPET 131'-4\" (CMU)", size=TXT["tiny"])
    _vtxt(v, (-18.0, 39.6), "LINK ROOF", size=TXT["small"], font=FONT_B)
    _vtxt(v, (-18.0, 38.4), "T.O. STEEL 114'-0\"", size=TXT["tiny"])
    # references
    _sec_cut(v, (45.0, 77.5), (45.0, 69.0), 9, "S-302")
    _sec_cut(v, (115.0, 39.5), (115.0, 44.5), 8, "S-302")
    _sec_cut(v, (68.0, 13.0), (68.0, 17.0), 6, "S-302")
    _sec_cut(v, (88.5, 57.0), (91.5, 57.0), 7, "S-302")
    detail_callout(v, (45.0, 57.0), 8.5, 11, "S-302", bubble_dir=(-1, 1))
    # keynotes
    keynote_tag(v, (56.0, 64.5), 1, leader_to=(52.0, 60.5))
    keynote_tag(v, (115.0, 64.5), 1, leader_to=(112.0, 60.5))
    keynote_tag(v, (115.0, 21.0), 1, leader_to=(112.0, 18.5))
    keynote_tag(v, (52.0, 26.5), 2, leader_to=(48.0, 27.0))
    keynote_tag(v, (57.0, 39.0), 3, leader_to=(53.2, 36.5))
    keynote_tag(v, (11.0, 39.5), 4, leader_to=(14.0, 37.5))
    keynote_tag(v, (138.0, 39.5), 4, leader_to=(134.0, 37.5))
    keynote_tag(v, (17.0, 27.0), 5, leader_to=(23.0, 25.5))
    keynote_tag(v, (-6.0, 47.5), 6, leader_to=(-9.6, 43.0))
    keynote_tag(v, (-42.0, 24.0), 7, leader_to=(-36.1, 33.0))
    keynote_tag(v, (-30.0, 26.0), 8, leader_to=(-26.0, 29.6))
    keynote_tag(v, (100.0, 77.0), 9, leader_to=(97.0, 72.6))

    legend = [("beam", "STEEL BEAM (W-SHAPE)"),
              ("joist", "STEEL JOIST (K-SERIES) @ 5'-0\" O.C."),
              ("bridging", "ROW OF HORIZONTAL BRIDGING"),
              ("col", "STEEL COLUMN BELOW"),
              ("wall_light", "LEVEL 2 CMU / WALLS BELOW (REFERENCE)")]

    def extra(sh, x, top):
        cnt = OrderedDict()
        for j in js:
            key = j["type"] + (" *" if j.get("special") else "")
            span = j["y1"] - j["y0"]
            c = cnt.setdefault(key, [0, 0.0])
            c[0] += 1
            c[1] += span
        rows = [[k, str(n), f"{L / n:.1f}'", f"{L:,.0f}'"] for k, (n, L) in cnt.items()]
        bcnt = OrderedDict()
        for mm in roof_members() + [mm for mm in link_members()]:
            L = vlen(vsub(mm["p2"], mm["p1"]))
            c = bcnt.setdefault(mm["size"], [0, 0.0])
            c[0] += 1
            c[1] += L
        rows.append("BEAMS (MAIN + LINK ROOF)")
        rows += [[k, str(n), "-", f"{L:,.0f}'"] for k, (n, L) in bcnt.items()]
        table(sh, x, top, [("MEMBER", 1.15), ("QTY", 0.55), ("AVG. SPAN", 0.95),
                           ("TOTAL LF", 0.95)], rows, row_h=0.17, size=TXT["small"],
              title="ROOF MEMBER SUMMARY", align=["l", "c", "c", "r"])

    _plan_title_block(sh, v, 1, "ROOF FRAMING PLAN", RF_NOTES, RF_KEYNOTES, legend,
                      "ROOF FRAMING NOTES", extra)



# ----------------------------------------------------------------------------------------
# Detail drawing toolkit (model units = feet; x = horizontal, y = elevation)
# ----------------------------------------------------------------------------------------
DT = TXT["small"]       # detail note size


def _dview(sh, cell, sc, bb, title_h=0.62, dx=0.0, dy=0.0):
    cw, ch = cell["w"], cell["h"] - title_h
    w, h = (bb[2] - bb[0]) * sc, (bb[3] - bb[1]) * sc
    ox = cell["x"] + (cw - w) / 2 + dx
    oy = cell["y"] + title_h + (ch - h) / 2 + dy
    return sh.view(ox, oy, sc, bb[0], bb[1])


def _dtitle(sh, cell, num, title, sc, width=None, sheet=None):
    w = width or min(cell["w"] - 0.9, 4.8)
    sh.view_title(cell["x"] + 0.18, cell["y"] + 0.40, num, title, sc, width=w)


def _conc(v, pts, lw="heavy", dens=1.0):
    v.polygon(pts, lw=lw, fill="white", hatch="concrete", hatch_kw=dict(scale=dens))


def _crect(v, x0, y0, x1, y1, lw="heavy", dens=1.0):
    _conc(v, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], lw, dens)


def _earth(v, pts):
    v.polygon(pts, lw=None, hatch="earth", hatch_kw=dict(spacing=0.16, col="g30"), stroke=False)


def _erect(v, x0, y0, x1, y1):
    _earth(v, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _gravel(v, x0, y0, x1, y1):
    v.rect(x0, y0, x1 - x0, y1 - y0, lw=None, fill="white", hatch="gravel",
           hatch_kw=dict(scale=0.55), stroke=False)
    v.line((x0, y0), (x1, y0), lw="hair")


def _cmu_sec(v, x0, x1, y0, y1, grout=(), course0=99 + 4 * IN, lw="med", full_grout=False):
    """CMU in section; grout = list of (ya, yb) grouted bands (bond beams / solid cells)"""
    if full_grout:
        _crect(v, x0, y0, x1, y1, lw=lw, dens=0.8)
    else:
        v.rect(x0, y0, x1 - x0, y1 - y0, lw=lw, fill="white", hatch="ansi31",
               hatch_kw=dict(spacing=0.055))
    for ya, yb in grout:
        ya, yb = max(ya, y0), min(yb, y1)
        if yb > ya:
            _crect(v, x0, ya, x1, yb, lw="fine", dens=0.8)
    k = math.ceil((y0 - course0) / (8 * IN) - 1e-6)
    y = course0 + k * 8 * IN
    while y < y1 - 1e-6:
        if y > y0 + 1e-6:
            v.line((x0, y), (x1, y), lw="hair")
        y += 8 * IN


def _brick_sec(v, x0, x1, y0, y1, course0=99.0, lw="thin"):
    v.rect(x0, y0, x1 - x0, y1 - y0, lw=lw, fill="white", hatch="brick",
           hatch_kw=dict(spacing=0.03))
    y = course0 + math.ceil((y0 - course0) / (8 / 3 * IN)) * 8 / 3 * IN
    while y < y1 - 1e-6:
        if y > y0 + 1e-6:
            v.line((x0, y), (x1, y), lw="hair")
        y += 8 / 3 * IN


def _insul_sec(v, x0, x1, y0, y1, lw="fine"):
    v.rect(x0, y0, x1 - x0, y1 - y0, lw=lw, fill="white", hatch="insul",
           hatch_kw=dict(spacing=max(0.02, (x1 - x0) * v.s * 0.9)))


def _bar(v, p, dia_in=0.625):
    r = max(dia_in / 2 * IN, v.paper_len(0.017))
    v.circle(p, r, lw=None, fill="black")


def _bars(v, pts, dia_in=0.625):
    for p in pts:
        _bar(v, p, dia_in)


def _barline(v, pts, w=1.0):
    v.polyline(pts, lw=w)


def _wsec(v, cx, top, d, bf, tf, tw, fill="black"):
    """W-shape cross section (inches given), top = T.O. steel (ft)"""
    D, B, TF, TW = d * IN, bf * IN, tf * IN, tw * IN
    pts = [(cx - B / 2, top), (cx + B / 2, top), (cx + B / 2, top - TF), (cx + TW / 2, top - TF),
           (cx + TW / 2, top - D + TF), (cx + B / 2, top - D + TF), (cx + B / 2, top - D),
           (cx - B / 2, top - D), (cx - B / 2, top - D + TF), (cx - TW / 2, top - D + TF),
           (cx - TW / 2, top - TF), (cx - B / 2, top - TF)]
    v.polygon(pts, lw="fine", fill=fill)


def _welev(v, x0, x1, top, d, tf, lw="thin", dash=None):
    """W-shape in elevation (along its length)"""
    D, TF = d * IN, tf * IN
    v.rect(x0, top - D, x1 - x0, D, lw=lw, dash=dash)
    v.line((x0, top - TF), (x1, top - TF), lw="fine", dash=dash)
    v.line((x0, top - D + TF), (x1, top - D + TF), lw="fine", dash=dash)


def _ang(v, heel, h, vv, t, hx=1, vy=1, fill="black"):
    """angle section: heel point, horizontal leg h (in) toward hx, vertical leg vv (in) toward vy"""
    x, y = heel
    H, V, T = h * IN, vv * IN, t * IN
    pts = [(x, y), (x + hx * H, y), (x + hx * H, y + vy * T), (x + hx * T, y + vy * T),
           (x + hx * T, y + vy * V), (x, y + vy * V)]
    v.polygon(pts, lw="fine", fill=fill)


def _hss_sec(v, cx, cy, b, h, t):
    B, H, T = b * IN, h * IN, t * IN
    v.rect(cx - B / 2, cy - H / 2, B, H, lw="fine", fill="black")
    v.rect(cx - B / 2 + T, cy - H / 2 + T, B - 2 * T, H - 2 * T, lw="hair", fill="white")


def _pl(v, x0, y0, x1, y1, fill="black", lw="fine"):
    v.rect(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0), lw=lw, fill=fill)


def _ldr(v, tip, at, lines, side=None, size=DT, arrow="arrow"):
    """leader from tip (arrow) to `at`; text block beside `at` on a white mask"""
    if isinstance(lines, str):
        lines = lines.split("\n")
    side = side or ("r" if at[0] >= tip[0] else "l")
    v.polyline([tip, at], lw="fine")
    if arrow == "arrow":
        v._arrowhead(tip, vsub(tip, at), size_in=0.06)
    elif arrow == "dot":
        v.circle(tip, v.paper_len(0.018), lw=None, fill="black")
    px, py = v.to_paper(at)
    lead = size * 1.18 / 72
    n = len(lines)
    y0 = py + (n - 1) * lead / 2
    for k, ln in enumerate(lines):
        _ptxt(v.c, (px + 0.035 if side == "r" else px - 0.035, y0 - k * lead), ln, size=size,
              anchor="l" if side == "r" else "r", valign="mid", bg=True, pad=0.012)


def _dgrid(v, x, y0, y1, label=""):
    v.line((x, y0), (x, y1), lw="hair", dash="center")
    r = v.paper_len(0.09)
    v.circle((x, y1 + r), r, lw="fine", fill="white")
    if label:
        v.text((x, y1 + r), label, size=TXT["tiny"], font=FONT_B, anchor="c", valign="mid")


def _lev(v, x, el, label, side="r", x_from=None, value=None):
    level_marker(v, x, el, label, side=side, x_line_from=x_from, value_text=value)


def _dim(v, p1, p2, off, text=None, size=TXT["tiny"]):
    L = vlen(vsub(p2, p1))
    if text is None and L < 1.0 - 1e-6:
        text = fmt_in(L * 12)
    v.dim(p1, p2, off, text=text, size=size)


def _dimc(v, pts, off, size=TXT["tiny"]):
    for a, b in zip(pts[:-1], pts[1:]):
        if vlen(vsub(b, a)) > 1e-6:
            _dim(v, a, b, off, size=size)


def _wwf(v, x0, x1, y):
    v.line((x0, y), (x1, y), lw="fine", dash=[3, 1.5])


def _brk_v(v, x, y0, y1):
    break_line(v, (x, y0), (x, y1), zig=0.08)


def _brk_h(v, y, x0, x1):
    break_line(v, (x0, y), (x1, y), zig=0.08)


# ----------------------------------------------------------------------------------------
# S-301 FOUNDATION SECTIONS & DETAILS
# ----------------------------------------------------------------------------------------
GS = 99 + 7 * IN     # bottom of 5" slab
CA = GS - 0.5        # bottom of 6" CA-6


def _sog(v, x0, x1, ts=None, ts_bot=99.0, wwf=True, base_to=None):
    """slab on grade x0..x1 with optional thickened zone ts=(a, b); CA-6 base under"""
    if ts:
        a, b = ts
        _gravel(v, x0, CA, a, GS)
        _gravel(v, b, CA, x1, GS)
        _conc(v, [(x0, GS), (a, GS), (a, ts_bot), (b, ts_bot), (b, GS), (x1, GS), (x1, EL_L1),
                  (x0, EL_L1)], dens=0.8)
    else:
        _gravel(v, x0, CA, x1, GS)
        _crect(v, x0, GS, x1, EL_L1, dens=0.8)
    if wwf:
        _wwf(v, x0 + 0.1, x1 - 0.1, EL_L1 - 1.5 * IN)


def d301_ext_wall(sh, cell):
    sc = 3 / 4
    v = _dview(sh, cell, sc, (-5.6, 94.0, 4.8, 102.9))
    x_in, x_out = -3.4, 2.9
    _earth(v, [(x_in, 94.6), (x_out, 94.6), (x_out, 99.333 - 0.10), (0.96, 99.333), (0.96, 96.3),
               (-0.4, 96.3), (-0.4, CA), (x_in, CA)])
    v.line((0.953, 99.333), (x_out, 99.333 - 0.10), lw="thin")
    _gravel(v, x_in, CA, -0.5417, GS)
    _insul_sec(v, -0.5417, -0.375, GS - 2.0, GS)
    _crect(v, CF_IN, EL_BOF, CF_OUT, EL_TOF)
    _conc(v, [(FW_IN, EL_TOF), (FW_OUT, EL_TOF), (FW_OUT, EL_LEDGE), (FW_LEDGE, EL_LEDGE),
              (FW_LEDGE, EL_TOW), (FW_IN, EL_TOW)])
    _crect(v, x_in, GS, -CMUh - 0.5 * IN, EL_L1, dens=0.8)
    v.rect(-CMUh - 0.5 * IN, GS, 0.5 * IN, 5 * IN, lw="fine", fill="g20")
    v.line((x_in, GS), (-0.5417, GS), lw="thin")
    _wwf(v, x_in + 0.1, -0.42, EL_L1 - 1.5 * IN)
    top = 102.2
    _cmu_sec(v, -CMUh, CMUh, EL_TOW, top, grout=[(EL_TOW, EL_L1 + 8 * IN)])
    v.rect(-0.12, EL_L1 + 8 * IN, 0.24, top - EL_L1 - 8 * IN, lw=None, fill="white",
           hatch="concrete", hatch_kw=dict(scale=0.8), stroke=False)
    _insul_sec(v, CMUh, CMUh + 2 * IN, EL_TOW, top)
    _brick_sec(v, 7.8125 * IN, 11.4375 * IN, EL_LEDGE, top)
    _brk_h(v, top, -0.6, 1.15)
    _brk_v(v, x_in, CA, EL_L1 + 0.1)
    v.polyline([(CMUh + 2 * IN + 0.02, EL_L1 + 0.1), (CMUh + 2 * IN + 0.02, EL_TOW + 0.02),
                (FW_LEDGE + 0.02, EL_TOW + 0.02), (FW_LEDGE + 0.02, EL_LEDGE + 0.02),
                (11.4375 * IN + 0.06, EL_LEDGE + 0.02), (11.4375 * IN + 0.08, EL_LEDGE - 0.03)],
               lw="med")
    _bars(v, [(CF_IN + 0.35, EL_BOF + 0.30), (0.29, EL_BOF + 0.30), (CF_OUT - 0.35, EL_BOF + 0.30)])
    _barline(v, [(CF_IN + 0.3, EL_BOF + 0.36), (CF_OUT - 0.3, EL_BOF + 0.36)], w=0.8)
    xv = FW_IN + 2.5 * IN
    _barline(v, [(xv + 0.9, EL_BOF + 0.42), (xv, EL_BOF + 0.42), (xv, EL_TOW - 0.18)])
    xo = FW_OUT - 2.5 * IN
    _barline(v, [(xo - 0.9, EL_BOF + 0.42), (xo, EL_BOF + 0.42), (xo, EL_LEDGE - 0.18)])
    _bars(v, [(xv + 0.07, y) for y in (97.0, 98.0)] + [(xo - 0.07, y) for y in (97.0, 98.0)])
    _bars(v, [(xv + 0.07, EL_TOW - 0.2), (FW_LEDGE - 0.25, EL_TOW - 0.2)])
    _barline(v, [(0.0, 97.6), (0.0, 101.8)], w=1.0)
    _dgrid(v, 0.0, 94.75, 102.55, "")
    xl = -2.25
    _ldr(v, (-0.34, 99.95), (xl, 102.35), "1/2\" ISOLATION JOINT W/ SEALANT", "l")
    _ldr(v, (-1.6, 99.8), (xl, 101.75), "5\" SLAB ON GRADE, T.O. 100'-0\",\nW/ 6x6-W2.9xW2.9 WWF", "l")
    _ldr(v, (-1.3, GS), (xl, 101.0), "15-MIL VAPOR RETARDER, LAP\n& TAPE, TURN UP AT WALL", "l")
    _ldr(v, (-1.6, CA + 0.25), (xl, 98.95), "6\" COMPACTED CA-6", "l")
    _ldr(v, (FW_LEDGE - 0.25, EL_TOW - 0.2), (xl, 98.4), "(2) #5 CONT. TOP", "l")
    _ldr(v, (-0.46, 97.9), (xl, 97.8), "2\" XPS (R-10) PERIMETER\nINSULATION x 2'-0\" DEEP", "l")
    _ldr(v, (xv, 97.0), (xl, 96.95), "#5 @ 16\" VERT. (HOOKED);\n#5 @ 12\" HORIZ. EA. FACE", "l")
    _ldr(v, (CF_IN + 0.35, EL_BOF + 0.30), (xl, 95.8), "CF-1: 2'-6\" x 1'-0\",\n(3) #5 CONT. BOT.", "l")
    xr = 1.75
    _ldr(v, (0.40, 101.9), (xr, 102.5), "2\" POLYISO + AIR BARRIER (A-501)", "r")
    _ldr(v, (-0.15, 101.4), (xr, 101.9), "8\" CMU BACKUP, #5 @ 48\" O.C.\n(SEE 1/S-302)", "r")
    _ldr(v, (0.0, 100.3), (xr, 101.15), "#5 DOWEL @ 48\" O.C., 30\" LAP;\nGROUT CELLS SOLID BELOW SLAB", "r")
    _ldr(v, (0.80, 100.7), (xr, 100.4), "FACE BRICK ON 4\" LEDGE (99'-0\")", "r")
    _ldr(v, (0.97, EL_LEDGE + 0.02), (xr, 99.85), "THRU-WALL FLASHING &\nWEEPS (ARCH.)", "r")
    _ldr(v, (2.4, 99.26), (xr + 0.35, 99.0), "FINISH GRADE", "r")
    _ldr(v, (FW_OUT, 98.0), (xr, 98.35), "DAMPPROOFING", "r")
    _lev(v, 3.6, EL_TOF, "T.O. FTG.", "r", x_from=CF_OUT)
    _lev(v, 3.6, EL_BOF, "B.O. FTG.", "r", x_from=CF_OUT)
    chain = [CF_IN, FW_IN, 0.0, FW_LEDGE, FW_OUT, CF_OUT]
    _dimc(v, [(x, EL_BOF) for x in chain], -0.32)
    _dim(v, (CF_IN, EL_BOF), (CF_OUT, EL_BOF), -0.65)
    _dim(v, (CF_OUT, EL_BOF), (CF_OUT, EL_TOF), -0.25)
    _dim(v, (2.95, EL_BOF), (2.95, EL_TOW), 0, text="4'-0\" MIN. (FROST)")
    _dim(v, (FW_OUT, EL_LEDGE), (FW_OUT, EL_TOW), -0.25)
    _dtitle(sh, cell, 1, "TYPICAL EXTERIOR WALL FOUNDATION", sc)


def d301_f1(sh, cell):
    sc = 1 / 2
    v = _dview(sh, cell, sc, (-7.9, 95.9, 7.9, 107.6))
    X0, X1 = -5.2, 5.2
    tof = EL_TOF_INT
    _earth(v, [(X0, 96.3), (X1, 96.3), (X1, CA), (1.0, CA), (1.0, 99.0), (-1.0, 99.0), (-1.0, CA),
               (X0, CA)])
    _crect(v, -3.5, tof - 20 * IN, 3.5, tof)
    _sog(v, X0, X1, ts=(-1.0, 1.0))
    bp0 = tof + 1.5 * IN
    v.rect(-0.55, tof, 1.1, 1.5 * IN, lw="fine", fill="g40")
    _pl(v, -0.5, bp0, 0.5, bp0 + 0.75 * IN)
    c0 = bp0 + 0.75 * IN
    v.rect(-0.25 - 0.5 * IN, 99.0, 0.5 + 1 * IN, EL_L1 - 99.0, lw="fine", fill="g20")
    ct = 106.6
    v.rect(-0.25, c0, 0.5, ct - c0, lw="thin", fill="white")
    v.line((-0.25 + 0.5 * IN, c0), (-0.25 + 0.5 * IN, ct), lw="hair")
    v.line((0.25 - 0.5 * IN, c0), (0.25 - 0.5 * IN, ct), lw="hair")
    for xx in (-1 / 3, 1 / 3):
        v.line((xx, bp0 - 1.25), (xx, c0 + 0.12), lw=1.2)
        _pl(v, xx - 0.12, bp0 - 1.25, xx + 0.12, bp0 - 1.25 + 0.04)
        _pl(v, xx - 0.07, c0, xx + 0.07, c0 + 0.08)
    for a, b in ((-CMUh, -0.25), (0.25, CMUh)):
        v.rect(a, EL_L1, b - a, ct - EL_L1, lw="thin", fill="white", hatch="ansi31",
               hatch_kw=dict(spacing=0.04))
    _brk_h(v, ct, -0.9, 0.9)
    _brk_v(v, X0, CA, EL_L1 + 0.1)
    _brk_v(v, X1, CA, EL_L1 + 0.1)
    yb = tof - 20 * IN + 0.33
    _bars(v, [(-3.5 + 0.35 + k * 6.3 / 7, yb) for k in range(8)], 0.75)
    _barline(v, [(-3.1, yb + 0.08), (3.1, yb + 0.08)])
    _bars(v, [(-0.6, 99.3), (0.0, 99.3), (0.6, 99.3)], 0.5)
    _dgrid(v, 0.0, 96.4, 107.1, "")
    xl = -3.4
    _ldr(v, (-0.29, 105.0), (xl, 106.8), "8\" CMU CUT TO FIT AROUND\nCOLUMN; GROUT SOLID", "l")
    _ldr(v, (-2.6, 99.85), (xl, 105.9), "5\" SLAB ON GRADE", "l")
    _ldr(v, (-0.27, 99.92), (xl, 105.2), "1/2\" ISOLATION JOINT AROUND\nCOLUMN; POUR AFTER ERECTION", "l")
    _ldr(v, (-0.6, 99.3), (xl, 104.35), "TS-1 W/ (3) #4 CONT. BOT.", "l")
    _ldr(v, (-0.55, tof + 0.06), (xl, 103.65), "1 1/2\" NON-SHRINK GROUT", "l")
    _ldr(v, (-2.9, yb), (xl, 102.85), "F1: 7'-0\" x 7'-0\" x 1'-8\"\n(8) #6 EA. WAY BOT.", "l")
    xr = 3.4
    _ldr(v, (0.25, 105.8), (xr, 106.8), "C2: HSS6x6x1/2 EMBEDDED\nIN CORRIDOR CMU (5/S-302)", "r")
    _ldr(v, (0.45, bp0 + 0.03), (xr, 105.6), "BASE PL 3/4\" x 12\" x 12\"", "r")
    _ldr(v, (1 / 3, 98.2), (xr, 104.6), "(4) 3/4\" DIA. F1554 GR. 36\nANCHOR RODS x 1'-3\" EMBED,\nHEAVY HEX NUT + PL WASHER", "r")
    _lev(v, 5.5, EL_L1, "T.O. SLAB", "r", x_from=X1)
    _lev(v, 5.5, tof, "T.O.F.", "r", x_from=3.5)
    _lev(v, 5.5, tof - 20 * IN, "B.O.F.", "r", x_from=3.5)
    _dim(v, (-3.5, tof - 20 * IN), (3.5, tof - 20 * IN), -0.45)
    _dim(v, (3.5, tof - 20 * IN), (3.5, tof), -0.35)
    _dtitle(sh, cell, 2, "INTERIOR COLUMN FOOTING F1", sc)


def d301_ts(sh, cell):
    sc = 3 / 4
    v = _dview(sh, cell, sc, (-5.2, 98.0, 5.2, 105.6))
    X0, X1 = -3.4, 3.4
    _earth(v, [(X0, 98.3), (X1, 98.3), (X1, CA), (1.0, CA), (1.0, 99.0), (-1.0, 99.0), (-1.0, CA),
               (X0, CA)])
    _sog(v, X0, X1, ts=(-1.0, 1.0))
    ct = 104.9
    _cmu_sec(v, -CMUh, CMUh, EL_L1, ct, course0=100.0)
    v.rect(-0.1, EL_L1, 0.2, ct - EL_L1, lw=None, fill="white", hatch="concrete",
           hatch_kw=dict(scale=0.8), stroke=False)
    _brk_h(v, ct, -0.7, 0.7)
    _brk_v(v, X0, CA, EL_L1 + 0.1)
    _brk_v(v, X1, CA, EL_L1 + 0.1)
    _bars(v, [(-0.6, 99.3), (0.0, 99.3), (0.6, 99.3)], 0.5)
    _barline(v, [(0.55, 99.36), (0.0, 99.36), (0.0, 102.8)])
    _dgrid(v, 0.0, 98.4, 105.25, "")
    xr = 1.25
    _ldr(v, (0.2, 104.2), (xr, 104.9), "8\" CMU WALL (P1 / P2),\nREINF. PER 1/S-302", "r")
    _ldr(v, (0.0, 102.2), (xr, 103.75), "#5 x 3'-6\" DOWEL @ 48\" O.C.\n(STD. HOOK) TO MATCH CMU\nVERT. REINF., 30\" LAP", "r")
    _ldr(v, (2.2, 99.85), (xr, 102.3), "5\" SLAB ON GRADE", "r")
    _ldr(v, (0.6, 99.3), (xr, 101.55), "(3) #4 CONT. BOT., 3\" CLR.", "r")
    xl = -1.25
    _ldr(v, (-1.0, 99.3), (xl, 102.8), "TS-1: 2'-0\" W x 1'-0\" D\nTHICKENED SLAB", "l")
    _ldr(v, (-2.3, GS), (xl, 101.9), "VAPOR RETARDER CONT.\nUNDER THICKENED SLAB", "l")
    _ldr(v, (-2.8, 99.3), (xl, 101.1), "6\" CA-6", "l")
    _dim(v, (-1.0, 99.0), (1.0, 99.0), -0.42)
    _dim(v, (-1.0, 99.0), (-1.0, EL_L1), 0.35)
    _dtitle(sh, cell, 3, "THICKENED SLAB TS-1 AT CMU WALL", sc)


def d301_joints(sh, cell):
    sc = 1.0
    title_h = 0.62
    h_each = (cell["h"] - title_h - 0.2) / 3
    subs = ("A. SAWCUT CONTROL JOINT", "B. DOWELED CONSTRUCTION JOINT",
            "C. ISOLATION JOINT AT COLUMN / WALL")
    for k, sub in enumerate(subs):
        c = dict(x=cell["x"], y=cell["y"] + title_h + (2 - k) * h_each, w=cell["w"], h=h_each)
        v = sh.view(c["x"] + cell["w"] / 2 - 1.0, c["y"] + 0.42, sc, 0.0, CA)
        X0, X1 = -1.5, 1.5
        _erect(v, X0, CA - 0.25, X1, CA)
        _gravel(v, X0, CA, X1, GS)
        if k == 0:
            _crect(v, X0, GS, X1, EL_L1, dens=0.7)
            v.rect(-0.06 * IN, EL_L1 - 1.25 * IN, 0.125 * IN, 1.25 * IN, lw="fine", fill="white")
            v.polyline([(0, EL_L1 - 1.25 * IN), (0.02, 99.8), (-0.02, 99.7), (0.01, GS)], lw="fine",
                       dash="dot")
            _wwf(v, X0, X1, EL_L1 - 1.5 * IN)
            _ldr(v, (0.0, EL_L1 - 0.03), (0.45, EL_L1 + 0.3),
                 "1/8\" SAWCUT x 1 1/4\" DEEP WITHIN 12 HRS;\nSEMI-RIGID EPOXY FILLER AT EXPOSED /\nRESILIENT FLOORING AREAS", "r")
            _ldr(v, (-0.9, EL_L1 - 1.5 * IN), (-0.45, EL_L1 + 0.3), "WWF: CUT ALTERNATE\nWIRES AT JOINT", "l")
        elif k == 1:
            _crect(v, X0, GS, 0.0, EL_L1, dens=0.7)
            _crect(v, 0.0, GS, X1, EL_L1, dens=0.7)
            ym = GS + 2.5 * IN
            v.rect(-8 * IN, ym - 0.375 * IN, 16 * IN, 0.75 * IN, lw="fine", fill="g50")
            v.rect(0.0, ym - 0.45 * IN, 8 * IN, 0.9 * IN, lw="hair")
            _ldr(v, (-0.4, ym), (-0.45, EL_L1 + 0.3), "3/4\" DIA. x 16\" SMOOTH\nDOWELS @ 12\" O.C.", "l")
            _ldr(v, (0.45, ym + 0.03), (0.45, EL_L1 + 0.3), "BOND BREAKER / SLEEVE ONE\nSIDE; DOWELS PERPENDICULAR\nTO JOINT", "r")
        else:
            _crect(v, X0, GS, -0.5 * IN, EL_L1, dens=0.7)
            v.rect(-0.5 * IN, GS, 0.5 * IN, EL_L1 - GS, lw="fine", fill="g30")
            _cmu_sec(v, 0.0, 0.64, GS - 0.1, 100.9, course0=100.0)
            _brk_h(v, 100.9, -0.1, 0.8)
            _ldr(v, (-0.02, EL_L1 - 0.15), (-0.45, 100.6), "1/2\" PREMOLDED JOINT\nFILLER, FULL DEPTH,\nSEALANT AT TOP", "l")
            _ldr(v, (0.45, 100.6), (0.95, 100.75), "COLUMN / CMU WALL", "r")
        _brk_v(v, X0, CA - 0.25, EL_L1 + 0.05)
        _brk_v(v, X1, CA - 0.25, EL_L1 + 0.05)
        sh.text((c["x"] + 0.25, c["y"] + h_each - 0.12), sub, size=TXT["small"], font=FONT_B,
                valign="top", underline=True)
    _dtitle(sh, cell, 4, "SLAB ON GRADE JOINTS", "SCALE: 1\" = 1'-0\"")


def d301_step(sh, cell):
    sc = 1 / 2
    v = _dview(sh, cell, sc, (-1.0, 91.3, 14.0, 103.0))
    hi_b, hi_t = EL_BOF, EL_TOF
    lo_b, lo_t = EL_BOF - 2.0, EL_TOF - 2.0
    xa, xb = -0.5, 13.5
    _erect(v, xa, 92.4, xb, lo_b)
    _erect(v, xa, lo_b, 6.0, hi_b)
    v.line((xa, EL_TOW), (xb, EL_TOW), lw="thin")
    # footing (elevation, heavy outline) and wall face (thin)
    v.polygon([(xa, hi_b), (6.0, hi_b), (6.0, lo_b), (xb, lo_b), (xb, lo_t), (7.0, lo_t),
               (7.0, hi_t), (xa, hi_t)], lw="heavy", fill="white")
    v.polyline([(xa, hi_t), (7.0, hi_t), (7.0, lo_t), (xb, lo_t)], lw="thin")
    v.rect(xa, hi_t, xb - xa, EL_TOW - hi_t, lw=None, stroke=False)
    v.polyline([(xa, EL_TOW), (xb, EL_TOW)], lw="med")
    v.polyline([(xa, EL_TOW + 0.0), (xa, EL_TOW + 2.3)], lw="hair")
    # CMU / brick above (outline)
    for y in [EL_TOW + k * 8 * IN for k in range(1, 4)]:
        v.line((xa, y), (xb, y), lw="hair", color="g50")
    v.line((xa, EL_TOW + 2.3), (xb, EL_TOW + 2.3), lw="hair", color="g50")
    _vtxt(v, (3.0, EL_TOW + 1.2), "CMU / BRICK ABOVE", size=TXT["tiny"], color="g50")
    # pipe and sleeve
    pc = (10.0, lo_t + 1.0)
    v.circle(pc, 0.42, lw="thin", fill="white")
    v.circle(pc, 0.29, lw="thin", fill="g50")
    # rebar (dashed = in wall / footing)
    yb = hi_b + 0.3
    _barline(v, [(xa, yb), (6.3, yb), (6.3, lo_b + 0.3), (xb, lo_b + 0.3)])
    _barline(v, [(4.0, hi_t - 0.3), (6.7, hi_t - 0.3), (6.7, lo_b + 0.9)], w=0.8)
    _barline(v, [(5.0, lo_t - 0.3), (xb, lo_t - 0.3)], w=0.8)
    for x in [xa + 0.6 + k * 1.333 for k in range(10)]:
        y0 = hi_t if x < 7.0 else lo_t
        if abs(x - 10.0) < 0.6:
            continue
        v.line((x, y0 - 0.25), (x, EL_TOW - 0.15), lw=0.5, dash=[3, 1.5])
    _brk_v(v, xa, 92.4, EL_TOW + 2.3)
    _brk_v(v, xb, 92.4, EL_TOW + 2.3)
    _ldr(v, (10.3, lo_t + 1.3), (11.0, 101.0), "SLEEVE PIPE THRU FDN. WALL\n(SCH. 40, 2\" OVERSIZE),\nSEAL BOTH ENDS", "r")
    _ldr(v, (11.6, lo_t + 0.5), (11.0, 99.95), "LOWER FOOTING SO PIPE\nCLEARS T.O.F. BY 2\" MIN.;\nNO PIPES BELOW FOOTINGS", "r")
    _ldr(v, (2.0, yb), (1.2, 93.2), "(3) #5 CONT. BOT., BENT AT STEP;\nLAP 2'-6\" MIN. PAST CORNERS", "r")
    _ldr(v, (5.4, hi_t - 0.3), (3.2, 101.2), "(2) #5 x 5'-0\" ADDED AT EACH\nSTEP CORNER", "l")
    _ldr(v, (1.9, 97.8), (3.2, 100.2), "FDN. WALL REINF. PER 1/S-301", "l")
    _dim(v, (7.0, lo_t), (7.0, hi_t), 0.45, text="2'-0\" MAX.")
    _dim(v, (6.0, lo_b), (7.0, lo_b), -0.4)
    _dim(v, (7.0, lo_b), (xb, lo_b), -0.4, text="2'-0\" MIN. TO NEXT STEP")
    _dim(v, (xb, lo_b), (xb, lo_t), -0.35)
    _dtitle(sh, cell, 5, "STEP FOOTING / FOOTING AT PIPE CROSSING", sc)


def d301_pit(sh, cell):
    sc = 1 / 2
    xw0, xw1 = HX0 - PIT_WALL, HX0
    xe0, xe1 = HX1, HX1 + PIT_WALL
    mx0, mx1 = MAT[0], MAT[2]
    mb = EL_PIT - 14 * IN
    s0, s1 = 22.0, 24.0
    sb = EL_PIT - 2.0
    X0, X1 = mx0 - 1.6, mx1 + 2.0
    v = _dview(sh, cell, sc, (X0 - 5.4, 90.6, X1 + 5.6, 103.6))
    _erect(v, X0, 91.0, X1, CA)
    mat = box(mx0, mb, mx1, EL_PIT).union(box(21.5, sb - 1.0, 24.5, mb)).difference(
        box(s0, sb, s1, EL_PIT + 1))
    grav = box(mx0, mb - 0.5, mx1, mb).union(box(21.0, sb - 1.5, 25.0, mb))
    v.geom(grav, lw=None, fill="white", hatch="gravel", hatch_kw=dict(scale=0.55), stroke=False)
    v.geom(mat, lw="heavy", fill="white", hatch="concrete", hatch_kw=dict(scale=1.0))
    # backfill / gravel beside the walls up to slab
    v.rect(xw0 - 0.01, mb, 0.01, 0.01, lw=None)
    _gravel(v, X0, CA, xw0, GS)
    _gravel(v, xe1, CA, X1, GS)
    _crect(v, xw0, EL_PIT, xw1, EL_L1)
    _crect(v, xe0, EL_PIT, xe1, EL_L1)
    _crect(v, X0, GS, xw0 - 0.5 * IN, EL_L1, dens=0.8)
    _crect(v, xe1 + 0.5 * IN, GS, X1, EL_L1, dens=0.8)
    ct = 102.7
    _cmu_sec(v, 21 - CMUh, 21 + CMUh, EL_L1, ct, course0=100.0)
    _cmu_sec(v, 30 - CMUh, 30 + CMUh, EL_L1, ct, course0=100.0)
    for xx in (21.0, 30.0):
        _brk_h(v, ct, xx - 0.6, xx + 0.6)
    _brk_v(v, X0, CA, EL_L1 + 0.1)
    _brk_v(v, X1, CA, EL_L1 + 0.1)
    v.rect(30 - 0.25, EL_TOW + 0.75 * IN, 0.5, ct - EL_TOW, lw="fine", dash="hidden")
    v.rect(30 - 0.5, EL_TOW, 1.0, 0.75 * IN, lw="fine", dash="hidden")
    v.polyline([(xw0 - 0.05, EL_L1 - 0.7), (xw0 - 0.05, mb - 0.05), (mx1 + 0.05, mb - 0.05)],
               lw="xheavy", color="g50")
    v.polyline([(xe1 + 0.05, EL_L1 - 0.7), (xe1 + 0.05, mb - 0.05)], lw="xheavy", color="g50")
    for x in (xw0 + 0.2, xw1 - 0.2, xe0 + 0.2, xe1 - 0.2):
        _barline(v, [(x, mb + 0.25), (x, EL_L1 - 0.2)], w=0.8)
    for x in (xw0 + 0.29, xw1 - 0.29, xe0 + 0.29, xe1 - 0.29):
        _bars(v, [(x, EL_PIT + 0.5 + k) for k in range(5)])
    _barline(v, [(mx0 + 0.25, mb + 0.25), (21.6, mb + 0.25), (21.6, sb - 0.75), (24.4, sb - 0.75),
                 (24.4, mb + 0.25), (mx1 - 0.25, mb + 0.25)], w=0.8)
    _barline(v, [(mx0 + 0.25, EL_PIT - 0.25), (s0 - 0.2, EL_PIT - 0.25)], w=0.8)
    _barline(v, [(s1 + 0.2, EL_PIT - 0.25), (mx1 - 0.25, EL_PIT - 0.25)], w=0.8)
    for x in (xw0 + 0.5, xe1 + 0.6):
        pass
    for x in ((xw0 + xw1) / 2, (xe0 + xe1) / 2):
        v.rect(x - 0.06, EL_PIT - 0.12, 0.12, 0.24, lw="fine", fill="g60")
    xl = X0 - 0.3
    _ldr(v, (21.0, 101.8), (xl, 103.1), "8\" CMU HOISTWAY WALL (P2) ON\nPIT WALL, SEE S-302", "l")
    _ldr(v, (xw0 + 0.5, 99.0), (xl, 101.8), "12\" CONC. PIT WALLS: #5 @ 12\"\nEA. FACE EA. WAY, 2\" CLR.", "l")
    _ldr(v, (xw0 - 0.05, 97.5), (xl, 99.4), "60-MIL WATERPROOFING MEMBRANE\nUNDER MAT & UP WALLS W/\nPROTECTION BOARD", "l")
    _ldr(v, ((xw0 + xw1) / 2, EL_PIT), (xl, 97.6), "PVC WATERSTOP AT\nCONSTRUCTION JOINT", "l")
    _ldr(v, (mx0 + 0.6, mb + 0.3), (xl, 96.2), "14\" MAT: #5 @ 12\" EA. WAY\nTOP & BOTTOM", "l")
    _ldr(v, (mx0 + 0.6, mb - 0.25), (xl, 94.7), "6\" CA-6 + 15-MIL\nVAPOR RETARDER", "l")
    xr = X1 + 0.3
    _ldr(v, (30.1, 102.2), (xr, 103.1), "C2 COLUMN 2/C BEYOND: BASE PL ON\nPIT WALL CORNER (B.O. PL 99'-4\");\nF1 OMITTED", "r")
    _ldr(v, (xe1 + 0.02, 99.9), (xr, 101.55), "1/2\" ISOLATION JT.; SLAB ON GRADE", "r")
    _ldr(v, (27.0, EL_PIT + 0.05), (xr, 100.4), "PIT FLOOR T.O. 95'-0\": BUFFER / RAIL\nLOADS PER ELEVATOR MFR.", "r")
    _ldr(v, (23.0, sb + 0.2), (xr, 98.9), "SUMP 24\"x24\"x24\" W/ GALV. GRATE\n(PUMP & OIL SENSOR BY DIV. 22)", "r")
    _ldr(v, (mx1 - 0.6, mb + 0.6), (xr, 97.4), "MAT EXTENDS 3'-0\" E & N\nUNDER COLUMN 2/C", "r")
    _ldr(v, (29.0, 98.0), (xr, 95.9), "CRYSTALLINE WATERPROOFING\nADMIXTURE; PIT LADDER BY MFR.", "r")
    _lev(v, mx0 - 0.25, EL_PIT, "T.O. PIT", "l", x_from=xw0)
    _lev(v, mx0 - 0.25, mb, "B.O. MAT", "l", x_from=mx0)
    _dim(v, (HX0, 100.6), (HX1, 100.6), 0)
    _dim(v, (xw0, ct), (xw1, ct), 0.25)
    _dim(v, (xe0, ct), (xe1, ct), 0.25)
    _dim(v, (mx0, sb - 1.5), (mx1, sb - 1.5), -0.65)
    _dim(v, (mx0, sb - 1.5), (xw0, sb - 1.5), -0.3)
    _dim(v, (xe1, sb - 1.5), (mx1, sb - 1.5), -0.3)
    _dim(v, (26.0, EL_PIT), (26.0, EL_L1), 0, text="5'-0\" PIT DEPTH")
    _dim(v, (mx1, mb), (mx1, EL_PIT), -0.3)
    _dim(v, (s0, sb), (s1, sb), 0.3)
    _dtitle(sh, cell, 6, "ELEVATOR PIT SECTION (LOOKING NORTH)", sc)


def d301_stair(sh, cell):
    sc = 3 / 4
    v = _dview(sh, cell, sc, (-5.2, 97.9, 5.4, 105.4))
    X0, X1 = -2.6, 4.8
    tb = EL_L1 - 16 * IN
    _earth(v, [(X0, 98.1), (X1, 98.1), (X1, CA), (1.0, CA), (1.0, tb), (-1.0, tb), (-1.0, CA),
               (X0, CA)])
    _sog(v, X0, X1, ts=(-1.0, 1.0), ts_bot=tb)
    _pl(v, -0.1, EL_L1 - 0.5 * IN, 0.9, EL_L1)
    for xx in (0.1, 0.7):
        v.line((xx, EL_L1 - 0.5 * IN), (xx, EL_L1 - 4.5 * IN), lw=1.2)
    R, T = 7 * IN, 11 * IN
    s = R / T
    pts = [(0.0, EL_L1)]
    for k in range(5):
        x = k * T
        pts += [(x, EL_L1 + (k + 1) * R), (x + T, EL_L1 + (k + 1) * R)]
    v.polyline(pts, lw="fine", dash="hidden")
    d = 12 * IN / math.cos(math.atan(s))
    yt = lambda x: EL_L1 + R + x * s + 1 * IN
    xb0 = (d - R - 1 * IN) / s
    xe = 4.4
    v.polygon([(-0.1, EL_L1), (xb0, EL_L1), (xe, yt(xe) - d), (xe, yt(xe)), (-0.1, yt(-0.1)),
               (-0.1, EL_L1)], lw="med", fill=None)
    _brk_v(v, X0, CA, EL_L1 + 0.1)
    _brk_v(v, X1, CA, EL_L1 + 0.1)
    _brk_v(v, xe, yt(xe) - d - 0.1, yt(xe) + 0.6)
    _bars(v, [(-0.6, tb + 0.3), (0.0, tb + 0.3), (0.6, tb + 0.3), (-0.6, EL_L1 - 0.25),
              (0.6, EL_L1 - 0.25)])
    v.rect(-0.75, tb + 0.22, 1.5, EL_L1 - tb - 0.44, lw=0.7)
    xl = -1.3
    _ldr(v, (1.6, yt(1.6) - d + 0.05), (xl, 104.7), "C12x20.7 STRINGER, STEEL PAN\nSTAIR (DELEGATED DESIGN BY\nSTAIR FABRICATOR)", "l")
    _ldr(v, (0.4, EL_L1 - 0.02), (xl, 103.3), "EMBED PL 1/2\"x6\"x12\" W/ (4)\n1/2\"x4\" HEADED STUDS AT EA.\nSTRINGER; FIELD WELD", "l")
    _ldr(v, (-0.75, tb + 0.6), (xl, 101.9), "STF-1: 2'-0\" x 1'-4\" THICK-\nENED SLAB, (3) #5 BOT.,\n(2) #5 TOP, #4 TIES @ 12\"", "l")
    _ldr(v, (3.6, 99.85), (2.6, 101.2), "5\" SLAB ON GRADE", "r")
    _ldr(v, (3.3, yt(3.3) - 0.3), (3.4, 104.6), "PAN TREADS / RISERS\nBEYOND (HIDDEN)", "r")
    _dim(v, (-1.0, tb), (1.0, tb), -0.4)
    _dim(v, (1.0, tb), (1.0, EL_L1), -0.4)
    _dtitle(sh, cell, 7, "STAIR FOOTING STF-1 (ST-1 / ST-2)", sc)


def d301_curb(sh, cell):
    sc = 3 / 4
    v = _dview(sh, cell, sc, (-5.5, 94.2, 4.9, 103.0))
    X0, X1 = -2.9, 2.9
    wi, wo = FW_IN, FW_LEDGE
    _earth(v, [(X0, 94.6), (X1, 94.6), (X1, 99.24), (wo, 99.333), (wo, EL_TOF), (wi - 0.17, EL_TOF),
               (wi - 0.17, CA), (X0, CA)])
    v.line((wo, EL_TOW), (X1, 99.24), lw="thin")
    _gravel(v, X0, CA, wi - 0.17, GS)
    _insul_sec(v, wi - 0.1667, wi, GS - 2.0, GS)
    _crect(v, CF_IN, EL_BOF, CF_OUT, EL_TOF)
    _conc(v, [(wi, EL_TOF), (wo, EL_TOF), (wo, EL_L1 - 0.75 * IN), (wo - 0.75 * IN, EL_L1),
              (wi, EL_L1)])
    _crect(v, X0, GS, wi - 1.5 * IN, EL_L1, dens=0.8)
    _insul_sec(v, wi - 1.5 * IN, wi - 0.5 * IN, GS, EL_L1 - 0.5 * IN)
    v.rect(wi - 0.5 * IN, GS, 0.5 * IN, EL_L1 - GS, lw="fine", fill="g20")
    _wwf(v, X0 + 0.1, wi - 0.2, EL_L1 - 1.5 * IN)
    sx0, sx1 = -0.05, 0.33
    top = 102.5
    v.rect(sx0 - 0.05, EL_L1, sx1 - sx0 + 0.1, 0.12, lw="fine")
    v.rect(sx0, EL_L1 + 0.12, sx1 - sx0, 0.35, lw="fine")
    v.line((0.14, EL_L1 + 0.47), (0.14, top), lw="thin")
    v.line((sx0, EL_L1 + 0.47), (sx0, top), lw="fine")
    v.line((sx1, EL_L1 + 0.47), (sx1, top), lw="fine")
    _brk_h(v, top, -0.3, 0.6)
    v.rect(-5 / 24, EL_TOW + 1 * IN, 5 / 12, top - EL_TOW - 1 * IN, lw="fine", dash="hidden")
    v.rect(-0.5, EL_TOW, 1.0, 1 * IN, lw="fine", dash="hidden")
    _brk_v(v, X0, CA, EL_L1 + 0.1)
    _bars(v, [(CF_IN + 0.35, EL_BOF + 0.3), (0.29, EL_BOF + 0.3), (CF_OUT - 0.35, EL_BOF + 0.3)])
    xv = wi + 2.5 * IN
    _barline(v, [(xv + 0.8, EL_BOF + 0.4), (xv, EL_BOF + 0.4), (xv, EL_L1 - 0.2), (xv + 0.45, EL_L1 - 0.2)])
    xo = wo - 2.5 * IN
    _barline(v, [(xo - 0.8, EL_BOF + 0.4), (xo, EL_BOF + 0.4), (xo, EL_L1 - 0.2), (xo - 0.45, EL_L1 - 0.2)])
    _bars(v, [(xv + 0.07, y) for y in (97.0, 98.0, 99.0)] + [(xv + 0.07, EL_L1 - 0.3), (xo - 0.07, EL_L1 - 0.3)])
    _dgrid(v, 0.0, 94.75, 102.85, "")
    xl = -1.9
    _ldr(v, (0.14, 102.0), (xl, 102.55), "SF-3 STOREFRONT ON SILL\nRECEPTOR (A-312 / A-711)", "l")
    _ldr(v, (-0.21, 101.3), (xl, 101.6), "C4 COLUMN BEYOND (L1 / L2);\nBASE PL GROUTED AT 99'-4\",\nCURB 2ND POUR AROUND COL.", "l")
    _ldr(v, (wi - 1.0 * IN, 99.85), (xl, 100.55), "1\" XPS THERMAL BREAK +\n1/2\" ISOLATION JOINT", "l")
    _ldr(v, (-1.6, 99.85), (xl - 0.6, 99.75), "5\" SOG", "l")
    _ldr(v, (wi - 0.08, 98.4), (xl, 98.9), "2\" XPS x 2'-0\" DEEP", "l")
    _ldr(v, (xv, 97.6), (xl, 97.95), "12\" WALL: #5 @ 16\" VERT. EA.\nFACE, #5 @ 12\" HORIZ.,\n(2) #5 CONT. TOP", "l")
    _ldr(v, (CF_IN + 0.35, EL_BOF + 0.3), (xl, 96.3), "CF-1 W/ (3) #5 CONT.", "l")
    xr = 1.25
    _ldr(v, (wo - 0.03, EL_L1 - 0.03), (xr, 101.3), "8\" EXPOSED CONC. CURB,\n3/4\" CHAMFER, RUBBED\nFINISH (4,500 PSI, AIR-\nENTRAINED)", "r")
    _ldr(v, (wo, 98.6), (xr, 98.3), "DAMPPROOF BELOW GRADE", "r")
    _lev(v, 3.3, EL_L1, "T.O. CURB", "r", x_from=1.0)
    _lev(v, 3.3, EL_TOW, "GRADE", "r", x_from=X1)
    _lev(v, 3.3, EL_TOF, "T.O. FTG.", "r", x_from=CF_OUT)
    _dim(v, (wi, EL_TOF), (wo, EL_TOF), 0.3)
    _dim(v, (CF_IN, EL_BOF), (CF_OUT, EL_BOF), -0.35)
    _dim(v, (wo, EL_TOW), (wo, EL_L1), -0.75)
    _dtitle(sh, cell, 8, "LINK STOREFRONT CURB / FOOTING", sc)


def d301_existing(sh, cell):
    sc = 1 / 2
    v = _dview(sh, cell, sc, (-47.0, 93.0, -28.6, 103.8))
    fx = M.EXIST_FACE_X
    X0, X1 = -41.0, -30.0
    ex_b, ex_t = EL_BOF, EL_TOF
    _erect(v, X0, 93.4, X1, CA)
    v.rect(-37.5, ex_b, 2.0, 1.0, lw="thin", dash="hidden", color="g40", fill="g10")
    v.rect(fx - 1.0, ex_t, 1.0, 103.2 - ex_t, lw="thin", color="g40", fill="g10",
           hatch="ansi31", hatch_kw=dict(spacing=0.05, col="g50"))
    v.rect(X0, GS, fx - 1.0 - X0, EL_L1 - GS, lw="thin", color="g40", fill="g10")
    v.rect(X0, CA, fx - 1.0 - X0, GS - CA, lw="hair", color="g40", fill="white")
    _brk_h(v, 103.2, fx - 1.3, fx + 0.3)
    _brk_v(v, X0, CA, EL_L1 + 0.1)
    f_b, f_t = ex_b, ex_b + 16 * IN
    _crect(v, -35.5, f_b, -31.0, f_t)
    v.rect(-35.5 - 0.5 * IN, f_b, 0.5 * IN, f_t - f_b, lw="fine", fill="g30")
    v.polyline([(-35.5, f_t), (-35.5, EL_TOW - 1.5 * IN), (-34.33, EL_TOW - 1.5 * IN),
                (-34.33, f_t)], lw="thin")
    v.polyline([(-34.33, EL_TOW - 1.5 * IN), (-34.33, EL_L1), (X1, EL_L1)], lw="thin")
    v.rect(-35.0 - 5 / 24, EL_TOW + 1 * IN, 5 / 12, 103.2 - EL_TOW - 1 * IN, lw="thin")
    v.rect(-35.0 - 0.5, EL_TOW - 1.5 * IN, 1.0, 1.5 * IN, lw="hair", fill="g40")
    _pl(v, -35.5, EL_TOW, -34.5, EL_TOW + 1 * IN)
    _gravel(v, -31.0, CA, X1, GS)
    _crect(v, fx + 1 * IN, GS, X1, EL_L1, dens=0.8)
    v.rect(fx, GS, 1 * IN, EL_L1 - GS, lw="fine", fill="g20")
    _brk_v(v, X1, CA, EL_L1 + 0.1)
    _brk_h(v, 103.2, -35.5, -34.5)
    _bars(v, [(-35.5 + 0.3 + k * 0.78, f_b + 0.3) for k in range(6)])
    v.line((-35.5, ex_b), (-31.5, ex_b - 2.0), lw="fine", dash="hidden")
    xl = -38.3
    _ldr(v, (fx - 0.5, 102.4), (xl, 103.3), "EXISTING EXTERIOR WALL\n(12\" BRICK / CMU)", "l")
    _ldr(v, (fx + 0.04, 100.6), (xl, 102.2), "1\" EXPANSION JOINT; NO\nCONNECTION TO EXISTING", "l")
    _ldr(v, (-39.0, 99.85), (xl - 0.6, 101.2), "EXIST. SLAB (VERIFY)", "l")
    _ldr(v, (-35.52, ex_b + 0.9), (xl, 98.6), "1/2\" BOND BREAKER /\nPREMOLDED JOINT; DO NOT\nDOWEL TO EXIST. FOOTING", "l")
    _ldr(v, (-37.0, ex_b + 0.5), (xl, 96.6), "EXIST. FOOTING (ASSUMED\n2'-0\" W, B.O.F. 95'-4\"): VERIFY\nBY TEST PIT BEFORE EXCAV.", "l")
    _ldr(v, (-33.4, ex_b - 1.0), (xl, 94.2), "1V:2H LINE FROM EDGE OF EXIST. FTG.", "l")
    xr = -33.4
    _ldr(v, (-34.8, 102.6), (xr, 103.3), "C4 HSS5x5x1/4 AT GRID L1\n(1'-0\" CLEAR OF EXIST. WALL)", "r")
    _ldr(v, (-34.6, EL_TOW + 0.04), (xr, 101.9), "BASE PL 1\"x12\"x12\", (4) 3/4\"\nANCHOR RODS (MOMENT BASE)", "r")
    _ldr(v, (-31.4, EL_L1 - 0.2), (xr + 1.2, 100.8), "LINK SLAB ON GRADE", "r")
    _ldr(v, (-32.0, f_t - 0.3), (xr + 1.2, 97.9), "F3E: 4'-6\" x 5'-0\" x 1'-4\"\nECCENTRIC, (6) #6 EA. WAY\nBOT.; B.O.F. = EXIST. B.O.F.\n(DO NOT UNDERMINE)", "r")
    _dim(v, (-35.5, f_b), (-31.0, f_b), -0.45)
    _dim(v, (-35.5, f_b), (-35.0, f_b), -0.95)
    _dim(v, (fx, 103.2), (-35.0, 103.2), 0.25)
    _dtitle(sh, cell, 9, "NEW FOOTING ADJACENT TO EXISTING", sc)


def d301_f2(sh, cell):
    sc = 1 / 2
    v = _dview(sh, cell, sc, (-8.4, 93.9, 7.6, 105.6))
    X0, X1 = -4.6, 4.4
    bof = EL_TOF - 16 * IN
    pin = -8 * IN
    tp = EL_TOW - 1.5 * IN
    _earth(v, [(X0, 94.3), (X1, 94.3), (X1, 99.24), (FW_OUT, EL_TOW), (FW_OUT, EL_TOF),
               (pin - 0.17, EL_TOF), (pin - 0.17, CA), (X0, CA)])
    v.line((0.953, EL_TOW), (X1, 99.24), lw="thin")
    _gravel(v, X0, CA, pin - 0.17, GS)
    _insul_sec(v, pin - 0.1667, pin, GS - 2.0, GS)
    _crect(v, -2.5, bof, 2.5, EL_TOF)
    _conc(v, [(pin, EL_TOF), (FW_OUT, EL_TOF), (FW_OUT, EL_LEDGE), (FW_LEDGE, EL_LEDGE),
              (FW_LEDGE, tp), (pin, tp)])
    v.rect(-0.55, tp, 1.1, 1.5 * IN, lw="fine", fill="g40")
    _pl(v, -0.5, EL_TOW, 0.5, EL_TOW + 0.75 * IN)
    c0 = EL_TOW + 0.75 * IN
    _crect(v, X0, GS, -CMUh - 0.5 * IN, EL_L1, dens=0.8)
    v.rect(-CMUh - 0.5 * IN, GS, 0.5 * IN, 5 * IN, lw="fine", fill="g20")
    ct = 104.6
    for a, b in ((-CMUh, -0.25), (0.25, CMUh)):
        v.rect(a, EL_TOW, b - a, ct - EL_TOW, lw="thin", fill="white", hatch="ansi31",
               hatch_kw=dict(spacing=0.04))
    v.rect(-0.25, c0, 0.5, ct - c0, lw="thin", fill="white")
    _insul_sec(v, CMUh, CMUh + 2 * IN, EL_TOW, ct)
    _brick_sec(v, 7.8125 * IN, 11.4375 * IN, EL_LEDGE, ct)
    _brk_h(v, ct, -0.6, 1.2)
    _brk_v(v, X0, CA, EL_L1 + 0.1)
    for xx in (-1 / 3, 1 / 3):
        v.line((xx, EL_TOW - 1.25), (xx, c0 + 0.12), lw=1.2)
        _pl(v, xx - 0.12, EL_TOW - 1.25, xx + 0.12, EL_TOW - 1.25 + 0.04)
    yb = bof + 0.3
    _bars(v, [(-2.5 + 0.35 + k * 4.3 / 5, yb) for k in range(6)])
    _barline(v, [(-2.1, yb + 0.08), (2.1, yb + 0.08)])
    for xx in (pin + 0.2, FW_LEDGE - 0.2):
        _barline(v, [(xx, yb + 0.15), (xx, tp - 0.15)], w=0.8)
    for y in (97.0, 97.67, 98.33):
        v.line((pin + 0.15, y), (FW_LEDGE - 0.15, y), lw=0.6)
    _dgrid(v, 0.0, 94.4, 105.0, "")
    xl = -2.6
    _ldr(v, (-0.1, 103.8), (xl, 104.9), "C1 HSS6x6x3/8 EMBEDDED IN\nCMU; GROUT CELLS SOLID,\nSEE 5/S-302", "l")
    _ldr(v, (-0.5, tp + 0.06), (xl, 103.4), "1 1/2\" NON-SHRINK GROUT", "l")
    _ldr(v, (pin, 98.9), (xl, 102.5), "PIER 1'-7\" x 2'-0\" (INSIDE FACE\n8\" INSIDE GRID), (4) #5 VERT.\n+ #3 TIES @ 8\"; INTEGRAL W/ WALL", "l")
    _ldr(v, (pin - 0.08, 98.0), (xl, 98.6), "2\" XPS PERIMETER INSUL.", "l")
    _ldr(v, (-2.2, yb), (xl, 97.0), "F2: 5'-0\" x 5'-0\" x 1'-4\"\n(6) #5 EA. WAY BOT.", "l")
    xr = 1.4
    _ldr(v, (0.45, EL_TOW + 0.03), (xr, 103.6), "BASE PL 3/4\"x12\"x12\";\nCUT CMU TO CLEAR", "r")
    _ldr(v, (1 / 3, 98.6), (xr, 102.6), "(4) 3/4\" ANCHOR RODS\nx 1'-3\" EMBED", "r")
    _ldr(v, (0.8, 101.0), (xr, 101.6), "BRICK ON 4\" LEDGE", "r")
    _ldr(v, (2.1, EL_TOF - 0.25), (xr + 0.6, 97.65), "CF-1 CONT. THRU F2\n(B.O. F2 4\" BELOW CF-1)", "r")
    _lev(v, 5.0, EL_TOF, "T.O.F.", "r", x_from=2.5)
    _lev(v, 5.0, bof, "B.O. F2", "r", x_from=2.5)
    _lev(v, 5.0, EL_TOW, "T.O. WALL", "r", x_from=X1)
    _dim(v, (-2.5, bof), (2.5, bof), -0.45)
    _dim(v, (-2.5, bof), (-2.5, EL_TOF), 0.35)
    _dim(v, (pin, tp), (0.0, tp), 0.75)
    _dtitle(sh, cell, 10, "EXTERIOR COLUMN FOOTING F2 / PIER", sc)


def d301_corner(sh, cell):
    sc = 1 / 2
    v = _dview(sh, cell, sc, (-5.4, -4.8, 9.6, 7.6))
    o, i = -FW_OUT, -FW_IN
    L = 7.6
    wall = Polygon([(o, o), (L, o), (L, i), (i, i), (i, L), (o, L)])
    v.geom(wall, lw="heavy", fill="white", hatch="concrete", hatch_kw=dict(scale=0.8))
    ledge = -FW_LEDGE
    v.polyline([(L, ledge), (ledge, ledge), (ledge, L)], lw="fine", dash="hidden")
    cf = Polygon([(-CF_OUT, -CF_OUT), (L, -CF_OUT), (L, -CF_IN), (-CF_IN, -CF_IN), (-CF_IN, L),
                  (-CF_OUT, L)])
    v.geom(cf, lw="fine", dash="hidden")
    v.rect(-2.5, -2.5, 5.0, 5.0, lw="fine", dash="hidden")
    v.rect(-0.25, -0.25, 0.5, 0.5, lw="thin", fill="black")
    _brk_v(v, L, o - 0.9, i + 0.9)
    _brk_h(v, L, o - 0.9, i + 0.9)
    c = 2.5 * IN
    ob, ib = o + c, i - c
    v.polyline([(L, ob), (ob, ob), (ob, L)], lw=1.4)
    v.polyline([(ib, L), (ib, ib), (L, ib)], lw=1.4)
    v.polyline([(2.5, ob + 0.09), (ob + 0.09, ob + 0.09), (ob + 0.09, 2.5)], lw=1.4, color="g50")
    v.polyline([(ib + 2.5, ib - 0.08), (ib - 0.08, ib - 0.08), (ib - 0.08, ib + 2.5)], lw=1.4,
               color="g50")
    xr = 3.4
    _ldr(v, (5.5, ob), (xr, -2.9), "#5 HORIZ. @ 12\" EA. FACE, CONT.\n(LAP 30\", STAGGER SPLICES)", "r")
    _ldr(v, (2.0, ob + 0.09), (xr, -1.6), "#5 CORNER BAR x 2'-6\" EA. LEG\n@ EA. HORIZ. BAR, OUTSIDE FACE", "r")
    _ldr(v, (ib + 1.6, ib - 0.08), (xr, 1.8), "#5 CORNER BAR x 2'-6\" EA. LEG\n@ EA. HORIZ. BAR, INSIDE FACE", "r")
    _ldr(v, (2.5, 2.2), (xr, 3.4), "F2 BELOW (5'-0\" SQ.)", "r")
    _ldr(v, (-1.3, 5.0), (xr, 5.6), "CF-1 BELOW: (3) #5 x 4'-0\"\nCORNER BARS EA. LEG", "r")
    _ldr(v, (ledge, 6.4), (xr, 6.9), "BRICK LEDGE (DASHED)", "r")
    _ldr(v, (-0.2, -0.2), (-1.0, -4.2), "C1 COLUMN ON PIER", "l")
    _dim(v, (o, 6.6), (i, 6.6), 0)
    v.line((0, -4.5), (0, 7.3), lw="hair", dash="center")
    v.line((-4.8, 0), (9.0, 0), lw="hair", dash="center")
    _dtitle(sh, cell, 11, "TYP. FOUNDATION WALL CORNER (PLAN)", sc)


def s301(sh):
    cells = sh.cells(4, 3)
    d301_ext_wall(sh, cells[0])
    d301_f1(sh, cells[1])
    d301_ts(sh, cells[2])
    d301_joints(sh, cells[3])
    d301_step(sh, cells[4])
    big = sh.merge_cells(cells, [5, 6])
    sh.rect(big["x"] + 0.02, big["y"] + 0.02, big["w"] - 0.04, big["h"] - 0.04, lw=None,
            fill="white", stroke=False)
    d301_pit(sh, big)
    d301_stair(sh, cells[7])
    d301_curb(sh, cells[8])
    d301_existing(sh, cells[9])
    d301_f2(sh, cells[10])
    d301_corner(sh, cells[11])


# ----------------------------------------------------------------------------------------
SHEETS = [
    ("S-101", "FOUNDATION PLAN", s101),
    ("S-102", "SECOND FLOOR FRAMING PLAN", s102),
    ("S-103", "ROOF FRAMING PLAN", s103),
    ("S-301", "FOUNDATION SECTIONS\nAND DETAILS", s301),
]
