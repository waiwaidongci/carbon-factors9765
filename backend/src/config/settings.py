import os,json
from pathlib import Path
_cfg=Path(os.environ.get('PROJECT_JSON','/app/project.json'))
CONFIG=json.loads(_cfg.read_text()) if _cfg.exists() else {'title':'绿电凭证用电核算','slug':'green-power'}
DATABASE_URL=os.environ.get('DATABASE_URL','sqlite:///./green_local.db')
REDIS_URL=os.getenv('REDIS_URL','redis://localhost:6379/0')
SECRET=os.environ.get('JWT_SECRET','local-dev-secret-change-me')
