from sqlalchemy import create_engine,event
from sqlalchemy.orm import sessionmaker,DeclarativeBase
from src.config.settings import DATABASE_URL
class Base(DeclarativeBase): pass
_is_sqlite=DATABASE_URL.startswith('sqlite')
_engine_kw={} if not _is_sqlite else {'connect_args':{'check_same_thread':False},'isolation_level':None}
engine=create_engine(DATABASE_URL,pool_pre_ping=True,**_engine_kw)
if _is_sqlite:
 @event.listens_for(engine,'connect')
 def _sqlite_pragmas(dbapi_conn,_):
  cur=dbapi_conn.cursor();cur.execute('PRAGMA journal_mode=WAL');cur.execute('PRAGMA foreign_keys=ON');cur.close()
 @event.listens_for(engine,'begin')
 def _sqlite_immediate(conn):
  # 写事务立即取库级写锁，配合服务层 RLock 实现排队事务的可串行化
  conn.connection.dbapi_connection.execute('BEGIN IMMEDIATE')
Session=sessionmaker(bind=engine,expire_on_commit=False)
def database():
 with Session() as db: yield db
