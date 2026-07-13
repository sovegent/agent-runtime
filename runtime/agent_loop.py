"""
Agent Loop — the heart of Agent Runtime.

Implements the ReAct pattern:
  Input → Reason → Act → Observe → Repeat

This is your control plane. Every step is logged, stored in memory,
and traceable. Not LLM vibes — deterministic, observable execution.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from runtime.agent import BaseAgent
from runtime.executor import Executor
from runtime.llm.base import BaseLLM
from runtime.memory.memory_store import MemoryStore
from runtime.logger import get_logger


@dataclass
class LoopResult:
    """Final result of an agent loop execution."""
    session_id: str
    task: str
    success: bool
    output: str
    steps_taken: int
    stop_reason: str                        # "complete" | "max_steps" | "error" | "agent_stop"
    memory_summary: Dict = field(default_factory=dict)
    error: Optional[str] = None


class AgentLoop:
    """
    Executes an agent over a task until completion or max_steps.

    The loop manages:
      - Conversation history (messages list sent to LLM each turn)
      - Tool call → result → observation cycle
      - Memory persistence (every step saved)
      - Structured logging for full traceability
      - Clean stop conditions

    Usage:
        loop = AgentLoop(llm, executor, memory, config)
        result = loop.run(agent, task="Summarize the last 3 nginx logs")
    """

    def __init__(
        self,
        llm: BaseLLM,
        executor: Executor,
        memory: MemoryStore,
        max_steps: int = 20,
        log_level: str = "INFO",
    ):
        self.llm = llm
        self.executor = executor
        self.memory = memory
        self.max_steps = max_steps
        self.logger = get_logger("agent_loop", log_level)

    def run(self, agent: BaseAgent, task: str) -> LoopResult:
        """
        Run an agent on a task. Returns a LoopResult when done.

        Args:
            agent: The agent definition (system prompt, stop conditions, hooks)
            task:  The task description / user input
        """
        session_id = self.memory.session_id
        self.logger.banner(f"{agent.name}  |  session {session_id}")
        self.logger.info("task_received", task=task[:200])

        # Initial state passed through agent hooks
        state: Dict[str, Any] = {
            "session_id": session_id,
            "task": task,
            "step": 0,
        }
        state = agent.on_start(task, state)

        # Save task to memory
        self.memory.save({
            "type": "task",
            "role": "user",
            "content": task,
        })

        # Conversation history maintained in-loop
        # Anthropic API format: [{role, content}]
        messages: List[Dict] = [{"role": "user", "content": task}]

        # Tool definitions exposed to the LLM
        tool_definitions = self.executor.get_tool_definitions()
        system_prompt = agent.get_system_prompt()

        # ─── Main execution loop ──────────────────────────────────────────────
        for step in range(1, self.max_steps + 1):
            state["step"] = step
            self.logger.step(step, "reasoning")

            # ── Reason: ask LLM what to do next ───────────────────────────────
            try:
                response = self.llm.complete(
                    messages=messages,
                    system=system_prompt,
                    tools=tool_definitions,
                )
            except Exception as e:
                self.logger.error("llm_error", error=str(e))
                return LoopResult(
                    session_id=session_id,
                    task=task,
                    success=False,
                    output="",
                    steps_taken=step,
                    stop_reason="error",
                    error=f"LLM error: {e}",
                    memory_summary=self.memory.summary(),
                )

            # ── Check for natural completion (no tool calls, just a response) ─
            if not response.has_tool_calls:
                final_output = response.content.strip()
                self.logger.step(step, "complete", output=final_output[:150])
                self.memory.save({
                    "type": "final_output",
                    "role": "assistant",
                    "content": final_output,
                    "step": step,
                })
                agent.on_complete(final_output, state)
                return LoopResult(
                    session_id=session_id,
                    task=task,
                    success=True,
                    output=final_output,
                    steps_taken=step,
                    stop_reason="complete",
                    memory_summary=self.memory.summary(),
                )

            # ── Act: execute each tool call the LLM requested ─────────────────
            # Append the assistant's tool-use message to history
            messages.append({
                "role": "assistant",
                "content": self._build_assistant_content(response),
            })

            # Collect all tool results for this step
            tool_results_content = []

            for tool_call in response.tool_calls:
                self.logger.step(
                    step, "action",
                    tool=tool_call.tool_name,
                    input=str(tool_call.tool_input)[:200],
                )

                # ── Observe: execute the tool, get the result ─────────────────
                result = self.executor.execute(tool_call.tool_name, tool_call.tool_input)

                result_text = json.dumps(result.to_dict(), default=str)

                self.logger.step(
                    step, "observe",
                    tool=tool_call.tool_name,
                    success=result.success,
                    output=result_text[:200],
                )

                # Save step to memory
                self.memory.save({
                    "type": "step",
                    "step": step,
                    "tool": tool_call.tool_name,
                    "input": tool_call.tool_input,
                    "result": result.to_dict(),
                })

                # Build tool result for next LLM message
                tool_results_content.append({
                    "type": "tool_result",
                    "tool_use_id": tool_call.tool_use_id,
                    "content": result_text,
                })

                # Agent step hook
                state = agent.on_step_complete(
                    step, {"tool": tool_call.tool_name, "input": tool_call.tool_input},
                    result, state
                )

                # Agent custom stop condition
                if agent.should_stop(step, result, state):
                    self.logger.info("agent_stop", step=step)
                    agent.on_complete("", state)
                    return LoopResult(
                        session_id=session_id,
                        task=task,
                        success=True,
                        output=f"Agent stopped at step {step}",
                        steps_taken=step,
                        stop_reason="agent_stop",
                        memory_summary=self.memory.summary(),
                    )

            # Append tool results as user message for next round
            messages.append({
                "role": "user",
                "content": tool_results_content,
            })

        # ─── Max steps reached ────────────────────────────────────────────────
        self.logger.warning("max_steps_reached", max=self.max_steps)
        agent.on_complete("", state)
        return LoopResult(
            session_id=session_id,
            task=task,
            success=False,
            output=f"Reached max steps ({self.max_steps}) without completing task.",
            steps_taken=self.max_steps,
            stop_reason="max_steps",
            memory_summary=self.memory.summary(),
        )

    def _build_assistant_content(self, response) -> List[Dict]:
        """Build the assistant content block for the messages history."""
        content = []
        if response.content:
            content.append({"type": "text", "text": response.content})
        for tc in response.tool_calls:
            content.append({
                "type": "tool_use",
                "id": tc.tool_use_id,
                "name": tc.tool_name,
                "input": tc.tool_input,
            })
        return content
