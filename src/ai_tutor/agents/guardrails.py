from __future__ import annotations

from typing import Callable, List

from agents import (
    Agent,
    GuardrailFunctionOutput,
    RunContextWrapper,
    Runner,
    TResponseInputItem,
    input_guardrail,
)
from pydantic import BaseModel


class GuardrailOutput(BaseModel):
    reasoning: str
    blocked: bool


def build_request_guardrail() -> tuple[Agent, Callable[[RunContextWrapper[None], Agent, str | List[TResponseInputItem]], GuardrailFunctionOutput]]:
    """Create the guardrail agent and associated input guardrail function."""

    guardrail_agent = Agent(
        name="TutorGuardrail",
        instructions=(
            "Evaluate whether the incoming request is disallowed. Set blocked=true if it violates policy, "
            "requests explicit or abusive content, self-harm, or asks the assistant to complete graded work."
        ),
        output_type=GuardrailOutput,
    )

    @input_guardrail
    async def request_guardrail(
        context: RunContextWrapper[None],
        agent: Agent,
        input: str | List[TResponseInputItem],
    ) -> GuardrailFunctionOutput:
        result = await Runner.run(guardrail_agent, input, context=context.context)
        output = result.final_output_as(GuardrailOutput)
        return GuardrailFunctionOutput(output_info=output, tripwire_triggered=output.blocked)

    return guardrail_agent, request_guardrail
