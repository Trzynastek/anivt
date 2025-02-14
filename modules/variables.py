from modules import database, console
import os, json

queue = []
queueTitles = []
past = {}
schedule = []
authPause = False

default = {
            "secret": "SecureSecretKey",
            "host": "0.0.0.0",
            "port": "7980",
            "cleanup_interval": 3600,
            "full_interval": 1200,
            "partial_interval": 120,
            "remove_after": 86400,
            "debug": False,
            "logs": True,
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
                "Fontname": "Roboto Medium",
                "Fontsize": 32,
                "Outline": 3,
                "MarginV": 40,
                "resX": 1280,
                "resY": 720
            },
            "anilist": {
                "redirect_base": "http://127.0.0.1:7980",
                "cid": None,
                "secret": None,
                "token": None
            }
        }

if not os.path.exists('config.json'):
    with open('config.json', 'w') as f:
        json.dump(default, f, indent=4) 
        
with open('config.json', 'r', encoding='utf-8') as f:
    char = f.read(1)
    if not char:
        config = default
        with open('config.json', 'w') as f:
            json.dump(default, f, indent=4) 
    else:
        config = json.load(f)

db = database.instance()
console = console.instance(config['debug'], config['logs'])