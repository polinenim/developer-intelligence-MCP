"""Tests for the SearXNG tool (mock HTTP responses)."""
import unittest
from unittest.mock import patch, Mock

from tools import searxng


class SearxngTests(unittest.TestCase):
    def test_empty_query_raises(self):
        with self.assertRaises(ValueError):
            searxng.search_web("")

    @patch("tools.searxng.requests.get")
    def test_search_parses_results(self, mock_get: Mock):
        sample = {"results": [{"title": "T1", "url": "http://a", "content": "snippet1"}, {"title": "T2", "url": "http://b", "content": "snippet2"}]}
        resp = Mock()
        resp.json.return_value = sample
        resp.raise_for_status.return_value = None
        mock_get.return_value = resp

        with patch.dict("os.environ", {"SEARXNG_URL": "http://searx"}):
            out = searxng.search_web("query", limit=2)

        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["title"], "T1")
        self.assertEqual(out[0]["url"], "http://a")
        self.assertEqual(out[0]["snippet"], "snippet1")


if __name__ == "__main__":
    unittest.main()
