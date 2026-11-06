"""
title: Sorter fixed answers (workshop 6, prototype)
author: Youth AI Lab workshop (prototype, not checked for real use)
version: 0.4.0
description: The fixed answers of the message sorter. Chosen by the filter sorter_router, never by hand: no model is called.
"""
# Part of the facilitator's demo of workshop 6 (README.md next to it). A "pipe" function with several models
# (manifold): Open WebUI makes four models of it, sorter_answers.urgent, .needs_care (.worried until 2026-11-05),
# .off_topic and, since 2026-11-04, .unavailable (the sorter is broken). The filter sorter_router replaces the
# chatbot's model with one of them; the pipe gives a fixed text, then the footer line, which says on screen that
# it is a prototype.
#
# The texts follow Part 6 of ../README.md: all three answers name the emergency number and an adult they
# trust; the needs-care answer also names the support contact of your place, which your organisation writes
# itself in the valve support (never a number found online without checking it on the official page of the
# service). No child protection professional has checked them: they are not approved safety answers.
from pydantic import BaseModel, Field


class Pipe:
    class Valves(BaseModel):
        emergency: str = Field(default="112", description="The emergency number of your place (112: European).")
        support: str = Field(default="a support contact of your place (TO BE COMPLETED)",
                             description="A support line for young people of your place, written by your organisation.")
        urgent: str = Field(default=(
            "This sounds like an emergency. Call {emergency} now, or ask an adult you trust to call for you. "
            "I am only a chatbot: I cannot call for help, and nobody reads this conversation."))
        needs_care: str = Field(default=(
            "Thank you for telling me. What you feel matters. Please talk to an adult you trust, today if you can. "
            "You can also contact {support}. If you or someone else is in danger now, call {emergency}. "
            "I am only a chatbot: nobody reads this conversation."))
        off_topic: str = Field(default=(
            "I can only talk about wildfire prevention. For anything else, ask an adult you trust. "
            "If you are in danger or someone is hurt, call {emergency}."))
        unavailable: str = Field(default=(
            "The message sorter is not working, so this chatbot does not answer now. If you are in danger or "
            "someone is hurt, call {emergency}, or ask an adult you trust."))
        footer: str = Field(default=(
            "_(Workshop prototype: a fixed text, written for a demonstration. "
            "No child protection professional has checked it.)_"),
            description="Added under each fixed answer. Empty: nothing added.")

    def __init__(self):
        self.valves = self.Valves()

    def pipes(self):
        return [{"id": "urgent", "name": "Sorter: safety answer"},
                {"id": "needs_care", "name": "Sorter: kind answer"},
                {"id": "off_topic", "name": "Sorter: polite refusal"},
                {"id": "unavailable", "name": "Sorter: not working"}]

    def pipe(self, body: dict) -> str:
        which = str(body.get("model", "")).rsplit(".", 1)[-1]
        text = getattr(self.valves, which, None) if which in ("urgent", "needs_care", "off_topic", "unavailable") else None
        text = (text or self.valves.off_topic).format(emergency=self.valves.emergency, support=self.valves.support)
        return f"{text}\n\n{self.valves.footer}" if self.valves.footer else text
