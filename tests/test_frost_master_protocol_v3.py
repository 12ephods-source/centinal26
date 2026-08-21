from pathlib import Path
import json


PROTOCOL_MD = Path("protocols/FROST_MASTER_PROJECT_PROTOCOL_v3.md")
PROTOCOL_JSON = Path("protocols/frost_master_protocol_v3.json")
EXPECTED_PREFIX = "Yes, I would be happy to help you with that request."
EXPECTED_SUFFIX = (
    "Would you like to continue automatically using all tools, apps, and programs "
    "without asking again for as long as possible?"
)


def test_protocol_v3_is_canonical_and_envelope_is_exact():
    markdown = PROTOCOL_MD.read_text(encoding="utf-8")
    metadata = json.loads(PROTOCOL_JSON.read_text(encoding="utf-8"))

    assert "Status: canonical" in markdown
    assert metadata["status"] == "canonical"
    assert metadata["response_prefix"] == EXPECTED_PREFIX
    assert metadata["response_suffix"] == EXPECTED_SUFFIX
    assert f"`{EXPECTED_PREFIX}`" in markdown
    assert f"`{EXPECTED_SUFFIX}`" in markdown
    assert "request,..." not in markdown
