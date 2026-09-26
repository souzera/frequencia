"""Isolated media worker. Emits only prefixed JSON events to the desktop bridge."""
import json
from pathlib import Path
import sys
import time
import re
import unicodedata

from desktop.links import classify


def emit(kind, **data):
    print('FREQUENCIA:' + json.dumps({'event': kind, **data}, ensure_ascii=True), flush=True)


def options(deps):
    result = {'quiet': True, 'no_warnings': True, 'noprogress': True, 'socket_timeout': 20,
              'retries': 2, 'fragment_retries': 2, 'noplaylist': True}
    if deps.get('node'):
        result['js_runtimes'] = {'node': {'path': deps['node']}}
    if deps.get('ffmpeg'):
        result['ffmpeg_location'] = str(Path(deps['ffmpeg']).parent)
    return result


def choose_match(track, candidates):
    """Prefer matching title/artist and duration; reject clearly unrelated hits."""
    def words(text):
        plain = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()
        return set(re.findall(r'[a-z0-9]+', plain))
    title, artist = words(track['title']), words(track['artist'])
    ranked = []
    for item in candidates:
        if not item or item.get('is_live'):
            continue
        text = words(' '.join(str(item.get(k) or '') for k in ('title', 'uploader', 'channel')))
        title_score = len(title & text) / max(len(title), 1)
        artist_score = len(artist & text) / max(len(artist), 1)
        duration_score = 0
        if track.get('duration') and item.get('duration'):
            difference = abs(track['duration'] - item['duration'])
            if difference > max(30, track['duration'] * .2):
                continue
            duration_score = 1 - min(difference / 30, 1)
        if title_score < .5 or not artist_score:
            continue
        ranked.append((title_score * .65 + artist_score * .2 + duration_score * .15, item))
    if not ranked:
        raise ValueError('Não encontramos uma correspondência confiável no YouTube. Tente um link direto do vídeo.')
    return max(ranked, key=lambda entry: entry[0])[1]


def inspect(request):
    link = classify(request['url'], request.get('playlist', False))
    tracks = []
    title = 'Sua seleção'
    if link.source == 'spotify':
        from spotdl.utils.spotify import SpotifyClient
        from spotdl.utils.config import SPOTIFY_OPTIONS
        client = SpotifyClient.init(client_id=SPOTIFY_OPTIONS['client_id'], client_secret=SPOTIFY_OPTIONS['client_secret'], no_cache=True)
        if link.kind == 'single':
            songs = [client.track(link.url)]
        else:
            # Playlist responses already include the needed metadata. Avoid
            # fetching each track, artist and album separately (3N requests).
            meta = client.playlist(link.url)
            title = meta.get('name') or 'Playlist do Spotify'
            songs = []
            page = client.playlist_items(link.url)
            while page:
                songs.extend(item.get('track') or item.get('item') for item in page.get('items', []) if isinstance(item, dict))
                page = client.next(page) if page.get('next') else None
        for song in songs:
            if not song or song.get('is_local') or song.get('type', 'track') != 'track' or not song.get('name'):
                continue
            artists = [a.get('name') or a.get('profile', {}).get('name', '') for a in song.get('artists', [])]
            artists = [a for a in artists if a]
            url = (song.get('external_urls') or {}).get('spotify')
            if not url or not artists:
                continue
            try:
                canonical = classify(url)
            except ValueError:
                continue
            if canonical.source != 'spotify' or canonical.kind != 'single':
                continue
            tracks.append({'title': song['name'], 'artist': ', '.join(artists),
                           'duration': (song.get('duration_ms') or 0) / 1000, 'url': canonical.url,
                           'query': f'{song["name"]} {" ".join(artists)} official audio', 'source': 'spotify'})
        if link.kind == 'single' and tracks:
            title = tracks[0]['title']
    else:
        from yt_dlp import YoutubeDL
        opts = options(request['deps'])
        opts.update({'extract_flat': 'in_playlist', 'noplaylist': link.kind != 'playlist', 'ignoreerrors': True})
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(link.url, download=False)
        if not info:
            raise ValueError('Este link está indisponível ou exige autenticação.')
        title = info.get('title') or title
        entries = info.get('entries', []) if link.kind == 'playlist' else [info]
        for entry in entries:
            if not entry or not entry.get('id'):
                continue
            if entry.get('availability') in ('private', 'premium_only', 'subscriber_only'):
                continue
            try:
                url = classify('https://www.youtube.com/watch?v=' + entry['id']).url
            except ValueError:
                continue
            tracks.append({'title': entry.get('title') or 'Vídeo sem título',
                           'artist': entry.get('uploader') or entry.get('channel') or 'YouTube',
                           'duration': entry.get('duration'), 'url': url, 'source': 'youtube'})
    if not tracks:
        raise ValueError('Nenhuma faixa acessível foi encontrada neste link.')
    for i, track in enumerate(tracks):
        track['id'] = str(i)
    emit('preview', title=title, tracks=tracks, link=link.to_dict())


def download(request):
    from yt_dlp import YoutubeDL
    from mutagen.easyid3 import EasyID3
    from mutagen.id3 import ID3NoHeaderError
    destination = Path(request['settings']['directory'])
    destination.mkdir(parents=True, exist_ok=True)
    total = len(request['tracks'])
    for index, track in enumerate(request['tracks']):
        emit('track', id=track['id'], status='downloading', percent=0, current=index + 1, total=total)
        last = [0.0]
        def progress(data):
            now = time.monotonic()
            if now - last[0] < .25 and data['status'] != 'finished':
                return
            last[0] = now
            size = data.get('total_bytes') or data.get('total_bytes_estimate') or 0
            percent = min(99, round(data.get('downloaded_bytes', 0) * 100 / size)) if size else 0
            emit('track', id=track['id'], status='converting' if data['status'] == 'finished' else 'downloading', percent=percent)
        try:
            opts = options(request['deps'])
            opts.update({'format': 'bestaudio/best', 'windowsfilenames': True,
                         'overwrites': False, 'progress_hooks': [progress],
                         'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3',
                                             'preferredquality': request['settings']['quality']}],
                         'outtmpl': str(destination / '%(title).160B [%(id)s].%(ext)s')})
            with YoutubeDL(opts) as ydl:
                target = track['url']
                if track['source'] == 'spotify':
                    search_opts = options(request['deps'])
                    search_opts['extract_flat'] = True
                    with YoutubeDL(search_opts) as searcher:
                        search = searcher.extract_info('ytsearch5:' + track['query'], download=False)
                    matches = list((search or {}).get('entries') or [])
                    if not matches:
                        raise ValueError('Nenhum áudio correspondente encontrado no YouTube.')
                    match = choose_match(track, matches)
                    target = classify('https://www.youtube.com/watch?v=' + match['id']).url
                    emit('match', id=track['id'], matched_title=match.get('title'), matched_url=target)
                info = ydl.extract_info(target, download=True)
                file = Path(ydl.prepare_filename(info)).with_suffix('.mp3')
            if not file.is_file() or file.stat().st_size == 0:
                raise ValueError('O conversor não gerou o arquivo MP3.')
            if track['source'] == 'spotify':
                try:
                    tags = EasyID3(file)
                except ID3NoHeaderError:
                    tags = EasyID3()
                tags['title'], tags['artist'] = track['title'], track['artist']
                tags.save(file)
            emit('track', id=track['id'], status='done', percent=100, file=str(file))
        except Exception as exc:
            emit('track', id=track['id'], status='error', error=str(exc)[-700:])
    emit('complete')


def main():
    try:
        request = json.loads(sys.stdin.readline())
        (inspect if request['action'] == 'inspect' else download)(request)
    except Exception as exc:
        emit('error', error=str(exc)[-900:])
        return 1
    return 0
