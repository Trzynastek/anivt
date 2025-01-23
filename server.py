from flask import Flask, request, send_from_directory
from flask_cors import CORS
import feedparser
import asyncio
from torrentp import TorrentDownloader as downloader
import ffmpeg
import urllib.parse
import os
import shlex
import json
import requests
import re
import bencodepy
import hashlib
import base64
import threading
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

queue = []
queueTitles = []
processing = False
past = {}

if not os.path.exists('config.json'):
    with open('config.json', 'w') as f:
        default = {
            "host": "127.0.0.1",
            "port": "7980",
            "cleanup_interval": 3600,
            "full_interval": 1200,
            "partial_interval": 120,
            "remove_after": 86400,
            "rss": [],
            "encoding": {
                "vcodec": "libx264",
                "pix_fmt": "yuv420p",
                "crf": 18,
                "preset": "veryfast",
                "acodec": "aac",
                "threads": 0
            },
            "subtitles_font": "Arial",
            "anilist_cid": None,
            "anilist_secret": None,
            "token": None
        }
        json.dump(default, f, indent=4) 
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

if config['token'] == None:
    print('|')
    print(f'| Authentificate with AniList: https://anilist.co/api/v2/oauth/authorize?client_id={config['anilist_cid']}&redirect_uri=http://{config['host']}:{config['port']}/api/auth&response_type=code')
    print('|')

class dbHandler:
    def __init__(self):
        self.dbf = './public/db.json'
        self.ensureDb()
        self.db = self.load()

    def ensureDb(self):
        if not os.path.exists(self.dbf):
            with open(self.dbf, 'w', encoding='utf-8') as f:
                json.dump({'videos': {}}, f, indent=4)
    
    def load(self):
        with open(self.dbf, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def save(self):
        with open(self.dbf, 'w', encoding='utf-8') as f:
            json.dump(self.db, f, ensure_ascii=False, indent=4)
    
    def update(self, title, key, value):
        self.db['videos'][title][key] = value
        self.save()
    
    def remove(self, title):
        del self.db['videos'][title]
        self.save()
    
    def add(self, title, episode, cover):
        self.db['videos'][title] = {
            "file": None,
            "episode": episode,
            "cover": cover,
            "watched": None,
            "status": "in queue"
        }
        self.save()

    def exists(self, title):
        return title in self.db['videos']
    
    def read(self, title, key):
        return self.db['videos'][title][key]
    
    def dump(self):
        return self.db['videos']

@app.route('/')
@app.route('/<path:file>')
def serve(file='index.html'):
    return send_from_directory('./public', file)

@app.route('/api/auth', methods=['GET'])
def apiAuth():
    code = request.args.get('code')
    res = requests.post(
        'https://anilist.co/api/v2/oauth/token',
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        },
        json = {
            'grant_type': 'authorization_code',
            'client_id': config['anilist_cid'],
            'client_secret': config['anilist_secret'],
            'redirect_uri': f"http://{config['host']}:{config['port']}/api/auth",
            'code': code
        }
    )
    config['token'] = res.json()
    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)
    return '<h1>Authenfificated</h1><h2>You can now close this tab.</h2>', 200

@app.route('/api/watched', methods=['POST'])
def markWatched():
    title = request.json['title']
    if db.exists(title):
        now = str(datetime.now())
        db.update(title, 'watched', now)
    return '', 200

async def getUID():
    query = '{ Viewer { id } }'
    success = False
    while not success:
        res = requests.post(
            'https://graphql.anilist.co',
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {config['token']['access_token']}',
            },
            json = {'query': query}
        )
        if res.status_code == 200:
            success = True
        else:
            await asyncio.sleep(10)
    data = res.json()
    return data['data']['Viewer']['id']

async def getWatching():
    uid = await getUID()
    query = f'{{ MediaListCollection(userId: {uid}, type: ANIME) {{ lists {{ entries {{ progress media {{ title {{ english romaji }} synonyms coverImage {{ large }} episodes }} }} }} }} }}'
    success = False
    while not success:
        res = requests.post(
            'https://graphql.anilist.co',
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {config['token']['access_token']}',
            },
            json = {'query': query}
        )
        if res.status_code == 200:
            success = True
        else:
            await asyncio.sleep(10)
    data = res.json()
    data = data['data']['MediaListCollection']['lists'][3]['entries']
    data = [{
        'progress': item['progress'],
        'title': item['media']['title'],
        'episodes': item['media']['episodes'],
        'cover': item['media']['coverImage']['large'],
        'synonyms': item['media']['synonyms']
    } for item in data]
    return data

# Stollen from https://github.com/DanySK/torrent2magnet 
async def toMagnet(data):
    metadata = bencodepy.decode(data)
    subj = metadata[b'info']
    hashcontents = bencodepy.encode(subj)
    digest = hashlib.sha1(hashcontents).digest()
    b32hash = base64.b32encode(digest).decode()
    return 'magnet:?'\
             + 'xt=urn:btih:' + b32hash\
             + '&dn=' + metadata[b'info'][b'name'].decode()\
             + '&tr=' + metadata[b'announce'].decode()\
             + '&xl=' + str(metadata[b'info'][b'length'])

async def preCheck(title, episode, magnet):
    res = requests.get(magnet)
    data = res.content
    magnet = await toMagnet(data)
    query = urllib.parse.urlparse(magnet).query
    dl = os.getcwd() + '/mkv/' + urllib.parse.parse_qs(query).get('dn', [None])[0]
    file = os.getcwd() + '/mkv/' + f'{title}_[Ep.{episode}].mkv'
    inp = re.sub(r'[^A-Za-z0-9 /\[\].]+', '', file).replace(' ', '_')
    out = inp.replace('.mkv', '.mp4').replace('/mkv/', '/public/mp4/')
    exists = os.path.exists(inp) or os.path.exists(out)
    return (inp, out, exists, magnet, dl)

async def download(title, episode, magnet):
    global processing
    processing = True
    inp, out, exists, magnet, dl = await preCheck(title, episode, magnet)
    if not exists:
        db.update(title, 'status', 'downloading')
        torrent = downloader(magnet, './mkv/', stop_after_download=True)
        await torrent.start_download()
        os.rename(dl, inp)
    if os.path.exists(out):
        db.update(title, 'status', 'ready')
        db.update(title, 'file', out.replace(f'{os.getcwd()}/public/', ''))
        return
    db.update(title, 'status', 'encoding')
    ffmpeg.input(inp).output(
        out,
        vf=f"subtitles={shlex.quote(inp.replace(':', '\\:'))}:force_style='{config['subtitles_font']}'",
        movflags='+faststart',
        **config['encoding']
    ).run(overwrite_output=True)
    os.remove(inp)
    db.update(title, 'status', 'ready')
    db.update(title, 'file', out.replace(f'{os.getcwd()}/public/', ''))
    processing = False

async def check(partial = False):
    global processing
    global queue
    global queueTitles
    global past
    update = False
    if partial:
        for source in config['rss']:
            last = feedparser.parse(source['url'])['entries'][0]
            if len(past) == len(config['rss']):
                if past[source['url']] != last:
                    update = True
            past[source['url']] = last
    if partial and not update:
        return
    for source in config['rss']:
        raw = feedparser.parse(source['url'])['entries']
        feed = []
        for item in raw:
            match = re.match(source['regex'], item['title'])
            if not match:
                continue
            feed.append({
                'title': re.sub(r'\bS(\d+)\b', r'Season \1', match.group(1)),
                'episode': int(match.group(2)),
                'link': item['link']
            })
        watchlist = await getWatching()
        filters = []
        for item in watchlist:
            temp = []
            if item['title'] is not None:
                eng = item['title'].get('english', None)
                rom = item['title'].get('romaji', None)
                
                eng = eng.split(':')[0].strip().lower() if eng else None
                rom = rom.split(':')[0].strip().lower() if rom else None

                temp.append(eng)
                temp.append(rom)
            if item['synonyms'] is not None:
                for item in item['synonyms']:
                    temp.append(item)
            filters.append(temp)
        for item in feed:
            found = False
            for index, subarray in enumerate(filters):
                if found:
                    break
                for title in subarray:
                    if found:
                        break
                    if title is None:
                        continue
                    normTitle = re.sub(r'[^A-Za-z0-9]+', '', title.lower())
                    normItem = re.sub(r'[^A-Za-z0-9]+', '', item['title'].lower())
                    if len(normTitle) == 0 or len(normItem) == 0:
                        continue
                    title = watchlist[index]['title'].get('english', None)
                    if not eng:
                        title = watchlist[index]['title'].get('romaji', None)
                    if normItem in normTitle:
                        found = True
                        if item['episode'] == watchlist[index]['progress'] + 1:
                            entry = {'title': title, 'episode': item['episode'], 'magnet': item['link']}
                            if entry['title'] not in queueTitles:
                                queueTitles.append(entry['title'])
                                queue.append(entry)
                                if not db.exists(title):
                                        db.add(title, item['episode'], watchlist[index]['cover'])
                        elif item['episode'] > watchlist[index]['progress']:
                            query = f'{{ Page {{ media(search: "{title}", type: ANIME) {{ id title {{ romaji }} relations {{ nodes {{ episodes }} }} }} }} }}'
                            res = requests.post(
                                'https://graphql.anilist.co',
                                headers = {
                                    'Content-Type': 'application/json',
                                    'Accept': 'application/json'
                                },
                                json = {'query': query}
                            )
                            data = res.json()
                            nodes = data['data']['Page']['media'][0]['relations']['nodes']
                            episodes = 0
                            for node in nodes:
                                if node['episodes'] != None:
                                    episodes += node['episodes']
                            episodes += watchlist[index]['progress']
                            if item['episode'] == episodes + 1:
                                entry = {'title': title, 'episode': watchlist[index]['progress'] + 1, 'magnet': item['link']}
                                if entry['title'] not in queueTitles:
                                    queueTitles.append(entry['title'])
                                    queue.append(entry)
                                    if not db.exists(title):
                                        db.add(title, watchlist[index]['progress'] + 1, watchlist[index]['cover'])
                            elif item['episode'] > episodes:
                                entry = {'title': title, 'episode': item['episode'], 'magnet': item['link']}
                                if entry['title'] not in queueTitles:
                                    queueTitles.append(entry['title'])
                                    queue.append(entry)
                                    if not db.exists(title):
                                        db.add(title, item['episode'], watchlist[index]['cover'])
    for item in queue:
        if db.exists(item['title']):
            if db.read(item['title'], 'status') != 'ready':
                while processing:
                    await asyncio.sleep(20)
                await download(item['title'], item['episode'], item['magnet'])
                queue.remove(item)

async def cleanup():
    data = db.dump()
    for entry in list(data.keys()):
        if data[entry]['watched'] != None:
            now = datetime.now()
            watched = datetime.strptime(data[entry]['watched'], "%Y-%m-%d %H:%M:%S.%f")
            if (now - watched).total_seconds() > config['remove_after']:
                file = db.read(entry, 'file')
                os.remove(f'os.getcwd()/public/{file}')
                db.remove(entry)

async def watcher():
    cleanupCounter, fullCounter, patialCounter = 0, 0, 0
    while True:
        if cleanupCounter <= 0:
            print('cleanup')
            await cleanup()
            cleanupCounter = config['cleanup_interval']
        if fullCounter <= 0:
            print('full')
            await check()
            fullCounter = config['full_interval']
            patialCounter = config['partial_interval']
        if patialCounter <= 0:
            print('partial')
            await check(True)
            patialCounter = config['partial_interval']
        cleanupCounter -= 1 
        fullCounter -= 1
        patialCounter -= 1
        await asyncio.sleep(1)

def server():
    app.run(port=config['port'],host=config['host'])

db = dbHandler()
webserver = threading.Thread(target=server)
webserver.start()
asyncio.run(watcher())