"""Standalone stdlib tests; never connect to a runtime database."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import zipfile

spec=importlib.util.spec_from_file_location("accounting",Path(__file__).resolve().parents[1]/"backend/app/services/home_material_accounting.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class AccountingTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.data=Path(self.temp.name);self.c=m.connect(self.data);self.addCleanup(self.c.close)
  self.c.executescript("""
  CREATE TABLE spool(id INTEGER PRIMARY KEY,weight_used REAL,cost_per_kg REAL,last_used TEXT,updated_at TEXT);
  CREATE TABLE print_archives(id INTEGER PRIMARY KEY,file_path TEXT,plate_id INTEGER,filament_used_grams REAL,cost REAL,status TEXT);
  CREATE TABLE print_log_entries(id INTEGER PRIMARY KEY,archive_id INTEGER,status TEXT,print_name TEXT,
    printer_id INTEGER,completed_at TEXT,created_at TEXT,filament_used_grams REAL,cost REAL,user_verdict TEXT);
  CREATE TABLE spool_usage_history(id INTEGER PRIMARY KEY,spool_id INTEGER,printer_id INTEGER,print_name TEXT,
    archive_id INTEGER,weight_used REAL,percent_used INTEGER,status TEXT,cost REAL,created_at TEXT);
  INSERT INTO spool VALUES(1,100,50,NULL,NULL);
  INSERT INTO print_archives VALUES(1,'',1,10,NULL,'completed');
  INSERT INTO print_log_entries VALUES(1,1,'completed','test',1,'2026-01-01','2026-01-01',10,NULL,NULL);
  INSERT INTO home_material_sources(archive_id,slots_json,evidence) VALUES(1,'{"1":1}','test evidence');
  """)
  self.policy={"runs":{"1":{"filaments":[{"slot":1,"grams":10}]}}}
 def run_accounting(self):
  run=self.c.execute("SELECT * FROM print_log_entries WHERE id=1").fetchone()
  with self.c: m.reconcile_run(self.c,self.data,run,self.policy)
 def test_reconciliation_is_idempotent(self):
  self.run_accounting();self.run_accounting()
  self.assertEqual(self.c.execute("SELECT weight_used FROM spool").fetchone()[0],110)
  self.assertEqual(self.c.execute("SELECT count(*) FROM spool_usage_history").fetchone()[0],1)
 def test_opening_balance_is_not_deducted_again(self):
  self.policy["runs"]["1"]["included_in_opening_balance"]=True
  self.run_accounting()
  self.assertEqual(self.c.execute("SELECT weight_used FROM spool").fetchone()[0],100)
  self.assertEqual(self.c.execute("SELECT count(*) FROM spool_usage_history").fetchone()[0],1)
 def test_native_tracker_is_not_double_charged(self):
  self.c.execute("INSERT INTO spool_usage_history VALUES(1,1,1,'test',1,10,1,'completed',.5,'2026-01-01')")
  self.run_accounting()
  self.assertEqual(self.c.execute("SELECT weight_used FROM spool").fetchone()[0],100)
  self.assertEqual(self.c.execute("SELECT count(*) FROM spool_usage_history").fetchone()[0],1)
 def test_missing_mapping_is_pending(self):
  self.c.execute("DELETE FROM home_material_sources");self.run_accounting()
  self.assertEqual(self.c.execute("SELECT state FROM home_material_runs").fetchone()[0],"pending")
  self.assertEqual(self.c.execute("SELECT weight_used FROM spool").fetchone()[0],100)
 def test_failed_run_not_charged_as_full_plate(self):
  self.c.execute("UPDATE print_log_entries SET status='failed'");self.run_accounting()
  self.assertEqual(self.c.execute("SELECT state FROM home_material_runs").fetchone()[0],"pending")
 def test_measurement_does_not_deduct_again_and_is_audited(self):
  self.run_accounting();m.record_waste(self.data,1,2,"support on scale","admin")
  s=m.summary(self.data)
  self.assertEqual(s["known_waste_rate"],20)
  self.assertEqual(self.c.execute("SELECT weight_used FROM spool").fetchone()[0],110)
  with self.assertRaises(ValueError): m.record_waste(self.data,1,11,"bad","admin")
  self.assertEqual(self.c.execute("SELECT count(*) FROM home_material_audit").fetchone()[0],1)
 def test_fractional_e_retraction_and_feature_classification(self):
  p=self.data/"test.3mf"
  with zipfile.ZipFile(p,"w") as z:
   z.writestr("Metadata/slice_info.config",'<config><plate><metadata key="index" value="1"/><filament id="1" used_g="1"/></plate></config>')
   z.writestr("Metadata/project_settings.config",json.dumps({"filament_density":["1.24"],"filament_diameter":["1.75"]}))
   z.writestr("Metadata/plate_1.gcode","M83\nT0\n; FEATURE: Outer wall\nG1 X1 Y1 E.5\nG1 E-.5\nG1 E.5\n; FEATURE: Support\nG1 X2 E.5\n; FEATURE: Prime tower\nG1 X3 E1\n; VFLUSH_START\n;VG1 E10 F100\n; VFLUSH_END\n;VG1 E100 F100\n")
  b=m.toolpath_breakdown(p)
  self.assertAlmostEqual(b["model_g"],b["support_g"],places=3)
  self.assertGreater(b["support_g"],0)
  self.assertAlmostEqual(b["flush_g"],0.030,places=3)
  self.assertGreater(b["unclassified_g"],0)
 def test_reprint_cannot_reuse_previous_usage(self):
  self.run_accounting()
  self.c.execute("INSERT INTO print_log_entries VALUES(2,1,'completed','reprint',1,'2026-01-01','2026-01-01',10,NULL,NULL)")
  run=self.c.execute("SELECT * FROM print_log_entries WHERE id=2").fetchone()
  with self.c: m.reconcile_run(self.c,self.data,run,self.policy)
  self.assertEqual(self.c.execute("SELECT state FROM home_material_runs WHERE run_id=2").fetchone()[0],"pending")
  self.assertEqual(self.c.execute("SELECT weight_used FROM spool").fetchone()[0],110)
 def test_measured_waste_overrides_failed_run_assumption(self):
  self.c.execute("UPDATE print_log_entries SET status='failed'")
  self.c.execute("INSERT INTO spool_usage_history VALUES(1,1,1,'test',1,10,1,'failed',.5,'2026-01-01')")
  self.run_accounting()
  m.record_waste(self.data,1,3,"usable parts retained","admin")
  self.assertEqual(m.summary(self.data)["known_waste_rate"],30)
 def test_unknown_cost_stays_unknown(self):
  self.c.execute("UPDATE spool SET cost_per_kg=NULL");self.run_accounting()
  self.assertIsNone(self.c.execute("SELECT cost FROM print_log_entries").fetchone()[0])

if __name__=="__main__":unittest.main()
