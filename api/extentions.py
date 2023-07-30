from sqlmodel import create_engine
from starlette.config import Config
import json
import redis

config = Config('.env')
DATABASE = config('DATABASE', default='sqlite:///fortify.db')
AUTH_KEY = config('AUTH_KEY')
API_PORT = config('API_PORT', cast=int, default=8000)
engine = create_engine(DATABASE)
redis_client = redis.StrictRedis(host='0.0.0.0', port=4323)

def realod_singbox():
    pass

def import_inbound(inbound_dict):
    with open('singbox/config.json', 'r') as config:
        json_config = json.loads(config.read())
        json_config['inbounds'].append(inbound_dict)
        open('singbox/config.json', 'w').write(json.dumps(json_config, indent=2))

def export_inbound(inbound_tag: str):
    with open('singbox/config.json', 'r') as config:
        json_config = json.loads(config.read())
        for index, inbound in enumerate(json_config['inbounds']):
            if inbound['tag'] == inbound_tag:
                json_config['inbounds'].pop(index)
                break
        open('singbox/config.json', 'w').write(json.dumps(json_config, indent=2))
