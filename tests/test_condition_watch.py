from concurrent.futures import ThreadPoolExecutor
from frost_core.condition_watch import ConditionWatchLedger


TERMINAL = {"PASS", "FAIL", "CANCELLED"}


def test_pending_then_terminal_notifies_once(tmp_path):
    ledger = ConditionWatchLedger(tmp_path / "watch.sqlite3")
    first = ledger.observe("repo:pr:sha", "PENDING", terminal_states=TERMINAL, observed_at=1)
    terminal = ledger.observe("repo:pr:sha", "PASS", terminal_states=TERMINAL, observed_at=2)
    repeat = ledger.observe("repo:pr:sha", "PASS", terminal_states=TERMINAL, observed_at=3)

    assert not first.notify
    assert terminal.notify
    assert terminal.first_terminal_state == "PASS"
    assert not repeat.notify
    assert repeat.observation_count == 3


def test_new_immutable_target_gets_independent_notification(tmp_path):
    ledger = ConditionWatchLedger(tmp_path / "watch.sqlite3")
    old = ledger.observe("repo:5:sha-old", "PASS", terminal_states=TERMINAL)
    new = ledger.observe("repo:5:sha-new", "PASS", terminal_states=TERMINAL)
    assert old.notify and new.notify


def test_post_terminal_regression_does_not_renotify(tmp_path):
    ledger = ConditionWatchLedger(tmp_path / "watch.sqlite3")
    assert ledger.observe("target", "PASS", terminal_states=TERMINAL).notify
    assert not ledger.observe("target", "PENDING", terminal_states=TERMINAL).notify
    failed = ledger.observe("target", "FAIL", terminal_states=TERMINAL)
    assert not failed.notify
    assert failed.first_terminal_state == "PASS"


def test_concurrent_terminal_observations_emit_exactly_once(tmp_path):
    ledger = ConditionWatchLedger(tmp_path / "watch.sqlite3")

    def observe_once(_):
        return ledger.observe("same-target", "PASS", terminal_states=TERMINAL).notify

    with ThreadPoolExecutor(max_workers=8) as pool:
        decisions = list(pool.map(observe_once, range(32)))

    assert sum(decisions) == 1
    assert ledger.get("same-target")["observation_count"] == 32
    assert sum(int(row["notify"]) for row in ledger.history("same-target")) == 1


def test_invalid_inputs_fail_closed(tmp_path):
    ledger = ConditionWatchLedger(tmp_path / "watch.sqlite3")

    invalid_calls = (
        lambda: ledger.observe("", "PASS", terminal_states=TERMINAL),
        lambda: ledger.observe("target", "", terminal_states=TERMINAL),
        lambda: ledger.observe("target", "PASS", terminal_states=()),
    )
    for call in invalid_calls:
        try:
            call()
        except ValueError:
            continue
        raise AssertionError("invalid condition-watch input did not fail closed")
