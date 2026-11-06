#!/usr/bin/env python3
"""The facilitator's demo of workshop 6: the sorter in front of a chatbot, in the kit's Open WebUI.
A PROTOTYPE to think with (well-being, private data, energy), not a tool for a real service.

In your own Codespace of workshop 6, after ./sorter setup, ./sorter train and openwebui start (your key):

    python3 demo.py start     puts your sorter in front of every model of your Open WebUI, adds the chatbot
                              "Sorter demo (prototype)", and prints what to show
    python3 demo.py status    what is installed
    python3 demo.py stop      removes all of it, the conversations with the demo chatbot included

Keep demo.py, sorter_router.py and sorter_answers.py in the same folder.
"""
# The facilitator's demo of workshop 6 (README.md next to it). Python's standard library only, in the
# Codespace as in the container of Open WebUI.
#
# What this file does, and what it never does:
# - it never reads the key (~/.workshop-key) and sends nothing to a provider: no test question to the model.
#   The only messages that leave are those the facilitator types afterwards, through Open WebUI, to the
#   provider of their key;
# - the head of the model is turned into numbers (head.json) by the python of ./sorter setup, in the Codespace;
#   model_head.pkl (a pickle) never enters the container of Open WebUI;
# - only the files a sentence-transformers model needs are copied (safetensors, no .bin);
# - no log of the messages (valve log_path empty, checked);
# - the filter is global during the demo: the base model (hidden, but reachable by its name), "Wildfire RAG"
#   when this Open WebUI has one (not in the repository of workshop 6: no documents) and any other chatbot go
#   through the sorter too;
# - the demo chatbot is built on the hidden base model that openwebui start always sets up (plain_model() of
#   the kit), with its settings for the provider (OpenRouter's data rule);
# - stop removes the functions, the models, the conversations with the demo chatbot and the copied files, then
#   checks.
#
# The work on the API of Open WebUI is done INSIDE its container (docker exec, http://127.0.0.1:8080): the same
# path in a Codespace and in the offline test kept in the facilitators' repository (demo_check.py).
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTAINER = os.environ.get("WORKSHOP_OPENWEBUI_CONTAINER", "yal-kit-openwebui")
PORT = int(os.environ.get("WORKSHOP_OPENWEBUI_PORT", "3000"))
FT = Path(os.environ.get("WORKSHOP_FINETUNE_HOME", Path.home() / ".workshop-finetune"))
DEST = "/app/backend/data/sorter-demo"        # in the volume of Open WebUI; removed by stop
MODEL = DEST + "/model"
INSIDE_URL = "http://127.0.0.1:8080"
# The only versions this demo was tried with: 0.12.4 (image 2026.11.4), 0.12.5 (image 2026.11.5 and later).
VERSIONS = ("0.12.4", "0.12.5")
ROUTER, ANSWERS = "sorter_router", "sorter_answers"
ANSWER_IDS = [f"{ANSWERS}.{a}" for a in ("urgent", "needs_care", "off_topic", "unavailable")]
CHATBOT, CHATBOT_NAME = "sorter-demo-prototype", "Sorter demo (prototype)"
# The kind answer was sorter_answers.worried until 2026-11-05: stop removes it too, after an older start.
OURS = [CHATBOT, *ANSWER_IDS, f"{ANSWERS}.worried"]
SYSTEM = ("You are a DEMO chatbot of a workshop, about wildfire prevention, for young people. Answer in a few short "
          "sentences. Refuse questions outside wildfire prevention, kindly. You have no live tool: never guess "
          "today's fire danger level, say where to read it instead. If someone is in danger, tell them to call 112 "
          "and to talk to an adult they trust.")
# The files a sentence-transformers model needs, nothing else (no pickle, no pytorch_model.bin).
MODEL_FILES = ["config.json", "config_sentence_transformers.json", "sentence_bert_config.json", "modules.json",
               "model.safetensors", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json",
               "sentencepiece.bpe.model", "vocab.txt"]
# What to type, in this order. The class and what happens are computed by start with YOUR model.
DEMO = [
    ("Which plants burn less around a house?", "a question on the topic"),
    ("Is the fire danger high today?", "a question about today"),
    ("I can see flames on the hill, what do I do?", "an emergency"),
    ("Il y a de la fumée derrière l'école !", "an emergency, in French"),
    ("help!!", "a short cry for help"),
    ("I'm sad all the time since my best friend moved away", "someone sad, no danger now"),
    ("I feel like nobody would care if I disappeared", "may be thinking of dying, so it should be urgent"),
    ("How do I bake a chocolate cake?", "off-topic"),
    ("ok", "a follow-up in the same conversation: sorted alone"),
]
WHAT = {"urgent": "safety answer, the chatbot is not asked",
        "needs_care": "kind answer, the chatbot is not asked",
        "off_topic": "polite refusal, the chatbot is not asked",
        "chatbot": "the chatbot answers (a paid call with your key)"}


def fail(message):
    print(message, file=sys.stderr)
    sys.exit(1)


# === In the Codespace ===========================================================================

def docker(*args, check=True):
    r = subprocess.run(["docker", *args], text=True, capture_output=True)
    if check and r.returncode != 0:
        fail(f"docker {args[0]} failed: {r.stderr.strip()[:400]}")
    return r


def inside(*args):
    """This file, run by the python of the Open WebUI container. Its output goes straight to the terminal."""
    docker("exec", CONTAINER, "mkdir", "-p", DEST)
    docker("cp", str(HERE / "demo.py"), f"{CONTAINER}:{DEST}/demo.py")
    sys.stdout.flush()
    return subprocess.run(["docker", "exec", "-e", "TRANSFORMERS_VERBOSITY=error", "-e", "HF_HUB_DISABLE_PROGRESS_BARS=1",
                           CONTAINER, "python3", "-I", "-B", f"{DEST}/demo.py", "_inside", *args]).returncode


def check_open_webui():
    if not shutil.which("docker") or subprocess.run(["docker", "info"], capture_output=True).returncode != 0:
        fail("Docker is not available here. In a Codespace, wait one minute and try again.")
    running = docker("inspect", "--format", "{{.State.Running}}", CONTAINER, check=False)
    if running.returncode != 0 or running.stdout.strip() != "true":
        fail("Open WebUI is not running. Type: openwebui start")
    # The kit's own check: its Open WebUI has no accounts, so its port must stay private.
    if shutil.which("openwebui"):
        if subprocess.run(["openwebui", "check-private"]).returncode != 0:
            sys.exit(1)
    else:
        print("Note: the command openwebui was not found, so the port was not checked. Keep port "
              f"{PORT} private (Ports tab).")


def address():
    name, domain = os.environ.get("CODESPACE_NAME"), os.environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN")
    return f"https://{name}-{PORT}.{domain}" if name and domain else f"http://localhost:{PORT}"


def local_numbers():
    """EMERGENCY and SUPPORT of tools/sorter.py (this folder or above it), when the facilitator changed them."""
    found = {}
    for folder in [Path.cwd(), *Path.cwd().parents, HERE, *HERE.parents]:
        path = folder / "tools" / "sorter.py"
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            for name in ("EMERGENCY", "SUPPORT"):
                match = re.search(rf'^{name} = "([^"\n]*)"', text, re.M)
                if match:
                    found[name.lower()] = match.group(1)
            break
    return found


def model_files(model):
    """[(relative path, path)] of the files to copy. Stops on anything unexpected."""
    if not (model / "model.safetensors").is_file():
        fail(f"No model.safetensors in {model}: this demo copies only safetensors weights. Type: ./sorter train")
    files = [(name, model / name) for name in MODEL_FILES if (model / name).is_file()]
    for entry in json.loads((model / "modules.json").read_text(encoding="utf-8")):
        kind, sub = str(entry.get("type", "")), str(entry.get("path", ""))
        if not kind.startswith("sentence_transformers.") or ".." in sub or sub.startswith("/"):
            fail(f"Unexpected module in {model}/modules.json: {kind} {sub}")
        if sub and (model / sub / "config.json").is_file():
            files.append((f"{sub}/config.json", model / sub / "config.json"))
    return files


def convert_head(model, out):
    """head.json from model_head.pkl, by the python of ./sorter setup (it has scikit-learn): run in the
    Codespace, as you, on the model you just trained."""
    python = FT / "venv" / "bin" / "python"
    if not python.exists():
        fail("The libraries of the sorter are not installed here. Type: ./sorter setup, then ./sorter train")
    r = subprocess.run([str(python), "-I", str(HERE / "demo.py"), "_head", str(model), str(out)],
                       text=True, capture_output=True)
    if r.returncode != 0:
        fail(f"Could not read the trained model: {(r.stderr or r.stdout).strip()[-600:]}")
    print(r.stdout.strip(), flush=True)


def cmd_start():
    model = FT / "model"
    if not (model / "model_head.pkl").is_file():
        fail("No fine-tuned model yet. Type: ./sorter train")
    for name in ("sorter_router.py", "sorter_answers.py"):
        if not (HERE / name).is_file():
            fail(f"{name} is missing: keep it next to demo.py.")
    check_open_webui()
    t0 = time.monotonic()
    with tempfile.TemporaryDirectory() as tmp:
        head = Path(tmp) / "head.json"
        convert_head(model, head)
        docker("exec", CONTAINER, "rm", "-rf", MODEL)
        docker("exec", CONTAINER, "mkdir", "-p", MODEL)
        files = model_files(model)
        for rel, path in files:
            if "/" in rel:
                docker("exec", CONTAINER, "mkdir", "-p", f"{MODEL}/{rel.rsplit('/', 1)[0]}")
            docker("cp", str(path), f"{CONTAINER}:{MODEL}/{rel}")
        docker("cp", str(head), f"{CONTAINER}:{MODEL}/head.json")
    for name in ("sorter_router.py", "sorter_answers.py"):
        docker("cp", str(HERE / name), f"{CONTAINER}:{DEST}/{name}")
    print(f"Model copied into Open WebUI ({len(files)} files and head.json, {time.monotonic() - t0:.0f} s).", flush=True)
    code = inside("start", json.dumps({**local_numbers(), "address": address()}))
    if code != 0:
        fail("The demo is not fully installed. To remove what is there: python3 demo.py stop")


def cmd_stop():
    check_open_webui()
    if inside("stop") != 0:
        fail("Something could not be removed (see above). Type python3 demo.py stop again.")
    docker("exec", CONTAINER, "rm", "-rf", DEST)
    left = docker("exec", CONTAINER, "test", "-e", DEST, check=False).returncode == 0
    if left:
        fail(f"{DEST} is still in the Open WebUI container.")
    print(f"Copied files removed ({DEST}). Nothing of the demo is left in Open WebUI.")
    print("The sorter's memory inside Open WebUI (about 0.5 GB) is freed when Open WebUI restarts: "
          "openwebui stop, then openwebui start.")


def cmd_status():
    check_open_webui()
    sys.exit(inside("status"))


# === In the Codespace, with the python of ./sorter setup ========================================

def head_json(model_dir, out):
    import joblib
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    model_dir = Path(model_dir)
    head = joblib.load(model_dir / "model_head.pkl")   # your own model, as ./sorter itself loads it
    if type(head) is not LogisticRegression:
        fail(f"The head of this model is a {type(head).__name__}, not the LogisticRegression of ./sorter train.")
    setfit = json.loads((model_dir / "config_setfit.json").read_text(encoding="utf-8"))
    coef, intercept = np.asarray(head.coef_, dtype=np.float64), np.asarray(head.intercept_, dtype=np.float64)
    classes = [str(c) for c in head.classes_]
    if coef.shape[0] != len(classes) or len(classes) < 3:
        fail(f"Unexpected head: {coef.shape[0]} rows for {len(classes)} classes.")
    # The same probabilities as head.predict_proba, from numbers only: checked on random points.
    x = np.random.default_rng(0).normal(size=(256, coef.shape[1]))
    z = x @ coef.T + intercept
    z -= z.max(axis=1, keepdims=True)
    p = np.exp(z)
    p /= p.sum(axis=1, keepdims=True)
    gap = float(np.abs(p - head.predict_proba(x)).max())
    if gap > 1e-9:
        fail(f"head.json would not give the same probabilities (gap {gap:.1e}).")
    Path(out).write_text(json.dumps({"format": "softmax-v1", "classes": classes, "coef": coef.tolist(),
                                     "intercept": intercept.tolist(),
                                     "normalize_embeddings": bool(setfit.get("normalize_embeddings", False))}))
    print(f"Head converted to numbers: {len(classes)} classes ({', '.join(classes)}), same probabilities "
          f"(largest gap {gap:.1e}).")


# === In the Open WebUI container ================================================================

class Api:
    def __init__(self):
        self.token = ""
        try:
            self.token = self.call("POST", "/auths/signin", {"email": "", "password": ""})["token"]
        except RuntimeError:
            fail("This Open WebUI has accounts (group mode): the demo is for the kit's Open WebUI only.")

    def call(self, method, path, body=None, raw=False):
        url = INSIDE_URL + (path if path.startswith("/api/") else "/api/v1" + path)
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                text = resp.read().decode()
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{method} {path}: HTTP {e.code}: {e.read().decode(errors='replace')[:300]}") from None
        if raw:
            return text
        return json.loads(text) if text else None

    def get_or_none(self, path):
        try:
            return self.call("GET", path)
        except RuntimeError as e:
            if "HTTP 404" in str(e) or "HTTP 401" in str(e):
                return None
            raise

    def model_record(self, model_id):
        return self.get_or_none(f"/models/model?id={urllib.parse.quote(model_id)}")

    def save_model(self, form):
        self.call("POST", "/models/model/update" if self.model_record(form["id"]) else "/models/create", form)

    def listed(self):
        return [m["id"] for m in self.call("GET", "/api/models?refresh=true")["data"]]


def put_function(api, fid, name, description):
    content = Path(DEST, f"{fid}.py").read_text(encoding="utf-8")
    form = {"id": fid, "name": name, "content": content, "meta": {"description": description}}
    if api.get_or_none(f"/functions/id/{fid}"):
        api.call("POST", f"/functions/id/{fid}/update", form)
    else:
        api.call("POST", "/functions/create", form)
    if not api.call("GET", f"/functions/id/{fid}").get("is_active"):
        api.call("POST", f"/functions/id/{fid}/toggle")


def set_valves(api, fid, values):
    valves = api.call("GET", f"/functions/id/{fid}/valves") or {}
    valves.update(values)
    api.call("POST", f"/functions/id/{fid}/valves/update", valves)
    return api.call("GET", f"/functions/id/{fid}/valves") or {}


def preview(numbers):
    """The class of each message of DEMO, with the copied model and the filter's own rules: no model is called."""
    import importlib.util
    import logging
    logging.getLogger("sentence_transformers").setLevel(logging.ERROR)   # its version warning, on screen
    try:
        from transformers.utils import logging as transformers_logging
        transformers_logging.disable_progress_bar()
    except ImportError:
        pass
    spec = importlib.util.spec_from_file_location("sorter_router_preview", f"{DEST}/sorter_router.py")
    router = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(router)
    f = router.Filter()
    f.valves.model_dir = MODEL
    probas_of, names = f._local_model()
    rows = []
    for message, what in DEMO:
        label, confidence, action, why = router.decide(message, probas_of, names)
        happens = WHAT[action]
        if action == "chatbot" and why != "sure":
            happens = f"{why}: {happens}"
        rows.append((message, what, label, confidence, happens))
    return rows


def base_model(api):
    """The record of the hidden base model that openwebui start always sets up: the model of the key, as the
    container offers it (OPENAI_API_CONFIGS, kit mode: one model), saved with no base_model_id. Since image
    2026.11.6, openwebui start makes no "Wildfire RAG" model in a repository without documents (workshop 6)."""
    try:
        offered = json.loads(os.environ["OPENAI_API_CONFIGS"])["0"]["model_ids"]
    except (KeyError, TypeError, ValueError):
        offered = []
    for model_id in offered:
        record = api.model_record(model_id)
        if record and not record.get("base_model_id") and (record.get("meta") or {}).get("hidden"):
            return record
    fail("No hidden base model in this Open WebUI yet. Type openwebui start, then python3 demo.py start again.")


def inside_start(options):
    options = json.loads(options)
    api = Api()
    version = api.call("GET", "/api/version").get("version")
    if version not in VERSIONS:
        fail(f"This demo was tried with Open WebUI {' and '.join(VERSIONS)} only, and this one is {version}.")
    base = base_model(api)
    put_function(api, ANSWERS, "Sorter fixed answers (prototype)", "PROTOTYPE of workshop 6: the fixed answers.")
    put_function(api, ROUTER, "Message sorter (prototype)", "PROTOTYPE of workshop 6: sorts each message first.")
    answers = set_valves(api, ANSWERS, {k: options[k] for k in ("emergency", "support") if options.get(k)})
    valves = set_valves(api, ROUTER, {"model_dir": MODEL, "answers_pipe": ANSWERS, "show_status": True,
                                      "log_path": ""})
    if valves.get("log_path") or valves.get("model_dir") != MODEL:
        fail("The sorter's settings were not saved as expected.")
    # Global: every model of this Open WebUI goes through the sorter, the hidden base model included.
    if not api.call("GET", f"/functions/id/{ROUTER}").get("is_global"):
        api.call("POST", f"/functions/id/{ROUTER}/toggle/global")
    missing = [i for i in ANSWER_IDS if i not in api.listed()]
    if missing:
        fail(f"Open WebUI does not show the fixed answers {missing}.")
    for model_id in ANSWER_IDS:   # never chosen by hand: hidden from the list
        api.save_model({"id": model_id, "base_model_id": None, "name": model_id, "is_active": True,
                        "meta": {"hidden": True}, "params": {}})
    params = {"system": SYSTEM, "function_calling": "legacy"}
    if (base.get("params") or {}).get("custom_params"):
        params["custom_params"] = base["params"]["custom_params"]   # OpenRouter's data rule, as the kit sets it
    api.save_model({
        "id": CHATBOT, "base_model_id": base["id"], "name": CHATBOT_NAME, "is_active": True,
        "meta": {"description": "PROTOTYPE of workshop 6: a small fine-tuned model sorts each message before "
                                "the chatbot. Not a tool for a real service.",
                 "filterIds": [ROUTER],
                 "capabilities": {"file_context": False, "citations": False, "builtin_tools": False,
                                  "file_upload": False, "web_search": False, "image_generation": False,
                                  "code_interpreter": False}},
        "params": params})
    listed = api.listed()   # also refreshes the copy of the models that a chat uses
    router = api.call("GET", f"/functions/id/{ROUTER}")
    if CHATBOT not in listed or not (router.get("is_active") and router.get("is_global")):
        fail("The sorter or the demo chatbot is not active.")
    rows = preview(options)
    line = "=" * 78
    print(f"\n{line}\nPROTOTYPE - workshop 6\n{line}")
    print("Your sorter now sits in front of every model of this Open WebUI, and of the chatbot")
    print(f'"{CHATBOT_NAME}". It is a prototype to think about well-being, private data and')
    print("energy. It is not a tool for a real service: no professional has checked its answers.")
    print(f"\nOpen: {options['address']}  (if it is already open, reload the page)")
    print(f'Choose "{CHATBOT_NAME}" in the message box (the name at the bottom right). Above each')
    print("answer, a grey line shows the class and whether the chatbot was asked.")
    print("\nType these messages, in this order (classes from YOUR model, computed now):")
    for i, (message, what, label, confidence, happens) in enumerate(rows, 1):
        print(f"  {i}. {message}\n     {what}: {label} ({confidence:.2f}) -> {happens}")
    print(f"\nEmergency number in the fixed answers: {answers.get('emergency')}. Support contact: "
          f"{answers.get('support')}.")
    print("No message is logged by the sorter. Open WebUI keeps each conversation, as any chat does:")
    print("stop deletes the conversations with the demo chatbot.")
    print(f"\nWhen you are done: python3 demo.py stop\n{line}")


def our_chats(api):
    found = []
    for line in api.call("GET", "/chats/all", raw=True).splitlines():
        if not line.strip():
            continue
        chat = json.loads(line)
        body = chat.get("chat") or {}
        used = set(body.get("models") or [])
        for message in (body.get("history") or {}).get("messages", {}).values():
            used.add(message.get("model"))
            used.update(message.get("models") or [])
        if used & set(OURS):
            found.append(chat["id"])
    return found


def inside_stop():
    api = Api()
    chats = our_chats(api)
    for chat_id in chats:
        api.call("DELETE", f"/chats/{chat_id}")
    removed = []
    for model_id in OURS:
        if api.model_record(model_id):
            api.call("POST", "/models/model/delete", {"id": model_id})
            removed.append(model_id)
    for fid in (ROUTER, ANSWERS):
        if api.get_or_none(f"/functions/id/{fid}"):
            api.call("DELETE", f"/functions/id/{fid}/delete")
            removed.append(fid)
    listed = api.listed()
    left = ([fid for fid in (ROUTER, ANSWERS) if api.get_or_none(f"/functions/id/{fid}")]
            + [m for m in OURS if api.model_record(m) or m in listed] + our_chats(api))
    if left:
        fail(f"Still in Open WebUI: {left}")
    print(f"Removed from Open WebUI: {len(chats)} conversation(s) with the demo chatbot, "
          f"{', '.join(removed) or 'nothing else'}.")
    wipe_deleted()


DB = Path("/app/backend/data/webui.db")


def wipe_deleted():
    """SQLite keeps deleted rows on disk, in its WAL file and in free pages (measured on 2026-11-04: the demo's
    names were still in webui.db-wal after stop). VACUUM rewrites the database without them, then the WAL is
    emptied. Then the files are searched for the demo chatbot's id."""
    import sqlite3
    if not DB.is_file():
        print("Note: no SQLite file in Open WebUI: the deleted conversations were not wiped from the disk.")
        return
    db = sqlite3.connect(DB, timeout=60)
    try:
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        db.execute("VACUUM")
        busy = db.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0]
    finally:
        db.close()
    found = [p.name for p in DB.parent.glob(DB.name + "*") if p.is_file() and any(
        name.encode() in p.read_bytes() for name in (CHATBOT, CHATBOT_NAME, ROUTER, ANSWERS))]
    if busy or found:
        fail(f"The demo's deleted data may still be on disk ({', '.join(found) or 'database busy'}). "
             "Type python3 demo.py stop again in a minute.")
    print("Database rewritten without the deleted rows (SQLite VACUUM).")


def inside_status():
    api = Api()
    functions = {f["id"]: f for f in api.call("GET", "/functions/")}
    for fid in (ROUTER, ANSWERS):
        f = functions.get(fid)
        print(f"{fid}: " + ("not installed" if not f else
                            f"active {f.get('is_active')}, for every model {f.get('is_global')}"))
    print(f"{CHATBOT_NAME}: {'installed' if api.model_record(CHATBOT) else 'not installed'}")
    print(f"model copied: {'yes' if Path(MODEL, 'head.json').is_file() else 'no'}")


def main(argv):
    command = argv[0] if argv else ""
    if command == "start" and len(argv) == 1:
        cmd_start()
    elif command == "stop" and len(argv) == 1:
        cmd_stop()
    elif command == "status" and len(argv) == 1:
        cmd_status()
    elif command == "_head" and len(argv) == 3:
        head_json(argv[1], argv[2])
    elif command == "_inside" and argv[1:2] == ["start"] and len(argv) == 3:
        inside_start(argv[2])
    elif command == "_inside" and argv[1:] == ["stop"]:
        inside_stop()
    elif command == "_inside" and argv[1:] == ["status"]:
        inside_status()
    else:
        print(__doc__.strip())
        sys.exit(0 if command in ("", "help", "-h", "--help") else 1)


if __name__ == "__main__":
    main(sys.argv[1:])
