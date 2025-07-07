import json, os, time, threading

default = {'videos': {}, 'pfp': None, 'blacklist': {}}

class instance:
    def __init__(self, configs):
        self.dbf = f'{configs}/db.json'
        self.lock = threading.Lock()
        self.ensureDb()
        self.db = self.load()
        for key, value in default.items():
            if key not in self.db:
                self.db[key] = value
        self.save()

    def ensureDb(self):
        with self.lock:
            if not os.path.exists(self.dbf):
                with open(self.dbf, 'w', encoding='utf-8') as f:
                    json.dump(default, f, indent=4)
            else:
                with open(self.dbf, 'r', encoding='utf-8') as f:
                    char = f.read(1)
                    if not char:
                        with open(self.dbf, 'w') as f:
                            json.dump(default, f, indent=4)
    
    def load(self):
        with self.lock:
            with open(self.dbf, 'r', encoding='utf-8') as f:
                return json.load(f)
    
    def save(self):
        with self.lock:
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
    
    def add(self, title, episode, cover, id, description, url, status):
        target = f'{str(episode).zfill(5)}{title}'
        self.db['videos'][target] = {
            "id": id,
            "file": None,
            "episode": episode,
            "cover": cover,
            "watched": None,
            "status": "in queue",
            "description": description,
            "url": url,
            "anilistStatus": status
        }
        self.save()

    def blacklisted(self):
        return set(self.db['blacklist'].keys())

    def blacklist(self, magnet):
        self.db['blacklist'][magnet] = time.time()
        self.save()

    def cleanup(self):
        now = time.time()
        for item in list(self.db['blacklist'].keys()):
            if now -self.db['blacklist'][item] > 604800:
                del self.db['blacklist'][item]
        self.save()

    def exists(self, title, episode):
        target = f'{str(episode).zfill(5)}{title}'
        return target in self.db['videos']
    
    def read(self, title, episode, key):
        target = f'{str(episode).zfill(5)}{title}'
        return self.db.get('videos', {}).get(target, {}).get(key)
    
    def dump(self):
        return self.db['videos']