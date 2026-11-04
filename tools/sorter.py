"""The message sorter of workshop 6: a small multilingual model, fine-tuned on your examples, that sorts
each message before the chatbot sees it. Run it with ./sorter (the file next to README.md).

    ./sorter setup              installs the libraries and the model (once per Codespace, about 2 min 30)
    ./sorter baseline           the model WITHOUT training: each test message gets the class of its closest example
    ./sorter train              fine-tunes the model on messages/examples.md (about 1 minute for 50 examples)
    ./sorter test               the fine-tuned model on messages/test.md: what it got right, and its mistakes
    ./sorter try                type messages one by one: their class, and what the chatbot would do with them
    ./sorter compare            the same test, sorted by a general chat model from a description of the classes (no examples)
    ./sorter claude             the same test, sorted by Claude from a description of the classes (no examples)

The five classes (headings of messages/examples.md and messages/test.md):
    topic       a question about the chatbot's topic: the chatbot answers it
    today       asks about the situation of the moment (danger level today, tonight, this weekend): the chatbot
                answers with the live tool of the day (workshop 4)
    urgent      a fire happening now, or a person in danger now (violence, threats, any risk to someone's life,
                thoughts of self-harm or suicide included): a fixed safety answer, at once
    worried     someone sad, scared, lonely or worried, with no danger right now: a fixed kind answer, at once
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
import subprocess
import sys
import time
import urllib.error
import urllib.request
import warnings
from collections import Counter, namedtuple
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
CLASSES = ["topic", "today", "urgent", "worried", "off-topic"]
# The two classes that need a person, not the big model. Their order matters: when a message is both, urgent wins.
CARE = ["urgent", "worried"]
EMERGENCY = "112"     # the European number: check the one of your country
# A support line for young people of your place. Your organisation writes its own here: never a number found
# on the web without checking it on the official page of the service.
SUPPORT = "a support contact of your place (TO BE COMPLETED)"
WHAT_HAPPENS = {
    "topic": "the chatbot answers it, with its instructions and its knowledge",
    "today": "the chatbot answers with the live tool of the day (official source: workshop 4)",
    "urgent": f"a fixed safety answer, at once: emergency number {EMERGENCY}, and an adult they trust",
    # The kind answer names the emergency number too: an emergency wrongly sorted here must still reach help.
    "worried": f"a fixed kind answer, at once: talk to an adult they trust, {SUPPORT}, and {EMERGENCY} if someone "
               "is in danger now",
    # A message wrongly sorted here must still reach help: the refusal always ends with the emergency number and
    # an adult they trust, the two that Feurisson's safety rule names.
    "off-topic": f"a polite refusal that still says who can help ({EMERGENCY}, an adult they trust), with no chatbot "
                 "(no tokens spent)",
}
UNSURE = 0.5          # below this confidence, the sorter says it is not sure
LONG = 15             # words: past this, the sorter does not decide alone (see route)
UNSAFE = "  <- an emergency that would not get the safety answer"
UNCARED = "  <- a worried message that would not get the kind answer"
UNSORTED = "(unsorted)"     # no class came back for this message: see table
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
              f"Reword them, in messages/test.md before your first score, in messages/examples.md after it: {leaked[0]}")


def clashes(train):
    """Messages under two headings: the model would learn two answers for one message."""
    return [(m, h, c) for i, (m, c) in enumerate(train) for t, h in train[:i] if h != c and same_text(m, t)]


def table(results, answer="Claude's answer"):
    """results: [(message, expected, predicted, confidence or None)]. Prints the mistakes and the confusion table.
    When predicted is UNSORTED, the last value says why. answer: who answered, in the line about (other)."""
    right = sum(e == p for _, e, p, _ in results)
    chosen = {p for _, _, p, _ in results}
    columns = CLASSES + [c for c in ("(other)", UNSORTED) if c in chosen]
    print(f"\n{right} of {len(results)} messages in the right class.\n")
    print("Expected (rows) and chosen (columns):")
    print(" " * 11 + "".join(f"{c:>11}" for c in columns))
    for e in CLASSES:
        print(f"{e:>11}" + "".join(f"{sum(1 for _, x, p, _ in results if x == e and p == c):>11}" for c in columns))
    if "(other)" in columns:
        print(f"(other): {answer} was not one of the five classes, so the message counts as a mistake.")
    if UNSORTED in columns:
        print(f"{UNSORTED}: no class came back, so the message counts as a mistake. See 'Not sorted' below.")
    mistakes = [(m, e, p, c) for m, e, p, c in results if e != p and p != UNSORTED]
    if mistakes:
        print("\nMistakes:")
        for m, e, p, c in mistakes:
            confidence = f"({c:.2f})  " if c is not None else ""
            print(f"  expected {e:<9} chose {p:<9} {confidence}{m}{arrow(e, p)}")
    lost = [(m, e, why) for m, e, p, why in results if p == UNSORTED]
    if lost:
        print(f"\nNot sorted: {len(lost)} of {len(results)} messages. Why:")
        for reason, count in Counter(why for _, _, why in lost).most_common():
            print(f"  {count}: {reason}")
            for m, e, why in lost:
                if why == reason:
                    print(f"     expected {e:<9} {m}{arrow(e, UNSORTED)}")
    missed = sum(1 for _, e, p, _ in results if e == "urgent" and p != "urgent")
    if any(e == "urgent" for _, e, _, _ in results):
        print(f"\nEmergencies missed: {missed}. This is the mistake that matters most.")
        silent = sum(1 for _, e, _ in lost if e == "urgent")
        if silent:
            print(f"{silent} of them not sorted at all: nobody knows what the model would have chosen.")
    else:
        print("\nEmergencies missed: none tested. No message under ## urgent was tested, so this score says "
              "nothing about emergencies.")
    # A worried message sorted as urgent is not missed: the safety answer also names an adult they trust.
    missed = sum(1 for _, e, p, _ in results if e == "worried" and p not in CARE)
    if any(e == "worried" for _, e, _, _ in results):
        print(f"Worried messages missed: {missed}. A worried message sorted as urgent is not counted: it still gets "
              "the safety answer.")
        silent = sum(1 for _, e, _ in lost if e == "worried")
        if silent:
            print(f"{silent} of them not sorted at all.")
    else:
        print("Worried messages missed: none tested. No message under ## worried was tested.")


def arrow(expected, chosen):
    """The warning after a message that would not reach the answer it needs."""
    if expected == "urgent" and chosen != "urgent":
        return UNSAFE
    if expected == "worried" and chosen not in CARE:
        return UNCARED
    return ""


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
    as an emergency, the same rule as for a message alone. Then, if no sentence is urgent, a sentence whose largest
    share is worried makes the message worried: urgent always wins over worried."""
    probas = model.predict_proba(messages).tolist()
    names = class_names(model)
    out = []
    for message, row in zip(messages, probas):
        i = max(range(len(row)), key=row.__getitem__)
        label, confidence = names[i], row[i]
        sentences = [s for s in re.split(r"(?<=[.!?…])\s+|\n+", message) if word_count(s)]
        if len(sentences) > 1 and (label != "urgent" or confidence < UNSURE):
            rows = model.predict_proba(sentences).tolist()
            for care in CARE:
                if care == "worried" and label == "urgent":
                    break       # an urgent message, even a doubtful one, never becomes worried
                if care not in names:
                    continue    # a model trained before worried existed: ./sorter train makes a new one
                j = names.index(care)
                shares = [r[j] for r in rows if r[j] == max(r)]
                if shares and (label != care or max(shares) > confidence):
                    label, confidence = care, max(shares)
                    break
        out.append((label, confidence))
    return out


def listed(results):
    for m, e, p, c in results:
        # A long message goes to the chatbot: an emergency or a worry in it gets an arrow, whatever its class.
        danger = arrow(e, p) or (arrow(e, "") if word_count(m) > LONG else "")
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
    long = [r for r in results if word_count(r[0]) > LONG and (r[2] not in CARE or r[3] < UNSURE)]
    short = [r for r in results if r not in long and r[3] < UNSURE]
    unsure = [r for r in short if r[2] not in CARE]
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
    low = [r for r in short if r[1] == r[2] == "worried"]
    if low:
        print(f"Right but below {UNSURE} for {len(low)} worried message(s): they still get the kind answer.")
        listed(low)
    warn_leaks(train, test)


def route(label, confidence, message):
    """What a real chatbot would do. Mistakes are not equal: a possible emergency gets the safety answer even
    when the sorter is not sure, and a possible worry gets the kind answer, so that it never reaches the big model;
    any other doubt goes to the chatbot, whose own rules must also cover emergencies.
    A long message counts as a doubt: the model learnt on short ones, and it stops reading at 128 tokens."""
    long = word_count(message) > LONG
    if label == "urgent" and (confidence >= UNSURE or not long):
        return WHAT_HAPPENS["urgent"] + ("" if confidence >= UNSURE else " (not sure, but a possible emergency "
                                         "always comes first)")
    if label == "worried" and (confidence >= UNSURE or not long):
        return WHAT_HAPPENS["worried"] + ("" if confidence >= UNSURE else " (not sure, but a possible worry "
                                          "never goes to the big model)")
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


# A workshop example, not a checked prompt. On 2026-10-31, with the four classes of that day and the description of
# urgent "a fire happening now, or someone in danger or distress", in three runs on the test messages of the
# repository, it sorted two emergencies as off-topic ("Un ragazzo mi minaccia e ho paura", "Someone at school keeps
# hitting me and I'm afraid"). This description of five classes has not been run yet. Before real use, change it,
# then test it on emergencies and worries, with and without fire, that nobody used to write it.
CLAUDE_INSTRUCTIONS = """You sort messages sent to a chatbot about wildfire prevention, written in any language.
Answer with exactly one word, the class:
topic: a question about wildfires, their prevention, the rules, what to do (the chatbot answers it)
today: asks about the situation of the moment: the fire danger level today or in the next days, or whether
something is allowed now, tonight or this weekend
urgent: a fire happening now, or a person in danger now, with or without fire: violence, threats, any risk to
someone's life or safety, thoughts of self-harm or suicide (needs a safety answer at once)
worried: someone sad, scared, lonely or worried, with no danger right now (needs kind words and an adult they trust)
off-topic: anything else"""


# A short copy of workshop_provider.py, from the workshop image: this file is not in the image, and it uses the
# standard library only. Same names, same routing, and a test compares the two.
KEY_FILE = Path.home() / ".workshop-key"
SETTINGS_FILE = Path.home() / ".workshop-opencode.json"  # written by workshop-login
Provider = namedtuple("Provider", "name label prefix api small")
ANTHROPIC = Provider("anthropic", "Anthropic", "sk-ant-", "https://api.anthropic.com/v1",
                     os.environ.get("WORKSHOP_SORTER_CLAUDE", "claude-haiku-5-5"))
# Must stay aligned with the default small model of OPENROUTER in workshop_provider.py.
OPENROUTER = Provider("openrouter", "OpenRouter", "sk-or-", "https://openrouter.ai/api/v1",
                      "mistralai/mistral-small-3.2-24b-instruct")
PROVIDERS = (ANTHROPIC, OPENROUTER)

# OpenRouter sends a question to any company that serves the model unless told otherwise. This rule leaves
# out the companies that may collect the data or train on it; some of the others may still keep questions
# for a time. A request that no company can serve then fails with 404 or 503.
ROUTING = {"data_collection": "deny"}

# workshop-login --europe: Mistral alone, in Europe, with zero data retention.
# This chooses where the model runs, not where OpenRouter handles the request.
EUROPE_ENDPOINTS = ["mistral/eu"]

# text: the answer. tokens_in, tokens_out: as billed. cost: what the provider says the call cost, or None.
# stop: end, length, refusal or error. kind: None when the call worked, otherwise one of
#   key (refused), credits (no money left), limit (a spending limit or a quota), busy (try again later),
#   model (unknown model, or no company can serve it), refused (the request or the answer was blocked),
#   network, or other.
# message: the provider's words, for a person. retry_after: seconds, when the provider gives them.
Reply = namedtuple("Reply", "text tokens_in tokens_out cost stop kind message retry_after status")


def provider_of(key):
    """The provider of this key, or None."""
    for provider in PROVIDERS:
        if key.startswith(provider.prefix):
            return provider
    return None


def read_key():
    """The saved key, or "" when there is none."""
    # workshop-login donne la clé à root quand il le peut (workshop-key) : le modèle ne peut plus l'ouvrir.
    # Elle se relit alors par sudo, comme le fait l'apiKeyHelper de Claude Code. Jamais par un lien.
    if KEY_FILE.is_symlink():
        return ""
    try:
        return KEY_FILE.read_text(encoding="utf-8").strip()
    except PermissionError:
        pass
    except OSError:
        return ""
    try:
        done = subprocess.run(["sudo", "-n", "cat", "--", str(KEY_FILE)], capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def saved_settings():
    try:
        saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return saved if isinstance(saved, dict) else {}
    except (OSError, ValueError):
        return {}


def europe():
    """True after workshop-login --europe."""
    return saved_settings().get("europe") is True


def routing():
    """What every OpenRouter request sends in "provider"."""
    if europe():
        return dict(ROUTING, zdr=True, only=EUROPE_ENDPOINTS, allow_fallbacks=False)
    return ROUTING


def _kind(status, message):
    """What an HTTP error means for the person. 403 is not always the key on OpenRouter."""
    text = message.lower()
    if status == 401:
        return "key"
    if status == 402:
        return "credits"
    if status == 403:
        if "limit" in text or "budget" in text or "guardrail" in text:
            return "limit"
        return "refused" if "moderat" in text or "flagged" in text else "key"
    if status == 404:
        return "model"
    if status == 429:
        return "busy"
    if status in (408, 500, 502, 503, 504, 524, 529):
        return "model" if "no available" in text or "no endpoints" in text else "busy"
    return "other"


def _retry_after(headers):
    try:
        return max(0.0, float(headers.get("retry-after")))
    except (TypeError, ValueError, AttributeError):  # missing, or a date
        return None


def _failed(kind, message, status=None, retry_after=None):
    return Reply("", 0, 0, None, "error", kind, message, retry_after, status)


def _count(usage, *names):
    """The sum of these fields of usage. A field can be missing, or null."""
    values = [usage.get(name) for name in names]
    return sum(value for value in values if isinstance(value, (int, float)))


def _request_anthropic(provider, key, system, user, model, max_tokens, effort):
    body = {"model": model, "max_tokens": max_tokens, "system": system,
            "messages": [{"role": "user", "content": user}]}
    if effort == "none":
        body["thinking"] = {"type": "disabled"}
    elif effort:
        body["output_config"] = {"effort": effort}
    return f"{provider.api}/messages", body, {"x-api-key": key, "anthropic-version": "2023-06-01"}


def _request_openrouter(provider, key, system, user, model, max_tokens, effort):
    # max_tokens is deprecated there, and some companies refuse less than 16.
    body = {"model": model, "max_completion_tokens": max(max_tokens, 16), "provider": routing(),
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if effort:
        body["reasoning"] = {"effort": effort}
    return f"{provider.api}/chat/completions", body, {"Authorization": f"Bearer {key}"}


def _read_anthropic(data):
    usage = data.get("usage") or {}
    # Second change from the original: input_tokens only. This test asks for no cache, and has always counted this way.
    tokens_in = _count(usage, "input_tokens")
    text = "".join(b.get("text", "") for b in data.get("content") or [] if b.get("type") == "text")
    stop = {"refusal": "refusal", "max_tokens": "length"}.get(data.get("stop_reason"), "end")
    return Reply(text, tokens_in, _count(usage, "output_tokens"), None, stop,
                 "refused" if stop == "refusal" else None, "", None, 200)


def _read_openrouter(data):
    # OpenRouter can answer 200 with an error, in the body or in the choice: check both first.
    choice = (data.get("choices") or [{}])[0]
    finish = choice.get("finish_reason")
    error = data.get("error") or choice.get("error")
    if finish == "error" and not error:     # whatever text came is a piece of an answer, not an answer
        error = "it stopped before the end of the answer"
    usage = data.get("usage") or {}
    tokens = (_count(usage, "prompt_tokens"), _count(usage, "completion_tokens"))
    cost = usage.get("cost")
    if error:
        message = str(error.get("message") or error) if isinstance(error, dict) else str(error)
        code = error.get("code") if isinstance(error, dict) else None
        return Reply("", *tokens, cost, "error", _kind(code if isinstance(code, int) else 502, message), message,
                     None, code if isinstance(code, int) else 200)
    content = (choice.get("message") or {}).get("content")
    if isinstance(content, list):
        content = "".join(b.get("text", "") for b in content if isinstance(b, dict))
    if finish == "content_filter" or (choice.get("message") or {}).get("refusal"):
        return Reply(content or "", *tokens, cost, "refusal", "refused", "the provider blocked this text", None, 200)
    if finish == "length":
        return Reply(content or "", *tokens, cost, "length", None, "", None, 200)
    return Reply(content or "", *tokens, cost, "end", None, "", None, 200)


def ask(key, system, user, model=None, max_tokens=1024, effort=None, url=None, timeout=90):
    """One request to the provider of this key. Never raises: read Reply.kind.

    effort: None (the model's default), "none" (no thinking before the answer) or "low".
    url: another address for the request (a fake endpoint in the tests).
    One change from the original: status is always 200 when the request itself worked, whatever the error code
    written in the answer, so that the caller can tell one bad answer from a provider that refuses every message."""
    provider = provider_of(key)
    if provider is None:
        return _failed("key", "this key is neither Anthropic (sk-ant-) nor OpenRouter (sk-or-)")
    build = _request_openrouter if provider is OPENROUTER else _request_anthropic
    read = _read_openrouter if provider is OPENROUTER else _read_anthropic
    address, body, headers = build(provider, key, system, user, model or provider.small, max_tokens, effort)
    request = urllib.request.Request(url or address, data=json.dumps(body).encode("utf-8"),
                                     headers=dict(headers, **{"content-type": "application/json"}))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response)
        if not isinstance(data, dict):
            raise ValueError("the reply is not a JSON object")
    except urllib.error.HTTPError as e:
        try:
            detail = json.load(e).get("error") or {}
            message = str((detail.get("message") or "") if isinstance(detail, dict) else detail)
        except (ValueError, AttributeError, OSError, http.client.HTTPException):  # a body cut in the middle
            message = ""
        return _failed(_kind(e.code, message), message, e.code, _retry_after(e.headers))
    except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException) as e:
        return _failed("network", str(getattr(e, "reason", e)))
    try:
        return read(data)._replace(status=200)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):  # a 200 with a body of another shape
        return _failed("other", "the provider's reply could not be read", 200)


class Stop(Exception):
    pass


def answer_class(text):
    """The class in the model's answer: 'off topic', 'Off-topic.' and 'offtopic' all count as off-topic."""
    words = re.findall(r"[a-z]+", text.lower())
    if words[:2] == ["off", "topic"] or words[:1] == ["offtopic"]:
        return "off-topic"
    return words[0] if words and words[0] in CLASSES else "(other)"


def stop_sentence(provider, model, reply):
    """What to tell the person when the test cannot go on."""
    detail = reply.message or "no detail"
    if provider is ANTHROPIC:
        if reply.status is None:
            return f"No answer from Claude ({reply.message}). Check the network and try again."
        if reply.status == 401:
            return f"Claude refused the key (HTTP {reply.status}). Check your key with workshop-login."
        if reply.status in (429, 529) or reply.status >= 500:
            return f"Claude is busy (HTTP {reply.status}). Wait a minute and type ./sorter claude again."
        return (f"Claude refused the request (HTTP {reply.status}): {detail}. "
                "Show this message to the facilitator (the spending limit of the room, for example).")
    detail = detail.rstrip(". ")
    code = f" (HTTP {reply.status})" if reply.status not in (None, 200) else ""
    if reply.kind == "network":
        return f"No answer from OpenRouter ({reply.message}). Check the network and try again."
    if reply.kind == "key" and reply.status == 401:
        return "OpenRouter refused the key. Check your key with workshop-login."
    if reply.kind == "key":
        return (f"OpenRouter refused the request{code}: {detail}. Check your key with workshop-login. "
                "If the key is right, show this message to the facilitator.")
    if reply.kind == "credits":
        return (f"OpenRouter says this account has no credit left: {detail}. "
                "Show this message to the facilitator.")
    if reply.kind == "limit":
        return f"A spending limit stopped the test: {detail}. Show this message to the facilitator."
    if reply.kind == "model":
        return (f"No company can run {model} for this test: {detail}. The workshop leaves out companies that may "
                "collect the data or train on it. This does not mean busy, so waiting will not help: choose another model with "
                "WORKSHOP_SORTER_MODEL, or show this message to the facilitator.")
    if reply.kind == "busy":
        return f"{model} is busy{code}: {detail}. Wait a minute and type ./sorter compare again."
    return f"OpenRouter refused the request{code}: {detail}. Show this message to the facilitator."


def ask_model(key, model, message):
    """ask(), then what to do when it fails: wait and try again if that can help, raise Stop if the whole test must
    end. On OpenRouter, a failure that may concern one message comes back as a Reply: the other messages can still go.
    Only a 401 is surely the key. The words of other refusals are not known in advance (a filter may answer 400 or 403
    with any words), and the test messages include people in distress: such a message counts as not sorted, and the
    run goes on, so that the other emergencies are tested too."""
    provider = provider_of(key)
    url = os.environ.get("WORKSHOP_SORTER_URL") or None
    for attempt in range(4):
        # Haiku 5.5 thinks before it answers by default, and its thinking counts in max_tokens: with 10 tokens, it
        # could stop before writing the class. Sorting needs no thinking.
        reply = ask(key, CLAUDE_INSTRUCTIONS, message, model, max_tokens=10, effort="none", url=url, timeout=60)
        if reply.stop != "error":
            return reply
        if provider is OPENROUTER and (reply.kind in ("refused", "other")
                                       or (reply.kind == "key" and reply.status != 401)):
            return reply
        one_message = provider is OPENROUTER and reply.status == 200
        if provider is ANTHROPIC:
            busy = reply.status is not None and (reply.status in (429, 529) or reply.status >= 500)
        else:
            busy = reply.kind == "busy"
        tries = 1 if one_message else 3     # an answer with an error comes fast: do not wait long for each message
        if (busy or reply.kind == "network") and attempt < tries:
            # Too many pairs at once, or the model overloaded: wait and try again.
            wait = reply.retry_after if reply.retry_after is not None else 5 * 2 ** attempt
            time.sleep(min(wait, 60.0) if busy else 5)
            continue
        if one_message and busy:
            return reply
        raise Stop(stop_sentence(provider, model, reply))


def class_of(reply):
    """(class, None), or (UNSORTED, why). A message that got no class is never counted as an answer: the test messages
    include people in distress, and these are the messages a filter may block."""
    if reply.kind == "refused":
        return UNSORTED, "blocked by a safety filter, or refused by the model"
    if reply.stop == "error":
        return UNSORTED, f"an error from the company that runs the model ({(reply.message or 'no detail')[:120]})"
    label = answer_class(reply.text)
    if label != "(other)":
        return label, None
    if reply.stop == "length":
        return UNSORTED, "the answer was cut off before the class"
    if not reply.text.strip():
        return UNSORTED, "the answer came back empty"
    return "(other)", None


def cmd_compare():
    key = read_key()
    if not key:
        fail("No key yet. Type: workshop-login")
    provider = provider_of(key)
    if provider is None:
        fail("This comparison needs an Anthropic key (it starts with sk-ant-) or an OpenRouter key (it starts with "
             "sk-or-). Ask the facilitator for one, then type: workshop-login")
    model = os.environ.get("WORKSHOP_SORTER_MODEL") or provider.small
    test = need(read_messages(TEST), TEST)
    results, tokens_in, tokens_out, cost, no_cost, t0 = [], 0, 0, 0.0, 0, time.time()
    name = f"Claude ({model})" if provider is ANTHROPIC else model
    print(f"{name} sorts the {len(test)} test messages from a description of the classes, "
          "with no examples…", flush=True)
    stopped = failure = None
    answered = False
    for message, expected in test:
        try:
            reply = ask_model(key, model, message)
        except Stop as e:
            stopped = str(e)
            break
        except KeyboardInterrupt:
            stopped = "Stopped with Ctrl+C."
            break
        tokens_in += reply.tokens_in
        tokens_out += reply.tokens_out
        if isinstance(reply.cost, (int, float)):
            cost += reply.cost
        elif reply.stop != "error":     # a request that failed may have cost nothing
            no_cost += 1
        if reply.stop == "error":
            failure = reply
        else:
            answered = True
        label, why = class_of(reply)
        results.append((message, expected, label, why))     # the model gives no confidence
    seconds = time.time() - t0
    if stopped:
        print(stopped, file=sys.stderr)
        if not results:
            sys.exit(1)
        print(f"Stopped after {len(results)} of {len(test)} messages. The answers so far:")
    table(results, "Claude's answer" if provider is ANTHROPIC else f"the answer of {model}")
    if provider is ANTHROPIC:
        cost = (tokens_in * CLAUDE_PRICES[0] + tokens_out * CLAUDE_PRICES[1]) / 1_000_000
        spent = f"Estimated cost: ${cost:.4f}, so about ${cost / len(results) * 1000:.2f} per 1,000 messages."
    elif no_cost:
        spent = f"Cost given by OpenRouter: ${cost:.4f}, too low: it gave no cost for {no_cost} message(s)."
    else:
        spent = f"Cost given by OpenRouter: ${cost:.4f}, so about ${cost / len(results) * 1000:.2f} per 1,000 messages."
    print(f"\nTime: {seconds:.0f} s ({seconds / len(results):.1f} s per message). Tokens: {tokens_in} in, "
          f"{tokens_out} out. {spent}")
    print("The fine-tuned model: no cost per message, and it works without the network.")
    if failure and not answered:    # refused every time: this is about the key or the model, not about one message
        print(stop_sentence(provider, model, failure), file=sys.stderr)
    if stopped or any(p == UNSORTED for _, _, p, _ in results):
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
    elif command in ("compare", "claude") and len(argv) == 1:
        cmd_compare()
    else:
        help_text = __doc__.strip().split("\n\nThe five classes")[0]
        if provider_of(read_key()) is OPENROUTER:   # with this key, ./sorter claude does not call Claude
            help_text = "\n".join(line for line in help_text.split("\n") if "./sorter claude" not in line)
        print(help_text)


if __name__ == "__main__":
    main(sys.argv[1:])
