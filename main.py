import web

import os
import sys
import json
import time
import uuid
import pymongo
from bson.objectid import ObjectId
import ConfigParser

config_path = './config.conf'

config = ConfigParser.ConfigParser()
config.read(config_path)

mongo_host = config.get('mongodb', 'host')
mongo_port = int(config.get('mongodb', 'port'))
mongo_username = config.get('mongodb', 'username')
mongo_password = config.get('mongodb', 'password')
mongo_dbname = config.get('mongodb', 'db')

# qqbot_path = config.get('qqbot', 'path') + '/main.py'
sys.path.append(config.get('qqbot', 'path'))
from bot_launch import bot_params, bot_launch, bot_loop

mongo_uri = "mongodb://{0}:{1}@{2}:{3}".format(mongo_username, mongo_password, mongo_host, mongo_port)
mongo_client = pymongo.MongoClient(mongo_uri)
db = mongo_client[mongo_dbname]

root_path = os.path.split(os.path.realpath(__file__))[0] + '/'

def close_bot(process_id, with_kill = True):
    if not isinstance(process_id, ObjectId): process_id = ObjectId(process_id)
    process = db.bots.find_one({'_id': process_id})
    if os.path.isfile(process['qrcode_file_path']): os.remove(process['qrcode_file_path'])
    if os.path.isfile(process['config_file_path']): os.remove(process['config_file_path'])
    db.bots.update_one({'_id': process_id}, {'$set': {'status': 'offline'}})
    if with_kill: os.system('kill %d' % process['pid'])

urls = (
    '/', 'Index',
    '/launch', 'Launch',
    '/config', 'Config'
)

class Index:
    def GET(self):
        return 'index'

class Launch:
    def GET(self):
        _uuid = str(uuid.uuid1())
        config_file_url = '/game_config/{0}.json'.format(_uuid)
        qr_code_file_url = '/qr_code/{0}.jpg'.format(_uuid)
        config_file_path = os.path.realpath(root_path + './static' + config_file_url)
        qrcode_file_path = os.path.realpath(root_path + './static' + qr_code_file_url)
        config_tpl_path = os.path.realpath(root_path + './static/game_config_tpl.json')
        config_file = open(config_file_path, 'w')
        config_tpl_file = open(config_tpl_path, 'r')
        config_file.write(config_tpl_file.read())
        config_file.close()
        config_tpl_file.close()
        pid = os.fork()
        if pid == 0:
            # child process
            cpid = os.getpid()
            process_record = None
            for i in range(0,10):
                time.sleep(1)
                print "try ", i
                process_record = db.bots.find_one({"uuid": _uuid})
                if process_record: break
            if process_record:
                # os.system('python {0} -c {1} -q {2}'.format(qqbot_path, config_file_path, qrcode_file_path))
                bot_params['config_path'] = config_file_path
                bot_params['qrcode_path'] = qrcode_file_path
                bot_params['debug'] = True
                (bot, bot_handler) = bot_launch(bot_params)
                gnamelist = bot.get_groupnames()
                db.update_one({'_id': process_record['_id']})
                close_bot(process_record['_id'])
            else:
                print "no record"
        else:
            _id = db.bots.insert({
                "uuid": _uuid,
                "pid": pid,
                "config_file_path": config_file_path,
                "qrcode_file_path": qr_code_file_url,
                "status": "online"
            })
            return json.dumps({
                "_id": str(_id),
                "config_url": config_file_url, 
                "qrcode_url": qr_code_file_url
            })

if __name__ == '__main__':
    app = web.application(urls, globals())
    app.run()