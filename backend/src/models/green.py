from sqlalchemy import Column,Integer,String,JSON,Float,Text,UniqueConstraint
from src.config.database import Base
class GreenCertificate(Base):
 __tablename__='green_certificates'
 id=Column(Integer,primary_key=True); code=Column(String(120),unique=True); month=Column(String(7)); department=Column(String(100)); factor=Column(Float); kwh_total=Column(Float); kwh_remaining=Column(Float); created=Column(Float)
class GreenReport(Base):
 __tablename__='green_reports'
 id=Column(Integer,primary_key=True); name=Column(String(120)); month=Column(String(7)); department=Column(String(100)); kwh=Column(Float); grid_factor=Column(Float); status=Column(String(20),default='draft'); attempt=Column(Integer,default=0); frozen=Column(JSON); result=Column(JSON); error=Column(Text); created=Column(Float); updated=Column(Float); heartbeat=Column(Float)
class GreenReservation(Base):
 __tablename__='green_reservations'
 id=Column(Integer,primary_key=True); report_id=Column(Integer,index=True); attempt=Column(Integer); certificate_id=Column(Integer,index=True); kwh=Column(Float); created=Column(Float)
 __table_args__=(UniqueConstraint('report_id','attempt','certificate_id',name='uq_green_reservation'),)
class GreenLedger(Base):
 __tablename__='green_ledger'
 id=Column(Integer,primary_key=True); certificate_id=Column(Integer,index=True); report_id=Column(Integer); action=Column(String(30)); kwh_delta=Column(Float); balance_after=Column(Float); attempt=Column(Integer); created=Column(Float)
