#!/usr/bin/env python3
"""Read-only host capacity report. No installation, credentials or serials."""
import json
import os
import shutil
import subprocess
from pathlib import Path

def command(args):
    if not shutil.which(args[0]):
        return None
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=15)
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None

def main():
    cpu = Path('/proc/cpuinfo').read_text()
    fields = {}
    for line in cpu.splitlines():
        if ':' in line:
            key, value = line.split(':', 1)
            fields.setdefault(key.strip(), value.strip())
    memory = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, value = line.split(':', 1)
        if key in {'MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree'}:
            memory[key + '_GiB'] = round(int(value.split()[0]) / 1024**2, 2)
    pci = command(['lspci'])
    displays = [line for line in (pci or '').splitlines()
                if any(term in line.lower() for term in ('vga', '3d controller', 'display controller'))]
    nvidia = command(['nvidia-smi', '--query-gpu=name,memory.total,driver_version',
                      '--format=csv,noheader,nounits'])
    disk = shutil.disk_usage('/opt/vector' if Path('/opt/vector').is_dir() else '/')
    flags = set(fields.get('flags', '').split())
    print(json.dumps({
        'cpu_model': fields.get('model name'),
        'logical_cpus': os.cpu_count(),
        'cpu_features': sorted(flags & {'avx', 'avx2', 'avx512f', 'avx512_vnni', 'amx_tile'}),
        'load_average': list(os.getloadavg()),
        'memory': memory,
        'disk_free_GiB': round(disk.free / 1024**3, 2),
        'display_devices': displays,
        'nvidia_name_vramMiB_driver': nvidia,
        'ollama_binary_present': shutil.which('ollama') is not None,
        'note': 'Missing GPU output is inconclusive when detection utilities or drivers are absent.'
    }, indent=2))

if __name__ == '__main__':
    main()
