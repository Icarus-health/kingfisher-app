"""Gemeinsames für die Microsoft-Tests: kein Netz außer 127.0.0.1, die Graph-Attrappe als Umgebung."""
from __future__ import annotations

import ipaddress
import socket

import pytest

from icarus_memory import microsoft_anmeldung
from tests.graph_attrappe import CLIENT_ID, GraphAttrappe


def _lokal(adresse) -> bool:
    if isinstance(adresse, tuple) and adresse:
        try:
            return ipaddress.ip_address(adresse[0]).is_loopback
        except ValueError:
            return adresse[0] == 'localhost'
    return True  # Unix-Sockets


class NetzVersuch(ConnectionRefusedError):
    """Wie ein Rechner ohne Netz; der Versuch steht trotzdem in der Liste, und `graph` lässt den Test daran scheitern."""


@pytest.fixture
def kein_netz(monkeypatch):
    """Jede Verbindung außer zu 127.0.0.1 schlägt fehl, und der Versuch wird gemerkt (auch DNS über UDP).

    Schon die Namensauflösung eines fremden Rechners zählt als Versuch. Sonst bliebe die Liste leer, wo die
    Auflösung vorher scheitert (etwa in einer abgeschotteten Umgebung), und eine DNS-Anfrage ginge hinaus.
    """
    versuche: list = []
    # Ein Proxy auf 127.0.0.1 wäre sonst ein Weg nach draußen, den die Sperre unten für lokal hält.
    for name in ('HTTPS_PROXY', 'https_proxy', 'HTTP_PROXY', 'http_proxy', 'ALL_PROXY', 'all_proxy'):
        monkeypatch.delenv(name, raising=False)
    connect, sendto, aufloesen = socket.socket.connect, socket.socket.sendto, socket.getaddrinfo

    def nur_lokal_aufloesen(host, *rest, **benannt):
        name = host.decode() if isinstance(host, bytes) else host
        if name is not None and not _lokal((name,)):
            versuche.append((name, *rest[:1]))
            raise NetzVersuch(f'Netzzugriff in einem Test: {name}')
        return aufloesen(host, *rest, **benannt)

    def nur_lokal(sock, adresse, *rest):
        if not _lokal(adresse):
            versuche.append(adresse)
            raise NetzVersuch(f'Netzzugriff in einem Test: {adresse}')
        return connect(sock, adresse, *rest)

    def senden(sock, daten, *rest):
        adresse = rest[-1]
        if not _lokal(adresse):
            versuche.append(adresse)
            raise NetzVersuch(f'Netzzugriff in einem Test: {adresse}')
        return sendto(sock, daten, *rest)

    monkeypatch.setattr(socket.socket, 'connect', nur_lokal)
    monkeypatch.setattr(socket.socket, 'sendto', senden)
    monkeypatch.setattr(socket, 'getaddrinfo', nur_lokal_aufloesen)
    return versuche


@pytest.fixture
def graph(monkeypatch, kein_netz):
    dienst = GraphAttrappe()
    monkeypatch.setenv(microsoft_anmeldung.LOGIN_ENV, dienst.login)
    monkeypatch.setenv(microsoft_anmeldung.GRAPH_ENV, dienst.graph)
    monkeypatch.setenv(microsoft_anmeldung.CLIENT_ENV, CLIENT_ID)
    monkeypatch.delenv(microsoft_anmeldung.TENANT_ENV, raising=False)
    monkeypatch.setenv('ICARUS_SECRETS_PASSPHRASE', 'probe-passphrase-nur-fuer-tests')
    monkeypatch.setattr(microsoft_anmeldung, 'INTERVALL', 0)
    yield dienst
    dienst.stop()
    assert not kein_netz, f'Ein Test wollte ins Netz: {kein_netz}'


class Schluessel:
    """Ein Schlüsselspeicher im Arbeitsspeicher."""

    def __init__(self) -> None:
        self.werte: dict[str, str] = {}
        self.available = True

    def get(self, name):
        return self.werte.get(name)

    def set(self, name, wert):
        self.werte[name] = wert

    def delete(self, name):
        self.werte.pop(name, None)


class Uhr:
    def __init__(self, jetzt: float = 1_800_000_000.0) -> None:
        self.jetzt = jetzt

    def __call__(self) -> float:
        return self.jetzt
