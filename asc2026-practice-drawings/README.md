# ASC 2026 Region III Commercial: Practice Drawing Set (Fictional)

**Cedar Prairie Elementary School: Two-Story Classroom Addition** is a fictional bid set (MEP excluded)
built to match the 2026 ASC Region III Commercial Estimating Competition problem format: an addition to
an occupied elementary school. The real competition drawings are released at the opening meeting.
This set is for practicing takeoff, estimating, scheduling, logistics and safety planning **before** the competition.

> Rules 2, 4 and 12 of the problem statement prohibit outside help (including tools like this one)
> from the moment the problem is distributed (Oct 22, 2026, 8:00 a.m.) until the end of the competition.

## Contents
| File | Description |
|---|---|
| `output/CedarPrairie_ES_Addition_Practice_Drawings_BidSet.pdf` | Full drawing set, ARCH D (36"x24"), true-scale vector PDF (calibrate Bluebeam / OST on the stated scales). Printing at 50% gives a half-size set (scales halve). |
| `output/CedarPrairie_ES_Addition_Practice_Quantity_Answer_Key.xlsx` | Quantity answer key (masonry, flooring/base/tile, doors-frames-hardware, windows/storefront, carpentry/casework). Open it only after doing your own takeoff. |
| `DESIGN.md` | Design basis: dimensions, levels, wall types, openings, structure, site, owner requirements |
| `drawset/` | Python source (reportlab + shapely) that generates every sheet from one model (`model.py`) |

## Sheet groups
* **G**: cover, code analysis / owner requirements / bid-form allowances, life safety plans
* **C**: existing conditions & demolition, site layout, grading & erosion control, utilities, details
* **S**: general notes, foundation / 2nd-floor / roof framing plans, details, schedules
* **A**: demolition at the tie-in, floor / roof / finish / reflected ceiling plans, elevations, sections,
  wall sections, enlarged plans, details, interior elevations, door / hardware / window / finish schedules

## Rebuild
```bash
pip install reportlab shapely openpyxl
python3 -m drawset.build          # full PDF set -> output/
python3 -m drawset.quantities     # answer key workbook -> output/
python3 -m drawset.build --only A-101 A-111 --png   # preview selected sheets
```
