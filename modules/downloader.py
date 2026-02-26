import bencodepy, hashlib, base64, shlex, urllib.parse, os, re, asyncio, json, requests, time
from datetime import datetime, timedelta
import libtorrent as lt
from ffmpeg import Progress
from ffmpeg.asyncio import FFmpeg
from modules import variables as var

class instance():
    def __init__(self):
        subPath = var.workdir + '/subtitles'
        if not os.path.exists(subPath):
            os.mkdir(subPath)

    # Stollen from https://github.com/DanySK/torrent2magnet 
    async def toMagnet(self, data):
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

    async def patchSubtiles(self, inp, sub):
        ffprobe = FFmpeg(executable="ffprobe").input(
            inp,
            print_format="json",
            show_streams=None,
            select_streams='s'
        )
        streams = json.loads(await ffprobe.execute())['streams']

        mappings = None
        for i, stream in enumerate(streams):
            if stream['tags']['language'] == var.config['language']['subtitles']:
                mappings = f'0:s:{i}'
                break
        if mappings == None:
            for i, stream in enumerate(streams):
                if stream['tags']['language'] == var.config['language_fallback']['subtitles']:
                    mappings = f'0:s:{i}'
                    break
        if mappings == None:
            if var.config['encode_when_no_language']:
                mappings = '0:s:0'
            else:
                var.console.debug('Subtitles language not available', variables={
                    'mappings': mappings,
                    'encode_when_no_language': var.config['encode_when_no_language']
                })
                return False

        ffmpeg = (
            FFmpeg()
            .input(inp)
            .output(
                sub,
                map=mappings
            )
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
            elif line.startswith('PlayResY'):
                resY = int(line.strip().removeprefix('PlayResY: '))

        overrides = []
        for key in var.config['subtitles']:
            if key in keys:
                overrides.append({'index': keys.index(key), 'value': var.config['subtitles'][key]})

        with open(sub, 'w', encoding='utf-8') as f:
            for line in lines:
                if line.startswith('Style:'):
                    values = line.strip().split(',')
                    for entry in overrides:
                        values[entry['index']] = await self.convertRes(720, resY, entry['value']) if type(entry['value']) == int else entry['value']
                    line = ', '.join(str(v) for v in values) + '\n'
                    f.write(line)
                else:
                    f.write(line)
        var.console.debug('Subtitles patched', variables={
            'inp': inp,
            'sub': sub
        })

        return True

    async def preCheck(self, title, episode, magnet):
        file = var.workdir + '/mkv/' + f'{title}[Ep.{episode}].mkv'
        inp = re.sub(r'[^A-Za-z0-9 /\[\].]+', '', file).replace(' ', '_')
        out = inp.replace('.mkv', '.mp4').replace('/mkv/', '/public/mp4/')
        sub = inp.replace('.mkv', '.ass').replace('/mkv/', '/subtitles/')
        exists = False

        if os.path.exists(out):
            var.db.update(title, episode, 'status', 'ready')
            var.db.update(title, episode, 'file', out.replace(f'{var.workdir}/public/', ''))
        elif not os.path.exists(inp):
            res = requests.get(magnet)
            data = res.content
            magnet = await self.toMagnet(data)
            query = urllib.parse.urlparse(magnet).query
            dl = var.workdir + '/mkv/' + urllib.parse.parse_qs(query).get('dn', [None])[0]
        else:
            magnet, dl = None, None

        var.console.debug('Precheck completed.', variables={
            'inp': inp,
            'out': out,
            'exists': exists,
            'magnet': magnet,
            'dl': dl,
            'sub': sub
        })
        return(inp, out, magnet, dl, sub)

    async def process(self, title, episode, magnet):
        try:
            inp, out, magnet, dl, sub = await self.preCheck(title, episode, magnet)
            if magnet in var.db.blacklisted():
                var.console.debug('Skipping beacause of: blacklist', variables={
                    'magnet': magnet,
                    'title': title,
                    'episode': episode
                })
                var.db.remove(title, episode)
                return
            var.console.info(f'Processing {title} EP{episode}', variables={
                'magnet': magnet
            })
            if not os.path.exists(out):
                if not os.path.exists(inp):
                    await self.download(title, episode, magnet, dl, inp)
                if not os.path.exists(sub):
                    subtitlesOk = await self.patchSubtiles(inp, sub)
                else:
                    subtitlesOk = True
                if not subtitlesOk:
                    var.console.info('Processing aborted - no language', variables={
                        'reason': 'Skipping beacause of: no subtitle language found',
                        'magnet': magnet,
                        'title': title,
                        'episode': episode
                    })
                    var.db.remove(title, episode)
                    var.db.blacklist(magnet)
                    return
                encodeOk = await self.encode(title, episode, inp, out, sub)
                if not encodeOk:
                    var.console.info('Processing aborted - no language', variables={
                        'reason': 'Skipping beacause of: no audio language found',
                        'magnet': magnet,
                        'title': title,
                        'episode': episode
                    })
                    var.db.blacklist(magnet)
                    var.db.remove(title, episode)
                    return
            var.db.update(title, episode, 'status', 'ready')
            var.db.update(title, episode, 'file', out.replace(f'{var.workdir}/public/', ''))
            var.console.info('Processing finished.', variables={
                'file': out.replace(f'{var.workdir}/public/', '')
            })
        except Exception as e:
            var.console.error(f'An exception has occured while processing {title} EP{episode}', variables={
                'type': type(e),
                'message': str(e)
            })
            var.db.remove(title, episode)

    async def convertRes(self, original, target, value):
        return value * (target / original)

    async def download(self, title, episode, magnet, dl, inp):
        var.console.debug('Downloading.')
        var.db.update(title, episode, 'status', 'downloading')
        retries = 0

        while True:
            session = lt.session()
            params = {
                'save_path': './mkv/',
                'url': magnet
            }
            torrent = session.add_torrent(params)

            lastChange = time.time()
            lastPercentage = 0
            restart = False

            status = torrent.status()
            while not status.is_seeding:
                percentage = round(status.progress * 100)
                if lastPercentage == percentage:
                    if time.time() - lastChange > var.config['download_timeout']:
                        restart = True
                        break
                else:
                    lastPercentage = percentage   
                    lastChange = time.time()
                status = torrent.status()
                var.db.update(title, episode, 'status', f'downloading {percentage}%')
                await asyncio.sleep(1)
            
            if not restart:
                session.remove_torrent(torrent)
                session.pause()
                os.rename(dl, inp)
                break

            if retries >= var.config['download_retries']:
                break
            else:
                retries += 1
                var.console.debug('Download stuck, restarting.', variables={
                    'title': title,
                    'episode': episode,
                    'retries': retries
                })


    async def encode(self, title, episode, inp, out, sub):
        var.console.debug('Encoding.')
        var.db.update(title, episode, 'status', 'encoding')

        ffprobe = FFmpeg(executable="ffprobe").input(
            inp,
            print_format="json",
            show_streams=None,
            select_streams='a'
        )
        streams = json.loads(await ffprobe.execute())['streams']
        tags = streams[0]['tags']

        for key in tags:
            if 'DURATION' in key:
                time = datetime.strptime(tags[key][:8], "%H:%M:%S")
                duration = timedelta(hours=time.hour, minutes=time.minute, seconds=time.second).total_seconds()
                break
        var.console.debug('Duration assigned', variables={
            'duration': duration
        })

        mappings = ['0:v:0']
        for i, stream in enumerate(streams):
            if stream['tags']['language'] == var.config['language']['audio']:
                mappings.append(f'0:a:{i}')
                break
        if len(mappings) == 1:
            for i, stream in enumerate(streams):
                if stream['tags']['language'] == var.config['language_fallback']['audio']:
                    mappings.append(f'0:a:{i}')
                    break
        if len(mappings) == 1:
            if var.config['encode_when_no_language']:
                mappings.append('0:a:0')
            else:
                var.console.debug('Audio language not available', variables={
                    'mappings': mappings,
                    'encode_when_no_language': var.config['encode_when_no_language']
                })
                return False
        
        var.console.debug('Mappings assigned', variables={
            'mappings': mappings
        })

        fsub = shlex.quote(sub.replace(':', '\\:'))
        
        encode_options = var.config['encoding'].copy()


        if var.config.get('quicksync', False):
            var.console.debug("Using QuickSync")
            encode_options.pop('vcodec', None) 
            encode_options.pop('vf', None)

            ffmpeg = (
                FFmpeg()
                .option("init_hw_device", "qsv=hw:/dev/dri/renderD128")
                .option("filter_hw_device", "hw")
                .input(
                    inp,
                    hwaccel="qsv",
                    hwaccel_output_format="qsv"
                )
                .output(
                    out,
                    vf=f"hwdownload,format=nv12,subtitles={fsub}",
                    vcodec="h264_qsv",
                    movflags="+faststart",
                    map=mappings,
                    **encode_options
                )
            )
        else:
            ffmpeg = (
                FFmpeg()
                .input(
                    inp
                )
                .output(
                    out,
                    vf=f"subtitles={fsub}",
                    movflags="+faststart",
                    map=mappings,
                    **encode_options
                )
            )

        @ffmpeg.on('progress')
        async def _(progress: Progress):
            pct = round(int(progress.time.total_seconds()) / int(duration) * 100) if duration > 0 else 0
            var.db.update(title, episode, 'status', f'encoding {pct}%')
            await asyncio.sleep(1)

        await ffmpeg.execute()

        os.remove(inp)
        os.remove(sub)
        var.console.debug('Encoding finished', variables={
            'file': out
        })

        return True