"""绿电凭证分配优化器。

字典序目标：①最大化被绿电凭证覆盖的电量；②在覆盖最大的前提下最小化总排放。
用最小费用最大流（ successive shortest augmenting path + SPFA ）一次求解：
每单位电量的费用 = 凭证因子 - 电网因子，全网固定项 kwh*grid_factor 不参与优化。
所有容量/流量为整数 kWh，凭证余额与报告电量在服务层做整数化校验。
"""
from collections import deque
class _Edge:
 __slots__=('to','rev','cap','cost','ident')
 def __init__(self,to,rev,cap,cost,ident=None):
  self.to=to;self.rev=rev;self.cap=cap;self.cost=cost;self.ident=ident
class MinCostMaxFlow:
 def __init__(self,n):
  self.n=n;self.g=[[] for _ in range(n)]
 def add_edge(self,u,v,cap,cost,ident=None):
  f=_Edge(v,len(self.g[v]),cap,cost,ident);r=_Edge(u,len(self.g[u]),0,-cost,None)
  self.g[u].append(f);self.g[v].append(r);return f
 def solve(self,s,t):
  flow=cost=0
  g=self.g
  while True:
   dist=[None]*self.n;prev_v=[-1]*self.n;prev_e=[-1]*self.n;dist[s]=0
   q=deque([s]);in_q=[False]*self.n;in_q[s]=True
   while q:
    v=q.popleft();in_q[v]=False
    for i,e in enumerate(g[v]):
     if e.cap<=0 or dist[e.to] is not None and dist[e.to]<=dist[v]+e.cost:continue
     dist[e.to]=dist[v]+e.cost;prev_v[e.to]=v;prev_e[e.to]=i
     if not in_q[e.to]:q.append(e.to);in_q[e.to]=True
   if dist[t] is None:break
   add=float('inf');v=t
   while v!=s:add=min(add,g[prev_v[v]][prev_e[v]].cap);v=prev_v[v]
   v=t
   while v!=s:
    e=g[prev_v[v]][prev_e[v]];e.cap-=add;g[v][e.rev].cap+=add;v=prev_v[v]
   flow+=add;cost+=add*dist[t]
  return flow,cost
def plan(certificates,reports):
 """certificates: dict 列表 id/month/department/factor/kwh_remaining；
 reports: dict 列表 id/month/department/kwh/grid_factor。返回 dict 方案。"""
 certs=list(certificates)
 rep_ids=[r['id'] for r in reports];cert_ids=[c['id'] for c in certs]
 ri={rid:i for i,rid in enumerate(rep_ids)};ci={cid:len(rep_ids)+i for i,cid in enumerate(cert_ids)}
 s=len(rep_ids)+len(certs);t=s+1;m=MinCostMaxFlow(t+1)
 edge_refs={}
 for r in reports:m.add_edge(s,ri[r['id']],r['kwh'],0)
 for c in certs:
  u=ci[c['id']]
  for r in reports:
   if c['month']==r['month'] and c['department']==r['department']:
    cost=float(c['factor'])-float(r['grid_factor'])
    ref=m.add_edge(ri[r['id']],u,min(c['kwh_remaining'],r['kwh']),cost,(c['id'],r['id']))
    edge_refs[(c['id'],r['id'])]=ref
  m.add_edge(u,t,c['kwh_remaining'],0)
 flow,cost=m.solve(s,t)
 allocations=[]
 for (cid,rid),ref in edge_refs.items():
  reverse=m.g[ref.to][ref.rev]
  used=reverse.cap
  if used>0:allocations.append({'certificate_id':cid,'report_id':rid,'kwh':used})
 covered=sum(a['kwh'] for a in allocations)
 total_kwh=sum(r['kwh'] for r in reports)
 grid={r['id']:r['grid_factor'] for r in reports}
 cert_factor={c['id']:c['factor'] for c in certs}
 emission=sum(a['kwh']*cert_factor[a['certificate_id']] for a in allocations)
 emission+=sum((r['kwh']-sum(a['kwh'] for a in allocations if a['report_id']==r['id']))*r['grid_factor'] for r in reports)
 return {'flow':flow,'covered_kwh':covered,'total_kwh':total_kwh,'uncovered_kwh':total_kwh-covered,
  'min_cost_delta':cost,'emissions_kg':emission,'allocations':allocations}
