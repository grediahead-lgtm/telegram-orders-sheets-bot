import argparse
import json
import os
import sys
import time

from .core import OrderBot
from .storage import make_storage
from .telegram_api import TelegramClient

REQUIRED_TEXTS = ["greeting", "cancelled", "ask_item", "ask_quantity", "ask_contact", "ask_comment", "ask_photo",
                  "need_text", "bad_quantity", "done", "save_failed"]


def load_config(path):
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    missing = [k for k in REQUIRED_TEXTS if not cfg.get("texts", {}).get(k)]
    if missing:
        raise ValueError("config.texts is missing: " + ", ".join(missing))
    return cfg


def main(argv=None):
    ap = argparse.ArgumentParser(prog="order_bot")
    ap.add_argument("--config", required=True)
    ap.add_argument("--check", action="store_true", help="validate config and storage, then exit")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    storage = make_storage(cfg)
    if args.check:
        print("config ok, storage:", cfg.get("storage", "csv"))
        return 0
    client = TelegramClient(os.environ.get("TELEGRAM_BOT_TOKEN", ""))
    owner = cfg.get("owner_chat_id")

    def notify(order):
        if owner:
            client.send(owner, "New order %s: %s x%s, %s" % (order["order_id"], order["item"], order["quantity"], order["contact"]))

    bot = OrderBot(cfg, storage, notify_owner=notify)
    offset = 0
    while True:
        try:
            for upd in client.updates(offset):
                offset = upd["update_id"] + 1
                m = upd.get("message") or {}
                chat = m.get("chat", {})
                if chat.get("type") != "private" or m.get("from", {}).get("is_bot"):
                    continue
                photo = (m.get("photo") or [{}])[-1].get("file_id")
                u = m.get("from", {})
                user = {"name": " ".join(filter(None, [u.get("first_name"), u.get("last_name")])), "username": u.get("username", "")}
                for reply in bot.handle(chat["id"], user, m.get("text"), photo):
                    client.send(chat["id"], reply)
        except KeyboardInterrupt:
            return 0
        except Exception as e:  # network hiccup: log the type only, never message text
            print("error:", type(e).__name__, file=sys.stderr)
            time.sleep(5)


if __name__ == "__main__":
    sys.exit(main())
