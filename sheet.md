# Workshop 6 - Teach a small model to sort messages (one page)

**Question of the day: how can a small model that you teach help a big one?**
Full page: [README.md](README.md). Setup and common problems: [SETUP.md](SETUP.md) (steps 1 to 3 and 6 today).

| Class | What it means | What a real chatbot would do |
|---|---|---|
| `topic` | a question about the chatbot's topic | answer, with its instructions and knowledge |
| `today` | a question that needs the facts of the moment, tonight or this weekend included | call the live tool (workshop 4), read the result |
| `urgent` | a fire happening now, or a person in danger or distress, with no fire needed | fixed safety answer at once: 112 (European number), an adult they trust |
| `off-topic` | anything else | polite refusal naming 112 and an adult they trust, no tokens spent |

## 1. Welcome (15 min)

1. Idle timeout not set yet on this account? First: [SETUP.md, step 1](SETUP.md#step-1---let-the-codespace-wait-for-you).
2. Open **https://codespaces.new/Youth-AI-Lab/yal-workshop-finetune** → **Create codespace**.
3. Terminal: `workshop-login`, paste the key, Enter → `Key OK`. It fails? Tell the facilitator: Parts 1 to 4 go on.
4. `workshop-start 6`, then `./sorter setup` (about 2 min 30) → `Model ready`.

## 2. A model that has not learned your classes yet (15 min)

Open `messages/examples.md` and `messages/test.md`. `./sorter baseline`: read the table (rows: right class,
columns: chosen class). **Emergencies missed**, an emergency sorted as something else, matters most.

## 3. Write your examples, and a test for another pair (25 min)

1. At least **10 messages per class** in `messages/examples.md`, in your language, real-sounding, 15 words
   at most, with hard cases. Examples and test: **invented, nothing about a real person**. Headings unchanged, each message starts with `- `. The file ends under `## off-topic`: check the heading above each line.
2. On paper or in the chat: **3 messages per class for another pair**, 15 words at most, the class above each group. Swap.
3. Type theirs into `messages/test.md`, under **the classes they gave you**. **Never** a test message in the examples.

## 4. Fine-tune, test, improve (30 min)

1. Read "What do you train?" and "How does the training work?" (4 min). Predict.
   `./sorter baseline`: **baseline score**.
2. `./sorter train` (about 2 min with 80 examples): the facilitator talks. When it ends, type `./sorter test`
   and keep listening: your **first score**, the one honest test. On the board: both scores, emergencies missed.
   The `README.md` of the model folder (`~/.workshop-finetune/model`) quotes some of your examples.
3. No line under `Mistakes:` or `Right but below 0.5`? Read "What the training changes" as far as the map,
   then go to 4. Otherwise take 2 of these lines at most, emergencies first, add 2 examples like each one,
   train again and read that section meanwhile. Test: your **improved score**, not honest: you tuned the examples on it.
4. `./sorter try`, paste the facilitator's hard messages, one per line, then type short cries for help in your
   language. An empty line stops. Never on the command line: a `!` in quotes leaves you at `dquote>`.

## 5. The big model, without training (15 min)

1. `./sorter compare` (needs a key, not `./sorter setup`): a big model sorts the same test from a
   description of the classes, no examples: Claude Haiku with an Anthropic key, Mistral Small with an
   OpenRouter key. Each test message goes to Anthropic, or through OpenRouter to a company that runs
   the model.
2. Fill in the table, with your first score and its emergencies missed.

## 6. Closing (15 min)

Type `workshop-save`: it keeps `messages/`, not `SETUP.md`, `sheet.md` or `tools/sorter.py`. Right-click on
`my-work.zip` → **Download...**. Then delete the Codespace: **github.com/codespaces** → **...** → **Delete**.

Exit card, alone: why can a classifier not invent? Why never a test message in the examples? One case
for fine-tuning a small model, one for asking a big one.

**Copy / paste in the terminal:** `Ctrl+Shift+C` / `Ctrl+Shift+V` (`Cmd+C` / `Cmd+V` on a Mac).
