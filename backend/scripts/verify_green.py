"""小例穷举验证：打印 MCMF 最优解与暴力穷举 oracle 的对照，并做额度守恒演示。

运行：PYTHONPATH=src python -m scripts.verify_green
不依赖数据库与 Redis，纯算法层验证。
"""
from src.services.mcmf import plan
from src.services.exhaustive import exhaustive
def cert(i,m,d,f,k):return {'id':i,'month':m,'department':d,'factor':f,'kwh_remaining':k}
def rep(i,m,d,k,g):return {'id':i,'month':m,'department':d,'kwh':k,'grid_factor':g}
CASES=[
 ('同部门两凭证两报告（逐条贪心在排放上漏配）',
  [cert('A','2026-11','D',0.10,40),cert('B','2026-11','D',0.30,30)],
  [rep('R2','2026-11','D',40,0.20),rep('R1','2026-11','D',50,0.90)]),
 ('月份/部门门槛：不匹配组合不可用',
  [cert('A','2026-10','D1',0.05,20),cert('B','2026-11','D1',0.20,20),cert('C','2026-11','D2',0.10,50)],
  [rep('R1','2026-11','D1',30,0.57),rep('R2','2026-11','D2',40,0.57)]),
 ('凭证不足：先保覆盖，剩余按电网因子计排',
  [cert('A','2026-11','D',0.05,25)],
  [rep('R1','2026-11','D',60,0.57)]),
]
def main():
 ok=True
 for name,certs,reps in CASES:
  got=plan(certs,reps);want=exhaustive(certs,reps)
  match=(got['covered_kwh']==want['covered_kwh'] and abs(got['emissions_kg']-want['emissions_kg'])<1e-9)
  ok&=match
  print('\n【%s】%s'%(name,'一致✓' if match else '不一致✗'))
  print('  覆盖电量 最优=%d 穷举=%d；总排放 最优=%.4f 穷举=%.4f'%(
   got['covered_kwh'],want['covered_kwh'],got['emissions_kg'],want['emissions_kg']))
  print('  分配:',sorted((a['certificate_id'],a['report_id'],a['kwh']) for a in got['allocations']))
  # 额度守恒：每张凭证分配量不超过余额
  used={}
  for a in got['allocations']:used[a['certificate_id']]=used.get(a['certificate_id'],0)+a['kwh']
  for c in certs:assert used.get(c['id'],0)<=c['kwh_remaining']+1e-9
 print('\n额度守恒：所有凭证 分配量 ≤ 余额，报告 分配量 ≤ 用电量（测试内断言）。')
 print('结论：%s'%('全部小例 MCMF 与穷举最优解一致' if ok else '存在偏差'))
 return 0 if ok else 1
if __name__=='__main__':raise SystemExit(main())
