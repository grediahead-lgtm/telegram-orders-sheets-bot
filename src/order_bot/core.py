"""Conversation logic. Pure Python: no network, so it is easy to test."""
import datetime
import re
import time

STEPS = ["item", "quantity", "contact", "comment", "photo"]
MAX_TEXT = 500


def clean(text):
    return re.sub(r"\s+", " ", (text or "")).strip()[:MAX_TEXT]


class OrderBot:
    def __init__(self, cfg, storage, notify_owner=None, now=None, rate_limit=20):
        self.cfg, self.storage, self.notify_owner = cfg, storage, notify_owner
        self.now = now or (lambda: datetime.datetime.now().isoformat(timespec="seconds"))
        self.sessions = {}
        self.counter = 0
        self.rate_limit = rate_limit
        self._hits = {}

    def _limited(self, chat_id):
        t = time.monotonic()
        hits = [h for h in self._hits.get(chat_id, []) if t - h < 60]
        hits.append(t)
        self._hits[chat_id] = hits
        return len(hits) > self.rate_limit

    def handle(self, chat_id, user, text=None, photo_file_id=None):
        """Returns a list of reply texts for this chat."""
        if self._limited(chat_id):
            return []
        text = clean(text)
        cmd = text.split(" ")[0].lower() if text.startswith("/") else ""
        t = self.cfg["texts"]
        if cmd in ("/start", "/help"):
            return [t["greeting"]]
        if cmd == "/cancel":
            self.sessions.pop(chat_id, None)
            return [t["cancelled"]]
        if cmd == "/order":
            self.sessions[chat_id] = {"step": 0, "data": {}}
            return [t["ask_item"]]
        s = self.sessions.get(chat_id)
        if s is None:
            return [t["greeting"]]
        step = STEPS[s["step"]]
        if step == "photo":
            return self._photo_step(chat_id, user, s, text, photo_file_id)
        if not text or text.startswith("/"):
            return [t["need_text"]]
        if step == "quantity":
            m = re.fullmatch(r"\d{1,4}", text)
            if not m or int(text) == 0:
                return [t["bad_quantity"]]
        s["data"][step] = text
        s["step"] += 1
        return [t["ask_" + STEPS[s["step"]]]]

    def _photo_step(self, chat_id, user, s, text, photo_file_id):
        t = self.cfg["texts"]
        if photo_file_id:
            s["data"]["photo_file_id"] = photo_file_id
        elif text.lower() not in ("-", "skip", "пропустити", "пропустить"):
            return [t["ask_photo"]]
        self.counter += 1
        order = dict(s["data"])
        order.update({
            "created_at": self.now(), "order_id": "%s-%04d" % (self.now()[:10].replace("-", ""), self.counter),
            "customer": clean(user.get("name", "")), "username": clean(user.get("username", "")),
        })
        try:
            self.storage.save(order)
        except Exception:  # keep the customer's data in the session so they can retry
            return [t["save_failed"]]
        self.sessions.pop(chat_id, None)
        if self.notify_owner:
            try:
                self.notify_owner(order)
            except Exception:  # the order is already saved: a failed owner message must not hide the confirmation
                pass
        return [t["done"].format(order_id=order["order_id"])]
