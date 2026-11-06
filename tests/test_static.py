import tempfile
import json
import re
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

import youtube_metadata as metadata
from ickost_final import SPOT_DATA, app


class StaticTests(unittest.TestCase):
    def setUp(self):
        self.cache = patch.object(metadata, 'CACHE', {'videos': {}, 'channels': {}})
        self.cache.start()
        self.addCleanup(self.cache.stop)

    def test_refresh_batches_and_reuses_metadata(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(metadata, 'CACHE_PATH', Path(directory) / 'cache.json'), \
                patch.object(metadata, '_loaded', False), \
                patch.dict('os.environ', {'YOUTUBE_API_KEY': 'test-only'}), \
                patch.object(metadata, '_fetch', return_value=[]) as fetch:
            ids = [f'video-{i}' for i in range(75)]
            metadata.refresh(ids + ids, 'channel')
            metadata.refresh(ids, 'channel')
            self.assertEqual(fetch.call_count, 3)
            self.assertEqual([len(call.args[1]) for call in fetch.call_args_list], [50, 25, 1])
            self.assertNotIn('test-only', metadata.CACHE_PATH.read_text())

    def test_failure_keeps_previous_metadata(self):
        metadata.CACHE['videos']['old'] = {'snippet': {'title': 'Existing'}}
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(metadata, 'CACHE_PATH', Path(directory) / 'cache.json'), \
                patch.object(metadata, '_loaded', False), \
                patch.dict('os.environ', {'YOUTUBE_API_KEY': 'test-only'}), \
                patch.object(metadata, '_fetch', side_effect=RuntimeError('quota')):
            metadata.refresh(['old'], 'channel')
            self.assertEqual(metadata.get_video_info('old')['title'], 'Existing')
            self.assertEqual(metadata.get_video_info('missing')['viewCount'], '—')

    def test_explorer_payload_and_assets(self):
        with patch.object(metadata, '_loaded', True), app.test_client() as client:
            html = client.get('/').get_data(as_text=True)
            payload = re.search(r'<script id="spot-data" type="application/json">(.*?)</script>', html, re.S).group(1)
            spots = json.loads(payload)
            expected = sum(len(data['spots']) for data in SPOT_DATA.values())
            self.assertEqual(len(spots), expected)
            self.assertEqual(sum(s['video_count'] for s in spots), 75)
            for spot in spots:
                self.assertIn(spot['region'], SPOT_DATA)
                self.assertEqual(len(spot['videos']), spot['video_count'])
                self.assertTrue(spot['detail_url'].startswith('/spot/'))
            for asset in ('explorer.js', 'explorer.css'):
                with client.get('/static/' + asset) as response:
                    self.assertEqual(response.status_code, 200)

    def test_all_routes_work_without_api(self):
        with patch.object(metadata, '_loaded', True), app.test_client() as client:
            paths = ['/'] + [f'/spot/{quote(region, safe="")}/{quote(name, safe="")}'
                             for region, data in SPOT_DATA.items() for name in data['spots']]
            for path in paths:
                with self.subTest(path=path):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 200)
                    html = response.get_data(as_text=True)
                    self.assertNotIn('cartodb-basemaps-', html)
                    self.assertIn('tile.openstreetmap.org', html if path != '/' else Path('static/explorer.js').read_text())
            self.assertEqual(client.get('/spot/missing/missing').status_code, 404)


if __name__ == '__main__':
    unittest.main()
