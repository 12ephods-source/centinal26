from pathlib import Path

"""Hermes Frost Orchestrator — C05-backed execution integration."""

from . import tools

CALL_SCHEMA = {
    "name": "frost_c05_call",
    "description": (
        "Request an allowlisted automatic C05 capability. Model-callable execution "
        "is restricted to C05 A0/read-only capabilities; other capabilities require "
        "direct user CLI authorization outside model context."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "capability": {"type": "string"},
            "arguments": {"type": "object"},
            "provider": {
                "type": "string",
                "enum": ["local", "github"],
                "description": (
                    "local executes through C05; github stages an immutable local "
                    "frost-call request only and performs no GitHub write"
                ),
            },
        },
        "required": ["capability"],
    },
}

STATUS_SCHEMA = {
    "name": "frost_c05_status",
    "description": "Return Hermes/C05 bridge status, capabilities, and audit health.",
    "parameters": {"type": "object", "properties": {}},
}

STAGE_SCHEMA = {
    "name": "frost_stage_script",
    "description": (
        "Compatibility migration tool. Hash and preserve proposed code as an inert "
        "artifact; it does NOT execute or authorize the script."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "script": {"type": "string"},
            "filename": {"type": "string"},
        },
        "required": ["script"],
    },
}


def register(ctx):
    ctx.register_tool(
        name="frost_c05_call",
        toolset="frost_orchestrator",
        schema=CALL_SCHEMA,
        handler=tools.c05_call,
        description=CALL_SCHEMA["description"],
    )
    ctx.register_tool(
        name="frost_c05_status",
        toolset="frost_orchestrator",
        schema=STATUS_SCHEMA,
        handler=tools.c05_status,
        description=STATUS_SCHEMA["description"],
    )
    ctx.register_tool(
        name="frost_stage_script",
        toolset="frost_orchestrator",
        schema=STAGE_SCHEMA,
        handler=tools.stage_script_inert,
        description=STAGE_SCHEMA["description"],
    )

    ctx.register_command(
        "frost-status",
        tools.status_command,
        description="Show C05 execution bridge status",
    )
    ctx.register_command(
        "frost-call",
        tools.call_command,
        description="Call an automatic C05 capability: /frost-call CAPABILITY {JSON}",
    )
    ctx.register_command(
        "frost-approve",
        tools.approve_migration_command,
        description="Explain the retired direct-script approval path",
    )
    ctx.register_command(
        "frost-relay",
        lambda raw: tools.relay_command(ctx, raw),
        description="Run archived adversarial review using Hermes host-owned LLM",
    )
    ctx.register_command(
        "frost-protocol",
        tools.protocol_command,
        description="Show Frost/Hermes/C05 operating protocol",
    )
    skill = Path(__file__).parent / "skills" / "frost-c05-execution" / "SKILL.md"
    if skill.exists():
        ctx.register_skill("frost-c05-execution", skill)
