import socket

_original = socket.socket.connect, socket.socket.connect_ex

def _blocked(*args, **kwargs):
    raise ConnectionRefusedError('This offline test run may not connect to sockets.')

def pytest_sessionstart(session):
    socket.socket.connect = socket.socket.connect_ex = _blocked

def pytest_sessionfinish(session, exitstatus):
    socket.socket.connect, socket.socket.connect_ex = _original
