import feedparser, asyncio, os, requests, re, jwt, time
from unidecode import unidecode
from datetime import datetime
from modules import downloader
from modules import variables as var
from ruamel.yaml import YAML

yaml = YAML()
yaml.indent(mapping=4)
yaml.default_flow_style = False

class instance:
    def __init__(self):
        self.dl = downloader.instance()
        self.lastUpdate = None

    async def getWatching(self):
        uid = jwt.decode(var.config['anilist']['token']['access_token'], options={"verify_signature": False})['sub']

        query = f'{{ MediaListCollection(userId: {uid}, type: ANIME, status_in: [CURRENT, PLANNING]) {{ lists {{ name entries {{ progress media {{ id title {{ english romaji }} synonyms airingSchedule {{ edges {{ node {{ airingAt episode }} }} }} coverImage {{ large }} episodes description siteUrl }} }} }} }} }}'

        success = False
        while not success:
            res = requests.post(
                'https://graphql.anilist.co',
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {var.config["anilist"]["token"]["access_token"]}',
                },
                json = {'query': query}
            )
            if res.status_code == 200:
                success = True
            else:
                var.console.warn("Couldn't get the watchlist. Retrying in 10s", variables={
                    'status code': res.status_code,
                    'response': res.json()
                })
                await asyncio.sleep(10)

        data = res.json()
        data = [entry for lst in data['data']['MediaListCollection']['lists'] for entry in lst['entries']]
        data = [{
            'id': item['media']['id'],
            'progress': item['progress'],
            'title': item['media']['title'],
            'episodes': item['media']['episodes'],
            'cover': item['media']['coverImage']['large'],
            'synonyms': item['media']['synonyms'],
            'airing': item['media']['airingSchedule']['edges'],
            'description': item['media']['description'],
            'url': item['media']['siteUrl']
        } for item in data]

        return data

    async def isToday(self, timestamp):
        if datetime.fromtimestamp(timestamp).date() == datetime.now().date():
            return True
        return False

    async def updateSchedule(self):
        temp = []

        watchlist = await self.getWatching()
        for entry in watchlist:
            if entry['airing'] == None: 
                continue
            for node in entry['airing']:
                node = node['node']
                airing = node['airingAt']
                episode = node['episode']

                if await self.isToday(airing):
                    temp.append({'title': entry['title'], 'airing': airing, 'episode': episode})

        var.schedule = temp

        var.console.debug('Schedule updated.')

    async def check(self, partial = False):
        update = False

        if partial:
            var.console.debug('Running partial RSS check.')
            for source in var.config['rss']:
                feed = feedparser.parse(source['url'])['entries']
                if len(feed) == 0:
                    continue

                last = feed[0]
                if len(var.past) == len(var.config['rss']):
                    if var.past[source['url']] != last:
                        update = True

                var.past[source['url']] = last
        else:
            var.console.debug('Running full RSS check.')

        if partial and not update:
            var.console.debug('Nothing new was found.')
            return
        
        for source in var.config['rss']:
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

            watchlist = await self.getWatching()
            filters = []
            for item in watchlist:
                temp = []
                if item['title'] is not None:
                    eng = item['title'].get('english', None)
                    rom = item['title'].get('romaji', None)
                    
                    eng = eng.strip().lower() if eng else None
                    rom = rom.strip().lower() if rom else None

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

                        normTitle = re.sub(r'[^A-Za-z0-9]+', '', unidecode(title).lower())
                        normItem = re.sub(r'[^A-Za-z0-9]+', '', unidecode(item['title']).lower())
                        if len(normTitle) == 0 or len(normItem) == 0:
                            continue

                        title = watchlist[index]['title'].get('english', None)
                        if not title:
                            title = watchlist[index]['title'].get('romaji', None)
                        if title is None:
                            continue

                        title = title.replace("'", '’')

                        if normItem in normTitle:
                            var.console.debug('Title found.', variables={
                                'title': title,
                                'normItem': normItem,
                                'normTitle': normTitle
                            })
                            found = True
                            if item['episode'] > watchlist[index]['progress']:
                                if source['per_season_episodes']:
                                    entry = {'title': title, 'episode': item['episode'], 'magnet': item['link']}
                                    if f'{str(item["episode"]).zfill(5)}{entry["title"]}' not in var.queueTitles:
                                        var.queueTitles.append(f'{str(item["episode"]).zfill(5)}{entry["title"]}')
                                        var.queue.append(entry)
                                        if not var.db.exists(title, item['episode']):
                                            var.db.add(title, item['episode'], watchlist[index]['cover'], watchlist[index]['id'], watchlist[index]['description'], watchlist[index]['url'])
                                else:
                                    var.console.warn('"Global" episodes are currently not supported, sorry X﹏X', variables={
                                        'title': title,
                                        'episode': item['episode']
                                    })
                                    # query = f'{{ Page {{ media(search: "{title}", type: ANIME) {{ id title {{ romaji }} relations {{ nodes {{ episodes }} }} }} }} }}'
                                    # res = requests.post(
                                    #     'https://graphql.anilist.co',
                                    #     headers = {
                                    #         'Content-Type': 'application/json',
                                    #         'Accept': 'application/json'
                                    #     },
                                    #     json = {'query': query}
                                    # )

                                    # data = res.json()
                                    # nodes = data['data']['Page']['media'][0]['relations']['nodes']
                                    # episodes = 0

                                    # if len(nodes) > 0:
                                    #     for node in nodes:
                                    #         if node['episodes'] != None:
                                    #             episodes += node['episodes']
                                    # else:
                                    #     episodes = 0
                                    # if item['episode'] > episodes:
                                    #     episode = item['episode'] - episodes
                                    #     if episode > watchlist[index]['progress']:
                                    #         entry = {'title': title, 'episode': episode, 'magnet': item['link']}
                                    #         if f'{str(episode).zfill(5)}{entry["title"]}' not in var.queueTitles:
                                    #             var.queueTitles.append(f'{str(episode).zfill(5)}{entry["title"]}')
                                    #             var.queue.append(entry)
                                    #             if not var.db.exists(title, episode):
                                    #                 var.db.add(title, episode, watchlist[index]['cover'], watchlist[index]['id'], watchlist[index]['description'], watchlist[index]['url'])
                                    # var.console.debug('Episodes coversion', variables={
                                    #     'nodes': nodes,
                                    #     'total episodes': episodes,
                                    #     'converted episode': episode,
                                    #     'original episode': item['episode']
                                    # })
        if not partial:
            var.console.debug('Check finished.', variables={
                'queue': var.queue
            })
        for item in var.queue[:]:
            if var.db.exists(item['title'], item['episode']):
                if var.db.read(item['title'], item['episode'], 'status') != 'ready':
                    await self.dl.process(item['title'], item['episode'], item['magnet'])
                    var.queue.remove(item)

    async def cleanup(self):
        var.console.debug('Running cleanup.')
        data = var.db.dump()
        for entry in list(data.keys()):
            if data[entry]['watched'] != None:
                now = datetime.now()
                title = entry[5:]
                watched = datetime.strptime(data[entry]['watched'], "%Y-%m-%d %H:%M:%S.%f")
                if (now - watched).total_seconds() > var.config['remove_after']:
                    file = var.db.read(title, data[entry]['episode'], 'file')
                    file = f'{var.workdir}/public/{file}'
                    if os.path.exists(file):
                        os.remove(file)
                    var.db.remove(title, data[entry]['episode'])
                    var.console.debug('Removed item', variables={
                        'title': title,
                        'watched': watched,
                        'file': file
                    })
        for file in os.listdir(f'{var.workdir}/public/mp4/'):
            file = f'mp4/{file}'
            found = False
            for entry in data.values():
                if entry['file'] == file:
                    found = True
                    break
            if not found:
                os.remove(f'{var.workdir}/public/{file}')
        for file in os.listdir(f'{var.workdir}/mkv/'):
            os.remove(f'{var.workdir}/mkv/{file}')

    async def updateConfig(self):
        with open(var.configFile, 'r', encoding='utf-8') as f:
            var.config = yaml.load(f)
        return
    
    async def cleanShareKeys(self):
        now = time.time()
        var.shareKeys = {k: v for k, v in var.shareKeys.items() if v['expires'] > now}

    async def watcher(self):
        cleanupCounter, fullCounter, patialCounter, scheduleCounter, shareKeyCounter, configCounter, blacklistCounter = 0, 0, 0, 0, 0, 0, 0
        lastScheduleUpdate = None

        while True:
            if configCounter <= 0:
                await self.updateConfig()
                shareKeyCounter = 300

            if shareKeyCounter <= 0:
                await self.cleanShareKeys()
                shareKeyCounter = 3600

            if blacklistCounter <= 0:
                var.db.cleanup()
                shareKeyCounter = 28800

            if scheduleCounter <= 0:
                if var.config['update_schedule_once_a_day']:
                    if lastScheduleUpdate != datetime.now().date():
                        lastScheduleUpdate = datetime.now().date()
                        await self.updateConfig()
                        await self.updateSchedule()
                else:
                    await self.updateConfig()
                    await self.updateSchedule()
                scheduleCounter = 3600

            if cleanupCounter <= 0:
                await self.updateConfig()
                await self.cleanup()
                cleanupCounter = var.config['cleanup_interval']

            if fullCounter <= 0:
                await self.updateConfig()
                await self.check()
                fullCounter = var.config['full_interval']
                patialCounter = var.config['partial_interval']

            if patialCounter <= 0:
                await self.updateConfig()
                await self.check(True)
                patialCounter = var.config['partial_interval']

            cleanupCounter -= 1 
            fullCounter -= 1
            patialCounter -= 1
            scheduleCounter -= 1
            shareKeyCounter -= 1
            configCounter -= 1
            blacklistCounter -= 1
            await asyncio.sleep(1)

    def run(self):
        asyncio.run(self.watcher())