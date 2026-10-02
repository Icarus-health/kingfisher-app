"""Small transaction helpers; nested writes join their owning operation."""
from contextlib import contextmanager


@contextmanager
def sqlite_transaction(connection, lock):
    with lock:
        owns = not connection.in_transaction
        if owns:
            connection.execute('BEGIN IMMEDIATE')
        try:
            yield
            if owns:
                connection.commit()
        except BaseException:
            if owns:
                connection.rollback()
            raise
