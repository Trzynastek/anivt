from flask import Flask, request, send_from_directory
from flask_cors import CORS
import feedparser
import asyncio
from torrentp import TorrentDownloader as downloader
from ffmpeg.asyncio import FFmpeg
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
from datetime import datetime

app = Flask(__name__)
CORS(app)

queue = []
queueTitles = []
processing = False
past = {}
schedule = []

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
            "subtitles": {
                "font": "Roboto Medium",
                "size": 45,
                "outline": 3
            },
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
    
    def update(self, title, episode, key, value):
        target = f'{str(episode).zfill(5)}{title}'
        self.db['videos'][target][key] = value
        self.save()
    
    def remove(self, title, episode):
        target = f'{str(episode).zfill(5)}{title}'
        del self.db['videos'][target]
        self.save()
    
    def add(self, title, episode, cover):
        target = f'{str(episode).zfill(5)}{title}'
        self.db['videos'][target] = {
            "file": None,
            "episode": episode,
            "cover": cover,
            "watched": None,
            "status": "in queue"
        }
        self.save()

    def exists(self, title, episode):
        target = f'{str(episode).zfill(5)}{title}'
        return target in self.db['videos']
    
    def read(self, title, episode, key):
        target = f'{str(episode).zfill(5)}{title}'
        return self.db['videos'][target][key]
    
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
    episode = request.json['episode']
    if db.exists(title, episode):
        now = str(datetime.now())
        db.update(title, episode, 'watched', now)
    return '', 200

@app.route('/api/schedule', methods=['GET'])
async def getSchedule():
    global schedule
    return schedule, 200

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
    query = f'{{ MediaListCollection(userId: {uid}, type: ANIME) {{ lists {{ entries {{ progress media {{ title {{ english romaji }} synonyms airingSchedule {{ edges {{ node {{ airingAt }} }} }} coverImage {{ large }} episodes }} }} }} }} }}'
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
        'synonyms': item['media']['synonyms'],
        'airing': item['media']['airingSchedule']['edges']
    } for item in data]
    return data

async def isToday(timestamp):
    if datetime.fromtimestamp(timestamp).date() == datetime.now().date():
        return True
    return False

async def updateSchedule():
    global schedule
    temp = []
    watchlist = await getWatching()
    for entry in watchlist:
        progress = int(entry['progress'])
        if len(entry['airing']) > progress:
            airing = entry['airing'][progress]['node']['airingAt']
            if await isToday(airing):
                temp.append({'title': entry['title'], 'airing': airing, 'episode': entry['progress']})
                continue
            if progress > 1:
                airing = entry['airing'][progress - 1]['node']['airingAt']
                if await isToday(airing):
                    temp.append({'title': entry['title'], 'airing': airing, 'episode': entry['progress'] + 1})
                    continue
            if progress > 2:
                airing = entry['airing'][progress - 2]['node']['airingAt']
                if await isToday(airing):
                    temp.append({'title': entry['title'], 'airing': airing, 'episode': entry['progress'] - 1})
        elif len(entry['airing']) == progress:
            if progress > 1:
                airing = entry['airing'][progress - 1]['node']['airingAt']
                if await isToday(airing):
                    temp.append({'title': entry['title'], 'airing': airing, 'episode': entry['progress'] + 1})
                    continue
            if progress > 2:
                airing = entry['airing'][progress - 2]['node']['airingAt']
                if await isToday(airing):
                    temp.append({'title': entry['title'], 'airing': airing, 'episode': entry['progress'] - 1})
    schedule = temp

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

async def patchSubtiles(inp, sub):
    ffmpeg = (
        FFmpeg()
        .input(inp)
        .output(sub)
    )
    await ffmpeg.execute()
    with open(sub, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    styles = False
    for line in lines:
        if line.startswith('[V4+ Styles]'):
            styles = True
        elif line.startswith('['):
            styles = False
        elif line.startswith('Format:') and styles:
            keys = line.replace(' ', '').split(',')
    overrides = []
    for key in config['subtitles']:
        if key in keys:
            overrides.append({'index': keys.index(key), 'value': config['subtitles'][key]})
    with open(sub, 'w', encoding='utf-8') as f:
        for line in lines:
            if line.startswith('Style:'):
                values = line.strip().split(',')
                for entry in overrides:
                    values[entry['index']] = entry['value']
                line = ', '.join(str(v) for v in values) + '\n'
                f.write(line)
            elif line.startswith('PlayRes'):
                if line.startswith('PlayResX'):
                    line = 'PlayResX: 1920 \n'
                else:
                    line = 'PlayResY: 1080 \n'
                f.write(line)
            else:
                f.write(line)

async def preCheck(title, episode, magnet):
    file = os.getcwd() + '/mkv/' + f'{title}[Ep.{episode}].mkv'
    inp = re.sub(r'[^A-Za-z0-9 /\[\].]+', '', file).replace(' ', '_')
    out = inp.replace('.mkv', '.mp4').replace('/mkv/', '/public/mp4/')
    sub = inp.replace('.mkv', '.ass').replace('/mkv/', '/subtitles/')
    exists = os.path.exists(inp) or os.path.exists(out)
    if not exists:
        res = requests.get(magnet)
        data = res.content
        magnet = await toMagnet(data)
        query = urllib.parse.urlparse(magnet).query
        dl = os.getcwd() + '/mkv/' + urllib.parse.parse_qs(query).get('dn', [None])[0]
    else:
        magnet, dl = None, None
    return (inp, out, exists, magnet, dl, sub)

async def download(title, episode, magnet):
    global processing
    processing = True
    inp, out, exists, magnet, dl, sub = await preCheck(title, episode, magnet)
    if not exists:
        db.update(title, episode, 'status', 'downloading')
        torrent = downloader(magnet, './mkv/', stop_after_download=True)
        await torrent.start_download()
        os.rename(dl, inp)
    if not os.path.exists(sub):
        await patchSubtiles(inp, sub)
    if os.path.exists(out):
        db.update(title, episode, 'status', 'ready')
        db.update(title, episode, 'file', out.replace(f'{os.getcwd()}/public/', ''))
        return
    db.update(title, episode, 'status', 'encoding')
    ffprobe = FFmpeg(executable="ffprobe").input(
        inp,
        print_format="json",
        show_streams=None,
        select_streams='a'
    )
    streams = json.loads(await ffprobe.execute())['streams']
    if len(streams) > 1:
        mappings = ['0:v:0', '0:a:1']
    else:
        mappings = ['0:v:0', '0:a:0']
    ffmpeg = (
        FFmpeg()
        .input(inp, ss=0, t=10)
        .output(
            out,
            vf=f"subtitles={shlex.quote(sub.replace(':', '\\:'))}",
            movflags="+faststart",
            map=mappings,
            **config['encoding']
        )
    )
    await ffmpeg.execute()
    os.remove(inp)
    os.remove(sub)
    db.update(title, episode, 'status', 'ready')
    db.update(title, episode, 'file', out.replace(f'{os.getcwd()}/public/', ''))
    processing = False

async def check(partial = False):
    global processing
    global queue
    global queueTitles
    global past
    update = False
    if partial:
        for source in config['rss']:
            feed =feedparser.parse(source['url'])['entries']
            if len(feed) == 0:
                continue
            last = feed[0]
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
                    if title is None:
                        continue
                    title = title.replace("'", '’')
                    if normItem in normTitle:
                        found = True
                        if item['episode'] > watchlist[index]['progress']:
                            if source['per_season_episodes']:
                                entry = {'title': title, 'episode': item['episode'], 'magnet': item['link']}
                                if f'{str(item['episode']).zfill(5)}{entry['title']}' not in queueTitles:
                                    queueTitles.append(f'{str(item['episode']).zfill(5)}{entry['title']}')
                                    queue.append(entry)
                                    if not db.exists(title, item['episode']):
                                            db.add(title, item['episode'], watchlist[index]['cover'])
                            else:
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
                                if len(nodes) > 0:
                                    for node in nodes:
                                        if node['episodes'] != None:
                                            episodes += node['episodes']
                                else:
                                    episodes = 0
                                if item['episode'] > episodes:
                                    episode = item['episode'] - episodes
                                    if episode > watchlist[index]['progress']:
                                        entry = {'title': title, 'episode': episode, 'magnet': item['link']}
                                        if f'{str(episode).zfill(5)}{entry['title']}' not in queueTitles:
                                            queueTitles.append(f'{str(episode).zfill(5)}{entry['title']}')
                                            queue.append(entry)
                                            if not db.exists(title, episode):
                                                db.add(title, episode, watchlist[index]['cover'])
    for item in queue:
        if db.exists(item['title'], item['episode']):
            if db.read(item['title'], item['episode'], 'status') != 'ready':
                while processing:
                    await asyncio.sleep(20)
                await download(item['title'], item['episode'], item['magnet'])
                queue.remove(item)

async def cleanup():
    data = db.dump()
    for entry in list(data.keys()):
        if data[entry]['watched'] != None:
            now = datetime.now()
            title = entry[5:]
            watched = datetime.strptime(data[entry]['watched'], "%Y-%m-%d %H:%M:%S.%f")
            if (now - watched).total_seconds() > config['remove_after']:
                file = db.read(title, data[entry]['episode'], 'file')
                file = f'{os.getcwd()}/public/{file}'
                if os.path.exists(file):
                    os.remove(file)
                db.remove(title, data[entry]['episode'])

async def watcher():
    cleanupCounter, fullCounter, patialCounter, scheduleCounter = 0, 0, 0, 0
    while True:
        if fullCounter <= 0:
            await check()
            fullCounter = config['full_interval']
            patialCounter = config['partial_interval']
        if patialCounter <= 0:
            await check(True)
            patialCounter = config['partial_interval']
        if scheduleCounter <= 0:
            await updateSchedule()
            scheduleCounter = 3600
        if cleanupCounter <= 0:
            await cleanup()
            cleanupCounter = config['cleanup_interval']
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