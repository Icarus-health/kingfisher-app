"""Eine Aussage zur lokalen KI (Fremdprobe, Befund 9): nach „Alles einrichten“ sagt jede Stelle dasselbe."""
import pytest
from fastapi.testclient import TestClient

from icarus_memory import device_profile
from icarus_memory.server import create_app
from tests.ollama_fake import FakeOllama, Verbindungsfehler

MODELL = 'qwen3.5:4b'


@pytest.fixture
def app_und_client(monkeypatch):
    # Wie in der Fremdprobe: kein Anbieter aus der Umgebung, keiner in der Einstellungsdatei.
    for name in ('ICARUS_PROVIDER', 'ICARUS_BASE_URL', 'ICARUS_MODEL', 'ICARUS_TRUSTED_LOCAL_MODEL_HOSTS'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(device_profile, 'freier_platz_gb', lambda *a, **k: None)
    app = create_app()
    with TestClient(app) as client:
        yield app, client


def ollama(app, fake):
    app.state.ollama_transport = fake.transport
    app.state.ollama_inventar.vergiss()


def lokale_ki(client):
    stand = client.get('/api/v1/setup').json()['status']['lokale_ki']
    assert stand == client.get('/api/v1/models/stand').json()   # eine Quelle, zwei Wege dorthin
    return stand


def test_ohne_modell_keins(app_und_client):
    app, client = app_und_client
    ollama(app, FakeOllama(installiert=[]))
    stand = lokale_ki(client)
    assert stand['zustand'] == 'keins' and stand['kurz'] == 'Noch kein Modell eingerichtet'


def test_nach_alles_einrichten_bereit_und_die_liste_stimmt(app_und_client):
    """Befund 9: Der Anbietername in der Datei bleibt leer; trotzdem ist das Modell lokal, erreichbar und bereit."""
    app, client = app_und_client
    fake = FakeOllama(installiert=[MODELL, 'bge-m3'])
    ollama(app, fake)
    antwort = client.put('/api/v1/models/roles/antwort', json={'modell': MODELL})
    assert antwort.status_code == 200, antwort.text
    assert app.state.settings.provider == ''   # die Ursache der widersprüchlichen Anzeige bleibt bestehen …
    stand = lokale_ki(client)                    # … und stört die Aussage nicht mehr
    assert stand['zustand'] == 'bereit' and stand['lokal'] is True and stand['erreichbar'] is True
    assert stand['satz'] == f'Eingerichtet und bereit: {MODELL} läuft auf diesem Rechner.'
    assert MODELL in stand['installiert'] and 'bge-m3:latest' in stand['installiert']
    # Die Modellliste kommt von der Adresse, unter der Kingfisher Ollama selbst findet, nicht aus Docker.
    assert 'host.docker.internal' not in stand['endpunkt']


def test_ollama_aus_und_modell_fehlt_werden_benannt(app_und_client):
    app, client = app_und_client
    ollama(app, FakeOllama(installiert=[MODELL]))
    assert client.put('/api/v1/models/roles/antwort', json={'modell': MODELL}).status_code == 200
    ollama(app, Verbindungsfehler())
    stand = lokale_ki(client)
    assert stand['zustand'] == 'nicht_erreichbar' and 'Ollama antwortet gerade nicht' in stand['satz']
    ollama(app, FakeOllama(installiert=['anderes-modell']))
    stand = lokale_ki(client)
    assert stand['zustand'] == 'fehlt' and stand['installiert'] == ['anderes-modell:latest']
