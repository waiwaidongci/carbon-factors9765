import os,tempfile
_TMP=tempfile.mkdtemp(prefix='green-test-')
os.environ['DATABASE_URL']='sqlite:///'+os.path.join(_TMP,'test.db')
os.environ['PROJECT_JSON']=os.path.join(_TMP,'missing.json')
os.environ['GREEN_HEARTBEAT_TTL']='0.05'
import unittest
from src.services import mcmf
from src.services.exhaustive import exhaustive
def cert(cid,month,dept,factor,remain):return {'id':cid,'month':month,'department':dept,'factor':factor,'kwh_remaining':remain}
def rep(rid,month,dept,kwh,grid):return {'id':rid,'month':month,'department':dept,'kwh':kwh,'grid_factor':grid}
class OptimizerTest(unittest.TestCase):
 def assert_optimal(self,certs,reps):
  got=mcmf.plan(certs,reps);want=exhaustive(certs,reps)
  self.assertEqual(got['covered_kwh'],want['covered_kwh'],'覆盖电量非最优')
  self.assertAlmostEqual(got['emissions_kg'],want['emissions_kg'],places=9,msg='同覆盖下排放非最低')
  self.assertEqual(got['total_kwh'],want['total_kwh'])
  used={}
  for a in got['allocations']:
   c=next(x for x in certs if x['id']==a['certificate_id']);r=next(x for x in reps if x['id']==a['report_id'])
   self.assertEqual((c['month'],c['department']),(r['month'],r['department']),'存在不允许的凭证-用电组合')
   used[a['certificate_id']]=used.get(a['certificate_id'],0)+a['kwh']
  for c in certs:self.assertLessEqual(used.get(c['id'],0),c['kwh_remaining']+1e-9,'超出凭证余额')
  per_report={}
  for a in got['allocations']:per_report[a['report_id']]=per_report.get(a['report_id'],0)+a['kwh']
  for r in reps:self.assertLessEqual(per_report.get(r['id'],0),r['kwh']+1e-9,'超出报告电量')
 def test_greedy_counterexample(self):
  """逐条贪心（按报告顺序、每报告先选低因子凭证）在最小化排放上漏配：
  先处理的 R2 占走便宜凭证 A，高电网因子的 R1 反而只能用贵凭证，排放高于最优。
  覆盖量同为最大，但第二目标排放不是最小——逐条贪心在该规则下的典型错误。"""
  certs=[cert('A','2026-11','D',0.1,40),cert('B','2026-11','D',0.3,30)]
  reps=[rep('R2','2026-11','D',40,0.20),rep('R1','2026-11','D',50,0.90)]
  def greedy_ordered():
   bal={c['id']:c['kwh_remaining'] for c in certs};emission=0.0
   for r in reps:
    need=r['kwh']
    for c in sorted(certs,key=lambda x:x['factor']):
     take=min(bal[c['id']],need);need-=take;bal[c['id']]-=take;emission+=take*c['factor']
    emission+=need*r['grid_factor']
   return emission
  got=mcmf.plan(certs,reps)
  self.assertEqual(got['covered_kwh'],70)
  self.assertGreater(greedy_ordered(),got['emissions_kg']+1e-9)
  self.assert_optimal(certs,reps)
 def test_small_exhaustive_cases(self):
  base=[
   ([cert('A','2026-11','D1',0.1,30),cert('B','2026-11','D1',0.4,60)],[rep('R1','2026-11','D1',70,0.57)]),
   ([cert('A','2026-10','D1',0.0,20),cert('B','2026-11','D1',0.2,20)],[rep('R1','2026-11','D1',50,0.57)]),
   ([cert('A','2026-11','D1',0.1,40),cert('B','2026-11','D2',0.3,60)],[rep('R1','2026-11','D1',40,0.57),rep('R2','2026-11','D2',60,0.57)]),
   ([],[rep('R1','2026-11','D1',30,0.57)]),
   ([cert('A','2026-11','D1',0.0,100)],[rep('R1','2026-11','D1',25,0.57)]),
  ]
  for certs,reps in base:self.assert_optimal(certs,reps)
 def test_randomized_vs_exhaustive(self):
  import random
  rng=random.Random(20261117)
  months=['2026-10','2026-11'];depts=['D1','D2']
  for _ in range(40):
   nc=rng.randint(1,2);nr=rng.randint(1,2)
   certs=[cert(f'C{i}',rng.choice(months),rng.choice(depts),round(rng.uniform(0,0.5),3),rng.randint(1,4)) for i in range(nc)]
   reps=[rep(f'R{i}',rng.choice(months),rng.choice(depts),rng.randint(1,4),0.57) for i in range(nr)]
   self.assert_optimal(certs,reps)
 def test_lexicographic_order(self):
  certs=[cert('A','2026-11','D',0.6,30),cert('B','2026-11','D',0.1,30)]
  reps=[rep('R1','2026-11','D',40,0.57)]
  got=mcmf.plan(certs,reps)
  self.assertEqual(got['covered_kwh'],40)
  a={x['certificate_id']:x['kwh'] for x in got['allocations']}
  self.assertEqual(a.get('B'),30);self.assertEqual(a.get('A'),10)
if __name__=='__main__':unittest.main()
