import time,traceback
from pathlib import Path
import redis
from src.config.database import Base,engine,Session
from src.config.settings import REDIS_URL
from src.models import identity,source,run,green
from src.models.run import Run
from src.models.green import GreenReport
from src.services.calculation import calculate
from src.services.delivery import tick
from src.services import green as green_service
from src.services.green_queue import pop as green_pop
Base.metadata.create_all(engine)
r=redis.Redis.from_url(REDIS_URL,socket_connect_timeout=2,socket_timeout=2)
def run_legacy(item):
 with Session() as db:
  job=db.get(Run,int(item))
  if job and job.status=='queued':
   job.status='running';db.commit()
   try:job.result=calculate(job.snapshot['sources'],job.snapshot['policy']);job.status='completed'
   except Exception as exc:job.status='failed';job.error=str(exc);traceback.print_exc()
   db.commit()
def run_green(payload):
 rid=int(payload['report_id']);attempt=int(payload['attempt'])
 with Session() as db:
  if not green_service.claim(db,rid,attempt):return
 ok=False
 try:
  with Session() as db:ok=green_service.run_report(db,rid,attempt)
 except Exception:
  traceback.print_exc();ok=False
 if not ok:
  with Session() as db:
   obj=db.get(GreenReport,rid)
   if obj and obj.attempt==attempt and obj.status=='running':green_service._fail(db,obj,attempt,'worker异常退出')
def main():
 while True:
  Path('/tmp/worker-heartbeat').write_text(str(time.time()))
  try:
   try:item=r.lpop('report-jobs')
   except Exception:item=None
   if item:run_legacy(item)
   payload=green_pop()
   if payload:run_green(payload)
   else:
    with Session() as db:
     q=db.query(GreenReport).filter_by(status='queued').order_by(GreenReport.id).first()
     if q:run_green({'report_id':q.id,'attempt':q.attempt})
     green_service.recover_stale(db)
   with Session() as db:tick(db)
  except Exception:traceback.print_exc()
  time.sleep(1)
if __name__=='__main__':main()
