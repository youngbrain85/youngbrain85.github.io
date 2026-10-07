"""
C-100 .. C-500  CIVIL SHEETS
    C-100 existing conditions & site demolition plan      1" = 30'
    C-200 site layout & paving plan                         1" = 30'
    C-300 grading & erosion control plan                    1" = 30' (+ 1" = 20' enlarged plan)
    C-400 site utility plan (+ storm / sanitary profiles)   1" = 30'
    C-500 civil details

One site model (the SITE_* data and helper functions below) in plan FEET with the same origin
as the building (grid 1 / grid D = (0, 0), x east, y north) feeds every C-sheet so they agree.
Civil elevations are NAVD88: arch 100'-0" = EL. 712.50 (model.CIVIL_DATUM).
"""
from __future__ import annotations

import math

import numpy as np
import shapely
from reportlab.lib.colors import Color, white
from reportlab.pdfbase.pdfmetrics import stringWidth
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

from . import model as M
from .cad import (FONT, FONT_B, FONT_I, PT, TXT, Paper, View, color, keynote_tag, notes_block,
                  scale_bar, table, wrap_lines)

SC = 1 / 30.0            # plan scale, paper inches per foot (1" = 30')
SC20 = 1 / 20.0
SM = TXT["small"]        # 5.6 pt plan labels
NT = TXT["note"]         # 6.75 pt notes
TY = TXT["tiny"]         # 4.5 pt minimum
EXC = Color(0.42, 0.42, 0.42)   # existing-feature label color (screened, still legible)
SCR = "screen"

FFE = M.CIVIL_DATUM                                   # 712.50
FG = round(M.civil(M.LEVELS["GRADE"]), 2)             # 711.83 finish grade at building
STOOP = round(FFE - 0.04, 2)                          # 712.46 top of stoop (1/2" below FFE)
DATUM_NOTE = "CIVIL DATUM: ARCH 100'-0\" = EL. 712.50 (NAVD88)"

# ========================================================================================
# 1. SITE MODEL  (plan feet)
# ========================================================================================
PL_W, PL_E, PL_S, PL_N = -420.0, 255.0, -150.0, 260.0
PROPERTY = box(PL_W, PL_S, PL_E, PL_N)

# Prairie Avenue (east-west, south frontage), 66' ROW
PR = dict(row_n=-150.0, row_s=-216.0, cl=-183.0, boc_n=-162.0, eop_n=-163.5, eop_s=-202.5,
          boc_s=-204.0, sw_n=(-156.0, -151.0), sw_s=(-215.0, -210.0))
# Maple Street (north-south, east frontage), 66' ROW
MP = dict(row_w=255.0, row_e=321.0, cl=288.0, boc_w=268.0, eop_w=269.5, eop_e=306.5,
          boc_e=308.0, sw_w=(256.0, 261.0), sw_e=(315.0, 320.0))
R_RET = 25.0             # curb return radius (back of curb) at the intersection
FAR = 900.0              # "infinite" extent for street lines (clipped by the view)

# ---- existing school (1 story, occupied, FFE 712.50): 38,600 SF with two open courtyards
EXB = box(-320, -60, -36, 120).difference(box(-288, -26, -212, 84)).difference(
    box(-182, -2, -142, 102))
EXB_COURTS = [box(-288, -26, -212, 84), box(-182, -2, -142, 102)]
EX_CANOPY = box(-200, -68, -170, -60)        # main entry canopy over the drop-off walk
EX_DOORS = {"MAIN ENTRY": (-185.0, -60.0), "E. CORRIDOR DOOR": (-36.0, 36.0)}

# ---- existing pavements
EX_LOT = box(-300, -135, -70, -80)            # parking lot
EX_BUS = box(-300, -80, -70, -68)             # bus drop-off lane (one way, eastbound)
EX_DRIVES = [-280.0, -95.0]                   # drive centerlines to Prairie Ave (24' wide)
DRIVE_W = 24.0


def _ex_paving():
    g = [EX_LOT, EX_BUS]
    for xc in EX_DRIVES:
        g.append(box(xc - DRIVE_W / 2, PR["eop_n"], xc + DRIVE_W / 2, -135))
    return unary_union(g)


EX_PAVE = _ex_paving()
# stalls: north row y -97..-80, aisle -119..-97, south row -135..-119; rows x -264..-111
STALL_W = 9.0
ROW_X0, ROW_X1 = -264.0, -111.0
ACC_STALLS = [(-201.0, -192.0, "VAN"), (-184.0, -175.0, "ACC")]   # north row; 8' aisle -192..-184


def _stall_lines():
    """returns (list of stall separator segments, n_stalls, n_accessible)"""
    segs = []
    n = 0
    # north row (accessible group near the main entry)
    xs = [ROW_X0]
    x = ROW_X0
    while x + STALL_W <= -201.0 + 1e-6:
        x += STALL_W
        xs.append(x)
    n += len(xs) - 1
    xs2 = [-192.0, -184.0, -175.0]
    n += 2
    x = -175.0
    rest = [x]
    while x + STALL_W <= ROW_X1 + 1e-6:
        x += STALL_W
        rest.append(x)
    n += len(rest) - 1
    for xx in xs + xs2 + rest:
        segs.append(((xx, -97.0), (xx, -80.0)))
    # south row
    x = ROW_X0
    segs.append(((x, -135.0), (x, -119.0)))
    while x + STALL_W <= ROW_X1 + 1e-6:
        x += STALL_W
        segs.append(((x, -135.0), (x, -119.0)))
        n += 1
    return segs, n, 2


STALL_SEGS, N_STALLS, N_ACC = _stall_lines()

# ---- existing walks
EX_WALK_A = box(-312, -68, -36, -60)          # drop-off walk along the south face
EX_WALK_C = box(-66, -151, -60, -68)          # walk from Prairie Ave sidewalk to the south face
EX_WALK_D = box(-36, 33, 256, 39)             # walk Maple St -> existing E. corridor door (REMOVE)
EX_WALK_N = box(-262, 120, -256, 175)         # walk to north play field (to remain)
SIDEWALK_PR = box(-FAR, PR["sw_n"][0], MP["sw_w"][1], PR["sw_n"][1])
SIDEWALK_MP = box(MP["sw_w"][0], PR["sw_n"][0], MP["sw_w"][1], FAR)

# ---- existing playground (protect)
PLAYGROUND = box(10, 115, 130, 200)
PLAY_ITEMS = [(box(26, 138, 74, 178), "PLAY STRUCTURE"), (box(90, 128, 118, 150), "SWINGS"),
              (box(92, 166, 120, 190), "PLAY STRUCTURE")]

# ---- existing trees: id, x, y, DBH (in), species, disposition (R = remove, P = protect)
TREES = [
    ("T1", 22.0, 52.0, 18, "BUR OAK", "R"),
    ("T2", 75.0, 20.0, 12, "SUGAR MAPLE", "R"),
    ("T3", 118.0, 58.0, 14, "GREEN ASH", "R"),
    ("T4", 140.0, 8.0, 10, "LINDEN", "R"),
    ("T5", -20.0, 12.0, 16, "HONEYLOCUST", "R"),
    ("T6", 182.0, 46.0, 10, "CRABAPPLE", "R"),
    ("T7", 40.0, 96.0, 14, "RED MAPLE", "R"),
    ("T8", -24.0, 78.0, 12, "NORWAY SPRUCE", "R"),
    ("T9", 152.0, 152.0, 20, "BUR OAK", "P"),
    ("T10", 205.0, 132.0, 16, "SUGAR MAPLE", "P"),
    ("T11", 222.0, -98.0, 18, "WHITE OAK", "P"),
    ("T12", 128.0, -92.0, 12, "WHITE PINE", "P"),
    ("T13", 264.5, 125.0, 10, "HONEYLOCUST", "P"),
    ("T14", 264.5, -45.0, 10, "HONEYLOCUST", "P"),
    ("T15", 264.5, -108.0, 12, "LINDEN", "P"),
    ("T16", 0.0, -159.0, 12, "LINDEN", "P"),
    ("T17", 160.0, -159.0, 10, "LINDEN", "P"),
    ("T18", -48.0, 168.0, 22, "BUR OAK", "P"),
]
# trees outside the work area (shown on C-100 only, no number)
TREES_BG = [(-150, -143, 12, "D"), (-238, -143, 12, "D"), (-330, -143, 14, "D"),
            (-370, -40, 16, "D"), (-385, 60, 18, "D"), (-360, 180, 20, "E"), (-250, 205, 18, "D"),
            (-150, 215, 16, "D"), (-90, 230, 14, "E"), (60, 238, 18, "D"), (200, 225, 16, "D"),
            (-250, 30, 10, "D"), (-162, 52, 10, "D"), (-400, 230, 14, "E"), (-405, -110, 12, "D"),
            (264.5, 205, 10, "D"), (-330, -159, 12, "D"), (-180, -159, 12, "D")]

# ---- light poles, utility poles, misc
LIGHT_POLES = [(-230.0, -80.5, "P"), (-150.0, -80.5, "P"), (-230.0, -134.5, "P"),
               (-150.0, -134.5, "P"), (60.0, 41.0, "R"), (190.0, 43.0, "P")]
UPOLES = [(-385.0, -159.0), (-235.0, -159.0), (-85.0, -159.0), (110.0, -159.0), (225.0, -159.0)]
HYDRANTS = [(265.0, 160.0, "H-1"), (265.0, -80.0, "H-2")]
FLAGPOLE = (-150.0, -143.0)
SCHOOL_SIGN = (-185.0, -143.0)
EX_XFMR = box(-54, -40, -46, -32)

# ---- existing utilities ----------------------------------------------------------------
WM_X = 275.0                                   # 8" DIP water main in Maple St (6'-0" cover)
SAN_Y = -180.0                                 # 8" PVC sanitary in Prairie Ave
STM_X = 284.0                                  # 12" RCP storm in Maple St
PRSTM_Y = -197.0                               # 15" RCP storm in Prairie Ave
GAS_X = 312.0                                  # 4" gas (NICOR) Maple St east parkway

# existing structures: id -> dict(x, y, kind, inv=[(dir, size, inv)])
EX_STR = {
    "EX ST-1": dict(x=STM_X, y=205.0, kind="smh", inv=[("N", 12, 704.30), ("S", 12, 704.20)]),
    "EX ST-2": dict(x=STM_X, y=90.0, kind="smh", inv=[("N", 12, 703.65), ("S", 12, 703.55)]),
    "EX ST-3": dict(x=STM_X, y=-40.0, kind="smh",
                    inv=[("N", 12, 702.90), ("W", 12, 706.10), ("S", 12, 702.80)]),
    "EX ST-4": dict(x=STM_X, y=PRSTM_Y, kind="smh", inv=[("N", 12, 702.00), ("E/W", 15, 701.40)]),
    "EX CI-1": dict(x=269.9, y=205.0, kind="ci", inv=[("E", 10, 705.40)]),
    "EX CI-2": dict(x=269.9, y=-40.0, kind="ci", inv=[("E", 10, 705.00)]),
    "EX CI-3": dict(x=306.1, y=-40.0, kind="ci", inv=[("W", 10, 705.10)]),
    "EX CI-4": dict(x=150.0, y=-163.9, kind="ci", inv=[("S", 10, 705.20)]),
    "EX CI-5": dict(x=-60.0, y=-163.9, kind="ci", inv=[("S", 10, 705.90)]),
    "EX CB-1": dict(x=-230.0, y=-108.0, kind="cb", inv=[("S", 10, 707.10)]),
    "EX CB-2": dict(x=-140.0, y=-108.0, kind="cb", inv=[("S", 10, 706.70)]),
    "EX YI-1": dict(x=-14.0, y=90.0, kind="yi", inv=[("SE", 12, 708.20)]),
    "EX YI-2": dict(x=75.0, y=49.5, kind="yi", inv=[("NW", 12, 707.60), ("SE", 12, 707.50)]),
    "EX SAN-1": dict(x=-330.0, y=SAN_Y, kind="sanmh", inv=[("E/W", 8, 706.40)]),
    "EX SAN-2": dict(x=-140.0, y=SAN_Y, kind="sanmh", inv=[("N", 6, 705.90), ("E/W", 8, 705.25)]),
    "EX SAN-3": dict(x=75.0, y=SAN_Y, kind="sanmh", inv=[("W", 8, 703.85), ("E", 8, 703.80)]),
    "EX SAN-4": dict(x=MP["cl"], y=SAN_Y, kind="sanmh", inv=[("W", 8, 702.50)]),
}
EX_RCP_REMOVE = [(-14.0, 90.0), (75.0, 49.5), (STM_X, -40.0)]     # 12" RCP crossing the footprint
EX_WATER_SVC = [(WM_X, 232.0), (-60.0, 232.0), (-60.0, 120.0)]      # 4" to existing school (N)
EX_SAN_SVC = [(-140.0, -60.0), (-140.0, SAN_Y)]                    # 6" from existing school
EX_STORM_LEADS = [[(-230.0, -108.0), (-230.0, PRSTM_Y)], [(-140.0, -108.0), (-140.0, PRSTM_Y)],
                  [(269.9, 205.0), (STM_X, 205.0)], [(269.9, -40.0), (STM_X, -40.0)],
                  [(306.1, -40.0), (STM_X, -40.0)], [(150.0, -163.9), (150.0, PRSTM_Y)],
                  [(-60.0, -163.9), (-60.0, PRSTM_Y)]]
EX_VALVES = [(WM_X, 160.0), (WM_X, -80.0), (WM_X, -172.0)]

# ========================================================================================
# 2. PROPOSED WORK
# ========================================================================================
NEW_BLDG = M.outline_poly("L1").buffer(M.EW_OUT, join_style=2).difference(
    box(-200, -500, M.EXIST_FACE_X, 500))
NEW_MAIN = M.outline_poly("L2").buffer(M.EW_OUT, join_style=2)       # 2-story block / roof
LINK = NEW_BLDG.difference(NEW_MAIN.buffer(0.01))
BX0, BY0, BX1, BY1 = NEW_MAIN.bounds                                  # brick face extents
DOORS = {  # exterior doors needing stoops / walks (from model.py)
    "ST1-B": M.OPENING_BY_ID["ST1-B"], "ST2-B": M.OPENING_BY_ID["ST2-B"],
    "100B": M.OPENING_BY_ID["100B"], "112": M.OPENING_BY_ID["112"]}


def _lin(axis, pts):
    """elevation = piecewise-linear interpolation along x or y (vectorized)"""
    s = np.array([p[0] for p in pts], float)
    z = np.array([p[1] for p in pts], float)
    order = np.argsort(s)
    s, z = s[order], z[order]

    def f(x, y):
        t = np.asarray(x if axis == "x" else y, float)
        return np.interp(t, s, z)
    return f


ENT_X1 = MP["sw_w"][0]          # entrance walk meets the public walk at x = 256


# Elevation at the public walk (match existing) is set after E() is defined (see below).
def _plane(z0, x0, y0, sx, sy):
    return lambda x, y: z0 - sx * (np.asarray(x, float) - x0) - sy * (np.asarray(y, float) - y0)


# new pavements: id, polygon, kind, elevation function, label
NEW_PAVE = [
    dict(id="STOOP-1", poly=box(-5.95, 21.0, BX0, 29.0), kind="stoop",
         z=_plane(STOOP, BX0, 0, -0.012, 0.0)),                       # ST1-B, slopes west
    dict(id="W-1", poly=box(-11.95, -60.0, -5.95, 26.0), kind="walk",
         z=_lin("y", [(26.0, 712.40), (12.5, 711.80), (-60.0, 711.42)])),
    dict(id="W-2", poly=box(-36.0, -68.0, -5.95, -60.0), kind="walk",
         z=_lin("x", [(-11.95, 711.40), (-36.0, 711.92)])),
    dict(id="W-3", poly=box(-5.95, -10.95, 30.5, -5.95), kind="walk",
         z=_lin("x", [(-5.95, 711.70), (30.5, 712.31)])),
    dict(id="APRON", poly=box(30.5, -10.95, 42.5, BY0), kind="apron",
         z=_plane(STOOP, 0, BY0, 0.0, -0.015)),                       # slopes south 1.5%
    dict(id="PLAZA", poly=box(BX1, 26.0, 164.95, 52.0), kind="stoop",
         z=_plane(STOOP, BX1, 0, 0.01, 0.0)),
    dict(id="BIKE", poly=box(152.95, 52.0, 164.95, 60.0), kind="pad",
         z=lambda x, y: STOOP - 0.01 * (np.asarray(x) - BX1) - 0.015 * (np.asarray(y) - 52.0)),
    dict(id="W-4", poly=box(164.95, 31.0, ENT_X1, 41.0), kind="walk", z=None),   # set below
]
PAVE_BY_ID = {p["id"]: p for p in NEW_PAVE}
BIKE_RACKS = [(155.5 + 2.75 * i, 56.0) for i in range(5)]   # 5 inverted-U racks, 2'-9" o.c.

# public-way work
PUB_WALK_REPL = [box(256, 29.0, 261, 43.0), box(256, 54.0, 261, 82.0)]   # sidewalk panels
CURB_REPL = [box(268.0, 54.0, 269.5, 82.0)]                               # curb & gutter (constr. entr.)
PATCH_WATER = box(268.5, -21.0, 280.0, -6.0)
PATCH_STORM = box(268.5, 84.0, 289.5, 96.0)
PATCH_SAN = Polygon([(58, -163.5), (72, -163.5), (84, -176), (84, -186), (66, -186), (66, -176)])
CORNER_RAMP_AREA = box(240, -170, 272, -138)

# ---- construction limits / owner constraints ----
_LOW_PARTS = [box(-36, -34, PL_E, 104), box(-40, -72, 40, -34), box(40, -150, 92, -34),
              box(165, -66, PL_E, -34),
              box(PL_E, 28.0, 262.0, 44.0), box(PL_E, 54.0, 270.5, 82.0),
              box(PL_E, 82.0, 290.5, 98.0), box(PL_E, -23.0, 281.0, -4.0),
              box(40, -188, 92, -150)]
LOW = unary_union(_LOW_PARTS).difference(EXB)
LOW_RAMP = box(242, -168, 270, -140)                  # separate LOW: corner curb ramps
LOW_ALL = unary_union([LOW, LOW_RAMP])
DISTURBED_SF = LOW_ALL.area
DISTURBED_AC = DISTURBED_SF / 43560.0
STAGING = box(170, -58, 245, 100)
CONST_ENT = box(185, 56, PL_E, 80)                    # stabilized construction entrance (70' x 24')
CONST_APRON = box(PL_E, 56, MP["boc_w"], 80)
WASHOUT = box(226, -52, 238, -40)
STOCKPILE_C, STOCKPILE_R = (203.0, -30.0), (20.0, 10.0)

# ---- new utilities ----
SAN_EXIT = (52.0, BY0)
FIRE_EXIT = (44.0, BY0)
DOM_EXIT = (46.5, BY0)
FIRE_Y, DOM_Y = -12.0, -15.0
FIRE_RUN = [(WM_X, FIRE_Y), (FIRE_EXIT[0], FIRE_Y), FIRE_EXIT]
DOM_RUN = [(WM_X, DOM_Y), (DOM_EXIT[0], DOM_Y), DOM_EXIT]
CURB_STOP = (264.0, DOM_Y)
XFMR = box(14, -42, 22, -34)
ELEC_PRI = [(110.0, -159.0), (110.0, -48.0), (22.0, -38.0)]
ELEC_SEC = [(18.0, -34.0), (18.0, -22.0), (31.5, -18.0), (31.5, BY0)]
GAS_RUN = [(GAS_X, -26.0), (58.5, -26.0), (58.5, BY0)]
GAS_METER = (58.5, BY0 - 1.2)

# storm: structure id -> (x, y, type, rim(None=from grade), [(pipe_in_label, inv)], inv_out)
STM = {
    "AD-1": dict(x=-18.0, y=60.0, kind="ad", desc="12\" AREA DRAIN, PVC BODY W/ DUCTILE IRON GRATE"),
    "CB-1": dict(x=-14.0, y=90.0, kind="cb", desc="48\" CATCH BASIN TYPE A, NEENAH R-4342 FRAME & GRATE"),
    "MH-1": dict(x=52.5, y=90.0, kind="mh", desc="48\" STORM MANHOLE TYPE A, NEENAH R-1712 CLOSED LID"),
    "CB-2": dict(x=97.5, y=90.0, kind="cb", desc="48\" CATCH BASIN TYPE A, NEENAH R-4342 FRAME & GRATE"),
    "CB-3": dict(x=185.0, y=90.0, kind="cb", desc="48\" CATCH BASIN TYPE A, NEENAH R-4342 FRAME & GRATE"),
}
STM_EXIST_CONN = "EX ST-2"
DS_BOOT = (-10.0, 42.0 + M.EW_OUT + 1.0)              # link downspout boot (north side, x = -10)
RL = {"RL-1": (52.5, BY1), "RL-2": (97.5, BY1)}

# pipes: (id, from, to, size, material, inv_from, slope)  inverts computed from slope & length
STM_PIPES = [
    ("P-1", "DS-1", "AD-1", 6, "PVC SDR-35", 709.90, 0.0200),
    ("P-2", "AD-1", "CB-1", 8, "PVC SDR-35", 709.44, 0.0200),
    ("P-3", "RL-1", "MH-1", 8, "PVC SDR-35", 708.90, 0.0200),
    ("P-4", "RL-2", "CB-2", 8, "PVC SDR-35", 708.90, 0.0200),
    ("P-5", "CB-1", "MH-1", 12, "PVC SDR-35", 708.40, 0.0050),
    ("P-6", "MH-1", "CB-2", 12, "PVC SDR-35", 707.97, 0.0050),
    ("P-7", "CB-2", "CB-3", 12, "PVC SDR-35", 707.65, 0.0050),
    ("P-8", "CB-3", "EX ST-2", 12, "PVC SDR-35", 707.11, 0.0050),
]
SAN = {
    "CO-1": dict(x=52.0, y=BY0 - 5.0, kind="co", desc="6\" TWO-WAY CLEANOUT, C.I. FRAME & COVER IN CONC. COLLAR"),
    "CO-2": dict(x=52.0, y=-70.0, kind="co", desc="6\" CLEANOUT, C.I. FRAME & COVER IN CONC. COLLAR"),
    "SMH-1": dict(x=52.0, y=-136.0, kind="sanmh", desc="48\" SANITARY MANHOLE, NEENAH R-1712 SOLID LID, BOLTED"),
}
SAN_PIPES = [
    ("S-1", "BLDG", "CO-1", 6, "PVC SDR-26", 709.00, 0.0208),
    ("S-2", "CO-1", "CO-2", 6, "PVC SDR-26*", None, 0.0208),
    ("S-3", "CO-2", "SMH-1", 6, "PVC SDR-26", None, 0.0208),
    ("S-4", "SMH-1", "EX SAN-3", 6, "PVC SDR-26", 706.10, 0.0400),
]


def _pt(name):
    if name in STM:
        return (STM[name]["x"], STM[name]["y"])
    if name in SAN:
        return (SAN[name]["x"], SAN[name]["y"])
    if name in EX_STR:
        return (EX_STR[name]["x"], EX_STR[name]["y"])
    if name == "DS-1":
        return DS_BOOT
    if name in RL:
        return RL[name]
    if name == "BLDG":
        return SAN_EXIT
    raise KeyError(name)


def _pipe_table(pipes):
    """compute lengths and inverts. Returns list of dicts."""
    out = []
    prev_out = {}
    for pid, a, b, size, mat, inv0, s in pipes:
        pa, pb = _pt(a), _pt(b)
        L = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
        if inv0 is None:
            inv0 = prev_out[a]
        inv1 = inv0 - s * L
        out.append(dict(id=pid, a=a, b=b, size=size, mat=mat, L=L, inv_a=inv0, inv_b=inv1, s=s,
                        pa=pa, pb=pb))
        prev_out[b] = inv1
    return out


STM_PIPE_DATA = _pipe_table(STM_PIPES)
SAN_PIPE_DATA = _pipe_table(SAN_PIPES)


# ========================================================================================
# 3. SURFACES (existing E, proposed P) and contouring
# ========================================================================================
def E_nat(x, y):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    return (711.80 - 0.0052 * x + 0.0058 * y + 0.30 * np.sin((x + 60.0) / 95.0) *
            np.cos((y - 30.0) / 80.0) + 0.15 * np.sin((x - 2.0 * y) / 130.0))


def E(x, y):
    """existing ground: natural surface held to the existing building pad (FFE 712.50,
    grade about 711.95 at the walls, 2.5% max away from the pad)"""
    x = np.atleast_1d(np.asarray(x, float))
    y = np.atleast_1d(np.asarray(y, float))
    d = shapely.distance(EXB, shapely.points(x, y))
    n = E_nat(x, y)
    z = 711.95 + np.clip(n - 711.95, -0.025 * d, 0.025 * d)
    return z


def E1(x, y):
    return float(E(x, y)[0])


# entrance walk: from the plaza (712.32) down to the public walk (match existing)
ENT_Z1 = round(E1(ENT_X1, 36.0) + 0.05, 2)
PAVE_BY_ID["W-4"]["z"] = _lin("x", [(164.95, round(STOOP - 0.14, 2)), (ENT_X1, ENT_Z1)])

INLETS = {k: v for k, v in STM.items() if v["kind"] in ("cb", "ad")}
SWALE_Y = 90.0
SWALE_S = [(-14.0, 711.00), (40.0, 711.25), (97.5, 710.85), (141.0, 711.20), (185.0, 710.85)]
SWALE_HP = [(40.0, 711.25), (141.0, 711.20)]


def _smooth(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def P_surface(xs, ys):
    """proposed finished grade on the grid xs (nx) x ys (ny) -> (ny, nx) array"""
    X, Y = np.meshgrid(xs, ys)
    return P_points(X.ravel(), Y.ravel()).reshape(X.shape)


def P_points(xf, yf):
    """proposed finished grade at arbitrary points (NaN inside the new building)"""
    xf = np.asarray(xf, float)
    yf = np.asarray(yf, float)
    pts = shapely.points(xf, yf)
    Ez = E(xf, yf)
    d = shapely.distance(NEW_BLDG, pts)
    Db = FG - 0.05 * np.minimum(d, 10.0) - 0.02 * np.maximum(d - 10.0, 0.0)
    P0 = np.maximum(Db, Ez - 0.06 * np.maximum(30.0 - d, 0.0))
    # pavements: blend toward the pavement surface within 5 ft
    for pv in NEW_PAVE:
        poly = pv["poly"]
        dw = shapely.distance(poly, pts)
        near = dw < 5.0
        if not near.any():
            continue
        zw = pv["z"](xf[near], yf[near])
        w = 1.0 - _smooth(dw[near] / 5.0)
        P0[near] = P0[near] * (1 - w) + zw * w
    # north swale (y = SWALE_Y) graded to the catch basins, 6% side slopes
    band = (np.abs(yf - SWALE_Y) < 16.0) & (xf > SWALE_S[0][0] - 12) & (xf < SWALE_S[-1][0] + 12)
    if band.any():
        sx = np.array([q[0] for q in SWALE_S])
        sz = np.array([q[1] for q in SWALE_S])
        Sw = np.interp(xf[band], sx, sz) + 0.06 * np.abs(yf[band] - SWALE_Y)
        P0[band] = np.minimum(P0[band], Sw)
    # inlet bowls
    for k, s in INLETS.items():
        r = np.hypot(xf - s["x"], yf - s["y"])
        R = 9.0 if s["kind"] == "cb" else 7.0
        dep = 0.25 if s["kind"] == "cb" else 0.30
        m = r < R
        P0[m] -= dep * (1 - r[m] / R) ** 1.6
    # only inside the limit of work; blend to existing over 8 ft inside the LOW line
    inside = shapely.contains_xy(LOW, xf, yf)
    dl = shapely.distance(LOW.boundary, pts)
    w = np.where(inside, _smooth(dl / 8.0), 0.0)
    Pz = Ez + w * (P0 - Ez)
    inb = shapely.contains_xy(NEW_BLDG, xf, yf)
    Pz[inb] = np.nan
    return Pz


def P1(x, y):
    return float(P_surface(np.array([x]), np.array([y]))[0, 0])


def _rim(name):
    s = STM.get(name) or SAN.get(name)
    return round(P1(s["x"], s["y"]), 2)


def ex_rim(name):
    s = EX_STR[name]
    z = E1(s["x"], s["y"])
    if s["kind"] in ("ci",):
        z -= 0.45
    return round(z, 2)


# ---- marching squares ----
_SEG = {1: [(3, 0)], 2: [(0, 1)], 3: [(3, 1)], 4: [(1, 2)], 6: [(0, 2)], 7: [(3, 2)],
        8: [(2, 3)], 9: [(0, 2)], 11: [(1, 2)], 12: [(1, 3)], 13: [(0, 1)], 14: [(3, 0)]}


def contour_lines(xs, ys, Z, level):
    z0 = Z[:-1, :-1]
    z1 = Z[:-1, 1:]
    z2 = Z[1:, 1:]
    z3 = Z[1:, :-1]
    valid = ~(np.isnan(z0) | np.isnan(z1) | np.isnan(z2) | np.isnan(z3))
    case = ((z0 > level) * 1 + (z1 > level) * 2 + (z2 > level) * 4 + (z3 > level) * 8)
    case = np.where(valid, case, 0)
    idx = np.argwhere((case > 0) & (case < 15))
    segs = []
    for j, i in idx:
        c = int(case[j, i])
        E_ = [("h", i, j), ("v", i + 1, j), ("h", i, j + 1), ("v", i, j)]
        if c in (5, 10):
            ctr = (z0[j, i] + z1[j, i] + z2[j, i] + z3[j, i]) / 4.0
            up = ctr > level
            if c == 5:
                pairs = [(0, 1), (2, 3)] if up else [(3, 0), (1, 2)]
            else:
                pairs = [(3, 0), (1, 2)] if up else [(0, 1), (2, 3)]
        else:
            pairs = _SEG[c]
        for a, b in pairs:
            segs.append((E_[a], E_[b]))

    def ept(e):
        k, i, j = e
        if k == "h":
            za, zb = Z[j, i], Z[j, i + 1]
            t = (level - za) / (zb - za)
            return (xs[i] + t * (xs[i + 1] - xs[i]), ys[j])
        za, zb = Z[j, i], Z[j + 1, i]
        t = (level - za) / (zb - za)
        return (xs[i], ys[j] + t * (ys[j + 1] - ys[j]))

    adj = {}
    for n, (a, b) in enumerate(segs):
        adj.setdefault(a, []).append(n)
        adj.setdefault(b, []).append(n)
    used = [False] * len(segs)
    lines = []
    for n in range(len(segs)):
        if used[n]:
            continue
        used[n] = True
        a, b = segs[n]
        chain = [a, b]
        for end in (1, 0):
            while True:
                tip = chain[-1] if end == 1 else chain[0]
                nxt = None
                for m in adj.get(tip, []):
                    if not used[m]:
                        nxt = m
                        break
                if nxt is None:
                    break
                used[nxt] = True
                p, q = segs[nxt]
                other = q if p == tip else p
                if end == 1:
                    chain.append(other)
                else:
                    chain.insert(0, other)
        lines.append([ept(e) for e in chain])
    return lines


def chaikin(pts, it=2):
    if len(pts) < 3:
        return pts
    closed = math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) < 1e-6
    for _ in range(it):
        out = [pts[0]] if not closed else []
        rng = range(len(pts) - 1)
        for k in rng:
            p, q = pts[k], pts[k + 1]
            out.append((0.75 * p[0] + 0.25 * q[0], 0.75 * p[1] + 0.25 * q[1]))
            out.append((0.25 * p[0] + 0.75 * q[0], 0.25 * p[1] + 0.75 * q[1]))
        if closed:
            out.append(out[0])
        else:
            out.append(pts[-1])
        pts = out
    return pts


_CACHE = {}


def existing_contours(win, step=3.0, mask=None):
    key = ("E", tuple(win.values()), step, mask is not None)
    if key in _CACHE:
        return _CACHE[key]
    xs = np.arange(win["x0"] - 6, win["x1"] + 6, step)
    ys = np.arange(win["y0"] - 6, win["y1"] + 6, step)
    X, Y = np.meshgrid(xs, ys)
    Z = E(X.ravel(), Y.ravel()).reshape(X.shape)
    inb = shapely.contains_xy(EXB.buffer(1.0), X.ravel(), Y.ravel()).reshape(X.shape)
    Z[inb] = np.nan
    out = {}
    lo, hi = int(math.floor(np.nanmin(Z))), int(math.ceil(np.nanmax(Z)))
    for L in range(lo, hi + 1):
        ls = [chaikin(p, 2) for p in contour_lines(xs, ys, Z, L + 1e-6)]
        geoms = [LineString(p) for p in ls if len(p) >= 2]
        g = unary_union(geoms) if geoms else None
        if g is not None and mask is not None:
            g = g.difference(mask)
        out[L] = g
    _CACHE[key] = out
    return out


def proposed_grid(step=2.0):
    if "P" in _CACHE:
        return _CACHE["P"]
    x0, y0, x1, y1 = LOW.bounds
    xs = np.arange(x0 - 4, x1 + 4, step)
    ys = np.arange(y0 - 4, y1 + 4, step)
    Z = P_surface(xs, ys)
    _CACHE["P"] = (xs, ys, Z)
    return xs, ys, Z


def proposed_contours():
    if "PC" in _CACHE:
        return _CACHE["PC"]
    xs, ys, Z = proposed_grid()
    X, Y = np.meshgrid(xs, ys)
    D = np.abs(Z - E(X.ravel(), Y.ravel()).reshape(X.shape))
    x0, y0, h = xs[0], ys[0], xs[1] - xs[0]

    def regraded(q):
        i = int(round((q[0] - x0) / h))
        j = int(round((q[1] - y0) / h))
        i = min(max(i, 1), len(xs) - 2)
        j = min(max(j, 1), len(ys) - 2)
        d = D[j - 1:j + 2, i - 1:i + 2]
        return np.nanmax(d) > 0.10 if np.isfinite(d).any() else False

    out = {}
    for L in range(int(math.floor(np.nanmin(Z))), int(math.ceil(np.nanmax(Z))) + 1):
        ls = [chaikin(p, 2) for p in contour_lines(xs, ys, Z, L + 1e-6)]
        geoms = []
        for pl in ls:
            run = []
            for q in pl:
                if regraded(q):
                    run.append(q)
                else:
                    if len(run) >= 2 and LineString(run).length > 12.0:
                        geoms.append(LineString(run))
                    run = []
            if len(run) >= 2 and LineString(run).length > 12.0:
                geoms.append(LineString(run))
        if not geoms:
            continue
        g = unary_union(geoms).intersection(LOW.buffer(-0.5))
        if not g.is_empty:
            out[L] = g
    _CACHE["PC"] = out
    return out


# ========================================================================================
# 4. DRAWING HELPERS
# ========================================================================================
class Clip:
    """with Clip(sh, x0, y0, x1, y1): ...  clips drawing to a paper rectangle"""

    def __init__(self, p, x0, y0, x1, y1):
        self.c, self.r = p.c, (x0, y0, x1, y1)

    def __enter__(self):
        x0, y0, x1, y1 = self.r
        self.c.saveState()
        path = self.c.beginPath()
        path.rect(x0 * PT, y0 * PT, (x1 - x0) * PT, (y1 - y0) * PT)
        self.c.clipPath(path, stroke=0, fill=0)
        return self

    def __exit__(self, *a):
        self.c.restoreState()


class XY(Paper):
    """profile / section space: (s, z) with separate horizontal and vertical scales"""

    def __init__(self, c, ox, oy, hs, vs, s0, z0):
        super().__init__(c)
        self.ox, self.oy, self.hs, self.vs, self.s0, self.z0 = ox, oy, hs, vs, s0, z0

    def P(self, p):
        return ((self.ox + (p[0] - self.s0) * self.hs) * PT, (self.oy + (p[1] - self.z0) * self.vs) * PT)

    def L(self, d):
        return d * self.hs * PT

    def to_paper(self, p):
        return (self.ox + (p[0] - self.s0) * self.hs, self.oy + (p[1] - self.z0) * self.vs)


def elev_grid(xy: XY, s0, s1, z0, z1, step=1.0, labels=True, sta=None, size=TY + 0.6):
    """light elevation grid with elevation labels at both ends; optional station ticks"""
    z = math.ceil(z0)
    while z <= z1 + 1e-6:
        lw_ = "fine" if abs(z % 5) < 1e-6 else "hair"
        xy.line((s0, z), (s1, z), lw=lw_, color=Color(0.6, 0.6, 0.6))
        if labels:
            a = xy.to_paper((s0, z))
            b = xy.to_paper((s1, z))
            xy_p = Paper(xy.c)
            xy_p.text((a[0] - 0.05, a[1]), f"{z:.0f}", size=size, anchor="r", valign="mid")
            xy_p.text((b[0] + 0.05, b[1]), f"{z:.0f}", size=size, anchor="l", valign="mid")
        z += step
    xy.polyline([(s0, z0), (s1, z0), (s1, z1), (s0, z1)], lw="thin", closed=True)
    if sta:
        pp = Paper(xy.c)
        for st, lab in sta:
            a = xy.to_paper((st, z0))
            pp.line((a[0], a[1]), (a[0], a[1] - 0.05), lw="fine")
            pp.text((a[0], a[1] - 0.08), lab, size=size, anchor="c", valign="top")


def ptext(p: Paper, xy, s, size=SM, font=FONT, anchor="l", valign="mid", rot=0.0, col="black",
          mask=True, pad=0.012):
    """paper-space text with an optional white mask behind it"""
    c = p.c
    w = stringWidth(s, font, size) / PT
    h = size / PT
    c.saveState()
    c.translate(xy[0] * PT, xy[1] * PT)
    if rot:
        c.rotate(rot)
    dx = {"l": 0.0, "c": -w / 2, "r": -w}[anchor]
    dy = {"base": 0.0, "mid": -0.35 * h, "top": -0.72 * h, "bot": 0.0}[valign]
    if mask:
        c.setFillColor(white)
        c.rect((dx - pad) * PT, (dy - 0.22 * h - pad) * PT, (w + 2 * pad) * PT,
               (0.98 * h + 2 * pad) * PT, stroke=0, fill=1)
    c.setFillColor(color(col))
    c.setFont(font, size)
    c.drawString(dx * PT, dy * PT, s)
    c.restoreState()
    return w


def plines(p: Paper, xy, lines, size=SM, font=FONT, anchor="l", valign="mid", col="black",
           mask=True, lead=1.18):
    """multi-line paper text (valign refers to the whole block). '**x**' = bold line"""
    if isinstance(lines, str):
        lines = lines.split("\n")
    n = len(lines)
    ld = size * lead / PT
    if valign == "mid":
        y = xy[1] + (n - 1) * ld / 2
    elif valign == "top":
        y = xy[1] - size * 0.72 / PT
    else:
        y = xy[1] + (n - 1) * ld
    for ln in lines:
        f = font
        if ln.startswith("**") and ln.endswith("**"):
            ln, f = ln[2:-2], FONT_B
        ptext(p, (xy[0], y), ln, size, f, anchor, "mid" if valign != "top" else "mid", 0, col, mask)
        y -= ld
    return n * ld


def callout(v: View, target, at, lines, size=SM, col="black", arrow="arrow", font=FONT,
            side=None, mask=True, shoulder=0.07):
    """leader from model `target` to model `at`, with a short horizontal shoulder and text"""
    p = Paper(v.c)
    tx, ty = v.to_paper(target)
    ax, ay = v.to_paper(at)
    if side is None:
        side = "r" if ax >= tx else "l"
    sx = ax + (shoulder if side == "r" else -shoulder)
    p.polyline([(tx, ty), (ax, ay), (sx, ay)], lw="fine", color=col)
    if arrow == "arrow":
        d = math.hypot(ax - tx, ay - ty) or 1.0
        ux, uy = (tx - ax) / d, (ty - ay) / d
        L, W = 0.055, 0.017
        bx, by = tx - ux * L, ty - uy * L
        p.polygon([(tx, ty), (bx - uy * W, by + ux * W), (bx + uy * W, by - ux * W)], lw="fine",
                  fill=col, color=col)
    elif arrow == "dot":
        p.circle((tx, ty), 0.016, lw=None, fill=col)
    if isinstance(lines, str):
        lines = lines.split("\n")
    plines(p, (sx + (0.03 if side == "r" else -0.03), ay), lines, size, font,
           "l" if side == "r" else "r", "mid", col, mask)


def path_points(v, pts):
    pp = [v.to_paper(q) for q in pts]
    segs = []
    tot = 0.0
    for a, b in zip(pp[:-1], pp[1:]):
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        segs.append((a, b, L, tot))
        tot += L
    return segs, tot


def _at(segs, s):
    for a, b, L, s0 in segs:
        if s <= s0 + L or (a, b, L, s0) == segs[-1]:
            t = 0.0 if L == 0 else min(1.0, max(0.0, (s - s0) / L))
            ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), ang
    return segs[-1][1], 0.0


def upright(ang):
    while ang > 90.01:
        ang -= 180
    while ang < -89.99:
        ang += 180
    return ang


def tagged_line(v: View, pts, tag, lw="thin", col="black", dash=None, every=1.5, size=4.6,
                first=None, font=FONT_B):
    """utility-type line with an inline tag ( --W-- ) every `every` paper inches"""
    v.polyline(pts, lw=lw, color=col, dash=dash)
    segs, tot = path_points(v, pts)
    if tot < 0.25:
        return
    p = Paper(v.c)
    if first is None:
        first = min(every / 2, tot / 2)
    s = first
    while s < tot - 0.08:
        q, ang = _at(segs, s)
        ptext(p, q, tag, size, font, "c", "mid", upright(ang), col, True, 0.01)
        s += every


def mark_line(v: View, pts, mark="x", every=0.16, size=0.028, lw="fine", col="black",
              dash=None, line_lw=None):
    """fence-type line with x / o marks"""
    v.polyline(pts, lw=line_lw or lw, color=col, dash=dash)
    segs, tot = path_points(v, pts)
    p = Paper(v.c)
    s = every / 2
    while s < tot:
        q, ang = _at(segs, s)
        if mark == "x":
            d = size
            p.line((q[0] - d, q[1] - d), (q[0] + d, q[1] + d), lw=lw, color=col)
            p.line((q[0] - d, q[1] + d), (q[0] + d, q[1] - d), lw=lw, color=col)
        elif mark == "o":
            p.circle(q, size, lw=lw, color=col, fill="white")
        elif mark == "tick":
            a = math.radians(ang + 90)
            p.line(q, (q[0] + math.cos(a) * size * 2, q[1] + math.sin(a) * size * 2), lw=lw,
                   color=col)
        s += every


def ring_pts(g):
    """exterior ring coordinates of a polygon"""
    return list(g.exterior.coords)


def tree_sym(v: View, x, y, dbh, kind="D", col=SCR, lw="fine", remove=False, label=None,
             label_side=(1, -1), lsize=TY + 0.3):
    R = max(5.0, dbh * 0.85)
    if kind == "E":
        n = 10
        pts = []
        for k in range(2 * n + 1):
            a = 2 * math.pi * k / (2 * n)
            r = R if k % 2 == 0 else R * 0.72
            pts.append((x + r * math.cos(a), y + r * math.sin(a)))
        v.polyline(pts, lw=lw, color=col)
    else:
        n = max(7, int(R * 0.7))
        pts = []
        for k in range(n * 8 + 1):
            a = 2 * math.pi * k / (n * 8)
            r = R * (0.9 + 0.1 * abs(math.sin(a * n / 2)))
            pts.append((x + r * math.cos(a), y + r * math.sin(a)))
        v.polyline(pts, lw=lw, color=col)
    c = v.paper_len(0.025)
    v.line((x - c, y), (x + c, y), lw="fine", color=col)
    v.line((x, y - c), (x, y + c), lw="fine", color=col)
    if remove:
        k = R * 0.75
        v.line((x - k, y - k), (x + k, y + k), lw="med")
        v.line((x - k, y + k), (x + k, y - k), lw="med")
    if label:
        p = Paper(v.c)
        px, py = v.to_paper((x + label_side[0] * R * 0.75, y + label_side[1] * R * 0.75))
        plines(p, (px + 0.02 * label_side[0], py), label, lsize, FONT,
               "l" if label_side[0] > 0 else "r", "mid", EXC if not remove else "black", True)
    return R


def sym_hydrant(v, x, y, col=SCR):
    p = Paper(v.c)
    px, py = v.to_paper((x, y))
    r = 0.032
    p.circle((px, py), r, lw="thin", color=col, fill="white")
    p.line((px - r * 2.0, py), (px + r * 2.0, py), lw="thin", color=col)
    p.circle((px, py), r * 0.45, lw=None, fill=col)


def sym_valve(v, x, y, col=SCR, size=0.04, ang=0.0):
    p = Paper(v.c)
    px, py = v.to_paper((x, y))
    a = math.radians(ang)
    u = (math.cos(a), math.sin(a))
    n = (-u[1], u[0])
    s = size
    pts = [(px - u[0] * s + n[0] * s * 0.6, py - u[1] * s + n[1] * s * 0.6),
           (px + u[0] * s - n[0] * s * 0.6, py + u[1] * s - n[1] * s * 0.6),
           (px + u[0] * s + n[0] * s * 0.6, py + u[1] * s + n[1] * s * 0.6),
           (px - u[0] * s - n[0] * s * 0.6, py - u[1] * s - n[1] * s * 0.6)]
    p.polygon(pts, lw="fine", color=col, fill=col)


def sym_structure(v, x, y, kind, col="black", lw="thin", fill="white"):
    p = Paper(v.c)
    px, py = v.to_paper((x, y))
    if kind in ("smh", "mh", "sanmh"):
        r = max(0.055, v.L(2.0) / PT)
        p.circle((px, py), r, lw=lw, color=col, fill=fill)
        if kind == "sanmh":
            p.text((px, py), "S", size=TY, font=FONT_B, anchor="c", valign="mid", color=col)
        else:
            p.circle((px, py), r * 0.45, lw="fine", color=col)
    elif kind in ("cb", "yi"):
        r = max(0.055, v.L(2.0) / PT)
        p.circle((px, py), r, lw=lw, color=col, fill=fill)
        s = r * 0.62
        p.rect(px - s, py - s, 2 * s, 2 * s, lw="fine", color=col, fill=col if kind == "cb" else None)
        if kind == "yi":
            p.line((px - s, py - s), (px + s, py + s), lw="fine", color=col)
            p.line((px - s, py + s), (px + s, py - s), lw="fine", color=col)
    elif kind == "ci":
        w, h = 0.05, 0.11
        p.rect(px - w / 2, py - h / 2, w, h, lw=lw, color=col, fill=fill)
        p.line((px - w / 2, py - h / 2), (px + w / 2, py + h / 2), lw="fine", color=col)
    elif kind == "ad":
        r = 0.04
        p.circle((px, py), r, lw=lw, color=col, fill=fill)
        p.line((px - r, py), (px + r, py), lw="fine", color=col)
        p.line((px, py - r), (px, py + r), lw="fine", color=col)
    elif kind == "co":
        r = 0.028
        p.circle((px, py), r, lw=lw, color=col, fill=fill)
        p.circle((px, py), 0.008, lw=None, fill=col)


def sym_light(v, x, y, col=SCR):
    p = Paper(v.c)
    px, py = v.to_paper((x, y))
    p.circle((px, py), 0.022, lw="thin", color=col, fill=col)
    p.line((px, py), (px + 0.06, py + 0.03), lw="thin", color=col)
    p.rect(px + 0.05, py + 0.015, 0.035, 0.028, lw="fine", color=col, fill="white")


def sym_upole(v, x, y, col=SCR):
    p = Paper(v.c)
    px, py = v.to_paper((x, y))
    r = 0.032
    p.circle((px, py), r, lw="thin", color=col, fill="white")
    p.line((px - r * 0.7, py - r * 0.7), (px + r * 0.7, py + r * 0.7), lw="fine", color=col)
    p.line((px - r * 0.7, py + r * 0.7), (px + r * 0.7, py - r * 0.7), lw="fine", color=col)


def spot(v, x, y, z, prefix="", col="black", size=TY + 0.6, dx=0.035, dy=0.0, anchor="l",
         marker="x", underline=False, font=FONT):
    p = Paper(v.c)
    px, py = v.to_paper((x, y))
    d = 0.022
    if marker == "x":
        p.line((px - d, py - d), (px + d, py + d), lw="fine", color=col)
        p.line((px - d, py + d), (px + d, py - d), lw="fine", color=col)
    elif marker == "dot":
        p.circle((px, py), 0.014, lw=None, fill=col)
    s = (prefix + " " if prefix else "") + (f"{z:.2f}" if isinstance(z, (int, float)) else z)
    ox = dx if anchor == "l" else -dx
    ptext(p, (px + ox, py + dy), s, size, font, anchor, "mid", 0, col, True)


def slope_arrow(v, a, b, text, col="black", size=TY + 0.5):
    p = Paper(v.c)
    pa, pb = v.to_paper(a), v.to_paper(b)
    p.line(pa, pb, lw="fine", color=col)
    d = math.hypot(pb[0] - pa[0], pb[1] - pa[1]) or 1
    ux, uy = (pb[0] - pa[0]) / d, (pb[1] - pa[1]) / d
    L, W = 0.06, 0.02
    bx, by = pb[0] - ux * L, pb[1] - uy * L
    p.polygon([pb, (bx - uy * W, by + ux * W), (bx + uy * W, by - ux * W)], lw="fine", fill=col,
              color=col)
    ang = upright(math.degrees(math.atan2(uy, ux)))
    m = ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2)
    nx, ny = -math.sin(math.radians(ang)), math.cos(math.radians(ang))
    ptext(p, (m[0] + nx * 0.045, m[1] + ny * 0.045), text, size, FONT, "c", "mid", ang, col, True,
          0.005)


def flow_arrow(v, a, b, col="black"):
    p = Paper(v.c)
    pa, pb = v.to_paper(a), v.to_paper(b)
    d = math.hypot(pb[0] - pa[0], pb[1] - pa[1]) or 1
    ux, uy = (pb[0] - pa[0]) / d, (pb[1] - pa[1]) / d
    m = ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2)
    L, W = 0.07, 0.025
    tip = (m[0] + ux * L / 2, m[1] + uy * L / 2)
    bx, by = m[0] - ux * L / 2, m[1] - uy * L / 2
    p.polygon([tip, (bx - uy * W, by + ux * W), (bx + uy * W, by - ux * W)], lw="fine",
              color=col, fill=col)


def text_along(v, a, b, s, size=SM, col="black", font=FONT_B, off=0.0, t=0.5, mask=True):
    p = Paper(v.c)
    pa, pb = v.to_paper(a), v.to_paper(b)
    ang = upright(math.degrees(math.atan2(pb[1] - pa[1], pb[0] - pa[0])))
    m = (pa[0] + (pb[0] - pa[0]) * t, pa[1] + (pb[1] - pa[1]) * t)
    nx, ny = -math.sin(math.radians(ang)), math.cos(math.radians(ang))
    ptext(p, (m[0] + nx * off, m[1] + ny * off), s, size, font, "c", "mid", ang, col, mask)


def hex_tag(p: Paper, xy, s, size=SM, col="black"):
    """hexagon keynote tag in paper space (civil keynotes)"""
    w = max(0.11, (stringWidth(s, FONT_B, size) / PT + 0.07) / 2)
    h = 0.075
    x, y = xy
    pts = [(x - w, y), (x - w + h * 0.8, y + h), (x + w - h * 0.8, y + h), (x + w, y),
           (x + w - h * 0.8, y - h), (x - w + h * 0.8, y - h)]
    p.polygon(pts, lw="thin", color=col, fill="white")
    p.text((x, y), s, size=size, font=FONT_B, anchor="c", valign="mid", color=col)


def key_tag(v: View, target, at, s, arrow="arrow"):
    """leader from model target to a keynote hexagon at model point `at`"""
    p = Paper(v.c)
    ax, ay = v.to_paper(at)
    tx, ty = v.to_paper(target) if target is not None else (ax, ay)
    if target is not None and math.hypot(ax - tx, ay - ty) > 0.12:
        p.line((tx, ty), (ax, ay), lw="fine")
        if arrow == "arrow":
            d = math.hypot(ax - tx, ay - ty)
            ux, uy = (tx - ax) / d, (ty - ay) / d
            L, W = 0.055, 0.017
            bx, by = tx - ux * L, ty - uy * L
            p.polygon([(tx, ty), (bx - uy * W, by + ux * W), (bx + uy * W, by - ux * W)],
                      lw="fine", fill="black")
        else:
            p.circle((tx, ty), 0.016, lw=None, fill="black")
    hex_tag(p, (ax, ay), s)


def contour_label(v, g, z, col, size=TY + 0.4, every=5.0, min_len=1.2, font=FONT):
    """label a contour geometry with its elevation every `every` paper inches"""
    if g is None or g.is_empty:
        return
    geoms = g.geoms if hasattr(g, "geoms") else [g]
    p = Paper(v.c)
    for ln in geoms:
        if ln.geom_type != "LineString":
            continue
        pts = list(ln.coords)
        segs, tot = path_points(v, pts)
        if tot < min_len:
            continue
        n = max(1, int(tot / every))
        for k in range(n):
            s = tot * (k + 0.5) / n
            q, ang = _at(segs, s)
            ptext(p, q, f"{z}", size, font, "c", "mid", upright(ang), col, True, 0.01)


def conc(v, g, dens=0.05, tri=0.12, tsize=1.1, col="black", seed=3):
    """light concrete stipple (dots + small triangles) clipped to geometry g"""
    if g is None or g.is_empty:
        return
    geoms = g.geoms if hasattr(g, "geoms") else [g]
    c = v.c
    import random as _r
    rnd = _r.Random(seed)
    for q in geoms:
        if q.geom_type != "Polygon":
            continue
        rings = [list(q.exterior.coords)] + [list(r.coords) for r in q.interiors]
        pp = [v.P(pt) for pt in rings[0]]
        xs_ = [a[0] for a in pp]
        ys_ = [a[1] for a in pp]
        X0, X1, Y0, Y1 = min(xs_), max(xs_), min(ys_), max(ys_)
        area = (X1 - X0) * (Y1 - Y0)
        if area <= 0:
            continue
        c.saveState()
        v._clip_rings(rings)
        c.setFillColor(color(col))
        c.setStrokeColor(color(col))
        c.setLineWidth(0.25)
        c.setDash([])
        n = int(min(area * dens, 20000))
        for _ in range(n):
            c.circle(rnd.uniform(X0, X1), rnd.uniform(Y0, Y1), 0.22, stroke=0, fill=1)
        for _ in range(int(n * tri)):
            x, y = rnd.uniform(X0, X1), rnd.uniform(Y0, Y1)
            a = rnd.uniform(0, 2 * math.pi)
            sz = tsize * rnd.uniform(0.8, 1.3)
            path = c.beginPath()
            for j in range(3):
                aa = a + j * 2 * math.pi / 3
                (path.moveTo if j == 0 else path.lineTo)(x + sz * math.cos(aa), y + sz * math.sin(aa))
            path.close()
            c.drawPath(path, stroke=1, fill=0)
        c.restoreState()


def draw_geom_lines(v, g, lw="fine", col="black", dash=None):
    if g is None or g.is_empty:
        return
    geoms = g.geoms if hasattr(g, "geoms") else [g]
    for ln in geoms:
        if ln.geom_type == "LineString":
            v.polyline(list(ln.coords), lw=lw, color=col, dash=dash)
        elif ln.geom_type in ("MultiLineString", "GeometryCollection"):
            draw_geom_lines(v, ln, lw, col, dash)


def fmt_ft(L):
    return f"{L:.1f}'" if abs(L - round(L)) > 0.05 else f"{L:.0f}'"


# ========================================================================================
# 5. PLAN LAYERS
# ========================================================================================
def _curb_quadrant(xb, yb, sx, sy, R):
    """polyline of a curb line around the block corner (xb, yb); sx/sy = direction from the
    corner into the block (+1/-1). Horizontal leg runs away in -sx, vertical in +sy."""
    cx, cy = xb - sx * R, yb + sy * R
    pts = [(xb - sx * FAR, yb)]
    a0 = math.degrees(math.atan2(yb - cy, xb - sx * R - cx)) if False else None
    n = 16
    for k in range(n + 1):
        t = k / n
        # angle from pointing at the horizontal tangent to pointing at the vertical tangent
        ang0 = math.atan2(-sy, 0.0)
        ang1 = math.atan2(0.0, sx)
        # shortest sweep
        da = (ang1 - ang0 + math.pi) % (2 * math.pi) - math.pi
        a = ang0 + da * t
        pts.append((cx + R * math.cos(a), cy + R * math.sin(a)))
    pts.append((xb, yb + sy * FAR))
    return pts


def draw_streets(v: View, col=SCR, labels=True, p_lw="med"):
    """ROW, curb & gutter, sidewalks, centerlines, property line"""
    # curb lines for the 4 quadrants around the intersection
    quads = [(MP["boc_w"], PR["boc_n"], 1, 1, MP["eop_w"], PR["eop_n"]),      # NW block
             (MP["boc_e"], PR["boc_n"], -1, 1, MP["eop_e"], PR["eop_n"]),     # NE
             (MP["boc_w"], PR["boc_s"], 1, -1, MP["eop_w"], PR["eop_s"]),     # SW
             (MP["boc_e"], PR["boc_s"], -1, -1, MP["eop_e"], PR["eop_s"])]    # SE
    for xb, yb, sx, sy, xe, ye in quads:
        boc = _curb_quadrant(xb, yb, sx, sy, R_RET)
        cx, cy = xb - sx * R_RET, yb + sy * R_RET
        eop = _curb_quadrant(xe, ye, sx, sy, R_RET + 1.5)
        # shift eop so its arc shares the center
        eop = [(q[0], q[1]) for q in eop]
        if (xb, yb) == (MP["boc_w"], PR["boc_n"]):
            # break for the two drive aprons on Prairie Ave
            line = LineString(boc).difference(unary_union(
                [box(xc - DRIVE_W / 2 - 5, PR["boc_n"] - 1, xc + DRIVE_W / 2 + 5, PR["boc_n"] + 1)
                 for xc in EX_DRIVES]))
            draw_geom_lines(v, line, lw="thin", col=col)
            line = LineString(eop).difference(unary_union(
                [box(xc - DRIVE_W / 2 - 5, PR["eop_n"] - 1, xc + DRIVE_W / 2 + 5, PR["eop_n"] + 1)
                 for xc in EX_DRIVES]))
            draw_geom_lines(v, line, lw="fine", col=col)
            for xc in EX_DRIVES:
                for sg in (-1, 1):
                    x0 = xc + sg * DRIVE_W / 2
                    v.polyline([(x0 + sg * 5, PR["boc_n"]), (x0, PR["boc_n"] + 4.0)], lw="thin",
                               color=col)
        else:
            v.polyline(boc, lw="thin", color=col)
            v.polyline(eop, lw="fine", color=col)
    # centerlines
    v.line((-FAR, PR["cl"]), (MP["eop_w"] - 30, PR["cl"]), lw="fine", color=col, dash="center")
    v.line((MP["eop_e"] + 30, PR["cl"]), (FAR, PR["cl"]), lw="fine", color=col, dash="center")
    v.line((MP["cl"], PR["eop_n"] + 30), (MP["cl"], FAR), lw="fine", color=col, dash="center")
    v.line((MP["cl"], -FAR), (MP["cl"], PR["eop_s"] - 30), lw="fine", color=col, dash="center")
    # sidewalks (public)
    walks = [SIDEWALK_PR, SIDEWALK_MP, box(-FAR, PR["sw_s"][0], MP["sw_w"][1], PR["sw_s"][1]),
             box(MP["sw_e"][0], -FAR, MP["sw_e"][1], PR["sw_s"][1]),
             box(MP["sw_e"][0], PR["sw_n"][0], MP["sw_e"][1], FAR),
             box(MP["sw_w"][0], -FAR, MP["sw_w"][1], PR["sw_s"][1]),
             box(MP["sw_e"][0], PR["sw_s"][0], FAR, PR["sw_s"][1]),
             box(MP["sw_e"][0], PR["sw_n"][0], FAR, PR["sw_n"][1])]
    g = unary_union(walks)
    v.geom(g, lw="fine", color=col)
    # crosswalks (existing striping)
    for (x0, y0, x1, y1) in ((244, PR["eop_s"], 254, PR["eop_n"]), (MP["eop_w"], -148, MP["eop_e"], -138)):
        v.rect(x0, y0, x1 - x0, y1 - y0, lw="fine", color=col, dash="dashed")
    # right-of-way lines
    for yy in (PR["row_n"], PR["row_s"]):
        v.line((-FAR, yy), (FAR, yy), lw="fine", color=col, dash="phantom")
    for xx in (MP["row_w"], MP["row_e"]):
        v.line((xx, -FAR), (xx, FAR), lw="fine", color=col, dash="phantom")
    # property line (heavy)
    v.polyline(ring_pts(PROPERTY), lw=p_lw, dash="property")


def street_labels(v: View, x_pr=-20.0, y_mp=180.0):
    p = Paper(v.c)
    px, py = v.to_paper((x_pr, PR["cl"] - 7.5))
    ptext(p, (px, py), "PRAIRIE AVENUE", TXT["sub"], FONT_B, "c", "mid", 0, "black", True)
    ptext(p, (px, py - 0.17), "(66' R.O.W., 40' F-F, PUBLIC)", SM, FONT, "c", "mid", 0, EXC, True)
    px, py = v.to_paper((MP["cl"] + 8.0, y_mp))
    ptext(p, (px, py), "MAPLE STREET", TXT["sub"], FONT_B, "c", "mid", 90, "black", True)
    ptext(p, (px + 0.17, py), "(66' R.O.W., 37' F-F, PUBLIC)", SM, FONT, "c", "mid", 90, EXC, True)


def draw_existing_site(v: View, col=SCR, show_stalls=True, labels=True, lot_labels=True,
                       building_label=True, tie_door=True, trees="all", lights=True,
                       walk_d=True, rcp=True, playground_label=True):
    # pavements
    v.geom(EX_PAVE, lw="thin", color=col, fill="g05")
    v.line((ROW_X0, -80.0), (ROW_X1, -80.0), lw="thin", color=col)        # bus lane curb
    if show_stalls:
        for a, b in STALL_SEGS:
            v.line(a, b, lw="fine", color=col)
        for x0, x1, k in ACC_STALLS:
            v.rect(x0, -97.0, x1 - x0, 17.0, lw="fine", color=col)
        v.rect(-192.0, -97.0, 8.0, 17.0, lw=None, hatch="ansi31",
               hatch_kw=dict(spacing=0.03, col=col, w="hair"))
    for xc in EX_DRIVES:
        for s in (-1, 1):
            v.line((xc + s * DRIVE_W / 2, -135.0), (xc + s * DRIVE_W / 2, PR["boc_n"] + 4.0),
                   lw="thin", color=col)
    # walks
    walks = [EX_WALK_A, EX_WALK_C, EX_WALK_N] + ([EX_WALK_D] if walk_d else [])
    v.geom(unary_union(walks), lw="fine", color=col, fill="g05")
    # building
    v.geom(EXB, lw="med", color=col, fill="g10")
    v.geom(EX_CANOPY, lw="fine", color=col, dash="hidden")
    for x in (-199.0, -171.0):
        v.rect(x - 0.6, -67.6, 1.2, 1.2, lw="fine", color=col, fill=col)
    v.geom(EX_XFMR, lw="fine", color=col, fill="g10")
    # playground
    v.geom(PLAYGROUND, lw="fine", color=col)
    mark_line(v, ring_pts(PLAYGROUND), "x", every=0.22, size=0.022, col=col)
    for g, nm in PLAY_ITEMS:
        v.geom(g, lw="fine", color=col, dash="dashed")
    # misc
    if lights:
        for x, y, k in LIGHT_POLES:
            sym_light(v, x, y, col)
    for x, y in UPOLES:
        sym_upole(v, x, y, col)
    for a, b in zip(UPOLES[:-1], UPOLES[1:]):
        v.line(a, b, lw="fine", color=col, dash="dashed")
    p = Paper(v.c)
    fx, fy = v.to_paper(FLAGPOLE)
    p.circle((fx, fy), 0.02, lw="fine", color=col, fill="white")
    sx, sy = v.to_paper(SCHOOL_SIGN)
    p.rect(sx - 0.08, sy - 0.015, 0.16, 0.03, lw="fine", color=col, fill="white")
    # fences: north & west property (existing 6' chain link)
    mark_line(v, [(PL_W + 1, PR["row_n"] + 12), (PL_W + 1, PL_N - 1), (PL_E - 1, PL_N - 1)],
              "x", every=0.3, size=0.02, col=col)
    # trees
    for x, y, d, k in TREES_BG:
        tree_sym(v, x, y, d, k, col)
    if labels:
        bx, by = v.to_paper((-178, 30))
        if building_label:
            plines(p, v.to_paper((-178.0, 110.0)), ["EXISTING 1-STORY SCHOOL (OCCUPIED)",
                                                    "38,600 SF   FFE 712.50"],
                   NT, FONT_B, "c", "mid", EXC, True)
        for g in EXB_COURTS:
            c = g.centroid
            ptext(p, v.to_paper((c.x, c.y)), "COURTYARD", TY + 0.5, FONT, "c", "mid", 90, EXC, False)
        if lot_labels:
            plines(p, v.to_paper((-187.0, -108.0)),
                   [f"EXISTING PARKING LOT ({N_STALLS} STALLS INCL. {N_ACC} ACCESSIBLE)"],
                   SM, FONT, "c", "mid", EXC, True)
            ptext(p, v.to_paper((-187.0, -74.0)), "EX. BUS DROP-OFF LANE (ONE-WAY EASTBOUND)",
                  SM, FONT, "c", "mid", 0, EXC, True)
            ptext(p, v.to_paper((-232.0, -64.0)), "EX. 8' PCC DROP-OFF WALK", TY + 0.5, FONT,
                  "c", "mid", 0, EXC, True)
            for xc in EX_DRIVES:
                ptext(p, v.to_paper((xc, -143.0)), "EX. DRIVE", TY + 0.5, FONT, "c", "mid", 90,
                      EXC, True)
            ptext(p, v.to_paper((-185.0, -64.0)), "EX. CANOPY", TY + 0.3, FONT, "c", "mid", 0,
                  EXC, True)
        if playground_label:
            plines(p, v.to_paper((70.0, 207.0)), ["EXISTING PLAYGROUND (TO REMAIN - PROTECT)"],
                   SM, FONT_B, "c", "mid", EXC, True)


def draw_existing_utils(v: View, col=SCR, labels=True, rcp=True, keep_inv=False):
    p = Paper(v.c)
    lw_ = "thin"
    # water
    tagged_line(v, [(WM_X, -FAR), (WM_X, FAR)], "W", lw_, col, every=1.6, first=0.9)
    tagged_line(v, EX_WATER_SVC, "W", "fine", col, every=1.8)
    for x, y, nm in HYDRANTS:
        v.line((WM_X, y), (x, y), lw="fine", color=col)
        sym_hydrant(v, x, y, col)
        sym_valve(v, x + 5.0, y, col, 0.03)
    for x, y in EX_VALVES:
        sym_valve(v, x, y, col, 0.035, 90)
    # sanitary
    tagged_line(v, [(-FAR, SAN_Y), (MP["cl"], SAN_Y)], "SAN", lw_, col, every=1.8, first=1.0)
    tagged_line(v, EX_SAN_SVC, "SAN", "fine", col, every=1.6)
    # storm
    tagged_line(v, [(STM_X, PRSTM_Y), (STM_X, FAR)], "ST", lw_, col, every=1.6, first=0.6)
    tagged_line(v, [(-FAR, PRSTM_Y), (FAR, PRSTM_Y)], "ST", lw_, col, every=1.9, first=1.3)
    for ln in EX_STORM_LEADS:
        v.polyline(ln, lw="fine", color=col)
    if rcp:
        tagged_line(v, EX_RCP_REMOVE, "ST", lw_, col, every=1.4)
    # gas / overhead electric
    tagged_line(v, [(GAS_X, -FAR), (GAS_X, FAR)], "G", "fine", col, every=1.6, first=1.2)
    for nm, s in EX_STR.items():
        if not rcp and nm in ("EX YI-1", "EX YI-2"):
            continue
        sym_structure(v, s["x"], s["y"], s["kind"], col)


# ========================================================================================
# 6. LEGEND helper
# ========================================================================================
def legend(sh, x, y, w, items, title="LEGEND", row=0.2, size=SM):
    """items: list of (draw_fn(v, x0, x1, ymid) in model units of a 1/30 view, label) or
    '##HEADER' strings. Returns height."""
    sh.text((x, y), title, size=TXT["label"], font=FONT_B, valign="top", underline=True)
    yy = y - 0.3
    for it in items:
        if isinstance(it, str):
            sh.text((x, yy - 0.02), it[2:], size=size, font=FONT_B, valign="mid")
            yy -= row * 0.95
            continue
        fn, label = it
        vv = sh.view(x, yy, SC)                # model (0,0) at the sample's left/middle
        fn(vv, 0.0, 0.58 / SC)
        sh.mtext((x + 0.72, yy + 0.005), label, size=size, valign="mid", width=w - 0.75)
        nl = len(wrap_lines([label], size, FONT, w - 0.75))
        yy -= row * (1 + 0.6 * (nl - 1))
    return y - yy


def L_line(lw="thin", col="black", dash=None):
    return lambda v, a, b: v.line((a, 0), (b, 0), lw=lw, color=col, dash=dash)


def L_tag(tag, lw="thin", col="black", dash=None):
    return lambda v, a, b: tagged_line(v, [(a, 0), (b, 0)], tag, lw, col, dash, every=0.6,
                                       first=0.29)


def L_mark(mark, col="black", lw="fine", every=0.12, line_lw=None, dash=None):
    return lambda v, a, b: mark_line(v, [(a, 0), (b, 0)], mark, every, 0.022, lw, col, dash,
                                     line_lw)


def L_box(fill=None, hatch=None, hatch_kw=None, col="black", lw="thin", dash=None):
    def f(v, a, b):
        h = 0.11 / SC
        v.rect(a, -h / 2, b - a, h, lw=lw, color=col, fill=fill, hatch=hatch, hatch_kw=hatch_kw,
               dash=dash)
    return f


def L_sym(fn, *args, **kw):
    return lambda v, a, b: fn(v, (a + b) / 2, 0.0, *args, **kw)


def L_tree(remove=False, kind="D", col=SCR):
    return lambda v, a, b: tree_sym(v, (a + b) / 2, 0, 6.5, kind, col, remove=remove)


# ========================================================================================
# 7. SHEET LAYOUT HELPERS
# ========================================================================================
FULL = dict(x0=-430.0, x1=330.0, y0=-222.0, y1=268.0)


def plan_frame(sh, win, scale, left, top):
    """returns (view, paper rect) for a plan window placed with its top-left at (left, top)"""
    w = (win["x1"] - win["x0"]) * scale
    h = (win["y1"] - win["y0"]) * scale
    ox = left - win["x0"] * scale
    oy = top - win["y1"] * scale
    v = sh.view(ox, oy, scale)
    return v, (left, top - h, left + w, top)


def title_block_plan(sh, rect, num, title, scale, na_dx=None):
    x0, y0, x1, y1 = rect
    ty = y0 - 0.5
    sh.view_title(x0 + 0.1, ty, num, title, scale, width=7.4)
    na = x0 + 8.4 if na_dx is None else x0 + na_dx
    sh.north_arrow(na, ty + 0.0, 0.4)
    scale_bar(sh, na + 0.7, ty - 0.02, scale, 120 if scale == SC else 80, 4)
    sh.text((na + 0.7, ty - 0.12), "GRAPHIC SCALE (FEET)  " +
            ("1 INCH = 30 FT" if scale == SC else "1 INCH = 20 FT"), size=TY, valign="top")
    sh.text((na + 5.1 if scale == SC else na + 3.9, ty + 0.05), DATUM_NOTE, size=SM, font=FONT_B,
            valign="mid")
    return ty


def panel_rule(sh, x0, x1, y):
    sh.line((x0, y), (x1, y), lw="thin")


def vrule(sh, x, y0, y1):
    sh.line((x, y0), (x, y1), lw="thin")


# ========================================================================================
# 8. C-100  EXISTING CONDITIONS & SITE DEMOLITION PLAN
# ========================================================================================
DEMO_KEYNOTES = [
    ("D1", "SAWCUT AND REMOVE EXISTING 6' PCC WALK (MAPLE ST. TO EXIST. EAST CORRIDOR DOOR), "
           "INCL. AGGREGATE BASE. LENGTH 292 LF (1,752 SF)."),
    ("D2", "REMOVE EXISTING TREE INCLUDING STUMP AND ROOTS TO 18\" BELOW GRADE. SEE TREE SCHEDULE."),
    ("D3", "REMOVE EXISTING 12\" RCP STORM SEWER (FULL LENGTH FROM EX YI-1 TO EX ST-3) AND "
           "BACKFILL TRENCH PER 9/C-500."),
    ("D4", "REMOVE EXISTING YARD INLET AND FRAME/GRATE. NEW CB-1 REPLACES EX YI-1 (SEE C-400)."),
    ("D5", "PLUG 12\" OPENING IN EX ST-3 WITH BRICK & NON-SHRINK GROUT, BOTH FACES. "
           "WORK FROM INSIDE STRUCTURE, NO PAVEMENT REMOVAL."),
    ("D6", "REMOVE EXISTING LIGHT POLE AND FOUNDATION; SALVAGE POLE & FIXTURE TO OWNER. "
           "DIV. 26 TO MAKE CIRCUIT SAFE (NOT IN THIS SET)."),
    ("D7", "SAWCUT FULL DEPTH AND REMOVE HMA PAVEMENT FOR UTILITY CONNECTION. PATCH PER 3/C-500."),
    ("D8", "REMOVE PUBLIC SIDEWALK (AND CURB & GUTTER WHERE SHOWN) TO NEAREST JOINT. REPLACE PER C-200."),
    ("D9", "REMOVE EXISTING NON-COMPLIANT CURB RAMPS (2) AND CORNER WALK; REPLACE PER C-200 "
           "(CITY PERMIT CONDITION)."),
    ("D10", "EXISTING EAST WALL OF SCHOOL AT LINK TIE-IN: BUILDING DEMOLITION BY ARCHITECTURAL, "
            "SEE AD101. TIE-IN ONLY DURING SUMMER RECESS (JUNE 7 - AUG. 13, 2027)."),
    ("D11", "STRIP AND STOCKPILE TOPSOIL (6\" AVG.) WITHIN THE LIMIT OF WORK, SEE C-300."),
    ("D12", "EXISTING FEATURE TO REMAIN. PROTECT IN PLACE; REPAIR DAMAGE AT CONTRACTOR'S EXPENSE."),
]

DEMO_NOTES = [
    "THE EXISTING CONDITIONS SHOWN ARE BASED ON A TOPOGRAPHIC SURVEY (PRACTICE, FICTIONAL) "
    "SUPPLEMENTED WITH RECORD DRAWINGS. CONTRACTOR SHALL VERIFY ALL CONDITIONS BEFORE BIDDING.",
    "CALL JULIE (811 / 1-800-892-0123) AT LEAST 48 HOURS (2 WORKING DAYS) BEFORE ANY EXCAVATION. "
    "PRIVATE UTILITIES ON SCHOOL PROPERTY ARE NOT LOCATED BY JULIE; OWNER'S PRIVATE LOCATOR REQUIRED.",
    "THE SCHOOL REMAINS OCCUPIED. MAINTAIN THE BUS LOOP, PARKING LOT, DRIVES, WALKS, EXITS AND "
    "FIRE DEPARTMENT ACCESS TO THE EXISTING BUILDING AT ALL TIMES. NO WORK OR STAGING OUTSIDE THE LIMIT OF WORK.",
    "CONSTRUCTION ACCESS IS FROM MAPLE STREET ONLY THROUGH THE STABILIZED CONSTRUCTION ENTRANCE "
    "SHOWN ON C-300. NO CONTRACTOR USE OF THE PRAIRIE AVE. DRIVES, BUS LOOP OR PARKING LOT.",
    "SAWCUT EXISTING PAVEMENT, CURB AND WALK FULL DEPTH AT REMOVAL LIMITS TO A NEAT LINE; "
    "REMOVE WALKS TO THE NEAREST JOINT.",
    "REMOVED MATERIALS BECOME THE PROPERTY OF THE CONTRACTOR AND SHALL BE LEGALLY DISPOSED OF OFF SITE "
    "UNLESS NOTED AS SALVAGED TO OWNER. NO BURNING OR BURYING ON SITE.",
    "EXISTING UTILITIES NOT SHOWN TO BE REMOVED REMAIN IN SERVICE. NOTIFY OWNER 72 HOURS BEFORE "
    "ANY SHUTDOWN; SHUTDOWNS ONLY OUTSIDE SCHOOL HOURS.",
    "INSTALL TREE PROTECTION, SILT FENCE AND INLET PROTECTION (C-300) BEFORE DEMOLITION OR "
    "EARTHWORK BEGINS.",
    "WORK IN THE PUBLIC RIGHT-OF-WAY REQUIRES A CITY OF CEDAR PRAIRIE R.O.W. PERMIT; PROVIDE "
    "TRAFFIC CONTROL PER IDOT STANDARDS 701201 / 701301 AND THE MUTCD.",
]


def _demo_items(v: View):
    """demolition graphics: X-hatch removals, X'd trees, removed pipes / structures"""
    hk = dict(spacing=0.045, w="fine")
    v.geom(EX_WALK_D, lw="thin", hatch="ansi37", hatch_kw=hk)
    for g in PUB_WALK_REPL + CURB_REPL:
        v.geom(g, lw="thin", hatch="ansi37", hatch_kw=hk)
    for g in (PATCH_WATER, PATCH_STORM, PATCH_SAN):
        v.geom(g, lw="thin", dash="dashed", hatch="ansi37", hatch_kw=hk)
    # corner curb ramps to remove
    ramp_g = box(MP["sw_w"][0] - 14, PR["sw_n"][0] - 9, MP["boc_w"] + 0.5, PR["sw_n"][1] + 12)
    corner = ramp_g.difference(box(-FAR, -FAR, FAR, PR["boc_n"] - 0.01).difference(
        box(0, -FAR, MP["boc_w"] - R_RET, FAR)))
    # (draw a simple hatched patch at the corner landing)
    corner = Polygon([(244, -156), (261, -156), (261, -141), (267.5, -141), (266.2, -149.0),
                      (262.5, -155.2), (256.2, -159.6), (248.5, -161.6), (244, -161.6)])
    v.geom(corner, lw="thin", hatch="ansi37", hatch_kw=hk)
    # pipe to remove: heavy dashed with slashes
    pts = EX_RCP_REMOVE
    v.polyline(pts, lw="heavy", dash="demo")
    segs, tot = path_points(v, pts)
    p = Paper(v.c)
    s = 0.25
    while s < tot - 0.1:
        q, ang = _at(segs, s)
        a = math.radians(ang + 60)
        d = 0.045
        p.line((q[0] - math.cos(a) * d, q[1] - math.sin(a) * d),
               (q[0] + math.cos(a) * d, q[1] + math.sin(a) * d), lw="thin")
        p.line((q[0] - math.cos(a) * d + 0.025 * math.cos(math.radians(ang)),
                q[1] - math.sin(a) * d + 0.025 * math.sin(math.radians(ang))),
               (q[0] + math.cos(a) * d + 0.025 * math.cos(math.radians(ang)),
                q[1] + math.sin(a) * d + 0.025 * math.sin(math.radians(ang))), lw="thin")
        s += 0.42
    for nm in ("EX YI-1", "EX YI-2"):
        s_ = EX_STR[nm]
        px, py = v.to_paper((s_["x"], s_["y"]))
        d = 0.09
        p.line((px - d, py - d), (px + d, py + d), lw="med")
        p.line((px - d, py + d), (px + d, py - d), lw="med")
    # light pole to remove
    for x, y, k in LIGHT_POLES:
        if k == "R":
            px, py = v.to_paper((x, y))
            d = 0.07
            p.line((px - d, py - d), (px + d, py + d), lw="med")
            p.line((px - d, py + d), (px + d, py - d), lw="med")


def _limit_of_work(v: View, g=None, lw="heavy"):
    g = LOW_ALL if g is None else g
    geoms = g.geoms if hasattr(g, "geoms") else [g]
    for q in geoms:
        v.polyline(ring_pts(q), lw=lw, dash=[9, 3, 2, 3])


def _low_labels(v: View, at_list):
    p = Paper(v.c)
    for (x, y, rot) in at_list:
        ptext(p, v.to_paper((x, y)), "LIMIT OF WORK", TY + 0.6, FONT_B, "c", "mid", rot, "black",
              True)


def draw_c100(sh):
    left, top = sh.x0 + 0.15, sh.y1 - 0.1
    v, rect = plan_frame(sh, FULL, SC, left, top)
    x0, y0, x1, y1 = rect
    with Clip(sh, x0, y0, x1, y1):
        ec = existing_contours(FULL)
        for z, g in ec.items():
            idx = (z % 5 == 0)
            draw_geom_lines(v, g, lw="thin" if idx else "fine", col=SCR, dash="dashed")
        for z, g in ec.items():
            contour_label(v, g, z, EXC, every=7.0, min_len=2.0)
        draw_streets(v)
        draw_existing_site(v)
        draw_existing_utils(v)
        for tid, x, y, d, sp, disp in TREES:
            tree_sym(v, x, y, d, "E" if sp in ("NORWAY SPRUCE", "WHITE PINE") else "D",
                     col="black" if disp == "R" else SCR, lw="thin" if disp == "R" else "fine",
                     remove=(disp == "R"))
        _demo_items(v)
        _limit_of_work(v)
        _c100_labels(v)
        street_labels(v, x_pr=-200.0, y_mp=200.0)
    ty = title_block_plan(sh, rect, 1, "EXISTING CONDITIONS & SITE DEMOLITION PLAN", SC)
    _c100_panels(sh, rect, ty)


def _c100_labels(v: View):
    p = Paper(v.c)
    # existing utilities
    callout(v, (WM_X, 215.0), (300.0, 228.0), ["EX. 8\" DIP WATER MAIN"], SM, EXC)
    callout(v, (STM_X, 150.0), (300.0, 150.0), ["EX. 12\" RCP STORM"], SM, EXC)
    callout(v, (GAS_X, 60.0), (318.0, 40.0), ["EX. 4\" GAS", "(NICOR)"], SM, EXC, side="l")
    callout(v, (-250.0, SAN_Y), (-262.0, -194.0), ["EX. 8\" PVC SANITARY"], SM, EXC, side="l")
    callout(v, (-320.0, PRSTM_Y), (-330.0, -209.0), ["EX. 15\" RCP STORM"], SM, EXC, side="l")
    callout(v, (-160.0, -159.0), (-150.0, -172.0), ["EX. OVERHEAD ELECTRIC (ComEd)"], SM, EXC,
            side="r")
    callout(v, (-60.0, 190.0), (-50.0, 200.0), ["EX. 4\" WATER SERVICE", "TO SCHOOL"], SM, EXC,
            arrow="arrow", side="r")
    callout(v, (-140.0, -100.0), (-122.0, -97.0), ["EX. 6\" SAN. SERVICE"], TY + 0.6, EXC)
    # structures with rims / inverts
    st_lab = {
        "EX ST-1": (300.0, 197.0), "EX ST-2": (300.0, 103.0), "EX ST-3": (300.0, -54.0),
        "EX SAN-3": (100.0, -196.0), "EX SAN-2": (-118.0, -196.0), "EX YI-1": (-60.0, 98.0),
        "EX YI-2": (104.0, 66.0), "EX CB-2": (-118.0, -112.0),
    }
    for nm, at in st_lab.items():
        s = EX_STR[nm]
        lines = [nm.replace("EX ", "EX. ") + f"  RIM {ex_rim(nm):.2f}"]
        for d, size, inv in s["inv"]:
            lines.append(f"INV {size}\" {d} {inv:.2f}")
        callout(v, (s["x"], s["y"]), at, lines, TY + 0.5, EXC,
                side="l" if at[0] < s["x"] else "r")
    for x, y, nm in HYDRANTS:
        ptext(p, v.to_paper((x - 4.0, y + 5.0)), nm, TY + 0.5, FONT, "r", "mid", 0, EXC, True)
    # benchmark
    bm = (246.0, PR["boc_n"] + 0.5)
    spot(v, bm[0], bm[1], "BM-1", col="black", marker="dot", dx=-0.04, anchor="r", font=FONT_B)
    # spot elevations (existing ground)
    for (x, y) in [(-0.95, -0.95), (150.95, -0.95), (150.95, 72.95), (-0.95, 72.95), (75, 36),
                   (210, 10), (210, 90), (120, -60), (20, -60), (-20, 60), (60, 105),
                   (230, -120), (-80, 100), (-90, 0), (-90, -60.5)]:
        spot(v, x, y, round(E1(x, y), 2), col=EXC)
    for x in (-30.0, 120.0, 220.0):
        spot(v, x, PR["boc_n"] + 0.3, f"TC {E1(x, PR['boc_n']):.2f}", col=EXC, dy=0.05)
    for y in (-60.0, 60.0, 180.0):
        spot(v, MP["boc_w"] - 0.3, y, f"TC {E1(MP['boc_w'], y):.2f}", col=EXC, anchor="r", dy=0.05)
    spot(v, -185.0, -58.5, "FFE 712.50", col=EXC, marker="dot", dy=0.06)
    spot(v, -37.0, 36.0, "FFE 712.50", col=EXC, marker="dot", anchor="r", dy=0.06)
    # demolition keynotes on plan
    key_tag(v, (100.0, 36.0), (100.0, 25.0), "D1")
    key_tag(v, (225.0, 36.0), (225.0, 25.0), "D1")
    for tid, x, y, d, sp, disp in TREES:
        if disp == "R":
            ptext(p, v.to_paper((x, y + d * 0.85 + 2.5)), tid, TY + 0.6, FONT_B, "c", "mid", 0,
                  "black", True)
        else:
            ptext(p, v.to_paper((x, y - d * 0.85 - 3.0)), tid, TY + 0.6, FONT, "c", "mid", 0, EXC,
                  True)
    key_tag(v, (22.0, 52.0), (10.0, 62.0), "D2", arrow="dot")
    key_tag(v, (118.0, 58.0), (135.0, 62.0), "D2", arrow="dot")
    key_tag(v, (182.0, 46.0), (196.0, 56.0), "D2", arrow="dot")
    key_tag(v, (152.0, 22.0), (160.0, 12.0), "D3")
    key_tag(v, (-14.0, 90.0), (-28.0, 100.0), "D4", arrow="dot")
    key_tag(v, (75.0, 49.5), (88.0, 56.0), "D4", arrow="dot")
    key_tag(v, (STM_X, -40.0), (288.0, -28.0), "D5")
    key_tag(v, (60.0, 41.0), (52.0, 28.0), "D6")
    key_tag(v, (276.0, -13.0), (296.0, -12.0), "D7")
    key_tag(v, (273.5, 90.0), (290.0, 82.0), "D7")
    key_tag(v, (72.0, -175.0), (100.0, -172.0), "D7")
    key_tag(v, (258.5, 68.0), (243.0, 70.0), "D8")
    key_tag(v, (258.5, 36.0), (243.0, 24.0), "D8")
    key_tag(v, (255.0, -153.0), (234.0, -146.0), "D9")
    key_tag(v, (-36.0, 36.0), (-50.0, 36.0), "D10")
    key_tag(v, (100.0, 0.0), (100.0, -12.0), "D11", arrow="dot")
    key_tag(v, (40.0, 150.0), (40.0, 125.0), "D12", arrow="dot")
    key_tag(v, (152.0, 152.0), (175.0, 165.0), "D12", arrow="dot")
    key_tag(v, (222.0, -98.0), (200.0, -112.0), "D12", arrow="dot")
    key_tag(v, (190.0, 43.0), (205.0, 50.0), "D12")
    # LOW labels
    _low_labels(v, [(120.0, 104.0, 0), (130.0, -34.0, 0), (PL_E, 10.0, 90), (92.0, -100.0, 90)])
    # property line labels
    ptext(p, v.to_paper((-300.0, PL_N)), "PROPERTY LINE", SM, FONT_B, "c", "mid", 0, "black", True)
    ptext(p, v.to_paper((PL_W, 60.0)), "PROPERTY LINE", SM, FONT_B, "c", "mid", 90, "black", True)
    ptext(p, v.to_paper((-330.0, PR["row_n"])), "PROPERTY LINE / NORTH R.O.W. LINE", TY + 0.6,
          FONT_B, "c", "mid", 0, "black", True)
    ptext(p, v.to_paper((PL_E, 205.0)), "PROPERTY LINE / WEST R.O.W. LINE", TY + 0.6, FONT_B,
          "c", "mid", 90, "black", True)
    plines(p, v.to_paper((72.0, 30.0)), ["**FUTURE ADDITION**", "(FOOTPRINT SHOWN FOR",
                                        "REFERENCE ONLY)"], TY + 0.6, FONT, "c", "mid", "black",
           True)
    plines(p, v.to_paper((-200.0, 150.0)), ["NORTH PLAY FIELD (NO WORK)"], SM, FONT, "c", "mid",
           EXC, True)


def _footprint_ref(v: View):
    v.geom(NEW_BLDG, lw="thin", dash="hidden")


def _c100_panels(sh, rect, ty):
    x0, y0, x1, y1 = rect
    # right column
    cx = x1 + 0.3
    cw = sh.x1 - cx - 0.1
    vrule(sh, x1 + 0.15, sh.y0, sh.y1)
    items = [
        "##BOUNDARY / RIGHT-OF-WAY",
        (L_line("med", "black", "property"), "PROPERTY LINE"),
        (L_line("fine", SCR, "phantom"), "RIGHT-OF-WAY LINE"),
        (L_line("fine", SCR, "center"), "STREET CENTERLINE"),
        (lambda v, a, b: [v.line((a, -1.5), (b, -1.5), lw="thin", color=SCR),
                          v.line((a, 1.5), (b, 1.5), lw="fine", color=SCR)],
         "EXISTING CURB & GUTTER"),
        "##EXISTING FEATURES",
        (L_box(fill="g10", col=SCR), "EXISTING BUILDING"),
        (L_box(fill="g05", col=SCR, lw="fine"), "EXISTING PAVEMENT / WALK"),
        (L_line("fine", SCR, "dashed"), "EXISTING 1' CONTOUR (5' INDEX HEAVIER)"),
        (lambda v, a, b: spot(v, a + 2, 0, "711.45", col=EXC), "EXISTING SPOT ELEVATION"),
        (L_tag("W", "thin", SCR), "EXISTING WATER MAIN / SERVICE"),
        (L_tag("SAN", "thin", SCR), "EXISTING SANITARY SEWER"),
        (L_tag("ST", "thin", SCR), "EXISTING STORM SEWER"),
        (L_tag("G", "fine", SCR), "EXISTING GAS MAIN (NICOR)"),
        (lambda v, a, b: [v.line((a, 0), (b, 0), lw="fine", color=SCR, dash="dashed"),
                          sym_upole(v, a + 2, 0, SCR), sym_upole(v, b - 2, 0, SCR)],
         "EXIST. OVERHEAD ELECTRIC / UTILITY POLE"),
        (L_mark("x", SCR), "EXISTING CHAIN LINK FENCE"),
        (lambda v, a, b: [sym_structure(v, a + 3, 0, "smh", SCR), sym_structure(v, a + 9, 0, "sanmh", SCR),
                          sym_structure(v, a + 15, 0, "cb", SCR)],
         "EX. STORM MH / SANITARY MH / CATCH BASIN"),
        (lambda v, a, b: [sym_structure(v, a + 3, 0, "ci", SCR), sym_structure(v, a + 9, 0, "yi", SCR),
                          sym_hydrant(v, a + 15, 0, SCR)],
         "EX. CURB INLET / YARD INLET / HYDRANT"),
        (lambda v, a, b: [sym_valve(v, a + 3, 0, SCR, 0.035), sym_light(v, a + 8, 0, SCR)],
         "EXISTING VALVE / LIGHT POLE"),
        (lambda v, a, b: [tree_sym(v, a + 5, 0, 6, "D", SCR), tree_sym(v, a + 14, 0, 6, "E", SCR)],
         "EXISTING DECIDUOUS / EVERGREEN TREE"),
        "##DEMOLITION / CONSTRUCTION LIMITS",
        (L_box(hatch="ansi37", hatch_kw=dict(spacing=0.045, w="fine")),
         "PAVEMENT, WALK OR CURB TO BE REMOVED"),
        (lambda v, a, b: tree_sym(v, (a + b) / 2, 0, 6.5, "D", "black", "thin", remove=True),
         "TREE TO BE REMOVED"),
        (lambda v, a, b: v.line((a, 0), (b, 0), lw="heavy", dash="demo"),
         "UTILITY TO BE REMOVED"),
        (lambda v, a, b: v.polyline([(a, -2), (b, -2)], lw="heavy", dash=[9, 3, 2, 3]),
         "LIMIT OF WORK (LOW)"),
        (lambda v, a, b: v.line((a, 0), (b, 0), lw="thin", dash="hidden"),
         "FUTURE ADDITION FOOTPRINT (REF.)"),
        (lambda v, a, b: key_tag(v, None, ((a + b) / 2, 0), "D1"), "DEMOLITION KEYNOTE"),
    ]
    h = legend(sh, cx, sh.y1 - 0.1, cw, items, "LEGEND", row=0.205)
    yy = sh.y1 - 0.1 - h - 0.25
    sh.line((x1 + 0.15, yy + 0.12), (sh.x1, yy + 0.12), lw="thin")
    yy -= 0.05
    bm = ["**BENCHMARKS (NAVD88)**",
          f"BM-1: CUT \"+\" ON TOP OF CURB, NW CORNER OF PRAIRIE",
          f"AVE. & MAPLE ST. (SHOWN).  EL. {E1(246.0, PR['boc_n']) + 0.5:.2f}",
          f"BM-2: TOP NUT OF HYDRANT H-1, MAPLE ST.  EL. {E1(265.0, 160.0) + 2.6:.2f}",
          "", "**HORIZONTAL DATUM**",
          "LOCAL SITE GRID: GRID 1 / GRID D OF THE ADDITION =",
          "N 10,000.00  E 10,000.00. PLAN NORTH = TRUE NORTH.",
          "", "**CIVIL / ARCHITECTURAL DATUM**",
          "ARCH. 100'-0\" = EL. 712.50 (NAVD88) = FFE OF THE",
          "EXISTING SCHOOL AND OF THE ADDITION."]
    sh.mtext((cx, yy), bm, size=NT, leading=NT * 1.25)
    # bottom band: notes | keynotes | tree schedule
    top = ty - 0.5
    sh.line((sh.x0, top + 0.15), (x1 + 0.15, top + 0.15), lw="thin")
    h = notes_block(sh, sh.x0 + 0.2, top, "DEMOLITION NOTES", DEMO_NOTES, 8.2)
    kx = sh.x0 + 8.8
    sh.text((kx, top), "DEMOLITION KEYNOTES", size=TXT["label"], font=FONT_B, valign="top",
            underline=True)
    yy = top - 0.27
    for k, t in DEMO_KEYNOTES:
        hex_tag(sh, (kx + 0.15, yy - 0.06), k)
        hh = sh.mtext((kx + 0.36, yy), t, size=NT, width=7.6, leading=NT * 1.22)
        yy -= max(hh, 0.14) + 0.06
    tx = kx + 8.3
    rows = []
    for tid, x, y, d, sp, disp in TREES:
        rows.append([tid, sp, f"{d}\"", "REMOVE" if disp == "R" else "PROTECT",
                     "IN FOOTPRINT / WORK AREA" if disp == "R" else
                     ("CITY PARKWAY TREE" if abs(x - 264.5) < 1 or abs(y + 159) < 1 else
                      "TREE PROTECTION FENCE")])
    table(sh, tx, top, [("TREE", 0.42), ("SPECIES", 1.2), ("DBH", 0.42), ("ACTION", 0.75),
                        ("REMARKS", 1.75)], rows, row_h=0.148, size=TY + 0.6,
          title="EXISTING TREE SCHEDULE", align=["c", "l", "c", "c", "l"])



# ========================================================================================
# 9. PROPOSED-WORK LAYERS (shared by C-200 / C-300 / C-400)
# ========================================================================================
def pave_union(kinds=None):
    return unary_union([pv["poly"] for pv in NEW_PAVE if kinds is None or pv["kind"] in kinds])


def draw_new_building(v: View, fill="g20", label=True, doors=True, lw="xheavy", size=NT):
    v.geom(NEW_BLDG, lw=lw, fill=fill)
    v.line((BX0, 29.05), (BX0, 42.95), lw="thin")            # link / addition joint
    p = Paper(v.c)
    if label:
        plines(p, v.to_paper((75.0, 40.0)), ["**PROPOSED TWO-STORY**", "**CLASSROOM ADDITION**",
                                            "FFE 712.50 (ARCH. 100'-0\")"], size, FONT, "c",
               "mid", "black", False)
        plines(p, v.to_paper((75.0, 22.0)), [f"LEVEL 1 = {M.gross_area('L1'):,.0f} GSF (INCL. LINK)"],
               TY + 0.6, FONT, "c", "mid", "black", False)
        ptext(p, v.to_paper((-18.0, 36.0)), "1-STORY LINK", TY + 0.5, FONT_B, "c", "mid", 0,
              "black", False)
    if doors:
        for nm, o in DOORS.items():
            ax = M.opening_axis(o)
            k = M.opening_line_coord(o)
            if ax == "x":                      # south wall door
                at, d = (o.c, BY0), (0, 1)
            else:
                at, d = (BX1 if k > 100 else BX0, o.c), ((-1, 0) if k > 100 else (1, 0))
            px, py = v.to_paper(at)
            s_ = 0.06
            tip = (px + d[0] * s_ * 1.4, py + d[1] * s_ * 1.4)
            p.polygon([tip, (px - d[1] * s_, py + d[0] * s_), (px + d[1] * s_, py - d[0] * s_)],
                      lw="fine", fill="black")


def door_labels(v: View, size=TY + 0.6):
    p = Paper(v.c)
    lab = {"ST1-B": ((-2.0, 33.0), "r", "EXIT ST1-B"), "ST2-B": ((152.5, 49.5), "l", "EXIT ST2-B"),
           "100B": ((152.5, 36.0), "l", "ENTRANCE SF-1"), "112": ((36.5, 3.0), "c", "DOOR 112")}
    for nm, (at, an, txt) in lab.items():
        ptext(p, v.to_paper(at), txt, size, FONT_B, an, "mid", 0, "black", True)


def draw_new_paving(v: View, hatch=True, col="black"):
    hk = dict(spacing=0.045, w="hair", col=col)
    for pv in NEW_PAVE:
        if hatch:
            conc(v, pv["poly"], col=col)
    g = pave_union()
    v.geom(g, lw="thin", color=col)
    # contraction joints (schematic) along walks
    for pv in NEW_PAVE:
        if pv["kind"] != "walk":
            continue
        x0, y0, x1, y1 = pv["poly"].bounds
        if (x1 - x0) > (y1 - y0):
            w = y1 - y0
            x = x0 + w
            while x < x1 - 0.5:
                v.line((x, y0), (x, y1), lw="hair", color=col)
                x += w
        else:
            w = x1 - x0
            y = y0 + w
            while y < y1 - 0.5:
                v.line((x0, y), (x1, y), lw="hair", color=col)
                y += w
    for x, y in BIKE_RACKS:
        v.polyline([(x, y - 1.5), (x, y + 1.5)], lw="thin", color=col)


def draw_public_work(v: View, demo=False):
    hk = dict(spacing=0.045, w="fine")
    for g in PUB_WALK_REPL:
        conc(v, g)
        v.geom(g, lw="thin")
    for g in CURB_REPL:
        v.geom(g, lw="thin", fill="g40")
    for g in (PATCH_WATER, PATCH_STORM, PATCH_SAN):
        v.geom(g, lw="thin", hatch="ansi37", hatch_kw=dict(spacing=0.035, w="hair"))
    # corner landing + two perpendicular curb ramps with detectable warnings
    land = Polygon([(244, -156), (261, -156), (261, -141), (267.5, -141), (266.2, -149.0),
                    (262.5, -155.2), (256.2, -159.6), (248.5, -161.6), (244, -161.6)])
    conc(v, land)
    v.geom(land, lw="thin")
    for dw in (box(246.0, -161.6, 252.0, -159.6), box(265.5, -147.0, 267.5, -141.0)):
        v.geom(dw, lw="fine", hatch="ansi37", hatch_kw=dict(spacing=0.02, w="hair"))


def restoration_geoms():
    onsite = LOW.intersection(PROPERTY)
    hard = unary_union([NEW_BLDG, pave_union()])
    sod = unary_union([NEW_BLDG.buffer(10.0, join_style=2), pave_union().buffer(3.0, join_style=2)])
    sod = sod.intersection(onsite).difference(hard)
    row_sod = unary_union([box(MP["sw_w"][1], 28.0, MP["boc_w"], 98.0),
                           box(MP["sw_w"][1], -23.0, MP["boc_w"], -4.0),
                           box(40.0, PR["sw_n"][1], 92.0, PR["row_n"]),
                           box(56.0, PR["boc_n"], 84.0, PR["sw_n"][0])]).difference(
        unary_union(PUB_WALK_REPL + [CONST_APRON.intersection(box(0, 0, 0, 0))]))
    seed = onsite.difference(hard).difference(sod)
    return sod, row_sod, seed


def draw_restoration(v: View):
    sod, row_sod, seed = restoration_geoms()
    for g in (sod, row_sod):
        v.geom(g, lw=None, hatch="sand", hatch_kw=dict(scale=1.9, col=Color(0.45, 0.45, 0.45)))


def draw_low_and_fence(v: View, fence=True, labels=True):
    _limit_of_work(v)
    if fence:
        g = LOW.intersection(PROPERTY)
        ring = LineString(ring_pts(g)).difference(EXB.buffer(1.5)).difference(
            CONST_ENT.buffer(0.5).intersection(box(PL_E - 1, 0, PL_E + 1, 200)))
        geoms = ring.geoms if hasattr(ring, "geoms") else [ring]
        for ln in geoms:
            pts = list(ln.coords)
            # draw the fence 1.5' inside the LOW so both lines read
            mark_line(v, pts, "x", every=0.2, size=0.02, lw="fine")


def draw_staging(v: View, label=True, size=SM):
    v.geom(STAGING, lw="thin", dash="dashed", hatch="ansi31",
           hatch_kw=dict(spacing=0.14, w="hair", col=Color(0.5, 0.5, 0.5)))
    if label:
        p = Paper(v.c)
        plines(p, v.to_paper((207.5, 15.0)),
               ["**OWNER-DESIGNATED**", "**CONTRACTOR STAGING**", f"**AREA ({STAGING.area:,.0f} SF)**",
                "TRAILERS, STORAGE, LAYDOWN", "& WORKER PARKING ONLY", "WITHIN THIS AREA"],
               size, FONT, "c", "mid", "black", True)


def access_arrow(v: View, size=SM):
    p = Paper(v.c)
    a = v.to_paper((300.0, 68.0))
    b = v.to_paper((262.0, 68.0))
    p.line(a, b, lw="xheavy")
    p.polygon([(b[0] - 0.02, b[1]), (b[0] + 0.12, b[1] + 0.06), (b[0] + 0.12, b[1] - 0.06)],
              lw="fine", fill="black")
    plines(p, (a[0] - 0.02, a[1] + 0.2), ["**CONSTRUCTION ACCESS**", "**FROM MAPLE ST. ONLY**"],
           size, FONT, "c", "mid", "black", True)


def owner_constraint_label(v: View, at=(-187.0, -112.0), size=SM):
    p = Paper(v.c)
    plines(p, v.to_paper(at), ["**EXISTING BUS LOOP, PARKING LOT AND PRAIRIE AVE. DRIVES**",
                               "**REMAIN IN SCHOOL USE - NO CONTRACTOR ACCESS, PARKING,**",
                               "**STAGING OR DELIVERIES**"], size, FONT, "c", "mid", "black", True)


def ddim(v, p1, p2, off, text=None, size=TY + 0.6):
    L = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
    v.dim(p1, p2, off, text=text or fmt_ft(L), size=size)


# ========================================================================================
# 10. C-200 SITE LAYOUT & PAVING PLAN
# ========================================================================================
C200_KEYS = [
    ("1", "5\" PCC SIDEWALK, WIDTH AS DIMENSIONED. 1.5% CROSS SLOPE (2% MAX.), 5% MAX. RUNNING "
          "SLOPE. CONTRACTION JOINTS AT SPACING = WALK WIDTH. SEE 1/C-500."),
    ("2", "6\" PCC STOOP WITH THICKENED EDGE AT EXIT ST1-B (5'-0\" x 8'-0\"). TOP OF STOOP 712.46 "
          "(1/2\" BELOW FFE), 1% SLOPE AWAY. SEE 4/C-500."),
    ("3", "6\" PCC ENTRY PLAZA AT ENTRANCE SF-1 / EXIT ST2-B (14'-0\" x 26'-0\"), 1% SLOPE AWAY. "
          "SEE 4/C-500."),
    ("4", "6\" PCC SERVICE APRON AT MECH./ELEC. 112 PAIR DOOR (12'-0\" x 10'-0\"), 1.5% SLOPE "
          "AWAY. SEE 4/C-500."),
    ("5", "6\" PCC BIKE RACK PAD (12'-0\" x 8'-0\") WITH (5) SURFACE-MOUNTED GALV. INVERTED-U "
          "RACKS AT 2'-9\" O.C. (10 BIKES)."),
    ("6", "PERPENDICULAR CURB RAMPS (2) WITH CAST-IN-PLACE DETECTABLE WARNINGS AND CORNER "
          "LANDING (CITY PERMIT CONDITION). SEE 5/C-500."),
    ("7", "REMOVE AND REPLACE PUBLIC SIDEWALK, 5\" PCC (6\" ACROSS THE CONSTRUCTION ENTRANCE). "
          "MATCH EXISTING JOINTS AND GRADES."),
    ("8", "REPLACE COMBINATION CONCRETE CURB & GUTTER, IDOT TYPE B-6.12, AT THE TEMPORARY "
          "CONSTRUCTION ENTRANCE. SEE 2/C-500."),
    ("9", "HMA PAVEMENT PATCH AT UTILITY CONNECTION (SEE C-400). SEE 3/C-500."),
    ("10", "8\" EXPOSED CONCRETE CURB UNDER LINK STOREFRONT SF-3 (BY GC, SEE A-312). FINISH "
           "GRADE 711.83 BOTH SIDES."),
    ("11", "CONNECT TO EXISTING PCC WALK WITH 1/2\" PREMOLDED EXPANSION JOINT. MATCH EXISTING "
           "ELEVATION."),
    ("12", "SOD: WITHIN 10' OF THE BUILDING, 3' EACH SIDE OF NEW WALKS AND IN THE PUBLIC PARKWAY."),
    ("13", "SEED (IDOT CLASS 1A) AND MULCH ALL OTHER DISTURBED AREAS WITHIN THE LIMIT OF WORK, "
           "INCLUDING THE STAGING AREA AFTER DEMOBILIZATION."),
    ("14", "TEMPORARY 8' CHAIN LINK CONSTRUCTION FENCE WITH WINDSCREEN ON THE LIMIT OF WORK; "
           "24' DOUBLE SWING GATE AT THE CONSTRUCTION ENTRANCE. REMOVE AT COMPLETION."),
    ("15", "EXISTING LIGHT POLE TO REMAIN. PROTECT."),
]

C200_NOTES = [
    "DIMENSIONS ARE IN FEET TO THE FACE OF BRICK, EDGE OF PAVEMENT OR BACK OF CURB UNLESS NOTED. "
    "DO NOT SCALE THE DRAWINGS.",
    "LAY OUT THE BUILDING FROM THE ARCHITECTURAL GRIDS. GRID 1 / GRID D = N 10,000.00, E 10,000.00 "
    "(LOCAL). CONSTRUCTION LAYOUT BY AN ILLINOIS PROFESSIONAL LAND SURVEYOR.",
    "PCC FOR WALKS, STOOPS AND PADS: 4,000 PSI AT 28 DAYS, AIR-ENTRAINED 6% +/-1.5%, IDOT CLASS "
    "SI, LIGHT BROOM FINISH PERPENDICULAR TO TRAVEL, TOOLED EDGES, CURING COMPOUND.",
    "ACCESSIBLE ROUTES (ILLINOIS ACCESSIBILITY CODE / 2010 ADA STANDARDS): RUNNING SLOPE 5% MAX., "
    "CROSS SLOPE 2% MAX. (DESIGN 1.5%), LEVEL LANDING 5'x5' MIN. (2% MAX.) AT EVERY EXTERIOR DOOR, "
    "VERTICAL CHANGES 1/4\" MAX.",
    "EXPANSION JOINTS (1/2\" PREMOLDED FILLER, FULL DEPTH) WHERE WALKS ABUT THE BUILDING, STOOPS, "
    "CURBS AND EXISTING WALKS AND AT 50' MAX. ON STRAIGHT RUNS.",
    "THE SCHOOL REMAINS OCCUPIED THROUGHOUT CONSTRUCTION. THE OWNER-DESIGNATED STAGING AREA, "
    "LIMIT OF WORK AND MAPLE STREET ACCESS ARE OWNER REQUIREMENTS; THE CONTRACTOR'S SITE "
    "LOGISTICS PLAN SHALL BE SUBMITTED FOR APPROVAL BEFORE MOBILIZATION.",
    "NO DELIVERIES OR CRANE PICKS DURING STUDENT ARRIVAL (7:30-8:15 AM) AND DISMISSAL "
    "(2:45-3:30 PM). MAINTAIN FIRE DEPARTMENT ACCESS TO THE EXISTING BUILDING AT ALL TIMES.",
    "STAGING AREA: VACATE AND RESTORE BEFORE THE ENTRANCE WALK IS BUILT. REPAIR ANY DAMAGE TO "
    "LAWN, PAVEMENT, WALKS OR UTILITIES OUTSIDE THE LIMIT OF WORK AT THE CONTRACTOR'S EXPENSE.",
    "WORK IN THE PUBLIC R.O.W. (WALK, CURB, CURB RAMPS, PATCHES) PER CITY OF CEDAR PRAIRIE "
    "STANDARDS AND IDOT STANDARD SPECIFICATIONS FOR ROAD AND BRIDGE CONSTRUCTION (CURRENT EDITION).",
]


def draw_c200(sh):
    left, top = sh.x0 + 0.15, sh.y1 - 0.1
    v, rect = plan_frame(sh, FULL, SC, left, top)
    x0, y0, x1, y1 = rect
    with Clip(sh, x0, y0, x1, y1):
        draw_streets(v)
        draw_existing_site(v, walk_d=False, building_label=True, lights=True)
        for tid, x, y, d, sp, disp in TREES:
            if disp == "P":
                tree_sym(v, x, y, d, "E" if sp in ("NORWAY SPRUCE", "WHITE PINE") else "D", SCR)
        draw_staging(v)
        draw_restoration(v)
        draw_public_work(v)
        draw_new_paving(v)
        draw_new_building(v)
        door_labels(v)
        v.geom(CONST_ENT, lw="thin", dash="dashed")
        draw_low_and_fence(v)
        _c200_dims(v)
        _c200_labels(v)
        street_labels(v, x_pr=-200.0, y_mp=200.0)
    ty = title_block_plan(sh, rect, 1, "SITE LAYOUT & PAVING PLAN", SC)
    _c200_panels(sh, rect, ty)


def _c200_dims(v: View):
    # building to property lines / existing building
    ddim(v, (BX1, 60.0), (PL_E, 60.0), 0.0)
    ddim(v, (110.0, BY0), (110.0, PL_S), 0.0)
    ddim(v, (-36.0, 60.0), (BX0, 60.0), 0.0)
    # entrance walk / plaza
    ddim(v, (230.0, 31.0), (230.0, 41.0), 0.0)
    ddim(v, (BX1, 26.0), (164.95, 26.0), -4.0)
    ddim(v, (171.0, 26.0), (171.0, 52.0), 0.0)
    ddim(v, (152.95, 60.0), (164.95, 60.0), 3.5)
    # W-1 / stoop / service walk
    ddim(v, (-11.95, -30.0), (-5.95, -30.0), -0.0)
    ddim(v, (-5.95, -30.0), (BX0, -30.0), -0.0)
    ddim(v, (12.0, -10.95), (12.0, -5.95), 0.0)
    ddim(v, (12.0, -5.95), (12.0, BY0), 0.0)
    ddim(v, (30.5, -14.5), (42.5, -14.5), 0.0)
    ddim(v, (-24.0, -68.0), (-24.0, -60.0), 0.0)


def _c200_labels(v: View):
    p = Paper(v.c)
    K = {
        "1": [((-8.95, -40.0), (-24.0, -40.0)), ((210.0, 36.0), (210.0, 48.0)),
              ((12.0, -8.45), (2.0, -20.0)), ((-20.0, -64.0), (-28.0, -80.0))],
        "2": [((-3.5, 25.0), (-22.0, 18.0))],
        "3": [((158.0, 30.0), (178.0, 20.0))],
        "4": [((36.5, -8.0), (50.0, -24.0))],
        "5": [((159.0, 56.0), (176.0, 66.0))],
        "6": [((249.0, -160.6), (232.0, -172.0)), ((266.5, -144.0), (290.0, -140.0))],
        "7": [((258.5, 36.0), (242.0, 47.0)), ((258.5, 68.0), (242.0, 87.0))],
        "8": [((268.7, 75.0), (290.0, 86.0))],
        "9": [((276.0, -13.0), (296.0, -13.0)), ((273.5, 90.0), (296.0, 98.0)),
              ((72.0, -175.0), (100.0, -172.0))],
        "10": [((-18.0, 43.4), (-30.0, 55.0)), ((-18.0, 28.6), (-28.0, 12.0))],
        "11": [((-36.0, -64.0), (-46.0, -50.0))],
        "12": [((80.0, 78.0), (80.0, 92.0)), ((100.0, -6.0), (115.0, -16.0)),
               ((264.0, 92.0), (292.0, 110.0))],
        "13": [((60.0, -60.0), (60.0, -76.0)), ((120.0, 95.0), (135.0, 108.0))],
        "14": [((140.0, 104.0), (150.0, 115.0)), ((PL_E, -40.0), (240.0, -78.0))],
        "15": [((190.0, 43.0), (196.0, 52.0))],
    }
    for k, lst in K.items():
        for tgt, at in lst:
            key_tag(v, tgt, at, k)
    access_arrow(v)
    owner_constraint_label(v)
    _low_labels(v, [(80.0, 104.0, 0), (130.0, -34.0, 0), (92.0, -110.0, 90)])
    ptext(p, v.to_paper((220.0, 68.0)), "STABILIZED CONSTRUCTION ENTRANCE (SEE C-300)", TY + 0.6,
          FONT, "c", "mid", 0, "black", True)
    ptext(p, v.to_paper((PL_E, 205.0)), "PROPERTY LINE / WEST R.O.W. LINE", TY + 0.6, FONT_B,
          "c", "mid", 90, "black", True)
    ptext(p, v.to_paper((-330.0, PR["row_n"])), "PROPERTY LINE / NORTH R.O.W. LINE", TY + 0.6,
          FONT_B, "c", "mid", 0, "black", True)
    callout(v, (-36.0, 100.0), (-60.0, 135.0), ["MAINTAIN FIRE DEPT. ACCESS",
                                                 "AND EXISTING EXITS AT ALL TIMES"], TY + 0.6)
    callout(v, (-36.0, 36.0), (-60.0, 20.0), ["LINK TIE-IN AT EX. EAST", "CORRIDOR DOOR (SEE AD101)",
                                               "SUMMER RECESS ONLY"], TY + 0.6, side="l")


def _c200_panels(sh, rect, ty):
    x0, y0, x1, y1 = rect
    cx = x1 + 0.3
    cw = sh.x1 - cx - 0.1
    vrule(sh, x1 + 0.15, sh.y0, sh.y1)
    items = [
        (L_line("med", "black", "property"), "PROPERTY LINE"),
        (lambda v, a, b: v.geom(box(a, -1.7, b, 1.7), lw="thin", fill="g20"),
         "PROPOSED BUILDING (FFE 712.50)"),
        (lambda v, a, b: [conc(v, box(a, -1.65, b, 1.65)), v.geom(box(a, -1.65, b, 1.65), lw="thin")],
         "PROPOSED PCC WALK / STOOP / PAD"),
        (L_box(hatch="ansi37", hatch_kw=dict(spacing=0.035, w="hair")), "HMA PAVEMENT PATCH"),
        (L_box(fill="g40"), "CONCRETE CURB & GUTTER (REPLACE)"),
        (L_box(hatch="ansi37", hatch_kw=dict(spacing=0.02, w="hair"), lw="fine"),
         "DETECTABLE WARNING (TRUNCATED DOMES)"),
        (L_box(hatch="sand", hatch_kw=dict(scale=1.9, col=Color(0.45, 0.45, 0.45)), lw=None),
         "SOD"),
        (L_box(lw="fine"), "SEED & MULCH (DISTURBED AREAS)"),
        (L_box(hatch="ansi31", hatch_kw=dict(spacing=0.14, w="hair", col=Color(0.5, 0.5, 0.5)),
               dash="dashed", lw="thin"), "CONTRACTOR STAGING AREA"),
        (lambda v, a, b: v.polyline([(a, 0), (b, 0)], lw="heavy", dash=[9, 3, 2, 3]),
         "LIMIT OF WORK (LOW)"),
        (L_mark("x", "black"), "TEMP. 8' CHAIN LINK CONSTRUCTION FENCE"),
        (lambda v, a, b: Paper(v.c).polygon([v.to_paper((a + 8, 0)),
                                             (v.to_paper((a + 8, 0))[0] - 0.06,
                                              v.to_paper((a + 8, 0))[1] + 0.06),
                                             (v.to_paper((a + 8, 0))[0] - 0.06,
                                              v.to_paper((a + 8, 0))[1] - 0.06)],
                                            lw="fine", fill="black"), "BUILDING ENTRANCE / EXIT"),
        (lambda v, a, b: key_tag(v, None, ((a + b) / 2, 0), "1"), "SITE KEYNOTE"),
        (L_box(fill="g05", col=SCR, lw="fine"), "EXISTING PAVEMENT (SCREENED)"),
    ]
    h = legend(sh, cx, sh.y1 - 0.1, cw, items, "LEGEND", row=0.205)
    yy = sh.y1 - 0.1 - h - 0.2
    sh.line((x1 + 0.15, yy + 0.1), (sh.x1, yy + 0.1), lw="thin")
    # paving schedule
    rows = [["A", "PCC SIDEWALK", "5\" PCC", "4\" CA-6", "1/C-500"],
            ["B", "STOOP / PLAZA / APRON / PAD", "6\" PCC, #4 @ 12\" E.W.", "6\" CA-6", "4/C-500"],
            ["C", "PUBLIC SIDEWALK", "5\" (6\" AT DRIVE)", "4\" CA-6", "1/C-500"],
            ["D", "CURB & GUTTER B-6.12", "PCC", "4\" CA-6", "2/C-500"],
            ["E", "CURB RAMP + DET. WARNING", "6\" PCC", "4\" CA-6", "5/C-500"],
            ["F", "HMA PATCH (STREET)", "2\" N50 SURF. + 3\" BINDER", "10\" PCC BASE", "3/C-500"]]
    hh = table(sh, cx, yy, [("TYPE", 0.38), ("PAVEMENT", 1.62), ("SURFACE", 1.38), ("BASE", 0.78),
                            ("DETAIL", 0.66)], rows, row_h=0.17, size=TY + 0.7,
               title="PAVEMENT SCHEDULE", align=["c", "l", "l", "c", "c"])
    yy -= hh + 0.3
    # horizontal control
    pts = [("1", "ADDITION SW CORNER (FACE OF BRICK)", (BX0, BY0)),
           ("2", "ADDITION SE CORNER (FACE OF BRICK)", (BX1, BY0)),
           ("3", "ADDITION NE CORNER (FACE OF BRICK)", (BX1, BY1)),
           ("4", "ADDITION NW CORNER (FACE OF BRICK)", (BX0, BY1)),
           ("5", "LINK NORTH FACE AT EXIST. BUILDING", (-36.0, 42.0 + M.EW_OUT)),
           ("6", "LINK SOUTH FACE AT EXIST. BUILDING", (-36.0, 30.0 - M.EW_OUT)),
           ("7", "GRID 1 / GRID D", (0.0, 0.0)),
           ("8", "GRID 6 / GRID A", (150.0, 72.0)),
           ("9", "ENTRANCE WALK CL AT R.O.W.", (PL_E, 36.0)),
           ("10", "PROPERTY CORNER (PRAIRIE / MAPLE)", (PL_E, PL_S))]
    rows = [[n, d, f"{10000 + q[1]:,.2f}", f"{10000 + q[0]:,.2f}"] for n, d, q in pts]
    hh = table(sh, cx, yy, [("PT", 0.3), ("DESCRIPTION", 2.42), ("NORTHING", 0.94),
                            ("EASTING", 0.94)], rows, row_h=0.16, size=TY + 0.7,
               title="HORIZONTAL CONTROL (LOCAL SITE GRID)", align=["c", "l", "r", "r"])
    yy -= hh + 0.3
    # site data
    on = PROPERTY
    ex_pave = EX_PAVE.intersection(on).area
    ex_walk = unary_union([EX_WALK_A, EX_WALK_C, EX_WALK_D, EX_WALK_N]).intersection(on).area
    new_pave = pave_union().intersection(on).area
    walk_d_rem = EX_WALK_D.intersection(on).difference(NEW_BLDG).area
    ex_imp = EXB.area + ex_pave + ex_walk
    pr_imp = ex_imp + NEW_BLDG.area + new_pave - EX_WALK_D.intersection(on).area
    site = PROPERTY.area
    rows = [["SITE AREA (PROPERTY)", f"{site:,.0f} SF", f"{site / 43560:.2f} AC"],
            ["EXISTING SCHOOL FOOTPRINT", f"{EXB.area:,.0f} SF", ""],
            ["ADDITION + LINK FOOTPRINT", f"{NEW_BLDG.area:,.0f} SF", ""],
            ["EXISTING PAVEMENT (ON SITE)", f"{ex_pave:,.0f} SF", ""],
            ["EXISTING WALKS (ON SITE)", f"{ex_walk:,.0f} SF", ""],
            ["WALK REMOVED (D1, C-100)", f"-{EX_WALK_D.intersection(on).area:,.0f} SF", ""],
            ["NEW PCC WALKS / STOOPS / PADS", f"{new_pave:,.0f} SF", ""],
            ["IMPERVIOUS - EXISTING", f"{ex_imp:,.0f} SF", f"{ex_imp / site * 100:.1f} %"],
            ["IMPERVIOUS - PROPOSED", f"{pr_imp:,.0f} SF", f"{pr_imp / site * 100:.1f} %"],
            ["NET NEW IMPERVIOUS", f"{pr_imp - ex_imp:,.0f} SF", ""],
            ["EXISTING PARKING (NO CHANGE)", f"{N_STALLS} STALLS", f"{N_ACC} ACCESSIBLE"]]
    table(sh, cx, yy, [("SITE DATA", 2.75), ("AREA", 1.05), ("", 0.8)], rows, row_h=0.16,
          size=TY + 0.7, align=["l", "r", "r"])
    # bottom band
    top = ty - 0.5
    sh.line((sh.x0, top + 0.15), (x1 + 0.15, top + 0.15), lw="thin")
    notes_block(sh, sh.x0 + 0.2, top, "SITE LAYOUT & PAVING NOTES", C200_NOTES, 8.3)
    kx = sh.x0 + 9.0
    sh.text((kx, top), "SITE KEYNOTES", size=TXT["label"], font=FONT_B, valign="top",
            underline=True)
    yy = top - 0.27
    col2 = kx + 8.2
    for i, (k, t) in enumerate(C200_KEYS):
        if i == 9:
            kx, yy = col2, top - 0.27
        hex_tag(sh, (kx + 0.15, yy - 0.06), k)
        hh = sh.mtext((kx + 0.36, yy), t, size=NT, width=7.5, leading=NT * 1.22)
        yy -= max(hh, 0.14) + 0.06


# ========================================================================================
# 11. C-300 GRADING & EROSION CONTROL PLAN
# ========================================================================================
CROP = dict(x0=-150.0, x1=330.0, y0=-214.0, y1=262.0)
ENL = dict(x0=-44.0, x1=172.0, y0=-77.0, y1=109.0)

SF_LINES = [[(-40.0, -71.0), (39.0, -71.0)],
            [(41.0, -148.5), (91.0, -148.5), (91.0, -35.0), (164.0, -35.0), (164.0, -65.0),
             (253.5, -65.0), (253.5, 53.0)],
            [(253.5, 83.0), (253.5, 103.0)]]
STOCKPILE = Point(STOCKPILE_C).buffer(1.0).simplify(0).buffer(0)  # placeholder (scaled below)
_sp = [(STOCKPILE_C[0] + STOCKPILE_R[0] * math.cos(a), STOCKPILE_C[1] + STOCKPILE_R[1] * math.sin(a))
       for a in np.linspace(0, 2 * math.pi, 41)]
STOCKPILE = Polygon(_sp)
TPF_TREES = ["T9", "T10", "T11", "T12", "T13", "T14", "T18"]
TPF_PLAY = box(PLAYGROUND.bounds[0] - 3, PLAYGROUND.bounds[1] - 3, PLAYGROUND.bounds[2] + 3,
               PLAYGROUND.bounds[3] + 3)
IP_INLETS = ["EX CI-2", "EX CI-3", "EX CI-4", "AD-1", "CB-1", "CB-2", "CB-3"]


def _tree_by_id(t):
    for q in TREES:
        if q[0] == t:
            return q
    raise KeyError(t)


def draw_contours(v: View, ex_mask=None, ex=True, pr=True, ex_lab_every=6.0, pr_lab_every=4.0,
                  win=None, lab_size=TY + 0.4):
    if ex:
        ec = existing_contours(win or CROP, mask=ex_mask)
        for z, g in ec.items():
            draw_geom_lines(v, g, lw="fine", col=SCR, dash="dashed")
        for z, g in ec.items():
            contour_label(v, g, z, EXC, every=ex_lab_every, min_len=1.5, size=lab_size)
    if pr:
        pc = proposed_contours()
        for z, g in pc.items():
            draw_geom_lines(v, g, lw="med", col="black")
        for z, g in pc.items():
            contour_label(v, g, z, "black", every=pr_lab_every, min_len=0.8, font=FONT_B,
                          size=lab_size + 0.3)


def draw_esc(v: View, labels=True, size=TY + 0.7):
    p = Paper(v.c)
    # silt fence
    for ln in SF_LINES:
        tagged_line(v, ln, "SF", "thin", "black", every=0.9, size=TY + 0.2, first=0.35)
    # stockpile with silt fence ring
    v.geom(STOCKPILE, lw="thin", hatch="dots", hatch_kw=dict(scale=1.6))
    ring = list(Polygon(_sp).buffer(4.0).exterior.coords)
    tagged_line(v, ring, "SF", "thin", "black", every=0.9, size=TY + 0.2, first=0.3)
    # construction entrance
    v.geom(CONST_ENT, lw="thin", hatch="gravel", hatch_kw=dict(scale=1.0))
    v.geom(CONST_APRON, lw="thin", hatch="gravel", hatch_kw=dict(scale=1.0))
    # washout
    v.geom(WASHOUT, lw="thin", hatch="ansi31", hatch_kw=dict(spacing=0.04, w="hair"))
    # tree protection fence
    mark_line(v, ring_pts(TPF_PLAY), "o", every=0.2, size=0.016, lw="fine", line_lw="thin")
    for t in TPF_TREES:
        tid, x, y, d, sp, disp = _tree_by_id(t)
        R = max(5.0, d * 0.85) + 1.0
        pts = [(x + R * math.cos(a), y + R * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 33)]
        if t in ("T13", "T14"):        # parkway trees: fence the parkway side only
            pts = [(MP["sw_w"][1] + 0.5, y - R), (MP["boc_w"] - 0.5, y - R),
                   (MP["boc_w"] - 0.5, y + R), (MP["sw_w"][1] + 0.5, y + R),
                   (MP["sw_w"][1] + 0.5, y - R)]
        mark_line(v, pts, "o", every=0.2, size=0.016, lw="fine", line_lw="thin")
    # inlet protection
    for nm in IP_INLETS:
        s_ = EX_STR.get(nm) or STM.get(nm)
        px, py = v.to_paper((s_["x"], s_["y"]))
        r = 0.1
        p.rect(px - r, py - r, 2 * r, 2 * r, lw="thin", dash=[2, 1.2])


def _c300_spots_main(v: View):
    for nm in ("CB-1", "CB-2", "CB-3"):
        s_ = STM[nm]
        spot(v, s_["x"], s_["y"] - 1.0, f"RIM {_rim(nm):.2f}", marker=None, dy=-0.1, dx=-0.02,
             anchor="l", font=FONT_B)
    spot(v, ENT_X1 - 1.0, 36.0, ENT_Z1, "ME", dy=0.0)
    # tie-ins along the limit of work
    for (x, y) in [(120.0, 104.0), (60.0, 104.0), (230.0, 104.0), (120.0, -34.0), (200.0, -66.0),
                   (-30.0, -34.0), (92.0, -90.0)]:
        spot(v, x, y - 0.5, round(E1(x, y), 2), "ME", size=TY + 0.4)


def draw_c300(sh):
    left, top = sh.x0 + 0.15, sh.y1 - 0.1
    v, rect = plan_frame(sh, CROP, SC, left, top)
    x0, y0, x1, y1 = rect
    mask = unary_union([box(-320, -60, -36, 120), NEW_BLDG.buffer(0.5)])
    with Clip(sh, x0, y0, x1, y1):
        draw_streets(v)
        draw_existing_site(v, walk_d=False, building_label=False, lot_labels=False,
                           playground_label=False, lights=True)
        for tid, x, y, d, sp, disp in TREES:
            if disp == "P":
                tree_sym(v, x, y, d, "E" if sp in ("NORWAY SPRUCE", "WHITE PINE") else "D", SCR)
        v.geom(STAGING, lw="thin", dash="dashed")
        draw_contours(v, ex_mask=mask)
        v.geom(pave_union(), lw="thin", fill="white")
        v.geom(NEW_BLDG, lw="xheavy", fill="g20")
        _limit_of_work(v)
        draw_esc(v)
        for nm, s_ in STM.items():
            sym_structure(v, s_["x"], s_["y"], s_["kind"])
        for nm in ("EX CI-2", "EX CI-3", "EX CI-4"):
            s_ = EX_STR[nm]
            sym_structure(v, s_["x"], s_["y"], s_["kind"], SCR)
        _c300_spots_main(v)
        _c300_labels(v)
        street_labels(v, x_pr=-40.0, y_mp=175.0)
    ty = title_block_plan(sh, rect, 1, "GRADING & EROSION CONTROL PLAN", SC, na_dx=7.9)
    # enlarged plan
    eleft = x1 + 0.45
    etop = sh.y1 - 0.1
    ve, erect = plan_frame(sh, ENL, SC20, eleft, etop)
    ex0, ey0, ex1, ey1 = erect
    with Clip(sh, ex0, ey0, ex1, ey1):
        _c300_enlarged(ve)
    sh.rect(ex0, ey0, ex1 - ex0, ey1 - ey0, lw="fine")
    ety = ey0 - 0.36
    sh.view_title(ex0 + 0.05, ety, 2, "ENLARGED GRADING PLAN - ADDITION", SC20, width=5.6)
    sh.north_arrow(ex0 + 7.0, ety + 0.05, 0.38)
    scale_bar(sh, ex0 + 7.6, ety - 0.02, SC20, 40, 4)
    sh.text((ex0 + 7.6, ety - 0.12), "1 INCH = 20 FT", size=TY, valign="top")
    _c300_panels(sh, rect, ty, erect, ety)


def _c300_labels(v: View):
    p = Paper(v.c)
    sz = TY + 0.7
    callout(v, (220.0, 74.0), (215.0, 120.0) if False else (232.0, 116.0),
            ["STABILIZED CONSTRUCTION", "ENTRANCE 70' x 24' (8/C-500)"], sz)
    callout(v, (232.0, -46.0), (236.0, -88.0) if False else (200.0, -84.0),
            ["CONCRETE WASHOUT (LINED)"], sz, side="l")
    callout(v, (195.0, -30.0), (150.0, -50.0), ["TOPSOIL STOCKPILE W/", "SILT FENCE (TEMP. SEED)"],
            sz, side="l")
    callout(v, (130.0, -35.0), (120.0, -58.0), ["SILT FENCE (6/C-500)"], sz, side="l")
    callout(v, (91.0, -120.0), (110.0, -128.0), ["SILT FENCE"], sz)
    callout(v, (40.0, 112.0), (-10.0, 128.0) if False else (-20.0, 126.0),
            ["TREE PROTECTION FENCE", "AT PLAYGROUND (13/C-500)"], sz, side="l")
    callout(v, (205.0, 146.0), (230.0, 160.0), ["TREE PROTECTION", "FENCE (TYP.)"], sz)
    ip = EX_STR["EX CI-2"]
    callout(v, (ip["x"] + 3.0, ip["y"] + 2.0), (300.0, -15.0) if False else (296.0, -60.0),
            ["INLET PROTECTION", "(7/C-500, TYP.)"], sz)
    callout(v, (STM["CB-3"]["x"] + 3, 92.0), (215.0, 96.0) if False else (200.0, 112.0),
            ["INLET PROTECTION (TYP.", "AT NEW CB / AD)"], sz)
    # swale flow arrows & labels
    for a, b in (((40.0, 90.0), (75.0, 90.0)), ((141.0, 90.0), (110.0, 90.0)),
                 ((141.0, 90.0), (170.0, 90.0)), ((40.0, 90.0), (10.0, 90.0))):
        flow_arrow(v, a, b)
    ptext(p, v.to_paper((75.0, 97.0)), "GRASS SWALE (EROSION CONTROL BLANKET)", TY + 0.5, FONT_I,
          "c", "mid", 0, "black", True)
    _low_labels(v, [(130.0, 104.0, 0), (225.0, -66.0, 0), (91.0, -60.0, 90)])
    plines(p, v.to_paper((120.0, -185.0)) if False else v.to_paper((170.0, -112.0)),
           [f"**DISTURBED AREA = {DISTURBED_AC:.2f} AC ({DISTURBED_SF:,.0f} SF)**",
            "IEPA NPDES ILR10 COVERAGE REQUIRED"], TY + 0.9, FONT, "c", "mid", "black", True)
    plines(p, v.to_paper((75.0, 36.0)), ["**ADDITION**", "FFE 712.50", "SEE ENLARGED", "PLAN 2"],
           TY + 0.8, FONT, "c", "mid", "black", False)
    ptext(p, v.to_paper((-95.0, 45.0)), "EXISTING SCHOOL", SM, FONT_B, "c", "mid", 0, EXC, True)
    ptext(p, v.to_paper((-95.0, 37.0)), "FFE 712.50", SM, FONT, "c", "mid", 0, EXC, True)
    ptext(p, v.to_paper((70.0, 207.0)), "EXISTING PLAYGROUND (PROTECT)", SM, FONT_B, "c", "mid", 0,
          EXC, True)


def _c300_enlarged(v: View):
    p = Paper(v.c)
    mask = unary_union([box(-320, -60, -36, 120), NEW_BLDG.buffer(0.5), pave_union()])
    draw_existing_site(v, walk_d=False, building_label=False, lot_labels=False,
                       playground_label=False, lights=False, show_stalls=False, labels=False)
    # existing contours (light) & proposed
    ec = existing_contours(CROP, mask=mask)
    for z, g in ec.items():
        draw_geom_lines(v, g, lw="fine", col=SCR, dash="dashed")
        contour_label(v, g, z, EXC, every=4.0, min_len=1.2, size=TY + 0.5)
    pc = proposed_contours()
    for z, g in pc.items():
        g2 = g.difference(pave_union().buffer(0.2))
        draw_geom_lines(v, g2, lw="med")
        contour_label(v, g2, z, "black", every=3.5, min_len=0.8, font=FONT_B, size=TY + 0.9)
    v.geom(pave_union(), lw=None, fill="white")
    conc(v, pave_union(), dens=0.035)
    v.geom(pave_union(), lw="thin")
    v.geom(NEW_BLDG, lw="xheavy", fill="g20")
    draw_new_building(v, fill="g20", label=False)
    plines(p, v.to_paper((75.0, 40.0)), ["**PROPOSED ADDITION**", "**FFE 712.50**",
                                         "(ARCH. 100'-0\")"], NT, FONT, "c", "mid", "black", False)
    ptext(p, v.to_paper((-18.0, 36.0)), "LINK  FFE 712.50", TY + 0.7, FONT_B, "c", "mid", 0,
          "black", False)
    ptext(p, v.to_paper((-41.0, 15.0)), "EXISTING SCHOOL  FFE 712.50", TY + 0.8, FONT_B, "c",
          "mid", 90, EXC, True)
    # structures + rims
    for nm, s_ in STM.items():
        sym_structure(v, s_["x"], s_["y"], s_["kind"])
    lab = {"AD-1": ((-30.0, 66.0), "l"), "CB-1": ((-30.0, 97.0), "l"),
           "MH-1": ((40.0, 97.0), "l"), "CB-2": ((110.0, 97.0), "r"),
           "CB-3": ((170.0, 97.0), "l")}
    for nm, (at, side) in lab.items():
        s_ = STM[nm]
        callout(v, (s_["x"], s_["y"]), at, [f"{nm}  RIM {_rim(nm):.2f}"], TY + 0.8,
                side="l" if at[0] < s_["x"] else "r")
    # downspout
    px, py = v.to_paper(DS_BOOT)
    p.rect(px - 0.03, py - 0.03, 0.06, 0.06, lw="thin", fill="white")
    callout(v, DS_BOOT, (-8.0, 54.0), ["DS-1 (LINK DOWNSPOUT BOOT)"], TY + 0.7, side="r")
    # spot grades: building corners
    S = TY + 0.8
    o = 0.6
    for (x, y, an, dy) in [(BX0 - o, BY1 + o, "r", 0.06), (BX1 + o, BY1 + o, "l", 0.06),
                           (BX1 + o, BY0 - o, "l", -0.06), (40.0, BY1 + o, "l", 0.06),
                           (120.0, BY1 + o, "l", 0.06), (90.0, BY0 - o, "l", -0.06),
                           (130.0, BY0 - o, "l", -0.06), (BX1 + o, 14.0, "l", 0.0),
                           (BX1 + o, 66.0, "l", 0.0), (-4.0, 46.0, "r", 0.05),
                           (-4.0, 70.0, "r", 0.0), (-20.0, BY0 + 26.0, "r", 0.0)]:
        spot(v, x, y, FG, "FG", size=S, anchor=an, dy=dy)
    spot(v, -36.0 + o, 45.0, round(E1(-36.0, 45.0), 2), "ME", size=S, dy=0.06)
    spot(v, -36.0 + o, 27.0, round(E1(-36.0, 27.0), 2), "ME", size=S, dy=-0.06)
    # stoops / pavements
    spot(v, -2.0, 27.5, STOOP, "TS", size=S, anchor="l", dy=0.06)
    spot(v, -5.95, 22.0, 712.40, "TW", size=S, anchor="r", dx=0.06)
    spot(v, -9.0, 12.5, 711.80, "TW", size=S, anchor="r", dx=0.15)
    spot(v, -9.0, -36.0, round(float(PAVE_BY_ID["W-1"]["z"](0, -36.0)), 2), "TW", size=S,
         anchor="r", dx=0.15)
    spot(v, -20.0, -64.0, round(float(PAVE_BY_ID["W-2"]["z"](-20.0, 0)), 2), "TW", size=S,
         anchor="l", dy=0.0)
    spot(v, 29.0, -8.45, 712.31, "TW", size=S, anchor="r", dy=-0.08)
    spot(v, -4.5, -8.45, 711.70, "TW", size=S, anchor="l", dy=-0.09)
    spot(v, 36.5, BY0 - 0.6, STOOP, "TS", size=S, anchor="l", dy=-0.07)
    spot(v, 41.5, -10.4, 712.31, "TS", size=S, anchor="l", dy=-0.05)
    spot(v, BX1 + 0.8, 36.0, STOOP, "TS", size=S, anchor="l", dy=0.0)
    spot(v, BX1 + 0.8, 47.5, STOOP, "TS", size=S, anchor="l", dy=0.0)
    spot(v, 164.0, 27.0, round(STOOP - 0.14, 2), "TS", size=S, anchor="r", dy=-0.08)
    spot(v, 169.0, 36.0, round(float(PAVE_BY_ID["W-4"]["z"](169.0, 0)), 2), "TW", size=S,
         anchor="l", dy=0.09)
    spot(v, 164.0, 59.0, round(float(PAVE_BY_ID["BIKE"]["z"](164.0, 59.0)), 2), "TS", size=S,
         anchor="l", dy=0.06)
    # swale high points & lawn grades
    for x, z in SWALE_HP:
        spot(v, x, SWALE_Y, z, "HP", size=S, anchor="l", dy=0.07, font=FONT_B)
    for (x, y) in [(-18.0, 100.0), (75.0, 100.0), (150.0, 100.0), (60.0, -30.0), (120.0, -30.0),
                   (20.0, -30.0), (165.0, -20.0), (165.0, 80.0), (-30.0, 0.0)]:
        spot(v, x, y, round(P1(x, y), 2), "", size=S)
    # slope arrows: 5% away from the building for the first 10 ft
    for a, b in [((75.0, BY1 + 1.0), (75.0, BY1 + 9.0)), ((25.0, BY1 + 1.0), (25.0, BY1 + 9.0)),
                 ((125.0, BY1 + 1.0), (125.0, BY1 + 9.0)), ((75.0, BY0 - 1.0), (75.0, BY0 - 9.0)),
                 ((115.0, BY0 - 1.0), (115.0, BY0 - 9.0)), ((BX1 + 1.0, 8.0), (BX1 + 9.0, 8.0)),
                 ((BX1 + 1.0, 64.0), (BX1 + 9.0, 64.0)), ((BX0 - 1.0, 60.0), (BX0 - 9.0, 60.0)),
                 ((-20.0, 41.0 + M.EW_OUT + 1.0), (-20.0, 41.0 + M.EW_OUT + 9.0)),
                 ((-26.0, 30.0 - M.EW_OUT - 1.0), (-26.0, 30.0 - M.EW_OUT - 9.0))]:
        slope_arrow(v, a, b, "5.0%")
    # walk slopes
    slope_arrow(v, (-14.5, 24.0), (-14.5, 14.0), "4.4%")
    slope_arrow(v, (-14.5, 0.0), (-14.5, -24.0), "0.5%")
    slope_arrow(v, (25.0, -13.5), (5.0, -13.5), "1.7%")
    slope_arrow(v, (36.5, -2.0), (36.5, -9.5), "1.5%")
    slope_arrow(v, (153.0, 30.0), (162.0, 30.0), "1.0%")
    slope_arrow(v, (166.0, 43.5), (172.0, 43.5) if False else (171.5, 43.5), "1.7%")
    slope_arrow(v, (-26.0, -57.0), (-16.0, -57.0), "1.7%")
    # swale flow
    for a, b in (((40.0, SWALE_Y), (70.0, SWALE_Y)), ((141.0, SWALE_Y), (115.0, SWALE_Y)),
                 ((141.0, SWALE_Y), (165.0, SWALE_Y)), ((40.0, SWALE_Y), (10.0, SWALE_Y))):
        flow_arrow(v, a, b)
    # south swale label
    callout(v, (100.0, -27.0), (108.0, -34.0), ["SHALLOW GRASS SWALE, DRAINS EAST"], TY + 0.7)


GRADING_NOTES = [
    "EXISTING CONTOURS (1' INTERVAL, DASHED) ARE FROM THE TOPOGRAPHIC SURVEY. PROPOSED CONTOURS "
    "(1' INTERVAL, SOLID) AND SPOT GRADES ARE FINISHED GRADE; SPOT GRADES GOVERN.",
    "FFE 712.50 = ARCH. 100'-0\". FINISH GRADE AT THE BUILDING = 711.83 (8\" BELOW FFE, TOP OF "
    "FOUNDATION WALL) EXCEPT AT STOOPS AND WALKS. TOP OF STOOPS 712.46 (1/2\" BELOW FFE).",
    "SLOPE FINISHED GRADE AWAY FROM THE BUILDING AT 5% MIN. FOR THE FIRST 10' (IBC 1804.4). "
    "LAWN AREAS 2% MIN., 4:1 MAX. GRASS SWALES 1% MIN. NO PONDING ANYWHERE.",
    "WALKS: 5% MAX. RUNNING SLOPE, 2% MAX. CROSS SLOPE (DESIGN 1.5%); DOOR LANDINGS 2% MAX. "
    "VERIFY ADA SLOPES BEFORE PLACING CONCRETE; REMOVE AND REPLACE NON-COMPLIANT PANELS.",
    "STRIP TOPSOIL (6\" AVG.) WITHIN THE LIMIT OF WORK AND STOCKPILE IN THE STAGING AREA. "
    "RESPREAD 6\" MIN. TOPSOIL IN ALL LAWN AREAS; EXPORT EXCESS.",
    "FILL UNDER THE BUILDING AND PAVEMENTS: APPROVED STRUCTURAL FILL IN 8\" LIFTS COMPACTED TO "
    "95% STANDARD PROCTOR (ASTM D698), +/-2% OF OPTIMUM MOISTURE; LAWN AREAS 90%. PROOF-ROLL "
    "SUBGRADES; UNDERCUT AND REPLACE SOFT AREAS AS DIRECTED.",
    "STRUCTURE RIMS ARE SET TO FINISHED GRADE. ADJUST ALL EXISTING FRAMES, VALVE BOXES AND "
    "CLEANOUTS WITHIN THE WORK AREA TO FINISHED GRADE.",
    "TOLERANCE: +/- 0.10' LAWN, +/- 0.03' PAVEMENT. EARTHWORK DOES NOT BALANCE; CONTRACTOR "
    "DETERMINES IMPORT / EXPORT.",
]

ESC_NOTES = [
    f"THE PROJECT DISTURBS {DISTURBED_AC:.2f} ACRES (> 1 AC): COVERAGE UNDER IEPA GENERAL NPDES "
    "PERMIT NO. ILR10 IS REQUIRED. THE OWNER FILES THE NOTICE OF INTENT (NOI) 30 DAYS BEFORE "
    "CONSTRUCTION; THE CONTRACTOR SIGNS THE SWPPP CONTRACTOR CERTIFICATION.",
    "KEEP THE SWPPP, NOI, PERMIT AND INSPECTION REPORTS ON SITE. POST THE NOI AT THE "
    "CONSTRUCTION ENTRANCE.",
    "INSTALL PERIMETER CONTROLS (SILT FENCE, INLET PROTECTION, CONSTRUCTION ENTRANCE, TREE "
    "PROTECTION) BEFORE ANY LAND DISTURBANCE. ALL MEASURES PER THE ILLINOIS URBAN MANUAL.",
    "INSPECT ALL MEASURES AT LEAST ONCE EVERY 7 CALENDAR DAYS AND WITHIN 24 HOURS AFTER A "
    "RAINFALL OF 0.5\" OR MORE. REPAIR WITHIN 24 HOURS. REMOVE SEDIMENT AT 1/3 FENCE HEIGHT.",
    "STABILIZE DISTURBED AREAS (TEMPORARY SEED + MULCH) WITHIN 7 DAYS WHERE WORK HAS CEASED "
    "FOR 14 DAYS OR MORE. STOCKPILES INACTIVE > 7 DAYS: TEMPORARY SEED OR COVER.",
    "SWEEP MAPLE STREET AND THE PUBLIC WALK DAILY AND AS NEEDED; NO FLUSHING OF SEDIMENT INTO "
    "INLETS. CONTROL DUST WITH WATER.",
    "CONCRETE WASHOUT: LINED (10 MIL POLY) CONTAINMENT, 12'x12'x3' MIN.; NO WASHOUT TO GRADE OR "
    "INLETS. REMOVE HARDENED CONCRETE WHEN 50% FULL.",
    "DEWATERING: PUMP TO A SEDIMENT FILTER BAG ON A STABLE VEGETATED AREA; NEVER DIRECTLY TO A "
    "STORM INLET.",
    "PERMANENT STABILIZATION: SOD / SEED PER C-200; EROSION CONTROL BLANKET (NAG S150 OR EQUAL) "
    "IN SWALES AND ON SLOPES > 4%. REMOVE TEMPORARY MEASURES AFTER 70% UNIFORM PERENNIAL "
    "COVER; OWNER FILES THE NOTICE OF TERMINATION (NOT).",
    "RECEIVING SYSTEM: CITY STORM SEWER IN MAPLE ST. TO CEDAR CREEK (FICTIONAL). SOILS: DRUMMER "
    "SILTY CLAY LOAM (FICTIONAL), HSG B/D.",
]

SEQUENCE = [
    "PRE-CONSTRUCTION MEETING WITH OWNER, ENGINEER AND CITY. NOI EFFECTIVE; JULIE LOCATES AND "
    "PRIVATE LOCATES COMPLETE.",
    "INSTALL STABILIZED CONSTRUCTION ENTRANCE (MAPLE ST.), TREE PROTECTION FENCE, CONSTRUCTION "
    "FENCE, SILT FENCE AND INLET PROTECTION ON EXISTING INLETS.",
    "MOBILIZE TO THE STAGING AREA. INSTALL CONCRETE WASHOUT.",
    "SITE DEMOLITION (C-100). STRIP AND STOCKPILE TOPSOIL; TEMPORARY SEED THE STOCKPILE.",
    "ROUGH GRADE THE BUILDING PAD. INSTALL STORM SEWER FROM EX ST-2 UPSTREAM (CB-3 TO CB-1, "
    "AD-1) AND PROTECT EACH INLET AS SET.",
    "INSTALL WATER AND SANITARY SERVICES (R.O.W. PERMIT, TRAFFIC CONTROL; CONNECTIONS AND "
    "SHUTDOWNS OUTSIDE SCHOOL HOURS).",
    "BUILDING CONSTRUCTION. MAINTAIN ALL ESC MEASURES. LINK TIE-IN DURING SUMMER RECESS ONLY.",
    "FINE GRADE, RESPREAD TOPSOIL, CONSTRUCT WALKS, STOOPS, PADS, CURB RAMPS AND R.O.W. "
    "RESTORATION. VACATE THE STAGING AREA; REMOVE THE CONSTRUCTION ENTRANCE.",
    "SOD / SEED / BLANKET. AFTER FINAL STABILIZATION REMOVE SILT FENCE, INLET PROTECTION AND "
    "TREE PROTECTION; RESTORE DISTURBED AREAS; FILE NOT.",
]


def _section_A(sh, x, y):
    """north side grading section at x = 75 (looking west). (x, y) = lower-left of the frame"""
    s0, s1, z0, z1 = 64.0, 112.0, 708.0, 713.5
    xy = XY(sh.c, x, y, 0.1, 0.5, s0, z0)
    elev_grid(xy, s0, s1, z0, z1, sta=[(BY1, "BLDG"), (BY1 + 10, "10'"), (SWALE_Y, "SWALE"),
                                        (104.0, "LOW")])
    ss = np.linspace(BY1, s1, 97)
    pz = P_points(np.full_like(ss, 75.0), ss)
    ez = E(np.full_like(ss, 75.0), ss)
    se = np.linspace(s0, s1, 97)
    ez2 = E(np.full_like(se, 75.0), se)
    xy.polyline(list(zip(se, ez2)), lw="thin", color=SCR, dash="dashed")
    xy.polyline(list(zip(ss, pz)), lw="heavy")
    # building wall + slab
    wi, wo = 72.0 - M.EW_IN, BY1
    xy.polygon([(wi, z0), (wo, z0), (wo, z1), (wi, z1)], lw="thin", fill="white", hatch="ansi31",
               hatch_kw=dict(spacing=0.035, w="hair"))
    xy.polygon([(s0, FFE - 5 / 12.0), (wi, FFE - 5 / 12.0), (wi, FFE), (s0, FFE)], lw="thin",
               fill="g20")
    pp = Paper(sh.c)
    a = xy.to_paper((s0 + 0.5, FFE))
    ptext(pp, (a[0] + 0.02, a[1] + 0.07), "FFE 712.50", TY + 0.8, FONT_B, "l", "mid", 0, "black", True)
    a = xy.to_paper((wo, FG))
    ptext(pp, (a[0] + 0.05, a[1] + 0.09), "FG 711.83", TY + 0.8, FONT, "l", "mid", 0, "black", True)
    z10 = float(P_points([75.0], [BY1 + 10.0])[0])
    a, b = xy.to_paper((wo + 1, FG - 0.05)), xy.to_paper((wo + 9, z10 + 0.0))
    ptext(pp, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 - 0.12), "5.0% MIN. (10')", TY + 0.7, FONT,
          "c", "mid", 0, "black", True)
    zs = float(P_points([75.0], [SWALE_Y])[0])
    a = xy.to_paper((SWALE_Y, zs))
    ptext(pp, (a[0], a[1] - 0.14), f"SWALE {zs:.2f}", TY + 0.7, FONT_B, "c", "mid", 0, "black", True)
    zl = float(E([75.0], [104.0])[0])
    a = xy.to_paper((104.0, zl))
    pp.line((a[0], a[1] - 0.25), (a[0], a[1] + 0.35), lw="thin", dash=[6, 2, 1.5, 2])
    ptext(pp, (a[0] + 0.04, a[1] + 0.3), f"ME {zl:.2f}", TY + 0.7, FONT, "l", "mid", 0, "black", True)
    a = xy.to_paper((100.0, float(P_points([75.0], [100.0])[0])))
    ptext(pp, (a[0] - 0.3, a[1] + 0.25), "6% BACK SLOPE", TY + 0.7, FONT, "c", "mid", 0, "black", True)
    a = xy.to_paper((66.0, 709.0))
    plines(pp, (a[0], a[1]), ["ADDITION", "(CLASSROOM 103)"], TY + 0.7, FONT, "l", "mid", "black", True)
    a = xy.to_paper((108.0, float(E([75.0], [108.0])[0]) - 0.6))
    plines(pp, a, ["EXISTING", "GRADE"], TY + 0.6, FONT, "c", "mid", EXC, True)
    sh.view_title(x, y - 0.42, "A", "GRADING SECTION - NORTH SIDE AT x = 75'",
                  "HORIZ. 1\" = 10', VERT. 1\" = 2'", width=4.6)


def _section_B(sh, x, y):
    """entrance walk section at y = 36 (looking north)"""
    s0, s1, z0, z1 = 140.0, 272.0, 709.0, 713.5
    xy = XY(sh.c, x, y, 0.05, 0.5, s0, z0)
    elev_grid(xy, s0, s1, z0, z1, sta=[(BX1, "BLDG"), (164.95, "PLAZA"), (PL_E, "PL"),
                                        (MP["boc_w"], "B.O.C.")])
    se = np.linspace(s0, s1, 133)
    ez = E(se, np.full_like(se, 36.0))
    xy.polyline(list(zip(se, ez)), lw="thin", color=SCR, dash="dashed")
    zp = PAVE_BY_ID["PLAZA"]["z"]
    zw = PAVE_BY_ID["W-4"]["z"]
    top = [(BX1, STOOP), (164.95, float(zp(164.95, 36)))] + \
          [(x_, float(zw(x_, 36))) for x_ in np.linspace(164.95, ENT_X1, 12)]
    t6, t5 = 0.5, 5 / 12.0
    slab = top + [(ENT_X1, top[-1][1] - t5), (164.95, float(zp(164.95, 36)) - t5),
                  (164.95, float(zp(164.95, 36)) - t6), (BX1, STOOP - t6)]
    xy.polygon(slab, lw="thin", fill="g20")
    xy.polyline(top, lw="heavy")
    # public walk + parkway + curb
    zpw = ENT_Z1
    xy.polygon([(256.0, zpw), (261.0, zpw + 0.05), (261.0, zpw + 0.05 - t5), (256.0, zpw - t5)],
               lw="thin", fill="g10")
    ztc = float(E([MP["boc_w"]], [36.0])[0])
    xy.polyline([(261.0, zpw + 0.03), (MP["boc_w"], ztc)], lw="heavy")
    xy.polyline([(MP["boc_w"], ztc), (MP["boc_w"], ztc - 0.5), (MP["eop_w"], ztc - 0.45),
                 (s1, ztc - 0.25)], lw="thin")
    # building
    wi = 150.0 - M.EW_IN
    xy.polygon([(wi, z0), (BX1, z0), (BX1, FFE), (wi, FFE)], lw="thin", fill="white",
               hatch="ansi31", hatch_kw=dict(spacing=0.035, w="hair"))
    xy.polygon([(s0, FFE - 5 / 12.0), (wi, FFE - 5 / 12.0), (wi, FFE), (s0, FFE)], lw="thin", fill="g20")
    xy.line((wi + 0.4, FFE), (wi + 0.4, z1), lw="thin")
    xy.line((BX1 - 0.3, FFE), (BX1 - 0.3, z1), lw="thin")
    pp = Paper(sh.c)
    a = xy.to_paper((141.0, FFE))
    ptext(pp, (a[0], a[1] + 0.08), "FFE 712.50", TY + 0.8, FONT_B, "l", "mid", 0, "black", True)
    a = xy.to_paper((BX1, z1 - 0.4))
    ptext(pp, (a[0] + 0.04, a[1]), "ENTRANCE SF-1", TY + 0.7, FONT, "l", "mid", 0, "black", True)
    for (st, z, lab, dy) in [(BX1 + 0.5, STOOP, f"TS {STOOP:.2f}", 0.14),
                             (164.95, float(zp(164.95, 36)), f"TS {float(zp(164.95, 36)):.2f}", 0.14),
                             (ENT_X1, ENT_Z1, f"ME {ENT_Z1:.2f}", 0.16)]:
        a = xy.to_paper((st, z))
        pp.line((a[0], a[1]), (a[0], a[1] + dy - 0.03), lw="fine")
        ptext(pp, (a[0], a[1] + dy + 0.02), lab, TY + 0.7, FONT, "c", "mid", 0, "black", True)
    a, b = xy.to_paper((152.0, STOOP)), xy.to_paper((164.0, STOOP))
    ptext(pp, ((a[0] + b[0]) / 2, a[1] - 0.2), "6\" PLAZA 1.0%", TY + 0.6, FONT, "c", "mid", 0,
          "black", True)
    sl = (STOOP - 0.14 - ENT_Z1) / (ENT_X1 - 164.95) * 100
    a = xy.to_paper((210.0, float(zw(210.0, 36))))
    ptext(pp, (a[0], a[1] + 0.13), f"5\" PCC ENTRANCE WALK  {sl:.1f}% (5% MAX.)", TY + 0.7, FONT_B,
          "c", "mid", -math.degrees(math.atan(sl / 100 * 0.5 / 0.05)), "black", True)
    a = xy.to_paper((262.0, zpw))
    plines(pp, (a[0] + 0.02, a[1] - 0.38), ["PUBLIC", "WALK"], TY + 0.6, FONT, "c", "mid", "black", True)
    a = xy.to_paper((190.0, float(E([190.0], [36.0])[0])))
    ptext(pp, (a[0], a[1] - 0.12), "EXISTING GRADE", TY + 0.6, FONT, "c", "mid", 0, EXC, True)
    sh.view_title(x, y - 0.42, "B", "GRADING SECTION - ENTRANCE WALK AT y = 36'",
                  "HORIZ. 1\" = 20', VERT. 1\" = 2'", width=5.9)


SEED_ROWS = [
    ["TEMPORARY SEED", "OATS 3 BU/AC (SPRING) OR CEREAL RYE 2 BU/AC (FALL)", "STRAW 2 TONS/AC", "INACTIVE > 14 DAYS"],
    ["PERMANENT SEED", "IDOT CLASS 1A LAWN MIX 220 LB/AC + 10-10-10 FERT.", "STRAW 2 TONS/AC", "FINAL GRADE"],
    ["SOD", "KENTUCKY BLUEGRASS BLEND, 1 YR MIN., ON 6\" TOPSOIL", "-", "SEE C-200"],
    ["EROSION BLANKET", "NAG S150 (STRAW, DOUBLE NET) OR EQUAL, STAPLED", "-", "SWALES / SLOPES > 4%"],
    ["DORMANT SEEDING", "AFTER NOV. 1: 1.5x RATE + BLANKET; REPAIR IN SPRING", "BLANKET", "NOV. 1 - MAR. 1"],
]
POLL_ROWS = [
    ["CONCRETE WASHOUT", "LINED CONTAINMENT IN STAGING AREA; NO WASHOUT TO GRADE / INLETS"],
    ["FUEL / OIL", "NO BULK FUEL ON SITE; SPILL KIT AT STAGING AREA; REFUEL > 50' FROM INLETS"],
    ["SANITARY FACILITIES", "PORTABLE TOILETS IN STAGING AREA, STAKED, > 20' FROM INLETS"],
    ["SOLID WASTE", "COVERED DUMPSTER IN STAGING AREA; EMPTY WHEN 3/4 FULL"],
    ["MATERIAL STORAGE", "ON PALLETS, COVERED; NO STORAGE INSIDE TREE PROTECTION"],
    ["TRACKING / DUST", "STABILIZED ENTRANCE; DAILY STREET SWEEPING; WATER FOR DUST"],
]


def _c300_panels(sh, rect, ty, erect, ety):
    x0, y0, x1, y1 = rect
    ex0, ey0, ex1, ey1 = erect
    vrule(sh, x1 + 0.15, sh.y0, sh.y1)
    # column right of the enlarged plan: disturbed area summary + owner constraints + prefixes
    lx = ex1 + 0.3
    lw_ = sh.x1 - lx - 0.05
    vrule(sh, ex1 + 0.15, ety - 0.35, sh.y1)
    sod, row_sod, seed = restoration_geoms()
    onsite = LOW.intersection(PROPERTY).area
    rows = [["TOTAL (LIMIT OF WORK)", f"{DISTURBED_SF:,.0f}", f"{DISTURBED_AC:.2f}"],
            ["  ON SCHOOL PROPERTY", f"{onsite:,.0f}", f"{onsite / 43560:.2f}"],
            ["  IN PUBLIC R.O.W.", f"{DISTURBED_SF - onsite:,.0f}", f"{(DISTURBED_SF - onsite) / 43560:.2f}"],
            ["ADDITION + LINK", f"{NEW_BLDG.area:,.0f}", f"{NEW_BLDG.area / 43560:.2f}"],
            ["NEW PCC (ON SITE)", f"{pave_union().area:,.0f}", f"{pave_union().area / 43560:.2f}"],
            ["SOD (INCL. PARKWAY)", f"{sod.area + row_sod.area:,.0f}", f"{(sod.area + row_sod.area) / 43560:.2f}"],
            ["SEED & MULCH", f"{seed.area:,.0f}", f"{seed.area / 43560:.2f}"]]
    h = table(sh, lx, sh.y1 - 0.1, [("DISTURBED AREA", 1.62), ("SF", 0.85), ("AC", 0.55)], rows,
              row_h=0.17, size=TY + 0.7, title="DISTURBED AREA SUMMARY", align=["l", "r", "r"])
    yy = sh.y1 - 0.1 - h - 0.14
    sh.mtext((lx, yy), [f"DISTURBED AREA {DISTURBED_AC:.2f} AC > 1.0 AC:",
                        "IEPA GENERAL NPDES PERMIT ILR10", "COVERAGE AND SWPPP REQUIRED."],
             size=TY + 0.9, font=FONT_B, leading=(TY + 0.9) * 1.25)
    yy -= 0.7
    hh = notes_block(sh, lx, yy, "OWNER CONSTRAINTS", [
        "SCHOOL OCCUPIED; WORK ONLY INSIDE THE LIMIT OF WORK.",
        "ACCESS FROM MAPLE ST. ONLY (STABILIZED ENTRANCE).",
        "NO USE OF BUS LOOP, PARKING LOT OR PRAIRIE AVE. DRIVES.",
        "NO DELIVERIES 7:30-8:15 AM / 2:45-3:30 PM.",
        "EXISTING BUILDING TIE-IN JUNE 7 - AUG. 13, 2027 ONLY.",
        "MAINTAIN FIRE DEPT. ACCESS AT ALL TIMES."], lw_, size=TY + 1.0)
    yy -= hh + 0.25
    sh.text((lx, yy), "SPOT GRADE PREFIXES", size=TXT["label"], font=FONT_B, valign="top",
            underline=True)
    sh.mtext((lx, yy - 0.25), ["FG = FINISH GRADE (LAWN)", "TS = TOP OF STOOP / SLAB",
                               "TW = TOP OF WALK", "ME = MATCH EXISTING", "HP = HIGH POINT",
                               "RIM = STRUCTURE RIM (FINISHED GRADE)"],
             size=TY + 1.0, leading=(TY + 1.0) * 1.35)
    # notes under the enlarged plan (3 columns)
    top = ety - 0.55
    sh.line((x1 + 0.15, top + 0.17), (sh.x1, top + 0.17), lw="thin")
    cw = (sh.x1 - x1 - 0.15 - 0.2 * 4) / 3
    cx1 = x1 + 0.35
    cx2 = cx1 + cw + 0.25
    cx3 = cx2 + cw + 0.25
    h1 = notes_block(sh, cx1, top, "GRADING NOTES", GRADING_NOTES, cw, size=NT)
    h2 = notes_block(sh, cx2, top, "EROSION & SEDIMENT CONTROL / SWPPP NOTES", ESC_NOTES, cw, size=NT)
    h3 = notes_block(sh, cx3, top, "SEQUENCE OF CONSTRUCTION", SEQUENCE, cw, size=NT)
    ly = top - max(h1, h2, h3) - 0.25
    sh.line((x1 + 0.15, ly + 0.13), (sh.x1, ly + 0.13), lw="thin")
    items1 = [
        (L_line("fine", SCR, "dashed"), "EXISTING CONTOUR (1')"),
        (L_line("med", "black"), "PROPOSED CONTOUR (1')"),
        (lambda v, a, b: spot(v, a + 1.5, 0, "711.83", "FG"), "SPOT GRADE"),
        (lambda v, a, b: slope_arrow(v, (a + 1, 0), (b - 1, 0), "5.0%"), "SLOPE / DIRECTION"),
        (lambda v, a, b: flow_arrow(v, (a, 0), (b, 0)), "SWALE FLOW"),
        (lambda v, a, b: [sym_structure(v, a + 4, 0, "cb"), sym_structure(v, a + 12, 0, "mh"),
                          sym_structure(v, a + 18, 0, "ad")], "CATCH BASIN / MANHOLE / AREA DRAIN"),
        (lambda v, a, b: v.polyline([(a, 0), (b, 0)], lw="heavy", dash=[9, 3, 2, 3]),
         "LIMIT OF WORK"),
    ]
    items2 = [
        (L_tag("SF", "thin"), "SILT FENCE (6/C-500)"),
        (L_mark("o", "black", "fine", 0.12, "thin"), "TREE PROTECTION FENCE (13/C-500)"),
        (lambda v, a, b: [sym_structure(v, (a + b) / 2, 0, "cb"),
                          Paper(v.c).rect(v.to_paper(((a + b) / 2, 0))[0] - 0.1,
                                          v.to_paper(((a + b) / 2, 0))[1] - 0.1, 0.2, 0.2,
                                          lw="thin", dash=[2, 1.2])], "INLET PROTECTION (7/C-500)"),
        (L_box(hatch="gravel", hatch_kw=dict(scale=1.0)), "STABILIZED CONSTR. ENTRANCE (8/C-500)"),
        (L_box(hatch="ansi31", hatch_kw=dict(spacing=0.04, w="hair")), "CONCRETE WASHOUT"),
        (L_box(hatch="dots", hatch_kw=dict(scale=1.6)), "TOPSOIL STOCKPILE"),
        (L_line("thin", "black", "dashed"), "CONTRACTOR STAGING AREA"),
    ]
    legend(sh, cx1, ly, cw, items1, "LEGEND", row=0.22, size=TY + 1.0)
    legend(sh, cx2, ly, cw, items2, " ", row=0.22, size=TY + 1.0)
    table(sh, cx3, ly, [("ITEM", 1.05), ("CONTROL / PRACTICE", cw - 1.05)], POLL_ROWS, row_h=0.17,
          size=TY + 0.8, title="POLLUTION PREVENTION (SWPPP)", align=["l", "l"], wrap=True)
    by = ly - 2.0
    table(sh, cx1, by, [("STABILIZATION", 1.2), ("MATERIAL / RATE", 3.3), ("MULCH", 1.05),
                        ("WHEN", 1.25)], SEED_ROWS, row_h=0.17, size=TY + 0.9,
          title="SEEDING & STABILIZATION SCHEDULE", align=["l", "l", "c", "c"])
    rows = [["SILT FENCE", "6/C-500", "WEEKLY + 0.5\" RAIN", "SEDIMENT AT 1/3 HT.; REPAIR SAGS"],
            ["INLET PROTECTION", "7/C-500", "WEEKLY + 0.5\" RAIN", "EMPTY BAG AT 1/2 FULL"],
            ["CONSTR. ENTRANCE", "8/C-500", "DAILY", "TOP-DRESS STONE; SWEEP ST."],
            ["TREE PROTECTION", "13/C-500", "WEEKLY", "UPRIGHT AT DRIP LINE"],
            ["CONCRETE WASHOUT", "NOTE 7", "DAILY (POURS)", "12\" FREEBOARD; LINER"],
            ["STOCKPILE", "-", "WEEKLY", "SF RING; TEMP. SEED > 7 DAYS"],
            ["SEEDED AREAS", "C-200", "WEEKLY", "RESEED UNTIL 70% COVER"]]
    table(sh, cx1 + 7.15, by, [("MEASURE", 1.35), ("DETAIL", 0.62), ("INSPECTION", 1.2),
                               ("MAINTENANCE", 2.05)], rows, row_h=0.17, size=TY + 0.8,
          title="ESC INSPECTION & MAINTENANCE", align=["l", "c", "c", "l"])
    # grading sections under the main plan
    bt = ty - 0.55
    sh.line((sh.x0, bt + 0.2), (x1 + 0.15, bt + 0.2), lw="thin")
    _section_A(sh, sh.x0 + 0.65, bt - 3.0)
    _section_B(sh, sh.x0 + 6.9, bt - 3.0)
    notes_block(sh, sh.x0 + 0.3, bt - 4.0, "SECTION NOTES", [
        "SECTIONS ARE SCHEMATIC WITH 5x (A) AND 10x (B) VERTICAL EXAGGERATION. EXISTING GRADE "
        "DASHED, FINISHED GRADE HEAVY.",
        "SEE ENLARGED GRADING PLAN 2 FOR SPOT GRADES AND C-500 FOR PAVEMENT SECTIONS."],
        x1 - sh.x0 - 0.6, size=NT)


# ========================================================================================
# 12. C-400 SITE UTILITY PLAN
# ========================================================================================
WATER_COVER = 5.5
SVC = dict(x0=16.0, x1=66.0, y0=-36.0, y1=4.0)       # enlarged service entry plan window


def fire_len():
    return LineString(FIRE_RUN).length


def dom_len():
    return LineString(DOM_RUN).length


def thrust_block(v, at, d1, d2, col="black"):
    """filled block on the outside of a bend; d1, d2 = unit directions of the two legs"""
    p = Paper(v.c)
    px, py = v.to_paper(at)
    ox, oy = -(d1[0] + d2[0]), -(d1[1] + d2[1])
    L = math.hypot(ox, oy) or 1
    ox, oy = ox / L, oy / L
    s_ = 0.045
    cx, cy = px + ox * s_, py + oy * s_
    p.polygon([(cx - oy * s_, cy + ox * s_), (cx + oy * s_, cy - ox * s_),
               (cx + ox * s_ * 1.2, cy + oy * s_ * 1.2)], lw="fine", fill=col, color=col)


def draw_new_utils(v: View, labels=True, gas_elec=True, size=TY + 0.7):
    p = Paper(v.c)
    # --- water
    tagged_line(v, FIRE_RUN, "F", "heavy", every=1.2, size=TY + 0.4, first=0.5)
    tagged_line(v, DOM_RUN, "W", "med", every=1.2, size=TY + 0.4, first=1.0)
    sym_valve(v, WM_X - 3.0, FIRE_Y, "black", 0.04)
    p.circle(v.to_paper((WM_X, DOM_Y)), 0.018, lw=None, fill="black")
    cs = v.to_paper(CURB_STOP)
    p.circle(cs, 0.03, lw="thin", fill="white")
    p.circle(cs, 0.01, lw=None, fill="black")
    thrust_block(v, (FIRE_EXIT[0], FIRE_Y), (1, 0), (0, 1))
    thrust_block(v, (WM_X, FIRE_Y), (-1, 0), (0, 1))
    # --- sanitary
    for pd in SAN_PIPE_DATA:
        tagged_line(v, [pd["pa"], pd["pb"]], "SAN", "heavy", every=1.2, size=TY + 0.2, first=0.6)
        if math.hypot(pd["pb"][0] - pd["pa"][0], pd["pb"][1] - pd["pa"][1]) > 20:
            flow_arrow(v, lerp2(pd["pa"], pd["pb"], 0.2), lerp2(pd["pa"], pd["pb"], 0.3))
    for nm, s_ in SAN.items():
        sym_structure(v, s_["x"], s_["y"], s_["kind"])
    # --- storm
    for pd in STM_PIPE_DATA:
        lw_ = "heavy" if pd["size"] >= 12 else "med"
        tagged_line(v, [pd["pa"], pd["pb"]], "ST", lw_, every=1.2, size=TY + 0.2, first=0.55)
        if pd["L"] > 25:
            flow_arrow(v, lerp2(pd["pa"], pd["pb"], 0.7), lerp2(pd["pa"], pd["pb"], 0.8))
    for nm, s_ in STM.items():
        sym_structure(v, s_["x"], s_["y"], s_["kind"])
    px, py = v.to_paper(DS_BOOT)
    p.rect(px - 0.025, py - 0.025, 0.05, 0.05, lw="thin", fill="white")
    # --- gas / electric (by others): dashed routes only
    if gas_elec:
        tagged_line(v, GAS_RUN, "G", "thin", dash=[5, 3], every=1.4, size=TY + 0.2, first=0.8)
        gm = v.to_paper(GAS_METER)
        p.rect(gm[0] - 0.035, gm[1] - 0.03, 0.07, 0.06, lw="thin", fill="white")
        tagged_line(v, ELEC_PRI, "E", "thin", dash=[5, 3], every=1.4, size=TY + 0.2, first=0.8)
        tagged_line(v, ELEC_SEC, "E", "thin", dash=[5, 3], every=1.0, size=TY + 0.2, first=0.4)
        v.geom(XFMR, lw="thin", fill="g20")


def lerp2(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _pipe_label(pd, unit="LF"):
    return f"{pd['L']:.0f} LF {pd['size']}\" {pd['mat'].replace('*', '')} @ {pd['s'] * 100:.2f}%"


def _c400_labels(v: View):
    p = Paper(v.c)
    sz = TY + 0.7
    # storm pipe labels (along pipes)
    for pid, off in (("P-5", 0.1), ("P-6", 0.1), ("P-7", 0.1), ("P-8", 0.1)):
        pd = next(q for q in STM_PIPE_DATA if q["id"] == pid)
        text_along(v, pd["pa"], pd["pb"], _pipe_label(pd), TY + 0.5, "black", FONT, off=off,
                   t=0.5 if pid != "P-8" else 0.42)
    callout(v, lerp2(RL["RL-1"], (52.5, 90.0), 0.5), (30.0, 110.0),
            ["RL-1: 8\" PVC ROOF LEADER @ 2.0%", "INV. 708.90 AT BLDG (SEE A-103)"], sz, side="l")
    callout(v, lerp2(RL["RL-2"], (97.5, 90.0), 0.5), (120.0, 118.0),
            ["RL-2: 8\" PVC ROOF LEADER @ 2.0%", "INV. 708.90 AT BLDG"], sz, side="r")
    for nm, at in (("CB-1", (-40.0, 104.0)), ("MH-1", (40.0, 128.0) if False else (62.0, 100.0)),
                   ("CB-2", (105.0, 104.0)), ("CB-3", (196.0, 104.0)), ("AD-1", (-46.0, 70.0))):
        s_ = STM[nm]
        callout(v, (s_["x"], s_["y"]), at, [nm], sz, font=FONT_B,
                side="l" if at[0] < s_["x"] else "r")
    callout(v, DS_BOOT, (-44.0, 52.0), ["DS-1 LINK DOWNSPOUT", "6\" PVC TO AD-1"], sz, side="l")
    s_ = EX_STR["EX ST-2"]
    callout(v, (s_["x"], s_["y"]), (300.0, 112.0),
            ["CORE DRILL & CONNECT TO EX ST-2", f"NEW 12\" INV. {STM_PIPE_DATA[-1]['inv_b']:.2f}"],
            sz, side="r")
    # sanitary
    callout(v, (52.0, -40.0), (70.0, -52.0) if False else (100.0, -58.0),
            ["6\" PVC SDR-26 SANITARY @ 2.08%", "(C900 WITHIN 10' OF WATER CROSSING)"], sz, side="r")
    for nm, at in (("CO-2", (30.0, -76.0)), ("SMH-1", (20.0, -128.0))):
        s_ = SAN[nm]
        callout(v, (s_["x"], s_["y"]), at, [nm], sz, font=FONT_B, side="l")
    callout(v, lerp2((52.0, -136.0), (75.0, -180.0), 0.55), (100.0, -150.0),
            ["50 LF 6\" PVC SDR-26 @ 4.00%"], sz, side="r")
    s_ = EX_STR["EX SAN-3"]
    callout(v, (s_["x"], s_["y"]), (110.0, -192.0),
            ["CORE & CONNECT TO EX SAN-3 W/", "FLEXIBLE BOOT, INV. 704.11; RE-BENCH"], sz, side="r")
    # water
    callout(v, (WM_X - 3.0, FIRE_Y), (300.0, 8.0),
            ["8\"x6\" TAPPING SLEEVE & VALVE", "W/ VALVE BOX (LIVE TAP)"], sz, side="r")
    callout(v, (WM_X, DOM_Y), (300.0, -30.0), ["2\" CORPORATION STOP"], sz, side="r")
    callout(v, CURB_STOP, (238.0, -40.0) if False else (232.0, -32.0),
            ["2\" CURB STOP & BOX"], sz, side="l")
    text_along(v, (200.0, FIRE_Y), (120.0, FIRE_Y), f"{fire_len():.0f} LF 6\" DIP CL. 52 FIRE SERVICE",
               TY + 0.5, "black", FONT, off=0.09)
    text_along(v, (200.0, DOM_Y), (120.0, DOM_Y), f"{dom_len():.0f} LF 2\" TYPE K COPPER DOMESTIC",
               TY + 0.5, "black", FONT, off=-0.09)
    callout(v, (45.0, -6.0), (14.0, 16.0) if False else (-30.0, 18.0),
            ["SERVICE ENTRY - SEE", "ENLARGED PLAN 2"], sz, side="l")
    # gas / electric
    callout(v, (150.0, GAS_RUN[0][1]), (150.0, -50.0) if False else (165.0, -48.0),
            ["GAS SERVICE BY NICOR GAS (ROUTE", "APPROX.) - NOT IN THIS SET"], sz, side="r")
    callout(v, (110.0, -100.0), (128.0, -108.0),
            ["ELECTRIC PRIMARY BY ComEd / SECONDARY", "BY DIV. 26 (ROUTE APPROX.) - NOT IN THIS SET"],
            sz, side="r")
    callout(v, (18.0, -38.0), (-20.0, -90.0) if False else (-40.0, -84.0),
            ["PAD-MOUNTED TRANSFORMER", "(BY ComEd; PAD BY DIV. 26)"], sz, side="l")
    # removed RCP note
    plines(p, v.to_paper((150.0, -1.0)) if False else v.to_paper((207.0, 46.0)),
           ["EX. 12\" RCP AND YARD", "INLETS REMOVED (C-100)"], TY + 0.6, FONT_I, "c", "mid", EXC, True)
    _low_labels(v, [(130.0, 104.0, 0), (91.0, -60.0, 90)])
    plines(p, v.to_paper((75.0, 36.0)), ["**ADDITION**", "FFE 712.50"], TY + 0.8, FONT, "c", "mid",
           "black", False)
    ptext(p, v.to_paper((-95.0, 45.0)), "EXISTING SCHOOL", SM, FONT_B, "c", "mid", 0, EXC, True)
    # existing labels
    callout(v, (WM_X, 200.0), (300.0, 215.0), ["EX. 8\" DIP WATER MAIN"], sz, EXC, side="r")
    callout(v, (STM_X, 160.0), (300.0, 172.0), ["EX. 12\" RCP STORM"], sz, EXC, side="r")
    callout(v, (-100.0, SAN_Y), (-112.0, -196.0), ["EX. 8\" PVC SANITARY"], sz, EXC, side="r")


def _svc_plan(sh, x, y):
    """enlarged service entry plan at 1" = 10' with lower-left at paper (x, y)"""
    sc = 0.1
    v, rect = plan_frame(sh, SVC, sc, x, y + (SVC["y1"] - SVC["y0"]) * sc)
    x0, y0, x1, y1 = rect
    with Clip(sh, x0, y0, x1, y1):
        v.geom(NEW_BLDG, lw="xheavy", fill="g20")
        # wall layers line + louvers + door
        for o in ("112-LV1", "112-LV2"):
            op = M.OPENING_BY_ID[o]
            v.rect(op.lo, BY0, op.w, 0.95, lw="fine", fill="white")
        op = M.OPENING_BY_ID["112"]
        v.rect(op.lo, BY0, op.w, 0.95, lw="thin", fill="white")
        for pv in ("APRON", "W-3"):
            g = PAVE_BY_ID[pv]["poly"]
            conc(v, g, dens=0.03)
            v.geom(g, lw="thin")
        tagged_line(v, FIRE_RUN, "F", "heavy", every=1.0, size=TY + 0.4, first=0.6)
        tagged_line(v, DOM_RUN, "W", "med", every=1.0, size=TY + 0.4, first=1.2)
        thrust_block(v, (FIRE_EXIT[0], FIRE_Y), (1, 0), (0, 1))
        tagged_line(v, [SAN_EXIT, (52.0, SVC["y0"])], "SAN", "heavy", every=1.0, size=TY + 0.3,
                    first=0.55)
        sym_structure(v, SAN["CO-1"]["x"], SAN["CO-1"]["y"], "co")
        tagged_line(v, GAS_RUN, "G", "thin", dash=[5, 3], every=1.0, size=TY + 0.2, first=0.5)
        gm = v.to_paper(GAS_METER)
        Paper(sh.c).rect(gm[0] - 0.1, gm[1] - 0.06, 0.2, 0.12, lw="thin", fill="white")
        tagged_line(v, ELEC_SEC, "E", "thin", dash=[5, 3], every=0.8, size=TY + 0.2, first=0.4)
        v.geom(XFMR, lw="thin", fill="g20")
        # labels (kept inside the window)
        v.dim((46.5, -30.0), (52.0, -30.0), 0, text="5.5'", size=TY + 0.6)
        p = Paper(sh.c)
        sz = TY + 0.7
        callout(v, (44.0, FIRE_Y), (17.5, -21.0),
                ["6\" FIRE: MJ 90 DEG. BEND + THRUST", "BLOCK; VERT. BEND & RISER 1'-6\"",
                 "INSIDE WALL (12/C-500)"], sz, side="r")
        callout(v, (46.5, -6.0), (55.0, -10.0),
                ["2\" CU THRU FDN. WALL", "SLEEVE; METER / RPZ", "BY PLUMBING"], sz, side="r")
        callout(v, (52.0, SAN["CO-1"]["y"]), (55.0, -3.4), ["CO-1 (10/C-500)"], sz, side="r")
        callout(v, (52.0, -13.5), (55.0, -21.5),
                ["CROSSING: SAN. 2.6'", "ABOVE WATER; C900", "10' EACH SIDE"], sz, side="r")
        callout(v, GAS_METER, (61.0, 2.0), ["GAS MTR."], sz, side="r")
        callout(v, (31.5, -16.0), (17.5, -29.5), ["ELEC. CONDUITS (DIV. 26)"], sz, side="r")
        ptext(p, v.to_paper((44.0, 2.2)), "MECH./ELEC. 112", TY + 1.0, FONT_B, "c", "mid", 0,
              "black", True)
        ptext(p, v.to_paper((36.5, -5.5)), "APRON", TY + 0.8, FONT, "c", "mid", 0, "black", True)
        ptext(p, v.to_paper((22.0, -8.45)), "WALK W-3", TY + 0.6, FONT, "c", "mid", 0, "black", True)
        ptext(p, v.to_paper((36.5, BY0 + 0.45)), "DOOR 112", TY + 0.4, FONT, "c", "mid", 0, "black", True)
        ptext(p, v.to_paper((55.0, BY0 + 0.45)), "LV-1", TY + 0.4, FONT, "c", "mid", 0, "black", True)
    sh.rect(x0, y0, x1 - x0, y1 - y0, lw="fine")
    sh.view_title(x0, y0 - 0.38, 2, "SERVICE ENTRY PLAN", 0.1, width=3.4)
    return rect


PRO_H, PRO_V = 1 / 40.0, 1 / 4.0      # profile scales: 1" = 40' horiz., 1" = 4' vert.


def _profile(sh, x, y, runs, s_max, z0, z1, title, num, sheet_scale_h=PRO_H, vs=PRO_V,
             crossings=(), structs=None, width_title=6.0, label_pipes=True):
    """generic sewer profile. runs: list of pipe dicts (pa, pb, inv_a, inv_b, size, ...).
    structs: list of (station, name, rim, inv_text_lines, kind)."""
    hs = sheet_scale_h
    xy = XY(sh.c, x, y, hs, vs, 0.0, z0)
    # stations along the alignment
    stas = [0.0]
    for r in runs:
        stas.append(stas[-1] + r["L"])
    sta_lab = []
    for st in stas:
        if sta_lab and (st - sta_lab[-1][0]) * hs < 0.55:
            continue
        sta_lab.append((st, f"{int(st // 100)}+{st % 100:05.2f}"))
    elev_grid(xy, -6.0, s_max, z0, z1, sta=sta_lab)
    # ground lines
    pts_e, pts_p = [], []
    for k, r in enumerate(runs):
        for t in np.linspace(0, 1, 15):
            q = lerp2(r["pa"], r["pb"], t)
            st = stas[k] + r["L"] * t
            pts_e.append((st, float(E([q[0]], [q[1]])[0])))
            zz = float(P_points([q[0]], [q[1]])[0])
            pts_p.append((st, zz if np.isfinite(zz) else FG))
    xy.polyline(pts_e, lw="thin", color=SCR, dash="dashed")
    xy.polyline(pts_p, lw="med")
    pp = Paper(sh.c)
    # pipes
    for k, r in enumerate(runs):
        d = r["size"] / 12.0
        a, b = stas[k], stas[k + 1]
        xy.polygon([(a, r["inv_a"]), (b, r["inv_b"]), (b, r["inv_b"] + d), (a, r["inv_a"] + d)],
                   lw="thin", fill="g40")
        if label_pipes:
            m = xy.to_paper(((a + b) / 2, (r["inv_a"] + r["inv_b"]) / 2))
            ang = math.degrees(math.atan2((r["inv_b"] - r["inv_a"]) * vs, (b - a) * hs))
            lab = f"{r['L']:.1f} LF {r['size']}\" @ {r['s'] * 100:.2f}%"
            if (b - a) * hs > stringWidth(lab, FONT, TY + 0.5) / PT + 0.1:
                ptext(pp, (m[0], m[1] - d / 2 * vs - 0.1), lab, TY + 0.5, FONT, "c", "mid", ang,
                      "black", True)
    # structures
    if structs:
        for st, nm, rim, lines, kind in structs:
            w = 4.0
            bot = min(float(l_) for l_ in [r for r in [q for q in lines if isinstance(q, float)]] or [z0 + 0.5])
            inv_min = bot
            sump = 2.0 if kind == "cb" else 0.5
            if kind in ("cb", "mh", "smh", "sanmh"):
                xy.polygon([(st - w / 2, inv_min - sump), (st + w / 2, inv_min - sump),
                            (st + w / 2, rim), (st - w / 2, rim)], lw="thin", fill="white")
            elif kind == "co":
                xy.line((st, inv_min + 0.5), (st, rim), lw="med")
            a = xy.to_paper((st, rim))
            txt = [nm, f"RIM {rim:.2f}"] + [q for q in lines if isinstance(q, str)]
            top = xy.to_paper((st, z1))
            pp.line((a[0], a[1]), (a[0], top[1] - 0.02 - 0.0), lw="hair")
            plines(pp, (a[0], top[1] + 0.06 + (len(txt) - 1) * (TY + 0.6) * 1.18 / PT / 2 + 0.02),
                   txt, TY + 0.6, FONT, "c", "mid", "black", True)
    for st, z, d, lab in crossings:
        c = xy.to_paper((st, z + d / 2))
        pp.circle(c, max(0.02, d * vs / 2), lw="thin", fill="white")
        if lab:
            ptext(pp, (c[0] + 0.1, c[1] - 0.1), lab, TY + 0.5, FONT, "l", "mid", 0, "black", True)
    return xy, stas


def _storm_profile(sh, x, y):
    runs = [q for q in STM_PIPE_DATA if q["id"] in ("P-5", "P-6", "P-7", "P-8")]
    pdm = {q["id"]: q for q in STM_PIPE_DATA}
    structs = [
        (0.0, "CB-1", _rim("CB-1"), [f"INV IN 8\" (S) {pdm['P-2']['inv_b']:.2f}",
                                    f"INV OUT 12\" (E) {pdm['P-5']['inv_a']:.2f}", pdm['P-5']['inv_a']], "cb"),
        (pdm["P-5"]["L"], "MH-1", _rim("MH-1"), [f"INV IN 12\" (W) {pdm['P-5']['inv_b']:.2f}",
                                                 f"INV IN 8\" (S) {pdm['P-3']['inv_b']:.2f}",
                                                 f"INV OUT 12\" (E) {pdm['P-6']['inv_a']:.2f}",
                                                 pdm['P-6']['inv_a']], "mh"),
        (pdm["P-5"]["L"] + pdm["P-6"]["L"], "CB-2", _rim("CB-2"),
         [f"INV IN 12\" (W) {pdm['P-6']['inv_b']:.2f}", f"INV IN 8\" (S) {pdm['P-4']['inv_b']:.2f}",
          f"INV OUT 12\" (E) {pdm['P-7']['inv_a']:.2f}", pdm['P-7']['inv_a']], "cb"),
        (pdm["P-5"]["L"] + pdm["P-6"]["L"] + pdm["P-7"]["L"], "CB-3", _rim("CB-3"),
         [f"INV IN 12\" (W) {pdm['P-7']['inv_b']:.2f}", f"INV OUT 12\" (E) {pdm['P-8']['inv_a']:.2f}",
          pdm['P-8']['inv_a']], "cb"),
        (sum(q["L"] for q in runs), "EX ST-2", ex_rim("EX ST-2"),
         [f"NEW INV IN 12\" (W) {pdm['P-8']['inv_b']:.2f}", "EX. INV 12\" (N) 703.65",
          "EX. INV 12\" (S) 703.55", 703.55], "smh"),
    ]
    L = sum(q["L"] for q in runs)
    # water main crossing in Maple St (station of x = WM_X)
    st_w = L - (STM_X - WM_X)
    cr = [(st_w, float(E([WM_X], [90.0])[0]) - 6.0 - 0.67, 0.75, "EX. 8\" WM")]
    xy, stas = _profile(sh, x, y, runs, L + 10, 702.0, 714.0, "", 1, crossings=cr, structs=structs)
    sh.view_title(x - 0.2, y - 0.55, 3, "STORM SEWER PROFILE (CB-1 TO EX ST-2)",
                  "HORIZ. 1\" = 40', VERT. 1\" = 4'", width=6.4)


def _san_profile(sh, x, y):
    runs = SAN_PIPE_DATA
    pdm = {q["id"]: q for q in SAN_PIPE_DATA}
    st = [0.0]
    for r in runs:
        st.append(st[-1] + r["L"])
    structs = [
        (st[1], "CO-1", _rim("CO-1"), [f"INV {pdm['S-1']['inv_b']:.2f}", pdm['S-1']['inv_b']], "co"),
        (st[2], "CO-2", _rim("CO-2"), [f"INV {pdm['S-2']['inv_b']:.2f}", pdm['S-2']['inv_b']], "co"),
        (st[3], "SMH-1", _rim("SMH-1"), [f"INV IN (N) {pdm['S-3']['inv_b']:.2f}",
                                         f"INV OUT (S) {pdm['S-4']['inv_a']:.2f}",
                                         pdm['S-4']['inv_a']], "sanmh"),
        (st[4], "EX SAN-3", ex_rim("EX SAN-3"), [f"NEW INV IN 6\" {pdm['S-4']['inv_b']:.2f}",
                                                 "EX. INV 8\" 703.80", 703.80], "sanmh"),
    ]
    zf = float(E([52.0], [FIRE_Y])[0]) - WATER_COVER - 0.58
    zd = float(E([52.0], [DOM_Y])[0]) - WATER_COVER - 0.2
    cr = [(BY0 - FIRE_Y, zf, 0.58, "6\" FIRE / 2\" CU"), (BY0 - DOM_Y + 0.0, zd, 0.2, "")]
    xy, stas = _profile(sh, x, y, runs, st[-1] + 8, 701.0, 714.0, "", 1, crossings=cr,
                        structs=structs, label_pipes=False)
    pp = Paper(sh.c)
    a = xy.to_paper((0.0, 709.0))
    plines(pp, (a[0] - 0.03, a[1] + 0.6), ["BLDG", "INV 709.00"], TY + 0.6, FONT, "c", "mid", "black", True)
    for r, t in zip(runs, st[:-1]):
        if r["L"] < 20:
            continue
        m = xy.to_paper((t + r["L"] / 2, (r["inv_a"] + r["inv_b"]) / 2))
        ang = math.degrees(math.atan2((r["inv_b"] - r["inv_a"]) * PRO_V, r["L"] * PRO_H))
        ptext(pp, (m[0], m[1] - 0.15), f"{r['L']:.1f} LF 6\" @ {r['s'] * 100:.2f}%", TY + 0.5,
              FONT, "c", "mid", ang, "black", True)
    sh.view_title(x - 0.2, y - 0.55, 4, "SANITARY SERVICE PROFILE",
                  "HORIZ. 1\" = 40', VERT. 1\" = 4'", width=3.9)


UTIL_NOTES = [
    "VERIFY LOCATION, SIZE AND ELEVATION OF EXISTING UTILITIES AT ALL CONNECTIONS AND CROSSINGS "
    "(POTHOLE) BEFORE ORDERING STRUCTURES OR PIPE. REPORT CONFLICTS TO THE ENGINEER.",
    "WATER SERVICE: 6\" DIP AWWA C151 CL. 52, CEMENT LINED, POLYETHYLENE ENCASED (C105), MJ "
    "FITTINGS WITH RESTRAINED JOINTS AND THRUST BLOCKS; 2\" TYPE K SOFT COPPER, NO JOINTS BETWEEN "
    "CURB STOP AND BUILDING. 5'-6\" MIN. COVER. TEST PER AWWA C600 (150 PSI, 2 HR), DISINFECT PER C651.",
    "TAPS ON THE CITY MAIN ARE LIVE TAPS WITNESSED BY THE CITY WATER DEPARTMENT. METER, RPZ AND "
    "FIRE BACKFLOW ASSEMBLY ARE INSIDE ROOM 112 BY DIV. 21 / 22 (NOT IN THIS SET).",
    "SANITARY: PVC SDR-26 (ASTM D3034) WITH ASTM F477 GASKETS; AWWA C900 PVC 10' EACH SIDE OF "
    "WATER CROSSINGS. AIR TEST AND 5% MANDREL TEST (30 DAYS). STORM: PVC SDR-35 (ASTM D3034).",
    "SEPARATION (IEPA 35 IAC 653.119 / TEN STATES STANDARDS): 10' HORIZONTAL BETWEEN WATER AND "
    "SEWERS; 18\" VERTICAL AT CROSSINGS WITH WATER ABOVE WHERE POSSIBLE.",
    "STRUCTURES: PRECAST ASTM C478, 48\" DIA., FLEXIBLE BOOTS (ASTM C923), MAX. 8\" ADJUSTING "
    "RINGS, CHIMNEY SEALS ON SANITARY. CATCH BASINS WITH 2' SUMP. SEE 11/C-500.",
    "BEDDING AND BACKFILL PER 9/C-500. GRANULAR BACKFILL (CA-6) UNDER AND WITHIN 2' OF PAVEMENT; "
    "PLACE 2\" XPS INSULATION 4' WIDE OVER STORM / SANITARY WHERE COVER IS LESS THAN 3'-6\".",
    "ROOF LEADERS RL-1 / RL-2 (8\") AND THE SANITARY EXIT THROUGH THE FOUNDATION WALL IN SLEEVES; "
    "COORDINATE WITH S-301. INTERIOR PIPING BY DIV. 22 (NOT IN THIS SET).",
    "GAS, ELECTRIC AND TELECOM SERVICES ARE BY THE UTILITY COMPANIES AND DIV. 23 / 26 / 27 - NOT "
    "IN THIS SET. ROUTES ARE SHOWN DASHED FOR COORDINATION ONLY.",
    "WORK IN MAPLE ST. AND PRAIRIE AVE.: CITY R.O.W. PERMIT, TRAFFIC CONTROL PER IDOT 701201, "
    "TRENCH BACKFILL CA-6 COMPACTED, HMA PATCH PER 3/C-500. CONNECTIONS OUTSIDE SCHOOL HOURS.",
]


def draw_c400(sh):
    left, top = sh.x0 + 0.15, sh.y1 - 0.1
    v, rect = plan_frame(sh, CROP, SC, left, top)
    x0, y0, x1, y1 = rect
    with Clip(sh, x0, y0, x1, y1):
        draw_streets(v)
        draw_existing_site(v, walk_d=False, building_label=False, lot_labels=False,
                           playground_label=False, lights=True)
        for tid, x, y, d, sp, disp in TREES:
            if disp == "P":
                tree_sym(v, x, y, d, "E" if sp in ("NORWAY SPRUCE", "WHITE PINE") else "D", SCR)
        draw_existing_utils(v, rcp=False)
        v.geom(pave_union(), lw="thin", color=Color(0.35, 0.35, 0.35))
        v.geom(NEW_BLDG, lw="xheavy", fill="g20")
        _limit_of_work(v)
        draw_new_utils(v)
        _c400_labels(v)
        street_labels(v, x_pr=-40.0, y_mp=230.0)
    ty = title_block_plan(sh, rect, 1, "SITE UTILITY PLAN", SC, na_dx=7.9)
    vrule(sh, x1 + 0.15, sh.y0, sh.y1)
    # right side: storm profile + service entry plan / sanitary profile + legend / tables
    rx = x1 + 0.75
    _storm_profile(sh, rx, sh.y1 - 4.0)
    _svc_plan(sh, sh.x1 - 5.15, sh.y1 - 0.2 - (SVC["y1"] - SVC["y0"]) * 0.1)
    yy = sh.y1 - 5.35
    sh.line((x1 + 0.15, yy), (sh.x1, yy), lw="thin")
    _san_profile(sh, rx, yy - 4.3)
    items = [
        (L_tag("F", "heavy"), "PROPOSED 6\" DIP FIRE SERVICE"),
        (L_tag("W", "med"), "PROPOSED 2\" COPPER DOMESTIC WATER"),
        (L_tag("SAN", "heavy"), "PROPOSED SANITARY SEWER"),
        (L_tag("ST", "heavy"), "PROPOSED STORM SEWER"),
        (L_tag("G", "thin", dash=[5, 3]), "GAS SERVICE (BY NICOR - NOT IN SET)"),
        (L_tag("E", "thin", dash=[5, 3]), "ELECTRIC (ComEd / DIV. 26 - NOT IN SET)"),
    ]
    items2 = [
        (L_tag("W", "thin", SCR), "EXISTING UTILITY (SCREENED)"),
        (lambda v, a, b: [sym_structure(v, a + 3, 0, "cb"), sym_structure(v, a + 9.5, 0, "mh"),
                          sym_structure(v, a + 16, 0, "ad")], "CATCH BASIN / STORM MH / AREA DRAIN"),
        (lambda v, a, b: [sym_structure(v, a + 3, 0, "sanmh"), sym_structure(v, a + 10, 0, "co")],
         "SANITARY MANHOLE / CLEANOUT"),
        (lambda v, a, b: [sym_valve(v, a + 3, 0, "black", 0.04),
                          thrust_block(v, (a + 10, 0), (1, 0), (0, 1))],
         "VALVE & BOX / THRUST BLOCK"),
        (lambda v, a, b: flow_arrow(v, (a, 0), (b, 0)), "DIRECTION OF FLOW"),
        (lambda v, a, b: v.polyline([(a, 0), (b, 0)], lw="heavy", dash=[9, 3, 2, 3]),
         "LIMIT OF WORK"),
    ]
    lgx = rx + 5.3
    lgw = (sh.x1 - lgx - 0.3) / 2
    legend(sh, lgx, yy - 0.15, lgw, items, "LEGEND", row=0.22, size=TY + 0.9)
    legend(sh, lgx + lgw + 0.25, yy - 0.15, lgw, items2, " ", row=0.22, size=TY + 0.9)
    notes_block(sh, lgx, yy - 1.75, "PROFILE NOTES", [
        "PROFILES ARE ALONG THE PIPE CENTERLINE. EXISTING GRADE DASHED (SCREENED), FINISHED GRADE "
        "SOLID. STATIONS ARE PIPE LENGTHS (CENTER TO CENTER OF STRUCTURES).",
        "STRUCTURE DEPTHS INCLUDE A 2'-0\" SUMP AT CATCH BASINS.",
        "SANITARY CROSSES 2.6' ABOVE THE NEW WATER SERVICES: S-2 SHALL BE AWWA C900 PVC (DR 18) "
        "FROM CO-1 TO 10' SOUTH OF THE CROSSING, PRESSURE TESTED.",
        "STORM P-8 CROSSES OVER THE EX. 8\" WATER MAIN IN MAPLE ST. WITH 18\" MIN. CLEARANCE; "
        "VERIFY BY POTHOLE BEFORE CONSTRUCTION."], sh.x1 - lgx - 0.1, size=NT)
    # structure table
    ty2 = yy - 5.45
    sh.line((x1 + 0.15, ty2 + 0.2), (sh.x1, ty2 + 0.2), lw="thin")
    pdm = {q["id"]: q for q in STM_PIPE_DATA + SAN_PIPE_DATA}
    rows = ["STORM"]
    stm_rows = [
        ("AD-1", "P-1 (NE) 6\"", pdm["P-1"]["inv_b"], "P-2 (N) 8\"", pdm["P-2"]["inv_a"]),
        ("CB-1", "P-2 (S) 8\"", pdm["P-2"]["inv_b"], "P-5 (E) 12\"", pdm["P-5"]["inv_a"]),
        ("MH-1", "P-5 (W) 12\" / P-3 (S) 8\"", (pdm["P-5"]["inv_b"], pdm["P-3"]["inv_b"]), "P-6 (E) 12\"",
         pdm["P-6"]["inv_a"]),
        ("CB-2", "P-6 (W) 12\" / P-4 (S) 8\"", (pdm["P-6"]["inv_b"], pdm["P-4"]["inv_b"]), "P-7 (E) 12\"",
         pdm["P-7"]["inv_a"]),
        ("CB-3", "P-7 (W) 12\"", pdm["P-7"]["inv_b"], "P-8 (E) 12\"", pdm["P-8"]["inv_a"]),
    ]
    for nm, ins, iv, out, ov in stm_rows:
        s_ = STM[nm]
        rim = _rim(nm)
        ivs = " / ".join(f"{q:.2f}" for q in (iv if isinstance(iv, tuple) else (iv,)))
        rows.append([nm, s_["desc"], f"N {10000 + s_['y']:,.2f}\nE {10000 + s_['x']:,.2f}",
                     f"{rim:.2f}", f"{ins}: {ivs}", f"{out}: {ov:.2f}", f"{rim - ov:.2f}'"])
    rows.append(["EX ST-2", "EXISTING 48\" STORM MH - CORE DRILL, BOOT, GROUT",
                 f"N {10000 + 90:,.2f}\nE {10000 + STM_X:,.2f}", f"{ex_rim('EX ST-2'):.2f}",
                 f"P-8 (W) 12\": {pdm['P-8']['inv_b']:.2f}", "EX. 12\" (S): 703.55",
                 f"{ex_rim('EX ST-2') - 703.55:.2f}'"])
    rows.append("SANITARY")
    for nm in ("CO-1", "CO-2", "SMH-1"):
        s_ = SAN[nm]
        rim = _rim(nm)
        pin = {"CO-1": "S-1", "CO-2": "S-2", "SMH-1": "S-3"}[nm]
        pout = {"CO-1": "S-2", "CO-2": "S-3", "SMH-1": "S-4"}[nm]
        rows.append([nm, s_["desc"], f"N {10000 + s_['y']:,.2f}\nE {10000 + s_['x']:,.2f}",
                     f"{rim:.2f}", f"{pin} (N) 6\": {pdm[pin]['inv_b']:.2f}",
                     f"{pout} (S) 6\": {pdm[pout]['inv_a']:.2f}", f"{rim - pdm[pout]['inv_a']:.2f}'"])
    rows.append(["EX SAN-3", "EXISTING 48\" SAN. MH - CORE DRILL, BOOT, RE-BENCH",
                 f"N {10000 + SAN_Y:,.2f}\nE {10000 + 75:,.2f}", f"{ex_rim('EX SAN-3'):.2f}",
                 f"S-4 (NW) 6\": {pdm['S-4']['inv_b']:.2f}", "EX. 8\" (E): 703.80",
                 f"{ex_rim('EX SAN-3') - 703.80:.2f}'"])
    cols = [("STR.", 0.62), ("TYPE / FRAME & GRATE", 3.55), ("LOCATION", 1.15), ("RIM", 0.62),
            ("INVERT(S) IN", 2.65), ("INVERT OUT", 1.6), ("DEPTH", 0.55)]
    h = table(sh, x1 + 0.35, ty2, cols, rows, row_h=0.17, size=TY + 0.8, title="STRUCTURE TABLE",
              align=["c", "l", "l", "c", "l", "l", "c"], wrap=True)
    # pipe table to the right? -> below
    py_ = ty2 - h - 0.3
    rows = []
    for q in STM_PIPE_DATA + SAN_PIPE_DATA:
        rows.append([q["id"], q["a"], q["b"], f"{q['size']}\"", q["mat"].replace("*", " / C900"),
                     f"{q['L']:.1f}", f"{q['s'] * 100:.2f}%", f"{q['inv_a']:.2f}", f"{q['inv_b']:.2f}"])
    rows.append(["W-1", "MAIN", "RM 112", "6\"", "DIP CL. 52 (FIRE)", f"{fire_len():.1f}", "-", "-", "-"])
    rows.append(["W-2", "MAIN", "RM 112", "2\"", "TYPE K COPPER", f"{dom_len():.1f}", "-", "-", "-"])
    cols = [("PIPE", 0.45), ("FROM", 0.72), ("TO", 0.72), ("SIZE", 0.4), ("MATERIAL", 1.45),
            ("LF", 0.55), ("SLOPE", 0.55), ("INV UP", 0.62), ("INV DN", 0.62)]
    h2 = table(sh, x1 + 0.35, py_, cols, rows, row_h=0.155, size=TY + 0.8, title="PIPE TABLE",
               align=["c", "c", "c", "c", "l", "r", "r", "r", "r"])
    notes_block(sh, x1 + 6.6, py_, "UTILITY NOTES", UTIL_NOTES, sh.x1 - x1 - 6.8, size=NT)
    # bottom-left under the plan: water service fittings schedule
    bt = ty - 0.55
    sh.line((sh.x0, bt + 0.2), (x1 + 0.15, bt + 0.2), lw="thin")
    rows = [["1", "8\" x 6\" STAINLESS TAPPING SLEEVE, 6\" RW GATE VALVE (AWWA C509) & BOX", "1 EA"],
            ["2", "6\" DIP CL. 52 FIRE SERVICE, POLY-WRAPPED, RESTRAINED JOINTS", f"{fire_len():.0f} LF"],
            ["3", "6\" MJ 90 DEG. BEND (HORIZ.) WITH CONCRETE THRUST BLOCK (12/C-500)", "1 EA"],
            ["4", "6\" MJ 90 DEG. BEND (VERT.) + RISER TO 1'-0\" ABOVE SLAB, BLIND FLANGE", "1 EA"],
            ["5", "2\" CORPORATION STOP (AWWA C800) AT MAIN", "1 EA"],
            ["6", "2\" TYPE K SOFT COPPER DOMESTIC SERVICE", f"{dom_len():.0f} LF"],
            ["7", "2\" CURB STOP & ADJUSTABLE BOX IN PARKWAY", "1 EA"],
            ["8", "SLEEVES THRU FOUNDATION WALL (SCH. 40 STEEL), LINK-SEAL, 2 EA", "2 EA"]]
    table(sh, sh.x0 + 0.3, bt, [("NO.", 0.35), ("WATER SERVICE ITEM", 5.6), ("QTY", 0.8)], rows,
          row_h=0.17, size=TY + 0.9, title="WATER SERVICE SCHEDULE", align=["c", "l", "r"])
    notes_block(sh, sh.x0 + 7.5, bt, "CONNECTION & SHUTDOWN REQUIREMENTS", [
        "ALL CONNECTIONS TO CITY MAINS AND MANHOLES ARE MADE OUTSIDE SCHOOL HOURS WITH THE CITY "
        "INSPECTOR PRESENT. 72-HOUR NOTICE TO OWNER AND CITY.",
        "NO INTERRUPTION OF WATER, SEWER OR FIRE PROTECTION SERVICE TO THE EXISTING SCHOOL IS "
        "PERMITTED; THE EXISTING SCHOOL SERVICES ARE NOT AFFECTED BY THIS WORK.",
        "ONE LANE OF MAPLE ST. AND PRAIRIE AVE. SHALL REMAIN OPEN AT ALL TIMES; FLAGGERS DURING "
        "BUS ARRIVAL AND DISMISSAL ARE NOT PERMITTED - SCHEDULE WORK BETWEEN 9:00 AM AND 2:00 PM.",
        "RECORD DRAWINGS: LOCATE ALL NEW PIPES, FITTINGS, VALVES AND STRUCTURES (X, Y, Z) BEFORE "
        "BACKFILL AND SUBMIT AS-BUILT DATA AT CLOSEOUT."], x1 - sh.x0 - 7.7, size=NT)


# ========================================================================================
# 13. C-500 CIVIL DETAILS
# ========================================================================================
from .cad import break_line, fmt_ftin  # noqa: E402

DS = 6.2          # detail label size (pt)
IN_ = 1 / 12.0


def _cv(sh, cell, scale, ext, dx=0.0, dy=0.0):
    """view fitting model extents ext=(x0, y0, x1, y1) centered in the cell above the title"""
    x0, y0, x1, y1 = ext
    w, h = (x1 - x0) * scale, (y1 - y0) * scale
    cx = cell["x"] + cell["w"] / 2 + dx
    cy = cell["y"] + 0.7 + (cell["h"] - 0.75) / 2 + dy
    return sh.view(cx - w / 2 - x0 * scale, cy - h / 2 - y0 * scale, scale)


def _dt(sh, cell, n, title, scale):
    sh.view_title(cell["x"] + 0.18, cell["y"] + 0.42, n, title, scale, width=cell["w"] - 0.8)


def dl(v, target, at, lines, side=None, size=DS, arrow="arrow"):
    callout(v, target, at, lines, size, side=side, arrow=arrow)


def _earth(v, pts):
    v.polygon(pts, lw=None, hatch="earth", hatch_kw=dict(scale=0.9, w="hair"))


def _gravel(v, pts, lw="thin"):
    v.polygon(pts, lw=lw, fill="white", hatch="gravel", hatch_kw=dict(scale=0.8))


def _concrete(v, pts, lw="med"):
    v.polygon(pts, lw=lw, fill="white", hatch="concrete", hatch_kw=dict(scale=0.9))


def _grass(v, x0, x1, y, col="black"):
    v.line((x0, y), (x1, y), lw="thin", color=col)
    n = int(abs(x1 - x0) / v.paper_len(0.06))
    for k in range(n):
        x = x0 + (x1 - x0) * (k + 0.5) / max(n, 1)
        h = v.paper_len(0.035)
        v.line((x, y), (x - h * 0.4, y + h), lw="hair")
        v.line((x, y), (x + h * 0.4, y + h), lw="hair")


def det_sidewalk(sh, c):
    v = _cv(sh, c, 0.75, (-3.6, -3.4, 7.6, 2.4), dy=0.25)
    W, t, b = 5.0, 5 * IN_, 4 * IN_
    _earth(v, [(-1.5, -t - b), (W + 1.5, -t - b), (W + 1.5, -1.6), (-1.5, -1.6)])
    _gravel(v, [(-0.5, -t - b), (W + 0.5, -t - b), (W + 0.5, -t), (-0.5, -t)])
    sl = 0.015 * W
    _concrete(v, [(0, -t + sl), (W, -t), (W, 0.0), (0, sl)])
    v.polygon([(-1.5, -0.04 + sl - 0.25), (-0.0, sl - 0.04), (0, -t - b + 0.02), (-0.5, -t - b),
               (-1.5, -t - b)], lw=None, fill="white")
    v.polygon([(W, -0.04), (W + 1.5, -0.04 - 0.08), (W + 1.5, -t - b), (W + 0.5, -t - b),
               (W, -t)], lw=None, fill="white")
    v.polygon([(-1.5, sl - 0.29), (0, sl - 0.04), (0, -t + sl), (-0.5, -t - b), (-1.5, -t - b)],
              lw=None, hatch="earth", hatch_kw=dict(scale=0.9, w="hair"))
    v.polygon([(W, -0.04), (W + 1.5, -0.12), (W + 1.5, -t - b), (W + 0.5, -t - b), (W, -t)],
              lw=None, hatch="earth", hatch_kw=dict(scale=0.9, w="hair"))
    _grass(v, -1.5, 0.0, sl - 0.04)
    _grass(v, W, W + 1.5, -0.04)
    break_line(v, (-1.5, -1.6), (-1.5, sl))
    break_line(v, (W + 1.5, -1.6), (W + 1.5, 0.1))
    v.dim((0, sl), (W, 0.0), 0.9, text="5'-0\" MIN. (AS SHOWN)")
    v.dim((W, 0.0), (W, -t), -0.0, text="")
    dl(v, (1.5, sl * 0.7), (-3.4, 1.6), ["5\" PCC SIDEWALK, 4,000 PSI,", "AIR-ENTRAINED, BROOM FINISH"], "r")
    dl(v, (3.5, -t - b / 2), (-3.4, -2.3), ["4\" CA-6 AGGREGATE BASE,", "COMPACTED TO 95% STD. PROCTOR"], "r")
    dl(v, (2.0, -1.2), (-3.4, -3.0), ["COMPACTED SUBGRADE"], "r")
    dl(v, (W - 0.03, -0.02), (5.6, 1.4), ["1/4\" R TOOLED EDGE"], "r")
    dl(v, (W + 0.8, -0.08), (5.9, -2.0), ["SOD ON 6\" TOPSOIL,", "1/2\" BELOW WALK"], "r")
    slope_arrow(v, (1.2, sl * 0.76 + 0.22), (3.8, sl * 0.24 + 0.22), "1.5% (2% MAX.)", size=DS - 0.4)
    # joint plan (inset)
    pv = sh.view(c["x"] + c["w"] - 2.25, c["y"] + 1.05, 1 / 16.0)
    pv.rect(0, 0, 25, 5, lw="thin")
    for x in (5, 10, 15, 20):
        pv.line((x, 0), (x, 5), lw="fine", dash="dashed")
    pv.line((25, 0), (25, 5), lw="med")
    Paper(sh.c).text((c["x"] + c["w"] - 2.25, c["y"] + 1.62), "JOINT PLAN (NTS)", size=DS - 0.6,
                     font=FONT_B)
    Paper(sh.c).mtext((c["x"] + c["w"] - 2.25, c["y"] + 0.98),
                      ["TOOLED CONTRACTION JOINT 1/4 DEPTH @ 5'-0\" O.C.",
                       "1/2\" EXP. JOINT @ 50' MAX. & AT STRUCTURES"], size=DS - 1.0)
    _dt(sh, c, 1, "PCC SIDEWALK", '3/4" = 1\'-0"')


def det_curb(sh, c):
    v = _cv(sh, c, 1.5, (-1.9, -1.15, 2.2, 1.85), dx=0.1, dy=0.2)
    # inches -> feet; x = 0 at back of curb, gutter lip at x = 1.5
    I = IN_
    pts = [(0, -5 * I), (0, 13 * I), (5.5 * I, 13 * I), (6 * I, 12.5 * I), (7 * I, 7 * I),
           (18 * I, 8 * I), (18 * I, 0), (6 * I, 0), (6 * I, -5 * I)]
    _earth(v, [(-1.2, -1.0), (2.6, -1.0), (2.6, -4 * I - 0.0), (-1.2, -4 * I)])
    _gravel(v, [(-0.5, -9 * I), (2.6, -9 * I), (2.6, -0.0), (18 * I, 0), (6 * I, 0), (6 * I, -5 * I),
                (0, -5 * I), (-0.5, -5 * I)])
    _concrete(v, pts)
    # HMA pavement beyond lip
    v.polygon([(18 * I, 8 * I), (2.6, 8.3 * I), (2.6, 0), (18 * I, 0)], lw="thin", fill="g20")
    v.line((18 * I, 6 * I), (2.6, 6.2 * I), lw="fine")
    # parkway soil behind the curb
    v.polygon([(-1.2, 13 * I - 0.02), (0, 13 * I), (0, -5 * I), (-1.2, -5 * I)], lw=None,
              hatch="earth", hatch_kw=dict(scale=0.9, w="hair"))
    _grass(v, -1.2, 0.0, 13 * I - 0.01)
    break_line(v, (2.6, -0.85), (2.6, 0.75))
    v.dim((0, 13 * I), (6 * I, 13 * I), 0.35, text="6\"")
    v.dim((6 * I, 13 * I), (18 * I, 13 * I), 0.35, text="1'-0\"")
    v.dim((0, 13 * I), (18 * I, 13 * I), 0.62, text="1'-6\"")
    v.dim((18 * I, 0), (18 * I, 8 * I), -0.25, text="8\"")
    v.dim((0, -5 * I), (0, 13 * I), 0.55, text="1'-6\"")
    v.dim((7 * I, 7 * I), (7 * I, 13 * I), -0.0, text="")
    dl(v, (6.6 * I, 10 * I), (-1.85, 1.35), ["6\" CURB FACE, 1\" BATTER"], "r")
    dl(v, (12 * I, 4 * I), (-1.85, -0.3), ["PCC CURB & GUTTER,", "4,000 PSI, AIR-ENTR."], "r")
    dl(v, (1.8, -7 * I), (0.9, -1.15), ["4\" CA-6 AGG. BASE (MIN. 6\"", "BEYOND BACK OF CURB)"], "r")
    dl(v, (2.3, 7.1 * I), (1.6, 1.55), ["MATCH EX. HMA", "PAVEMENT"], "r")
    dl(v, (-0.6, 13 * I), (-1.85, 0.85), ["TOPSOIL & SOD"], "r")
    Paper(sh.c).mtext((c["x"] + 0.25, c["y"] + 1.25),
                      ["CONTRACTION JOINTS @ 15' O.C. MAX.; 1\" EXPANSION JOINTS AT RADIUS",
                       "POINTS, STRUCTURES AND 100' MAX. MATCH EXISTING CURB AND",
                       "GUTTER LINE & GRADE. PER IDOT HIGHWAY STANDARD 606001."], size=DS - 0.6)
    _dt(sh, c, 2, "COMBINATION CONC. CURB & GUTTER B-6.12", '1 1/2" = 1\'-0"')


def det_patch(sh, c):
    v = _cv(sh, c, 0.5, (-5.6, -5.2, 5.6, 2.0), dy=0.25)
    s1, b1, t = 2 / 12, 3 / 12, 10 / 12
    T = s1 + b1 + t
    hw = 1.5
    sc_ = hw + 1.0
    # existing pavement both sides
    for sg in (-1, 1):
        x0, x1 = sg * sc_, sg * 4.5
        a, b = min(x0, x1), max(x0, x1)
        v.polygon([(a, 0), (b, 0), (b, -s1 - b1), (a, -s1 - b1)], lw="thin", fill="g40")
        v.polygon([(a, -s1 - b1), (b, -s1 - b1), (b, -T - 0.2), (a, -T - 0.2)], lw="thin",
                  fill="white", hatch="gravel", hatch_kw=dict(scale=0.7))
        _earth(v, [(a, -T - 0.2), (b, -T - 0.2), (b, -5.0), (a, -5.0)])
    # patch
    v.polygon([(-sc_, 0), (sc_, 0), (sc_, -s1), (-sc_, -s1)], lw="thin", fill="g40")
    v.polygon([(-sc_, -s1), (sc_, -s1), (sc_, -s1 - b1), (-sc_, -s1 - b1)], lw="thin", fill="g20")
    _concrete(v, [(-sc_, -s1 - b1), (sc_, -s1 - b1), (sc_, -T), (-sc_, -T)], lw="thin")
    # trench backfill
    v.polygon([(-hw, -T), (hw, -T), (hw, -5.0), (-hw, -5.0)], lw="thin", fill="white",
              hatch="gravel", hatch_kw=dict(scale=0.7))
    v.polygon([(-sc_, -T), (-hw, -T), (-hw, -T - 0.2), (-sc_, -T - 0.2)], lw=None, fill="white",
              hatch="gravel", hatch_kw=dict(scale=0.7))
    v.polygon([(hw, -T), (sc_, -T), (sc_, -T - 0.2), (hw, -T - 0.2)], lw=None, fill="white",
              hatch="gravel", hatch_kw=dict(scale=0.7))
    for x in (-sc_, sc_):
        v.line((x, 0.25), (x, -T), lw="med")
    break_line(v, (-4.5, -5.0), (4.5, -5.0))
    v.dim((-sc_, 0), (-hw, 0), 0.9, text="1'-0\"")
    v.dim((-hw, 0), (hw, 0), 0.9, text="TRENCH WIDTH")
    v.dim((hw, 0), (sc_, 0), 0.9, text="1'-0\"")
    dl(v, (-1.0, -s1 / 2), (-5.5, 1.55), ["2\" HMA SURFACE COURSE, MIX \"D\" N50"], "r")
    dl(v, (-0.4, -s1 - b1 / 2), (-5.5, -0.8), ["3\" HMA BINDER COURSE IL-19.0 N50"], "r")
    dl(v, (0.6, -s1 - b1 - t / 2), (-5.5, -1.5), ["10\" PCC BASE COURSE (HIGH EARLY)"], "r")
    dl(v, (0.5, -3.2), (-5.5, -3.6), ["CA-6 TRENCH BACKFILL, 8\" LIFTS,", "95% STD. PROCTOR"], "r")
    dl(v, (sc_, 0.15), (3.0, 1.6), ["SAWCUT FULL DEPTH;", "TACK COAT & SEAL EDGES"], "r")
    dl(v, (3.6, -0.2), (3.3, -2.4), ["EXISTING", "PAVEMENT"], "r")
    _dt(sh, c, 3, "HMA PAVEMENT PATCH (STREET)", '1/2" = 1\'-0"')


def det_stoop(sh, c):
    v = _cv(sh, c, 0.75, (-2.6, -4.0, 6.6, 2.6), dy=0.2)
    I = IN_
    L = 5.0
    top_w = -0.5 * I                 # top of stoop at the wall (relative to FFE = 0)
    top_e = top_w - 0.01 * L
    t = 6 * I
    # foundation wall + slab-on-grade inside (x < 0)
    v.polygon([(-1.0, -4.0), (0.0, -4.0), (0.0, -8 * I), (-0.33, -8 * I), (-0.33, 0.0),
               (-1.0, 0.0)], lw="med", fill="white", hatch="concrete", hatch_kw=dict(scale=0.9))
    v.polygon([(-2.5, 0.0), (-1.0, 0.0), (-1.0, -5 * I), (-2.5, -5 * I)], lw="thin", fill="white",
              hatch="concrete", hatch_kw=dict(scale=0.9))
    v.polygon([(-0.33, 0.0), (0.0, 0.0), (0.0, 1.9), (-0.33, 1.9)], lw="thin", fill="g20")
    v.line((-1.0, 0.0), (-1.0, 1.9), lw="thin")
    v.rect(-0.95, 0.0, 0.62, 0.06, lw="thin", fill="g40")
    _earth(v, [(0.0, -4.0), (6.4, -4.0), (6.4, top_e - 2.0), (0.0, top_e - 2.0)])
    _gravel(v, [(0.0, top_w - t - 0.5), (L - 1.0, top_e - t - 0.5), (L - 1.0, top_e - t),
                (0.0, top_w - t)])
    slab = [(0.04, top_w), (L, top_e), (L, top_e - 1.0), (L - 1.0, top_e - 1.0), (L - 1.0, top_e - t),
            (0.04, top_w - t)]
    _concrete(v, slab)
    v.line((0.02, top_w + 0.02), (0.02, top_w - t), lw="thin")
    for k in range(5):
        x = 0.4 + k * 1.0
        if x < L - 0.2:
            v.circle((x, top_w - t / 2 - 0.01 * x), 0.04, lw=None, fill="black")
    v.line((-0.6, top_w - t / 2 + 0.03), (1.6, top_w - t / 2 - 0.0), lw="thin")
    _grass(v, L, 6.4, top_e - 0.63)
    v.polygon([(L, top_e - 0.63), (6.4, top_e - 0.7), (6.4, top_e - 2.0), (L, top_e - 2.0)],
              lw=None, hatch="earth", hatch_kw=dict(scale=0.9, w="hair"))
    break_line(v, (-2.5, -4.0), (6.4, -4.0))
    v.dim((0.0, top_w), (L, top_e), 1.2, text="5'-0\" (STOOP DEPTH)")
    v.dim((L, top_e), (L, top_e - 1.0), -0.6, text="1'-0\"")
    v.dim((L - 1.0, top_e - 1.0), (L, top_e - 1.0), -0.35, text="1'-0\"")
    dl(v, (2.5, top_w - 0.12), (1.2, 2.3), ["6\" PCC STOOP, #4 @ 12\" E.W. CENTERED;", "TOP 1/2\" BELOW FFE (712.46),",
                                           "1% SLOPE AWAY FROM DOOR"], "r")
    dl(v, (0.6, top_w - t / 2 + 0.02), (-2.5, -1.3), ["#4 x 24\" DOWELS @ 12\" O.C.,", "EPOXY 6\" INTO FDN. WALL"], "r")
    dl(v, (0.02, top_w - 0.25), (-2.5, -0.55), ["1/2\" ISOLATION JT. & SEALANT"], "r")
    dl(v, (2.0, top_w - t - 0.3), (2.2, -2.7), ["6\" CA-6 BASE, 95% COMPACTION"], "r")
    dl(v, (4.6, top_e - 0.8), (5.0, -3.4), ["THICKENED EDGE", "(2) #4 CONT."], "r")
    dl(v, (-0.6, -2.5), (-2.5, -3.5), ["FOUNDATION WALL (S-301)"], "r")
    dl(v, (-0.6, 0.03), (-2.5, 1.4), ["THRESHOLD / FFE 712.50", "(SEE A-501, A-701)"], "r")
    _dt(sh, c, 4, "CONCRETE STOOP WITH THICKENED EDGE", '3/4" = 1\'-0"')


def det_ramp(sh, c):
    v = _cv(sh, c, 0.25, (-8.5, -4.5, 14.5, 15.0), dy=0.9)
    # curb & gutter along y = 0 (gutter y -1.5..0); ramp x 0..6, run y 0..6; landing y 6..10
    v.rect(-8.0, -2.0, 22.0, 0.5, lw="thin")
    v.line((-8.0, -1.5), (14.0, -1.5), lw="thin")
    v.line((-8.0, 0.0), (-5.0, 0.0), lw="thin")
    v.line((11.0, 0.0), (14.0, 0.0), lw="thin")
    v.line((-8.0, 0.5), (-5.0, 0.5), lw="thin")
    v.line((11.0, 0.5), (14.0, 0.5), lw="thin")
    v.polygon([(-5.0, 0.5), (0.0, 0.0), (0.0, 6.0)], lw="thin")
    v.polygon([(6.0, 0.0), (11.0, 0.5), (6.0, 6.0)], lw="thin")
    v.polygon([(0, 0), (6, 0), (6, 6), (0, 6)], lw="med")
    v.polygon([(0.0, 0.0), (6.0, 0.0), (6.0, 2.0), (0.0, 2.0)], lw="thin", hatch="dots",
              hatch_kw=dict(scale=0.45))
    v.rect(-8.0, 6.0, 22.0, 5.0, lw="thin")
    v.line((-3.5, 6.0), (-3.5, 11.0), lw="fine", dash="dashed")
    v.line((9.5, 6.0), (9.5, 11.0), lw="fine", dash="dashed")
    v.dim((0, 6.0), (6, 6.0), 6.2, text="6'-0\" (MATCH WALK, 4' MIN.)")
    v.dim((6.0, 0.0), (6.0, 2.0), -1.0, text="2'-0\"")
    v.dim((6.0, 2.0), (6.0, 6.0), -1.0, text="")
    slope_arrow(v, (3.0, 5.6), (3.0, 2.4), "8.33% MAX.", size=DS - 0.6)
    p = Paper(sh.c)
    dl(v, (1.0, 1.0), (-8.0, -4.0), ["DETECTABLE WARNING: CAST-IN-PLACE TRUNCATED", "DOMES, FULL WIDTH x 2'-0\", CONTRASTING COLOR"], "r")
    dl(v, (-2.0, 0.6), (-8.0, 3.5), ["FLARE 10% MAX."], "r")
    dl(v, (3.0, 8.5), (-8.0, 13.6), ["LANDING 4'x4' MIN., 2% MAX. EACH WAY"], "r")
    dl(v, (12.0, -0.75), (12.5, 3.0), ["CURB &", "GUTTER"], "r")
    dl(v, (3.0, -0.1), (12.5, -3.6), ["0\" LIP AT RAMP;", "GUTTER COUNTER-", "SLOPE 5% MAX."], "r")
    # schematic section A-A
    sx, sy = c["x"] + 0.35, c["y"] + 0.95
    q = Paper(sh.c)
    q.text((sx, sy + 0.42), "SECTION THRU RAMP (NTS)", size=DS - 0.6, font=FONT_B)
    q.polyline([(sx, sy), (sx + 0.6, sy + 0.04), (sx + 0.6, sy + 0.04), (sx + 1.6, sy + 0.24),
                (sx + 2.6, sy + 0.26)], lw="med")
    q.polyline([(sx, sy - 0.08), (sx + 2.6, sy - 0.08 + 0.18)], lw="fine", dash="dashed")
    q.text((sx + 0.3, sy - 0.03), "GUTTER", size=DS - 1.2, anchor="c", valign="top")
    q.text((sx + 1.1, sy + 0.22), "RAMP 8.33%", size=DS - 1.2, anchor="c", valign="bot")
    q.text((sx + 2.1, sy + 0.31), "LANDING 2%", size=DS - 1.2, anchor="c", valign="bot")
    _dt(sh, c, 5, "PERPENDICULAR CURB RAMP W/ DETECTABLE WARNING", '1/4" = 1\'-0"')


def det_silt(sh, c):
    v = _cv(sh, c, 1.0, (-2.7, -2.4, 3.2, 3.4), dy=0.15)
    # ground y = 0 sloping slightly; fabric at x = 0; trench x -0.5..0 depth 0.5
    _earth(v, [(-2.5, 0.0), (-0.5, 0.0), (-0.5, -0.5), (0.0, -0.5), (0.0, 0.0), (3.0, -0.15),
               (3.0, -2.2), (-2.5, -2.2)])
    _grass(v, -2.5, -0.5, 0.0)
    v.line((0.0, 0.0), (3.0, -0.15), lw="thin")
    v.polygon([(-0.5, 0.0), (0.0, 0.0), (0.0, -0.5), (-0.5, -0.5)], lw="thin", fill="white",
              hatch="sand", hatch_kw=dict(scale=0.8))
    v.rect(0.04, -2.0, 1.5 / 12, 4.5, lw="thin", fill="g20")           # stake
    v.polyline([(-0.48, -0.48), (-0.02, -0.48), (-0.02, 2.5)], lw="heavy")  # fabric
    for yy in (0.6, 1.4, 2.2):
        v.line((-0.12, yy), (0.04, yy), lw="thin")
    break_line(v, (-2.5, -2.2), (3.0, -2.2))
    v.dim((-0.02, 0.0), (-0.02, 2.5), 0.9, text="24\"-30\"")
    v.dim((0.06, -2.0), (0.06, 0.0), -0.75, text="18\" MIN.")
    v.dim((-0.5, -0.5), (0.0, -0.5), -0.35, text="6\"")
    v.dim((-0.5, -0.5), (-0.5, 0.0), -0.35, text="6\"")
    flow_arrow(v, (-2.4, 0.5), (-1.2, 0.5))
    Paper(sh.c).text(v.to_paper((-1.8, 0.75)), "FLOW", size=DS - 0.6, anchor="c", font=FONT_B)
    dl(v, (-0.02, 1.9), (-2.6, 2.9), ["WOVEN GEOTEXTILE SILT FENCE", "FABRIC (IDOT ART. 1080.02)"], "r")
    dl(v, (0.1, 1.0), (0.9, 2.6), ["1 1/8\" SQ. HARDWOOD STAKE,", "4'-0\" LONG, 8'-0\" O.C. MAX.,",
                                  "ON DOWNSTREAM SIDE"], "r")
    dl(v, (-0.25, -0.3), (-2.6, -1.0), ["TRENCH 6\"x6\"; FABRIC TOE", "LAID IN TRENCH, BACKFILLED", "& COMPACTED"], "r")
    dl(v, (0.08, 2.15), (0.9, 1.25), ["FASTEN FABRIC TO STAKE", "W/ (3) STAPLES OR TIES"], "r")
    Paper(sh.c).mtext((c["x"] + 0.25, c["y"] + 1.25),
                      ["INSTALL ON CONTOUR; TURN ENDS UPSLOPE (J-HOOK). OVERLAP JOINTS",
                       "AT A STAKE (WRAP 2 STAKES). REMOVE SEDIMENT AT 1/3 HEIGHT.",
                       "PER ILLINOIS URBAN MANUAL, CODE 920."], size=DS - 0.6)
    _dt(sh, c, 6, "SILT FENCE", '1" = 1\'-0"')


def det_inlet(sh, c):
    v = _cv(sh, c, 0.6, (-4.2, -4.0, 5.6, 2.6), dy=0.2)
    R = 2.0
    wt = 5 / 12.0
    # structure walls
    for sg in (-1, 1):
        x0 = sg * R
        x1 = sg * (R + wt)
        a, b = min(x0, x1), max(x0, x1)
        _concrete(v, [(a, -3.6), (b, -3.6), (b, -0.6), (a, -0.6)], lw="thin")
    # top slab, rings, frame & grate
    _concrete(v, [(-R - wt, -0.6), (-1.2, -0.6), (-1.2, -0.0), (-R - wt, -0.0)], lw="thin")
    _concrete(v, [(1.2, -0.6), (R + wt, -0.6), (R + wt, 0.0), (1.2, 0.0)], lw="thin")
    v.polygon([(-1.35, 0.0), (1.35, 0.0), (1.35, 0.35), (-1.35, 0.35)], lw="thin", fill="g40")
    v.polygon([(-1.15, 0.35), (1.15, 0.35), (1.15, 0.45), (-1.15, 0.45)], lw="thin", fill="g80")
    for k in range(9):
        x = -1.0 + k * 0.25
        v.line((x, 0.35), (x, 0.45), lw="fine", color="white")
    _earth(v, [(-4.0, -3.6), (-R - wt, -3.6), (-R - wt, 0.45), (-4.0, 0.45)])
    _earth(v, [(R + wt, -3.6), (4.0, -3.6), (4.0, 0.45), (R + wt, 0.45)])
    _grass(v, -4.0, -1.35, 0.45)
    _grass(v, 1.35, 4.0, 0.45)
    # filter bag
    bag = [(-1.1, 0.35), (-1.0, -0.2), (-0.95, -1.9), (-0.6, -2.3), (0.6, -2.3), (0.95, -1.9),
           (1.0, -0.2), (1.1, 0.35)]
    v.polyline(bag, lw="med", dash=[3, 1.5])
    v.polygon([(-0.95, -1.9), (-0.6, -2.3), (0.6, -2.3), (0.95, -1.9), (0.9, -1.5), (-0.9, -1.5)],
              lw=None, hatch="sand", hatch_kw=dict(scale=0.7))
    for x in (-0.95, 0.95):
        v.circle((x, -0.35), 0.1, lw="fine", fill="white")
    break_line(v, (-4.0, -3.6), (4.0, -3.6))
    dl(v, (0.0, 0.42), (-4.1, 2.2), ["EXISTING / PROPOSED FRAME & GRATE"], "r")
    dl(v, (-1.0, -1.0), (-4.1, -1.2), ["GEOTEXTILE FILTER BAG INSERT", "(DANDY BAG OR EQUAL) SIZED", "TO STRUCTURE"], "r")
    dl(v, (0.95, -0.35), (2.7, 1.6), ["OVERFLOW OPENINGS", "& LIFTING STRAPS"], "r")
    dl(v, (0.3, -2.0), (2.7, -2.2), ["SEDIMENT - EMPTY", "AT 1/2 FULL"], "r")
    dl(v, (R + 0.2, -3.0), (2.7, -3.3), ["CB / INLET STRUCTURE"], "r")
    Paper(sh.c).mtext((c["x"] + 0.25, c["y"] + 1.25),
                      ["CURB INLETS IN MAPLE ST. / PRAIRIE AVE.: CURB INLET FILTER WITH",
                       "OVERFLOW (DANDY CURB SACK OR EQUAL) - DO NOT BLOCK THE CURB OPENING.",
                       "INSTALL ON NEW STRUCTURES IMMEDIATELY AFTER SETTING THE GRATE."], size=DS - 0.6)
    _dt(sh, c, 7, "INLET PROTECTION", "NTS")


def det_entrance(sh, c):
    # plan at 1" = 20'
    v = sh.view(c["x"] + 0.75, c["y"] + c["h"] - 2.45, 1 / 20.0)
    v.rect(0, 0, 70, 24, lw="thin", fill="white", hatch="gravel", hatch_kw=dict(scale=0.9))
    v.rect(70, -6, 10, 36, lw="thin")
    v.line((76, -6), (76, 30), lw="fine")
    v.line((80, -6), (80, 30), lw="fine", dash="center")
    for sg in (-1, 1):
        y0 = 0 if sg < 0 else 24
        v.polyline([(70, y0), (66, y0 + sg * 4)], lw="thin")
    v.dim((0, 24), (70, 24), 3.0, text="70'-0\" (50' MIN.)")
    v.dim((0, 0), (0, 24), 3.0, text="24'-0\"")
    p = Paper(sh.c)
    p.text(v.to_paper((35, 12)), "CA-1 STONE", size=DS, font=FONT_B, anchor="c", valign="mid")
    p.mtext(v.to_paper((75, 34)), ["MAPLE ST.", "(EX. PAVEMENT)"], size=DS - 0.8, anchor="c", valign="bot")
    flow_arrow(v, (55, -4), (75, -4))
    p.text(v.to_paper((40, -6)), "EXIT TO MAPLE ST.", size=DS - 0.8, anchor="c", valign="top")
    p.text(v.to_paper((0, -14)), "PLAN", size=DS, font=FONT_B, valign="top")
    # section (NTS)
    sx, sy = c["x"] + 0.5, c["y"] + 1.85
    q = Paper(sh.c)
    q.text((sx, sy + 0.95), "SECTION (NTS)", size=DS, font=FONT_B)
    q.polygon([(sx, sy), (sx + 4.8, sy), (sx + 4.8, sy + 0.45), (sx, sy + 0.45)], lw="thin",
              fill="white", hatch="gravel", hatch_kw=dict(scale=0.9))
    q.line((sx, sy - 0.02), (sx + 4.8, sy - 0.02), lw="heavy", dash=[3, 1.5])
    q.polygon([(sx - 0.2, sy - 0.02), (sx + 5.0, sy - 0.02), (sx + 5.0, sy - 0.5), (sx - 0.2, sy - 0.5)],
              lw=None, hatch="earth", hatch_kw=dict(scale=0.9, w="hair"))
    q.line((sx + 4.8, sy + 0.45), (sx + 5.2, sy + 0.3), lw="thin")
    q.text((sx + 5.1, sy + 0.08), "8\"", size=DS, anchor="c")
    q.line((sx + 4.95, sy), (sx + 4.95, sy + 0.45), lw="fine")
    callout(sh.view(0, 0, 1), (sx + 1.0, sy + 0.3), (sx + 1.6, sy + 0.78),
            ["8\" CA-1 (2\"-3\") CRUSHED STONE"], DS, side="r")
    callout(sh.view(0, 0, 1), (sx + 2.6, sy - 0.02), (sx + 3.0, sy - 0.75),
            ["NON-WOVEN GEOTEXTILE (IDOT 1080.02) ON", "COMPACTED SUBGRADE"], DS, side="r")
    Paper(sh.c).mtext((c["x"] + 0.25, c["y"] + 0.92 + 0.0),
                      ["TOP-DRESS WITH STONE AS NEEDED; SWEEP MAPLE ST. DAILY. REMOVE AT",
                       "COMPLETION; RESTORE CURB, WALK & PARKWAY (C-200). IUM CODE 930."],
                      size=DS - 0.6)
    _dt(sh, c, 8, "STABILIZED CONSTRUCTION ENTRANCE", "AS NOTED")


def det_trench(sh, c):
    v = _cv(sh, c, 0.5, (-6.4, -8.2, 5.4, 1.4), dy=0.3)
    D = 1.0
    hw = 1.5
    inv = -6.5
    crown = inv + D
    _earth(v, [(-4.5, inv - 0.8), (-hw, inv - 0.8), (-hw, 0.0), (-4.5, 0.0)])
    _earth(v, [(hw, inv - 0.8), (4.5, inv - 0.8), (4.5, 0.0), (hw, 0.0)])
    _earth(v, [(-4.5, inv - 1.5), (4.5, inv - 1.5), (4.5, inv - 0.5), (-4.5, inv - 0.5)])
    _gravel(v, [(-hw, inv - 0.5), (hw, inv - 0.5), (hw, crown + 1.0), (-hw, crown + 1.0)])
    v.polygon([(-hw, crown + 1.0), (hw, crown + 1.0), (hw, -0.5), (-hw, -0.5)], lw="thin",
              fill="white", hatch="earth", hatch_kw=dict(scale=1.3, w="hair"))
    v.polygon([(-hw, -0.5), (hw, -0.5), (hw, 0.0), (-hw, 0.0)], lw="thin", fill="g10")
    _grass(v, -4.5, 4.5, 0.0)
    v.circle((0, inv + D / 2), D / 2, lw="med", fill="white")
    v.circle((0, inv + D / 2), D / 2 - 0.08, lw="fine")
    v.line((-hw, inv + D / 2), (hw, inv + D / 2), lw="fine", dash="center")
    v.line((-1.0, -1.5), (1.0, -1.5), lw="thin", dash=[2, 1])
    break_line(v, (-4.5, inv - 1.5), (4.5, inv - 1.5))
    v.dim((-hw, inv - 0.5), (hw, inv - 0.5), -0.9, text="O.D. + 24\" MAX.")
    v.dim((hw, inv - 0.5), (hw, inv), -0.6, text="6\"")
    v.dim((hw, crown), (hw, crown + 1.0), -0.6, text="12\"")
    v.dim((hw, inv + D / 2), (hw, crown), -0.6, text="")
    dl(v, (-0.6, -0.25), (-6.3, 0.9), ["6\" TOPSOIL & SOD / SEED (OR PAVEMENT", "PER 1/C-500, 3/C-500)"], "r")
    dl(v, (-0.6, -2.5), (-6.3, -2.2), ["FINAL BACKFILL: CA-6 @ 95% UNDER /", "WITHIN 2' OF PAVEMENT; SUITABLE",
                                      "EXCAV. MATL. @ 90% IN LAWNS"], "r")
    dl(v, (0.8, -1.5), (1.9, -0.9), ["DETECTABLE WARNING", "TAPE 18\" BELOW GRADE"], "r")
    dl(v, (-1.2, crown + 0.6), (-6.3, -4.6), ["INITIAL BACKFILL CA-7,", "12\" ABOVE PIPE"], "r")
    dl(v, (-1.1, inv + 0.3), (-6.3, -6.2), ["HAUNCHING CA-7 TO SPRINGLINE,", "SHOVEL-SLICED"], "r")
    dl(v, (-0.9, inv - 0.25), (-6.3, -7.5), ["BEDDING CA-7, 6\" MIN."], "r")
    dl(v, (0.35, inv + 0.85), (2.3, -4.2), ["PIPE (SEE C-400)"], "r")
    Paper(sh.c).mtext((c["x"] + 0.25, c["y"] + 1.15),
                      ["EXCAVATION PER OSHA 29 CFR 1926 SUBPART P (SLOPE, BENCH OR SHORE).",
                       "COPPER & DIP WATER: SAND BEDDING ACCEPTABLE. COMPACT IN 8\" LIFTS."],
                      size=DS - 0.6)
    _dt(sh, c, 9, "UTILITY TRENCH & BEDDING", '1/2" = 1\'-0"')


def det_cleanout(sh, c):
    v = _cv(sh, c, 0.75, (-3.6, -4.2, 4.2, 1.6), dy=0.25)
    r = 3.25 / 12
    _earth(v, [(-3.0, -4.0), (3.5, -4.0), (3.5, -0.5), (-3.0, -0.5)])
    v.polygon([(-0.75, 0.0), (0.75, 0.0), (0.75, -0.5), (-0.75, -0.5)], lw="med", fill="white",
              hatch="concrete", hatch_kw=dict(scale=0.9))
    v.polygon([(-3.0, 0.0), (-0.75, 0.0), (-0.75, -0.5), (-3.0, -0.5)], lw=None, hatch="earth",
              hatch_kw=dict(scale=0.9, w="hair"))
    v.polygon([(0.75, 0.0), (3.5, 0.0), (3.5, -0.5), (0.75, -0.5)], lw=None, hatch="earth",
              hatch_kw=dict(scale=0.9, w="hair"))
    _grass(v, -3.0, -0.75, 0.0)
    _grass(v, 0.75, 3.5, 0.0)
    v.polygon([(-0.4, 0.0), (0.4, 0.0), (0.4, -0.35), (-0.4, -0.35)], lw="thin", fill="g40")
    # riser + sweep to the main
    v.polygon([(-r, -0.35), (r, -0.35), (r, -2.6), (-r, -2.6)], lw="thin", fill="white")
    v.polygon([(-3.0, -3.2), (3.5, -3.2), (3.5, -3.2 + 2 * r), (-3.0, -3.2 + 2 * r)], lw="thin",
              fill="white")
    v.polyline([(-r, -2.6), (-r - 0.25, -2.9), (-r - 0.45, -3.2 + 2 * r)], lw="thin")
    v.polyline([(r, -2.6), (r + 0.25, -2.9), (r + 0.45, -3.2 + 2 * r)], lw="thin")
    v.polygon([(-r - 0.6, -3.2 - 0.33), (3.5, -3.2 - 0.33), (3.5, -3.2), (-r - 0.6, -3.2)], lw=None,
              hatch="gravel", hatch_kw=dict(scale=0.6))
    v.rect(-0.18, -0.35, 0.36, 0.08, lw="fine", fill="g80")
    flow_arrow(v, (1.5, -3.2 + r), (3.0, -3.2 + r))
    break_line(v, (-3.0, -4.0), (3.5, -4.0))
    v.dim((-0.75, 0.0), (0.75, 0.0), 0.8, text="18\" SQ.")
    v.dim((0.75, 0.0), (0.75, -0.5), -0.55, text="6\"")
    dl(v, (0.0, -0.05), (-3.5, 1.3), ["C.I. CLEANOUT FRAME & SCREW COVER", "(NEENAH R-1976 OR EQUAL), FLUSH W/ GRADE"], "r")
    dl(v, (0.6, -0.3), (1.3, 0.85), ["6\" CONC. COLLAR,", "18\"x18\""], "r")
    dl(v, (-0.1, -0.33), (-3.5, -1.0), ["THREADED PVC PLUG"], "r")
    dl(v, (-r, -1.8), (-3.5, -1.8), ["6\" PVC RISER (SDR-26)"], "r")
    dl(v, (-r - 0.3, -2.95), (-3.5, -2.55), ["COMBINATION WYE & 1/8 BEND", "(2-WAY: TWO WYES BACK TO BACK)"], "r")
    dl(v, (2.3, -3.2 + 2 * r), (1.6, -2.1), ["6\" PVC SANITARY"], "r")
    _dt(sh, c, 10, "SANITARY CLEANOUT", '3/4" = 1\'-0"')


def det_manhole(sh, c):
    v = _cv(sh, c, 0.4, (-8.6, -9.4, 6.6, 1.6), dy=0.2)
    R, wt = 2.0, 5 / 12
    base_t = 8 / 12
    inv = -5.0
    bot = inv - 2.0
    # walls
    for sg in (-1, 1):
        a, b = sorted((sg * R, sg * (R + wt)))
        _concrete(v, [(a, bot), (b, bot), (b, -1.0), (a, -1.0)], lw="thin")
    _concrete(v, [(-R - wt - 0.5, bot - base_t), (R + wt + 0.5, bot - base_t), (R + wt + 0.5, bot),
                  (-R - wt - 0.5, bot)], lw="thin")
    _concrete(v, [(-R - wt, -1.0), (-1.2, -1.0), (-1.2, -0.5), (-R - wt, -0.5)], lw="thin")
    _concrete(v, [(1.2, -1.0), (R + wt, -1.0), (R + wt, -0.5), (1.2, -0.5)], lw="thin")
    for k, y in enumerate((-0.5, -0.33)):
        v.polygon([(-1.6, y), (-1.2, y), (-1.2, y + 0.17), (-1.6, y + 0.17)], lw="fine", fill="g40")
        v.polygon([(1.2, y), (1.6, y), (1.6, y + 0.17), (1.2, y + 0.17)], lw="fine", fill="g40")
    v.polygon([(-1.6, -0.16), (1.6, -0.16), (1.6, 0.0), (-1.6, 0.0)], lw="thin", fill="g80")
    _earth(v, [(-8.0, bot - base_t - 0.6), (-R - wt, bot - base_t - 0.6), (-R - wt, 0.0), (-8.0, 0.0)])
    _earth(v, [(R + wt, bot - base_t - 0.6), (6.0, bot - base_t - 0.6), (6.0, 0.0), (R + wt, 0.0)])
    _gravel(v, [(-R - wt - 0.5, bot - base_t - 0.5), (R + wt + 0.5, bot - base_t - 0.5),
                (R + wt + 0.5, bot - base_t), (-R - wt - 0.5, bot - base_t)])
    _grass(v, -8.0, -1.6, 0.0)
    _grass(v, 1.6, 6.0, 0.0)
    # pipes
    v.polygon([(-8.0, inv), (-R - wt, inv), (-R - wt, inv + 1.0), (-8.0, inv + 1.0)], lw="thin",
              fill="white")
    v.polygon([(R + wt, inv - 0.1), (6.0, inv - 0.12), (6.0, inv + 0.9), (R + wt, inv + 0.9)],
              lw="thin", fill="white")
    # steps
    for k in range(int((-1.2 - inv) / 1.333)):
        y = -1.4 - k * 1.333
        v.line((R - 0.05, y), (R - 0.45, y), lw="med")
    v.line((-R, bot + 0.0), (R, bot), lw="fine")
    v.text((0, bot + 0.9), "2'-0\" SUMP (CB)", size=DS - 0.6, anchor="c", valign="mid")
    v.line((-R, inv), (R, inv), lw="fine", dash="dashed")
    break_line(v, (-8.0, bot - base_t - 0.6), (6.0, bot - base_t - 0.6))
    v.dim((-R, bot - 1.5), (R, bot - 1.5), 0, text="4'-0\" I.D.")
    v.dim((R + wt, inv), (R + wt, bot), -2.2, text="2'-0\"")
    dl(v, (0.0, -0.05), (-8.5, 1.4), ["FRAME & GRATE (CB): NEENAH R-4342; LID (MH):", "R-1712 \"STORM\" / \"SANITARY\""], "r")
    dl(v, (-1.4, -0.33), (-8.5, -1.1), ["ADJ. RINGS 8\" MAX., MORTARED;", "CHIMNEY SEAL ON SANITARY"], "r")
    dl(v, (-R - 0.2, -2.5), (-8.5, -2.6), ["48\" PRECAST REINF. CONC.", "ASTM C478, 5\" WALL"], "r")
    dl(v, (-R - wt - 0.1, inv + 0.5), (-8.5, -4.0), ["FLEXIBLE BOOT", "ASTM C923 (TYP.)"], "r")
    dl(v, (R - 0.3, -2.733), (3.2, -2.0), ["STEPS @ 16\" O.C.", "(M.A. INDUSTRIES", "PS2-PF OR EQUAL)"], "r")
    dl(v, (0.0, bot - base_t / 2), (-8.5, -8.4), ["8\" PRECAST BASE; MH: CONC. BENCH", "& CHANNEL; CB: 2' SUMP"], "r")
    dl(v, (2.5, bot - base_t - 0.3), (3.0, -8.8), ["6\" CA-7 BASE"], "r")
    _dt(sh, c, 11, "STORM MANHOLE / CATCH BASIN (48\")", '3/8" = 1\'-0"')


def det_thrust(sh, c):
    v = _cv(sh, c, 0.6, (-3.6, -3.0, 5.6, 4.2), dy=1.1)
    D = 0.6
    # 90 deg bend: pipe from west along y=0 turning north at x=0
    v.polygon([(-3.0, -D / 2), (0.0, -D / 2), (0.0, D / 2), (-3.0, D / 2)], lw="thin", fill="white")
    v.polygon([(-D / 2, 0.0), (D / 2, 0.0), (D / 2, 3.0), (-D / 2, 3.0)], lw="thin", fill="white")
    v.polygon([(-D / 2, D / 2), (0.0, D / 2), (D / 2, 0.0), (D / 2, -D / 2), (0.0, -D / 2)],
              lw="thin", fill="white")
    blk = [(D / 2, -D / 2), (D / 2 + 0.05, D / 2), (2.2, 1.6), (2.2, -2.2), (-1.6, -2.2),
           (-D / 2, -D / 2 - 0.05)]
    _concrete(v, [(0.0 + D / 2, -D / 2), (2.2, 1.0), (2.2, -2.2), (-1.0, -2.2), (0.0, -D / 2)],
              lw="med")
    _earth(v, [(2.2, 1.5), (3.0, 1.5), (3.0, -2.6), (-1.6, -2.6), (-1.6, -2.2), (2.2, -2.2)])
    flow_arrow(v, (-0.5, -0.4), (1.2, -1.4))
    dl(v, (1.4, -1.4), (2.8, 3.4), ["CONCRETE THRUST BLOCK, 3,000 PSI,", "POURED AGAINST UNDISTURBED SOIL"], "r")
    dl(v, (0.15, 0.25), (-3.5, 2.6), ["MJ 90 DEG. BEND WITH", "RESTRAINED JOINTS"], "r")
    dl(v, (0.0, -D / 2), (-3.5, -2.4), ["KEEP JOINTS & BOLTS", "CLEAR OF CONCRETE;", "POLY SHEET BETWEEN"], "r")
    p = Paper(sh.c)
    p.text(v.to_paper((-3.0, 3.6)), "PLAN - HORIZONTAL BEND", size=DS, font=FONT_B)
    rows = [["90 DEG. BEND", "6.0"], ["45 DEG. BEND", "3.0"], ["22 1/2 DEG. BEND", "1.5"],
            ["11 1/4 DEG. BEND", "1.0"], ["TEE / PLUG / DEAD END", "4.0"]]
    table(sh, c["x"] + 0.6, c["y"] + 2.3, [("6\" FITTING", 2.0), ("MIN. BEARING AREA (SF)", 2.4)],
          rows, row_h=0.16, size=DS - 0.4, align=["l", "c"])
    sh.mtext((c["x"] + 0.6, c["y"] + 1.18), ["BASED ON 200 PSI TEST PRESSURE AND 2,000 PSF ALLOWABLE",
                                             "SOIL BEARING. VERTICAL BEND AT BUILDING: RESTRAINED",
                                             "JOINTS + 1 CY CONCRETE BLOCK UNDER BEND."], size=DS - 0.6)
    _dt(sh, c, 12, "THRUST BLOCK (WATER SERVICE)", "NTS")


def det_tpf(sh, c):
    v = _cv(sh, c, 0.375, (-4.0, -2.8, 13.5, 6.2), dy=0.9)
    _earth(v, [(-3.0, -2.5), (13.0, -2.5), (13.0, 0.0), (-3.0, 0.0)])
    _grass(v, -3.0, 13.0, 0.0)
    for x in (0.0, 6.0, 12.0):
        v.rect(x - 0.06, -2.0, 0.12, 6.0, lw="thin", fill="g60")
    v.polygon([(0.0, 0.2), (12.0, 0.2), (12.0, 4.0), (0.0, 4.0)], lw="thin", hatch="ansi37",
              hatch_kw=dict(spacing=0.06, w="hair"))
    v.rect(4.2, 2.2, 3.6, 1.2, lw="thin", fill="white")
    Paper(sh.c).mtext(v.to_paper((6.0, 2.8)), ["TREE PROTECTION", "ZONE - KEEP OUT"], size=DS - 1.2,
                      anchor="c", valign="mid", font=FONT_B)
    break_line(v, (-3.0, -2.5), (13.0, -2.5))
    v.dim((0.0, 4.0), (6.0, 4.0), 1.0, text="6'-0\" O.C. (8' MAX.)")
    v.dim((12.0, 0.0), (12.0, 4.0), -1.0, text="4'-0\"")
    v.dim((12.0, -2.0), (12.0, 0.0), -1.0, text="2'-0\"")
    dl(v, (3.0, 3.6), (-3.8, 5.6), ["4' HIGH ORANGE HIGH-DENSITY POLYETHYLENE", "BARRIER FENCE, FASTENED W/ (3) TIES PER POST"], "r")
    dl(v, (6.0, 1.0), (-3.8, -1.2), ["STEEL T-POST, 6' LONG,", "DRIVEN 2' MIN."], "r")
    dl(v, (9.0, 2.0), (9.5, 5.4), ["SIGN EVERY 50'", "(BILINGUAL)"], "r")
    sh.mtext((c["x"] + 0.3, c["y"] + 1.95), [
        "LOCATE AT THE DRIP LINE OR 1'-0\" RADIUS PER INCH OF DBH, WHICHEVER IS",
        "GREATER, AND AROUND THE PLAYGROUND (C-300). INSTALL BEFORE ANY WORK.",
        "NO STORAGE, PARKING, STOCKPILING, WASHOUT, TRENCHING OR GRADE CHANGE",
        "INSIDE THE FENCE. ROOTS > 1\" EXPOSED BY EXCAVATION: CLEAN-CUT WITH A",
        "SAW, COVER WITHIN 24 HRS. REMOVE FENCE AFTER FINAL RESTORATION."], size=DS - 0.5)
    _dt(sh, c, 13, "TREE PROTECTION FENCE", '3/8" = 1\'-0"')


CIVIL_GENERAL_NOTES = [
    "##GENERAL",
    "WORK SHALL CONFORM TO THE IDOT STANDARD SPECIFICATIONS FOR ROAD AND BRIDGE CONSTRUCTION, THE "
    "STANDARD SPECIFICATIONS FOR WATER AND SEWER MAIN CONSTRUCTION IN ILLINOIS (CURRENT EDITIONS), "
    "THE ILLINOIS URBAN MANUAL, THE ILLINOIS PLUMBING CODE (FOR BUILDING SERVICES) AND CITY OF "
    "CEDAR PRAIRIE STANDARDS. WHERE REQUIREMENTS CONFLICT, THE MORE STRINGENT GOVERNS.",
    "CIVIL ELEVATIONS ARE NAVD88. ARCH. 100'-0\" = EL. 712.50 = FFE OF THE ADDITION AND THE "
    "EXISTING SCHOOL. HORIZONTAL: LOCAL SITE GRID, GRID 1 / GRID D = N 10,000.00, E 10,000.00.",
    "THE SCHOOL IS OCCUPIED DURING CONSTRUCTION. OWNER CONSTRAINTS (ACCESS FROM MAPLE ST. ONLY, "
    "STAGING AREA, LIMIT OF WORK, NO DELIVERIES 7:30-8:15 AM AND 2:45-3:30 PM, SUMMER TIE-IN) ARE "
    "SHOWN ON C-200 / C-300. THE CONTRACTOR PREPARES THE SITE LOGISTICS PLAN.",
    "CALL JULIE (811) 48 HOURS BEFORE DIGGING. PRIVATE UTILITY LOCATES ON SCHOOL PROPERTY BY THE "
    "CONTRACTOR. PROTECT ALL UTILITIES TO REMAIN.",
    "##MATERIALS",
    "PCC: 4,000 PSI AT 28 DAYS, AIR-ENTRAINED 6% +/-1.5%, MAX. SLUMP 4\", IDOT CLASS SI. CURING "
    "COMPOUND IDOT TYPE I. REINFORCING ASTM A615 GRADE 60. NO CONCRETE ON FROZEN SUBGRADE.",
    "AGGREGATE: CA-6 (BASE COURSE), CA-7 (BEDDING / INITIAL BACKFILL), CA-1 (CONSTRUCTION "
    "ENTRANCE) PER IDOT SECTION 1004. HMA: IDOT SECTION 406, MIX D N50 SURFACE, IL-19.0 BINDER.",
    "TOPSOIL: STOCKPILED SITE TOPSOIL, SCREENED, 6\" MIN. AFTER SETTLEMENT IN LAWN AREAS.",
    "##TESTING & ACCEPTANCE",
    "OWNER'S TESTING AGENCY: COMPACTION (1 PER 2,500 SF PER LIFT, 1 PER 100 LF OF TRENCH PER 2' OF "
    "DEPTH), CONCRETE (SLUMP, AIR, TEMP., 4 CYLINDERS PER 50 CY OR DAILY). FAILED TESTS RETESTED AT "
    "THE CONTRACTOR'S EXPENSE.",
    "WATER: PRESSURE / LEAKAGE (AWWA C600) AND DISINFECTION (AWWA C651) WITH 2 CONSECUTIVE "
    "SATISFACTORY BACTERIOLOGICAL SAMPLES. SEWERS: AIR TEST, MANDREL TEST, MANHOLE VACUUM TEST "
    "(ASTM C1244).",
    "##RESTORATION & CLOSEOUT",
    "RESTORE ALL AREAS DISTURBED OUTSIDE THE LIMIT OF WORK TO EQUAL OR BETTER CONDITION AT NO "
    "COST. WARRANTY ON SOD AND SEED UNTIL 70% UNIFORM COVER IS ACHIEVED.",
    "SUBMIT AS-BUILT DRAWINGS SHOWING FINAL LOCATIONS, INVERTS AND RIMS OF ALL UTILITIES AND "
    "STRUCTURES, PREPARED BY AN ILLINOIS PROFESSIONAL LAND SURVEYOR.",
]


def draw_c500(sh):
    cells = sh.cells(5, 3)
    fns = [det_sidewalk, det_curb, det_patch, det_stoop, det_ramp,
           det_silt, det_inlet, det_entrance, det_trench, det_cleanout,
           det_manhole, det_thrust, det_tpf]
    for fn, cl in zip(fns, cells):
        fn(sh, cl)
    nc = sh.merge_cells(cells, [13, 14])
    # erase the divider between the two merged cells
    xm = cells[14]["x"]
    sh.line((xm, nc["y"] + 0.02), (xm, nc["y"] + nc["h"] - 0.02), lw=1.4, color="white")
    notes_block(sh, nc["x"] + 0.25, nc["y"] + nc["h"] - 0.25, "CIVIL GENERAL NOTES",
                CIVIL_GENERAL_NOTES, nc["w"] - 0.5, size=NT)


# ========================================================================================
SHEETS = [
    ("C-100", "EXISTING CONDITIONS &\nSITE DEMOLITION PLAN", draw_c100),
    ("C-200", "SITE LAYOUT &\nPAVING PLAN", draw_c200),
    ("C-300", "GRADING & EROSION\nCONTROL PLAN", draw_c300),
    ("C-400", "SITE UTILITY PLAN", draw_c400),
    ("C-500", "CIVIL DETAILS", draw_c500),
]
