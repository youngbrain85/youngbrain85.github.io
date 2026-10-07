"""A-701 / A-702 / A-711 / A-801: door, hardware, window/storefront, room finish and casework
schedules with door, frame and window type elevations.

Every schedule row is GENERATED from drawset.model (OPENINGS, doors(), DOOR_TYPES, FRAME_TYPES,
HARDWARE_SETS, WINDOW_TYPES, ROOMS, FINISHES, CASEWORK_TYPES, CASEWORK_TYPICAL) so that the plans
and the schedules cannot disagree. Values that the model does not carry (door thickness, finish
abbreviations, glass type tags, detail references, operational descriptions, basis-of-design notes)
are defined ONCE in the tables near the top of this module and applied by rule, never per opening.

Per the coordinator: no computed floor / wall / glass areas and no casework grand totals appear on
these sheets (students perform their own takeoff). Counts by type are shown where a real schedule
would show them.
"""
from __future__ import annotations

import math
import re
from collections import OrderedDict

from reportlab.pdfbase.pdfmetrics import stringWidth
from shapely.geometry import Point

from . import model as M
from .cad import (FONT, FONT_B, PT, TXT, Paper, fmt_elev, fmt_ftin, fmt_in, notes_block,
                  wrap_lines)

IN = M.IN
CELL = 6.0            # table cell text (pt)  >= 5.6 pt
HDR = 6.0             # table header text (pt)
NOTE = TXT["note"]    # 6.75 pt general notes

# ----------------------------------------------------------------------------------------
# Rule tables (design information not carried by model.py; applied by rule, not per opening)
# ----------------------------------------------------------------------------------------
DOOR_THK = 1.75                     # inches, all leaves
FRAME_HEAD = 4 * IN                 # HM frame head face (FRAME_TYPES: 4" head)
FRAME_FACE = 2 * IN                 # HM frame jamb / mullion face (FRAME_TYPES: 2" face)
FINISH_ABBR = {"WD": "FACT. FIN.", "HM": "PAINT", "AL": "CL. ANOD."}
MAT_NAME = {"WD": "WOOD", "HM": "HOLLOW METAL", "AL": "ALUMINUM"}

GLASS_TYPES = OrderedDict([
    ("GL-1", "1\" INSULATING GLASS UNIT: 1/4\" CLEAR LOW-E (COATING ON #2) + 1/2\" ARGON-FILLED "
             "AIR SPACE, WARM-EDGE SPACER + 1/4\" CLEAR. ANNEALED OR HEAT-STRENGTHENED PER ASTM E1300."),
    ("GL-1T", "SAME AS GL-1, BOTH LITES FULLY TEMPERED (ASTM C1048 KIND FT), PERMANENT SAFETY "
              "GLAZING LABEL EACH LITE (CPSC 16 CFR 1201 CAT. II)."),
    ("GL-2", "1/4\" CLEAR FULLY TEMPERED MONOLITHIC SAFETY GLASS (INTERIOR): F2 SIDELITES AND "
             "DOOR TYPE B VISION LITES."),
    ("GL-3", "FIRE-PROTECTION-RATED GLASS-CERAMIC, 60 MIN WITH HOSE STREAM, MARKED D-H-60, "
             "IMPACT SAFETY RATED (CPSC CAT. II). DOOR TYPE D LITES, 100 SQ. IN. MAX."),
])

# door type -> glass tag in the leaf (model DOOR_TYPES text tells which leaves are glazed)
DOOR_GLASS = {"B": "GL-2", "D": "GL-3", "E": "GL-1T"}

# window / storefront type -> glass tag (consistent with WINDOW_TYPES[...]["glazing"])
def win_glass(t):
    g = M.WINDOW_TYPES[t]["glazing"]
    if g.strip() in ("-", ""):
        return "-"
    return "GL-1T" if "TEMPERED" in g else "GL-1"


# detail references (head, jamb, sill).  See DETAIL_KEY for the titles expected on A-501/A-502.
DET = {
    "HM_CMU": ("5/A-502", "6/A-502", "-"),
    "HM_STUD": ("7/A-502", "8/A-502", "-"),
    "HM_EXT": ("1/A-501 SIM", "2/A-501 SIM", "5/A-501 SIM"),
    "SF": ("4/A-501", "6/A-501", "5/A-501"),
}
DETAIL_KEY = [
    ("1/A-501", "WINDOW HEAD W-A (STEEL LINTEL, FLASHING, FB-2 SOLDIER)"),
    ("2/A-501", "WINDOW JAMB W-A"),
    ("3/A-501", "WINDOW SILL W-A (CS-1 CAST STONE SILL)"),
    ("4/A-501", "STOREFRONT HEAD SF-1"),
    ("5/A-501", "STOREFRONT SILL / THRESHOLD SF-1"),
    ("6/A-501", "STOREFRONT JAMB SF-1"),
    ("7/A-501", "STOREFRONT HEAD SF-3 (LINK ROOF)"),
    ("8/A-501", "STOREFRONT SILL SF-3 AT 8\" CONCRETE CURB"),
    ("9/A-501", "STOREFRONT JAMB SF-3"),
    ("5/A-502", "HM FRAME HEAD IN CMU PARTITION"),
    ("6/A-502", "HM FRAME JAMB IN CMU PARTITION"),
    ("7/A-502", "HM FRAME HEAD IN METAL STUD PARTITION"),
    ("8/A-502", "HM FRAME JAMB IN METAL STUD PARTITION"),
    ("9/A-502", "HM SIDELITE MULLION AND SILL RAIL (F2)"),
]
# window / storefront type -> (head, jamb, sill) details and wall-section references
WIN_DET = {
    "W-A": ("1/A-501", "2/A-501", "3/A-501"),
    "W-B": ("1/A-501 SIM", "2/A-501 SIM", "3/A-501 SIM"),
    "W-C": ("1/A-501 SIM", "2/A-501 SIM", "3/A-501 SIM"),
    "SF-1": ("4/A-501", "6/A-501", "5/A-501"),
    "SF-2": ("1/A-501 SIM", "2/A-501 SIM", "3/A-501 SIM"),
    "SF-3": ("7/A-501", "9/A-501", "8/A-501"),
    "LV-1": ("1/A-501 SIM", "2/A-501 SIM", "3/A-501 SIM"),
}
WIN_SECTION = {"W-A": "1/A-311, 2/A-311", "W-C": "3/A-311", "SF-1": "1/A-312",
               "SF-3": "2/A-312", "W-B": "-", "SF-2": "-", "LV-1": "-"}

# ----------------------------------------------------------------------------------------
# Generic helpers
# ----------------------------------------------------------------------------------------

def natkey(s):
    m = re.match(r"(\d+)(.*)", s)
    if m:
        return (0, int(m.group(1)), m.group(2))
    return (1, 0, s)


def rname(r):
    return r.name.replace("\n", " ")


def room_label(r):
    return f"{r.num} {rname(r)}" if r else "EXTERIOR"


def ft(x, denom=16):
    return fmt_ftin(x, denom)


def size_txt(w, h):
    return f"{ft(w)} x {ft(h)}"


def host_wall_type(o):
    return "EW-1" if o.wall in M.EXT_SEGS else M.WALL_BY_ID[o.wall].type


def _cells_of(rows):
    return [r for r in rows if not isinstance(r, str)]


class _Null:
    """measuring stand-in for a Paper (no output)"""

    def __getattr__(self, name):
        return lambda *a, **k: 0.0


def sched_table(p, x, y, cols, rows, title=None, groups=None, size=CELL, hsize=HDR, row_h=0.19,
                align=None, max_lines=4, title_note=None, draw=True, title_h=0.27,
                fonts=None):
    """Schedule table, (x, y) = TOP-LEFT. Returns height (in).

    cols   : [(header, width_in)]   header may contain '\\n'
    groups : [(label, ncols)]       grouped header band; label '' -> column headers span both bands
    rows   : list of rows: [cells...] | 'SEPARATOR TEXT' | {'cells': [...], 'bold': True, 'fill': 'g05'}
    """
    q = p if draw else _Null()
    hs = hsize or size
    W = sum(w for _, w in cols)
    xs = [x]
    for _, w in cols:
        xs.append(xs[-1] + w)
    lead = size * 1.13 / PT
    cy = y
    if title:
        q.rect(x, cy - title_h, W, title_h, lw="thin", fill="g30")
        q.text((x + 0.08, cy - title_h / 2), title, size=TXT["label"], font=FONT_B, anchor="l",
               valign="mid")
        if title_note:
            q.text((x + W - 0.08, cy - title_h / 2), title_note, size=size, anchor="r",
                   valign="mid")
        cy -= title_h
    nlh = max(len(h.split("\n")) for h, _ in cols)
    ch = nlh * hs * 1.12 / PT + 0.08
    gh = (hs * 1.12 / PT + 0.08) if groups else 0.0
    q.rect(x, cy - gh - ch, W, gh + ch, lw=None, fill="g15", stroke=False)
    span = [False] * len(cols)
    gedges = {0, len(cols)}
    if groups:
        ci = 0
        for label, n in groups:
            x0, x1 = xs[ci], xs[ci + n]
            if label:
                q.text(((x0 + x1) / 2, cy - gh / 2), label, size=hs + 0.5, font=FONT_B, anchor="c",
                       valign="mid")
                q.line((x0, cy - gh), (x1, cy - gh), lw="fine")
            else:
                for k in range(n):
                    span[ci + k] = True
            for k in range(n + 1):
                pass
            gedges.add(ci)
            gedges.add(ci + n)
            ci += n
    for i, (h, w) in enumerate(cols):
        top = cy if (span[i] or not groups) else cy - gh
        bot = cy - gh - ch
        q.mtext(((xs[i] + xs[i + 1]) / 2, (top + bot) / 2), h.split("\n"), size=hs, font=FONT_B,
                anchor="c", valign="mid", leading=hs * 1.12)
    for i in range(1, len(cols)):
        top = cy if (i in gedges or not groups) else cy - gh
        q.line((xs[i], top), (xs[i], cy - gh - ch), lw="fine")
    cy -= gh + ch
    q.line((x, cy), (x + W, cy), lw="thin")
    al = align or (["c"] * len(cols))
    for r in rows:
        if r is None:
            continue
        if isinstance(r, str):
            rh = row_h
            q.rect(x, cy - rh, W, rh, lw=None, fill="g05", stroke=False)
            q.text((x + 0.07, cy - rh / 2), r, size=size + 0.25, font=FONT_B, anchor="l",
                   valign="mid")
            q.line((x, cy - rh), (x + W, cy - rh), lw="fine")
            cy -= rh
            continue
        opts = {}
        if isinstance(r, dict):
            opts = r
            r = r["cells"]
        fnt = FONT_B if opts.get("bold") else FONT
        cells = []
        nl = 1
        for i, ((h, w), cell) in enumerate(zip(cols, r)):
            s = "" if cell is None else str(cell)
            f = fnt
            if fonts and fonts[i]:
                f = fonts[i]
            ls = wrap_lines(s.split("\n"), size, f, w - 0.09)[:max_lines]
            nl = max(nl, len(ls))
            cells.append((ls, f))
        rh = row_h + (nl - 1) * lead
        if opts.get("fill"):
            q.rect(x, cy - rh, W, rh, lw=None, fill=opts["fill"], stroke=False)
        for i, ((ls, f), a) in enumerate(zip(cells, al)):
            x0, x1 = xs[i], xs[i + 1]
            tx = {"l": x0 + 0.05, "c": (x0 + x1) / 2, "r": x1 - 0.05}[a]
            q.mtext((tx, cy - rh / 2), [l.strip() if a != "l" else l for l in ls], size=size,
                    font=f, anchor=a, valign="mid", leading=size * 1.13)
        for i in range(1, len(cols)):
            q.line((xs[i], cy), (xs[i], cy - rh), lw="fine")
        q.line((x, cy - rh), (x + W, cy - rh), lw="hair" if opts.get("light") else "fine")
        cy -= rh
    H = y - cy
    q.rect(x, cy, W, H, lw="thin")
    if title:
        q.line((x, y - title_h), (x + W, y - title_h), lw="thin")
    return H


def table_w(cols):
    return sum(w for _, w in cols)


def hexagon(p, x, y, text, size=TXT["small"], r=None, font=FONT_B, fill="white"):
    rr = r or max(0.11, (p.text_width(text, size, font) + 0.07) / 1.7)
    pts = [(x + rr * math.cos(math.radians(a)), y + rr * math.sin(math.radians(a)))
           for a in range(0, 360, 60)]
    p.polygon(pts, lw="thin", fill=fill)
    p.text((x, y), text, size=size, font=font, anchor="c", valign="mid")
    return rr


def circle_tag(p, x, y, text, size=TXT["label"], r=0.15):
    p.circle((x, y), r, lw="thin", fill="white")
    p.text((x, y), text, size=size, font=FONT_B, anchor="c", valign="mid")


def box_tag(p, x, y, text, size=TXT["label"], pad=0.06):
    w = p.text_width(text, size, FONT_B) + 2 * pad
    h = size * 1.5 / PT
    p.rect(x - w / 2, y - h / 2, w, h, lw="thin", fill="white")
    p.text((x, y), text, size=size, font=FONT_B, anchor="c", valign="mid")


def glass_tag(p, x, y, text, size=TXT["small"]):
    w = p.text_width(text, size) + 0.07
    h = 0.12
    # rounded-end (obround) tag
    r = h / 2
    p.c.saveState()
    p.c.setLineWidth(0.4)
    p.c.setFillColorRGB(1, 1, 1)
    p.c.roundRect((x - w / 2) * PT, (y - h / 2) * PT, w * PT, h * PT, r * PT, stroke=1, fill=1)
    p.c.restoreState()
    p.text((x, y), text, size=size, anchor="c", valign="mid")


def glass_marks(v, x0, y0, x1, y1, n=3):
    """conventional glass indication: short parallel diagonals in a lite (model coords)"""
    w, h = x1 - x0, y1 - y0
    s = min(w, h)
    L = min(s * 0.45, v.paper_len(0.45))
    gap = min(s * 0.07, v.paper_len(0.06))
    cx, cy = x0 + w * 0.68, y0 + h * 0.70
    d = (math.cos(math.radians(45)), math.sin(math.radians(45)))
    nrm = (-d[1], d[0])
    for k in range(n):
        o = (k - (n - 1) / 2) * gap
        L2 = L * (1.0 - abs(k - (n - 1) / 2) * 0.35)
        a = (cx + nrm[0] * o - d[0] * L2 / 2, cy + nrm[1] * o - d[1] * L2 / 2)
        b = (cx + nrm[0] * o + d[0] * L2 / 2, cy + nrm[1] * o + d[1] * L2 / 2)
        v.line(a, b, lw="hair")


def dim_s(v, p1, p2, offset, text, side="r", size=TXT["small"]):
    """dimension whose text is placed beside the dimension line (for short dims).
    side: 'r' / 'l' (horizontal dims) or 'u' / 'd' (vertical dims) relative to segment."""
    v.dim(p1, p2, offset, text="", size=size)
    # dimension line location
    d = (p2[0] - p1[0], p2[1] - p1[1])
    L = math.hypot(*d)
    u = (d[0] / L, d[1] / L)
    n = (-u[1], u[0])
    a = (p1[0] + n[0] * offset, p1[1] + n[1] * offset)
    b = (p2[0] + n[0] * offset, p2[1] + n[1] * offset)
    pad = v.paper_len(0.07)
    if abs(u[1]) < 1e-6:   # horizontal
        y = a[1] + v.paper_len(0.035)
        if side == "r":
            v.text((max(a[0], b[0]) + pad, y), text, size=size, anchor="l", valign="bot")
        else:
            v.text((min(a[0], b[0]) - pad, y), text, size=size, anchor="r", valign="bot")
    else:                  # vertical
        x = a[0] - v.paper_len(0.035)
        if side in ("u", "r"):
            v.text((x, max(a[1], b[1]) + pad), text, size=size, anchor="l", valign="bot", rot=90)
        else:
            v.text((x, min(a[1], b[1]) - pad), text, size=size, anchor="r", valign="bot", rot=90)


def leader_note(v, tip, at, text, size=TXT["small"], width=None):
    """leader from tip (model) to label point at (model). Text on the side away from the tip."""
    elbow = (at[0], at[1])
    v.leader([tip, elbow], text if width is None else None,
             lines=None if width is None else text, size=size, width=width)


def view_label(sh, x, y, num, title, scale, width=None):
    sh.view_title(x, y, num, title, scale, width=width)


# ----------------------------------------------------------------------------------------
# Door data (generated)
# ----------------------------------------------------------------------------------------

def _pt(ax, along, across):
    return (along, across) if ax == "x" else (across, along)


def door_rooms(o):
    """(to_room, from_room) Room objects (None = exterior), found by probing both wall faces."""
    ax = M.opening_axis(o)
    k = M.opening_line_coord(o)
    rms = M.rooms(o.level)
    found = []
    for s in (-1.0, 1.0):
        pt = Point(*_pt(ax, o.c, k + s * 1.0))
        hit = None
        for r in rms:
            if r.shape.contains(pt):
                hit = r
                break
        found.append(hit)
    a, b = found
    if a is not None and a.num == o.room:
        return a, b
    if b is not None and b.num == o.room:
        return b, a
    # fall back: room named by the model
    to = next((r for r in rms if r.num == o.room), None)
    other = b if a is to else a
    return to, other


def door_height(o):
    h = o.head - o.sill
    return h - FRAME_HEAD if o.frame in ("F1", "F2", "F3") else h


def door_lite(t):
    """vision lite size (w, h in inches) parsed from DOOR_TYPES text, or None"""
    m = re.search(r"(\d+(?:\.\d+)?)\"\s*x\s*(\d+(?:\.\d+)?)\"", M.DOOR_TYPES[t])
    if m:
        return float(m.group(1)), float(m.group(2))
    return None


def storefront_for(o):
    for s in M.OPENINGS:
        if s.kind == "storefront" and s.wall == o.wall and abs(s.c - o.c) < 0.01:
            return s
    return None


def door_details(o):
    if o.frame == "SF":
        return DET["SF"]
    if o.wall in M.EXT_SEGS:
        return DET["HM_EXT"]
    if M.WALL_TYPES[host_wall_type(o)]["mat"] == "stud":
        return DET["HM_STUD"]
    return DET["HM_CMU"]


def door_row(o):
    to, frm = door_rooms(o)
    leaf = ft(o.leaf)
    h = ft(door_height(o))
    size = (f"PR {leaf} x {h}" if o.pair else f"{leaf} x {h}")
    lite = DOOR_GLASS.get(o.type, "-")
    if o.type in DOOR_GLASS and door_lite(o.type):
        lw, lh = door_lite(o.type)
        lite = f"{lite} ({fmt_in(lw)}x{fmt_in(lh)})"
    elif o.type == "E":
        lite = "GL-1T (FULL)"
    if o.frame == "SF":
        sf = storefront_for(o)
        mo = f"IN {sf.type}" if sf else "IN STOREFRONT"
    else:
        mo = size_txt(o.w, o.head - o.sill)
    hd, jb, sl = door_details(o)
    side = "GL-2" if o.frame == "F2" else "-"
    return [o.id, room_label(to), room_label(frm), size, fmt_in(DOOR_THK), o.type, o.dmat,
            FINISH_ABBR.get(o.dmat, "-"), lite, o.frame, o.fmat, FINISH_ABBR.get(o.fmat, "-"),
            host_wall_type(o), mo, side, hd, jb, sl, o.rating or "-", o.hw, o.remarks or ""]


DOOR_COLS = [
    ("DOOR\nNO.", 0.52),
    ("ROOM (TO)", 1.32), ("FROM", 1.22),
    ("SIZE\n(W x H)", 1.02), ("THK.", 0.4), ("TYPE", 0.38), ("MATL", 0.4), ("FINISH", 0.62),
    ("GLAZING\n(VISIBLE)", 0.95),
    ("TYPE", 0.38), ("MATL", 0.4), ("FINISH", 0.62), ("WALL\nTYPE", 0.42), ("MO\n(W x H)", 0.98),
    ("SIDE-\nLITE", 0.42), ("HEAD", 0.74), ("JAMB", 0.74), ("SILL", 0.74),
    ("FIRE\nRATING", 0.52), ("HDW.\nSET", 0.48), ("REMARKS", 2.35),
]
DOOR_GROUPS = [("", 1), ("LOCATION", 2), ("DOOR", 6), ("FRAME", 9), ("", 1), ("", 1), ("", 1)]


def door_schedule_rows():
    rows = []
    for lev in ("L1", "L2"):
        ds = sorted(M.doors(lev), key=lambda o: natkey(o.id))
        rows.append(f"LEVEL {lev[1]}  -  FFE {fmt_elev(M.LEVELS[lev])}  ({len(ds)} OPENINGS)")
        for o in ds:
            rows.append(door_row(o))
    return rows


# ----------------------------------------------------------------------------------------
# A-701 drawing pieces
# ----------------------------------------------------------------------------------------

def _break_v(v, x, y0, y1, zig=0.06):
    """vertical break line (model coords)"""
    m = (y0 + y1) / 2
    z = v.paper_len(zig)
    v.polyline([(x, y0), (x, m - z), (x + z * 0.9, m - z * 0.3), (x - z * 0.9, m + z * 0.3),
                (x, m + z), (x, y1)], lw="fine")


def cmu_context(v, x0, x1, top, band=16 * IN, courses=12, color="g50"):
    """light running-bond CMU coursing around an opening x0..x1 (MO), MO head at `top`."""
    H = courses * 8 * IN
    for (a, b, ylo) in ((x0 - band, x0, 0.0), (x1, x1 + band, 0.0), (x0, x1, top)):
        y = ylo
        j = int(round(ylo / (8 * IN)))
        while y < H - 1e-6:
            yt = min(y + 8 * IN, H)
            v.line((a, yt), (b, yt), lw="hair", color=color)
            st = (j % 2) * 8 * IN
            xx = -64 * IN + st
            while xx < x1 + band + 1e-6:
                if a + 1e-6 < xx < b - 1e-6:
                    v.line((xx, y), (xx, yt), lw="hair", color=color)
                xx += 16 * IN
            y = yt
            j += 1
    # outer limits: break lines
    _break_v(v, x0 - band, 0, H)
    _break_v(v, x1 + band, 0, H)
    v.line((x0 - band, H), (x1 + band, H), lw="fine", dash="hidden", color=color)


def floor_line(v, x0, x1, lw="heavy"):
    v.line((x0, 0), (x1, 0), lw=lw)


def draw_leaf(v, x0, w, h, t, hinge="l", show_hw=True):
    """door leaf elevation, lower-left at (x0, 0). t = door type letter."""
    v.rect(x0, 0, w, h, lw="med")
    lite = door_lite(t)
    lock_x = x0 + w if hinge == "l" else x0
    sgn = -1 if hinge == "l" else 1
    info = {}
    if t in ("B", "D") and lite:
        lw_, lh_ = lite[0] * IN, lite[1] * IN
        edge = 6 * IN
        bot = 3.5 if t == "B" else 3.5
        if hinge == "l":
            gx1 = x0 + w - edge
            gx0 = gx1 - lw_
        else:
            gx0 = x0 + edge
            gx1 = gx0 + lw_
        # lite kit frame
        k = 0.75 * IN
        v.rect(gx0 - k, bot - k, lw_ + 2 * k, lh_ + 2 * k, lw="fine")
        v.rect(gx0, bot, lw_, lh_, lw="thin")
        glass_marks(v, gx0, bot, gx1, bot + lh_, n=2)
        info = dict(gx0=gx0, gx1=gx1, gy0=bot, gy1=bot + lh_)
    if t == "E":
        st, tr, br = 3.5 * IN, 3.5 * IN, 10 * IN
        gx0, gx1, gy0, gy1 = x0 + st, x0 + w - st, br, h - tr
        v.rect(gx0, gy0, gx1 - gx0, gy1 - gy0, lw="thin")
        v.rect(gx0 + 0.6 * IN, gy0 + 0.6 * IN, gx1 - gx0 - 1.2 * IN, gy1 - gy0 - 1.2 * IN,
               lw="hair")
        glass_marks(v, gx0, gy0, gx1, gy1)
        info = dict(gx0=gx0, gx1=gx1, gy0=gy0, gy1=gy1, st=st, tr=tr, br=br)
        if show_hw:
            # offset pull on lock stile (exterior face)
            px = lock_x + sgn * 1.75 * IN
            v.rect(px - 0.5 * IN, 3.0, 1.0 * IN, 3.0, lw="fine", fill="g30")
    elif show_hw:
        # lever trim at 3'-2" AFF
        lx = lock_x + sgn * 2.75 * IN
        v.circle((lx, 38 * IN), 1.25 * IN, lw="fine")
        v.line((lx, 38 * IN), (lx + sgn * 5 * IN, 38 * IN), lw="thin")
        if t == "C":
            # exit device bar on push side shown dashed
            v.rect(x0 + 3 * IN, 37 * IN, w - 6 * IN, 2.5 * IN, lw="hair", dash="hidden")
    return info


def door_type_view(sh, cx, base_y, t, scale=0.25):
    """draw door type t centered at paper cx with floor at paper base_y. returns paper bbox top."""
    pair = t == "E"
    W = 6.0 if pair else 3.0
    H = 7.0
    v = sh.view(cx - W * scale / 2, base_y, scale)
    floor_line(v, -0.8, W + 0.8)
    if pair:
        i1 = draw_leaf(v, 0, 3.0, H, t, hinge="l")
        draw_leaf(v, 3.0, 3.0, H, t, hinge="r")
        v.dim((0, 0), (3.0, 0), -1.1)
        v.dim((3.0, 0), (6.0, 0), -1.1)
        v.dim((0, 0), (6.0, 0), -2.0, text=f"PAIR {ft(6.0)}")
        v.dim((0, 0), (0, H), 1.1)
        # stile / rail dims on right leaf
        dim_s(v, (6.0 - i1["st"], H), (6.0, H), 0.7, fmt_in(3.5), side="r")
        dim_s(v, (6.0, 0), (6.0, i1["br"]), -0.7, fmt_in(10), side="d")
        dim_s(v, (6.0, H - i1["tr"]), (6.0, H), -0.7, fmt_in(3.5), side="u")
        glass_tag(sh, *v.to_paper((1.5, 4.6)), DOOR_GLASS["E"])
        glass_tag(sh, *v.to_paper((4.5, 4.6)), DOOR_GLASS["E"])
        v.leader([(5.1, 2.0), (7.6, 1.2)], "10\" BOTTOM RAIL", size=TXT["small"])
        v.leader([(5.1 - 0.0, 4.5), (7.6, 5.4)], "OFFSET PULL", size=TXT["small"])
        return v
    info = draw_leaf(v, 0, W, H, t, hinge="l")
    v.dim((0, 0), (W, 0), -1.1)
    v.dim((0, 0), (0, H), 1.1)
    if info:
        gx0, gx1, gy0, gy1 = info["gx0"], info["gx1"], info["gy0"], info["gy1"]
        lw_, lh_ = door_lite(t)
        # horizontal: lite width + edge distance, above the door
        dim_s(v, (gx0, H), (gx1, H), 0.75, fmt_in(lw_), side="l")
        dim_s(v, (gx1, H), (W, H), 0.75, fmt_in((W - gx1) * 12), side="r")
        # vertical chain on right side
        v.dim((W, 0), (W, gy0), -0.9)
        v.dim((W, gy0), (W, gy1), -0.9)
        dim_s(v, (W, gy1), (W, H), -0.9, fmt_in((H - gy1) * 12), side="u")
        gtag = DOOR_GLASS[t]
        glass_tag(sh, *v.to_paper(((gx0 + gx1) / 2 - 1.05, gy1 + 0.35)), gtag)
        v.line(((gx0 + gx1) / 2 - 0.75, gy1 + 0.3), ((gx0 + gx1) / 2, gy1 - 0.4), lw="hair")
    return v


DOOR_TYPE_NOTES = {
    "A": ["1 3/4\" FLUSH SOLID CORE (SCLC) WOOD", "AWI PREMIUM, PLAIN SLICED WHITE OAK",
          "FACTORY FINISHED (TRANSPARENT)"],
    "B": ["1 3/4\" SOLID CORE WOOD, MATCH TYPE A", "NARROW LITE KIT, STEEL, PRIMED/PAINTED",
          "ADA: BOTTOM OF GLASS 43\" AFF MAX."],
    "C": ["1 3/4\" FLUSH HM, 16 GA. A60 GALVANNEALED", "POLYSTYRENE / POLYURETHANE CORE",
          "SDI 100 LEVEL 3, MODEL 2 (SEAMLESS)"],
    "D": ["1 3/4\" HM, 18 GA., SDI LEVEL 2, LABELED", "60 MIN, POSITIVE PRESSURE (UL 10C)",
          "GL-3 LITE 100 SQ. IN. MAX."],
    "E": ["1 3/4\" ALUM. MEDIUM STILE ENTRANCE DOORS", "3 1/2\" STILES & TOP RAIL, 10\" BOTTOM",
          "RAIL, GL-1T, CL. ANOD. (SECTION 08 43 13)"],
}


def frame_view(sh, x0p, base_y, ftype, scale=0.25):
    """frame type elevation. x0p = paper x of MO left edge."""
    v = sh.view(x0p, base_y, scale)
    F = FRAME_FACE
    Hd = 7.0
    MOh = Hd + FRAME_HEAD
    if ftype == "F1":
        MOw = 2 * F + 3.0
        openings = [(F, F + 3.0)]
    elif ftype == "F2":
        MOw = F + 3.0 + F + 14 * IN + F
        openings = [(F, F + 3.0)]
    else:
        MOw = 2 * F + 6.0
        openings = [(F, F + 6.0)]
    # check against the model frame widths
    cmu_context(v, 0, MOw, MOh)
    floor_line(v, -1.8, MOw + 1.8)
    # frame outline (MO)
    v.polyline([(0, 0), (0, MOh), (MOw, MOh), (MOw, 0)], lw="med")
    # door opening(s)
    for a, b in openings:
        v.polyline([(a, 0), (a, Hd), (b, Hd), (b, 0)], lw="med")
        # frame stop / rabbet line
        v.polyline([(a + 0.6 * IN, 0), (a + 0.6 * IN, Hd - 0.6 * IN), (b - 0.6 * IN, Hd - 0.6 * IN),
                    (b - 0.6 * IN, 0)], lw="hair")
    if ftype == "F3":
        # removable / meeting line
        v.line((F + 3.0, 0), (F + 3.0, Hd), lw="hair", dash="hidden")
    if ftype == "F2":
        sx0 = F + 3.0 + F
        sx1 = sx0 + 14 * IN
        sy0 = FRAME_HEAD
        sy1 = Hd
        v.rect(sx0, sy0, sx1 - sx0, sy1 - sy0, lw="med")
        v.rect(sx0 + 1 * IN, sy0 + 1 * IN, sx1 - sx0 - 2 * IN, sy1 - sy0 - 2 * IN, lw="hair")
        glass_marks(v, sx0, sy0, sx1, sy1, n=2)
        glass_tag(sh, *v.to_paper(((sx0 + sx1) / 2, 2.2)), "GL-2")
    # dimensions ------------------------------------------------------------------
    top = MOh
    if ftype == "F1":
        dim_s(v, (0, top), (F, top), 0.75, fmt_in(2), side="l")
        v.dim((F, top), (F + 3.0, top), 0.75)
        dim_s(v, (F + 3.0, top), (MOw, top), 0.75, fmt_in(2), side="r")
    elif ftype == "F2":
        dim_s(v, (0, top), (F, top), 0.75, fmt_in(2), side="l")
        v.dim((F, top), (F + 3.0, top), 0.75)
        dim_s(v, (F + 3.0, top), (F + 3.0 + F, top), 1.45, fmt_in(2), side="l")
        v.dim((2 * F + 3.0, top), (2 * F + 3.0 + 14 * IN, top), 0.75)
        dim_s(v, (MOw - F, top), (MOw, top), 0.75, fmt_in(2), side="r")
        # door portion / sidelite portion
        v.dim((0, 0), (2 * F + 3.0, 0), -1.0)
        v.dim((2 * F + 3.0, 0), (MOw, 0), -1.0, text=ft(MOw - 2 * F - 3.0))
    else:
        dim_s(v, (0, top), (F, top), 0.75, fmt_in(2), side="l")
        v.dim((F, top), (F + 3.0, top), 0.75)
        v.dim((F + 3.0, top), (F + 6.0, top), 0.75)
        dim_s(v, (F + 6.0, top), (MOw, top), 0.75, fmt_in(2), side="r")
    off_mo = -1.9 if ftype == "F2" else -1.0
    v.dim((0, 0), (MOw, 0), off_mo, text=f"{ft(MOw)} MO")
    # vertical: door opening + head, and MO height
    v.dim((0, 0), (0, Hd), 2.0)
    dim_s(v, (0, Hd), (0, MOh), 2.0, fmt_in(4), side="u")
    v.dim((0, 0), (0, MOh), 2.9, text=f"{ft(MOh)} MO")
    if ftype == "F2":
        dim_s(v, (MOw, 0), (MOw, FRAME_HEAD), -2.0, fmt_in(4), side="d")
        v.dim((MOw, FRAME_HEAD), (MOw, Hd), -2.0)
    return v, MOw, MOh


FRAME_TYPE_NOTES = {
    "F1": ["SINGLE OPENING FOR 3'-0\" x 7'-0\" LEAF", "16 GA. INTERIOR / 14 GA. EXTERIOR (GALV.)",
           "3 HINGE PREPS, STRIKE PREP, 3 SILENCERS"],
    "F2": ["3'-0\" LEAF + 1'-0\" SIDELITE (CLASSROOMS)", "GL-2 TEMPERED, 1\" GLAZING STOPS:",
           "VISIBLE GLASS 1'-0\" x 6'-6\"; 4\" SILL RAIL"],
    "F3": ["PAIR OPENING FOR (2) 3'-0\" x 7'-0\" LEAVES", "KEYED REMOVABLE STEEL MULLION AT 112",
           "(HW-6); NO MULLION AT 100A (HW-8)"],
}


def door_summary_rows():
    ds = M.doors()
    t_rows = []
    for t in sorted(M.DOOR_TYPES):
        sel = [o for o in ds if o.type == t]
        sg = sum(1 for o in sel if not o.pair)
        pr = sum(1 for o in sel if o.pair)
        t_rows.append([t, f"{sg}", f"{pr}", f"{sg + 2 * pr}", f"{len(sel)}"])
    sg = sum(1 for o in ds if not o.pair)
    pr = sum(1 for o in ds if o.pair)
    t_rows.append({"cells": ["TOTAL", f"{sg}", f"{pr}", f"{sg + 2 * pr}", f"{len(ds)}"],
                   "bold": True, "fill": "g05"})
    f_rows = []
    for f in M.FRAME_TYPES:
        sel = [o for o in ds if o.frame == f]
        l1 = sum(1 for o in sel if o.level == "L1")
        l2 = sum(1 for o in sel if o.level == "L2")
        if f == "SF":
            mo = "IN SF-1"
        else:
            ws = sorted({round(o.w, 4) for o in sel})
            mo = ", ".join(size_txt(w, M.DH) for w in ws)
        f_rows.append([f, mo, f"{l1}", f"{l2}", f"{len(sel)}"])
    f_rows.append({"cells": ["TOTAL", "", f"{sum(1 for o in ds if o.level == 'L1')}",
                             f"{sum(1 for o in ds if o.level == 'L2')}", f"{len(ds)}"],
                   "bold": True, "fill": "g05"})
    r_rows = []
    ratings = sorted({o.rating for o in ds}, key=lambda s: (s == "", s))
    for rt in ratings:
        sel = sorted([o for o in ds if o.rating == rt], key=lambda o: (o.level, natkey(o.id)))
        lab = rt if rt else "NON-RATED"
        if rt:
            lst = ", ".join(o.id for o in sel)
        else:
            lst = "ALL OTHERS"
        r_rows.append([lab, f"{len(sel)}", lst])
    return t_rows, f_rows, r_rows


A701_NOTES = [
    "##DOORS",
    "WOOD DOORS (TYPES A, B): WDMA I.S.1A / AWI-AWMAC-WI ARCHITECTURAL WOODWORK STANDARDS (AWS) "
    "PREMIUM GRADE, EXTRA HEAVY DUTY, 5-PLY STRUCTURAL COMPOSITE LUMBER CORE (SCLC), PLAIN SLICED "
    "WHITE OAK, BOOK AND BALANCE MATCH. FACTORY FINISH AWS SYSTEM TR-6 (CATALYZED POLYURETHANE), "
    "ALL 6 SIDES SEALED. FACTORY MACHINE FOR HARDWARE AND FACTORY CUT LITE OPENINGS.",
    "HOLLOW METAL DOORS: ANSI/SDI A250.8 (SDI 100). INTERIOR TYPE D: LEVEL 2 (HEAVY DUTY), 18 GA. "
    "EXTERIOR TYPE C: LEVEL 3 (EXTRA HEAVY DUTY), MODEL 2 SEAMLESS, 16 GA., A60 GALVANNEALED, "
    "INSULATED (U-0.50 MAX.), TOP CAP CLOSED FLUSH. SHOP PRIMED; FIELD PAINT DTM ACRYLIC SEMI-GLOSS.",
    "ALUMINUM ENTRANCE DOORS (TYPE E): FURNISHED BY STOREFRONT MANUFACTURER, SEE A-711 SF-1. "
    "HARDWARE PER HW-7.",
    "DOOR SIZES ARE NOMINAL LEAF SIZES. ALL LEAVES 1 3/4\" THICK. UNDERCUT: 3/4\" MAX. ABOVE "
    "FINISH FLOOR (NFPA 80: 3/4\" MAX. AT RATED DOORS); 1/2\" MAX. ABOVE THRESHOLDS.",
    "##FRAMES",
    "HOLLOW METAL FRAMES: ANSI/SDI A250.8, FULLY WELDED, 2\" FACES, 4\" HEAD, DOUBLE RABBET, 5/8\" "
    "STOPS. 16 GA. INTERIOR, 14 GA. A60 GALVANNEALED AT EXTERIOR. JAMB DEPTH TO SUIT WALL TYPE "
    "SCHEDULED (SEE A-502 PARTITION TYPES).",
    "FRAMES IN MASONRY: ADJUSTABLE T-STRAP OR WIRE MASONRY ANCHORS, 3 PER JAMB UP TO 7'-6\" "
    "HEIGHT; FLOOR ANCHORS EACH JAMB. GROUT JAMBS AND HEADS SOLID WITH MORTAR OR 2,500 PSI GROUT "
    "AS MASONRY IS LAID (NOT AT ELECTRIFIED HARDWARE BOXES; PROVIDE MORTAR GUARDS).",
    "FRAMES IN METAL STUD PARTITIONS (DOORS 107, 207): STUD ANCHORS 3 PER JAMB, (2) 20 GA. JAMB "
    "STUDS EACH SIDE AND HEADER PER A-502.",
    "MASONRY OPENINGS (MO) ARE MODULAR: F1 3'-4\", F2 4'-8\", F3 6'-4\" WIDE x 7'-4\" HIGH. "
    "STEEL LINTELS OVER OPENINGS IN CMU PER S-302 LINTEL SCHEDULE.",
    "##FIRE-RATED AND SAFETY",
    "RATED OPENINGS: COMPLETE ASSEMBLIES PER NFPA 80 AND IBC 716, POSITIVE PRESSURE TESTED (UL 10C), "
    "PERMANENT LABELS ON DOOR AND FRAME. 60 MIN DOORS IN 1-HR P2 STAIR ENCLOSURES. "
    "DO NOT PAINT OVER LABELS.",
    "SAFETY GLAZING: ALL GLASS IN DOORS AND SIDELITES IS SAFETY GLAZING PER IBC 2406 "
    "(GL-1T, GL-2) OR IMPACT SAFETY-RATED FIRE-PROTECTION GLAZING (GL-3).",
    "PROVIDE SMOKE / DRAFT CONTROL GASKETING AT STAIR DOORS (HW-4). LEVER HARDWARE AT ALL "
    "DOORS. MANEUVERING CLEARANCES PER ICC A117.1-2017 404.2.4.",
    "ELEVATOR HOISTWAY ENTRANCES ARE FURNISHED AND INSTALLED BY THE ELEVATOR CONTRACTOR "
    "(SECTION 14 21 00) AND ARE NOT LISTED IN THIS SCHEDULE: {elev}.",
]


def draw_a701(sh):
    x0, y0, x1, y1 = sh.x0, sh.y0, sh.x1, sh.y1
    # ---------------- door schedule (top-left) ----------------
    tx, ty = x0 + 0.25, y1 - 0.2
    rows = door_schedule_rows()
    al = ["c", "l", "l", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c",
          "c", "c", "c", "l"]
    th = sched_table(sh, tx, ty, DOOR_COLS, rows, title="DOOR SCHEDULE", groups=DOOR_GROUPS,
                     align=al, row_h=0.195,
                     title_note="ALL DOORS 1 3/4\" THICK  |  SEE GENERAL NOTES THIS SHEET")
    sch_w = table_w(DOOR_COLS)
    sch_bot = ty - th
    sh.text((tx, sch_bot - 0.12),
            "ABBREVIATIONS:  WD = WOOD   HM = HOLLOW METAL   AL = ALUMINUM   FACT. FIN. = FACTORY "
            "FINISH   PAINT = FIELD PAINTED   CL. ANOD. = CLASS I CLEAR ANODIZED   PR = PAIR   "
            "MO = MASONRY OPENING   SIM = SIMILAR",
            size=TXT["small"], valign="top")

    # ---------------- right column: summaries, glass, detail key ----------------
    rx = tx + sch_w + 0.55
    rw = x1 - 0.2 - rx
    t_rows, f_rows, r_rows = door_summary_rows()
    cy = ty
    cols = [("DOOR\nTYPE", 0.55), ("SINGLE", 0.6), ("PAIR", 0.55), ("LEAVES", 0.62),
            ("OPENINGS", 0.75)]
    h1 = sched_table(sh, rx, cy, cols, t_rows, title="QUANTITY SUMMARY - DOOR TYPES",
                     row_h=0.18)
    cols2 = [("FRAME\nTYPE", 0.55), ("MO (W x H)", 1.95), ("LEVEL 1", 0.6), ("LEVEL 2", 0.6),
             ("TOTAL", 0.55)]
    fx = rx + table_w(cols) + 0.3
    h2 = sched_table(sh, fx, cy, cols2, f_rows, title="QUANTITY SUMMARY - FRAME TYPES",
                     row_h=0.18)
    cy -= max(h1, h2) + 0.3
    cols3 = [("FIRE RATING", 1.0), ("OPENINGS", 0.75), ("DOOR NUMBERS", rw - 1.75)]
    h3 = sched_table(sh, rx, cy, cols3, r_rows, title="QUANTITY SUMMARY - FIRE-RATED OPENINGS",
                     row_h=0.18, align=["c", "c", "l"])
    cy -= h3 + 0.3
    g_rows = [[k, v] for k, v in GLASS_TYPES.items()]
    h4 = sched_table(sh, rx, cy, [("GLASS TAG", 0.8), ("DESCRIPTION", rw - 0.8)], g_rows,
                     title="GLASS TYPES (DOORS, SIDELITES, STOREFRONT)", row_h=0.18,
                     align=["c", "l"])
    cy -= h4 + 0.3
    k_rows = [[a, b] for a, b in DETAIL_KEY if "A-502" in a] + \
             [[a, b] for a, b in DETAIL_KEY if a in ("1/A-501", "2/A-501", "4/A-501", "5/A-501",
                                                       "6/A-501")]
    half = (len(k_rows) + 1) // 2
    kw = (rw - 0.3) / 2
    kc = [("DETAIL", 0.62), ("TITLE", kw - 0.62)]
    hk1 = sched_table(sh, rx, cy, kc, k_rows[:half], title="DOOR DETAIL KEY", row_h=0.18,
                      align=["c", "l"])
    hk2 = sched_table(sh, rx + kw + 0.3, cy, kc, k_rows[half:], title="DOOR DETAIL KEY (CONT.)",
                      row_h=0.18, align=["c", "l"])
    cy -= max(hk1, hk2) + 0.15
    sh.mtext((rx, cy), ["EXTERIOR HOLLOW METAL OPENINGS (ST1-B, ST2-B, 112): HEAD, JAMB AND THRESHOLD "
                        "SIMILAR TO WINDOW / STOREFRONT DETAILS NOTED; STEEL LINTEL AND THROUGH-WALL "
                        "FLASHING WITH END DAMS AT HEAD."], size=TXT["small"], width=rw)

    # ---------------- lower band: door types + frame types | notes ----------------
    band_top = min(sch_bot - 0.45, cy - 0.5)
    band_top = sch_bot - 0.45
    sh.line((x0, band_top), (rx - 0.3, band_top), lw="thin")
    lw_ = rx - 0.3 - x0
    # door types row
    row_h = (band_top - y0) / 2
    dt_top = band_top
    types = list(M.DOOR_TYPES)
    widths = {t: (1.25 if t == "E" else 1.0) for t in types}
    tot = sum(widths.values())
    cxs = []
    acc = x0
    for t in types:
        w = lw_ * widths[t] / tot
        cxs.append((acc, w))
        acc += w
    base = dt_top - 0.85 - 7.0 * 0.25
    for (cx0, w), t in zip(cxs, types):
        cx = cx0 + w / 2 - (0.0 if t != "E" else 0.25)
        door_type_view(sh, cx, base, t)
        ty0 = base - 0.75
        circle_tag(sh, cx0 + 0.45, ty0, t)
        sh.text((cx0 + 0.7, ty0 + 0.02), f"TYPE {t}", size=TXT["label"], font=FONT_B, valign="mid")
        sh.mtext((cx0 + 0.3, ty0 - 0.22), DOOR_TYPE_NOTES[t], size=TXT["small"], leading=7.0)
        sh.mtext((cx0 + 0.3, ty0 - 0.68), M.DOOR_TYPES[t], size=TXT["small"], width=w - 0.45,
                 leading=7.0, color="g60")
    view_y = dt_top - 0.22
    sh.view_title(x0 + 0.25, dt_top - row_h + 0.18, 2, "DOOR TYPES", 0.25, width=5.0,
                  note="ELEVATIONS VIEWED FROM PUSH SIDE / EXTERIOR")
    sh.line((x0, dt_top - row_h), (rx - 0.3, dt_top - row_h), lw="fine")
    # frame types row
    ft_top = dt_top - row_h
    ftypes = ["F1", "F2", "F3", "SF"]
    fw = {"F1": 1.0, "F2": 1.15, "F3": 1.3, "SF": 1.0}
    tot = sum(fw.values())
    acc = x0
    base = ft_top - 0.85 - 8.0 * 0.25
    for f in ftypes:
        w = lw_ * fw[f] / tot
        if f != "SF":
            MOw = {"F1": 2 * FRAME_FACE + 3.0, "F2": 3 * FRAME_FACE + 3.0 + 14 * IN,
                   "F3": 2 * FRAME_FACE + 6.0}[f]
            xm = acc + w / 2 - MOw * 0.25 / 2 + 0.2
            frame_view(sh, xm, base, f)
            ty0 = base - 0.95
            box_tag(sh, acc + 0.5, ty0, f)
            sh.text((acc + 0.82, ty0), f"FRAME TYPE {f}", size=TXT["label"], font=FONT_B,
                    valign="mid")
            sh.mtext((acc + 0.3, ty0 - 0.22), FRAME_TYPE_NOTES[f], size=TXT["small"], leading=7.0)
            sh.mtext((acc + 0.3, ty0 - 0.68), M.FRAME_TYPES[f], size=TXT["small"], width=w - 0.45,
                     leading=7.0, color="g60")
        else:
            bx, by = acc + 0.4, base + 0.2
            bw, bh = w - 0.8, 1.8
            sh.rect(bx, by, bw, bh, lw="fine", dash="dashed")
            box_tag(sh, bx + 0.35, by + bh - 0.25, "SF")
            sh.mtext((bx + 0.15, by + bh - 0.55),
                     ["ALUMINUM STOREFRONT FRAMING", "DOOR 100B (TYPE E PAIR) IS SET IN",
                      "STOREFRONT SF-1. SEE A-711 FOR SF-1",
                      "ELEVATION AND DIMENSIONS, A-501 FOR",
                      "HEAD / JAMB / THRESHOLD DETAILS",
                      f"({', '.join(DET['SF'])})."], size=TXT["small"], leading=8.0)
            ty0 = base - 0.95
            box_tag(sh, acc + 0.5, ty0, f)
            sh.text((acc + 0.82, ty0), "STOREFRONT FRAME", size=TXT["label"], font=FONT_B,
                    valign="mid")
            sh.mtext((acc + 0.3, ty0 - 0.22), M.FRAME_TYPES["SF"], size=TXT["small"],
                     width=w - 0.45, leading=7.0, color="g60")
        acc += w
    sh.view_title(x0 + 0.25, y0 + 0.3, 3, "FRAME TYPES", 0.25, width=5.0,
                  note="DIMENSIONS ARE MASONRY OPENING / FRAME FACE")

    # ---------------- notes (lower right) ----------------
    elev = ", ".join(f"{o.id} ({ft(o.leaf)} WIDE, MO {size_txt(o.w, o.head - o.sill)})"
                     for o in M.OPENINGS if o.kind == "elevator")
    notes = [n.replace("{elev}", elev) for n in A701_NOTES]
    sh.line((rx - 0.3, band_top), (rx - 0.3, y0), lw="thin")
    notes_block(sh, rx, cy - 0.55 if cy - 0.55 < band_top else band_top - 0.15,
                "DOOR AND FRAME GENERAL NOTES", notes, rw)


# ----------------------------------------------------------------------------------------
SHEETS = [
    ("A-701", "DOOR SCHEDULE,\nDOOR TYPES AND\nFRAME TYPES", draw_a701),
]
