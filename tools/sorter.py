"""The message sorter of workshop 6: a small multilingual model, fine-tuned on your examples, that sorts
each message before the chatbot sees it. Run it with ./sorter (the file next to README.md).

    ./sorter setup              installs the libraries and the model (once per Codespace, about 2 minutes)
    ./sorter baseline           the model WITHOUT training: each test message gets the class of its closest example
    ./sorter train              fine-tunes the model on messages/examples.md (about 1 minute)
    ./sorter test               the fine-tuned model on messages/test.md: what it got right, and its mistakes
    ./sorter try "a message"    one message: its class, and what the chatbot would do with it
    ./sorter claude             the same test, sorted by Claude from a description of the classes (no examples)

The four classes (headings of messages/examples.md and messages/test.md):
    topic       a question about the chatbot's topic: the chatbot answers it
    today       asks about today's situation (today's fire danger level): a live tool answers it (workshop 4)
    urgent      a fire happening now, or someone in danger or distress: a fixed safety answer, at once
    off-topic   anything else: a polite refusal, without spending tokens

Nothing here changes the chatbot of the earlier workshops: this is a separate tool, to see what fine-tuning
a small model is, and when it is worth it.
"""
import json
import logging
import os
import re
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
WHAT_HAPPENS = {
    "topic": "the chatbot answers it, with its instructions and its knowledge",
    "today": "a live tool answers it (today's level, from the official source: workshop 4)",
    "urgent": "a fixed safety answer, at once: emergency number 112, or an adult they trust",
    "off-topic": "a polite refusal, without calling the chatbot (no tokens spent)",
}
UNSURE = 0.5          # below this confidence, the sorter says it is not sure
CLAUDE_MODEL = os.environ.get("WORKSHOP_SORTER_CLAUDE", "claude-haiku-5-5")
CLAUDE_PRICES = (0.10, 0.50)    # $ per million tokens in and out (claude-haiku-5-5, price list 2026-10-31)


def fail(message):
    print(message, file=sys.stderr)
    sys.exit(1)


def read_messages(path):
    """[(message, class)] from a file of '## class' headings followed by '- message' lines."""
    if not path.is_file():
        fail(f"{path.relative_to(HERE)} is missing.")
    pairs, current, unknown = [], None, []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if line.startswith("<!--") or not line:
            continue
        if line.startswith("## "):
            current = line[3:].strip().lower()
            if current not in CLASSES:
                unknown.append(f"line {n}: '{current}'")
        elif line.startswith("- ") and current in CLASSES and line[2:].strip():
            pairs.append((line[2:].strip(), current))
    if unknown:
        fail(f"{path.relative_to(HERE)}: unknown class ({', '.join(unknown)}). "
             f"The headings must be: {', '.join('## ' + c for c in CLASSES)}")
    return pairs


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
    except ImportError:
        fail("The libraries are not installed yet. Type: ./sorter setup")


def same_text(a, b):
    return re.sub(r"\W+", " ", a.lower()).strip() == re.sub(r"\W+", " ", b.lower()).strip()


def leaks(train, test):
    return [m for m, _ in test if any(same_text(m, t) for t, _ in train)]


def table(results):
    """results: [(message, expected, predicted, confidence)]. Prints the mistakes and the confusion table."""
    right = sum(e == p for _, e, p, _ in results)
    print(f"\n{right} of {len(results)} messages in the right class.\n")
    print("Expected (rows) and chosen (columns):")
    print(" " * 11 + "".join(f"{c:>11}" for c in CLASSES))
    for e in CLASSES:
        print(f"{e:>11}" + "".join(f"{sum(1 for _, x, p, _ in results if x == e and p == c):>11}" for c in CLASSES))
    mistakes = [(m, e, p, c) for m, e, p, c in results if e != p]
    if mistakes:
        print("\nMistakes:")
        for m, e, p, c in mistakes:
            danger = "  <- an emergency that would not get the safety answer" if e == "urgent" else ""
            print(f"  expected {e:<9} chose {p:<9} ({c:.2f})  {m}{danger}")
    missed = sum(1 for _, e, p, _ in results if e == "urgent" and p != "urgent")
    print(f"\nEmergencies missed: {missed}. This is the mistake that matters most.")


def cmd_setup():
    """Done by the bash part of ./sorter (it creates the environment); here, download the model once."""
    t0 = time.time()
    from sentence_transformers import SentenceTransformer
    SentenceTransformer(BASE, revision=REVISION, device="cpu")
    print(f"Model ready ({time.time() - t0:.0f} s). Next: ./sorter baseline")


def cmd_baseline():
    """No training: each test message takes the class of the closest example (by meaning)."""
    check_libraries()
    import numpy as np
    from sentence_transformers import SentenceTransformer
    train, test = read_messages(EXAMPLES), read_messages(TEST)
    model = SentenceTransformer(BASE, revision=REVISION, device="cpu")
    vectors = model.encode([m for m, _ in train], normalize_embeddings=True)
    results = []
    for message, expected in test:
        scores = vectors @ model.encode([message], normalize_embeddings=True)[0]
        best = int(np.argmax(scores))
        results.append((message, expected, train[best][1], float(scores[best])))
    print("WITHOUT training: each message gets the class of its closest example in messages/examples.md.")
    table(results)
    print("\nNext: ./sorter train, then ./sorter test, and compare.")


def cmd_train():
    check_libraries()
    import torch
    from datasets import Dataset
    from setfit import SetFitModel, Trainer, TrainingArguments
    train, test = read_messages(EXAMPLES), read_messages(TEST)
    counts = {c: sum(1 for _, x in train if x == c) for c in CLASSES}
    missing = [c for c, n in counts.items() if n < 2]
    if missing:
        fail(f"Each class needs at least 2 examples in messages/examples.md (missing: {', '.join(missing)}).")
    leaked = leaks(train, test)
    if leaked:
        print(f"Warning: {len(leaked)} test message(s) are also in the examples: the test will look better than "
              f"it is. Rewrite them in messages/test.md: {leaked[0]}")
    torch.set_num_threads(cores())
    print(f"Fine-tuning on {len(train)} examples ({', '.join(f'{c} {n}' for c, n in counts.items())})…", flush=True)
    model = SetFitModel.from_pretrained(BASE, revision=REVISION, labels=sorted(CLASSES))
    t0 = time.time()
    HOME.mkdir(parents=True, exist_ok=True)
    trainer = Trainer(model=model, train_dataset=Dataset.from_dict(
        {"text": [m for m, _ in train], "label": [c for _, c in train]}),
        args=TrainingArguments(output_dir=str(HOME / "steps"), save_strategy="no", batch_size=16,
                               num_epochs=1, num_iterations=10, seed=42))
    trainer.train()
    model.save_pretrained(str(MODEL_DIR))
    print(f"\nFine-tuned in {time.time() - t0:.0f} s. Next: ./sorter test")


def load_model():
    check_libraries()
    import torch
    torch.set_num_threads(cores())
    if not (MODEL_DIR / "model_head.pkl").is_file():
        fail("No fine-tuned model yet. Type: ./sorter train")
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
    probas = model.predict_proba(messages).tolist()
    names = class_names(model)
    out = []
    for row in probas:
        i = max(range(len(row)), key=row.__getitem__)
        out.append((names[i], row[i]))
    return out


def cmd_test():
    model = load_model()
    train, test = read_messages(EXAMPLES), read_messages(TEST)
    t0 = time.time()
    chosen = predict(model, [m for m, _ in test])
    ms = (time.time() - t0) / max(len(test), 1) * 1000
    print(f"The FINE-TUNED model, on the {len(test)} messages of messages/test.md ({ms:.0f} ms per message):")
    table([(m, e, p, c) for (m, e), (p, c) in zip(test, chosen)])
    if leaks(train, test):
        print("\nWarning: some test messages are also in the examples: this score is too good.")


def cmd_try(message):
    model = load_model()
    (label, confidence), = predict(model, [message])
    print(f"Class: {label} (confidence {confidence:.2f})")
    if confidence < UNSURE:
        print(f"Not sure (below {UNSURE}): a real chatbot would rather pass it to the chatbot, whose own rules "
              "also cover emergencies.")
    print(f"What would happen: {WHAT_HAPPENS[label]}.")


CLAUDE_INSTRUCTIONS = """You sort messages sent to a chatbot about wildfire prevention, written in any language.
Answer with exactly one word, the class:
topic: a question about wildfires, their prevention, the rules, what to do (the chatbot answers it)
today: asks about today's situation or today's fire danger level, or whether something is allowed today
urgent: a fire happening now, or someone in danger or distress (needs a safety answer at once)
off-topic: anything else"""


def cmd_claude():
    key_file = Path.home() / ".workshop-key"
    if not key_file.is_file():
        fail("No key yet. Type: workshop-login")
    key = key_file.read_text(encoding="utf-8").strip()
    if not key.startswith("sk-ant-"):
        fail("This comparison needs an Anthropic key (it starts with sk-ant-). Type: workshop-login")
    test = read_messages(TEST)
    results, tokens_in, tokens_out, t0 = [], 0, 0, time.time()
    print(f"Claude ({CLAUDE_MODEL}) sorts the {len(test)} test messages from a description of the classes, "
          "with no examples…", flush=True)
    for message, expected in test:
        body = {"model": CLAUDE_MODEL, "max_tokens": 10, "system": CLAUDE_INSTRUCTIONS,
                "messages": [{"role": "user", "content": message}]}
        request = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(),
                                         headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                                  "content-type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.load(response)
        except urllib.error.HTTPError as e:
            fail(f"Claude refused the request (HTTP {e.code}). Check your key with workshop-login.")
        except (urllib.error.URLError, OSError) as e:
            fail(f"No answer from Claude ({getattr(e, 'reason', e)}). Check the network and try again.")
        usage = data.get("usage") or {}
        tokens_in += usage.get("input_tokens", 0)
        tokens_out += usage.get("output_tokens", 0)
        text = "".join(b.get("text", "") for b in data.get("content") or [] if b.get("type") == "text")
        word = re.sub(r"[^a-z-]", "", text.strip().lower().split()[0] if text.strip() else "")
        results.append((message, expected, word if word in CLASSES else "(other)", 1.0))
    seconds = time.time() - t0
    cost = (tokens_in * CLAUDE_PRICES[0] + tokens_out * CLAUDE_PRICES[1]) / 1_000_000
    table(results)
    print(f"\nTime: {seconds:.0f} s ({seconds / len(test):.1f} s per message). Tokens: {tokens_in} in, {tokens_out} out. "
          f"Estimated cost: ${cost:.4f}, so about ${cost / len(test) * 1000:.2f} per 1,000 messages.")
    print("The fine-tuned model: no cost per message, and it works without the network.")


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
    elif command == "try" and len(argv) >= 2:
        cmd_try(" ".join(argv[1:]))
    elif command == "claude" and len(argv) == 1:
        cmd_claude()
    else:
        print(__doc__.strip().split("\n\nThe four classes")[0])


if __name__ == "__main__":
    main(sys.argv[1:])
