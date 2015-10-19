import web

import os
import sys
import json
import time
import uuid
import pymongo
from bson.objectid import ObjectId
import ConfigParser

# reload(sys)
# sys.setdefaultencoding("utf-8")

root_path = os.path.split(os.path.realpath(__file__))[0] + '/'

config_path = root_path + './config.conf'

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
bots_collection = db.bots
configs_collection = db.botconfigs

def close_bot(process_id, with_kill = True):
    if not isinstance(process_id, ObjectId): process_id = ObjectId(process_id)
    process = bots_collection.find_one({'_id': process_id})
    if 'qrcode_file_path' in process and os.path.isfile(process['qrcode_file_path']): os.remove(process['qrcode_file_path'])
    if 'config_file_path' in process and os.path.isfile(process['config_file_path']): os.remove(process['config_file_path'])
    bots_collection.update_one({'_id': process_id}, {'$set': {'status': 'offline'}})
    if with_kill: os.system('kill %d' % process['pid'])

urls = (
    '/', 'Index',
    '/status', 'Status',
    '/launch', 'Launch',
    '/shutdown', 'Shutdown',
    '/gnamelist', 'Gnamelist',
    '/config', 'Config'
)

class Index:
    def GET(self):
        return 'index'
    def POST(self):
        inputdata = web.input()
        return inputdata.t

class Status:
    def GET(self):
        return json.dumps([{
            '_id': str(item['_id']),
            'account': item['account'] if 'account' in item else None,
            'qrcode_url': item['qrcode_url'] if 'qrcode_url' in item else None,
            'status': item['status']
        } for item in bots_collection.find({'status': {'$ne': 'offline'}})])

class Launch:
    def GET(self):
        _uuid = str(uuid.uuid1())
        config_file_url = '/static/game_config/{0}.json'.format(_uuid)
        qr_code_file_url = '/static/qr_code/{0}.jpg'.format(_uuid)
        config_file_path = os.path.realpath(root_path + './' + config_file_url)
        qrcode_file_path = os.path.realpath(root_path + './' + qr_code_file_url)
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
                process_record = bots_collection.find_one({"uuid": _uuid})
                if process_record: break
            if process_record:
                # os.system('python {0} -c {1} -q {2}'.format(qqbot_path, config_file_path, qrcode_file_path))
                bot_params['config_path'] = config_file_path
                bot_params['qrcode_path'] = qrcode_file_path
                bot_params['debug'] = False
                bot_params['login_retry_time'] = 1
                try:
                    (bot, bot_handler) = bot_launch(bot_params)
                    print "login finished, bot id: ", str(process_record['_id'])
                    if not bot is None and not bot_handler is None:
                        config_record = configs_collection.find_one({'account': bot.account})
                        if config_record:
                            config_file = open(config_file_path, 'r')
                            config_obj = json.load(config_file)
                            config_file.close()
                            if isinstance(config_record['admins'], list): config_obj['default']['admin_qq'] = config_record['admins']
                            if isinstance(config_record['gcodes'], list): config_obj['default']['admin_gcodes'] = config_record['gcodes']
                            config_file = open(config_file_path, 'w')
                            config_obj = json.dump(config_obj, config_file, indent = 4)
                            config_file.close()
                        gnamelist = bot.get_groupnames()
                        bots_collection.update_one({'_id': process_record['_id']}, {'$set': {
                            'gnames': gnamelist,
                            'account': bot.account,
                            'status': 'online',
                            'qrcode_url': None
                        }})
                        bot_loop(bot, bot_handler)
                except Exception, e:
                    print "bot error, bot id: ", str(process_record['_id'])
                    print e
                print "[CLOSE] bot id: ", str(process_record['_id'])
                close_bot(process_record['_id'])
            else:
                os.system('kill %d' % cpid)
        else:
            _id = bots_collection.insert({
                "uuid": _uuid,
                "pid": pid,
                "config_url": config_file_url,
                "qrcode_url": qr_code_file_url,
                "config_file_path": config_file_path,
                "qrcode_file_path": qr_code_file_url,
                "status": "login"
            })
            return json.dumps({
                "_id": str(_id),
                "config_url": config_file_url, 
                "qrcode_url": qr_code_file_url
            })

class Shutdown:
    def GET(self):
        inputdata = web.input()
        close_bot(inputdata.id)
        return json.dumps({'status': 0})

class Gnamelist:
    def GET(self):
        inputdata = web.input()
        process_record = bots_collection.find_one({'_id': ObjectId(inputdata.id), 'account': {'$exists': True}})
        gnamelist = None
        if process_record and 'gnames' in process_record and isinstance(process_record['gnames'], list):
            gnamelist = process_record['gnames']
        else:
            iter_time_limit = 60
            for i in range(0, iter_time_limit):
                process_record = bots_collection.find_one({'_id': ObjectId(inputdata.id), 'account': {'$exists': True}})
                if process_record and 'gnames' in process_record and isinstance(process_record['gnames'], list):
                    gnamelist = process_record['gnames']
                    break
                if i < iter_time_limit: time.sleep(1)
        if gnamelist: return json.dumps({'status': 0, 'data': gnamelist})
        else: return json.dumps({'status': 1})

class Config:
    def GET(self):
        inputdata = web.input()
        process_record = bots_collection.find_one({'_id': ObjectId(inputdata.id), 'account': {'$exists': True}})
        config_file_path = None
        if process_record and 'config_file_path' in process_record:
            config_file_path = process_record['config_file_path']
        else:
            iter_time_limit = 60
            for i in range(0, iter_time_limit):
                process_record = bots_collection.find_one({'_id': ObjectId(inputdata.id), 'account': {'$exists': True}})
                if process_record and 'config_file_path' in process_record:
                    config_file_path = process_record['config_file_path']
                    break
                if i < iter_time_limit: time.sleep(1)
        if config_file_path:
            config_file_obj = open(config_file_path)
            config_obj = json.load(config_file_obj)
            config_file_obj.close()
            return json.dumps({'status': 0, 'data': {'admins': config_obj['default']['admin_qq'], 'gcodes': config_obj['default']['admin_gcodes']}})
        else:
            return json.dumps({'status': 1})
    def POST(self):
        inputdata = web.input()
        rawdata = json.loads(web.data())
        process_record = bots_collection.find_one({'_id': ObjectId(inputdata.id)})
        if not process_record: return json.dumps({'status': 1})
        config_file_path = process_record['config_file_path']
        config_file_obj = open(config_file_path)
        config_obj = json.load(config_file_obj)
        config_file_obj.close()
        if 'admins' in rawdata and isinstance(rawdata['admins'], list): config_obj['default']['admin_qq'] = rawdata['admins']
        if 'gcodes' in rawdata and isinstance(rawdata['gcodes'], list): config_obj['default']['admin_gcodes'] = rawdata['gcodes']
        f = open(config_file_path, 'w')
        json.dump(config_obj, f, indent = 4)
        configs_collection.update({"account": process_record["account"]}, {"account": process_record["account"], "admins": config_obj['default']['admin_qq'], "gcodes": config_obj['default']['admin_gcodes']}, upsert=True)
        return json.dumps({'status': 0})

if __name__ == '__main__':
    for item in bots_collection.find({'status': {'$ne': 'offline'}}):
        close_bot(item['_id'])
    app = web.application(urls, globals())
    app.run()