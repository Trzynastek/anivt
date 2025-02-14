from flask import Flask, request, send_from_directory, session, make_response, redirect, render_template
from flask_cors import CORS
import json, asyncio, jwt, requests, threading, os
from datetime import datetime, timedelta
from waitress import serve
from modules import variables as var


whitelist = [
    'auth.html',
    'auth.css',
    'auth.js',
    'assets/logo.svg',
    'assets/icon.svg'
]

class instance:
    def __init__(self):
        self.app = Flask(__name__)
        self.app.template_folder = os.getcwd() + '/public/'
        self.app.secret_key = var.config['secret']
        self.app.config["SESSION_PERMANENT"] = False
        self.app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
        self.app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
        self.app.config['SESSION_COOKIE_NAME'] = "sessionToken"
        CORS(self.app)
        self.createRoutes()

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

            if 'error' in token:
                var.console.error('Invalid AniList auth token repsonse.', variables={
                    'token': token
                })
                return render_template(
                    'message.html', 
                    type="error", 
                    message="Incorrect token response.", 
                    redirect=True, 
                    delay=2000
                ), 200
            
            if var.config['anilist']['token'] == None:
                var.config['anilist']['token'] = token
                with open('config.json', 'w', encoding='utf-8') as f:
                    json.dump(var.config, f, indent=4)
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
                return render_template(
                    'message.html', 
                    type="error", 
                    message="User not permited", 
                    details="If this is your instance, try removing AniList token from config.", 
                    redirect=True, 
                    delay=2000
                ), 200
            
            return render_template(
                'message.html', 
                redirect=True, 
                delay=0
            ), 200

        @self.app.route('/api/redirect', methods=['GET'])
        def sendRedirect():
            return {"cid": var.config['anilist']['cid'], "redirect": var.config['anilist']['redirect_base']}

        @self.app.route('/api/watched', methods=['POST'])
        def markWatched():
            if not session.get('authenticated'):
                return send_from_directory('../public', 'auth.html'), 403
            
            title = request.json['title']
            episode = request.json['episode']

            if var.db.exists(title, episode):
                now = str(datetime.now())
                var.db.update(title, episode, 'watched', now)
                id = var.db.read(title, episode, 'id')
                query = f'mutation {{ SaveMediaListEntry(mediaId: {id}, progress: {episode}) {{ id progress }} }}'
                res = requests.post(
                    'https://graphql.anilist.co',
                    headers = {
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {var.config["anilist"]["token"]["access_token"]}',
                    },
                    json = {'query': query}
                )
                
            var.console.infof(f'Marked {title} EP{episode} as watched')
            return '', 200

        @self.app.route('/api/schedule', methods=['GET'])
        def getSchedule():
            if not session.get('authenticated'):
                return send_from_directory('../public', 'auth.html'), 403
            return var.schedule

        @self.app.route('/')
        def homepage():
            if not session.get('authenticated'):
                return send_from_directory('../public', 'auth.html'), 403
            return send_from_directory('../public', 'index.html')

        @self.app.route('/<path:file>')
        def serveFile(file):
            if not session.get('authenticated'):
                if file in whitelist:
                    return send_from_directory('../public', file)
                return send_from_directory('../public', 'auth.html'), 403
            return send_from_directory('../public', file)
    
    def server(self):
        serve(self.app, host=var.config['host'], port=var.config['port'])
    
    def run(self):
        webserver = threading.Thread(target=self.server)
        webserver.start()