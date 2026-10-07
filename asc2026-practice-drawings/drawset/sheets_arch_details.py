"""A-501 EXTERIOR DETAILS and A-502 PARTITION TYPES & INTERIOR DETAILS.

Every detail is drawn in a DV ("detail view") whose model unit is the INCH (true size),
so all geometry below is written with real material sizes:
    brick 3 5/8" x 2 1/4" (3 courses = 8"), CMU 7 5/8" x 7 5/8" x 15 5/8" (8" module),
    2x lumber 1 1/2" x 3 1/2" / 5 1/2" / 7 1/4" / 9 1/4", plywood 3/4", GWB 5/8", etc.

Exterior wall (EW-1) layer offsets used throughout, measured in inches from the exterior
face of brick toward the interior (see DESIGN.md section 4 / model.EW_LAYERS):
    brick 0 .. 3 5/8 | air space .. 5 5/8 | polyiso .. 7 5/8 | CMU .. 15 1/4 (grid at 11 7/16)
Aluminum windows / storefront (2" x 4 1/2") are set 3 1/8" back from the brick face with the
interior face of frame flush with the exterior face of CMU (x = 3 1/8 .. 7 5/8).
"""
from __future__ import annotations

import math

from shapely.geometry import Polygon, box

from . import model as M
from .cad import (FONT, FONT_B, TXT, Paper, View, break_line, fmt_ftin, fmt_in, table,
                  notes_block, vlen, vsub, wrap_lines, wall_tag, door_tag, window_tag)
from reportlab.pdfbase.pdfmetrics import stringWidth

# ----------------------------------------------------------------------------------------
# Text standards for this module
# ----------------------------------------------------------------------------------------
NS = 6.0            # leader note text (pt)
DS = 5.6            # dimension text (pt)
LEADF = 1.17        # leading factor

# ----------------------------------------------------------------------------------------
# Wall build-up (inches from exterior face of brick)
# ----------------------------------------------------------------------------------------
XB1 = 3.625          # back of brick
XA1 = 5.625          # exterior face of rigid insulation
XC0 = 7.625          # exterior face of CMU / air barrier
XC1 = 15.25          # interior face of CMU
XG = 11.4375         # grid line (CMU centerline)
FR0, FR1 = 3.125, 7.625   # window / storefront frame zone
BRICK_H = 2.25
BRICK_MOD = 8.0 / 3.0
CMU_MOD = 8.0
CMU_H = 7.625
FS = 1.25            # CMU face shell


def fmt_len(inches: float) -> str:
    """inches -> 7 5/8"  or  1'-3 1/4" """
    if abs(inches) >= 11.99:
        return fmt_ftin(inches / 12.0, 16)
    return fmt_in(inches, 16)


# ----------------------------------------------------------------------------------------
# Detail view in inches
# ----------------------------------------------------------------------------------------
class DV(View):
    """Model unit = inch. scale_ft = paper inches per foot (1.5 => 1 1/2" = 1'-0")."""

    def __init__(self, c, ox, oy, scale_ft, mx=0.0, my=0.0):
        super().__init__(c, ox, oy, scale_ft / 12.0, mx, my)
        self.sft = scale_ft

    def dimi(self, p1, p2, off, text=None, **kw):
        L = vlen(vsub(p2, p1))
        if text is None:
            text = fmt_len(L)
        kw.setdefault("size", DS)
        self.dim(p1, p2, off, text=text, **kw)

    def pp(self, p):
        return self.to_paper(p)


def R(v, x0, y0, x1, y1, **kw):
    v.polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], **kw)


# ----------------------------------------------------------------------------------------
# Material primitives (all coordinates in inches)
# ----------------------------------------------------------------------------------------

def brick_courses(v, x0, x1, ylo, yhi, base, unit=BRICK_H, mod=BRICK_MOD, hatch=True,
                  lw="thin", skip=()):
    """Brick in section: units with bed joint at the BOTTOM of each module starting at `base`.
    Units are clipped to ylo..yhi."""
    k0 = math.floor((ylo - base) / mod) - 1
    k1 = math.ceil((yhi - base) / mod) + 1
    for k in range(k0, k1):
        if k in skip:
            continue
        b = base + k * mod + (mod - unit)
        t = base + (k + 1) * mod
        b2, t2 = max(b, ylo), min(t, yhi)
        if t2 - b2 < 0.05:
            continue
        R(v, x0, b2, x1, t2, lw=lw, fill="white",
          hatch="ansi31" if hatch else None, hatch_kw=dict(spacing=0.042, w="hair"))


def brick_unit(v, x0, y0, x1, y1, lw="thin"):
    R(v, x0, y0, x1, y1, lw=lw, fill="white", hatch="ansi31",
      hatch_kw=dict(spacing=0.042, w="hair"))


def cmu_courses(v, x0, x1, ylo, yhi, base, joint="bot", grout=(), bond=(), bars=None,
                lw="thin", vgrout=False):
    """CMU in vertical section (cut through the cores).
    Module k spans base+8k .. base+8k+8; joint 3/8" at bottom ('bot') or top ('top').
    grout: course indexes grouted; bond: course indexes that are bond-beam (U) units.
    bars: dict k -> list of x positions of horizontal bars (#5) in that course.
    vgrout: whole wall grouted (vertical reinforced cell cut)."""
    bars = bars or {}
    k0 = math.floor((ylo - base) / CMU_MOD) - 1
    k1 = math.ceil((yhi - base) / CMU_MOD) + 1
    for k in range(k0, k1):
        m0 = base + k * CMU_MOD
        b, t = (m0 + 0.375, m0 + 8.0) if joint == "bot" else (m0, m0 + CMU_H)
        b2, t2 = max(b, ylo), min(t, yhi)
        if t2 - b2 < 0.05:
            continue
        g = vgrout or k in grout or k in bond
        if g:
            R(v, x0 + FS, b2, x1 - FS, t2, lw=None, hatch="sand",
              hatch_kw=dict(scale=1.25, seed=k + 3), stroke=False)
        hk = dict(spacing=0.06, w="hair")
        R(v, x0, b2, x0 + FS, t2, lw="fine", fill="white", hatch="ansi31", hatch_kw=hk)
        R(v, x1 - FS, b2, x1, t2, lw="fine", fill="white", hatch="ansi31", hatch_kw=hk)
        if k in bond and b >= ylo:
            R(v, x0 + FS, b, x1 - FS, b + 1.25, lw="fine", fill="white", hatch="ansi31",
              hatch_kw=hk)
        R(v, x0, b2, x1, t2, lw=lw)
        for bx in bars.get(k, []):
            v.circle((bx, b + (3.0 if k in bond else 3.5)), 0.3125, lw=None, fill="black")


def cmu_plan(v, u0, u1, d0, d1, start, grout_cores=(), bars=(), end_bullnose=None,
             lw="thin", half_end=False):
    """CMU in plan: wall runs along u (paper x) from start (an END of a unit) to the right
    by whole units (16" module, unit 15 5/8"); the drawing is clipped to u0..u1.
    grout_cores: indexes of cores (2 per unit, counted from `start`) that are grouted.
    end_bullnose: 'r' -> 1" bullnose at the interior (d1) corner of the last unit end at u1.
    """
    from shapely.geometry import box as sbox
    clip = sbox(u0, d0 - 1, u1, d1 + 1)
    k = 0
    u = start
    ci = 0
    while u < u1 + 16:
        L = 15.625
        if half_end and u + 16 > u1 + 0.01 and abs((u1 - u) - 7.625) < 0.05:
            L = 7.625
        unit = sbox(u, d0, u + L, d1)
        if end_bullnose == "r" and abs(u + L - u1) < 0.05:
            r = 1.0
            unit = unit.difference(sbox(u + L - r, d1 - r, u + L, d1)).union(
                _circle_poly(u + L - r, d1 - r, r).intersection(sbox(u + L - r, d1 - r, u + L, d1)))
        cores = []
        if L > 10:
            c_l = (15.625 - 3.0) / 2
            for j, cu in enumerate((u + 1.0, u + 2.0 + c_l)):
                cores.append((ci + j, sbox(cu, d0 + FS, cu + c_l, d1 - FS)))
            ci += 2
        else:
            cores.append((ci, sbox(u + 1.0, d0 + FS, u + L - 1.0, d1 - FS)))
            ci += 1
        solid = unit
        for idx, cp in cores:
            solid = solid.difference(cp)
        solid = solid.intersection(clip)
        if not solid.is_empty:
            v.geom(solid, lw="fine", fill="white", hatch="ansi31",
                   hatch_kw=dict(spacing=0.06, w="hair"))
        for idx, cp in cores:
            cc = cp.intersection(clip)
            if cc.is_empty:
                continue
            if idx in grout_cores:
                v.geom(cc, lw="fine", hatch="sand", hatch_kw=dict(scale=1.25, seed=idx + 5))
                if idx in bars:
                    ctr = cp.centroid
                    if u0 <= ctr.x <= u1:
                        v.circle((ctr.x, ctr.y), 0.3125, lw=None, fill="black")
            else:
                v.geom(cc, lw="fine")
        uu = unit.intersection(clip)
        if not uu.is_empty:
            v.geom(uu, lw=lw)
        u += 16.0
        k += 1


def _circle_poly(cx, cy, r, n=24):
    return Polygon([(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n))
                    for i in range(n)])


def brick_plan(v, u0, u1, d0, d1, start, lw="thin"):
    """Brick in plan: 7 5/8" units + 3/8" head joints from `start` (end of unit) to the right."""
    u = start
    while u < u1 + 8:
        a, b = max(u, u0), min(u + 7.625, u1)
        if b - a > 0.05:
            R(v, a, d0, b, d1, lw=lw, fill="white", hatch="ansi31",
              hatch_kw=dict(spacing=0.042, w="hair"))
        u += 8.0


def rigid(v, x0, y0, x1, y1, lw="fine", pts=None):
    """Rigid board insulation (cross hatch)."""
    if pts is None:
        pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    v.polygon(pts, lw=lw, fill="white", hatch="insul", hatch_kw=dict(spacing=0.055, w="hair"))


def batt(v, x0, y0, x1, y1, vertical=True, lw="fine"):
    """Batt insulation: loop line along the long axis."""
    if vertical:
        w = x1 - x0
        L = y1 - y0
        n = max(2, int(L / (w * 0.55)))
        pts = []
        for i in range(n * 12 + 1):
            t = i / (n * 12)
            ang = t * n * 2 * math.pi
            pts.append((x0 + w / 2 + (w / 2) * math.sin(ang), y0 + t * L + (w * 0.18) * math.cos(ang)))
        pts = [(x, min(max(y, y0), y1)) for x, y in pts]
    else:
        w = y1 - y0
        L = x1 - x0
        n = max(2, int(L / (w * 0.55)))
        pts = []
        for i in range(n * 12 + 1):
            t = i / (n * 12)
            ang = t * n * 2 * math.pi
            pts.append((x0 + t * L + (w * 0.18) * math.cos(ang), y0 + w / 2 + (w / 2) * math.sin(ang)))
        pts = [(min(max(x, x0), x1), y) for x, y in pts]
    v.polyline(pts, lw=lw)


def wood(v, x0, y0, x1, y1, lw="thin"):
    """Dimension lumber / blocking in section: box with X."""
    R(v, x0, y0, x1, y1, lw=lw, fill="white")
    v.line((x0, y0), (x1, y1), lw="fine")
    v.line((x0, y1), (x1, y0), lw="fine")


def wood_poly(v, pts, lw="thin"):
    v.polygon(pts, lw=lw, fill="white", hatch="wood", hatch_kw=dict(w="fine"))


def plywood(v, x0, y0, x1, y1, lw="thin"):
    R(v, x0, y0, x1, y1, lw=lw, fill="white")
    if (x1 - x0) >= (y1 - y0):
        for f in (1 / 3, 2 / 3):
            y = y0 + (y1 - y0) * f
            v.line((x0, y), (x1, y), lw="hair")
    else:
        for f in (1 / 3, 2 / 3):
            x = x0 + (x1 - x0) * f
            v.line((x, y0), (x, y1), lw="hair")


def concrete(v, pts, lw="thin", seed=1):
    v.polygon(pts, lw=lw, fill="white", hatch="concrete", hatch_kw=dict(seed=seed))


def concrete_r(v, x0, y0, x1, y1, lw="thin", seed=1):
    concrete(v, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], lw, seed)


def caststone(v, pts, lw="thin"):
    v.polygon(pts, lw=lw, fill="white", hatch="sand", hatch_kw=dict(scale=1.6, seed=7))


def earth(v, pts, lw=None):
    v.polygon(pts, lw=lw, fill="white", hatch="earth", hatch_kw=dict(spacing=0.1),
              stroke=bool(lw))


def gravel(v, pts, lw=None):
    v.polygon(pts, lw=lw, fill="white", hatch="gravel", hatch_kw=dict(scale=0.8, seed=3),
              stroke=bool(lw))


def steel(v, pts):
    v.polygon(pts, lw="fine", fill="black")


def angle(v, heel, h, vl, t, dx=1, dy=1):
    """Steel angle in section. heel = outer corner; horizontal leg h toward dx, vertical vl
    toward dy, thickness t."""
    x, y = heel
    pts = [(x, y), (x + dx * h, y), (x + dx * h, y + dy * t), (x + dx * t, y + dy * t),
           (x + dx * t, y + dy * vl), (x, y + dy * vl)]
    steel(v, pts)


def wshape(v, cx, ytop, d, bf, tf, tw):
    pts = [(cx - bf / 2, ytop), (cx + bf / 2, ytop), (cx + bf / 2, ytop - tf), (cx + tw / 2, ytop - tf),
           (cx + tw / 2, ytop - d + tf), (cx + bf / 2, ytop - d + tf), (cx + bf / 2, ytop - d),
           (cx - bf / 2, ytop - d), (cx - bf / 2, ytop - d + tf), (cx - tw / 2, ytop - d + tf),
           (cx - tw / 2, ytop - tf), (cx - bf / 2, ytop - tf)]
    steel(v, pts)


def flashing(v, pts, lw=1.35):
    v.polyline(pts, lw=lw)


def membrane(v, pts, lw=1.35):
    v.polyline(pts, lw=lw)


def air_barrier(v, pts):
    v.polyline(pts, lw="med", dash=[2.2, 1.2])


def rod(v, c, r=0.3125):
    """closed-cell backer rod"""
    v.circle(c, r, lw="fine", fill="white")


def bead(v, pts):
    """sealant bead (gray)"""
    v.polygon(pts, lw="fine", fill="g40")


def sealant_h(v, x0, x1, y, depth, up=True, rod_r=None):
    """Sealant joint spanning x0..x1 (joint width) whose exposed face is at y; sealant
    extends `depth` into the joint (up or down) with a backer rod behind."""
    s = 1 if up else -1
    w = x1 - x0
    bead(v, [(x0, y), (x0 + w * 0.5, y + s * depth * 0.45), (x1, y), (x1, y + s * depth),
             (x0, y + s * depth)])
    rr = rod_r or w * 0.55
    rod(v, ((x0 + x1) / 2, y + s * (depth + rr)), rr)


def sealant_v(v, y0, y1, x, depth, right=True, rod_r=None):
    """Vertical joint spanning y0..y1 with exposed face at x."""
    s = 1 if right else -1
    w = y1 - y0
    bead(v, [(x, y0), (x + s * depth * 0.45, (y0 + y1) / 2), (x, y1), (x + s * depth, y1),
             (x + s * depth, y0)])
    rr = rod_r or w * 0.55
    rod(v, (x + s * (depth + rr), (y0 + y1) / 2), rr)


def glass_v(v, xc, y0, y1, t=1.0, lite=0.25):
    """Insulating glass unit, vertical (in section), centered at xc."""
    a = xc - t / 2
    R(v, a, y0, a + lite, y1, lw="fine", fill="white")
    R(v, a + t - lite, y0, a + t, y1, lw="fine", fill="white")


def glass_h(v, yc, x0, x1, t=1.0, lite=0.25):
    a = yc - t / 2
    R(v, x0, a, x1, a + lite, lw="fine", fill="white")
    R(v, x0, a + t - lite, x1, a + t, lw="fine", fill="white")


def alum(v, pts, lw="thin"):
    v.polygon(pts, lw=lw, fill="g10")


def tbreak(v, x0, y0, x1, y1):
    R(v, x0, y0, x1, y1, lw="fine", fill="g60")


def bar_dot(v, x, y, r=0.3125):
    v.circle((x, y), r, lw=None, fill="black")


def brk(v, p1, p2, zig=0.07):
    break_line(v, p1, p2, zig)


def deck_profile(v, x0, x1, ybot, depth=1.5, pitch=6.0, top=3.5, bot=1.75, phase=0.0,
                 lw="med"):
    """1 1/2" type B roof deck profile (ribs perpendicular to the cut)."""
    pts = []
    x = x0 - pitch + phase
    w_slope = (pitch - top - bot) / 2
    while x < x1 + pitch:
        seg = [(x, ybot), (x + bot, ybot), (x + bot + w_slope, ybot + depth),
               (x + bot + w_slope + top, ybot + depth), (x + pitch, ybot)]
        pts.extend(seg)
        x += pitch
    out = []
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        if b[0] < x0 or a[0] > x1:
            continue
        def clipx(p, q):
            if p[0] < x0:
                t = (x0 - p[0]) / (q[0] - p[0]) if q[0] != p[0] else 0
                p = (x0, p[1] + t * (q[1] - p[1]))
            return p
        a2 = clipx(a, b)
        b2 = b if b[0] <= x1 else (x1, a[1] + (x1 - a[0]) / (b[0] - a[0]) * (b[1] - a[1]))
        out.append((a2, b2))
    for a, b in out:
        v.line(a, b, lw=lw)


# ----------------------------------------------------------------------------------------
# Annotation helpers (paper space)
# ----------------------------------------------------------------------------------------

def _arrow(p: Paper, tip, frm, size=0.06):
    dx, dy = tip[0] - frm[0], tip[1] - frm[1]
    L = math.hypot(dx, dy) or 1.0
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    bx, by = tip[0] - ux * size, tip[1] - uy * size
    w = size * 0.3
    p.polygon([tip, (bx + nx * w, by + ny * w), (bx - nx * w, by - ny * w)], lw="fine",
              fill="black")


def notes_col(sh, v, items, x, side, width, ylo, yhi, size=NS, gap=0.045, shoulder=0.12):
    """Stack leader notes in a column and draw leaders to their targets.

    items : list of (target, text) or (target, text, desired_paper_y). target is a model
            point (inches) or a list of model points (multiple leaders from one note).
    side  : 'l' -> column of right-aligned text ending at paper x (drawing is to the right)
            'r' -> column of left-aligned text starting at paper x (drawing is to the left)
    """
    lead = size * LEADF / 72.0
    blocks = []
    for it in items:
        tgt, text = it[0], it[1]
        tl = tgt if isinstance(tgt, list) else [tgt]
        tp = [v.to_paper(t) for t in tl]
        dy = it[2] if len(it) > 2 and it[2] is not None else sum(q[1] for q in tp) / len(tp)
        lines = wrap_lines([text.upper()], size, FONT, width)
        blocks.append(dict(tp=tp, lines=lines, want=dy, n=len(lines)))
    blocks.sort(key=lambda b: -b["want"])
    # first line center yc; block top = yc + lead/2 ; bottom = top - n*lead
    prev_bot = yhi + gap
    for b in blocks:
        yc = min(b["want"], prev_bot - gap - lead / 2)
        b["yc"] = yc
        prev_bot = yc + lead / 2 - b["n"] * lead
    # push up from the bottom if needed
    nxt_top = ylo - gap
    for b in reversed(blocks):
        bot = b["yc"] + lead / 2 - b["n"] * lead
        lim = nxt_top + gap
        if bot < lim:
            b["yc"] += lim - bot
        nxt_top = b["yc"] + lead / 2
    for b in blocks:
        top = b["yc"] + lead / 2
        tw = max(stringWidth(ln, FONT, size) for ln in b["lines"]) / 72.0
        bx0 = x - tw - 0.02 if side == "l" else x - 0.02
        sh.rect(bx0, top - b["n"] * lead - 0.01, tw + 0.04, b["n"] * lead + 0.02, lw=None,
                fill="white", stroke=False)
        sh.mtext((x, top + size * 0.02 / 72), b["lines"], size=size, anchor="r" if side == "l" else "l",
                 valign="top", leading=size * LEADF)
        w1 = stringWidth(b["lines"][0], FONT, size) / 72.0
        yc = b["yc"]
        for tp in b["tp"]:
            if side == "l":
                if tp[0] < x - w1 - 0.05:          # target lies left of the text: attach left
                    sx, ex = x - w1 - 0.04, x - w1 - shoulder
                else:
                    sx, ex = x + 0.04, x + shoulder
            else:
                if tp[0] > x + w1 + 0.05:          # target lies right of the text: attach right
                    sx, ex = x + w1 + 0.04, x + w1 + shoulder
                else:
                    sx, ex = x - 0.04, x - shoulder
            sh.line((sx, yc), (ex, yc), lw="fine")
            sh.line((ex, yc), tp, lw="fine")
            _arrow(sh, tp, (ex, yc))


def label(sh, v, at, text, size=NS, anchor="c", font=FONT, rot=0):
    sh.text(v.to_paper(at), text, size=size, anchor=anchor, valign="mid", font=font, rot=rot)


def elev_tag(sh, v, at, lab, val, side="r", length=0.5):
    """Datum: short line from model point, target symbol, label + elevation."""
    px, py = v.to_paper(at)
    d = 1 if side == "r" else -1
    ex = px + d * length
    sh.line((px, py), (ex, py), lw="fine", dash=[3, 1.5])
    r = 0.05
    sh.circle((ex, py), r, lw="fine", fill="white")
    for a0 in (0, 180):
        path = sh.c.beginPath()
        path.moveTo(ex * 72, py * 72)
        path.arcTo((ex - r) * 72, (py - r) * 72, (ex + r) * 72, (py + r) * 72, a0, 90)
        path.close()
        sh.c.setFillColorRGB(0, 0, 0)
        sh.c.drawPath(path, stroke=0, fill=1)
    tx = ex + d * 0.09
    anc = "l" if side == "r" else "r"
    sh.text((tx, py + 0.025), lab, size=DS, font=FONT_B, anchor=anc, valign="bot")
    sh.text((tx, py - 0.02), val, size=DS, anchor=anc, valign="top")


def title(sh, c, num, text, scale, note=None):
    sh.view_title(c["x"] + 0.18, c["y"] + 0.36, num, text, scale, width=None, note=note)


def fit_view(c, ext, sft, left=0.0, right=0.0, top=0.12, bot=0.72, dx=0.0, dy=0.0):
    """Place a DV so that model extents ext=(x0,y0,x1,y1) (inches) are centered in the cell
    leaving `left`/`right` paper inches for note columns."""
    s = sft / 12.0
    x0, y0, x1, y1 = ext
    w, h = (x1 - x0) * s, (y1 - y0) * s
    ax0 = c["x"] + left
    ax1 = c["x"] + c["w"] - right
    ay0 = c["y"] + bot
    ay1 = c["y"] + c["h"] - top
    ox = ax0 + ((ax1 - ax0) - w) / 2 + dx
    oy = ay0 + ((ay1 - ay0) - h) / 2 + dy
    return ox, oy, x0, y0


def make_dv(sh, c, ext, sft, **kw):
    ox, oy, mx, my = fit_view(c, ext, sft, **kw)
    return DV(sh.c, ox, oy, sft, mx, my)


def layout_rows(sh, rows):
    """rows: list of (height, [widths]) from the top. Returns flat list of cells and draws the
    cell borders (fine lines)."""
    cells = []
    y = sh.y1
    for h, widths in rows:
        tot = sum(widths)
        k = sh.w / tot
        x = sh.x0
        for i, w in enumerate(widths):
            ww = w * k
            cells.append({"x": x, "y": y - h, "w": ww, "h": h})
            if i:
                sh.line((x, y - h), (x, y), lw="fine")
            x += ww
        y -= h
        if y > sh.y0 + 0.01:
            sh.line((sh.x0, y), (sh.x1, y), lw="fine")
    return cells


def cell_dbg(sh, c):
    sh.rect(c["x"], c["y"], c["w"], c["h"], lw="hair", color="red")


# ========================================================================================
# A-501 EXTERIOR DETAILS
# ========================================================================================

def ext_wall_section(v, ylo, yhi, brick_base, cmu_base, cmu_joint="bot", grout=(), bond=(),
                     bars=None, insul=True, air=True, brick=True, cmu=True, brick_skip=()):
    if brick:
        brick_courses(v, 0, XB1, ylo, yhi, brick_base, skip=brick_skip)
    if insul:
        rigid(v, XA1, ylo, XC0, yhi)
    if cmu:
        cmu_courses(v, XC0, XC1, ylo, yhi, cmu_base, joint=cmu_joint, grout=grout, bond=bond,
                    bars=bars)


def veneer_anchor(v, y_cmu, y_brk, x_in=10.0):
    v.polyline([(x_in, y_cmu), (XC0 + 0.05, y_cmu), (XA1 - 0.6, y_cmu), (XA1 - 0.6, y_brk),
                (1.2, y_brk)], lw="med")
    v.line((XA1 - 0.6, y_cmu), (XA1 - 0.6, y_brk), lw="med")


def setup(sh, c, ext, sft, wl=1.4, wr=1.4, top=0.14, bot=0.74, pad=0.24, dx=0.0, dy=0.0):
    """Create the detail view centered between the note columns of cell c.
    Returns (view, xl, xr, ylo, yhi): xl = right edge of the left note column, xr = left edge
    of the right note column, ylo/yhi = vertical band available for notes."""
    xl = c["x"] + 0.1 + wl
    xr = c["x"] + c["w"] - 0.1 - wr
    a0 = xl + pad if wl > 0 else c["x"] + 0.15
    a1 = xr - pad if wr > 0 else c["x"] + c["w"] - 0.15
    s = sft / 12.0
    w = (ext[2] - ext[0]) * s
    h = (ext[3] - ext[1]) * s
    ay0 = c["y"] + bot
    ay1 = c["y"] + c["h"] - top
    if w > a1 - a0 + 0.02 or h > ay1 - ay0 + 0.02:
        print(f"  [warn] detail at ({c['x']:.1f},{c['y']:.1f}) does not fit: need {w:.2f}x{h:.2f}, "
              f"have {a1 - a0:.2f}x{ay1 - ay0:.2f}")
    ox = a0 + (a1 - a0 - w) / 2 + dx
    oy = ay0 + (ay1 - ay0 - h) / 2 + dy
    v = DV(sh.c, ox, oy, sft, ext[0], ext[1])
    return v, xl, xr, ay0, ay1


def dtitle(sh, c, num, text, sft, note=None):
    """View title at the bottom-left of the cell. sft = paper inches per foot."""
    tw = stringWidth(text.upper(), FONT_B, TXT["sub"]) / 72.0
    nw = stringWidth(note, FONT, TXT["small"]) / 72.0 if note else 0.0
    width = max(tw + 0.15, (1.3 + nw) if note else 0.0)
    sh.view_title(c["x"] + 0.18, c["y"] + 0.36, num, text, sft, width=width, note=note)


# ---------------------------------------------------------------------------------------- 1
def det_wa_head(sh, c):
    """W-A window head. y = 0 at head (MO) = 109'-4" (L1) / 123'-4" (L2)."""
    sft = 1.5
    ext = (-0.8, -11.6, 20.6, 26.4)
    v, xl, xr, ylo, yhi = setup(sh, c, ext, sft, wl=1.38, wr=1.33)
    top = 25.0
    # brick: FB-2 soldier on lintel + FB-1 running bond above (bed joint at bottom of module)
    brick_unit(v, 0, 0.375, XB1, 8.0)
    brick_courses(v, 0, XB1, 8.0, top, 8.0)
    # L5x3 1/2x5/16 LLV loose lintel, heel 1/8" behind back of brick
    angle(v, (4.0625, 0.0), 3.5, 5.0, 0.3125, dx=-1, dy=1)
    # PT blocking, spray foam fill below flashing, cavity insulation above
    wood(v, 4.125, 0.0, XC0, 1.5)
    yfl = lambda x: 5.1 + (8.2 - 5.1) / (7.55 - 3.69) * (x - 3.69)
    rigid(v, 0, 0, 0, 0, pts=[(4.125, 1.5), (7.5, 1.5), (7.5, yfl(7.5)), (4.125, yfl(4.125))])
    rigid(v, 0, 0, 0, 0, pts=[(XA1, yfl(XA1) + 0.12), (7.5, yfl(7.5) + 0.12), (7.5, top), (XA1, top)])
    # CMU: bond beam lintel (2 courses) + hollow units; MO = bottom of lintel units
    cmu_courses(v, XC0, XC1, 0.0, top, 0.0, joint="top", bond=(0, 1),
                bars={0: [9.9, 12.95]})
    flashing(v, [(-0.32, 0.12), (-0.55, 0.36), (3.69, 0.36), (3.69, 5.1), (7.55, 8.2),
                 (7.55, 13.5)])
    R(v, 7.55, 12.6, 7.85, 13.6, lw="fine", fill="black")
    air_barrier(v, [(7.7, top), (7.7, 0.07), (9.8, 0.07)])
    veneer_anchor(v, 15.81, 16.21)
    # window head member + glass
    alum(v, [(FR0, -0.5), (FR1, -0.5), (FR1, -2.5), (6.15, -2.5), (6.15, -1.25), (4.6, -1.25),
             (4.6, -2.5), (FR0, -2.5)])
    tbreak(v, 5.2, -1.25, 5.55, -0.5)
    glass_v(v, 5.375, -9.0, -1.55)
    R(v, 5.125, -1.95, 5.625, -1.55, lw="fine", fill="g50")
    R(v, 4.6, -2.5, 4.875, -1.75, lw="fine", fill="black")
    R(v, 5.875, -2.5, 6.15, -1.75, lw="fine", fill="black")
    brk(v, (2.6, -9.0), (8.2, -9.0))
    # perimeter sealant (exterior and interior)
    sealant_v(v, -0.5, 0.0, FR0, 0.4, right=True, rod_r=0.27)
    sealant_v(v, -0.5, 0.0, FR1, 0.4, right=False, rod_r=0.27)
    # ACT ceiling 8" above head
    R(v, XC1, 8.0, 18.2, 8.625, lw="thin", fill="g10")
    v.polyline([(XC1 + 0.05, 9.4), (XC1 + 0.05, 7.95), (XC1 + 0.95, 7.95)], lw="med")
    brk(v, (18.2, 6.9), (18.2, 9.8))
    brk(v, (-0.6, top), (XC1 + 0.6, top))
    # dimensions
    v.dimi((XC1, 0.0), (XC1, 8.0), -2.2)
    v.dimi((19.6, 0.0), (19.6, 16.0), -0.01, text="1'-4\" LINTEL", ext=False)
    v.line((XC1 + 0.3, 16.0), (20.3, 16.0), lw="hair")
    v.line((XC1 + 0.3, 0.0), (20.3, 0.0), lw="hair")
    v.dimi((0.0, -0.5), (FR0, -0.5), -10.3)
    v.dimi((FR0, -0.5), (FR1, -0.5), -10.3)
    v.dimi((0.0, top), (XC1, top), 1.6)
    notes_col(sh, v, [
        ((1.8, 21.0), "FB-1 FACE BRICK, RUNNING BOND"),
        ((3.0, 16.2), "ADJUSTABLE 2-PIECE VENEER ANCHOR @ 16\" O.C. EA. WAY; ADD'L WITHIN 12\" OF OPENING"),
        ((4.6, 22.5), "2\" AIR SPACE"),
        ((6.6, 19.5), "2\" POLYISO CAVITY INSULATION"),
        ((5.6, 6.65), "THRU-WALL FLASHING W/ SS DRIP EDGE, LAP 8\" UP CMU + TERM. BAR; END DAMS EA. END"),
        ((1.8, 4.2), "FB-2 SOLDIER COURSE (8\")"),
        ((1.4, 0.7), "WEEP VENTS @ 24\" O.C."),
        ((1.8, 0.16), "BL-2: L5x3 1/2x5/16 LLV GALV. LOOSE LINTEL, 8\" BRG. EA. END (S-302)"),
        ((FR0 + 0.15, -0.25), "SEALANT + BACKER ROD"),
    ], xl, "l", 1.38, ylo, yhi)
    notes_col(sh, v, [
        ((13.0, 12.0), "CL-2: 16\" CMU BOND BEAM LINTEL (2 COURSES), (2) #5 BOT., GROUT SOLID (S-302)"),
        ((7.7, 19.0), "FLUID-APPLIED AIR / WATER BARRIER, TURN 2\" ONTO SOFFIT"),
        ((6.4, 0.75), "2x4 PT WOOD BLOCKING (RIPPED), ANCHOR @ 16\" O.C."),
        ((6.4, 3.4), "CLOSED-CELL SPRAY FOAM FILL"),
        ((17.5, 8.3), "ACT-1 CEILING 10'-0\" AFF"),
        ((FR1 - 0.2, -0.25), "INT. SEALANT + BACKER ROD (AIR SEAL)"),
        ((6.9, -1.7), "W-A ALUM. WINDOW 2\" x 4 1/2\" THERMALLY BROKEN (A-711)"),
        ((5.75, -6.0), "1\" INSULATED LOW-E GLASS"),
    ], xr, "r", 1.33, ylo, yhi)
    dtitle(sh, c, 1, "W-A WINDOW HEAD", sft, note="HEAD 109'-4\" (L1) / 123'-4\" (L2)")


# ---------------------------------------------------------------------------------------- 2/6
def jamb_plan(sh, c, num, ttl, kind="W-A"):
    """Plan detail at the jamb of a W-A window or SF-1 storefront (3" = 1'-0").
    u (paper x) along the wall, MO at u = 0, opening to the right; d (paper y) = depth from
    the exterior face of brick (exterior at the bottom)."""
    sft = 3.0
    ext = (-10.2, -1.9, 5.6, 17.4)
    v, xl, xr, ylo, yhi = setup(sh, c, ext, sft, wl=0.0, wr=1.62, pad=0.3)
    u0 = -7.2
    brick_plan(v, u0, 0.0, 0.0, XB1, start=-23.625)
    rigid(v, u0, XA1, -1.56, XC0)
    cmu_plan(v, u0, 0.0, XC0, XC1, start=-15.625, grout_cores={1}, bars=set(), end_bullnose="r")
    bar_dot(v, -5.2, 11.4375)
    bar_dot(v, -3.0, 11.4375)
    air_barrier(v, [(u0, XC0 + 0.05), (-1.5, XC0 + 0.05)])
    wood(v, -1.5, 4.125, 0.0, XC0)
    v.polyline([(-4.0, XC0 - 0.07), (-1.57, XC0 - 0.07), (-1.57, 4.06), (0.07, 4.06),
                (0.07, 9.7)], lw=1.0)
    # frame jamb
    alum(v, [(0.5, FR0), (2.5, FR0), (2.5, 4.625), (1.25, 4.625), (1.25, 6.125), (2.5, 6.125),
             (2.5, FR1), (0.5, FR1)])
    tbreak(v, 0.5, 5.2, 1.25, 5.55)
    glass_h(v, 5.375, 1.55, 5.2)
    R(v, 1.55, 5.125, 1.95, 5.625, lw="fine", fill="g50")
    R(v, 1.75, 4.625, 2.5, 4.875, lw="fine", fill="black")
    R(v, 1.75, 5.875, 2.5, 6.125, lw="fine", fill="black")
    brk(v, (5.2, 3.6), (5.2, 7.2))
    # anchor screw + shim
    R(v, 0.08, 6.55, 0.5, 7.25, lw="fine", fill="g40")
    v.line((1.1, 6.9), (-1.25, 6.9), lw="med")
    R(v, 1.1, 6.72, 1.22, 7.08, lw="fine", fill="black")
    # sealants
    sealant_h(v, 0.0, 0.5, FR0, 0.3, up=True, rod_r=0.27)
    sealant_h(v, 0.0, 0.5, FR1, 0.3, up=False, rod_r=0.27)
    # breaks
    brk(v, (u0, -0.5), (u0, XC1 + 0.6))
    # dims
    v.dimi((0.5, XC1), (0.0, XC1), -1.2, text="1/2\"")
    v.dimi((0.5, XC1), (2.5, XC1), -1.2)
    v.dimi((u0, 0.0), (u0, FR0), 1.3)
    v.dimi((u0, FR0), (u0, FR1), 1.3)
    v.dimi((u0, FR1), (u0, XC1), 1.3)
    v.dimi((u0, 0.0), (u0, XC1), 2.6)
    v.line((0.0, -0.25), (0.0, -1.1), lw="fine")
    label(sh, v, (0.0, -1.45), "MO", size=DS, font=FONT_B)
    label(sh, v, (-4.6, -1.2), "EXTERIOR", size=DS, font=FONT_B)
    label(sh, v, (-4.6, 16.7), "INTERIOR", size=DS, font=FONT_B)
    if kind == "W-A":
        fr = "W-A ALUM. WINDOW JAMB 2\" x 4 1/2\", THERMALLY BROKEN (A-711)"
        gl = "1\" INSULATED LOW-E GLASS"
        anc = "FRAME ANCHOR CLIP / SCREW @ 16\" O.C. INTO BLOCKING, SHIM AT ANCHORS"
        blk = "2x4 PT WOOD BLOCKING (CAVITY CLOSURE) FULL HEIGHT OF JAMB, ANCHOR @ 16\" O.C."
    else:
        fr = "SF-1 STOREFRONT JAMB 2\" x 4 1/2\" CENTER-SET, THERMALLY BROKEN (A-711)"
        gl = "1\" INSULATED LOW-E TEMPERED GLASS (SIDELITE)"
        anc = "JAMB ANCHORS @ 12\" O.C. (3 MIN.) INTO BLOCKING, SHIM AT ANCHORS"
        blk = "2x4 PT WOOD BLOCKING (CAVITY CLOSURE) FULL HEIGHT (9'-4\"), ANCHOR @ 12\" O.C."
    notes_col(sh, v, [
        ((-6.0, 12.5), "8\" CMU; BULLNOSE JAMB UNITS; PNT-1"),
        ((-4.1, 11.3), "GROUT JAMB CELL SOLID W/ (2) #5 VERT. FULL HEIGHT (S-302)"),
        ((-6.5, XC0 + 0.05), "FLUID-APPLIED AIR / WATER BARRIER"),
        ([(-3.0, XC0 - 0.07), (0.07, 8.9)], "SELF-ADHERED TRANSITION MEMBRANE, WRAP BLOCKING, LAP 2\" ONTO CMU RETURN"),
        ((-0.75, 5.6), blk),
        ((-5.0, 6.6), "2\" POLYISO INSULATION"),
        ((-5.0, 4.6), "2\" AIR SPACE"),
        ((-3.8, 1.8), "FB-1 BRICK, ALTERNATE FULL / HALF UNITS AT JAMB"),
        ((0.25, FR0 + 0.15), "SEALANT + BACKER ROD"),
        ((0.25, FR1 - 0.15), "INTERIOR SEALANT + BACKER ROD"),
        ((-0.6, 6.9), anc),
        ((1.9, 3.4), fr),
        ((4.3, 5.25), gl),
    ], xr, "r", 1.62, ylo, yhi)
    dtitle(sh, c, num, ttl, sft)


def det_wa_jamb(sh, c):
    jamb_plan(sh, c, 2, "W-A WINDOW JAMB", "W-A")


def det_sf1_jamb(sh, c):
    jamb_plan(sh, c, 6, "SF-1 STOREFRONT JAMB", "SF-1")


# ---------------------------------------------------------------------------------------- 3
def det_wa_sill(sh, c):
    """W-A sill. y = 0 at sill (MO) = top of CMU = 102'-8" (L1) / 116'-8" (L2)."""
    sft = 1.5
    ext = (-1.6, -19.5, 19.2, 12.6)
    v, xl, xr, ylo, yhi = setup(sh, c, ext, sft, wl=1.38, wr=1.33)
    bot = -18.0
    # brick below (coursing adjusted to the cast stone bed)
    brick_courses(v, 0, XB1, bot, -4.375, -4.375)
    rigid(v, XA1, bot, XC0, -3.0)
    cmu_courses(v, XC0, XC1, bot, 0.0, 0.0, joint="bot")
    air_barrier(v, [(7.7, bot), (7.7, -3.05)])
    veneer_anchor(v, -7.81, -7.0)
    # CS-1 cast stone sill: 4" high at back, 3 1/2" at face, 1" projection, drip
    stone = Polygon([(-1.0, -4.0), (4.0, -4.0), (4.0, 0.0), (3.0, 0.0), (-1.0, -0.5), (-1.0, -4.0)])
    stone = stone.difference(Polygon([(-0.75, -4.01), (-0.55, -3.7), (-0.35, -4.01)]))
    v.geom(stone, lw="thin", fill="white", hatch="sand", hatch_kw=dict(scale=1.6, seed=7))
    # through-wall flashing under stone with drip + back leg
    flashing(v, [(-0.25, -4.55), (-0.05, -4.2), (4.08, -4.2), (4.08, -1.0)])
    # (2) 2x4 PT blocking flat in cavity
    wood(v, 4.125, -3.0, XC0, -1.5)
    wood(v, 4.125, -1.5, XC0, 0.0)
    # sill pan flashing w/ end dams, back leg up
    flashing(v, [(2.4, 0.04), (4.0, 0.04), (7.75, 0.04), (7.75, 1.4)], lw=1.0)
    # frame sill + awning vent sash bottom rail + glass
    alum(v, [(FR0, 0.5), (FR1, 0.5), (FR1, 2.5), (6.15, 2.5), (6.15, 1.25), (4.6, 1.25),
             (4.6, 2.5), (FR0, 2.5)])
    tbreak(v, 5.2, 0.5, 5.55, 1.25)
    alum(v, [(4.0, 2.75), (6.75, 2.75), (6.75, 4.6), (6.15, 4.6), (6.15, 3.55), (4.6, 3.55),
             (4.6, 4.6), (4.0, 4.6)])
    glass_v(v, 5.375, 3.65, 10.0)
    brk(v, (3.4, 10.0), (7.3, 10.0))
    R(v, 5.0, 0.04, 5.75, 0.5, lw="fine", fill="black")
    sealant_v(v, 0.04, 0.5, FR0, 0.35, right=True, rod_r=0.22)
    # interior: 2x8 FRT blocking + solid surface stool
    wood(v, 7.875, 0.0, 7.875 + 7.25, 1.5)
    R(v, 7.7, 1.5, XC1 + 0.75, 2.25, lw="thin", fill="g20")
    bead(v, [(FR1, 2.25), (7.7, 2.25), (7.7, 2.5), (FR1, 2.5)])
    brk(v, (-0.6, bot), (XC1 + 0.6, bot))
    # dims
    v.dimi((-1.0, -0.5), (0.0, -0.5), 2.0, text="1\"")
    v.dimi((-1.0, -4.0), (-1.0, 0.0), 1.0, text="4\"")
    v.dimi((FR0, 0.5), (FR1, 0.5), 11.2, text="4 1/2\"")
    v.dimi((0.0, bot), (XC1, bot), -1.2)
    notes_col(sh, v, [
        ((4.3, 3.9), "AWNING VENT SASH (W-A)"),
        ((FR0 + 0.2, 0.3), "SEALANT + BACKER ROD; LEAVE 1/2\" GAPS AT FRAME WEEPS"),
        ((1.6, -1.6), "CS-1 CAST STONE SILL, 4\" HIGH, WASH 1/2\", 1\" PROJECTION W/ DRIP; ANCHOR EA. END"),
        ((0.9, -4.2), "THRU-WALL FLASHING W/ SS DRIP UNDER SILL, END DAMS, BACK LEG TURNED UP"),
        ((1.8, -11.0), "FB-1 FACE BRICK"),
        ((3.0, -7.0), "ADJUSTABLE VENEER ANCHOR"),
        ((4.6, -14.0), "2\" AIR SPACE"),
        ((6.6, -12.0), "2\" POLYISO INSULATION"),
    ], xl, "l", 1.38, ylo, yhi)
    notes_col(sh, v, [
        ((5.75, 7.0), "1\" INSULATED LOW-E GLASS"),
        ((6.9, 1.8), "W-A SILL FRAME 2\" x 4 1/2\" (A-711)"),
        ((5.4, 0.25), "SHIMS / SETTING CHAIRS AT ANCHORS"),
        ((7.75, 1.0), "SELF-ADHERED SILL PAN FLASHING, END DAMS + BACK LEG"),
        ((6.0, -0.75), "(2) 2x4 PT WOOD BLOCKING, ANCHOR @ 16\" O.C."),
        ((13.0, 2.0), "3/4\" SOLID SURFACE STOOL, 3/4\" OVERHANG, EASED EDGES"),
        ((13.5, 0.8), "2x8 FRT WOOD BLOCKING, ANCHOR @ 16\" O.C."),
        ((11.0, -4.0), "8\" CMU BELOW SILL, PNT-1 (S-302)"),
        ((7.7, -10.0), "AIR / WATER BARRIER"),
    ], xr, "r", 1.33, ylo, yhi)
    dtitle(sh, c, 3, "W-A WINDOW SILL", sft, note="SILL 102'-8\" (L1) / 116'-8\" (L2)")


# ---------------------------------------------------------------------------------------- 4
def det_sf1_head(sh, c):
    """SF-1 storefront head. y = 0 at head (MO) 109'-4". CL-3 + BL-3 per S-302 lintel schedule."""
    sft = 1.5
    ext = (-0.8, -11.6, 20.6, 26.4)
    v, xl, xr, ylo, yhi = setup(sh, c, ext, sft, wl=1.38, wr=1.33)
    top = 25.0
    brick_courses(v, 0, XB1, 0.0, top, 0.0)
    angle(v, (4.125, 0.0), 4.0, 6.0, 0.375, dx=-1, dy=1)
    wood(v, 4.1875, 0.0, XC0, 1.5)
    yfl = lambda x: 6.1 + (9.2 - 6.1) / (7.55 - 3.69) * (x - 3.69)
    rigid(v, 0, 0, 0, 0, pts=[(4.19, 1.5), (7.5, 1.5), (7.5, yfl(7.5)), (4.19, yfl(4.19))])
    rigid(v, 0, 0, 0, 0, pts=[(XA1, yfl(XA1) + 0.12), (7.5, yfl(7.5) + 0.12), (7.5, top), (XA1, top)])
    cmu_courses(v, XC0, XC1, 0.0, top, 0.0, joint="top", bond=(0, 1, 2),
                bars={0: [9.9, 12.95], 2: [9.9, 12.95]})
    flashing(v, [(-0.32, 0.17), (-0.55, 0.42), (3.69, 0.42), (3.69, 6.1), (7.55, 9.2),
                 (7.55, 14.5)])
    R(v, 7.55, 13.6, 7.85, 14.6, lw="fine", fill="black")
    air_barrier(v, [(7.7, top), (7.7, 0.07), (9.8, 0.07)])
    veneer_anchor(v, 15.81, 16.4)
    # head receptor + storefront head member (3/4" deflection space) + transom glass
    v.polyline([(FR0 - 0.05, -1.6), (FR0 - 0.05, -0.5), (FR1 + 0.05, -0.5), (FR1 + 0.05, -1.6)],
               lw="med")
    alum(v, [(FR0 + 0.12, -1.25), (FR1 - 0.12, -1.25), (FR1 - 0.12, -3.25), (6.15, -3.25),
             (6.15, -2.0), (4.6, -2.0), (4.6, -3.25), (FR0 + 0.12, -3.25)])
    tbreak(v, 5.2, -2.0, 5.55, -1.25)
    glass_v(v, 5.375, -9.0, -2.3)
    R(v, 4.6, -3.25, 4.875, -2.5, lw="fine", fill="black")
    R(v, 5.875, -3.25, 6.15, -2.5, lw="fine", fill="black")
    brk(v, (2.6, -9.0), (8.2, -9.0))
    sealant_v(v, -0.5, 0.0, FR0 - 0.05, 0.4, right=True, rod_r=0.27)
    sealant_v(v, -0.5, 0.0, FR1 + 0.05, 0.4, right=False, rod_r=0.27)
    # corridor ACT ceiling 9'-6" AFF (2" above head)
    R(v, XC1, 2.0, 18.2, 2.625, lw="thin", fill="g10")
    v.polyline([(XC1 + 0.05, 3.4), (XC1 + 0.05, 1.95), (XC1 + 0.95, 1.95)], lw="med")
    brk(v, (18.2, 0.9), (18.2, 3.8))
    brk(v, (-0.6, top), (XC1 + 0.6, top))
    v.dimi((XC1, 0.0), (XC1, 2.0), -2.2, text="2\"")
    v.dimi((19.6, 0.0), (19.6, 24.0), -0.01, text="2'-0\" LINTEL", ext=False)
    v.line((XC1 + 0.3, 24.0), (20.3, 24.0), lw="hair")
    v.line((XC1 + 0.3, 0.0), (20.3, 0.0), lw="hair")
    v.dimi((FR0, -0.5), (FR1, -0.5), -10.3)
    v.dimi((0.0, -0.5), (FR0, -0.5), -10.3)
    v.dimi((0.0, top), (XC1, top), 1.6)
    notes_col(sh, v, [
        ((1.8, 20.0), "FB-1 FACE BRICK, RUNNING BOND"),
        ((3.0, 16.4), "ADJUSTABLE VENEER ANCHORS @ 16\" O.C. EA. WAY"),
        ((6.6, 22.0), "2\" POLYISO CAVITY INSULATION"),
        ((5.6, 7.75), "THRU-WALL FLASHING W/ SS DRIP EDGE, END DAMS, LAP 8\" UP CMU + TERM. BAR"),
        ((1.4, 1.3), "WEEP VENTS @ 24\" O.C."),
        ((1.8, 0.2), "BL-3: L6x4x3/8 LLV GALV. LOOSE LINTEL, 12\" BRG. EA. END (S-302)"),
        ((FR0 + 0.1, -0.25), "SEALANT + BACKER ROD"),
    ], xl, "l", 1.38, ylo, yhi)
    notes_col(sh, v, [
        ((13.0, 12.0), "CL-3: 24\" CMU BOND BEAM LINTEL (3 COURSES), (2) #5 BOT. + (2) #4 TOP, GROUT SOLID (S-302)"),
        ((7.7, 19.0), "FLUID-APPLIED AIR / WATER BARRIER"),
        ((6.4, 0.75), "2x4 PT WOOD BLOCKING (RIPPED), ANCHOR @ 16\" O.C."),
        ((6.4, 3.6), "CLOSED-CELL SPRAY FOAM FILL"),
        ((17.5, 2.3), "ACT-1 CEILING 9'-6\" AFF (CORRIDOR)"),
        ((FR1 + 0.06, -1.0), "ALUM. HEAD RECEPTOR, 3/4\" DEFLECTION SPACE, ANCHOR @ 12\" O.C."),
        ((6.9, -2.6), "SF-1 STOREFRONT HEAD 2\" x 4 1/2\", THERMALLY BROKEN (A-711)"),
        ((5.75, -6.5), "1\" INSUL. LOW-E TEMPERED GLASS (TRANSOM)"),
    ], xr, "r", 1.33, ylo, yhi)
    dtitle(sh, c, 4, "SF-1 STOREFRONT HEAD", sft, note="HEAD 109'-4\"")


# ---------------------------------------------------------------------------------------- 5
def det_sf1_sill(sh, c):
    """SF-1 sill & threshold at the entrance pair. y = 0 at FFE 100'-0".
    Walk 1/2" below FFE (A-201 keynote 6); slab recessed 1/2" under the threshold so the
    threshold top is flush with the interior floor (ADA: 1/2" max. above the walk)."""
    sft = 1.5
    ext = (-4.5, -21.5, 22.5, 17.0)
    v, xl, xr, ylo, yhi = setup(sh, c, ext, sft, wl=1.4, wr=1.4)
    bot = -20.0
    xf = -0.0625                       # face of foundation wall (S-301)
    fi = 15.9375                       # interior face of foundation wall
    concrete(v, [(xf, bot), (fi, bot), (fi, -5.0), (xf, -5.0)], seed=4)
    # slab: recessed 1/2" under threshold (x 0.5 .. 8.0), WOM-1 recess 1/4" inboard
    concrete(v, [(xf, -5.0), (22.5, -5.0), (22.5, -0.25), (8.0, -0.25), (8.0, -0.5), (0.5, -0.5),
                 (0.5, 0.0), (xf, 0.0)], seed=5)
    rigid(v, fi, bot, fi + 2.0, -5.0)
    gravel(v, [(fi + 2.0, -11.0), (22.5, -11.0), (22.5, -5.0), (fi + 2.0, -5.0)])
    v.line((fi, -5.05), (22.5, -5.05), lw="med", dash=[4, 1.5])
    earth(v, [(fi + 2.0, bot), (22.5, bot), (22.5, -11.0), (fi + 2.0, -11.0)])
    # exterior walk 1/2" below FFE, isolation joint
    concrete(v, [(-4.5, -5.5), (xf - 0.5, -5.5), (xf - 0.5, -0.5), (-4.5, -0.6)], seed=6)
    gravel(v, [(-4.5, -9.5), (xf, -9.5), (xf, -5.5), (-4.5, -5.5)])
    earth(v, [(-4.5, bot), (xf, bot), (xf, -9.5), (-4.5, -9.5)])
    R(v, xf - 0.5, -5.5, xf, -0.95, lw="fine", fill="g20")
    bead(v, [(xf - 0.5, -0.5), (xf, -0.5), (xf, -0.95), (xf - 0.5, -0.95)])
    v.polyline([(xf, bot), (xf, -5.5)], lw="med", dash=[1.5, 1])
    # WOM-1 recessed walk-off carpet tile
    R(v, 8.0, -0.25, 22.5, 0.0, lw="fine", fill="white", hatch="carpet")
    # threshold (ADA, 1/2" high, 1:2 bevels) set in sealant in the recess
    bead(v, [(0.6, -0.54), (7.9, -0.54), (7.9, -0.5), (0.6, -0.5)])
    alum(v, [(0.6, -0.5), (1.6, 0.0), (6.9, 0.0), (7.9, -0.5)])
    for xx in (2.6, 5.9):
        v.line((xx, -0.05), (xx, -2.4), lw="med")
    # door bottom rail + sweep + glass
    alum(v, [(4.5, 0.25), (6.25, 0.25), (6.25, 10.25), (4.5, 10.25)])
    R(v, 4.62, 0.0, 6.13, 0.25, lw="fine", fill="g60")
    glass_v(v, 5.375, 10.25, 15.6, t=0.5, lite=0.2)
    brk(v, (3.7, 15.6), (7.0, 15.6))
    for (a, b) in ((0.0, XB1), (XC0, XC1)):
        v.polyline([(a, 15.6), (a, 0.0), (b, 0.0), (b, 15.6)], lw="fine", dash=[2, 1.5])
    brk(v, (-4.0, bot), (22.0, bot))
    brk(v, (22.5, -11.5), (22.5, 0.6))
    v.dimi((21.5, -5.0), (21.5, 0.0), -0.01, text="5\"", ext=False)
    v.dimi((21.5, -11.0), (21.5, -5.0), -0.01, text="6\"", ext=False)
    v.dimi((xf, bot + 2), (fi, bot + 2), 1.0, text="1'-4\"")
    v.dimi((-3.0, -0.55), (-3.0, 0.0), 0.01, text="1/2\"", ext=False)
    v.line((-3.6, 0.0), (0.4, 0.0), lw="hair")
    notes_col(sh, v, [
        ((5.4, 13.0), "SF-1 ALUM. ENTRANCE DOOR, MEDIUM STILE, 10\" BOTTOM RAIL (HW-7)"),
        ((5.4, 0.12), "BRUSH SWEEP / DOOR BOTTOM SEAL"),
        ((1.2, -0.3), "ALUM. THRESHOLD 6\" x 1/2\", 1:2 BEVELS, SET IN SEALANT IN 1/2\" SLAB RECESS, SS SCREWS IN ANCHORS (ADA)"),
        ((-2.5, -0.6), "CONC. WALK 1/2\" BELOW FFE, SLOPE AWAY 1/8\" PER FT (CIVIL)"),
        ((xf - 0.25, -0.75), "1/2\" ISOLATION JOINT + SEALANT"),
        ((-2.5, -7.5), "CA-6 BASE"),
        ((xf, -14.0), "DAMPPROOFING"),
    ], xl, "l", 1.4, ylo, yhi)
    notes_col(sh, v, [
        ((1.8, 9.0), "BRICK / CMU JAMB BEYOND"),
        ((17.0, -0.12), "WOM-1 WALK-OFF CARPET TILE IN 1/4\" SLAB DEPRESSION"),
        ((12.0, -2.5), "5\" SLAB ON GRADE, 4,000 PSI, WWF 6x6-W2.9xW2.9"),
        ((20.0, -5.05), "15 MIL VAPOR RETARDER"),
        ((20.0, -8.5), "6\" CA-6 BASE"),
        ((fi + 1.0, -14.0), "2\" XPS PERIMETER INSULATION x 2'-0\" (SEE 10)"),
        ((8.0, -15.0), "CONC. FOUNDATION WALL, NO BRICK LEDGE AT DOOR (S-301)"),
    ], xr, "r", 1.4, ylo, yhi)
    dtitle(sh, c, 5, "SF-1 SILL & THRESHOLD", sft, note="FFE 100'-0\"; ENTRANCE PAIR 100B")


# ---------------------------------------------------------------------------------------- 7
def det_sf3(sh, c):
    """SF-3 link storefront: head on HSS8x8 head beam (S-302 13) and sill on the 8" concrete
    curb (S-301 8); the two halves are separated by a break."""
    sft = 1.5
    s = sft / 12.0
    F0, F1 = 4.75, 9.25            # SF-3 frame zone, set back past the 3/4" curb chamfer
    HX0 = XG - 4.0                 # exterior face of HSS8x8 (on grid)
    wl, wr = 1.25, 1.25
    xl = c["x"] + 0.1 + wl
    xr = c["x"] + c["w"] - 0.1 - wr
    ex0, ex1 = -2.0, 17.8
    ox = xl + 0.24 + ((xr - 0.24) - (xl + 0.24) - (ex1 - ex0) * s) / 2
    top_y = c["y"] + c["h"] - 0.2
    vh = DV(sh.c, ox, top_y - 26.0 * s, sft, ex0, -6.0)
    vs = DV(sh.c, ox, c["y"] + 0.85, sft, ex0, -15.0)
    # ---- head ----
    v = vh
    tp = 19.0
    R(v, HX0, 0.0, HX0 + 8.0, 8.0, lw="thin", fill="black")
    R(v, HX0 + 0.5, 0.5, HX0 + 7.5, 7.5, lw="fine", fill="white")
    angle(v, (HX0, 0.0), 7.0, 4.0, 0.375, dx=-1, dy=1)
    brick_courses(v, 0, XB1, 0.375, tp, 0.375)
    cmu_courses(v, XC0, XC1, 8.0, tp, 8.0, joint="bot")
    yfl = lambda x: 4.6 + (5.2 - 4.6) / (HX0 - 0.1 - 5.6) * (x - 5.6)
    rigid(v, 0, 0, 0, 0, pts=[(XA1, 0.45), (HX0 - 0.45, 0.45), (HX0 - 0.45, 4.2), (XA1, 4.2)])
    rigid(v, 0, 0, 0, 0, pts=[(XA1, 5.3), (HX0 - 0.05, 5.3), (HX0 - 0.05, 8.0), (7.5, 8.0), (7.5, tp),
                               (XA1, tp)])
    flashing(v, [(-0.32, 0.2), (-0.55, 0.45), (5.5, 0.45), (5.5, 4.7), (HX0 - 0.03, 4.7),
                 (HX0 - 0.03, 8.0), (7.55, 8.0), (7.55, 12.0)])
    R(v, 7.55, 11.1, 7.85, 12.1, lw="fine", fill="black")
    air_barrier(v, [(7.7, tp), (7.7, 8.1)])
    v.polyline([(F0 - 0.05, -1.6), (F0 - 0.05, -0.05), (F1 + 0.05, -0.05), (F1 + 0.05, -1.6)], lw="med")
    alum(v, [(F0 + 0.12, -0.8), (F1 - 0.12, -0.8), (F1 - 0.12, -2.8), (7.65, -2.8), (7.65, -1.55),
             (6.1, -1.55), (6.1, -2.8), (F0 + 0.12, -2.8)])
    tbreak(v, 6.7, -1.55, 7.05, -0.8)
    glass_v(v, 6.875, -6.0, -1.85)
    brk(v, (3.8, -6.0), (10.0, -6.0))
    sealant_v(v, -0.45, 0.0, F0 - 0.05, 0.4, right=True, rod_r=0.22)
    sealant_v(v, -0.45, 0.0, F1 + 0.05, 0.4, right=False, rod_r=0.22)
    R(v, HX0 + 8.0, 2.0, 17.8, 2.625, lw="thin", fill="g10")
    brk(v, (-0.5, tp), (XC1 + 0.5, tp))
    brk(v, (17.8, 0.8), (17.8, 3.8))
    # ---- sill ----
    v = vs
    bt = -14.0
    cx0, cx1 = 3.9375, 15.9375      # 12" curb / foundation wall (S-301)
    concrete(v, [(cx0, bt), (cx1, bt), (cx1, 0.0), (cx0 + 0.75, 0.0), (cx0, -0.75)], seed=9)
    earth(v, [(-2.0, bt), (cx0, bt), (cx0, -8.0), (-2.0, -8.15)])
    v.line((-2.0, -8.15), (cx0, -8.0), lw="thin")
    v.polyline([(cx0, bt), (cx0, -8.0)], lw="med", dash=[1.5, 1])
    R(v, cx1, -5.0, cx1 + 0.5, -0.4, lw="fine", fill="g20")
    bead(v, [(cx1, 0.0), (cx1 + 0.5, 0.0), (cx1 + 0.5, -0.4), (cx1, -0.4)])
    rigid(v, cx1 + 0.5, -5.0, cx1 + 1.5, -0.6)
    concrete(v, [(cx1 + 1.5, -5.0), (17.8, -5.0), (17.8, 0.0), (cx1 + 1.5, 0.0)], seed=10)
    rigid(v, cx1, bt, cx1 + 1.86, -5.0)
    R(v, 9.6, 0.0, 17.8, 0.125, lw="fine", fill="g40")
    flashing(v, [(cx0 + 0.55, -0.15), (cx0 + 0.75, 0.04), (9.45, 0.04), (9.45, 1.4)], lw=1.0)
    alum(v, [(F0, 0.5), (F1, 0.5), (F1, 2.5), (7.65, 2.5), (7.65, 1.25), (6.1, 1.25), (6.1, 2.5),
             (F0, 2.5)])
    tbreak(v, 6.7, 0.5, 7.05, 1.25)
    glass_v(v, 6.875, 2.75, 8.0)
    R(v, 6.1, 2.5, 6.375, 3.25, lw="fine", fill="black")
    R(v, 7.375, 2.5, 7.65, 3.25, lw="fine", fill="black")
    brk(v, (3.9, 8.0), (10.0, 8.0))
    R(v, 5.4, 0.04, 5.9, 0.5, lw="fine", fill="black")
    v.line((8.3, 0.6), (8.3, -2.2), lw="med")
    sealant_v(v, 0.04, 0.5, F0, 0.35, right=True, rod_r=0.2)
    sealant_v(v, 0.04, 0.5, F1, 0.3, right=False, rod_r=0.2)
    brk(v, (3.4, bt), (17.5, bt))
    brk(v, (17.8, -5.5), (17.8, 0.6))
    vs.dimi((cx0, -8.0), (cx0, 0.0), 1.6, text="8\"")
    vs.dimi((cx0, bt + 1.5), (cx1, bt + 1.5), 0.6, text="1'-0\"")
    # compressed MO dimension between head and sill views (paper space)
    xd = vs.to_paper((-1.4, 0))[0]
    ya = vs.to_paper((0, 0.0))[1]
    yb = vh.to_paper((0, 0.0))[1]
    sh.line((xd, ya - 0.05), (xd, yb + 0.05), lw="fine")
    for yy in (ya, yb):
        sh.line((xd - 0.05, yy - 0.05), (xd + 0.05, yy + 0.05), lw="med")
        sh.line((xd - 0.08, yy), (vs.to_paper((F0, 0))[0] - 0.05, yy), lw="hair")
    ym = (ya + yb) / 2
    sh.rect(xd - 0.07, ym - 0.12, 0.14, 0.24, lw=None, fill="white", stroke=False)
    sh.line((xd - 0.08, ym - 0.06), (xd + 0.08, ym - 0.02), lw="fine")
    sh.line((xd - 0.08, ym + 0.02), (xd + 0.08, ym + 0.06), lw="fine")
    sh.text((xd - 0.04, ym + 0.45), "9'-4\" MO", size=DS, anchor="c", valign="bot", rot=90)
    yh_lo = vh.to_paper((0, -6.0))[1]
    notes_col(sh, vh, [
        ((1.8, 12.0), "FB-1 FACE BRICK"),
        ((5.5, 3.0), "THRU-WALL FLASHING W/ SS DRIP, END DAMS, LAP UP HSS + CMU, TERM. BAR"),
        ((2.5, 0.19), "L7x4x3/8 LLH CONT., WELDED TO HSS (S-302)"),
        ((F0, -0.25), "SEALANT + BACKER ROD"),
    ], xl, "l", wl, yh_lo, top_y)
    notes_col(sh, vh, [
        ((13.0, 13.0), "8\" CMU ON HSS"),
        ((HX0 + 6.0, 6.0), "HSS8x8x1/2 HEAD BEAM ON GRID, T.O.S. 110'-0\" (S-302)"),
        ((6.6, 6.6), "2\" POLYISO"),
        ((17.0, 2.3), "ACT-1 CEILING 9'-6\" AFF"),
        ((F1 + 0.05, -1.0), "HEAD RECEPTOR, 1/2\" DEFLECTION, FASTEN @ 12\" O.C."),
        ((7.6, -4.0), "SF-3 STOREFRONT, 1\" INSUL. LOW-E TEMPERED (A-711)"),
    ], xr, "r", wr, yh_lo, top_y)
    ys_hi = vs.to_paper((0, 8.0))[1] + 0.25
    notes_col(sh, vs, [
        ((F0 + 0.1, 0.27), "SEALANT W/ WEEP GAPS AT FRAME WEEPS"),
        ((cx0 + 0.6, -0.1), "SELF-ADHERED SILL PAN, END DAMS, BACK LEG UP"),
        ((cx0, -4.0), "8\" EXPOSED CONC. CURB, 3/4\" CHAMFER, RUBBED FINISH (S-301)"),
        ((0.0, -11.0), "FINISH GRADE 99'-4\""),
    ], xl, "l", wl, c["y"] + 0.75, ys_hi)
    notes_col(sh, vs, [
        ((7.0, 1.9), "SF-3 SILL 2\" x 4 1/2\""),
        ((8.3, -1.2), "3/8\" SS SCREW ANCHORS @ 16\" O.C. SET IN SEALANT"),
        ((12.0, 0.08), "LVT-1 TO FRAME"),
        ((cx1 + 1.0, -2.5), "1\" XPS THERMAL BREAK + 1/2\" JOINT"),
        ((cx1 + 0.9, -9.0), "2\" XPS x 2'-0\" DEEP"),
    ], xr, "r", wr, c["y"] + 0.75, ys_hi)
    dtitle(sh, c, 7, "SF-3 HEAD & SILL AT CURB", sft, note="LINK 100A")


# ---------------------------------------------------------------------------------------- 8
def det_parapet(sh, c):
    """Parapet & coping at the main roof. y = 0 at T.O. CMU parapet 131'-4".
    Structure per 9/S-302: W16x26 edge beam 7 1/2" inboard of grid, T.O.S. 127'-9 1/2"."""
    sft = 1.5
    ext = (-2.6, -50.0, 36.5, 6.6)
    v, xl, xr, ylo, yhi = setup(sh, c, ext, sft, wl=1.42, wr=0.0)
    bot = -49.0
    brick_courses(v, 0, XB1, bot, 0.0, 0.0)
    rigid(v, XA1, bot, XC0, 0.0)
    cmu_courses(v, XC0, XC1, bot, 0.0, 0.0, joint="bot", bond=(-1, -6),
                bars={-1: [9.9, 12.95], -6: [9.9, 12.95]})
    air_barrier(v, [(7.7, bot), (7.7, 0.0)])
    veneer_anchor(v, -15.81, -15.79)
    veneer_anchor(v, -39.81, -39.79)
    # PT wood blocking: layer 1 flat, layer 2 tapered (slope to roof), 3/4" plywood cap
    o = 0.5
    wood(v, o, 0.0, o + 5.5, 1.5)
    wood(v, o + 5.5, 0.0, XC1, 1.5)
    sl = 0.5 / (XC1 - o)
    yt = lambda x: 3.0 - (x - o) * sl
    wood_poly(v, [(o, 1.5), (o + 9.25, 1.5), (o + 9.25, yt(o + 9.25)), (o, yt(o))])
    wood_poly(v, [(o + 9.25, 1.5), (XC1, 1.5), (XC1, yt(XC1)), (o + 9.25, yt(o + 9.25))])
    v.polygon([(o, yt(o)), (XC1, yt(XC1)), (XC1, yt(XC1) + 0.75), (o, yt(o) + 0.75)], lw="thin",
              fill="white")
    for f in (0.33, 0.66):
        v.line((o, yt(o) + 0.75 * f), (XC1, yt(XC1) + 0.75 * f), lw="hair")
    v.line((XG, -6.0), (XG, 1.2), lw="med")
    R(v, XG - 0.5, 1.2, XG + 0.5, 1.45, lw="fine", fill="black")
    # roof assembly
    xe = 36.0
    deck_profile(v, XC1 + 0.2, xe, -40.0, phase=1.0)
    v.line((XC1 + 0.2, -38.45), (xe, -38.45), lw="fine")
    rigid(v, XC1, -38.4, xe, -36.4)
    rigid(v, XC1, -36.4, xe, -34.4)
    tap = lambda x: -29.0 - (x - XC1) * (0.25 / 12.0)
    rigid(v, 0, 0, 0, 0, pts=[(XC1, -34.4), (xe, -34.4), (xe, tap(xe)), (XC1, tap(XC1))])
    v.polygon([(XC1, tap(XC1)), (xe, tap(xe)), (xe, tap(xe) + 0.5), (XC1, tap(XC1) + 0.5)],
              lw="fine", fill="g20")
    membrane(v, [(xe, tap(xe) + 0.55), (XC1 + 0.07, tap(XC1) + 0.55), (XC1 + 0.07, yt(XC1) + 0.8),
                 (o - 0.05, yt(o) + 0.8), (o - 0.05, 1.5)])
    # coping (4" laps both faces) + continuous cleats
    ct = lambda x: yt(o) + 0.92 - (x - o) * sl
    v.polyline([(-0.5, -4.4), (-0.95, -4.0), (-0.95, ct(-0.95)), (16.25, ct(16.25)),
                (16.25, -4.0), (16.65, -4.4)], lw=1.0)
    v.polyline([(o - 0.03, 1.4), (o - 0.03, 0.04), (-0.05, 0.04), (-0.05, -3.8), (-0.72, -4.25)],
               lw="med")
    v.polyline([(XC1 + 0.17, 1.0), (XC1 + 0.17, -3.8), (16.0, -4.2)], lw="med")
    # structure: L3x3 deck edge angle, W16x26 edge beam 7 1/2" inboard, 22K6 seat
    angle(v, (XC1, -40.0), 3.0, 3.0, 0.25, dx=1, dy=-1)
    v.line((XC1 + 0.3, -41.6), (12.5, -41.6), lw="med")
    bx = XG + 7.5
    steel(v, [(bx - 2.75, -42.5), (bx + 2.75, -42.5), (bx + 2.75, -42.845), (bx + 0.125, -42.845),
              (bx + 0.125, -49.0), (bx - 0.125, -49.0), (bx - 0.125, -42.845), (bx - 2.75, -42.845)])
    R(v, 16.6, -42.5, 21.4, -42.25, lw="fine", fill="black")
    R(v, 16.6, -42.5, 16.85, -40.0, lw="fine", fill="black")
    R(v, 16.85, -41.5, xe, -40.0, lw="fine", fill="g40")
    v.polyline([(21.4, -41.5), (26.4, -49.0)], lw="thin")
    v.polyline([(21.9, -41.5), (26.9, -49.0)], lw="thin")
    brk(v, (-0.5, bot), (22.4, bot))
    brk(v, (xe, -42.0), (xe, -27.5))
    v.dimi((24.0, tap(24.0) + 0.55), (24.0, 0.0), 0.01, text="2'-4 1/2\" (8\" MIN. ABOVE ROOF)",
           ext=False)
    v.line((XC1 + 1.2, 0.0), (25.0, 0.0), lw="hair")
    v.dimi((-0.95, 5.6), (0.0, 5.6), 0.01, text="1\"", ext=False)
    v.dimi((-1.9, -4.0), (-1.9, 0.0), 0.01, text="4\"", ext=False)
    xa = 31.0
    lys = [tap(xa) + 0.55, tap(xa) + 0.25, -32.0, -35.4, -37.4, -38.45, -39.25]
    v.line((xa, lys[0]), (xa, lys[-1]), lw="fine")
    for yy in lys:
        v.circle((xa, yy), v.paper_len(0.018), lw=None, fill="black")
    notes_col(sh, v, [
        ((-0.95, 1.5), "PREFINISHED METAL COPING, 24 GA., 4\" FACE LAPS, 10'-0\" LENGTHS, CONCEALED SPLICE PLATES; SLOPE TO ROOF"),
        ((-0.05, -2.5), "CONT. 22 GA. GALV. CLEAT EA. FACE, FASTEN @ 12\" O.C."),
        ((1.8, -10.0), "FB-1 FACE BRICK"),
        ((3.0, -15.8), "ADJUSTABLE VENEER ANCHORS @ 16\" O.C. EA. WAY"),
        ((4.6, -24.0), "2\" AIR SPACE"),
        ((6.6, -20.0), "2\" POLYISO CAVITY INSULATION, EXTEND TO TOP OF WALL"),
        ((7.7, -33.0), "FLUID-APPLIED AIR / WATER BARRIER"),
        ((11.0, -44.0), "ROOF BOND BEAM 127'-4\" TO 128'-0\", (2) #5; VERT. #5 @ 48\" O.C. (S-302)"),
    ], xl, "l", 1.42, ylo, yhi)
    xr2 = v.to_paper((17.6, 0))[0]
    wr2 = c["x"] + c["w"] - 0.12 - xr2
    notes_col(sh, v, [
        ((8.0, yt(8.0) + 0.38), "3/4\" PT PLYWOOD CAP"),
        ((4.0, yt(4.0) - 0.5), "PT 2x10 + 2x6 TAPERED 1 1/2\" TO 1\""),
        ((3.0, 0.75), "PT 2x6 + 2x10 FLAT, 1/2\" ANCHOR BOLTS @ 32\" O.C. IN BOND BEAM"),
        ((XC1 + 0.07, -6.0), "EPDM BASE FLASHING (60 MIL REINF.) UP & OVER BLOCKING, TURN DOWN 1 1/2\" AT EXT. FACE"),
        ((12.0, -4.0), "TOP BOND BEAM 130'-8\" TO 131'-4\", (2) #5"),
        ((xa, lys[0]), "ROOF ASSEMBLY (TOP DOWN): 60 MIL EPDM FULLY ADHERED, RUSS STRIP AT BASE OF WALL / "
                       "1/2\" GYPSUM COVER BOARD / TAPERED POLYISO 1/4\" PER FT (A-103) / (2) LAYERS 2\" "
                       "POLYISO, JOINTS STAGGERED / SELF-ADHERED VAPOR RETARDER / 1 1/2\" TYPE B GALV. "
                       "ROOF DECK (S-103)", v.to_paper((0, tap(XC1) + 6.0))[1]),
    ], xr2, "r", wr2, v.to_paper((0, tap(XC1) + 1.2))[1], yhi)
    xr3 = v.to_paper((26.0, 0))[0]
    notes_col(sh, v, [
        ((17.5, -40.6), "CONT. L3x3x1/4 DECK EDGE ANGLE, 5/8\" ADH. ANCHORS @ 24\" (S-302)"),
        ((33.0, -40.75), "22K6 JOISTS @ 5'-0\" O.C."),
        ((bx + 2.0, -42.7), "W16x26 EDGE BEAM 7 1/2\" INBOARD OF GRID, T.O.S. 127'-9 1/2\" (S-103)"),
    ], xr3, "r", c["x"] + c["w"] - 0.12 - xr3, ylo, v.to_paper((0, -41.9))[1])
    dtitle(sh, c, 8, "PARAPET & COPING", sft, note="T.O. CMU 131'-4\", T.O. JOIST 128'-0\"")


# ---------------------------------------------------------------------------------------- 9
def det_shelf(sh, c):
    """Shelf angle at L2 / CS-2 band per 4/S-302. y = 0 at T.O. slab L2 = 114'-0".
    L7x4x7/16 LLH, top 113'-4", vertical leg down against CMU, 3/4" embedded bolts @ 24" in the
    grouted L2 bond beam (112'-8" to 114'-0"); slab edge at inside face of CMU."""
    sft = 1.5
    ext = (-2.4, -30.0, 31.0, 11.0)
    v, xl, xr, ylo, yhi = setup(sh, c, ext, sft, wl=1.42, wr=0.0)
    bot, tp = -29.0, 10.0
    t = 7.0 / 16.0
    # brick below (coursing adjusted to the soft joint) and above the band
    brick_courses(v, 0, XB1, bot, -8.0 - t - 0.375, -8.0 - t - 0.375)
    brick_courses(v, 0, XB1, 0.0, tp, 0.0)
    caststone(v, [(0.0, -7.625), (XB1, -7.625), (XB1, 0.0), (0.0, 0.0)])
    # CMU continuous: L2 bond beam 2 courses (112'-8" to 114'-0")
    cmu_courses(v, XC0, XC1, bot, tp, 0.0, joint="bot", bond=(-2, -1),
                bars={-2: [9.9, 12.95], -1: [9.9, 12.95]})
    # shelf angle L7x4x7/16 LLH: heel at CMU face, horizontal leg 7" out, vertical leg 4" down
    angle(v, (XC0, -8.0), 7.0, 4.0, t, dx=-1, dy=-1)
    v.line((XC0 - 0.6, -10.0), (12.5, -10.0), lw=1.6)
    R(v, XC0 - 0.75, -10.3, XC0 - 0.45, -9.7, lw="fine", fill="black")
    # insulation (cut at angle), flashing, air barrier
    rigid(v, XA1, bot, XC0 - t - 0.05, -12.05)
    yfl = lambda x: -7.5 + (3.5 / (XC0 - 0.08 - 5.6)) * (x - 5.6)
    rigid(v, 0, 0, 0, 0, pts=[(XA1, -7.4), (XC0 - 0.1, yfl(XC0 - 0.1) + 0.1), (XC0 - 0.1, tp), (XA1, tp)])
    flashing(v, [(-0.32, -8.2), (-0.55, -7.94), (5.6, -7.94), (XC0 - 0.08, -4.0),
                 (XC0 - 0.08, 1.0)])
    R(v, XC0 - 0.08, 0.1, XC0 + 0.22, 1.1, lw="fine", fill="black")
    air_barrier(v, [(7.7, bot), (7.7, -12.0)])
    air_barrier(v, [(7.7, 1.2), (7.7, tp)])
    sealant_v(v, -8.0 - t - 0.375, -8.0 - t, 0.0, 0.3, right=True, rod_r=0.2)
    veneer_anchor(v, -23.81, -24.0)
    # slab edge at inside face of CMU: 1/2" joint, 3/8" bent plate pour stop, deck, spandrel
    sx = XC1 + 0.5
    R(v, XC1, -6.25, sx, -0.4, lw="fine", fill="g20")
    bead(v, [(XC1, 0.0), (sx, 0.0), (sx, -0.4), (XC1, -0.4)])
    concrete(v, [(sx + 0.375, -6.25), (31.0, -6.25), (31.0, 0.0), (sx + 0.375, 0.0)], seed=12)
    steel(v, [(sx, -6.25), (sx + 0.375, -6.25), (sx + 0.375, -0.3), (sx, -0.3)])
    steel(v, [(sx, -6.625), (XG + 7.5 + 2.76, -6.625), (XG + 7.5 + 2.76, -6.25), (sx, -6.25)])
    v.line((sx + 0.4, -3.25), (31.0, -3.25), lw="fine", dash=[2, 1.5])
    bx = XG + 7.5
    wshape(v, bx, -6.625, 15.875, 5.525, 0.44, 0.275)
    v.polyline([(28.0, -2.0), (13.0, -2.0), (13.0, -11.5)], lw="med")
    # L2 floor finish + base
    R(v, sx + 0.375, 0.0, 31.0, 0.125, lw="fine", fill="g40")
    R(v, XC1, 0.125, XC1 + 0.25, 4.125, lw="fine", fill="g60")
    brk(v, (-0.5, bot), (XC1 + 0.5, bot))
    brk(v, (-0.5, tp), (XC1 + 0.5, tp))
    brk(v, (31.0, -7.5), (31.0, 1.0))
    brk(v, (bx - 3.4, -22.9), (bx + 3.4, -22.9))
    v.dimi((0.0, -8.0), (0.0, 0.0), 1.6, text="8\"")
    v.dimi((0.625, -12.6), (XC0, -12.6), 0.01, text="7\"", ext=False)
    v.dimi((XC0, tp - 1.0), (bx, tp - 1.0), 0.01, text="1'-3 1/16\"", ext=False) if False else None
    elev_tag(sh, v, (24.0, 0.13), "T.O. SLAB L2", "114'-0\"", side="r", length=0.12)
    notes_col(sh, v, [
        ((1.8, 5.0), "FB-1 FACE BRICK"),
        ((1.8, -4.0), "CS-2 CAST STONE BAND, 8\" x 3 5/8\", SS STRAP ANCHORS (2) PER PIECE"),
        ((6.4, -5.3), "THRU-WALL FLASHING W/ SS DRIP, LAP 8\" UP CMU + TERM. BAR; END DAMS AT W-C JAMBS"),
        ((1.2, -7.4), "WEEP VENTS @ 24\" O.C."),
        ((2.0, -8.2), "L7x4x7/16 LLH GALV. SHELF ANGLE, CONT., 1/4\" GAP @ 20'-0\" MAX. (S-302)"),
        ((0.15, -8.6), "3/8\" SOFT JOINT: BACKER ROD + SEALANT"),
        ((XC0 - 0.6, -10.0), "3/4\" A307 EMBEDDED BOLTS @ 24\" O.C. W/ SHIMS"),
        ((3.0, -24.0), "ADJUSTABLE VENEER ANCHORS"),
        ((6.6, -20.0), "2\" POLYISO (CUT AT ANGLE)"),
    ], xl, "l", 1.42, ylo, yhi)
    xr2 = v.to_paper((17.6, 0))[0]
    wr2 = c["x"] + c["w"] - 0.12 - xr2
    notes_col(sh, v, [
        ((12.0, 5.0), "8\" CMU, CONTINUOUS"),
        ((XC1 + 0.12, 2.6), "RB-1 RUBBER BASE"),
        ((26.0, 0.07), "VCT-1 (L2 CLASSROOMS)"),
    ], xr2, "r", wr2, v.to_paper((0, 1.3))[1], yhi)
    notes_col(sh, v, [
        ((22.0, -3.0), "6 1/4\" COMPOSITE SLAB: 3\" DECK + 3 1/4\" LW CONC. (S-102)"),
        ((sx + 0.2, -4.6), "3/8\" BENT PL POUR STOP + 1/2\" COMPRESSIBLE JOINT"),
        ((13.0, -9.0), "#4 x 4'-0\" @ 24\" HOOKED INTO BOND BEAM"),
        ((11.0, -14.0), "L2 BOND BEAM 112'-8\" TO 114'-0\", (2) #5 EA. COURSE"),
        ((bx + 0.14, -16.0), "W16x31 SPANDREL 7 1/2\" INBOARD OF GRID (S-102)"),
        ((13.0, -24.0), "8\" CMU, PNT-1"),
    ], xr2, "r", wr2, ylo, v.to_paper((0, -7.4))[1])
    dtitle(sh, c, 9, "SHELF ANGLE AT L2 / CS-2 BAND", sft, note="BAND 113'-4\" TO 114'-0\"")


# ---------------------------------------------------------------------------------------- 10
def det_foundation(sh, c):
    """Foundation / base of wall per 1/S-301. y = 0 at FFE 100'-0"; grade 99'-4"; ledge 99'-0".
    12" foundation wall 3 15/16" .. 15 15/16" from brick face; 4" ledge."""
    sft = 1.5
    ext = (-6.0, -34.0, 28.5, 14.5)
    v, xl, xr, ylo, yhi = setup(sh, c, ext, sft, wl=1.42, wr=0.0)
    bot, tp = -33.0, 13.0
    xf, xg, fi = -0.0625, 3.9375, 15.9375
    concrete(v, [(xf, bot), (fi, bot), (fi, -8.0), (xg, -8.0), (xg, -12.0), (xf, -12.0)], seed=14)
    v.line((XG, bot), (XG, 6.0), lw="fine", dash=[3, 1.5])
    # brick: base course on mortar bed, FB-2 band 99'-4" to 100'-8", FB-1 above
    R(v, 0.0, -12.0, XB1, -10.667, lw="fine", fill="white", hatch="sand", hatch_kw=dict(scale=1.4))
    brick_unit(v, 0.0, -10.25, XB1, -8.0)
    brick_courses(v, 0, XB1, -8.0, tp, -8.0, skip=(3,))
    R(v, 0.0, 0.4167, XB1, 2.667, lw="thin", fill="g10")
    for xx in (0.6, 1.2, 1.8, 2.4, 3.0):
        v.line((xx, 0.5), (xx, 2.6), lw="hair")
    R(v, XB1, -12.0, xg, -8.0, lw="fine", fill="white", hatch="sand", hatch_kw=dict(scale=1.25))
    R(v, XB1, -8.0, XA1, 0.0, lw="fine", fill="white", hatch="sand", hatch_kw=dict(scale=1.25))
    rigid(v, XA1, -8.0, XC0, 0.0)
    rigid(v, XA1, 0.3, XC0, tp)
    R(v, XB1, 0.3, XB1 + 1.0, 10.0, lw="fine", fill="white", hatch="dots")
    cmu_courses(v, XC0, XC1, -8.0, tp, -8.0, joint="bot", grout=(0,))
    flashing(v, [(-0.32, -0.05), (-0.55, 0.2), (XC0 - 0.07, 0.2), (XC0 - 0.07, 8.0)])
    R(v, XC0 - 0.08, 7.0, XC0 + 0.22, 8.1, lw="fine", fill="black")
    air_barrier(v, [(7.7, 7.2), (7.7, tp)])
    # slab, isolation joint, vapor retarder, base, perimeter insulation (2'-0" deep, S-301)
    concrete(v, [(15.75, -5.0), (28.5, -5.0), (28.5, 0.0), (15.75, 0.0)], seed=15)
    R(v, XC1, -5.0, 15.75, -0.4, lw="fine", fill="g20")
    bead(v, [(XC1, 0.0), (15.75, 0.0), (15.75, -0.4), (XC1, -0.4)])
    rigid(v, fi, -29.0, fi + 2.0, -5.0)
    v.polyline([(15.8, -1.0), (15.8, -5.05), (28.5, -5.05)], lw="med", dash=[4, 1.5])
    gravel(v, [(fi + 2.0, -11.0), (28.5, -11.0), (28.5, -5.1), (fi + 2.0, -5.1)])
    earth(v, [(fi + 2.0, bot), (28.5, bot), (28.5, -11.0), (fi + 2.0, -11.0)])
    earth(v, [(fi, bot), (fi + 2.0, bot), (fi + 2.0, -29.0), (fi, -29.0)])
    earth(v, [(-6.0, bot), (xf, bot), (xf, -8.0), (-6.0, -8.3)])
    v.line((-6.0, -8.3), (0.0, -8.0), lw="thin")
    v.polyline([(xf - 0.06, bot), (xf - 0.06, -8.0)], lw="med", dash=[1.5, 1])
    v.line((XG + 3.0, -31.0), (XG + 3.0, 4.0), lw="med", dash=[6, 1.5])
    R(v, 15.75, 0.0, 28.5, 0.125, lw="fine", fill="g40")
    R(v, XC1, 0.125, XC1 + 0.25, 4.125, lw="fine", fill="g60")
    brk(v, (-5.5, bot), (28.0, bot))
    brk(v, (28.5, -12.0), (28.5, 1.0))
    brk(v, (-0.5, tp), (XC1 + 0.5, tp))
    v.dimi((-3.0, -8.0), (-3.0, 0.0), 0.01, text="8\"", ext=False)
    v.dimi((xf, -12.0), (xg, -12.0), 1.2, text="4\"", flip_text=True)
    v.dimi((xg, -18.0), (fi, -18.0), 0.01, text="1'-0\"", ext=False)
    v.dimi((27.0, -5.0), (27.0, 0.0), -0.01, text="5\"", ext=False)
    v.dimi((27.0, -11.0), (27.0, -5.0), -0.01, text="6\"", ext=False)
    v.dimi((fi + 1.0, -29.0), (fi + 1.0, -5.0), 0.01, text="2'-0\"", ext=False)
    elev_tag(sh, v, (21.0, 0.13), "FFE L1", "100'-0\"", side="r", length=0.12)
    notes_col(sh, v, [
        ((1.8, 9.0), "FB-1 FACE BRICK"),
        ((1.8, 4.0), "FB-2 ACCENT BRICK BASE BAND, 6 COURSES 99'-4\" TO 100'-8\""),
        ((XB1 + 0.5, 6.0), "MORTAR NET DRAINAGE MAT 10\" HIGH"),
        ((1.5, 1.6), "WEEP VENTS @ 24\" O.C. IN FIRST COURSE ABOVE FLASHING"),
        ((2.6, 0.2), "THRU-WALL FLASHING W/ SS DRIP 8\" ABOVE GRADE (100'-0\"); LAP 8\" UP CMU, TERM. BAR + SEALANT; END DAMS"),
        ((4.6, -4.0), "GROUT AIR SPACE SOLID BELOW FLASHING"),
        ((6.6, -6.0), "2\" XPS INSULATION BELOW FLASHING"),
        ((1.8, -9.0), "BRICK ON 4\" LEDGE 99'-0\", FULL MORTAR BED"),
        ((-3.0, -9.0), "FINISH GRADE 99'-4\", SLOPE AWAY 5% MIN. FOR 10'-0\""),
        ((xf - 0.06, -20.0), "BITUMINOUS DAMPPROOFING"),
        ((-3.0, -26.0), "COMPACTED BACKFILL"),
    ], xl, "l", 1.42, ylo, yhi)
    xr2 = v.to_paper((17.6, 0))[0]
    wr2 = c["x"] + c["w"] - 0.12 - xr2
    notes_col(sh, v, [
        ((12.0, 10.0), "8\" CMU, PNT-1"),
        ((7.85, 7.5), "AIR / WATER BARRIER OVER TERM. BAR"),
        ((XC1 + 0.12, 2.5), "RB-1 RUBBER BASE"),
        ((24.0, 0.07), "VCT-1"),
    ], xr2, "r", wr2, v.to_paper((0, 1.0))[1], yhi)
    xr3 = v.to_paper((19.2, 0))[0]
    wr3 = c["x"] + c["w"] - 0.1 - xr3
    notes_col(sh, v, [
        ((17.0, -2.5), "5\" SLAB ON GRADE, 4,000 PSI, WWF 6x6-W2.9xW2.9"),
        ((15.5, -0.6), "1/2\" ISOLATION JOINT + SEALANT"),
        ((18.2, -5.05), "15 MIL VAPOR RETARDER, TURN UP AT WALL"),
        ((18.3, -9.5), "6\" CA-6 BASE"),
        ((fi + 0.5, -16.0), "2\" XPS (R-10) PERIMETER INSULATION x 2'-0\" DEEP"),
        ((11.0, -3.5), "GROUT CMU CELLS SOLID BELOW SLAB; #5 DOWELS @ 48\" (S-301)"),
        ((10.0, -24.0), "12\" CONC. FDN. WALL W/ 4\" BRICK LEDGE (S-301)"),
    ], xr3, "r", wr3, ylo, v.to_paper((0, -12.0))[1])
    dtitle(sh, c, 10, "FOUNDATION / BASE OF WALL", sft)


# ---------------------------------------------------------------------------------------- 11
def det_ej_cj(sh, c):
    """Brick expansion joint + CMU control joint (aligned), plan, 3" = 1'-0".
    u along the wall, joint centered at u = 0; d = depth from brick face (exterior down)."""
    sft = 3.0
    ext = (-6.3, -2.4, 6.3, 18.0)
    v, xl, xr, ylo, yhi = setup(sh, c, ext, sft, wl=1.22, wr=1.22, pad=0.22)
    u0, u1 = -5.9, 5.9
    h = 0.1875
    # brick: units stop at the 3/8" EJ
    brick_plan(v, u0, -h, 0.0, XB1, start=-h - 7.625 - 8.0)
    brick_plan(v, h, u1, 0.0, XB1, start=h)
    R(v, -h, 0.75, h, XB1, lw="fine", fill="g20")
    sealant_h(v, -h, h, 0.0, 0.3, up=True, rod_r=0.22)
    rigid(v, u0, XA1, u1, XC0)
    air_barrier(v, [(u0, XC0 + 0.05), (u1, XC0 + 0.05)])
    v.polyline([(-3.0, XC0 - 0.09), (3.0, XC0 - 0.09)], lw=1.0)
    # CMU: sash units each side of the CJ, rubber shear key, sealant both faces
    cmu_plan(v, u0, -h, XC0, XC1, start=-h - 15.625, grout_cores={1}, bars={1})
    cmu_plan(v, h, u1, XC0, XC1, start=h, grout_cores={0}, bars={0})
    for sgn in (-1, 1):
        R(v, sgn * h, 10.6, sgn * (h + 0.75), 12.1, lw="fine", fill="white")
    v.polygon([(-0.85, 10.75), (0.85, 10.75), (0.85, 11.95), (-0.85, 11.95)], lw="fine", fill="g60")
    sealant_h(v, -h, h, XC0, 0.3, up=True, rod_r=0.22)
    sealant_h(v, -h, h, XC1, 0.3, up=False, rod_r=0.22)
    # veneer anchors within 12" each side (dashed: in bed joints)
    for uu in (-4.0, 4.0):
        v.polyline([(uu, 9.5), (uu, XA1 - 0.6), (uu + 0.6, XA1 - 0.6), (uu + 0.6, 1.2)], lw="fine",
                   dash=[2, 1])
    for uu in (u0, u1):
        brk(v, (uu, -0.5), (uu, XC1 + 0.5))
    v.line((0.0, -0.3), (0.0, -1.4), lw="fine", dash="center")
    v.line((0.0, XC1 + 0.3), (0.0, 17.3), lw="fine", dash="center")
    label(sh, v, (0.0, -1.9), "EJ / CJ", size=DS, font=FONT_B)
    label(sh, v, (-3.6, -1.5), "EXTERIOR", size=DS, font=FONT_B)
    label(sh, v, (3.6, 16.7), "INTERIOR", size=DS, font=FONT_B)
    v.dimi((-h, -0.1), (h, -0.1), 1.1, text="3/8\"")
    notes_col(sh, v, [
        ((-2.0, 1.8), "FB-1 FACE BRICK"),
        ((-4.0, 4.6), "2\" AIR SPACE"),
        ((-3.3, 6.6), "2\" POLYISO, CONTINUOUS ACROSS JOINT"),
        ((-4.6, 6.0), "ADJUSTABLE VENEER ANCHORS WITHIN 12\" EA. SIDE OF EJ"),
        ((-0.1, 0.25), "BRICK EJ: 3/8\" OPEN JOINT, NO MORTAR, BACKER ROD + SILICONE SEALANT"),
        ((-0.1, 2.5), "CLOSED-CELL COMPRESSIBLE FILLER FULL DEPTH"),
    ], xl, "l", 1.22, ylo, yhi)
    notes_col(sh, v, [
        ((3.0, 14.0), "8\" CMU SASH UNITS EA. SIDE OF CJ, PNT-1"),
        ((0.0, 11.3), "PREFORMED RUBBER CJ SHEAR KEY"),
        ((-3.9, 11.4), "#5 VERT. IN GROUTED CELL EA. SIDE OF CJ (S-SERIES)"),
        ((0.1, XC1 - 0.2), "INT. SEALANT + BACKER ROD (PAINTABLE)"),
        ((0.1, XC0 + 0.25), "SEALANT + BACKER ROD UNDER AIR BARRIER"),
        ((2.0, XC0 - 0.09), "6\" SELF-ADHERED MEMBRANE STRIP OVER CJ"),
        ((4.5, XC0 + 0.05), "FLUID-APPLIED AIR / WATER BARRIER"),
    ], xr, "r", 1.22, ylo, yhi)
    dtitle(sh, c, 11, "BRICK EJ & CMU CONTROL JOINT", sft, note="PLAN - EJ 25'-0\" O.C. MAX.")


# ---------------------------------------------------------------------------------------- 12
def det_link_roof(sh, c):
    """Link roof at main building wall W0 (grid 1 between B and C). y = 0 at 114'-0" (link
    T.O. steel = L2 T.O. slab). x = 0 at face of brick of W0 (link roof to the left).
    W0 CMU bears on 3/8" cap PL on W16x31 on grid (S-102 note 4); brick starts on a shelf
    angle at 115'-4" (A-202); base flashing below on glass-mat sheathing."""
    sft = 1.5
    ext = (-12.0, -24.0, 21.5, 31.0)
    v, xl, xr, ylo, yhi = setup(sh, c, ext, sft, wl=1.5, wr=1.2)
    bot, tp = -23.5, 30.0
    ys = 16.0                          # 115'-4" shelf angle (top)
    t = 7.0 / 16.0
    # W16x31 on grid + 3/8" cap plate, grouted cut course, CMU above from 114'-0"
    wshape(v, XG, -6.25, 15.875, 5.525, 0.44, 0.275)
    R(v, XC0, -6.25, XC1, -5.875, lw="fine", fill="black")
    R(v, XC0, -5.875, XC1, -0.375, lw="thin", fill="white", hatch="sand", hatch_kw=dict(scale=1.25))
    cmu_courses(v, XC0, XC1, 0.0, tp, 0.0, joint="bot", bond=(1,), bars={1: [9.9, 12.95]})
    air_barrier(v, [(7.7, 1.5), (7.7, tp)])
    # link deck on ledger angle bolted to the cut course / CMU
    angle(v, (XC0, 0.0), 4.0, 4.0, 0.375, dx=-1, dy=-1)
    v.line((XC0 - 0.6, -2.0), (10.5, -2.0), lw="med")
    deck_profile(v, -12.0, XC0 - 4.0 + 0.2, 0.0, phase=2.0)
    v.line((-12.0, 1.55), (-2.4, 1.55), lw="fine")
    rigid(v, -12.0, 1.6, -2.4, 3.6)
    rigid(v, -12.0, 3.6, -2.4, 5.5)
    R(v, -12.0, 5.5, -2.4, 6.0, lw="fine", fill="g20")
    for k in range(3):
        wood(v, -2.375, 1.5 + 1.5 * k, 3.125, 3.0 + 1.5 * k)
    # wall below the shelf angle: 2" XPS + 2" polyiso + 1/2" glass-mat sheathing
    rigid(v, XB1, 1.5, XA1, ys - 6.0 - 0.1)
    rigid(v, XA1, 1.5, XC0 - t - 0.05, ys - 4.0 - 0.1)
    rigid(v, XA1, ys - 4.0 + 0.05, XC0 - 0.05, ys - t - 0.05) if False else None
    R(v, 3.125, 1.5, XB1, ys - 6.0 - 0.1, lw="fine", fill="g20")
    wood_poly(v, [(-0.375, 6.0), (3.125, 6.0), (3.125, 9.5)])
    membrane(v, [(-12.0, 6.05), (-0.43, 6.05), (3.07, 9.55), (3.07, 9.75)])
    # shelf angle L7x4x7/16 LLH at 115'-4" (sim. 9) + flashing, brick above
    angle(v, (XC0, ys), 7.0, 4.0, t, dx=-1, dy=-1)
    v.line((XC0 - 0.6, ys - 2.0), (12.5, ys - 2.0), lw=1.6)
    rigid(v, XA1, ys - 4.0 + 0.05, XC0 - t - 0.05, ys - t - 0.05)
    brick_courses(v, 0, XB1, ys, tp, ys)
    flashing(v, [(-0.32, ys - 0.2), (-0.55, ys + 0.06), (5.6, ys + 0.06), (XC0 - 0.08, ys + 4.0),
                 (XC0 - 0.08, ys + 9.0)])
    R(v, XC0 - 0.08, ys + 8.0, XC0 + 0.22, ys + 9.0, lw="fine", fill="black")
    yi = lambda x: ys + 0.5 + (3.4 / (XC0 - 0.1 - 5.6)) * (x - 5.6)
    rigid(v, 0, 0, 0, 0, pts=[(XA1, ys + 0.6), (XC0 - 0.1, yi(XC0 - 0.1) + 0.1), (XC0 - 0.1, tp),
                               (XA1, tp)])
    # base flashing up sheathing, termination bar, counterflashing fastened under shelf angle
    membrane(v, [(3.07, 9.5), (3.07, ys - 6.6)])
    R(v, 2.8, ys - 7.4, 3.07, ys - 6.4, lw="fine", fill="black")
    v.polyline([(2.2, ys - t), (2.2, ys - t - 0.15), (2.75, ys - t - 0.15), (2.75, ys - 9.0),
                (2.45, ys - 9.4)], lw=1.0)
    R(v, -0.2, 1.5, 0.0, 1.5, lw=None) if False else None
    # L2 corridor slab (inside), deck edge per 4/S-302 sim.
    sx = XC1 + 0.5
    R(v, XC1, -6.25, sx, -0.4, lw="fine", fill="g20")
    bead(v, [(XC1, 0.0), (sx, 0.0), (sx, -0.4), (XC1, -0.4)])
    concrete(v, [(sx + 0.375, -6.25), (21.5, -6.25), (21.5, 0.0), (sx + 0.375, 0.0)], seed=17)
    steel(v, [(sx, -6.25), (sx + 0.375, -6.25), (sx + 0.375, -0.3), (sx, -0.3)])
    v.line((sx + 0.4, -3.25), (21.5, -3.25), lw="fine", dash=[2, 1.5])
    R(v, sx + 0.375, 0.0, 21.5, 0.125, lw="fine", fill="g40")
    R(v, XC1, 0.125, XC1 + 0.25, 4.125, lw="fine", fill="g60")
    brk(v, (-0.5, tp), (XC1 + 0.5, tp))
    brk(v, (-12.0, -1.0), (-12.0, 7.0))
    brk(v, (21.5, -7.0), (21.5, 1.0))
    brk(v, (XG - 3.4, -22.5), (XG + 3.4, -22.5))
    v.dimi((-6.0, 6.0), (-6.0, ys), 2.2, text="10\" (8\" MIN.)")
    elev_tag(sh, v, (XC1 + 0.5, 0.13), "T.O. SLAB L2", "114'-0\"", side="r", length=0.1)
    notes_col(sh, v, [
        ((1.8, ys + 9.0), "FB-1 FACE BRICK, STARTS ON SHELF ANGLE @ 115'-4\""),
        ((2.0, ys - 0.2), "L7x4x7/16 LLH SHELF ANGLE W/ FLASHING + SS DRIP, 3/4\" BOLTS @ 24\" (SIM. 9)"),
        ((2.75, ys - 4.0), "SS COUNTERFLASHING FASTENED UNDER SHELF ANGLE @ 12\" O.C., LAP 4\" OVER BASE FLASHING"),
        ((2.94, ys - 6.9), "TERMINATION BAR @ 8\" O.C. + LAP SEALANT"),
        ((3.07, 8.0), "EPDM BASE FLASHING (60 MIL REINF.) UP WALL 8\" MIN."),
        ((1.2, 7.0), "PT WOOD CANT STRIP 3 1/2\""),
        ((-8.0, 6.05), "60 MIL EPDM FULLY ADHERED ON 1/2\" COVER BOARD"),
        ((-9.0, 4.5), "(2) LAYERS 2\" POLYISO (TAPERED CRICKET PER A-103)"),
        ((0.4, 3.75), "(3) PT 2x6 NAILERS = INSUL. HT., FASTEN TO DECK @ 12\" O.C."),
        ((-10.0, 0.9), "1 1/2\" TYPE B ROOF DECK, SIDE LAP AT WALL"),
        ((XC0 - 2.0, -0.2), "CONT. L4x4x3/8 DECK LEDGER, 3/4\" ANCHORS @ 24\" (S-103)"),
    ], xl, "l", 1.5, ylo, yhi)
    notes_col(sh, v, [
        ((12.0, 24.0), "EW-1: 8\" CMU W/ AIR BARRIER"),
        ((6.6, 21.5), "2\" POLYISO"),
        ((4.6, 7.0), "1/2\" GLASS-MAT SHEATHING ON 2\" XPS, FASTEN THRU TO CMU"),
        ((XC1 + 0.12, 2.6), "RB-1 / LVT-1 (CORRIDOR 200)"),
        ((12.0, -3.0), "GROUT CUT COURSE SOLID ON 3/8\" CAP PL"),
        ((XG + 0.14, -14.0), "W16x31 ON GRID 1 (S-102)"),
        ((19.0, -4.5), "L2 SLAB, POUR STOP + JOINT (SIM. 9)"),
    ], xr, "r", 1.2, ylo, yhi)
    dtitle(sh, c, 12, "LINK ROOF TO MAIN WALL", sft, note="GRID 1 BETWEEN B AND C")


# ---------------------------------------------------------------------------------------- 13
def det_curb(sh, c):
    """RTU / roof hatch curb at main roof. y = 0 at top of joists (bottom of deck) 128'-0"."""
    sft = 1.5
    ext = (-12.0, -6.5, 5.5, 30.0)
    v, xl, xr, ylo, yhi = setup(sh, c, ext, sft, wl=1.42, wr=1.2)
    rs = 9.0                       # roof surface at curb
    deck_profile(v, -12.0, 2.0, 0.0, phase=0.5)
    angle(v, (2.25, 0.0), 4.0, 4.0, 0.25, dx=-1, dy=-1)
    R(v, -12.0, -1.5, -3.0, 0.0, lw="fine", fill="g40")
    v.line((-12.0, 1.55), (-5.5, 1.55), lw="fine")
    rigid(v, -12.0, 1.6, -5.5, 3.6)
    rigid(v, -12.0, 3.6, -5.5, 5.6)
    rigid(v, -12.0, 5.6, -5.5, 8.5)
    R(v, -12.0, 8.5, -5.5, 9.0, lw="fine", fill="g20")
    for k in range(5):
        wood(v, -5.5, 1.5 + 1.5 * k, 0.0, 3.0 + 1.5 * k)
    # prefabricated curb (Div. 23): 14 ga double wall w/ 1 1/2" insulation, 2x nailer at top
    v.polygon([(0.0, 1.5), (2.25, 1.5), (2.25, 1.62), (0.12, 1.62), (0.12, rs + 14.0),
               (0.0, rs + 14.0)], lw="fine", fill="black")
    rigid(v, 0.12, 1.62, 1.62, rs + 13.5)
    v.line((1.62, 1.62), (1.62, rs + 13.5), lw="thin")
    wood(v, 0.12, rs + 13.5 - 1.5, 1.62, rs + 13.5)
    v.polyline([(-0.8, rs + 11.0), (-0.5, rs + 14.6), (2.4, rs + 14.6), (2.4, rs + 13.0)], lw=1.0,
               dash=[3, 1.5])
    R(v, -1.0, rs + 14.6, 5.5, rs + 20.0, lw="fine", dash=[3, 1.5])
    membrane(v, [(-12.0, rs + 0.05), (-0.06, rs + 0.05), (-0.06, rs + 12.5)])
    brk(v, (-12.0, -1.8), (-12.0, 10.0))
    brk(v, (5.5, rs + 14.0), (5.5, rs + 21.0))
    v.dimi((-3.0, rs), (-3.0, rs + 14.0), 1.4, text="14\" MIN.")
    v.dimi((-5.5, 1.5), (-5.5, rs), 1.5, text="7 1/2\"")
    notes_col(sh, v, [
        ((-0.6, rs + 12.0), "UNIT / HATCH CAP COUNTERFLASHING (BY MFR.)"),
        ((-0.06, rs + 7.0), "EPDM BASE FLASHING UP CURB TO UNDER CAP, TERM. BAR"),
        ((-9.0, rs + 0.05), "60 MIL EPDM ON COVER BOARD"),
        ((-9.5, 5.0), "POLYISO (TAPERED, VARIES)"),
        ((-2.75, 5.5), "(5) PT 2x6 NAILERS STACKED TO INSUL. HT., FULL CURB PERIMETER, FASTEN TO DECK"),
        ((-10.0, 0.8), "ROOF DECK"),
        ((-9.0, -0.75), "JOIST TOP CHORD"),
    ], xl, "l", 1.42, ylo, yhi)
    notes_col(sh, v, [
        ((3.0, rs + 17.0), "RTU (DIV. 23)"),
        ((0.9, rs + 12.75), "2x PT NAILER (BY CURB MFR.)"),
        ((1.0, rs + 6.0), "PREFAB. INSULATED CURB, 14 GA. GALV. (DIV. 23)"),
        ((1.0, -2.0), "L4x4x1/4 OPENING FRAME (S-103)"),
    ], xr, "r", 1.2, ylo, yhi)
    dtitle(sh, c, 13, "RTU / ROOF HATCH CURB", sft, note="RTU-1/2/3 7'-0\"x14'-0\"; HATCH 30\"x36\"")


# ---------------------------------------------------------------------------------------- 14
def det_exist_ej(sh, c):
    """Link roof to existing building: curbed roof expansion joint, 1" = 1'-0".
    x = 0 at existing east face (x = -36'); y = 0 at link T.O. steel 114'-0"."""
    sft = 1.0
    ext = (-17.5, -13.5, 13.5, 22.0)
    v, xl, xr, ylo, yhi = setup(sh, c, ext, sft, wl=1.15, wr=1.15)
    # existing wall + roof (screened)
    v.polygon([(-12.0, -13.0), (0.0, -13.0), (0.0, 2.0), (-12.0, 2.0)], lw="thin", color="screen",
              fill="g10", hatch="ansi31", hatch_kw=dict(spacing=0.06, col="screen"))
    R(v, -17.5, -8.0, -12.0, -6.5, lw="fine", color="screen")
    v.polygon([(-17.5, -6.5), (-12.0, -6.5), (-12.0, -3.5), (-17.5, -3.8)], lw="fine",
              color="screen", fill="g05")
    # new curbs: existing side on wall, link side on deck
    wood(v, -11.0, 2.0, -1.0, 3.5)
    wood(v, -4.5, 3.5, -1.5, 14.75)
    v.line((-3.0, 3.5), (-3.0, 14.75), lw="fine")
    wshape(v, 9.0, 0.0, 11.91, 3.97, 0.225, 0.2)
    deck_profile(v, 4.5, 13.5, 0.0, phase=1.0)
    wood(v, 4.5, 1.5, 10.0, 3.0)
    wood(v, 4.5, 3.0, 7.5, 14.25)
    v.line((6.0, 3.0), (6.0, 14.25), lw="fine")
    rigid(v, 10.0, 1.6, 13.5, 5.5)
    R(v, 10.0, 5.5, 13.5, 6.0, lw="fine", fill="g20")
    wood_poly(v, [(7.5, 6.0), (10.5, 6.0), (7.5, 9.0)])
    membrane(v, [(13.5, 6.05), (10.5, 6.05), (7.56, 9.0), (7.56, 14.35), (4.4, 14.35)])
    membrane(v, [(-17.5, -3.75), (-12.06, -3.5), (-12.06, 2.05), (-4.6, 3.55), (-4.6, 14.85),
                 (-1.4, 14.85)])
    # EJ cover: flanges + bellows; mineral wool in gap
    v.polyline([(-5.0, 15.1), (-1.5, 15.1), (-1.0, 15.1)], lw=1.0)
    v.polyline([(4.0, 14.6), (8.0, 14.6)], lw=1.0)
    pts = [(-1.0, 15.1)]
    for i in range(1, 20):
        t = i / 20.0
        pts.append((-1.0 + 5.0 * t, 15.1 - 0.5 * t - 3.2 * math.sin(math.pi * t)))
    pts.append((4.0, 14.6))
    v.polyline(pts, lw=1.0)
    v.polyline([(-5.3, 14.6), (-5.3, 15.6), (8.3, 15.4), (8.3, 14.1)], lw="med")
    R(v, 0.2, 1.5, 4.3, 12.0, lw="fine", fill="white", hatch="insul", hatch_kw=dict(spacing=0.035))
    brk(v, (13.5, -1.0), (13.5, 7.0))
    brk(v, (-17.5, -9.0), (-17.5, -3.0))
    brk(v, (-12.5, -13.0), (0.5, -13.0))
    v.dimi((0.0, -1.0), (4.5, -1.0), -2.0, text="4 1/2\"")
    notes_col(sh, v, [
        ((-6.0, 15.5), "PREFAB. ROOF EXPANSION JOINT COVER: EPDM BELLOWS + FOAM, METAL CAP, NAILING FLANGES"),
        ((-3.0, 9.0), "(2) PT 2x12 ON EDGE, ON 2x6 PT PLATE ANCHORED TO EXIST. WALL @ 24\" O.C."),
        ((-12.06, 0.0), "NEW EPDM FLASHING OVER EXIST. WALL, TIE TO EXIST. ROOFING"),
        ((-15.0, -5.0), "EXISTING ROOF (113'-4\" +/-), PROTECT"),
        ((-6.0, -8.0), "EXISTING WALL"),
    ], xl, "l", 1.15, ylo, yhi)
    notes_col(sh, v, [
        ((2.3, 7.0), "MINERAL WOOL FILL"),
        ((6.0, 9.0), "(2) PT 2x12 ON EDGE ON 2x6 PT PLATE, FASTEN TO DECK"),
        ((9.0, 7.5), "PT CANT"),
        ((12.0, 6.05), "LINK ROOF: EPDM / COVER BD. / 4\" POLYISO"),
        ((9.0, -6.0), "LINK EDGE BEAM (S-103)"),
    ], xr, "r", 1.15, ylo, yhi)
    dtitle(sh, c, 14, "LINK TO EXISTING ROOF EJ", sft, note="X = -36'-0\"")


# ---------------------------------------------------------------------------------------- notes
EXT_NOTES = [
    "DETAILS APPLY AT LEVEL 1 AND LEVEL 2 UNLESS NOTED; ELEVATIONS NOTED IN TITLES. DIMENSIONS ARE ACTUAL MATERIAL SIZES.",
    "FB-1 / FB-2: MODULAR FACE BRICK 3 5/8\" x 2 1/4\" x 7 5/8\", RUNNING BOND, 3 COURSES = 8\", TYPE N MORTAR (TYPE S BELOW GRADE).",
    "CMU: 8\" (7 5/8\" x 7 5/8\" x 15 5/8\") NORMAL WEIGHT, TYPE S MORTAR; GROUT, REINFORCING, BOND BEAMS AND LINTELS PER S-SERIES (LINTEL SCHEDULE S-302).",
    "VENEER ANCHORS: ADJUSTABLE 2-PIECE HOT-DIP GALV. @ 16\" O.C. EACH WAY; ADD ANCHORS @ 36\" O.C. MAX. WITHIN 12\" OF OPENINGS AND EJs (TMS 402).",
    "THRU-WALL FLASHING: 40 MIL SELF-ADHERED RUBBERIZED ASPHALT W/ 26 GA. SS DRIP EDGE AT HEADS, SILLS, SHELF ANGLES, BASE OF WALL AND ROOF INTERSECTIONS; END DAMS AT ALL TERMINATIONS; LAP 6\" AND SEAL. WEEP VENTS @ 24\" O.C.",
    "WOOD BLOCKING: PRESERVATIVE-TREATED (PT, AWPA UC3B / UC4A) AT CAVITY, EXTERIOR AND ROOF; FIRE-RETARDANT-TREATED (FRT) AT INTERIOR. HOT-DIP GALV. OR SS FASTENERS. SEE WOOD BLOCKING SCHEDULE ON A-502.",
    "SEALANT JOINTS: SILICONE (EXTERIOR) / URETHANE (INTERIOR) OVER CLOSED-CELL BACKER ROD, 1/2\" WIDE UNLESS NOTED.",
    "STEEL LINTELS, SHELF ANGLES AND BENT PLATES: HOT-DIP GALVANIZED. CONFIRM SIZES WITH S-302.",
    "AIR / WATER BARRIER CONTINUOUS: LAP TRANSITION MEMBRANES TO WINDOW AND STOREFRONT FRAMES, ROOF MEMBRANE AND THRU-WALL FLASHINGS.",
    "BRICK EXPANSION JOINTS @ 25'-0\" O.C. MAX. AND WITHIN 4'-0\" OF OUTSIDE CORNERS; CMU CONTROL JOINTS @ 24'-0\" O.C. MAX., ALIGNED WITH BRICK EJ WHERE POSSIBLE (SEE ELEVATIONS A-201 / A-202).",
]


def legend_swatches(sh, x, y, w):
    """Material legend: returns height used."""
    sh.text((x, y), "MATERIAL LEGEND", size=TXT["label"], font=FONT_B, valign="top", underline=True)
    items = ["brick", "cmu", "grout", "conc", "cast", "rigid", "batt", "wood", "ply", "steel",
             "earth", "gravel", "seal", "flash", "ab"]
    labels = {
        "brick": "FACE BRICK (SECTION)", "cmu": "CMU (FACE SHELLS CUT)", "grout": "GROUT / GROUTED CELL",
        "conc": "CONCRETE", "cast": "CAST STONE", "rigid": "RIGID INSULATION",
        "batt": "BATT / SOUND INSULATION", "wood": "WOOD BLOCKING (CONT.)", "ply": "PLYWOOD",
        "steel": "STEEL", "earth": "COMPACTED EARTH", "gravel": "CA-6 GRANULAR BASE",
        "seal": "SEALANT + BACKER ROD", "flash": "FLASHING / ROOF MEMBRANE", "ab": "AIR / WATER BARRIER",
    }
    col_w = w / 2
    yy = y - 0.3
    for i, k in enumerate(items):
        cx = x + (i % 2) * col_w
        cy = yy - (i // 2) * 0.27
        v = DV(sh.c, cx, cy - 0.16, 3.0, 0.0, 0.0)
        bw, bh = 0.5 * 4.0, 0.16 * 4.0      # inches at 3" scale
        if k == "brick":
            brick_unit(v, 0, 0, bw, bh)
        elif k == "cmu":
            R(v, 0, 0, bw, bh, lw="thin", fill="white", hatch="ansi31", hatch_kw=dict(spacing=0.06))
        elif k == "grout":
            R(v, 0, 0, bw, bh, lw="thin", hatch="sand", hatch_kw=dict(scale=1.25))
        elif k == "conc":
            concrete_r(v, 0, 0, bw, bh)
        elif k == "cast":
            caststone(v, [(0, 0), (bw, 0), (bw, bh), (0, bh)])
        elif k == "rigid":
            rigid(v, 0, 0, bw, bh)
        elif k == "batt":
            R(v, 0, 0, bw, bh, lw="thin")
            batt(v, 0, 0, bw, bh, vertical=False)
        elif k == "wood":
            wood(v, 0, 0, bw, bh)
        elif k == "ply":
            plywood(v, 0, 0, bw, bh)
        elif k == "steel":
            R(v, 0, bh * 0.35, bw, bh * 0.65, lw="fine", fill="black")
        elif k == "earth":
            earth(v, [(0, 0), (bw, 0), (bw, bh), (0, bh)], lw="thin")
        elif k == "gravel":
            gravel(v, [(0, 0), (bw, 0), (bw, bh), (0, bh)], lw="thin")
        elif k == "seal":
            bead(v, [(0.0, bh * 0.3), (0.5, bh * 0.5), (0.0, bh * 0.7), (0.4, bh * 0.7), (0.4, bh * 0.3)])
            rod(v, (0.75, bh * 0.5), 0.22)
        elif k == "flash":
            flashing(v, [(0, bh * 0.5), (bw, bh * 0.5)])
        elif k == "ab":
            air_barrier(v, [(0, bh * 0.5), (bw, bh * 0.5)])
        sh.text((cx + 0.6, cy - 0.08), labels[k], size=DS, valign="mid")
    return 0.3 + ((len(items) + 1) // 2) * 0.27


def det_notes(sh, c):
    x = c["x"] + 0.2
    y = c["y"] + c["h"] - 0.2
    w = c["w"] - 0.4
    h = notes_block(sh, x, y, "EXTERIOR DETAIL NOTES", EXT_NOTES, w, size=TXT["small"])
    legend_swatches(sh, x, y - h - 0.15, w)


# ----------------------------------------------------------------------------------------
def draw_a501(sh):
    cells = layout_rows(sh, [
        (6.4, [6.1, 6.15, 6.0, 6.1, 6.95]),
        (8.3, [6.15, 5.7, 7.0, 6.2, 6.25]),
        (8.31, [6.3, 7.6, 5.6, 5.6, 6.2]),
    ])
    det_wa_head(sh, cells[0])
    det_wa_jamb(sh, cells[1])
    det_wa_sill(sh, cells[2])
    det_sf1_head(sh, cells[3])
    det_sf1_sill(sh, cells[4])
    det_sf1_jamb(sh, cells[5])
    det_sf3(sh, cells[6])
    det_parapet(sh, cells[7])
    det_shelf(sh, cells[8])
    det_foundation(sh, cells[9])
    det_ej_cj(sh, cells[10])
    det_link_roof(sh, cells[11])
    det_curb(sh, cells[12])
    det_exist_ej(sh, cells[13])
    det_notes(sh, cells[14])


SHEETS = [
    ("A-501", "EXTERIOR DETAILS", draw_a501),
]
