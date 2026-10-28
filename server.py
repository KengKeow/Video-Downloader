"""SaveNest local web server.

Starts on http://127.0.0.1:8765 . Only YouTube URLs are accepted by the API.
Requires `pip install -r requirements.txt`. FFmpeg optional for HD muxing.
"""
import json
import mimetypes
import re
import shutil
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

try:
    import yt_dlp
except ImportError:
    raise SystemExit("Install dependencies first: python -m pip install -r requirements.txt")

ROOT = Path(__file__).parent.resolve()
MAX_DURATION = 60 * 60  # one hour per video for a friendly local tool
MAX_SIZE = 350 * 1024 * 1024


def valid_url(candidate):
    """Accept only ordinary YouTube video pages; reject arbitrary remote hosts."""
    try:
        parsed = urlparse(candidate)
        host = (parsed.hostname or '').lower()
        if parsed.scheme not in ('https', 'http'):
            return False
        if host not in ('youtube.com', 'youtu.be', 'www.youtu.be') and not host.endswith('.youtube.com'):
            return False
        if host in ('youtu.be', 'www.youtu.be'):
            video_id = parsed.path.strip('/').split('/')[0]
        else:
            params = parse_qs(parsed.query)
            match = re.match(r'^/(?:shorts|live|embed)/([A-Za-z0-9_-]{11})(?:/|$)', parsed.path)
            video_id = (params.get('v') or [''])[0] or (match.group(1) if match else '')
        return bool(re.fullmatch(r'[\w-]{11}', video_id))
    except (ValueError, TypeError):
        return False


def ydl_opts(**kwargs):
    return dict(quiet=True, no_warnings=True, noplaylist=True, socket_timeout=18,
                ignoreerrors=False, **kwargs)


def metadata(url):
    with yt_dlp.YoutubeDL(ydl_opts(skip_download=True)) as dl:
        info = dl.extract_info(url, download=False)
    if not info or info.get('is_live'):
        raise ValueError('Live streams and unavailable videos are not supported.')
    if (info.get('duration') or 0) > MAX_DURATION:
        raise ValueError('This demo supports videos up to 60 minutes long.')
    return info


def available_formats(info):
    progressive = {}
    video_only = set()
    audio_m4a = False
    for f in info.get('formats') or []:
        if f.get('ext') != 'mp4' and not (f.get('vcodec') == 'none' and f.get('ext') == 'm4a'):
            continue
        if f.get('protocol') not in ('http', 'https'):
            continue
        if f.get('vcodec') == 'none':
            audio_m4a = True
            continue
        height = f.get('height')
        if not isinstance(height, int) or height < 144:
            continue
        size = f.get('filesize') or f.get('filesize_approx') or 0
        if size > MAX_SIZE:
            continue
        if f.get('acodec') == 'none':
            video_only.add(height)
        else:
            old = progressive.get(height)
            if not old or (f.get('tbr') or 0) > (old.get('tbr') or 0):
                progressive[height] = f
    result = []
    # Only offer merged resolutions actually represented among source video streams.
    if shutil.which('ffmpeg') and audio_m4a:
        for height in sorted(video_only, reverse=True):
            if height > 2160 or height in progressive:
                continue
            result.append({'id': f'merge:{height}', 'label': f'MP4 {height}p', 'size': 'video + audio', 'height': height})
    for height, f in progressive.items():
        size = f.get('filesize') or f.get('filesize_approx')
        size_str = f'{size / 1024 / 1024:.1f} MB' if size else None
        result.append({'id': str(f.get('format_id')), 'label': f'MP4 {height}p', 'size': size_str, 'height': height})
    return sorted(result, key=lambda it: (it['height'], 'merge:' in it['id']), reverse=True)[:10]


class Handler(BaseHTTPRequestHandler):
    def respond_json(self, code, obj):
        body = json.dumps(obj).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path)
        if path.path in ('/', '/index.html'):
            content = (ROOT / 'index.html').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(content)
            return
        if path.path not in ('/api/info', '/api/download'):
            self.respond_json(404, {'error': 'Not found'})
            return
        params = parse_qs(path.query)
        url = (params.get('url') or [''])[0]
        if not valid_url(url):
            self.respond_json(400, {'error': 'Please enter a valid YouTube video URL.'})
            return
        try:
            info = metadata(url)
            available = available_formats(info)
            if path.path == '/api/info':
                self.respond_json(200, {
                    'title': info.get('title') or 'Untitled video',
                    'uploader': info.get('uploader') or 'YouTube',
                    'duration': info.get('duration'),
                    'formats': available,
                })
                return
            choice = (params.get('format_id') or [''])[0]
            if choice not in {f['id'] for f in available}:
                self.respond_json(400, {'error': 'This format is unavailable.'})
                return
            if choice.startswith('merge:'):
                target = int(choice.split(':')[1])
                format_string = f'bestvideo[height={target}][ext=mp4]+bestaudio[ext=m4a]/best[height={target}][ext=mp4]'
            else:
                format_string = choice
            with tempfile.TemporaryDirectory(prefix='savenest_') as folder:
                options = ydl_opts(format=format_string,
                                   outtmpl=str(Path(folder) / '%(title).100s-%(id)s.%(ext)s'),
                                   max_filesize=MAX_SIZE,
                                   merge_output_format='mp4',
                                   restrictfilenames=True,
                                   noprogress=True)
                with yt_dlp.YoutubeDL(options) as dl:
                    dl.download([url])
                downloaded = [p for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() == '.mp4']
                if not downloaded:
                    raise RuntimeError('MP4 was not produced. Check source availability and FFmpeg installation.')
                file = max(downloaded, key=lambda p: p.stat().st_size)
                size = file.stat().st_size
                if size > MAX_SIZE:
                    raise ValueError('File exceeds the 350 MB local demo limit.')
                self.send_response(200)
                self.send_header('Content-Type', 'video/mp4')
                self.send_header('Content-Length', str(size))
                # Safe filename generated by yt-dlp restrictfilenames option.
                self.send_header('Content-Disposition', f'attachment; filename="{file.name}"')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.end_headers()
                with file.open('rb') as stream:
                    shutil.copyfileobj(stream, self.wfile, 1024 * 1024)
        except (BrokenPipeError, ConnectionResetError):
            pass  # browser canceled download
        except Exception as exc:
            print('Request error:', type(exc).__name__, str(exc))
            try:
                self.respond_json(502, {'error': str(exc)[:350]})
            except (BrokenPipeError, ConnectionResetError):
                pass


if __name__ == '__main__':
    print('\nSaveNest started! Open http://127.0.0.1:8765 in your browser.')
    print('Press Ctrl+C to stop the local server.\n')
    ThreadingHTTPServer(('127.0.0.1', 8765), Handler).serve_forever()
