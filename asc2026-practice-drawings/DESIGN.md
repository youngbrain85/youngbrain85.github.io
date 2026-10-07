# Design Basis: Cedar Prairie Elementary School Classroom Addition (PRACTICE SET)

This is a **fictional** project created for ASC Region III Commercial estimating practice.
It is not the actual competition project. The real drawings are handed out at the competition.
Every dimension below is authoritative. All sheets and the quantity check workbook derive from
`drawset/model.py`, which encodes this document.

## 1. Project Summary
| Item | Value |
|---|---|
| Project | Cedar Prairie Elementary School: Two-Story Classroom Addition |
| Owner | Cedar Prairie Community School District (fictional) |
| Site | 1400 Prairie Avenue, Cedar Prairie, Illinois (fictional) |
| Project No. | 2026-117 |
| Issue | BID SET, September 15, 2026 |
| Occupancy | Group E (Educational) |
| Construction type | IIB, fully sprinklered (NFPA 13) |
| Code basis | 2021 IBC, 2021 IECC (as amended by Illinois), Illinois Accessibility Code, 23 IAC 180 (ISBE Health/Life Safety) |
| Stories | 2 (addition) + 1-story link to existing 1-story school |
| Gross area | Level 1 11,714 SF (incl. 500 SF link); Level 2 11,227 SF; total 22,941 GSF |

## 2. Coordinates, Grids, Levels
Model units are **feet**. x = east, y = north. Origin = grid 1 / grid D.

* Column grids (numbers, x): 1 = 0', 2 = 30', 3 = 60', 4 = 90', 5 = 120', 6 = 150'
* Column grids (letters, y): D = 0', C = 30', B = 42', A = 72'
* Link grids: L1 = x -35' (new columns 1'-0" clear of the existing wall), L2 = x -18'
* Existing building east exterior face: x = -36'. The existing wall is 1'-0" thick (x -37' to -36').

Grid lines are at the **centerline of the CMU** (exterior backup and interior CMU walls) and at
column centerlines.

| Level | Elevation (arch) | Notes |
|---|---|---|
| T.O. footing (exterior) | 96'-4" | bottom of footing 95'-4" (4'-0" below grade, frost) |
| Brick ledge | 99'-0" | |
| T.O. foundation wall / finish grade at building | 99'-4" | |
| Level 1 FFE | 100'-0" | = civil elevation 712.50 (NAVD88) |
| Level 2 T.O. slab | 114'-0" | |
| Link roof T.O. steel | 114'-0" | link parapet top 116'-8" |
| Roof T.O. steel (flat; tapered insulation) | 128'-0" | |
| Top of parapet (main) | 131'-4" | |
| Existing roof (approx.) | 113'-4" | |

## 3. Building Layout (both levels unless noted)
North side (between B and A, 30' deep):

| Bay (x) | Level 1 | Level 2 |
|---|---|---|
| 0 to 30 | 101 Classroom | 201 Classroom |
| 30 to 60 | 102 Classroom | 202 Classroom |
| 60 to 90 | 103 Classroom | 203 Classroom |
| 90 to 120 | 104 Classroom | 204 Classroom |
| 120 to 138 | 105 Small Group | 205 Small Group |
| 138 to 150 | ST-2 Stair 2 | ST-2 Stair 2 |

Corridor between C and B (12' c-c, 11'-4 3/8" clear): 100 Corridor / 200 Corridor.
Link (L1 only): 100A Link Corridor, x -36 to 0, between y 30 and 42.

South side (between D and C, 30' deep):

| Zone | Level 1 | Level 2 |
|---|---|---|
| x 0 to 12 | ST-1 Stair 1 | ST-1 Stair 1 |
| x 12 to 30 (L-shape around the elevator) | 106 Staff Workroom | 206 Teacher Planning |
| x 12 to 20, y 0 to 8.5 | 107 Staff Toilet (from 106) | 207 Staff Toilet (from 206) |
| x 21 to 30, y 21 to 30 | 108 Elevator hoistway | 208 Elevator hoistway |
| x 30 to 41, y 12 to 30 | 109 Boys | 209 Boys |
| x 41 to 49, y 20 to 30 | 110 Custodial | 210 Custodial (roof hatch + ladder) |
| x 49 to 60, y 12 to 30 | 111 Girls | 211 Girls |
| x 30 to 60, y 0 to 12 plus x 41 to 49, y 12 to 20 (T-shape) | 112 Mech./Elec. (ext. door + door from 110) | 212 Storage / IDF (door from 210) |
| 60 to 90 | 113 Classroom | 213 Classroom |
| 90 to 120 | 114 Classroom | 214 Classroom |
| 120 to 150 | 115 Classroom | 215 Classroom |

Stairs: 2 flights per floor, 24 risers at 7", 11" treads (11 treads per flight = 10'-1"), flights 5'-2" wide, 12" well.
* ST-1: L1 and L2 landings at the north (corridor) end. Intermediate landing at the south. Exterior exit door on the west wall (x = 0) near the north end.
* ST-2: L1 and L2 landings at the south (corridor) end. Intermediate landing at the north. Exterior exit door on the east wall (x = 150) near the south end.

Elevator: 3,500 lb MRL traction, 2 stops, front opening 3'-6" x 7'-0" (by elevator contractor). Pit 5'-0" deep. Controller located in Room 112.

## 4. Wall Types
| Tag | Description | Thickness |
|---|---|---|
| EW-1 | Exterior cavity wall: 3 5/8" modular face brick (FB-1), 2" air space, 2" polyiso insulation, fluid-applied air/water barrier, 8" CMU backup (reinforced) with exposed painted interior face | 15 1/4" (CMU centered on grid; brick outboard) |
| P1 | 8" CMU (7 5/8"), painted, to underside of structure | 7 5/8" |
| P2 | 8" CMU, 1-HR fire-resistance rated, to underside of deck, firestopped head | 7 5/8" |
| P3 | 3 5/8" 20 ga metal studs @ 16" o.c., 5/8" GWB each side, sound batt, to 6" above ceiling | 4 7/8" |
| P4 | 6" 20 ga metal studs @ 16" o.c., 5/8" moisture-resistant GWB each side (wet wall), to underside of structure | 7 1/4" |

Exterior wall layers (offset from grid toward exterior): CMU -3 13/16" to +3 13/16"; insulation to +5 13/16";
air space to +7 13/16"; brick to +11 7/16".

CMU heights for takeoff: L1 interior CMU 100'-0" to 113'-4" (20 courses). L2 interior CMU 114'-0" to 127'-4".
Exterior CMU backup 99'-4" to 131'-4" (48 courses). Brick from 99'-0" to coping.

## 5. Openings
Masonry opening (MO) sizes are modular (8"). Door frames: hollow metal, 2" faces, 4" head (7'-4" MO height).
* Frame F1 (single 3'-0" door): MO 3'-4" wide
* Frame F2 (3'-0" door + 1'-0" glass sidelight): MO 4'-8" wide (classrooms)
* Frame F3 (pair 2 x 3'-0"): MO 6'-4" wide

Windows (aluminum, thermally broken) and storefront:
| Type | MO (W x H) | Sill | Notes |
|---|---|---|---|
| W-A | 6'-8" x 6'-8" | 2'-8" AFF | fixed upper lites over awning vent; cast stone sill |
| W-B | 4'-0" x 6'-8" | 2'-8" AFF | fixed over awning |
| W-C | 4'-0" x 18'-8" | 103'-4" (head 122'-0") | stair tower vertical storefront strip at the intermediate landings |
| SF-1 | 10'-8" x 9'-4" | 0 | east entrance: pair 3'-0" x 7'-0" alum. doors, sidelites, transom |
| SF-2 | 10'-8" x 6'-8" | 2'-8" AFF (L2) | corridor end windows (L2 east and west) |
| SF-3 | 32'-0" x 9'-4" | 100'-0" | link storefront, north and south walls; sits on an 8" exposed concrete curb (grade 99'-4" to 100'-0") |
| LV-1 | 4'-0" x 4'-0" | 8'-0" AFF | louver by Div 23; opening, lintel and frame by GC |

## 6. Exterior Materials
FB-1 field brick (modular, running bond, 3 courses = 8"). FB-2 accent brick: 6-course base band from
grade 99'-4" to 100'-8", and an 8" soldier course directly above every W-A / W-B / SF-2 head
(L1 heads 109'-4" -> soldier 109'-4" to 110'-0"; L2 heads 123'-4" -> 123'-4" to 124'-0").
CS-1 cast stone sills 4" high x 1" projection under W-A, W-B, SF-2. CS-1 cast stone sills at W-A/W-B. CS-2 cast stone band 8" high at Level 2
(113'-4" to 114'-0") on a steel shelf angle. Prefinished metal coping on treated wood blocking.
Roof: 60-mil fully adhered EPDM, 1/2" cover board, tapered polyiso (R-30 average) on 1 1/2" type B steel deck.
Brick expansion joints (EJ) at 25'-0" max o.c. and within 4'-0" of each outside corner (one face); CMU control joints
aligned with brick EJs where possible, max 24'-0" o.c.

## 6a. Roof Items (coordinate A-103, S-103, C-400)
* Roof drains RD-1 to RD-4 at (15, 36), (52.5, 36), (97.5, 36), (135, 36); overflow drains OD-1 to OD-4 2'-0" east of each.
  Tapered insulation slopes 1/4" per ft from grids A and D toward the drain line y = 36 with crickets between drains.
  Storm leaders exit the building below slab on the north side at x = 52.5 and x = 97.5 (two 8" laterals).
* Link roof: slopes to a scupper + conductor head + downspout on the link north parapet at x = -10.
* RTU-1 (45, 57), RTU-2 (105, 57), RTU-3 (105, 15): curbs 7'-0" (N-S) x 14'-0" (E-W), by Div. 23, structural frame by GC.
* Roof hatch 2'-6" x 3'-0" centered at (46.75, 27.0), above Custodial 210, with fixed ladder.
* Sanitary exits the south wall at x = 52 (6" PVC) toward Prairie Ave. Fire (6") and domestic (2") water enter Room 112 at x = 45 on the south wall.

## 7. Structure
Steel frame with ordinary reinforced masonry shear walls (stair, elevator, exterior CMU).
* Columns HSS 6x6x3/8 (grids A/D), HSS 6x6x1/2 (grids B/C), HSS 5x5x1/4 (link).
* Level 2: 3" 20 ga composite deck + 3 1/4" lightweight concrete (6 1/4" total). Infill W16x26 E-W at y = 10, 20, 52, 62.
  Girders on numbered grids: W24x55 (A-B, C-D spans), W12x19 (B-C). Beams on B, C: W18x35. Spandrels on A, D: W16x31.
  Openings framed at stairs (x = 12 and x = 138 lines W12x19) and elevator.
* Roof: K-series joists N-S @ 5'-0" o.c. (22K6 at 30' spans, 12K1 at corridor), on W18x35 (B, C) and W16x26 (A, D). W12x14 ties on numbered grids.
* Foundations: continuous footing 2'-6" x 1'-0" under EW-1, foundation wall 12" with 4" brick ledge, spread footings
  F1 7'-0"x7'-0"x1'-8" (B/C), F2 5'-0"x5'-0"x1'-4" (A/D, below continuous footing), thickened slab 2'-0"x1'-0" under L1 interior CMU.
  Slab on grade 5", 4,000 psi, WWF 6x6-W2.9xW2.9, 15-mil vapor retarder, 6" CA-6 base. Allowable soil bearing 3,000 psf.
* Elevator pit 5'-0" deep, 12" walls, 14" mat.

## 8. Site (civil coordinates use the same origin; feet)
* Property lines: west x = -420, east x = 255 (Maple Street west ROW), south y = -150 (Prairie Avenue north ROW), north y = 260.
* Existing school: 1-story, footprint x -320 to -36, y -60 to 120 (with a south entry canopy at x -200 to -170).
* Existing parking lot (78 stalls): x -300 to -70, y -135 to -80, two drives to Prairie Avenue (x -280 and x -95).
* Existing bus loop / drop-off along the south face of the existing building.
* Existing playground (to remain, protect): x 10 to 130, y 115 to 200.
* Existing utilities: 8" water main in Maple St., 12" storm sewer in Maple St., 8" sanitary in Prairie Ave.
* New services: 6" fire + 2" domestic from Maple St. to Room 112; 6" sanitary to the existing manhole in Prairie Ave.; roof drain storm to Maple St.

## 9. Owner Requirements (for proposal practice)
* School stays occupied. Student arrival 7:30-8:15 AM and dismissal 2:45-3:30 PM: no deliveries or crane picks.
* Tie-in to the existing building (demolition at the existing east wall and the link) only during summer recess (June 7 to August 13, 2027).
* Substantial Completion: August 6, 2027. Final Completion: August 20, 2027.
* Maintain fire department access to the existing building at all times.
