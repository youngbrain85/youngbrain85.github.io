"""A-401 enlarged plans, A-402 stair sections & details, A-601 classroom interior elevations,
A-602 toilet room interior elevations.

All geometry is derived from model.py (walls, openings, rooms) and plans.py (stair geometry,
wall rendering).  Toilet fixtures, partitions and accessories are defined ONCE in this module
(FIXTURES / PARTITIONS / ACCESSORIES, plan coordinates in feet) and are rendered both in the
1/4" enlarged plans and in the interior elevations, so plans and elevations always agree.
"""
from __future__ import annotations

import math
from contextlib import contextmanager

from . import model as M
from . import plans as PL
from .cad import (FONT, FONT_B, FONT_I, TXT, Paper, View, _section_bubble, break_line,
                  door_tag, fmt_ftin, grid_bubble, keynote_tag, level_marker, notes_block,
                  room_tag, section_mark, table, vnorm, wall_tag, window_tag, wrap_lines)

IN = M.IN
CMUh = M.CMU_T / 2
P3h = M.WALL_TYPES["P3"]["thk"] / 2
P4h = M.WALL_TYPES["P4"]["thk"] / 2
Q = 1 / 4          # 1/4" = 1'-0"
TREAD, RISER, NT = PL.TREAD, PL.RISER, PL.N_TREADS


def ft(feet=0.0, inch=0.0):
    return feet + inch / 12.0


# =========================================================================================
# Generic helpers
# =========================================================================================
@contextmanager
def clipped(v: View, x0, y0, x1, y1):
    """Clip all drawing to a model-space rectangle (used for enlarged plans)."""
    c = v.c
    c.saveState()
    a, b = v.P((x0, y0)), v.P((x1, y1))
    p = c.beginPath()
    p.rect(min(a[0], b[0]), min(a[1], b[1]), abs(b[0] - a[0]), abs(b[1] - a[1]))
    c.clipPath(p, stroke=0, fill=0)
    try:
        yield
    finally:
        c.restoreState()


def ptxt(p: Paper, xy, s, size=TXT["note"], **kw):
    return p.text(xy, s, size=size, **kw)


def acc_tag(v: View, at, n, leader_to=None, size=TXT["small"]):
    """Toilet accessory tag: small circle with the accessory number (see schedule on A-401)."""
    p = Paper(v.c)
    if leader_to is not None:
        v.line(leader_to, at, lw="hair")
        v.circle(leader_to, v.paper_len(0.012), lw=None, fill="black")
    x, y = v.to_paper(at)
    r = 0.072 if len(str(n)) < 2 else 0.082
    p.circle((x, y), r, lw="fine", fill="white")
    p.text((x, y), str(n), size=size * 0.92, font=FONT_B, anchor="c", valign="mid")


def fix_tag(v: View, at, text, leader_to=None, size=TXT["small"]):
    """Plumbing fixture tag (by Div. 22, coordination only): rounded box."""
    p = Paper(v.c)
    if leader_to is not None:
        v.line(leader_to, at, lw="hair")
    x, y = v.to_paper(at)
    w = p.text_width(text, size * 0.92, FONT_B) + 0.07
    h = 0.12
    p.rect(x - w / 2, y - h / 2, w, h, lw="fine", fill="white")
    p.line((x - w / 2 + 0.025, y - h / 2), (x - w / 2 + 0.025, y + h / 2), lw="hair")
    p.line((x + w / 2 - 0.025, y - h / 2), (x + w / 2 - 0.025, y + h / 2), lw="hair")
    p.text((x, y), text, size=size * 0.92, font=FONT_B, anchor="c", valign="mid")


def elev_mark4(v: View, c, sheet, nums=(1, 2, 3, 4), r=0.12):
    """4-way interior elevation marker. nums in N, E, S, W order (None = no pointer)."""
    rr = v.paper_len(r)
    for n, d in zip(nums, ((0, 1), (1, 0), (0, -1), (-1, 0))):
        if n is None:
            continue
        tip = (c[0] + d[0] * rr * 1.8, c[1] + d[1] * rr * 1.8)
        a = (c[0] + d[1] * rr * 0.78, c[1] - d[0] * rr * 0.78)
        b = (c[0] - d[1] * rr * 0.78, c[1] + d[0] * rr * 0.78)
        v.polygon([a, tip, b], lw="fine", fill="black")
        q = (c[0] + d[0] * rr * 2.45, c[1] + d[1] * rr * 2.45)
        v.text(q, str(n), size=TXT["small"], font=FONT_B, anchor="c", valign="mid")
    v.circle(c, rr, lw="thin", fill="white")
    v.text(c, sheet, size=TXT["tiny"], anchor="c", valign="mid")


def elev_mark1(v: View, at, num, sheet, direction):
    _section_bubble(v, at, vnorm(direction), num, sheet, r=0.15)


def note(v: View, tip, at, text, side=None, width=None, size=TXT["note"], arrow="arrow"):
    """Leader note: arrow at `tip`, text at `at` (model coords)."""
    v.leader([tip, at], text if "\n" not in text else None, size=size,
             lines=text.split("\n") if "\n" in text else None, text_side=side, width=width,
             arrow=arrow)


def dim_t(v: View, p1, p2, offset, t=0.5, text=None, size=TXT["small"], side=1):
    """Dimension (horizontal or vertical) whose text sits at fraction t along the line."""
    L = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
    s = text if text is not None else fmt_ftin(L, 8)
    v.dim(p1, p2, offset, text=" ", size=size)
    horiz = abs(p1[1] - p2[1]) < 1e-9
    to = v.paper_len(0.035)
    if horiz:
        x = p1[0] + (p2[0] - p1[0]) * t
        y = p1[1] + offset
        v.text((x, y + side * to), s, size=size, anchor="c", valign="bot" if side > 0 else "top")
    else:
        y = p1[1] + (p2[1] - p1[1]) * t
        sg = 1 if p2[1] > p1[1] else -1
        x = p1[0] - sg * offset
        v.text((x - side * to, y), s, size=size, anchor="c", valign="bot" if side > 0 else "top",
               rot=90)


def btext(v: View, at, lines, size=TXT["tiny"], font=FONT, pad=0.025):
    """centered multi-line text on a white knock-out box (over linework)."""
    if isinstance(lines, str):
        lines = lines.split("\n")
    p = Paper(v.c)
    x, y = v.to_paper(at)
    w = max(p.text_width(t, size, font) for t in lines) + 2 * pad
    lead = size * 1.25 / 72
    h = lead * len(lines) + pad
    p.rect(x - w / 2, y - h / 2, w, h, lw=None, fill="white", stroke=False)
    p.mtext((x, y), lines, size=size, font=font, anchor="c", valign="mid", leading=size * 1.25)


def sub_label(p: Paper, x, y, text, w=None):
    """Small underlined sub-title used under partial views (e.g. LEVEL 1 / LEVEL 2)."""
    p.text((x, y), text, size=TXT["label"], font=FONT_B, anchor="c", valign="top", underline=True)


def legend_row(p: Paper, x, y, draw_sym, label, size=TXT["small"], dx=0.42):
    draw_sym(x + 0.15, y)
    p.text((x + dx, y), label, size=size, valign="mid")


# =========================================================================================
# Room clear faces (plan, feet) -- derived from model wall thicknesses
# =========================================================================================
def _faces(x0, y0, x1, y1, w=CMUh, e=CMUh, s=CMUh, n=CMUh):
    return dict(W=x0 + w, E=x1 - e, S=y0 + s, N=y1 - n)


BOYS = _faces(30, 12, 41, 30)                                  # 109 / 209
GIRLS = _faces(49, 12, 60, 30)                                 # 111 / 211
CUST = _faces(41, 20, 49, 30)                                  # 110 / 210
STAFF = _faces(12, 0, 20, 8.5, e=P4h, s=M.EW_IN, n=P3h)       # 107 / 207
HOIST = _faces(21, 21, 30, 30)                                 # 108 / 208

# ---- fixture layout (enlarged plans govern; consistent with plans.draw_toilets) ---------
BX = dict(acc_part=BOYS["E"] - ft(5, 1), front=BOYS["S"] + 5.0)
BX["std_part"] = BX["acc_part"] - 3.0
BX["wc_acc"] = BOYS["E"] - 1.5
BX["wc_std"] = BX["acc_part"] - 1.5
BX["ur"] = (BOYS["S"] + ft(6, 8), BOYS["S"] + ft(9, 2))
BX["screen"] = (BX["ur"][0] + BX["ur"][1]) / 2
BX["lav"] = (BOYS["S"] + ft(11, 2), BOYS["S"] + ft(13, 8))
BX["fd"] = (35.6, 21.6)

GX = dict(front=GIRLS["W"] + 5.0, parts=(GIRLS["S"] + 5.5, GIRLS["S"] + 8.5, GIRLS["S"] + 11.5))
GX["wc"] = (GIRLS["S"] + 1.5, GX["parts"][0] + 1.5, GX["parts"][1] + 1.5)
GX["lav"] = (GIRLS["S"] + ft(11, 2), GIRLS["S"] + ft(13, 8))
GX["fd"] = (56.6, 20.4)

SX = dict(wc=STAFF["S"] + 1.5, lav=STAFF["S"] + ft(4, 8))
PANEL_T = 1 * IN      # HDPE panel / door
PIL_T = 1.25 * IN     # pilaster
LAV_W, LAV_D = 20 * IN, 18 * IN
WC_D = 28.25 * IN     # elongated floor-mounted flush valve WC projection

# ---- toilet accessory catalogue (A-401 schedule; tags used on A-401 and A-602) ---------
ACC_TYPES = [
    (1, "GRAB BAR - 42\" HORIZONTAL", "1 1/2\" DIA. TYPE 304 SS, 18 GA., PEENED GRIP, CONCEALED SNAP FLANGES, 1 1/2\" WALL CLR.; 250 LBF DESIGN LOAD",
     "TOP OF BAR 34\" AFF (33\"-36\"); 12\" MAX. FROM REAR WALL, EXTEND 54\" MIN. FROM REAR WALL"),
    (2, "GRAB BAR - 36\" HORIZONTAL", "SAME AS TA-1",
     "TOP OF BAR 34\" AFF; 12\" MIN. TOWARD SIDE WALL AND 24\" MIN. ON OPEN SIDE OF WC CENTERLINE"),
    (3, "GRAB BAR - 18\" VERTICAL", "SAME AS TA-1 (ICC A117.1-2017 604.5.1)",
     "BOTTOM OF BAR 40\" AFF (39\"-41\"); CL 40\" FROM REAR WALL (39\"-41\")"),
    (4, "TOILET TISSUE DISPENSER", "SURFACE-MOUNTED, DOUBLE JUMBO-ROLL, SS, THEFT-RESISTANT SPINDLES",
     "CL 7\"-9\" IN FRONT OF WC; OUTLET 19\" AFF (15\"-48\"); 1 1/2\" MIN. BELOW GRAB BAR"),
    (5, "SANITARY NAPKIN DISPOSAL", "SURFACE-MOUNTED, SS, SELF-CLOSING LID, REMOVABLE LINER",
     "BOTTOM 24\" AFF; OPERABLE PART 48\" MAX. AFF; CLEAR OF GRAB BARS"),
    (6, "SOAP DISPENSER", "WALL-MOUNTED, 40 OZ., SS, PUSH VALVE (5 LBF MAX.)",
     "OPERABLE PART 42\" AFF (44\" MAX. OVER LAV)"),
    (7, "MIRROR 18\" x 36\"", "1/4\" FLOAT GLASS, SILVERED, 3/4\" SS CHANNEL FRAME, THEFT-PROOF HANGER",
     "BOTTOM OF REFLECTING SURFACE 40\" AFF MAX., CENTERED ON LAV"),
    (8, "PAPER TOWEL DISP. / WASTE RECEPT.", "RECESSED, SS, 16\"W x 54\"H x 4\" RECESS, 12 GAL. LINER; GC FRAMES CMU OPENING + LINTEL",
     "BOTTOM 6\" AFF (TOP OF BASE); TOWEL OUTLET 48\" MAX. AFF"),
    (9, "MOP & BROOM HOLDER W/ SHELF", "SS UTILITY SHELF 8\"D x 36\"W W/ (3) SPRING-LOADED HOLDERS + (4) HOOKS",
     "TOP OF SHELF 60\" AFF"),
]
ACC_LOC = {1: "109,111,107 (+L2)", 2: "109,111,107 (+L2)", 3: "109,111,107 (+L2)",
           4: "109,111,107 (+L2)", 5: "111,107 (+L2)", 6: "109,111,107 (+L2)",
           7: "109,111,107 (+L2)", 8: "109,111,107 (+L2)", 9: "110 / 210"}

# accessories located in plan: (room, tag, wall, along_center, width_ft, z_bottom_ft, z_top_ft, proj_ft)
# along = x for N/S walls, y for E/W walls; wall may also be a partition id ('BP1' etc.)
GB_Z = 34 * IN          # top of horizontal grab bar
ACCESSORIES = []


def _acc(room, tag, wall, along, w, zb, zt, proj):
    ACCESSORIES.append(dict(room=room, tag=tag, wall=wall, c=along, w=w, zb=zb, zt=zt, proj=proj))


def _build_accessories():
    B, G, S = BOYS, GIRLS, STAFF
    gb = 1.5 * IN
    # BOYS accessible stall (rear wall S, side wall E)
    _acc("109", 1, "E", B["S"] + 1.0 + 1.75, 3.5, GB_Z - gb, GB_Z, 3 * IN)
    _acc("109", 2, "S", BX["wc_acc"] - 0.5, 3.0, GB_Z - gb, GB_Z, 3 * IN)
    _acc("109", 3, "E", B["S"] + ft(3, 4), 3 * IN, ft(3, 4), ft(4, 10), 3 * IN)
    _acc("109", 4, "E", B["S"] + 3.0, 1.0, 13 * IN, 25 * IN, 5 * IN)
    # BOYS standard stall: TPD on the partition between stalls (west face)
    _acc("109", 4, "BP2w", B["S"] + 3.0, 1.0, 13 * IN, 25 * IN, 5 * IN)
    # BOYS lavatory wall (E)
    for yl in BX["lav"]:
        _acc("109", 7, "E", yl, 1.5, ft(3, 4), ft(6, 4), 1 * IN)
    _acc("109", 6, "E", BX["lav"][0] - 0.75 - 0.4, 5 * IN, 40 * IN, 47 * IN, 4 * IN)
    _acc("109", 6, "E", (BX["lav"][0] + BX["lav"][1]) / 2, 5 * IN, 40 * IN, 47 * IN, 4 * IN)
    _acc("109", 8, "E", 28.2, 16 * IN, 0.5, 5.0, 0.0)
    # GIRLS accessible stall (rear wall W, side wall S)
    _acc("111", 1, "S", G["W"] + 1.0 + 1.75, 3.5, GB_Z - gb, GB_Z, 3 * IN)
    _acc("111", 2, "W", GX["wc"][0] + 0.5, 3.0, GB_Z - gb, GB_Z, 3 * IN)
    _acc("111", 3, "S", G["W"] + ft(3, 4), 3 * IN, ft(3, 4), ft(4, 10), 3 * IN)
    _acc("111", 4, "S", G["W"] + 3.0, 1.0, 13 * IN, 25 * IN, 5 * IN)
    _acc("111", 5, "GP1s", G["W"] + 2.0, 10 * IN, 24 * IN, 36 * IN, 4 * IN)
    # GIRLS standard stalls
    _acc("111", 4, "GP1n", G["W"] + 3.0, 1.0, 13 * IN, 25 * IN, 5 * IN)
    _acc("111", 5, "GP2s", G["W"] + 2.0, 10 * IN, 24 * IN, 36 * IN, 4 * IN)
    _acc("111", 4, "GP2n", G["W"] + 3.0, 1.0, 13 * IN, 25 * IN, 5 * IN)
    _acc("111", 5, "GP3s", G["W"] + 2.0, 10 * IN, 24 * IN, 36 * IN, 4 * IN)
    for yl in GX["lav"]:
        _acc("111", 7, "E", yl, 1.5, ft(3, 4), ft(6, 4), 1 * IN)
    _acc("111", 6, "E", GX["lav"][0] - 0.75 - 0.4, 5 * IN, 40 * IN, 47 * IN, 4 * IN)
    _acc("111", 6, "E", (GX["lav"][0] + GX["lav"][1]) / 2, 5 * IN, 40 * IN, 47 * IN, 4 * IN)
    _acc("111", 8, "E", 28.2, 16 * IN, 0.5, 5.0, 0.0)
    # STAFF TOILET (rear wall W, side wall S)
    _acc("107", 1, "S", S["W"] + 1.0 + 1.75, 3.5, GB_Z - gb, GB_Z, 3 * IN)
    _acc("107", 2, "W", SX["wc"] + 0.5, 3.0, GB_Z - gb, GB_Z, 3 * IN)
    _acc("107", 3, "S", S["W"] + ft(3, 4), 3 * IN, ft(3, 4), ft(4, 10), 3 * IN)
    _acc("107", 4, "S", S["W"] + 3.0, 1.0, 13 * IN, 25 * IN, 5 * IN)
    _acc("107", 5, "S", S["W"] + ft(5, 3), 10 * IN, 24 * IN, 36 * IN, 4 * IN)
    _acc("107", 7, "E", SX["lav"], 1.5, ft(3, 4), ft(6, 4), 1 * IN)
    _acc("107", 6, "E", SX["lav"] - 0.75 - 0.4, 5 * IN, 40 * IN, 47 * IN, 4 * IN)
    _acc("107", 8, "E", 7.2, 16 * IN, 0.5, 5.0, 0.0)
    # CUSTODIAL
    _acc("110", 9, "W", 24.6, 3.0, ft(4, 4), 5.0, 8 * IN)


_build_accessories()

# stall fronts: (room, axis, k, segments). axis 'x' = front runs along x at y = k.
# seg: ('pil', a, b) | ('panel', a, b) | ('door', a, b, hinge_end 'a'/'b', swing +1/-1, acc)
STALL_FRONTS = [
    ("109", "x", BX["front"], [
        ("pil", BX["std_part"] - 0.042, BX["std_part"] + 0.458),
        ("door", BX["std_part"] + 0.458, BX["std_part"] + 2.458, "a", -1, False),
        ("pil", BX["std_part"] + 2.458, BX["acc_part"] + 0.291),
        ("door", BX["acc_part"] + 0.291, BX["acc_part"] + 3.291, "b", +1, True),
        ("pil", BX["acc_part"] + 3.291, BX["acc_part"] + 3.791),
        ("panel", BX["acc_part"] + 3.791, BOYS["E"]),
    ]),
    ("111", "y", GX["front"], [
        ("panel", GIRLS["S"], GIRLS["S"] + ft(1, 8.25)),
        ("pil", GIRLS["S"] + ft(1, 8.25), GIRLS["S"] + ft(2, 2.25)),
        ("door", GIRLS["S"] + ft(2, 2.25), GIRLS["S"] + ft(5, 2.25), "a", +1, True),
        ("pil", GIRLS["S"] + ft(5, 2.25), GX["parts"][0] + 0.25),
        ("door", GX["parts"][0] + 0.25, GX["parts"][0] + 2.25, "b", -1, False),
        ("pil", GX["parts"][0] + 2.25, GX["parts"][1] + 0.25),
        ("door", GX["parts"][1] + 0.25, GX["parts"][1] + 2.25, "b", -1, False),
        ("pil", GX["parts"][1] + 2.25, GX["parts"][2] + 0.042),
    ]),
]
# side panels (room, p1, p2)
STALL_PANELS = [
    ("109", (BX["std_part"], BOYS["S"]), (BX["std_part"], BX["front"])),
    ("109", (BX["acc_part"], BOYS["S"]), (BX["acc_part"], BX["front"])),
    ("111", (GIRLS["W"], GX["parts"][0]), (GX["front"], GX["parts"][0])),
    ("111", (GIRLS["W"], GX["parts"][1]), (GX["front"], GX["parts"][1])),
    ("111", (GIRLS["W"], GX["parts"][2]), (GX["front"], GX["parts"][2])),
]
PART_Z = (1.0, ft(5, 10))          # HDPE panels/doors 12" to 70" AFF (58" high)
PIL_TOP = ft(6, 10)                # pilaster / headrail 82" AFF
SCREEN_Z = (1.0, 4.5)              # urinal screen 18" x 42" at 12" AFF
WAINSCOT = 7.0
TILE_BASE = 0.5
CLG_TOILET = 9.0


# =========================================================================================
# Plan symbols (1/4" and larger)
# =========================================================================================
def _frame(x, y, f):
    fx, fy = f
    px, py = -fy, fx

    def P(a, b):
        return (x + fx * a + px * b, y + fy * a + py * b)
    return P


def _ellipse(P, ca, ra, rb, n=36, a0=0, a1=360):
    pts = []
    for i in range(n + 1):
        t = math.radians(a0 + (a1 - a0) * i / n)
        pts.append(P(ca + ra * math.cos(t), rb * math.sin(t)))
    return pts


def wc_plan(v, x, y, f, valve_side=1):
    """Floor-mounted elongated flush-valve WC; (x, y) = wall face at fixture CL, f = facing."""
    P = _frame(x, y, f)
    v.polygon([P(0, -0.3), P(0, 0.3), P(0.62, 0.3), P(0.62, -0.3)], lw="fine", fill="white")
    v.polygon(_ellipse(P, 1.42, WC_D - 1.42, 0.66), lw="thin", fill="white")
    v.polyline(_ellipse(P, 1.5, 0.62, 0.46), lw="hair")
    v.circle(P(0.22, valve_side * 0.52), 0.1, lw="hair")
    v.line(P(0.0, valve_side * 0.52), P(0.12, valve_side * 0.52), lw="hair")


def urinal_plan(v, x, y, f):
    P = _frame(x, y, f)
    v.polygon(_ellipse(P, 0.0, 1.15, 0.72, 24, -90, 90), lw="thin", fill="white")
    v.polyline(_ellipse(P, 0.0, 0.85, 0.48, 24, -90, 90), lw="hair")
    v.circle(P(0.15, 0), 0.08, lw="hair")


def lav_plan(v, x, y, f):
    P = _frame(x, y, f)
    hw = LAV_W / 2
    v.polygon([P(0, -hw), P(0, hw), P(LAV_D, hw), P(LAV_D, -hw)], lw="thin", fill="white")
    v.polyline(_ellipse(P, 0.82, 0.5, 0.58), lw="hair")
    v.circle(P(0.22, 0), 0.06, lw="hair")
    v.circle(P(0.85, 0), 0.05, lw="hair")


def mop_sink_plan(v, x0, y0):
    v.rect(x0, y0, 2.0, 2.0, lw="thin", fill="white")
    v.rect(x0 + 0.2, y0 + 0.2, 1.6, 1.6, lw="hair")
    v.circle((x0 + 1.0, y0 + 1.0), 0.12, lw="hair")
    v.line((x0 + 0.9, y0 + 1.0), (x0 + 1.1, y0 + 1.0), lw="hair")


def floor_drain(v, at):
    r = 0.3
    v.circle(at, r, lw="fine", fill="white")
    v.line((at[0] - r, at[1]), (at[0] + r, at[1]), lw="hair")
    v.line((at[0], at[1] - r), (at[0], at[1] + r), lw="hair")


def panel_plan(v, p1, p2, t=PANEL_T, fill="g40"):
    if abs(p1[1] - p2[1]) < 1e-9:   # along x
        x0, x1 = sorted((p1[0], p2[0]))
        v.rect(x0, p1[1] - t / 2, x1 - x0, t, lw="hair", fill=fill)
    else:
        y0, y1 = sorted((p1[1], p2[1]))
        v.rect(p1[0] - t / 2, y0, t, y1 - y0, lw="hair", fill=fill)


def stall_front_plan(v, axis, k, segs):
    def pt(a, b):
        return (a, b) if axis == "x" else (b, a)
    for s in segs:
        kind = s[0]
        a, b = s[1], s[2]
        if kind == "pil":
            q0, q1 = pt(a, k - PIL_T / 2), pt(b, k + PIL_T / 2)
            v.rect(min(q0[0], q1[0]), min(q0[1], q1[1]), abs(q1[0] - q0[0]), abs(q1[1] - q0[1]),
                   lw="fine", fill="g60")
        elif kind == "panel":
            panel_plan(v, pt(a, k), pt(b, k))
        elif kind == "door":
            hinge, sw = s[3], s[4]
            piv = a if hinge == "a" else b
            other = b if hinge == "a" else a
            L = abs(b - a)
            # open leaf (90 deg) + swing arc
            p0 = pt(piv, k + sw * PANEL_T / 2)
            p1 = pt(piv, k + sw * (L + PANEL_T / 2))
            v.line(p0, p1, lw="thin")
            c = pt(piv, k)
            if axis == "x":
                a_open = 90 if sw > 0 else -90
                a_closed = 0 if other > piv else 180
            else:
                a_open = 0 if sw > 0 else 180
                a_closed = 90 if other > piv else -90
            lo, hi = sorted([a_open, a_closed])
            if hi - lo > 180:
                lo, hi = hi, lo + 360
            v.arc(c, L, lo, hi, lw="hair")


def grab_bar_plan(v, wall, along0, along1, k):
    """grab bar drawn 1 1/2" off a wall face at coordinate k (wall: N/E/S/W)."""
    inward = {"N": -1, "S": 1, "E": -1, "W": 1}[wall]
    a0, a1 = k + inward * 1.5 * IN, k + inward * 3.0 * IN
    if wall in ("N", "S"):
        v.rect(along0, min(a0, a1), along1 - along0, abs(a1 - a0), lw="hair", fill="g50")
        for e in (along0 + 0.08, along1 - 0.08):
            v.line((e, k), (e, a0), lw="hair")
    else:
        v.rect(min(a0, a1), along0, abs(a1 - a0), along1 - along0, lw="hair", fill="g50")
        for e in (along0 + 0.08, along1 - 0.08):
            v.line((k, e), (a0, e), lw="hair")


def _wall_k(room_faces, wall):
    return room_faces[wall]


def _part_surface(pid):
    """partition faces used as accessory mounting surfaces: returns (axis, k, inward_sign)."""
    t = PANEL_T / 2
    m = {
        "BP2w": ("y", BX["acc_part"] - t, -1),
        "GP1s": ("x", GX["parts"][0] - t, -1),
        "GP1n": ("x", GX["parts"][0] + t, +1),
        "GP2s": ("x", GX["parts"][1] - t, -1),
        "GP2n": ("x", GX["parts"][1] + t, +1),
        "GP3s": ("x", GX["parts"][2] - t, -1),
    }
    return m[pid]


ROOM_FACES = {"109": BOYS, "111": GIRLS, "107": STAFF, "110": CUST}


def acc_rect_plan(a):
    """plan rectangle (x0, y0, x1, y1) of an accessory and its mounting-surface point."""
    if a["wall"] in ("N", "S", "E", "W"):
        F = ROOM_FACES[a["room"]]
        k = F[a["wall"]]
        axis = "x" if a["wall"] in ("N", "S") else "y"
        s = {"N": -1, "S": 1, "E": -1, "W": 1}[a["wall"]]
    else:
        axis_, k, s = _part_surface(a["wall"])
        axis = "x" if axis_ == "x" else "y"
    lo, hi = a["c"] - a["w"] / 2, a["c"] + a["w"] / 2
    d = a["proj"] if a["proj"] > 0 else -4 * IN
    if axis == "x":
        return (lo, min(k, k + s * d), hi, max(k, k + s * d)), (a["c"], k + s * d), s, axis
    return (min(k, k + s * d), lo, max(k, k + s * d), hi), (k + s * d, a["c"]), s, axis


def draw_accessories_plan(v, rooms, tags=True, tag_pos=None):
    tag_pos = tag_pos or {}
    for i, a in enumerate(ACCESSORIES):
        if a["room"] not in rooms:
            continue
        (x0, y0, x1, y1), tip, s, axis = acc_rect_plan(a)
        if a["tag"] in (1, 2):
            F = ROOM_FACES[a["room"]]
            grab_bar_plan(v, a["wall"], a["c"] - a["w"] / 2, a["c"] + a["w"] / 2, F[a["wall"]])
        elif a["tag"] == 3:
            F = ROOM_FACES[a["room"]]
            k = F[a["wall"]]
            inward = {"N": -1, "S": 1, "E": -1, "W": 1}[a["wall"]]
            c = (a["c"], k + inward * 2.25 * IN) if a["wall"] in ("N", "S") else \
                (k + inward * 2.25 * IN, a["c"])
            v.circle(c, 0.75 * IN, lw="hair", fill="g50")
        elif a["tag"] == 8:
            v.rect(x0, y0, x1 - x0, y1 - y0, lw="fine", fill="white")
            v.line((x0, y0), (x1, y1), lw="hair")
        elif a["tag"] == 7:
            v.rect(x0, y0, x1 - x0, y1 - y0, lw="hair", fill="g20")
        else:
            v.rect(x0, y0, x1 - x0, y1 - y0, lw="fine", fill="white")
        if tags:
            key = (a["room"], i)
            if key in tag_pos:
                at = tag_pos[key]
                if at is not None:
                    acc_tag(v, at, a["tag"], leader_to=tip if _far(v, at, tip) else None)


def _far(v, a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1]) > v.paper_len(0.11)


def draw_partitions_plan(v, rooms):
    for room, axis, k, segs in STALL_FRONTS:
        if room in rooms:
            stall_front_plan(v, axis, k, segs)
    for room, p1, p2 in STALL_PANELS:
        if room in rooms:
            panel_plan(v, p1, p2)
    if "109" in rooms:
        y = BX["screen"]
        panel_plan(v, (BOYS["W"], y), (BOYS["W"] + 1.5, y))


def draw_fixtures_plan(v, level):
    B, G, S, C = BOYS, GIRLS, STAFF, CUST
    # boys
    wc_plan(v, BX["wc_acc"], B["S"], (0, 1), valve_side=1)
    wc_plan(v, BX["wc_std"], B["S"], (0, 1))
    for y in BX["ur"]:
        urinal_plan(v, B["W"], y, (1, 0))
    for y in BX["lav"]:
        lav_plan(v, B["E"], y, (-1, 0))
    floor_drain(v, BX["fd"])
    # girls
    wc_plan(v, G["W"], GX["wc"][0], (1, 0), valve_side=-1)
    for y in GX["wc"][1:]:
        wc_plan(v, G["W"], y, (1, 0))
    for y in GX["lav"]:
        lav_plan(v, G["E"], y, (-1, 0))
    floor_drain(v, GX["fd"])
    # custodial
    mop_sink_plan(v, C["W"], C["S"])


# =========================================================================================
# A-401  ENLARGED PLANS
# =========================================================================================
def _plan_base(v, level, box_, stairs=False, elevator=False):
    x0, y0, x1, y1 = box_
    with clipped(v, x0, y0, x1, y1):
        PL.draw_walls(v, level, "normal")
        PL.draw_openings(v, level, swing=True)
        if stairs:
            pass
        if elevator:
            pass


def _grid_marks(v, xs, ys, box_, top=True, left=True, gap=1.4):
    x0, y0, x1, y1 = box_
    dia = 0.36
    r = v.paper_len(dia / 2)
    for lab, x in xs:
        v.line((x, y1 + 0.2), (x, y1 + gap + 1.5), lw="hair", dash="grid")
        grid_bubble(v, (x, y1 + gap + 1.5 + r), lab, dia, size=TXT["label"])
    for lab, y in ys:
        v.line((x0 - 0.2, y), (x0 - gap - 1.5, y), lw="hair", dash="grid")
        grid_bubble(v, (x0 - gap - 1.5 - r, y), lab, dia, size=TXT["label"])


def toilet_plan(sh, ox, oy, level):
    """Enlarged toilet plan, crop x 28..62, y -2..32 at 1/4". (ox, oy) = paper pos of model (28,-2)."""
    L2 = level == "L2"
    box_ = (28.0, -2.0, 62.0, 32.0)
    v = sh.view(ox, oy, Q, mx=28.0, my=-2.0)
    off = 100 if L2 else 0

    def n(k):
        return str(k + off)
    B, G, C = BOYS, GIRLS, CUST
    with clipped(v, *box_):
        PL.draw_walls(v, level, "normal")
        PL.draw_openings(v, level, swing=True)
        # EWC on corridor side (coordination)
        v.rect(38.0, 30 + CMUh, 2.6, 1.5, lw="fine", fill="white")
        v.line((39.3, 30 + CMUh), (39.3, 30 + CMUh + 1.5), lw="hair")
    v.text((40.85, 31.05), "EWC", size=TXT["tiny"], valign="mid")
    draw_fixtures_plan(v, level)
    draw_partitions_plan(v, ("109", "111"))
    tp = {}
    for i, a in enumerate(ACCESSORIES):
        if a["room"] in ("109", "111", "110"):
            tp[(a["room"], i)] = None
    _acc_tag_positions(tp, L2)
    draw_accessories_plan(v, ("109", "111", "110"), tag_pos=tp)
    if L2:   # roof hatch above + fixed ladder (floor-anchored, braced to east wall)
        v.rect(45.5, 25.5, 2.5, 3.0, lw="fine", dash="hidden")
        yl = 25.75
        for xr in (46.0, 47.5):
            v.rect(xr - 0.03, yl - 0.1, 0.06, 0.2, lw="hair", fill="black")
        v.line((46.0, yl), (47.5, yl), lw="thin")
        v.line((47.53, yl - 0.05), (C["E"], yl - 0.05), lw="fine")
        v.line((47.53, yl + 0.05), (C["E"], yl + 0.05), lw="fine")
        btext(v, (46.75, 27.3), "ROOF HATCH\n30\"x36\" ABOVE")
        btext(v, (46.75, 24.75), "FIXED STEEL\nLADDER")
    # ---- room tags / labels
    room_tag(v, (35.6, 27.6), "BOYS", n(109), size=TXT["room"])
    room_tag(v, (56.1, 27.6), "GIRLS", n(111), size=TXT["room"])
    room_tag(v, (45.9, 25.0) if not L2 else (43.5, 28.25), "CUST.", n(110), size=TXT["label"])
    room_tag(v, (45.0, 6.4), "MECH. / ELEC." if not L2 else "STORAGE / IDF", n(112),
             size=TXT["room"])
    v.text((28.6, 31.05), "CORRIDOR " + n(100), size=TXT["small"], font=FONT_B, valign="mid")
    v.text((BX["wc_acc"] - 0.75, BX["front"] - 0.55), "ACCESSIBLE", size=TXT["tiny"],
           anchor="c")
    v.text((GX["front"] - 2.3, GX["parts"][0] - 0.5), "ACCESSIBLE", size=TXT["tiny"],
           anchor="c")
    # ---- door tags
    door_tag(v, (33.5, 31.05), n(109))
    door_tag(v, (46.7, 31.05), n(110))
    door_tag(v, (56.5, 31.05), n(111))
    door_tag(v, (47.6, 18.4), n(110) + "B")
    if not L2:
        door_tag(v, (36.5, -1.25), "112")
    # ---- wall tags
    for at, t in (((30.0, 25.5), "P2"), ((30.0, 16.0), "P1"), ((41.0, 14.0), "P1"),
                  ((49.0, 14.0), "P1"), ((60.0, 17.0), "P1"), ((52.5, 30.0), "P1"),
                  ((53.5, 12.0), "P1"), ((42.6, 20.0), "P1")):
        wall_tag(v, at, t)
    # ---- interior elevation marks -> A-602
    elev_mark4(v, (35.7, 24.0), "A-602", (1, 2, 3, 4))
    elev_mark4(v, (56.25, 23.0), "A-602", (5, 6, 7, 8))
    elev_mark1(v, (34.3, 20.1), 14, "A-602", (0, -1))
    elev_mark1(v, (57.0, 15.2), 15, "A-602", (-1, 0))
    elev_mark1(v, (45.2, 22.0) if not L2 else (45.3, 22.55), 13, "A-602", (-1, 0))
    # ---- fixture tags
    fix_tag(v, (37.7, 13.9), "WC-1", leader_to=(BX["wc_acc"] - 0.3, B["S"] + 1.5))
    fix_tag(v, (33.15, 13.3), "WC-2", leader_to=(BX["wc_std"] - 0.25, B["S"] + 1.2))
    fix_tag(v, (32.75, 22.9), "UR-1", leader_to=(B["W"] + 0.8, BX["ur"][1] + 0.25))
    fix_tag(v, (37.6, 25.25), "LAV-1", leader_to=(B["E"] - 1.0, BX["lav"][1] - 0.35))
    fix_tag(v, (52.0, 15.9), "WC-1", leader_to=(G["W"] + 1.7, GX["wc"][0] + 0.4))
    fix_tag(v, (52.3, 22.55), "WC-2", leader_to=(G["W"] + 1.9, GX["wc"][2] + 0.1))
    fix_tag(v, (57.2, 21.7), "LAV-1", leader_to=(G["E"] - 1.0, GX["lav"][0] - 0.35))
    fix_tag(v, (44.7, 20.95) if not L2 else (47.6, 21.0), "MS-1",
            leader_to=(C["W"] + 1.5, C["S"] + 1.3))
    for fd in (BX["fd"], GX["fd"]):
        v.text((fd[0] + 0.42, fd[1] - 0.1), "FD", size=TXT["tiny"], font=FONT_B, valign="top")
    note(v, (B["W"] + 1.25, BX["screen"]), (33.4, 21.35), "US-1", side="r", size=TXT["small"])
    # ---- dimensions (interior, clear)
    sm = TXT["small"]
    v.dim_chain([(B["W"], 17.85), (BX["std_part"], 17.85), (BX["wc_std"], 17.85),
                 (BX["acc_part"], 17.85), (BX["wc_acc"], 17.85), (B["E"], 17.85)], 0, size=sm)
    v.dim_chain([(32.3, B["S"]), (32.3, BX["ur"][0]), (32.3, BX["ur"][1]), (32.3, B["N"])], 0,
                size=sm)
    v.dim((36.15, B["S"]), (36.15, BX["front"]), 0, size=sm, flip_text=True)
    v.dim_chain([(38.6, BX["front"]), (38.6, BX["lav"][0]), (38.6, BX["lav"][1]),
                 (38.6, B["N"])], 0, size=sm)
    dim_t(v, (B["W"], 28.95), (B["E"], 28.95), 0, t=0.72)
    dim_t(v, (29.05, B["S"]), (29.05, B["N"]), 0, t=0.3)
    # girls
    v.dim_chain([(54.95, G["S"]), (54.95, GX["wc"][0]), (54.95, GX["parts"][0]),
                 (54.95, GX["wc"][1]), (54.95, GX["parts"][1]), (54.95, GX["wc"][2]),
                 (54.95, GX["parts"][2])], 0, size=sm)
    v.dim((G["W"], 24.55), (GX["front"], 24.55), 0, size=sm)
    v.dim_chain([(58.05, G["S"]), (58.05, GX["lav"][0]), (58.05, GX["lav"][1]),
                 (58.05, G["N"])], 0, size=sm)
    dim_t(v, (G["W"], 28.95), (G["E"], 28.95), 0, t=0.3)
    v.dim((61.0, G["S"]), (61.0, G["N"]), 0, size=sm)
    # custodial (dimensioned on level 1 only)
    if not L2:
        dim_t(v, (C["W"], 29.2), (C["E"], 29.2), 0, t=0.5)
        v.dim((48.15, C["S"]), (48.15, C["N"]), 0, size=sm)
        v.dim((C["W"], C["S"] + 2.25), (C["W"] + 2.0, C["S"] + 2.25), 0, size=sm)
    # ---- grids + exterior chains
    _grid_marks(v, (("2", 30.0), ("3", 60.0)), (("C", 30.0), ("D", 0.0)), box_)
    v.dim_chain([(30.0, 32.0), (41.0, 32.0), (49.0, 32.0), (60.0, 32.0)], 0.8, size=sm)
    v.dim_chain([(28.0, 0.0), (28.0, 12.0), (28.0, 20.0), (28.0, 30.0)], 0.9, size=sm)
    # ---- notes in 112 / 212
    ns = TXT["small"]
    if not L2:
        note(v, (50.0, 0.6), (52.2, 3.6), "LV-1 LOUVERS ABOVE\n(8'-0\" AFF), SEE A-711",
             side="r", size=ns)
        note(v, (33.4, 10.2), (35.4, 8.6), "ELEVATOR CONTROLLER\n(BY ELEV. CONTR.)", side="r",
             size=ns)
        v.rect(30.4, 9.4, 3.0, 2.2, lw="fine", dash="dashed")
    else:
        note(v, (34.0, 11.6), (35.4, 9.0), "FRT PLYWOOD BACKBOARD\n3/4\" x 4' x 8' (3) AT IDF",
             side="r", size=ns)
        v.rect(30.4, 11.55, 12.0, 0.12, lw="fine", fill="g30")
    return v


def _acc_tag_positions(tp, L2=False):
    """hand-placed tag positions (model coords) for the 1/4" toilet plans."""
    B, G, C = BOYS, GIRLS, CUST
    for (room, i) in list(tp):
        a = ACCESSORIES[i]
        t = a["tag"]
        pos = None
        if room == "109":
            if t == 1:
                pos = (B["E"] - 0.75, B["S"] + 2.0)
            elif t == 2:
                pos = (BX["wc_acc"] - 1.6, B["S"] + 0.7)
            elif t == 3:
                pos = (B["E"] - 0.75, B["S"] + 4.45)
            elif t == 4 and a["wall"] == "E":
                pos = (B["E"] - 1.35, B["S"] + 3.15)
            elif t == 4:
                pos = (BX["acc_part"] - 0.6, B["S"] + 3.95)
            elif t == 7:
                pos = (B["E"] - 0.75, a["c"] + 0.45)
            elif t == 6:
                pos = (B["E"] - 0.95, a["c"])
            elif t == 8:
                pos = (B["E"] - 0.8, 28.2)
        elif room == "111":
            if t == 1:
                pos = (G["W"] + 1.6, G["S"] + 0.62)
            elif t == 2:
                pos = (G["W"] + 0.65, GX["wc"][0] + 1.45)
            elif t == 3:
                pos = (G["W"] + 4.3, G["S"] + 0.62)
            elif t == 4 and a["wall"] == "S":
                pos = (G["W"] + 2.75, G["S"] + 1.35)
            elif t == 4:
                pos = (a["c"] + 0.6, GX["parts"][0 if a["wall"] == "GP1n" else 1] + 0.75)
            elif t == 5:
                pos = (a["c"] - 0.45, GX["parts"][{"GP1s": 0, "GP2s": 1, "GP3s": 2}[a["wall"]]]
                       - 0.62)
            elif t == 7:
                pos = (G["E"] - 0.75, a["c"] + 0.45)
            elif t == 6:
                pos = (G["E"] - 0.95, a["c"])
            elif t == 8:
                pos = (G["E"] - 0.8, 28.2)
        elif room == "110":
            pos = (C["W"] + 1.1, a["c"])
        tp[(room, i)] = pos


# ---- stairs ------------------------------------------------------------------------------
STAIR_BOX = {"ST-1": (-1.3, -1.6, 13.0, 31.6), "ST-2": (137.0, 40.4, 151.6, 73.6)}


def stair_plan(sh, ox, oy, name, level, show_dims=True):
    g = PL.stair_geom(name)
    st1 = name == "ST-1"
    box_ = STAIR_BOX[name]
    v = sh.view(ox, oy, Q, mx=box_[0], my=box_[1])
    x0, x1, y0, y1, fw = g["x0"], g["x1"], g["y0"], g["y1"], g["fw"]
    f_lo, f_hi, du = g["f_lo"], g["f_hi"], g["dir_up"]
    up, up2 = g["up"], g["up2"]          # (x range) first flight (L1->mid) / second flight
    with clipped(v, *box_):
        PL.draw_walls(v, level, "normal")
        PL.draw_openings(v, level, swing=True)
    risers = [f_lo + i * TREAD for i in range(NT + 1)]
    bot1 = f_hi if du < 0 else f_lo     # bottom riser line of flight 1 (at floor landing)
    top1 = f_lo if du < 0 else f_hi     # top of flight 1 (at intermediate landing)
    well = (min(up[1], up2[1]), max(up[0], up2[0]))
    well = (min(up[0], up2[0]) + fw, max(up[0], up2[0]))
    hr = 2.25 * IN
    if level == "L1":
        order = sorted(risers, key=lambda yy: abs(yy - bot1))
        ncut = 7
        for i, yy in enumerate(order):
            v.line((up[0], yy), (up[1], yy), lw="thin" if i < ncut else "hair",
                   dash=None if i < ncut else "hidden")
        ycut = order[ncut - 1] + du * 0.35
        v.line((up[0] - 0.15, ycut + du * 1.1), (up[1] + 0.15, ycut - du * 0.5), lw="thin")
        # flight 2 above (dashed) + intermediate landing edge above
        for yy in risers:
            v.line((up2[0], yy), (up2[1], yy), lw="hair", dash="hidden")
        v.line((up2[0], top1), (up[1], top1), lw="hair", dash="hidden")
        # stringers/rails of flight 1 up to the cut, dashed beyond
        ya, yb = bot1, ycut
        for xx in (up[0], up[1]):
            v.line((xx, ya), (xx, yb), lw="fine")
            v.line((xx, yb), (xx, top1), lw="hair", dash="hidden")
        xw = up[0] if st1 else up[1]          # well side of flight 1
        xo = up[1] if st1 else up[0]          # wall side of flight 1
        si = 1 if st1 else -1                 # direction from well into flight 1
        # handrails (wall + well) with bottom extension one tread
        for xx in (xo - si * hr, xw + si * hr):
            v.line((xx, bot1 + du * 0 - du * TREAD), (xx, ycut), lw="fine")
        v.line((xo - si * hr, bot1 - du * TREAD), (xo, bot1 - du * TREAD), lw="fine")
        # arrow
        xm = (up[0] + up[1]) / 2
        a, b = bot1 + du * 0.5, bot1 + du * (NT * TREAD - 0.8)
        v.line((xm, a), (xm, b), lw="fine")
        v._arrowhead((xm, b), (0, du), size_in=0.08)
        v.text((xm + 0.35, a + du * 0.9), "UP 24R", size=TXT["small"], font=FONT_B,
               anchor="l" if du > 0 else "r", valign="mid", rot=90)
        btext(v, ((up2[0] + up2[1]) / 2, (f_lo + f_hi) / 2), "FLIGHT\nABOVE")
    else:
        for yy in risers:
            v.line((up[0], yy), (up[1], yy), lw="thin")
            v.line((up2[0], yy), (up2[1], yy), lw="thin")
        for xx in (up[0], up[1], up2[0], up2[1]):
            v.line((xx, f_lo), (xx, f_hi), lw="fine")
        # guard at the L2 landing edge over flight 1
        v.rect(up[0], bot1 - 0.06, up[1] - up[0], 0.12, lw="fine", fill="g40")
        xw2 = up2[1] if st1 else up2[0]
        xo2 = up2[0] if st1 else up2[1]
        si2 = -1 if st1 else 1
        xw = up[0] if st1 else up[1]
        xo = up[1] if st1 else up[0]
        si = 1 if st1 else -1
        # wall rails both flights; L2 top extension 12" horizontal
        v.line((xo2 - si2 * hr, top1), (xo2 - si2 * hr, bot1 - du * 1.0), lw="fine")
        v.line((xo2 - si2 * hr, bot1 - du * 1.0), (xo2, bot1 - du * 1.0), lw="fine")
        v.line((xo - si * hr, top1), (xo - si * hr, bot1), lw="fine")
        # well guards + continuous inside rail around the well at the intermediate landing
        v.line((xw2 + si2 * hr, bot1 - du * 1.0), (xw2 + si2 * hr, top1), lw="fine")
        v.line((xw + si * hr, top1), (xw + si * hr, bot1), lw="fine")
        yt = top1 - du * 0.35
        v.line((xw2 + si2 * hr, top1), (xw2 + si2 * hr, yt), lw="fine")
        v.line((xw2 + si2 * hr, yt), (xw + si * hr, yt), lw="fine")
        v.line((xw + si * hr, yt), (xw + si * hr, top1), lw="fine")
        xm = (up2[0] + up2[1]) / 2
        a, b = bot1 + du * 0.5, bot1 + du * (NT * TREAD - 0.8)
        v.line((xm, a), (xm, b), lw="fine")
        v._arrowhead((xm, b), (0, du), size_in=0.08)
        v.text((xm + 0.35, a + du * 0.9), "DN 24R", size=TXT["small"], font=FONT_B,
               anchor="l" if du > 0 else "r", valign="mid", rot=90)
        xm1 = up[0] + 1.0 if st1 else up[1] - 1.0
        v.text((xm1, (f_lo + f_hi) / 2), "FLIGHT BELOW", size=TXT["tiny"], anchor="c",
               valign="mid", rot=90)
    # well stringers (both levels, 12" well)
    for xx in well:
        v.line((xx, f_lo), (xx, f_hi), lw="fine" if level == "L2" else "hair",
               dash=None if level == "L2" else "hidden")
    return v, g


def stair_annot(sh, v, g, name, level):
    st1 = name == "ST-1"
    x0, x1, y0, y1 = g["x0"], g["x1"], g["y0"], g["y1"]
    f_lo, f_hi = g["f_lo"], g["f_hi"]
    up, up2 = g["up"], g["up2"]
    sm = TXT["small"]
    mid, flo = g["mid_land"], g["floor_land"]
    xs = sorted(set(round(t, 5) for t in (x0, up2[0], up2[1], up[0], up[1], x1)))
    tr = "11 TREADS @ 11\" = 10'-1\""
    if st1:
        v.dim_chain([(t, y0) for t in xs], -2.75, size=sm)
        v.dim((x0, y0), (x1, y0), -3.7, size=sm)
        v.dim((x0, f_lo), (x0, f_hi), 2.85, text=tr, size=sm)
        v.dim((x0, y0), (x0, f_lo), 2.85, size=sm)
        v.dim((x0, f_hi), (x0, y1), 2.85, size=sm)
        v.dim((x0, y0), (x0, y1), 3.85, size=sm)
    else:
        v.dim_chain([(t, y0) for t in xs], -2.75, size=sm)
        v.dim((x0, y0), (x1, y0), -3.7, size=sm)
        v.dim((x1, f_lo), (x1, f_hi), -2.85, text=tr, size=sm)
        v.dim((x1, f_hi), (x1, y1), -2.85, size=sm)
        v.dim((x1, y0), (x1, f_lo), -2.85, size=sm)
        v.dim((x1, y0), (x1, y1), -3.85, size=sm)
    mlx = (x0 + x1) / 2
    lab_mid = (mlx + (0.0 if level == "L2" else 0.0), (mid[0] + mid[1]) / 2)
    fl = (mlx, (flo[0] + flo[1]) / 2 + (2.0 if st1 else 1.4))
    if level == "L1":
        btext(v, lab_mid, "INTERMEDIATE LANDING\nABOVE - EL. 107'-0\"")
        btext(v, fl, "LEVEL 1 LANDING\nEL. 100'-0\"  RF-1")
    else:
        btext(v, lab_mid, "INTERMEDIATE LANDING\nEL. 107'-0\"  RF-1")
        btext(v, fl, "LEVEL 2 LANDING\nEL. 114'-0\"  RF-1")
    room_tag(v, (3.6, 27.3) if st1 else (145.2, 46.4),
             "STAIR " + ("1" if st1 else "2"), name, size=TXT["label"])
    if st1:
        door_tag(v, (7.9, 28.5), "ST1-A" if level == "L1" else "ST1-C")
        if level == "L1":
            door_tag(v, (2.6, 21.8), "ST1-B")
        window_tag(v, (2.2, -0.95), "W-C")
        wall_tag(v, (12.0, 20.0), "P2")
        wall_tag(v, (4.0, 30.0), "P2")
    else:
        door_tag(v, (141.2, 43.5), "ST2-A" if level == "L1" else "ST2-C")
        if level == "L1":
            door_tag(v, (147.4, 49.8), "ST2-B")
        window_tag(v, (147.8, 72.95), "W-C")
        wall_tag(v, (138.0, 50.0), "P2")
        wall_tag(v, (146.6, 42.0), "P2")
    # section cut -> A-402 (jogs into the W-C window)
    if st1:
        pts, num, look = [(9.1, 31.2), (9.1, 2.6), (6.0, 2.6), (6.0, -1.2)], 1, (-1, 0)
    else:
        pts, num, look = [(140.9, 40.8), (140.9, 69.4), (144.0, 69.4), (144.0, 73.2)], 2, (1, 0)
    v.polyline(pts, lw="med", dash="phantom")
    _section_bubble(v, pts[0], look, num, "A-402", r=0.15)
    _section_bubble(v, pts[-1], look, num, "A-402", r=0.15)
    ns = TXT["tiny"]
    hr = 2.25 * IN
    if level == "L2":
        if st1:
            note(v, (10.4, f_hi + 0.06), (12.6, f_hi + 1.9), "42\" GUARD\n6/A-402", side="r",
                 size=ns)
            note(v, (x0 + hr, f_hi + 0.6), (2.0, f_hi + 2.6), "HANDRAIL (TYP.) 5/A-402",
                 side="r", size=ns)
        else:
            note(v, (139.6, f_lo - 0.06), (137.3, f_lo - 1.9), "42\" GUARD\n6/A-402", side="l",
                 size=ns)
            note(v, (x1 - hr, f_lo - 0.6), (148.0, f_lo - 2.6), "HANDRAIL (TYP.) 5/A-402",
                 side="l", size=ns)


SUMP = (HOIST["E"] - 2.3, HOIST["S"] + 1.3)     # 24" x 24" x 24" sump pit (plan LL corner)


def elevator_plan(sh, ox, oy, scale=1 / 2, level="L1"):
    box_ = (20.3, 20.3, 30.9, 32.3)
    v = sh.view(ox, oy, scale, mx=box_[0], my=box_[1])
    with clipped(v, *box_):
        PL.draw_walls(v, level, "normal")
        PL.draw_openings(v, level, swing=True)
    H = HOIST
    cw, cd = ft(6, 8), ft(5, 5)
    cx = 25.5
    yf = H["N"] - 0.42
    # car platform + cab
    v.rect(cx - cw / 2, yf - cd, cw, cd, lw="thin", fill="white")
    v.rect(cx - cw / 2 + 0.15, yf - cd + 0.15, cw - 0.3, cd - 0.3, lw="hair")
    # car sill, hoistway sill, 2-speed side-slide car + hoistway doors (stack to west)
    v.rect(cx - 2.0, yf, 4.0, 0.08, lw="hair", fill="g20")
    v.rect(cx - 2.0, H["N"] - 0.1, 4.0, 0.08, lw="hair", fill="g20")
    for yy in (yf + 0.1, yf + 0.18):
        v.rect(cx - 1.75 + (0.0 if yy < yf + 0.15 else 0.0), yy, 1.9, 0.07, lw="hair", fill="g40")
    for i, yy in enumerate((H["N"] - 0.25, H["N"] - 0.17)):
        v.rect(cx - 1.75 + i * 1.75, yy, 1.85, 0.07, lw="hair", fill="g40")
    # car guide rails (T-rails) both sides, counterweight + rails at rear
    for xx, sg in ((H["W"], 1), (H["E"], -1)):
        yc = yf - cd / 2
        v.rect(xx + sg * 0.12 - (0.0 if sg > 0 else 0.0) - (0.0), yc - 0.22, sg * 0.08, 0.44,
               lw="hair", fill="black")
        v.rect(xx + sg * 0.2, yc - 0.03, sg * 0.22, 0.06, lw="hair", fill="black")
        v.line((xx, yc - 0.15), (xx + sg * 0.12, yc - 0.15), lw="hair")
        v.line((xx, yc + 0.15), (xx + sg * 0.12, yc + 0.15), lw="hair")
    v.rect(cx - 1.75, H["S"] + 0.3, 3.5, 0.75, lw="fine", hatch="ansi31",
           hatch_kw=dict(spacing=0.035))
    for xx in (cx - 1.95, cx + 1.85):
        v.rect(xx, H["S"] + 0.55, 0.1, 0.25, lw="hair", fill="black")
    # below: pit ladder (strike side of entrance), sump; above: MRL machine
    v.rect(28.05, H["N"] - 0.7, 1.5, 0.58, lw="fine", dash="hidden")
    for xx in (28.05, 29.55):
        v.line((xx, H["N"]), (xx, H["N"] - 0.7), lw="hair", dash="hidden")
    v.rect(SUMP[0], SUMP[1], 2.0, 2.0, lw="fine", dash="hidden")
    v.rect(H["W"] + 0.35, H["S"] + 1.25, 2.2, 1.6, lw="fine", dash="dashed")
    # labels / notes
    btext(v, (cx, yf - cd / 2 + 0.6), "ELEV. " + ("108" if level == "L1" else "208"),
          size=TXT["label"], font=FONT_B)
    btext(v, (cx, yf - cd / 2 - 0.2), "3,500 LB MRL TRACTION\n2 STOPS (L1, L2)", size=TXT["small"])
    btext(v, (cx, H["S"] + 0.68), "CWT", size=TXT["tiny"])
    btext(v, (SUMP[0] + 1.0, SUMP[1] + 1.0), "SUMP\nBELOW", size=TXT["tiny"])
    btext(v, (H["W"] + 1.45, H["S"] + 2.05), "MRL MACH.\nABOVE", size=TXT["tiny"])
    ns = TXT["small"]
    note(v, (29.4, H["N"] - 0.4), (30.75, 28.2), "PIT LADDER\n(BELOW)", side="r", size=ns)
    note(v, (H["E"] - 0.17, yf - cd / 2 - 0.1), (30.75, 23.3), "CAR GUIDE\nRAIL", side="r",
         size=ns)
    v.rect(28.5, 30 + CMUh, 0.5, 0.12, lw="fine", fill="g40")
    note(v, (28.75, 30 + CMUh + 0.12), (29.7, 31.75), "HALL CALL STA.\n(BY ELEV. CONTR.)",
         side="r", size=ns)
    sm = TXT["small"]
    v.dim((H["W"], H["S"]), (H["E"], H["S"]), -0.65, size=sm)
    v.dim((H["E"], H["S"]), (H["E"], H["N"]), -0.85, size=sm)
    v.dim((cx - cw / 2, yf - cd), (cx + cw / 2, yf - cd), 0.35, size=sm, text="6'-8\" CAR")
    v.dim((cx + cw / 2 - 0.0, yf - cd), (cx + cw / 2, yf), -0.35, size=sm, text="5'-5\"")
    v.dim((cx - 1.75, 30 + CMUh), (cx + 1.75, 30 + CMUh), 0.45, size=sm,
          text="3'-6\" x 7'-0\" ENTRANCE")
    v.dim((23.167, 31.55), (27.833, 31.55), 0, size=sm, text="4'-8\" MO")
    wall_tag(v, (21.0, 27.5), "P2")
    wall_tag(v, (27.6, 21.0), "P2")
    door_tag(v, (22.0, 31.55), "ELEV")
    # pit section -> A-402 (N-S through the entrance, looking east)
    v.line((cx, 32.25), (cx, 31.95), lw="med", dash="phantom")
    v.line((cx, 20.6), (cx, 20.35), lw="med", dash="phantom")
    _section_bubble(v, (cx - 0.95, 32.25), (1, 0), 3, "A-402", r=0.15)
    v.line((cx - 0.95, 32.25), (cx, 32.25), lw="fine")
    _section_bubble(v, (cx - 0.95, 20.6), (1, 0), 3, "A-402", r=0.15)
    v.line((cx - 0.95, 20.6), (cx, 20.6), lw="fine")
    return v


def staff_toilet_plan(sh, ox, oy, scale=1 / 2):
    box_ = (11.3, -1.3, 20.8, 9.7)
    v = sh.view(ox, oy, scale, mx=box_[0], my=box_[1])
    S = STAFF
    with clipped(v, *box_):
        PL.draw_walls(v, "L1", "normal")
        PL.draw_openings(v, "L1", swing=True)
    wc_plan(v, S["W"], SX["wc"], (1, 0), valve_side=-1)
    lav_plan(v, S["E"], SX["lav"], (-1, 0))
    tp = {}
    for i, a in enumerate(ACCESSORIES):
        if a["room"] == "107":
            t = a["tag"]
            pos = {1: (S["W"] + 2.25, S["S"] + 0.55), 2: (S["W"] + 0.55, SX["wc"] + 1.75),
                   3: (S["W"] + 3.75, S["S"] + 0.95), 4: (S["W"] + 2.75, S["S"] + 1.25),
                   5: (S["W"] + 5.25, S["S"] + 0.75), 6: (S["E"] - 0.75, a["c"]),
                   7: (S["E"] - 0.55, a["c"] + 0.42), 8: (S["E"] - 0.55, a["c"] - 0.1)}
            tp[("107", i)] = pos[t]
    draw_accessories_plan(v, ("107",), tag_pos=tp)
    room_tag(v, (15.6, 6.9), "STAFF TOILET", "107", size=TXT["label"])
    door_tag(v, (15.2, 9.5), "107")
    fix_tag(v, (15.6, 3.2), "WC-1", leader_to=(S["W"] + 1.6, SX["wc"] + 0.3))
    fix_tag(v, (17.25, 5.25), "LAV-1", leader_to=(S["E"] - 0.8, SX["lav"] + 0.2))
    elev_mark4(v, (16.3, 4.6) if False else (15.9, 5.1), "A-602", (9, 10, 11, 12))
    sm = TXT["small"]
    v.dim_chain([(S["W"], S["S"]), (S["W"] + 3.0, S["S"]), (S["E"], S["S"])], -0.9, size=sm)
    v.dim((S["W"], S["S"]), (S["E"], S["S"]), -1.6, size=sm)
    v.dim((S["W"], S["N"]), (S["W"], S["S"]), -1.25, size=sm)
    v.dim_chain([(S["E"], S["S"]), (S["E"], SX["lav"]), (S["E"], S["N"])], -1.0, size=sm)
    v.dim((S["W"], S["S"]), (S["W"], SX["wc"]), 0.75, size=sm)
    wall_tag(v, (20.0, 1.6), "P4")
    wall_tag(v, (13.2, 8.5), "P3")
    wall_tag(v, (12.0, 4.6), "P2")
    return v


# ---- schedules / legends ----------------------------------------------------------------
PART_NOTES = [
    "TP-1 TOILET PARTITIONS (SECTION 10 21 13): SOLID HIGH-DENSITY POLYETHYLENE (HDPE), 1\" THICK, FLOOR-MOUNTED OVERHEAD-BRACED. "
    "PANELS AND DOORS 58\" HIGH MOUNTED 12\" AFF; PILASTERS 1 1/4\" x 82\" HIGH W/ 3\" SS SHOES ANCHORED TO SLAB; "
    "CLEAR ANODIZED ALUM. ANTI-GRIP HEADRAIL AT 82\" AFF; FULL-HEIGHT SS CONTINUOUS BRACKETS AT WALLS.",
    "STANDARD STALL DOORS 24\" WIDE, IN-SWINGING. ACCESSIBLE STALL DOORS 36\" WIDE (32\" CLR. MIN.), OUT-SWINGING, SELF-CLOSING, "
    "U-PULLS BOTH SIDES NEAR LATCH. EACH DOOR: CONTINUOUS SS HINGE, SLIDE LATCH, COAT HOOK / BUMPER.",
    "US-1 URINAL SCREEN: HDPE 1\" x 18\" DEEP x 42\" HIGH, BOTTOM 12\" AFF, (2) SS CONTINUOUS WALL BRACKETS.",
    "STALL WIDTHS ARE TO PANEL CENTERLINES; STALL DEPTHS FROM FACE OF FINISH TO CENTERLINE OF PILASTER LINE.",
]
ENL_NOTES = [
    "DIMENSIONS ARE CLEAR (FACE OF CMU / FACE OF GWB), TO FIXTURE CENTERLINES OR PANEL CENTERLINES. ENLARGED PLANS GOVERN OVER 1/8\" PLANS.",
    "TOILET FINISHES: PT-1 FLOOR, PT-1B BASE, CT-1 WAINSCOT TO 7'-0\" AFF, PNT-1 ABOVE, GWB-1 CEILING AT 9'-0\" AFF. CUSTODIAL: SC-1, RB-1, PNT-2, ACT-2. SEE A-602 / A-801.",
    "PLUMBING FIXTURES AND FLOOR DRAINS BY DIV. 22, SHOWN FOR COORDINATION ONLY. SLOPE PT-1 TO FD 1/8\" PER FT MAX. WITHIN 4'-0\" OF DRAIN; "
    "1:48 MAX. AT ACCESSIBLE CLEAR FLOOR SPACES.",
    "PROVIDE GROUTED CMU CELLS (CMU WALLS) OR FRT BLOCKING (STUD WALLS) AT ALL GRAB BARS, ACCESSORIES, PARTITION BRACKETS AND FIXTURE CARRIERS.",
    "ACCESSIBLE WC: CL 18\" FROM SIDE WALL (16\"-18\"); 60\" DIA. TURNING SPACE IN EACH TOILET ROOM; LAV KNEE CLEARANCE 27\" MIN.",
    "LEVEL 2 ROOMS 209 / 210 / 211 / 207 ARE IDENTICAL TO 109 / 110 / 111 / 107 UNLESS NOTED (210: ROOF HATCH + FIXED LADDER).",
    "UR-1 AT GRID 2, NORTH OF Y = 21'-0\", IS ON THE 1-HR HOISTWAY WALL (P2): NO PIPING INTO THE HOISTWAY; FIRESTOP ALL PENETRATIONS (COORD. DIV. 22).",
]
FIXTURE_LEGEND = [
    ("WC-1", "ACCESSIBLE WC: FLOOR-MOUNTED, ELONGATED, FLUSH VALVE, SEAT 17\"-19\" AFF, FLUSH CONTROL ON OPEN SIDE"),
    ("WC-2", "STANDARD WC: FLOOR-MOUNTED, ELONGATED, FLUSH VALVE"),
    ("UR-1", "URINAL: WALL-HUNG, ELONGATED RIM AT 17\" AFF MAX. (BOTH URINALS), FLUSH VALVE"),
    ("LAV-1", "LAVATORY: WALL-HUNG 20\"x18\" ON CONCEALED-ARM CARRIER, RIM 34\" AFF MAX., INSULATED TRAP + SUPPLIES"),
    ("MS-1", "MOP SERVICE BASIN 24\"x24\"x10\" MOLDED STONE, SS WALL GUARDS, HOSE + BRACKET"),
    ("FD", "FLOOR DRAIN, NICKEL-BRONZE STRAINER, TRAP PRIMER"),
]
STAIR_NOTES = [
    "STEEL PAN STAIRS: C10x15.3 STRINGERS, 14 GA. FORMED PANS W/ 1 1/2\" CONC. FILL, CLOSED RISERS; 24 RISERS @ 7\" (12 PER FLIGHT), "
    "11 TREADS @ 11\" PER FLIGHT; FLIGHTS 5'-2\" WIDE, 12\" WELL. RST-1 TREADS / RISERS, RF-1 LANDINGS. SEE A-402.",
    "HANDRAILS BOTH SIDES AT 36\" ABOVE NOSINGS (34\"-38\"), INSIDE RAIL CONTINUOUS AROUND WELL; EXTEND 12\" HORIZ. AT TOP, ONE TREAD AT SLOPE AT BOTTOM.",
    "GUARDS 42\" HIGH AT THE WELL AND THE LEVEL 2 LANDING EDGE; 1/2\" SQ. PICKETS, 4\" SPHERE MAX. OPENING. STAIR SHAFT (P2, 1-HR) CONTINUES TO ROOF.",
]


def acc_schedule(sh, x, y, width=10.8):
    rows = [[f"TA-{n}", item, desc, mh, ACC_LOC[n]] for n, item, desc, mh in ACC_TYPES]
    k = width / 10.8
    cols = [("TAG", 0.5 * k), ("ITEM", 1.95 * k), ("DESCRIPTION (SECTION 10 28 00)", 3.85 * k),
            ("MOUNTING HEIGHT / LOCATION (ICC A117.1-2017 / 2010 ADA)", 3.3 * k),
            ("ROOMS", 1.2 * k)]
    return table(sh, x, y, cols, rows, row_h=0.22, size=TXT["note"] * 0.93, wrap=True,
                 title="TOILET ACCESSORY SCHEDULE", align=["c", "l", "l", "l", "c"], max_lines=3)


def a401(sh):
    X0, X1, Y0, Y1 = sh.x0, sh.x1, sh.y0, sh.y1
    # ---------------- top row: enlarged toilet plans
    oy = Y0 + 12.45
    tx = (X0 + 1.3, X0 + 1.3 + 34 * Q + 1.35)
    for i, (lev, x) in enumerate(zip(("L1", "L2"), tx)):
        toilet_plan(sh, x, oy, lev)
        ty = oy - 0.85
        sh.view_title(x - 0.45, ty, i + 1, "ENLARGED TOILET PLAN - LEVEL " + str(i + 1), Q,
                      width=7.7)
        sh.north_arrow(x + 7.95, ty + 0.3, 0.42)
    # ---------------- bottom row: stairs
    sy = Y0 + 1.3
    gap = 0.95
    b1, b2 = STAIR_BOX["ST-1"], STAIR_BOX["ST-2"]
    w1, w2 = (b1[2] - b1[0]) * Q, (b2[2] - b2[0]) * Q
    sx = X0 + 1.05
    for i, lev in enumerate(("L1", "L2")):
        v, g = stair_plan(sh, sx + i * (w1 + gap), sy, "ST-1", lev)
        stair_annot(sh, v, g, "ST-1", lev)
        px, py = v.to_paper((6.0, 31.6))
        sub_label(sh, px, py + 0.4, "LEVEL " + lev[1])
    sh.view_title(sx - 0.65, sy - 0.75, 3, "STAIR 1 ENLARGED PLANS", Q, width=2 * w1 + 0.7)
    sx2 = sx + 2 * w1 + gap + 0.5
    for i, lev in enumerate(("L1", "L2")):
        v, g = stair_plan(sh, sx2 + i * (w2 + gap), sy, "ST-2", lev)
        stair_annot(sh, v, g, "ST-2", lev)
        px, py = v.to_paper((144.0, 73.6))
        sub_label(sh, px, py + 0.4, "LEVEL " + lev[1])
    sh.view_title(sx2 - 0.3, sy - 0.75, 4, "STAIR 2 ENLARGED PLANS", Q, width=2 * w2 + 0.7)
    # ---------------- bottom right: staff toilet + elevator at 1/2"
    bx = X0 + 19.0
    staff_toilet_plan(sh, bx + 0.95, sy + 0.05, 1 / 2)
    sh.view_title(bx + 0.35, sy - 0.75, 5, "STAFF TOILET 107 (207 SIM.)", 1 / 2, width=4.6)
    elevator_plan(sh, bx + 6.35, sy + 0.05, 1 / 2)
    sh.view_title(bx + 6.1, sy - 0.75, 6, "ELEVATOR 108 (208 SIM.)", 1 / 2, width=4.9)
    # ---------------- right column (schedules / notes)
    rx = X0 + 20.3
    cw = X1 - rx - 0.05
    h = acc_schedule(sh, rx, Y1 - 0.1, width=cw)
    yy = Y1 - 0.1 - h - 0.28
    sh.text((rx, yy), "PLUMBING FIXTURES (BY DIV. 22 - COORDINATION ONLY)", size=TXT["label"],
            font=FONT_B, valign="top", underline=True)
    yy -= 0.3
    for tag, desc in FIXTURE_LEGEND:
        vv = sh.view(rx + 0.28, yy, Q)
        if tag == "FD":
            floor_drain(vv, (0, 0))
        else:
            fix_tag(vv, (0, 0), tag)
        sh.text((rx + 0.65, yy), desc, size=TXT["note"], valign="mid")
        yy -= 0.21
    yy -= 0.14
    hgt = notes_block(sh, rx, yy, "TOILET PARTITIONS", PART_NOTES, cw)
    yy -= hgt + 0.14
    hgt = notes_block(sh, rx, yy, "ENLARGED PLAN NOTES", ENL_NOTES, cw)
    yy -= hgt + 0.14
    hgt = notes_block(sh, rx, yy, "STAIR NOTES", STAIR_NOTES, cw)
    yy -= hgt + 0.12
    sh.text((rx, yy), "SYMBOLS", size=TXT["label"], font=FONT_B, valign="top", underline=True)
    yy -= 0.4
    c2, c3 = rx + 3.75, rx + 7.55
    vv = sh.view(rx + 0.2, yy, Q)
    acc_tag(vv, (0, 0), 4)
    sh.text((rx + 0.45, yy), "TOILET ACCESSORY TAG (TA-4)", size=TXT["small"], valign="mid")
    vv = sh.view(c2 + 0.25, yy, Q)
    elev_mark4(vv, (0, 0), "A-602", (1, 2, 3, 4), r=0.09)
    sh.text((c2 + 0.65, yy), "INTERIOR ELEVATIONS", size=TXT["small"], valign="mid")
    vv = sh.view(c3 + 0.2, yy, Q)
    fix_tag(vv, (0, 0), "WC-1")
    sh.text((c3 + 0.5, yy), "PLUMBING FIXTURE TAG", size=TXT["small"], valign="mid")
    yy -= 0.34
    vv = sh.view(rx + 0.2, yy, Q)
    grab_bar_plan(vv, "S", -0.8, 0.8, -0.15)
    sh.text((rx + 0.45, yy), "GRAB BAR TA-1 / TA-2", size=TXT["small"], valign="mid")
    vv = sh.view(c2 + 0.25, yy, Q)
    panel_plan(vv, (-0.8, 0), (0.8, 0))
    sh.text((c2 + 0.65, yy), "HDPE PARTITION PANEL", size=TXT["small"], valign="mid")
    vv = sh.view(c3 + 0.2, yy, Q)
    vv.rect(-0.5, -0.25, 1.0, 0.5, lw="fine", dash="hidden")
    sh.text((c3 + 0.5, yy), "ITEM ABOVE / BELOW", size=TXT["small"], valign="mid")


# =========================================================================================
# Interior elevation engine (model x = horizontal ft from left end of wall, y = ft AFF)
# =========================================================================================
class Elev:
    """Interior elevation of one wall.  F = room clear faces, side = wall looked at."""

    def __init__(self, sh, ox, oy, F, side, clg, scale=Q, title=None, wall_t=(CMUh * 2, CMUh * 2),
                 slab=5 * IN, clg_kind="GWB"):
        self.sh, self.F, self.side, self.clg, self.s = sh, F, side, clg, scale
        self.v = sh.view(ox, oy, scale)
        self.W = (F["E"] - F["W"]) if side in ("N", "S") else (F["N"] - F["S"])
        self.wall_t = wall_t
        self.slab = slab
        self.clg_kind = clg_kind
        self.holes = []

    # plan coordinate along this wall -> h
    def h(self, c):
        F, sd = self.F, self.side
        return {"N": c - F["W"], "E": F["N"] - c, "S": F["E"] - c, "W": c - F["S"]}[sd]

    # plan coordinate perpendicular to this wall: distance from the wall face (depth)
    def depth(self, c):
        F, sd = self.F, self.side
        return {"N": F["N"] - c, "E": F["E"] - c, "S": c - F["S"], "W": c - F["W"]}[sd]

    def frame(self, top_extra=0.7):
        v, W, c = self.v, self.W, self.clg
        tl, tr = self.wall_t
        # side walls (cut) + floor slab (cut) + ceiling
        v.rect(-tl, -self.slab, tl, c + top_extra + self.slab, lw="heavy", fill="white",
               hatch="ansi31", hatch_kw=dict(spacing=0.045))
        v.rect(W, -self.slab, tr, c + top_extra + self.slab, lw="heavy", fill="white",
               hatch="ansi31", hatch_kw=dict(spacing=0.045))
        v.rect(0, -self.slab, W, self.slab, lw="heavy", fill="white", hatch="concrete",
               hatch_kw=dict(scale=0.8))
        if self.clg_kind == "GWB":
            v.rect(0, c, W, 0.06, lw="thin", fill="g40")
            for x in [i * 1.333 for i in range(int(W / 1.333) + 1)]:
                if 0.1 < x < W - 0.1:
                    v.line((x, c + 0.06), (x, c + 0.32), lw="hair", color="screen")
            v.line((0, c + 0.32), (W, c + 0.32), lw="hair", color="screen")
        else:
            v.rect(0, c, W, 0.05, lw="thin", fill="g30")
            for x in [i * 2.0 for i in range(int(W / 2.0) + 1)]:
                if 0.1 < x < W - 0.1:
                    v.line((x, c), (x, c + 0.12), lw="hair")
        v.line((-tl - 0.15, 0), (W + tr + 0.15, 0), lw="heavy")
        v.line((0, 0), (0, c), lw="heavy")
        v.line((W, 0), (W, c), lw="heavy")

    def tile(self, z0=TILE_BASE, z1=WAINSCOT, h0=0.0, h1=None):
        """CT-1 4x12 running bond wainscot with bullnose cap course; PT-1B cove base below."""
        v, W = self.v, self.W
        h1 = W if h1 is None else h1
        c = v.c
        c.saveState()
        rings = [[(h0, z0), (h1, z0), (h1, z1), (h0, z1)]]
        rings += self.holes
        v._clip_rings(rings)
        c.setLineWidth(0.2)
        c.setStrokeColor(GRAY_SCREEN)
        z = z0
        row = 0
        while z < z1 - 1e-6:
            zt = min(z + 4 * IN, z1)
            v.line((h0, zt), (h1, zt), lw="hair", color="screen")
            off = 0.0 if row % 2 == 0 else 0.5
            x = h0 + off
            while x < h1:
                if x > h0 + 1e-3:
                    v.line((x, z), (x, zt), lw="hair", color="screen")
                x += 1.0
            z = zt
            row += 1
        c.restoreState()
        # cap, base
        v.line((h0, z1), (h1, z1), lw="thin")
        v.line((h0, z1 - 0.06), (h1, z1 - 0.06), lw="hair")
        v.line((h0, z0), (h1, z0), lw="thin")
        c.saveState()
        v._clip_rings([[(h0, 0), (h1, 0), (h1, z0), (h0, z0)]] + self.holes)
        x = h0 + 1.0
        while x < h1:
            v.line((x, 0), (x, z0), lw="hair", color="screen")
            x += 2.0
        c.restoreState()

    def rb_base(self, h0=0.0, h1=None):
        h1 = self.W if h1 is None else h1
        self.v.line((h0, 4 * IN), (h1, 4 * IN), lw="thin")

    def hole(self, h0, z0, h1, z1):
        self.holes.append([(h0, z0), (h1, z0), (h1, z1), (h0, z1)])

    # ---- dims ------------------------------------------------------------------------
    def vdims(self, zs=(0, TILE_BASE, WAINSCOT), right=True, off=0.75, overall=True):
        v, W = self.v, self.W
        x = W + self.wall_t[1] if right else -self.wall_t[0]
        pts = [(x, z) for z in list(zs) + [self.clg]]
        o = -off if right else off
        v.dim_chain(pts, o, size=TXT["small"])
        if overall:
            v.dim((x, 0), (x, self.clg), o * 1.95, size=TXT["small"])

    def hdims(self, hs, tier=1, z=None):
        v = self.v
        zz = -self.slab if z is None else z
        hs = sorted(set(round(t, 5) for t in hs))
        v.dim_chain([(t, zz) for t in hs], -0.75 * tier, size=TXT["small"])

    def label(self, h, z, text, size=TXT["small"]):
        btext(self.v, (h, z), text, size=size, font=FONT_B if text.isupper() and len(text) < 7 else FONT)


GRAY_SCREEN = None


def _init_gray():
    global GRAY_SCREEN
    from .cad import SCREEN
    GRAY_SCREEN = SCREEN


_init_gray()


# ---- elevation symbols --------------------------------------------------------------------
def e_door(ev: Elev, h0, h1, hinge="l", face="pull", hw=""):
    """HM frame F1 + door in elevation; h0/h1 = masonry opening."""
    v = ev.v
    fh = 2 * IN
    v.polygon([(h0, 0), (h0, DH), (h1, DH), (h1, 0), (h1 - fh, 0), (h1 - fh, 7.0), (h0 + fh, 7.0),
               (h0 + fh, 0)], lw="thin", fill="white")
    v.rect(h0 + fh, 0, (h1 - h0) - 2 * fh, 7.0, lw="thin", fill="white")
    a, b = h0 + fh + 0.02, h1 - fh - 0.02
    hx = a if hinge == "l" else b
    lx = b - 0.25 if hinge == "l" else a + 0.25
    for zz in (0.75, 3.5, 6.25):
        v.rect(hx - 0.03, zz - 0.15, 0.06, 0.3, lw="hair", fill="g50")
    if face == "pull":
        v.rect(lx - 0.04, 3.1, 0.08, 0.9, lw="fine", fill="g40")
    else:
        v.rect(lx - 0.17, 3.25, 0.33, 1.0, lw="fine", fill="g20")
        v.rect(a + 0.08, 0.05, b - a - 0.16, 10 * IN, lw="hair", fill="g10")
    if hw:
        btext(v, ((a + b) / 2, 5.4), hw, size=TXT["tiny"])
    ev.hole(h0, 0, h1, DH)


DH = M.DH


def e_wc_front(ev: Elev, h, acc=True, valve=1):
    v = ev.v
    rim = 16.5 * IN if acc else 15 * IN
    v.polygon([(h - 0.3, 0), (h + 0.3, 0), (h + 0.36, 0.45), (h + 0.62, rim - 0.12),
               (h + 0.62, rim), (h - 0.62, rim), (h - 0.62, rim - 0.12), (h - 0.36, 0.45)],
              lw="thin", fill="white")
    v.rect(h - 0.66, rim, 1.32, 0.09, lw="fine", fill="white")
    v.rect(h - 0.6, rim + 0.09, 1.2, 0.06, lw="hair", fill="g20")
    # flush valve on the open side
    xv = h + valve * 0.38
    v.line((h + valve * 0.05, rim - 0.05), (xv, rim - 0.05), lw="fine")
    v.line((xv, rim - 0.05), (xv, 2.25), lw="fine")
    v.rect(xv - 0.12, 2.25, 0.24, 0.33, lw="fine", fill="white")
    v.line((xv, 2.58), (xv, 2.75), lw="fine")
    v.line((xv, 2.4), (xv + valve * 0.35, 2.4), lw="fine")


def e_wc_side(ev: Elev, hw, d, acc=True):
    """WC profile; hw = h of the wall the WC is mounted on, d = +1/-1 direction it projects."""
    v = ev.v
    rim = 16.5 * IN if acc else 15 * IN
    L = WC_D
    prof = [(0.3, 0.0), (1.8, 0.0), (1.9, 0.1), (1.82, 0.3), (2.0, 0.72), (2.25, 1.0),
            (L, rim - 0.06), (L, rim), (0.05, rim), (0.05, 0.95), (0.3, 0.72)]
    v.polygon([(hw + d * a, z) for a, z in prof], lw="thin", fill="white")
    v.polyline([(hw + d * 0.3, 0.72), (hw + d * 1.2, 0.62), (hw + d * 1.82, 0.3)], lw="hair")
    v.rect(min(hw + d * 0.08, hw + d * (L + 0.04)), rim, abs(L + 0.04 - 0.08), 0.09, lw="fine",
           fill="white")
    v.line((hw + d * 0.12, rim + 0.09), (hw + d * 0.12, 2.25), lw="fine")
    v.rect(min(hw + d * 0.02, hw + d * 0.22), 2.25, 0.2, 0.33, lw="fine", fill="white")


def e_urinal_front(ev: Elev, h):
    v = ev.v
    rim = 17 * IN
    pts = [(h - 0.58, rim + 0.05), (h - 0.6, 2.6), (h - 0.5, 3.05), (h, 3.15), (h + 0.5, 3.05),
           (h + 0.6, 2.6), (h + 0.58, rim + 0.05), (h + 0.45, rim - 0.12), (h - 0.45, rim - 0.12)]
    v.polygon(pts, lw="thin", fill="white")
    v.polyline([(h - 0.42, rim + 0.15), (h - 0.42, 2.55), (h, 2.75), (h + 0.42, 2.55),
                (h + 0.42, rim + 0.15)], lw="hair")
    v.line((h, 3.15), (h, 3.45), lw="fine")
    v.rect(h - 0.12, 3.45, 0.24, 0.33, lw="fine", fill="white")
    v.line((h, 3.78), (h, 4.1), lw="fine")
    v.line((h, 3.6), (h + 0.35, 3.6), lw="fine")


def e_urinal_side(ev: Elev, hw, d):
    v = ev.v
    rim = 17 * IN
    v.polygon([(hw, rim - 0.1), (hw + d * 1.15, rim + 0.05), (hw + d * 1.1, rim + 0.25),
               (hw + d * 0.55, 3.0), (hw, 3.15)], lw="thin", fill="white")
    v.line((hw + d * 0.1, 3.15), (hw + d * 0.1, 3.8), lw="fine")


def e_lav_front(ev: Elev, h):
    v = ev.v
    rim = 34 * IN
    hw = LAV_W / 2
    v.polygon([(h - hw, rim), (h + hw, rim), (h + hw, rim - 0.12), (h + hw - 0.1, 29 * IN),
               (h - hw + 0.1, 29 * IN), (h - hw, rim - 0.12)], lw="thin", fill="white")
    v.rect(h - 0.06, rim, 0.12, 0.2, lw="fine", fill="white")
    v.line((h - 0.06, rim + 0.2), (h + 0.06, rim + 0.2), lw="fine")
    # insulated trap + supplies
    v.rect(h - 0.08, 1.75, 0.16, 29 * IN - 1.75, lw="hair", fill="g20")
    v.polyline([(h, 1.75), (h, 1.6), (h - 0.35, 1.6)], lw="fine")
    for sx in (-0.4, 0.4):
        v.line((h + sx * 0.6, 29 * IN), (h + sx, 1.9), lw="hair")


def e_lav_side(ev: Elev, hw, d):
    v = ev.v
    rim = 34 * IN
    v.polygon([(hw, rim), (hw + d * LAV_D, rim), (hw + d * LAV_D, rim - 0.12),
               (hw + d * (LAV_D - 0.08), 29 * IN), (hw + d * 0.2, 29 * IN), (hw, 2.2)],
              lw="thin", fill="white")
    v.polyline([(hw + d * 0.6, 29 * IN), (hw + d * 0.6, 1.6), (hw, 1.6)], lw="fine")


def e_mirror(ev: Elev, h, w=1.5, zb=ft(3, 4), zt=ft(6, 4)):
    v = ev.v
    v.rect(h - w / 2, zb, w, zt - zb, lw="thin", fill="white")
    v.rect(h - w / 2 + 0.06, zb + 0.06, w - 0.12, zt - zb - 0.12, lw="hair")
    for k in (0.3, 0.45):
        v.line((h - w / 2 + 0.25, zb + (zt - zb) * k), (h - w / 2 + 0.55, zb + (zt - zb) * k + 0.3),
               lw="hair")


def e_box(ev: Elev, h, w, zb, zt, fill="white", lw="fine"):
    ev.v.rect(h - w / 2, zb, w, zt - zb, lw=lw, fill=fill)


def e_tpd(ev: Elev, h):
    v = ev.v
    e_box(ev, h, 1.0, 13 * IN, 25 * IN)
    for dx in (-0.22, 0.22):
        v.circle((h + dx, 19 * IN), 0.16, lw="hair")


def e_napkin(ev: Elev, h):
    e_box(ev, h, 10 * IN, 24 * IN, 36 * IN)
    ev.v.line((h - 0.3, 33 * IN), (h + 0.3, 33 * IN), lw="hair")


def e_soap(ev: Elev, h):
    v = ev.v
    e_box(ev, h, 5 * IN, 40 * IN, 47 * IN)
    v.rect(h - 0.03, 39 * IN, 0.06, 1 * IN, lw="hair", fill="black")


def e_ptd(ev: Elev, h):
    v = ev.v
    w = 16 * IN
    v.rect(h - w / 2 - 0.05, 0.45, w + 0.1, 4.6, lw="thin", fill="white")
    v.rect(h - w / 2, 3.2, w, 1.75, lw="hair")
    v.rect(h - 0.35, 3.3, 0.7, 0.06, lw="hair", fill="black")
    v.rect(h - w / 2, 0.55, w, 2.55, lw="hair")
    v.circle((h, 2.6), 0.06, lw="hair")
    ev.hole(h - w / 2 - 0.05, 0.45, h + w / 2 + 0.05, 5.05)


def e_gb_h(ev: Elev, h0, h1, zt=GB_Z):
    v = ev.v
    d = 1.5 * IN
    v.rect(h0, zt - d, h1 - h0, d, lw="fine", fill="g30")
    for x in (h0 + 0.12, h1 - 0.12):
        v.circle((x, zt - d / 2), 0.1, lw="hair", fill="white")


def e_gb_v(ev: Elev, h, zb=ft(3, 4), zt=ft(4, 10)):
    v = ev.v
    d = 1.5 * IN
    v.rect(h - d / 2, zb, d, zt - zb, lw="fine", fill="g30")
    for z in (zb + 0.12, zt - 0.12):
        v.circle((h, z), 0.1, lw="hair", fill="white")


def e_gb_profile(ev: Elev, hw, d, zt=GB_Z):
    """grab bar seen end-on / in profile on an adjacent wall."""
    v = ev.v
    v.rect(min(hw, hw + d * 3 * IN), zt - 1.5 * IN, 3 * IN, 1.5 * IN, lw="fine", fill="g30")


def e_profile_box(ev: Elev, hw, d, proj, zb, zt):
    ev.v.rect(min(hw, hw + d * proj), zb, proj, zt - zb, lw="fine", fill="white")


def e_panel_sec(ev: Elev, h, z0=PART_Z[0], z1=PART_Z[1], t=PANEL_T):
    ev.v.rect(h - t / 2, z0, t, z1 - z0, lw="fine", fill="g50")


def e_pil_sec(ev: Elev, h, t=PIL_T, top=PIL_TOP, hr=True):
    v = ev.v
    v.rect(h - t / 2, 0.25, t, top - 0.25, lw="fine", fill="g50")
    v.rect(h - t / 2 - 0.04, 0, t + 0.08, 0.25, lw="fine", fill="g20")
    if hr:
        v.rect(h - 0.08, top - 0.02, 0.16, 0.14, lw="fine", fill="g30")


def e_screen_sec(ev: Elev, h):
    e_panel_sec(ev, h, SCREEN_Z[0], SCREEN_Z[1])


def acc_e(ev: Elev, at, n, tip=None):
    acc_tag(ev.v, at, n, leader_to=tip)


def mh_dim(ev: Elev, h, z, label=None, z0=0.0, side=1):
    """vertical mounting-height dimension from z0 to z at h."""
    ev.v.dim((h, z0), (h, z), 0, text=label, size=TXT["tiny"] * 1.15, flip_text=side < 0)


# =========================================================================================
# A-602  INTERIOR ELEVATIONS - TOILET ROOMS
# =========================================================================================
def _acc_list(room, wall):
    return [a for a in ACCESSORIES if a["room"] == room and a["wall"] == wall]


def _draw_wall_acc(ev: Elev, room, wall, tags=True, tag_dz=None):
    """accessories mounted on the elevated wall, face-on."""
    for a in _acc_list(room, wall):
        h = ev.h(a["c"])
        t = a["tag"]
        if t in (1, 2):
            e_gb_h(ev, h - a["w"] / 2, h + a["w"] / 2)
            at, tip = (h + 0.35, GB_Z + 0.42), (h + 0.35, GB_Z - 0.06)
        elif t == 3:
            e_gb_v(ev, h)
            at, tip = (h + 0.42, ft(4, 6)), (h + 0.06, ft(4, 6))
        elif t == 4:
            e_tpd(ev, h)
            at, tip = (h - 0.42, 0.75), (h - 0.3, 1.25)
        elif t == 5:
            e_napkin(ev, h)
            at, tip = (h + 0.0, 3.5), (h, 3.0)
        elif t == 6:
            e_soap(ev, h)
            at, tip = (h, 4.4), (h, 47 * IN)
        elif t == 7:
            e_mirror(ev, h)
            at, tip = (h, 5.3), None
        elif t == 8:
            e_ptd(ev, h)
            at, tip = (h, 2.0), None
        elif t == 9:
            e_mop_holder(ev, h, a["w"])
            at, tip = (h, 5.45), (h, 5.0)
        if tags:
            if tag_dz and t in tag_dz:
                at = (at[0] + tag_dz[t][0], at[1] + tag_dz[t][1])
            acc_tag(ev.v, at, t, leader_to=tip)


def e_mop_holder(ev: Elev, h, w):
    v = ev.v
    v.rect(h - w / 2, 4.92, w, 0.08, lw="fine", fill="g30")
    for k in range(3):
        x = h - w / 2 + 0.6 + k * 0.9
        v.rect(x - 0.08, 4.45, 0.16, 0.42, lw="hair", fill="white")
        v.line((x, 4.45), (x, 2.4), lw="hair", dash="hidden")
    for k in range(4):
        x = h - w / 2 + 0.15 + k * 0.9
        v.polyline([(x, 4.9), (x, 4.7), (x + 0.08, 4.7)], lw="hair")


def _fin(ev: Elev, h, tile=True, wall_pnt="PNT-1", base="PT-1B", clg="GWB-1", z_ct=6.25):
    v = ev.v
    btext(v, (h, 7.6), wall_pnt, size=TXT["small"], font=FONT_B)
    if tile:
        btext(v, (h, z_ct), "CT-1", size=TXT["small"], font=FONT_B)
        btext(v, (h, 0.25), base, size=TXT["tiny"], font=FONT_B)
    else:
        btext(v, (h, 0.55), base, size=TXT["tiny"], font=FONT_B)
    btext(v, (h, ev.clg - 0.42), clg + " CLG. @ " + fmt_ftin(ev.clg) + " AFF", size=TXT["tiny"])


def _title(sh, ev: Elev, num, title, w=None):
    x0, y0 = ev.v.to_paper((-ev.wall_t[0], 0))
    sh.view_title(x0 - 0.1, y0 - 0.78, num, title, Q, width=w or (ev.W * Q + 0.6))


def elev_boys(sh, ox, oy, side, num):
    B = BOYS
    ev = Elev(sh, ox, oy, B, side, CLG_TOILET)
    ev.frame()
    W = ev.W
    if side == "N":
        d = M.OPENING_BY_ID["109"]
        h0, h1 = ev.h(d.lo), ev.h(d.hi)
        e_door(ev, h0, h1, hinge="l", face="pull", hw="")
        ev.tile()
        e_lav_side(ev, W, -1)
        e_profile_box(ev, W, -1, 1 * IN, ft(3, 4), ft(6, 4))
        door_tag(ev.v, ((h0 + h1) / 2, 7.85), "109")
        _fin(ev, 7.3)
        ev.hdims([0, h0, h1, W])
        fix_tag(ev.v, (W - 1.3, 1.6), "LAV-1", leader_to=(W - 0.8, 2.6))
    elif side == "E":
        ev.hole(ev.h(28.2) - 0.75, 0.45, ev.h(28.2) + 0.75, 5.05)
        ev.tile()
        for y in BX["lav"]:
            e_lav_front(ev, ev.h(y))
        _draw_wall_acc(ev, "109", "E", tag_dz={4: (-0.05, 0.0)})
        hf = ev.h(BX["front"])
        e_pil_sec(ev, hf)
        e_wc_side(ev, W, -1)
        e_gb_profile(ev, W, -1)
        fix_tag(ev.v, (W - 1.6, 1.85), "WC-1", leader_to=(W - 1.2, 1.2))
        fix_tag(ev.v, (ev.h(BX["lav"][1]) - 0.0, 1.15), "LAV-1",
                leader_to=(ev.h(BX["lav"][1]), 1.62))
        btext(ev.v, (hf - 0.0, 7.55), "STALL FRONT\n(SECTION)", size=TXT["tiny"])
        _fin(ev, 10.2)
        ev.hdims([0, ev.h(28.2), ev.h(BX["lav"][1]), ev.h(BX["lav"][0]), hf, W])
        ev.hdims([hf, ev.h(B["S"] + 1.0 + 3.5), ev.h(B["S"] + 1.0), W], tier=2)
        mh_dim(ev, ev.h(BX["lav"][0]) + 1.15, 34 * IN, "2'-10\" MAX")
        mh_dim(ev, ev.h(BX["lav"][1]) - 1.15, ft(3, 4), "3'-4\" MAX", side=-1)
        mh_dim(ev, W - 0.45, GB_Z, None)
    elif side == "S":
        ev.tile()
        e_wc_front(ev, ev.h(BX["wc_acc"]), acc=True, valve=1)
        e_wc_front(ev, ev.h(BX["wc_std"]), acc=False, valve=1)
        _draw_wall_acc(ev, "109", "S")
        for xp in (BX["acc_part"], BX["std_part"]):
            e_panel_sec(ev, ev.h(xp))
        hp = ev.h(BX["acc_part"])
        e_profile_box(ev, hp + PANEL_T / 2, 1, 5 * IN, 13 * IN, 25 * IN)
        acc_tag(ev.v, (hp + 0.75, 0.75), 4, leader_to=(hp + 0.3, 1.25))
        e_gb_profile(ev, 0, 1)
        e_profile_box(ev, 0, 1, 5 * IN, 13 * IN, 25 * IN)
        ev.v.rect(0, ft(3, 4), 3 * IN, ft(1, 6), lw="fine", fill="g30")
        fix_tag(ev.v, (ev.h(BX["wc_acc"]), 2.7) if False else (ev.h(BX["wc_acc"]) + 0.15, 2.0),
                "WC-1")
        fix_tag(ev.v, (ev.h(BX["wc_std"]), 2.0), "WC-2")
        btext(ev.v, (ev.h(BX["acc_part"]), 6.3), "TP-1", size=TXT["tiny"], font=FONT_B)
        _fin(ev, 9.2, z_ct=6.45)
        ev.hdims([0, ev.h(BX["wc_acc"]), ev.h(BX["acc_part"]), ev.h(BX["wc_std"]),
                  ev.h(BX["std_part"]), W])
        ev.hdims([0, ev.h(BX["wc_acc"] + 1.0), ev.h(BX["wc_acc"] - 2.0)], tier=2)
        mh_dim(ev, ev.h(BX["wc_acc"] - 2.0) + 0.3, GB_Z, None)
    elif side == "W":
        ev.tile()
        hf = ev.h(BX["front"])
        # std stall west side panel seen face-on + its front pilaster edge
        ev.v.rect(0, PART_Z[0], hf, PART_Z[1] - PART_Z[0], lw="thin", fill="g05")
        e_pil_sec(ev, hf)
        e_wc_side(ev, 0, 1, acc=False)
        for y in BX["ur"]:
            e_urinal_front(ev, ev.h(y))
        e_screen_sec(ev, ev.h(BX["screen"]))
        btext(ev.v, (hf / 2 + 0.3, 4.6), "TP-1 PANEL (STD. STALL)", size=TXT["tiny"])
        fix_tag(ev.v, (ev.h(BX["ur"][0]), 0.6), "UR-1")
        fix_tag(ev.v, (ev.h(BX["ur"][1]), 0.6), "UR-1")
        btext(ev.v, (ev.h(BX["screen"]) + 0.0, 5.0), "US-1", size=TXT["tiny"], font=FONT_B)
        btext(ev.v, (13.4, 7.5), "P2 HOISTWAY WALL BEYOND (Y > 21'-0\")", size=TXT["tiny"])
        _fin(ev, 13.4, z_ct=5.0)
        ev.hdims([0, hf, ev.h(BX["ur"][0]), ev.h(BX["ur"][1]), W])
        mh_dim(ev, ev.h(BX["ur"][1]) + 0.95, 17 * IN, "1'-5\" MAX")
    ev.vdims()
    return ev


def elev_girls(sh, ox, oy, side, num):
    G = GIRLS
    ev = Elev(sh, ox, oy, G, side, CLG_TOILET)
    ev.frame()
    W = ev.W
    if side == "N":
        d = M.OPENING_BY_ID["111"]
        h0, h1 = ev.h(d.lo), ev.h(d.hi)
        e_door(ev, h0, h1, hinge="r", face="pull")
        ev.tile()
        e_lav_side(ev, W, -1)
        e_profile_box(ev, W, -1, 1 * IN, ft(3, 4), ft(6, 4))
        door_tag(ev.v, ((h0 + h1) / 2, 7.85), "111")
        _fin(ev, 2.6)
        ev.hdims([0, h0, h1, W])
    elif side == "E":
        ev.hole(ev.h(28.2) - 0.75, 0.45, ev.h(28.2) + 0.75, 5.05)
        ev.tile()
        for y in GX["lav"]:
            e_lav_front(ev, ev.h(y))
        _draw_wall_acc(ev, "111", "E")
        fix_tag(ev.v, (ev.h(GX["lav"][1]), 1.15), "LAV-1", leader_to=(ev.h(GX["lav"][1]), 1.62))
        _fin(ev, 12.0)
        ev.hdims([0, ev.h(28.2), ev.h(GX["lav"][1]), ev.h(GX["lav"][0]), W])
        mh_dim(ev, ev.h(GX["lav"][0]) + 1.15, 34 * IN, "2'-10\" MAX")
        mh_dim(ev, ev.h(GX["lav"][1]) - 1.15, ft(3, 4), "3'-4\" MAX", side=-1)
    elif side == "S":
        ev.tile()
        hf = ev.h(GX["front"])
        e_pil_sec(ev, hf)
        _draw_wall_acc(ev, "111", "S")
        e_wc_side(ev, W, -1)
        e_gb_profile(ev, W, -1)
        fix_tag(ev.v, (W - 1.6, 1.85), "WC-1", leader_to=(W - 1.2, 1.2))
        btext(ev.v, (hf, 7.55), "STALL FRONT\n(SECTION)", size=TXT["tiny"])
        _fin(ev, 2.6)
        ev.hdims([0, hf, ev.h(G["W"] + 4.5), ev.h(G["W"] + 1.0), W])
        ev.hdims([ev.h(G["W"] + ft(3, 4)), W], tier=2)
        mh_dim(ev, ev.h(G["W"] + 4.5) - 0.35, GB_Z, None)
    elif side == "W":
        ev.tile()
        for i, y in enumerate(GX["wc"]):
            e_wc_front(ev, ev.h(y), acc=(i == 0), valve=1)
        _draw_wall_acc(ev, "111", "W")
        for yp in GX["parts"]:
            e_panel_sec(ev, ev.h(yp))
        for a in ACCESSORIES:
            if a["room"] == "111" and a["wall"].startswith("GP"):
                ax, k, sgn = _part_surface(a["wall"])
                hk = ev.h(k)
                if a["tag"] == 4:
                    e_profile_box(ev, hk, sgn, 5 * IN, 13 * IN, 25 * IN)
                    acc_tag(ev.v, (hk + sgn * 0.62, 0.62), 4, leader_to=(hk + sgn * 0.25, 1.2))
                else:
                    e_profile_box(ev, hk, sgn, 4 * IN, 24 * IN, 36 * IN)
                    acc_tag(ev.v, (hk + sgn * 0.6, 3.55), 5, leader_to=(hk + sgn * 0.2, 2.9))
        e_gb_profile(ev, 0, 1)
        e_profile_box(ev, 0, 1, 5 * IN, 13 * IN, 25 * IN)
        ev.v.rect(0, ft(3, 4), 3 * IN, ft(1, 6), lw="fine", fill="g30")
        fix_tag(ev.v, (ev.h(GX["wc"][0]), 2.05), "WC-1")
        for y in GX["wc"][1:]:
            fix_tag(ev.v, (ev.h(y), 2.05), "WC-2")
        _fin(ev, 14.4)
        ev.hdims([0] + [ev.h(t) for t in (GX["wc"][0], GX["parts"][0], GX["wc"][1],
                                          GX["parts"][1], GX["wc"][2], GX["parts"][2])] + [W])
        ev.hdims([0, ev.h(GX["wc"][0] - 1.0), ev.h(GX["wc"][0] + 2.0)], tier=2)
    ev.vdims()
    return ev


def elev_staff(sh, ox, oy, side, num):
    S = STAFF
    ev = Elev(sh, ox, oy, S, side, CLG_TOILET,
              wall_t={"N": (CMUh * 2, P4h * 2), "E": (P3h * 2, M.EW_OUT + M.EW_IN),
                      "S": (P4h * 2, CMUh * 2), "W": (M.EW_OUT + M.EW_IN, P3h * 2)}[side])
    ev.frame()
    W = ev.W
    if side == "N":
        d = M.OPENING_BY_ID["107"]
        h0, h1 = ev.h(d.lo), ev.h(d.hi)
        e_door(ev, h0, h1, hinge="r", face="push")
        ev.v.rect(h0 + 0.5, 4.0 - 0.06, 0.12, 0.12, lw="fine", fill="g40")
        ev.tile()
        e_lav_side(ev, W, -1)
        e_profile_box(ev, W, -1, 1 * IN, ft(3, 4), ft(6, 4))
        e_wc_side(ev, 0, 1)
        e_gb_profile(ev, 0, 1)
        door_tag(ev.v, ((h0 + h1) / 2, 7.85), "107")
        note(ev.v, (h0 + 0.56, 4.0), (h0 - 0.2, 5.35), "COAT HOOK\n(HW-3) 48\"", side="l",
             size=TXT["tiny"])
        _fin(ev, 1.2, z_ct=6.4)
        ev.hdims([0, h0, h1, W])
    elif side == "E":
        ev.hole(ev.h(7.2) - 0.75, 0.45, ev.h(7.2) + 0.75, 5.05)
        ev.tile()
        e_lav_front(ev, ev.h(SX["lav"]))
        _draw_wall_acc(ev, "107", "E")
        e_gb_profile(ev, W, -1)
        e_profile_box(ev, W, -1, 5 * IN, 13 * IN, 25 * IN)
        fix_tag(ev.v, (ev.h(SX["lav"]), 1.15), "LAV-1", leader_to=(ev.h(SX["lav"]), 1.62))
        _fin(ev, 5.9, z_ct=6.45)
        ev.hdims([0, ev.h(7.2), ev.h(SX["lav"]), W])
        mh_dim(ev, ev.h(SX["lav"]) - 1.0, 34 * IN, "2'-10\" MAX", side=-1)
    elif side == "S":
        ev.tile()
        _draw_wall_acc(ev, "107", "S", tag_dz={5: (-0.1, 0.0)})
        e_wc_side(ev, W, -1)
        e_gb_profile(ev, W, -1)
        e_lav_side(ev, 0, 1)
        fix_tag(ev.v, (W - 1.3, 2.0), "WC-1", leader_to=(W - 1.0, 1.25))
        _fin(ev, 1.0, z_ct=6.45)
        ev.hdims([0, ev.h(S["W"] + ft(5, 3)), ev.h(S["W"] + 4.5), ev.h(S["W"] + 1.0), W])
        ev.hdims([ev.h(S["W"] + ft(3, 4)), W], tier=2)
    elif side == "W":
        ev.tile()
        e_wc_front(ev, ev.h(SX["wc"]), acc=True, valve=1)
        _draw_wall_acc(ev, "107", "W")
        e_gb_profile(ev, 0, 1)
        e_profile_box(ev, 0, 1, 5 * IN, 13 * IN, 25 * IN)
        ev.v.rect(0, ft(3, 4), 3 * IN, ft(1, 6), lw="fine", fill="g30")
        fix_tag(ev.v, (ev.h(SX["wc"]) + 0.2, 2.0), "WC-1")
        _fin(ev, 5.6)
        ev.hdims([0, ev.h(SX["wc"]), W])
        ev.hdims([0, ev.h(SX["wc"] - 1.0), ev.h(SX["wc"] + 2.0)], tier=2)
    ev.vdims()
    return ev


def elev_cust(sh, ox, oy):
    C = CUST
    ev = Elev(sh, ox, oy, C, "W", 9.0, clg_kind="ACT")
    ev.frame()
    W = ev.W
    v = ev.v
    ev.rb_base()
    # mop service basin + SS wall guards + service faucet
    v.rect(0, 0, 2.0, 10 * IN, lw="thin", fill="white")
    v.line((0.12, 10 * IN - 0.1), (1.88, 10 * IN - 0.1), lw="hair")
    v.rect(0, 10 * IN, 2.0, 4.0 - 10 * IN, lw="fine", fill="g05")
    for z in (2.0, 3.0):
        v.line((0, z), (2.0, z), lw="hair", color="screen")
    v.rect(0.65, 3.05, 0.7, 0.12, lw="fine", fill="white")
    v.line((1.0, 3.05), (1.0, 2.55), lw="fine")
    v.rect(0.92, 3.17, 0.16, 0.3, lw="hair", fill="white")
    _draw_wall_acc(ev, "110", "W")
    fix_tag(v, (1.0, 1.4), "MS-1")
    note(v, (1.7, 3.6), (2.5, 4.3) if False else (2.3, 6.4), "SS WALL GUARDS 2 SIDES\nTO 48\" AFF (DIV. 22)",
         side="r", size=TXT["tiny"])
    btext(v, (7.6, 7.6), "PNT-2", size=TXT["small"], font=FONT_B)
    btext(v, (7.6, 0.55), "RB-1", size=TXT["tiny"], font=FONT_B)
    btext(v, (7.6, 8.58), "ACT-2 CLG. @ 9'-0\" AFF", size=TXT["tiny"])
    ev.hdims([0, 2.0, ev.h(24.6 - 1.5), ev.h(24.6 + 1.5), W])
    mh_dim(ev, ev.h(24.6 + 1.5) + 0.35, 5.0, "5'-0\"")
    pts = [(W + ev.wall_t[1], z) for z in (0, 4 * IN, ev.clg)]
    v.dim_chain(pts, -0.75, size=TXT["small"])
    return ev


def front_elev(sh, ox, oy, room):
    """stall front (partition) elevation; Boys looks south, Girls looks west."""
    if room == "109":
        F, side = BOYS, "S"
    else:
        F, side = GIRLS, "W"
    ev = Elev(sh, ox, oy, F, side, CLG_TOILET)
    ev.frame()
    ev.tile()
    v = ev.v
    front = [f for f in STALL_FRONTS if f[0] == room][0]
    segs = front[3]
    hs = []
    hmax = 0
    for sgm in segs:
        a, b = sorted((ev.h(sgm[1]), ev.h(sgm[2])))
        hs += [a, b]
        hmax = max(hmax, b)
        kind = sgm[0]
        if kind == "pil":
            v.rect(a, 0.25, b - a, PIL_TOP - 0.25, lw="thin", fill="g10")
            v.rect(a - 0.02, 0, b - a + 0.04, 0.25, lw="fine", fill="g30")
        elif kind == "panel":
            v.rect(a, PART_Z[0], b - a, PART_Z[1] - PART_Z[0], lw="thin", fill="g05")
            v.rect(a + 0.02, PART_Z[0] + 0.3, 0.06, PART_Z[1] - PART_Z[0] - 0.6, lw="hair",
                   fill="g40")
        else:
            hinge, acc = sgm[3], sgm[5]
            v.rect(a, PART_Z[0], b - a, PART_Z[1] - PART_Z[0], lw="thin", fill="white")
            hx = ev.h(sgm[1] if hinge == "a" else sgm[2])
            lx = a + 0.22 if abs(hx - b) < 1e-6 else b - 0.22
            v.rect(hx - 0.04 if hx > a + 0.1 else hx, PART_Z[0] + 0.05, 0.04,
                   PART_Z[1] - PART_Z[0] - 0.1, lw="hair", fill="g40")
            v.rect(lx - 0.1, 3.35, 0.2, 0.1, lw="hair", fill="g40")
            if acc:
                v.rect(lx - 0.03, 2.65, 0.06, 0.55, lw="fine", fill="g40")
                btext(v, ((a + b) / 2, 4.6), "36\" ACC.\nOUT-SWING", size=TXT["tiny"])
            else:
                btext(v, ((a + b) / 2, 4.6), "24\"\nIN-SWING", size=TXT["tiny"])
    # headrail
    v.rect(0, PIL_TOP - 0.02, hmax, 0.12, lw="fine", fill="g40")
    v.rect(0, PART_Z[0] + 0.25, 0.06, PART_Z[1] - PART_Z[0] - 0.5, lw="hair", fill="g40")
    note(v, (hmax * 0.55, PIL_TOP + 0.1), (hmax * 0.55 + 0.6, 8.1), "ANTI-GRIP HEADRAIL @ 82\" AFF",
         side="r", size=TXT["tiny"])
    btext(v, (hmax + (ev.W - hmax) * 0.3, 6.3), "CT-1", size=TXT["small"], font=FONT_B)
    ev.hdims([0] + hs + [ev.W])
    x = hmax + (ev.W - hmax) * 0.62
    v.dim_chain([(x, 0), (x, PART_Z[0]), (x, PART_Z[1]), (x, PIL_TOP)], 0, size=TXT["small"])
    ev.vdims()
    return ev


# ---- typical mounting diagrams (1/2") -----------------------------------------------------
def typ_wc_side(sh, ox, oy, s=1 / 2):
    """side wall of an accessible WC compartment (rear wall at left)."""
    v = sh.view(ox, oy, s)
    W, H = 5.5, 5.4
    v.line((-0.3, 0), (W, 0), lw="heavy")
    v.rect(-0.35, -0.3, 0.35, H + 0.3, lw="heavy", fill="white", hatch="ansi31",
           hatch_kw=dict(spacing=0.045))
    break_line(v, (W, -0.2), (W, H), zig=0.1)
    ev = Elev.__new__(Elev)
    ev.v = v
    e_wc_side(ev, 0, 1)
    e_gb_h(ev, 1.0, 4.5)
    e_gb_v(ev, ft(3, 4))
    e_tpd(ev, 3.0)
    sm = TXT["tiny"] * 1.15
    v.dim((0, GB_Z + 0.2), (1.0, GB_Z + 0.2), 0, text="12\" MAX", size=sm)
    v.dim((1.0, GB_Z + 0.2), (4.5, GB_Z + 0.2), 0, text="42\" MIN", size=sm)
    v.dim((0, 5.15), (4.5, 5.15), 0, text="54\" MIN", size=sm)
    v.dim((0, 4.9) if False else (0, 0.0 - 0.4), (ft(3, 4), -0.4), 0, text="39\"-41\" (40\")",
          size=sm)
    v.dim((WC_D, -0.95), (3.0, -0.95), 0, text="7\"-9\"", size=sm)
    v.dim((0, -0.95), (WC_D, -0.95), 0, text="WC", size=sm)
    v.dim((5.0, 0), (5.0, GB_Z), 0, text="33\"-36\"", size=sm)
    v.dim((ft(3, 4) + 0.35, 0), (ft(3, 4) + 0.35, ft(3, 4)), 0, text="39\"-41\"", size=sm,
          flip_text=True)
    v.dim((2.2, 0), (2.2, 19 * IN), 0, text="19\"", size=sm)
    v.dim((0.9, 0), (0.9, 18 * IN), 0, text="17\"-19\"", size=sm, flip_text=True)
    acc_tag(v, (2.7, GB_Z + 0.55), 1)
    acc_tag(v, (ft(3, 4) + 0.35, 4.6), 3)
    acc_tag(v, (3.75, 1.0), 4)
    return v


def typ_wc_rear(sh, ox, oy, s=1 / 2):
    v = sh.view(ox, oy, s)
    W, H = 4.6, 5.4
    v.line((-0.3, 0), (W, 0), lw="heavy")
    v.rect(-0.35, -0.3, 0.35, H + 0.3, lw="heavy", fill="white", hatch="ansi31",
           hatch_kw=dict(spacing=0.045))
    break_line(v, (W, -0.2), (W, H), zig=0.1)
    ev = Elev.__new__(Elev)
    ev.v = v
    e_wc_front(ev, 1.5, acc=True, valve=1)
    e_gb_h(ev, 0.5, 3.5)
    sm = TXT["tiny"] * 1.15
    v.dim((0, -0.45), (1.5, -0.45), 0, text="16\"-18\"", size=sm)
    v.dim((0.5, GB_Z + 0.25), (1.5, GB_Z + 0.25), 0, text="12\" MIN", size=sm)
    v.dim((1.5, GB_Z + 0.25), (3.5, GB_Z + 0.25), 0, text="24\" MIN", size=sm)
    v.dim((0.5, GB_Z + 0.95), (3.5, GB_Z + 0.95), 0, text="36\" MIN", size=sm)
    v.dim((4.1, 0), (4.1, GB_Z), 0, text="33\"-36\"", size=sm)
    v.line((1.5, -0.3), (1.5, 2.9), lw="hair", dash="center")
    acc_tag(v, (2.6, GB_Z + 1.6), 2, leader_to=(2.6, GB_Z))
    return v


def typ_lav(sh, ox, oy, s=1 / 2):
    v = sh.view(ox, oy, s)
    W, H = 3.2, 7.0
    v.line((-0.3, 0), (W, 0), lw="heavy")
    break_line(v, (-0.3, H), (W, H), zig=0.1)
    ev = Elev.__new__(Elev)
    ev.v = v
    e_lav_front(ev, 1.2)
    e_mirror(ev, 1.2)
    e_soap(ev, 2.45)
    sm = TXT["tiny"] * 1.15
    v.dim((-0.15, 0), (-0.15, 34 * IN), 0, text="34\" MAX", size=sm)
    v.dim((-0.75, 0), (-0.75, ft(3, 4)), 0, text="40\" MAX", size=sm)
    v.dim((0.25, 0), (0.25, 29 * IN), 0, text="29\" MIN", size=sm, flip_text=True)
    v.dim((2.85, 0), (2.85, 42 * IN), 0, text="42\"", size=sm, flip_text=True)
    acc_tag(v, (1.2, 5.3), 7)
    acc_tag(v, (2.45, 4.45), 6, leader_to=(2.45, 47 * IN))
    btext(v, (1.2, 0.55), "27\" MIN. KNEE CLR.\nAT 8\" DEPTH", size=TXT["tiny"])
    return v


def typ_urinal(sh, ox, oy, s=1 / 2):
    v = sh.view(ox, oy, s)
    W, H = 3.0, 5.2
    v.line((-0.3, 0), (W, 0), lw="heavy")
    break_line(v, (-0.3, H), (W, H), zig=0.1)
    ev = Elev.__new__(Elev)
    ev.v = v
    e_urinal_front(ev, 1.0)
    v.rect(2.2, SCREEN_Z[0], 0.12, SCREEN_Z[1] - SCREEN_Z[0], lw="fine", fill="g50")
    sm = TXT["tiny"] * 1.15
    v.dim((-0.2, 0), (-0.2, 17 * IN), 0, text="17\" MAX", size=sm)
    v.dim((2.65, 0), (2.65, SCREEN_Z[0]), 0, text="12\"", size=sm, flip_text=True)
    v.dim((2.65, SCREEN_Z[0]), (2.65, SCREEN_Z[1]), 0, text="42\"", size=sm, flip_text=True)
    btext(v, (2.26, 4.85), "US-1", size=TXT["tiny"], font=FONT_B)
    btext(v, (1.0, 4.6), "UR-1", size=TXT["tiny"], font=FONT_B)
    return v


def wainscot_detail(sh, ox, oy, s=1.5):
    """vertical section: PT-1 / PT-1B base and CT-1 bullnose cap at CMU wall (with break)."""
    v = sh.view(ox, oy, s)
    t_cmu = M.CMU_T
    t_tile = 5 / 16 * IN
    t_set = 3 / 16 * IN
    xw = 0.0                    # face of CMU
    # lower part z -0.5 .. 0.9  ; upper part z 1.1 .. 2.1 represents 6'-6" .. 7'-6"
    lo0, lo1, up0, up1 = -0.5, 0.95, 1.25, 2.35
    zoff = 6.5 - up0             # model z = drawing z + zoff in the upper part

    def cmu(z0, z1):
        v.rect(-t_cmu, z0, t_cmu, z1 - z0, lw="heavy", fill="white", hatch="ansi31",
               hatch_kw=dict(spacing=0.06))
    cmu(0.0, lo1)
    cmu(up0, up1)
    # slab + floor tile
    v.rect(-t_cmu, -0.5, 1.6 + t_cmu, 0.5 - 0.06, lw="heavy", fill="white", hatch="concrete",
           hatch_kw=dict(scale=1.2))
    v.rect(xw, -0.06, 1.6, 0.025, lw="fine", fill="g30")
    v.rect(xw, -0.035, 1.6, 0.035, lw="thin", fill="g60")
    # cove base PT-1B (6") + CT-1 above
    v.polygon([(xw, 0), (xw + t_set + t_tile, 0), (xw + t_set + t_tile, 0.0)], lw="fine")
    v.rect(xw, 0, t_set, lo1, lw="hair", fill="g20")
    v.polygon([(xw + t_set, 0.0), (xw + t_set + 0.12, 0.0), (xw + t_set + 0.12, 0.012),
               (xw + t_set + t_tile + 0.01, 0.1), (xw + t_set + t_tile, 0.5), (xw + t_set, 0.5)],
              lw="thin", fill="g60")
    v.rect(xw + t_set, 0.5, t_tile, lo1 - 0.5, lw="thin", fill="g40")
    for z in (0.5 + 4 * IN * k for k in range(1, 3)):
        v.line((xw + t_set, z), (xw + t_set + t_tile, z), lw="hair", color="white")
    # upper: field tile to 7'-0" with bullnose cap course, PNT-1 above
    v.rect(xw, up0, t_set, 7.0 - zoff - up0, lw="hair", fill="g20")
    v.rect(xw + t_set, up0, t_tile, 7.0 - zoff - up0 - 4 * IN, lw="thin", fill="g40")
    zc0 = 7.0 - zoff - 4 * IN
    v.polygon([(xw + t_set, zc0), (xw + t_set + t_tile, zc0), (xw + t_set + t_tile, 7.0 - zoff - 0.03),
               (xw + t_set + 0.01, 7.0 - zoff), (xw + t_set, 7.0 - zoff)], lw="thin", fill="g60")
    v.line((xw, 7.0 - zoff), (xw, up1), lw="thin")
    v.line((xw + 0.01, 7.0 - zoff), (xw + 0.01, up1), lw="hair")
    for zz in (lo1, up0):
        break_line(v, (-t_cmu - 0.15, zz), (0.3, zz), zig=0.06)
    sm = TXT["tiny"] * 1.15
    note(v, (xw + t_set + 0.02, 0.25), (0.62, 0.42), "PT-1B COVE BASE 6\"\n(MATCH PT-1)",
         side="r", size=sm)
    note(v, (xw + 0.4, -0.03), (0.62, -0.68), "PT-1 12\"x24\" PORCELAIN TILE,\nTHINSET, EPOXY GROUT",
         side="r", size=sm)
    note(v, (xw + t_set + t_tile, 0.8), (0.62, 0.85),
         "CT-1 4\"x12\" WALL TILE, RUNNING\nBOND, THINSET ON CMU", side="r", size=sm)
    note(v, (xw + t_set + t_tile, 7.0 - zoff - 0.15), (0.62, 1.55), "CT-1 BULLNOSE CAP\nCOURSE @ 7'-0\" AFF",
         side="r", size=sm)
    note(v, (xw - 0.02, up1 - 0.25), (0.62, 2.15), "PNT-1 ABOVE", side="r", size=sm)
    note(v, (-t_cmu * 0.5, 0.75), (0.62, 1.15) if False else (-t_cmu * 0.5, 0.75), "", side="r",
         size=sm) if False else None
    btext(v, (-t_cmu * 0.5, 0.25), "8\" CMU", size=sm)
    v.dim((-t_cmu - 0.45, 0), (-t_cmu - 0.45, 0.5), 0, text="6\"", size=sm)
    v.text((-t_cmu - 0.62, 7.0 - zoff), "7'-0\" AFF", size=sm, anchor="r", valign="mid")
    v.line((-t_cmu - 0.58, 7.0 - zoff), (-t_cmu, 7.0 - zoff), lw="hair", dash="center")
    return v


def _det_label(p, x, y, text):
    p.text((x, y), text, size=TXT["small"], font=FONT_B, valign="top", underline=True)


def partition_details(sh, x, top, cw=3.75, s=3.0):
    """partition details at 3" = 1'-0" in three cells starting at paper x; `top` = label line."""
    p = Paper(sh.c)
    sm = TXT["tiny"] * 1.15
    T = top - 0.35
    # (A) pilaster shoe + floor anchor (section)
    _det_label(p, x, top, "A  PILASTER SHOE (SECTION)")
    v = sh.view(x + 0.9, T - 0.72 * s, s)
    v.rect(-0.25, -0.28, 0.6, 0.25, lw="heavy", fill="white", hatch="concrete",
           hatch_kw=dict(scale=1.0))
    v.rect(-0.25, -0.03, 0.6, 0.03, lw="thin", fill="g60")
    v.rect(0, 0.0, PIL_T, 0.72, lw="thin", fill="g20")
    v.rect(-0.02, 0, PIL_T + 0.04, 0.25, lw="fine", fill="g50")
    v.rect(0.01, 0.0, PIL_T - 0.02, 0.05, lw="hair", fill="black")
    v.rect(0.04, -0.2, 0.025, 0.25, lw="hair", fill="black")
    break_line(v, (-0.12, 0.72), (0.22, 0.72), zig=0.05)
    note(v, (PIL_T + 0.02, 0.18), (0.2, 0.42), "3\" SS PILASTER SHOE", side="r", size=sm)
    note(v, (PIL_T - 0.01, 0.03), (0.2, 0.12), "LEVELING BAR", side="r", size=sm)
    note(v, (0.06, -0.15), (0.2, -0.14), "3/8\" EXP. ANCHOR (2)", side="r", size=sm)
    # (B) panel to wall bracket (plan)
    x2 = x + cw
    _det_label(p, x2, top, "B  WALL BRACKET (PLAN)")
    v2 = sh.view(x2 + 0.55, T - 0.36 * s, s)
    v2.rect(-0.12, 0, 0.52, 0.32, lw="heavy", fill="white", hatch="ansi31",
            hatch_kw=dict(spacing=0.06))
    break_line(v2, (-0.12, 0.32), (0.4, 0.32), zig=0.04)
    v2.rect(-0.12, -0.04, 0.52, 0.04, lw="fine", fill="g40")
    v2.rect(0.08, -0.6, PANEL_T, 0.6 - 0.08, lw="thin", fill="g20")
    v2.polyline([(0.06, -0.42), (0.06, -0.06), (0.08 + PANEL_T + 0.02, -0.06),
                 (0.08 + PANEL_T + 0.02, -0.42)], lw="fine")
    v2.line((0.0, -0.26), (0.23, -0.26), lw="hair")
    v2.line((0.12, -0.06), (0.12, 0.18), lw="hair")
    break_line(v2, (-0.02, -0.6), (0.26, -0.6), zig=0.04)
    note(v2, (0.08 + PANEL_T + 0.02, -0.34), (0.32, -0.38), "SS CONT. U-BRACKET,\nTHRU-BOLTED",
         side="r", size=sm)
    note(v2, (0.3, 0.14), (0.48, 0.2), "CMU, GROUTED", side="r", size=sm)
    note(v2, (0.3, -0.02), (0.48, -0.05), "CT-1", side="r", size=sm)
    note(v2, (0.125, -0.52), (0.32, -0.56), "1\" HDPE PANEL", side="r", size=sm)
    # (C) headrail at pilaster (section)
    x3 = x + 2 * cw
    _det_label(p, x3, top, "C  HEADRAIL (SECTION)")
    v3 = sh.view(x3 + 0.75, T - 0.25 * s, s)
    v3.rect(0, -0.62, PIL_T, 0.62, lw="thin", fill="g20")
    v3.polygon([(-0.06, 0.0), (PIL_T + 0.06, 0.0), (PIL_T + 0.06, 0.1), (PIL_T / 2, 0.15),
                (-0.06, 0.1)], lw="thin", fill="g40")
    v3.rect(-0.04, -0.12, PIL_T + 0.08, 0.12, lw="hair", fill="g60")
    break_line(v3, (-0.12, -0.62), (0.22, -0.62), zig=0.04)
    note(v3, (PIL_T + 0.06, 0.06), (0.3, 0.1), "ANTI-GRIP ALUM. HEADRAIL,\nTOP @ 82\" AFF", side="r",
         size=sm)
    note(v3, (PIL_T + 0.04, -0.06), (0.3, -0.2), "SS HEADRAIL BRACKET", side="r", size=sm)
    note(v3, (PIL_T, -0.42), (0.3, -0.45), "1 1/4\" HDPE PILASTER", side="r", size=sm)


def tile_terminations(sh, x, top, cw=4.4, s=3.0):
    """plan details: A CT-1 at HM frame jamb, B outside corner, C at recessed TA-8."""
    p = Paper(sh.c)
    sm = TXT["tiny"] * 1.15
    t = M.CMU_T
    tt = 0.5 * IN                     # tile + setting bed
    T = top - 0.35
    # (A) jamb
    _det_label(p, x, top, "A  AT HM FRAME JAMB")
    v = sh.view(x + 0.45, T - 0.55 - t * s, s)
    v.rect(0, 0, 0.5, t, lw="heavy", fill="white", hatch="ansi31", hatch_kw=dict(spacing=0.06))
    break_line(v, (0.5, -0.1), (0.5, t + 0.1), zig=0.04)
    v.rect(0.02, t, 0.48, tt, lw="fine", fill="g40")
    v.rect(0.02, -tt, 0.48, tt, lw="fine", fill="g40")
    fr = [(0.0, -2 * IN), (-2 * IN, -2 * IN), (-2 * IN, t + 2 * IN), (0.0, t + 2 * IN),
          (0.0, t + 1.6 * IN), (-1.6 * IN, t + 1.6 * IN), (-1.6 * IN, -1.6 * IN), (0.0, -1.6 * IN)]
    v.polygon(fr, lw="thin", fill="g60")
    v.circle((0.01, t + tt / 2), 0.012, lw="hair", fill="black")
    note(v, (-1.0 * IN, t + 2 * IN), (0.15, t + 0.3), "HM FRAME F1, GROUT-FILLED", side="r", size=sm)
    note(v, (0.25, t + tt), (0.62, t + 0.12), "CT-1 BUTTS FRAME;\nSILICONE SEALANT", side="r",
         size=sm)
    # (B) outside corner
    x2 = x + cw
    _det_label(p, x2, top, "B  OUTSIDE CORNER")
    v2 = sh.view(x2 + 0.55, T - 0.55 * s, s)
    v2.rect(0, 0, t, 0.5, lw="heavy", fill="white", hatch="ansi31", hatch_kw=dict(spacing=0.06))
    break_line(v2, (-0.1, 0.5), (t + 0.1, 0.5), zig=0.04)
    v2.polygon([(-tt, 0.5), (-tt, -tt), (t + tt, -tt), (t + tt, 0.5), (t, 0.5), (t, 0),
                (0, 0), (0, 0.5)], lw="fine", fill="g40")
    v2.polyline([(-tt - 0.012, -tt + 0.03), (-tt - 0.012, -tt - 0.012), (-tt + 0.03, -tt - 0.012)],
                lw="thin")
    note(v2, (t + tt, -tt), (t + 0.3, -0.15), "SS TILE EDGE TRIM\n(OR BULLNOSE)", side="r", size=sm)
    note(v2, (t + tt, 0.3), (t + 0.3, 0.35), "CT-1", side="r", size=sm)
    # (C) recessed TA-8
    x3 = x + 2 * cw
    _det_label(p, x3, top, "C  AT RECESSED TA-8")
    sc = s / 2
    v3 = sh.view(x3 + 0.3, T - 1.0 - t * sc, sc)
    v3.rect(0, 0, 0.3, t, lw="heavy", fill="white", hatch="ansi31", hatch_kw=dict(spacing=0.06))
    v3.rect(0.3 + 1.333, 0, 0.3, t, lw="heavy", fill="white", hatch="ansi31",
            hatch_kw=dict(spacing=0.06))
    v3.rect(0.3, 0, 1.333, t - 4 * IN, lw="heavy", fill="white", hatch="ansi31",
            hatch_kw=dict(spacing=0.06))
    v3.rect(0.3 + 0.02, t - 4 * IN, 1.333 - 0.04, 4 * IN, lw="thin", fill="g10")
    v3.rect(0.3 - 0.06, t + tt, 1.333 + 0.12, 0.03, lw="thin", fill="g60")
    v3.rect(0.0, t, 0.3 - 0.06, tt, lw="fine", fill="g40")
    v3.rect(0.3 + 1.333 + 0.06, t, 0.24, tt, lw="fine", fill="g40")
    note(v3, (1.0, t + tt + 0.03), (1.3, t + 0.45), "TA-8 FLANGE LAPS CT-1", side="r", size=sm)
    note(v3, (1.2, t - 0.25), (1.75, -0.35), "4\" RECESS; GC PROVIDES\nCMU OPENING + LINTEL",
         side="r", size=sm)
    p.text((x3 + 2.9, top), "(1 1/2\" = 1'-0\")", size=TXT["tiny"], valign="top")


A602_NOTES = [
    "ELEVATIONS SHOW LEVEL 1 ROOMS; LEVEL 2 ROOMS 207 / 209 / 211 / 210 ARE IDENTICAL. SEE A-401 FOR PLANS, TAGS AND THE TOILET ACCESSORY SCHEDULE.",
    "CT-1 WALL TILE: FROM TOP OF PT-1B BASE (6\" AFF) TO 7'-0\" AFF (6'-6\" FIELD INCL. BULLNOSE CAP COURSE) ON ALL WALLS OF 107, 109, 111 (+ L2). "
    "TILE STOPS AT HM FRAMES AND RECESSED ACCESSORIES; RETURN TILE INTO NO OPENINGS. PNT-1 ABOVE TO CEILING.",
    "TAKEOFF BASIS: CT-1 SF = ROOM CLEAR PERIMETER x 6'-6\" LESS DOOR MO (3'-4\" x 6'-6\") AND TA-8 RECESSES (1'-5\" x 4'-6\"); "
    "PT-1B LF = CLEAR PERIMETER LESS DOOR MO WIDTHS. CLEAR ROOM DIMENSIONS ARE ON A-401.",
    "PARTITIONS (TP-1) AND ACCESSORIES ARE INSTALLED OVER FINISHED TILE: USE SS FASTENERS INTO GROUTED CMU OR FRT BLOCKING; SEAL PENETRATIONS.",
    "MOUNTING HEIGHTS PER ICC A117.1-2017 / 2010 ADA STANDARDS (ADULT DIMENSIONS); SEE TYPICAL DIAGRAMS 16 AND 17.",
    "PLUMBING FIXTURES (WC, UR, LAV, MS) BY DIV. 22 - SHOWN FOR COORDINATION. PROVIDE CARRIER BLOCKING / GROUTED CELLS AS REQUIRED.",
    "CUSTODIAL 110 / 210: PNT-2 WATERBORNE EPOXY WALLS, RB-1 BASE, SC-1 FLOOR, ACT-2 CEILING; NO WALL TILE.",
]


def a602(sh):
    X0, X1, Y0, Y1 = sh.x0, sh.x1, sh.y0, sh.y1
    rowh = 5.25
    y_rows = [Y1 - 0.45 - 9.9 * Q - i * rowh for i in range(3)]
    G = 1.02
    sides = {"N": "NORTH", "E": "EAST", "S": "SOUTH", "W": "WEST"}
    for r, (fn, room, nm, base_num, fr) in enumerate(((elev_boys, "109", "BOYS 109/209", 1, 14),
                                                     (elev_girls, "111", "GIRLS 111/211", 5, 15))):
        x = X0 + 0.45
        oy = y_rows[r]
        for k, side in enumerate(("N", "E", "S", "W")):
            ev = fn(sh, x, oy, side, base_num + k)
            _title(sh, ev, base_num + k, f"{nm} - {sides[side]}")
            x += ev.W * Q + 0.16 + G
        ev = front_elev(sh, x, oy, room)
        _title(sh, ev, fr, f"{nm.split()[0]} - STALL FRONTS")
    x = X0 + 0.45
    oy = y_rows[2]
    for k, side in enumerate(("N", "E", "S", "W")):
        ev = elev_staff(sh, x, oy, side, 9 + k)
        _title(sh, ev, 9 + k, "STAFF 107/207 - " + sides[side][0], w=ev.W * Q + 0.8)
        x += ev.W * Q + 0.16 + G + 0.12
    ev = elev_cust(sh, x, oy)
    _title(sh, ev, 13, "CUSTODIAL 110/210 - WEST")
    # row 3 right: tile terminations (plan details)
    tile_terminations(sh, X0 + 17.95, y_rows[2] + 2.75)
    sh.view_title(X0 + 17.95, y_rows[2] - 0.78 - 0.0, 20, "CT-1 TERMINATIONS (PLAN)", 3.0,
                  width=12.6)
    # bottom band
    by = Y0 + 1.6
    s1 = 3 / 4
    typ_wc_side(sh, X0 + 0.95, by, s1)
    typ_wc_rear(sh, X0 + 5.75, by, s1)
    sh.view_title(X0 + 0.45, by - 1.05, 16, "TYP. ACCESSIBLE WC - SIDE / REAR WALL", s1,
                  width=8.0)
    typ_lav(sh, X0 + 10.75, by, s1)
    typ_urinal(sh, X0 + 14.0, by, s1)
    sh.view_title(X0 + 9.75, by - 1.05, 17, "TYP. LAV / URINAL MOUNTING", s1, width=6.5)
    wainscot_detail(sh, X0 + 18.45, by + 0.9)
    sh.view_title(X0 + 17.2, by - 1.05, 18, "CT-1 WAINSCOT + BASE", 1.5, width=3.9)
    partition_details(sh, X0 + 22.25, by + 4.85, cw=3.0)
    sh.view_title(X0 + 21.85, by - 1.05, 19, "TOILET PARTITION DETAILS", 3.0, width=8.8)
    # right column: notes + finish legend
    rx = X0 + 24.25
    cw = X1 - rx - 0.08
    h = notes_block(sh, rx, Y1 - 0.15, "TOILET ROOM ELEVATION NOTES", A602_NOTES, cw)
    yy = Y1 - 0.15 - h - 0.2
    rows = [[k, M.FINISHES[k]] for k in ("PT-1", "PT-1B", "CT-1", "PNT-1", "PNT-2", "GWB-1",
                                         "ACT-2", "RB-1", "SC-1")]
    table(sh, rx, yy, [("TAG", 0.65), ("FINISH (SEE A-801)", cw - 0.65)], rows, row_h=0.2,
          size=TXT["small"], wrap=True, title="FINISH LEGEND - TOILET / CUSTODIAL",
          align=["c", "l"])


# =========================================================================================
SHEETS = [
    ("A-401", "ENLARGED PLANS", a401),
    ("A-602", "INTERIOR ELEVATIONS -\nTOILET ROOMS", a602),
]
