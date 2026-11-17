import json,logging
import redis
from src.config.settings import REDIS_URL
KEY='green-jobs'
_client=None
def client():
 global _client
 if _client is None:_client=redis.Redis.from_url(REDIS_URL,socket_connect_timeout=2,socket_timeout=2)
 return _client
def push(payload):
 try:client().rpush(KEY,json.dumps(payload));return True
 except Exception:logging.getLogger('green').warning('Redis不可用，改用数据库轮询');return False
def pop():
 try:
  raw=client().lpop(KEY)
  return json.loads(raw) if raw else None
 except Exception:return None
