import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SUPERVISOR = ROOT / "scripts/ftoe_secure_supervisor.py"
BROKER = ROOT / "scripts/ftoe_provider_broker.py"
INSTALLER = ROOT / "termux/install_ftoe_research_daemon.sh"


class SplitAuthorityTests(unittest.TestCase):
    def test_supervisor_has_no_http_client_import(self):
        tree = ast.parse(SUPERVISOR.read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertFalse(any(name.startswith(("urllib", "requests", "httpx", "aiohttp")) for name in imported))

    def test_broker_has_no_subprocess_import(self):
        tree = ast.parse(BROKER.read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertNotIn("subprocess", imported)

    def test_supervisor_does_not_read_secrets_file(self):
        text = SUPERVISOR.read_text()
        self.assertNotIn("SECRETS.read_text", text)
        self.assertNotIn("load_secrets", text)

    def test_installer_never_sources_provider_secrets(self):
        text = INSTALLER.read_text()
        self.assertNotIn('source "$SECRETS_FILE"', text)
        self.assertNotIn('source "$ENV_FILE"', text)
        self.assertIn("ftoe_secure_supervisor.py", text)

    def test_broker_forbids_shell_expansion_syntax(self):
        text = BROKER.read_text()
        self.assertIn("shell expansion syntax is forbidden", text)

    def test_sister_agents_are_blind_until_arbitration(self):
        text = SUPERVISOR.read_text()
        self.assertIn("You cannot see other sister-agent verdicts", text)
        self.assertNotIn('json.dumps({"panel"', text)


if __name__ == "__main__":
    unittest.main()
