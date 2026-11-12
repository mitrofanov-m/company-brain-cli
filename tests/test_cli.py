"""Executable client tests against an isolated, synthetic HTTP API."""
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from brain_cli import cli
from brain_cli.client import APIError, BrainAPIClient

ROOT = Path(__file__).resolve().parents[1]


class ClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calls = []
        class Handler(BaseHTTPRequestHandler):
            def respond(self):
                payload = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
                cls.calls.append((self.command, self.path, payload, dict(self.headers)))
                status, result = 200, {}
                if self.headers.get('Authorization') == 'Bearer rejected-fixture':
                    status, result = 401, {'error': 'invalid token'}
                elif self.path == '/redirect':
                    self.send_response(302)
                    self.send_header('Location', '/credential-sink')
                    self.end_headers()
                    return
                elif self.path == '/v1/workspaces':
                    result = {'workspaces': [{'id': 'w'}]}
                elif self.path == '/v1/workspaces/w/sessions':
                    result = {'id': 's', 'workspace_id': 'w'}
                elif self.path == '/v1/workspaces/w':
                    result = {'resources': [{'path': 'docs/hello.md'}, {'path': 'other.md'}]}
                elif '/resources/' in self.path:
                    result = {'content': {'content_base64': base64.b64encode(b'hello\x00world\n').decode()}}
                elif '/search?' in self.path:
                    result = {'results': [{'path': 'docs/hello.md'}]}
                elif self.path.endswith('/changesets'):
                    result = {'changesets': [{'session_id': 's'}]}
                elif self.path == '/v1/sessions/s/history':
                    result = {'events': [{'kind': 'resource.read'}]}
                elif self.path == '/v1/sessions/s/tools/brain.execute':
                    failed = payload['arguments']['script'] == 'fail'
                    result = {'exit_code': 3 if failed else 0, 'stdout': {'content_base64': 'cnVuLW9rCg=='}, 'stderr': {'content_base64': ''}, 'commit': None}
                elif self.path.endswith('/tools/files.write'):
                    result = {'staged': True}
                elif self.path.endswith('/commit'):
                    result = {'paths': ['docs/hello.md']}
                elif '/tools/' in self.path:
                    result = {'name': 'files.write', 'ok': True}
                elif self.path.endswith('/tools') or '/tool-search?' in self.path:
                    result = {'tools': [{'name': 'files.write'}]}
                elif self.path.startswith('/v1/sessions/'):
                    result = {'id': 's', 'workspace_id': 'w'}
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            do_GET = do_POST = do_DELETE = respond
            def log_message(self, *args):
                pass
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        scratch = ROOT / '.test-tmp'
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.cwd = Path(self.temp.name)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('BRAIN_')}
        self.env.update(PYTHONPATH=str(ROOT / 'src'), PYTHONDONTWRITEBYTECODE='1',
                        TMPDIR=str(scratch), BRAIN_API_URL=self.url,
                        BRAIN_TOKEN='synthetic-fixture-key', BRAIN_WORKSPACE_ID='w')
        self.calls.clear()

    def run_cli(self, *args, stdin=None, **env):
        return subprocess.run([sys.executable, '-m', 'brain_cli', *args], cwd=self.cwd,
                              env={**self.env, **env}, input=stdin, capture_output=True, timeout=10)

    def okay(self, *args, **kwargs):
        result = self.run_cli(*args, **kwargs)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def test_version_and_help_work_without_server(self):
        for args in (('--help',), ('--version',), ('help',)):
            self.okay(*args, BRAIN_API_URL='http://127.0.0.1:1')
        self.assertFalse(self.calls)

    def test_workspace_list_tree_binary_read_search_and_history(self):
        self.assertEqual(json.loads(self.okay('workspaces').stdout)[0]['id'], 'w')
        self.assertEqual(self.okay('ls', 'docs').stdout, b'docs/hello.md\n')
        self.assertEqual(self.okay('cat', 'docs/hello.md').stdout, b'hello\x00world\n')
        self.assertEqual(json.loads(self.okay('search', 'hello world').stdout)[0]['path'], 'docs/hello.md')
        self.assertIn('q=hello%20world', self.calls[-1][1])
        self.assertEqual(json.loads(self.okay('history').stdout)[0]['session_id'], 's')
        self.assertEqual(self.calls[-1][3]['Authorization'], 'Bearer synthetic-fixture-key')
        self.assertEqual(self.calls[-1][3]['X-Brain-Client'], 'cli')

    def test_session_write_commit_resume_close_and_private_config(self):
        self.okay('session', 'start')
        config = self.cwd / '.brain/config.json'
        self.assertEqual(config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(config.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(json.loads(config.read_text())['session_id'], 's')
        self.okay('files', 'write', 'docs/hello.md', '--commit', stdin=b'hello')
        self.assertEqual(self.calls[-2][2]['arguments']['content'], 'hello')
        self.assertEqual(self.calls[-1][1], '/v1/sessions/s/commit')
        self.okay('files', 'delete', 'docs/hello.md', '--commit')
        self.okay('session', 'commit')
        self.okay('session', 'resume', 's')
        self.assertEqual(json.loads(self.okay('history', '--session-events').stdout)[0]['kind'], 'resource.read')
        self.okay('session', 'close')
        self.assertNotIn('session_id', json.loads(config.read_text()))
        self.assertEqual(self.run_cli('files', 'write', 'x', stdin=b'x').returncode, 1)

    def test_tools_discovery_detail_call_and_help(self):
        self.okay('session', 'start')
        for args in (('tools', 'list'), ('tools', 'search', 'write'),
                     ('tools', 'detail', 'files.write'),
                     ('tools', 'call', 'files.write', '{"path":"hello.md","content":"x"}'), ('help',)):
            with self.subTest(args=args):
                self.okay(*args)

    def test_file_input_and_remote_script_exit_status(self):
        self.okay('session', 'start')
        source = self.cwd / 'input.md'
        source.write_text('from disk')
        self.okay('files', 'write', 'docs/hello.md', str(source))
        self.assertEqual(self.calls[-1][2]['arguments']['content'], 'from disk')
        script = self.cwd / 'task.py'
        script.write_text('raise RuntimeError("must not run locally")')
        result = self.okay('run', str(script))
        self.assertEqual(result.stdout, b'run-ok\n')
        self.assertEqual(json.loads(result.stderr)['exit_code'], 0)
        script.write_text('fail')
        result = self.run_cli('run', str(script))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stderr)['exit_code'], 3)

    def test_workspace_mismatch_rejected_before_write(self):
        self.okay('session', 'start')
        self.calls.clear()
        result = self.run_cli('--workspace', 'other', 'files', 'write', 'x', stdin=b'x')
        self.assertEqual(result.returncode, 1)
        self.assertIn(b'different workspace', result.stderr)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][0], 'GET')

    def test_environment_overrides_saved_context_and_flags_override_environment(self):
        self.okay('session', 'start')
        (self.cwd / '.brain/config.json').write_text(json.dumps({'workspace_id': 'wrong', 'session_id': 'stale'}))
        self.okay('ls', BRAIN_SESSION_ID='s')
        self.assertEqual(self.calls[-1][1], '/v1/workspaces/w')
        self.okay('--workspace', 'w', '--session', 's', 'ls', BRAIN_WORKSPACE_ID='wrong', BRAIN_SESSION_ID='wrong')
        self.assertEqual(self.calls[-1][1], '/v1/workspaces/w')

    def test_guest_does_not_reuse_saved_private_session(self):
        self.okay('session', 'start')
        self.calls.clear()
        self.okay('cat', 'docs/hello.md', BRAIN_TOKEN='')
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][1], '/v1/workspaces/w/resources/docs/hello.md')
        self.assertNotIn('Authorization', self.calls[0][3])

    def test_api_error_does_not_print_key_or_traceback(self):
        result = self.run_cli('workspaces', BRAIN_TOKEN='rejected-fixture')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, b'brain: invalid token\n')

    def test_invalid_json_arguments_and_usage_are_nonzero(self):
        result = self.run_cli('--session', 's', 'tools', 'call', 'files.write', '{')
        self.assertEqual(result.returncode, 1)
        self.assertNotIn(b'Traceback', result.stderr)
        self.assertEqual(self.run_cli('not-a-command').returncode, 2)

    def test_config_cannot_escape_working_directory_or_follow_file_symlink(self):
        result = self.run_cli('help', BRAIN_CONFIG_DIR=str(ROOT / '.test-tmp'))
        self.assertEqual(result.returncode, 1)
        (self.cwd / '.brain').mkdir()
        target = self.cwd / 'config-target.json'
        target.write_text('{}')
        (self.cwd / '.brain/config.json').symlink_to(target)
        result = self.run_cli('help')
        self.assertEqual(result.returncode, 1)
        self.assertIn(b'symlink', result.stderr)
        self.assertEqual(target.read_text(), '{}')

    def test_login_prompt_stores_key_privately(self):
        with patch.object(cli, '_config_path', return_value=self.cwd / '.brain/config.json'), \
             patch('getpass.getpass', return_value='synthetic-login-fixture'), \
             patch('sys.stdout'):
            self.assertEqual(cli.main(['login', '--api-url', self.url]), 0)
        config = self.cwd / '.brain/config.json'
        self.assertEqual(config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(config.read_text())['token'], 'synthetic-login-fixture')

    def test_redirect_does_not_forward_credentials(self):
        with self.assertRaises(APIError):
            BrainAPIClient(self.url, 'synthetic-fixture-key').request('GET', '/redirect')
        self.assertEqual([call[1] for call in self.calls], ['/redirect'])

    def test_api_origin_validation_and_segment_encoding(self):
        for url in ('http://example.test', 'https://user:password@example.test',
                    'https://example.test/path', 'https://example.test/?key=x'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                BrainAPIClient(url, 'synthetic-fixture-key')
        self.assertEqual(BrainAPIClient.segment('a/b ?'), 'a%2Fb%20%3F')


if __name__ == '__main__':
    unittest.main()
