"""Write the agent-visible project files from project.py and method.py: the owner's design standard (docx),
the architect's room schedule (xlsx), the addenda (pdf), the contractor's load calculations (xlsx) and
transmittal (docx), the manufacturer's extended performance data (pdf) and the facilities office's records."""
import os, sys, datetime
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Font, Alignment, PatternFill
from docx import Document
from docx.shared import Pt
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project as P2
import project_base as P
import method as M
P.SPACES = P2.RECORD

CAT62 = {'office': 'Office space', 'conference': 'Conference/meeting', 'training': 'Classroom (age 9 plus)', 'corridor': 'Corridor', 'storage': 'Storage room', 'break': 'Break room', 'lab': 'Science laboratory', 'assembly': 'Multipurpose assembly'}
OWNER = "Tallgrass Community College District"
PROJECT = "Whitlock Hall renovation and addition, project 2025-114"
CONTRACTOR = "Ostrander Mechanical Design-Build"
ARCH = "Fenwick Lund Architects"
MFR = "Corvid Air Systems"


def xlsx_room_schedule(path):
    wb = Workbook()
    ws = wb.active; ws.title = "Room schedule"
    hdr = ["Room", "Name", "Level", "Area (m2)", "Occupants", "Use category", "Equipment (W)", "HVAC", "Remarks"]
    ws.append([f"{ARCH} - {PROJECT} - Room schedule, issue for construction 2026-03-06 (existing areas from the 2004 record drawings)"]); ws.append([])
    ws.append(hdr)
    for c in ws[3]: c.font = Font(bold=True)
    bold = Font(bold=True); strike = Font(strike=True, color="808080")
    for s in P.SPACES:
        hvac = "New RTU"
        rem = ""
        if s.get("shell"): hvac = "Shell - fit-out NIC"; rem = "Tenant fit-out by others under separate permit"
        row = [s["no"], s["name"], s["level"], s["area"], s["people"] if s["people"] is not None else "-",
               s["cat"] if s["cat"] else "-", s["equip"] if s["equip"] is not None else "-", hvac, rem]
        ws.append(row)
        r = ws.max_row
        if s["no"] == "160":
            ws.cell(r, 7).comment = Comment("Equipment load from the 2004 record drawings lab equipment schedule.", "M. Reyes")
    for col, w in zip("ABCDEFGHI", (8, 26, 7, 11, 11, 14, 14, 22, 36)):
        ws.column_dimensions[col].width = w
    ws2 = wb.create_sheet("Envelope")
    ws2.append(["Exterior walls and glazing by room (net wall area excludes glazing); roof area where the room is under the roof"])
    ws2.append([])
    ws2.append(["Room", "Wall N (m2)", "Wall E (m2)", "Wall S (m2)", "Wall W (m2)", "Glass N (m2)", "Glass E (m2)", "Glass S (m2)",
                "Glass W (m2)", "Roof (m2)", "Glazing type"])
    for c in ws2[3]: c.font = bold
    for s in P.SPACES:
        ws2.append([s["no"]] + [s["walls"].get(o, 0.0) for o in "NESW"] + [s["glass"].get(o, 0.0) for o in "NESW"] + [s["roof"], s["glz"]])
    ws2.append([]); ws2.append(["Glazing types: standard = double clear, SHGC 0.40; low-e = double low-e, SHGC 0.27 (addition and room 130)."])
    wb.save(path)


def pdf_text_pages(path, title, pages, mono=False):
    c = canvas.Canvas(path, pagesize=letter); W, H = letter
    for pi, lines in enumerate(pages):
        y = H - 54
        c.setFont("Helvetica-Bold", 11); c.drawString(54, y, title); y -= 20
        c.setFont("Courier" if mono else "Helvetica", 8 if mono else 10)
        for ln in lines:
            if ln.startswith("## "):
                c.setFont("Helvetica-Bold", 10); c.drawString(54, y, ln[3:]); c.setFont("Courier" if mono else "Helvetica", 8 if mono else 10); y -= 15
            else:
                c.drawString(54, y, ln); y -= 11 if mono else 13
        c.setFont("Helvetica", 8); c.drawString(54, 36, f"{title} - page {pi + 1} of {len(pages)}")
        c.showPage()
    c.save()


def pdf_addenda(path):
    a1 = ["## Addendum 1 - 2026-03-27",
          "To all bidders and the design-build mechanical contractor. This addendum forms part of the contract documents.",
          "",
          "1.1  Specification 08 71 00: Door hardware sets 3 and 7 revised; see attached schedule.",
          "1.2  Drawing A-501: Interior finish of corridor 119 changed to resilient tile.",
          "1.3  Drawing A-101: Courtyard paving pattern revised; no change to the building envelope.",
          "",
          "End of Addendum 1."]
    a2 = ["## Addendum 2 - 2026-04-03",
          "To all bidders and the design-build mechanical contractor. This addendum forms part of the contract documents.",
          "",
          "2.1  Specification 09 51 00: Acoustic ceiling tile product substitution accepted for rooms 210 to 233.",
          "2.2  Drawing E-201: Receptacle circuiting in Room 212 revised; no change in connected equipment load.",
          "2.3  Schedule: Bid date unchanged.",
          "",
          "End of Addendum 2."]
    pdf_text_pages(path, f"{ARCH} - {PROJECT} - Addenda", [a1, a2])


def pdf_catalog(path):
    notes = ["Notes",
             "1. TC = gross total capacity, SHC = gross sensible capacity, kW. Capacities are gross:",
             "   they include no deduction for indoor fan motor heat. Motor heat is listed with each",
             "   airflow, at 125 Pa external static pressure.",
             "2. SHC is based on 26.7 C entering dry bulb. At other entering dry bulb temperatures,",
             "   SHC = SHC(table) + 1.23 x (1 - BF) x airflow (L/s) x (EDB - 26.7) / 1000 kW,",
             "   with BF the coil bypass factor listed with each airflow.",
             "3. Where the corrected SHC exceeds TC, the coil is dry: use SHC = TC.",
             "4. Interpolation within the tables is permissible. Do not extrapolate.",
             "5. AHRI 340/360 rating conditions: 35.0 C outdoor, 26.7 C DB / 19.4 C WB entering,",
             "   rated airflow.",
             "6. Indoor fan arrangement: draw-through (fan downstream of the evaporator coil).",
             "7. kW (input) = compressor and outdoor fan power."]
    pages = [["## RTX series packaged rooftop units, cooling, extended performance (SI)",
              "Model  Nominal  Rated airflow  AHRI rated gross TC / SHC (kW)",
              "               (L/s)"]
             + ["%-6s %-8s %-14d %5.1f / %5.1f" % ((m, M.MODELS[m][0], M.ahri_rating(m)[2]) + M.ahri_rating(m)[:2]) for m in M.MODELS]
             + [""] + notes]
    for m in M.MODELS:
        tons, qr = M.MODELS[m][0], M.MODELS[m][1]
        lines = ["## Model %s, nominal %s tons, rated airflow %d L/s" % (m, tons, M.ahri_rating(m)[2])]
        for q in sorted(M.CATALOG[m]):
            d = M.CATALOG[m][q]
            lines += ["", "Airflow %d L/s, bypass factor BF %.3f, indoor fan motor heat %.2f kW" % (q, d["bf"], d["fan"]),
                      "ODB C | EWB 13.9 C: TC SHC kW | EWB 16.7 C: TC SHC kW | EWB 19.4 C: TC SHC kW | EWB 22.2 C: TC SHC kW"]
            for o in M.ODB_ROWS:
                lines.append("%5.1f | " % o + " | ".join("%17s" % ("%.1f %.1f %.2f" % (d["tc"][o][e], d["shc"][o][e], d["kw"][o][e])) for e in M.EWB_COLS))
        lines += ["", "See the notes on page 1."]
        pages.append(lines)
    pdf_text_pages(path, f"{MFR} - RTX series catalogue, extended cooling performance, 2025 edition", pages, mono=True)


def docx_standard(path):
    d = Document()
    st = d.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(10.5)
    d.add_heading(f"{OWNER}", level=1)
    d.add_heading("Facilities design standard 23 05 10 - HVAC cooling load and equipment sizing review", level=2)
    d.add_paragraph("Rev 4, issued 2025-09-15. Applies to all design-build and design-bid-build projects. The District "
                    "reviews a contractor's cooling load calculation and packaged equipment selection by recomputing "
                    "them with the methods and design data below and testing each selection against section 7.")
    d.add_heading("1. Design conditions and data", level=3)
    d.add_paragraph("Site: Chicago, station pressure %.1f kPa. Outdoor cooling design condition %.1f C dry bulb, %.1f C mean "
                    "coincident wet bulb (0.4%%). Indoor design condition %.1f C dry bulb, %d%% relative humidity. Psychrometric "
                    "properties per ASHRAE Handbook - Fundamentals, Chapter 1, at the station pressure. Sensible and latent "
                    "air-side loads use the standard-air relations of Chapter 18 (SI), without altitude correction. For the "
                    "load calculation the outdoor dry bulb follows Table 1 by hour and the outdoor humidity ratio stays at the "
                    "design value; loads are evaluated at the four hours of Table 1 only (solar time), with all spaces occupied "
                    "and lit at all four hours." % (M.P_STATION, M.T_OA_DESIGN, M.WB_OA_DESIGN, M.T_ROOM, int(M.RH_ROOM * 100)))
    t = d.add_table(rows=1, cols=5); t.style = "Table Grid"
    for i, h in enumerate(["Table 1 - hour", "10:00", "13:00", "15:00", "17:00"]): t.rows[0].cells[i].text = h
    r = t.add_row().cells; r[0].text = "Outdoor dry bulb (C)"
    for i, h in enumerate(P.HOURS): r[i + 1].text = "%.1f" % P.T_OUT[h]
    r = t.add_row().cells; r[0].text = "Roof CLTD (K)"
    for i, h in enumerate(P.HOURS): r[i + 1].text = "%.0f" % P.CLTD_ROOF[h]
    for o, nm in zip("NESW", ("north", "east", "south", "west")):
        r = t.add_row().cells; r[0].text = f"Wall CLTD, {nm} (K)"
        for i, h in enumerate(P.HOURS): r[i + 1].text = "%.0f" % P.CLTD_WALL[o][h]
    r = t.add_row().cells; r[0].text = "Glass conduction CLTD (K)"
    for i, h in enumerate(P.HOURS): r[i + 1].text = "%.1f" % (P.T_OUT[h] - M.T_ROOM)
    for o, nm in zip("NESW", ("north", "east", "south", "west")):
        r = t.add_row().cells; r[0].text = f"Solar cooling load, {nm} glass (W/m2 per unit SHGC)"
        for i, h in enumerate(P.HOURS): r[i + 1].text = "%.0f" % P.SCL[o][h]
    d.add_heading("2. Space loads", level=3)
    d.add_paragraph("Space sensible and latent loads by the CLTD/SCL/CLF method (ASHRAE Handbook - Fundamentals 1997, "
                    f"Chapter 28) with the District's factors in Tables 1 to 3. CLF = 1.0 for people, lighting and equipment "
                    f"(continuous occupancy through the design hours). Infiltration {P.INFIL} L/s per m2 of exterior wall and "
                    "glass. Occupants, equipment and areas from the room schedule as amended by the contract documents; "
                    "SHGC by glazing type from the room schedule. Interior partitions, floors over conditioned space and "
                    "doors are neglected.")
    t = d.add_table(rows=1, cols=7); t.style = "Table Grid"
    for i, h in enumerate(["Table 2 - use category", "ASHRAE 62.1 Table 6-1 occupancy category", "Sensible per person (W)",
                           "Latent per person (W)", "Lighting (W/m2)", "Rp (L/s per person)", "Ra (L/s per m2)"]): t.rows[0].cells[i].text = h
    for cat in P.LIGHTS:
        r = t.add_row().cells
        r[0].text = cat; r[1].text = CAT62[cat]; r[2].text = "%.0f" % P.PEOPLE[cat][0]; r[3].text = "%.0f" % P.PEOPLE[cat][1]
        r[4].text = "%.0f" % P.LIGHTS[cat]; r[5].text = "%.1f" % P.OA[cat][0]; r[6].text = "%.1f" % P.OA[cat][1]
    t = d.add_table(rows=1, cols=2); t.style = "Table Grid"
    t.rows[0].cells[0].text = "Table 3 - assembly"; t.rows[0].cells[1].text = "U (W/m2 K)"
    for nm, uv in (("Roof, R-20 (2004 record drawings, levels 1 and 2)", "0.25"), ("Roof, R-30 (re-roofed with added polyiso)", "0.18"),
                   ("Exterior wall, insulated block (all)", "0.45"), ("Glazing, double (standard or low-e)", "2.8")):
        r = t.add_row().cells; r[0].text = nm; r[1].text = uv
    d.add_heading("2.1 Inputs and the as-built condition", level=3)
    d.add_paragraph("The review is made on the building as it exists. Inputs are taken from the contract documents "
                    "(room schedule, envelope areas, addenda) unless field verification by the District's facilities "
                    "office shows a different area, assembly, glazing, occupancy (current furniture layout), equipment "
                    "(nameplate) or service arrangement, in which case the verified value is used. The contract "
                    "documents for an existing building are usually prepared from record drawings, which are not "
                    "updated for later work; the facilities office's records (work orders, asset inventory, user-group "
                    "minutes) indicate where the record may be out of date. Field verification is requested item by item "
                    "(a room, a roof level, an existing unit) and the office's capacity for a review is limited; the "
                    "reviewer decides which items to verify.")
    d.add_heading("3. Scope of each unit", level=3)
    d.add_paragraph("A unit's load includes every space the contractor's zoning assigns to it, except: spaces that the "
                    "contract documents or field verification show as served by existing equipment that remains in "
                    "service; spaces deleted from the project by addendum; and spaces described in 3.2.")
    d.add_paragraph("3.2 Shell and tenant spaces. A space without an issued fit-out (occupancy, lighting and "
                    "equipment not fixed by the contract documents) shall not be assigned assumed loads. The unit "
                    "serving such a space is reported as undetermined, naming the missing information; the District "
                    "will issue the fit-out loads and the selection is reviewed when they are available. Other units "
                    "are reviewed normally.")
    d.add_heading("4. Ventilation", level=3)
    d.add_paragraph("Outdoor air by the Ventilation Rate Procedure of ANSI/ASHRAE Standard 62.1-2019. Each new unit "
                    "serves a multiple-zone recirculating system in which each room in its scope is a ventilation zone. "
                    "Breathing-zone rates from Table 2, occupant diversity D = 1.0, zone air distribution effectiveness "
                    "from Table 6-4 for ceiling supply of cool air with ceiling return. System ventilation efficiency by "
                    "Normative Appendix A, with each zone's scheduled supply airflow in the submittal as its primary "
                    "airflow and the unit's scheduled supply airflow as the system primary airflow.")
    d.add_heading("5. Block load", level=3)
    d.add_paragraph("A unit's load at each hour of Table 1 is the sum of its spaces' loads plus the load of its outdoor "
                    "air intake flow brought from the outdoor condition of that hour to the indoor design condition. The "
                    "design block load is the hour with the largest total; its sensible and latent parts are taken at that "
                    "same hour. Space loads are not taken at each space's own peak hour.")
    d.add_heading("6. Equipment capacity", level=3)
    d.add_paragraph("Capacity is taken from the manufacturer's published performance data, applying its notes, at the "
                    "unit's scheduled supply airflow, the outdoor design dry bulb, and the coil entering condition: the "
                    "mixture of the outdoor air intake flow at the outdoor design condition with return air at the indoor "
                    "design condition. The capacity credited is the net capacity delivered to the supply air, total and "
                    "sensible; the net latent capacity is their difference. No safety factor is applied to loads or capacities.")
    d.add_heading("7. Acceptance of a selection", level=3)
    d.add_paragraph(f"A selection is acceptable when the net total capacity is between {P.BAND[0]:.2f} and {P.BAND[1]:.2f} "
                    "times the design block load, the net sensible capacity is at least the design sensible load and the "
                    "net latent capacity is at least the design latent load. A selection short on any of these is rejected "
                    "as undersized; one above the upper limit (and not short on any) is rejected as oversized. A submittal "
                    "is approved only when every unit is acceptable; otherwise it is returned for revision.")
    sec = d.sections[0]
    sec.footer.paragraphs[0].text = ("23 05 10 Rev 4 (2025-09-15). Rev 3 (2023-02) superseded. Document control: "
                                     "Facilities Engineering.")
    d.save(path)


def xlsx_contractor(path):
    bold = Font(bold=True)
    C = P2.contractor()
    wb = Workbook(); ws = wb.active; ws.title = "Design conditions"
    ws.append([f"{CONTRACTOR} - {PROJECT} - Cooling load calculations and RTU selection, submittal 23 74 13-01, 2026-04-10"])
    ws.append([])
    ws.append(["Method", "Owner standard 23 05 10 Rev 4: CLTD/SCL/CLF with the District's Tables 1-3; block load at the Table 1 hours"])
    ws.append(["Outdoor design", "%.1f C DB / %.1f C MCWB (0.4%%); Table 1 dry bulb by hour, design humidity ratio" % (M.T_OA_DESIGN, M.WB_OA_DESIGN)])
    ws.append(["Indoor design", "%.1f C DB, %d%% RH" % (M.T_ROOM, int(M.RH_ROOM * 100))])
    ws.append(["Site", "Chicago, %.1f kPa" % M.P_STATION])
    ws.append(["U-values (W/m2 K)", f"wall {P.U_WALL}, roof {P.U_ROOF} (R-20 record assembly), glass {P.U_GLASS}"])
    ws.append(["Glazing", "standard SHGC 0.40; low-e SHGC 0.27 (addition, room 130)"])
    ws.append(["Infiltration", f"{P.INFIL} L/s per m2 exterior wall + glass"])
    ws.append(["Ventilation", "ASHRAE 62.1-2019 Ventilation Rate Procedure, Table 6-1 rates per Table 2; unit outdoor air = sum of the zone outdoor airflows (D = 1.0)"])
    ws.append(["Supply air", "Zone airflows for each room's peak sensible load at 13.0 C supply, minimum 2.0 L/s per m2; unit airflow = sum of the zones, adjusted to the model's catalogue range"])
    ws.append(["Capacity basis", f"{MFR} RTX catalogue 2025, AHRI 340/360 rated capacity (35.0 C outdoor, 26.7/19.4 C entering, rated airflow)"])
    ws.append(["Acceptance", "Rated total capacity 1.00-1.25 x block total load and rated sensible capacity above the block sensible load"])
    ws.append(["Source documents", "Room schedule and envelope areas IFC 2026-03-06 (existing areas per 2004 record drawings); addenda 1 and 2"])
    ws.column_dimensions["A"].width = 20; ws.column_dimensions["B"].width = 110
    ws = wb.create_sheet("Spaces")
    ws.append(["Room", "Name", "Unit", "Area (m2)", "Occupants", "Category", "Equipment (W)", "Zone outdoor air (L/s)",
               "Sensible 10:00 (W)", "Sensible 13:00 (W)", "Sensible 15:00 (W)", "Sensible 17:00 (W)", "Latent (W)",
               "Scheduled supply airflow (L/s)"])
    for cc in ws[1]: cc.font = bold
    for u in P2.UNITS:
        for no in C[u]["spaces"]:
            x = P2.contractor_space(no)
            oa = P.OA[x["cat"]][0] * x["people"] + P.OA[x["cat"]][1] * x["area"]
            ws.append([x["no"], x["name"], u, x["area"], x["people"], x["cat"], x["equip"], round(oa, 1)]
                      + [round(P2.space_loads(x, h)[0]) for h in P2.HOURS] + [round(P2.space_loads(x, P2.HOURS[0])[1]),
                      C[u]["zone_airflow"][no]])
    for col, w in zip("ABCDEFGHIJKLMN", (8, 26, 8, 10, 10, 12, 13, 15, 16, 16, 16, 16, 11, 18)):
        ws.column_dimensions[col].width = w
    ws = wb.create_sheet("Units")
    ws.append(["Unit", "Spaces served", "Scheduled supply airflow (L/s)", "Outdoor air (L/s)", "Total 10:00 (kW)", "Total 13:00 (kW)",
               "Total 15:00 (kW)", "Total 17:00 (kW)", "Design hour", "Block total (kW)", "Block sensible (kW)", "Block latent (kW)",
               "Selected model", "Rated total (kW)", "Rated sensible (kW)", "Rated total / block", "Remarks"])
    for cc in ws[1]: cc.font = bold
    for u in P2.UNITS:
        c = C[u]
        sp = [P2.contractor_space(no) for no in c["spaces"]]
        hourly = {}
        for h in P2.HOURS:
            S = sum(P2.space_loads(x, h)[0] for x in sp) + M.CP_AIR * c["oa"] * (P2.T_OUT[h] - M.T_ROOM)
            L = sum(P2.space_loads(x, h)[1] for x in sp) + M.CL_AIR * c["oa"] * (M.W_OA - M.W_ROOM)
            hourly[h] = (S, L)
        rem = "Room 130 loads assumed (office, 26 occupants, 3000 W) pending tenant fit-out" if u == "RTU-5" else ""
        ws.append([u, ", ".join(c["spaces"]), c["airflow"], round(c["oa"], 1)] + [round(sum(hourly[h]) / 1000, 2) for h in P2.HOURS]
                  + [f"{c['hour']}:00", round(c["total"], 2), round(c["sens"], 2), round(c["lat"], 2), c["model"], c["rated_total"],
                     c["rated_sens"], round(c["ratio"], 3), rem])
    ws.append([]); ws.append(["All selections within 1.00-1.25 of the design block load with rated sensible capacity above the sensible load."])
    for col, w in zip("ABCDEFGHIJKLMNOPQ", (8, 40, 16, 14, 14, 14, 14, 14, 11, 14, 16, 14, 14, 14, 16, 16, 60)):
        ws.column_dimensions[col].width = w
    wb.save(path)


def docx_transmittal(path):
    d = Document()
    st = d.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(10.5)
    d.add_paragraph(f"{CONTRACTOR}\n2026-04-10")
    d.add_paragraph(f"To: Facilities Engineering, {OWNER}\nRe: {PROJECT} - Submittal 23 74 13-01, packaged rooftop units, "
                    "cooling load calculations and selections")
    d.add_paragraph("Please find attached the cooling load calculations (hvac_load_calcs.xlsx) for the seven new packaged "
                    "rooftop units and the proposed selections from the Corvid RTX series. Loads were calculated with the "
                    "District's standard 23 05 10 using the room schedule issued for construction on 2026-03-06 and the "
                    "envelope areas from the architect's schedule; outdoor air follows ASHRAE 62.1-2019. Each unit's "
                    "AHRI-rated capacity falls within the standard's acceptance band, and the supply airflows and air "
                    "balance schedule are listed on the Spaces sheet.")
    d.add_paragraph("Room 130 is a shell space for a future tenant. In the absence of fit-out information we have "
                    "carried an office occupancy of 26 persons and 3000 W of equipment so that RTU-5 can be released "
                    "for procurement with the other units.")
    d.add_paragraph("Existing-building inputs (areas, glazing, occupancy, equipment) are taken from the room schedule "
                    "issued for construction, which the architect prepared from the 2004 record drawings. The Corvid RTX "
                    "extended performance data are attached (rtx_catalog_performance.pdf). Please return comments within "
                    "ten working days.")
    d.add_paragraph("D. Haverford, PE\nProject engineer")
    d.save(path)


def csv_work_orders(path):
    import csv, random
    rnd = random.Random(2026)
    trades = ["plumbing", "electrical", "HVAC", "carpentry", "roofing", "glazing", "painting", "locks", "lighting"]
    noise = ["Replace lavatory faucet cartridge", "Reset tripped breaker, panel LP-%d" , "Replace filters, unit %s", "Adjust door closer",
             "Patch and paint wall", "Replace ceiling tiles (water stain)", "Rekey office lock", "Replace exit sign battery",
             "Clear condensate drain, unit %s", "Replace thermostat batteries", "Repair blind", "Replace lamp, corridor fixture",
             "Tighten loose handrail", "Clean roof drains", "Replace damaged floor tile", "Re-hang whiteboard", "Replace smoke detector head",
             "Repair window latch", "Replace broken chair", "Seal roof penetration at vent"]
    rooms = [str(x) for x in (101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 112, 114, 116, 118, 119, 120, 121, 122, 123, 124, 125,
                              201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 212, 214, 215, 220, 221, 222, 223, 225, 230, 231, 232, 233,
                              240, 241, 242, 142, 143, 144, 145, 146, 160, 161, 162, 163, 170, 171)]
    rows = []
    special = {
        ("2019", 412): ("118", "HVAC", "Install 5-ton ductless split system (tag AC-1) to serve server room 118, 24/7 cooling; condenser on grade at east wall. Commissioned 2019-08-30.", "closed"),
        ("2022", 51): ("110", "lighting", "LED retrofit of level 1 offices and corridors (rooms 110-119, 142-146): replace fluorescent troffers with LED, same layout.", "closed"),
        ("2024", 77): ("161", "HVAC", "Install ductless fume hood in lab prep 161 (recirculating, no exhaust connection).", "closed"),
        ("2018", 290): ("160", "plumbing", "Replace emergency eyewash in teaching lab 160.", "closed"),
    }
    for n, room in enumerate(P2.REFURNISHED):
        special[("2019", 500 + n)] = (room, "furniture", "Reorganisation plan RO-2019: deliver and install new workstations and seating, room %s; remove existing furniture." % room, "closed")
    for yr in range(2017, 2026):
        for k in range(1, 46):
            wo = "WO-%s-%04d" % (yr, k * 9 + (yr % 7))
            date = "%s-%02d-%02d" % (yr, rnd.randint(1, 12), rnd.randint(1, 28))
            room = rnd.choice(rooms); trade = rnd.choice(trades); d = rnd.choice(noise)
            if "%d" in d: d = d % rnd.randint(1, 6)
            if "%s" in d: d = d % rnd.choice(["RTU-A", "RTU-B", "AHU-2", "EF-3"])
            rows.append([wo, date, "Whitlock Hall", room, trade, d, "closed"])
    dates = {("2019", 412): "2019-07-22", ("2022", 51): "2022-02-14", ("2024", 77): "2024-03-11", ("2018", 290): "2018-09-04"}
    for n in range(len(P2.REFURNISHED)):
        dates[("2019", 500 + n)] = "2019-%02d-%02d" % (5 + n // 8, 3 + (n * 3) % 26)
    ids = {"WO-%s-%04d" % (yr, k) for (yr, k) in special}
    rows = [r for r in rows if r[0] not in ids]
    for (yr, k), (room, trade, desc, status) in special.items():
        rows.append(["WO-%s-%04d" % (yr, k), dates[(yr, k)], "Whitlock Hall", room, trade, desc, status])
    rows.sort(key=lambda r: r[1])
    with open(path, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["wo_id", "date", "building", "room", "trade", "description", "status"]); w.writerows(rows)


def xlsx_assets(path):
    import random
    rnd = random.Random(7)
    wb = Workbook(); ws = wb.active; ws.title = "Assets"
    ws.append(["Asset tag", "Description", "Building", "Room", "Category", "Installed", "Power (W)", "Status"])
    for c in ws[1]: c.font = Font(bold=True)
    rooms = [str(x) for x in (101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 112, 114, 116, 118, 119, 120, 121, 122, 123, 124, 125,
                              201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 212, 214, 215, 220, 221, 222, 223, 225, 230, 231, 232, 233,
                              240, 241, 242, 142, 143, 144, 145, 146, 160, 161, 162, 163, 170, 171)]
    kinds = [("Desktop computer", "IT", (120, 180)), ("Monitor 24 in", "IT", (25, 40)), ("Laser printer", "IT", (300, 600)),
             ("Projector", "AV", (250, 350)),
             ("Display 65 in", "AV", (120, 160)), ("Refrigerator, under-counter", "appliance", (90, 120)), ("Microwave", "appliance", (1000, 1200)),
             ("Fire extinguisher", "safety", (0, 0)), ("Water cooler", "appliance", (80, 110))]
    rows = []
    for i in range(520):
        k = rnd.choice(kinds); room = rnd.choice(rooms)
        rows.append(["WH-%05d" % (10000 + i), k[0], "Whitlock Hall", room, k[1], "%d-%02d" % (rnd.randint(2015, 2025), rnd.randint(1, 12)),
                     rnd.randint(*k[2]) if k[2][1] else 0, "in service"])
    rows += [["WH-10904", "Benchtop instruments, programme expansion (various)", "Whitlock Hall", "160", "lab equipment", "2022-08", None, "in service"],
             ["WH-10905", "Benchtop instruments, programme expansion (various)", "Whitlock Hall", "161", "lab equipment", "2022-08", None, "in service"],
             ["WH-10611", "Ductless split system 5 ton, AC-1 (serves server room)", "Whitlock Hall", "118", "HVAC", "2019-08", 0, "in service"],
             ["WH-10612", "Ductless fume hood, recirculating", "Whitlock Hall", "161", "lab equipment", "2024-03", 400, "in service"]]
    rnd.shuffle(rows)
    for r in rows: ws.append(r)
    for col, w in zip("ABCDEFGH", (11, 44, 14, 8, 14, 11, 10, 14)): ws.column_dimensions[col].width = w
    wb.save(path)


def docx_minutes(path):
    d = Document()
    st = d.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(10.5)
    d.add_heading(f"{OWNER} - Whitlock Hall user group - meeting minutes 2024-2026", level=2)
    meetings = [
        ("2024-09-12", ["Project kickoff for the renovation and addition. Architect presented the program.",
                        "IT asked that the server room keep its own cooling; facilities confirmed the 2019 split system stays.",
                        "Parking during construction to be addressed with campus safety."]),
        ("2024-11-14", ["Facilities reminded the group that the 2019 reorganisation refurnished a number of rooms across the building "
                        "with new workstations and seating (the furniture work orders list them); the new layouts followed the furniture "
                        "planner's room-size standards and headcounts rose where the new furniture went. The 2004 record drawings do not "
                        "reflect any of this.",
                        "Signage package reviewed; no comments."]),
        ("2025-02-06", ["Teaching lab 160 and lab prep 161: the 2022 programme expansion added benchtop instruments; the department "
                        "could not say what they draw and asked that it be checked in the field.",
                        "Corridor finishes selected."]),
        ("2025-06-19", ["Schedule: bid documents expected March 2026.",
                        "Facilities asked that the record drawings be used with caution for existing areas; several rooms have changed since 2004.",
                        "Conference 144 to receive a video wall at a later phase; not in this project."]),
    ]
    for date, items in meetings:
        d.add_heading(f"Meeting of {date}", level=3)
        for it in items: d.add_paragraph(it, style="List Bullet")
    d.save(path)


def main(out):
    for sub in ("owner", "architect", "contractor", "manufacturer"):
        os.makedirs(os.path.join(out, sub), exist_ok=True)
    docx_standard(os.path.join(out, "owner", "design_standard_23_05_10.docx"))
    xlsx_room_schedule(os.path.join(out, "architect", "room_schedule.xlsx"))
    pdf_addenda(os.path.join(out, "architect", "addenda.pdf"))
    xlsx_contractor(os.path.join(out, "contractor", "hvac_load_calcs.xlsx"))
    docx_transmittal(os.path.join(out, "contractor", "transmittal.docx"))
    pdf_catalog(os.path.join(out, "manufacturer", "rtx_catalog_performance.pdf"))
    os.makedirs(os.path.join(out, "facilities"), exist_ok=True)
    csv_work_orders(os.path.join(out, "facilities", "work_orders_2017_2025.csv"))
    xlsx_assets(os.path.join(out, "facilities", "asset_inventory.xlsx"))
    docx_minutes(os.path.join(out, "facilities", "user_group_minutes.docx"))



if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "environment", "data"))
