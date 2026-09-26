"""Strict, offline classification. Never resolve arbitrary redirects."""
from dataclasses import asdict, dataclass
import re
from urllib.parse import parse_qs, urlsplit


@dataclass(frozen=True)
class MediaLink:
    source: str
    kind: str
    url: str
    playlist_url: str | None = None

    def to_dict(self):
        return asdict(self)


def classify(value: str, playlist: bool = False) -> MediaLink:
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError('Cole um link do YouTube ou Spotify.')
    try:
        u = urlsplit(value.strip())
        if u.scheme != 'https' or u.username or u.password or u.port not in (None, 443):
            raise ValueError()
        if u.hostname == 'open.spotify.com':
            m = re.fullmatch(r'/(?:intl-[a-z]{2}(?:-[a-z]{2})?/)?(track|playlist)/([A-Za-z0-9]{22})/?', u.path)
            if m:
                return MediaLink('spotify', 'single' if m[1] == 'track' else 'playlist',
                                 f'https://open.spotify.com/{m[1]}/{m[2]}')
        if u.hostname in {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtu.be'}:
            q = parse_qs(u.query)
            pid = q.get('list', [''])[0]
            pu = f'https://www.youtube.com/playlist?list={pid}' if re.fullmatch(r'[A-Za-z0-9_-]{10,100}', pid) else None
            vid = ''
            if u.hostname == 'youtu.be':
                vid = u.path.strip('/')
            elif u.path == '/watch':
                vid = q.get('v', [''])[0]
            elif u.path == '/playlist' and pu:
                return MediaLink('youtube', 'playlist', pu)
            else:
                m = re.fullmatch(r'/(?:shorts|embed|live)/([A-Za-z0-9_-]{11})/?', u.path)
                vid = m[1] if m else ''
            if re.fullmatch(r'[A-Za-z0-9_-]{11}', vid):
                if playlist and pu:
                    return MediaLink('youtube', 'playlist', pu)
                return MediaLink('youtube', 'single', f'https://www.youtube.com/watch?v={vid}', pu)
    except ValueError:
        pass
    raise ValueError('Use um link HTTPS de vídeo, faixa ou playlist do YouTube ou Spotify. Links encurtados do Spotify e álbuns não são aceitos.')
