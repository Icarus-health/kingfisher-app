"""Bound background validation cost without relaxing any release guard."""
import threading
import time

from tests.test_local_module_controller import env, begin


def blocked(env):
    gateway = env['gateway']
    gateway.release.clear()
    gateway.ignore_cancel = True
    return env['create']()


def test_waiting_job_does_not_continuously_reread_provider_metadata(env):
    controller = blocked(env)
    provider = controller._provider
    calls, lock = [], threading.Lock()
    def counted_provider():
        with lock:
            calls.append(time.monotonic())
        return provider()
    controller._provider = counted_provider
    run = begin(controller, env['source'])
    try:
        assert env['gateway'].entered.wait(1)
        # Only the idle background watcher can request provider identity here:
        # the gateway is blocked, no poll/tool/model/status request is made.
        started = time.monotonic()
        time.sleep(1.2)
        ended = time.monotonic()
        with lock:
            observed = [stamp for stamp in calls if started <= stamp < ended]
        # Two identity reads per full refresh. Allow two rounds for timer phase,
        # while refusing the former tens-of-refreshes-per-second busy polling.
        assert len(observed) <= 4, f'{len(observed)} provider metadata reads while waiting'
        assert not env['infer_calls']
    finally:
        controller.cancel(run['id'])
        env['gateway'].release.set()


def test_cancel_wakes_background_watch_before_its_interval_without_releasing_busy_work(env):
    controller = blocked(env)
    watch = controller._watch
    refresh = controller._refresh
    exited, checked = threading.Event(), threading.Event()
    def observed_refresh(job):
        refresh(job)
        if env['gateway'].entered.is_set():
            checked.set()
    controller._refresh = observed_refresh
    def observed(job):
        try:
            watch(job)
        finally:
            exited.set()
    controller._watch = observed
    run = begin(controller, env['source'])
    try:
        assert env['gateway'].entered.wait(1)
        # Observe a real background pass first, then allow it to park again.
        # Cancelling before the watch thread starts would miss a sleep bug.
        assert checked.wait(1.5)
        time.sleep(.02)
        result = controller.cancel(run['id'])
        assert exited.wait(.5), 'cancel must wake the watcher immediately'
        assert result['status'] == 'cancelled' and result['execution_pending'] is True
        assert controller.runtime_status()['busy'] is True
        assert not controller._broker.current(env['gateway'].tokens[0])
        assert not env['infer_calls']
    finally:
        env['gateway'].release.set()


def test_background_watch_revokes_withdrawn_source_by_next_check_without_poll(env):
    controller = blocked(env)
    run = begin(controller, env['source'])
    try:
        assert env['gateway'].entered.wait(1)
        with controller._lock:
            job = controller._jobs[run['id']]
        env['episodes'].ignore(env['source'].id)
        # Waiting for the cancellation event cannot itself call freshness/poll.
        assert job.cancelled.wait(1.5), 'withdrawal must be observed by the next background check'
        with controller._lock:
            result = controller._public(job)
        assert result['status'] == 'stale' and result['execution_pending'] is True
        assert 'text' not in result and 'evidence' not in result
        assert not controller._broker.current(env['gateway'].tokens[0])
        assert not env['infer_calls']
    finally:
        env['gateway'].release.set()
