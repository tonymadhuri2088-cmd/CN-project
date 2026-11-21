"""Scripted stand-in for the Anthropic client (shape: client.messages.create(**kw))."""
from __future__ import annotations

import copy
from types import SimpleNamespace as NS


def text(t):
    return NS(type="text", text=t)


def tool_use(id_, tool_name, /, **inp):
    return NS(type="tool_use", id=id_, name=tool_name, input=inp)


def final(id_, verdict, fault_type, evidence=()):
    return tool_use(id_, "final_answer", verdict=verdict, fault_type=fault_type, evidence=list(evidence))


class FakeClient:
    def __init__(self, script, usage=(100, 50)):
        self.script = list(script)
        self.usage = usage
        self.calls = []
        self.messages = NS(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        assert self.script, "FakeClient script exhausted: the agent loop did not terminate"
        blocks = self.script.pop(0)
        usage = None if self.usage is None else NS(input_tokens=self.usage[0], output_tokens=self.usage[1])
        stop = "tool_use" if any(b.type == "tool_use" for b in blocks) else "end_turn"
        return NS(content=blocks, stop_reason=stop, usage=usage)
