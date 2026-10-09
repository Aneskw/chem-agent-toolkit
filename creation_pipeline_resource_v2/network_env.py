"""Inherit explicit proxies; otherwise use the user's configured macOS proxy."""
import os
import re
import subprocess
import sys


def model_environment():
    env = os.environ.copy()
    if sys.platform != 'darwin' or any(env.get(k) for k in
            ('HTTPS_PROXY', 'https_proxy', 'ALL_PROXY', 'all_proxy')):
        return env
    try:
        result = subprocess.run(['scutil', '--proxy'], capture_output=True, text=True, timeout=3)
        fields = dict(re.findall(r'^\s*(\w+)\s*:\s*(\S+)\s*$', result.stdout, re.M))
        if fields.get('HTTPSEnable') == '1':
            host, port = fields['HTTPSProxy'], int(fields['HTTPSPort'])
            if not re.fullmatch(r'[A-Za-z0-9.\-]+', host) or not 0 < port < 65536:
                return env
            proxy = f'http://{host}:{port}'
            env.setdefault('HTTPS_PROXY', proxy)
            env.setdefault('HTTP_PROXY', proxy)
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
        pass
    return env
