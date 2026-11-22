"""Bounded LangGraph orchestration for AI-02 read-only tools."""

from __future__ import annotations

from json import JSONDecodeError, loads
from typing import Literal, Protocol, TypedDict

from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, ConfigDict

from app.agents.tools import ReadOnlyToolSet, create_read_only_langchain_tools

MAX_TOOL_ROUNDS = 5
LOOKUP_LIMIT_MESSAGE = (
    "I reached the information lookup limit. Please narrow the request or try again."
)


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Literal[
        "search_products",
        "get_product_details",
        "check_availability",
        "find_alternatives",
        "get_company_info",
    ]
    arguments: dict[str, object]


class ModelStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    tool_call: ToolCall | None = None


class AgentModel(Protocol):
    async def next_step(self, *, messages: list[dict[str, object]]) -> ModelStep: ...


class AgentState(TypedDict):
    messages: list[dict[str, object]]
    rounds: int
    final_text: str


class ReadOnlyAgent:
    def __init__(self, model: AgentModel, tools: ReadOnlyToolSet) -> None:
        self._model = model
        self._tools = tools
        self._langchain_tool_node = ToolNode(
            create_read_only_langchain_tools(tools),
            handle_tool_errors="The requested information is unavailable.",
        )
        graph = StateGraph(AgentState)
        graph.add_node("model", self._model_node)
        graph.add_node("tools", self._tool_node)
        graph.add_edge(START, "model")
        graph.add_conditional_edges("model", self._route, {"tools": "tools", "end": END})
        graph.add_conditional_edges("tools", self._after_tool, {"model": "model", "end": END})
        self._graph = graph.compile()

    async def invoke(self, user_text: str) -> str:
        result = await self._graph.ainvoke(
            {"messages": [{"role": "user", "content": user_text}], "rounds": 0, "final_text": ""}
        )
        return result["final_text"]

    async def _model_node(self, state: AgentState) -> dict[str, object]:
        try:
            step = await self._model.next_step(messages=state["messages"])
        except Exception:
            return {"final_text": "The AI provider is unavailable. Please try again."}
        if step.tool_call is None:
            return {"final_text": step.text}
        return {
            "messages": [
                *state["messages"],
                {"role": "assistant", "tool_call": step.tool_call.model_dump()},
            ]
        }

    def _route(self, state: AgentState) -> Literal["tools", "end"]:
        if state["final_text"]:
            return "end"
        if state["rounds"] >= MAX_TOOL_ROUNDS:
            return "end"
        return "tools" if state["messages"][-1].get("tool_call") else "end"

    @staticmethod
    def _after_tool(state: AgentState) -> Literal["model", "end"]:
        """Stop immediately after the fifth execution instead of asking the model again."""
        return "end" if state["rounds"] >= MAX_TOOL_ROUNDS else "model"

    async def _tool_node(self, state: AgentState) -> dict[str, object]:
        tool_name = "unknown"
        try:
            call = ToolCall.model_validate(state["messages"][-1]["tool_call"])
            tool_name = call.name
            response = await self._langchain_tool_node.ainvoke(
                {
                    "messages": [
                        AIMessage(
                            content="",
                            tool_calls=[
                                {"name": call.name, "args": call.arguments, "id": "read-only-call"}
                            ],
                        )
                    ]
                }
            )
            content = response["messages"][-1].content
            result = loads(content) if isinstance(content, str) else content
            if not isinstance(result, dict):
                result = {"error": "The requested information is unavailable."}
        except JSONDecodeError, TypeError, ValueError:
            result = {"error": "The requested information is unavailable."}
        return {
            "messages": [
                *state["messages"],
                {"role": "tool", "name": tool_name, "content": result},
            ],
            "rounds": state["rounds"] + 1,
            "final_text": LOOKUP_LIMIT_MESSAGE if state["rounds"] + 1 >= MAX_TOOL_ROUNDS else "",
        }
