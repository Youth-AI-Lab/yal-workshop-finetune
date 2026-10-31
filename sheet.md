# Workshop 6 - Teach a small model to sort messages (one page)

**Question of the day: when is it worth teaching a small model, instead of asking a big one?**
Full page: [README.md](README.md). Setup and common problems: [SETUP.md](SETUP.md).

| Class | What the chatbot should do |
|---|---|
| `topic` | answer, with its instructions and knowledge |
| `today` | ask the live tool of the day (workshop 4) |
| `urgent` | a fixed safety answer, at once |
| `off-topic` | a polite refusal, without spending tokens |

## 1. Welcome (15 min)

1. Idle timeout not set yet on this account? First: [SETUP.md, step 1](SETUP.md#step-1---let-the-codespace-wait-for-you).
2. Open the Codespace: **https://codespaces.new/Youth-AI-Lab/yal-workshop-finetune** → **Create codespace**.
3. Terminal: `workshop-login`, paste the key once, Enter → `Key OK`.
4. `./sorter setup` (about 2 min 30) → `Model ready`.

## 2. A model that has learned nothing yet (15 min)

1. Open `messages/examples.md` and `messages/test.md`.
2. `./sorter baseline`: read the table (rows: right class, columns: chosen class) and the line
   **Emergencies missed**.

## 3. Write your examples, and a test for another pair (25 min)

1. At least **10 messages per class** in `messages/examples.md`, in your language, real-sounding, with
   hard cases. Headings unchanged, each message starts with `- `. No personal information.
2. On paper: **3 messages per class for another pair**. Swap.
3. Type the other pair's messages into `messages/test.md`. **Never** put a test message in the examples.

## 4. Fine-tune, test, improve (25 min)

1. Predict the score. `./sorter baseline` again.
2. `./sorter train` (about 1 min), then `./sorter test`. Both scores on the board.
3. For each mistake, add 2 or 3 examples that look like it. Train and test again.
4. `./sorter try "your message"`.

## 5. The big model, without training (15 min)

1. `./sorter claude`: Claude sorts the same test from a description of the classes, no examples.
2. Fill in the table: right answers, emergencies missed, time, cost per 1,000 messages, network,
   where the message goes, what it took to set up.

## 6. Closing (15 min)

Exit card, alone: why can a classifier not invent? Why never a test message in the examples? One case
for fine-tuning a small model, one for asking a big one.

**The mistake that matters most: an emergency sorted as something else.** **Copy / paste in the
terminal:** `Ctrl+Shift+C` / `Ctrl+Shift+V` (`Cmd+C` / `Cmd+V` on a Mac).
