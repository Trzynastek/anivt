import bencodepy, hashlib, base64, shlex, urllib.parse, os, re, asyncio, json, requests
from datetime import datetime, timedelta
import libtorrent as lt
from ffmpeg import Progress
from ffmpeg.asyncio import FFmpeg
from modules import variables as var

class instance():
    def __init__(self):
        subPath = os.getcwd() + '/subtitles'
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

        for i, stream in enumerate(streams):
            if stream['tags']['language'] == var.config['language']['subtitles']:
                mappings = f'0:s:{i}'
                break
        else:
            mappings = '0:s:0'

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

        overrides = []
        for key in var.config['subtitles']:
            if key in keys:
                overrides.append({'index': keys.index(key), 'value': var.config['subtitles'][key]})

        with open(sub, 'w', encoding='utf-8') as f:
            for line in lines:
                if line.startswith('Style:'):
                    values = line.strip().split(',')
                    for entry in overrides:
                        values[entry['index']] = entry['value']
                    line = ', '.join(str(v) for v in values) + '\n'
                    f.write(line)
                elif line.startswith('PlayRes'):
                    if line.startswith('PlayResX'):
                        line = f'PlayResX: {var.config["subtitles"]["resX"]} \n'
                    else:
                        line = f'PlayResY: {var.config["subtitles"]["resY"]} \n'
                    f.write(line)
                else:
                    f.write(line)
        var.console.debug('Subtitles patched', variables={
            'inp': inp,
            'sub': sub
        })

    async def preCheck(self, title, episode, magnet):
        file = os.getcwd() + '/mkv/' + f'{title}[Ep.{episode}].mkv'
        inp = re.sub(r'[^A-Za-z0-9 /\[\].]+', '', file).replace(' ', '_')
        out = inp.replace('.mkv', '.mp4').replace('/mkv/', '/public/mp4/')
        sub = inp.replace('.mkv', '.ass').replace('/mkv/', '/subtitles/')
        exists = False

        if os.path.exists(out):
            var.db.update(title, episode, 'status', 'ready')
            var.db.update(title, episode, 'file', out.replace(f'{os.getcwd()}/public/', ''))
        elif not os.path.exists(inp):
            res = requests.get(magnet)
            data = res.content
            magnet = await self.toMagnet(data)
            query = urllib.parse.urlparse(magnet).query
            dl = os.getcwd() + '/mkv/' + urllib.parse.parse_qs(query).get('dn', [None])[0]
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
        var.console.info(f'Processing {title} EP{episode}', variables={
            'magnet': magnet
        })
        inp, out, magnet, dl, sub = await self.preCheck(title, episode, magnet)
        if not os.path.exists(out):
            if not os.path.exists(inp):
                await self.download(title, episode, magnet, dl, inp)
            if not os.path.exists(sub):
                await self.patchSubtiles(inp, sub)
            await self.encode(title, episode, inp, out, sub)
        var.db.update(title, episode, 'status', 'ready')
        var.db.update(title, episode, 'file', out.replace(f'{os.getcwd()}/public/', ''))
        var.console.info('Processing finished.', variables={
            'file': out.replace(f'{os.getcwd()}/public/', '')
        })

    async def download(self, title, episode, magnet, dl, inp):
        var.console.debug('Downloading.')
        var.db.update(title, episode, 'status', 'downloading')
        session = lt.session()
        params = {
            'save_path': './mkv/',
            'url': magnet
        }
        torrent = session.add_torrent(params)

        status = torrent.status()
        while not status.is_seeding:
            status = torrent.status()
            var.db.update(title, episode, 'status', f'downloading {round(status.progress * 100)}%')
            await asyncio.sleep(1)

        session.remove_torrent(torrent)
        session.pause()
        os.rename(dl, inp)

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
            codec_name = stream.get('codec_name')
            if codec_name == var.config['encoding']['acodec'] and stream['tags']['language'] == var.config['language']['audio']:
                mappings.append(f'0:a:{i}')
                break
        else:
            mappings.append('0:a:0')
        
        var.console.debug('Mappings assigned', variables={
            'mappings': mappings
        })

        fsub = shlex.quote(sub.replace(':', '\\:'))
        ffmpeg = (
            FFmpeg()
            .input(inp)
            .output(
                out,
                vf=f"subtitles={fsub}",
                movflags="+faststart",
                map=mappings,
                **var.config['encoding']
            )
        )

        @ffmpeg.on('progress')
        async def _(progress: Progress):
            var.db.update(title, episode, 'status', f'encoding {round(int(progress.time.total_seconds()) / int(duration) * 100)}%')
            await asyncio.sleep(1)

        await ffmpeg.execute()

        os.remove(inp)
        os.remove(sub)
        var.console.debug('Encoding finished', variables={
            'file': out
        })