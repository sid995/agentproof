"""Minimal AgentProof SDK example.

Run with:
    AGENTPROOF_API_KEY=ap_live_... uv run python examples/sample_agent.py
"""

from agentproof import AgentProofClient

client = AgentProofClient(endpoint="http://127.0.0.1:8000")

with client.trace("sample-support-agent") as trace:
    trace.set_input({"question": "Where is my order?"})
    with trace.span("lookup-order", span_type="tool") as span:
        span.set_output({"status": "in_transit"})

client.shutdown()
