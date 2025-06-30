from modules import database, console
import os, json
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

yaml = YAML()
yaml.indent(mapping=4)
yaml.default_flow_style = False

queue = []
queueTitles = []
past = {}
schedule = []
authPause = False

shareKeys = {}

workdir = os.getcwd()
configs = workdir + '/configs'
if not os.path.exists(configs):
    os.mkdir(configs)

oldConfig = f'{configs}/config.json'
configFile = f'{configs}/config.yml'

default = CommentedMap({
    "secret": "SecureSecretKey",
    "host": "0.0.0.0",
    "port": "7980",
    "cleanup_interval": 3600,
    "full_interval": 1200,
    "partial_interval": 120,
    "remove_after": 86400,
    "download_timeout": 240,
    "download_retries": 3,
    "debug": False,
    "logs": True,
    "enable_shareKeys": True,
    "update_schedule_once_a_day": True,
    "rss": [],
    "language": {
        "audio": "jpn",
        "subtitles": "eng"
    },
    "language_fallback": {
        "audio": "eng",
        "subtitles": "eng"
    },
    "encode_when_no_language": False,
    "encoding": {
        "vcodec": "libx264",
        "pix_fmt": "yuv420p",
        "crf": 18,
        "preset": "veryfast",
        "acodec": "aac",
        "ac": 2,
        "threads": 0
    },
    "subtitles": {
        "Fontname": "Roboto Medium",
        "Fontsize": 36,
        "Outline": 4,
        "MarginV": 40
    },
    "anilist": CommentedMap({
        "redirect_base": "http://127.0.0.1:7980",
        "cid": None,
        "secret": None,
        "token": None
    })
})

def addComments(content):
    content.yaml_set_comment_before_after_key('secret', before=(
        '\n'
        'Secret used for flask sessions.\n'
        ' \n'
        'Set it to something long and hard to guess.\n'
        'You can also use a password generator such as: https://1password.com/password-generator'
    ))
    content.yaml_set_comment_before_after_key('cleanup_interval', before=(
        '\n'
        'All time values are in seconds.\n'
        ' \n'
        'How often Aniv/t attempts to remove old files.\n'
        'Default: 3600'
    ))
    content.yaml_set_comment_before_after_key('full_interval', before=(
        '\n'
        'How often Aniv/t checks for new episodes.\n'
        ' \n'
        'Default: 1200'
    ))
    content.yaml_set_comment_before_after_key('partial_interval', before=(
        '\n'
        'How often Aniv/t checks for updates in RSS feeds.\n'
        ' \n'
        'Default: 120'
    ))
    content.yaml_set_comment_before_after_key('remove_after', before=(
        '\n'
        'After what time should watched episodes be removed.\n'
        ' \n'
        'Default: 86400'
    ))
    content.yaml_set_comment_before_after_key('download_timeout', before=(
        '\n'
        'After how long should of being stuck should the download restart.\n'
        ' \n'
        'When the download progress is stuck at the same % for amount of time set here the download will restart.\n'
        'Default: 240'
    ))
    content.yaml_set_comment_before_after_key('download_retries', before=(
        '\n'
        'How many times can the download be restarted when stuck.\n'
        ' \n'
        'Default: 3'
    ))
    content.yaml_set_comment_before_after_key('enable_shareKeys', before=(
        '\n'
        'Enables option to generate a temporary unauthenticated URL to any episode.\n'
        ' \n'
        'Default: True'
    ))
    content.yaml_set_comment_before_after_key('update_schedule_once_a_day', before=(
        '\n'
        'Lowers schedule update rate to once a day.\n'
        ' \n'
        'When this is disabled, the updates will happen every hour.\n'
        'Default: True'
    ))
    content.yaml_set_comment_before_after_key('rss', before=(
        '\n'
        'List of RSS feeds to check for episodes.\n'
        ' \n'
        'Format:\n'
        "- url: 'Url to a RSS feed with torrent files.'\n"
        "  regex: 'Regex matching two groups: title and episode number.'\n"
        '  per_season_episodes: false / true'
    ))
    content.yaml_set_comment_before_after_key('encode_when_no_language', before=(
        '\n'
        'When disabled the episode will not be encoded when neither the preferred language nor the fallback language is found.\n'
        ' \n'
        'When this is enabled the episode will fallback to first available stream and encode it.\n'
        'Default: False'
    ))
    content.yaml_set_comment_before_after_key('language', before=(
        '\n'
        'Preferred languages used when encoding.\n'
        ' \n'
        'Default audio: jpn\n'
        'Default subtitles: eng'
    ))
    content.yaml_set_comment_before_after_key('language_fallback', before=(
        '\n'
        'Fallback for when the preferred language is not available.\n'
        ' \n'
        'If a selected language is not found in the MKV file, it will fall back to one set here instead.\n'
        'Default audio: eng\n'
        'Default subtitles: eng'
    ))
    content.yaml_set_comment_before_after_key('encoding', before=(
        '\n'
        'Encoding options for ffmpeg.\n'
        ' \n'
        'Refer to the official documentation\n'
        'https://www.ffmpeg.org'
    ))
    content.yaml_set_comment_before_after_key('subtitles', before=(
        '\n'
        'Subtitle style overrides.\n'
        ' \n'
        'All subtitles are converted to .ass format.\n'
        'Refer to the official documentation\n'
        'https://fileformats.fandom.com/wiki/SubStation_Alpha#Styles_section'
    ))
    anilist = content['anilist']
    anilist.yaml_set_comment_before_after_key('redirect_base', before=(
        '\n'
        'Url of your Aniv/t instance.\n'
        ' \n'
        'Must match with redirect URL set in the API client.\n'
        'Default: http://127.0.0.1:7980'
    ))
    anilist.yaml_set_comment_before_after_key('cid', before=(
        '\n'
        'AniList client ID.'
    ))
    anilist.yaml_set_comment_before_after_key('secret', before=(
        '\n'
        'AniList client secret'
    ))
    anilist.yaml_set_comment_before_after_key('token', before=(
        '\n'
        'AniList access token.\n'
        ' \n'
        'This value will be automatically filled out after the first login.\n'
        'DO NOT SHARE THIS'
    ))

addComments(default)

def merge(default, old):
    for key in default:
        if key in old:
            if isinstance(default[key], dict) and isinstance(old[key], dict):
                if key in ['anilist', 'language']:
                    for subkey in default[key]:
                        if subkey in old[key]:
                            default[key][subkey] = old[key][subkey]
                else:
                    for subkey in old[key]:
                        default[key][subkey] = old[key][subkey]
            else:
                default[key] = old[key]

if not os.path.exists(configFile):
    if os.path.exists(oldConfig):
        with open(oldConfig, 'r', encoding='utf-8') as f:
            char = f.read(1)
            if not char:
                old = default
            else:
                f.seek(0)
                old = json.load(f)
                merge(default, old)
    with open(configFile, 'w') as f:
        yaml.dump(default, f) 
        
with open(configFile, 'r', encoding='utf-8') as f:
    char = f.read(1)
    if not char:
        config = default
        with open(configFile, 'w') as f:
            yaml.dump(default, f) 
    else:
        f.seek(0)
        config = yaml.load(f)

missing = [k for k in default if k not in config]
if missing:
    update = CommentedMap()
    for key in default:
        update[key] = config.get(key, default[key])
    addComments(update)
    with open(configFile, 'w') as f:
        yaml.dump(update, f)

db = database.instance(configs)
console = console.instance(config['debug'], config['logs'])