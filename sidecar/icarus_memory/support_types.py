"""Bounded portable evidence data. This value alone never grants authorization."""
from copy import deepcopy
from .self_model_basis import digest

MAX_EVIDENCE = 16
MAX_QUOTE = 4096
MAX_ID = 256
FIELDS = {'episode_id','digest','quote','source_key','metadata_digest','support_generation'}


def parse_support(value):
    if value is None:
        return None
    if (not isinstance(value, dict) or set(value) != {'version','proposal_id','episodes'}
            or type(value['version']) is not int or value['version'] != 1
            or not isinstance(value['proposal_id'],str) or not 1 <= len(value['proposal_id']) <= MAX_ID
            or not isinstance(value['episodes'],list) or not 1 <= len(value['episodes']) <= MAX_EVIDENCE):
        raise ValueError('Invalid episode support')
    for item in value['episodes']:
        if (not isinstance(item,dict) or set(item) != FIELDS
                or any(not isinstance(item[k],str) for k in FIELDS-{'support_generation'})
                or not 1 <= len(item['episode_id']) <= MAX_ID
                or not 1 <= len(item['quote']) <= MAX_QUOTE or not item['digest']
                or len(item['digest']) > 128 or len(item['metadata_digest']) > 128
                or len(item['source_key']) > 2048
                or type(item['support_generation']) is not int or item['support_generation'] < 0):
            raise ValueError('Invalid episode evidence')
    return deepcopy(value)


def identity(assertion):
    # Explicit immutable authorization identity; status/confirmation/sensitivity
    # remain live checks, never a factual freshness grant through this identity.
    from .source_snapshot import canonical_instant
    document = assertion.to_dict()
    document['recorded_at'] = canonical_instant(document['recorded_at'])
    if document['provenance'].get('captured_at'):
        document['provenance']['captured_at'] = canonical_instant(document['provenance']['captured_at'])
    return digest({key: document.get(key) for key in
        ('id','kind','statement','recorded_at','provenance','structured','derived_from','supersedes')})
