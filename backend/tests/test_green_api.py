import os,tempfile
_TMP=tempfile.mkdtemp(prefix='green-api-')
os.environ['DATABASE_URL']='sqlite:///'+os.path.join(_TMP,'api.db')
os.environ['PROJECT_JSON']=os.path.join(_TMP,'missing.json')
import unittest
from fastapi.testclient import TestClient
from src.main import app
from src.config.database import Base,engine,Session
from src.models.identity import User
from src.utils.security import password_hash
Base.metadata.create_all(engine)
with Session() as db:
 if not db.query(User).filter_by(email='admin@demo.local').first():
  db.add(User(email='admin@demo.local',role='admin',password=password_hash('Demo2026!')));db.commit()
class GreenApiTest(unittest.TestCase):
 def setUp(self):self.c=TestClient(app)
 def token(self):
  r=self.c.post('/auth/login',json={'email':'admin@demo.local','password':'Demo2026!'})
  self.assertEqual(r.status_code,200);return {'Authorization':'Bearer '+r.json()['token']}
 def test_full_flow_and_trace(self):
  h=self.token()
  r=self.c.post('/green/certificates',headers=h,json={'code':'GC-1','month':'2026-11','department':'材料室',
   'factor':0.05,'kwh_total':100});self.assertEqual(r.status_code,200,r.text);cid=r.json()['id']
  self.assertEqual(r.json()['kwh_remaining'],100)
  r=self.c.post('/green/certificates',headers=h,json={'code':'GC-2','month':'2026-10','department':'材料室',
   'factor':0.2,'kwh_total':30});self.assertEqual(r.status_code,200)
  r=self.c.post('/green/reports',headers=h,json={'name':'十一月材料室用电','month':'2026-11','department':'材料室',
   'kwh':120,'grid_factor':0.57});self.assertEqual(r.status_code,200,r.text);rid=r.json()['id']
  r=self.c.post(f'/green/reports/{rid}/enqueue',headers=h,json={});self.assertEqual(r.status_code,200,r.text)
  self.assertEqual(r.json()['status'],'queued');self.assertEqual(r.json()['attempt'],1)
  r=self.c.get('/green/certificates',headers=h);self.assertEqual(r.json()[0]['kwh_remaining'],0)
  r=self.c.post(f'/green/reports/{rid}/cancel',headers=h,json={});self.assertEqual(r.status_code,200)
  self.assertEqual(r.json()['status'],'draft')
  r=self.c.get('/green/certificates',headers=h);self.assertEqual(r.json()[0]['kwh_remaining'],100)
  r=self.c.post(f'/green/reports/{rid}/enqueue',headers=h,json={});self.assertEqual(r.status_code,200)
  r=self.c.get('/green/conservation',headers=h);self.assertTrue(r.json()['ok'])
  r=self.c.get('/green/ledger',headers=h)
  actions=[x['action'] for x in r.json()];self.assertIn('reserve',actions);self.assertIn('release',actions)
 def test_validation_and_unknown(self):
  h=self.token()
  r=self.c.post('/green/certificates',headers=h,json={'code':'BAD','month':'2026-11','department':'X',
   'factor':0.1,'kwh_total':12.5});self.assertEqual(r.status_code,422)
  r=self.c.post('/green/reports/99999/enqueue',headers=h,json={});self.assertEqual(r.status_code,404)
if __name__=='__main__':unittest.main()
