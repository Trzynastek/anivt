from flask import Flask, request, send_from_directory, session, make_response, redirect, jsonify
from flask_cors import CORS
import asyncio, jwt, requests, threading, os, hashlib, time, secrets
from datetime import datetime, timedelta
from waitress import serve
from modules import variables as var
from jinja2 import Environment, FileSystemLoader
from functools import wraps
from ruamel.yaml import YAML

yaml = YAML()
yaml.indent(mapping=4)
yaml.default_flow_style = False

whitelist = [
    'global.css',
    'logo.svg',
    'icon.svg'
]

class instance:
    def __init__(self):
        self.app = Flask(__name__)
        self.app.template_folder = var.workdir + '/web/'
        self.app.secret_key = var.config['secret']
        self.app.config["SESSION_PERMANENT"] = False
        self.app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
        self.app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
        self.app.config['SESSION_COOKIE_NAME'] = "sessionToken"
        CORS(self.app)
        self.createRoutes()
        self.env = Environment(loader=FileSystemLoader(['web/pages', 'web/components', 'web/layouts']))

    def requireAuth(self, whitelist=None):
        def decorator(f):
            @wraps(f)
            def wrapped(*args, **kwargs):
                if session.get('authenticated'):
                    return f(*args, **kwargs)

                if whitelist:
                    file = kwargs.get('file')
                    if file in whitelist:
                        return send_from_directory('../web/assets/', file)
                template = self.env.get_template('auth.html')

                return template.render(cid=var.config['anilist']['cid'], redirect=var.config['anilist']['redirect_base']), 403
            return wrapped
        return decorator

    async def getPfp(self, uid):
        if var.db.db['pfp'] == None:
            query = f'{{ User(id: {uid}) {{ avatar {{ medium }} }} }}'

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
                    pfp = res.json()['data']['User']['avatar']['medium']
                    var.db.db['pfp'] = pfp
                    var.db.save()
                    var.console.debug('Pfp updated', variables={
                        'pfp': pfp,
                    })
                else:
                    var.console.warn("Couldn't get the pfp. Retrying in 10s", variables={
                        'status code': res.status_code,
                        'response': res.json()
                    })
                    await asyncio.sleep(10)

    def createRoutes(self):
        @self.app.route('/api/logout')
        @self.requireAuth()
        def logout():
            session.clear()
            response = make_response(redirect("/"))
            response.set_cookie("session", "", expires=0)
            var.console.info('User logged out')
            return response

        @self.app.route('/api/auth', methods=['GET'])
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
                    'client_id': var.config['anilist']['cid'],
                    'client_secret': var.config['anilist']['secret'],
                    'redirect_uri': f'{var.config["anilist"]["redirect_base"]}/api/auth',
                    'code': code
                }
            )
            token = res.json()
            template = self.env.get_template('message.html')

            if 'error' in token:
                var.console.error('Invalid AniList auth token repsonse.', variables={
                    'token': token
                })
                return template.render(
                    type="error", 
                    message="Incorrect token response.", 
                    redirect=True, 
                    delay=2000
                ), 200
            
            if var.config['anilist']['token'] == None:
                var.config['anilist']['token'] = token
                with open(var.configFile, 'r', encoding='utf-8') as f:
                    temp = yaml.load(f)
                temp['anilist']['token'] = token
                with open(var.configFile, 'w', encoding='utf-8') as f:
                    yaml.dump(temp, f)
                var.console.info('AniList token set.', variables={
                    'token': token
                })

            serverUID = jwt.decode(var.config['anilist']['token']['access_token'], options={"verify_signature": False})['sub']
            requestUID = jwt.decode(token['access_token'], options={"verify_signature": False})['sub']

            if serverUID == requestUID:
                asyncio.run(self.getPfp(requestUID))
                var.authPause = False
                session.permanent = True
                session['authenticated'] = True
                var.console.info('User authentificated', variables={
                    'UID': requestUID
                })
            else:
                var.console.warn('A not-permitted user tried to log in.', variables={
                    'UID': requestUID
                })
                return template.render( 
                    type="error", 
                    message="User not permited", 
                    details="If this is your instance, try removing AniList token from config.", 
                    redirect=True, 
                    delay=2000
                ), 200
            
            return template.render(
                redirect=True, 
                delay=0
            ), 200

        @self.app.route('/api/watched', methods=['POST'])
        @self.requireAuth()
        def markWatched():
            title = request.json['title']
            episode = request.json['episode']

            if var.db.exists(title, episode):
                now = str(datetime.now())
                var.db.update(title, episode, 'watched', now)
                id = var.db.read(title, episode, 'id')
                status = var.db.read(title, episode, 'anilistStatus')
                if status == "PLANNING" or status == None:
                    query = f'mutation {{ SaveMediaListEntry(mediaId: {id}, progress: {episode}, status: CURRENT) {{ id progress status }} }}'
                else:
                    query = f'mutation {{ SaveMediaListEntry(mediaId: {id}, progress: {episode}) {{ id progress }} }}'
                requests.post(
                    'https://graphql.anilist.co',
                    headers = {
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {var.config["anilist"]["token"]["access_token"]}',
                    },
                    json = {'query': query}
                )
                
            var.console.info(f'Marked {title} EP{episode} as watched')
            return '', 200

        @self.app.route('/schedule', methods=['GET'])
        @self.requireAuth()
        def schedule():
            content = ''.join(
                self.env.get_template('scheduleEntry.html').render(
                    entry=entry, 
                    now=time.time(), 
                    datetime=datetime
                )
                for entry in sorted(var.schedule, key=lambda e: e['airing'])
            )
            if not content:
                return 'Nothing here ¯\_(ツ)_/¯'
            etag = hashlib.md5(content.encode()).hexdigest()

            if request.headers.get('If-None-Match') == etag:
                return '', 304

            res = make_response(content)
            res.headers['ETag'] = etag
            return res

        @self.app.route('/api/pfp', methods=['GET'])
        @self.requireAuth()
        def pfp():
            pfp = var.db.load()['pfp']
            return jsonify({'pfp': pfp})

        @self.app.route('/')
        @self.requireAuth()
        def homepage():
            videos = var.db.load()['videos']
            template = self.env.get_template('home.html')
            return template.render(
                videos=dict(reversed(list(videos.items()))),
                schedule=sorted(var.schedule, key=lambda e: e['airing']),
                now=time.time(),
                datetime=datetime
            )
        
        @self.app.route('/watch')
        @self.requireAuth()
        def watchpage():
            videoId = request.args.get('id')
            videos = var.db.load()['videos']
            template = self.env.get_template('watch.html')
            return template.render(video=videos[videoId], title=videoId, enableShareKeys=var.config['enable_shareKeys'])

        @self.app.route('/feed')
        @self.requireAuth()
        def renderFeed():
            videos = var.db.dump()
            content = ''.join(
                self.env.get_template('card.html').render(key=key, entry=entry)
                for key, entry in reversed(videos.items())
            )
            if len(videos) % 2 == 1:
                content += '<div id="filler"></div>'
            etag = hashlib.md5(content.encode()).hexdigest()

            if request.headers.get('If-None-Match') == etag:
                return '', 304

            res = make_response(content)
            res.headers['ETag'] = etag
            return res

        @self.app.route('/<path:file>')
        @self.requireAuth(whitelist)
        def serveFile(file):
            if file.startswith('mp4/'):
                return send_from_directory('../public/', file)
            return send_from_directory('../web/assets/', file)
        
        if var.config['enable_shareKeys']:
            @self.app.route('/api/createShareKey', methods=['POST'])
            @self.requireAuth()
            def createShareKey():
                data = request.get_json()
                file = data.get('file')
                duration = int(data.get('duration'))
                token = secrets.token_urlsafe(24)
                var.shareKeys[token] = {
                    'file': file,
                    'expires': time.time() + duration
                }
                return {'shareKey': token}
            
            @self.app.route('/shareKey/<token>')
            def serveWithSK(token):
                data = var.shareKeys.get(token, None)
                if not data or time.time() > data['expires']:
                    return 'The ShareKey is not valid or expired', 404
                return send_from_directory('../public/', data['file'])
        
    def server(self):
        serve(self.app, host=var.config['host'], port=var.config['port'])
    
    def run(self):
        webserver = threading.Thread(target=self.server)
        webserver.start()