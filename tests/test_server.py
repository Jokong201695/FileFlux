import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch

import server


class FileServerPathTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.upload_dir = self.temp_dir.name

    def _new_handler(self):
        return server.FileServer.__new__(server.FileServer)

    def test_get_safe_path_blocks_traversal_variants(self):
        handler = self._new_handler()

        with patch.object(server, "UPLOAD_DIR", self.upload_dir):
            safe = handler.get_safe_path("nested/file.txt")
            self.assertEqual(safe, os.path.join(self.upload_dir, "nested", "file.txt"))

            dangerous_inputs = [
                "../../etc/passwd",
                "..%2F..%2Fetc%2Fpasswd",
                "/../../etc/passwd",
            ]
            for raw in dangerous_inputs:
                with self.subTest(raw=raw):
                    self.assertIsNone(handler.get_safe_path(raw))


class FileServerDeleteTests(unittest.TestCase):
    def _handler_for_path(self, path):
        handler = server.FileServer.__new__(server.FileServer)
        handler.path = path
        handler.headers = {}
        handler.wfile = io.BytesIO()
        handler.send_response = lambda code: setattr(handler, "response_code", code)
        handler.send_header = lambda *_args, **_kwargs: None
        handler.end_headers = lambda: None
        return handler

    def test_delete_rejects_non_delete_endpoint(self):
        handler = self._handler_for_path("/files/demo.txt")

        handler.do_DELETE()

        self.assertEqual(handler.response_code, 404)
        payload = json.loads(handler.wfile.getvalue().decode())
        self.assertFalse(payload["success"])
        self.assertEqual(payload["error"], "Invalid delete endpoint")


if __name__ == "__main__":
    unittest.main()
