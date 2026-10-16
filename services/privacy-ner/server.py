"""Private, authenticated local NER service. Parent never imports model libraries."""
import contextlib
import hmac
import http.server
import importlib.util
import json
import multiprocessing
import os
from pathlib import Path
import re
import signal
import sys
import threading
import time

MODEL = 'urchade/gliner_multi_pii-v1'
MODEL_REV = '1fcf13e85f4eef5394e1fcd406cf2ca9ea82351d'
MAX_INPUT_BYTES = 160000
MAX_BODY_BYTES = MAX_INPUT_BYTES * 6 + 64


def model_worker(connection, backend):
    # Child exit releases the model, Torch allocator and all caches to the OS.
    # Never print model exceptions or user content into container logs.
    with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        try:
            spec = importlib.util.spec_from_file_location('privacy_ner_core', backend)
            core = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = core
            spec.loader.exec_module(core)
            started = time.monotonic()
            detector = core.LocalPersonDetector()
            connection.send({'ready': True, 'load_seconds': time.monotonic() - started})
            while True:
                text = connection.recv()
                if text is None:
                    break
                started = time.monotonic()
                result = detector.inspect(text)
                connection.send({'result': result, 'scan_seconds': time.monotonic() - started})
        except (EOFError, BrokenPipeError):
            pass
        except Exception:
            with contextlib.suppress(Exception):
                connection.send({'error': 'DETECTOR_FAILED'})
        finally:
            connection.close()


class Unavailable(Exception):
    pass


class Busy(Unavailable):
    pass


class ModelManager:
    def __init__(self, backend, idle_seconds=300, deadline_seconds=120):
        self.backend = str(backend)
        self.idle_seconds = idle_seconds
        self.deadline_seconds = deadline_seconds
        self.lock = threading.Lock()
        self.process = None
        self.connection = None
        self.last_used = 0
        self.generation = 0
        self.closed = False
        self.stopping = threading.Event()
        self.sweeper = threading.Thread(target=self._sweep, daemon=True)
        self.sweeper.start()

    def _stop(self):
        if self.process is not None:
            if self.process.is_alive():
                self.process.terminate()
            self.process.join(3)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(3)
            if self.process.is_alive():
                raise Unavailable('WORKER_STOP_FAILED')
            self.process.close()
            self.process = None
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def _receive(self, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not self.connection.poll(remaining):
            raise Unavailable('DETECTOR_TIMEOUT')
        result = self.connection.recv()
        if not isinstance(result, dict) or result.get('error'):
            raise Unavailable('DETECTOR_FAILED')
        return result

    def inspect(self, text):
        if not isinstance(text, str) or len(text.encode('utf8')) > MAX_INPUT_BYTES:
            raise ValueError('INVALID_TEXT')
        if not self.lock.acquire(blocking=False):
            raise Busy('DETECTOR_BUSY')
        cold = False
        load_seconds = 0
        try:
            if self.closed:
                raise Unavailable('SERVICE_STOPPING')
            deadline = time.monotonic() + self.deadline_seconds
            if self.process is None or not self.process.is_alive():
                self._stop()
                context = multiprocessing.get_context('spawn')
                self.connection, child = context.Pipe()
                self.process = context.Process(target=model_worker, args=(child, self.backend), daemon=True)
                self.process.start()
                child.close()
                ready = self._receive(deadline)
                if ready.get('ready') is not True:
                    raise Unavailable('DETECTOR_NOT_READY')
                load_seconds = ready['load_seconds']
                self.generation += 1
                cold = True
            self.connection.send(text)
            message = self._receive(deadline)
            if not isinstance(message.get('result'), dict):
                raise Unavailable('INVALID_DETECTOR_RESULT')
            self.last_used = time.monotonic()
            return {**message['result'], 'model': MODEL, 'model_revision': MODEL_REV,
                    'cold': cold, 'load_seconds': round(load_seconds, 3),
                    'scan_seconds': round(message['scan_seconds'], 3), 'generation': self.generation}
        except (EOFError, OSError, Unavailable, ValueError, KeyError, TypeError):
            self._stop()
            raise Unavailable('DETECTOR_UNAVAILABLE') from None
        finally:
            self.lock.release()

    def state(self):
        # Health never wakes a sleeping model and never waits behind inference.
        if not self.lock.acquire(blocking=False):
            return {'state': 'busy', 'generation': self.generation}
        try:
            return {'state': 'loaded' if self.process and self.process.is_alive() else 'sleeping',
                    'generation': self.generation}
        finally:
            self.lock.release()

    def _sweep(self):
        while not self.stopping.wait(min(1, self.idle_seconds / 2)):
            if self.lock.acquire(blocking=False):
                try:
                    if self.process is not None and time.monotonic() - self.last_used >= self.idle_seconds:
                        self._stop()
                finally:
                    self.lock.release()

    def close(self):
        self.stopping.set()
        with self.lock:
            self.closed = True
            self._stop()
        self.sweeper.join(3)


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 8

    def __init__(self, address, manager, token):
        self.manager, self.token = manager, token
        self.slots = threading.BoundedSemaphore(8)
        super().__init__(address, Handler)

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()

    def handle_error(self, request, client_address):
        pass


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = 'VectorPrivacy'
    sys_version = ''

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, *_args):
        pass

    def reply(self, status, payload):
        content = json.dumps(payload, ensure_ascii=True, allow_nan=False).encode('utf8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            self.wfile.write(content)

    def authorized(self):
        values = self.headers.get_all('Authorization') or []
        supplied = values[0] if len(values) == 1 else ''
        # compare_digest(str) rejects non-ASCII: compare bytes for any header.
        if not hmac.compare_digest(supplied.encode('utf8'), ('Bearer ' + self.server.token).encode('ascii')):
            self.reply(401, {'error': 'UNAUTHORIZED'})
            return False
        return True

    def do_GET(self):
        if not self.authorized():
            return
        if self.path != '/health':
            return self.reply(404, {'error': 'NOT_FOUND'})
        self.reply(200, {'ok': True, 'model': MODEL, 'model_revision': MODEL_REV, **self.server.manager.state()})

    def do_POST(self):
        if not self.authorized():
            return
        if self.path != '/scan':
            return self.reply(404, {'error': 'NOT_FOUND'})
        lengths = self.headers.get_all('Content-Length') or []
        if self.headers.get('Transfer-Encoding') or len(lengths) != 1 or not re.fullmatch('[0-9]{1,7}', lengths[0]):
            return self.reply(400, {'error': 'INVALID_LENGTH'})
        length = int(lengths[0])
        if not 0 < length <= MAX_BODY_BYTES:
            return self.reply(413, {'error': 'INPUT_TOO_LARGE'})
        if self.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
            return self.reply(415, {'error': 'JSON_REQUIRED'})
        try:
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError()
            payload = json.loads(raw)
            if not isinstance(payload, dict) or set(payload) != {'text'} or not isinstance(payload['text'], str):
                raise ValueError()
            if len(payload['text'].encode('utf8')) > MAX_INPUT_BYTES:
                return self.reply(413, {'error': 'INPUT_TOO_LARGE'})
        except (ValueError, UnicodeError, OSError, RecursionError):
            return self.reply(400, {'error': 'INVALID_REQUEST'})
        try:
            result = self.server.manager.inspect(payload['text'])
        except Busy:
            return self.reply(429, {'error': 'DETECTOR_BUSY'})
        except Exception:
            return self.reply(503, {'error': 'DETECTOR_UNAVAILABLE'})
        self.reply(200, result)


def main():
    token = Path('/run/secrets/vector_privacy_ner_token').read_text().strip()
    if not re.fullmatch('[a-f0-9]{64}', token):
        raise RuntimeError('Invalid private service token file.')
    idle = int(os.environ.get('VECTOR_PRIVACY_NER_IDLE_SECONDS', '300'))
    if not 1 <= idle <= 600:
        raise RuntimeError('Invalid idle limit.')
    manager = ModelManager('/work/privacy-ner-core.py', idle_seconds=idle)
    server = Server(('0.0.0.0', 8091), manager, token)
    def stop(_signal, _frame):
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
        manager.close()


if __name__ == '__main__':
    main()
