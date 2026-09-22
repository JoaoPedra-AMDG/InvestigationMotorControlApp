"""Structured JSON-lines log of operator commands, outcomes and controller state changes.

One file per UTC day under <output>/logs. Logging never blocks or breaks control:
a storage failure is counted and reported, not raised.
"""
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

# Bulky or free-text request fields that are summarised instead of logged in full.
SUMMARISED = {'csv', 'mapping', 'metadata', 'note', 'reason'}


class EventLog:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.lock = threading.Lock()
        self.failures = 0

    def write(self, kind, **data):
        now = datetime.now(timezone.utc)
        entry = dict(utc=now.isoformat(), kind=kind, **data)
        try:
            with self.lock:
                self.folder.mkdir(parents=True, exist_ok=True)
                with (self.folder/f'events-{now:%Y%m%d}.jsonl').open('a', encoding='utf-8') as f:
                    f.write(json.dumps(entry, default=str)+'\n')
        except OSError:
            self.failures += 1

    @staticmethod
    def _request(data):
        if not isinstance(data, dict):
            return {}
        return {k: (f'<{len(str(v))} characters>' if k in SUMMARISED else v) for k, v in data.items()}

    def command(self, data):
        self.write('command', request=self._request(data))

    def outcome(self, data, result, detail=''):
        action = data.get('action') if isinstance(data, dict) else None
        self.write('outcome', action=action, result=result, detail=detail)
