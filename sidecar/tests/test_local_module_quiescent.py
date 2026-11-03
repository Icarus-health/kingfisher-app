"""Maintenance cannot overlap source work or admit an in-flight old review."""
import threading

import pytest

from .test_local_module_controller import env, api, begin, terminal, QUESTION


def test_backup_pause_blocks_admission_and_invalidates_unstarted_reviews(env):
    controller = env['create']()
    review = controller.prepare(env['source'].id, QUESTION)
    with controller.quiescent(wait_seconds=0):
        for work in [lambda: controller.prepare(env['source'].id, QUESTION),
                     lambda: begin(controller, env['source'], review=review)]:
            with pytest.raises(api().ControllerError) as error:
                work()
            assert error.value.code == 'Busy'
    with pytest.raises(api().ControllerError) as error:
        begin(controller, env['source'], review=review)
    assert error.value.code == 'ReviewChanged'
    assert terminal(controller, begin(controller, env['source']))['status'] == 'completed'


def test_backup_does_not_yield_while_cancelled_execution_still_exists(env):
    controller = env['create']()
    env['gateway'].ignore_cancel = True
    env['gateway'].release.clear()
    run = begin(controller, env['source'])
    assert env['gateway'].entered.wait(1)
    try:
        with pytest.raises(api().ControllerError) as error:
            with controller.quiescent(wait_seconds=0):
                pytest.fail('Maintenance overlapped the old execution')
        assert error.value.code == 'Busy'
        assert controller.poll(run['id'])['status'] == 'cancelled'
        assert controller.runtime_status()['busy'] is True
        assert not controller._broker.current(env['gateway'].tokens[0])
        with pytest.raises(api().ControllerError):
            begin(controller, env['source'], key='second-request-key')
    finally:
        env['gateway'].release.set()


@pytest.mark.parametrize('operation', ['prepare', 'start'])
def test_admission_crossing_even_a_finished_pause_never_creates_work(env, monkeypatch, operation):
    controller = env['create']()
    review = controller.prepare(env['source'].id, QUESTION)
    entered, release = threading.Event(), threading.Event()
    errors = []
    name = '_scope' if operation == 'prepare' else '_review_current'
    original = getattr(controller, name)

    def wait(*args, **kwargs):
        result = original(*args, **kwargs)
        entered.set()
        assert release.wait(2)
        return result

    monkeypatch.setattr(controller, name, wait)
    def call():
        try:
            if operation == 'prepare':
                controller.prepare(env['source'].id, QUESTION)
            else:
                begin(controller, env['source'], review=review)
        except api().ControllerError as error:
            errors.append(error.code)
    thread = threading.Thread(target=call)
    thread.start()
    assert entered.wait(1)
    try:
        with controller.quiescent(wait_seconds=0):
            pass
    finally:
        release.set()
        thread.join(2)
    assert errors == ['ReviewChanged']
    assert not env['gateway'].tokens


def test_pause_does_not_duplicate_a_completed_idempotent_replay(env):
    controller = env['create']()
    review = controller.prepare(env['source'].id, QUESTION)
    first = terminal(controller, begin(controller, env['source'], review=review))
    calls = len(env['infer_calls'])
    # A terminal result can precede the execution thread's physical exit.
    # Exercise the normal bounded drain rather than racing that cleanup.
    with controller.quiescent(wait_seconds=2):
        pass
    replay = begin(controller, env['source'], review=review)
    assert replay['id'] == first['id']
    assert len(env['infer_calls']) == calls


def test_replay_freshness_crossing_pause_cannot_release_old_completed_text(env, monkeypatch):
    controller = env['create']()
    review = controller.prepare(env['source'].id, QUESTION)
    terminal(controller, begin(controller, env['source'], review=review))
    original = controller._review_current

    def crossing(*args):
        result = original(*args)
        with controller.quiescent(wait_seconds=2):
            pass
        return result

    monkeypatch.setattr(controller, '_review_current', crossing)
    with pytest.raises(api().ControllerError) as error:
        begin(controller, env['source'], review=review)
    assert error.value.code == 'ReviewChanged'


def test_nested_pause_and_close_do_not_reenable_admission(env):
    controller = env['create']()
    with controller.quiescent(wait_seconds=0):
        with controller.quiescent(wait_seconds=0):
            pass
        with pytest.raises(api().ControllerError):
            controller.prepare(env['source'].id, QUESTION)
        controller.close()
    with pytest.raises(api().ControllerError) as error:
        controller.prepare(env['source'].id, QUESTION)
    assert error.value.code == 'Restarted'
