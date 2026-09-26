import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import create_app
from media import parse_url, execute

YT = 'https://youtu.be/abcdefghijk'
SP = 'https://open.spotify.com/track/1234567890123456789012'

class MediaTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({'TESTING': True})
        self.client = self.app.test_client()

    def test_valid_urls_are_canonical(self):
        self.assertEqual(parse_url(YT + '?list=evil')[1], 'https://www.youtube.com/watch?v=abcdefghijk')
        self.assertEqual(parse_url(SP)[0], 'spotify')
        self.assertEqual(parse_url('https://www.youtube.com/shorts/abcdefghijk')[0], 'youtube')

    def test_invalid_urls(self):
        for value in [None, [], 'http://youtu.be/abcdefghijk', 'https://youtube.com.evil.com/watch?v=abcdefghijk', 'https://user@youtu.be/abcdefghijk', 'https://youtu.be:8080/abcdefghijk', 'https://open.spotify.com/playlist/123', 'https://localhost/test', 'https://youtube.com/playlist?list=123']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_url(value)

    def test_validation_never_starts_download(self):
        with patch('media.download_media') as download:
            cases = [[], {'url': YT}, {'url': YT, 'authorized': 'true'}, {'url': SP, 'type': 'video', 'authorized': True}, {'url': YT, 'type': 'other', 'authorized': True}]
            for body in cases:
                self.assertEqual(self.client.post('/api/media/download', json=body).status_code, 400)
            download.assert_not_called()

    def test_home_and_inspection(self):
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertEqual(self.client.post('/api/media/inspect', json={'url': YT}).json['source'], 'youtube')

    def test_stream_and_cleanup(self):
        directories = []
        def fake(source, url, kind, directory):
            directories.append(directory)
            result = directory / 'audio.mp3'
            result.write_bytes(b'fake-audio')
            return result
        with patch('media.download_media', side_effect=fake):
            response = self.client.post('/api/media/download', json={'url': YT, 'authorized': True})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, b'fake-audio')
            self.assertIn('attachment', response.headers['Content-Disposition'])
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            response.close()
        self.assertFalse(directories[0].exists())

    def test_failure_cleanup(self):
        for failure, expected in [(subprocess.TimeoutExpired('test', 1), 504), (RuntimeError('Unavailable'), 502)]:
            directories = []
            def fake(source, url, kind, directory):
                directories.append(directory)
                raise failure
            with patch('media.download_media', side_effect=fake):
                response = self.client.post('/api/media/download', json={'url': YT, 'authorized': True})
                self.assertEqual(response.status_code, expected)
                self.assertFalse(directories[0].exists())

    def test_commands_and_file_validation(self):
        def fake(command, directory, timeout):
            self.assertNotIn('shell', command)
            name = 'audio.mp3' if 'spotdl' in command else 'media.mp4'
            (directory / name).write_bytes(b'media')
        from media import download_media
        with self.app.app_context(), tempfile.TemporaryDirectory() as temp, patch('media.shutil.which', return_value='ffmpeg'), patch('media.execute', side_effect=fake) as run:
            directory = Path(temp)
            self.assertEqual(download_media('spotify', SP, 'audio', directory).suffix, '.mp3')
            self.assertIn('spotdl', run.call_args.args[0])
            self.assertEqual(download_media('youtube', YT, 'video', directory).suffix, '.mp4')
            self.assertIn('--no-playlist', run.call_args.args[0])
            self.app.config['MEDIA_MAX_BYTES'] = 1
            with self.assertRaises(RuntimeError):
                download_media('youtube', YT, 'video', directory)

    def test_real_process_timeout(self):
        import sys
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(subprocess.TimeoutExpired):
                execute([sys.executable, '-c', 'import time; time.sleep(30)'], Path(temp), 0.2)

if __name__ == '__main__':
    unittest.main()
