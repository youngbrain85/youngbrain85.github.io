"""
Building information model for the practice project (single source of truth).
Units: feet. x = east, y = north. See DESIGN.md.

Everything that appears on more than one sheet (grids, walls, openings, rooms, finishes,
schedules) is defined here so plans, elevations, schedules and the quantity workbook agree.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

IN = 1 / 12.0  # one inch in feet

# ----------------------------------------------------------------------------------------
# Grids & levels
# ----------------------------------------------------------------------------------------
GRID_X = {"1": 0.0, "2": 30.0, "3": 60.0, "4": 90.0, "5": 120.0, "6": 150.0}
GRID_Y = {"D": 0.0, "C": 30.0, "B": 42.0, "A": 72.0}
LINK_GRID_X = {"L1": -35.0, "L2": -18.0}
EXIST_FACE_X = -36.0          # east face of existing building
EXIST_WALL_T = 1.0            # existing exterior wall thickness

LEVELS = {
    "BOF": 95 + 4 * IN,       # bottom of exterior footing
    "TOF": 96 + 4 * IN,       # top of exterior footing
    "LEDGE": 99.0,            # brick ledge
    "GRADE": 99 + 4 * IN,     # finish grade at building / T.O. foundation wall
    "L1": 100.0,
    "L2": 114.0,
    "LINK_ROOF": 114.0,
    "LINK_PARAPET": 116 + 8 * IN,
    "ROOF": 128.0,
    "PARAPET": 131 + 4 * IN,
    "EXIST_ROOF": 113 + 4 * IN,
}
CIVIL_DATUM = 712.50          # civil elevation of arch 100'-0"
CEILING_CUT = 4.0             # plan cut height above level


def civil(el_arch: float) -> float:
    return CIVIL_DATUM + (el_arch - 100.0)


# ----------------------------------------------------------------------------------------
# Wall types
# ----------------------------------------------------------------------------------------
CMU_T = 7.625 * IN
WALL_TYPES = {
    "EW-1": dict(thk=15.25 * IN, mat="cavity", rated=None,
                 desc="EXTERIOR CAVITY WALL: 3 5/8\" MODULAR FACE BRICK, 2\" AIR SPACE, 2\" POLYISO "
                      "INSULATION, FLUID-APPLIED AIR/WATER BARRIER, 8\" CMU BACKUP (REINF.), PAINTED INT. FACE"),
    "P1": dict(thk=CMU_T, mat="cmu", rated=None,
               desc="8\" CMU, PAINTED, TO UNDERSIDE OF STRUCTURE"),
    "P2": dict(thk=CMU_T, mat="cmu", rated="1 HR",
               desc="8\" CMU, 1-HOUR FIRE-RESISTANCE RATED, TO UNDERSIDE OF DECK, FIRESTOP HEAD JOINT"),
    "P3": dict(thk=(3.625 + 1.25) * IN, mat="stud", rated=None,
               desc="3 5/8\" 20 GA. MTL. STUDS @ 16\" O.C., 5/8\" GWB EACH SIDE, SOUND BATT, TO 6\" ABOVE CLG."),
    "P4": dict(thk=(6.0 + 1.25) * IN, mat="stud", rated=None,
               desc="6\" 20 GA. MTL. STUDS @ 16\" O.C., 5/8\" MOISTURE-RESISTANT GWB EACH SIDE, TO STRUCTURE"),
}
# exterior wall layer offsets from the grid line, positive toward the exterior (feet)
EW_LAYERS = [
    ("cmu", -3.8125 * IN, 3.8125 * IN),
    ("insul", 3.8125 * IN, 5.8125 * IN),
    ("air", 5.8125 * IN, 7.8125 * IN),
    ("brick", 7.8125 * IN, 11.4375 * IN),
]
EW_OUT = 11.4375 * IN   # grid to exterior face of brick
EW_IN = 3.8125 * IN     # grid to interior face of CMU

# ----------------------------------------------------------------------------------------
# Exterior envelope
# ----------------------------------------------------------------------------------------
# CCW outline of grid lines (exterior is always to the RIGHT of travel).
OUTLINE = {
    "L1": [(0, 0), (150, 0), (150, 72), (0, 72), (0, 42), (EXIST_FACE_X, 42), (EXIST_FACE_X, 30),
           (0, 30)],
    "L2": [(0, 0), (150, 0), (150, 72), (0, 72)],
}

# named exterior wall segments (start -> end, CCW). axis 'x' = horizontal wall.
EXT_SEGS = {
    "S": ((0, 0), (150, 0)),
    "E": ((150, 0), (150, 72)),
    "N": ((150, 72), (0, 72)),
    "W1": ((0, 72), (0, 42)),       # classroom 101 / 201 west wall (both levels)
    "LN": ((0, 42), (EXIST_FACE_X, 42)),
    "LS": ((EXIST_FACE_X, 30), (0, 30)),
    "W2": ((0, 30), (0, 0)),        # stair 1 west wall
    "W0": ((0, 42), (0, 30)),       # L2 only: corridor end above link roof
}
SEG_LEVELS = {"S": ("L1", "L2"), "E": ("L1", "L2"), "N": ("L1", "L2"), "W1": ("L1", "L2"),
              "LN": ("L1",), "LS": ("L1",), "W2": ("L1", "L2"), "W0": ("L2",)}


def seg_axis(seg):
    (x0, y0), (x1, y1) = EXT_SEGS[seg] if isinstance(seg, str) else seg
    return "x" if abs(y1 - y0) < 1e-9 else "y"


def seg_outward(seg):
    """unit vector pointing to the exterior for a named exterior segment"""
    (x0, y0), (x1, y1) = EXT_SEGS[seg]
    dx, dy = x1 - x0, y1 - y0
    L = (dx * dx + dy * dy) ** 0.5
    return (dy / L, -dx / L)  # right normal


# ----------------------------------------------------------------------------------------
# Interior walls
# ----------------------------------------------------------------------------------------
@dataclass
class Wall:
    id: str
    type: str
    p1: tuple
    p2: tuple
    levels: tuple = ("L1", "L2")

    @property
    def axis(self):
        return "x" if abs(self.p1[1] - self.p2[1]) < 1e-9 else "y"

    @property
    def length(self):
        return ((self.p2[0] - self.p1[0]) ** 2 + (self.p2[1] - self.p1[1]) ** 2) ** 0.5

    def poly(self, extend=0.0):
        t = WALL_TYPES[self.type]["thk"]
        ls = LineString([self.p1, self.p2])
        return ls.buffer(t / 2, cap_style=2, join_style=2) if not extend else \
            LineString(_extend(self.p1, self.p2, extend)).buffer(t / 2, cap_style=2, join_style=2)


def _extend(p1, p2, e):
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    L = (dx * dx + dy * dy) ** 0.5
    ux, uy = dx / L, dy / L
    return [(p1[0] - ux * e, p1[1] - uy * e), (p2[0] + ux * e, p2[1] + uy * e)]


BOTH = ("L1", "L2")
WALLS = [
    # corridor walls
    Wall("C1", "P2", (0, 30), (12, 30)),
    Wall("C2", "P1", (12, 30), (21, 30)),
    Wall("C3", "P2", (21, 30), (30, 30)),
    Wall("C4", "P1", (30, 30), (150, 30)),
    Wall("B1", "P1", (0, 42), (138, 42)),
    Wall("B2", "P2", (138, 42), (150, 42)),
    # north demising
    Wall("N2", "P1", (30, 42), (30, 72)),
    Wall("N3", "P1", (60, 42), (60, 72)),
    Wall("N4", "P1", (90, 42), (90, 72)),
    Wall("N5", "P1", (120, 42), (120, 72)),
    Wall("N6", "P2", (138, 42), (138, 72)),
    # south side
    Wall("S12", "P2", (12, 0), (12, 30)),
    Wall("E21", "P2", (21, 21), (21, 30)),
    Wall("E21H", "P2", (21, 21), (30, 21)),
    Wall("S2a", "P1", (30, 0), (30, 21)),
    Wall("S2b", "P2", (30, 21), (30, 30)),
    Wall("T20", "P4", (20, 0), (20, 8.5)),
    Wall("T85", "P3", (12, 8.5), (20, 8.5)),
    Wall("B12a", "P1", (30, 12), (41, 12)),
    Wall("B12b", "P1", (49, 12), (60, 12)),
    Wall("B41", "P1", (41, 12), (41, 30)),
    Wall("B49", "P1", (49, 12), (49, 30)),
    Wall("B20", "P1", (41, 20), (49, 20)),
    Wall("S3", "P1", (60, 0), (60, 30)),
    Wall("S4", "P1", (90, 0), (90, 30)),
    Wall("S5", "P1", (120, 0), (120, 30)),
    # link cross-corridor wall (level 1 only)
    Wall("X0", "P1", (0, 30), (0, 42), ("L1",)),
]
WALL_BY_ID = {w.id: w for w in WALLS}


# ----------------------------------------------------------------------------------------
# Openings
# ----------------------------------------------------------------------------------------
@dataclass
class Opening:
    """Door / window / storefront / louver in a wall.

    wall  : interior Wall id or exterior segment name (EXT_SEGS)
    c     : center coordinate ALONG the wall axis (x for horizontal walls, y for vertical)
    w     : masonry/rough opening width (ft)
    sill, head : absolute elevations (ft, arch datum)
    """
    id: str
    kind: str              # door | window | storefront | louver | elevator
    type: str              # window/storefront type tag, or door type letter
    level: str             # level the opening belongs to (for tags & schedules)
    wall: str
    c: float
    w: float
    sill: float
    head: float
    # door specifics
    leaf: float = 3.0      # leaf width (each leaf for pairs)
    pair: bool = False
    hinge: str = "lo"      # lo / hi end of the opening (singles)
    swing: str = "+"       # + / - (toward +y for horizontal walls, +x for vertical walls)
    frame: str = ""        # F1 / F2 / F3 / SF
    side: str = "hi"       # sidelight side for F2
    hw: str = ""
    rating: str = ""
    room: str = ""
    remarks: str = ""
    dmat: str = ""         # door material WD / HM / AL
    fmat: str = ""         # frame material HM / AL

    @property
    def lo(self):
        return self.c - self.w / 2

    @property
    def hi(self):
        return self.c + self.w / 2

    @property
    def height(self):
        return self.head - self.sill


def _host(wall):
    if wall in EXT_SEGS:
        return EXT_SEGS[wall]
    w = WALL_BY_ID[wall]
    return (w.p1, w.p2)


def opening_axis(o: Opening):
    (x0, y0), (x1, y1) = _host(o.wall)
    return "x" if abs(y1 - y0) < 1e-9 else "y"


def opening_line_coord(o: Opening):
    """the fixed coordinate of the host wall line (y for horizontal walls, x for vertical)"""
    (x0, y0), (x1, y1) = _host(o.wall)
    return y0 if opening_axis(o) == "x" else x0


L1, L2 = LEVELS["L1"], LEVELS["L2"]
DH = 7 + 4 * IN    # door MO head height (7'-0" door + 4" head)

OPENINGS: list[Opening] = []


def _door(id, level, wall, c, frame, swing, hinge="lo", hw="", dtype="A", rating="", room="",
          side="hi", remarks="", dmat="WD", fmat="HM", leaf=3.0):
    base = LEVELS[level]
    w = {"F1": 3 + 4 * IN, "F2": 4 + 8 * IN, "F3": 6 + 4 * IN}[frame]
    OPENINGS.append(Opening(id, "door", dtype, level, wall, c, w, base, base + DH, leaf=leaf,
                            pair=(frame == "F3"), hinge=hinge, swing=swing, frame=frame, side=side,
                            hw=hw, rating=rating, room=room, remarks=remarks, dmat=dmat, fmat=fmat))


def _win(id, typ, level, wall, c, sill_aff=2 + 8 * IN, kind="window", w=None, h=None,
         sill_abs=None):
    base = LEVELS[level]
    W, H = WINDOW_TYPES[typ]["mo"]
    if w:
        W = w
    if h:
        H = h
    sill = sill_abs if sill_abs is not None else base + sill_aff
    OPENINGS.append(Opening(id, kind, typ, level, wall, c, W, sill, sill + H))


WINDOW_TYPES = {
    "W-A": dict(mo=(6 + 8 * IN, 6 + 8 * IN), desc="ALUM. WINDOW: (2) FIXED LITES OVER (2) AWNING VENTS",
                sill="CS-1 CAST STONE", glazing="1\" INSUL. LOW-E"),
    "W-B": dict(mo=(4.0, 6 + 8 * IN), desc="ALUM. WINDOW: FIXED LITE OVER AWNING VENT",
                sill="CS-1 CAST STONE", glazing="1\" INSUL. LOW-E"),
    "W-C": dict(mo=(4.0, 18 + 8 * IN), desc="ALUM. STOREFRONT STRIP AT STAIR, (4) LITES HIGH",
                sill="PREFIN. MTL. SILL", glazing="1\" INSUL. LOW-E, TEMPERED"),
    "SF-1": dict(mo=(10 + 8 * IN, 9 + 4 * IN),
                 desc="ALUM. STOREFRONT ENTRANCE: PAIR 3'-0\"x7'-0\" DOORS, SIDELITES, TRANSOM",
                 sill="THRESHOLD", glazing="1\" INSUL. LOW-E, TEMPERED"),
    "SF-2": dict(mo=(10 + 8 * IN, 6 + 8 * IN), desc="ALUM. STOREFRONT WINDOW, 3 BAYS",
                 sill="CS-1 CAST STONE", glazing="1\" INSUL. LOW-E"),
    "SF-3": dict(mo=(32.0, 9 + 4 * IN), desc="ALUM. STOREFRONT, 6 BAYS @ 5'-4\", ON 8\" CONC. CURB",
                 sill="CONC. CURB", glazing="1\" INSUL. LOW-E, TEMPERED"),
    "LV-1": dict(mo=(4.0, 4.0), desc="ALUM. LOUVER (FURNISHED BY DIV. 23), OPENING & LINTEL BY GC",
                 sill="PREFIN. MTL. SILL", glazing="-"),
}

# ---- exterior windows (both levels) ----
_CLASS_N = {"101": 0, "102": 30, "103": 60, "104": 90}
_CLASS_S = {"113": 60, "114": 90, "115": 120}
for lev, off in (("L1", 0), ("L2", 100)):
    for rm, x0 in _CLASS_N.items():
        r = str(int(rm) + off)
        for k, dx in enumerate((5 + 8 * IN, 15.0, 24 + 4 * IN)):
            _win(f"{r}-W{k + 1}", "W-A", lev, "N", x0 + dx)
    for rm, x0 in _CLASS_S.items():
        r = str(int(rm) + off)
        for k, dx in enumerate((5 + 8 * IN, 15.0, 24 + 4 * IN)):
            _win(f"{r}-W{k + 1}", "W-A", lev, "S", x0 + dx)
    r = str(101 + off)
    _win(f"{r}-W4", "W-A", lev, "W1", 57.0)
    r = str(115 + off)
    _win(f"{r}-W4", "W-A", lev, "E", 15.0)
    r = str(105 + off)
    _win(f"{r}-W1", "W-B", lev, "N", 125 + 8 * IN)
    _win(f"{r}-W2", "W-B", lev, "N", 132 + 4 * IN)
    r = str(106 + off)
    _win(f"{r}-W1", "W-B", lev, "S", 25.0)

_win("ST1-W", "W-C", "L1", "S", 6.0, sill_abs=103 + 4 * IN)
_win("ST2-W", "W-C", "L1", "N", 144.0, sill_abs=103 + 4 * IN)
_win("200-W1", "SF-2", "L2", "E", 36.0, kind="storefront")
_win("200-W2", "SF-2", "L2", "W0", 36.0, kind="storefront")
_win("100A-SF1", "SF-3", "L1", "LN", -18.0, kind="storefront", sill_aff=0.0)
_win("100A-SF2", "SF-3", "L1", "LS", -18.0, kind="storefront", sill_aff=0.0)
_win("100-SF", "SF-1", "L1", "E", 36.0, kind="storefront", sill_aff=0.0)
_win("112-LV1", "LV-1", "L1", "S", 50.0, sill_aff=8.0, kind="louver")
_win("112-LV2", "LV-1", "L1", "S", 55.0, sill_aff=8.0, kind="louver")

# ---- doors ----
for lev, off in (("L1", 0), ("L2", 100)):
    for rm, x0 in _CLASS_N.items():
        n = str(int(rm) + off)
        _door(n, lev, "B1", x0 + 3 + 8 * IN, "F2", "+", "lo", "HW-1", "B", room=n)
    for rm, x0 in _CLASS_S.items():
        n = str(int(rm) + off)
        _door(n, lev, "C4", x0 + 3 + 8 * IN, "F2", "-", "lo", "HW-1", "B", room=n)
    n = str(105 + off)
    _door(n, lev, "B1", 122.5, "F1", "+", "lo", "HW-1", "B", room=n)
    _door(f"{106 + off}", lev, "C2", 15.0, "F1", "-", "lo", "HW-10", "A", room=str(106 + off))
    _door(f"{107 + off}", lev, "T85", 16.5, "F1", "+", "hi", "HW-3", "A", room=str(107 + off))
    _door(f"{109 + off}", lev, "C4", 33.5, "F1", "-", "lo", "HW-2", "A", room=str(109 + off))
    _door(f"{110 + off}", lev, "C4", 45.0, "F1", "-", "lo", "HW-9", "A", room=str(110 + off))
    _door(f"{110 + off}B", lev, "B20", 45.0, "F1", "-", "hi", "HW-9", "A", room=str(112 + off),
          remarks="TO MECH./ELEC. 112" if lev == "L1" else "TO STORAGE / IDF 212")
    _door(f"{111 + off}", lev, "C4", 56.5, "F1", "-", "hi", "HW-2", "A", room=str(111 + off))
    st = "A" if lev == "L1" else "C"
    _door(f"ST1-{st}", lev, "C1", 8.5, "F1", "-", "hi", "HW-4", "D", rating="60 MIN", room="ST-1",
          dmat="HM")
    _door(f"ST2-{st}", lev, "B2", 141.5, "F1", "+", "lo", "HW-4", "D", rating="60 MIN", room="ST-2",
          dmat="HM")

_door("ST1-B", "L1", "W2", 25.0, "F1", "-", "lo", "HW-5", "C", room="ST-1", dmat="HM",
      remarks="EXTERIOR EXIT")
_door("ST2-B", "L1", "E", 46.0, "F1", "+", "hi", "HW-5", "C", room="ST-2", dmat="HM",
      remarks="EXTERIOR EXIT")
_door("112", "L1", "S", 36.5, "F3", "-", hw="HW-6", dtype="C", room="112", dmat="HM",
      remarks="EXTERIOR, REMOVABLE MULLION")
_door("100A", "L1", "X0", 36.0, "F3", "-", hw="HW-8", dtype="B", room="100A",
      remarks="CROSS-CORRIDOR PAIR ON MAG. HOLD-OPENS (DIV. 26)")
# storefront entrance doors (part of SF-1)
OPENINGS.append(Opening("100B", "door", "E", "L1", "E", 36.0, 6.0, L1, L1 + 7.0, leaf=3.0,
                        pair=True, swing="+", frame="SF", hw="HW-7", room="100",
                        remarks="IN STOREFRONT SF-1; CARD READER PREP", dmat="AL", fmat="AL"))
# elevator entrances (by elevator contractor)
for lev in ("L1", "L2"):
    base = LEVELS[lev]
    OPENINGS.append(Opening(f"ELEV-{lev}", "elevator", "ELEV", lev, "C3", 25.5, 4 + 8 * IN, base,
                            base + 7 + 8 * IN, leaf=3.5, swing="-", room="108" if lev == "L1" else "208"))

OPENING_BY_ID = {o.id: o for o in OPENINGS}


def openings_on(level: str, kinds=None):
    out = []
    for o in OPENINGS:
        if kinds and o.kind not in kinds:
            continue
        if o.level == level:
            out.append(o)
        elif o.wall in EXT_SEGS and level in SEG_LEVELS[o.wall]:
            # tall exterior openings that pass through this level's cut plane
            cut = LEVELS[level] + CEILING_CUT
            if o.sill < cut < o.head:
                out.append(o)
    return out


def doors(level=None):
    return [o for o in OPENINGS if o.kind == "door" and (level is None or o.level == level)]


# ----------------------------------------------------------------------------------------
# Door / frame / hardware definitions
# ----------------------------------------------------------------------------------------
DOOR_TYPES = {
    "A": "FLUSH SOLID CORE WOOD (WD), PLAIN SLICED WHITE OAK, FACTORY FINISH",
    "B": "SOLID CORE WOOD (WD) WITH NARROW VISION LITE 5\" x 33\", TEMPERED GLASS",
    "C": "FLUSH INSULATED HOLLOW METAL (HM), 16 GA., GALVANNEALED, PAINTED",
    "D": "HOLLOW METAL (HM), 18 GA., WITH 4\" x 25\" FIRE-RATED CERAMIC GLAZING, 60 MIN LABEL",
    "E": "ALUMINUM STOREFRONT ENTRANCE DOOR, MEDIUM STILE, FULL GLASS (PART OF SF-1)",
}
FRAME_TYPES = {
    "F1": "HM FRAME, SINGLE, 2\" FACE, 4\" HEAD, 16 GA. (14 GA. EXTERIOR), WELDED, MASONRY ANCHORS",
    "F2": "HM FRAME WITH 1'-0\" SIDELITE (TEMPERED GLASS), 2\" FACES, 4\" HEAD, WELDED",
    "F3": "HM FRAME, PAIR, 2\" FACE, 4\" HEAD, WELDED (REMOVABLE MULLION WHERE NOTED)",
    "SF": "ALUMINUM STOREFRONT FRAMING (SECTION 08 43 13)",
}
HARDWARE_SETS = {
    "HW-1": ("CLASSROOM", ["3 EA HINGES, 4 1/2\" x 4 1/2\", BALL BEARING", "1 EA CLASSROOM SECURITY LOCKSET (ANSI F32), LEVER",
                           "1 EA SURFACE CLOSER, PARALLEL ARM", "1 EA KICK PLATE 10\" x 34\"", "1 EA WALL STOP", "3 EA SILENCERS"]),
    "HW-2": ("GROUP TOILET", ["3 EA HINGES", "1 EA PUSH PLATE", "1 EA PULL", "1 EA SURFACE CLOSER",
                              "1 EA KICK PLATE", "1 EA WALL STOP", "3 EA SILENCERS"]),
    "HW-3": ("SINGLE TOILET", ["3 EA HINGES", "1 EA PRIVACY LOCKSET W/ OCCUPANCY INDICATOR", "1 EA SURFACE CLOSER",
                               "1 EA KICK PLATE", "1 EA WALL STOP", "3 EA SILENCERS", "1 EA COAT HOOK"]),
    "HW-4": ("STAIR - 60 MIN", ["3 EA HINGES", "1 EA FIRE-RATED RIM EXIT DEVICE, LEVER TRIM (PASSAGE)",
                                "1 EA SURFACE CLOSER W/ STOP", "1 EA KICK PLATE", "1 SET SMOKE GASKETING",
                                "1 EA FIRE-RATED SIGN"]),
    "HW-5": ("EXTERIOR EXIT", ["1 EA CONTINUOUS GEARED HINGE", "1 EA RIM EXIT DEVICE, NIGHT LATCH TRIM",
                               "1 EA SURFACE CLOSER, HEAVY DUTY", "1 EA THRESHOLD, ALUM., ADA", "1 SET WEATHERSTRIP",
                               "1 EA DOOR SWEEP", "1 EA RAIN DRIP", "1 EA DOOR POSITION SWITCH (DIV. 28)"]),
    "HW-6": ("EXTERIOR PAIR - MECH.", ["2 EA CONTINUOUS GEARED HINGES", "1 EA KEYED REMOVABLE MULLION",
                                       "2 EA RIM EXIT DEVICES (1 NIGHT LATCH, 1 DUMMY)", "2 EA SURFACE CLOSERS",
                                       "1 EA THRESHOLD", "1 SET WEATHERSTRIP", "2 EA DOOR SWEEPS", "1 EA RAIN DRIP"]),
    "HW-7": ("STOREFRONT ENTRANCE", ["2 EA CONTINUOUS HINGES (BY STOREFRONT MFR.)", "2 EA CONCEALED VERTICAL ROD EXIT DEVICES",
                                     "2 EA OFFSET PULLS", "2 EA OVERHEAD CONCEALED CLOSERS", "ELECTRIFIED LATCH RETRACTION (BOTH DEVICES) + 2 POWER TRANSFERS, CARD READER PREP",
                                     "1 EA THRESHOLD", "1 SET WEATHERSTRIP", "1 EA ACCESSIBLE OPERATOR (ONE LEAF)"]),
    "HW-8": ("CROSS-CORRIDOR PAIR", ["6 EA HINGES", "2 EA PUSH/PULL SETS", "2 EA SURFACE CLOSERS",
                                     "2 EA KICK PLATES", "2 EA MAGNETIC HOLD-OPENS (BY DIV. 26 / 28)", "1 SET SPLIT ASTRAGAL (NON-LATCHING PAIR)"]),
    "HW-9": ("STOREROOM / CUSTODIAL", ["3 EA HINGES", "1 EA STOREROOM LOCKSET (ANSI F07)", "1 EA SURFACE CLOSER",
                                       "1 EA KICK PLATE", "1 EA WALL STOP", "3 EA SILENCERS"]),
    "HW-10": ("OFFICE / WORKROOM", ["3 EA HINGES", "1 EA OFFICE LOCKSET (ANSI F04)", "1 EA WALL STOP",
                                    "3 EA SILENCERS"]),
}

# ----------------------------------------------------------------------------------------
# Rooms & finishes
# ----------------------------------------------------------------------------------------
def R(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


@dataclass
class Room:
    num: str
    name: str
    level: str
    poly: list
    floor: str = ""
    base: str = ""
    walls: str = ""
    ceiling: str = ""
    clg_ht: Optional[float] = None
    remarks: str = ""
    tag_at: Optional[tuple] = None

    @property
    def shape(self):
        return Polygon(self.poly)


FIN_CLASS = dict(floor="VCT-1 / VCT-2", base="RB-1", walls="PNT-1", ceiling="ACT-1", clg_ht=10.0,
                 remarks="VCT-2 12\" BAND 2'-0\" FROM WALLS")
FIN_SMALL = dict(floor="CPT-1", base="RB-1", walls="PNT-1", ceiling="ACT-1", clg_ht=10.0)
FIN_CORR = dict(floor="LVT-1 / LVT-2", base="RB-1", walls="PNT-1", ceiling="ACT-1",
                clg_ht=9.5, remarks="LVT-2 2'-0\" BANDS AT GRID LINES")
FIN_TOIL = dict(floor="PT-1", base="PT-1B", walls="CT-1 / PNT-1", ceiling="GWB-1", clg_ht=9.0,
                remarks="CT-1 WAINSCOT TO 7'-0\" AFF, PNT-1 ABOVE")
FIN_CUST = dict(floor="SC-1", base="RB-1", walls="PNT-2", ceiling="ACT-2", clg_ht=9.0)
FIN_MECH = dict(floor="SC-1", base="RB-1", walls="PNT-1", ceiling="EXP", clg_ht=None)
FIN_STAIR = dict(floor="RF-1 / RST-1", base="RB-1", walls="PNT-1", ceiling="EXP", clg_ht=None,
                 remarks="RUBBER TREADS/RISERS, RUBBER SHEET AT LANDINGS")

ROOMS: list[Room] = []


def _room(num, name, level, poly, fin, tag_at=None, **over):
    d = dict(fin)
    d.update(over)
    ROOMS.append(Room(num, name, level, poly, tag_at=tag_at, **d))


WORK_POLY = [(12, 8.5), (20, 8.5), (20, 0), (30, 0), (30, 21), (21, 21), (21, 30), (12, 30)]
MECH_POLY = [(30, 0), (60, 0), (60, 12), (49, 12), (49, 20), (41, 20), (41, 12), (30, 12)]
for lev, off in (("L1", 0), ("L2", 100)):
    P = lambda n: str(n + off)
    for i, x0 in enumerate((0, 30, 60, 90)):
        _room(P(101 + i), "CLASSROOM", lev, R(x0, 42, x0 + 30, 72), FIN_CLASS)
    _room(P(105), "SMALL GROUP", lev, R(120, 42, 138, 72), FIN_SMALL)
    if lev == "L1":
        _room("106", "STAFF WORKROOM", lev, WORK_POLY,
              dict(floor="VCT-1", base="RB-1", walls="PNT-1", ceiling="ACT-1", clg_ht=9.0),
              tag_at=(21, 13))
    else:
        _room("206", "TEACHER PLANNING", lev, WORK_POLY,
              dict(floor="CPT-1", base="RB-1", walls="PNT-1", ceiling="ACT-1", clg_ht=9.0),
              tag_at=(21, 13))
    _room(P(107), "STAFF\nTOILET", lev, R(12, 0, 20, 8.5), FIN_TOIL, tag_at=(16, 4.6))
    _room(P(108), "ELEV.", lev, R(21, 21, 30, 30),
          dict(floor="BY ELEV. MFR.", base="-", walls="-", ceiling="-", clg_ht=None,
               remarks="3,500 LB MRL ELEVATOR"), tag_at=(25.5, 24.5))
    _room(P(109), "BOYS", lev, R(30, 12, 41, 30), FIN_TOIL, tag_at=(35.5, 21))
    _room(P(110), "CUST.", lev, R(41, 20, 49, 30), FIN_CUST, tag_at=(45.6, 24.6),
          remarks="ROOF HATCH & LADDER" if lev == "L2" else "")
    _room(P(111), "GIRLS", lev, R(49, 12, 60, 30), FIN_TOIL, tag_at=(54.5, 21))
    if lev == "L1":
        _room("112", "MECH. / ELEC.", lev, MECH_POLY, FIN_MECH, tag_at=(45, 6),
              remarks="ELEV. CONTROLLER IN THIS ROOM; FRT PLYWOOD BACKBOARDS")
    else:
        _room("212", "STORAGE / IDF", lev, MECH_POLY,
              dict(floor="VCT-1", base="RB-1", walls="PNT-1", ceiling="EXP", clg_ht=None,
                   remarks="FRT PLYWOOD BACKBOARD AT IDF WALL"), tag_at=(45, 6))
    for i, x0 in enumerate((60, 90, 120)):
        _room(P(113 + i), "CLASSROOM", lev, R(x0, 0, x0 + 30, 30), FIN_CLASS)
    _room(P(100), "CORRIDOR", lev, R(0, 30, 150, 42),
          dict(FIN_CORR, floor="LVT-1 / LVT-2 / WOM-1",
               remarks="LVT-2 2'-0\" BANDS AT GRID LINES; WOM-1 AT EAST ENTRANCE") if lev == "L1" else FIN_CORR,
          tag_at=(105.5, 36.0))
    _room("ST-1" if lev == "L1" else "ST-1 ", "STAIR 1", lev, R(0, 0, 12, 30), FIN_STAIR,
          tag_at=(6, 20.5))
    _room("ST-2" if lev == "L1" else "ST-2 ", "STAIR 2", lev, R(138, 42, 150, 72), FIN_STAIR,
          tag_at=(144, 51.5))
_room("100A", "LINK", "L1", R(EXIST_FACE_X, 30, 0, 42), dict(FIN_CORR, floor="LVT-1", remarks=""),
      tag_at=(-18, 36))
# normalise duplicated stair keys
for r in ROOMS:
    r.num = r.num.strip()


def rooms(level):
    return [r for r in ROOMS if r.level == level]


FINISHES = {
    # floors
    "VCT-1": "VINYL COMPOSITION TILE 12\"x12\"x1/8\", FIELD COLOR",
    "VCT-2": "VINYL COMPOSITION TILE 12\"x12\"x1/8\", ACCENT COLOR",
    "LVT-1": "LUXURY VINYL TILE 6\"x36\" PLANK, 20 MIL WEAR LAYER, FIELD",
    "LVT-2": "LUXURY VINYL TILE 24\"x24\", ACCENT BANDS (ONE TILE = 2'-0\" BAND)",
    "CPT-1": "CARPET TILE 24\"x24\", SOLUTION-DYED NYLON, QUARTER TURN",
    "WOM-1": "WALK-OFF CARPET TILE 24\"x24\" (RECESSED 1/4\" SLAB DEPRESSION)",
    "PT-1": "PORCELAIN FLOOR TILE 12\"x24\", THINSET, EPOXY GROUT",
    "RF-1": "RUBBER SHEET FLOORING 3.0 MM (STAIR LANDINGS)",
    "RST-1": "RUBBER STAIR TREAD w/ INTEGRAL RISER, VISUALLY CONTRASTING NOSING",
    "SC-1": "SEALED CONCRETE (PENETRATING SEALER)",
    # base
    "RB-1": "RUBBER COVE BASE 4\" HIGH, PREFORMED OUTSIDE CORNERS",
    "PT-1B": "PORCELAIN TILE COVE BASE 6\" (MATCH PT-1)",
    # walls
    "PNT-1": "BLOCK FILLER + 2 COATS LATEX EGGSHELL (CMU); PRIMER + 2 COATS (GWB)",
    "PNT-2": "BLOCK FILLER + 2 COATS WATERBORNE EPOXY",
    "CT-1": "GLAZED CERAMIC WALL TILE 4\"x12\", THINSET ON CMU (1/2\" CEMENT BACKER BOARD AT STUD WALLS), BULLNOSE CAP",
    # ceilings
    "ACT-1": "ACOUSTICAL PANEL CEILING 24\"x24\" REVEAL EDGE, 15/16\" GRID",
    "ACT-2": "VINYL-FACED WASHABLE ACOUSTICAL PANEL 24\"x24\", 15/16\" GRID",
    "GWB-1": "5/8\" MOISTURE-RESISTANT GWB ON SUSPENDED FRAMING, EPOXY PAINT",
    "EXP": "EXPOSED STRUCTURE, PAINTED",
}

# ----------------------------------------------------------------------------------------
# Casework (Section 06 41 00) per room
# ----------------------------------------------------------------------------------------
CASEWORK_TYPES = {
    "CW-1": "BASE CABINET 24\"D x 34 1/2\"H, PLAM, DRAWER OVER DOORS",
    "CW-2": "SINK BASE CABINET 36\"W x 24\"D, PLAM, OPEN BACK",
    "CW-3": "WALL CABINET 12\"D x 30\"H, PLAM, ADJ. SHELVES, BOTTOM @ 54\" AFF",
    "CW-4": "TALL STORAGE / WARDROBE CABINET 36\"W x 24\"D x 84\"H, LOCKABLE",
    "CW-5": "OPEN STUDENT CUBBY UNIT 15\"D x 60\"H, 12 CUBBIES PER 8'-0\", COAT HOOKS",
    "CT-1": "PLASTIC LAMINATE COUNTERTOP, 1 1/4\" PARTICLEBOARD CORE, 4\" BACKSPLASH",
}
# LF (or EA for CW-4)
CASEWORK_TYPICAL = {
    "CLASSROOM": {"CW-1": 9.0, "CW-2": 3.0, "CW-3": 9.0, "CW-4": 1, "CW-5": 16.0, "CT-1": 12.0},
    "SMALL GROUP": {"CW-1": 8.0, "CT-1": 8.0},
    "STAFF WORKROOM": {"CW-1": 12.0, "CW-2": 3.0, "CW-3": 12.0, "CW-4": 2, "CT-1": 15.0},
    "TEACHER PLANNING": {"CW-1": 9.0, "CW-2": 3.0, "CW-3": 12.0, "CW-4": 1, "CT-1": 12.0},
}


# ----------------------------------------------------------------------------------------
# Geometry helpers used by several sheets
# ----------------------------------------------------------------------------------------
def outline_poly(level):
    return Polygon(OUTLINE[level])


def _existing_mask():
    # removes ring parts along/behind the existing building face
    return box(EXIST_FACE_X - 50, -500, EXIST_FACE_X, 500).union(
        box(EXIST_FACE_X - 1, 30 + EW_IN + 0.01, EXIST_FACE_X + EW_IN + 0.02, 42 - EW_IN - 0.01))


def ext_layer(level, lo, hi):
    """Exterior wall layer between offsets lo..hi (ft, + toward exterior) as a shapely geometry."""
    P = outline_poly(level)
    outer = P.buffer(hi, join_style=2, mitre_limit=10) if hi > 0 else P.buffer(hi, join_style=2)
    inner = P.buffer(lo, join_style=2, mitre_limit=10) if lo > 0 else P.buffer(lo, join_style=2)
    g = outer.difference(inner)
    if level == "L1":
        g = g.difference(_existing_mask())
        # no exterior wall across the corridor/link junction at grid 1 (between C and B)
        g = g.difference(box(-EW_OUT - 0.5, 30 + EW_IN + 0.001, EW_OUT + 0.5, 42 - EW_IN - 0.001))
    return g


def interior_walls(level, types=None):
    return [w for w in WALLS if level in w.levels and (types is None or w.type in types)]


def opening_cut_box(o: Opening, depth=3.0):
    """rectangle (shapely) covering the opening through the host wall"""
    ax = opening_axis(o)
    k = opening_line_coord(o)
    if ax == "x":
        return box(o.lo, k - depth / 2, o.hi, k + depth / 2)
    return box(k - depth / 2, o.lo, k + depth / 2, o.hi)


def clear_room_poly(room: Room):
    """Room polygon minus walls (finish floor area)."""
    lev = room.level
    walls = [w.poly() for w in interior_walls(lev)]
    walls.append(ext_layer(lev, -EW_IN, EW_OUT))
    if lev == "L1":
        walls.append(box(EXIST_FACE_X - 2, 25, EXIST_FACE_X, 47))
    g = room.shape.difference(unary_union(walls))
    if g.geom_type == "MultiPolygon":
        g = max(g.geoms, key=lambda q: q.area)
    return g


def gross_area(level):
    g = outline_poly(level).buffer(EW_OUT, join_style=2)
    if level == "L1":
        g = g.difference(box(EXIST_FACE_X - 50, -500, EXIST_FACE_X, 500))
    return g.area


if __name__ == "__main__":
    for lev in ("L1", "L2"):
        print(lev, "gross", round(gross_area(lev)))
        for r in rooms(lev):
            print(f"  {r.num:6s} {r.name.replace(chr(10), ' '):18s} {clear_room_poly(r).area:8.1f}")
    print("doors", len(doors()), "openings", len(OPENINGS))
