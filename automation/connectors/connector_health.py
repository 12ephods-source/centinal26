"""Connector health tracking scaffold."""


def check_connector(connector):
    result = connector.health_check()
    return {
        "connector": getattr(connector, "name", "unknown"),
        "health": result,
    }
