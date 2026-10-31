# Workshop 6 - Teach a small model to sort messages

### Youth AI Lab (Erasmus+) - series "Build your own chatbot", workshop 6 of 6

- **Project:** Youth AI Lab (Erasmus+), with five partners: L.A.B. (Aix-en-Provence, France),
  UAB (Barcelona, Spain), Perlatecnica (Naples, Italy), Digitale Wolven (Antwerp, Belgium),
  CSC Vent des Îles (La Rochelle, France).
- **The series:** [the workshops](https://github.com/Youth-AI-Lab/yal-workshop-kit#the-series)
- **Need help?**
  - Raise your hand and ask the facilitator.
  - If something breaks, don't panic: your files stay in the Codespace.

> 🎓 **Open your Codespace** (one per pair): 👉 **https://codespaces.new/Youth-AI-Lab/yal-workshop-finetune**
>
> **Before you click**, if the idle timeout of this GitHub account is not set yet: do
> [step 1 of SETUP.md](SETUP.md#step-1---let-the-codespace-wait-for-you) (1 minute).
>
> This link creates your own copy of this repository, in VS Code running in your browser. Nothing
> to install. The detailed steps are in [Part 1](#part-1---welcome-15-min).

> 📚 **The slides of the facilitator:** https://youth-ai-lab.github.io/yal-workshop/6/ (the same
> words as this page). **The short version** of this page, on one page: [sheet.md](sheet.md). The
> setup and the common problems of the whole series: [SETUP.md](SETUP.md).

### Contents

- [Goals of the session](#goals-of-the-session)
- [Part 1 - Welcome (15 min)](#part-1---welcome-15-min)
- [Part 2 - A model that has learned nothing yet (★, 15 min)](#part-2---a-model-that-has-learned-nothing-yet--15-min)
- [Part 3 - Write your examples, and a test for another pair (★★, 25 min)](#part-3---write-your-examples-and-a-test-for-another-pair--25-min)
- [Part 4 - Fine-tune, test, improve (★★, 25 min)](#part-4---fine-tune-test-improve--25-min)
- [Part 5 - The big model, without training (★★★, 15 min)](#part-5---the-big-model-without-training--15-min)
- [Part 6 - Closing (15 min)](#part-6---closing-15-min)
- [Troubleshooting](#troubleshooting)

---

## Goals of the session

### What you will be able to do by the end of this session

In workshops 1 to 5, you gave the chatbot instructions, knowledge, a way to search, tools and a
wiki. You never changed the model itself: it stayed the same Claude for everyone. Today, you change
a model. A small one, for one narrow task: **sorting the messages** that people send to a chatbot,
before the chatbot sees them. The question of the day is:

> **When is it worth teaching a small model, instead of asking a big one?**

| Bloom level | Parts | You will be able to... |
|---|---|---|
| **Understand** | 1, 2 | Explain what a classifier does, and why a model that chooses cannot invent an answer. |
| **Apply** | 3, 4 | Write examples and a test in your language, fine-tune a model on them, and test it. |
| **Analyse** | 2, 4 | Read a confusion table, and find the mistake that matters most. |
| **Evaluate** | 5, 6 | Compare your small model with Claude (right answers, speed, cost, what leaves the Codespace), and decide when fine-tuning is worth it. |

### Why this approach?

**Fine-tuning** means changing a model a little, with your own examples, so that it gets better at
one task. On the slide of the earlier workshops, it was level 5: "a slide only". Fine-tuning a big
model that writes answers needs graphics cards, thousands of examples and days of work. And even
fine-tuned, a model that writes can still invent.

A **classifier** is different. It does not write: it only **chooses** one class among a few that you
decide. So it cannot invent an answer. A small classifier (here, about 118 million parameters; the
big chatbots are many times larger, and their makers do not publish their size) learns from a few
dozen examples, in about a minute, on the two processors of your Codespace, with no graphics card.

The task of the day is a real one. Every chatbot receives four kinds of messages, and they do not
all deserve the same treatment:

| Class | Example | What the chatbot should do |
|---|---|---|
| `topic` | "How can I protect my garden from wildfires?" | answer, with its instructions and knowledge |
| `today` | "What is the fire danger level today?" | ask a live tool, the official source of the day (workshop 4) |
| `urgent` | "There is smoke coming from the woods behind my house!" | a fixed safety answer, at once, with no AI in the way |
| `off-topic` | "Can you help me with my maths homework?" | a polite refusal, without spending tokens |

A sorter placed **before** the chatbot does this in a few milliseconds, for free, and without
sending the message anywhere.

### How this connects to WikiYouthBot

- **The chatbot of the young people of La Rochelle, Feurisson**, does exactly this in its public
  version: a small French model, fine-tuned by the group, recognises the questions of its FAQ before
  Claude is called. The FAQ answers are free and always the same. See
  [wikiyouthbot-feurisson](https://github.com/Youth-AI-Lab/wikiyouthbot-feurisson) and its activity
  with young people.
- **Part 3** is an activity in itself with young people: writing the messages that a chatbot will
  receive, in their own words, is a way to think about who will use it and how.
- **Part 5** is a question to ask before choosing a tool: what does each message cost, and where
  does it go?

The series, one piece of the chatbot at a time:

- **Workshop 1**: the instructions, and how to test a chatbot
- **Workshop 2**: all the knowledge in the context, then a RAG
- **Workshop 3**: the model searches by itself, and skills
- **Workshop 4**: tools that bring today's facts
- **Workshop 5**: organise what it knows in a wiki, and pack the chatbot of your territory
- **Workshop 6** (this one): **fine-tune a small model**, to sort messages before the chatbot

### Before you start

**Nothing to bring from the earlier workshops**: this one stands on its own. **Think of real
messages**: how do young people write to a chatbot in your language, with what words, what
mistakes? You will need them in Part 3. You need your key (`workshop-login`) for Part 5 only.

### Reference documents

All of these are in your Codespace, in the file list on the left:

- `messages/examples.md`: the examples the model learns from, under four headings. You write here
  today.
- `messages/test.md`: the test messages. The model never sees them while it learns.
- `sorter`: the command of the day (type `./sorter` to see what it can do).
- `tools/sorter.py`: the program behind it, about 300 lines of Python, if you are curious.
- `SETUP.md`: setup and common problems of the whole series.

---

## Part 1 - Welcome (15 min)

### Step 1 - Open your Codespace and save your key

1. Open the link at the top of this page, then **Create codespace**. Wait for the terminal.
2. In the terminal, save your key (once per Codespace):

   ```bash
   workshop-login
   ```

   Paste your key, press Enter. **What you should see:** `Key OK`. The key is only used in Part 5.

> ℹ️ **No Codespace?** The same repository opens on your own computer, with Docker and VS Code: see
> the [dev containers guide](https://github.com/Youth-AI-Lab/yal-devcontainer-guide).

### Step 2 - Install the sorter

The libraries that fine-tune a model are big (about 2 GB with the model). They are not in the
Codespace from the start: you install them now, once.

1. Type:

   ```bash
   ./sorter setup
   ```

2. While it installs, read the next section.

**What you should see:** after about two and a half minutes (151 s in our test on 2026-10-31, in a
copy of the Codespace with 2 processors), `Model ready (… s). Next: ./sorter baseline`.

### What is this small model?

The model of the day is `paraphrase-multilingual-MiniLM-L12-v2`, published by the authors of the
sentence-transformers library, under the Apache 2.0 licence. It knows about 50 languages, among
them English, French, Spanish, Catalan, Italian and Dutch.

It does one thing: it turns a sentence into a list of 384 numbers, so that **two sentences with the
same meaning get close lists**, whatever their words and their language. "Is the forest closed
today?" and "Est-ce que les massifs sont ouverts aujourd'hui ?" end up close. That is all it knows.
It has never seen a fire, and it does not write.

> 💡 **Tip.** **Checkpoint**: `Key OK`, then `Model ready`.

---

## Part 2 - A model that has learned nothing yet (★, 15 min)

> **Goal**: see what the model does with no training at all, and learn to read a confusion table.

### What you will discover

- A model that only knows "close meanings" already sorts many messages well.
- One number ("28 out of 32") hides which mistakes were made. A table shows them.
- All mistakes are not equal.

### How it sorts without training

`messages/examples.md` holds 40 example messages, 10 per class, in six languages. Without any
training, the sorter takes each test message, finds **the closest example** by meaning, and gives
the test message the class of that example. Nothing has been learned: it only compares.

### What to do

1. Open `messages/examples.md` and `messages/test.md`, side by side. The test messages are different
   from the examples, and some are in other languages.
2. Type:

   ```bash
   ./sorter baseline
   ```

**What you should see**, with the messages as they are in the repository (our test on 2026-10-31):

```text
28 of 32 messages in the right class.

Expected (rows) and chosen (columns):
                 topic      today     urgent  off-topic
      topic        …
```

The rows are the right classes, the columns are what the sorter chose. Everything on the diagonal is
right. Below the table, each mistake is listed, and the last line counts the **emergencies missed**.

> ⚠️ **Important.** **The mistake that matters most is an emergency sorted as something else.** A
> message about the weather sorted as `topic` costs a few tokens. "Help, the field next to us is on
> fire" sorted as `off-topic` gets a polite refusal. Read this line first, every time.

> 💡 **Tip.** **Checkpoint**: you can point, in the table, at the cell of "an emergency sorted as
> off-topic", and say how many messages are in it.

### Think about it

1. Why can a model that has never seen a fire still sort "Au feu !" as urgent?
2. Which would you rather have: 30 right out of 32 with one emergency missed, or 28 right with none
   missed?

---

## Part 3 - Write your examples, and a test for another pair (★★, 25 min)

> **Goal**: give the model the examples that will teach it, in your language, and write an honest
> test.

### What you will discover

- The quality of a fine-tuned model comes from its examples, more than from the computer.
- A test is only honest if the model has never seen its messages.
- Hard examples teach more than easy ones.

### Good examples

The model will learn from every line of `messages/examples.md`. A good set of examples:

- **sounds real**: the way a young person or a resident really writes, with slang, mistakes, no
  punctuation, a single word ("help!!"), or a long story;
- **varies**: different words, lengths and languages for the same class;
- **includes the hard cases**: an emergency that contains a question ("there is smoke, what do I
  do?"), an off-topic message about fire ("light my birthday candles?"), a `today` question that
  does not say "today" ("can we barbecue this weekend?");
- **contains no personal information**: no names, no addresses, nothing about a real person.

### What to do

1. **Add at least ten messages per class** to `messages/examples.md`, in your language, under the
   four headings. Keep the headings exactly as they are (`## topic`, `## today`, `## urgent`,
   `## off-topic`), and start each message with `- `. Save.
2. **Write a test for another pair**: on paper or in the chat of the session, three messages per
   class, in your language, that the other pair has never seen. Give them your messages and receive
   theirs.
3. **Type the messages of the other pair** into `messages/test.md`, under the right headings, in place
   of the starting messages or in addition to them. Save.

> ⚠️ **Important.** **The golden rule: a test message never goes into the examples.** Otherwise the
> test measures memory, not understanding. If a test message is also an example, `./sorter train`
> warns you.

> ℹ️ **Note.** **Why another pair?** You write the examples and you know them: your test messages
> would look like them. Someone else writes the way real users do, with words you did not expect.

> 💡 **Tip.** **Checkpoint**: `examples.md` has at least 20 messages per class (10 from the start, 10
> of yours), and `test.md` has the messages of another pair.

### Think about it

1. Which class was the hardest to write examples for? Why?
2. What message would a young person send that none of your examples looks like?

---

## Part 4 - Fine-tune, test, improve (★★, 25 min)

> **Goal**: fine-tune the model on your examples, see what it learned, and make it better.

### What you will discover

- Fine-tuning a small model takes about a minute, on the processors of the Codespace.
- The confusion table tells you which examples to write next.
- A second round of examples improves the model; more of the same does not.

### What happens during fine-tuning

The method is called **SetFit**. It works in two steps:

1. It makes **pairs** of your examples. Two examples of the same class must get closer, two examples
   of different classes must move apart. The model changes a little, so that its "close meanings"
   become "same class".
2. It then learns a simple rule that draws the borders between the four classes.

That is why a few dozen examples are enough: from 40 examples, it makes about 800 pairs.

### What to do

1. **Before you start, predict** on paper: how many test messages will be right, and how many
   emergencies missed?
2. Run the baseline again, on your new test:

   ```bash
   ./sorter baseline
   ```

3. Fine-tune:

   ```bash
   ./sorter train
   ```

   **What you should see:** `Fine-tuning on … examples (topic …, today …, urgent …, off-topic …)…`,
   a progress bar, then `Fine-tuned in … s`. In our test on 2026-10-31, with the 40 starting
   examples: 62 s.
4. Test:

   ```bash
   ./sorter test
   ```

   **What you should see:** the same table as the baseline, for the fine-tuned model. With the
   messages of the repository, in our test: 32 of 32, no emergency missed, 9 ms per message.
5. **Compare** with the baseline and with your prediction. Write both scores on the board.
6. **Improve**: for each mistake, add two or three examples that look like it (not the test
   message itself) under the right heading. Fine-tune and test again. Write the second score.
7. **Try your own messages**, one at a time:

   ```bash
   ./sorter try "Is it OK to make a campfire tonight?"
   ```

   **What you should see:** the class, the confidence (from 0 to 1), and what a chatbot would do
   with this message. Below 0.5, the sorter says it is not sure.

> ℹ️ **Note.** **Where is the model?** In `~/.workshop-finetune/model`, outside the repository: it
> weighs about 470 MB. It stays in your Codespace until you delete the Codespace.

> 💡 **Tip.** **Checkpoint**: two scores on the board (baseline, fine-tuned), and the number of
> emergencies missed for each.

### Think about it

1. Did the second round of examples help? Which examples made the difference?
2. A score of 100% on your test: is the model perfect? What would you need to know more?

---

## Part 5 - The big model, without training (★★★, 15 min)

> **Goal**: compare your small fine-tuned model with a big model that has never seen your
> examples.

### What you will discover

- A big model sorts well from a short description of the classes, with no examples at all.
- Each message it sorts costs money, takes time, and leaves the Codespace.
- The right choice depends on what you need, not on which model is "better".

### What to do

1. Type:

   ```bash
   ./sorter claude
   ```

   Claude (`claude-haiku-5-5`, the smallest current Claude) receives a description of the four
   classes, then each test message, and answers with one word. It has never seen your examples.

   **What you should see:** the same table, then the time, the tokens and the estimated cost, for the
   test and for 1,000 messages. In our test: TO BE COMPLETED (not measured yet).
2. Fill in the comparison on the board:

   | | Your fine-tuned model | Claude, without training |
   |---|---|---|
   | Right answers on the test | | |
   | Emergencies missed | | |
   | Time per message | about 9 ms | |
   | Cost per 1,000 messages | nothing | |
   | Works without the network | yes | no |
   | Where the message goes | stays in the Codespace | to Anthropic |
   | What it took to set up | your examples, one minute of training | a description of the classes |

> ℹ️ **Note.** **What leaves the Codespace.** With Claude, every message is sent to Anthropic. With
> your small model, nothing leaves: the model runs on the Codespace's processors. For messages that
> young people write, this can decide the choice.

> 💡 **Tip.** **Checkpoint**: the table is full, and you can say in one sentence when you would choose
> each.

### Think about it

1. Your chatbot receives 10,000 messages a month. Which sorter would you use, and why?
2. You add a fifth class next week. What does it take with each?

---

## Part 6 - Closing (15 min)

### Step 1 - Where the pieces go

What you did today, in a real chatbot:

- **A sorter before the chatbot**: `urgent` gets the safety answer at once, `off-topic` a refusal
  that costs nothing, `today` goes to the tool of workshop 4, and only `topic` reaches the big model.
  Feurisson's public version works this way with its FAQ
  ([wikiyouthbot-feurisson](https://github.com/Youth-AI-Lab/wikiyouthbot-feurisson)).
- **The examples and the test** stay useful: when the chatbot is online, the messages it got wrong
  become new examples.
- **The method** works for any short list of classes, in any of the model's languages: the kind of
  question, the topic, the age group it seems to come from, the tone.

### Step 2 - Fill in the exit card

Answer on the card of the facilitator, alone, in a few words:

1. Why can a classifier not invent an answer?
2. Why must a test message never be one of the examples?
3. Name one case where you would fine-tune a small model, and one where you would ask a big one.

---

## Troubleshooting

The common problems (key, Codespace, terminal) are in the
[Troubleshooting of SETUP.md](SETUP.md#troubleshooting).

**`The libraries are not installed yet. Type: ./sorter setup`** - Type it, and wait for
`Model ready`. Each new Codespace needs it once.

**`./sorter setup` stops on a network error.** - Type it again: it starts from where it stopped.

**`… unknown class (line …)`** - A heading of `messages/examples.md` or `messages/test.md` is not
one of the four. They must be exactly `## topic`, `## today`, `## urgent`, `## off-topic`.

**`Each class needs at least 2 examples`** - A heading has fewer than two messages under it, or its
messages do not start with `- `.

**`Warning: … test message(s) are also in the examples`** - Change or remove that message in
`messages/test.md` (or in `examples.md`), then fine-tune again.

**`No fine-tuned model yet. Type: ./sorter train`** - `test` and `try` need a fine-tuned model:
type `./sorter train` first.

**`./sorter claude` says the key was refused.** - Type `workshop-login` and paste your key again.

---

Texts: [CC BY-SA 4.0](LICENSES/CC-BY-SA-4.0.txt). Configuration and programs:
[EUPL-1.2](LICENSES/EUPL-1.2.txt). The model is not ours: Apache 2.0, see its page on Hugging Face.

*Youth AI Lab (Erasmus+) - Workshop 6 of the series "Build your own chatbot" - 2026*
