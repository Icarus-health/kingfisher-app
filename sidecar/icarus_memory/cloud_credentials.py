"""Vorbereitete Schlüssel sind keine automatische Wahl eines Standardanbieters."""
PREPARED_CLOUD_KEYS = {
    'anthropic': 'ICARUS_PREPARED_ANTHROPIC_API_KEY',
    'openai': 'ICARUS_PREPARED_OPENAI_API_KEY',
    'mistral': 'MISTRAL_API_KEY',
}

# Source packages have their own fixed identity, independent of ordinary chat.
MISTRAL_IMPORT_MODEL = 'mistral-small-2603'
MISTRAL_IMPORT_ENDPOINT = 'https://api.eu.mistral.ai/v1'
MISTRAL_REVISION_KEY = 'CLOUD_IMPORT_MISTRAL_REVISION'
