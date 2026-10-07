"""A-1xx floor plans, roof plan, finish plans, reflected ceiling plans."""
from __future__ import annotations

import math

from shapely.geometry import box
from shapely.ops import unary_union

from . import model as M
from . import plans as PL
from .cad import (FONT, FONT_B, TXT, Paper, detail_callout, elevation_mark, fmt_ftin, grid_bubble,
                  keynote_tag, notes_block, room_tag, section_mark, table, wall_tag, window_tag)

IN = M.IN
SCALE = 1 / 8


def plan_view(sh, level):
    # model x -66..169, y -20..91 at 1/8"
    ox = sh.x0 + 0.35 + 66 * SCALE
    oy = sh.y1 - 0.35 - 91 * SCALE
    return sh.view(ox, oy, SCALE)


def draw_plan_base(v, level, style="normal", grids=True, dims=True, swing=True, existing=True,
                   fixtures=True, casework=True, stairs=True):
    if existing:
        PL.draw_existing(v, level, "new")
    if level == "L2":
        # link roof below
        v.rect(M.EXIST_FACE_X, 30 - M.EW_OUT, 36 - 0.0, 12 + 2 * M.EW_OUT, lw="fine", dash="hidden")
    PL.draw_walls(v, level, style)
    PL.draw_openings(v, level, swing=swing)
    if stairs:
        PL.draw_stair(v, "ST-1", level)
        PL.draw_stair(v, "ST-2", level)
        PL.draw_elevator(v, level)
    if fixtures:
        PL.draw_toilets(v, level)
        PL.draw_drinking_fountains(v, level)
    if casework:
        PL.draw_casework(v, level)
    if grids:
        if level == "L1":
            PL.draw_grids(v, level, x_ext=(-16.0, 88.5), y_ext=(-14.0, 166.0), link=True)
        else:
            PL.draw_grids(v, level, x_ext=(-16.0, 88.5), y_ext=(-17.0, 166.0), link=False)
    if dims:
        PL.draw_dims(v, level)


def _hide_link_west_bubbles(v, level):
    """L1: grid lines B and C pass along the link walls; mask their west bubbles."""
    if level != "L1":
        return
    for y in (30.0, 42.0):
        r = v.paper_len(0.21)
        c = (-14.0 - r, y)
        v.circle(c, r * 1.08, lw=None, fill="white")
        v.rect(-14.0 - 2 * r - 0.3, y - 0.25, 2 * r + 0.3 + 13.0, 0.5, lw=None, fill="white",
               stroke=False)


PLAN_NOTES = [
    "DIMENSIONS ARE TO GRID LINES (CENTERLINE OF CMU), FACE OF CMU, OR MASONRY OPENING (MO) UNLESS NOTED. DO NOT SCALE DRAWINGS.",
    "ALL INTERIOR CMU PARTITIONS ARE TYPE P1 UNLESS TAGGED OTHERWISE. CMU EXTENDS TO UNDERSIDE OF STRUCTURE.",
    "DOOR FRAMES: LOCATE HINGE JAMB 8\" FROM ADJACENT PERPENDICULAR WALL FACE UNLESS DIMENSIONED.",
    "SEE A-701 FOR DOOR SCHEDULE, A-702 FOR HARDWARE SETS, A-711 FOR WINDOW AND STOREFRONT TYPES, A-801 FOR FINISHES AND CASEWORK.",
    "SEE A-401 FOR ENLARGED TOILET, STAIR AND ELEVATOR PLANS. SEE A-601 / A-602 FOR INTERIOR ELEVATIONS.",
    "PROVIDE FIRE-RETARDANT-TREATED WOOD BLOCKING IN WALLS FOR ALL CASEWORK, MARKERBOARDS, TACKBOARDS, TOILET ACCESSORIES, GRAB BARS AND WALL-HUNG FIXTURES.",
    "PLUMBING FIXTURES, EWC AND MECHANICAL/ELECTRICAL EQUIPMENT ARE SHOWN FOR COORDINATION ONLY. MEP DRAWINGS ARE NOT PART OF THIS PRACTICE SET.",
    "PROVIDE CONTROL JOINTS IN CMU AT MAX. 24'-0\" O.C. AND AS SHOWN ON ELEVATIONS. COORDINATE WITH MASONRY REINFORCING ON S-SHEETS.",
    "FIRE EXTINGUISHER CABINETS (FEC): SEMI-RECESSED IN CMU AT LOCATIONS SHOWN (4 PER FLOOR).",
]


def _legend(sh, x, y):
    p = sh
    p.text((x, y), "PLAN LEGEND", size=TXT["label"], font=FONT_B, valign="top", underline=True)
    yy = y - 0.3
    v = sh.view(x, yy, 1 / 8)
    items = [
        ("cmu", "CMU (P1 / P2 / EW-1 BACKUP)"),
        ("brick", "FACE BRICK VENEER"),
        ("insul", "CAVITY INSULATION"),
        ("stud", "METAL STUD PARTITION (P3 / P4)"),
        ("exist", "EXISTING CONSTRUCTION"),
    ]
    for k, label in items:
        r = (x, yy - 0.12, 0.45, 0.12)
        if k == "cmu":
            p.rect(*r, lw="thin", fill="white", hatch="ansi31", hatch_kw=dict(spacing=0.045))
        elif k == "brick":
            p.rect(*r, lw="thin", fill="white", hatch="brick", hatch_kw=dict(spacing=0.022))
        elif k == "insul":
            p.rect(*r, lw="thin", fill="g15")
        elif k == "stud":
            p.rect(*r, lw="thin", fill="g20")
        else:
            p.rect(*r, lw="thin", fill="g10", color="screen")
        p.text((x + 0.6, yy - 0.06), label, size=TXT["small"], valign="mid")
        yy -= 0.22
    syms = [
        ("door", "101", "DOOR NUMBER (SEE A-701)"),
        ("win", "W-A", "WINDOW / STOREFRONT TYPE (SEE A-711)"),
        ("wall", "P1", "PARTITION TYPE (SEE A-502)"),
        ("key", "1", "KEYNOTE"),
    ]
    for kind, t, label in syms:
        vv = sh.view(x + 0.22, yy - 0.06, 1 / 8)
        if kind == "door":
            from .cad import door_tag
            door_tag(vv, (0, 0), t)
        elif kind == "win":
            window_tag(vv, (0, 0), t)
        elif kind == "wall":
            wall_tag(vv, (0, 0), t)
        else:
            keynote_tag(vv, (0, 0), t)
        p.text((x + 0.6, yy - 0.06), label, size=TXT["small"], valign="mid")
        yy -= 0.24
    return y - yy


KEYNOTES_L1 = {
    1: "LINE OF EXISTING BUILDING FACE. SEE AD101 FOR DEMOLITION AT TIE-IN OPENING.",
    2: "NEW STEEL LINTEL IN EXISTING WALL AT ENLARGED OPENING, SEE S-302.",
    3: "BI-LEVEL ELECTRIC WATER COOLER (EWC) BY DIV. 22; PROVIDE BLOCKING.",
    4: "CONCRETE STOOP / WALK, SEE CIVIL. SLOPE AWAY FROM DOOR 1/4\" PER FT MAX.",
    5: "RECESSED WALK-OFF CARPET TILE WOM-1, SEE FINISH PLAN A-111.",
    6: "ELEVATOR CONTROLLER IN ROOM 112 (WITHIN 150 FT OF HOISTWAY PER MFR.).",
    7: "MAGNETIC HOLD-OPENS ON CROSS-CORRIDOR PAIR 100A RELEASE ON FIRE ALARM.",
    8: "8\" CONCRETE CURB UNDER LINK STOREFRONT SF-3, SEE A-312.",
    9: "FIRE EXTINGUISHER CABINET, SEMI-RECESSED.",
}
KEYNOTES_L2 = {
    1: "LINK ROOF BELOW (EPDM). SEE A-103.",
    3: "BI-LEVEL ELECTRIC WATER COOLER (EWC) BY DIV. 22; PROVIDE BLOCKING.",
    9: "FIRE EXTINGUISHER CABINET, SEMI-RECESSED.",
    10: "ROOF ACCESS HATCH 30\"x36\" WITH FIXED STEEL LADDER, SEE A-103.",
    11: "FRT PLYWOOD BACKBOARD 3/4\"x4'x8' (3) AT IDF WALL.",
    12: "GUARDRAIL 42\" HIGH AT TOP LANDING, SEE A-401.",
}


def _keynotes_on_plan(v, level):
    if level == "L1":
        keynote_tag(v, (-42.5, 44.0), 1, leader_to=(-36.6, 40.0))
        keynote_tag(v, (-44.0, 27.5), 2, leader_to=(-36.6, 31.0))
        keynote_tag(v, (39.3, 34.5), 3)
        keynote_tag(v, (-6.5, 22.0), 4)
        keynote_tag(v, (157.5, 25.5), 4)
        keynote_tag(v, (144.0, 33.0), 5)
        keynote_tag(v, (52.0, 8.0), 6)
        keynote_tag(v, (4.0, 38.5), 7)
        keynote_tag(v, (-26.0, 46.5), 8, leader_to=(-26.0, 43.2))
        for at in ((64.0, 33.0), (128.0, 39.0)):
            keynote_tag(v, at, 9)
            v.rect(at[0] - 1.0, 30 + PL.CMUh if at[1] < 36 else 42 - PL.CMUh - 0.5, 2.0, 0.5, lw="fine")
    else:
        keynote_tag(v, (-18.0, 46.0), 1, leader_to=(-18.0, 41.0))
        keynote_tag(v, (39.3, 34.5), 3)
        for at in ((64.0, 33.0), (128.0, 39.0)):
            keynote_tag(v, at, 9)
            v.rect(at[0] - 1.0, 30 + PL.CMUh if at[1] < 36 else 42 - PL.CMUh - 0.5, 2.0, 0.5, lw="fine")
        keynote_tag(v, (49.5, 27.5), 10)
        keynote_tag(v, (36.0, 3.5), 11)
        keynote_tag(v, (9.0, 14.3), 12)


def _ref_marks(v, level):
    """section, wall section, elevation and enlarged plan references"""
    # building sections (A-301)
    section_mark(v, (75.0, -20.0), (75.0, 92.5), 1, "A-301", look="left")
    section_mark(v, (-8.0, 36.0) if level == "L1" else (-8.0, 36.0), (171.5, 36.0), 2, "A-301",
                 look="left")
    if level == "L1":
        section_mark(v, (-18.0, 22.0), (-18.0, 52.0), 3, "A-301", look="right")
    # wall sections (A-311 / A-312)
    from .cad import _section_bubble
    # wall section cuts: bubble inside the building, cut line through the wall
    for (p, n, num, sht) in (((45.0, 66.0), (0, 1), 1, "A-311"), ((105.0, 6.0), (0, -1), 2, "A-311"),
                             ((8.6, 4.2), (0, -1), 3, "A-311"), ((144.5, 36.0), (1, 0), 1, "A-312")):
        a = (p[0] + n[0] * (abs(p[0] - 150) + 2.5 if n[0] > 0 else 0) + n[1] * 0,
             p[1] + (n[1] * ((72 - p[1]) + 2.5) if n[1] > 0 else n[1] * (p[1] + 2.5)))
        if n[0] > 0:
            a = (152.5, p[1])
        v.line(p, a, lw="med")
        _section_bubble(v, p, (n[1], -n[0]) if n[1] != 0 else (0, 1), num, sht, r=0.15)
    if level == "L1":
        a, p = (-12.0, 45.5), (-12.0, 41.0)
        v.line(a, p, lw="med")
        _section_bubble(v, a, (-1, 0), 2, "A-312", r=0.15)
    # exterior elevations
    if level == "L1":
        elevation_mark(v, (75.0, 98.0) if False else (40.0, 84.0), 1, "A-201", direction=(0, -1))
        elevation_mark(v, (40.0, -12.0), 2, "A-201", direction=(0, 1))
        elevation_mark(v, (173.0, 57.0), 1, "A-202", direction=(-1, 0))
        elevation_mark(v, (-14.0, 64.0), 2, "A-202", direction=(1, 0))
        elevation_mark(v, (-27.0, 55.0), 3, "A-202", direction=(0, -1))
        elevation_mark(v, (-27.0, 17.0), 4, "A-202", direction=(0, 1))
    # enlarged plan callouts (A-401)
    n = 1 if level == "L1" else 2
    detail_callout(v, (45.0, 15.0), (32.0, 31.0), n, "A-401", bubble_dir=(1, -1), shape="rect")
    detail_callout(v, (6.0, 15.0), (13.0, 31.0), 3, "A-401", bubble_dir=(-1, -1), shape="rect")
    detail_callout(v, (144.0, 57.0), (13.0, 31.0), 4, "A-401", bubble_dir=(1, 1), shape="rect")
    # interior elevation marks (A-601: classroom; A-602: toilets on A-401)
    if level == "L1":
        interior_elev_mark(v, (45.0, 57.0), "A-601")


def interior_elev_mark(v, c, sheet, nums=(1, 2, 3, 4)):
    """4-way interior elevation marker: circle with sheet no. and numbered pointers N/E/S/W."""
    r = v.paper_len(0.13)
    for i, d in enumerate(((0, 1), (1, 0), (0, -1), (-1, 0))):
        tip = (c[0] + d[0] * r * 1.75, c[1] + d[1] * r * 1.75)
        a = (c[0] + d[1] * r * 0.75, c[1] - d[0] * r * 0.75)
        b = (c[0] - d[1] * r * 0.75, c[1] + d[0] * r * 0.75)
        v.polygon([a, tip, b], lw="fine", fill="black")
        q = (c[0] + d[0] * r * 2.45, c[1] + d[1] * r * 2.45)
        v.text(q, str(nums[i]), size=TXT["small"], font=FONT_B, anchor="c", valign="mid")
    v.circle(c, r, lw="thin", fill="white")
    v.text(c, sheet, size=TXT["tiny"], anchor="c", valign="mid")


def floor_plan_sheet(level):
    def draw(sh):
        v = plan_view(sh, level)
        draw_plan_base(v, level)
        PL.draw_room_tags(v, level)
        PL.draw_door_tags(v, level)
        PL.draw_window_tags(v, level)
        PL.draw_wall_tags(v, level)
        _keynotes_on_plan(v, level)
        _ref_marks(v, level)
        # title + north arrow
        ty = v.to_paper((0, -21.5))[1] - 0.1
        nm = "FIRST FLOOR PLAN" if level == "L1" else "SECOND FLOOR PLAN"
        sh.view_title(sh.x0 + 0.4, ty, 1, nm, SCALE, width=6.0)
        sh.north_arrow(sh.x0 + 8.2, ty + 0.2, 0.55)
        sh.scale_bar(sh.x0 + 9.2, ty - 0.05, SCALE, 32)
        # bottom panel: notes, keynotes, legend
        top = ty - 0.55
        sh.line((sh.x0, top + 0.12), (sh.x1, top + 0.12), lw="thin")
        h = notes_block(sh, sh.x0 + 0.3, top, "GENERAL FLOOR PLAN NOTES", PLAN_NOTES, 10.6)
        kn = KEYNOTES_L1 if level == "L1" else KEYNOTES_L2
        kx = sh.x0 + 11.6
        sh.text((kx, top), "KEYNOTES", size=TXT["label"], font=FONT_B, valign="top", underline=True)
        yy = top - 0.25
        for k, t in kn.items():
            vv = sh.view(kx + 0.12, yy - 0.05, 1 / 8)
            keynote_tag(vv, (0, 0), k)
            sh.mtext((kx + 0.32, yy + 0.01), t, size=TXT["note"], width=8.2)
            yy -= 0.26 if len(t) < 95 else 0.38
        _legend(sh, sh.x0 + 21.0, top)
        # area / occupancy summary (code information, not takeoff quantities)
        ax = sh.x0 + 26.0
        occ = 0
        for r in M.rooms(level):
            a = M.clear_room_poly(r).area
            if r.name in ("CLASSROOM", "SMALL GROUP"):
                occ += a / 20.0
            elif r.name.startswith("CORR") or r.name == "LINK" or r.name.startswith("STAIR") \
                    or r.name.startswith("ELEV"):
                pass
            elif "TOILET" in r.name or r.name in ("BOYS", "GIRLS"):
                pass
            elif r.name.startswith("MECH") or r.name.startswith("STOR") or r.name.startswith("CUST"):
                occ += a / 300.0
            else:
                occ += a / 150.0
        g = M.gross_area(level)
        ncls = len([r for r in M.rooms(level) if r.name == "CLASSROOM"])
        rows = [["GROSS FLOOR AREA (O/O BRICK)", f"{g:,.0f} SF"], ["CLASSROOMS", f"{ncls}"],
                ["OCCUPANT LOAD (IBC TABLE 1004.5)", f"{math.ceil(occ)}"],
                ["REQUIRED EXITS / PROVIDED", "2 / " + ("4" if level == "L1" else "2")]]
        table(sh, ax, top, [("LEVEL " + level[-1] + " SUMMARY", 3.4), ("", 1.6)], rows, row_h=0.2,
              size=TXT["small"], align=["l", "r"])
    return draw


# ========================================================================================
# FINISH PLANS (A-111 / A-112)
# ========================================================================================
FLOOR_STYLE = {
    "VCT-1": dict(hatch="grid", hatch_kw=dict(spacing=1.0, w="hair", col="g40")),
    "VCT-2": dict(fill="g20", hatch="grid", hatch_kw=dict(spacing=1.0, w="hair", col="g50")),
    "LVT-1": dict(hatch="plank", hatch_kw=dict(spacing=(3.0, 0.5), w="hair", col="g40")),
    "LVT-2": dict(fill="g30", hatch="grid", hatch_kw=dict(spacing=1.5, w="hair", col="g60")),
    "CPT-1": dict(hatch="grid", hatch_kw=dict(spacing=2.0, w="hair", col="g40"), dots=True),
    "WOM-1": dict(fill="g40", hatch="grid", hatch_kw=dict(spacing=2.0, w="hair", col="g70")),
    "PT-1": dict(hatch="tile", hatch_kw=dict(spacing=(2.0, 1.0), w="hair", col="g40")),
    "SC-1": dict(hatch="concrete", hatch_kw=dict(scale=1.3, w="hair", col="g50")),
    "RF-1": dict(hatch="dots", hatch_kw=dict(scale=0.8, col="g40")),
    "RST-1": dict(hatch="tile", hatch_kw=dict(spacing=(1000.0, 11 / 12.0), w="hair", col="g40")),
}


def floor_zones(level):
    """[(code, geometry, room)] floor finish zones for a level."""
    zones = []
    for r in M.rooms(level):
        g = M.clear_room_poly(r)
        f = r.floor
        if r.name == "CLASSROOM":
            band = g.buffer(-2.0, join_style=2).difference(g.buffer(-3.0, join_style=2))
            zones.append(("VCT-1", g.difference(band), r))
            zones.append(("VCT-2", band, r))
        elif r.num in ("100", "200"):
            bands = unary_union([box(x - 1.0, 29, x + 1.0, 43) for x in (30, 60, 90, 120)])
            wom = box(140.0, 29, 151, 43) if level == "L1" else None
            b = g.intersection(bands)
            rest = g.difference(bands)
            if wom is not None:
                rest = rest.difference(wom)
                zones.append(("WOM-1", g.intersection(wom), r))
            zones.append(("LVT-1", rest, r))
            zones.append(("LVT-2", b, r))
        elif r.num == "100A":
            zones.append(("LVT-1", g, r))
        elif r.num.startswith("ST"):
            sg = PL.stair_geom(r.num)
            flights = box(sg["x0"], sg["f_lo"], sg["x1"], sg["f_hi"])
            zones.append(("RF-1", g.difference(flights), r))
            zones.append(("RST-1", g.intersection(flights), r))
        elif f.startswith("BY"):
            continue
        else:
            zones.append((f.split(" ")[0], g, r))
    return zones


def finish_plan_sheet(level):
    def draw(sh):
        v = plan_view(sh, level)
        if level == "L1":
            PL.draw_existing(v, level, "new")
        else:
            v.rect(M.EXIST_FACE_X, 30 - M.EW_OUT, 36, 12 + 2 * M.EW_OUT, lw="fine", dash="hidden")
            v.text((-18, 36), "LINK ROOF BELOW", size=TXT["note"], anchor="c", valign="mid")
        for code, g, r in floor_zones(level):
            st = FLOOR_STYLE.get(code, {})
            v.geom(g, lw="hair", fill=st.get("fill"), hatch=st.get("hatch"),
                   hatch_kw=st.get("hatch_kw"))
            if st.get("dots"):
                v.geom(g, lw=None, hatch="carpet", hatch_kw=dict(scale=1.6, col="g50"), stroke=False)
        PL.draw_walls(v, level, "light")
        PL.draw_openings(v, level, swing=False)
        PL.draw_grids(v, level, x_ext=(-16.0, 88.5), y_ext=(-14.0 if level == "L1" else -17.0, 166.0),
                      link=False)
        # finish tags
        for r in M.rooms(level):
            if r.floor.startswith("BY"):
                continue
            c = r.tag_at or (r.shape.centroid.x, r.shape.centroid.y + 2.5)
            name = r.name.replace("\n", " ")
            p = Paper(sh.c)
            x, y = v.to_paper(c)
            lbl = f"{r.num}  {name}" if len(name) < 14 else r.num
            w = max(p.text_width(lbl, TXT["small"], FONT_B), p.text_width(r.floor, TXT["small"])) + 0.14
            h = 0.36
            p.rect(x - w / 2, y - h / 2, w, h, lw="fine", fill="white")
            p.text((x, y + 0.07), lbl, size=TXT["small"],
                   font=FONT_B, anchor="c", valign="mid")
            p.text((x, y - 0.09), r.floor, size=TXT["small"], anchor="c", valign="mid")
        # pattern dimension notes
        v.leader([(15.0, 47.0), (9.0, 50.5)], "VCT-2 12\" BAND, 2'-0\" FROM WALL", size=TXT["tiny"])
        v.leader([(30.0, 36.0), (25.0, 39.5)], "LVT-2 2'-0\" BAND CENTERED ON GRID (TYP.)",
                 size=TXT["tiny"])
        v.dim((30 - 1.0, 41.2), (30 + 1.0, 41.2), 0, size=TXT["tiny"])
        if level == "L1":
            v.leader([(145.0, 34.0), (154.0, 26.0)], "WOM-1 RECESSED WALK-OFF (10'-0\" FROM ENTRANCE)",
                     size=TXT["tiny"])
        ty = v.to_paper((0, -21.5))[1] - 0.1
        nm = "FIRST FLOOR FINISH PLAN" if level == "L1" else "SECOND FLOOR FINISH PLAN"
        sh.view_title(sh.x0 + 0.4, ty, 1, nm, SCALE, width=6.5)
        sh.north_arrow(sh.x0 + 8.2, ty + 0.2, 0.55)
        top = ty - 0.55
        sh.line((sh.x0, top + 0.12), (sh.x1, top + 0.12), lw="thin")
        # legend of floor patterns
        sh.text((sh.x0 + 0.3, top), "FLOOR FINISH LEGEND", size=TXT["label"], font=FONT_B, valign="top",
                underline=True)
        codes = ["VCT-1", "VCT-2", "LVT-1", "LVT-2", "CPT-1", "WOM-1", "PT-1", "RF-1", "RST-1", "SC-1"]
        yy = top - 0.3
        xx = sh.x0 + 0.3
        for k, code in enumerate(codes):
            if k == 5:
                xx += 7.6
                yy = top - 0.3
            st = FLOOR_STYLE[code]
            vv = sh.view(xx, yy - 0.3, 1 / 8)
            sq = [(0, 0), (5.6, 0), (5.6, 2.4), (0, 2.4)]
            vv.polygon(sq, lw="fine", fill=st.get("fill"), hatch=st.get("hatch"),
                       hatch_kw=st.get("hatch_kw"))
            if st.get("dots"):
                vv.polygon(sq, lw=None, hatch="carpet", hatch_kw=dict(scale=1.6, col="g50"), stroke=False)
            sh.text((xx + 0.85, yy - 0.15), code, size=TXT["small"], font=FONT_B, valign="mid")
            sh.mtext((xx + 1.45, yy - 0.15), M.FINISHES[code], size=TXT["small"], valign="mid", width=5.9)
            yy -= 0.42
        notes = [
            "FLOOR PATTERNS ARE SHOWN TRUE TO SCALE. FIELD TILE LAYOUT: CENTER ON ROOM; NO TILE LESS THAN 1/2 WIDTH AT PERIMETER.",
            "CLASSROOMS: VCT-1 FIELD WITH CONTINUOUS VCT-2 12\" BAND LOCATED 2'-0\" FROM FACE OF WALL / CASEWORK TOE KICK.",
            "CORRIDORS: LVT-1 PLANKS LAID EAST-WEST, RANDOM ENDS (MIN. 6\" STAGGER). LVT-2 2'-0\" WIDE BANDS CENTERED ON GRIDS 2, 3, 4 AND 5, WALL TO WALL.",
            "PROVIDE RUBBER REDUCER / TRANSITION STRIPS AT ALL CHANGES OF FLOOR MATERIAL, CENTERED UNDER DOOR LEAF IN CLOSED POSITION.",
            "FLOOR FINISHES CONTINUE UNDER CASEWORK BASES ONLY WHERE CASEWORK IS ON LEGS; OTHERWISE STOP AT TOE KICK.",
            "RUBBER BASE RB-1 AT ALL WALLS, CASEWORK TOE KICKS AND COLUMNS UNLESS NOTED; PT-1B TILE COVE BASE AT TOILET ROOMS.",
            "TOILET ROOMS: CT-1 WALL TILE WAINSCOT TO 7'-0\" AFF ON ALL WALLS; SEE A-602.",
            "PERFORM CONCRETE MOISTURE (RH) AND pH TESTING PRIOR TO RESILIENT FLOORING; SEE SPECIFICATIONS.",
            "STAIRS: RST-1 TREADS/RISERS ON ALL STEPS; RF-1 SHEET ON LANDINGS WITH MATCHING STRINGER/SKIRT TRIM.",
        ]
        notes_block(sh, sh.x0 + 16.4, top, "FINISH PLAN NOTES", notes, 10.5)
        notes_block(sh, sh.x0 + 27.2, top, "WALL & CEILING FINISHES",
                    ["SEE ROOM FINISH SCHEDULE A-801 FOR WALL, BASE AND CEILING FINISHES.",
                     "PAINT ALL EXPOSED CMU (PNT-1) UNLESS NOTED. CUSTODIAL: PNT-2 EPOXY.",
                     "PAINT EXPOSED STEEL, DECK AND JOISTS IN STAIRS AND MECH./STORAGE (EXP)."], 3.9)
    return draw


# ========================================================================================
# REFLECTED CEILING PLANS (A-121 / A-122)
# ========================================================================================

def _ceiling_grid(v, g, size=2.0):
    """2'x2' grid centered on the polygon's bounding box (balanced borders)."""
    x0, y0, x1, y1 = g.bounds
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    # choose offset so borders >= half tile
    def lines(a0, a1, c):
        n = int((a1 - a0) / size) + 2
        start = c - size / 2 if ((a1 - a0) / size) % 2 < 1 else c
        out = []
        k = start
        while k > a0:
            k -= size
        k += size
        while k < a1:
            out.append(k)
            k += size
        return out
    for x in lines(x0, x1, cx):
        seg = g.intersection(box(x - 0.001, y0 - 1, x + 0.001, y1 + 1))
        if not seg.is_empty:
            bx = seg.bounds
            v.line((x, bx[1]), (x, bx[3]), lw="hair", color="g40")
    for y in lines(y0, y1, cy):
        seg = g.intersection(box(x0 - 1, y - 0.001, x1 + 1, y + 0.001))
        if not seg.is_empty:
            bx = seg.bounds
            v.line((bx[0], y), (bx[2], y), lw="hair", color="g40")


def clg_tag(v, at, mat, ht):
    p = Paper(v.c)
    x, y = v.to_paper(at)
    t2 = fmt_ftin(ht) + " AFF" if ht else "-"
    w = max(p.text_width(mat, TXT["small"], FONT_B), p.text_width(t2, TXT["small"])) + 0.12
    h = 0.32
    p.rect(x - w / 2, y - h / 2, w, h, lw="fine", fill="white")
    p.line((x - w / 2, y), (x + w / 2, y), lw="hair")
    p.text((x, y + 0.08), mat, size=TXT["small"], font=FONT_B, anchor="c", valign="mid")
    p.text((x, y - 0.08), t2, size=TXT["small"], anchor="c", valign="mid")


def rcp_sheet(level):
    def draw(sh):
        v = plan_view(sh, level)
        if level == "L1":
            PL.draw_existing(v, level, "new")
        else:
            v.rect(M.EXIST_FACE_X, 30 - M.EW_OUT, 36, 12 + 2 * M.EW_OUT, lw="fine", dash="hidden")
            v.text((-18, 36), "LINK ROOF BELOW", size=TXT["note"], anchor="c", valign="mid")
        for r in M.rooms(level):
            g = M.clear_room_poly(r)
            if r.ceiling in ("ACT-1", "ACT-2"):
                _ceiling_grid(v, g)
                if r.ceiling == "ACT-2":
                    v.geom(g, lw=None, hatch="ansi31", hatch_kw=dict(spacing=0.12, w="hair", col="g60"),
                           stroke=False)
            elif r.ceiling == "GWB-1":
                v.geom(g, lw=None, hatch="sand", hatch_kw=dict(scale=1.4, col="g50"), stroke=False)
            elif r.ceiling == "EXP":
                v.geom(g, lw=None, hatch="ansi31", hatch_kw=dict(spacing=0.25, w="hair", col="g70",
                                                                 angle=-45), stroke=False)
            c = r.tag_at or (r.shape.centroid.x, r.shape.centroid.y)
            if r.num.startswith("ST"):
                c = (c[0], c[1] - 4.5)
            if r.ceiling not in ("-",):
                clg_tag(v, (c[0], c[1] - (0 if r.tag_at else 3.0)), r.ceiling, r.clg_ht)
            if r.name == "CLASSROOM" or r.name == "CORRIDOR":
                room_lbl = r.num
                v.text((c[0], c[1] + 2.4), f"{r.name} {room_lbl}", size=TXT["small"], font=FONT_B,
                       anchor="c", valign="mid")
        PL.draw_walls(v, level, "rcp", openings=True)
        # door heads in rcp (line across opening) and window frames
        for o in M.doors(level):
            box_ = PL._opening_box(o, extra=0.0)
            v.geom(box_, lw="hair", fill="white")
        cut = M.LEVELS[level] + M.CEILING_CUT
        for o in M.openings_on(level, kinds=("window", "storefront")):
            if o.sill < cut < o.head:
                PL.draw_window(v, o, level)
        PL.draw_grids(v, level, x_ext=(-16.0, 88.5), y_ext=(-14.0 if level == "L1" else -17.0, 166.0),
                      link=False)
        ty = v.to_paper((0, -21.5))[1] - 0.1
        nm = "FIRST FLOOR REFLECTED CEILING PLAN" if level == "L1" else "SECOND FLOOR REFLECTED CEILING PLAN"
        sh.view_title(sh.x0 + 0.4, ty, 1, nm, SCALE, width=7.6)
        sh.north_arrow(sh.x0 + 9.0, ty + 0.2, 0.55)
        top = ty - 0.55
        sh.line((sh.x0, top + 0.12), (sh.x1, top + 0.12), lw="thin")
        sh.text((sh.x0 + 0.3, top), "CEILING LEGEND", size=TXT["label"], font=FONT_B, valign="top",
                underline=True)
        yy = top - 0.32
        items = [("ACT-1", M.FINISHES["ACT-1"]), ("ACT-2", M.FINISHES["ACT-2"]),
                 ("GWB-1", M.FINISHES["GWB-1"]), ("EXP", M.FINISHES["EXP"])]
        for code, d in items:
            vv = sh.view(sh.x0 + 0.3, yy - 0.3, 1 / 8)
            sq = box(0, 0, 6.0, 2.4)
            if code.startswith("ACT"):
                vv.geom(sq, lw="fine")
                for k in (2, 4):
                    vv.line((k, 0), (k, 2.4), lw="hair")
                vv.line((0, 1.2), (6, 1.2), lw="hair")
                if code == "ACT-2":
                    vv.geom(sq, lw=None, hatch="ansi31", hatch_kw=dict(spacing=0.12, w="hair"),
                            stroke=False)
            elif code == "GWB-1":
                vv.geom(sq, lw="fine", hatch="sand", hatch_kw=dict(scale=1.4))
            else:
                vv.geom(sq, lw="fine", hatch="ansi31", hatch_kw=dict(spacing=0.25, angle=-45))
            sh.text((sh.x0 + 1.25, yy - 0.15), code, size=TXT["small"], font=FONT_B, valign="mid")
            sh.mtext((sh.x0 + 1.85, yy - 0.15), d, size=TXT["small"], valign="mid", width=6.0)
            yy -= 0.42
        vv = sh.view(sh.x0 + 0.65, yy - 0.18, 1 / 8)
        clg_tag(vv, (0, 0), "ACT-1", 10.0)
        sh.text((sh.x0 + 1.25, yy - 0.18), "CEILING TAG: MATERIAL / HEIGHT ABOVE FINISH FLOOR",
                size=TXT["small"], valign="mid")
        notes = [
            "ACOUSTICAL CEILING GRID: CENTER IN ROOMS AS SHOWN; BORDER TILES NOT LESS THAN 1/2 TILE. SEISMIC BRACING PER ASTM E580 NOT REQUIRED (SDC B); PROVIDE PERIMETER WALL ANGLE AND HANGER WIRES @ 4'-0\" O.C.",
            "LIGHT FIXTURES, DIFFUSERS, GRILLES, SPEAKERS, SPRINKLER HEADS AND DEVICES ARE BY MEP AND ARE NOT SHOWN IN THIS PRACTICE SET. COORDINATE TILE CUTTING ALLOWANCE.",
            "GWB-1 CEILINGS: 5/8\" MOISTURE-RESISTANT GYPSUM BOARD ON SUSPENDED 1 1/2\" CRC MAIN RUNNERS @ 48\" O.C. AND 7/8\" FURRING CHANNELS @ 16\" O.C.; LEVEL 4 FINISH; EPOXY PAINT.",
            "PROVIDE 24\"x24\" ACCESS PANELS IN GWB CEILINGS AT VALVES/DAMPERS (ALLOW 2 PER TOILET ROOM).",
            "EXPOSED STRUCTURE (EXP): PAINT UNDERSIDE OF DECK, JOISTS AND BEAMS. STAIR SOFFITS: PAINT.",
            "CEILING HEIGHTS ARE TO UNDERSIDE OF GRID / FINISH. WINDOW HEADS AT 9'-4\" AFF; CORRIDOR STOREFRONT HEADS AT 9'-4\" AFF.",
        ]
        notes_block(sh, sh.x0 + 9.0, top, "REFLECTED CEILING PLAN NOTES", notes, 12.5)
    return draw


# ========================================================================================
# ROOF PLAN (A-103)
# ========================================================================================
ROOF_DRAINS = [(15.0, 36.0), (52.5, 36.0), (97.5, 36.0), (135.0, 36.0)]
RTUS = [("RTU-1", (45.0, 57.0)), ("RTU-2", (105.0, 57.0)), ("RTU-3", (105.0, 15.0))]
HATCH = (46.75, 27.0, 2.5, 3.0)


def roof_plan_sheet(sh):
    v = plan_view(sh, "L2")
    out = M.EW_OUT
    # existing building roof (screened) and link roof
    fx = M.EXIST_FACE_X
    v.line((fx, -8), (fx, 80), lw="thin", color="screen")
    v.line((fx - 1, -8), (fx - 1, 80), lw="fine", color="screen")
    v.mtext((fx - 14, 60), "EXISTING ROOF\n(NO WORK)", size=TXT["note"], anchor="c", valign="mid",
            color="screen")
    from .cad import break_line
    break_line(v, (PL.EX_X0, -8), (PL.EX_X0, 80))
    # link roof: parapets on N and S (outer brick face to inner CMU face)
    for yy, sgn in ((42.0, 1), (30.0, -1)):
        v.rect(fx, yy - M.EW_IN if sgn > 0 else yy - out, 36.0, out + M.EW_IN, lw="thin", fill="g20")
    v.rect(fx, 30 + M.EW_IN, 36.0, 12 - 2 * M.EW_IN, lw="fine")
    v.text((-18.0, 37.5), "LINK ROOF R-1", size=TXT["small"], font=FONT_B, anchor="c", valign="mid")
    v.text((-18.0, 35.6), "T.O. STEEL 114'-0\"", size=TXT["tiny"], anchor="c", valign="mid")
    # slope to scupper at north (x=-10)
    v.line((-18.0, 33.0), (-18.0, 34.4), lw="fine")
    v._arrowhead((-10.0, 41.4), (1, 1))
    v.line((-18.0, 34.4), (-10.0, 41.4), lw="fine")
    v.text((-14.5, 40.2), "1/4\"/FT", size=TXT["tiny"], anchor="r", valign="mid")
    v.rect(-11.0, 42.0 + M.EW_IN, 2.0, out - M.EW_IN, lw="thin", fill="white")
    v.leader([(-10.0, 43.4), (-6.0, 49.0)], "SCUPPER, CONDUCTOR HEAD & DOWNSPOUT", size=TXT["tiny"])
    # main roof parapet
    outer = M.outline_poly("L2").buffer(out, join_style=2)
    inner = M.outline_poly("L2").buffer(-M.EW_IN, join_style=2)
    v.geom(outer.difference(inner), lw="thin", fill="g20")
    v.geom(outer, lw="heavy")
    v.geom(inner, lw="thin")
    # tapered insulation: drain valley along y = 36, crickets between drains
    v.line((-M.EW_IN + 0.0 + 0.4, 36.0), (150 - M.EW_IN - 0.4, 36.0), lw="fine", dash="dashed")
    mids = [(ROOF_DRAINS[i][0] + ROOF_DRAINS[i + 1][0]) / 2 for i in range(3)]
    for xm in mids:
        d = 6.0
        v.polygon([(xm, 36 + d), (xm + d * 1.4, 36), (xm, 36 - d), (xm - d * 1.4, 36)], lw="fine",
                  dash="dashed")
        v.line((xm, 36 + d), (xm, 36 - d), lw="fine", dash="dashed")
        v.text((xm, 36 + d + 0.8), "CRICKET", size=TXT["tiny"], anchor="c", valign="bot")
    for ex in (0.5, 149.5):
        pass
    # slope arrows toward drain line
    for x in (30.0, 75.0, 120.0):
        for y0, y1 in ((66.0, 44.0), (6.0, 28.0)):
            v.line((x, y0), (x, y1), lw="fine")
            v._arrowhead((x, y1), (0, y1 - y0))
            v.text((x + 0.7, (y0 + y1) / 2), "1/4\"/FT", size=TXT["tiny"], anchor="l", valign="mid", rot=90)
    # drains
    for i, (x, y) in enumerate(ROOF_DRAINS, 1):
        v.circle((x, y), 0.9, lw="thin", fill="white")
        v.circle((x, y), 0.45, lw="fine")
        v.circle((x + 2.0, y), 0.7, lw="thin", fill="white")
        v.text((x + 2.0, y), "O", size=TXT["tiny"], anchor="c", valign="mid")
        v.text((x, y - 1.6), f"RD-{i} / OD-{i}", size=TXT["tiny"], font=FONT_B, anchor="c", valign="top")
    # RTU curbs + walkway pads
    for name, (x, y) in RTUS:
        v.rect(x - 7.0, y - 3.5, 14.0, 7.0, lw="thin", fill="g10")
        v.line((x - 7.0, y - 3.5), (x + 7.0, y + 3.5), lw="hair")
        v.line((x - 7.0, y + 3.5), (x + 7.0, y - 3.5), lw="hair")
        v.text((x, y + 4.2), f"{name} (DIV. 23) ON 14'-0\" x 7'-0\" CURB", size=TXT["tiny"], anchor="c",
               valign="bot")
    hx, hy, hw, hh = HATCH
    v.rect(hx - hw / 2, hy - hh / 2, hw, hh, lw="thin", fill="white")
    v.line((hx - hw / 2, hy - hh / 2), (hx + hw / 2, hy + hh / 2), lw="hair")
    v.leader([(hx + 1.3, hy + 1.0), (hx + 6.0, hy + 4.5)], "ROOF HATCH 30\"x36\" W/ SAFETY POST",
             size=TXT["tiny"])
    # walkway pads from hatch to RTUs
    for (x, y) in ((45.0, 53.5 - 0.0), (105.0, 53.5), (105.0, 18.5)):
        pass
    for seg in (((hx, hy + hh / 2), (hx, 53.5)), ((hx + hw / 2, 27.0), (111.25, 27.0)),
                ((110.0, 28.25), (110.0, 53.5)), ((110.0, 25.75), (110.0, 18.5))):
        (ax_, ay), (bx, by) = seg
        if ax_ == bx:
            v.rect(ax_ - 1.25, min(ay, by), 2.5, abs(by - ay), lw="fine", dash="hidden")
        else:
            v.rect(min(ax_, bx), ay - 1.25, abs(bx - ax_), 2.5, lw="fine", dash="hidden")
    v.leader([(80.0, 27.8), (84.0, 31.0)], "WALKWAY PADS 30\" WIDE (EPDM)", size=TXT["tiny"])
    # spot elevations (top of membrane, approximate)
    from .cad import spot_elev
    for (x, y, t) in ((1.5, 70.5, "T.O.INS. +9 1/2\""), (148.5, 1.5, "T.O.INS. +9 1/2\""),
                      (15.0, 37.8, "LOW PT +1/2\""), (33.75, 42.2, "+2\"")):
        spot_elev(v, (x, y), t, size=TXT["tiny"])
    v.text((75.0, 64.5), "ROOF R-1: 60-MIL FULLY ADHERED EPDM / 1/2\" COVER BOARD /", size=TXT["small"],
           font=FONT_B, anchor="c")
    v.text((75.0, 62.8), "TAPERED POLYISO (R-30 AVG., 1 1/2\" MIN.) / 1 1/2\" TYPE B STEEL DECK",
           size=TXT["small"], font=FONT_B, anchor="c")
    v.text((75.0, 61.1), "T.O. STEEL EL. 128'-0\"   TOP OF PARAPET EL. 131'-4\"", size=TXT["small"],
           anchor="c")
    # details refs
    detail_callout(v, (75.0, 72.0), 2.5, 8, "A-501", bubble_dir=(1, 1))
    detail_callout(v, (0.0, 36.0), 2.5, 12, "A-501", bubble_dir=(-1, 1))
    detail_callout(v, (hx, hy), 2.6, 13, "A-501", bubble_dir=(-1, -1))
    PL.draw_grids(v, "L2", x_ext=(-16.0, 88.5), y_ext=(-17.0, 166.0), link=False, skip_west=("B", "C"))
    # overall dims
    v.dim((-out, 72 + out), (150 + out, 72 + out), 9.0, size=TXT["small"])
    v.dim_chain([(x, 72 + out) for x in M.GRID_X.values()], 5.0, size=TXT["small"])
    v.dim((150 + out, -out), (150 + out, 72 + out), -6.0, size=TXT["small"])
    v.dim_chain([(150 + out, y) for y in sorted(M.GRID_Y.values())], -2.5, size=TXT["small"])
    ty = v.to_paper((0, -21.5))[1] - 0.1
    sh.view_title(sh.x0 + 0.4, ty, 1, "ROOF PLAN", SCALE, width=6.0)
    sh.north_arrow(sh.x0 + 8.2, ty + 0.2, 0.55)
    top = ty - 0.55
    sh.line((sh.x0, top + 0.12), (sh.x1, top + 0.12), lw="thin")
    notes = [
        "ROOFING CONTRACTOR SHALL PROVIDE MANUFACTURER'S 20-YEAR NDL SYSTEM WARRANTY. FM 1-90 WIND UPLIFT RATING.",
        "TAPERED INSULATION: 1/4\" PER FOOT TO DRAIN LINE; 1/2\" PER FOOT CRICKETS BETWEEN DRAINS. MIN. THICKNESS AT DRAINS 1 1/2\"; AVERAGE R-30 (CZ5).",
        "ROOF DRAINS, OVERFLOW DRAINS, LEADERS AND RTUs ARE FURNISHED BY DIV. 22/23 (NOT IN THIS SET). GC PROVIDES DECK OPENINGS, WOOD NAILERS, CURB BLOCKING AND FLASHING.",
        "BASE FLASHING MIN. 8\" ABOVE ROOF SURFACE, TERMINATED UNDER COPING. SEE 8/A-501.",
        "PROVIDE TREATED WOOD BLOCKING AT ALL PARAPETS (FULL PERIMETER), ROOF HATCH CURB AND RTU CURBS. SEE A-502 WOOD BLOCKING SCHEDULE.",
        "LINK ROOF: SAME ASSEMBLY, SLOPE 1/4\"/FT TO SCUPPER ON NORTH PARAPET. COUNTERFLASH INTO REGLET IN BRICK AT MAIN BUILDING (12/A-501).",
        "ROOF HATCH: 30\"x36\" GALV. STEEL, INSULATED, WITH SAFETY POST AND FIXED LADDER IN CUSTODIAL 210.",
    ]
    notes_block(sh, sh.x0 + 0.3, top, "ROOF PLAN NOTES", notes, 14.5)
    legend = [("RD / OD", "ROOF DRAIN / OVERFLOW DRAIN (DIV. 22)"), ("- - -", "TAPERED INSULATION VALLEY / CRICKET"),
              ("ARROW", "SLOPE DIRECTION (DOWN)"), ("X BOX", "MECHANICAL CURB (DIV. 23)")]
    table(sh, sh.x0 + 16.0, top, [("SYMBOL", 1.3), ("DESCRIPTION", 4.6)],
          [list(r) for r in legend], row_h=0.2, size=TXT["small"], title="ROOF LEGEND")


# ========================================================================================
# DEMOLITION PLAN (AD101)
# ========================================================================================

def clip_rect(c, x, y, w, h):
    """start a clipped region in paper inches; caller must c.restoreState()"""
    from .cad import PT as _PT
    c.saveState()
    pth = c.beginPath()
    pth.rect(x * _PT, y * _PT, w * _PT, h * _PT)
    c.clipPath(pth, stroke=0, fill=0)


EX_ROOMS = [("E-118", "CLASSROOM", (-51.0, 56.0)), ("E-117", "CLASSROOM", (-81.0, 56.0)),
            ("E-120", "CLASSROOM", (-51.0, 16.0)), ("E-121", "CLASSROOM", (-81.0, 16.0)),
            ("E-100", "CORRIDOR", (-75.0, 36.0))]


def existing_east_wing(v, enlarged=False):
    """Existing east wing near the tie-in, demolition graphics (model coords)."""
    fx = M.EXIST_FACE_X
    t = M.EXIST_WALL_T
    walls = [box(fx - t, -20, fx, 100)]
    for yy in (30.0, 42.0, 2.0, 70.0):
        walls.append(box(-130, yy - PL.CMUh, fx - t + 0.01, yy + PL.CMUh))
    for xx in (-66.0, -96.0):
        for (y0, y1) in ((2.0, 30.0), (42.0, 70.0)):
            walls.append(box(xx - PL.CMUh, y0, xx + PL.CMUh, y1))
    g = unary_union(walls)
    # existing openings: corridor end entrance (y 32..40), classroom doors, east windows (remain)
    holes = [box(fx - t - 0.1, 32.0, fx + 0.1, 40.0)]
    for xx in (-63.0, -93.0):
        holes += [box(xx, 30 - 1, xx + 3.0, 30 + 1), box(xx, 42 - 1, xx + 3.0, 42 + 1)]
    for (y0, y1) in ((9.0, 23.0), (49.0, 63.0)):
        holes.append(box(fx - t - 0.1, y0, fx + 0.1, y1))
    g = g.difference(unary_union(holes))
    v.geom(g, lw="thin", color="g60", fill="g10")
    # existing windows (remain)
    for (y0, y1) in ((9.0, 23.0), (49.0, 63.0)):
        for off in (0.35, 0.65):
            v.line((fx - t * off, y0), (fx - t * off, y1), lw="hair", color="g60")
    # existing classroom doors (remain)
    for xx in (-63.0, -93.0):
        for yy, sg in ((30.0, -1), (42.0, 1)):
            v.line((xx, yy + sg * PL.CMUh), (xx, yy + sg * (PL.CMUh + 3.0)), lw="fine", color="g60")
            v.arc((xx, yy + sg * PL.CMUh), 3.0, 0 if sg > 0 else -90, 90 if sg > 0 else 0, lw="hair",
                  color="g60")
    # --- demolition items (dashed) ---
    # wall to be removed for the enlarged opening (jambs)
    for (a, b) in ((30 + PL.CMUh, 32.0), (40.0, 42 - PL.CMUh)):
        v.rect(fx - t, a, t, b - a, lw="thin", dash="demo", hatch="ansi37", hatch_kw=dict(spacing=0.03))
    # existing aluminum entrance (pair + sidelites) to be removed
    v.rect(fx - t * 0.7, 32.0, t * 0.4, 8.0, lw="thin", dash="demo")
    for yy in (34.0, 38.0):
        v.line((fx - t * 0.5, yy), (fx + 2.6, yy + (1.4 if yy < 36 else -1.4)), lw="fine", dash="demo")
    # stoop + walk to remove (site)
    v.rect(fx, 31.0, 6.0, 10.0, lw="thin", dash="demo", hatch="ansi37", hatch_kw=dict(spacing=0.06, col="g50"))
    v.polygon([(fx + 6.0, 33.5), (fx + 34.0, 33.5), (fx + 34.0, 38.5), (fx + 6.0, 38.5)], lw="thin",
              dash="demo", hatch="ansi37", hatch_kw=dict(spacing=0.06, col="g50"))
    # canopy above (dashed) to remove
    v.rect(fx, 30.5, 5.0, 11.0, lw="fine", dash="hidden")
    # downspout + wall packs
    v.rect(fx, 44.0, 0.6, 0.6, lw="thin", dash="demo")
    for yy in (28.5, 43.5):
        v.circle((fx + 0.4, yy), 0.4, lw="fine", dash="demo")
    # ceiling removal limit (12 ft back)
    v.rect(fx - t - 12.0, 30 + PL.CMUh, 12.0, 12 - 2 * PL.CMUh, lw="fine", dash="phantom")
    # temporary partition
    v.line((fx - t - 13.0, 30 + PL.CMUh), (fx - t - 13.0, 42 - PL.CMUh), lw="heavy", dash=[5, 1.5, 1, 1.5])
    # new work (reference) dashed
    v.line((0.0, -10.0), (0.0, 90.0), lw="fine", dash="hidden")
    for yy in (30.0, 42.0):
        v.line((fx, yy), (0.0, yy), lw="fine", dash="hidden")
    for num, name, at in EX_ROOMS:
        room_tag(v, at, name, num, size=TXT["label"])


def demo_sheet(sh):
    fx = M.EXIST_FACE_X
    # ---------------- view 1: demolition plan at 1/8" ----------------
    s1 = 1 / 8
    X0, Y0, W1, H1 = sh.x0 + 0.3, sh.y0 + 7.4, 13.6, 15.4
    v = sh.view(X0 + (110.0) * s1, Y0 + 1.2 + 14.0 * s1, s1)
    clip_rect(sh.c, X0, Y0 + 0.9, W1, H1 - 0.9)
    existing_east_wing(v)
    sh.c.restoreState()
    from .cad import break_line
    v.text((-18.0, 77.0), "NEW ADDITION AND LINK SHOWN DASHED", size=TXT["tiny"], anchor="c")
    v.text((-18.0, 75.4), "FOR REFERENCE (SEE A-101)", size=TXT["tiny"], anchor="c")
    v.mtext((-80.0, 86.0), "EXISTING 1-STORY SCHOOL (OCCUPIED)", size=TXT["note"], font=FONT_B,
            anchor="c", valign="mid", color="g50")
    kn = [((-26.0, 49.0), 1, (fx + 3.0, 39.0)), ((-46.0, 46.0), 2, (fx - 0.6, 38.0)),
          ((-30.0, 24.0), 3, (fx + 0.5, 30.6)), ((-48.0, 26.5), 4, (fx - 0.5, 31.0)),
          ((-26.0, 56.0), 5, (fx + 0.4, 43.5)), ((-30.0, 44.0), 6, (fx + 0.3, 44.3)),
          ((-56.0, 40.0), 7, (fx - 7.0, 39.5)), ((-14.0, 46.5), 8, (-8.0, 36.0)),
          ((-26.0, 66.0), 9, (fx - 0.5, 60.0)), ((-58.0, 33.0), 10, (fx - 14.0, 33.0))]
    for at, n, to in kn:
        keynote_tag(v, at, n, size=TXT["small"], leader_to=to)
    grid_bubble(v, (0.0, 92.5), "1", 0.42)
    sh.view_title(X0 + 0.1, Y0 + 0.55, 1, "DEMOLITION PLAN - EXISTING EAST WING", s1, width=6.2)
    sh.north_arrow(X0 + 9.6, Y0 + 0.75, 0.5)

    # ---------------- view 2: enlarged tie-in plan at 1/4" ----------------
    s2 = 1 / 4
    X2, Y2 = sh.x0 + 14.6, sh.y0 + 7.4
    v2 = sh.view(X2 + 4.1 + 35.0 * s2, Y2 + 4.6 - 36.0 * s2, s2)
    clip_rect(sh.c, X2, Y2 + 0.9, 8.2, 7.2)
    existing_east_wing(v2, enlarged=True)
    sh.c.restoreState()
    v2.dim((fx + 0.0, 30 + PL.CMUh), (fx + 0.0, 42 - PL.CMUh), -4.5, size=TXT["small"],
           text=fmt_ftin(12 - 2 * PL.CMUh) + " NEW CLEAR OPENING")
    v2.dim((fx - 1.0, 32.0), (fx - 1.0, 40.0), 3.0, size=TXT["small"], text="8'-0\" EXIST. ENTRANCE")
    v2.dim((fx - 13.0 - 1.0, 44.5), (fx - 1.0, 44.5), 0.0, size=TXT["small"])
    v2.text((fx - 7.0, 46.2), "CEILING REMOVAL LIMIT", size=TXT["tiny"], anchor="c")
    v2.leader([(fx - 14.0, 35.0), (fx - 18.0, 27.5)], "TEMP. PARTITION (NOTE 2)", size=TXT["tiny"])
    sh.view_title(X2 + 0.1, Y2 + 0.55, 2, "ENLARGED DEMOLITION PLAN AT TIE-IN", s2, width=5.4)

    # ---------------- view 3: existing east elevation (1/4") ----------------
    X3, Y3 = sh.x0 + 23.2, sh.y1 - 7.2
    ya, yb = 24.0, 48.0
    ve = sh.view(X3 + 1.6, Y3 + 1.4, s2, mx=ya, my=99.0)
    ve.rect(ya, 99.0, yb - ya, M.LEVELS["EXIST_ROOF"] - 99.0, lw="thin", color="g60",
            hatch="tile", hatch_kw=dict(spacing=(1000.0, 8 / 12.0), w="hair", col="g70"))
    ve.line((ya - 1.0, 99.0), (yb + 1.0, 99.0), lw="med")
    ve.rect(ya, M.LEVELS["EXIST_ROOF"], yb - ya, 0.67, lw="thin", color="g60", fill="g20")
    for (y0, y1) in ((9.0, 23.0), (49.0, 63.0)):
        y0, y1 = max(y0, ya), min(y1, yb)
        if y1 - y0 > 0.5:
            ve.rect(y0, 102.67, y1 - y0, 6.0, lw="fine", color="g60", fill="white")
    from .cad import break_line
    break_line(ve, (ya, 98.5), (ya, M.LEVELS["EXIST_ROOF"] + 1.0), zig=0.08)
    break_line(ve, (yb, 98.5), (yb, M.LEVELS["EXIST_ROOF"] + 1.0), zig=0.08)
    ve.rect(32.0, 100.0, 8.0, 9.0, lw="thin", dash="demo", fill="white")
    for k in (34.0, 36.0, 38.0):
        ve.line((k, 100.0), (k, 107.0), lw="fine", dash="demo")
    ve.line((32.0, 107.0), (40.0, 107.0), lw="fine", dash="demo")
    ve.rect(30.5, 109.0, 11.0, 1.0, lw="fine", dash="demo")
    ve.rect(30 + PL.CMUh, 100.0, 12 - 2 * PL.CMUh, 10.0, lw="med", dash="phantom")
    ve.leader([(41.0, 109.7), (43.0, 115.4)], "NEW OPENING W/ STEEL LINTEL (S-302)", size=TXT["tiny"],
              text_side="l")
    ve.leader([(33.0, 104.0), (28.5, 106.0)], "REMOVE EXIST. ENTRANCE", size=TXT["tiny"])
    ve.leader([(31.0, 109.5), (28.5, 111.5)], "REMOVE CANOPY", size=TXT["tiny"])
    from .cad import level_marker
    level_marker(ve, ya - 0.8, 100.0, "EXIST. FFE", side="l", value_text="100'-0\"")
    level_marker(ve, ya - 0.8, M.LEVELS["EXIST_ROOF"], "EXIST. ROOF", side="l")
    for yy, lab in ((30.0, "C"), (42.0, "B")):
        ve.line((yy, 99.0), (yy, 116.5), lw="hair", dash="grid")
        grid_bubble(ve, (yy, 117.4), lab, 0.36)
    sh.view_title(X3 + 0.1, Y3 + 0.55, 3, "EXISTING EAST ELEVATION - DEMOLITION", s2, width=5.0)
    seq = [
        "##BEFORE SUMMER RECESS (SCHOOL IN SESSION)",
        "COMPLETE LINK FOUNDATIONS, STEEL AND ROOF UP TO THE EXISTING WALL WITHOUT PENETRATING IT.",
        "INSTALL LINK STOREFRONT SF-3 AND ROOF; LINK MUST BE WEATHER-TIGHT BEFORE JUNE 7, 2027.",
        "##SUMMER RECESS (JUNE 7 - AUGUST 13, 2027)",
        "ERECT TEMPORARY PARTITION (KEYNOTE 10) INSIDE EXISTING CORRIDOR E-100.",
        "SHORE WALL, INSTALL NEW LINTEL, SAWCUT AND REMOVE MASONRY (KEYNOTE 4).",
        "REMOVE EXISTING ENTRANCE, CANOPY, STOOP AND WALK (KEYNOTES 1, 2, 8).",
        "INSTALL CROSS-CORRIDOR PAIR 100A AND FINISHES; PATCH EXISTING CEILING AND FLOOR.",
        "REMOVE TEMPORARY PARTITION; OWNER WALK-THROUGH BEFORE AUGUST 6, 2027.",
    ]
    notes_block(sh, X3, Y3 - 0.4, "TIE-IN SEQUENCE (REQUIRED)", seq, 8.0)

    # ---------------- bottom: notes, keynotes, legend ----------------
    top = sh.y0 + 6.9
    sh.line((sh.x0, top + 0.15), (sh.x1, top + 0.15), lw="thin")
    sh.line((sh.x0 + 14.3, top + 0.15), (sh.x0 + 14.3, sh.y1), lw="fine")
    sh.line((sh.x0 + 22.95, top + 0.15), (sh.x0 + 22.95, sh.y1), lw="fine")
    gn = [
        "TIE-IN DEMOLITION AT THE EXISTING BUILDING SHALL OCCUR ONLY DURING SUMMER RECESS (JUNE 7 TO AUGUST 13, 2027). THE EXISTING BUILDING REMAINS OCCUPIED DURING THE SCHOOL YEAR.",
        "BEFORE BREAKING THROUGH, ERECT A TEMPORARY WEATHER-TIGHT, INSULATED, LOCKABLE PARTITION (2x4 STUDS @ 16\", 1/2\" PLYWOOD BOTH SIDES, 6-MIL POLY, 3'-0\" DOOR) IN EXISTING CORRIDOR E-100 AS SHOWN, UNTIL THE LINK IS ENCLOSED.",
        "MAINTAIN EXITING FROM EXISTING CORRIDOR E-100 AT ALL TIMES. PROVIDE TEMPORARY EXIT SIGNAGE AND A PROTECTED PATH AS APPROVED BY THE AUTHORITY HAVING JURISDICTION.",
        "HAZARDOUS MATERIALS: OWNER'S AHERA SURVEY FOUND NO ACM IN THE AREAS OF WORK. STOP WORK AND NOTIFY OWNER IF SUSPECT MATERIALS ARE ENCOUNTERED.",
        "FIELD-VERIFY EXISTING CONDITIONS, INCLUDING EXISTING FOUNDATION DEPTH AT THE LINK, PRIOR TO BID. REPORT DISCREPANCIES TO THE ARCHITECT.",
        "PATCH AND REPAIR ALL SURFACES DAMAGED BY DEMOLITION TO MATCH ADJACENT (BRICK TOOTHING, VCT INFILL, ACT, PAINT FULL WALL PLANES).",
        "REMOVED MATERIALS BECOME THE CONTRACTOR'S PROPERTY UNLESS NOTED; REMOVE FROM SITE DAILY. RECYCLE MINIMUM 50% BY WEIGHT.",
        "COORDINATE SHUTDOWNS OF FIRE ALARM, SPRINKLER AND SECURITY SYSTEMS WITH THE OWNER 72 HOURS IN ADVANCE (DIV. 21/26/28 WORK IS NOT IN THIS SET).",
        "SITE DEMOLITION (WALKS, TREES, UTILITIES) IS SHOWN ON C-100.",
    ]
    notes_block(sh, sh.x0 + 0.3, top, "GENERAL DEMOLITION NOTES", gn, 13.6)
    kx = sh.x0 + 14.6
    sh.text((kx, top), "DEMOLITION KEYNOTES", size=TXT["label"], font=FONT_B, valign="top", underline=True)
    notes = {
        1: "REMOVE EXISTING CONCRETE STOOP AND WALK TO MAPLE STREET IN THEIR ENTIRETY (SEE C-100).",
        2: "REMOVE EXISTING ALUMINUM ENTRANCE: PAIR OF DOORS, SIDELITES, TRANSOM, FRAME AND HARDWARE. TURN OVER KEYED CYLINDERS TO THE OWNER.",
        3: "REMOVE EXISTING WALL-PACK LIGHTS; RELOCATE PER DIV. 26 (NOT IN THIS SET).",
        4: "SAWCUT AND REMOVE EXISTING BRICK/CMU WALL TO ENLARGE OPENING TO 11'-4 3/8\" x 10'-0\". INSTALL NEW STEEL LINTEL WITH TEMPORARY SHORING BEFORE REMOVAL (S-302). TOOTH-IN MASONRY AT NEW JAMBS.",
        5: "REMOVE AND SALVAGE EXISTING DOWNSPOUT; CONNECT NEW DOWNSPOUT TO STORM (C-400).",
        6: "PROTECT EXISTING BRICK TO REMAIN; CLEAN AND REPOINT WITHIN 4'-0\" OF NEW WORK.",
        7: "REMOVE EXISTING ACT CEILING AND GRID 12'-0\" BACK FROM EXTERIOR WALL; REINSTALL NEW ACT-1 TO MATCH AFTER LINTEL WORK.",
        8: "REMOVE EXISTING STEEL CANOPY AND METAL FASCIA ABOVE THE ENTRANCE; PATCH BRICK AT ANCHORS.",
        9: "EXISTING CLASSROOM WINDOWS TO REMAIN. PROTECT WITH PLYWOOD DURING ADJACENT WORK.",
        10: "TEMPORARY SECURITY / WEATHER PARTITION (SEE GENERAL NOTE 2). REMOVE AT LINK ENCLOSURE.",
    }
    yy = top - 0.28
    for k, t in notes.items():
        vv = sh.view(kx + 0.12, yy - 0.06, 1 / 8)
        keynote_tag(vv, (0, 0), k)
        hgt = sh.mtext((kx + 0.32, yy), t, size=TXT["note"], width=9.0)
        yy -= max(0.24, hgt + 0.07)
    lx, ly = sh.x0 + 25.0, top
    sh.text((lx, ly), "DEMOLITION LEGEND", size=TXT["label"], font=FONT_B, valign="top", underline=True)
    rows = [("g10", "EXISTING TO REMAIN"), ("demo", "EXISTING TO BE REMOVED"),
            ("phantom", "LIMIT OF CEILING REMOVAL"), ("temp", "TEMPORARY PARTITION"),
            ("hidden", "NEW WORK (REFERENCE ONLY)")]
    yy = ly - 0.32
    for kind, label in rows:
        vv = sh.view(lx, yy - 0.08, 1 / 8)
        if kind == "g10":
            vv.rect(0, 0, 4.0, 1.2, lw="thin", color="g60", fill="g10")
        elif kind == "demo":
            vv.rect(0, 0, 4.0, 1.2, lw="thin", dash="demo", hatch="ansi37", hatch_kw=dict(spacing=0.03))
        elif kind == "temp":
            vv.line((0, 0.6), (4.0, 0.6), lw="heavy", dash=[5, 1.5, 1, 1.5])
        else:
            vv.line((0, 0.6), (4.0, 0.6), lw="thin", dash=kind)
        sh.text((lx + 0.7, yy), label, size=TXT["small"], valign="mid")
        yy -= 0.26


# ----------------------------------------------------------------------------------------
SHEETS = [
    ("AD101", "DEMOLITION PLAN\nAT EXISTING BUILDING TIE-IN", demo_sheet),
    ("A-101", "FIRST FLOOR PLAN", floor_plan_sheet("L1")),
    ("A-102", "SECOND FLOOR PLAN", floor_plan_sheet("L2")),
    ("A-103", "ROOF PLAN", roof_plan_sheet),
    ("A-111", "FIRST FLOOR\nFINISH PLAN", finish_plan_sheet("L1")),
    ("A-112", "SECOND FLOOR\nFINISH PLAN", finish_plan_sheet("L2")),
    ("A-121", "FIRST FLOOR REFLECTED\nCEILING PLAN", rcp_sheet("L1")),
    ("A-122", "SECOND FLOOR REFLECTED\nCEILING PLAN", rcp_sheet("L2")),
]
