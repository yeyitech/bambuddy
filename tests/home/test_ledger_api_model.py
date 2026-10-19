import unittest
from pydantic import ValidationError
from backend.app.api.routes.home_ledger import OrderPatch
class ModelTests(unittest.TestCase):
 def test_rejects_bad_money_and_extra_fields(self):
  for body in ({'revision':1,'paid_cny':-1},{'revision':1,'paid_cny':1.001},{'revision':1,'id':'P002'},{'revision':1,'date':'not-a-date'}):
   with self.assertRaises(ValidationError):OrderPatch(**body)
 def test_blank_zero_and_dates(self):
  p=OrderPatch(revision=1,paid_cny=0,due_cny=None,date='2026-10-19')
  self.assertEqual(p.paid_cny,0)
  self.assertIsNone(p.due_cny)
  self.assertEqual(p.date.isoformat(),'2026-10-19')
if __name__=='__main__':unittest.main()
