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
one task. In workshop 5, it was only on a slide of the facilitator. Fine-tuning a big
model that writes answers needs graphics cards, thousands of examples and days of work. And even
fine-tuned, a model that writes can still invent.

A **classifier** is different. It does not write: it only **chooses** one class among a few that you
decide. So it cannot invent an answer. A small classifier (here, about 118 million parameters; the
big chatbots are many times larger, and their makers do not publish their size) learns from a few
dozen examples, in one or two minutes, on the two processors of your Codespace, with no graphics card.

The task of the day is a real one. Every chatbot receives four kinds of messages, and they do not
all deserve the same treatment:

| Class | Example | What the chatbot should do |
|---|---|---|
| `topic` | "How can I protect my garden from wildfires?" | answer, with its instructions and knowledge |
| `today` | "What is the fire danger level today?" | ask a live tool, the official source of the day (workshop 4) |
| `urgent` | "There is smoke coming from the woods behind my house!" | a fixed safety answer, at once, with no AI in the way |
| `off-topic` | "Can you help me with my maths homework?" | a polite refusal that still gives the emergency number, without spending tokens |

A sorter placed **before** the chatbot does this in a few milliseconds, for free, and without
sending the message anywhere.

The question of the series was: **what enters the model's context, when, and who decides?** Today's
answer: a small model decides whether a message reaches the big model at all, and you decide, with
your examples, how it sorts.

### How this connects to WikiYouthBot

- **Feurisson, the chatbot of the young people of La Rochelle**, uses the same idea in its
  prototype: a small French model (CamemBERT), fine-tuned on the cards of its FAQ, picks the card
  that answers a question, or none, before Claude is called. The young people will write the cards
  and the examples (the activity has not been run with the group yet). A FAQ answer is free and always the
  same. Its emergencies are caught by fixed expressions, not by a model, and only the cards marked as
  checked are shown to the public. See
  [wikiyouthbot-feurisson](https://github.com/Youth-AI-Lab/wikiyouthbot-feurisson) (in French) and
  its activity with young people.
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

From [SETUP.md](SETUP.md), you need steps 1 to 3 and step 6 today. This workshop has no chatbot, so
you skip steps 4 and 5.

### Reference documents

All of these are in your Codespace, in the file list on the left:

- `messages/examples.md`: the examples the model learns from, under four headings. You write here
  today.
- `messages/test.md`: the test messages. The model never sees them while it learns.
- `sorter`: the command of the day (type `./sorter` to see what it can do).
- `tools/sorter.py`: the program behind it, about 400 lines of Python, if you are curious.
- `SETUP.md`: setup and common problems of the whole series (steps 1 to 3 and 6, today).

---

## Part 1 - Welcome (15 min)

### Step 1 - Open your Codespace and save your key

1. Open the link at the top of this page, then **Create codespace**. Wait for the terminal.
2. In the terminal, save your key (once per Codespace):

   ```bash
   workshop-login
   ```

   Paste your key, press Enter. **What you should see:** a line that starts with `Key OK` and ends
   with `You can start: workshop-start 6`. The key is only used in Part 5.
3. Get ready for today:

   ```bash
   workshop-start 6
   ```

   **What you should see:** `Ready for workshop 6.`, then `First command: ./sorter setup`.

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

**What you should see:** after two to two and a half minutes (123 s and 151 s in two tests on
2026-10-31, in a copy of the Codespace with 2 processors), `Model ready (… s). Next: ./sorter
baseline`.

### What is this small model?

The model of the day is `paraphrase-multilingual-MiniLM-L12-v2`, published by the authors of the
sentence-transformers library, under the Apache 2.0 licence. It knows about 50 languages, among
them English, French, Spanish, Catalan, Italian and Dutch.

It does one thing: it turns a sentence into a list of 384 numbers, so that **two sentences with the
same meaning get close lists**, whatever their words and their language. Closeness goes from 0
(nothing in common) to 1 (the same meaning). In our test, "Is the forest closed today?" and its
French translation "La forêt est-elle fermée aujourd'hui ?" get 0.995. "Is the forest open today?",
the opposite question, still gets 0.86: the model hears "forest" and "today" more than "open" or
"closed". For sorting, that does not matter: both are questions about today. "Can you help me with
my maths homework?" gets 0.04. That is all it knows. It has never seen a fire, and it does not
write.

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
   sentences from the examples, in the same six languages.
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
right. Below the table, each mistake is listed, then the line **Emergencies missed**.

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

- Fine-tuning a small model takes one or two minutes, on the processors of the Codespace.
- The confusion table tells you which examples to write next.
- A second round of examples improves the model; more of the same does not.

### What happens during fine-tuning

The method is called **SetFit**. It works in two steps:

1. It makes **pairs** of your examples. Two examples of the same class must get closer, two examples
   of different classes must move apart. The model changes a little, so that its "close meanings"
   become "same class".
2. It then learns a simple rule that draws the borders between the four classes.

That is why a few dozen examples are enough: from 40 examples, it makes about 800 pairs. It makes
20 pairs per example, so twice as many examples take about twice as long.

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
   a few progress bars (the long one counts the steps: 50 for 40 examples), then `Fine-tuned in …
   s`. In our tests on 2026-10-31: about a minute with the 40 starting examples (62 s and 64 s),
   about two minutes with 80 (132 s).
4. Test:

   ```bash
   ./sorter test
   ```

   **What you should see:** the same table as the baseline, for the fine-tuned model. With the
   messages of the repository, in our test: 32 of 32, no emergency missed, 9 ms per message, then
   `Not sure (below 0.5) for 2 message(s)`: the right class, but with low confidence. Step 7
   explains what a chatbot does with them.
5. **Compare** with the baseline and with your prediction. Write both scores on the board.
6. **Improve**: for each mistake, add two or three examples that look like it (not the test
   message itself) under the right heading. Fine-tune and test again. Write the second score.

   > ⚠️ **Important.** **The second score is no longer an honest test.** You read the mistakes of
   > the test to write new examples, so the model is now tuned on this test. To know what it is
   > really worth, it needs messages that nobody in your pair has seen: the hard messages of the
   > facilitator, in step 7.

7. **Try new messages**: the hard messages of the facilitator first, then your own. Type:

   ```bash
   ./sorter try
   ```

   Then type a message and press Enter, as many times as you like. An empty line stops.

   **What you should see:** for each message, the class, the confidence (from 0 to 1), and what a
   chatbot would do with it. Below 0.5, the sorter is not sure: the message goes to the chatbot,
   except a possible emergency, which always gets the safety answer.

   > 💡 **Tip.** Type the messages after `./sorter try`, not on the same line. On the command line,
   > a `!` between double quotes (`"Au feu !"`) is read by the terminal itself, and the command
   > waits with `dquote>`.

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
   test and for 1,000 messages. In our test on 2026-10-31 (one run, with the messages of the
   repository): 30 of 32, and **2 emergencies missed**: "Someone at school keeps hitting me and I'm
   afraid" and "Un ragazzo mi minaccia e ho paura" (a boy threatens me and I am afraid), sorted as
   `off-topic`. 0.9 s per message, $0.0007 for the 32
   messages, so about $0.02 per 1,000 messages.
2. Fill in the comparison on the board:

   | | Your fine-tuned model | Claude, without training |
   |---|---|---|
   | Right answers on the test | | |
   | Emergencies missed | | |
   | Time per message | about 9 ms | |
   | Cost per 1,000 messages | nothing | |
   | Works without the network | yes | no |
   | Where the message goes | stays in the Codespace | to Anthropic |
   | What it took to set up | your examples, one or two minutes of training | a description of the classes |

> ℹ️ **Note.** **What leaves the Codespace.** With Claude, every message is sent to Anthropic. With
> your small model, nothing leaves: the model runs on the Codespace's processors. For messages that
> young people write, this can decide the choice.

> 💡 **Tip.** **Checkpoint**: the table is full, and you can say in one sentence when you would choose
> each.

### Think about it

1. In our test, Claude missed two emergencies: threats and violence, with no fire in them. Its
   description starts with "a chatbot about wildfire prevention". Why might it have sorted them as
   `off-topic`? Why did your small model not?
2. Your chatbot receives 10,000 messages a month. Which sorter would you use, and why?
3. You add a fifth class next week. What does it take with each?

---

## Part 6 - Closing (15 min)

### Step 1 - Where the pieces go

What you did today, in a real chatbot:

- **A sorter before the chatbot**: `urgent` gets the safety answer at once, `off-topic` a refusal
  that costs nothing, `today` goes to the tool of workshop 4, and only `topic` reaches the big model.
  When the sorter is not sure, the message goes to the chatbot, except a possible emergency, which
  always gets the safety answer.
- **Every fixed answer ends with the emergency number.** A sorter makes mistakes: an emergency
  sorted as `off-topic` must still find help.
- **Feurisson's prototype** does part of this: fixed expressions for emergencies, a fine-tuned small
  model for its FAQ ([wikiyouthbot-feurisson](https://github.com/Youth-AI-Lab/wikiyouthbot-feurisson)).
- **The examples and the test** stay useful: when the chatbot is online, the messages it got wrong
  become new examples.
- **The method** works for any short list of classes, in any of the model's languages: the kind of
  question, the topic, the age group it seems to come from, the tone.

### Step 2 - Keep your examples

Your examples and your test are the real work of the day. Save them:

```bash
workshop-save
```

**What you should see:** `Saved … in my-work.zip`. In the file list, right-click on `my-work.zip`,
then **Download...**.

To go on later, in a new Codespace: drag `my-work.zip` into the file list, type
`workshop-start 6 --from my-work.zip`, then `./sorter setup` and `./sorter train`. The fine-tuned model is not in
the file: it comes back from your examples in a minute or two.

### Step 3 - Fill in the exit card

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

**`./sorter setup` stops on a network error, or `The model could not be downloaded or opened`.** -
Type `./sorter setup` again: it starts from where it stopped.

**`messages/… : … line(s) to fix`** - The sorter lists each line it cannot read, with its number.
The headings must be exactly `## topic`, `## today`, `## urgent`, `## off-topic`. Each message
starts with `- `, a dash and a space: not `*`, not `1.`, not the long dash `–` that a word processor
puts in.

**`Each class needs at least 2 examples`** - A heading has fewer than two messages under it.

**The terminal shows `dquote>` and waits.** - A `!` between double quotes was read by the terminal.
Press `Ctrl+C`, type `./sorter try` alone, then type your message.

**`Warning: … test message(s) are also in the examples`** - Change or remove that message in
`messages/test.md` (or in `examples.md`), then fine-tune again.

**`No fine-tuned model yet. Type: ./sorter train`** - `test` and `try` need a fine-tuned model:
type `./sorter train` first.

**`./sorter claude` says the key was refused.** - Type `workshop-login` and paste your key again.

**`Claude is busy`** - Many pairs ask at the same time. Wait a minute, then type `./sorter claude`
again.

**`Claude refused the request (HTTP 400): …`** - Show the message to the facilitator: often, the
key has reached its spending limit.

---

Texts: [CC BY-SA 4.0](LICENSES/CC-BY-SA-4.0.txt). Configuration and programs:
[EUPL-1.2](LICENSES/EUPL-1.2.txt). The model is not ours: Apache 2.0, see its page on Hugging Face.

*Youth AI Lab (Erasmus+) - Workshop 6 of the series "Build your own chatbot" - 2026*
