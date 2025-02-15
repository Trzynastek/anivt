import json, os

class instance:
    def __init__(self, configs):
        self.dbf = f'{configs}/db.json'
        self.ensureDb()
        self.db = self.load()

    def ensureDb(self):
        if not os.path.exists(self.dbf):
            with open(self.dbf, 'w', encoding='utf-8') as f:
                json.dump({'videos': {}, 'pfp': None}, f, indent=4)
        else:
            with open(self.dbf, 'r', encoding='utf-8') as f:
                char = f.read(1)
                if not char:
                    with open(self.dbf, 'w') as f:
                        json.dump({'videos': {}, 'pfp': None}, f, indent=4)
    
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
    
    def add(self, title, episode, cover, id):
        target = f'{str(episode).zfill(5)}{title}'
        self.db['videos'][target] = {
            "id": id,
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