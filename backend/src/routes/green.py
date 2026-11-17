from fastapi import APIRouter,Depends,HTTPException
from src.config.database import database
from src.controllers.auth import current,editor
from src.models.green import GreenCertificate,GreenReport,GreenReservation,GreenLedger
from src.schemas.green_requests import CertificateInput,GreenReportInput
from src.services import green
from src.services.green_queue import push
from src.utils.serialize import row
router=APIRouter()
def _report_row(r,db):
 data=row(r)
 data['reservations']=[row(x) for x in db.query(GreenReservation).filter_by(report_id=r.id).order_by(GreenReservation.id).all()]
 return data
@router.get('/green/certificates')
def certificates(db=Depends(database),u=Depends(current)):
 return [row(x) for x in db.query(GreenCertificate).order_by(GreenCertificate.id).all()]
@router.post('/green/certificates')
def add_certificate(b:CertificateInput,db=Depends(database),u=Depends(editor)):
 return row(green.register_certificate(db,u,b))
@router.get('/green/reports')
def reports(db=Depends(database),u=Depends(current)):
 return [_report_row(x,db) for x in db.query(GreenReport).order_by(GreenReport.id.desc()).all()]
@router.post('/green/reports')
def add_report(b:GreenReportInput,db=Depends(database),u=Depends(editor)):
 return row(green.create_report(db,u,b))
@router.get('/green/reports/{rid}')
def report_detail(rid:int,db=Depends(database),u=Depends(current)):
 obj=db.get(GreenReport,rid)
 if not obj:raise HTTPException(404,'用电报告不存在')
 return _report_row(obj,db)
@router.post('/green/reports/{rid}/enqueue')
def enqueue(rid:int,db=Depends(database),u=Depends(editor)):
 obj=green.enqueue(db,u,rid)
 push({'report_id':obj.id,'attempt':obj.attempt})
 return _report_row(obj,db)
@router.post('/green/reports/{rid}/cancel')
def cancel(rid:int,db=Depends(database),u=Depends(editor)):
 return _report_row(green.cancel(db,u,rid),db)
@router.get('/green/ledger')
def ledger(db=Depends(database),u=Depends(current)):
 return [row(x) for x in db.query(GreenLedger).order_by(GreenLedger.id.desc()).limit(300).all()]
@router.get('/green/conservation')
def conservation(db=Depends(database),u=Depends(current)):
 return green.conservation(db)
