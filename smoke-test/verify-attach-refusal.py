"""Real Wine startup boundary: attach must not create a host when none exists.

Run only inside an isolated container, or after its owned host has stopped.
This gate never stops processes, retries startup, or cleans someone else's host.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time


def inventory():
    result = subprocess.run(['ps', '-eo', 'pid,ppid,comm'], capture_output=True,
                            text=True, check=True, timeout=10)
    rows = []
    for line in result.stdout.splitlines()[1:]:
        pid, parent, name = line.strip().split(None, 2)
        if Path(name).name.casefold() in ('sldworks.exe', 'python.exe', 'pythonw.exe', 'swclid'):
            rows.append({'pid': int(pid), 'parent': int(parent), 'name': name})
    return {'raw': result.stdout, 'relevant': rows}


def verify(directory, cli, endpoint):
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / 'attach-refusal.json'
    proof = {'completed': False, 'success': False, 'endpoint': endpoint,
             'startup_calls': 0, 'events': [], 'observed_sw_processes': [],
             'cleanup_performed': False}
    with report.open('x', encoding='utf-8'):
        pass

    def save():
        report.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n')

    def call(name, arguments, timeout):
        command = [cli, '--endpoint', endpoint, *arguments]
        stdout, stderr = directory / (name + '.stdout'), directory / (name + '.stderr')
        row = {'name': name, 'command': command}
        proof['events'].append(row)
        save()
        with stdout.open('xb') as out, stderr.open('xb') as err:
            result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=out,
                                    stderr=err, timeout=timeout)
        row.update(exit_code=result.returncode,
                   stdout_sha256=hashlib.sha256(stdout.read_bytes()).hexdigest(),
                   stderr_sha256=hashlib.sha256(stderr.read_bytes()).hexdigest())
        save()
        return result.returncode, json.loads(stdout.read_text(encoding='utf-8'))

    def require_stopped(name):
        code, value = call(name, ['--request-timeout', '2', 'daemon', 'status', '--json'], 10)
        if code == 0 or value.get('success') is not False or value.get('error', {}).get('code') != 'ConnectionRefusedError':
            raise AssertionError('Endpoint is not proven stopped: ' + name)

    monitor_stop = threading.Event()
    monitor_errors = []

    def monitor():
        while not monitor_stop.is_set():
            try:
                rows = inventory()['relevant']
                sw = [row for row in rows if Path(row['name']).name.casefold() == 'sldworks.exe']
                if sw:
                    proof['observed_sw_processes'].append(sw)
            except Exception as exc:
                monitor_errors.append(str(exc))
                return
            monitor_stop.wait(.1)

    thread = None
    save()
    try:
        proof['before'] = inventory()
        save()
        if proof['before']['relevant']:
            raise AssertionError('Pre-existing SW/Windows Python process; no startup attempted')
        require_stopped('status-before')
        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
        proof['startup_calls'] = 1
        started = time.monotonic()
        code, value = call('attach-existing', ['daemon', 'start', '--attach-existing',
                           '--startup-timeout', '120', '--json'], 150)
        proof['startup_seconds'] = time.monotonic() - started
        if code == 0 or value.get('success') is not False or value.get('error', {}).get('code') != 'ExistingHostNotFound':
            raise AssertionError('Expected nonzero ExistingHostNotFound JSON')
        if value.get('cleanup_errors'):
            raise AssertionError('Startup returned cleanup errors')
        require_stopped('status-after')
    except Exception as exc:
        proof['first_failure'] = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        monitor_stop.set()
        if thread is not None:
            thread.join(timeout=12)
        try:
            proof['after'] = inventory()
            if proof['after']['relevant']:
                raise AssertionError('SW/Windows daemon processes remained')
            if proof['observed_sw_processes'] or monitor_errors:
                raise AssertionError('SW appeared during refusal, or process observation failed')
        except Exception as exc:
            proof.setdefault('first_failure', {'type': type(exc).__name__, 'message': str(exc)})
        proof['monitor_errors'] = monitor_errors
        proof['completed'] = True
        proof['success'] = 'first_failure' not in proof
        save()
    if not proof['success']:
        raise AssertionError(proof['first_failure'])
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--cli-command', default='/usr/local/bin/swcli')
    parser.add_argument('--endpoint', default=os.environ.get('SWCLI_ENDPOINT', '127.0.0.1:18495'))
    args = parser.parse_args()
    verify(args.output_dir, args.cli_command, args.endpoint)


if __name__ == '__main__':
    main()
