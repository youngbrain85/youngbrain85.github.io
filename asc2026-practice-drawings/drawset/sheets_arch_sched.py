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
from .cad import (FONT, FONT_B, PT, TXT, Paper, fmt_elev, fmt_ftin, fmt_in,
                  wrap_lines)

IN = M.IN
CELL = 6.0            # table cell text (pt)  >= 5.6 pt
HDR = 6.0             # table header text (pt)
NOTE = TXT["note"]    # 6.75 pt general notes

# ----------------------------------------------------------------------------------------
# Rule tables (design information not carried by model.py; applied by rule, not per opening)
# ----------------------------------------------------------------------------------------
DOOR_THK = 1.75                     # inches, all leaves
E_STILE = 4 * IN                    # type E medium stile and top rail (matches A-201/A-202)
E_BOTTOM = 10 * IN                  # type E bottom rail (ADA 10" smooth surface)
FRAME_HEAD = 4 * IN                 # HM frame head face (FRAME_TYPES: 4" head)
FRAME_FACE = 2 * IN                 # HM frame jamb / mullion face (FRAME_TYPES: 2" face)
FINISH_ABBR = {"WD": "FACT. FIN.", "HM": "PAINT", "AL": "CL. ANOD."}

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
    ("7/A-501", "STOREFRONT SF-3 HEAD AND SILL AT 8\" CONCRETE CURB"),
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
    "SF-3": ("7/A-501", "6/A-501 SIM", "7/A-501"),
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
    """feet-inches text; works around cad.fmt_ftin printing 7'-1/2" for 7'-0 1/2"."""
    return re.sub(r"'-(\d+/\d+)\"", r"'-0 \1\"", fmt_ftin(x, denom))


def D(v, p1, p2, offset, **kw):
    """View.dim with architecturally formatted default text"""
    if "text" not in kw:
        kw["text"] = ft(math.hypot(p2[0] - p1[0], p2[1] - p1[1]))
    v.dim(p1, p2, offset, **kw)


def DC(v, pts, offset, **kw):
    for a, b in zip(pts[:-1], pts[1:]):
        if math.hypot(b[0] - a[0], b[1] - a[1]) > 1e-6:
            D(v, a, b, offset, **kw)


def size_txt(w, h):
    return f"{ft(w)} x {ft(h)}"


def host_wall_type(o):
    return "EW-1" if o.wall in M.EXT_SEGS else M.WALL_BY_ID[o.wall].type


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
        if isinstance(r, dict) and "span" in r:
            # full-width wrapped text row (label in bold + text)
            lab = r.get("label", "")
            lab_w = (stringWidth(lab + " ", FONT_B, size) / PT) if lab else 0.0
            ls = wrap_lines([r["span"]], size, FONT, W - 0.12 - lab_w)
            rh = row_h + (len(ls) - 1) * lead
            if r.get("fill"):
                q.rect(x, cy - rh, W, rh, lw=None, fill=r["fill"], stroke=False)
            yy = cy - (row_h - lead) / 2 - lead / 2
            if lab:
                q.text((x + 0.06, yy), lab, size=size, font=FONT_B, valign="mid")
            for k_, ln in enumerate(ls):
                q.text((x + 0.06 + lab_w, yy - k_ * lead), ln.strip(), size=size, valign="mid")
            q.line((x, cy - rh), (x + W, cy - rh), lw="fine")
            cy -= rh
            continue
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
        if (s.kind == "storefront" and s.wall == o.wall and s.level == o.level
                and abs(s.c - o.c) < 0.01):
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
        st, tr, br = E_STILE, E_STILE, E_BOTTOM
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


def door_type_view(sh, x0p, base_y, t, scale=0.25):
    """draw door type t with the leaf's lower-left at paper (x0p, base_y). returns view."""
    pair = t == "E"
    W = 6.0 if pair else 3.0
    H = 7.0
    v = sh.view(x0p, base_y, scale)
    floor_line(v, -0.8, W + 0.8)
    if pair:
        i1 = draw_leaf(v, 0, 3.0, H, t, hinge="l")
        draw_leaf(v, 3.0, 3.0, H, t, hinge="r")
        D(v, (0, 0), (3.0, 0), -1.1)
        D(v, (3.0, 0), (6.0, 0), -1.1)
        v.dim((0, 0), (6.0, 0), -2.0, text=f"PAIR {ft(6.0)}")
        D(v, (0, 0), (0, H), 1.1)
        # stile (left leaf, above) and rails (right side chain)
        dim_s(v, (0, H), (i1["st"], H), 0.7, fmt_in(E_STILE * 12), side="l")
        dim_s(v, (6.0, 0), (6.0, i1["br"]), -0.8, fmt_in(10), side="d")
        D(v, (6.0, i1["br"]), (6.0, H - i1["tr"]), -0.8)
        dim_s(v, (6.0, H - i1["tr"]), (6.0, H), -0.8, fmt_in(E_STILE * 12), side="u")
        glass_tag(sh, *v.to_paper((1.5, 4.6)), DOOR_GLASS["E"])
        glass_tag(sh, *v.to_paper((4.5, 4.6)), DOOR_GLASS["E"])
        v.leader([(4.5, 0.45), (8.3, -0.6)], "10\" BOTTOM RAIL (ADA)", size=TXT["small"])
        v.leader([(3.15, 5.2), (8.3, 7.6)], "OFFSET PULL, EXTERIOR", size=TXT["small"])
        return v
    info = draw_leaf(v, 0, W, H, t, hinge="l")
    D(v, (0, 0), (W, 0), -1.1)
    D(v, (0, 0), (0, H), 1.1)
    if info:
        gx0, gx1, gy0, gy1 = info["gx0"], info["gx1"], info["gy0"], info["gy1"]
        lw_, lh_ = door_lite(t)
        # horizontal: lite width + edge distance, above the door
        dim_s(v, (gx0, H), (gx1, H), 0.75, fmt_in(lw_), side="l")
        dim_s(v, (gx1, H), (W, H), 0.75, fmt_in((W - gx1) * 12), side="r")
        # vertical chain on right side
        D(v, (W, 0), (W, gy0), -0.9)
        D(v, (W, gy0), (W, gy1), -0.9)
        dim_s(v, (W, gy1), (W, H), -0.9, fmt_in((H - gy1) * 12), side="u")
        gtag = DOOR_GLASS[t]
        glass_tag(sh, *v.to_paper(((gx0 + gx1) / 2 - 1.05, gy1 + 0.35)), gtag)
        v.line(((gx0 + gx1) / 2 - 0.75, gy1 + 0.3), ((gx0 + gx1) / 2, gy1 - 0.4), lw="hair")
    if t == "C":
        v.leader([(1.5, 38.5 * IN), (4.4, -0.6)], "EXIT DEVICE (HW-5 / HW-6)", size=TXT["small"])
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
    "E": ["1 3/4\" ALUM. MEDIUM STILE ENTRANCE DOORS", "4\" STILES & TOP RAIL, 10\" BOTTOM",
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
        v.dim((sx0 + 1 * IN, 3.3), (sx1 - 1 * IN, 3.3), 0, text="1'-0\"", ext=False)
    # dimensions ------------------------------------------------------------------
    top = MOh
    if ftype == "F1":
        dim_s(v, (0, top), (F, top), 0.75, fmt_in(2), side="l")
        D(v, (F, top), (F + 3.0, top), 0.75)
        dim_s(v, (F + 3.0, top), (MOw, top), 0.75, fmt_in(2), side="r")
    elif ftype == "F2":
        dim_s(v, (0, top), (F, top), 0.75, fmt_in(2), side="l")
        D(v, (F, top), (F + 3.0, top), 0.75)
        dim_s(v, (F + 3.0, top), (F + 3.0 + F, top), 1.45, fmt_in(2), side="l")
        D(v, (2 * F + 3.0, top), (2 * F + 3.0 + 14 * IN, top), 0.75)
        dim_s(v, (MOw - F, top), (MOw, top), 0.75, fmt_in(2), side="r")
        # door portion / sidelite portion
        D(v, (0, 0), (2 * F + 3.0, 0), -1.0)
        v.dim((2 * F + 3.0, 0), (MOw, 0), -1.0, text=ft(MOw - 2 * F - 3.0))
    else:
        dim_s(v, (0, top), (F, top), 0.75, fmt_in(2), side="l")
        D(v, (F, top), (F + 3.0, top), 0.75)
        D(v, (F + 3.0, top), (F + 6.0, top), 0.75)
        dim_s(v, (F + 6.0, top), (MOw, top), 0.75, fmt_in(2), side="r")
    off_mo = -1.9 if ftype == "F2" else -1.0
    v.dim((0, 0), (MOw, 0), off_mo, text=f"{ft(MOw)} MO")
    # vertical: door opening + head, and MO height
    D(v, (0, 0), (0, Hd), 2.0)
    dim_s(v, (0, Hd), (0, MOh), 2.0, fmt_in(4), side="u")
    v.dim((0, 0), (0, MOh), 2.9, text=f"{ft(MOh)} MO")
    if ftype == "F2":
        dim_s(v, (MOw, 0), (MOw, FRAME_HEAD), -2.0, fmt_in(4), side="d")
        D(v, (MOw, FRAME_HEAD), (MOw, Hd), -2.0)
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


def _note_items(notes, size, width):
    """[(kind, label, lines)] for notes; kind 'h' header or 'n' note. numbering restarts per header."""
    out = []
    i = 0
    lw_in = stringWidth("00. ", FONT, size) / PT
    for n in notes:
        if n.startswith("##"):
            out.append(("h", "", [n[2:].strip()]))
            i = 0
            continue
        i += 1
        out.append(("n", f"{i}.", wrap_lines([n], size, FONT, width - lw_in)))
    return out


def _note_item_h(it, size):
    lead = size * 1.28 / PT
    if it[0] == "h":
        return lead + 0.04
    return lead * len(it[2]) + lead * 0.25


def notes_cols(p, x, y, title, notes, width, ncols=1, gap=0.35, size=NOTE, max_h=None, draw=True):
    """General notes in ncols balanced columns (numbering continuous within sections).
    Returns height used."""
    if not draw:
        p = _Null()
    ts = TXT["label"]
    cw = (width - gap * (ncols - 1)) / ncols
    items = _note_items(notes, size, cw)
    total = sum(_note_item_h(it, size) for it in items)
    target = total / ncols
    cols = [[]]
    acc = 0.0
    for it in items:
        h = _note_item_h(it, size)
        if acc + h * 0.5 > target and len(cols) < ncols and cols[-1]:
            # avoid a lone header at the bottom of a column
            if cols[-1] and cols[-1][-1][0] == "h":
                hd = cols[-1].pop()
                cols.append([hd])
                acc = _note_item_h(hd, size)
            else:
                cols.append([])
                acc = 0.0
        cols[-1].append(it)
        acc += h
    p.text((x, y), title.upper(), size=ts, font=FONT_B, anchor="l", valign="top", underline=True)
    top = y - ts * 1.7 / PT
    lead = size * 1.28 / PT
    lw_in = stringWidth("00. ", FONT, size) / PT
    hmax = 0
    for k, col in enumerate(cols):
        cx = x + k * (cw + gap)
        cy = top
        for kind, lab, lines in col:
            if kind == "h":
                cy -= 0.04
                p.text((cx, cy), lines[0], size=size, font=FONT_B, valign="top")
                cy -= lead
                continue
            p.text((cx, cy), lab, size=size, valign="top")
            for ln in lines:
                p.text((cx + lw_in, cy), ln.strip(), size=size, valign="top")
                cy -= lead
            cy -= lead * 0.25
        hmax = max(hmax, y - cy)
    return hmax


def used_at(ids):
    return ", ".join(ids)


def door_type_cell(sh, cx0, cw, top, bot, t):
    pair = t == "E"
    W = 6.0 if pair else 3.0
    ew = W * 0.25
    # elevation: leaf lower-left
    ex = cx0 + 0.65
    base = (top + bot) / 2 - 7.0 * 0.25 / 2 + 0.05
    door_type_view(sh, ex, base, t)
    # text block
    tx = ex + ew + (1.85 if pair else 0.75)
    tw = cx0 + cw - 0.25 - tx
    ty = base + 7.0 * 0.25 + 0.05
    circle_tag(sh, tx + 0.15, ty - 0.12, t)
    sh.text((tx + 0.4, ty - 0.12), f"DOOR TYPE {t}", size=TXT["label"], font=FONT_B, valign="mid")
    ty -= 0.42
    for ln in DOOR_TYPE_NOTES[t]:
        sh.text((tx, ty), ln, size=CELL, valign="top")
        ty -= 0.105
    ty -= 0.06
    h = sh.mtext((tx, ty), "MODEL: " + M.DOOR_TYPES[t], size=CELL, width=tw, leading=CELL * 1.2)
    ty -= h + 0.08
    ids = sorted([o for o in M.doors() if o.type == t], key=lambda o: (o.level, natkey(o.id)))
    sh.mtext((tx, ty), f"USED AT ({len(ids)}): " + used_at([o.id for o in ids]), size=CELL,
             width=tw, leading=CELL * 1.2)


def frame_type_cell(sh, cx0, cw, top, bot, f):
    if f != "SF":
        MOw = {"F1": 2 * FRAME_FACE + 3.0, "F2": 3 * FRAME_FACE + 3.0 + 14 * IN,
               "F3": 2 * FRAME_FACE + 6.0}[f]
        xm = cx0 + 0.95
        base = (top + bot) / 2 - 8.0 * 0.25 / 2 + 0.05
        frame_view(sh, xm, base, f)
        tx = xm + MOw * 0.25 + 0.95
        ty = base + 8.0 * 0.25 + 0.05
    else:
        bx, by = cx0 + 0.45, (top + bot) / 2 - 1.0
        bw, bh = 2.1, 2.0
        sh.rect(bx, by, bw, bh, lw="fine", dash="dashed")
        sh.mtext((bx + bw / 2, by + bh / 2),
                 ["SEE A-711", "STOREFRONT TYPE SF-1", "(DOOR 100B, TYPE E PAIR)"],
                 size=TXT["label"], anchor="c", valign="mid", leading=11)
        tx = bx + bw + 0.4
        ty = by + bh + 0.05
    tw = cx0 + cw - 0.25 - tx
    box_tag(sh, tx + 0.2, ty - 0.12, f)
    sh.text((tx + 0.5, ty - 0.12), "STOREFRONT FRAME" if f == "SF" else f"FRAME TYPE {f}",
            size=TXT["label"], font=FONT_B, valign="mid")
    ty -= 0.42
    lines = FRAME_TYPE_NOTES.get(f, ["DOOR 100B (TYPE E PAIR) IS SET IN SF-1.",
                                      "ELEVATION / DIMENSIONS: SEE A-711.",
                                      "DETAILS: " + ", ".join(DET["SF"]) + "."])
    for ln in lines:
        sh.text((tx, ty), ln, size=CELL, valign="top")
        ty -= 0.105
    ty -= 0.06
    h = sh.mtext((tx, ty), "MODEL: " + M.FRAME_TYPES[f], size=CELL, width=tw, leading=CELL * 1.2)
    ty -= h + 0.08
    sel = sorted([o for o in M.doors() if o.frame == f], key=lambda o: (o.level, natkey(o.id)))
    h = sh.mtext((tx, ty), f"USED AT ({len(sel)}): " + used_at([o.id for o in sel]), size=CELL,
                 width=tw, leading=CELL * 1.2)
    ty -= h + 0.06
    stud = [o.id for o in sel if o.frame != "SF" and o.wall not in M.EXT_SEGS
            and M.WALL_TYPES[host_wall_type(o)]["mat"] == "stud"]
    ext = [o.id for o in sel if o.wall in M.EXT_SEGS and o.frame != "SF"]
    extra = []
    if ext:
        extra.append(f"EXTERIOR (14 GA., GALV.): {', '.join(ext)}")
    if stud:
        extra.append(f"IN METAL STUD WALL (P3): {', '.join(stud)}")
    if extra:
        sh.mtext((tx, ty), extra, size=CELL, width=tw, leading=CELL * 1.2)


def hw_index_rows():
    rows = []
    for k, (name, items) in M.HARDWARE_SETS.items():
        sel = [o for o in M.doors() if o.hw == k]
        rows.append([k, name, f"{len(sel)}", f"{sum(2 if o.pair else 1 for o in sel)}"])
    return rows


def hw_locations_cell(sh, cx0, cw, top, bot):
    """typical hardware mounting locations on a 3'-0" x 7'-0" leaf (DHI)."""
    s = 0.25
    W, H = 3.0, 7.0
    ex = cx0 + 0.95
    base = (top + bot) / 2 - H * s / 2 + 0.05
    v = sh.view(ex, base, s)
    floor_line(v, -0.9, W + 0.9)
    F = FRAME_FACE
    # frame
    v.polyline([(-F, 0), (-F, H + FRAME_HEAD), (W + F, H + FRAME_HEAD), (W + F, 0)], lw="thin")
    v.polyline([(0, 0), (0, H), (W, H), (W, 0)], lw="thin")
    v.rect(0.04, 0.06, W - 0.08, H - 0.06, lw="med")
    hh = 4.5 * IN
    top_h = (H - 5 * IN - hh, H - 5 * IN)
    bot_h = (10 * IN, 10 * IN + hh)
    mid_c = ((top_h[0] + top_h[1]) / 2 + (bot_h[0] + bot_h[1]) / 2) / 2
    mid_h = (mid_c - hh / 2, mid_c + hh / 2)
    for a, b in (top_h, mid_h, bot_h):
        v.rect(-0.6 * IN, a, 1.2 * IN, b - a, lw="fine", fill="g40")
    # lever
    lx = W - 2.75 * IN
    v.circle((lx, 38 * IN), 1.25 * IN, lw="fine")
    v.line((lx, 38 * IN), (lx - 5 * IN, 38 * IN), lw="thin")
    # kick plate (push side)
    v.rect(1 * IN, 0.06, W - 2 * IN, 10 * IN - 0.06, lw="fine", dash="hidden")
    # closer (pull side, dashed)
    v.rect(0.35, H - 7 * IN, 1.1, 3.5 * IN, lw="fine", dash="hidden")
    # push plate / pull alternates
    v.rect(W - 8 * IN, 45 * IN - 8 * IN, 4 * IN, 16 * IN, lw="hair", dash="dot")
    # dims (left: hinges, right: lever, kick plate)
    dim_s(v, (0, top_h[1]), (0, H), 1.0, fmt_in(5), side="u")
    v.dim((0, 0), (0, bot_h[0]), 1.0, text=fmt_in(10))
    D(v, (W, 0), (W, 38 * IN), -0.9)
    dim_s(v, (W, 0), (W, 10 * IN), -1.6, fmt_in(10), side="d")
    D(v, (W, 0), (W, 45 * IN), -2.3)
    D(v, (0, 0), (W, 0), -1.1)
    # text block
    tx = ex + W * s + 1.0
    tw = cx0 + cw - 0.25 - tx
    ty = base + H * s + FRAME_HEAD * s + 0.05
    sh.text((tx, ty - 0.12), "TYPICAL HARDWARE LOCATIONS", size=TXT["label"], font=FONT_B,
            valign="mid")
    ty -= 0.32
    lines = [
        "PER DHI \"RECOMMENDED LOCATIONS FOR ARCH.",
        "HARDWARE FOR STANDARD STEEL / WOOD DOORS\".",
        "TOP HINGE: 5\" HEAD RABBET TO TOP OF HINGE.",
        "BOTTOM HINGE: 10\" FFL TO BOTTOM OF HINGE.",
        "INTERMEDIATE HINGE(S): EQUALLY SPACED.",
        "LEVER / EXIT DEVICE C/L: 3'-2\" AFF",
        "(34\" - 48\" AFF, ICC A117.1 404.2.7).",
        "PUSH PLATE C/L 3'-9\" AFF (DOTTED); PULL C/L 3'-6\".",
        "KICK PLATE 10\" HIGH x LEAF WIDTH LESS 2\",",
        "PUSH SIDE (DASHED). CLOSER PER TEMPLATE.",
    ]
    for ln in lines:
        sh.text((tx, ty), ln, size=CELL, valign="top")
        ty -= 0.105


def frame_profile_cell(sh, cx0, cw, top, bot):
    """typical HM double-rabbet jamb profile in CMU (horizontal section) at 3" = 1'-0"."""
    s = 3.0
    D = 7.75 * IN       # jamb depth, butted in 7 5/8" CMU
    face = 2 * IN
    r1 = 1.9375 * IN    # door rabbet
    stop = 0.625 * IN
    sw = 2.0 * IN       # stop face
    bb = 0.5 * IN       # backbend
    cmu = M.CMU_T
    stub = 4.5 * IN
    dstub = 4.0 * IN
    # model coords: x = through the wall (push face x=0), y = across (MO edge y=0, opening y>0)
    ox = cx0 + 0.75
    oy = (top + bot) / 2 - 0.15
    v = sh.view(ox, oy, s)
    x_c0 = (D - cmu) / 2
    v.polygon([(x_c0, 0), (x_c0 + cmu, 0), (x_c0 + cmu, -stub), (x_c0, -stub)], lw=None,
              hatch="ansi31", hatch_kw=dict(spacing=0.06), stroke=False)
    v.line((x_c0, 0), (x_c0, -stub), lw="thin")
    v.line((x_c0 + cmu, 0), (x_c0 + cmu, -stub), lw="thin")
    from .cad import break_line
    break_line(v, (x_c0 - 0.4 * IN, -stub), (x_c0 + cmu + 0.4 * IN, -stub), zig=0.06)
    v.polygon([(bb, 0.03 * IN), (D - bb, 0.03 * IN), (D - bb, face - 0.06 * IN),
               (bb, face - 0.06 * IN)], lw=None, hatch="sand", stroke=False)
    prof = [(bb, 0), (0, 0), (0, face), (r1, face), (r1, face + stop), (r1 + sw, face + stop),
            (r1 + sw, face), (D, face), (D, 0), (D - bb, 0)]
    v.polyline(prof, lw="heavy", join=1)
    # door leaf in rabbet (1 3/4")
    d0 = r1 - DOOR_THK * IN
    yd = face + 0.125 * IN
    v.polygon([(d0, yd), (r1, yd), (r1, yd + dstub), (d0, yd + dstub)], lw="thin", fill="g10")
    break_line(v, (d0 - 0.4 * IN, yd + dstub), (r1 + 0.4 * IN, yd + dstub), zig=0.05)
    # masonry anchor (T-strap) in the throat
    v.polyline([(D / 2 - 1.0 * IN, 0.4 * IN), (D / 2 - 1.0 * IN, -2.5 * IN),
                (D / 2 + 1.0 * IN, -2.5 * IN), (D / 2 + 1.0 * IN, 0.4 * IN)], lw="thin")
    # dims
    v.dim((0, face + stop), (D, face + stop), 4.0 * IN, text=fmt_in(7.75) + " JAMB DEPTH")
    dim_s(v, (0, face + stop), (r1, face + stop), 2.0 * IN, fmt_in(1.9375), side="l")
    dim_s(v, (r1, face + stop), (r1 + sw, face + stop), 2.0 * IN, fmt_in(2), side="r")
    v.dim((x_c0, -stub), (x_c0 + cmu, -stub), -1.8 * IN, text=fmt_in(7.625) + " CMU")
    dim_s(v, (0, 0), (0, face), 1.4 * IN, fmt_in(2), side="d")
    dim_s(v, (0, face), (0, face + stop), 2.6 * IN, fmt_in(0.625), side="u")
    # labels
    lx = D + 2.2 * IN
    for tip, yl, txt in (((r1 + sw * 0.6, face + stop), face + 2.6 * IN, "16 GA. HM FRAME, 5/8\" STOP"),
                         ((r1 - 0.4 * IN, yd + 2.4 * IN), yd + 4.2 * IN, "1 3/4\" DOOR"),
                         ((D * 0.7, face * 0.5), face * 0.35, "GROUT / MORTAR SOLID"),
                         ((D / 2 + 1.0 * IN, -1.6 * IN), -1.6 * IN, "MASONRY T-ANCHOR"),
                         ((x_c0 + cmu * 0.8, -3.5 * IN), -3.4 * IN, "8\" CMU (P1 / P2 / EW-1)")):
        v.leader([tip, (lx, yl)], txt, size=TXT["small"])
    tx = ox + D * s + 2.05
    tw = cx0 + cw - 0.2 - tx
    ty = oy + (face + stop + 4.0 * IN) * s + 0.05
    sh.text((tx, ty), "TYPICAL HM JAMB PROFILE", size=TXT["label"], font=FONT_B, valign="mid")
    sh.text((tx, ty - 0.17), "SCALE: 3\" = 1'-0\"", size=TXT["small"], valign="mid")
    lines = ["DOUBLE RABBET FRAME, BUTTED", "IN CMU (P1, P2, EW-1 BACKUP):",
             "7 3/4\" JAMB DEPTH.", "AT P3 METAL STUD WALL:", "WRAP-AROUND FRAME, 5 3/4\"",
             "JAMB DEPTH, 1/2\" BACKBENDS.", "HEAD PROFILE SIMILAR WITH", "4\" FACE.",
             "SEE 5/A-502 THRU 8/A-502."]
    ty -= 0.4
    for ln in lines:
        sh.text((tx, ty), ln, size=CELL, valign="top")
        ty -= 0.105


def draw_a701(sh):
    x0, y0, x1, y1 = sh.x0, sh.y0, sh.x1, sh.y1
    # ---------------- door schedule (top-left) ----------------
    tx, ty = x0 + 0.25, y1 - 0.2
    rows = door_schedule_rows()
    al = ["c", "l", "l", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c",
          "c", "c", "c", "l"]
    k = 7.0 / 6.0
    cols = [(h, w * k) for h, w in DOOR_COLS]
    th = sched_table(sh, tx, ty, cols, rows, title="DOOR SCHEDULE", groups=DOOR_GROUPS,
                     align=al, row_h=0.232, size=7.0, hsize=6.5,
                     title_note="ALL LEAVES 1 3/4\" THICK  |  SEE DOOR AND FRAME GENERAL NOTES")
    sch_w = table_w(cols)
    sch_bot = ty - th
    sh.text((tx, sch_bot - 0.1),
            "ABBREVIATIONS:  WD = WOOD   HM = HOLLOW METAL   AL = ALUMINUM   FACT. FIN. = FACTORY "
            "FINISH   PAINT = FIELD PAINTED   CL. ANOD. = CLASS I CLEAR ANODIZED   PR = PAIR   "
            "MO = MASONRY OPENING   SIM = SIMILAR   - = NONE / NOT APPLICABLE",
            size=TXT["small"], valign="top")

    # ---------------- right column: summaries, glass, detail key, notes ----------------
    rx = tx + sch_w + 0.45
    rw = x1 - 0.2 - rx
    t_rows, f_rows, r_rows = door_summary_rows()
    cy = ty
    c1 = [("DOOR\nTYPE", 0.5), ("SINGLE", 0.55), ("PAIR", 0.45), ("LEAVES", 0.58),
          ("OPNGS.", 0.55)]
    c2 = [("FRAME\nTYPE", 0.5), ("MO (W x H)", 1.3), ("L1", 0.42), ("L2", 0.42), ("TOTAL", 0.5)]
    w3 = rw - table_w(c1) - table_w(c2) - 0.5
    c3 = [("SET", 0.55), ("FUNCTION", w3 - 0.55 - 1.1), ("OPNGS.", 0.55), ("LEAVES", 0.55)]
    h1 = sched_table(sh, rx, cy, c1, t_rows, title="DOOR TYPE COUNT", row_h=0.19)
    xb = rx + table_w(c1) + 0.25
    h2 = sched_table(sh, xb, cy, c2, f_rows, title="FRAME TYPE COUNT", row_h=0.19)
    xc = xb + table_w(c2) + 0.25
    hw_rows = hw_index_rows()
    h3 = sched_table(sh, xc, cy, c3, hw_rows, title="HARDWARE SETS (SEE A-702)", row_h=0.17,
                     align=["c", "l", "c", "c"])
    # fire-rated table under the two count tables
    cyf = cy - max(h1, h2) - 0.25
    c4 = [("RATING", 0.75), ("OPNGS.", 0.6), ("DOOR NUMBERS", table_w(c1) + table_w(c2) + 0.25
                                                - 1.35)]
    h4 = sched_table(sh, rx, cyf, c4, r_rows, title="FIRE-RATED OPENINGS", row_h=0.19,
                     align=["c", "c", "l"])
    cy = min(cyf - h4, cy - h3) - 0.28
    g_rows = [[k_, v_] for k_, v_ in GLASS_TYPES.items()]
    h5 = sched_table(sh, rx, cy, [("TAG", 0.6), ("GLASS TYPE DESCRIPTION", rw - 0.6)], g_rows,
                     title="GLASS TYPES", row_h=0.19, align=["c", "l"])
    cy -= h5 + 0.28
    k_rows = [[a_, b_] for a_, b_ in DETAIL_KEY if "A-502" in a_] + \
             [[a_, b_] for a_, b_ in DETAIL_KEY if a_ in ("1/A-501", "2/A-501", "4/A-501",
                                                          "5/A-501", "6/A-501")]
    half = (len(k_rows) + 1) // 2
    kw = (rw - 0.25) / 2
    kc = [("DETAIL", 0.62), ("TITLE", kw - 0.62)]
    hk1 = sched_table(sh, rx, cy, kc, k_rows[:half], title="DOOR / FRAME DETAIL KEY",
                      row_h=0.19, align=["c", "l"])
    hk2 = sched_table(sh, rx + kw + 0.25, cy, kc, k_rows[half:], title="DETAIL KEY (CONT.)",
                      row_h=0.19, align=["c", "l"])
    cy -= max(hk1, hk2) + 0.1
    hh = sh.mtext((rx, cy), "EXTERIOR HM OPENINGS (ST1-B, ST2-B, 112): HEAD, JAMB AND THRESHOLD "
                  "SIMILAR TO THE DETAILS NOTED, WITH STEEL LINTEL (S-302) AND THROUGH-WALL "
                  "FLASHING WITH END DAMS AT HEAD.", size=TXT["small"], width=rw)
    cy -= hh + 0.3
    elev = ", ".join(f"{o.id} ({ft(o.leaf)} WIDE, MO {size_txt(o.w, o.head - o.sill)})"
                     for o in M.OPENINGS if o.kind == "elevator")
    notes = [n.replace("{elev}", elev) for n in A701_NOTES]
    notes_cols(sh, rx, cy, "DOOR AND FRAME GENERAL NOTES", notes, rw, ncols=3, gap=0.3)

    # ---------------- lower band: door types row + frame types row ----------------
    band_top = sch_bot - 0.42
    sh.line((x0, band_top), (x1, band_top), lw="thin")
    row_h = (band_top - y0) / 2
    W = x1 - x0
    # door types + typical hardware locations
    types = list(M.DOOR_TYPES)
    widths = {t: (W - 6.9 - 6.3) / 4 for t in types}
    widths["E"] = 6.9
    acc = x0
    r1_top, r1_bot = band_top, band_top - row_h
    for t in types:
        door_type_cell(sh, acc, widths[t], r1_top - 0.1, r1_bot + 0.55, t)
        acc += widths[t]
        sh.line((acc, r1_top - 0.25), (acc, r1_bot + 0.6), lw="hair", color="g40")
    hw_locations_cell(sh, acc, x1 - acc, r1_top - 0.1, r1_bot + 0.55)
    sh.view_title(x0 + 0.25, r1_bot + 0.3, 2, "DOOR TYPES", 0.25, width=6.0,
                  note="ELEVATIONS FROM PUSH SIDE / EXTERIOR")
    sh.line((x0, r1_bot), (x1, r1_bot), lw="thin")
    # frame types + typical profile
    ftypes = ["F1", "F2", "F3", "SF"]
    fw = {"F1": 5.9, "F2": 6.5, "F3": 6.9, "SF": 5.4}
    acc = x0
    for f in ftypes:
        frame_type_cell(sh, acc, fw[f], r1_bot - 0.1, y0 + 0.55, f)
        acc += fw[f]
        sh.line((acc, r1_bot - 0.25), (acc, y0 + 0.6), lw="hair", color="g40")
    frame_profile_cell(sh, acc, x1 - acc, r1_bot - 0.1, y0 + 0.55)
    sh.view_title(x0 + 0.25, y0 + 0.3, 3, "FRAME TYPES", 0.25, width=6.0,
                  note="DIMENSIONS ARE MO / FRAME FACE")


# ========================================================================================
# A-702 DOOR HARDWARE SETS
# ========================================================================================
# keyword -> (BHMA standard, finish). First match wins (order matters).
HW_REF = [
    ("CONTINUOUS", ("A156.26 GR.1", "628")),
    ("HINGE", ("A156.1 GR.1", "630")),
    ("CLASSROOM SECURITY", ("A156.13 GR.1", "626")),
    ("PRIVACY", ("A156.13 GR.1", "626")),
    ("STOREROOM", ("A156.13 GR.1", "626")),
    ("OFFICE LOCKSET", ("A156.13 GR.1", "626")),
    ("REMOVABLE MULLION", ("A156.3 GR.1", "689")),
    ("EXIT DEVICE", ("A156.3 GR.1", "626")),
    ("OPERATOR", ("A156.19", "628")),
    ("CLOSER", ("A156.4 GR.1", "689")),
    ("ELEC. STRIKE", ("A156.31 GR.1", "630")),
    ("KICK PLATE", ("A156.6", "630")),
    ("PUSH PLATE", ("A156.6", "630")),
    ("PUSH/PULL", ("A156.6", "630")),
    ("PULL", ("A156.6", "630")),
    ("WALL STOP", ("A156.16", "626")),
    ("SILENCER", ("A156.16", "GRY")),
    ("COAT HOOK", ("A156.16", "626")),
    ("THRESHOLD", ("A156.21", "628")),
    ("WEATHERSTRIP", ("A156.22", "628")),
    ("GASKET", ("A156.22", "BLK")),
    ("SWEEP", ("A156.22", "628")),
    ("RAIN DRIP", ("A156.22", "628")),
    ("ASTRAGAL", ("A156.22", "628")),
    ("HOLD-OPEN", ("A156.15 GR.1", "689")),
    ("POSITION SWITCH", ("BY DIV. 28", "-")),
    ("SIGN", ("-", "-")),
]

HW_OPERATION = {
    "HW-1": "CLASSROOM SECURITY: OUTSIDE LEVER LOCKED OR UNLOCKED BY KEY FROM EITHER SIDE (LOCK-DOWN "
            "FROM INSIDE THE ROOM). INSIDE LEVER ALWAYS FREE FOR EGRESS. SELF-CLOSING.",
    "HW-2": "PUSH / PULL, NON-LATCHING, NO LOCKING. DOOR SELF-CLOSING; WALL STOP PROTECTS TILE.",
    "HW-3": "PRIVACY: INSIDE THUMBTURN LOCKS OUTSIDE LEVER AND SHOWS \"OCCUPIED\"; EMERGENCY "
            "RELEASE OUTSIDE. INSIDE LEVER ALWAYS FREE.",
    "HW-4": "EXIT DEVICE ON EGRESS SIDE ALWAYS FREE. PASSAGE LEVER TRIM ON STAIR SIDE, NEVER LOCKED "
            "(STAIR RE-ENTRY, IBC 1010.2.6). SELF-CLOSING, POSITIVE LATCHING, 60 MIN LABEL.",
    "HW-5": "EXIT DEVICE ALWAYS FREE EGRESS. OUTSIDE NIGHT LATCH TRIM: KEY RETRACTS LATCH. DOOR "
            "POSITION MONITORED BY ACCESS CONTROL / INTRUSION (DIV. 28).",
    "HW-6": "BOTH LEAVES ACTIVE ON KEYED REMOVABLE MULLION; NIGHT LATCH TRIM ON ACTIVE LEAF, DUMMY "
            "TRIM ON OTHER. MULLION REMOVED FOR EQUIPMENT REPLACEMENT.",
    "HW-7": "CARD READER (DIV. 28) RELEASES DOORS DURING SCHEDULED HOURS; KEY OVERRIDE; FREE EGRESS "
            "AT ALL TIMES. LOW-ENERGY OPERATOR ON ONE LEAF WITH ACTUATORS BOTH SIDES (DIV. 26 POWER).",
    "HW-8": "LEAVES HELD OPEN ON MAGNETIC HOLDERS; RELEASE ON FIRE ALARM OR POWER FAILURE AND "
            "SELF-CLOSE. PUSH / PULL, NON-LATCHING, NON-RATED.",
    "HW-9": "STOREROOM: OUTSIDE LEVER ALWAYS LOCKED, KEY RETRACTS LATCH. INSIDE LEVER ALWAYS FREE. "
            "SELF-CLOSING.",
    "HW-10": "OFFICE: PUSH-BUTTON INSIDE LOCKS OUTSIDE LEVER UNTIL INSIDE LEVER IS TURNED OR KEY "
             "IS USED OUTSIDE. INSIDE LEVER ALWAYS FREE.",
}

ELEC_KEYS = ("ELEC", "CARD", "MAGNETIC", "OPERATOR", "POSITION SWITCH")


def hw_item(line):
    m = re.match(r"^(\d+)\s+(EA|SET|PR)\s+(.*)$", line.strip())
    if m:
        q, u, d = m.groups()
    else:
        q, u, d = "1", "EA", line.strip()
    ref = ("-", "-")
    up = d.upper()
    for k, r in HW_REF:
        if k in up:
            ref = r
            break
    return [q, u, d, ref[0], ref[1]]


def hw_doors(k):
    return sorted([o for o in M.doors() if o.hw == k], key=lambda o: (o.level, natkey(o.id)))


HW_COLS = [("QTY.", 0.45), ("UNIT", 0.5), ("DESCRIPTION", 5.05), ("BHMA STD.", 1.15),
           ("FIN.", 0.55)]

# keying rule per set: (key group, keying, cylinders per opening)
HW_KEYING = OrderedDict([
    ("HW-1", ("KG-1", "KEYED DIFFERENT, UNDER BUILDING MASTER (CLASSROOM SECURITY: OUTSIDE + INSIDE)", 2)),
    ("HW-10", ("KG-2", "KEYED ALIKE - STAFF, UNDER BUILDING MASTER", 1)),
    ("HW-9", ("KG-3", "KEYED ALIKE - CUSTODIAL / STOREROOM, UNDER GRAND MASTER", 1)),
    ("HW-6", ("KG-3", "KEYED ALIKE - CUSTODIAL (NIGHT LATCH + REMOVABLE MULLION)", 2)),
    ("HW-5", ("KG-4", "KEYED ALIKE - EXTERIOR, UNDER GRAND MASTER (NIGHT LATCH)", 1)),
    ("HW-7", ("KG-4", "KEYED ALIKE - EXTERIOR (KEY OVERRIDE / DOGGING)", 1)),
    ("HW-3", ("-", "NO CYLINDER - EMERGENCY RELEASE TOOL (TURN-SLOT)", 0)),
    ("HW-2", ("-", "NO CYLINDER - PUSH / PULL", 0)),
    ("HW-4", ("-", "NO CYLINDER - PASSAGE TRIM, FIRE EXIT HARDWARE (NO DOGGING)", 0)),
    ("HW-8", ("-", "NO CYLINDER - PUSH / PULL ON HOLD-OPENS", 0)),
])


def hw_set_rows(k):
    name, items = M.HARDWARE_SETS[k]
    rows = [hw_item(it) for it in items]
    ds = hw_doors(k)
    rows.append({"span": HW_OPERATION.get(k, "-"), "label": "OPERATION:", "fill": "g05"})
    rows.append({"span": ", ".join(o.id for o in ds), "label": f"OPENINGS ({len(ds)}):"})
    return rows


def hw_set_table(sh, x, y, k, draw=True):
    name, items = M.HARDWARE_SETS[k]
    ds = hw_doors(k)
    leaves = sum(2 if o.pair else 1 for o in ds)
    rated = sorted({o.rating for o in ds if o.rating})
    note = f"{len(ds)} OPENING{'S' if len(ds) != 1 else ''} / {leaves} LEAVES"
    if rated:
        note += "  |  " + ", ".join(rated) + " LABELED"
    return sched_table(sh, x, y, HW_COLS, hw_set_rows(k), title=f"{k}   {name}", title_note=note,
                       size=7.5, hsize=6.75, row_h=0.325, align=["c", "c", "l", "c", "c"],
                       draw=draw, title_h=0.32)


A702_NOTES = [
    "##GENERAL",
    "HARDWARE SHALL COMPLY WITH ANSI/BHMA A156 SERIES, GRADE 1 UNLESS NOTED, AND BE FURNISHED BY A "
    "SINGLE SUPPLIER EMPLOYING A DHI ARCHITECTURAL HARDWARE CONSULTANT (AHC). SUBMIT A HARDWARE "
    "SCHEDULE IN DHI SEQUENCE AND FORMAT, KEYED TO THE DOOR NUMBERS ON A-701.",
    "QUANTITIES LISTED IN EACH SET ARE PER OPENING (PAIRS INCLUDE BOTH LEAVES). SETS ARE ASSIGNED "
    "TO OPENINGS IN THE DOOR SCHEDULE, A-701. MANUFACTURER-NEUTRAL: PROVIDE PRODUCTS MEETING THE "
    "REFERENCED BHMA STANDARD AND FUNCTION.",
    "FINISHES (BHMA A156.18): 626 SATIN CHROMIUM PLATED (LOCKS, EXIT DEVICE TRIM, STOPS); 630 SATIN "
    "STAINLESS STEEL (HINGES, PROTECTION PLATES, PUSH/PULLS); 628 SATIN CLEAR ANODIZED ALUMINUM "
    "(THRESHOLDS, SEALS, CONTINUOUS HINGES); 689 ALUMINUM PAINTED (CLOSERS, HOLDERS).",
    "TEMPLATES: FURNISH HARDWARE TEMPLATES TO THE DOOR AND FRAME MANUFACTURERS WITHIN 14 DAYS OF "
    "APPROVED HARDWARE SCHEDULE. PROVIDE REINFORCEMENT FOR CLOSERS, EXIT DEVICES AND HOLDERS.",
    "##KEYING",
    "KEY ALL CYLINDERS INTO THE OWNER'S EXISTING DISTRICT MASTER KEY SYSTEM (INTERCHANGEABLE CORE). "
    "HOLD A KEYING MEETING WITH THE OWNER; SUBMIT A KEYING SCHEDULE FOR APPROVAL.",
    "USE TEMPORARY CONSTRUCTION CORES DURING CONSTRUCTION; PERMANENT CORES SET BY THE SUPPLIER AT "
    "SUBSTANTIAL COMPLETION. FURNISH 3 CHANGE KEYS PER CYLINDER AND 6 MASTER KEYS; DELIVER KEYS "
    "TO THE OWNER BY SECURE SHIPMENT.",
    "##ACCESSIBILITY AND LIFE SAFETY",
    "ALL OPERATING TRIM SHALL BE LEVER OR PUSH/PULL TYPE OPERABLE WITH ONE HAND WITHOUT TIGHT "
    "GRASPING, PINCHING OR TWISTING OF THE WRIST, MOUNTED 34\" - 48\" AFF (ICC A117.1-2017 404.2.7; "
    "ILLINOIS ACCESSIBILITY CODE).",
    "ADJUST CLOSERS: INTERIOR DOORS 5 LBF MAX. OPENING FORCE; EXTERIOR DOORS 8.5 LBF MAX.; FIRE DOORS "
    "THE MINIMUM FORCE THAT RELIABLY CLOSES AND LATCHES. CLOSING SPEED 5 SEC MIN. FROM 90 TO 12 "
    "DEGREES.",
    "RATED OPENINGS: LISTED FIRE EXIT HARDWARE (UL 10C / UL 305), POSITIVE LATCHING, SELF-CLOSING, "
    "NO HOLD-OPENS EXCEPT FIRE-ALARM-RELEASED. INSTALL PER NFPA 80.",
    "EXIT DEVICES: UL 305 PANIC HARDWARE ON ALL EXIT AND STAIR DOORS. ACTUATING PORTION 34\" - 48\" AFF, "
    "AT LEAST HALF THE LEAF WIDTH. THRESHOLDS 1/2\" MAX. HIGH, BEVELED 1:2 (ICC A117.1 303).",
    "##ELECTRIFIED HARDWARE",
    "COORDINATE ELECTRIFIED HARDWARE WITH DIV. 26 (120 V POWER, RACEWAYS, BOXES) AND DIV. 28 (ACCESS "
    "CONTROL, CARD READERS, DOOR POSITION SWITCHES, FIRE ALARM RELEASE). FURNISH WIRING / RISER "
    "DIAGRAMS AND OPERATIONAL NARRATIVES FOR EACH ELECTRIFIED OPENING.",
    "PROVIDE CONCEALED RACEWAY FROM HINGE OR TRANSFER DEVICE TO JUNCTION BOX ABOVE CEILING; FRAMES "
    "AT ELECTRIFIED OPENINGS RECEIVE MORTAR GUARDS AND ARE NOT GROUT-FILLED AT WIRE PATHS.",
    "##INSTALLATION",
    "MOUNT HARDWARE PER DHI RECOMMENDED LOCATIONS (SEE A-701). WALL STOPS AT ALL DOORS THAT WOULD "
    "STRIKE A WALL; ANCHOR TO SOLID BLOCKING / GROUTED CMU. SET THRESHOLDS IN FULL BED OF SEALANT.",
    "WARRANTY: CLOSERS 10 YEARS, EXIT DEVICES 3 YEARS, LOCKSETS 3 YEARS, CONTINUOUS HINGES LIFETIME. "
    "PROVIDE AN ADJUSTMENT VISIT 6 MONTHS AFTER OCCUPANCY.",
]

FIN_LEGEND = [
    ("626", "SATIN CHROMIUM PLATED (BRASS / BRONZE BASE)", "LOCKSETS, LEVERS, EXIT DEVICE TRIM, STOPS"),
    ("628", "SATIN CLEAR ANODIZED ALUMINUM", "THRESHOLDS, WEATHERSTRIP, SWEEPS, CONT. HINGES"),
    ("630", "SATIN STAINLESS STEEL (300 SERIES)", "BUTT HINGES, PLATES, PUSH / PULLS, STRIKES"),
    ("689", "ALUMINUM PAINTED", "CLOSERS, HOLDERS, REMOVABLE MULLION"),
    ("GRY / BLK", "GRAY RUBBER / BLACK GASKET", "SILENCERS / SMOKE GASKETING"),
]

BHMA_LEGEND = [
    ("A156.1", "BUTTS AND HINGES"), ("A156.3", "EXIT DEVICES, REMOVABLE MULLIONS"),
    ("A156.4", "DOOR CONTROLS - CLOSERS"), ("A156.6", "ARCHITECTURAL DOOR TRIM"),
    ("A156.13", "MORTISE LOCKS AND LATCHES"), ("A156.15", "RELEASE DEVICES - HOLDERS"),
    ("A156.16", "AUXILIARY HARDWARE (STOPS, SILENCERS, HOOKS)"), ("A156.18", "MATERIALS AND FINISHES"),
    ("A156.19", "POWER ASSIST / LOW ENERGY OPERATORS"), ("A156.21", "THRESHOLDS"),
    ("A156.22", "DOOR GASKETING AND EDGE SEAL SYSTEMS"), ("A156.26", "CONTINUOUS HINGES"),
    ("A156.31", "ELECTRIC STRIKES AND FRAME MOUNTED ACTUATORS"),
]


def elec_rows():
    rows = []
    for k, (name, items) in M.HARDWARE_SETS.items():
        el = [it for it in items if any(e in it.upper() for e in ELEC_KEYS)]
        if not el:
            continue
        ds = hw_doors(k)
        rows.append([k, ", ".join(o.id for o in ds), "; ".join(re.sub(r"^\d+\s+(EA|SET)\s+", "", e)
                                                         for e in el)])
    return rows


def keying_rows():
    rows = []
    for k, (grp, desc, cyl) in HW_KEYING.items():
        if k not in M.HARDWARE_SETS:
            continue
        ds = hw_doors(k)
        rows.append([grp, k, desc, f"{cyl}", ", ".join(o.id for o in ds)])
    return rows


def draw_a702(sh):
    x0, y0, x1, y1 = sh.x0, sh.y0, sh.x1, sh.y1
    keys = list(M.HARDWARE_SETS)
    heights = {k: hw_set_table(sh, 0, 0, k, draw=False) for k in keys}
    tw = table_w(HW_COLS)
    # two columns, sets in order, split to balance heights
    tot = sum(heights[k] for k in keys)
    colA, colB = [], []
    acc = 0
    for k in keys:
        if not colB and acc + heights[k] / 2 <= tot / 2:
            colA.append(k)
            acc += heights[k]
        else:
            colB.append(k)
    xA = x0 + 0.25
    xB = xA + tw + 0.4
    top, bot = y1 - 0.2, y0 + 0.85
    for xx, col in ((xA, colA), (xB, colB)):
        hsum = sum(heights[k] for k in col)
        g = min(0.9, (top - bot - hsum) / max(1, len(col) - 1))
        cy = top
        for k in col:
            hw_set_table(sh, xx, cy, k)
            cy -= heights[k] + g
    sh.view_title(xA, y0 + 0.3, 1, "DOOR HARDWARE SETS", "NOT TO SCALE", width=6.0,
                  note="QUANTITIES ARE PER OPENING; SEE A-701 FOR DOOR ASSIGNMENTS")
    # right column
    rx = xB + tw + 0.55
    rw = x1 - 0.2 - rx
    sh.line((rx - 0.28, y0 + 0.1), (rx - 0.28, y1 - 0.1), lw="thin")
    cy = y1 - 0.2
    h = notes_cols(sh, rx, cy, "DOOR HARDWARE GENERAL NOTES", A702_NOTES, rw, ncols=2, gap=0.3)
    cy -= h + 0.35
    half = (rw - 0.3) / 2
    fc = [("FINISH", 0.7), ("DESCRIPTION", 2.0), ("TYPICAL USE", half - 2.7)]
    h1 = sched_table(sh, rx, cy, fc, [list(r) for r in FIN_LEGEND],
                     title="HARDWARE FINISHES (BHMA A156.18)", size=6.5, row_h=0.25,
                     align=["c", "l", "l"])
    bc = [("STANDARD", 0.85), ("TITLE", half - 0.85)]
    h2 = sched_table(sh, rx + half + 0.3, cy, bc, [list(r) for r in BHMA_LEGEND],
                     title="REFERENCED BHMA STANDARDS", size=6.5, row_h=0.25, align=["c", "l"])
    ec = [("SET", 0.55), ("OPENINGS", 0.95), ("ELECTRIFIED ITEMS (DIV. 26 / 28)", half - 1.5)]
    h3 = sched_table(sh, rx, cy - h1 - 0.3, ec, elec_rows(), title="ELECTRIFIED OPENINGS",
                     size=6.5, row_h=0.25, align=["c", "c", "l"])
    cy -= max(h1 + 0.3 + h3, h2) + 0.35
    kc = [("KEY\nGROUP", 0.6), ("SET", 0.55), ("KEYING", rw - 0.6 - 0.55 - 0.85 - 3.4),
          ("CYL. PER\nOPENING", 0.85), ("OPENINGS", 3.4)]
    h4 = sched_table(sh, rx, cy, kc, keying_rows(), title="KEYING SCHEDULE (EXISTING DISTRICT "
                     "MASTER KEY SYSTEM, INTERCHANGEABLE CORE)", size=6.5, row_h=0.25,
                     align=["c", "c", "l", "c", "l"])
    cy -= h4 + 0.4
    # opening index (door -> set), generated
    ds = sorted(M.doors(), key=lambda o: (o.level, natkey(o.id)))
    n = len(ds)
    ncol = 2
    per = math.ceil(n / ncol)
    iw = (rw - 0.3 * (ncol - 1)) / ncol
    ic = [("DOOR", 0.6), ("ROOM (TO)", iw - 0.6 - 0.6 - 0.5 - 0.55 - 0.65), ("SET", 0.6),
          ("TYPE", 0.5), ("FRAME", 0.55), ("RATING", 0.65)]
    sh.text((rx, cy), "OPENING / HARDWARE SET INDEX (GENERATED FROM DOOR SCHEDULE A-701)",
            size=TXT["label"], font=FONT_B, valign="top", underline=True)
    cy -= 0.28
    hmax = 0
    for i in range(ncol):
        part = ds[i * per:(i + 1) * per]
        rows = [[o.id, room_label(door_rooms(o)[0]), o.hw, o.type, o.frame, o.rating or "-"]
                for o in part]
        hmax = max(hmax, sched_table(sh, rx + i * (iw + 0.3), cy, ic, rows, size=6.5,
                                     row_h=0.235, align=["c", "l", "c", "c", "c", "c"]))
    cy -= hmax + 0.4
    ab = [("AHC", "ARCHITECTURAL HARDWARE CONSULTANT (DHI)"), ("BHMA", "BUILDERS HARDWARE MFRS. ASSN."),
          ("CVR", "CONCEALED VERTICAL ROD"), ("DPS", "DOOR POSITION SWITCH"),
          ("EA / SET", "EACH / SET (PER OPENING)"), ("FACP", "FIRE ALARM CONTROL PANEL"),
          ("FFL / AFF", "FINISH FLOOR LINE / ABOVE FIN. FLOOR"), ("GR.", "BHMA GRADE"),
          ("IC", "INTERCHANGEABLE CORE"), ("LBF", "POUNDS-FORCE"),
          ("LDW", "LESS DOOR WIDTH"), ("NL", "NIGHT LATCH (EXIT DEVICE TRIM)")]
    hh = (len(ab) + 1) // 2
    acols = [("ABBR.", 0.85), ("MEANING", iw - 0.85)]
    sched_table(sh, rx, cy, acols, [list(r) for r in ab[:hh]], title="HARDWARE ABBREVIATIONS",
                size=6.5, row_h=0.235, align=["c", "l"])
    sched_table(sh, rx + iw + 0.3, cy, acols, [list(r) for r in ab[hh:]],
                title="HARDWARE ABBREVIATIONS (CONT.)", size=6.5, row_h=0.235, align=["c", "l"])


# ========================================================================================
# A-711 WINDOW & STOREFRONT TYPES
# ========================================================================================
JOINT = 0.5 * IN          # perimeter sealant joint MO -> frame
MULL = 2 * IN             # 2" x 4 1/2" frame / mullion face
VENT_CL = 2 + 4 * IN      # W-A / W-B: c/l of vent rail above MO sill (= elevations VENT_H)
SF_TRANSOM_W = 4 * IN     # SF-1 / SF-3 transom bar face (door head 7'-0" AFF)
SF_TRANSOM_CL = 7.0 + SF_TRANSOM_W / 2   # transom bar c/l above MO sill (FFE)
SF_BOTTOM_RAIL = 10 * IN  # SF-1 sidelite bottom rail (matches door bottom rail)
ELEV_GROUP = {"N": "N", "S": "S", "E": "E", "W1": "W", "W2": "W", "W0": "W", "LN": "LINK N",
              "LS": "LINK S"}


def win_layout(t):
    """frame, mullion and lite layout of a window / storefront type (MO coords, ft).
    Mullion / rail positions match the exterior elevations (sheets_arch_elev: VENT_H, SF_TRANSOM,
    MO-based bay divisions) and the plan renderer."""
    W, H = M.WINDOW_TYPES[t]["mo"]
    fx0, fx1 = JOINT, W - JOINT
    fy0 = 0.0 if t == "SF-1" else JOINT
    fy1 = H - JOINT
    vcl, hcl, vents, door = [], [], [], None
    hw = {}                      # horizontal member face width by index (default MULL)
    sill_rail = {}               # (i, j) -> bottom rail height above MO sill
    if t == "W-A":
        vcl = [W / 2]
        hcl = [VENT_CL]
        vents = [(0, 0), (1, 0)]
    elif t == "W-B":
        hcl = [VENT_CL]
        vents = [(0, 0)]
    elif t == "W-C":
        n = 4
        hcl = [H * k / n for k in range(1, n)]
    elif t == "SF-1":
        vcl = [W / 2 - 3.0 - MULL / 2, W / 2 + 3.0 + MULL / 2]
        hcl = [SF_TRANSOM_CL]
        hw = {0: SF_TRANSOM_W}
        door = (1, 0)
        sill_rail = {(0, 0): SF_BOTTOM_RAIL, (2, 0): SF_BOTTOM_RAIL}
    elif t == "SF-2":
        vcl = [W / 3, 2 * W / 3]
    elif t == "SF-3":
        n = 6
        vcl = [W * k / n for k in range(1, n)]
        hcl = [SF_TRANSOM_CL]
        hw = {0: SF_TRANSOM_W}
    xs = [fx0] + vcl + [fx1]
    ys = [fy0] + hcl + [fy1]
    lites = []
    for i in range(len(xs) - 1):
        lx0 = xs[i] + (MULL if i == 0 else MULL / 2)
        lx1 = xs[i + 1] - (MULL if i == len(xs) - 2 else MULL / 2)
        for j in range(len(ys) - 1):
            ly0 = ys[j] + (MULL if j == 0 else hw.get(j - 1, MULL) / 2)
            ly1 = ys[j + 1] - (MULL if j == len(ys) - 2 else hw.get(j, MULL) / 2)
            if door == (i, j):
                continue
            if (i, j) in sill_rail:
                ly0 = max(ly0, sill_rail[(i, j)])
            lites.append((i, j, lx0, ly0, lx1, ly1))
    return dict(W=W, H=H, fx0=fx0, fx1=fx1, fy0=fy0, fy1=fy1, vcl=vcl, hcl=hcl, xs=xs, ys=ys,
                lites=lites, vents=vents, door=door, hw=hw)


def win_openings(t):
    return [o for o in M.OPENINGS if o.kind in ("window", "storefront", "louver") and o.type == t]


def _sill_head_txt(t):
    ops = win_openings(t)
    o = ops[0]
    base = M.LEVELS[o.level]
    if o.head - base > 12.0:      # spans levels (W-C)
        return f"EL. {fmt_elev(o.sill)}", f"EL. {fmt_elev(o.head)}"
    sill = {round(x.sill - M.LEVELS[x.level], 4) for x in ops}
    head = {round(x.head - M.LEVELS[x.level], 4) for x in ops}
    st = " / ".join(f"{ft(v)} AFF" for v in sorted(sill))
    ht = " / ".join(f"{ft(v)} AFF" for v in sorted(head))
    if t in ("SF-1", "SF-3"):
        st = "FFE (0'-0\" AFF)"
    return st, ht


def draw_unit(sh, v, t, show_tags=True):
    """draw window / storefront type t into view v (model origin = MO lower-left). returns layout."""
    L = win_layout(t)
    W, H = L["W"], L["H"]
    gt = win_glass(t)
    # context: cast stone sill / soldier course / curb
    if M.WINDOW_TYPES[t]["sill"].startswith("CS-1"):
        v.rect(-3 * IN, -4 * IN, W + 6 * IN, 4 * IN, lw="thin", fill="g10")
        v.line((-3 * IN, -1 * IN), (W + 3 * IN, -1 * IN), lw="hair")
        # FB-2 soldier course above head
        v.rect(0, H, W, 8 * IN, lw="thin")
        x = 0.0
        step = (2.25 + 0.375) * IN
        while x + step < W - 1e-6:
            x += step
            v.line((x, H), (x, H + 8 * IN), lw="hair", color="g50")
    if t == "SF-3":
        v.polygon([(-0.5, -8 * IN), (W + 0.5, -8 * IN), (W + 0.5, 0), (-0.5, 0)], lw="thin",
                  hatch="concrete", hatch_kw=dict(scale=0.6))
        v.line((-1.2, -8 * IN), (W + 1.2, -8 * IN), lw="med")
    if t == "SF-1":
        v.line((-1.0, 0), (W + 1.0, 0), lw="med")
    # MO and frame
    v.rect(0, 0, W, H, lw="fine", dash="hidden")
    v.rect(L["fx0"], L["fy0"], L["fx1"] - L["fx0"], L["fy1"] - L["fy0"], lw="med")
    for (i, j, x0, y0, x1, y1) in L["lites"]:
        v.rect(x0, y0, x1 - x0, y1 - y0, lw="thin")
        if t == "LV-1":
            continue
        if (i, j) in L["vents"]:
            k = 1.25 * IN
            v.rect(x0 + k, y0 + k, x1 - x0 - 2 * k, y1 - y0 - 2 * k, lw="fine")
            v.polyline([(x0 + k, y0 + k), ((x0 + x1) / 2, y1 - k), (x1 - k, y0 + k)], lw="fine",
                       dash="hidden")
        glass_marks(v, x0, y0, x1, y1)
        if show_tags:
            if (i, j) in L["vents"]:
                tp = ((x0 + x1) / 2, y0 + (y1 - y0) * 0.30)
            elif (y1 - y0) * v.s < 0.45:      # short lite: keep tag clear of glass marks
                tp = (x0 + (x1 - x0) * 0.33, y0 + (y1 - y0) * 0.5)
            else:
                tp = ((x0 + x1) / 2, y0 + (y1 - y0) * 0.38)
            glass_tag(sh, *v.to_paper(tp), gt)
    if t == "LV-1":
        x0, y0, x1, y1 = L["lites"][0][2:]
        yy = y0 + 3 * IN
        while yy < y1 - 1 * IN:
            v.line((x0, yy), (x1, yy), lw="fine")
            v.line((x0, yy + 1.0 * IN), (x1, yy + 1.0 * IN), lw="hair")
            yy += 4 * IN
    if L["door"]:
        i, j = L["door"]
        dx0 = L["xs"][i] + MULL / 2
        dx1 = L["xs"][i + 1] - MULL / 2
        dh = L["ys"][j + 1] - L["hw"].get(j, MULL) / 2
        lw_ = (dx1 - dx0) / 2
        draw_leaf(v, dx0, lw_, dh, "E", hinge="l")
        draw_leaf(v, dx0 + lw_, lw_, dh, "E", hinge="r")
        # swing indication (apex at hinge side)
        for (a, b, hx) in ((dx0, dx0 + lw_, dx0), (dx0 + lw_, dx1, dx1)):
            lx = b if hx == a else a
            v.polyline([(lx, dh - 0.1), (hx, dh / 2), (lx, 0.1)], lw="hair", dash="hidden")
        if show_tags:
            glass_tag(sh, *v.to_paper((dx0 + lw_ / 2, dh * 0.58)), "GL-1T")
            glass_tag(sh, *v.to_paper((dx0 + lw_ * 1.5, dh * 0.58)), "GL-1T")
    return L


def _place_labels(v, items, xl, ylo, yhi, min_gap):
    """items: [(tip, text)] -> leaders to x = xl, labels spread between ylo..yhi (model)."""
    items = sorted(items, key=lambda it: it[0][1])
    n = len(items)
    ys = [it[0][1] for it in items]
    # push apart
    for k in range(1, n):
        ys[k] = max(ys[k], ys[k - 1] + min_gap)
    if ys and ys[-1] > yhi:
        shift = ys[-1] - yhi
        ys = [y - shift for y in ys]
        for k in range(n - 2, -1, -1):
            ys[k] = min(ys[k], ys[k + 1] - min_gap)
    for (tip, txt), y in zip(items, ys):
        v.leader([tip, (xl - v.paper_len(0.12), y), (xl, y)], None, lines=txt, size=TXT["small"],
                 width=LABEL_W)


def unit_dims(v, t, L, side_extra=0.0):
    W, H = L["W"], L["H"]
    s = v.s
    P = lambda inch: inch / s       # paper inches -> model feet
    fx0, fx1, fy0, fy1 = L["fx0"], L["fx1"], L["fy0"], L["fy1"]
    bot = -4 * IN if M.WINDOW_TYPES[t]["sill"].startswith("CS-1") else 0.0
    if t == "SF-3":
        bot = -8 * IN
    top = H + (8 * IN if M.WINDOW_TYPES[t]["sill"].startswith("CS-1") else 0.0)
    # top: c/l chain
    if L["vcl"]:
        pts = [(fx0, top)] + [(x, top) for x in L["vcl"]] + [(fx1, top)]
        DC(v, pts, P(0.28) + (top - top))
    # bottom: SF-1 door string, frame width, MO width
    off = P(0.3)
    if t == "SF-1":
        i, j = L["door"]
        dx0 = L["xs"][i] + MULL / 2
        dx1 = L["xs"][i + 1] - MULL / 2
        DC(v, [(dx0, bot), ((dx0 + dx1) / 2, bot), (dx1, bot)], -off)
        off += P(0.22)
    v.dim((fx0, bot), (fx1, bot), -off, text=f"{ft(fx1 - fx0)} FRAME")
    off += P(0.22)
    v.dim((0, bot), (W, bot), -off, text=f"{ft(W)} MO")
    # left: horizontal c/l chain (or faces for SF-1)
    if t == "SF-1":
        dh = L["ys"][1] - L["hw"].get(0, MULL) / 2
        DC(v, [(fx0, fy0), (fx0, dh), (fx0, fy1)], P(0.3) + fx0)
    elif L["hcl"]:
        pts = [(fx0, fy0)] + [(fx0, y) for y in L["hcl"]] + [(fx0, fy1)]
        DC(v, pts, P(0.3) + fx0)
    # right: frame and MO heights
    v.dim((fx1, fy0), (fx1, fy1), -(P(0.3) + (W - fx1)), text=f"{ft(fy1 - fy0)} FRAME")
    v.dim((W, 0), (W, H), -P(0.52), text=f"{ft(H)} MO")
    return W + P(0.52) + P(0.2)


WIN_SCALE = {"SF-3": 1 / 8}
LABEL_W = 1.3


def win_leaders(t, L):
    W, H = L["W"], L["H"]
    fx0, fx1, fy0, fy1 = L["fx0"], L["fx1"], L["fy0"], L["fy1"]
    items = []
    lt = L["lites"]
    top_lite = max(lt, key=lambda q: q[5])
    items.append(((fx1 - MULL / 2, (fy0 + fy1) * 0.62), "2\" x 4 1/2\" THERMALLY BROKEN ALUM. FRAME"))
    if M.WINDOW_TYPES[t]["sill"].startswith("CS-1"):
        items.append(((W - 0.6, H + 4 * IN), "FB-2 SOLDIER COURSE"))
        items.append(((W - 0.2, -2 * IN), "CS-1 CAST STONE SILL"))
    if L["vents"]:
        i, j = L["vents"][-1]
        v_ = [q for q in lt if (q[0], q[1]) == (i, j)][0]
        items.append((((v_[2] + v_[4]) / 2 + 0.6, (v_[3] + v_[5]) / 2 - 0.3), "AWNING VENT, INSECT SCREEN"))
    if t == "SF-1":
        items.append(((W / 2 + 1.5, 0.05), "ALUM. THRESHOLD (HW-7)"))
        items.append(((W / 2 + 0.2, 4.0), "DOOR 100B, TYPE E PAIR"))
    if t == "SF-3":
        items.append(((W - 1.0, -4 * IN), "8\" CONC. CURB, GRADE TO 100'-0\""))
    if t == "W-C":
        items.append(((W - 0.3, M.LEVELS["L2"] - win_openings(t)[0].sill), "L2 SLAB EDGE BEYOND"))
    if t == "LV-1":
        items = [((fx1 - MULL / 2, (fy0 + fy1) * 0.7), "4\" DEEP DRAINABLE BLADE LOUVER (DIV. 23)"),
                 ((W / 2, -0.5 * IN), "PREFIN. MTL. SILL FLASHING"),
                 ((W * 0.75, H * 0.35), "BIRD SCREEN, BLANK-OFF PER DIV. 23")]
    items.append(((-0.5 * IN + W, H - 0.25 * IN), "1/2\" SEALANT JOINT, TYP."))
    return items


WIN_NOTE_LINES = {
    "W-A": "VENTS: TOP-HINGED AWNING, 4\" OPENING LIMITER AT L2 (IBC 1015.8).",
    "W-B": "VENT: TOP-HINGED AWNING, 4\" OPENING LIMITER AT L2 (IBC 1015.8).",
    "W-C": "ALL LITES TEMPERED (ADJACENT TO STAIR LANDING, IBC 2406.4.7).",
    "SF-1": "ALL LITES TEMPERED (DOORS AND WITHIN 24\" OF DOOR, IBC 2406.4).",
    "SF-2": "FIXED. L2 CORRIDOR ENDS (EAST AND WEST).",
    "SF-3": "ALL LITES TEMPERED PER WINDOW_TYPES; LOWER LITES < 18\" AFF.",
    "LV-1": "GC: OPENING, LINTEL, SILL FLASHING AND PERIMETER SEALANT.",
}


def win_cell(sh, cell, num, t):
    x, y, w, h = cell["x"], cell["y"], cell["w"], cell["h"]
    sc = WIN_SCALE.get(t, 0.25)
    L = win_layout(t)
    W, H = L["W"], L["H"]
    cs = M.WINDOW_TYPES[t]["sill"].startswith("CS-1")
    top_ext = (8 * IN if cs else 0) + (0.5 / sc if L["vcl"] else 0.2 / sc)
    bot_ext = (4 * IN if cs else 0) + (8 * IN if t == "SF-3" else 0) + \
        (0.95 if t == "SF-1" else 0.72) / sc
    lab_w = LABEL_W + 0.3
    left_w = (0.62 if (L["hcl"] or t == "SF-1") else 0.2) + (1.55 if t == "W-C" else 0.0)
    tot_w = left_w + W * sc + 0.62 + lab_w
    title_h = 1.2
    oy = y + title_h + 0.12 + bot_ext * sc
    ox = x + max(0.25, (w - tot_w) / 2) + left_w
    v = sh.view(ox, oy, sc)
    L = draw_unit(sh, v, t)
    unit_dims(v, t, L)
    lab_x = W + 0.62 / sc + 0.05 / sc
    items = win_leaders(t, L)
    _place_labels(v, items, lab_x, -bot_ext * 0.6, H + top_ext * 0.8, 0.2 / sc)
    if t == "W-C":
        o = win_openings(t)[0]
        for nm, el in (("INTERMEDIATE LANDING", (M.LEVELS["L1"] + M.LEVELS["L2"]) / 2),
                       ("LEVEL 2 T.O. SLAB", M.LEVELS["L2"])):
            yy = el - o.sill
            xl = -0.5 / sc
            v.line((xl - 1.3 / sc, yy), (W + 0.3, yy), lw="fine", dash="center")
            v.text((xl, yy + 0.04 / sc), nm, size=TXT["small"], anchor="r", valign="bot",
                   font=FONT_B)
            v.text((xl, yy - 0.03 / sc), fmt_elev(el) + " (BEYOND)", size=TXT["small"],
                   anchor="r", valign="top")
    # title + data
    sh.view_title(x + 0.3, y + title_h - 0.3, num, f"TYPE {t}", sc, width=min(w - 0.7, 4.8))
    st, ht = _sill_head_txt(t)
    hd, jb, sl = WIN_DET[t]
    lines = [M.WINDOW_TYPES[t]["desc"],
             f"MO {size_txt(W, H)}  |  SILL {st}  |  HEAD {ht}",
             f"GLASS: {win_glass(t)}   SILL: {M.WINDOW_TYPES[t]['sill']}",
             f"DETAILS: HEAD {hd}, JAMB {jb}, SILL {sl}"
             + (f"   WALL SECT.: {WIN_SECTION[t]}" if WIN_SECTION[t] != "-" else ""),
             WIN_NOTE_LINES.get(t, "")]
    sh.mtext((x + 0.3 + 0.46, y + title_h - 0.5), [l for l in lines if l], size=CELL,
             width=w - 0.9, leading=CELL * 1.18)


def key_plan(sh, ox, oy, level, scale=1 / 16):
    """exterior wall outline with window / storefront / louver type tags (generated)."""
    v = sh.view(ox, oy, scale)
    out = M.outline_poly(level)
    g = M.ext_layer(level, -M.EW_IN, M.EW_OUT)
    for w in M.interior_walls(level):
        v.geom(w.poly(), lw="hair", fill="g10", color="g50")
    for r in M.rooms(level):
        if r.name in ("CLASSROOM", "SMALL GROUP", "CORRIDOR", "LINK"):
            c = r.shape.centroid
            v.text((c.x, c.y), f"{r.num}", size=TXT["small"], anchor="c", valign="mid",
                   color="g50")
    v.geom(g, lw="thin", fill="g20")
    if level == "L1":
        # existing building face
        v.line((M.EXIST_FACE_X - 1.0, 20), (M.EXIST_FACE_X - 1.0, 52), lw="thin", color="screen")
        v.text((M.EXIST_FACE_X - 2.5, 36), "EXIST.", size=TXT["small"], anchor="r", valign="mid",
               color="g50")
    # grids (light)
    for k, gx in M.GRID_X.items():
        v.line((gx, -9), (gx, 81), lw="hair", dash="grid", color="g50")
        v.text((gx, 83), k, size=TXT["small"], font=FONT_B, anchor="c", valign="bot")
    for k, gy in M.GRID_Y.items():
        x_end = 159
        v.line((-9 if level == "L2" else M.EXIST_FACE_X - 3, gy), (x_end, gy), lw="hair",
               dash="grid", color="g50")
        v.text((x_end + 1.5, gy), k, size=TXT["small"], font=FONT_B, anchor="l", valign="mid")
    ops = [o for o in M.OPENINGS if o.kind in ("window", "storefront", "louver")
           and o.level == level]
    placed = []
    for o in sorted(ops, key=lambda q: (q.wall, q.c)):
        ax = M.opening_axis(o)
        k = M.opening_line_coord(o)
        outv = M.seg_outward(o.wall)
        s_ = outv[1] if ax == "x" else outv[0]
        # opening in wall (white gap + glass line)
        a = (o.lo, k) if ax == "x" else (k, o.lo)
        b = (o.hi, k) if ax == "x" else (k, o.hi)
        if ax == "x":
            v.rect(o.lo, k - M.EW_IN, o.w, M.EW_IN + M.EW_OUT, lw=None, fill="white", stroke=False)
            v.rect(o.lo, k - M.EW_IN if s_ > 0 else k - M.EW_OUT, o.w, M.EW_IN + M.EW_OUT, lw="fine")
        else:
            lo_x = k - M.EW_IN if s_ > 0 else k - M.EW_OUT
            v.rect(lo_x, o.lo, M.EW_IN + M.EW_OUT, o.w, lw=None, fill="white", stroke=False)
            v.rect(lo_x, o.lo, M.EW_IN + M.EW_OUT, o.w, lw="fine")
        v.line(a, b, lw="thin")
        # tag
        d = 4.2 / (scale * 16)
        cpos = o.c
        off = d
        for (pc, pk, pax, poff) in placed:
            if pax == (o.wall) and abs(pc - cpos) * scale < 0.42 and abs(poff - off) < 1e-6:
                off = d + 3.4 / (scale * 16)
        placed.append((cpos, k, o.wall, off))
        if ax == "x":
            tp = (cpos, k + s_ * off)
        else:
            tp = (k + s_ * off, cpos)
        px, py = v.to_paper(tp)
        hexagon(sh, px, py, o.type, size=TXT["small"])
        # leader from tag to wall when pushed out
        if off > d:
            q = (cpos, k + s_ * (M.EW_OUT + 0.3)) if ax == "x" else (k + s_ * (M.EW_OUT + 0.3), cpos)
            r = (cpos, k + s_ * (off - 1.4)) if ax == "x" else (k + s_ * (off - 1.4), cpos)
            v.line(q, r, lw="hair")
    return v


WIN_ORDER = ["W-A", "W-B", "W-C", "SF-1", "SF-2", "SF-3", "LV-1"]
WIN_COLS_L1 = ["N", "S", "E", "W", "LINK N", "LINK S"]
WIN_COLS_L2 = ["N", "S", "E", "W"]


def win_schedule_rows():
    rows = []
    for t in WIN_ORDER:
        ops = win_openings(t)
        L = win_layout(t)
        W, H = L["W"], L["H"]
        cnt = {}
        for o in ops:
            cnt[(o.level, ELEV_GROUP[o.wall])] = cnt.get((o.level, ELEV_GROUP[o.wall]), 0) + 1
        st, ht = _sill_head_txt(t)
        hd, jb, sl = WIN_DET[t]
        c1 = [str(cnt.get(("L1", g), "-")) for g in WIN_COLS_L1]
        c2 = [str(cnt.get(("L2", g), "-")) for g in WIN_COLS_L2]
        rem = []
        if t == "W-C":
            rem.append("STAIR TOWERS ST-1 (S) / ST-2 (N); SPANS L1-L2, COUNTED AT L1")
        if t == "SF-1":
            rem.append("INCLUDES DOOR 100B (TYPE E PAIR, HW-7)")
        if t == "SF-3":
            rem.append("ON 8\" CONC. CURB; LINK 100A NORTH & SOUTH")
        if t == "LV-1":
            rem.append("ROOM 112; LOUVER BY DIV. 23")
        tags = sorted({o.id for o in ops}, key=natkey)
        rows.append([t, M.WINDOW_TYPES[t]["desc"], size_txt(W, H),
                     size_txt(L["fx1"] - L["fx0"], L["fy1"] - L["fy0"]), st, ht, win_glass(t),
                     hd, jb, sl, WIN_SECTION[t]] + c1 + c2 + [str(len(ops)), "; ".join(rem)])
    return rows


WIN_SCHED_COLS = [("TYPE", 0.5), ("DESCRIPTION", 3.25), ("MO\n(W x H)", 1.05),
                  ("FRAME\n(W x H)", 1.12), ("SILL", 1.0), ("HEAD", 1.0), ("GLASS", 0.52),
                  ("HEAD", 0.82), ("JAMB", 0.82), ("SILL", 0.82), ("WALL\nSECTION", 0.95)] + \
                 [(g.replace(" ", "\n"), 0.42) for g in WIN_COLS_L1] + \
                 [(g, 0.42) for g in WIN_COLS_L2] + [("TOTAL\n(EA)", 0.5), ("REMARKS", 2.5)]
WIN_SCHED_GROUPS = [("", 7), ("DETAILS (SEE A-501 / A-31x)", 4), ("LEVEL 1 - COUNT BY ELEVATION", 6),
                    ("LEVEL 2 - COUNT", 4), ("", 1), ("", 1)]

A711_NOTES = [
    "##GENERAL",
    "ELEVATIONS ARE VIEWED FROM THE EXTERIOR. DIMENSIONS ARE TO MASONRY OPENING (MO), FRAME "
    "EDGE OR MULLION CENTERLINE (C/L). FIELD VERIFY MO BEFORE FABRICATION.",
    "FRAME SIZE = MO LESS 1/2\" PERIMETER SEALANT JOINT AT JAMBS, HEAD AND SILL (SF-1: HEAD AND "
    "JAMBS ONLY, FRAME BEARS ON SLAB AT THRESHOLD).",
    "COUNTS IN THE SCHEDULE ARE GENERATED FROM THE PLANS (A-101 / A-102) AND ELEVATIONS "
    "(A-201 / A-202). TYPE TAGS ON PLANS AND ELEVATIONS GOVERN LOCATIONS.",
    "##PERFORMANCE",
    "FRAMING: THERMALLY BROKEN EXTRUDED ALUMINUM, 2\" x 4 1/2\" FACE x DEPTH, CENTER-SET (W-A, W-B, "
    "SF-2: FIXED/VENT WINDOW SYSTEM; W-C, SF-1, SF-3: STOREFRONT SYSTEM, SECTION 08 43 13). "
    "FINISH AAMA 611 CLASS I CLEAR ANODIZED (AA-M12C22A41).",
    "WINDOWS W-A / W-B: AAMA/WDMA/CSA 101/I.S.2/A440 (NAFS) PERFORMANCE CLASS AW, PG 40 MIN.",
    "GLAZING: 1\" INSULATING GLASS (GL-1 / GL-1T), ASTM E2190 CERTIFIED. GLASS THICKNESS AND "
    "HEAT TREATMENT PER ASTM E1300 FOR DESIGN WIND LOADS.",
    "ENERGY (2021 IECC, CLIMATE ZONE 5A, NFRC-RATED WHOLE ASSEMBLY): FIXED U-0.36 MAX., OPERABLE "
    "U-0.45 MAX., ENTRANCE DOORS U-0.63 MAX.; SHGC 0.38 MAX.; VT/SHGC 1.10 MIN.",
    "AIR INFILTRATION (ASTM E283 AT 6.24 PSF): FIXED 0.06 CFM/SF MAX.; OPERABLE 0.10 CFM/SF MAX.; "
    "ENTRANCE DOORS 1.0 CFM/SF MAX.",
    "WATER (ASTM E331): NO UNCONTROLLED WATER AT 12 PSF (WINDOWS) AND 10 PSF (STOREFRONT).",
    "STRUCTURAL (ASTM E330): DESIGN WIND PRESSURES PER ASCE 7-16 COMPONENTS AND CLADDING, RISK "
    "CATEGORY III (SEE S-001). DEFLECTION L/175 OR 3/4\" MAX.; L/360 WHERE SUPPORTING MASONRY "
    "ABOVE IS NOT INDEPENDENT. TEST AT 150% DESIGN LOAD, PERMANENT SET 0.2% OF SPAN MAX.",
    "CONDENSATION RESISTANCE (AAMA 1503): CRF 55 MIN.",
    "##SAFETY GLAZING",
    "TEMPERED (GL-1T) WHERE REQUIRED BY IBC 2406.4: IN AND ADJACENT TO DOORS (SF-1), WITHIN 18\" "
    "OF FLOOR (SF-3 LOWER LITES), ADJACENT TO STAIRS AND LANDINGS (W-C). EACH TEMPERED LITE "
    "PERMANENTLY LABELED (ANSI Z97.1 / CPSC 16 CFR 1201).",
    "L2 OPERABLE VENTS WITH SILL LESS THAN 36\" AFF AND MORE THAN 72\" ABOVE GRADE: WINDOW "
    "OPENING CONTROL DEVICES PER ASTM F2090 (IBC 1015.8).",
    "##INSTALLATION AND TESTING",
    "SILL PAN FLASHING WITH END DAMS AND BACK LEG AT ALL WINDOWS AND STOREFRONT; INTEGRATE WITH "
    "THROUGH-WALL FLASHING AND AIR/WATER BARRIER. PERIMETER SEALANT ASTM C920, CLASS 50, WITH "
    "BACKER ROD; INTERIOR SEAL TO AIR BARRIER.",
    "FIELD TESTING BY OWNER'S AGENCY: AAMA 502 (WINDOWS) / AAMA 503 (STOREFRONT): ASTM E1105 "
    "WATER TEST AT 2/3 LAB PRESSURE AND ASTM E783 AIR TEST, 2 LOCATIONS PER TYPE MIN. (W-A, "
    "SF-1, SF-3), PLUS RETEST OF FAILURES.",
    "SUBMIT SHOP DRAWINGS WITH ANCHORAGE CALCULATIONS (ILLINOIS SE), THERMAL PERFORMANCE "
    "(NFRC 100/200) AND GLASS SAMPLES. WARRANTY: 10 YEARS IGU SEAL, 2 YEARS INSTALLATION.",
]


def draw_a711(sh):
    x0, y0, x1, y1 = sh.x0, sh.y0, sh.x1, sh.y1
    rx = x1 - 7.6
    lx1 = rx - 0.3
    # schedule along the full bottom
    rows = win_schedule_rows()
    al = ["c", "l", "c", "c", "c", "c", "c", "c", "c", "c", "c"] + ["c"] * 11 + ["l"]
    cols = WIN_SCHED_COLS
    k = (x1 - x0 - 0.45) / table_w(cols)
    cols = [(h_, w_ * k) for h_, w_ in cols]
    kw = dict(title="WINDOW / STOREFRONT / LOUVER SCHEDULE", groups=WIN_SCHED_GROUPS, align=al,
              size=7.0, hsize=6.5, row_h=0.3,
              title_note="COUNTS GENERATED FROM MODEL OPENINGS (PLANS A-101 / A-102, "
                         "ELEVATIONS A-201 / A-202); W-C COUNTED ONCE AT LEVEL 1")
    hs = sched_table(sh, 0, 0, cols, rows, draw=False, **kw)
    sched_top = y0 + 0.35 + hs
    sched_table(sh, x0 + 0.25, sched_top, cols, rows, **kw)
    sh.text((x0 + 0.25, y0 + 0.25),
            "MO = MASONRY OPENING   AFF = ABOVE FINISH FLOOR   FFE = FINISH FLOOR ELEVATION   "
            "SIM = SIMILAR   - = NONE   GLASS TAGS: SEE GLASS TYPES", size=TXT["small"],
            valign="top")
    top = y1 - 0.05
    bot = sched_top + 0.3
    sh.line((x0, bot - 0.12), (x1, bot - 0.12), lw="thin")
    # rows of elevations (left area)
    r1 = 7.0
    r2 = 4.75
    row1 = [("W-A", 5.4), ("W-B", 4.6), ("W-C", 5.1), ("SF-1", 0)]
    row1[-1] = ("SF-1", lx1 - x0 - sum(w for _, w in row1[:-1]))
    row2 = [("SF-2", 6.6), ("SF-3", 0), ("LV-1", 4.6)]
    row2[1] = ("SF-3", lx1 - x0 - 6.6 - 4.6)
    num = 1
    xx = x0
    for t, w in row1:
        win_cell(sh, dict(x=xx, y=top - r1, w=w, h=r1), num, t)
        num += 1
        xx += w
        if t != row1[-1][0]:
            sh.line((xx, top - r1 + 0.15), (xx, top - 0.15), lw="hair", color="g40")
    sh.line((x0, top - r1), (lx1, top - r1), lw="fine")
    xx = x0
    for t, w in row2:
        win_cell(sh, dict(x=xx, y=top - r1 - r2, w=w, h=r2), num, t)
        num += 1
        xx += w
        if t != row2[-1][0]:
            sh.line((xx, top - r1 - r2 + 0.15), (xx, top - r1 - 0.15), lw="hair", color="g40")
    k_top = top - r1 - r2
    sh.line((x0, k_top), (x1, k_top), lw="thin")
    # key plans (full width band)
    sc = 1 / 16
    kp_y = bot + 1.0 + 9 * sc
    kx1 = x0 + 0.55 + 40 * sc
    kx2 = kx1 + 205 * sc
    for lev, kx in (("L1", kx1), ("L2", kx2)):
        key_plan(sh, kx, kp_y, lev, sc)
        tx = kx + (-36 if lev == "L1" else 0) * sc
        sh.view_title(tx - 0.1, bot + 0.35, num, f"WINDOW / STOREFRONT KEY PLAN - LEVEL {lev[1]}",
                      sc, width=6.2)
        num += 1
    kn_x = kx2 + 176 * sc
    kn = ["TAGS ARE GENERATED FROM THE SAME OPENING DATA AS THE FLOOR PLANS AND THE SCHEDULE "
          "BELOW. EACH TAG = ONE UNIT (MO).",
          "W-C STAIR STRIPS SPAN FROM LEVEL 1 TO ABOVE LEVEL 2; THEY ARE TAGGED AND COUNTED AT "
          "LEVEL 1 ONLY.",
          "SF-1 AT THE EAST ENTRANCE INCLUDES DOOR 100B (SEE A-701). SF-3 LINK STOREFRONTS SIT ON "
          "AN 8\" CONCRETE CURB.",
          "LV-1 LOUVERS IN ROOM 112 ARE FURNISHED BY DIV. 23; OPENING, LINTEL, SILL FLASHING "
          "AND SEALANT BY GC.",
          "ROOM NUMBERS SHOWN FOR ORIENTATION. SEE A-201 / A-202 FOR EXTERIOR ELEVATIONS."]
    notes_cols(sh, kn_x, k_top - 0.3, "KEY PLAN NOTES", kn, x1 - 0.2 - kn_x, ncols=1)
    # vertical divider for the right column (top band only)
    sh.line((rx - 0.25, k_top), (rx - 0.25, y1 - 0.1), lw="thin")
    # right column: glass types, legend, notes
    rw = x1 - 0.15 - rx
    cy = y1 - 0.2
    g_rows = [[k_, v_] for k_, v_ in GLASS_TYPES.items()]
    h = sched_table(sh, rx, cy, [("TAG", 0.6), ("GLASS TYPE", rw - 0.6)], g_rows,
                    title="GLASS TYPES", row_h=0.2, size=6.25, align=["c", "l"])
    cy -= h + 0.3
    sh.text((rx, cy), "ELEVATION LEGEND", size=TXT["label"], font=FONT_B, valign="top",
            underline=True)
    cy -= 0.32
    v = sh.view(rx + 0.15, cy - 0.25, 0.25)
    v.rect(0, 0, 1.2, 1.2, lw="thin")
    v.polyline([(0.1, 0.1), (0.6, 1.1), (1.1, 0.1)], lw="fine", dash="hidden")
    sh.text((rx + 0.6, cy - 0.1), "AWNING VENT: APEX OF DASHED LINES = HINGE SIDE", size=CELL,
            valign="mid")
    glass_tag(sh, rx + 0.3, cy - 0.5, "GL-1")
    sh.text((rx + 0.6, cy - 0.5), "GLASS TYPE TAG (T = FULLY TEMPERED SAFETY GLAZING)", size=CELL,
            valign="mid")
    vv = sh.view(rx + 0.15, cy - 0.88, 0.25)
    glass_marks(vv, 0, 0, 1.2, 0.6)
    vv.rect(0, 0, 1.2, 0.6, lw="thin")
    sh.text((rx + 0.6, cy - 0.8), "GLAZED LITE (DIAGONAL GLASS INDICATION)", size=CELL,
            valign="mid")
    sh.line((rx + 0.1, cy - 1.08), (rx + 0.45, cy - 1.08), lw="fine", dash="hidden")
    sh.text((rx + 0.6, cy - 1.08), "MASONRY OPENING (MO) LINE", size=CELL, valign="mid")
    hexagon(sh, rx + 0.3, cy - 1.36, "W-A", size=TXT["small"])
    sh.text((rx + 0.6, cy - 1.36), "WINDOW / STOREFRONT TYPE TAG (PLANS AND KEY PLANS)",
            size=CELL, valign="mid")
    cy -= 1.75
    notes_cols(sh, rx, cy, "WINDOW AND STOREFRONT NOTES", A711_NOTES, rw, ncols=1)


# ========================================================================================
# A-801 ROOM FINISH SCHEDULE, FINISH LEGEND, CASEWORK SCHEDULE
# ========================================================================================
# remarks the model does not carry (see report: WOM-1 is not assigned to any room in model.py)
SUPPLEMENTAL_REMARKS = {"100": "WOM-1 RECESSED WALK-OFF AT EAST ENTRANCE 100B, SEE A-111"}

FIN_BOD = {
    "VCT-1": "ASTM F1066 CLASS 2 THROUGH-PATTERN, 1/8\" GA.; ARCHITECT TO SELECT FROM MFR. "
             "STANDARD LINE. 3 COATS FACTORY-RECOMMENDED POLISH AFTER INSTALL.",
    "VCT-2": "SAME PRODUCT AS VCT-1, ACCENT COLOR (1 COLOR).",
    "LVT-1": "ASTM F1700 CLASS III TYPE B, 20 MIL WEAR LAYER, FACTORY URETHANE; GLUE-DOWN; "
             "RANDOM / ASHLAR PLANK LAYOUT.",
    "LVT-2": "ASTM F1700 CLASS III, 20 MIL; SAME MFR. AND THICKNESS AS LVT-1 (FLUSH JOINT).",
    "CPT-1": "TUFTED SOLUTION-DYED NYLON, CRI GREEN LABEL PLUS, ASTM E648 CLASS I, "
             "HARDBACK OR CUSHION BACK; RELEASE ADHESIVE.",
    "WOM-1": "HEAVY-DUTY SCRAPER / WIPER WALK-OFF TILE IN 1/4\" SLAB DEPRESSION, FLUSH WITH "
             "ADJACENT FLOORING.",
    "PT-1": "ANSI A137.1 PORCELAIN, DCOF 0.42 MIN. WET; ANSI A118.4 MORTAR; ANSI A118.3 "
            "EPOXY GROUT; 1/3 RUNNING BOND MAX. OFFSET.",
    "RF-1": "HOMOGENEOUS RUBBER SHEET, ASTM F1859, 3.0 MM, ADHESIVE PER MFR.; HEAT-WELDED "
            "OR COLD-WELDED SEAMS.",
    "RST-1": "ASTM F2169 TYPE TS CLASS 1, 1/4\" MIN. THICK, 2\" CONTRASTING NOSING STRIP; "
             "STAIR TREAD + RISER ONE PIECE.",
    "SC-1": "PENETRATING LITHIUM SILICATE DENSIFIER / SEALER, 2 COATS, COMPATIBLE WITH CURE.",
    "RB-1": "ASTM F1861 TYPE TS, GROUP 1 (SOLID), STYLE B (COVE), 1/8\" THICK, COILS; "
            "PREFORMED OUTSIDE CORNERS, JOB-FORMED INSIDE.",
    "PT-1B": "PORCELAIN COVE BASE 6\" x 12\" (OR 6\" x 24\"), FACTORY COVE, MATCH PT-1; "
             "EPOXY GROUT.",
    "PNT-1": "CMU: MPI #4 BLOCK FILLER + 2 COATS MPI #52 LATEX EGGSHELL. GWB: MPI #50 PRIMER + "
             "2 COATS. VOC 50 G/L MAX.",
    "PNT-2": "MPI #4 BLOCK FILLER + 2 COATS WATERBORNE 2-COMPONENT EPOXY, SEMI-GLOSS, "
             "SCRUBBABLE.",
    "CT-1": "ANSI A137.1 GLAZED WALL TILE, TCNA W202I THIN-SET ON CMU; POLYMER GROUT; "
            "BULLNOSE CAP, OUTSIDE CORNERS.",
    "ACT-1": "MINERAL FIBER, ASTM E1264 TYPE III, NRC 0.70, CAC 35, LR 0.83 MIN.; TEGULAR "
             "REVEAL EDGE; ASTM C635 INTERMEDIATE-DUTY GRID.",
    "ACT-2": "VINYL-FACED SCRUBBABLE MINERAL FIBER, SQUARE EDGE, ASTM E1264 CLASS A; "
             "INTERMEDIATE-DUTY GRID.",
    "GWB-1": "ASTM C1396 MOISTURE / MOLD-RESISTANT (ASTM D3273 SCORE 10) ON SUSPENSION SYSTEM, "
             "LEVEL 4 FINISH, PNT-2 EPOXY.",
    "EXP": "NO CEILING. DECK, JOISTS, STRUCTURE AND SERVICES PAINTED (DRY-FALL) WHERE EXPOSED.",
}
FIN_CAT_NAME = {"floor": "FLOORING", "base": "BASE", "walls": "WALLS", "ceiling": "CEILINGS"}


def _codes(field):
    return [c.strip() for c in field.split("/") if c.strip() in M.FINISHES]


def finish_usage():
    """{code: (category, [rooms])} derived from ROOMS (category of unused codes inherited)."""
    use = OrderedDict()
    for code in M.FINISHES:
        use[code] = [None, []]
    for r in M.ROOMS:
        for fld in ("floor", "base", "walls", "ceiling"):
            for c in _codes(getattr(r, fld)):
                if use[c][0] is None:
                    use[c][0] = fld
                use[c][1].append(r)
    prev = "floor"
    for c in use:
        if use[c][0] is None:
            use[c][0] = prev
        prev = use[c][0]
    return use


def _plural(n):
    return n if n.endswith("S") or n.endswith(".") else n + "S"


def location_text(code, rooms_):
    allr = [r for r in M.ROOMS if r.walls not in ("-", "")]
    if not rooms_:
        return "NOT ASSIGNED IN ROOM SCHEDULE - SEE REMARKS / A-111"
    nums = {r.num + r.level for r in rooms_}
    if len(nums) > 0.7 * len(allr):
        ex = sorted([r for r in allr if r.num + r.level not in nums],
                    key=lambda r: (r.level, natkey(r.num)))
        return "ALL ROOMS EXCEPT " + ", ".join(r.num for r in ex)
    groups = OrderedDict()
    for r in sorted(rooms_, key=lambda r: (natkey(r.num), r.level)):
        groups.setdefault(rname(r), []).append(r)
    parts = []
    for nm, rs in groups.items():
        tot = sum(1 for r in M.ROOMS if rname(r) == nm)
        if len(rs) == tot and len(rs) > 2:
            parts.append(f"ALL {_plural(nm)} ({len(rs)})")
        else:
            uniq = []
            for r in sorted(rs, key=lambda r: (r.level, natkey(r.num))):
                lab = r.num if not r.num.startswith("ST") else f"{r.num} ({r.level})"
                if lab not in uniq:
                    uniq.append(lab)
            parts.append(f"{nm} {', '.join(uniq)}")
    return "; ".join(parts)


def finish_legend_rows():
    use = finish_usage()
    rows = []
    cat = None
    for code, (c, rs) in use.items():
        if c != cat:
            rows.append(FIN_CAT_NAME[c])
            cat = c
        rows.append([code, M.FINISHES[code], FIN_BOD.get(code, "-"), location_text(code, rs)])
    return rows


ROOM_COLS = [("ROOM\nNO.", 0.55), ("ROOM NAME", 1.35), ("FLOOR", 0.92), ("BASE", 0.55),
             ("N", 0.72), ("E", 0.72), ("S", 0.72), ("W", 0.72), ("MATL.", 0.55),
             ("HEIGHT", 0.6), ("REMARKS", 2.65)]
ROOM_GROUPS = [("", 1), ("", 1), ("", 1), ("", 1), ("WALLS", 4), ("CEILING", 2), ("", 1)]


def room_rows(level):
    rows = []
    for r in sorted(M.rooms(level), key=lambda r: natkey(r.num)):
        clg = ft(r.clg_ht) if r.clg_ht else "-"
        rem = [x for x in (r.remarks, SUPPLEMENTAL_REMARKS.get(r.num, "")) if x]
        rows.append([r.num, rname(r), r.floor, r.base, r.walls, r.walls, r.walls, r.walls,
                     r.ceiling, clg, "; ".join(rem)])
    return rows


CW_KEYS = list(M.CASEWORK_TYPES)


def cw_unit(k):
    vals = [d[k] for d in M.CASEWORK_TYPICAL.values() if k in d]
    return "EA" if vals and all(isinstance(v, int) for v in vals) else "LF"


def casework_rows():
    rows = []
    for lev in ("L1", "L2"):
        rows.append(f"LEVEL {lev[1]}")
        for r in sorted(M.rooms(lev), key=lambda r: natkey(r.num)):
            d = M.CASEWORK_TYPICAL.get(rname(r))
            if not d:
                continue
            cells = [f"{d[k]:g}" if k in d else "-" for k in CW_KEYS]
            rem = "TYPICAL CLASSROOM, SEE A-601" if rname(r) == "CLASSROOM" else \
                "SEE A-101 / A-102 PLAN, A-502"
            rows.append([r.num, rname(r)] + cells + [rem])
    return rows


A801_FIN_NOTES = [
    "##GENERAL",
    "FINISH CODES REFER TO THE FINISH LEGEND ON THIS SHEET AND TO DIVISION 09 SPECIFICATIONS. "
    "SEE A-111 / A-112 FINISH PLANS FOR PATTERNS AND TRANSITIONS AND A-121 / A-122 FOR CEILINGS.",
    "WALL FINISH COLUMNS N / E / S / W REFER TO PLAN NORTH. WHERE TWO CODES ARE SHOWN (CT-1 / PNT-1) "
    "SEE REMARKS FOR THE HEIGHT OF EACH FINISH. PAINT ALL EXPOSED CMU, GWB, HM FRAMES AND "
    "EXPOSED STEEL IN FINISHED ROOMS UNLESS NOTED.",
    "CEILING HEIGHTS ARE ABOVE FINISH FLOOR. \"-\" = NO CEILING (EXPOSED STRUCTURE, EXP) OR NOT "
    "APPLICABLE. ELEVATOR CAB AND HOISTWAY FINISHES BY ELEVATOR MANUFACTURER.",
    "##FLOOR PATTERNS",
    "CLASSROOMS: VCT-1 FIELD WITH A VCT-2 BAND ONE TILE (12\") WIDE, LOCATED 2'-0\" FROM THE FACE "
    "OF WALLS AROUND THE ROOM PERIMETER, SQUARE CORNERS (SEE TYPICAL PATTERN). LAY VCT WITH "
    "GRAIN IN ONE DIRECTION, SQUARE TO THE ROOM.",
    "RESILIENT FLOORING AND CARPET ARE NOT INSTALLED UNDER FIXED BASE CASEWORK, TALL CABINETS OR "
    "CUBBIES; RB-1 BASE IS APPLIED AT CASEWORK TOE KICKS.",
    "CORRIDORS: LVT-1 PLANK FIELD (ASHLAR, LONG DIRECTION E-W) WITH LVT-2 ACCENT BANDS 2'-0\" WIDE "
    "ACROSS THE FULL CORRIDOR WIDTH, CENTERED ON EACH COLUMN GRID LINE. SEE A-111.",
    "CARPET TILE CPT-1: QUARTER-TURN (MONOLITHIC NOT ACCEPTED), START AT ROOM CENTER. WOM-1 AT THE "
    "EAST ENTRANCE IN 1/4\" SLAB DEPRESSION (COORDINATE WITH CONCRETE).",
    "TRANSITIONS: CENTER UNDER DOORS IN THE CLOSED POSITION. RESILIENT TO CARPET: RUBBER REDUCER; "
    "PT-1 TO RESILIENT: SATIN ALUMINUM TILE EDGE PROFILE; SC-1 TO RESILIENT: 1/8\" RUBBER REDUCER. "
    "1/4\" MAX. VERTICAL, 1/2\" MAX. BEVELED 1:2 (ICC A117.1 303).",
    "##SUBSTRATE",
    "MOISTURE AND pH TESTING BEFORE RESILIENT, CARPET AND TILE: ASTM F2170 IN-SITU RH (3 TESTS "
    "FIRST 1,000 SF + 1 PER ADDITIONAL 1,000 SF) AND ASTM F710 pH. MEET FLOORING MFR. LIMITS OR "
    "APPLY MOISTURE MITIGATION SYSTEM (ALTERNATE / UNIT PRICE).",
    "FLOOR FLATNESS FOR RESILIENT: 1/8\" IN 6'-0\" / 3/16\" IN 10'-0\"; PATCH AND LEVEL WITH "
    "PORTLAND-CEMENT-BASED UNDERLAYMENT. NO CURING COMPOUNDS UNDER ADHESIVE-APPLIED FLOORING.",
    "##ATTIC STOCK (FROM SAME PRODUCTION RUN, FULL CARTONS, LABELED)",
    "VCT-1 2%, VCT-2 5%; LVT-1 / LVT-2 3%; CPT-1 5%; PT-1 / PT-1B 2%; CT-1 2%; RB-1 2% (MIN. 1 "
    "COIL); RST-1 2 TREADS; RF-1 1 ROLL END; ACT-1 / ACT-2 2%; PAINT 1 GAL. PER COLOR.",
]

A801_CW_NOTES = [
    "CASEWORK: AWI / AWMAC / WI ARCHITECTURAL WOODWORK STANDARDS (AWS) PREMIUM GRADE, FRAMELESS "
    "FLUSH OVERLAY CONSTRUCTION, SECTION 06 41 00.",
    "HIGH-PRESSURE DECORATIVE LAMINATE (NEMA LD3): EXPOSED VERTICAL SURFACES VGS (0.028\"); "
    "COUNTERTOPS AND HORIZONTAL SURFACES HGS (0.048\"); CABINET INTERIORS THERMOFUSED MELAMINE.",
    "EDGES: 3 MM PVC EDGEBANDING ON DOORS, DRAWER FRONTS AND EXPOSED CABINET EDGES; 1 MM PVC ON "
    "SHELF EDGES. CORES: 3/4\" ANSI A208.1 M-2 PARTICLEBOARD, NAUF; MOISTURE-RESISTANT CORE AT "
    "SINK CABINETS (CW-2) AND SINK COUNTERTOPS.",
    "HARDWARE: FULL-EXTENSION BALL-BEARING DRAWER SLIDES, 100 LB (150 LB FILE DRAWERS); 170 DEG. "
    "CONCEALED HINGES; 4\" WIRE PULLS (ACCESSIBLE); ADJ. SHELF PINS; CW-4 CAM LOCKS KEYED ALIKE PER ROOM.",
    "CW-1 / CW-2 SET ON SEPARATE 4\" TOE KICK BASE, LEVELED, WITH RB-1 BASE APPLIED. COUNTERTOP "
    "CT-1 (CASEWORK TAG, NOT THE CT-1 WALL TILE FINISH) AT 34\" AFF MAX. AT SINK CW-2 (OPEN "
    "BACK FOR FORWARD APPROACH).",
    "ANCHOR WALL CABINETS CW-3 (BOTTOM AT 54\" AFF) AND TALL CABINETS CW-4 TO CMU WITH EXPANSION "
    "ANCHORS OR TO FRT BLOCKING IN STUD WALLS. SCRIBE FILLERS TO WALLS.",
    "SINKS, FAUCETS AND TRAPS BY DIV. 22; CUTOUTS BY CASEWORK FABRICATOR FROM TEMPLATES. "
    "SUBMIT SHOP DRAWINGS AND HPL SAMPLES (3 COLORS MAX. PER ROOM).",
]


def _clip_rect(sh, x, y, w, h):
    c = sh.c
    c.saveState()
    pth = c.beginPath()
    pth.rect(x * PT, y * PT, w * PT, h * PT)
    c.clipPath(pth, stroke=0, fill=0)


def classroom_pattern(sh, x, y, num):
    """typical classroom floor pattern (generated from clear_room_poly of classroom 102)."""
    r = next(q for q in M.ROOMS if q.num == "102")
    g = M.clear_room_poly(r)
    minx, miny, maxx, maxy = g.bounds
    sc = 1 / 8
    v = sh.view(x + 0.85 - minx * sc, y + 1.25 - miny * sc, sc)
    band = g.buffer(-2.0, join_style=2).difference(g.buffer(-3.0, join_style=2))
    field = g.difference(g.buffer(-2.0, join_style=2)).union(g.buffer(-3.0, join_style=2))
    v.geom(field, lw=None, hatch="tile", hatch_kw=dict(spacing=1.0, w="hair", col="g50"),
           stroke=False)
    v.geom(band, lw="fine", fill="g40")
    v.geom(g, lw="heavy")
    # dims
    v.dim((minx, maxy), (minx + 2.0, maxy), 2.4, text="2'-0\"", size=TXT["small"])
    dim_s(v, (minx + 2.0, maxy), (minx + 3.0, maxy), 2.4, "1'-0\"", side="r")
    v.dim((minx, miny), (maxx, miny), -2.2, text=ft(maxx - minx) + " CLEAR")
    v.dim((maxx, miny), (maxx, maxy), -2.2, text=ft(maxy - miny) + " CLEAR")
    v.leader([(maxx - 2.5, miny + 9.0), (maxx + 4.0, miny + 9.0), (maxx + 4.6, miny + 9.0)],
             "VCT-2 BAND, 12\" WIDE", size=TXT["small"])
    v.leader([(maxx - 8.0, miny + 16.0), (maxx + 4.0, miny + 16.0), (maxx + 4.6, miny + 16.0)],
             "VCT-1 FIELD, 12\" x 12\"", size=TXT["small"])
    v.leader([(maxx, miny + 22.0), (maxx + 4.0, miny + 22.0), (maxx + 4.6, miny + 22.0)],
             "FACE OF CMU / RB-1 BASE", size=TXT["small"])
    sh.view_title(x + 0.3, y + 0.35, num, "TYPICAL CLASSROOM FLOOR PATTERN", sc, width=4.6,
                  note=f"ROOM {r.num} SHOWN")
    return (maxy - miny) * sc + 1.25 + 0.75


def corridor_pattern(sh, x, y, w, num):
    """typical corridor LVT-1 field with LVT-2 2'-0" bands centered on column grid lines."""
    r = next(q for q in M.ROOMS if q.num == "100")
    g = M.clear_room_poly(r)
    miny, maxy = g.bounds[1], g.bounds[3]
    sc = 3 / 16
    gx = [M.GRID_X["2"], M.GRID_X["3"]]
    xa, xb = gx[0] - 7.0, gx[1] + 7.0
    v = sh.view(x + 0.9 - xa * sc, y + 1.05 - miny * sc, sc)
    from shapely.geometry import box as _box
    seg = g.intersection(_box(xa, miny - 1, xb, maxy + 1))
    bands = [_box(c - 1.0, miny, c + 1.0, maxy) for c in gx]
    from shapely.ops import unary_union as _uu
    bu = _uu(bands)
    v.geom(seg.difference(bu), lw=None, hatch="plank", hatch_kw=dict(spacing=(3.0, 0.5), w="hair",
                                                                       col="g50"), stroke=False)
    v.geom(seg.intersection(bu), lw="fine", fill="g40")
    v.line((xa, miny), (xb, miny), lw="heavy")
    v.line((xa, maxy), (xb, maxy), lw="heavy")
    from .cad import break_line
    break_line(v, (xa, miny - 0.8), (xa, maxy + 0.8))
    break_line(v, (xb, miny - 0.8), (xb, maxy + 0.8))
    for k, c in zip(("2", "3"), gx):
        v.line((c, miny - 0.4), (c, maxy + 2.2), lw="hair", dash="grid")
        from .cad import grid_bubble
        grid_bubble(v, (c, maxy + 3.0), k, dia=0.3, size=TXT["small"] + 1.5)
    D(v, (gx[0], miny), (gx[1], miny), -1.6)
    dim_s(v, (gx[0] - 1.0, maxy), (gx[0] + 1.0, maxy), 1.0, "2'-0\"", side="l")
    v.dim((xb, miny), (xb, maxy), -1.4, text=ft(maxy - miny) + " CLEAR")
    v.leader([(gx[0] + 7.0, (miny + maxy) / 2), (gx[0] + 9.5, maxy + 1.8)],
             "LVT-1 6\" x 36\" PLANK, LONG DIRECTION E-W", size=TXT["small"])
    v.leader([(gx[1] + 0.4, miny + 3.0), (gx[1] + 3.0, miny - 2.4)],
             "LVT-2 BAND CENTERED ON GRID, FULL WIDTH", size=TXT["small"])
    sh.view_title(x + 0.3, y + 0.35, num, "TYPICAL CORRIDOR FLOOR PATTERN", sc, width=4.6,
                  note="CORRIDOR 100 / 200, ALL GRID LINES")


def casework_plan(sh, x, y, num):
    """typical classroom casework plan (clipped from the shared plan renderer)."""
    from . import plans as PL
    sc = 3 / 16
    rx0, ry0, rx1, ry1 = 29.0, 41.0, 61.0, 73.0
    ox, oy = x + 0.35, y + 0.95
    v = sh.view(ox - rx0 * sc, oy - ry0 * sc, sc)
    _clip_rect(sh, ox, oy, (rx1 - rx0) * sc, (ry1 - ry0) * sc)
    PL.draw_walls(v, "L1")
    PL.draw_openings(v, "L1")
    PL.draw_casework(v, "L1")
    sh.c.restoreState()
    sh.rect(ox, oy, (rx1 - rx0) * sc, (ry1 - ry0) * sc, lw="hair", color="g50")
    lx = ox + (rx1 - rx0) * sc + 0.22
    ly = oy + (ry1 - ry0) * sc - 0.1
    pv = Paper(sh.c)
    leg = [("base", "BASE CAB. CW-1 / CW-2, CT-1 TOP"),
           ("wall", "WALL CAB. CW-3 ABOVE"),
           ("tall", "TALL CAB. CW-4"),
           ("sink", "SINK (DIV. 22) AT CW-2"),
           ("cub", "STUDENT CUBBIES CW-5")]
    for kind, txt in leg:
        if kind == "base":
            sh.rect(lx, ly - 0.07, 0.3, 0.14, lw="thin")
        elif kind == "wall":
            sh.rect(lx, ly - 0.05, 0.3, 0.1, lw="hair", dash="hidden")
        elif kind == "tall":
            sh.rect(lx, ly - 0.07, 0.3, 0.14, lw="thin")
            sh.line((lx, ly - 0.07), (lx + 0.3, ly + 0.07), lw="hair")
            sh.line((lx, ly + 0.07), (lx + 0.3, ly - 0.07), lw="hair")
        elif kind == "sink":
            sh.circle((lx + 0.15, ly), 0.07, lw="hair")
        else:
            sh.rect(lx, ly - 0.06, 0.3, 0.12, lw="fine")
            for k_ in range(1, 3):
                sh.line((lx + k_ * 0.1, ly - 0.06), (lx + k_ * 0.1, ly + 0.06), lw="hair")
        sh.text((lx + 0.42, ly), txt, size=CELL, valign="mid")
        ly -= 0.27
    d = M.CASEWORK_TYPICAL["CLASSROOM"]
    ly -= 0.05
    sh.text((lx, ly), "PER CLASSROOM:", size=CELL, font=FONT_B, valign="mid")
    ly -= 0.2
    for k_ in CW_KEYS:
        if k_ in d:
            sh.text((lx, ly), f"{k_}: {d[k_]:g} {cw_unit(k_)}", size=CELL, valign="mid")
            ly -= 0.17
    sh.view_title(x + 0.3, y + 0.35, num, "TYPICAL CLASSROOM CASEWORK PLAN", sc, width=4.6,
                  note="CLASSROOM 102 SHOWN; SOUTH ROOMS MIRROR")


def stack(top, bot, blocks, gmin=0.3, gmax=0.9):
    """blocks: [(height, fn(top_y))]; draws top-down with evenly distributed gaps."""
    tot = sum(h for h, _ in blocks)
    n = len(blocks)
    g = (top - bot - tot) / max(1, n - 1)
    g = max(gmin, min(gmax, g))
    cy = top
    for i, (h, fn) in enumerate(blocks):
        if i == n - 1 and n > 1:
            cy = min(cy, bot + h)     # last block (a drawing) sits on the bottom line
        fn(cy)
        cy -= h + g
    return cy


def draw_a801(sh):
    x0, y0, x1, y1 = sh.x0, sh.y0, sh.x1, sh.y1
    al = ["c", "l", "c", "c", "c", "c", "c", "c", "c", "c", "l"]
    c1x = x0 + 0.25
    c1w = 10.55
    c2x = c1x + c1w + 0.45
    c2w = 10.55
    c3x = c2x + c2w + 0.45
    c3w = x1 - 0.2 - c3x
    for xx in (c2x - 0.22, c3x - 0.22):
        sh.line((xx, y0 + 0.1), (xx, y1 - 0.1), lw="thin")
    top, bot = y1 - 0.2, y0 + 0.1
    # ---- column 1: room finish schedules + classroom pattern ----
    k = c1w / table_w(ROOM_COLS)
    cols = [(h_, w_ * k) for h_, w_ in ROOM_COLS]
    rkw = dict(groups=ROOM_GROUPS, align=al, size=7.0, hsize=6.5, row_h=0.325)
    blocks = []
    for lev in ("L1", "L2"):
        ttl = f"ROOM FINISH SCHEDULE - LEVEL {lev[1]} (FFE {fmt_elev(M.LEVELS[lev])})"
        rows = room_rows(lev)
        h = sched_table(sh, 0, 0, cols, rows, title=ttl, draw=False, **rkw)
        blocks.append((h, lambda cy, rows=rows, ttl=ttl: sched_table(sh, c1x, cy, cols, rows,
                                                                     title=ttl, **rkw)))
    note = ("NO AREAS ARE SCHEDULED: QUANTITIES ARE BY TAKEOFF FROM A-101 / A-102 AND FINISH PLANS "
            "A-111 / A-112. STAIRS ST-1 / ST-2 OCCUR ON BOTH LEVELS. \"-\" = NONE / NOT APPLICABLE.")
    blocks.append((0.3, lambda cy: sh.mtext((c1x, cy), note, size=TXT["small"], width=c1w)))
    blocks.append((5.45, lambda cy: classroom_pattern(sh, c1x + 1.2, cy - 5.45, 1)))
    stack(top, bot, blocks)
    # ---- column 2: finish legend + notes + corridor pattern ----
    fl_cols = [("CODE", 0.6), ("DESCRIPTION (DIV. 09)", 2.9), ("BASIS OF DESIGN / REQUIREMENTS "
               "(MANUFACTURER-NEUTRAL)", 3.95), ("LOCATION (FROM ROOM SCHEDULE)", c2w - 7.45)]
    fkw = dict(title="FINISH LEGEND", size=6.5, hsize=6.0, row_h=0.3, align=["c", "l", "l", "l"])
    frows = finish_legend_rows()
    hl = sched_table(sh, 0, 0, fl_cols, frows, draw=False, **fkw)
    hn = notes_cols(sh, 0, 0, "ROOM FINISH NOTES", A801_FIN_NOTES, c2w, ncols=1, draw=False,
                    size=7.0)
    stack(top, bot, [
        (hl, lambda cy: sched_table(sh, c2x, cy, fl_cols, frows, **fkw)),
        (hn, lambda cy: notes_cols(sh, c2x, cy, "ROOM FINISH NOTES", A801_FIN_NOTES, c2w,
                                   size=7.0)),
        (4.0, lambda cy: corridor_pattern(sh, c2x + 0.15, cy - 4.0, c2w, 2)),
    ])
    # ---- column 3: casework ----
    cw_cols = [("ROOM\nNO.", 0.55), ("ROOM NAME", 1.45)] + \
              [(f"{c}\n({cw_unit(c)})", 0.55) for c in CW_KEYS] + \
              [("REMARKS", c3w - 2.0 - 0.55 * len(CW_KEYS))]
    ckw = dict(title="CASEWORK SCHEDULE (PER ROOM)", size=7.0, hsize=6.5, row_h=0.31,
               align=["c", "l"] + ["c"] * len(CW_KEYS) + ["l"])
    crows = casework_rows()
    hc = sched_table(sh, 0, 0, cw_cols, crows, draw=False, **ckw)
    cwn = ("VALUES ARE DESIGN LENGTHS (LF) OR UNITS (EA) PER ROOM AS SHOWN ON PLANS AND INTERIOR "
           "ELEVATIONS; NO TOTALS ARE SCHEDULED.")

    def _cw(cy):
        h = sched_table(sh, c3x, cy, cw_cols, crows, **ckw)
        sh.mtext((c3x, cy - h - 0.1), cwn, size=TXT["small"], width=c3w)
    ct_rows = [[k_, v_, cw_unit(k_), "A-502 / A-601"] for k_, v_ in M.CASEWORK_TYPES.items()]
    tcols = [("TAG", 0.55), ("DESCRIPTION", c3w - 0.55 - 0.5 - 1.05), ("UNIT", 0.5), ("SEE", 1.05)]
    tkw = dict(title="CASEWORK TYPES (SECTION 06 41 00)", size=6.75, row_h=0.3,
               align=["c", "l", "c", "c"])
    ht = sched_table(sh, 0, 0, tcols, ct_rows, draw=False, **tkw)
    hcn = notes_cols(sh, 0, 0, "CASEWORK NOTES", A801_CW_NOTES, c3w, draw=False, size=7.0)
    stack(top, bot, [
        (hc + 0.35, _cw),
        (ht, lambda cy: sched_table(sh, c3x, cy, tcols, ct_rows, **tkw)),
        (hcn, lambda cy: notes_cols(sh, c3x, cy, "CASEWORK NOTES", A801_CW_NOTES, c3w,
                                    size=7.0)),
        (7.1, lambda cy: casework_plan(sh, c3x - 0.25, cy - 7.1, 3)),
    ])


# ----------------------------------------------------------------------------------------
SHEETS = [
    ("A-701", "DOOR SCHEDULE,\nDOOR TYPES AND\nFRAME TYPES", draw_a701),
    ("A-702", "DOOR HARDWARE\nSETS", draw_a702),
    ("A-711", "WINDOW AND\nSTOREFRONT TYPES\nAND SCHEDULE", draw_a711),
    ("A-801", "ROOM FINISH SCHEDULE,\nFINISH LEGEND AND\nCASEWORK SCHEDULE", draw_a801),
]
