"""Authenticated private transport. No public port, cloud tools or command API."""
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import stat
import threading
import time
from urllib.parse import urlsplit

from runtime import Assistant, LocalKnowledge, State
from recipes import RecipeBook

DOCUMENTATION_SHA256 = '214261e4c9184837e4f532dcb6482cc1be8e0b8db0089a130a3e20e7a18df7b8'


def knowledge_for(mode, state, dsn_path='/run/secrets/vector_fegcraft_slot_dsn',
                  documentation_path='/inputs/documentation.json'):
    if mode not in ('0', '1', '2', '3'):
        raise RuntimeError('INVALID_KNOWLEDGE_MODE')
    if mode == '0':
        return None
    if mode == '3':
        fd = os.open(dsn_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as handle:
            meta = os.fstat(handle.fileno())
            if (not stat.S_ISREG(meta.st_mode) or meta.st_size > 4096
                    or stat.S_IMODE(meta.st_mode) != 0o400 or meta.st_uid != os.getuid()):
                raise RuntimeError('INVALID_LOCAL_SLOT_FILE')
            raw = handle.read(4097)
        if len(raw) > 4096:
            raise RuntimeError('INVALID_LOCAL_SLOT_FILE')
        dsn = raw.decode().strip()
        value = urlsplit(dsn)
        if (value.scheme not in ('postgres', 'postgresql') or value.username != 'vector_fegcraft_slot'
                or not value.password or not value.hostname or value.port not in (None, 5432)
                or value.path in ('', '/') or value.query or value.fragment):
            raise RuntimeError('RESTRICTED_LOCAL_SLOT_REQUIRED')
        from documentation import DocumentationIndex, DocumentationKnowledge
        index = DocumentationIndex(documentation_path, DOCUMENTATION_SHA256)
        return DocumentationKnowledge(dsn, documentation=index, usage=state.model_usage)
    # Retain existing explicitly opted-in legacy modes; rollout only selects3.
    dsn = Path(dsn_path).read_text().strip()
    if not dsn:
        raise RuntimeError('MISSING_LOCAL_SLOT')
    if mode == '2':
        from knowledge import GeneralKnowledge
        return GeneralKnowledge(dsn, usage=state.model_usage)
    return LocalKnowledge(dsn)


class Service(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 4

    def __init__(self, address, assistant, key, clock=time.time):
        self.assistant, self.key, self.clock = assistant, key, clock
        self.slot = threading.BoundedSemaphore(1)
        self.connections = threading.BoundedSemaphore(8)
        super().__init__(address, Handler)

    def process_request(self, request, client_address):
        if not self.connections.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.connections.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.connections.release()

    def handle_error(self, *args):
        # No raw requests, names, secret headers or tracebacks in service logs.
        pass


class Handler(BaseHTTPRequestHandler):
    server_version = 'VectorLocal/1'
    sys_version = ''

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, *args):
        pass

    def respond(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(data)
        self.close_connection = True

    def do_POST(self):
        if self.path != '/v1/minecraft' or self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1:
            return self.respond(400, {'error': 'INVALID_REQUEST'})
        try:
            size = int(self.headers.get('Content-Length', '-1'))
        except ValueError:
            size = -1
        # Authenticated requests may include the current public block-item IDs.
        # Messages still have a separate 1200-character limit; replies stay 8192 B.
        if not 1 <= size <= 512 * 1024:
            return self.respond(413, {'error': 'REQUEST_LIMIT'})
        timestamp, signature = self.headers.get('X-Vector-Time', ''), self.headers.get('X-Vector-Signature', '')
        if not re.fullmatch(r'[0-9]{10}', timestamp) or not re.fullmatch(r'[a-f0-9]{64}', signature) or abs(self.server.clock() - int(timestamp)) > 60:
            return self.respond(401, {'error': 'UNAUTHORIZED'})
        raw = self.rfile.read(size)
        expected = hmac.new(self.server.key, timestamp.encode() + b'\n' + raw, hashlib.sha256).hexdigest()
        if len(raw) != size or not hmac.compare_digest(expected, signature):
            return self.respond(401, {'error': 'UNAUTHORIZED'})
        if not self.server.slot.acquire(blocking=False):
            return self.respond(503, {'error': 'LOCAL_BUSY'})
        try:
            value = json.loads(raw)
            result = self.server.assistant.handle(value)
            status = 200
        except (ValueError, TypeError, KeyError):
            status, result = 400, {'error': 'INVALID_REQUEST'}
        except Exception:
            status, result = 503, {'error': 'LOCAL_UNAVAILABLE'}
        finally:
            self.server.slot.release()
        # A client can send its next question as soon as it reads this response.
        # Release completed computation before making that completion visible.
        return self.respond(status, result)


def main():
    os.umask(0o077)
    token = Path('/run/secrets/vector_fegcraft_token').read_text().strip()
    if not re.fullmatch(r'[a-f0-9]{64}', token):
        raise RuntimeError('INVALID_TOKEN')
    key = bytes.fromhex(token)
    # Default remains OFF. The guarded deployment can opt into reviewed mode3
    # only after native model, restricted role and construction qualification.
    state = State('/state/events.sqlite', key)
    mode = os.environ.get('VECTOR_FEGCRAFT_KNOWLEDGE', '0')
    knowledge = knowledge_for(mode, state)
    # Always intercept recipe questions, including when no qualified catalog is
    # mounted. Missing/unsupported recipes must never go to the small model.
    recipes = RecipeBook.load('/inputs/recipes.json') if os.environ.get('VECTOR_FEGCRAFT_RECIPES') == '1' else RecipeBook()
    assistant = Assistant(state, '/inputs/stats', '/inputs/usercache.json', '/inputs/mods.json', knowledge, recipes)
    with Service(('0.0.0.0', 8090), assistant, key) as service:
        service.serve_forever(poll_interval=0.5)


if __name__ == '__main__':
    main()
