import os,tempfile,time,threading
_TMP=tempfile.mkdtemp(prefix='green-svc-')
os.environ['DATABASE_URL']='sqlite:///'+os.path.join(_TMP,'svc.db')
os.environ['PROJECT_JSON']=os.path.join(_TMP,'missing.json')
os.environ['GREEN_HEARTBEAT_TTL']='0.05'
import unittest
from types import SimpleNamespace
from src.config.database import Base,engine,Session
from src.models.green import GreenCertificate,GreenReport,GreenReservation,GreenLedger
from src.services import green
from src.services.exhaustive import exhaustive
Base.metadata.create_all(engine)
U=SimpleNamespace(email='tester@demo.local',role='admin')
def cert_input(code,month,dept,factor,kwh):return SimpleNamespace(code=code,month=month,department=dept,factor=factor,kwh_total=kwh)
def report_input(name,month,dept,kwh,grid=0.57):return SimpleNamespace(name=name,month=month,department=dept,kwh=kwh,grid_factor=grid)
class ServiceTest(unittest.TestCase):
 def setUp(self):
  with Session() as db:
   db.query(GreenLedger).delete();db.query(GreenReservation).delete();db.query(GreenReport).delete();db.query(GreenCertificate).delete();db.commit()
 def _seed(self):
  with Session() as db:
   a=green.register_certificate(db,U,cert_input('GC-A','2026-11','D1',0.10,40))
   b=green.register_certificate(db,U,cert_input('GC-B','2026-11','D1',0.30,60))
   r1=green.create_report(db,U,report_input('R1','2026-11','D1',50))
   r2=green.create_report(db,U,report_input('R2','2026-11','D1',40))
   return a.id,b.id,r1.id,r2.id
 def test_register_and_integer_guard(self):
  with Session() as db:
   c=green.register_certificate(db,U,cert_input('GC-X','2026-11','D1',0.2,100))
   self.assertEqual(c.kwh_remaining,100)
   with self.assertRaises(Exception):green.register_certificate(db,U,cert_input('GC-Y','2026-11','D1',0.2,12.5))
   db.rollback()
 def test_enqueue_reserve_then_consume(self):
  a,b,r1,r2=self._seed()
  with Session() as db:
   rep=green.enqueue(db,U,r1)
   self.assertEqual(rep.status,'queued');self.assertEqual(rep.attempt,1)
   self.assertEqual(db.get(GreenCertificate,a).kwh_remaining,0)
   self.assertEqual(db.get(GreenCertificate,b).kwh_remaining,50)
   self.assertTrue(green.claim(db,r1,1))
   self.assertTrue(green.run_report(db,r1,1))
   obj=db.get(GreenReport,r1)
   self.assertEqual(obj.status,'completed');self.assertEqual(obj.result['covered_kwh'],50)
   self.assertEqual(db.get(GreenCertificate,a).kwh_remaining,0)
   self.assertEqual(db.get(GreenCertificate,b).kwh_remaining,50)
   self.assertEqual(green.conservation(db)['ok'],True)
 def test_completed_report_keeps_allocation(self):
  a,b,r1,r2=self._seed()
  with Session() as db:
   green.enqueue(db,U,r1);green.claim(db,r1,1);green.run_report(db,r1,1)
   with self.assertRaises(Exception):green.enqueue(db,U,r1)
   db.rollback()
   # 核销后预占转正为结果中的已核销分配，预占行清空、余额不还原
   self.assertEqual(db.query(GreenReservation).filter_by(report_id=r1).count(),0)
   self.assertEqual(len(db.get(GreenReport,r1).result['allocations']),2)
   self.assertEqual(db.get(GreenCertificate,a).kwh_remaining,0)
   self.assertEqual(green.conservation(db)['ok'],True)
 def test_cancel_releases(self):
  a,b,r1,r2=self._seed()
  with Session() as db:
   green.enqueue(db,U,r1)
   green.cancel(db,U,r1)
   self.assertEqual(db.get(GreenCertificate,a).kwh_remaining,40)
   self.assertEqual(db.get(GreenCertificate,b).kwh_remaining,60)
   self.assertEqual(db.query(GreenReservation).count(),0)
   self.assertEqual(db.get(GreenReport,r1).status,'draft')
 def test_failure_releases_and_requeue(self):
  a,b,r1,r2=self._seed()
  with Session() as db:
   green.enqueue(db,U,r1);self.assertTrue(green.claim(db,r1,1))
   ok=green.run_report(db,r1,1,fail_predicate=lambda r:True)
   self.assertFalse(ok)
   self.assertEqual(db.get(GreenReport,r1).status,'failed')
   self.assertEqual(db.get(GreenCertificate,a).kwh_remaining,40)
   self.assertEqual(db.get(GreenCertificate,b).kwh_remaining,60)
   rep=green.enqueue(db,U,r1)
   self.assertEqual(rep.attempt,2);self.assertEqual(rep.status,'queued')
 def test_stale_executor_fencing(self):
  """旧执行者晚到：attempt 已变，claim/run 均失败，不重复扣额。"""
  a,b,r1,r2=self._seed()
  with Session() as db:
   green.enqueue(db,U,r1)
   self.assertTrue(green.claim(db,r1,1))
   rem_before=(db.get(GreenCertificate,a).kwh_remaining,db.get(GreenCertificate,b).kwh_remaining)
   db.get(GreenReport,r1).heartbeat=time.time()-999;db.commit()
   recovered=green.recover_stale(db)
   self.assertIn(r1,recovered)
   self.assertEqual(db.get(GreenReport,r1).attempt,2)
   self.assertEqual(db.get(GreenReport,r1).status,'queued')
   self.assertFalse(green.claim(db,r1,1))
   self.assertFalse(green.run_report(db,r1,1))
   rem_after=(db.get(GreenCertificate,a).kwh_remaining,db.get(GreenCertificate,b).kwh_remaining)
   self.assertEqual(rem_before,rem_after)
   self.assertTrue(green.claim(db,r1,2));self.assertTrue(green.run_report(db,r1,2))
   self.assertEqual(green.conservation(db)['ok'],True)
 def test_concurrent_enqueue_serialized(self):
  a,b,r1,r2=self._seed()
  errors=[]
  def job(rid):
   try:
    with Session() as db:green.enqueue(db,U,rid)
   except Exception as e:errors.append(str(e))
  t1=threading.Thread(target=job,args=(r1,));t2=threading.Thread(target=job,args=(r2,))
  t1.start();t2.start();t1.join();t2.join()
  self.assertEqual(errors,[])
  with Session() as db:
   # 总需求 90、总凭证 100，串行排队后剩余 10（R1=A40+B10，R2=B40）
   self.assertEqual(sum(c.kwh_remaining for c in db.query(GreenCertificate).all()),10)
   self.assertEqual(db.query(GreenReservation).count(),3)
   self.assertEqual(green.conservation(db)['ok'],True)
 def test_end_to_end_matches_exhaustive_and_conserves(self):
  """小例穷举：逐报告排队后系统总分配等于一次性穷举最优，且额度严格守恒。"""
  with Session() as db:
   specs=[('C1','2026-11','D1',0.1,40),('C2','2026-11','D1',0.3,60),('C3','2026-10','D1',0.2,25)]
   ids=[green.register_certificate(db,U,cert_input(*s)).id for s in specs]
   rspec=[('E1','2026-11','D1',50),('E2','2026-11','D1',40),('E3','2026-10','D1',30)]
   rids=[green.create_report(db,U,report_input(*s)).id for s in rspec]
   certs=[{'id':c.id,'month':c.month,'department':c.department,'factor':c.factor,'kwh_remaining':c.kwh_total} for c in db.query(GreenCertificate).all()]
   reps=[{'id':r.id,'month':r.month,'department':r.department,'kwh':r.kwh,'grid_factor':r.grid_factor} for r in db.query(GreenReport).all()]
   want=exhaustive(certs,reps)
   for rid in rids:
    rep=green.enqueue(db,U,rid)
    self.assertTrue(green.claim(db,rid,rep.attempt));self.assertTrue(green.run_report(db,rid,rep.attempt))
   got_covered=sum(db.get(GreenReport,rid).result['covered_kwh'] for rid in rids)
   got_emission=sum(db.get(GreenReport,rid).result['emissions_total_kg'] for rid in rids)
   self.assertEqual(got_covered,want['covered_kwh'])
   self.assertAlmostEqual(got_emission,want['emissions_kg'],places=9)
   self.assertEqual(green.conservation(db)['ok'],True)
   totals=sum(c.kwh_total for c in db.query(GreenCertificate).all())
   remaining=sum(c.kwh_remaining for c in db.query(GreenCertificate).all())
   consumed=sum(sum(a['kwh'] for a in db.get(GreenReport,rid).result['allocations']) for rid in rids)
   self.assertEqual(totals,remaining+consumed)
 def test_ledger_balance_chain(self):
  a,b,r1,r2=self._seed()
  with Session() as db:
   green.enqueue(db,U,r1);green.cancel(db,U,r1)
   rows=db.query(GreenLedger).filter_by(certificate_id=a).order_by(GreenLedger.id).all()
   self.assertEqual([x.action for x in rows],['register','reserve','release'])
   self.assertEqual([x.balance_after for x in rows],[40,0,40])
if __name__=='__main__':unittest.main()
