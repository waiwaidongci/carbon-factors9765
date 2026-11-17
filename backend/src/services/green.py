"""绿电凭证用电核算服务。

额度生命周期：排队即预占（reserve，余额立即减少）→ 计算成功核销（consume，余额不变）；
失败/取消/取消预占释放（release，余额还原）。余额变动全部走 green_ledger 流水，保证可守恒核对。
并发：跨库写锁串行化排队事务（PG 用 pg_advisory_xact_lock，SQLite 用进程内 RLock），
行版本用 report.attempt 做围栏，旧执行者晚到无法重复扣额。
"""
import os,threading,time,hashlib,json
from fastapi import HTTPException
from sqlalchemy import text
from src.config.database import engine
from src.models.green import GreenCertificate,GreenReport,GreenReservation,GreenLedger
from src.services import mcmf
from src.services.audit import log
_TTL=30.0
_local_lock=threading.RLock()
def ttl():
 try:return float(os.environ.get('GREEN_HEARTBEAT_TTL','30'))
 except ValueError:return _TTL
def _xact_lock(db):
 if engine.dialect.name=='postgresql':db.execute(text('SELECT pg_advisory_xact_lock(873261)'))
 else:_local_lock.acquire()
def _release_lock():
 if engine.dialect.name!='postgresql':_local_lock.release()
def _whole_kwh(value,label):
 if float(value)!=int(value):raise HTTPException(422,label+'须为整数 kWh（凭证按整额登记与核销）')
 return int(value)
def _kwh(value):
 return int(round(float(value)))
def _ledger(db,certificate_id,report_id,action,delta,balance_after,attempt):
 db.add(GreenLedger(certificate_id=certificate_id,report_id=report_id,action=action,kwh_delta=delta,
  balance_after=balance_after,attempt=attempt,created=time.time()))
def register_certificate(db,user,body):
 if db.query(GreenCertificate).filter_by(code=body.code).first():raise HTTPException(409,'凭证编号已存在')
 now=time.time()
 total=_whole_kwh(body.kwh_total,'凭证电量')
 obj=GreenCertificate(code=body.code,month=body.month,department=body.department,factor=body.factor,
  kwh_total=total,kwh_remaining=total,created=now)
 db.add(obj);db.flush()
 _ledger(db,obj.id,None,'register',total,obj.kwh_remaining,0)
 log(db,user.email,'green.cert.register',body.code);db.commit();return obj
def create_report(db,user,body):
 now=time.time()
 kwh=_whole_kwh(body.kwh,'用电电量')
 obj=GreenReport(name=body.name,month=body.month,department=body.department,kwh=kwh,
  grid_factor=body.grid_factor,status='draft',attempt=0,created=now,updated=now)
 db.add(obj);log(db,user.email,'green.report.create',body.name);db.commit();return obj
def _cert_payload(c):return {'id':c.id,'code':c.code,'month':c.month,'department':c.department,'factor':c.factor,
 'kwh_remaining':c.kwh_remaining}
def _release(db,report,attempt):
 for rv in db.query(GreenReservation).filter_by(report_id=report.id,attempt=attempt).all():
  cert=db.get(GreenCertificate,rv.certificate_id)
  cert.kwh_remaining+=rv.kwh
  _ledger(db,cert.id,report.id,'release',rv.kwh,cert.kwh_remaining,attempt)
  db.delete(rv)
def enqueue(db,user,report_id):
 try:_xact_lock(db)
 except Exception:_release_lock();raise
 try:
  report=db.get(GreenReport,report_id)
  if not report:raise HTTPException(404,'用电报告不存在')
  if report.status in ('queued','running'):raise HTTPException(409,'报告已在排队或计算中')
  if report.status=='completed':raise HTTPException(409,'已完成报告与交付保留原分配，不可重新核算')
  attempt=report.attempt+1
  certs=db.query(GreenCertificate).order_by(GreenCertificate.id).all()
  sol=mcmf.plan([_cert_payload(c) for c in certs],[{'id':report.id,'month':report.month,
   'department':report.department,'kwh':report.kwh,'grid_factor':report.grid_factor}])
  now=time.time()
  for a in sol['allocations']:
   cert=db.get(GreenCertificate,a['certificate_id']);kwh=_kwh(a['kwh'])
   if cert.kwh_remaining+1e-9<kwh:raise HTTPException(409,'凭证余额并发变化，请重试')
   cert.kwh_remaining-=kwh
   db.add(GreenReservation(report_id=report.id,attempt=attempt,certificate_id=cert.id,kwh=kwh,created=now))
   _ledger(db,cert.id,report.id,'reserve',-kwh,cert.kwh_remaining,attempt)
  frozen={'month':report.month,'department':report.department,'kwh':report.kwh,
   'grid_factor':report.grid_factor,'plan':sol,
   'certificates':[{'id':c.id,'code':c.code,'factor':c.factor} for c in certs]}
  report.attempt=attempt;report.status='queued';report.frozen=frozen;report.error=None;report.updated=now
  checksum=hashlib.sha256(json.dumps(frozen,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
  frozen['checksum']=checksum
  db.flush();log(db,user.email,'green.report.enqueue',f'{report.id}#{attempt}')
  db.commit();return report
 finally:_release_lock()
def cancel(db,user,report_id):
 try:_xact_lock(db)
 except Exception:_release_lock();raise
 try:
  report=db.get(GreenReport,report_id)
  if not report:raise HTTPException(404,'用电报告不存在')
  if report.status not in ('queued','running'):raise HTTPException(409,'仅排队中或计算中的报告可取消')
  attempt=report.attempt
  _release(db,report,attempt)
  report.status='draft';report.updated=time.time()
  log(db,user.email,'green.report.cancel',f'{report_id}#{attempt}');db.commit();return report
 finally:_release_lock()
def claim(db,report_id,attempt):
 """worker 认领：条件更新做围栏，仅当 attempt 匹配且仍在排队时成功。"""
 now=time.time()
 updated=db.query(GreenReport).filter(GreenReport.id==report_id,GreenReport.attempt==attempt,
  GreenReport.status=='queued').update({GreenReport.status:'running',GreenReport.heartbeat:now,
  GreenReport.updated:now})
 db.commit();return updated==1
def heartbeat(db,report_id,attempt):
 updated=db.query(GreenReport).filter(GreenReport.id==report_id,GreenReport.attempt==attempt,
  GreenReport.status=='running').update({GreenReport.heartbeat:time.time()})
 db.commit();return updated==1
def run_report(db,report_id,attempt,fail_predicate=None):
 """worker 执行。成功核销（余额不变，仅落 consume 流水与结果）；失败释放并置失败态。"""
 report=db.get(GreenReport,report_id)
 if not report or report.attempt!=attempt or report.status!='running':return False
 report.heartbeat=time.time()
 reservations=db.query(GreenReservation).filter_by(report_id=report_id,attempt=attempt).all()
 plan_ids={(a['certificate_id'],a['report_id']):a['kwh'] for a in report.frozen['plan']['allocations']}
 for rv in reservations:
  if plan_ids.get((rv.certificate_id,report_id))!=rv.kwh:
   return _fail(db,report,attempt,'冻结分配与预占记录不一致')
  cert=db.get(GreenCertificate,rv.certificate_id)
  if cert is None or cert.kwh_remaining<-1e-9:return _fail(db,report,attempt,'凭证余额异常，拒绝核销')
  reserved=sum(x.kwh for x in db.query(GreenReservation).filter_by(certificate_id=cert.id).all())
  consumed=sum(a['kwh'] for r in db.query(GreenReport).filter_by(status='completed').all()
   for a in r.result['allocations'] if a['certificate_id']==cert.id)
  if abs(cert.kwh_total-cert.kwh_remaining-reserved-consumed)>1e-4:
   return _fail(db,report,attempt,f'凭证{cert.code}额度守恒校验失败')
 if fail_predicate is not None and fail_predicate(report):
  return _fail(db,report,attempt,'注入的计算失败')
 covered=sum(rv.kwh for rv in reservations)
 allocations=[{'certificate_id':rv.certificate_id,'report_id':report_id,'kwh':_kwh(rv.kwh),
  'certificate_code':db.get(GreenCertificate,rv.certificate_id).code,
  'factor':db.get(GreenCertificate,rv.certificate_id).factor} for rv in reservations]
 emission_cert=sum(a['kwh']*a['factor'] for a in allocations)
 uncovered=report.kwh-covered;grid_kg=uncovered*report.grid_factor
 for rv in reservations:
  cert=db.get(GreenCertificate,rv.certificate_id)
  _ledger(db,cert.id,report_id,'consume',0,cert.kwh_remaining,attempt)
 for rv in reservations:db.delete(rv)
 result={'covered_kwh':covered,'uncovered_kwh':uncovered,'grid_kwh':uncovered,
  'emissions_cert_kg':emission_cert,'emissions_grid_kg':grid_kg,'emissions_total_kg':emission_cert+grid_kg,
  'baseline_grid_kg':report.kwh*report.grid_factor,
  'saved_kg':report.kwh*report.grid_factor-(emission_cert+grid_kg),'allocations':allocations}
 report.status='completed';report.result=result;report.error=None;report.updated=time.time()
 log(db,'worker','green.report.complete',f'{report_id}#{attempt}');db.commit();return True
def _fail(db,report,attempt,reason):
 _release(db,report,attempt)
 report.status='failed';report.error=reason;report.updated=time.time()
 log(db,'worker','green.report.fail',f'{report.id}#{attempt}:{reason}');db.commit();return False
def recover_stale(db,now=None):
 """看门狗：认领后崩溃（running 且心跳超时）的任务，释放旧预占并按当前余额重新排队。"""
 now=now or time.time();recovered=[]
 try:_xact_lock(db)
 except Exception:_release_lock();raise
 try:
  stale=db.query(GreenReport).filter(GreenReport.status=='running',
   GreenReport.heartbeat!=None,GreenReport.heartbeat<now-ttl()).all()
  for report in stale:
   old=report.attempt
   _release(db,report,old)
   certs=db.query(GreenCertificate).order_by(GreenCertificate.id).all()
   sol=mcmf.plan([_cert_payload(c) for c in certs],[{'id':report.id,'month':report.month,
    'department':report.department,'kwh':report.kwh,'grid_factor':report.grid_factor}])
   attempt=old+1
   for a in sol['allocations']:
    cert=db.get(GreenCertificate,a['certificate_id']);kwh=_kwh(a['kwh'])
    cert.kwh_remaining-=kwh
    db.add(GreenReservation(report_id=report.id,attempt=attempt,certificate_id=cert.id,kwh=kwh,created=now))
    _ledger(db,cert.id,report.id,'reserve',-kwh,cert.kwh_remaining,attempt)
   frozen={'month':report.month,'department':report.department,'kwh':report.kwh,
    'grid_factor':report.grid_factor,'plan':sol,
    'certificates':[{'id':c.id,'code':c.code,'factor':c.factor} for c in certs]}
   frozen['checksum']=hashlib.sha256(json.dumps(frozen,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
   report.attempt=attempt;report.status='queued';report.frozen=frozen;report.error='崩溃恢复：已重新预占';report.heartbeat=None;report.updated=now
   log(db,'watchdog','green.report.recover',f'{report.id}#{old}->#{attempt}');recovered.append(report.id)
  db.commit();return recovered
 finally:_release_lock()
def conservation(db):
 """额度守恒核对：每凭证 total - remaining == 未核销预占 + 已核销分配。"""
 problems=[]
 for cert in db.query(GreenCertificate).all():
  reserved=sum(rv.kwh for rv in db.query(GreenReservation).filter_by(certificate_id=cert.id).all())
  consumed=0
  for r in db.query(GreenReport).filter_by(status='completed').all():
   consumed+=sum(a['kwh'] for a in r.result['allocations'] if a['certificate_id']==cert.id)
  if abs((cert.kwh_total-cert.kwh_remaining)-(reserved+consumed))>1e-4:problems.append(cert.id)
 return {'ok':not problems,'problem_certificate_ids':problems}
