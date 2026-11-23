"""Registry observations; anonymous requests never discover host credentials."""
import base64
import hashlib
import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from creation_pipeline.records import now

ACCEPT = ', '.join(('application/vnd.oci.image.index.v1+json',
                    'application/vnd.oci.image.manifest.v1+json',
                    'application/vnd.docker.distribution.manifest.list.v2+json',
                    'application/vnd.docker.distribution.manifest.v2+json'))


class RegistryError(ValueError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        result = super().redirect_request(req, fp, code, msg, headers, newurl)
        if result and urllib.parse.urlsplit(req.full_url).netloc != urllib.parse.urlsplit(newurl).netloc:
            result.remove_header('Authorization')
        return result


def split_image(image):
    host, path = image.split('/', 1)
    if host != 'ghcr.io' or not re.fullmatch(r'[a-z0-9][a-z0-9/_.-]+', path.split('@')[0].split(':')[0]):
        raise ValueError('Shared publication currently supports ghcr.io repository names')
    if '@' in path:
        repo, ref = path.split('@', 1)
    else:
        repo, ref = path.rsplit(':', 1)
    if not repo or not ref or any(c.isspace() for c in ref):
        raise ValueError('Explicit registry reference required')
    return host, repo, ref


def credentials(host):
    """Read the configured publisher credential in memory; never log helper output."""
    config_dir = Path(os.environ.get('DOCKER_CONFIG', Path.home() / '.docker'))
    path = config_dir / 'config.json'
    config = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    override = os.environ.get('DOCKER_AUTH_CONFIG')
    if override:
        config = {**config, 'auths': json.loads(override).get('auths', {})}
    helper = config.get('credHelpers', {}).get(host) or config.get('credsStore')
    if helper:
        result = subprocess.run(['docker-credential-' + helper, 'get'], input=host + '\n',
                                capture_output=True, text=True, timeout=20)
        if result.returncode:
            raise RegistryError('Publisher credential helper could not supply registry credentials')
        value = json.loads(result.stdout)
        return value['Username'], value['Secret']
    value = config.get('auths', {}).get(host, {})
    if value.get('auth'):
        return tuple(base64.b64decode(value['auth']).decode().split(':', 1))
    if value.get('username') and value.get('password'):
        return value['username'], value['password']
    raise RegistryError('Log in to ghcr.io before authenticated publication checks')


class Registry:
    def __init__(self, timeout=30, opener=None):
        self.timeout = 30 if timeout is None else min(timeout, 60)
        self.opener = opener or urllib.request.build_opener(PublicRedirect()).open

    def read(self, url, headers=None, limit=None):
        try:
            with self.opener(urllib.request.Request(url, headers=headers or {}), timeout=self.timeout) as response:
                return response.read() if limit is None else response.read(limit)
        except urllib.error.HTTPError as exc:
            raise RegistryError('Registry request failed (HTTP ' + str(exc.code) + ')', exc.code) from None
        except (OSError, ValueError) as exc:
            raise RegistryError('Registry connection failed: ' + type(exc).__name__) from None

    def session(self, image, authenticated=False):
        host, repo, ref = split_image(image)
        headers = {}
        if authenticated:
            username, secret = credentials(host)
            headers['Authorization'] = 'Basic ' + base64.b64encode((username + ':' + secret).encode()).decode()
        scope = 'pull,push' if authenticated else 'pull'
        query = urllib.parse.urlencode({'service': host, 'scope': 'repository:' + repo + ':' + scope})
        token = json.loads(self.read('https://' + host + '/token?' + query, headers))['token']
        return host, repo, ref, {'Authorization': 'Bearer ' + token, 'Accept': ACCEPT}

    def manifest(self, host, repo, ref, headers):
        raw = self.read('https://' + host + '/v2/' + repo + '/manifests/' + ref, headers)
        return json.loads(raw), 'sha256:' + hashlib.sha256(raw).hexdigest()

    def resolve(self, image, authenticated=False):
        host, repo, ref, headers = self.session(image, authenticated)
        try:
            _, digest = self.manifest(host, repo, ref, headers)
            return digest
        except RegistryError as exc:
            if exc.status == 404:
                return None
            raise

    def public(self, image, expected_digest, platform):
        host, repo, ref, headers = self.session(image, authenticated=False)
        manifest, digest = self.manifest(host, repo, ref, headers)
        if digest != expected_digest:
            raise RegistryError('Remote tag differs from the verified image content')
        if 'manifests' in manifest:
            os_name, arch = platform.split('/')
            entry = next((m for m in manifest['manifests'] if m.get('platform', {}).get('os') == os_name
                          and m.get('platform', {}).get('architecture') == arch), None)
            if entry is None:
                raise RegistryError('Published image does not contain the required platform')
            manifest, observed = self.manifest(host, repo, entry['digest'], headers)
            if observed != entry['digest']:
                raise RegistryError('Platform manifest digest mismatch')
        else:
            config = json.loads(self.read('https://' + host + '/v2/' + repo + '/blobs/' + manifest['config']['digest'], headers))
            if config.get('os') + '/' + config.get('architecture') != platform:
                raise RegistryError('Published image platform mismatch')
        layers = []
        for layer in manifest.get('layers', []):
            data = self.read('https://' + host + '/v2/' + repo + '/blobs/' + layer['digest'],
                             {**headers, 'Range': 'bytes=0-0'}, limit=1)
            if not data:
                raise RegistryError('Published layer is not anonymously readable')
            layers.append(layer['digest'])
        return {'status': 'verified', 'image': image, 'digest': digest, 'platform': platform,
                'layers': layers, 'checked_at': now(), 'method': 'anonymous_registry_http'}
