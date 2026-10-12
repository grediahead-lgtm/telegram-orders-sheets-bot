"""Where finished orders go: a CSV file or a Google Sheet (through an Apps Script web app)."""
import csv
import json
import os
import urllib.request

FIELDS = ["created_at", "order_id", "customer", "username", "item", "quantity", "contact", "comment", "photo_file_id"]


class CsvStorage:
    def __init__(self, path):
        self.path = path

    def save(self, order):
        new_file = not os.path.exists(self.path) or os.path.getsize(self.path) == 0
        with open(self.path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
            if new_file:
                w.writeheader()
            w.writerow({k: _safe_cell(order.get(k, "")) for k in FIELDS})


def _safe_cell(value):
    """Spreadsheets run text starting with = + - @ as formulas; prefix an apostrophe-like space."""
    s = str(value)
    return "'" + s if s[:1] in ("=", "+", "-", "@") else s


class WebhookStorage:
    """POSTs the order as JSON to a Google Apps Script web app (see apps_script/Code.gs)."""

    def __init__(self, url, secret, timeout=15, opener=None):
        if not url.startswith("https://"):
            raise ValueError("webhook url must be https")
        self.url, self.secret, self.timeout = url, secret, timeout
        self.opener = opener or urllib.request.build_opener()

    def save(self, order):
        body = {k: _safe_cell(order.get(k, "")) for k in FIELDS}
        body["secret"] = self.secret
        req = urllib.request.Request(
            self.url, data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with self.opener.open(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
        if not data.get("ok"):
            raise RuntimeError("webhook rejected the order: %s" % data.get("error", "unknown"))


def make_storage(cfg, env=os.environ):
    kind = cfg.get("storage", "csv")
    if kind == "csv":
        return CsvStorage(cfg.get("csv_path", "orders.csv"))
    if kind == "webhook":
        secret = env.get("ORDER_WEBHOOK_SECRET", "")
        if not secret:
            raise ValueError("set ORDER_WEBHOOK_SECRET for the webhook storage")
        return WebhookStorage(cfg["webhook_url"], secret)
    raise ValueError("storage must be csv or webhook")
