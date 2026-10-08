"""Product source embeddings require positively verified local weights."""
import httpx
import pytest
from icarus_memory.local_embeddings import LocalEmbedder
from icarus_memory.providers import ProviderError


def transport(seen, *, tag_remote=False, show_remote=False, capability=True, flip=None):
    def respond(request):
        seen.append(request.url.path)
        remote = tag_remote or bool(flip and flip[0])
        if request.url.path == '/api/tags':
            row = {'name':'bge-m3:latest','digest':'a'*64,'size':100,
                   'details':{'format':'gguf'}}
            if remote:
                row.update(remote_host='https://cloud.invalid',remote_model='embedding')
            return httpx.Response(200,json={'models':[row]})
        if request.url.path == '/api/show':
            row = {'details':{'format':'gguf'},'model_info':{
                'general.architecture':'bert','general.parameter_count':100},
                'capabilities':['embedding'] if capability else ['completion']}
            if show_remote:
                row['remote_host']='https://cloud.invalid'
            return httpx.Response(200,json=row)
        return httpx.Response(200,json={'model':'bge-m3:latest','embeddings':[[1.,0.]]})
    return httpx.MockTransport(respond)


@pytest.mark.parametrize('scenario', ['tag_remote','show_remote','missing_embedding'])
def test_remote_or_unverified_exact_embedding_target_never_receives_source(scenario):
    seen=[]
    kwargs={scenario:True} if scenario!='missing_embedding' else {'capability':False}
    with pytest.raises((ProviderError, RuntimeError)):
        with LocalEmbedder(transport=transport(seen,**kwargs),verify_weights=True) as embedder:
            embedder.embed(['synthetic private source'])
    assert '/api/embed' not in seen


def test_weight_check_is_fresh_immediately_before_source_submission():
    seen=[]; remote=[False]
    with LocalEmbedder(transport=transport(seen,flip=remote),verify_weights=True) as embedder:
        remote[0]=True
        with pytest.raises((ProviderError, RuntimeError)):
            embedder.embed(['synthetic private source'])
    assert '/api/embed' not in seen


def test_verified_embedding_capability_and_digest_can_embed_locally():
    seen=[]
    with LocalEmbedder(transport=transport(seen),verify_weights=True,keep_alive='15s') as embedder:
        assert embedder.model_key == 'bge-m3:latest:'+'a'*64
        assert embedder.embed(['synthetic source']) == [[1.,0.]]
    assert '/api/show' in seen and seen.count('/api/embed') == 1


def test_permission_withdrawn_during_metadata_check_stops_before_source_post():
    seen=[]; allowed=[True]; show_calls=[0]
    original=transport(seen)
    def respond(request):
        response=original.handle_request(request)
        if request.url.path=='/api/show':
            show_calls[0]+=1
            if show_calls[0]==2:
                allowed[0]=False
        return response
    with LocalEmbedder(transport=httpx.MockTransport(respond),verify_weights=True) as embedder:
        def permitted():
            if not allowed[0]:
                raise RuntimeError('permission revoked')
        embedder.permission_check=permitted
        with pytest.raises(RuntimeError,match='permission revoked'):
            embedder.embed(['synthetic private source'])
    assert '/api/embed' not in seen
