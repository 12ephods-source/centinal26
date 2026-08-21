"""Frost Automation OS task router.

Selects candidate handlers. Does not bypass permissions.
"""


def route(task, agents):
    matches = []
    for agent in agents:
        if any(cap in task.get("required_capabilities", []) for cap in agent.get("capabilities", [])):
            matches.append(agent)
    return matches
