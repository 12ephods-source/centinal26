from scripts.run_host_chaos_qualification import SCENARIOS, run


def test_host_chaos_campaign_passes_every_registered_scenario() -> None:
    report = run()
    assert report["status"] == "PASS"
    assert report["scope"] == "HOST_ONLY"
    assert report["physical_promotion_allowed"] is False
    assert len(report["scenarios"]) == len(SCENARIOS)
    assert {item["scenario"] for item in report["scenarios"]} == {
        name for name, _scenario in SCENARIOS
    }
    assert all(item["status"] == "PASS" for item in report["scenarios"])
    assert len(report["report_sha256"]) == 64


def test_host_chaos_report_is_deterministic() -> None:
    assert run() == run()
