"""llm.ask with urllib.request.urlopen mocked (Ollama is never called).

Run from the project folder: python3 -m unittest discover -s tests
"""
import io
import json
import socket
import unittest
import urllib.error
from unittest import mock

import llm
from plant_db import init_db


def setUpModule():
    init_db()


def reply(content):
    """A fake urlopen() response carrying Ollama's JSON."""
    return io.BytesIO(json.dumps({"message": {"content": content}}).encode())


def http_error(code, body):
    return urllib.error.HTTPError(llm.OLLAMA_URL, code, "error", {},
                                  io.BytesIO(body.encode()))


class AskTests(unittest.TestCase):
    def ask(self, answer=None, error=None, **kwargs):
        """Call llm.ask with urlopen returning answer (or raising error).
        Returns ((ok, text), the request body that was sent)."""
        with mock.patch("urllib.request.urlopen") as urlopen:
            if error is not None:
                urlopen.side_effect = error
            else:
                urlopen.return_value = answer
            result = llm.ask("And what temperature?", **kwargs)
        sent = urlopen.call_args[0][0]
        return result, json.loads(sent.data)

    def test_answer(self):
        result, _body = self.ask(reply("  18–29 °C.  "))
        self.assertEqual(result, (True, "18–29 °C."))

    def test_history_is_sent_in_order(self):
        history = [("What humidity does basil like?", "40–60% RH."),
                   ("Is it too humid?", "No, 55% RH is fine.")]
        _result, body = self.ask(reply("18–29 °C."), active_plant="Basil",
                                 reading=(24.0, 55.0), history=history)
        roles = [m["role"] for m in body["messages"]]
        self.assertEqual(roles, ["system", "user", "assistant", "user",
                                 "assistant", "user"])
        contents = [m["content"] for m in body["messages"][1:]]
        self.assertEqual(contents, ["What humidity does basil like?", "40–60% RH.",
                                    "Is it too humid?", "No, 55% RH is fine.",
                                    "And what temperature?"])

    def test_no_history(self):
        _result, body = self.ask(reply("ok"))
        self.assertEqual([m["role"] for m in body["messages"]], ["system", "user"])

    def test_system_prompt_names_sprout(self):
        _result, body = self.ask(reply("ok"), active_plant="Basil")
        system = body["messages"][0]["content"]
        self.assertTrue(system.startswith(
            "You are Sprout, the assistant in Green Gauge, a greenhouse "
            "climate monitor."))
        self.assertIn("currently growing: Basil", system)

    def test_error_paths_are_not_ok(self):
        errors = {
            "timeout": socket.timeout(),
            "timeout error": TimeoutError(),
            "missing model": http_error(404, '{"error": "model not found"}'),
            "other HTTP error": http_error(500, '{"error": "boom"}'),
            "HTTP error without JSON": http_error(500, "not json"),
            "not running": urllib.error.URLError("refused"),
        }
        for name, error in errors.items():
            with self.subTest(name):
                (ok, text), _body = self.ask(error=error)
                self.assertFalse(ok)
                self.assertTrue(text)

    def test_bad_replies_are_not_ok(self):
        replies = {
            "empty answer": reply("   "),
            "not JSON": io.BytesIO(b"<html>"),
            "no message": io.BytesIO(b'{"done": true}'),
            "null content": io.BytesIO(b'{"message": {"content": null}}'),
        }
        for name, response in replies.items():
            with self.subTest(name):
                (ok, text), _body = self.ask(response)
                self.assertFalse(ok)
                self.assertTrue(text)


if __name__ == "__main__":
    unittest.main()
