# Brief for sheet authors (read fully before writing code)

## What we are building
A **fictional** bid-set drawing package (all disciplines **except MEP**) for a two-story
elementary school classroom addition. Students use it to practice quantity takeoff and
estimating for the ASC Region III commercial competition (scored scopes: masonry, carpentry,
resilient flooring / carpet / tile, doors-frames-hardware, windows & storefront, general conditions).
So drawings must be **dimensionally exact, internally consistent, and rich in quantity-relevant
information** (sizes, materials, spacing, heights, counts, schedules), with professional CD conventions.

Project root: `/home/user/youngbrain85.github.io/asc2026-practice-drawings`
* `DESIGN.md`: design basis (authoritative dimensions, materials, structure, site). READ IT.
* `drawset/model.py`: the data model (grids, levels, walls, openings, rooms, finishes, door/hardware/casework data). Use it; never re-type data that exists there.
* `drawset/cad.py`: drafting toolkit (Paper / View primitives, dims, hatches, tags, tables, notes, symbols). Read the whole file once.
* `drawset/sheet.py`: `Sheet` (ARCH D 36"x24", title block drawn automatically). Drawing area = `sh.x0..sh.x1` (about 1.12" to 32.4") by `sh.y0..sh.y1` (about 0.5" to 23.5"), in paper inches.
* `drawset/plans.py`: plan renderer used by the floor plans (wall geometry via shapely, doors, windows, stairs, toilets, casework). Reuse its functions where helpful (e.g. `wall_geoms`, `draw_walls(v, level, style)`, `draw_openings`, `stair_geom`, `draw_stair`).
* `drawset/sheets_arch_plans.py`: example sheet module (A-101 / A-102). Follow its style.
* `drawset/build.py`: builder. Your module must define `SHEETS = [(number, title, draw_fn), ...]`; `draw_fn(sh)` draws one sheet.

## Rules
1. Write ONLY your own module file(s) named in your task. **Do not edit** cad.py, sheet.py, model.py, plans.py, build.py or other agents' modules (other people are editing in parallel). If you need a helper, write it in your module. If you find a real bug or inconsistency in a shared file, work around it and **report it** in your final message (exact file/line and proposed fix).
2. Preview your sheets with:
   `cd /home/user/youngbrain85.github.io/asc2026-practice-drawings && python3 -m drawset.build --only S-101 S-102 --png --dpi 60`
   It writes `output/preview_<nums>.pdf` and `output/png/preview_<nums>-N.png`. LOOK at the PNG with the Read tool. For detail checks render a zoomed crop, e.g.
   `pdftoppm -png -r 150 -x 0 -y 0 -W 2400 -H 1600 output/preview_S-101.pdf output/png/zoom_s101` (x/y/W/H are pixels at that dpi).
   Iterate until: no overlapping text or symbols, nothing outside the drawing area, all text legible (minimum 4.5 pt; notes 6.75 pt), line weights hierarchical (cut/outline heavy, beyond/hidden light).
3. Units: model = feet (x east, y north, origin grid 1/D). Paper = inches. Scales: paper inches per foot (1/8" = 1'-0" -> 1/8; 1/2" -> 1/2; 1"=30' -> 1/30). Use the right conventional scale per drawing and label it with `sh.view_title(x, y, num, title, scale)`.
4. Use real numbers from model.py / DESIGN.md for everything (grid spacing, levels, opening sizes and positions, wall types). Dimension strings via `View.dim` / `dim_chain` show true model lengths.
5. Text must be project-specific and technically correct (US practice, IBC 2021, ACI 318, TMS 402/602, AISC 360, SJI, ASCE 7-16, IDOT standards for civil). No lorem ipsum, no placeholders.
6. Keep each sheet visually balanced: views laid out on a clean grid (`sh.cells(cols, rows)` helps for detail sheets), view titles under each view with number + scale, notes blocks aligned.
7. Performance: whole sheet should render in a few seconds. Avoid hatching huge areas with dense random patterns.
8. Finish with a short report: sheets produced (number + title + contents), anything in the shared model you found inconsistent, and any cross-references you used (e.g. details you referenced on other sheets).

## Cross-reference map (keep these numbers)
* A-101/A-102 floor plans, A-103 roof plan, A-111/A-112 finish plans, A-121/A-122 reflected ceiling plans, AD101 demolition.
* A-201: 1 NORTH ELEVATION, 2 SOUTH ELEVATION. A-202: 1 EAST ELEVATION, 2 WEST ELEVATION, 3 LINK NORTH ELEVATION, 4 LINK SOUTH ELEVATION.
* A-301: 1 TRANSVERSE BUILDING SECTION at x = 75' (looking west), 2 LONGITUDINAL BUILDING SECTION at y = 36' (looking north, through corridor from existing building to east entrance), 3 LINK SECTION at x = -18' (looking east).
* A-311: 1 WALL SECTION north wall at W-A window (x = 45'), 2 WALL SECTION south wall at W-A window with louver/solid wall context (x = 105'), 3 WALL SECTION stair tower at W-C (x = 6', y = 0').
* A-312: 1 WALL SECTION east entrance SF-1 (x = 150', y = 36'), 2 WALL SECTION link storefront SF-3 at existing building tie-in (x = -12', y = 42').
* A-401: 1 ENLARGED TOILET PLAN LEVEL 1 (x 28..62, y -2..32), 2 ENLARGED TOILET PLAN LEVEL 2, 3 STAIR 1 ENLARGED PLANS (L1 + L2), 4 STAIR 2 ENLARGED PLANS (L1 + L2). A-402: stair sections, railing and elevator pit details.
* A-501: exterior details (window head/jamb/sill W-A, storefront SF-1/SF-3 head/sill/jamb, parapet/coping, shelf angle at CS-2 band, foundation/base flashing, masonry control joint, link roof-to-wall).
* A-502: partition types P1-P4 + EW-1, door frame head/jamb details, casework sections, misc. interior details.
* A-601: typical classroom interior elevations (1-4) + casework details. A-602: toilet room interior elevations.
* A-701: door schedule, door types, frame types. A-702: hardware sets. A-711: window and storefront types/schedule. A-801: room finish schedule, finish legend, casework schedule.
* S-001 general notes; S-101 foundation plan; S-102 second floor framing; S-103 roof framing (+ link roof); S-301 foundation details; S-302 masonry and steel details incl. lintel schedule; S-401 schedules (column, footing, beam if needed).
* C-100 existing conditions & site demolition; C-200 site layout & paving; C-300 grading & erosion control; C-400 site utilities; C-500 civil details.
