"""Opt-in network smoke test. Inspects public metadata, never downloads audio."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from desktop.settings import ROOT, binaries

URLS = {
    'youtube_playlist': 'https://www.youtube.com/playlist?list=PLt5yu3-wZAlSLRHmI1qNm0wjyVNWw1pCU',
    'spotify_single': 'https://open.spotify.com/track/0VjIjW4GlUZAMYd2vXMi3b',
    'spotify_playlist': 'https://open.spotify.com/playlist/37i9dQZF1E8UXBoz02kGID',
}


def inspect(item):
    name, url = item
    p = subprocess.Popen([sys.executable, str(ROOT / 'desktop_app.py'), '--worker'],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
    try:
        out, err = p.communicate(json.dumps({'action': 'inspect', 'url': url, 'deps': binaries()}) + '\n', timeout=90)
        events = [json.loads(line.removeprefix('FREQUENCIA:')) for line in out.splitlines() if line.startswith('FREQUENCIA:')]
        previews = [e for e in events if e['event'] == 'preview']
        if previews:
            return {'name': name, 'ok': True, 'title': previews[0]['title'], 'tracks': len(previews[0]['tracks']),
                    'first_url': previews[0]['tracks'][0]['url']}
        return {'name': name, 'ok': False, 'error': events[-1] if events else err[-500:], 'provider_details': err[-1000:]}
    except subprocess.TimeoutExpired:
        subprocess.run(['taskkill', '/PID', str(p.pid), '/T', '/F'], capture_output=True)
        p.communicate()
        return {'name': name, 'ok': False, 'error': 'Provider timed out after 90 seconds'}


if __name__ == '__main__':
    urls = {k: v for k, v in URLS.items() if '--youtube-only' not in sys.argv or k.startswith('youtube')}
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(inspect, urls.items()))
    playlist = next((r for r in results if r['name'] == 'youtube_playlist' and r['ok']), None)
    if playlist:
        results.append(inspect(('youtube_single', playlist['first_url'])))
    filename = 'smoke-youtube.json' if '--youtube-only' in sys.argv else 'smoke-providers.json'
    (ROOT / 'build' / filename).write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(results, ensure_ascii=True, indent=2))
