"""G-sheets: cover, general information / code analysis, life safety plans."""
from __future__ import annotations

import math

from shapely.geometry import box
from shapely.ops import unary_union

from . import model as M
from . import plans as PL
from .cad import (FONT, FONT_B, FONT_I, TXT, Paper, door_tag, keynote_tag, notes_block, room_tag,
                  table, wall_tag, window_tag)
from .sheet import PROJECT

IN = M.IN

# ----------------------------------------------------------------------------------------
# code / occupancy numbers (computed from the model)
# ----------------------------------------------------------------------------------------
EXISTING_AREA = 38_600
LOAD_FACTORS = [  # (predicate on room, factor, basis)
    (lambda r: r.name in ("CLASSROOM", "SMALL GROUP"), 20, "NET"),
    (lambda r: r.name in ("STAFF WORKROOM", "TEACHER PLANNING"), 150, "GROSS"),
    (lambda r: r.name.startswith("MECH") or r.name.startswith("STOR") or r.name.startswith("CUST"), 300, "GROSS"),
]


def occupant_load(r):
    a = M.clear_room_poly(r).area
    for pred, f, _ in LOAD_FACTORS:
        if pred(r):
            return math.ceil(a / f), f
    return 0, None


def level_occ(level):
    return sum(occupant_load(r)[0] for r in M.rooms(level))


# ----------------------------------------------------------------------------------------
# G-001 COVER
# ----------------------------------------------------------------------------------------

def _iso(x, y, z):
    c, s = math.cos(math.radians(30)), math.sin(math.radians(30))
    return ((x + y) * c, (y - x) * s + z)


def draw_axon(sh, ox, oy, sc):
    """isometric massing from the south-east (painter's order)."""
    p = Paper(sh.c)

    def P(x, y, z):
        u, w = _iso(x, y, z - 99.0)
        return (ox + u * sc, oy + w * sc)

    def face(pts, **kw):
        p.polygon([P(*q) for q in pts], **kw)

    g0 = M.LEVELS["GRADE"]
    out = M.EW_OUT
    # ground plane hint
    face([(-90, -45, g0), (215, -45, g0), (215, 110, g0), (-90, 110, g0)], lw=None, fill="g05",
         stroke=False)
    # existing building east wing (x -90..-36, y -10..80), low box
    ex = (-90.0, -36.0, -10.0, 80.0, M.LEVELS["EXIST_ROOF"] + 1.0)
    x0, x1, y0, y1, zt = ex
    face([(x0, y0, zt), (x1, y0, zt), (x1, y1, zt), (x0, y1, zt)], lw="fine", color="g50", fill="g10")
    face([(x0, y0, g0), (x1, y0, g0), (x1, y0, zt), (x0, y0, zt)], lw="fine", color="g50", fill="g15")
    face([(x1, y0, g0), (x1, y1, g0), (x1, y1, zt), (x1, y0, zt)], lw="fine", color="g50", fill="g20")
    # link
    lz = M.LEVELS["LINK_PARAPET"]
    lx0, lx1, ly0, ly1 = -36.0, 0.0, 30 - out, 42 + out
    face([(lx0, ly0, lz), (lx1, ly0, lz), (lx1, ly1, lz), (lx0, ly1, lz)], lw="fine", fill="g20")
    face([(lx0, ly0, g0), (lx1, ly0, g0), (lx1, ly0, lz), (lx0, ly0, lz)], lw="fine", fill="white")
    # link storefront (south face)
    face([(-34, ly0, 100.0), (-2, ly0, 100.0), (-2, ly0, 109.33), (-34, ly0, 109.33)], lw="fine", fill="g40")
    # main block
    X0, X1, Y0, Y1 = -out, 150 + out, -out, 72 + out
    zt = M.LEVELS["PARAPET"]
    face([(X0, Y0, zt), (X1, Y0, zt), (X1, Y1, zt), (X0, Y1, zt)], lw="thin", fill="g15")
    face([(X0, Y0, g0), (X1, Y0, g0), (X1, Y0, zt), (X0, Y0, zt)], lw="thin", fill="white")
    face([(X1, Y0, g0), (X1, Y1, g0), (X1, Y1, zt), (X1, Y0, zt)], lw="thin", fill="g10")
    # bands on visible faces
    for z in (M.LEVELS["L1"] + 8 * IN, 113.33, 114.0, zt - 0.6):
        p.line(P(X0, Y0, z), P(X1, Y0, z), lw="hair")
        p.line(P(X1, Y0, z), P(X1, Y1, z), lw="hair")
    # roof parapet inner line + RTUs
    face([(0.3, 0.3, zt), (149.7, 0.3, zt), (149.7, 71.7, zt), (0.3, 71.7, zt)], lw="hair", fill="g10")
    for _, (cx, cy) in (("1", (45.0, 57.0)), ("2", (105.0, 57.0)), ("3", (105.0, 15.0))):
        h = 5.0
        z0 = M.LEVELS["ROOF"] + 1.0
        a, b, c_, d = (cx - 6.5, cy - 3.0), (cx + 6.5, cy - 3.0), (cx + 6.5, cy + 3.0), (cx - 6.5, cy + 3.0)
        face([(*a, z0 + h), (*b, z0 + h), (*c_, z0 + h), (*d, z0 + h)], lw="hair", fill="g20")
        face([(*a, z0), (*b, z0), (*b, z0 + h), (*a, z0 + h)], lw="hair", fill="g30")
        face([(*b, z0), (*c_, z0), (*c_, z0 + h), (*b, z0 + h)], lw="hair", fill="g40")
    # openings on south and east faces
    for o in M.OPENINGS:
        if o.wall not in ("S", "E") or o.kind == "elevator":
            continue
        if o.kind == "door" and o.frame == "SF":
            continue
        fill = "g50" if o.kind in ("window", "storefront") else ("g30" if o.kind == "louver" else "g60")
        if o.wall == "S":
            face([(o.lo, Y0, o.sill), (o.hi, Y0, o.sill), (o.hi, Y0, o.head), (o.lo, Y0, o.head)],
                 lw="hair", fill=fill)
        else:
            face([(X1, o.lo, o.sill), (X1, o.hi, o.sill), (X1, o.hi, o.head), (X1, o.lo, o.head)],
                 lw="hair", fill=fill)
    p.text(P(150 + out, 36, zt + 6), "", size=TXT["tiny"])


def _location_map(sh, x, y, w, h):
    sh.rect(x, y, w, h, lw="thin")
    # schematic streets
    def road(x0, y0, x1, y1, name=None, rot=0, at=None):
        sh.line((x0, y0), (x1, y1), lw="xheavy", color="g40")
        if name:
            ax, ay = at
            sh.text((ax, ay), name, size=TXT["tiny"], font=FONT_B, anchor="c", valign="mid", rot=rot)
    road(x + 0.2, y + 0.9, x + w - 0.2, y + 0.9, "PRAIRIE AVENUE", 0, (x + w * 0.3, y + 0.75))
    road(x + w * 0.62, y + 0.2, x + w * 0.62, y + h - 0.2, "MAPLE STREET", 90, (x + w * 0.62 + 0.14, y + h * 0.7))
    road(x + 0.2, y + h - 0.7, x + w - 0.2, y + h - 0.7, "CEDAR LANE", 0, (x + w * 0.3, y + h - 0.55))
    road(x + w * 0.15, y + 0.2, x + w * 0.15, y + h - 0.2, "BIRCH ROAD", 90, (x + w * 0.15 - 0.14, y + h * 0.5))
    road(x + w * 0.88, y + 0.2, x + w * 0.88, y + h - 0.2)
    sh.rect(x + w * 0.24, y + 1.05, w * 0.36, h - 1.9, lw="thin", fill="g10")
    sh.rect(x + w * 0.44, y + h * 0.48, w * 0.12, h * 0.16, lw="thin", fill="g60")
    sh.text((x + w * 0.42, y + h * 0.40), "PROJECT SITE", size=TXT["small"], font=FONT_B, anchor="c")
    sh.north_arrow(x + w - 0.35, y + h - 0.45, 0.35)
    sh.text((x + 0.1, y + h + 0.08), "LOCATION MAP (NOT TO SCALE)", size=TXT["label"], font=FONT_B,
            valign="bot")


def cover(sh):
    x0, y1 = sh.x0, sh.y1
    # title
    sh.text((x0 + 0.5, y1 - 0.9), PROJECT["name1"], size=34, font=FONT_B, valign="base")
    sh.text((x0 + 0.5, y1 - 1.55), PROJECT["name2"], size=24, font=FONT_B, valign="base")
    sh.text((x0 + 0.5, y1 - 2.05), PROJECT["address"] + "   |   " + PROJECT["owner"], size=TXT["sub"],
            valign="base")
    sh.rect(x0 + 0.5, y1 - 2.75, 14.5, 0.45, lw=None, fill="g80")
    sh.text((x0 + 0.65, y1 - 2.52), f"{PROJECT['issue']}  -  {PROJECT['date']}  -  PROJECT NO. {PROJECT['number']}",
            size=13, font=FONT_B, valign="mid", color="white")
    sh.mtext((x0 + 0.5, y1 - 3.05), [
        "ESTIMATING PRACTICE SET: A FICTIONAL PROJECT PREPARED FOR CONSTRUCTION ESTIMATING EDUCATION (ASC REGION III STYLE",
        "COMMERCIAL PROBLEM). THIS SET INCLUDES GENERAL, CIVIL, STRUCTURAL AND ARCHITECTURAL DRAWINGS. MECHANICAL, PLUMBING,",
        "ELECTRICAL AND FIRE PROTECTION DRAWINGS ARE NOT INCLUDED. NOT FOR CONSTRUCTION."],
        size=TXT["note"], valign="top")
    # axonometric
    from .sheets_arch_plans import clip_rect
    clip_rect(sh.c, x0 + 0.4, y1 - 15.3, 14.8, 11.9)
    draw_axon(sh, x0 + 4.9, y1 - 9.6, 0.05)
    sh.c.restoreState()
    sh.text((x0 + 0.5, y1 - 15.6), "AERIAL VIEW FROM SOUTHEAST (MASSING, NOT TO SCALE)", size=TXT["label"],
            font=FONT_B, valign="base")
    # project description
    desc = [
        "##PROJECT DESCRIPTION",
        "NEW TWO-STORY, 22,941 GSF CLASSROOM ADDITION TO THE EXISTING ONE-STORY ELEMENTARY SCHOOL: 14 CLASSROOMS, 2 SMALL GROUP ROOMS, STAFF WORKROOM, TEACHER PLANNING, TOILETS, ELEVATOR AND TWO EXIT STAIRS, CONNECTED TO THE EXISTING CORRIDOR BY A ONE-STORY GLAZED LINK.",
        "STRUCTURE: STEEL FRAME WITH COMPOSITE FLOOR DECK AND STEEL JOISTS AT THE ROOF; SPREAD AND CONTINUOUS FOOTINGS; REINFORCED CMU SHEAR WALLS.",
        "ENVELOPE: MODULAR FACE BRICK CAVITY WALL ON 8\" CMU BACKUP, CAST STONE TRIM, THERMALLY BROKEN ALUMINUM WINDOWS AND STOREFRONT, FULLY ADHERED EPDM ROOF ON TAPERED POLYISO.",
        "INTERIORS: PAINTED CMU PARTITIONS, VCT / LVT / CARPET TILE / PORCELAIN TILE FLOORING, ACOUSTICAL CEILINGS, PLASTIC LAMINATE CASEWORK, HOLLOW METAL FRAMES WITH WOOD DOORS.",
        "THE EXISTING SCHOOL REMAINS OCCUPIED. TIE-IN WORK AT THE EXISTING BUILDING IS LIMITED TO SUMMER RECESS (SEE G-002 AND AD101).",
    ]
    notes_block(sh, x0 + 0.5, y1 - 16.0, "PROJECT DESCRIPTION", desc[1:], 14.3, numbered=False)
    # project directory
    dx = x0 + 0.5
    dy = sh.y0 + 2.9
    rows = [["OWNER", "CEDAR PRAIRIE COMMUNITY SCHOOL DISTRICT (FICTIONAL)"],
            ["ARCHITECT", "PRAIRIE LINE STUDIO (PRACTICE)"],
            ["STRUCTURAL ENGINEER", "KEYSTONE STRUCTURAL (PRACTICE)"],
            ["CIVIL ENGINEER", "MEADOWLINE CIVIL (PRACTICE)"],
            ["MEP / FIRE PROTECTION", "NOT INCLUDED IN THIS PRACTICE SET"]]
    table(sh, dx, dy, [("PROJECT DIRECTORY", 2.4), ("", 6.0)], rows, row_h=0.22, size=TXT["small"],
          align=["l", "l"])
    _location_map(sh, x0 + 9.4, sh.y0 + 0.4, 5.6, 3.2)
    # sheet index
    from . import build as B
    idx = B.sheet_index()
    groups = {"G": "GENERAL", "C": "CIVIL", "S": "STRUCTURAL", "A": "ARCHITECTURAL"}
    rows = []
    cur = None
    for num, title in idx:
        g = "A" if num.startswith("AD") else num[0]
        if g != cur:
            rows.append(groups.get(g, g))
            cur = g
        rows.append([num, title.replace("\n", " ")])
    tx = x0 + 16.2
    half = (len(rows) + 1) // 2
    sh.text((tx, y1 - 0.35), "SHEET INDEX", size=TXT["sub"], font=FONT_B, valign="top", underline=True)
    table(sh, tx, y1 - 0.75, [("SHEET", 1.0), ("TITLE", 6.3)], rows[:half], row_h=0.25,
          size=TXT["note"])
    table(sh, tx + 7.6, y1 - 0.75, [("SHEET", 1.0), ("TITLE", 6.3)], rows[half:], row_h=0.25,
          size=TXT["note"])
    # code summary + project data (small)
    data = [["OCCUPANCY", "E - EDUCATIONAL"], ["CONSTRUCTION TYPE", "IIB, FULLY SPRINKLERED (NFPA 13)"],
            ["ADDITION GROSS AREA", f"{M.gross_area('L1') + M.gross_area('L2'):,.0f} SF (2 STORIES)"],
            ["EXISTING BUILDING", f"{EXISTING_AREA:,} SF (1 STORY, NO WORK EXCEPT TIE-IN)"],
            ["BUILDING HEIGHT", "32'-0\" TO TOP OF PARAPET"],
            ["SCHEDULE", "SUBSTANTIAL COMPLETION AUGUST 6, 2027"]]
    table(sh, tx, sh.y0 + 4.2, [("PROJECT DATA", 2.6), ("", 5.0)], data, row_h=0.22, size=TXT["small"],
          align=["l", "l"])
    sh.mtext((tx + 7.9, sh.y0 + 4.2), [
        "**ABOUT THIS PRACTICE SET**",
        "THE ACTUAL ASC COMPETITION DRAWINGS ARE RELEASED AT THE",
        "OPENING MEETING. THIS SET MIRRORS THE PROBLEM FORMAT",
        "(SCHOOL ADDITION, OCCUPIED CAMPUS, MEP EXCLUDED) SO TEAMS",
        "CAN PRACTICE TAKEOFFS FOR MASONRY, CARPENTRY, FLOORING,",
        "DOORS/FRAMES/HARDWARE, WINDOWS/STOREFRONT AND GENERAL",
        "CONDITIONS, AND PREPARE SCHEDULE, LOGISTICS AND SAFETY",
        "PLANS FOR AN ADDITION BUILT NEXT TO AN OCCUPIED SCHOOL."], size=TXT["small"], valign="top")


# ----------------------------------------------------------------------------------------
# G-002 GENERAL INFORMATION & CODE ANALYSIS
# ----------------------------------------------------------------------------------------
ABBREV = [
    ("AFF", "ABOVE FINISH FLOOR"), ("ACT", "ACOUSTICAL CEILING TILE"), ("AL / ALUM", "ALUMINUM"),
    ("B.O.", "BOTTOM OF"), ("BLKG", "BLOCKING"), ("CJ", "CONTROL JOINT"), ("CLG", "CEILING"),
    ("CMU", "CONCRETE MASONRY UNIT"), ("CONC", "CONCRETE"), ("CPT", "CARPET TILE"), ("CS", "CAST STONE"),
    ("CT", "CERAMIC TILE"), ("CW", "CASEWORK"), ("DN", "DOWN"), ("EJ", "EXPANSION JOINT"),
    ("EL", "ELEVATION"), ("EPDM", "ETHYLENE PROPYLENE DIENE MONOMER"), ("EWC", "ELECTRIC WATER COOLER"),
    ("EXIST / (E)", "EXISTING"), ("EXP", "EXPOSED"), ("FB", "FACE BRICK"), ("FEC", "FIRE EXTINGUISHER CABINET"),
    ("FFE", "FINISH FLOOR ELEVATION"), ("FRT", "FIRE-RETARDANT-TREATED"), ("GWB", "GYPSUM WALLBOARD"),
    ("HM", "HOLLOW METAL"), ("HW", "HARDWARE"), ("IDF", "INTERMEDIATE DISTRIBUTION FRAME"),
    ("LLV", "LONG LEG VERTICAL"), ("LVT", "LUXURY VINYL TILE"), ("MB", "MARKERBOARD"), ("MC", "METAL COPING"),
    ("MO", "MASONRY OPENING"), ("MRL", "MACHINE-ROOM-LESS"), ("NIC", "NOT IN CONTRACT"),
    ("O/O", "OUT TO OUT"), ("PLAM", "PLASTIC LAMINATE"), ("PNT", "PAINT"), ("PT", "PORCELAIN TILE"),
    ("RB", "RUBBER BASE"), ("RD / OD", "ROOF DRAIN / OVERFLOW DRAIN"), ("RF", "RUBBER FLOORING"),
    ("RST", "RUBBER STAIR TREAD"), ("RTU", "ROOFTOP UNIT"), ("SC", "SEALED CONCRETE"), ("SF", "STOREFRONT / SQUARE FEET"),
    ("SOG", "SLAB ON GRADE"), ("T.O.", "TOP OF"), ("TB", "TACKBOARD"), ("TYP", "TYPICAL"),
    ("UNO", "UNLESS NOTED OTHERWISE"), ("VCT", "VINYL COMPOSITION TILE"), ("WD", "WOOD"),
    ("WOM", "WALK-OFF MAT (CARPET TILE)"), ("WWF", "WELDED WIRE FABRIC"),
]

GENERAL_NOTES = [
    "THE CONTRACT DOCUMENTS CONSIST OF THESE DRAWINGS, THE PROJECT MANUAL (SPECIFICATIONS), THE BIDDING REQUIREMENTS AND ALL ADDENDA. WHERE CONFLICTS OCCUR, THE MORE STRINGENT / HIGHER-QUANTITY REQUIREMENT GOVERNS FOR BIDDING.",
    "DO NOT SCALE DRAWINGS. WRITTEN DIMENSIONS GOVERN. DIMENSIONS ARE TO GRID LINES, FACE OF CMU OR MASONRY OPENINGS (MO) UNLESS NOTED.",
    "THE CONTRACTOR SHALL VISIT THE SITE AND VERIFY EXISTING CONDITIONS BEFORE SUBMITTING A PROPOSAL.",
    "WORK SHALL COMPLY WITH ALL CODES LISTED IN THE CODE ANALYSIS AND WITH THE REQUIREMENTS OF THE AUTHORITY HAVING JURISDICTION (REGIONAL OFFICE OF EDUCATION / ISBE).",
    "PROVIDE FIRESTOPPING AT ALL PENETRATIONS OF RATED ASSEMBLIES (P2 PARTITIONS, SHAFTS, FLOORS) USING UL-LISTED SYSTEMS.",
    "PROVIDE BLOCKING FOR ALL WALL-MOUNTED ITEMS. SEE WOOD BLOCKING SCHEDULE ON A-502.",
    "ALL INTERIOR FINISHES SHALL MEET IBC CHAPTER 8 FLAME-SPREAD REQUIREMENTS FOR GROUP E, SPRINKLERED.",
    "MEP, FIRE PROTECTION, FIRE ALARM, TECHNOLOGY AND SECURITY WORK IS NOT INCLUDED IN THIS PRACTICE SET; ASSUME IT IS BID SEPARATELY (OWNER'S SEPARATE PRIME CONTRACTS) BUT INCLUDE GENERAL CONTRACTOR COORDINATION AND CUTTING/PATCHING.",
]

OWNER_REQ = [
    "##SCHEDULE",
    "NOTICE TO PROCEED: NOVEMBER 2, 2026. SUBSTANTIAL COMPLETION: AUGUST 6, 2027 (FURNITURE MOVE-IN AUGUST 9). FINAL COMPLETION: AUGUST 20, 2027. FIRST DAY OF SCHOOL: AUGUST 23, 2027.",
    "TIE-IN WORK THAT AFFECTS THE EXISTING BUILDING (OPENING THE EXISTING EAST WALL, CORRIDOR WORK, SYSTEM SHUTDOWNS) SHALL BE PERFORMED ONLY DURING SUMMER RECESS, JUNE 7 TO AUGUST 13, 2027.",
    "WINTER CONSTRUCTION IS EXPECTED: INCLUDE COLD-WEATHER MASONRY AND CONCRETE PROTECTION, TEMPORARY ENCLOSURES AND TEMPORARY HEAT.",
    "##OCCUPIED CAMPUS",
    "THE EXISTING SCHOOL (ABOUT 350 STUDENTS + STAFF) IS OCCUPIED 7:15 AM TO 4:00 PM, MONDAY TO FRIDAY. NO DELIVERIES, CRANE PICKS OR EQUIPMENT MOVES ACROSS PEDESTRIAN ROUTES DURING ARRIVAL (7:30-8:15 AM) AND DISMISSAL (2:45-3:30 PM).",
    "CONSTRUCTION ACCESS FROM MAPLE STREET ONLY. THE PRAIRIE AVENUE PARKING LOT AND BUS LOOP REMAIN IN SCHOOL USE. CONTRACTOR PARKING IN THE STAGING AREA ONLY (C-100).",
    "SEPARATE THE WORK AREA FROM SCHOOL USE WITH 8'-0\" CHAIN-LINK FENCE WITH PRIVACY SCREEN; ALL GATES LOCKED WHEN NOT ATTENDED. ALL WORKERS ON SITE DURING SCHOOL HOURS MUST PASS THE DISTRICT BACKGROUND CHECK AND WEAR BADGES.",
    "MAINTAIN FIRE DEPARTMENT ACCESS TO THE EXISTING BUILDING AND EXISTING HYDRANTS AT ALL TIMES.",
    "NOISY WORK (SAWCUTTING, HAMMERING, CORE DRILLING) ADJACENT TO OCCUPIED CLASSROOMS DURING STATE TESTING WEEKS (TWO WEEKS IN APRIL, DATES TBD) SHALL BE SCHEDULED AFTER 3:30 PM.",
    "##CONTRACT",
    "SINGLE GENERAL CONTRACT WITH A GUARANTEED MAXIMUM PRICE (GMP). PROPOSAL TO INCLUDE GENERAL CONDITIONS, INSURANCE, BONDS, CONTINGENCY AND FEE AS LISTED ON THE PROPOSAL FORM.",
]


def general_info(sh):
    x0, y1 = sh.x0, sh.y1
    col_w = 7.55
    cx = [x0 + 0.25 + i * (col_w + 0.3) for i in range(4)]
    # column 1: code analysis
    l1, l2 = M.gross_area("L1"), M.gross_area("L2")
    story1 = l1 + EXISTING_AREA
    at, ns, iff = 43_500, 14_500, 0.75
    aa = at + ns * iff
    rows = [
        "APPLICABLE CODES",
        ["BUILDING", "2021 IBC (AS ADOPTED)"], ["ENERGY", "2021 IECC + ILLINOIS AMENDMENTS (CZ 5A)"],
        ["ACCESSIBILITY", "ILLINOIS ACCESSIBILITY CODE / 2010 ADA"],
        ["LIFE SAFETY", "23 IAC 180 (ISBE HEALTH/LIFE SAFETY)"], ["PLUMBING", "ILLINOIS PLUMBING CODE (77 IAC 890)"],
        ["FIRE", "2021 IFC, NFPA 13 / 72 / 101 AS REFERENCED"],
        "BUILDING CLASSIFICATION",
        ["OCCUPANCY", "GROUP E (EDUCATIONAL)"], ["CONSTRUCTION TYPE", "TYPE IIB (NON-COMBUSTIBLE, UNPROTECTED)"],
        ["SPRINKLERS", "YES - NFPA 13 THROUGHOUT (EXISTING + NEW)"],
        "HEIGHT AND AREA (IBC CH. 5)",
        ["ALLOWABLE HEIGHT", "75 FT / 3 STORIES (T. 504.3, 504.4)"],
        ["ACTUAL HEIGHT", "32'-0\" / 2 STORIES"],
        ["ALLOWABLE AREA PER STORY", f"At = 43,500 + (14,500 x If 0.75) = {aa:,.0f} SF"],
        ["STORY 1 (EXIST. + ADDITION)", f"{EXISTING_AREA:,} + {l1:,.0f} = {story1:,.0f} SF  OK"],
        ["STORY 2 (ADDITION)", f"{l2:,.0f} SF  OK"],
        ["TOTAL BUILDING AREA", f"{story1 + l2:,.0f} SF <= 2 x {aa:,.0f}  OK"],
        "FIRE-RESISTANCE RATINGS (T. 601 / 602)",
        ["STRUCTURAL FRAME, FLOORS, ROOF", "0 HR"], ["EXTERIOR WALLS (FSD > 30 FT)", "0 HR"],
        ["EXIT STAIRS / ELEVATOR SHAFT", "1 HR (713.4) - PARTITION P2"],
        ["CORRIDORS (E, SPRINKLERED)", "0 HR (T. 1020.2)"],
        ["STAIR DOORS", "60 MIN, SELF-CLOSING, LATCHING"],
    ]
    table(sh, cx[0], y1 - 0.2, [("CODE ANALYSIS", 2.95), ("", 4.6)], rows, row_h=0.3, size=TXT["note"],
          align=["l", "l"], header_size=TXT["label"])
    # egress & occupancy tables (column 2)
    occ1, occ2 = level_occ("L1"), level_occ("L2")
    rows = [
        "OCCUPANT LOAD (T. 1004.5)",
        ["CLASSROOMS / SMALL GROUP", "20 SF NET"], ["WORKROOM / PLANNING", "150 SF GROSS"],
        ["STORAGE / MECH. / CUSTODIAL", "300 SF GROSS"],
        ["LEVEL 1 (ADDITION)", f"{occ1} OCCUPANTS"], ["LEVEL 2", f"{occ2} OCCUPANTS"],
        "MEANS OF EGRESS (CH. 10)",
        ["EXITS REQUIRED / PROVIDED", "L1: 2 / 4    L2: 2 / 2"],
        ["STAIR WIDTH REQ'D (0.3\"/OCC.)", f"{occ2 * 0.3:.0f}\" TOTAL; 44\" MIN. EACH"],
        ["STAIR WIDTH PROVIDED", "2 STAIRS x 62\" = 124\""],
        ["DOOR WIDTH REQ'D (0.2\"/OCC.)", f"{occ1 * 0.2:.0f}\" (L1)"],
        ["MAX. TRAVEL DISTANCE", "250 FT (SPRINKLERED) - SEE G-003"],
        ["COMMON PATH / DEAD END", "75 FT / 50 FT"],
        "PLUMBING FIXTURES (DESIGN ENROLLMENT)",
        ["BASIS", "14 CLASSROOMS x 25 + 30 STAFF = 380"],
        ["WATER CLOSETS / URINALS", "REQ'D 8 (1:50) - PROVIDED 16"],
        ["LAVATORIES", "REQ'D 8 (1:50) - PROVIDED 10"],
        ["DRINKING FOUNTAINS", "REQ'D 4 (1:100) - PROVIDED 4 (2 BI-LEVEL)"],
        ["SERVICE SINKS", "REQ'D 1 - PROVIDED 2"],
        "ENERGY (2021 IECC, CZ 5A)",
        ["ROOF", "R-30 CI (TAPERED POLYISO AVG.)"],
        ["MASS WALL", "R-11.4 CI REQ'D - R-13 PROVIDED (2\" POLYISO)"],
        ["FENESTRATION", "U-0.38 FIXED / 0.45 OPERABLE; SHGC 0.38"],
        ["SLAB ON GRADE", "R-10 FOR 24\" (2\" XPS PERIMETER)"],
    ]
    table(sh, cx[1], y1 - 0.2, [("OCCUPANCY / EGRESS / PLUMBING / ENERGY", 3.15), ("", 4.4)], rows,
          row_h=0.3, size=TXT["note"], align=["l", "l"], header_size=TXT["label"])
    # owner requirements (column 3)
    h = notes_block(sh, cx[2], y1 - 0.25, "OWNER REQUIREMENTS / SUMMARY OF WORK", OWNER_REQ, col_w,
                    size=TXT["label"])
    notes_block(sh, cx[2], y1 - 0.25 - h - 0.4, "GENERAL NOTES", GENERAL_NOTES, col_w, size=TXT["label"])
    # column 4: abbreviations
    half = (len(ABBREV) + 1) // 2
    sh.text((cx[3], y1 - 0.25), "ABBREVIATIONS", size=TXT["label"], font=FONT_B, valign="top", underline=True)
    for k, (a, d) in enumerate(ABBREV):
        col = 0 if k < half else 1
        row = k if k < half else k - half
        xx = cx[3] + col * 3.85
        yy = y1 - 0.6 - row * 0.255
        sh.text((xx, yy), a, size=TXT["note"], font=FONT_B, valign="top")
        sh.text((xx + 0.9, yy), d, size=TXT["small"], valign="top")
    # proposal / allowances (practice)
    ay = y1 - 8.75
    rows = [
        "ALLOWANCES (CARRY IN GMP; WORK BY SUBCONTRACT UNDER GC)",
        ["AL-1", "PLUMBING (DIV. 22) - FIXTURES, PIPING, ROOF DRAINAGE", "$575,000"],
        ["AL-2", "HVAC (DIV. 23) - RTU-1/2/3, DUCTWORK, CONTROLS", "$1,480,000"],
        ["AL-3", "ELECTRICAL (DIV. 26) - POWER, LIGHTING, SERVICE", "$1,035,000"],
        ["AL-4", "FIRE SUPPRESSION (DIV. 21) - NFPA 13 WET SYSTEM", "$140,000"],
        ["AL-5", "TECHNOLOGY, FIRE ALARM, ACCESS CONTROL (DIV. 27/28)", "$410,000"],
        ["AL-6", "ELEVATOR (DIV. 14) - 3,500 LB MRL, 2 STOPS, FURNISH & INSTALL", "$165,000"],
        ["AL-7", "TESTING & SPECIAL INSPECTIONS (IBC CH. 17)", "$45,000"],
        ["AL-8", "SIGNAGE AND ROOM IDENTIFICATION", "$18,000"],
        "ALTERNATES (PRICE SEPARATELY)",
        ["ALT-1", "ADD: LVT-1 IN ALL CLASSROOMS IN LIEU OF VCT-1/VCT-2", "ADD $ ____"],
        ["ALT-2", "ADD: PREFINISHED ALUMINUM SUNSHADES AT L2 SOUTH W-A WINDOWS (9)", "ADD $ ____"],
        ["ALT-3", "DEDUCT: OMIT WOM-1 WALK-OFF; EXTEND LVT-1", "DEDUCT $ ____"],
        "UNIT PRICES",
        ["UP-1", "UNSUITABLE SOIL REMOVAL & REPLACEMENT WITH CA-6 (CY) - CARRY 300 CY", "$ ____ / CY"],
        ["UP-2", "ADDITIONAL 8\" CMU PARTITION, PAINTED BOTH SIDES (SF)", "$ ____ / SF"],
        "PROPOSAL REQUIREMENTS",
        ["BONDS", "100% PERFORMANCE AND PAYMENT BONDS", "INCLUDE"],
        ["INSURANCE", "CGL $2M/$4M, AUTO $1M, UMBRELLA $10M, BUILDER'S RISK", "INCLUDE"],
        ["CONTINGENCY", "CONTRACTOR'S CONTINGENCY, MIN. 3% OF COST OF WORK", "INCLUDE"],
        ["FEE", "LUMP-SUM FEE STATED AS % OF COST OF WORK", "STATE %"],
    ]
    table(sh, cx[0], ay, [("ITEM", 1.05), ("DESCRIPTION (PRACTICE VALUES - NOT A REAL BID)", 4.9), ("AMOUNT", 1.6)],
          rows, row_h=0.255, size=TXT["note"], align=["l", "l", "r"], header_size=TXT["label"],
          title="BID FORM: ALLOWANCES, ALTERNATES & UNIT PRICES")
    sh.mtext((cx[1], ay - 0.05), [
        "**HOW TO USE THIS SET FOR PRACTICE**",
        "1. TAKE OFF THE SCORED SCOPES (MASONRY, CARPENTRY, FLOORING / TILE,",
        "   DOORS-FRAMES-HARDWARE, WINDOWS & STOREFRONT) FROM THE DRAWINGS.",
        "2. CARRY THE ALLOWANCES ABOVE FOR MEP, ELEVATOR AND TESTING.",
        "3. BUILD GENERAL CONDITIONS FROM YOUR SCHEDULE (NTP NOV. 2, 2026 TO",
        "   SUBSTANTIAL COMPLETION AUG. 6, 2027) AND THE OWNER REQUIREMENTS.",
        "4. PREPARE A SITE LOGISTICS PLAN (C-100 SHOWS ONLY OWNER LIMITS) AND A",
        "   PROJECT-SPECIFIC SAFETY PLAN FOR WORK BESIDE AN OCCUPIED SCHOOL.",
        "5. COMPARE YOUR QUANTITIES WITH THE SEPARATE ANSWER-KEY WORKBOOK",
        "   ONLY AFTER COMPLETING YOUR OWN TAKEOFF."], size=TXT["label"], valign="top", leading=TXT["label"] * 1.5)

    # symbols legend at bottom left
    sy = sh.y0 + 6.6
    sh.line((sh.x0, sy + 0.25), (sh.x1, sy + 0.25), lw="thin")
    sh.text((cx[0], sy), "SYMBOLS LEGEND", size=TXT["label"], font=FONT_B, valign="top", underline=True)
    from .cad import (detail_callout, elevation_mark, grid_bubble, level_marker, section_mark,
                      spot_elev, _section_bubble)
    items = [
        ("grid", "GRID LINE AND BUBBLE"), ("sect", "BUILDING / WALL SECTION (NUMBER / SHEET)"),
        ("elev", "EXTERIOR ELEVATION MARK"), ("ielev", "INTERIOR ELEVATION MARK"),
        ("detail", "DETAIL / ENLARGED PLAN CALLOUT"), ("level", "LEVEL DATUM"),
        ("room", "ROOM NAME AND NUMBER"), ("door", "DOOR NUMBER"), ("win", "WINDOW / STOREFRONT TYPE"),
        ("wall", "PARTITION TYPE"), ("key", "KEYNOTE"), ("spot", "SPOT ELEVATION"),
    ]
    for k, (kind, label) in enumerate(items):
        col, row = divmod(k, 6)
        xx = cx[0] + col * 7.8
        yy = sy - 0.75 - row * 0.85
        v = sh.view(xx + 0.6, yy, 1 / 8)
        if kind == "grid":
            v.line((-4, 0), (4, 0), lw="hair", dash="grid")
            grid_bubble(v, (5.7, 0), "3", 0.36)
        elif kind == "sect":
            v.line((-3.0, 0), (3.5, 0), lw="med", dash="phantom")
            _section_bubble(v, (-3.0, 0), (0, 1), 1, "A-301", r=0.16)
            _section_bubble(v, (3.5, 0), (0, 1), 1, "A-301", r=0.16)
        elif kind == "elev":
            elevation_mark(v, (0, 0), 1, "A-201", direction=(0, 1), r=0.16)
        elif kind == "ielev":
            from .sheets_arch_plans import interior_elev_mark
            interior_elev_mark(v, (0, 0), "A-601")
        elif kind == "detail":
            detail_callout(v, (0, 0), 1.6, 3, "A-501", bubble_dir=(1, 0.4))
        elif kind == "level":
            level_marker(v, 0, 0, "LEVEL 2", value_text="114'-0\"")
            v.line((-4, 0), (-0.6, 0), lw="fine", dash="center")
        elif kind == "room":
            room_tag(v, (0, 0.6), "CLASSROOM", "101")
        elif kind == "door":
            door_tag(v, (0, 0), "101")
        elif kind == "win":
            window_tag(v, (0, 0), "W-A")
        elif kind == "wall":
            wall_tag(v, (0, 0), "P1")
        elif kind == "key":
            keynote_tag(v, (0, 0), 4)
        elif kind == "spot":
            spot_elev(v, (0, 0), "712.46")
        sh.text((xx + 1.75, yy), label, size=TXT["small"], valign="mid")
    # drawing conventions / line types
    lx = cx[2] + 0.0
    yy = sy - 0.75
    sh.text((cx[2] + 4.0, sy), "LINE TYPES", size=TXT["label"], font=FONT_B, valign="top", underline=True)
    for dash, label in ((None, "VISIBLE / CUT"), ("hidden", "HIDDEN / ABOVE / BEYOND"), ("demo", "TO BE REMOVED"),
                        ("grid", "GRID / CENTER LINE"), ("phantom", "SECTION CUT / LIMIT LINE"),
                        ("property", "PROPERTY LINE")):
        sh.line((cx[2] + 4.0, yy), (cx[2] + 5.6, yy), lw="thin", dash=dash)
        sh.text((cx[2] + 5.8, yy), label, size=TXT["small"], valign="mid")
        yy -= 0.4


# ----------------------------------------------------------------------------------------
# G-003 LIFE SAFETY PLANS
# ----------------------------------------------------------------------------------------

def _ls_plan(sh, level, ox, oy, s):
    v = sh.view(ox, oy, s)
    if level == "L1":
        fx = M.EXIST_FACE_X
        v.rect(fx - 30, -5, 30, 82, lw="fine", color="g50", fill="g05")
        v.mtext((fx - 15, 60), "EXISTING\nBUILDING\n(SPRINKLERED)", size=TXT["small"], anchor="c",
                valign="mid", color="g50")
    PL.draw_walls(v, level, "light")
    PL.draw_openings(v, level, swing=True)
    PL.draw_stair(v, "ST-1", level)
    PL.draw_stair(v, "ST-2", level)
    # 1-hour rated walls highlighted
    for w in M.interior_walls(level, types=("P2",)):
        v.line(w.p1, w.p2, lw=3.2, color="g30")
        v.line(w.p1, w.p2, lw=1.2, dash=[4, 2], color="black")
    # occupant loads
    for r in M.rooms(level):
        ol, f = occupant_load(r)
        c = r.tag_at or (r.shape.centroid.x, r.shape.centroid.y)
        name = r.name.replace("\n", " ")
        v.text((c[0], c[1] + 1.6), f"{r.num} {name}" if len(name) < 13 else r.num, size=TXT["tiny"],
               font=FONT_B, anchor="c")
        if f:
            v.text((c[0], c[1] - 1.2), f"{M.clear_room_poly(r).area:,.0f} SF / {f} = {ol} OCC.",
                   size=TXT["tiny"], anchor="c")
    # exits
    exits = []
    if level == "L1":
        exits = [((-2.5, 25.0), (-1, 0), "EXIT 1 (ST-1)"), ((152.5, 46.0), (1, 0), "EXIT 2 (ST-2)"),
                 ((153.0, 36.0), (1, 0), "EXIT 3 (EAST ENTRY)"), ((-38.0, 36.0), (-1, 0), "TO EXISTING")]
    else:
        exits = [((8.5, 27.0), (0, -1), "EXIT STAIR 1"), ((141.5, 45.0), (0, 1), "EXIT STAIR 2")]
    for (pt, d, lab) in exits:
        tip = (pt[0] + d[0] * 3.0, pt[1] + d[1] * 3.0)
        v.line(pt, tip, lw="heavy")
        v._arrowhead(tip, d, size_in=0.12)
        ap = (tip[0] + d[0] * 1.5, tip[1] + d[1] * 1.5 + (2.2 if d[1] == 0 else 0))
        v.text(ap, lab, size=TXT["tiny"], font=FONT_B, anchor="l" if d[0] > 0 else ("r" if d[0] < 0 else "c"),
               valign="mid")
    # travel distance paths (computed)
    if level == "L2":
        paths = [[(119.0, 71.0), (93.7, 43.5), (93.7, 36.0), (141.5, 36.0), (141.5, 42.3)],
                 [(149.0, 1.0), (123.7, 28.5), (123.7, 36.0), (141.5, 36.0), (141.5, 42.3)],
                 [(89.0, 1.0), (63.7, 28.5), (63.7, 36.0), (8.5, 36.0), (8.5, 29.7)]]
    else:
        paths = [[(89.0, 71.0), (63.7, 43.5), (63.7, 36.0), (8.5, 36.0), (8.5, 29.7)],
                 [(149.0, 1.0), (123.7, 28.5), (123.7, 36.0), (150.5, 36.0)]]
    for pth in paths:
        L = sum(math.dist(a, b) for a, b in zip(pth[:-1], pth[1:]))
        v.polyline(pth, lw="thin", dash=[2, 1.5])
        v.circle(pth[0], v.paper_len(0.03), lw=None, fill="black")
        v._arrowhead(pth[-1], (pth[-1][0] - pth[-2][0], pth[-1][1] - pth[-2][1]), size_in=0.07)
        mid = pth[0]
        v.text((mid[0] + (-2 if mid[0] > 100 else 2), mid[1] + (-1.8 if mid[1] > 36 else 1.8)),
               f"TRAVEL {L:.0f} FT < 250 FT", size=TXT["tiny"], font=FONT_B,
               anchor="r" if mid[0] > 100 else "l", valign="mid")
    # fire extinguishers
    for at in ((64.0, 30.8), (128.0, 41.2)):
        v.rect(at[0] - 1.0, at[1] - 0.5, 2.0, 1.0, lw="fine", fill="black")
        v.text((at[0], at[1] + (1.4 if at[1] > 36 else -1.4)), "FEC", size=TXT["tiny"], anchor="c",
               valign="mid")
    return v


def life_safety(sh):
    s = 3 / 32
    ox = sh.x0 + 0.6 + 70 * s
    v1 = _ls_plan(sh, "L1", ox, sh.y1 - 1.0 - 80 * s, s)
    sh.view_title(sh.x0 + 0.4, sh.y1 - 1.0 - 80 * s - 0.9, 1, "LIFE SAFETY PLAN - LEVEL 1", s, width=6.0)
    v2 = _ls_plan(sh, "L2", ox, sh.y1 - 1.0 - 80 * s - 9.8, s)
    sh.view_title(sh.x0 + 0.4, sh.y1 - 1.0 - 80 * s - 9.8 - 0.9, 2, "LIFE SAFETY PLAN - LEVEL 2", s, width=6.0)
    # legend + notes
    lx = sh.x0 + 23.2
    ly = sh.y1 - 0.3
    sh.text((lx, ly), "LIFE SAFETY LEGEND", size=TXT["label"], font=FONT_B, valign="top", underline=True)
    vv = sh.view(lx, ly - 0.45, 1 / 8)
    vv.line((0, 0), (5, 0), lw=3.2, color="g30")
    vv.line((0, 0), (5, 0), lw=1.2, dash=[4, 2])
    sh.text((lx + 0.8, ly - 0.45), "1-HOUR FIRE-RESISTANCE-RATED WALL (P2)", size=TXT["small"], valign="mid")
    vv = sh.view(lx, ly - 0.8, 1 / 8)
    vv.polyline([(0, 0), (5, 0)], lw="thin", dash=[2, 1.5])
    sh.text((lx + 0.8, ly - 0.8), "EXIT ACCESS TRAVEL PATH (MEASURED)", size=TXT["small"], valign="mid")
    vv = sh.view(lx, ly - 1.15, 1 / 8)
    vv.line((0, 0), (3.5, 0), lw="heavy")
    vv._arrowhead((4.5, 0), (1, 0), size_in=0.12)
    sh.text((lx + 0.8, ly - 1.15), "EXIT / EXIT DISCHARGE", size=TXT["small"], valign="mid")
    vv = sh.view(lx, ly - 1.5, 1 / 8)
    vv.rect(1.0, -0.5, 2.0, 1.0, lw="fine", fill="black")
    sh.text((lx + 0.8, ly - 1.5), "FIRE EXTINGUISHER CABINET (2-A:10-B:C)", size=TXT["small"], valign="mid")
    notes = [
        "BUILDING IS FULLY SPRINKLERED (NFPA 13). FIRE ALARM WITH EMERGENCY VOICE/ALARM COMMUNICATION PER IBC 907.2.3 (BY OTHERS).",
        "EXIT STAIRS AND ELEVATOR HOISTWAY ARE ENCLOSED WITH 1-HOUR P2 CMU; OPENINGS 60-MIN, SELF-CLOSING AND LATCHING.",
        "CORRIDORS ARE NOT REQUIRED TO BE RATED (GROUP E, SPRINKLERED). CROSS-CORRIDOR PAIR 100A ON MAGNETIC HOLD-OPENS RELEASED BY FIRE ALARM.",
        "MAXIMUM EXIT ACCESS TRAVEL DISTANCE 250 FT; COMMON PATH 75 FT; DEAD-END CORRIDOR 50 FT (SPRINKLERED).",
        "EXIT SIGNS, EMERGENCY LIGHTING AND FIRE ALARM DEVICES ARE BY DIV. 26/28 (NOT IN THIS SET).",
        "INTERIOR FINISH: CORRIDORS AND STAIRS CLASS B MIN. (SPRINKLERED); ROOMS CLASS C MIN. FLOORS: CLASS II IN CORRIDORS/STAIRS.",
        "CLASSROOM DOORS WITH CLASSROOM-SECURITY LOCKSETS MUST BE OPERABLE FROM THE EGRESS SIDE WITHOUT KEYS (IBC 1010.2).",
    ]
    notes_block(sh, lx, ly - 2.0, "LIFE SAFETY NOTES", notes, 8.6)
    # occupant summary table
    rows = []
    for lev in ("L1", "L2"):
        rows.append(f"LEVEL {lev[-1]}")
        for r in M.rooms(lev):
            ol, f = occupant_load(r)
            if f:
                rows.append([r.num, r.name.replace("\n", " "), f"{M.clear_room_poly(r).area:,.0f}", str(f), str(ol)])
        rows.append(["", "TOTAL", "", "", str(level_occ(lev))])
    table(sh, lx, sh.y0 + 9.3, [("ROOM", 0.7), ("NAME", 2.6), ("AREA SF", 1.1), ("SF/OCC", 0.9), ("OCC.", 0.8)],
          rows, row_h=0.17, size=TXT["tiny"] * 1.15, title="OCCUPANT LOAD CALCULATION")


SHEETS = [
    ("G-001", "COVER SHEET", cover),
    ("G-002", "GENERAL INFORMATION\nCODE ANALYSIS & ABBREVIATIONS", general_info),
    ("G-003", "LIFE SAFETY PLANS", life_safety),
]
