import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request
from unittest.mock import patch

from scripts.http_utils import urlopen_with_retry


class UrlopenWithRetryTests(unittest.TestCase):
    def setUp(self):
        self.request = Request("https://example.invalid")

    @patch("scripts.http_utils.time.sleep")
    @patch("scripts.http_utils.urlopen")
    def test_retries_temporary_server_error(self, mock_urlopen, mock_sleep):
        response = object()
        mock_urlopen.side_effect = [
            HTTPError(self.request.full_url, 503, "Unavailable", None, None),
            response,
        ]

        self.assertIs(urlopen_with_retry(self.request, timeout=5), response)
        self.assertEqual(mock_urlopen.call_count, 2)
        mock_sleep.assert_called_once_with(1)

    @patch("scripts.http_utils.time.sleep")
    @patch("scripts.http_utils.urlopen")
    def test_does_not_retry_not_found(self, mock_urlopen, mock_sleep):
        mock_urlopen.side_effect = HTTPError(
            self.request.full_url, 404, "Not Found", None, None
        )

        with self.assertRaises(HTTPError):
            urlopen_with_retry(self.request, timeout=5)

        mock_urlopen.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("scripts.http_utils.time.sleep")
    @patch("scripts.http_utils.urlopen")
    def test_retries_connection_error(self, mock_urlopen, mock_sleep):
        response = object()
        mock_urlopen.side_effect = [URLError("temporary"), response]

        self.assertIs(urlopen_with_retry(self.request, timeout=5), response)
        self.assertEqual(mock_urlopen.call_count, 2)
        mock_sleep.assert_called_once_with(1)

    @patch("scripts.http_utils.time.sleep")
    @patch("scripts.http_utils.urlopen")
    def test_raises_after_max_attempts(self, mock_urlopen, mock_sleep):
        mock_urlopen.side_effect = URLError("temporary")

        with self.assertRaises(URLError):
            urlopen_with_retry(self.request, timeout=5)

        self.assertEqual(mock_urlopen.call_count, 3)
        self.assertEqual([call.args[0] for call in mock_sleep.call_args_list], [1, 2])


if __name__ == "__main__":
    unittest.main()
