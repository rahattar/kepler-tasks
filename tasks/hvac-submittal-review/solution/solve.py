"""Reference review, from the agent-visible documents only. Reads the standard's design data and tables, the
room schedule and envelope, the contractor's zoning, scheduled airflows and selections, and the manufacturer's
extended performance tables; mines the facilities records for where the record is stale; buys a verification
campaign (the lab rooms and one room per refurnished class); then reviews each unit: ASHRAE 62.1-2019 Appendix A
outdoor air, block load at the Table 1 hours, coil entering condition from adiabatic mixing at the station
pressure, catalogue capacity interpolated at the scheduled airflow, entering wet bulb and outdoor dry bulb, with
the entering-dry-bulb correction and fan heat, and the section 7 verdict. Writes OUT (default /app/review.json)."""
import csv, json, math, os, re, subprocess, urllib.request
from collections import defaultdict
import openpyxl
from docx import Document

DATA = os.environ.get("DATA", "/app/data")
OUT = os.environ.get("OUT", "/app/review.json")
URL = os.environ.get("VERIFY_URL", "http://127.0.0.1:8000").rstrip("/")


def get(path):
    with urllib.request.urlopen(URL + path, timeout=60) as r:
        return json.loads(r.read().decode())


# ---------------------------------------------------------------- psychrometrics (Fundamentals Ch. 1)
def pws(t):
    T = t + 273.15
    return math.exp(-5.8002206e3 / T + 1.3914993 - 4.8640239e-2 * T + 4.1764768e-5 * T * T - 1.4452093e-8 * T ** 3
                    + 6.5459673 * math.log(T)) / 1000.0


def w_pw(pw, p): return 0.621945 * pw / (p - pw)
def w_wb(t, wb, p):
    ws = w_pw(pws(wb), p)
    return ((2501.0 - 2.326 * wb) * ws - 1.006 * (t - wb)) / (2501.0 + 1.86 * t - 4.186 * wb)
def wb_w(t, w, p):
    lo, hi = -10.0, t
    for _ in range(80):
        m = 0.5 * (lo + hi)
        if w_wb(t, m, p) > w: hi = m
        else: lo = m
    return 0.5 * (lo + hi)
def h_tw(t, w): return 1.006 * t + w * (2501.0 + 1.86 * t)
def v_tw(t, w, p): return 0.287042 * (t + 273.15) * (1 + 1.607858 * w) / p


# ---------------------------------------------------------------- documents
def read_standard():
    d = Document(os.path.join(DATA, "owner", "design_standard_23_05_10.docx"))
    text = "\n".join(p.text for p in d.paragraphs)
    S = {}
    S["p"] = float(re.search(r"station pressure ([\d.]+) kPa", text).group(1))
    m = re.search(r"([\d.]+) C dry bulb, ([\d.]+) C mean coincident wet bulb", text); S["to"], S["wbo"] = float(m.group(1)), float(m.group(2))
    m = re.search(r"Indoor design condition ([\d.]+) C dry bulb, (\d+)% relative humidity", text); S["ti"], S["rhi"] = float(m.group(1)), float(m.group(2)) / 100
    S["infil"] = float(re.search(r"Infiltration ([\d.]+) L/s per m2", text).group(1))
    S["band"] = tuple(float(x) for x in re.search(r"between ([\d.]+) and ([\d.]+) times", text).groups())
    t1, t2, t3 = d.tables[:3]
    rows = {r.cells[0].text: [c.text for c in r.cells[1:]] for r in t1.rows}
    hours = [int(h.split(":")[0]) for h in rows["Table 1 - hour"]]
    num = lambda k: dict(zip(hours, [float(x) for x in rows[k]]))
    S["hours"] = hours; S["tout"] = num("Outdoor dry bulb (C)"); S["roof"] = num("Roof CLTD (K)"); S["glassc"] = num("Glass conduction CLTD (K)")
    S["wall"] = {o: num(f"Wall CLTD, {n} (K)") for o, n in zip("NESW", ("north", "east", "south", "west"))}
    S["scl"] = {o: num(f"Solar cooling load, {n} glass (W/m2 per unit SHGC)") for o, n in zip("NESW", ("north", "east", "south", "west"))}
    S["cat"] = {}
    for r in t2.rows[1:]:
        c = [x.text for x in r.cells]
        S["cat"][c[0]] = dict(ps=float(c[2]), pl=float(c[3]), lpd=float(c[4]), rp=float(c[5]), ra=float(c[6]))
    S["u"] = {r.cells[0].text: float(r.cells[1].text) for r in t3.rows[1:]}
    S["u_wall"] = next(v for k, v in S["u"].items() if k.startswith("Exterior wall"))
    S["u_glass"] = next(v for k, v in S["u"].items() if k.startswith("Glazing"))
    S["u_roof20"] = next(v for k, v in S["u"].items() if "R-20" in k)
    S["u_roof30"] = next(v for k, v in S["u"].items() if "R-30" in k)
    S["wi"] = w_pw(S["rhi"] * pws(S["ti"]), S["p"]); S["wo"] = w_wb(S["to"], S["wbo"], S["p"])
    return S


def read_rooms():
    wb = openpyxl.load_workbook(os.path.join(DATA, "architect", "room_schedule.xlsx"), data_only=True)
    ws = wb["Room schedule"]; rooms = {}
    for r in ws.iter_rows(min_row=4, values_only=True):
        if not r[0]: continue
        no = str(r[0])
        rooms[no] = dict(no=no, name=r[1], level=int(r[2]), area=float(r[3]), people=None if r[4] in ("-", None) else int(r[4]),
                         cat=None if r[5] in ("-", None) else r[5], equip=None if r[6] in ("-", None) else float(r[6]),
                         shell=("Shell" in (r[7] or "")), roof_u="R-20")
    ws = wb["Envelope"]
    for r in ws.iter_rows(min_row=4, values_only=True):
        if not r[0] or str(r[0]) not in rooms: continue
        s = rooms[str(r[0])]
        s["walls"] = {o: float(r[i]) for o, i in zip("NESW", (1, 2, 3, 4)) if r[i]}
        s["glass"] = {o: float(r[i]) for o, i in zip("NESW", (5, 6, 7, 8)) if r[i]}
        s["roof"] = float(r[9]); s["glz"] = r[10]
    return rooms


def read_submittal():
    wb = openpyxl.load_workbook(os.path.join(DATA, "contractor", "hvac_load_calcs.xlsx"), data_only=True)
    units = {}
    for r in wb["Units"].iter_rows(min_row=2, values_only=True):
        if r[0] and str(r[0]).startswith("RTU"):
            units[r[0]] = dict(spaces=[x.strip() for x in str(r[1]).split(",")], airflow=float(r[2]), model=r[12])
    zq = {}
    for r in wb["Spaces"].iter_rows(min_row=2, values_only=True):
        if r[0]: zq[str(r[0])] = float(r[13])
    return units, zq


def read_catalog():
    txt = subprocess.run(["pdftotext", "-layout", os.path.join(DATA, "manufacturer", "rtx_catalog_performance.pdf"), "-"],
                         capture_output=True, text=True).stdout
    cat, model, q = {}, None, None
    for ln in txt.splitlines():
        m = re.search(r"Model (RTX-\d+), nominal", ln)
        if m: model = m.group(1); cat[model] = {}; continue
        m = re.search(r"Airflow (\d+) L/s, bypass factor BF ([\d.]+), indoor fan motor heat ([\d.]+) kW", ln)
        if m and model:
            q = int(m.group(1)); cat[model][q] = dict(bf=float(m.group(2)), fan=float(m.group(3)), rows={}); continue
        m = re.match(r"\s*([\d.]+)\s*\|(.*)", ln)
        if m and model and q is not None:
            cells = [c.split() for c in m.group(2).split("|")]
            if len(cells) == 4 and all(len(c) == 3 for c in cells):
                cat[model][q]["rows"][float(m.group(1))] = [(float(c[0]), float(c[1])) for c in cells]
    return cat


EWB_COLS = [13.9, 16.7, 19.4, 22.2]


def lin(x, xs, ys):
    for i in range(len(xs) - 1):
        if xs[i] - 1e-9 <= x <= xs[i + 1] + 1e-9:
            r = (x - xs[i]) / (xs[i + 1] - xs[i]); return ys[i] + r * (ys[i + 1] - ys[i])
    raise ValueError("extrapolation: %s outside %s" % (x, xs))


def capacity(cat, model, airflow, ewb, edb, odb):
    tab = cat[model]; qs = sorted(tab); vals = []
    for q in qs:
        rows = tab[q]["rows"]; odbs = sorted(rows)
        tc = lin(odb, odbs, [lin(ewb, EWB_COLS, [c[0] for c in rows[o]]) for o in odbs])
        sc = lin(odb, odbs, [lin(ewb, EWB_COLS, [c[1] for c in rows[o]]) for o in odbs])
        vals.append((tc, sc, tab[q]["bf"], tab[q]["fan"]))
    tc, sc, bf, fan = (lin(airflow, qs, [v[i] for v in vals]) for i in range(4))
    sc = min(sc + 1.23 * (1 - bf) * airflow * (edb - 26.7) / 1000.0, tc)
    return tc - fan, sc - fan


# ---------------------------------------------------------------- loads
def space_loads(S, s, h):
    u_roof = S["u_roof30"] if s.get("roof_u") == "R-30" else S["u_roof20"]
    sens = u_roof * s["roof"] * S["roof"][h]
    for o, a in s["walls"].items(): sens += S["u_wall"] * a * S["wall"][o][h]
    ag = sum(s["glass"].values())
    sens += S["u_glass"] * ag * S["glassc"][h]
    for o, a in s["glass"].items(): sens += a * (0.40 if s["glz"] == "standard" else 0.27) * S["scl"][o][h]
    c = S["cat"][s["cat"]]
    sens += s["people"] * c["ps"] + c["lpd"] * s["area"] + s["equip"]
    lat = s["people"] * c["pl"]
    v = S["infil"] * (sum(s["walls"].values()) + ag)
    sens += 1.23 * v * (S["tout"][h] - S["ti"]); lat += 3010.0 * v * (S["wo"] - S["wi"])
    return sens, lat


def review_unit(S, cat, spaces, zq, airflow, model):
    vbz = [S["cat"][s["cat"]]["rp"] * s["people"] + S["cat"][s["cat"]]["ra"] * s["area"] for s in spaces]
    vou = sum(vbz); xs = vou / airflow
    ev = min(1 + xs - v / zq[s["no"]] for v, s in zip(vbz, spaces))
    vot = vou / ev
    best = None
    for h in S["hours"]:
        T = L = 0.0
        for s in spaces:
            a, b = space_loads(S, s, h); T += a; L += b
        T += 1.23 * vot * (S["tout"][h] - S["ti"]); L += 3010.0 * vot * (S["wo"] - S["wi"])
        if best is None or T + L > best[0]: best = (T + L, T, L)
    tot, sen, lat = best[0] / 1000, best[1] / 1000, best[2] / 1000
    mo = vot / v_tw(S["to"], S["wo"], S["p"]); mr = (airflow - vot) / v_tw(S["ti"], S["wi"], S["p"]); x = mo / (mo + mr)
    w = x * S["wo"] + (1 - x) * S["wi"]; hm = x * h_tw(S["to"], S["wo"]) + (1 - x) * h_tw(S["ti"], S["wi"])
    tm = (hm - 2501.0 * w) / (1.006 + 1.86 * w); wbm = wb_w(tm, w, S["p"])
    ct, cs = capacity(cat, model, airflow, wbm, tm, S["to"])
    cl = ct - cs
    lo, hi = S["band"]
    v = "reject_undersized" if (ct / tot < lo or cs < sen or cl < lat) else ("reject_oversized" if ct / tot > hi else "accept")
    return dict(verdict=v, outdoor_air_l_s=round(vot, 1), coil_entering_wb_c=round(wbm, 2), block_total_kw=round(tot, 2),
                block_sensible_kw=round(sen, 2), block_latent_kw=round(lat, 2), net_capacity_total_kw=round(ct, 2),
                net_capacity_sensible_kw=round(cs, 2), net_capacity_latent_kw=round(cl, 2))


# ---------------------------------------------------------------- the facilities records and the campaign
def mine_records(rooms):
    refurnished, served = set(), {}
    for r in csv.DictReader(open(os.path.join(DATA, "facilities", "work_orders_2017_2025.csv"))):
        if "RO-2019" in r["description"] and r["room"] in rooms: refurnished.add(r["room"])
        m = re.search(r"tag (AC-\d+)\) to serve server room (\d+)", r["description"])
        if m: served[m.group(2)] = m.group(1)
    text = "\n".join(p.text for p in Document(os.path.join(DATA, "facilities", "user_group_minutes.docx")).paragraphs)
    lab = set(re.findall(r"lab (\d{3})", text, flags=re.I)) | set(re.findall(r"prep (\d{3})", text, flags=re.I))
    return refurnished, served, lab & set(rooms)


def main():
    S = read_standard(); rooms = read_rooms(); units, zq = read_submittal(); cat = read_catalog()
    refurnished, served, lab = mine_records(rooms)
    budget = get("/status")["verifications_remaining"]
    band = lambda s: "small" if s["area"] <= 15 else "single" if s["area"] <= 20 else "mid" if s["area"] <= 50 else "open"
    classes = defaultdict(list)
    for no in sorted(refurnished): classes[(rooms[no]["cat"], band(rooms[no]))].append(no)
    plan = (sorted(lab) + [max(v, key=lambda n: rooms[n]["area"]) for k, v in sorted(classes.items())])[:budget]
    verified = {no: get(f"/verify?item=room:{no}") for no in plan}
    asb = {}
    for no, s in rooms.items():
        a = dict(s)
        if no in verified:
            v = verified[no]
            a.update(people=v["occupants_current_layout"], equip=v["equipment_nameplate_w"], area=v["area_m2"], walls=v["exterior_walls_m2"],
                     glass=v["glazing_m2"], glz=v["glazing_type"], roof=v["roof_m2"], roof_u="R-30" if "R-30" in v["roof_assembly"] else "R-20")
            if not v["served_by"].startswith("new"): a["served_by"] = v["served_by"]
        elif no in refurnished:
            twins = [t for t in classes[(s["cat"], band(s))] if t in verified]
            if twins:
                t = twins[0]; v = verified[t]; rt = rooms[t]
                if rt["area"] == s["area"] and rt["cat"] == s["cat"]:
                    a.update(people=v["occupants_current_layout"], equip=v["equipment_nameplate_w"])
                elif s["cat"] == "conference":
                    a.update(people=int(round(s["people"] * v["occupants_current_layout"] / max(rt["people"], 1))),
                             equip=s["equip"] + (v["equipment_nameplate_w"] - rt["equip"]))
                else:
                    a.update(people=int(round(s["people"] * v["occupants_current_layout"] / max(rt["people"], 1))),
                             equip=int(round(s["equip"] * v["equipment_nameplate_w"] / max(rt["equip"], 1))))
        if no in served and no not in verified: a["served_by"] = served[no]
        asb[no] = a
    out = {"units": {}}
    for u, info in units.items():
        sp = [asb[n] for n in info["spaces"] if n in asb]
        if any(s["shell"] for s in sp):
            out["units"][u] = dict(verdict="undetermined", missing="tenant_fitout_loads"); continue
        sp = [s for s in sp if not s.get("served_by")]
        out["units"][u] = review_unit(S, cat, sp, zq, info["airflow"], info["model"])
    out["submittal"] = "approve" if all(x["verdict"] == "accept" for x in out["units"].values()) else "return_for_revision"
    json.dump(out, open(OUT, "w"), indent=1)
    print("verified:", plan)


if __name__ == "__main__":
    main()
