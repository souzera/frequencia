"""Small synchronous download blueprint; one isolated directory per request."""
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from urllib.parse import parse_qs, urlsplit

from flask import Blueprint, current_app, jsonify, request, send_file

bp = Blueprint('media', __name__, url_prefix='/api/media')
YOUTUBE_HOSTS = {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com'}


def parse_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError('Informe um link válido do Spotify ou YouTube.')
    try:
        url = urlsplit(value.strip())
        if (url.scheme != 'https' or url.username or url.password
                or url.port not in (None, 443)):
            raise ValueError()
        if url.hostname == 'open.spotify.com':
            match = re.fullmatch(r'/(?:intl-[a-z]{2}/)?track/([A-Za-z0-9]{22})/?', url.path)
            if not match:
                raise ValueError('Use uma faixa individual do Spotify; playlists e álbuns não são aceitos.')
            return 'spotify', 'https://open.spotify.com/track/' + match[1]
        video_id = None
        if url.hostname == 'youtu.be':
            video_id = url.path.strip('/')
        elif url.hostname in YOUTUBE_HOSTS:
            if url.path == '/watch':
                video_id = parse_qs(url.query).get('v', [None])[0]
            else:
                match = re.fullmatch(r'/(?:shorts|embed|live)/([\w-]{11})/?', url.path)
                video_id = match[1] if match else None
        if video_id and re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
            return 'youtube', 'https://www.youtube.com/watch?v=' + video_id
    except ValueError as exc:
        if str(exc).startswith('Use uma faixa'):
            raise
    raise ValueError('Use um link HTTPS de uma faixa do Spotify ou de um vídeo do YouTube.')


def execute(command, directory, timeout):
    # Log to disk to avoid a full pipe or unbounded memory usage.
    with (directory / 'download.log').open('wb') as log:
        process = subprocess.Popen(
            command, cwd=directory, stdout=log, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, start_new_session=os.name != 'nt',
        )
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            # Terminate FFmpeg and other descendants before removing temporary files.
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if process.poll() is None:
                process.kill()
            process.wait()
            raise
        if code:
            raise RuntimeError('O provedor não conseguiu preparar esta mídia. Confira se ela está disponível e tente novamente.')


def download_media(source, url, kind, directory):
    ffmpeg = os.environ.get('FFMPEG_PATH') or shutil.which('ffmpeg')
    if not ffmpeg:
        raise RuntimeError('FFmpeg não encontrado. Instale-o ou configure FFMPEG_PATH no servidor.')
    if source == 'spotify':
        command = [sys.executable, '-m', 'spotdl', 'download', url,
                   '--format', 'mp3', '--output', str(directory / 'audio.{output-ext}'),
                   '--ffmpeg', ffmpeg, '--threads', '1', '--yt-dlp-args=--js-runtimes node']
    else:
        command = [sys.executable, '-m', 'yt_dlp', '--ignore-config', '--no-playlist',
                   '--no-progress', '--no-warnings', '--js-runtimes', 'node', '--socket-timeout', '20',
                   '--retries', '2', '--fragment-retries', '2',
                   '--max-filesize', '200M', '--match-filter', '!is_live & !is_upcoming & duration <= 1200',
                   '--ffmpeg-location', ffmpeg, '-o', str(directory / 'media.%(ext)s')]
        if kind == 'audio':
            command += ['-f', 'bestaudio/best', '-x', '--audio-format', 'mp3', '--audio-quality', '192K']
        else:
            command += ['-f', 'bv[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720][ext=mp4]',
                        '--merge-output-format', 'mp4']
        command += ['--', url]
    execute(command, directory, current_app.config['MEDIA_TIMEOUT'])
    extension = '.mp3' if kind == 'audio' else '.mp4'
    files = list(directory.glob('*' + extension))
    if len(files) != 1 or files[0].stat().st_size == 0:
        raise RuntimeError('Nenhum arquivo foi gerado. Vídeos ao vivo, acima de 20 minutos ou sem formato compatível não são aceitos.')
    if files[0].stat().st_size > current_app.config['MEDIA_MAX_BYTES']:
        raise RuntimeError('O arquivo ultrapassou o limite de 200 MB.')
    return files[0]


@bp.post('/inspect')
def inspect_url():
    body = request.get_json(silent=True)
    try:
        source, _ = parse_url(body.get('url') if isinstance(body, dict) else None)
        return jsonify(source=source)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400


@bp.post('/download')
def download():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(error='Envie um objeto JSON válido.'), 400
    try:
        source, url = parse_url(body.get('url'))
        kind = body.get('type', 'audio')
        if kind not in ('audio', 'video'):
            raise ValueError('Escolha áudio ou vídeo.')
        if source == 'spotify' and kind != 'audio':
            raise ValueError('Links do Spotify permitem apenas áudio.')
        if body.get('authorized') is not True:
            raise ValueError('Confirme que você tem direito ou autorização para baixar este conteúdo.')
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    temp = tempfile.TemporaryDirectory(prefix='portal-media-')
    try:
        media = download_media(source, url, kind, Path(temp.name))
        response = send_file(media, as_attachment=True, download_name='audio.mp3' if kind == 'audio' else 'video.mp4', conditional=False)
        response.headers['Cache-Control'] = 'no-store'
        # Ensure WSGI closes the file before deleting its directory, also on Windows.
        response.direct_passthrough = False
        response.call_on_close(temp.cleanup)
        return response
    except subprocess.TimeoutExpired:
        temp.cleanup()
        return jsonify(error='O preparo excedeu o tempo limite. Tente um conteúdo mais curto.'), 504
    except RuntimeError as exc:
        temp.cleanup()
        return jsonify(error=str(exc)), 502
    except Exception:
        current_app.logger.exception('Falha ao preparar mídia')
        temp.cleanup()
        return jsonify(error='Não foi possível preparar o arquivo. Verifique a configuração do servidor.'), 500

