from decimal import Decimal
from collections import defaultdict
from src.services.validation import validate_source,validate_policy
CONVERSIONS={('MWh','kWh'):1000,('kWh','kWh'):1,('L','L'):1,('mL','L'):0.001,('km','km'):1,('m','km'):0.001}
def emissions(activity,quantity,unit,factors):
 if activity not in factors:raise ValueError('缺少活动因子：'+activity)
 factor=factors[activity];key=(unit,factor['unit'])
 if key not in CONVERSIONS:raise ValueError('单位无法转换：'+unit+' → '+factor['unit'])
 qty=Decimal(str(quantity))*Decimal(str(CONVERSIONS[key]));kg=qty*Decimal(str(factor['kg_per_unit']))
 return qty,kg
def calculate(sources,policy):
 validate_policy(policy);pivot=defaultdict(lambda:[Decimal(0),Decimal(0),0]);rows=[]
 for s in sources:
  validate_source(s);qty,kg=emissions(s['activity'],s['quantity'],s['unit'],policy['factors']);factor=policy['factors'][s['activity']];k=(s['period'],s['department'],s['activity'],factor['unit']);p=pivot[k];p[0]+=qty;p[1]+=kg;p[2]+=1
 for (period,dept,activity,unit),(qty,kg,count) in sorted(pivot.items()):rows.append({'月份':period,'部门':dept,'活动':activity,'统一单位':unit,'统一活动量':float(qty),'因子kg每单位':policy['factors'][activity]['kg_per_unit'],'排放kgCO2e':float(kg),'记录数':count})
 return {'summary':{'活动记录数':len(sources),'核算kgCO2e':float(sum(p[1] for p in pivot.values())),'因子版本':policy['version']},'rows':rows,'method':'先按显式维度一致转换表转换活动量，再用Decimal活动量×冻结因子；按月份×部门×活动透视。缺活动因子或不兼容单位即失败，不以0替代。','warnings':[policy['scope']]}
