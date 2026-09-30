import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from desktop.api import DesktopAPI
from desktop.links import classify
from desktop.settings import Settings, binaries
from desktop import worker

YT = 'https://www.youtube.com/watch?v=abcdefghijk'
PL = 'PL1234567890abcdef'
SP = '1234567890123456789012'


class LinkTests(unittest.TestCase):
    def test_four_kinds(self):
        for url, source, kind in [(YT, 'youtube', 'single'),
            (f'https://youtube.com/playlist?list={PL}', 'youtube', 'playlist'),
            (f'https://open.spotify.com/intl-pt/track/{SP}?si=xyz', 'spotify', 'single'),
            (f'https://open.spotify.com/playlist/{SP}', 'spotify', 'playlist'),
            (f'https://open.spotify.com/album/{SP}', 'spotify', 'album')]:
            with self.subTest(url=url):
                value = classify(url)
                self.assertEqual((value.source, value.kind), (source, kind))

    def test_ambiguous_video_defaults_to_single_and_offers_playlist(self):
        value = classify(YT + '&list=' + PL)
        self.assertEqual(value.kind, 'single')
        self.assertEqual(value.url, YT)
        self.assertTrue(value.playlist_url)
        self.assertEqual(classify(YT + '&list=' + PL, True).kind, 'playlist')

    def test_video_variants(self):
        for url in ['https://youtu.be/abcdefghijk?si=abc', 'https://music.youtube.com/watch?v=abcdefghijk', 'https://youtube.com/shorts/abcdefghijk', 'https://youtube.com/live/abcdefghijk']:
            self.assertEqual(classify(url).url, YT)

    def test_reject_untrusted_hosts_and_unsupported_urls(self):
        for url in [None, [], 'http://youtu.be/abcdefghijk', 'https://youtube.com.evil.org/watch?v=abcdefghijk',
                    'https://user@youtu.be/abcdefghijk', 'https://youtu.be:8443/abcdefghijk',
                    'https://youtu.be:bad/abcdefghijk', 'file:///tmp/video', 'https://localhost/',
                    'https://spotify.link/abc', YT + 'x']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                classify(url)


class SettingsTests(unittest.TestCase):
    def test_round_trip_and_download_default(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'config.json'
            with patch('desktop.settings.user_downloads_dir', return_value=str(Path(temp) / 'Downloads')):
                settings = Settings(path)
            self.assertEqual(settings.value['directory'], str(Path(temp) / 'Downloads'))
            output = str(Path(temp) / 'my-music')
            settings.save(output, '320')
            self.assertEqual(Settings(path).value, {'directory': output, 'quality': '320'})

    def test_corrupt_settings_and_invalid_values(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'config.json'
            for data in ['not JSON', '[]', '{"quality":"999", "directory":null}']:
                path.write_text(data)
                settings = Settings(path)
                self.assertEqual(settings.value['quality'], '192')
            for directory, quality in [('', '192'), ('relative', '192'), (temp, '999')]:
                with self.assertRaises(ValueError):
                    settings.save(directory, quality)

    def test_bundled_binaries_win_without_path(self):
        with tempfile.TemporaryDirectory() as temp:
            vendor = Path(temp) / 'vendor'
            vendor.mkdir()
            import os
            for name in ('ffmpeg', 'ffprobe', 'node'):
                (vendor / (name + ('.exe' if os.name == 'nt' else ''))).touch()
            with patch('desktop.settings.ROOT', Path(temp)), patch('desktop.settings.shutil.which', return_value=None):
                self.assertTrue(all(binaries().values()))


class APITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.api = DesktopAPI(Settings(Path(self.temp.name) / 'settings.json'))

    def test_busy_requests_cannot_replace_current_job(self):
        with patch.object(self.api, '_start') as start:
            self.assertTrue(self.api.inspect_link(YT)['ok'])
            self.assertFalse(self.api.inspect_link(YT)['ok'])
            self.assertEqual(start.call_count, 1)

    def test_preview_must_precede_download_and_no_arbitrary_track_input(self):
        with patch.object(self.api, '_start') as start:
            self.assertFalse(self.api.download_selected(['0'])['ok'])
            self.api._state.update(phase='ready', tracks=[{'id': '0', 'url': YT, 'status': 'done'}, {'id': '1', 'url': YT}])
            with patch('desktop.api.binaries', return_value={'ffmpeg': 'f', 'ffprobe': 'p', 'node': 'n'}):
                self.assertTrue(self.api.download_selected(['0', '1', 'fake'])['ok'])
                self.assertEqual([t['id'] for t in start.call_args.args[0]['tracks']], ['1'])

    def test_state_is_a_snapshot(self):
        snapshot = self.api.get_state()
        snapshot['settings']['quality'] = '999'
        self.assertEqual(self.api.get_state()['settings']['quality'], '192')

    def test_worker_protocol_and_mixed_outcomes(self):
        self.api._state.update(phase='downloading', tracks=[{'id': '0'}, {'id': '1'}])
        process = MagicMock()
        process.stdout = io.StringIO('\n'.join('FREQUENCIA:' + json.dumps(e) for e in [
            {'event': 'track', 'id': '0', 'status': 'done', 'file': 'audio.mp3'},
            {'event': 'track', 'id': '1', 'status': 'error', 'error': 'unavailable'},
            {'event': 'complete'}]))
        process.wait.return_value = 0
        process.poll.return_value = 0
        with patch('desktop.api.subprocess.Popen', return_value=process):
            self.api._run({'action': 'download', 'tracks': [{}, {}]})
        self.assertEqual(self.api.get_state()['phase'], 'complete')
        self.assertEqual([t['status'] for t in self.api.get_state()['tracks']], ['done', 'error'])

    def test_cancel_targets_process_tree(self):
        self.api._state['phase'] = 'downloading'
        process = MagicMock()
        self.api._process = process
        with patch.object(self.api, '_kill') as kill:
            self.api.cancel()
            kill.assert_called_once_with(process)
        self.assertTrue(self.api._cancelled)

    def test_cancel_during_worker_start_is_not_reported_as_error(self):
        self.api._state.update(phase='downloading', tracks=[{'id': '0', 'status': 'queued'}])
        process = MagicMock()
        process.poll.return_value = 0
        def pipe_closed(_):
            self.api._cancelled = True
            raise BrokenPipeError('cancelled before request was sent')
        process.stdin.write.side_effect = pipe_closed
        with patch('desktop.api.subprocess.Popen', return_value=process):
            self.api._run({'action': 'download', 'tracks': [{}]})
        self.assertEqual(self.api.get_state()['phase'], 'cancelled')
        self.assertIsNone(self.api.get_state()['error'])


class WorkerTests(unittest.TestCase):
    def test_spotify_matching_avoids_wrong_artist_and_long_live_version(self):
        track = {'title': 'Example song', 'artist': 'Original Artist', 'duration': 180}
        hits = [{'id': 'cover', 'title': 'Example song', 'uploader': 'Another singer', 'duration': 180},
                {'id': 'live', 'title': 'Original Artist Example song live', 'duration': 320},
                {'id': 'studio', 'title': 'Example song (official audio)', 'uploader': 'Original Artist', 'duration': 182}]
        self.assertEqual(worker.choose_match(track, hits)['id'], 'studio')
        with self.assertRaises(ValueError):
            worker.choose_match(track, hits[:2])

    def test_youtube_playlist_skips_private_entries(self):
        ydl = MagicMock()
        ydl.__enter__.return_value = ydl
        ydl.extract_info.return_value = {'title': 'Playlist', 'entries': [None, {'id': 'abcdefghijk', 'title': '<script>x</script>'}, {'id': 'lmnopqrstuv', 'availability': 'private'}]}
        with patch('yt_dlp.YoutubeDL', return_value=ydl), patch('desktop.worker.emit') as emit:
            worker.inspect({'url': 'https://youtube.com/playlist?list=' + PL, 'deps': {}})
        tracks = emit.call_args.kwargs['tracks']
        self.assertEqual(len(tracks), 1)
        self.assertEqual(tracks[0]['title'], '<script>x</script>')

    def test_spotify_single_and_playlist_metadata(self):
        song = {'name': 'Song', 'artists': [{'name': 'Artist'}], 'duration_ms': 120000,
                'external_urls': {'spotify': f'https://open.spotify.com/track/{SP}'},
                'album': {'name': 'Album', 'images': [{'url': 'https://i.scdn.co/image/abc'}]}, 'track_number': 3}
        client = MagicMock()
        client.track.return_value = song
        client.playlist.return_value = {'name': 'My playlist'}
        client.playlist_items.return_value = {'items': [{'track': song}], 'next': 'next-page'}
        client.next.return_value = {'items': [{'track': None}, {'track': {**song, 'is_local': True}}, {'item': song}], 'next': None}
        tracks_by_kind = {}
        for kind in ('track', 'playlist'):
            with patch('spotdl.utils.spotify.SpotifyClient.init', return_value=client), patch('desktop.worker.emit') as emit:
                worker.inspect({'url': f'https://open.spotify.com/{kind}/{SP}', 'deps': {}})
            tracks_by_kind[kind] = emit.call_args.kwargs['tracks']
            self.assertEqual(tracks_by_kind[kind][0]['query'], 'Song Artist official audio')
            self.assertEqual(len(tracks_by_kind[kind]), 1 if kind == 'track' else 2)
        # Playlist items alone carry no album/cover data; inspect() backfills it
        # with one extra client.track call per playlist track.
        self.assertEqual(client.track.call_count, 1 + len(tracks_by_kind['playlist']))
        for track in tracks_by_kind['playlist']:
            self.assertEqual(track['cover_url'], 'https://i.scdn.co/image/abc')
            self.assertEqual(track['album'], 'Album')

    def test_spotify_album_metadata_reuses_shared_cover(self):
        bare_song = {'name': 'Song', 'artists': [{'name': 'Artist'}], 'duration_ms': 120000,
                     'external_urls': {'spotify': f'https://open.spotify.com/track/{SP}'}, 'track_number': 3}
        client = MagicMock()
        client.album.return_value = {'name': 'Album', 'images': [{'url': 'https://i.scdn.co/image/abc'}]}
        client.album_tracks.return_value = {'items': [bare_song, None], 'next': None}
        with patch('spotdl.utils.spotify.SpotifyClient.init', return_value=client), patch('desktop.worker.emit') as emit:
            worker.inspect({'url': f'https://open.spotify.com/album/{SP}', 'deps': {}})
        tracks = emit.call_args.kwargs['tracks']
        self.assertEqual(len(tracks), 1)
        self.assertEqual(tracks[0]['album'], 'Album')
        self.assertEqual(tracks[0]['cover_url'], 'https://i.scdn.co/image/abc')
        self.assertEqual(emit.call_args.kwargs['title'], 'Album')
        client.track.assert_not_called()

    def test_failed_track_does_not_abort_batch(self):
        with tempfile.TemporaryDirectory() as temp:
            ydl = MagicMock()
            ydl.__enter__.return_value = ydl
            ydl.extract_info.side_effect = RuntimeError('unavailable')
            tracks = [{'id': str(i), 'url': YT, 'source': 'youtube'} for i in range(2)]
            with patch('yt_dlp.YoutubeDL', return_value=ydl), patch('desktop.worker.emit') as emit:
                worker.download({'tracks': tracks, 'deps': {}, 'settings': {'directory': temp, 'quality': '192'}})
            errors = [c for c in emit.call_args_list if c.kwargs.get('status') == 'error']
            self.assertEqual(len(errors), 2)
            self.assertEqual(emit.call_args.args, ('complete',))


class ConversionIntegrationTests(unittest.TestCase):
    def test_real_ytdlp_ffmpeg_conversion_offline(self):
        """Use an original generated tone; no third-party media or network required."""
        deps = binaries()
        if not deps['ffmpeg'] or not deps['ffprobe']:
            self.skipTest('FFmpeg and FFprobe required for integration test')
        from yt_dlp import YoutubeDL
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'original.wav'
            subprocess.run([deps['ffmpeg'], '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1', str(source)], check=True, capture_output=True)
            opts = worker.options(deps)
            opts.update({'enable_file_urls': True, 'outtmpl': str(Path(temp) / 'converted.%(ext)s'),
                         'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]})
            with YoutubeDL(opts) as ydl:
                ydl.extract_info(source.as_uri(), download=True)
            output = Path(temp) / 'converted.mp3'
            self.assertGreater(output.stat().st_size, 1000)
            result = subprocess.run([deps['ffprobe'], '-v', 'error', '-show_entries', 'stream=codec_name', '-of', 'json', str(output)], capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout)['streams'][0]['codec_name'], 'mp3')

    def test_spotify_metadata_tags_cover_and_renames_file(self):
        deps = binaries()
        if not deps['ffmpeg'] or not deps['ffprobe']:
            self.skipTest('FFmpeg and FFprobe required for integration test')
        from yt_dlp import YoutubeDL
        from mutagen.id3 import ID3
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'original.wav'
            subprocess.run([deps['ffmpeg'], '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1', str(source)], check=True, capture_output=True)
            opts = worker.options(deps)
            opts.update({'enable_file_urls': True, 'outtmpl': str(Path(temp) / 'Example Video [abcdefghijk].%(ext)s'),
                         'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]})
            with YoutubeDL(opts) as ydl:
                ydl.extract_info(source.as_uri(), download=True)
            downloaded = Path(temp) / 'Example Video [abcdefghijk].mp3'
            track = {'title': 'Blinding Lights', 'artist': 'The Weeknd', 'album': 'After Hours',
                     'track_number': 9, 'cover_url': 'https://example.invalid/cover.jpg'}

            class FakeResponse(io.BytesIO):
                headers = type('H', (), {'get_content_type': lambda self: 'image/jpeg'})()
                def __enter__(self): return self
                def __exit__(self, *args): return False

            with patch('desktop.worker.urllib.request.urlopen', return_value=FakeResponse(b'\xff\xd8\xff\xe0fakejpeg')):
                result = worker.apply_spotify_metadata(downloaded, track)
            self.assertEqual(result.name, 'The Weeknd - Blinding Lights.mp3')
            self.assertFalse(downloaded.exists())
            self.assertTrue(result.exists())
            tags = ID3(result)
            self.assertEqual(str(tags['TIT2']), 'Blinding Lights')
            self.assertEqual(str(tags['TPE1']), 'The Weeknd')
            self.assertEqual(str(tags['TALB']), 'After Hours')
            self.assertEqual(str(tags['TRCK']), '9')
            covers = tags.getall('APIC')
            self.assertEqual(len(covers), 1)
            self.assertEqual(covers[0].mime, 'image/jpeg')
            self.assertEqual(covers[0].data, b'\xff\xd8\xff\xe0fakejpeg')

    def test_sanitize_filename_part_strips_invalid_characters(self):
        self.assertEqual(worker.sanitize_filename_part('AC/DC: "Hell" <2>'), 'ACDC Hell 2')
        self.assertEqual(worker.sanitize_filename_part('   '), 'Sem título')


if __name__ == '__main__':
    unittest.main()
