import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
spec=importlib.util.spec_from_file_location("store",Path(__file__).parents[2]/"backend/app/services/home_ledger_store.py")
store=importlib.util.module_from_spec(spec)
spec.loader.exec_module(store)
class StoreTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.root=Path(self.tmp.name); self.db=self.root/"ledger.sqlite"; self.seed=self.root/"seed.json"
  self.seed.write_text(json.dumps({"orders":[{"id":"P001","paid_cny":None,"notes":"unknown"}],"filament_units":[{"id":"F001","remaining_g":None}]}))
 def tearDown(self):self.tmp.cleanup()
 def test_unknown_zero_and_conflict(self):
  first=store.read(self.db,self.seed)
  self.assertIsNone(first["data"]["orders"][0]["paid_cny"])
  changed=store.update_order(self.db,"P001",{"paid_cny":0},1,"tester")
  self.assertEqual(changed["revision"],2)
  with self.assertRaises(store.ConflictError):store.update_order(self.db,"P001",{"paid_cny":99},1,"stale-client")
  current=store.read(self.db,self.seed)
  self.assertEqual(current["data"]["orders"][0]["paid_cny"],0)
  self.assertIsNone(current["data"]["filament_units"][0]["remaining_g"])
  with sqlite3.connect(self.db) as db:
   old=json.loads(db.execute("SELECT body FROM ledger_audit WHERE revision=1").fetchone()[0])
   self.assertIsNone(old["orders"][0]["paid_cny"])
 def test_seed_is_one_time_and_unknown_key_rolls_back(self):
  store.read(self.db,self.seed)
  self.seed.write_text("{}")
  with self.assertRaises(KeyError):store.update_order(self.db,"absent",{"paid_cny":5},1,"tester")
  state=store.read(self.db,self.seed)
  self.assertEqual(state["revision"],1)
  self.assertEqual(len(state["data"]["orders"]),1)
 def test_duplicate_ids_fail(self):
  self.seed.write_text('{"orders":[{"id":"P001"},{"id":"P001"}]}')
  with self.assertRaises(ValueError):store.read(self.db,self.seed)
if __name__=="__main__":unittest.main()
