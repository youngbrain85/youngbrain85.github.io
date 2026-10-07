"""
Plan renderer shared by floor plans, finish plans, RCPs, life safety and demolition plans.
"""
from __future__ import annotations

import math

from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from . import model as M
from .cad import (FONT, FONT_B, TXT, Paper, View, break_line, door_tag, elevation_mark,
                  fmt_ftin, grid_bubble, room_tag, section_mark, wall_tag, window_tag)

IN = M.IN

# ----------------------------------------------------------------------------------------
# Wall geometry
# ----------------------------------------------------------------------------------------

def _cut_openings(level, kinds=("door", "window", "storefront", "elevator")):
    """Openings that are cut by the plan cut plane at this level."""
    out = []
    cut = M.LEVELS[level] + M.CEILING_CUT
    for o in M.openings_on(level):
        if o.kind not in kinds:
            continue
        if o.kind in ("door", "elevator"):
            if o.level == level:
                out.append(o)
        elif o.sill < cut < o.head:
            out.append(o)
    return out


def _opening_box(o, extra=0.02):
    ax = M.opening_axis(o)
    k = M.opening_line_coord(o)
    if o.wall in M.EXT_SEGS:
        out = M.seg_outward(o.wall)
        s = out[1] if ax == "x" else out[0]
        a, b = k - s * (M.EW_IN + extra), k + s * (M.EW_OUT + extra)
        lo_, hi_ = min(a, b), max(a, b)
    else:
        t = M.WALL_TYPES[M.WALL_BY_ID[o.wall].type]["thk"]
        lo_, hi_ = k - t / 2 - extra, k + t / 2 + extra
    if o.frame == "SF" or o.kind == "door" and o.wall == "E" and o.id == "100B":
        pass
    if ax == "x":
        return box(o.lo, lo_, o.hi, hi_)
    return box(lo_, o.lo, hi_, o.hi)


def wall_geoms(level, openings=True):
    """Return dict of shapely geometries per material for the given level."""
    g = {}
    cmu_parts = [M.ext_layer(level, *M.EW_LAYERS[0][1:])]
    cmu_parts += [w.poly() for w in M.interior_walls(level) if M.WALL_TYPES[w.type]["mat"] == "cmu"]
    g["cmu"] = unary_union(cmu_parts)
    g["insul"] = M.ext_layer(level, *M.EW_LAYERS[1][1:])
    g["air"] = M.ext_layer(level, *M.EW_LAYERS[2][1:])
    g["brick"] = M.ext_layer(level, *M.EW_LAYERS[3][1:])
    studs = [w.poly() for w in M.interior_walls(level) if M.WALL_TYPES[w.type]["mat"] == "stud"]
    g["stud"] = unary_union(studs) if studs else None
    if g["stud"] is not None:
        g["cmu"] = g["cmu"].difference(g["stud"].buffer(-0.001))
    if openings:
        holes = unary_union([_opening_box(o) for o in _cut_openings(level)])
        for k in list(g):
            if g[k] is not None:
                g[k] = g[k].difference(holes)
    return g


def draw_walls(v: View, level, style="normal", openings=True):
    """style: normal (poché + hatch) | light (outlined, light fill) | rcp"""
    g = wall_geoms(level, openings)
    if style == "normal":
        v.geom(g["cmu"], lw="heavy", fill="white", hatch="ansi31",
               hatch_kw=dict(spacing=0.045, w="hair"))
        v.geom(g["brick"], lw="heavy", fill="white", hatch="brick",
               hatch_kw=dict(spacing=0.022, w="hair"))
        v.geom(g["insul"], lw="fine", fill="g15")
        v.geom(g["air"], lw=None, fill="white", stroke=False)
        if g["stud"] is not None:
            v.geom(g["stud"], lw="heavy", fill="g20")
    elif style == "light":
        for k in ("cmu", "brick", "insul"):
            v.geom(g[k], lw="thin", fill="g30" if k != "insul" else "g15")
        if g["stud"] is not None:
            v.geom(g["stud"], lw="thin", fill="g20")
    elif style == "rcp":
        for k in ("cmu", "brick"):
            v.geom(g[k], lw="med", fill="g40")
        v.geom(g["insul"], lw="fine", fill="g20")
        if g["stud"] is not None:
            v.geom(g["stud"], lw="med", fill="g30")
    return g


# ----------------------------------------------------------------------------------------
# Existing building fragment (west of the link)
# ----------------------------------------------------------------------------------------
EX_X0 = -64.0  # crop line


def draw_existing(v: View, level, mode="new", y_range=(-8, 80)):
    """Existing building fragment near the link. mode: new | demo"""
    if level != "L1":
        # level 2: show existing roof as screened outline only
        y0, y1 = y_range
        v.line((M.EXIST_FACE_X, y0), (M.EXIST_FACE_X, y1), lw="thin", color="screen")
        v.text((M.EXIST_FACE_X - 12, 52), "EXISTING ROOF", size=TXT["note"], anchor="c",
               color="screen")
        v.text((M.EXIST_FACE_X - 18, 36), "LINK ROOF BELOW", size=TXT["note"], anchor="c")
        return
    y0, y1 = y_range
    fx = M.EXIST_FACE_X
    ex = []
    # existing exterior wall (brick + CMU 12")
    ex.append(box(fx - M.EXIST_WALL_T, y0, fx, y1))
    # existing corridor walls and classroom demising walls
    for yy in (30, 42):
        ex.append(box(EX_X0, yy - CMUh, fx - 0.5, yy + CMUh))
    for yy in (2.0, 70.0):
        ex.append(box(EX_X0, yy - CMUh, fx - 0.5, yy + CMUh))
    exg = unary_union(ex)
    if mode == "new":
        exg = exg.difference(box(fx - 2, 30 + CMUh, fx + 0.1, 42 - CMUh))
    else:
        # existing opening: pair of doors + sidelites y 32..40
        exg = exg.difference(box(fx - 2, 32, fx + 0.1, 40))
    v.geom(exg, lw="thin", color="screen", fill="g10")
    # crop break lines
    break_line(v, (EX_X0, y0), (EX_X0, y1), zig=0.12)
    v.line((EX_X0, y0), (fx - 1, y0), lw="fine", color="screen")
    v.line((EX_X0, y1), (fx - 1, y1), lw="fine", color="screen")
    lab = "EXISTING BUILDING\n(NO WORK)" if mode == "new" else "EXISTING BUILDING\n(OCCUPIED)"
    v.mtext((EX_X0 + 13, 56), lab, size=TXT["note"], font=FONT_B, anchor="c", valign="mid",
            color="screen")
    v.mtext((EX_X0 + 13, 16), "EXISTING\nCLASSROOM", size=TXT["note"], anchor="c", valign="mid",
            color="screen")
    v.mtext((EX_X0 + 12, 36), "EXISTING CORRIDOR", size=TXT["note"], anchor="c", valign="mid",
            color="screen")
    if mode == "demo":
        # doors to be removed
        for yy, s in ((32.0, 1), (40.0, -1)):
            v.line((fx - 0.5, yy), (fx - 0.5 + 3.0, yy + s * 0.0), lw="thin", dash="demo")
        v.rect(fx - 1.0, 32, 1.0, 8, lw="thin", dash="demo")
        # wall to be removed (enlarge opening)
        for a, b in ((30 + CMUh, 32), (40, 42 - CMUh)):
            v.rect(fx - 1.0, a, 1.0, b - a, lw="thin", dash="demo", hatch="ansi37",
                   hatch_kw=dict(spacing=0.03))


CMUh = M.CMU_T / 2


# ----------------------------------------------------------------------------------------
# Openings
# ----------------------------------------------------------------------------------------

def _frame(o):
    """(axis, k, inner_face, outer_face, s_out) where faces are absolute coords across the wall"""
    ax = M.opening_axis(o)
    k = M.opening_line_coord(o)
    if o.wall in M.EXT_SEGS:
        out = M.seg_outward(o.wall)
        s = out[1] if ax == "x" else out[0]
        return ax, k, k - s * M.EW_IN, k + s * M.EW_OUT, s
    t = M.WALL_TYPES[M.WALL_BY_ID[o.wall].type]["thk"]
    return ax, k, k - t / 2, k + t / 2, 1


def _pt(ax, along, across):
    return (along, across) if ax == "x" else (across, along)


def draw_door(v: View, o, show_swing=True, lw_leaf="med"):
    ax, k, f_in, f_out, s_out = _frame(o)
    sw = 1 if o.swing == "+" else -1
    # face on the swing side
    if o.wall in M.EXT_SEGS:
        face = f_out if sw == s_out else f_in
    else:
        face = k + sw * M.WALL_TYPES[M.WALL_BY_ID[o.wall].type]["thk"] / 2
    other = k - (face - k)  # opposite face
    jamb = 2 * IN
    leafs = []
    if o.pair:
        if o.frame == "SF":
            a0 = o.c - o.w / 2
            leafs = [(a0, +1), (o.c + o.w / 2, -1)]
        else:
            leafs = [(o.lo + jamb, +1), (o.hi - jamb, -1)]
    else:
        if o.frame == "F2":
            if o.side == "hi":
                d0 = o.lo + jamb
            else:
                d0 = o.hi - jamb - o.leaf
            pivot = d0 if o.hinge == "lo" else d0 + o.leaf
            leafs = [(pivot, +1 if o.hinge == "lo" else -1)]
        else:
            leafs = [(o.lo + jamb, +1) if o.hinge == "lo" else (o.hi - jamb, -1)]
    L = o.leaf
    for piv, dirn in leafs:
        P0 = _pt(ax, piv, face)
        P1 = _pt(ax, piv, face + sw * L)
        v.line(P0, P1, lw=lw_leaf)
        if show_swing:
            # arc from open leaf to closed position
            c = P0
            if ax == "x":
                a_open = 90 if sw > 0 else -90
                a_closed = 0 if dirn > 0 else 180
            else:
                a_open = 0 if sw > 0 else 180
                a_closed = 90 if dirn > 0 else -90
            a0, a1 = sorted([a_open, a_closed])
            if a1 - a0 > 180:
                a0, a1 = a1, a0 + 360
            v.arc(c, L, a0, a1, lw="hair")
    # frame jambs
    for a in (o.lo, o.hi):
        v.line(_pt(ax, a, f_in), _pt(ax, a, f_out), lw="thin")
    # sidelight glazing
    if o.frame == "F2":
        if o.side == "hi":
            g0, g1 = o.lo + jamb + o.leaf + jamb, o.hi - jamb
        else:
            g0, g1 = o.lo + jamb, o.hi - jamb - o.leaf - jamb
        mid = k
        v.line(_pt(ax, g0, mid - 0.06), _pt(ax, g1, mid - 0.06), lw="fine")
        v.line(_pt(ax, g0, mid + 0.06), _pt(ax, g1, mid + 0.06), lw="fine")
        v.line(_pt(ax, g0, mid), _pt(ax, g1, mid), lw="hair")
        v.line(_pt(ax, g0 - jamb / 2, f_in), _pt(ax, g0 - jamb / 2, f_out), lw="fine")
    # threshold line for exterior doors
    if o.wall in M.EXT_SEGS and o.frame != "SF":
        v.line(_pt(ax, o.lo, f_out), _pt(ax, o.hi, f_out), lw="fine")


def draw_window(v: View, o, level, dashed=False):
    ax, k, f_in, f_out, s_out = _frame(o)
    dash = "hidden" if dashed else None
    a, b = o.lo, o.hi
    # frame zone (in the insulation line)
    fr0 = k + s_out * (1.0 * IN)
    fr1 = k + s_out * (5.5 * IN)
    gl = (fr0 + fr1) / 2
    if not dashed:
        v.line(_pt(ax, a, f_in), _pt(ax, a, f_out), lw="thin")
        v.line(_pt(ax, b, f_in), _pt(ax, b, f_out), lw="thin")
    v.line(_pt(ax, a, fr0), _pt(ax, b, fr0), lw="fine", dash=dash)
    v.line(_pt(ax, a, fr1), _pt(ax, b, fr1), lw="fine", dash=dash)
    v.line(_pt(ax, a, gl), _pt(ax, b, gl), lw="hair", dash=dash)
    if o.kind == "louver":
        n = 6
        for i in range(1, n):
            t = a + (b - a) * i / n
            v.line(_pt(ax, t, fr0), _pt(ax, t + 0.25, fr1), lw="hair", dash=dash)
        return
    if dashed:
        return
    # interior stool / sill line and exterior sill
    v.line(_pt(ax, a, f_in - s_out * 0.5 * IN), _pt(ax, b, f_in - s_out * 0.5 * IN), lw="hair")
    if o.type in ("W-A", "W-B", "SF-2"):
        ext = f_out + s_out * 1.0 * IN
        v.polyline([_pt(ax, a - 0.25, f_out), _pt(ax, a - 0.25, ext), _pt(ax, b + 0.25, ext),
                    _pt(ax, b + 0.25, f_out)], lw="fine")
    # mullions
    mulls = []
    if o.type == "SF-3":
        n = 6
        mulls = [a + (b - a) * i / n for i in range(0, n + 1)]
    elif o.type == "SF-2":
        mulls = [a + (b - a) * i / 3 for i in range(0, 4)]
    elif o.type == "W-A":
        mulls = [a, (a + b) / 2, b]
    elif o.type == "SF-1":
        mulls = [a, o.c - 3.0 - 1 * IN, o.c + 3.0 + 1 * IN, b]
    else:
        mulls = [a, b]
    for m in mulls:
        q0 = _pt(ax, m - 1 * IN, fr0)
        q1 = _pt(ax, m + 1 * IN, fr1)
        v.rect(min(q0[0], q1[0]), min(q0[1], q1[1]), abs(q1[0] - q0[0]), abs(q1[1] - q0[1]),
               lw="hair", fill="black")


def draw_openings(v: View, level, swing=True, tags=True):
    cut = M.LEVELS[level] + M.CEILING_CUT
    for o in M.openings_on(level):
        if o.kind == "door":
            if o.level == level:
                draw_door(v, o, show_swing=swing)
        elif o.kind == "elevator":
            if o.level == level:
                ax, k, f_in, f_out, s = _frame(o)
                v.line(_pt(ax, o.lo, f_in), _pt(ax, o.lo, f_out), lw="thin")
                v.line(_pt(ax, o.hi, f_in), _pt(ax, o.hi, f_out), lw="thin")
                v.line(_pt(ax, o.c - 1.75, k - 0.1), _pt(ax, o.c + 1.75, k - 0.1), lw="med")
        else:
            if o.sill < cut < o.head:
                draw_window(v, o, level)
    # openings above the cut plane (louvers, high windows) dashed
    for o in M.OPENINGS:
        if o.kind in ("window", "louver", "storefront") and o.wall in M.EXT_SEGS \
                and level in M.SEG_LEVELS[o.wall]:
            base = M.LEVELS[level]
            if cut < o.sill < base + 12.0:
                draw_window(v, o, level, dashed=True)


# ----------------------------------------------------------------------------------------
# Stairs & elevator
# ----------------------------------------------------------------------------------------
RISER = 7 * IN
TREAD = 11 * IN
N_TREADS = 11


def stair_geom(name):
    """inside box and flight layout for the two stairs"""
    if name == "ST-1":
        x0, x1 = 0 + CMUh, 12 - CMUh
        y0, y1 = 0 + CMUh, 30 - CMUh
        fw = (x1 - x0 - 1.0) / 2
        land = 5.5
        f_lo, f_hi = y0 + land, y0 + land + N_TREADS * TREAD
        return dict(x0=x0, x1=x1, y0=y0, y1=y1, fw=fw, mid_land=(y0, f_lo), floor_land=(f_hi, y1),
                    up=(x1 - fw, x1), up2=(x0, x0 + fw), f_lo=f_lo, f_hi=f_hi, dir_up=-1)
    x0, x1 = 138 + CMUh, 150 - CMUh
    y0, y1 = 42 + CMUh, 72 - CMUh
    fw = (x1 - x0 - 1.0) / 2
    land = 5.5
    f_hi = y1 - land
    f_lo = f_hi - N_TREADS * TREAD
    return dict(x0=x0, x1=x1, y0=y0, y1=y1, fw=fw, mid_land=(f_hi, y1), floor_land=(y0, f_lo),
                up=(x0, x0 + fw), up2=(x1 - fw, x1), f_lo=f_lo, f_hi=f_hi, dir_up=+1)


def draw_stair(v: View, name, level):
    g = stair_geom(name)
    f_lo, f_hi = g["f_lo"], g["f_hi"]
    risers = [f_lo + i * TREAD for i in range(N_TREADS + 1)]
    up = g["up"]
    up2 = g["up2"]
    if level == "L1":
        # first flight: cut at about 4'-0" (7 risers), rest dashed
        start = f_hi if g["dir_up"] < 0 else f_lo
        order = sorted(risers, key=lambda y: abs(y - start))
        ncut = 7
        for i, yy in enumerate(order):
            v.line((up[0], yy), (up[1], yy), lw="thin" if i < ncut else "hair",
                   dash=None if i < ncut else "hidden")
        ybrk_a = order[ncut - 1] + g["dir_up"] * 0.3
        v.line((up[0] - 0.2, ybrk_a + g["dir_up"] * 1.2), (up[1] + 0.2, ybrk_a - g["dir_up"] * 0.6),
               lw="thin")
        # stringers / handrails
        for xx in up:
            v.line((xx, f_lo), (xx, f_hi), lw="fine")
        # second flight (above) dashed
        for yy in risers:
            v.line((up2[0], yy), (up2[1], yy), lw="hair", dash="hidden")
        v.line((up2[1], f_lo), (up2[1], f_hi), lw="hair", dash="hidden")
        # arrow
        xm = (up[0] + up[1]) / 2
        a, b = (start + g["dir_up"] * 0.6, start + g["dir_up"] * (N_TREADS * TREAD - 0.8))
        v.line((xm, a), (xm, b), lw="fine")
        v._arrowhead((xm, b), (0, g["dir_up"]), size_in=0.08)
        v.text((xm + 0.4, a + g["dir_up"] * 1.5), "UP 24R", size=TXT["small"], anchor="l",
               valign="mid", rot=90)
    else:
        for yy in risers:
            v.line((up[0], yy), (up[1], yy), lw="thin")
            v.line((up2[0], yy), (up2[1], yy), lw="thin")
        for xx in (up[0], up[1], up2[0], up2[1]):
            v.line((xx, f_lo), (xx, f_hi), lw="fine")
        # guard at floor landing edge above the lower flight
        edge = f_hi if g["dir_up"] < 0 else f_lo
        v.line((up[0], edge), (up[1], edge), lw="med")
        xm = (up2[0] + up2[1]) / 2
        start = f_hi if g["dir_up"] < 0 else f_lo
        a, b = (start + g["dir_up"] * 0.6, start + g["dir_up"] * (N_TREADS * TREAD - 0.8))
        v.line((xm, a), (xm, b), lw="fine")
        v._arrowhead((xm, b), (0, g["dir_up"]), size_in=0.08)
        v.text((xm + 0.4, a + g["dir_up"] * 1.5), "DN 24R", size=TXT["small"], anchor="l",
               valign="mid", rot=90)
    # well rail
    xw0, xw1 = min(up[0], up2[0]) + g["fw"], max(up[0], up2[0])
    v.line((xw0 + 0.15, f_lo), (xw0 + 0.15, f_hi), lw="fine")
    v.line((xw1 - 0.15, f_lo), (xw1 - 0.15, f_hi), lw="fine")


def draw_elevator(v: View, level):
    x0, x1 = 21 + CMUh, 30 - CMUh
    y0, y1 = 21 + CMUh, 30 - CMUh
    # car 6'-8" x 5'-5" toward the door
    cw, cd = 6 + 8 * IN, 5 + 5 * IN
    cx = (x0 + x1) / 2
    v.rect(cx - cw / 2, y1 - 0.45 - cd, cw, cd, lw="thin")
    v.line((cx - cw / 2, y1 - 0.45 - cd), (cx + cw / 2, y1 - 0.45), lw="hair")
    v.line((cx - cw / 2, y1 - 0.45), (cx + cw / 2, y1 - 0.45 - cd), lw="hair")
    for xx in (x0 + 0.05, x1 - 0.35):
        v.rect(xx, y1 - 0.45 - cd / 2 - 0.25, 0.3, 0.5, lw="hair", fill="g50")


# ----------------------------------------------------------------------------------------
# Fixtures, toilet partitions, casework (simplified for 1/8" plans)
# ----------------------------------------------------------------------------------------

def _wc(v, x, y, facing, scale=1.0):
    """water closet: tank against wall at (x,y), facing = unit vector into room"""
    fx, fy = facing
    px, py = -fy, fx
    tw, td = 1.6, 0.6
    L = 2.2
    c = [(x + px * tw / 2, y + py * tw / 2), (x - px * tw / 2, y - py * tw / 2),
         (x - px * tw / 2 + fx * td, y - py * tw / 2 + fy * td),
         (x + px * tw / 2 + fx * td, y + py * tw / 2 + fy * td)]
    v.polygon(c, lw="fine")
    cx, cy = x + fx * (td + 0.85), y + fy * (td + 0.85)
    pts = []
    for i in range(0, 361, 20):
        a = math.radians(i)
        ex, ey = 0.85 * math.cos(a), 0.6 * math.sin(a)
        pts.append((cx + fx * ex + px * ey, cy + fy * ex + py * ey))
    v.polyline(pts, lw="fine")


def _lav(v, x, y, facing):
    fx, fy = facing
    px, py = -fy, fx
    w, d = 1.75, 1.4
    pts = [(x + px * w / 2, y + py * w / 2), (x - px * w / 2, y - py * w / 2),
           (x - px * w / 2 + fx * d, y - py * w / 2 + fy * d), (x + px * w / 2 + fx * d, y + py * w / 2 + fy * d)]
    v.polygon(pts, lw="fine")
    v.circle((x + fx * d * 0.55, y + fy * d * 0.55), 0.45, lw="hair")


def _urinal(v, x, y, facing):
    fx, fy = facing
    px, py = -fy, fx
    pts = []
    for i in range(0, 181, 15):
        a = math.radians(i)
        pts.append((x + px * 0.75 * math.cos(a) + fx * 1.1 * math.sin(a),
                    y + py * 0.75 * math.cos(a) + fy * 1.1 * math.sin(a)))
    v.polyline(pts, lw="fine")


def draw_toilets(v: View, level, detail=False):
    lw_p = "thin"
    # BOYS (x 30.32..40.68, y 12.32..29.68): 1 accessible + 1 std stall on south wall, 2 urinals W wall, 2 lavs E wall
    yS = 12 + CMUh
    xW, xE = 30 + CMUh, 41 - CMUh
    # accessible stall at east
    acc_w = 5.0 + 1 * IN
    v.polyline([(xE - acc_w, yS), (xE - acc_w, yS + 5.0)], lw=lw_p)
    v.polyline([(xE - acc_w, yS + 5.0), (xE - acc_w + 0.2, yS + 5.0)], lw=lw_p)
    v.line((xE - acc_w + 2.2, yS + 5.0), (xE, yS + 5.0), lw=lw_p)
    _wc(v, xE - 1.5, yS, (0, 1))
    # standard stall
    v.line((xE - acc_w - 3.0, yS), (xE - acc_w - 3.0, yS + 5.0), lw=lw_p)
    v.line((xE - acc_w - 3.0, yS + 5.0), (xE - acc_w - 2.6, yS + 5.0), lw=lw_p)
    _wc(v, xE - acc_w - 1.5, yS, (0, 1))
    _urinal(v, xW, 19.0, (1, 0))
    _urinal(v, xW, 21.5, (1, 0))
    v.line((xW, 20.25), (xW + 1.5, 20.25), lw=lw_p)
    _lav(v, xE, 23.5, (-1, 0))
    _lav(v, xE, 26.0, (-1, 0))
    # GIRLS (x 49.32..59.68): 3 stalls on west wall (accessible at south), 2 lavs E wall
    xW, xE = 49 + CMUh, 60 - CMUh
    v.line((xW, yS + 5.5), (xW + 5.0, yS + 5.5), lw=lw_p)
    v.line((xW + 5.0, yS), (xW + 5.0, yS + 2.0), lw=lw_p)
    _wc(v, xW, yS + 1.6, (1, 0))
    for i in range(2):
        y_a = yS + 5.5 + i * 3.0
        v.line((xW, y_a + 3.0), (xW + 5.0, y_a + 3.0), lw=lw_p)
        v.line((xW + 5.0, y_a), (xW + 5.0, y_a + 0.4), lw=lw_p)
        _wc(v, xW, y_a + 1.5, (1, 0))
    _lav(v, xE, 23.5, (-1, 0))
    _lav(v, xE, 26.0, (-1, 0))
    # STAFF TOILET (x 12.32..19.64, y 0.32..8.4)
    _wc(v, 12 + CMUh, 2.0, (1, 0))
    _lav(v, 20 - 3.625 * IN, 5.0, (-1, 0))
    # grab bars
    v.line((12 + CMUh + 0.15, 0.8), (12 + CMUh + 0.15, 4.3), lw="fine")
    # CUSTODIAL mop sink
    v.rect(41 + CMUh, 20 + CMUh, 2.0, 2.0, lw="fine")
    v.rect(41 + CMUh + 0.2, 20 + CMUh + 0.2, 1.6, 1.6, lw="hair")
    if level == "L2":
        # roof hatch above (dashed) + ladder
        v.rect(45.5, 25.5, 2.5, 3.0, lw="fine", dash="hidden")
        v.text((46.75, 25.2), "ROOF HATCH ABOVE", size=TXT["tiny"], anchor="c", valign="top")
        for yy in (26.0, 27.0, 28.0):
            v.line((46.0, yy), (47.5, yy), lw="hair")


def draw_casework(v: View, level, base_lw="thin"):
    """base cabinets (solid) and wall cabinets (dashed) at 1/8" plan"""
    D = 2.0
    def base(x0, y0, x1, y1):
        v.rect(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0), lw=base_lw)

    def wall_cab(x0, y0, x1, y1):
        v.rect(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0), lw="hair", dash="hidden")

    for rm in M.rooms(level):
        if rm.name != "CLASSROOM":
            continue
        xs = [p[0] for p in rm.poly]
        ys = [p[1] for p in rm.poly]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        north = y0 >= 42
        if north:
            xe = x1 - CMUh
            base(xe - D, 46.0, xe, 58.0)
            wall_cab(xe - 1.0, 46.0, xe, 55.0)
            base(xe - D, 58.0, xe, 61.0)  # tall CW-4
            v.line((xe - D, 58.0), (xe, 61.0), lw="hair")
            v.line((xe - D, 61.0), (xe, 58.0), lw="hair")
            v.circle((xe - 1.0, 56.5), 0.55, lw="hair")  # sink
            # cubbies on corridor wall
            yc = 42 + CMUh
            v.rect(x0 + 7.0, yc, 16.0, 1.25, lw="fine")
            for k in range(1, 6):
                v.line((x0 + 7.0 + k * 16 / 6, yc), (x0 + 7.0 + k * 16 / 6, yc + 1.25), lw="hair")
        else:
            xw = x0 + CMUh
            base(xw, 4.0, xw + D, 16.0)
            wall_cab(xw, 7.0, xw + 1.0, 16.0)
            base(xw, 16.0, xw + D, 19.0)
            v.line((xw, 16.0), (xw + D, 19.0), lw="hair")
            v.line((xw, 19.0), (xw + D, 16.0), lw="hair")
            v.circle((xw + 1.0, 5.5), 0.55, lw="hair")
            yc = 30 - CMUh
            v.rect(x0 + 7.0, yc - 1.25, 16.0, 1.25, lw="fine")
            for k in range(1, 6):
                v.line((x0 + 7.0 + k * 16 / 6, yc - 1.25), (x0 + 7.0 + k * 16 / 6, yc), lw="hair")
    # workroom / planning (west wall of the L-shaped room)
    xw = 12 + CMUh
    if level == "L1":
        base(xw, 10.0, xw + D, 25.0)
        wall_cab(xw, 10.0, xw + 1.0, 22.0)
        v.circle((xw + 1.0, 23.5), 0.55, lw="hair")
        for yy in (1.0, 4.0):
            base(30 - CMUh - D, yy, 30 - CMUh, yy + 3.0)
            v.line((30 - CMUh - D, yy), (30 - CMUh, yy + 3.0), lw="hair")
            v.line((30 - CMUh - D, yy + 3.0), (30 - CMUh, yy), lw="hair")
    else:
        base(xw, 12.0, xw + D, 24.0)
        wall_cab(xw, 12.0, xw + 1.0, 24.0)
        v.circle((xw + 1.0, 22.5), 0.55, lw="hair")
        base(30 - CMUh - D, 1.0, 30 - CMUh, 4.0)
        v.line((30 - CMUh - D, 1.0), (30 - CMUh, 4.0), lw="hair")
        v.line((30 - CMUh - D, 4.0), (30 - CMUh, 1.0), lw="hair")
    # small group (east wall)
    xe = 138 - CMUh
    base(xe - D, 50.0, xe, 58.0)


def draw_drinking_fountains(v: View, level):
    # bi-level fountain in alcove-less location on corridor wall C near the toilets
    for x in (38.0,):
        v.rect(x, 30 + CMUh, 2.6, 1.5, lw="fine")
        v.line((x + 1.3, 30 + CMUh), (x + 1.3, 30 + CMUh + 1.5), lw="hair")
    v.text((39.3, 31.0 + 0.9), "EWC", size=TXT["tiny"], anchor="c", valign="bot")


# ----------------------------------------------------------------------------------------
# Grids, dimensions, tags
# ----------------------------------------------------------------------------------------

def draw_grids(v: View, level, x_ext=(-14.0, 86.0), y_ext=(-16.0, 166.0), dia=0.42,
               link=True, full=False, skip_west=None):
    """Grid lines with bubbles. x_ext = y-range for the vertical (number) lines,
    y_ext = x-range for the horizontal (letter) lines. Unless full=True the lines stop
    short of the building so they do not clutter room areas."""
    out = M.EW_OUT + 0.6
    if skip_west is None:
        skip_west = ("B", "C") if level == "L1" else ()
    for lab, x in M.GRID_X.items():
        if full:
            v.line((x, x_ext[0]), (x, x_ext[1]), lw="hair", dash="grid")
        else:
            v.line((x, x_ext[0]), (x, -out), lw="hair", dash="grid")
            v.line((x, 72 + out), (x, x_ext[1]), lw="hair", dash="grid")
        grid_bubble(v, (x, x_ext[0] - v.paper_len(dia / 2)), lab, dia)
        grid_bubble(v, (x, x_ext[1] + v.paper_len(dia / 2)), lab, dia)
    for lab, y in M.GRID_Y.items():
        west = lab not in skip_west
        if full:
            v.line((y_ext[0] if west else -36.0, y), (y_ext[1], y), lw="hair", dash="grid")
        else:
            if west:
                v.line((y_ext[0], y), (-out, y), lw="hair", dash="grid")
            v.line((150 + out, y), (y_ext[1], y), lw="hair", dash="grid")
        if west:
            grid_bubble(v, (y_ext[0] - v.paper_len(dia / 2), y), lab, dia)
        grid_bubble(v, (y_ext[1] + v.paper_len(dia / 2), y), lab, dia)
    if link and level == "L1":
        for lab, x in M.LINK_GRID_X.items():
            if full:
                v.line((x, 22.0), (x, 50.0), lw="hair", dash="grid")
            else:
                v.line((x, 43.5), (x, 50.0), lw="hair", dash="grid")
            grid_bubble(v, (x, 50.0 + v.paper_len(dia * 0.85 / 2)), lab, dia * 0.85)


def draw_dims(v: View, level, tiers=(5.5, 10.0, 14.0)):
    """exterior dimension strings: openings, grids, overall."""
    t1, t2, t3 = tiers
    out = M.EW_OUT
    # --- north (y = 72) ---
    yN = 72 + out
    ops = sorted([o for o in M.openings_on(level) if o.wall == "N" and o.kind != "door"],
                 key=lambda o: o.c)
    pts = [0.0] + [p for o in ops for p in (o.lo, o.hi)] + [150.0]
    pts = sorted(set(round(p, 4) for p in pts))
    v.dim_chain([(p, yN) for p in pts], t1, size=TXT["tiny"])
    gx = list(M.GRID_X.values())
    v.dim_chain([(x, yN) for x in gx], t2, size=TXT["small"])
    v.dim((-out, yN), (150 + out, yN), t3, size=TXT["small"])
    # --- south (y = 0) ---
    yS = -out
    ops = sorted([o for o in M.openings_on(level) if o.wall == "S"], key=lambda o: o.c)
    pts = [0.0] + [p for o in ops for p in (o.lo, o.hi)] + [150.0]
    pts = sorted(set(round(p, 4) for p in pts))
    v.dim_chain([(p, yS) for p in pts], -t1, size=TXT["tiny"])
    v.dim_chain([(x, yS) for x in gx], -t2, size=TXT["small"])
    v.dim((-out, yS), (150 + out, yS), -t3, size=TXT["small"])
    # --- east (x = 150) ---
    xE = 150 + out
    ops = sorted([o for o in M.openings_on(level) if o.wall == "E"], key=lambda o: o.c)
    pts = [0.0] + [p for o in ops for p in (o.lo, o.hi)] + [72.0]
    pts = sorted(set(round(p, 4) for p in pts))
    v.dim_chain([(xE, p) for p in pts], -t1, size=TXT["tiny"])
    gy = sorted(M.GRID_Y.values())
    v.dim_chain([(xE, y) for y in gy], -t2, size=TXT["small"])
    v.dim((xE, -out), (xE, 72 + out), -t3, size=TXT["small"])
    # --- west (x = 0) ---
    xW = -out
    if level == "L1":
        ops = sorted([o for o in M.openings_on(level) if o.wall in ("W1", "W2")], key=lambda o: o.c)
        pts = [0.0] + [p for o in ops for p in (o.lo, o.hi)] + [30.0, 42.0, 72.0]
        pts = sorted(set(round(p, 4) for p in pts))
        # west dims stop where the link attaches; offset beyond the link to the west
        v.dim_chain([(xW, p) for p in pts if p <= 30.0], 3.0, size=TXT["tiny"])
        v.dim_chain([(xW, p) for p in pts if p >= 42.0], 3.0, size=TXT["tiny"])
    else:
        ops = sorted([o for o in M.openings_on(level) if o.wall in ("W1", "W2", "W0")],
                     key=lambda o: o.c)
        pts = [0.0] + [p for o in ops for p in (o.lo, o.hi)] + [30.0, 42.0, 72.0]
        pts = sorted(set(round(p, 4) for p in pts))
        v.dim_chain([(xW, p) for p in pts], t1, size=TXT["tiny"])
        v.dim_chain([(xW, y) for y in gy], t2, size=TXT["small"])
        v.dim((xW, -out), (xW, 72 + out), t3, size=TXT["small"])


def draw_room_tags(v: View, level, area=False, skip=()):
    for r in M.rooms(level):
        if r.num in skip:
            continue
        at = r.tag_at
        if at is None:
            c = r.shape.centroid
            at = (c.x, c.y + 2.5)
        num = r.num
        a = None
        if area:
            a = f"{M.clear_room_poly(r).area:,.0f} SF"
        room_tag(v, at, r.name, num, size=TXT["label"] if len(r.name) > 10 else TXT["room"], area=a)


def door_tag_pos(o):
    ax, k, f_in, f_out, s = _frame(o)
    sw = 1 if o.swing == "+" else -1
    off = 1.9
    if o.frame == "F2":
        along = o.lo + 0.2 + 1.5 if o.side == "hi" else o.hi - 1.7
    else:
        along = o.c
    return _pt(ax, along, k - sw * off)


DOOR_TAG_AT = {"110B": (45.0, 18.0), "210B": (45.0, 18.0), "100B": (146.0, 38.3),
               "100A": (2.6, 38.6), "107": (17.6, 10.6), "207": (17.6, 10.6)}


def draw_door_tags(v: View, level):
    for o in M.doors(level):
        door_tag(v, DOOR_TAG_AT.get(o.id, door_tag_pos(o)), o.id)


def draw_window_tags(v: View, level):
    seen = set()
    for o in M.openings_on(level, kinds=("window", "storefront", "louver")):
        ax = M.opening_axis(o)
        k = M.opening_line_coord(o)
        out = M.seg_outward(o.wall)
        s = out[1] if ax == "x" else out[0]
        at = _pt(ax, o.c, k + s * 3.2)
        window_tag(v, at, o.type.replace("W-", "").replace("SF-", "SF") if False else o.type)
    # louvers above (L1)
    if level == "L1":
        for o in M.OPENINGS:
            if o.kind == "louver":
                window_tag(v, (o.c, -3.2), o.type)


def draw_wall_tags(v: View, level):
    spots = [
        ((15.0, 42.0), "P1"), ((45.0, 42.0), "P1"), ((90.0, 57.0), "P1"), ((80.0, 30.0), "P1"),
        ((6.0, 30.0), "P2"), ((12.0, 4.5), "P2"), ((138.0, 64.0), "P2"), ((25.5, 21.0), "P2"),
        ((13.3, 8.5), "P3"), ((20.0, 3.0), "P4"), ((119.0, 72.0), "EW-1"), ((140.0, 0.0), "EW-1"),
        ((150.0, 60.0), "EW-1"), ((45.0, 12.0), "P1"), ((90.0, 15.0), "P1"),
    ]
    for at, t in spots:
        if t == "EW-1":
            ax_h = abs(at[1] - 72) < 1e-6 or abs(at[1]) < 1e-6
            if abs(at[1] - 72) < 1e-6:
                at = (at[0], at[1] + 2.4)
            elif abs(at[1]) < 1e-6:
                at = (at[0], at[1] - 2.4)
            else:
                at = (at[0] + 2.6, at[1])
        wall_tag(v, at, t)


def plan_extents(level):
    return (-66, -22, 175, 96)
