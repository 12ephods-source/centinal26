"""Frost Device Capability Classifier v1

Classifies discovered application metadata into possible capabilities.
This module does not grant permissions or activate applications.
It produces suggestions requiring verification.
"""

KEYWORDS = {
    "coding": ["ide", "code", "editor", "github", "terminal", "python"],
    "ai_agent": ["ai", "assistant", "agent", "chat", "llm"],
    "automation": ["automation", "task", "workflow", "macro", "bot"],
    "research": ["paper", "science", "calculator", "notebook"],
    "communication": ["mail", "chat", "message", "discord"]
}


def classify(app_name: str):
    text = app_name.lower()
    matches = []
    for capability, words in KEYWORDS.items():
        if any(word in text for word in words):
            matches.append(capability)
    return {
        "application": app_name,
        "suggested_capabilities": matches,
        "verification_status": "pending"
    }


if __name__ == "__main__":
    print(classify("Example AI Coding Agent"))
