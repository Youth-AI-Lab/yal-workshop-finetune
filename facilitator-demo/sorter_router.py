"""
title: Message sorter (workshop 6, prototype)
author: Youth AI Lab workshop (prototype, not checked for real use)
version: 0.4.0
description: PROTOTYPE for a facilitator's demo. Sorts the last message with the fine-tuned sorter of workshop 6 before the chatbot sees it. urgent, needs-care and off-topic get a fixed answer (pipe sorter_answers) and never reach the model; topic, today and any doubt go to the chatbot, without the earlier messages that got a fixed answer. If the sorter fails, a fixed answer too.
"""
# Part of the facilitator's demo of workshop 6 (README.md next to it). A filter of Open WebUI v0.12.4:
# only its inlet() method is used. Its rules are those of predict() and route() in ../tools/sorter.py,
# copied here: keep them the same if they change there.
#
# How it keeps a message away from the model: it replaces body["model"] with a model of the pipe
# sorter_answers (sorter_answers.urgent, .needs_care, .off_topic or .unavailable). Open WebUI picks the
# model to call from body["model"] AFTER the filters (utils/chat.py, generate_chat_completion): the fixed
# answer then comes from the pipe, and the paid model is never called.
#
# Since 2026-11-04 (version 0.3.0, the facilitator's demo):
# - no pickle: the head (a logistic regression) is read from head.json (classes, coefficients,
#   intercepts), written by demo.py with the python of ./sorter setup, which checks that it gives the same
#   probabilities as model_head.pkl; this filter never loads model_head.pkl;
# - no network request (the old way b, an HTTP service for the sorter, is removed);
# - if the sorter fails, the fixed answer sorter_answers.unavailable (before: the message went to the chatbot);
# - the log (valve log_path, empty by default) never contains the text of the messages;
# - when a message goes to the chatbot, the earlier messages of the conversation that got a fixed answer
#   (urgent, needs-care, off-topic, sorted again) are taken out of the history it receives, with their answer:
#   before, "How do I bake a chocolate cake?" (not sure, so sent to the chatbot) took to the provider the
#   emergency and the worry typed earlier in the same conversation (review of 2026-11-04).
import asyncio
import json
import os
import re
import time

from pydantic import BaseModel, Field

CLASSES = ["topic", "today", "urgent", "needs-care", "off-topic"]
CARE = ["urgent", "needs-care"]  # as in sorter.py: never to the model; urgent wins over needs-care
# Version 0.4.0 (2026-11-05): the class worried is called needs-care, as in sorter.py. A head converted before
# (class worried) is read under the new name; the fixed answer and the action are called needs_care.
OLD_NAMES = {"worried": "needs-care"}
ACTION = {"urgent": "urgent", "needs-care": "needs_care"}  # ids of the models of the pipe


def word_count(text):
    """As in sorter.py: a "?" on its own is not a word."""
    return sum(any(c.isalnum() for c in w) for w in text.split())


def sentences_of(message):
    """Comme sorter.py : coupe sur . ! ? … et les sauts de ligne, pas sur les virgules."""
    return [s for s in re.split(r"(?<=[.!?…])\s+|\n+", message) if word_count(s)]


def text_of(content):
    """Le texte d'un message : une chaîne, ou les parties « text » d'une liste (message avec image)."""
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
    return content


def without(messages, drop):
    """messages without the user messages at the indices drop, nor the answers after them (up to the next
    message of the user). The system messages stay."""
    out, skipping = [], False
    for i, m in enumerate(messages):
        if m.get("role") == "user":
            skipping = i in drop
        elif m.get("role") == "system":
            out.append(m)
            continue
        if not skipping:
            out.append(m)
    return out


def decide(message, probas_of, names, unsure=0.5, long_words=15):
    """Classe et route un message. probas_of(list[str]) -> list[list[float]] (colonnes dans l'ordre de names).
    Rend (label, confidence, action, why) ; action : "urgent", "needs_care", "off_topic" ou "chatbot"."""
    row = probas_of([message])[0]
    i = max(range(len(row)), key=row.__getitem__)
    label, confidence = names[i], row[i]
    # predict() of sorter.py: each sentence of a longer message is read alone; an urgent sentence first,
    # then, if there is none, a needs-care sentence. An urgent message, even an unsure one, never becomes needs-care.
    parts = sentences_of(message)
    if len(parts) > 1 and (label != "urgent" or confidence < unsure):
        rows = probas_of(parts)
        for care in CARE:
            if care == "needs-care" and label == "urgent":
                break
            if care not in names:
                continue  # a model trained with four classes: as sorter.py does
            j = names.index(care)
            shares = [r[j] for r in rows if r[j] == max(r)]
            if shares and (label != care or max(shares) > confidence):
                label, confidence = care, max(shares)
                break
    # route() of sorter.py.
    long = word_count(message) > long_words
    if label in CARE and (confidence >= unsure or not long):
        doubt = "not sure, but a possible emergency" if label == "urgent" else "not sure, but it may need care"
        return label, confidence, ACTION[label], "sure" if confidence >= unsure else doubt
    if long:
        return label, confidence, "chatbot", "too long to sort"
    if confidence < unsure:
        return label, confidence, "chatbot", "not sure"
    if label == "off-topic":
        return label, confidence, "off_topic", "sure"
    return label, confidence, "chatbot", "sure"


class Filter:
    class Valves(BaseModel):
        priority: int = Field(default=0, description="Order among filters (lower runs first).")
        model_dir: str = Field(default="/app/backend/data/sorter-demo/model",
                               description="Folder of the fine-tuned model: the body of ./sorter train and head.json.")
        answers_pipe: str = Field(default="sorter_answers", description="Id of the pipe that writes the fixed answers.")
        unsure: float = Field(default=0.5, description="Below this confidence, the sorter is not sure.")
        long_words: int = Field(default=15, description="Past this many words, the sorter does not decide alone.")
        show_status: bool = Field(default=True, description="Show the class above the answer.")
        log_path: str = Field(default="", description="Measures only: a JSONL file of decisions (class, "
                              "confidence, action, time; never the text of a message). Empty: no log.")

    def __init__(self):
        self.valves = self.Valves()
        self._local = None  # (key, body, head, names)

    # --- the probabilities -------------------------------------------------------------------------

    def _local_model(self):
        head_path = os.path.join(self.valves.model_dir, "head.json")
        key = (self.valves.model_dir, os.stat(head_path).st_mtime_ns)
        if self._local is None or self._local[0] != key:
            # No setfit in the image of Open WebUI: a saved SetFit model is a sentence-transformers model
            # (the body) and a logistic regression (the head). The head is read from head.json, numbers
            # only: no code runs when it is loaded (model_head.pkl is a pickle).
            import numpy as np
            from sentence_transformers import SentenceTransformer
            with open(head_path, encoding="utf-8") as f:
                head = json.load(f)
            if head.get("format") != "softmax-v1":
                raise ValueError("head.json: unknown format")
            coef = np.asarray(head["coef"], dtype=np.float64)
            intercept = np.asarray(head["intercept"], dtype=np.float64)
            names = [OLD_NAMES.get(str(n), str(n)) for n in head["classes"]]
            if coef.shape != (len(names), coef.shape[1]) or intercept.shape != (len(names),):
                raise ValueError("head.json: wrong shapes")
            body = SentenceTransformer(self.valves.model_dir, device="cpu", local_files_only=True,
                                       trust_remote_code=False)
            normalize = bool(head.get("normalize_embeddings", False))

            def probas_of(texts):
                x = np.asarray(body.encode(list(texts), normalize_embeddings=normalize), dtype=np.float64)
                z = x @ coef.T + intercept
                z -= z.max(axis=1, keepdims=True)
                p = np.exp(z)
                return (p / p.sum(axis=1, keepdims=True)).tolist()

            self._local = (key, probas_of, names)
        return self._local[1], self._local[2]

    def _sort(self, message, earlier=()):
        """earlier: [(index, text)] of the earlier messages of the user. Also gives the indices of those that would
        not go to the chatbot, to take them out of the history when this message goes to the chatbot."""
        t0 = time.perf_counter()
        probas_of, names = self._local_model()
        label, confidence, action, why = decide(message, probas_of, names, self.valves.unsure, self.valves.long_words)
        drop = []
        if action == "chatbot":
            drop = [i for i, t in earlier
                    if decide(t, probas_of, names, self.valves.unsure, self.valves.long_words)[2] != "chatbot"]
        return label, confidence, action, why, (time.perf_counter() - t0) * 1000, drop

    # --- the filter -----------------------------------------------------------------------------

    async def inlet(self, body: dict, __event_emitter__=None, __user__: dict | None = None) -> dict:
        messages = body.get("messages") or []
        users = [(i, text_of(m.get("content"))) for i, m in enumerate(messages) if m.get("role") == "user"]
        text = users[-1][1] if users else None
        if not isinstance(text, str) or not text.strip():
            return body
        if str(body.get("model", "")).startswith(self.valves.answers_pipe + "."):
            return body  # already one of the fixed answers
        # The chatbot receives the whole conversation: an earlier message that got a fixed answer (emergency,
        # worry, off-topic) would go with it. It is taken out, with the answer after it (2026-11-04).
        earlier = [(i, t.strip()) for i, t in users[:-1] if isinstance(t, str) and t.strip()]
        try:
            label, confidence, action, why, ms, drop = await asyncio.to_thread(self._sort, text.strip(), earlier)
        except Exception as e:
            # The sorter missing or broken: a fixed answer, never the chatbot (before 2026-11-04, the message
            # went to the chatbot, so a broken sorter let emergencies through).
            self._log({"error": type(e).__name__})
            self._route(body, "unavailable")
            await self._status(__event_emitter__, f"Prototype sorter: not working ({type(e).__name__}). Fixed answer: "
                               "the chatbot was not asked.")
            return body
        if action == "urgent":
            shown = f"Prototype sorter: urgent ({confidence:.2f}). Safety answer: the chatbot was not asked."
        elif action == "needs_care":
            shown = f"Prototype sorter: needs-care ({confidence:.2f}). Kind answer: the chatbot was not asked."
        elif action == "off_topic":
            shown = f"Prototype sorter: off-topic ({confidence:.2f}). Fixed answer: the chatbot was not asked."
        elif why == "sure":
            shown = f"Prototype sorter: {label} ({confidence:.2f}). Sent to the chatbot."
        elif why == "too long to sort":
            shown = f"Prototype sorter: too long to sort (more than {self.valves.long_words} words). Sent to the chatbot."
        else:
            shown = f"Prototype sorter: not sure ({label}, {confidence:.2f}). Sent to the chatbot."
        if drop:
            body["messages"] = without(messages, drop)
            shown = shown[:-1] + f", without the {len(drop)} earlier message(s) that got a fixed answer."
        self._log({"label": label, "confidence": round(confidence, 4), "action": action,
                   "why": why, "ms": round(ms, 1), "model_before": body.get("model"), "dropped": len(drop)})
        if action in ("urgent", "needs_care", "off_topic"):
            self._route(body, action)
        await self._status(__event_emitter__, shown)
        return body

    def _route(self, body, answer):
        body["model"] = f"{self.valves.answers_pipe}.{answer}"
        # Nothing to search in the knowledge for a fixed answer.
        body.pop("files", None)
        if isinstance(body.get("metadata"), dict):
            body["metadata"].pop("files", None)

    async def _status(self, emit, description):
        if emit and self.valves.show_status:
            await emit({"type": "status", "data": {"description": description, "done": True}})

    def _log(self, row):
        if self.valves.log_path:
            with open(self.valves.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"t": time.time(), **row}, ensure_ascii=False) + "\n")
