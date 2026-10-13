import csv
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from order_bot.__main__ import load_config  # noqa: E402
from order_bot.core import OrderBot  # noqa: E402
from order_bot.storage import CsvStorage, WebhookStorage, make_storage, FIELDS  # noqa: E402

CFG = load_config(os.path.join(os.path.dirname(__file__), "..", "examples", "config.example.json"))
USER = {"name": "Ira K", "username": "ira"}


class MemStorage:
    def __init__(self, fail=False):
        self.rows, self.fail = [], fail

    def save(self, order):
        if self.fail:
            raise RuntimeError("down")
        self.rows.append(order)


def bot(storage=None, **kw):
    return OrderBot(CFG, storage or MemStorage(), now=lambda: "2026-10-13T10:00:00", **kw)


def run(b, chat, answers):
    out = []
    for a in answers:
        out += b.handle(chat, USER, a)
    return out


class FlowTests(unittest.TestCase):
    def test_full_order(self):
        s = MemStorage()
        b = bot(s)
        out = run(b, 1, ["/order", "Bed Comfort M", "2", "+380000000001", "grey", "-"])
        self.assertIn("20261013-0001", out[-1])
        row = s.rows[0]
        self.assertEqual((row["item"], row["quantity"], row["customer"]), ("Bed Comfort M", "2", "Ira K"))

    def test_photo_is_recorded(self):
        s = MemStorage()
        b = bot(s)
        run(b, 1, ["/order", "Toy", "1", "ira@example.com", "-"])
        b.handle(1, USER, None, "FILEID123")
        self.assertEqual(s.rows[0]["photo_file_id"], "FILEID123")

    def test_bad_quantity_keeps_step(self):
        b = bot()
        out = run(b, 1, ["/order", "Toy", "abc", "0", "10000"])
        self.assertEqual(out[-3:], [CFG["texts"]["bad_quantity"]] * 3)
        self.assertEqual(b.sessions[1]["step"], 1)

    def test_cancel_and_no_session(self):
        b = bot()
        run(b, 1, ["/order", "Toy"])
        self.assertEqual(b.handle(1, USER, "/cancel"), [CFG["texts"]["cancelled"]])
        self.assertEqual(b.handle(1, USER, "hello"), [CFG["texts"]["greeting"]])

    def test_commands_inside_a_step_are_not_answers(self):
        b = bot()
        run(b, 1, ["/order"])
        self.assertEqual(b.handle(1, USER, "/start"), [CFG["texts"]["greeting"]])  # greeting, step unchanged
        self.assertEqual(b.sessions[1]["step"], 0)
        self.assertEqual(b.handle(1, USER, None), [CFG["texts"]["need_text"]])

    def test_save_failure_keeps_data_and_allows_retry(self):
        s = MemStorage(fail=True)
        b = bot(s)
        out = run(b, 1, ["/order", "Toy", "1", "c", "-", "-"])
        self.assertEqual(out[-1], CFG["texts"]["save_failed"])
        s.fail = False
        self.assertIn("recorded", b.handle(1, USER, "-")[0])
        self.assertEqual(len(s.rows), 1)

    def test_two_chats_do_not_mix(self):
        s = MemStorage()
        b = bot(s)
        run(b, 1, ["/order", "A"])
        run(b, 2, ["/order", "B", "1", "x", "-", "-"])
        run(b, 1, ["3", "y", "-", "-"])
        self.assertEqual(sorted(r["item"] for r in s.rows), ["A", "B"])

    def test_rate_limit(self):
        b = bot(rate_limit=3)
        outs = [b.handle(1, USER, "/start") for _ in range(5)]
        self.assertEqual([len(o) for o in outs], [1, 1, 1, 0, 0])

    def test_owner_notified(self):
        seen = []
        b = bot(notify_owner=seen.append)
        run(b, 1, ["/order", "Toy", "1", "c", "-", "-"])
        self.assertEqual(seen[0]["item"], "Toy")

    def test_failed_owner_notification_does_not_hide_the_confirmation(self):
        def boom(order):
            raise RuntimeError("telegram down")
        s = MemStorage()
        b = bot(s, notify_owner=boom)
        out = run(b, 1, ["/order", "Toy", "1", "c", "-", "-"])
        self.assertIn("recorded", out[-1])
        self.assertEqual(len(s.rows), 1)

    def test_long_text_is_trimmed(self):
        s = MemStorage()
        b = bot(s)
        run(b, 1, ["/order", "x" * 2000, "1", "c", "-", "-"])
        self.assertEqual(len(s.rows[0]["item"]), 500)


class StorageTests(unittest.TestCase):
    def test_csv_header_once_and_formula_guard(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "o.csv")
            st = CsvStorage(p)
            st.save({"item": "=HYPERLINK(\"http://x\")", "quantity": "1"})
            st.save({"item": "ok", "quantity": "2"})
            with open(p, encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["item"][0], "'")
            self.assertEqual(list(rows[0].keys()), FIELDS)

    def test_make_storage_needs_secret_and_https(self):
        cfg = {"storage": "webhook", "webhook_url": "https://example.com/x"}
        with self.assertRaises(ValueError):
            make_storage(cfg, env={})
        with self.assertRaises(ValueError):
            WebhookStorage("http://example.com", "s")
        self.assertIsInstance(make_storage(cfg, env={"ORDER_WEBHOOK_SECRET": "s"}), WebhookStorage)
        with self.assertRaises(ValueError):
            make_storage({"storage": "db"})

    def test_webhook_posts_json_and_handles_reject(self):
        got = []

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                got.append(body)
                ok = body["secret"] == "right"
                payload = json.dumps({"ok": ok, "error": "forbidden"}).encode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *a):
                pass

        srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            st = WebhookStorage("https://x.example/exec", "right")
            # point the https check aside: replace URL after validation, to hit the local server
            st.url = "http://127.0.0.1:%d/exec" % srv.server_port
            st.save({"item": "Toy", "quantity": "1"})
            self.assertEqual(got[0]["item"], "Toy")
            st.secret = "wrong"
            with self.assertRaises(RuntimeError):
                st.save({"item": "Toy"})
        finally:
            srv.shutdown()
            srv.server_close()


class ConfigTests(unittest.TestCase):
    def test_missing_text_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "c.json")
            with open(p, "w") as f:
                json.dump({"texts": {"greeting": "hi"}}, f)
            with self.assertRaises(ValueError) as cm:
                load_config(p)
            self.assertIn("ask_item", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
