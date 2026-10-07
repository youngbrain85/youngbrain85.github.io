"""
Build the drawing set.

    python3 -m drawset.build                 # full set -> output/<SET>.pdf
    python3 -m drawset.build --only A-101 A-102 --png   # quick preview of selected sheets

Sheet modules each expose SHEETS = [(number, title, draw_fn), ...].
"""
from __future__ import annotations

import argparse
import importlib
import os
import subprocess
import sys
import traceback

from reportlab.pdfgen.canvas import Canvas

from .cad import PT
from .sheet import PROJECT, SHEET_H, SHEET_W, Sheet

MODULES = [
    "drawset.sheets_general",
    "drawset.sheets_civil",
    "drawset.sheets_struct",
    "drawset.sheets_arch_plans",
    "drawset.sheets_arch_elev",
    "drawset.sheets_arch_interiors",
    "drawset.sheets_arch_details",
    "drawset.sheets_arch_sched",
]

ORDER_PREFIX = ["G", "C", "S", "AD", "A"]

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "output")
SET_NAME = "CedarPrairie_ES_Addition_Practice_Drawings_BidSet"


def collect(strict=False):
    sheets = []
    for mod in MODULES:
        try:
            m = importlib.import_module(mod)
        except ModuleNotFoundError as e:
            if e.name == mod:
                continue
            raise
        sheets.extend(getattr(m, "SHEETS", []))

    def key(s):
        num = s[0]
        pre = "".join(ch for ch in num if ch.isalpha())
        try:
            p = ORDER_PREFIX.index(pre)
        except ValueError:
            p = 99
        return (p, num)

    return sorted(sheets, key=key)


def sheet_index():
    """[(number, title)] for the cover sheet index"""
    return [(n, t) for n, t, _ in collect()]


def build(only=None, png=False, out_name=None, dpi=60):
    os.makedirs(OUT, exist_ok=True)
    sheets = collect()
    if only:
        sheets = [s for s in sheets if s[0] in only]
    name = out_name or (SET_NAME if not only else "preview_" + "_".join(only))
    path = os.path.join(OUT, name + ".pdf")
    c = Canvas(path, pagesize=(SHEET_W * PT, SHEET_H * PT))
    c.setTitle(f"{PROJECT['name1']} - {PROJECT['name2']} - {PROJECT['issue']}")
    c.setAuthor("Estimating practice set (fictional project)")
    c.setSubject("Drawing set excluding MEP")
    total = len(collect())
    allnums = [s[0] for s in collect()]
    errors = []
    for num, title, fn in sheets:
        sh = Sheet(c, num, title, allnums.index(num) + 1, total)
        c.bookmarkPage(num)
        c.addOutlineEntry(f"{num}  {title.replace(chr(10), ' ')}", num, level=0)
        try:
            sh.frame()
            fn(sh)
        except Exception:
            errors.append(num)
            traceback.print_exc()
            sh.text((10, 12), f"ERROR DRAWING SHEET {num}", size=30, color="red")
        c.showPage()
    c.save()
    print("wrote", path, f"({len(sheets)} sheets)")
    if errors:
        print("ERRORS ON:", errors)
    if png:
        prefix = os.path.join(OUT, "png", name)
        os.makedirs(os.path.dirname(prefix), exist_ok=True)
        subprocess.run(["pdftoppm", "-png", "-r", str(dpi), path, prefix], check=True)
        print("png ->", prefix + "-*.png")
    return path, errors


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--png", action="store_true")
    ap.add_argument("--dpi", type=int, default=60)
    a = ap.parse_args()
    p, errs = build(a.only, a.png, dpi=a.dpi)
    sys.exit(1 if errs else 0)
