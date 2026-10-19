"""Household inventory reconciliation. No printer commands or credential access.

One receipt per print_log row, committed atomically with native usage and stock.
3MF totals are estimates, not measured weight. Unknowns are never zero-filled.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import logging
import math
import re
import shutil
import sqlite3
import time
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

LOG = logging.getLogger(__name__)
MODEL_FEATURES = {"Outer wall", "Inner wall", "Overhang wall", "Sparse infill",
    "Internal solid infill", "Top surface", "Bottom surface", "Bridge",
    "Internal bridge", "Gap infill", "Floating vertical shell"}
WASTE_FEATURES = {"Support", "Support interface", "Prime tower", "Skirt", "Brim",
                  "Skirt/Brim", "Wipe tower"}
SCHEMA = """
CREATE TABLE IF NOT EXISTS home_material_sources(
 archive_id INTEGER PRIMARY KEY, sha256 TEXT, slots_json TEXT NOT NULL,
 evidence TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS home_material_runs(
 run_id INTEGER PRIMARY KEY, archive_id INTEGER, state TEXT NOT NULL,
 detail TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS home_material_measurements(
 run_id INTEGER PRIMARY KEY, waste_g REAL NOT NULL, note TEXT NOT NULL,
 actor TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS home_material_audit(
 id INTEGER PRIMARY KEY, action TEXT NOT NULL, detail TEXT NOT NULL,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS home_material_health(
 id INTEGER PRIMARY KEY CHECK(id=1), checked_at TEXT, error TEXT);
"""

def connect(data: Path):
    c = sqlite3.connect(data / "bambuddy.db", timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    c.executescript(SCHEMA)
    return c

def slice_info(path: Path, plate_id=1):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("Metadata/slice_info.config"))
        plates = root.findall("plate")
        plate = next((p for p in plates if any(m.get("key") == "index" and
            m.get("value") == str(plate_id) for m in p.findall("metadata"))), None)
        if plate is None:
            raise ValueError("Exact plate not found")
        filaments = [{"slot": int(f.get("id")), "grams": float(f.get("used_g")),
                      "color": f.get("color"), "material": f.get("type")}
                     for f in plate.findall("filament") if float(f.get("used_g", 0)) > 0]
        for f in filaments:
            if not math.isfinite(f["grams"]): raise ValueError("Nonfinite slice mass")
        prediction = next((float(m.get("value")) for m in plate.findall("metadata")
                           if m.get("key") == "prediction"), None)
        return filaments, prediction

def toolpath_breakdown(path: Path, plate_id=1):
    """Classify deposited paths only. Firmware purge/custom code stays unclassified.

    Never add path grams to slicer totals; they are a subset. Negative E and
    subsequent unretraction cancel. Unknown feature types remain unclassified.
    """
    filaments, _ = slice_info(path, plate_id)
    total = sum(f["grams"] for f in filaments)
    with zipfile.ZipFile(path) as z:
        config = json.loads(z.read("Metadata/project_settings.config"))
        densities = [float(x) for x in config["filament_density"]]
        diameters = [float(x) for x in config["filament_diameter"]]
        factors = [math.pi * d*d / 4 * rho / 1000 for d, rho in zip(diameters, densities)]
        grams = defaultdict(float)
        relative = False
        tool = 0
        position = defaultdict(float)
        debt = defaultdict(float)
        feature = None
        virtual_flush = False
        # Restrict calculations to motion under recognised slicer feature tags.
        with z.open(f"Metadata/plate_{plate_id}.gcode") as stream:
            for raw in stream:
                line = raw.decode("utf-8", "replace").strip()
                if line == "; VFLUSH_START":
                    virtual_flush = True
                    continue
                if line == "; VFLUSH_END":
                    virtual_flush = False
                    continue
                if virtual_flush:
                    virtual = re.match(r";VG1\s+E([-+]?(?:\d+(?:\.\d*)?|\.\d+))(?:\s|$)", line)
                    if virtual and tool < len(factors):
                        grams["flush_g"] += max(0, float(virtual[1])) * factors[tool]
                    continue
                if line.startswith("; FEATURE: ") or line.startswith(";TYPE:"):
                    feature = line.split(":", 1)[1].strip()
                    continue
                code = line.split(";", 1)[0].strip()
                if not code: continue
                if code == "M83": relative = True; continue
                if code == "M82": relative = False; continue
                match = re.match(r"T(\d+)(?:\s|$)", code)
                if match:
                    t = int(match[1])
                    if t < len(factors): tool = t
                    continue
                params = {k: float(v) for k,v in re.findall(r"([EXYZ])([-+]?(?:\d+(?:\.\d*)?|\.\d+))", code)}
                command = code.split()[0]
                if command == "G92":
                    if "E" in params: position[tool] = params["E"]
                    continue
                if command not in {"G0", "G1", "G2", "G3"} or "E" not in params: continue
                e = params["E"]
                delta = e if relative else e-position[tool]
                position[tool] = position[tool]+e if relative else e
                if delta < 0: debt[tool] += -delta; continue
                restored = min(debt[tool], delta)
                debt[tool] -= restored
                delta -= restored
                if delta <= 0 or not any(k in params for k in ["X","Y"]): continue
                if tool >= len(factors): continue
                if feature in MODEL_FEATURES: kind = "model_g"
                elif feature in WASTE_FEATURES:
                    kind = "support_g" if feature.startswith("Support") else "tower_brim_g"
                else: continue
                grams[kind] += delta*factors[tool]
    recognized = sum(grams.values())
    if recognized > total + max(0.2, total*0.02):
        return {"total_g": total, "error": "路径重量超出切片总量，分类暂不采用"}
    return {"total_g": total, **{k:round(grams[k],3) for k in
        ["model_g","support_g","tower_brim_g","flush_g"]},
        "unclassified_g": round(max(0,total-recognized),3),
        "basis": "切片路径估算；未分类含固件清料等，不视作零损耗"}

def discover_receipts(jobs: Path):
    results = {}
    if not jobs.exists(): return results
    for p in jobs.rglob("storage-readback-verification.json"):
        try:
            d = json.loads(p.read_text())
            source = p.parent/"storage-readback.3mf"
            intent = json.loads((p.parent/"mqtt-start-intent.json").read_text())
            packet = intent["packet"]["print"]
            if not d.get("matches_reviewed_artifact") or d["sha256"] != intent["sha256"]: continue
            if packet["file"] != d["name"] or not source.is_file(): continue
            name = packet["subtask_name"]
            if Path(d["name"]).name != d["name"]: continue
            results[name] = (source,d,packet)
        except (OSError,ValueError,KeyError,TypeError): continue
    return results

def ensure_sources(c, data, jobs, policy):
    receipts = discover_receipts(jobs)
    for a in c.execute("SELECT * FROM print_archives").fetchall():
        aid = a["id"]
        explicit = policy.get("runs", {}).get(str(aid), {})
        old = c.execute("SELECT * FROM home_material_sources WHERE archive_id=?", (aid,)).fetchone()
        slots = explicit.get("slots")
        sha = old["sha256"] if old else None
        evidence = explicit.get("evidence", "native archive")
        if a["print_name"] in receipts:
            source, receipt, packet = receipts[a["print_name"]]
            if not old or not a["file_path"] or not (data/a["file_path"]).is_file():
                sha = hashlib.sha256(source.read_bytes()).hexdigest()
                if sha != receipt["sha256"]: continue
                dest = data/"archive"/"home-accounting"/str(aid)/receipt["name"]
                dest.parent.mkdir(parents=True,exist_ok=True)
                if not dest.exists():
                    temp = dest.with_suffix(".tmp")
                    shutil.copyfile(source,temp)
                    temp.replace(dest)
                filaments,prediction = slice_info(dest,1)
                colors = ",".join(f["color"] for f in filaments)
                c.execute("""UPDATE print_archives SET file_path=?,file_size=?,plate_id=1,
                    filament_used_grams=?,print_time_seconds=?,filament_color=? WHERE id=?""",
                    (str(dest.relative_to(data)),dest.stat().st_size,sum(f["grams"] for f in filaments),
                     prediction,colors,aid))
                evidence = "device readback + dispatch SHA256:"+sha
            if slots is None and not old:
                slots = {}
                for i,tray in enumerate(packet.get("ams_mapping", []),1):
                    if tray < 0: continue
                    if tray >= 254: ams,slot = 255,tray-254
                    elif tray >= 128: ams,slot = tray,0
                    else: ams,slot = divmod(tray,4)
                    assignment = c.execute("""SELECT * FROM spool_assignment
                        WHERE printer_id=? AND ams_id=? AND tray_id=?""",
                        (a["printer_id"],ams,slot)).fetchone()
                    # Never retroactively guess using a spool installed after this run.
                    if assignment and a["started_at"] and assignment["created_at"] <= a["started_at"]:
                        slots[str(i)] = assignment["spool_id"]
        if old:
            continue
        if slots:
            c.execute("INSERT INTO home_material_sources(archive_id,sha256,slots_json,evidence) VALUES(?,?,?,?)",
                      (aid,sha,json.dumps(slots),evidence))
    c.commit()

def reconcile_run(c, data, run, policy):
    rid, aid = run["id"], run["archive_id"]
    old = c.execute("SELECT * FROM home_material_runs WHERE run_id=?", (rid,)).fetchone()
    if old and old["state"] == "settled": return
    archive = c.execute("SELECT * FROM print_archives WHERE id=?", (aid,)).fetchone()
    if not archive: return
    source = c.execute("SELECT * FROM home_material_sources WHERE archive_id=?", (aid,)).fetchone()
    explicit = policy.get("runs",{}).get(str(aid),{})
    same_runs = c.execute("SELECT count(*) FROM print_log_entries WHERE archive_id=?", (aid,)).fetchone()[0]
    # Evidence keyed by archive is safe for its sole run only. Reprints use native events.
    usages = c.execute("""SELECT * FROM spool_usage_history WHERE archive_id=?
        AND (ABS(julianday(created_at)-julianday(?))*86400 < 180)""",
        (aid,run["completed_at"] or run["created_at"])).fetchall()
    if same_runs == 1:
        usages = c.execute("SELECT * FROM spool_usage_history WHERE archive_id=?", (aid,)).fetchall()
    path = data/archive["file_path"] if archive["file_path"] else None
    breakdown = None
    if path and path.is_file() and run["status"] == "completed":
        try: breakdown = toolpath_breakdown(path,archive["plate_id"] or 1)
        except (OSError,ValueError,KeyError,zipfile.BadZipFile,ET.ParseError) as e:
            breakdown = {"error":str(e)[:160]}
    details = {"name":run["print_name"],"status":run["status"],"basis":"切片估算",
               "breakdown":breakdown,"completed_at":run["completed_at"] or run["created_at"]}
    claimed = set()
    for other in c.execute("SELECT detail FROM home_material_runs WHERE run_id!=? AND state='settled'", (rid,)):
        claimed.update(json.loads(other["detail"]).get("usage_ids", []))
    usages = [u for u in usages if u["id"] not in claimed]
    if usages:
        details["usage_ids"] = [u["id"] for u in usages]
        details["usage"] = [{"spool_id":u["spool_id"],"grams":u["weight_used"],"cost":u["cost"]} for u in usages]
        details["source"] = "native_usage"
        state = "settled"
    elif run["status"] != "completed":
        details["reason"] = "中止／失败任务缺少实际进度用料，不按整盘扣除"
        state = "pending"
    elif not source or same_runs != 1:
        details["reason"] = "缺少本次打印与料卷的可靠对应关系"
        state = "pending"
    else:
        slots = json.loads(source["slots_json"])
        try:
            if path and path.is_file():
                filaments,_ = slice_info(path,archive["plate_id"] or 1)
            else:
                filaments = explicit.get("filaments",[])
            if not filaments or any(str(f["slot"]) not in slots for f in filaments):
                raise ValueError("缺少切片或部分料卷对应关系")
            usage = []
            for f in filaments:
                spool = c.execute("SELECT * FROM spool WHERE id=?", (slots[str(f["slot"])],)).fetchone()
                if not spool: raise ValueError("料卷不存在")
                grams = f["grams"]
                if not math.isfinite(grams) or grams<=0: raise ValueError("用量无效")
                cost = grams/1000*spool["cost_per_kg"] if spool["cost_per_kg"] is not None else None
                usage.append({"spool_id":spool["id"],"grams":grams,"cost":cost})
            opening = bool(explicit.get("included_in_opening_balance"))
            for u in usage:
                if not opening:
                    c.execute("UPDATE spool SET weight_used=weight_used+?,last_used=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        (u["grams"],details["completed_at"],u["spool_id"]))
                c.execute("""INSERT INTO spool_usage_history
                    (spool_id,printer_id,print_name,archive_id,weight_used,percent_used,status,cost,created_at)
                    VALUES(?,?,?,?,?,0,?,?,?)""",
                    (u["spool_id"],run["printer_id"],run["print_name"],aid,u["grams"],
                     run["status"],u["cost"],details["completed_at"]))
            details.update(usage=usage,source="opening_balance" if opening else "verified_reconciliation",
                           evidence=source["evidence"])
            state = "settled"
        except ValueError as e:
            details["reason"] = str(e)
            state = "pending"
    if state == "settled":
        if "usage_ids" not in details:
            details["usage_ids"] = [u[0] for u in c.execute(
                "SELECT id FROM spool_usage_history WHERE archive_id=?", (aid,)) if u[0] not in claimed]
        total = sum(u["grams"] for u in details["usage"])
        costs = [u["cost"] for u in details["usage"]]
        cost = sum(costs) if all(x is not None for x in costs) else None
        c.execute("UPDATE print_log_entries SET filament_used_grams=?,cost=? WHERE id=?", (total,cost,rid))
        if same_runs == 1:
            c.execute("UPDATE print_archives SET filament_used_grams=?,cost=? WHERE id=?", (total,cost,aid))
    c.execute("""INSERT INTO home_material_runs(run_id,archive_id,state,detail) VALUES(?,?,?,?)
        ON CONFLICT(run_id) DO UPDATE SET state=excluded.state,detail=excluded.detail,updated_at=CURRENT_TIMESTAMP""",
        (rid,aid,state,json.dumps(details,ensure_ascii=False)))

def run_once(data: Path, jobs: Path):
    policy_path = data/"home-material-policy.json"
    policy = json.loads(policy_path.read_text()) if policy_path.exists() else {}
    c = connect(data)
    try:
        ensure_sources(c,data,jobs,policy)
        # Native tracker writes usage before its print-log row. The grace period
        # also avoids reading a just-written row from a concurrent completion.
        runs = c.execute("""SELECT * FROM print_log_entries WHERE status IN
            ('completed','failed','stopped','cancelled','aborted')
            AND julianday('now')-julianday(COALESCE(completed_at,created_at)) > 30.0/86400""").fetchall()
        for run in runs:
            with c:
                c.execute("BEGIN IMMEDIATE")
                reconcile_run(c,data,run,policy)
        with c:
            c.execute("INSERT OR REPLACE INTO home_material_health VALUES(1,?,NULL)",
                      (datetime.now(timezone.utc).isoformat(),))
    finally:
        c.close()

def summary(data: Path):
    c = sqlite3.connect("file:"+str(data / "bambuddy.db")+"?mode=ro", uri=True, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("BEGIN")
    try:
        rows=[]
        for r in c.execute("""SELECT h.*,p.user_verdict FROM home_material_runs h
            JOIN print_log_entries p ON p.id=h.run_id ORDER BY h.run_id DESC"""):
            d=json.loads(r["detail"]);d.update(run_id=r["run_id"],archive_id=r["archive_id"],state=r["state"])
            total=sum(u["grams"] for u in d.get("usage",[]))
            b=d.get("breakdown") or {}
            known=sum(b.get(k,0) for k in ["support_g","tower_brim_g","flush_g"]) if "model_g" in b else None
            m=c.execute("SELECT * FROM home_material_measurements WHERE run_id=?",(r["run_id"],)).fetchone()
            if b.get("total_g") and abs(b["total_g"]-total)>max(0.2,total*0.02):
                known=None
                d["breakdown"]={"error":"本次消耗与整盘预估不同，不能直接采用整盘损耗"}
            if m:
                known=m["waste_g"];d["waste_basis"]="人工称重记录";d["waste_note"]=m["note"]
            else: d["waste_basis"]="已识别工艺损耗估算"
            if not m and (r["user_verdict"]=="reject" or (d["status"]!="completed" and r["state"]=="settled")):
                known=total;d["waste_basis"]="整次报废／失败用料"
            d.update(total_g=round(total,3) if r["state"]=="settled" else None,
                     waste_g=round(known,3) if known is not None else None,
                     waste_rate=round(known/total*100,2) if known is not None and total>0 else None)
            rows.append(d)
        known=[r for r in rows if r["state"]=="settled" and r["waste_g"] is not None]
        denom=sum(r["total_g"] for r in known)
        waste=sum(r["waste_g"] for r in known)
        health=c.execute("SELECT * FROM home_material_health WHERE id=1").fetchone()
        running=[]
        for a in c.execute("SELECT * FROM print_archives WHERE status='printing'"):
            source=c.execute("SELECT * FROM home_material_sources WHERE archive_id=?",(a["id"],)).fetchone()
            if not source or not a["file_path"]: continue
            try:
                filaments,_=slice_info(data/a["file_path"],a["plate_id"] or 1)
                slots=json.loads(source["slots_json"])
                running.append({"archive_id":a["id"],"name":a["print_name"],
                    "planned_usage":[{"spool_id":slots.get(str(f["slot"])),"grams":f["grams"]} for f in filaments]})
            except (ValueError,OSError,KeyError,zipfile.BadZipFile,ET.ParseError): continue
        return {"running":running,"checked_at":health["checked_at"] if health else None,
            "runs":rows,"settled_count":sum(r["state"]=="settled" for r in rows),
            "pending_count":sum(r["state"]!="settled" for r in rows),
            "total_used_g":round(sum(r["total_g"] or 0 for r in rows),2),
            "known_waste_g":round(waste,2),"covered_g":round(denom,2),
            "known_waste_rate":round(waste/denom*100,2) if denom else None,
            "unknown_breakdown_count":sum(r["waste_g"] is None for r in rows),
            "note":"损耗率只覆盖有分类数据的任务；未分类、手动清料和漏记任务不按零损耗处理。"}
    finally: c.close()

def record_waste(data: Path, run_id: int, waste_g: float, note: str, actor: str):
    c=connect(data)
    try:
        with c:
            c.execute("BEGIN IMMEDIATE")
            r=c.execute("SELECT * FROM home_material_runs WHERE run_id=?",(run_id,)).fetchone()
            if not r or r["state"]!="settled": raise ValueError("任务尚未结算")
            total=sum(u["grams"] for u in json.loads(r["detail"]).get("usage",[]))
            if not math.isfinite(waste_g) or not 0<=waste_g<=total:
                raise ValueError("废料重量须介于0和本次已登记总耗料之间；超出时先校正总耗料")
            old=c.execute("SELECT * FROM home_material_measurements WHERE run_id=?",(run_id,)).fetchone()
            c.execute("INSERT INTO home_material_audit(action,detail) VALUES(?,?)",
                ("waste_measurement",json.dumps({"run_id":run_id,"before":dict(old) if old else None,
                    "after":{"waste_g":waste_g,"note":note,"actor":actor}},ensure_ascii=False)))
            c.execute("""INSERT INTO home_material_measurements(run_id,waste_g,note,actor) VALUES(?,?,?,?)
                ON CONFLICT(run_id) DO UPDATE SET waste_g=excluded.waste_g,note=excluded.note,
                actor=excluded.actor,updated_at=CURRENT_TIMESTAMP""",(run_id,waste_g,note,actor))
    finally: c.close()

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--data",type=Path,required=True);p.add_argument("--jobs",type=Path,required=True)
    p.add_argument("--watch",action="store_true")
    args=p.parse_args();logging.basicConfig(level=logging.INFO)
    while True:
        try:
            run_once(args.data,args.jobs)
            LOG.info("Material accounting reconciliation complete")
        except Exception:
            LOG.exception("Material accounting reconciliation failed")
            if not args.watch: raise
        if not args.watch: break
        time.sleep(60)
