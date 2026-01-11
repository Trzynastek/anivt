dev = False

import time
from modules import webserver
if not dev:
    from modules import watcher
from modules import variables as var


if not dev:
    if var.config['anilist']['token'] == None:
        var.authPause = True
        var.console.info('No token, waiting for auth.')

webserver.instance(dev).run()
var.console.info('Web server started.')

while var.authPause:
    time.sleep(1)

if not dev:
    watcher.instance().run()
    var.console.info('Watcher started.')