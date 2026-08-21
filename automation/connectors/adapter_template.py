"""Generic connector adapter template.

Adapters must declare capabilities and authorization state before use.
"""

class ConnectorAdapter:
    name = "UNIMPLEMENTED"

    def health_check(self):
        return {"connector": self.name, "status": "UNKNOWN"}

    def capabilities(self):
        return []

    def execute(self, request):
        raise NotImplementedError("Connector authorization required")
