import json
import queue
import threading
import time


class SseBroker:
    def __init__(self):
        self._lock = threading.Lock()
        self._subscribers = set()

    def subscribe(self):
        q = queue.Queue()
        with self._lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q):
        with self._lock:
            try:
                self._subscribers.remove(q)
            except KeyError:
                pass

    def publish(self, event, data):
        payload = {
            'event': event,
            **(data or {}),
        }
        msg = json.dumps(payload)

        with self._lock:
            subscribers = list(self._subscribers)

        for q in subscribers:
            try:
                q.put_nowait(msg)
            except Exception:
                pass

    def event_stream(self, q, keepalive_seconds=15):
        try:
            while True:
                try:
                    msg = q.get(timeout=keepalive_seconds)
                    yield f"data: {msg}\n\n"
                except queue.Empty:
                    yield f": keepalive {int(time.time())}\n\n"
        except GeneratorExit:
            return


lds_notifications_broker = SseBroker()
