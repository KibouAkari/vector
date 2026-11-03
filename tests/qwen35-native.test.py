"""Synthetic boundaries for the three-request probe; never runs a model."""
import contextlib
import importlib.util
import io
import itertools
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'probe', ROOT / 'scripts/deploy/evaluate-qwen35-native.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def answer(text):
    return {'model': 'vector-qwen35:9b-q4km-candidate', 'done': True,
        'done_reason': 'stop', 'prompt_eval_count': 100, 'eval_count': 20,
        'eval_duration': 2000000000,
        'message': {'role': 'assistant', 'content': text}}


def tool():
    value = answer('')
    value['message']['tool_calls'] = [{'function': {
        'name': 'compare_player_statistics', 'arguments': {
            'player_a': 'ExampleTwo', 'player_b': 'ExampleOne', 'metric': 'mob_kills'}}}]
    return value


class NativeBoundaryTests(unittest.TestCase):
    def run_inner(self, responses=None, slot_error=None, cleanup_error=None, slow=False, data_first=False):
        responses = list(responses if responses is not None else [
            answer('Mach mal Pause, dein Akku braucht heute offenbar ein Ladekabel.'),
            answer('Leg dich kurz aufs Sofa und gönn dir eine ruhige Pause.'), tool()])
        requests = []
        runtime = ModuleType('runtime')
        runtime.State = lambda *args: object()
        runtime.safe_answer = lambda value: value
        runtime.request_forbidden = lambda value: False

        @contextlib.contextmanager
        def slot(dsn):
            self.assertEqual(dsn, 'restricted-synthetic-slot')
            if slot_error:
                raise slot_error
            try:
                yield
            finally:
                if cleanup_error:
                    raise cleanup_error

        runtime.local_slot = slot
        server = ModuleType('server')
        server.knowledge_for = lambda *args: SimpleNamespace(dsn='restricted-synthetic-slot')

        class Connection:
            def __init__(this, host, port, timeout):
                self.assertEqual((host, port, timeout), ('vector-local-inference', 11434, 60))

            def request(this, method, route, body, headers):
                self.assertEqual((method, route), ('POST', '/api/chat'))
                requests.append(json.loads(body))

            def getresponse(this):
                value = responses.pop(0)
                if isinstance(value, Exception):
                    raise value
                return SimpleNamespace(status=200, read=lambda size: json.dumps(value).encode())

            def close(this):
                pass

        output = io.StringIO()
        payload = {'system': probe.DATA_SYSTEM if data_first else probe.SYSTEM,
                   'tool': probe.TOOL, 'pins': {'test': 'synthetic'}, 'data_first': data_first}
        original_path = list(sys.path)
        timer = itertools.count(step=9 if slow else .001)
        try:
            with patch.dict(sys.modules, {'runtime': runtime, 'server': server}), \
                    patch('http.client.HTTPConnection', Connection), \
                    patch('time.monotonic', side_effect=lambda: next(timer)), \
                    patch('sys.stdin', io.StringIO(json.dumps(payload))), \
                    contextlib.redirect_stdout(output):
                exec(compile(probe.INNER, '<synthetic-native>', 'exec'), {})
        finally:
            sys.path[:] = original_path
        line = next(line for line in output.getvalue().splitlines()
                    if line.startswith('VECTOR_QWEN35_RESULT='))
        return json.loads(line.split('=', 1)[1]), requests

    def test_three_requests_actual_history_native_tool_and_safe_defaults(self):
        result, requests = self.run_inner()
        self.assertTrue(result['passed'])
        self.assertEqual(result['model_calls'], 3)
        self.assertEqual(result['known_input_tokens'], 300)
        self.assertEqual(requests[1]['messages'][1:3], requests[0]['messages'][1:] + [{
            'role': 'assistant', 'content': result['cases'][0]['synthetic_answer']}])
        self.assertEqual(len(requests[2]['messages']), 2)
        for request in requests:
            self.assertIs(request['think'], False)
            self.assertIs(request['stream'], False)
            self.assertNotIn('format', request)
            self.assertEqual(request['options']['num_thread'], 2)
            self.assertEqual(request['options']['num_ctx'], 8192)
            self.assertEqual(request['options']['num_predict'], 96)
        self.assertEqual(requests[2]['tools'], [probe.TOOL])
        self.assertEqual(result['cases'][2]['synthetic_tool_result']['absolute_difference'], 250)
        for key in ('production_activated', 'eligible_for_activation',
                    'production_request_contract_tested', 'live_player_routes_tested',
                    'tool_result_composition_tested'):
            self.assertIs(result[key], False)

    def test_timeout_stops_and_reports_unknown_usage(self):
        result, requests = self.run_inner([TimeoutError()])
        self.assertEqual(len(requests), 1)
        self.assertFalse(result['diagnostic_completed'])
        self.assertEqual(result['unknown_usage_calls'], 1)
        self.assertTrue(result['cases'][0]['server_completion_unknown'])

    def test_busy_slot_makes_no_model_request(self):
        result, requests = self.run_inner(slot_error=RuntimeError('SLOT_BUSY'))
        self.assertEqual(requests, [])
        self.assertEqual(result['model_calls'], 0)
        self.assertEqual(result['unknown_usage_calls'], 0)
        self.assertFalse(result['diagnostic_completed'])

    def test_slot_cleanup_failure_retains_measured_usage(self):
        result, requests = self.run_inner(cleanup_error=RuntimeError('SLOT_RELEASE_FAILED'))
        self.assertEqual(len(requests), 1)
        self.assertEqual(result['known_input_tokens'], 100)
        self.assertEqual(result['known_output_tokens'], 20)
        self.assertEqual(result['unknown_usage_calls'], 0)
        self.assertFalse(result['passed'])

    def test_unexpected_tool_is_not_executed(self):
        value = tool()
        value['message']['tool_calls'][0]['function']['name'] = 'read_private_inventory'
        result, _ = self.run_inner([answer('Du brauchst eine Pause.'),
                                  answer('Ruh dich auf dem Sofa aus.'), value])
        self.assertEqual(result['cases'][-1]['error_code'], 'UNEXPECTED_STATISTICS_ARGUMENTS')
        self.assertNotIn('synthetic_tool_result', result['cases'][-1])

    def test_wrong_player_is_not_substituted(self):
        value = tool()
        value['message']['tool_calls'][0]['function']['arguments']['player_a'] = 'Unknown'
        result, _ = self.run_inner([answer('Du brauchst eine Pause.'),
                                  answer('Ruh dich auf dem Sofa aus.'), value])
        self.assertFalse(result['diagnostic_completed'])
        self.assertEqual(result['cases'][-1]['error_code'], 'UNEXPECTED_STATISTICS_ARGUMENTS')

    def test_thinking_output_rejected_without_exposing_it(self):
        value = answer('Du brauchst eine Pause.')
        value['message']['thinking'] = 'private internal reasoning'
        result, requests = self.run_inner([value])
        self.assertEqual(len(requests), 1)
        self.assertFalse(result['passed'])
        self.assertNotIn('private internal reasoning', json.dumps(result))
        self.assertEqual(result['cases'][0]['thinking_characters'], 26)

    def test_slow_complete_measurement_does_not_qualify(self):
        result, _ = self.run_inner(slow=True)
        self.assertTrue(result['diagnostic_completed'])
        self.assertFalse(result['passed'])
        self.assertFalse(result['cases'][0]['within_existing_backend_budget'])

    def test_advisory_semantic_failure_does_not_discard_remaining_signals(self):
        result, requests = self.run_inner([answer('Die Sonne scheint auf dein Haus.'),
                                          answer('Du brauchst eine Pause.'), tool()])
        self.assertEqual(len(requests), 3)
        self.assertTrue(result['diagnostic_completed'])
        self.assertFalse(result['passed'])

    def test_missing_punctuation_is_advisory_not_transport_failure(self):
        result, requests = self.run_inner([answer('Du brauchst eine Pause'),
                                          answer('Ruh dich auf dem Sofa aus.'), tool()])
        self.assertEqual(len(requests), 3)
        self.assertTrue(result['diagnostic_completed'])
        self.assertFalse(result['passed'])
        self.assertFalse(result['cases'][0]['checks']['complete_sentence'])

    def test_actual_failed_tool_message_is_retained(self):
        value = answer('Ich habe keine Daten.')
        result, _ = self.run_inner([answer('Du brauchst eine Pause.'),
                                  answer('Ruh dich auf dem Sofa aus.'), value])
        self.assertEqual(result['cases'][-1]['synthetic_native_message'], value['message'])

    def test_data_first_two_requests_and_calculated_evidence(self):
        result, requests = self.run_inner([
            answer('Gönn dir eine Pause, die Blöcke laufen dir nicht weg.'),
            answer('ExampleOne liegt mit 250 Mobkills vor ExampleTwo.')], data_first=True)
        self.assertTrue(result['passed'])
        self.assertEqual(result['model_calls'], 2)
        self.assertEqual(result['expected_cases'], 2)
        for request in requests:
            self.assertNotIn('tools', request)
            self.assertEqual(request['options']['presence_penalty'], 0)
            self.assertEqual(request['options']['num_predict'], 64)
        self.assertIn('müde', requests[0]['messages'][1]['content'])
        evidence = json.loads(requests[1]['messages'][1]['content'].removeprefix('Datenblock: '))
        self.assertEqual(evidence['difference'], 250)
        self.assertEqual(evidence['mob_kills'], {'ExampleOne': 1200, 'ExampleTwo': 950})
        self.assertFalse(result['production_activated'])
        self.assertFalse(result['production_request_contract_tested'])

    def test_progress_recovery_preserves_usage_and_marks_interrupted_request(self):
        cases = [{'id': 'smalltalk', 'request_attempted': True,
                  'input_tokens': 100, 'output_tokens': 20}]
        result = probe.recover_progress(cases, ['smalltalk', 'followup'])
        self.assertEqual(result['model_calls'], 2)
        self.assertEqual(result['known_input_tokens'], 100)
        self.assertEqual(result['known_output_tokens'], 20)
        self.assertEqual(result['unknown_usage_calls'], 1)
        self.assertEqual(result['interrupted_requests'], ['followup'])
        self.assertTrue(result['server_completion_unknown'])

    def test_private_evidence_rejects_world_readable_and_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'evidence.json'
            path.write_text('{}')
            guard = SimpleNamespace(checked_path=lambda path: Path(path))
            path.chmod(0o644)
            with self.assertRaisesRegex(RuntimeError, 'OWNED_PRIVATE_EVIDENCE_REQUIRED'):
                probe.private_json(path, guard)
            path.chmod(0o600)
            self.assertEqual(probe.private_json(path, guard), {})
            link = path.with_name('link.json')
            link.symlink_to(path)
            with self.assertRaises(OSError):
                probe.private_json(link, guard)


if __name__ == '__main__':
    unittest.main()
