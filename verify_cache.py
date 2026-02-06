import unittest
from app import app

class TestCacheHeaders(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_global_thumb_cache_headers(self):
        # We need a file that exists in data/Thumbnail/ for this to work
        # Or we can just mock send_from_directory if we were doing proper unit tests
        # But for a quick check, let's see if the route responds with headers
        response = self.app.get('/thumbs/event.webp')
        # Even if 404, we can see if the logic would have added headers if we modify it
        # Actually, global_thumb calls send_from_directory which might 404
        
        print(f"\nResponse Headers for /thumbs/event.webp: {response.headers}")
        self.assertIn('Cache-Control', response.headers)
        self.assertTrue('public' in response.headers['Cache-Control'])
        self.assertTrue('max-age=31536000' in response.headers['Cache-Control'])

if __name__ == '__main__':
    unittest.main()
