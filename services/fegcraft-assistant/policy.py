"""Trusted bridge admission policy; no model call or message sending here."""
from collections import OrderedDict, deque
import re
import threading
import time

INTRODUCTION = ('Hey zusammen, ich bin Vector, euer neuer Minecraft-Assistent! '
                'Ich helfe bei Fragen und Problemen rund um Minecraft und zeige '
                'euch Statistiken und Rekorde. Beginnt eure Nachricht einfach '
                'mit Hey Vector oder Yoo Vector.')
GREETING = re.compile(r'^\s*(hi|hey|hallo|yo{1,3}|hoi|huhu|hello)\s+vector(?:\s*[,!:?]\s*|\s+|$)', re.I)


def addressed_question(message):
    if not isinstance(message, str) or len(message) > 1200:
        return None
    match = GREETING.match(message)
    if not match:
        return None
    return match.group(1).lower(), message[match.end():].strip()


def display_name(value):
    # Do not allow Discord mentions, Minecraft control codes or multiline names.
    cleaned = ''.join(c for c in str(value) if c.isalnum() or c in ' _.-')
    return cleaned.strip()[:32] or 'Spieler'


class Admission:
    """Bridge supplies authenticated stable identity and canonical event ID.

    Forwarded copies must carry the original event ID. Display names are never
    identities. Full queues reject new work rather than delaying game chat.
    """
    def __init__(self, clock=time.monotonic, per_user=3, global_limit=12, capacity=1000):
        self.clock = clock
        self.per_user = per_user
        self.global_limit = global_limit
        self.capacity = capacity
        self.users = {}
        self.global_events = deque()
        self.seen = OrderedDict()
        self.lock = threading.Lock()

    def accept(self, *, principal, event_id, message, is_bot=False):
        question = addressed_question(message)
        if is_bot or question is None:
            return {'status': 'ignored'}
        if not isinstance(principal, str) or not principal or len(principal) > 128:
            return {'status': 'invalid'}
        if not isinstance(event_id, str) or not event_id or len(event_id) > 160:
            return {'status': 'invalid'}
        with self.lock:
            now = self.clock()
            while self.seen and next(iter(self.seen.values())) <= now - 300:
                self.seen.popitem(last=False)
            if event_id in self.seen:
                return {'status': 'duplicate'}
            if len(self.seen) >= self.capacity:
                return {'status': 'busy'}
            while self.global_events and self.global_events[0] <= now - 60:
                self.global_events.popleft()
            for key in list(self.users):
                values = self.users[key]
                while values and values[0] <= now - 60:
                    values.popleft()
                if not values:
                    del self.users[key]
            self.seen[event_id] = now
            values = self.users.get(principal, deque())
            if len(values) >= self.per_user or len(self.global_events) >= self.global_limit:
                return {'status': 'limited'}
            values.append(now)
            self.users[principal] = values
            self.global_events.append(now)
            return {'status': 'accepted', 'greeting': question[0], 'question': question[1]}
