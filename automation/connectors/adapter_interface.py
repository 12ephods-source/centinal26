"""Standard connector adapter interface for Automation OS.

Adapters define how authorized external tools expose capabilities.
"""

class ConnectorAdapter:
    name = "unknown"

    def health_check(self):
        return {"status": "UNKNOWN", "verified": False}

    def describe_capabilities(self):
        return []

    def execute(self, task):
        raise NotImplementedError("Connector execution requires an authorized implementation")
