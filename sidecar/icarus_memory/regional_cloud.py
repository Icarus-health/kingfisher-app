"""Fixed regional inference endpoints; no redirects, proxies or global fallback."""
import httpx

from .cloud_access_routes import PROVIDERS
from .providers import OpenAICompatible


class RegionalCloud(OpenAICompatible):
    def __init__(self, provider: str, model: str, api_key: str):
        super().__init__(model, api_key, base_url=PROVIDERS[provider][2])
        self.name = provider

    def _client(self, timeout):
        return httpx.Client(timeout=timeout, trust_env=False, follow_redirects=False)

    def _request_payload(self, payload):
        payload['max_tokens'] = 1024
        if self.name == 'openrouter':
            payload['provider'] = {'zdr': True, 'data_collection': 'deny', 'allow_fallbacks': False}
        return payload
