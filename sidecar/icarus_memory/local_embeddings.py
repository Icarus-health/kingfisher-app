"""Bounded local-only Ollama embeddings using an already installed model."""
import httpx
from .providers import is_local_endpoint

class LocalEmbedder:
    """Bounded diagnostic adapter; no application configuration is loaded."""
    is_local = True
    model = 'bge-m3:latest'

    def __init__(self, *, transport=None, base_url="http://127.0.0.1:11434", trusted_local_hosts=(), timeout=30,
                 model=None, keep_alive=None):
        if not is_local_endpoint(base_url, trusted_local_hosts):
            raise ValueError("Embedding endpoint must be explicitly local")
        if model:
            # Modell der Rolle „einbettung“ (Einstellungen); ohne Angabe bleibt es bge-m3.
            self.model = model
        self.client = httpx.Client(base_url=base_url.rstrip("/"), trust_env=False,
                                   follow_redirects=False, timeout=timeout, transport=transport)
        self.model_key = ''
        self.keep_alive = keep_alive

    def __enter__(self):
        try:
            self.model_key = self.identity()
        except BaseException:
            self.client.close()
            raise
        return self

    def __exit__(self, *_):
        self.client.close()

    def identity(self):
        response = self.client.get('/api/tags')
        response.raise_for_status()
        for row in response.json()['models']:
            # /api/tags does not require capabilities in its documented response.
            if row.get('name') == self.model and ('capabilities' not in row or 'embedding' in row['capabilities']):
                digest = row.get('digest', '')
                if len(digest) == 64 and all(c in '0123456789abcdef' for c in digest):
                    return self.model + ':' + digest
        raise RuntimeError('Exact local embedding model is not installed; no download attempted')

    def embed(self, texts):
        if not isinstance(texts, list) or not 1 <= len(texts) <= 128:
            raise RuntimeError('Invalid embedding batch')
        if any(not isinstance(t, str) or len(t.encode('utf-8')) > 8192 for t in texts):
            raise RuntimeError('Embedding text budget exceeded')
        try:
            if self.identity() != self.model_key:
                raise RuntimeError('Installed embedding weights changed')
            payload = {'model': self.model, 'input': texts, 'truncate': False}
            if self.keep_alive is not None:
                payload['keep_alive'] = self.keep_alive
            response = self.client.post('/api/embed', json=payload)
            response.raise_for_status()
            data = response.json()
            if data.get('model') != self.model or self.identity() != self.model_key:
                raise RuntimeError('Embedding model identity mismatch')
            return data['embeddings']
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise RuntimeError('Local embedding failed') from exc

