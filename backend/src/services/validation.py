import math
from src.config.settings import CONFIG
def number(value,name,minimum=0,integer=False):
 if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<minimum or (integer and int(value)!=value): raise ValueError(name+'数值不合法')
 return value
def validate_source(d):
 if not isinstance(d,dict) or set(d)!=set(CONFIG['fields']): raise ValueError('底稿字段必须与业务字段一致')
 for key in ('period','department'):
  if not isinstance(d[key],str) or not 1<=len(d[key])<=100: raise ValueError(key+'不能为空或过长')
 number(d['quantity'],'活动量')
 if not isinstance(d['activity'],str) or not isinstance(d['unit'],str):raise ValueError('活动类型与单位需为文本')
def validate_policy(d):
 if not isinstance(d,dict) or not isinstance(d.get('version'),str) or not 2<=len(d['version'])<=120: raise ValueError('口径版本名不合法')
 if not isinstance(d.get('scope'),str) or len(d['scope'])<5:raise ValueError('必须填写核算范围说明')
 if not isinstance(d.get('factors'),dict) or not d['factors'] or len(d['factors'])>100:raise ValueError('因子不能为空')
 for key,f in d['factors'].items():
  if not isinstance(f,dict) or f.get('unit') not in ('kWh','L','km'):raise ValueError('因子单位只接受kWh/L/km')
  number(f.get('kg_per_unit'),'排放因子')
