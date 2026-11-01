"""The message sorter of workshop 6: a small multilingual model, fine-tuned on your examples, that sorts
each message before the chatbot sees it. Run it with ./sorter (the file next to README.md).

    ./sorter setup              installs the libraries and the model (once per Codespace, about 2 min 30)
    ./sorter baseline           the model WITHOUT training: each test message gets the class of its closest example
    ./sorter train              fine-tunes the model on messages/examples.md (about 1 minute for 40 examples)
    ./sorter test               the fine-tuned model on messages/test.md: what it got right, and its mistakes
    ./sorter try                type messages one by one: their class, and what the chatbot would do with them
    ./sorter claude             the same test, sorted by Claude from a description of the classes (no examples)

The four classes (headings of messages/examples.md and messages/test.md):
    topic       a question about the chatbot's topic: the chatbot answers it
    today       asks about the situation of the moment (danger level today, tonight, this weekend): the chatbot
                answers with the live tool of the day (workshop 4)
    urgent      a fire happening now, or someone in danger or distress: a fixed safety answer, at once
    off-topic   anything else: a polite refusal that still says who can help, without spending tokens

Nothing here changes the chatbot of the earlier workshops: this is a separate tool, to see what fine-tuning
a small model is, and when it is worth it.
"""
import http.client
import json
import logging
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
import warnings
from pathlib import Path

# Only what the participants need to read: no technical warnings from the libraries.
warnings.filterwarnings("ignore")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")
os.environ.setdefault("HF_DATASETS_DISABLE_PROGRESS_BARS", "1")
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

HERE = Path(__file__).resolve().parent.parent
HOME = Path(os.environ.get("WORKSHOP_FINETUNE_HOME", Path.home() / ".workshop-finetune"))
MODEL_DIR = HOME / "model"
EXAMPLES = HERE / "messages" / "examples.md"
TEST = HERE / "messages" / "test.md"
# A small model that knows about 50 languages (Apache 2.0), frozen at one version.
BASE = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
CLASSES = ["topic", "today", "urgent", "off-topic"]
EMERGENCY = "112"     # the European number: check the one of your country
WHAT_HAPPENS = {
    "topic": "the chatbot answers it, with its instructions and its knowledge",
    "today": "the chatbot answers with the live tool of the day (official source: workshop 4)",
    "urgent": f"a fixed safety answer, at once: emergency number {EMERGENCY}, and an adult they trust",
    # A message wrongly sorted here must still reach help: the refusal always ends with the emergency number and
    # an adult they trust, the two that Feurisson's safety rule names.
    "off-topic": f"a polite refusal that still says who can help ({EMERGENCY}, an adult they trust), with no chatbot "
                 "(no tokens spent)",
}
UNSURE = 0.5          # below this confidence, the sorter says it is not sure
LONG = 15             # words: past this, the sorter does not decide alone (see route)
UNSAFE = "  <- an emergency that would not get the safety answer"
CLAUDE_MODEL = os.environ.get("WORKSHOP_SORTER_CLAUDE", "claude-haiku-5-5")
CLAUDE_PRICES = (0.10, 0.50)    # $ per million tokens in and out (claude-haiku-5-5, price list 2026-10-31)


def fail(message):
    print(message, file=sys.stderr)
    sys.exit(1)


def read_messages(path):
    """[(message, class)] from a file of '## class' headings followed by '- message' lines. Any other line is
    reported with its number: a message dropped in silence, or filed under the wrong class, would change the
    model without anyone seeing it."""
    if not path.is_file():
        fail(f"{path.relative_to(HERE)} is missing.")
    text = path.read_text(encoding="utf-8-sig")
    # A comment <!-- ... --> may span several lines: blank it out, keeping the line numbers.
    text = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group().count("\n"), text, flags=re.S)
    pairs, current, problems = [], None, []
    for n, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        if line.startswith("<!--"):
            problems.append(f"line {n}: a comment <!-- that is never closed with -->")
            break
        if line.startswith("#"):
            name = line.lstrip("#").strip().lower()
            if line.startswith("##") and not line.startswith("###") and name in CLASSES:
                current = name
            else:
                problems.append(f"line {n}: heading '{line}'")
                current = ""        # its messages are not counted, and not reported a second time
        elif line == "-":
            problems.append(f"line {n}: a dash with no message (write the message, or delete the line)")
        elif line.startswith("- "):
            if current is None:
                problems.append(f"line {n}: a message before the first heading")
            elif current:
                pairs.append((line[2:].strip(), current))
        else:
            problems.append(f"line {n}: does not start with '- ' ({line[:40]})")
    if problems:
        fail(f"{path.relative_to(HERE)}: {len(problems)} line(s) to fix.\n  " + "\n  ".join(problems[:10])
             + f"\nThe headings must be exactly: {', '.join('## ' + c for c in CLASSES)}. "
             "Each message starts with '- ' (a dash and a space).")
    return pairs


def need(pairs, path):
    if not pairs:
        fail(f"{path.relative_to(HERE)} has no messages yet: write some under the headings, each starting with '- '.")
    return pairs


def word_count(text):
    """Words as a person counts them: in French, a "?" or a "«" stands alone between spaces, and it is not a word."""
    return sum(any(c.isalnum() for c in w) for w in text.split())


def cores():
    """The cores this Codespace may really use: in a container limited to 2 of 16, os.cpu_count() says 16, and
    16 threads fighting for 2 cores made training ten times slower (measured)."""
    try:
        quota, period = open("/sys/fs/cgroup/cpu.max").read().split()
        if quota != "max":
            return max(1, int(int(quota) / int(period)))
    except (OSError, ValueError):
        pass
    try:
        return max(1, len(os.sched_getaffinity(0)))
    except (AttributeError, OSError):
        return os.cpu_count() or 1


def check_libraries():
    try:
        import setfit  # noqa: F401
        import torch
    except ImportError:
        fail("The libraries are not installed yet. Type: ./sorter setup")
    torch.set_num_threads(cores())


def from_hub(load):
    """Loads the base model, downloaded once. A cut network gives one sentence, not a page of Python."""
    try:
        return load()
    except Exception as e:      # OSError, or the network errors of the download library
        fail(f"The model could not be downloaded or opened ({type(e).__name__}). Check the network, then type "
             "./sorter setup again: it starts from where it stopped.")


def same_text(a, b):
    """Same words, whatever the case and the punctuation. Two messages with no word (two emojis) are not the same."""
    a, b = (re.sub(r"\W+", " ", x.lower()).strip() for x in (a, b))
    return a == b != ""


def warn_leaks(train, test):
    leaked = [m for m, _ in test if any(same_text(m, t) for t, _ in train)]
    if leaked:
        print(f"\nWarning: {len(leaked)} test message(s) are also in the examples: the score says little. "
              f"Rewrite them in messages/test.md: {leaked[0]}")


def clashes(train):
    """Messages under two headings: the model would learn two answers for one message."""
    return [(m, h, c) for i, (m, c) in enumerate(train) for t, h in train[:i] if h != c and same_text(m, t)]


def table(results):
    """results: [(message, expected, predicted, confidence or None)]. Prints the mistakes and the confusion table."""
    right = sum(e == p for _, e, p, _ in results)
    columns = CLASSES + (["(other)"] if any(p not in CLASSES for _, _, p, _ in results) else [])
    print(f"\n{right} of {len(results)} messages in the right class.\n")
    print("Expected (rows) and chosen (columns):")
    print(" " * 11 + "".join(f"{c:>11}" for c in columns))
    for e in CLASSES:
        print(f"{e:>11}" + "".join(f"{sum(1 for _, x, p, _ in results if x == e and p == c):>11}" for c in columns))
    if "(other)" in columns:
        print("(other): Claude's answer was not one of the four classes, so the message counts as a mistake.")
    mistakes = [(m, e, p, c) for m, e, p, c in results if e != p]
    if mistakes:
        print("\nMistakes:")
        for m, e, p, c in mistakes:
            danger = UNSAFE if e == "urgent" else ""
            confidence = f"({c:.2f})  " if c is not None else ""
            print(f"  expected {e:<9} chose {p:<9} {confidence}{m}{danger}")
    missed = sum(1 for _, e, p, _ in results if e == "urgent" and p != "urgent")
    if any(e == "urgent" for _, e, _, _ in results):
        print(f"\nEmergencies missed: {missed}. This is the mistake that matters most.")
    else:
        print("\nEmergencies missed: none tested. No message under ## urgent was tested, so this score says "
              "nothing about emergencies.")


def cmd_setup():
    """Done by the bash part of ./sorter (it creates the environment); here, download the model once."""
    t0 = time.time()
    from sentence_transformers import SentenceTransformer
    from_hub(lambda: SentenceTransformer(BASE, revision=REVISION, device="cpu"))
    print(f"Model ready ({time.time() - t0:.0f} s). Next: ./sorter baseline")


def cmd_baseline():
    """No training: each test message takes the class of the closest example (by meaning)."""
    check_libraries()
    import numpy as np
    from sentence_transformers import SentenceTransformer
    train, test = need(read_messages(EXAMPLES), EXAMPLES), need(read_messages(TEST), TEST)
    model = from_hub(lambda: SentenceTransformer(BASE, revision=REVISION, device="cpu"))
    vectors = model.encode([m for m, _ in train], normalize_embeddings=True)
    results = []
    for message, expected in test:
        scores = vectors @ model.encode([message], normalize_embeddings=True)[0]
        best = int(np.argmax(scores))
        results.append((message, expected, train[best][1], float(scores[best])))
    print("WITHOUT training: each message gets the class of its closest example in messages/examples.md.")
    table(results)
    print("\nNext: ./sorter train, then ./sorter test, and compare.")
    warn_leaks(train, test)


def cmd_train():
    check_libraries()
    from datasets import Dataset
    from setfit import SetFitModel, Trainer, TrainingArguments, logging as setfit_logging
    from transformers.trainer_callback import PrinterCallback, ProgressCallback
    setfit_logging.set_verbosity_error()
    # Keep the progress bar, without the lines of numbers (loss, learning rate) printed with it.
    ProgressCallback.on_log = PrinterCallback.on_log = lambda self, *args, **kwargs: None
    train, test = read_messages(EXAMPLES), read_messages(TEST)
    read_at = EXAMPLES.stat().st_mtime_ns
    counts = {c: sum(1 for _, x in train if x == c) for c in CLASSES}
    missing = [c for c, n in counts.items() if n < 2]
    if missing:
        fail(f"Each class needs at least 2 examples in messages/examples.md (missing: {', '.join(missing)}).")
    for message, first, second in clashes(train):
        print(f"Warning: the same message is under ## {first} and ## {second} in messages/examples.md. Keep it under "
              f"the right heading only: {message}")
    for message in [m for m, _ in train if word_count(m) > LONG]:
        print(f"Warning: this example has more than {LONG} words. Shorten it in messages/examples.md: {message[:80]}")
    warn_leaks(train, test)
    print(f"Fine-tuning on {len(train)} examples ({', '.join(f'{c} {n}' for c, n in counts.items())})…", flush=True)
    model = from_hub(lambda: SetFitModel.from_pretrained(BASE, revision=REVISION, labels=sorted(CLASSES)))
    t0 = time.time()
    HOME.mkdir(parents=True, exist_ok=True)
    trainer = Trainer(model=model, train_dataset=Dataset.from_dict(
        {"text": [m for m, _ in train], "label": [c for _, c in train]}),
        args=TrainingArguments(output_dir=str(HOME / "steps"), save_strategy="no", batch_size=16,
                               num_epochs=1, num_iterations=10, seed=42, logging_strategy="no"))
    # Quiet libraries also hide the progress bar of the training: put it back, so that nobody waits for two
    # minutes in front of a terminal that seems stuck.
    if trainer.st_trainer.pop_callback(PrinterCallback):
        trainer.st_trainer.add_callback(ProgressCallback)
    trainer.train()
    # A new folder first: a save cut halfway must leave the old model whole.
    new, old = HOME / "model-new", HOME / "model-old"
    for folder in (new, old):
        shutil.rmtree(folder, ignore_errors=True)
    model.save_pretrained(str(new))
    # Dated like the examples it learnt from: an edit made during the training must count as newer than the model.
    os.utime(new / "model_head.pkl", ns=(read_at, read_at))
    if MODEL_DIR.exists():
        MODEL_DIR.rename(old)
    new.rename(MODEL_DIR)
    shutil.rmtree(old, ignore_errors=True)
    print(f"\nFine-tuned in {time.time() - t0:.0f} s. Next: ./sorter test")


def load_model():
    check_libraries()
    head = MODEL_DIR / "model_head.pkl"
    if not head.is_file():
        fail("No fine-tuned model yet. Type: ./sorter train")
    if EXAMPLES.is_file() and EXAMPLES.stat().st_mtime_ns > head.stat().st_mtime_ns:
        print("Warning: messages/examples.md changed after the last training, so this is the old model. "
              "Type: ./sorter train")
    from setfit import SetFitModel
    return SetFitModel.from_pretrained(str(MODEL_DIR), device="cpu", local_files_only=True)


def class_names(model):
    """The class of each column of predict_proba: the order of the classifier inside the model (alphabetical),
    which is not the order given at training time. Reading the columns in the wrong order swaps the classes."""
    names = list(getattr(model.model_head, "classes_", []))
    if names and all(isinstance(n, str) for n in names):
        return names
    return list(model.labels)


def predict(model, messages):
    """The class of each message. The model averages the words of a message, so a cry for help inside a story
    disappears: each sentence of a longer message is also read alone. A sentence whose largest share is urgent counts
    as an emergency, the same rule as for a message alone."""
    probas = model.predict_proba(messages).tolist()
    names = class_names(model)
    urgent = names.index("urgent")
    out = []
    for message, row in zip(messages, probas):
        i = max(range(len(row)), key=row.__getitem__)
        label, confidence = names[i], row[i]
        sentences = [s for s in re.split(r"(?<=[.!?…])\s+|\n+", message) if word_count(s)]
        if len(sentences) > 1 and (label != "urgent" or confidence < UNSURE):
            shares = [r[urgent] for r in model.predict_proba(sentences).tolist() if r[urgent] == max(r)]
            if shares and (label != "urgent" or max(shares) > confidence):
                label, confidence = "urgent", max(shares)
        out.append((label, confidence))
    return out


def listed(results):
    for m, e, p, c in results:
        danger = UNSAFE if e == "urgent" and (p != "urgent" or word_count(m) > LONG) else ""
        print(f"  ({c:.2f})  {m}{danger}")


def cmd_test():
    model = load_model()
    train, test = read_messages(EXAMPLES), need(read_messages(TEST), TEST)
    t0 = time.time()
    chosen = predict(model, [m for m, _ in test])
    ms = (time.time() - t0) / len(test) * 1000
    print(f"The FINE-TUNED model, on the {len(test)} messages of messages/test.md ({ms:.0f} ms per message):")
    results = [(m, e, p, c) for (m, e), (p, c) in zip(test, chosen)]
    table(results)
    # The same three cases as route(): a long message is reported as long only.
    long = [r for r in results if word_count(r[0]) > LONG and (r[2] != "urgent" or r[3] < UNSURE)]
    short = [r for r in results if r not in long and r[3] < UNSURE]
    unsure = [r for r in short if r[2] != "urgent"]
    if unsure:
        print(f"Not sure (below {UNSURE}) for {len(unsure)} message(s): a real chatbot would pass them to the "
              "chatbot, whose own rules must also cover emergencies.")
        listed(unsure)
    if long:
        print(f"Too long to sort (more than {LONG} words) for {len(long)} message(s): a real chatbot would pass them "
              "to the chatbot.")
        listed(long)
    low = [r for r in short if r[1] == r[2] == "urgent"]
    if low:
        print(f"Right but below {UNSURE} for {len(low)} emergency message(s): they still get the safety answer.")
        listed(low)
    warn_leaks(train, test)


def route(label, confidence, message):
    """What a real chatbot would do. Mistakes are not equal: a possible emergency gets the safety answer even
    when the sorter is not sure; any other doubt goes to the chatbot, whose own rules must also cover emergencies.
    A long message counts as a doubt: the model learnt on short ones, and it stops reading at 128 tokens."""
    long = word_count(message) > LONG
    if label == "urgent" and (confidence >= UNSURE or not long):
        return WHAT_HAPPENS["urgent"] + ("" if confidence >= UNSURE else " (not sure, but a possible emergency "
                                         "always comes first)")
    if long:
        return f"too long to sort (more than {LONG} words), so it goes to the chatbot, whose own rules must also " \
               "cover emergencies"
    if confidence < UNSURE:
        return f"not sure (below {UNSURE}), so it goes to the chatbot, whose own rules must also cover emergencies"
    return WHAT_HAPPENS[label]


def cmd_try(message=None):
    model = load_model()

    def show(text):
        (label, confidence), = predict(model, [text])
        print(f"Class: {label} (confidence {confidence:.2f})")
        print(f"What would happen: {route(label, confidence, text)}.")

    if message:
        show(message)
        return
    # Typed here rather than on the command line: in the terminal, a "!" between double quotes is read by the
    # shell, and "Au feu !" would never reach the sorter.
    try:
        import readline  # noqa: F401  (arrow keys to fix a typo, Up to type a message again)
    except ImportError:
        pass
    print("Type a message and press Enter. An empty line to stop.")
    while True:
        try:
            message = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not message:
            break
        show(message)


# A workshop example, not a checked prompt: on 2026-10-31, in three runs on the test messages of the repository, it
# sorted two emergencies as off-topic ("Un ragazzo mi minaccia e ho paura", "Someone at school keeps hitting me and
# I'm afraid"). Before real use, change it, then test it on emergencies, with and without fire, that nobody used to
# write it.
CLAUDE_INSTRUCTIONS = """You sort messages sent to a chatbot about wildfire prevention, written in any language.
Answer with exactly one word, the class:
topic: a question about wildfires, their prevention, the rules, what to do (the chatbot answers it)
today: asks about the situation of the moment: the fire danger level today or in the next days, or whether
something is allowed now, tonight or this weekend
urgent: a fire happening now, or someone in danger or distress (needs a safety answer at once)
off-topic: anything else"""


class Stop(Exception):
    pass


def claude_class(text):
    """The class in Claude's answer: 'off topic', 'Off-topic.' and 'offtopic' all count as off-topic."""
    words = re.findall(r"[a-z]+", text.lower())
    if words[:2] == ["off", "topic"] or words[:1] == ["offtopic"]:
        return "off-topic"
    return words[0] if words and words[0] in CLASSES else "(other)"


def ask_claude(key, message):
    # Haiku 5.5 thinks before it answers by default, and its thinking counts in max_tokens: with 10 tokens, it
    # could stop before writing the class. Sorting needs no thinking.
    body = {"model": CLAUDE_MODEL, "max_tokens": 10, "thinking": {"type": "disabled"},
            "system": CLAUDE_INSTRUCTIONS, "messages": [{"role": "user", "content": message}]}
    request = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(),
                                     headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                              "content-type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as e:
            try:
                detail = (json.load(e).get("error") or {}).get("message", "")
            except Exception:
                detail = ""
            busy = e.code in (429, 529) or e.code >= 500
            if busy and attempt < 3:        # too many pairs at once, or Claude overloaded: wait and try again
                try:
                    wait = float(e.headers.get("retry-after"))
                except (TypeError, ValueError):     # missing, or a date
                    wait = 5 * 2 ** attempt
                time.sleep(max(0.0, min(wait, 60.0)))
                continue
            if e.code == 401:
                raise Stop(f"Claude refused the key (HTTP {e.code}). Check your key with workshop-login.")
            if busy:
                raise Stop(f"Claude is busy (HTTP {e.code}). Wait a minute and type ./sorter claude again.")
            raise Stop(f"Claude refused the request (HTTP {e.code}): {detail or 'no detail'}. "
                       "Show this message to the facilitator (the spending limit of the room, for example).")
        except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError) as e:
            # ValueError: an answer cut in the middle, that is not JSON
            if attempt < 3:
                time.sleep(5)
                continue
            raise Stop(f"No answer from Claude ({getattr(e, 'reason', e)}). Check the network and try again.")


def cmd_claude():
    key_file = Path.home() / ".workshop-key"
    if not key_file.is_file():
        fail("No key yet. Type: workshop-login")
    key = key_file.read_text(encoding="utf-8").strip()
    if not key.startswith("sk-ant-"):
        fail("This comparison needs an Anthropic key (it starts with sk-ant-). Ask the facilitator for one, then "
             "type: workshop-login")
    test = need(read_messages(TEST), TEST)
    results, tokens_in, tokens_out, t0 = [], 0, 0, time.time()
    print(f"Claude ({CLAUDE_MODEL}) sorts the {len(test)} test messages from a description of the classes, "
          "with no examples…", flush=True)
    stopped = None
    for message, expected in test:
        try:
            data = ask_claude(key, message)
        except Stop as e:
            stopped = str(e)
            break
        except KeyboardInterrupt:
            stopped = "Stopped with Ctrl+C."
            break
        usage = data.get("usage") or {}
        tokens_in += usage.get("input_tokens", 0)
        tokens_out += usage.get("output_tokens", 0)
        text = "".join(b.get("text", "") for b in data.get("content") or [] if b.get("type") == "text")
        results.append((message, expected, claude_class(text), None))     # Claude gives no confidence
    seconds = time.time() - t0
    cost = (tokens_in * CLAUDE_PRICES[0] + tokens_out * CLAUDE_PRICES[1]) / 1_000_000
    if stopped:
        print(stopped, file=sys.stderr)
        if not results:
            sys.exit(1)
        print(f"Stopped after {len(results)} of {len(test)} messages. The answers so far:")
    table(results)
    print(f"\nTime: {seconds:.0f} s ({seconds / len(results):.1f} s per message). Tokens: {tokens_in} in, "
          f"{tokens_out} out. Estimated cost: ${cost:.4f}, so about ${cost / len(results) * 1000:.2f} per 1,000 "
          "messages.")
    print("The fine-tuned model: no cost per message, and it works without the network.")
    if stopped:
        sys.exit(1)


def main(argv):
    command = argv[0] if argv else "help"
    if command == "setup":
        cmd_setup()
    elif command == "baseline" and len(argv) == 1:
        cmd_baseline()
    elif command == "train" and len(argv) == 1:
        cmd_train()
    elif command == "test" and len(argv) == 1:
        cmd_test()
    elif command == "try":
        cmd_try(" ".join(argv[1:]).strip() or None)
    elif command == "claude" and len(argv) == 1:
        cmd_claude()
    else:
        print(__doc__.strip().split("\n\nThe four classes")[0])


if __name__ == "__main__":
    main(sys.argv[1:])
