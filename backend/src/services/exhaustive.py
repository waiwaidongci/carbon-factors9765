"""小规模穷举 oracle：枚举所有凭证-报告组合的整数分配，按字典序求最优。

仅用于测试（凭证数×报告数较小）。与 mcmf.plan 的目标完全一致：
先最大化覆盖电量，再最小化排放。
"""
def exhaustive(certificates,reports):
 caps={c['id']:int(c['kwh_remaining']) for c in certificates}
 demands={r['id']:int(r['kwh']) for r in reports}
 cf={c['id']:float(c['factor']) for c in certificates}
 gf={r['id']:float(r['grid_factor']) for r in reports}
 edges=[(c['id'],r['id']) for c in certificates for r in reports
  if c['month']==r['month'] and c['department']==r['department']
  and caps[c['id']]>0 and demands[r['id']]>0]
 best={'covered_kwh':-1,'emissions_kg':None,'allocations':[]}
 current=[]
 def evaluate():
  covered=sum(a[2] for a in current)
  emission=sum(k*cf[cid] for cid,_,k in current)
  for r in reports:
   used=sum(k for cid,rid,k in current if rid==r['id'])
   emission+=(r['kwh']-used)*r['grid_factor']
  if covered>best['covered_kwh'] or covered==best['covered_kwh'] and (best['emissions_kg'] is None or emission<best['emissions_kg']-1e-9):
   best['covered_kwh']=covered;best['emissions_kg']=emission
   best['allocations']=[{'certificate_id':cid,'report_id':rid,'kwh':k} for cid,rid,k in current if k>0]
 def dfs(i,cap_left,demand_left):
  if i==len(edges):evaluate();return
  cid,rid=edges[i];upper=min(cap_left[cid],demand_left[rid])
  for x in range(upper+1):
   if x:current.append((cid,rid,x))
   cap_left[cid]-=x;demand_left[rid]-=x
   dfs(i+1,cap_left,demand_left)
   cap_left[cid]+=x;demand_left[rid]+=x
   if x:current.pop()
 dfs(0,dict(caps),dict(demands))
 best['total_kwh']=sum(demands.values());best['uncovered_kwh']=best['total_kwh']-best['covered_kwh']
 return best
