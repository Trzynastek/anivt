import time
from modules import webserver, watcher
from modules import variables as var

if var.config['anilist']['token'] == None:
    var.authPause = True
    var.console.info('No token, waiting for auth.')

webserver.instance().run()
var.console.info('Web server started.')

while var.authPause:
    time.sleep(1)

watcher.instance().run()
var.console.info('Watcher started.')