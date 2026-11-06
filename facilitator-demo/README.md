# The routing prototype (for the facilitator)

This folder is for the facilitator of workshop 6, not for the pairs. It holds a **prototype**: the
facilitator's own sorter, put in front of a chatbot in the Open WebUI of the kit, and shown on the big
screen in Part 6. It is there to make the room think about well-being, private data and energy (see
"Why think about routing" in the [workshop page](../README.md#why-think-about-routing)). It is not a
tool for a real service.

> 🚫 **Warning.** **Never let young people type into it or use it as a real chatbot.** You may show
> it to them on your screen, as in Part 6, to make them think about routing, but leave out message 7
> and any message about wanting to die. The fixed answers were written for a
> demonstration: no child protection professional has checked them. The sorter makes mistakes, so it
> is not a safety net. A real service needs a separately tested emergency path, and a person who
> takes over.

## What is in it

- `demo.py`: the command of the demo (`start`, `status`, `stop`). It uses Python's standard library only.
- `sorter_router.py`: a filter for Open WebUI. It sorts each message with your trained sorter before
  the chatbot sees it.
- `sorter_answers.py`: the fixed answers (safety answer, kind answer, polite refusal, and "The message
  sorter is not working").

Keep the three files together, in this folder.

## Before the workshop

Do this in your own Codespace of workshop 6, the day before:

1. `./sorter setup`, then `./sorter train`.
2. `openwebui start` (your key; the first time, it downloads about 1.6 GB).
3. In a terminal: `cd facilitator-demo`, then `python3 demo.py start`.
   **What you should see:** `Head converted to numbers`, `Model copied into Open WebUI`, then a frame
   `PROTOTYPE - workshop 6` with nine messages, each with the class your sorter gives it.
4. `python3 demo.py stop`.
   **What you should see:** `Nothing of the demo is left in Open WebUI.`
5. Keep this Codespace until the workshop.

The steps for the day itself, and what to point at on the screen, are in the facilitator sheet of
workshop 6 ("During Part 6").

## What it does, and what it never does

While the demo runs, the sorter sits in front of **every** model of your Open WebUI, the hidden base
model included (the model of your key, which `openwebui start` hides from the list). The demo chatbot is
built on that base model. An emergency, a message that needs care and a message the sorter is sure is off-topic get a
fixed answer, and never reach the big model. The other messages go to the chatbot: a paid call with
your key. If the sorter fails, the answer is the fixed "The message sorter is not working…", never the
chatbot.

`demo.py` never reads your key and never sends a message to a model: only the messages you type in
Open WebUI leave, through Open WebUI. The sorter keeps no record of the messages. `stop` deletes the
conversations with the demo chatbot, the functions, the models and the copied files, then checks that
nothing is left.

> ⚠️ **Important.** **Keep port 3000 private.** The Open WebUI of the kit has no accounts: anyone who
> can open it is its administrator. Such a person could also reach the model through Open WebUI's
> direct provider route, which no filter sees. `start` checks the port once, with
> `openwebui check-private`.

> ℹ️ **Note.** **What was tested.** The demo works only with Open WebUI 0.12.4 and 0.12.5, the versions
> of the kit, and stops on any other. It was tried on 2026-11-04, 2026-11-05 (0.12.4) and 2026-11-06 (0.12.5),
> without network, with a fake model, a fake key, the real `openwebui start` of the kit and Chrome without
> a screen. In the last two runs: 49 messages sorted as `./sorter` sorts them, the messages with a fixed answer never sent to the
> model, nothing left after `stop`. Since image 2026.11.6, `openwebui start` makes no "Wildfire RAG" model in
> this repository (it has no documents), so the demo chatbot is built on the hidden base model: tried again
> that way on 2026-11-06 (0.12.5 only), same results. It was not tried in a real Codespace, with a real model,
> or with a group.

## Licence

The three programs: EUPL-1.2. This page: CC BY-SA 4.0. See `REUSE.toml` at the root of the repository.
