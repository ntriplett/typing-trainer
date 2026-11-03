# Wanderpaw: the lore

The story bible. Game text should agree with this file. Agreed 2026-11-02; names and numbers marked
*(draft)* can still change.

The reader is about 9 years old. Short sentences, gentle stakes, nobody dies, and no timer: the
Heartstone fades over years, so a kid playing 15 minutes a day is never late.

## The story in short

Five friends fell out, and the land is slowly coming apart because of it. The player finishes the job
of the mail carrier who should have fixed it 100 years ago: win each friend's trust, read them a lost
letter, and carry the five relics back to the Heartstone.

## The old days

Five friends gave one relic each to the Heartstone, in the middle of the world, and it kept the land
in balance. A sixth friend, **Tumble**, was the **Wanderpaw**: he walked between the lands carrying
their letters, and kept them all talking.

## The Bad Season

One terrible season, each friend hurt the next by accident, in a ring. This is also why the types beat
each other the way they do.

| Who | Did what | Type |
|---|---|---|
| Nerissa, mermaid | Her flood put out Solenne's fires | {splash} beats {ember} |
| Solenne, phoenix | Their blaze scorched Lunelle's glades | {ember} beats {dream} |
| Lunelle, unicorn | Their sleep stopped Primrose's gardens growing | {dream} beats {leaf} |
| Primrose, fairy | Her vines choked Old Rumble's machines | {leaf} beats {shock} |
| Old Rumble, dragon | Their lightning struck Nerissa's sea | {shock} beats {splash} |

That night, all five sat down and wrote "I'm sorry". Tumble set off with the bag and never arrived.
With no letters, each friend decided the others were still angry. Each took their relic home, built a
temple around it, and stayed. The Heartstone began to fade.

**The secret:** Tumble went into the Heartstone to keep its last ember lit. He has been in there ever
since. Nobody knows.

## The Keepers (the five bosses)

The five friends are now the **Keepers**. They aren't evil, and they're partly right: since the
Heartstone dimmed, each relic is the only thing keeping its land calm. A Keeper can't leave and won't
let go.

| Keeper *(draft names)* | Land | Relic | Key | Why they refuse |
|---|---|---|---|---|
| Nerissa, mermaid (she) | {splash} | Tide Shell | Tide Pearl | Guilt: "If I let go, the water rises again." |
| Solenne, phoenix | {ember} | Hearth Flame | Sun Ember | Pride: "I won't be put out twice." |
| Lunelle, unicorn | {dream} | Moon Opal | Moon Feather | Fear: "Everyone is safe while they sleep." |
| Primrose, fairy (she) | {leaf} | Evergreen Leaf | Oak Seed | Protective: "My garden only just grew back." |
| Old Rumble, dragon | {shock} | Storm Feather | Thunder Key | Lonely: "They all left. Nobody ever came." |

How the rules fit the story:

- **The fight is a test, not a war.** A Keeper wants proof you can carry the relic. They end up worn
  out, like any creature, and nobody is hurt.
- **Taking a relic makes everything 2 levels harder.** Lifting it really does let the wild loose, and
  the other Keepers feel it and brace themselves. So they were right to worry, and only all five
  together fixes it.
- **The hidden keys.** Each Keeper hid their key instead of destroying it, because part of them hoped
  someone would come.
- **The door wants a pet of its type.** Only a friend of that land may knock.
- **The Elder buff** is the Keeper's blessing on your pet.
- **The game can be played in any order,** so no Keeper's lines may assume which relics you have. They
  can react to how many ("I felt you take the second one").

## The rest of the world

- **The five shortcuts** (ferry, tunnel, footbridge, ladder, lift) are the lands drifting apart.
  Mending them is the story in small: lands reconnecting.
- **Towns** hold only their own region's animals, have stopped crossing over, and grumble about the
  neighbors. Your mixed party of all five types is a startling sight.
- **Wild creatures** are stirred up, not bad. A beaten creature calms down, which is why befriending
  works.
- **Old-timers carry the history:** Grandpa Shellby built the lift 100 years ago, Lady Lulla says the
  stars said you would come, and Zip misses the mail.
- **The statue** of "a pet you don't know" becomes Tumble: change it to a worn stone figure in a tall
  hat, with five round stones floating over his head.

## The player

- A new Wanderpaw. By old custom a Wanderpaw may walk in any land.
- **Why only you:** Keepers can't leave and townsfolk won't cross. You're the first person in
  generations traveling with all five types.
- **Why you'd want to:** the bag was left "for the next Wanderpaw", and you have letters to deliver and
  a mystery to solve.

## The hook and tutorial

**Pip** *(draft)*, a goat and retired mail carrier, lives beside Camp. "I only ever ate the boring ones."

1. **The hook.** You arrive at Camp. The Heartstone flickers, for the first time in 100 years. That
   night Tumble's old bag turns up, holding five sealed letters and a tag: "for the next Wanderpaw."
   Pip explains in short keyboard-only pages. **Nothing is typed in this part;** it's just reading.
2. **Walking.** Pip walks you through typing to move, and going in with Enter.
3. **The books.** The map first, then the guidebook.
4. **A first fight.** A small, easy creature near Camp, with a few lines of help as you go: pick a move
   by typing its word, then what the types mean. It can't go badly.
5. **Off you go.** Pip points you to the nearest town.

Pip stays beside Camp. Talking to him offers the story again, the tutorial again, and his reaction to
each relic you've found.

## Reading the letter

The order at every temple:

1. Open the door with the key and a pet of its type (as now).
2. The Keeper refuses, and you fight.
3. **Win.** The win is saved, and this Keeper never has to be fought again.
4. Talk to them. They finally take the letter and ask you to read it to them.
5. **Type the letter**, one line at a time.
6. Get **the relic and the loot**. The world gets 2 levels harder only now.
7. The Keeper stays in the temple as a friendly NPC, like the townsfolk.

### Keeping it from being frustrating

Rules for the typing:

- **The ink fills in what you haven't learned.** You only type letters you've been taught, plus spaces.
  Everything else (untaught letters, capitals, punctuation, numbers) writes itself, shown in a soft ink
  color, and the cursor glides past it. The letter reads the same for everyone. A kid on home row keys
  types fewer of the characters and still sees the whole letter.
- **"Taught" is the same list that walking uses** (`_wander_words`), including its home-row fallback.
- **No timer, no score, no fail.** A wrong key just waits for the right one.
- **Saved line by line.** Esc leaves at any time. Come back and you continue from the same line.
- **No energy cost.** Worn-out pets don't matter here.
- **An easy way back.** Winning counts as resting at the temple's campfire, so the next trip wakes you
  at the door, not back across the map.
- It uses `prompt_view.js`, following the prompt display rules: plain spaces, one line at a time.

### The reward *(draft numbers)*

It should feel big. Boss wins pay 25 coins + level today, and the temple pays 300 XP.

- The relic and the Elder blessing.
- **1,500 coins,** a real shop trip.
- **1,000 XP** for the party (up from 300).
- **A keepsake:** a permanent item, unique to each Keeper, useful on the map. These stay out of
  battles, so they don't disturb the boss tuning.

| From | Keepsake | Does |
|---|---|---|
| Nerissa | Rippling Pearl | Wading a ford costs no extra energy |
| Solenne | Warm Ash | Resting at a campfire gives back 15 more energy |
| Lunelle | Dream Pillow | Every day starts with 15 more walking energy |
| Primrose | Seed Pouch | Forage spots give one extra |
| Old Rumble | Spark Compass | Twitches when you walk into a place with an unopened chest |

### The Keeper's relative

After the relic, a younger relative of the Keeper peeks out and asks to come along: Coralie (Nerissa's
sister), Cinderling (Solenne's cousin), Starling (Lunelle's cousin), Tansy (Primrose's sister) and
Little Grumble (Old Rumble's nephew).

- Free, no mana. Say yes and they go to Camp at level 13, if there's a spot.
- If Camp is full, you say no, or they ever leave Camp, you can ask again at the temple, and it's the
  same one.
- A Friendship Token at Camp makes them a real pet, after which they stop asking.

So every mythical can be had for sure: one Keeper's relative plus one token.

### The letters

Each is an apology from the friend who hurt them. In the game, the greeting and signature write
themselves.

**To Solenne, from Nerissa**
> I never meant to put out your fires.
> The water rose too fast and I was scared.
> Please come home. I miss your light.

**To Lunelle, from Solenne**
> I burned your moonlit glade, and I think of it every day.
> The fire got away from me.
> I would plant it all again if I could.

**To Primrose, from Lunelle**
> My sleep drifted over your garden.
> I only wanted everyone to rest.
> Your flowers deserve to wake up. I am so sorry.

**To Old Rumble, from Primrose**
> My vines choked your wonderful machines.
> I should have asked first.
> I wish I could hear them hum again.

**To Nerissa, from Old Rumble**
> My lightning struck your sea.
> I roared when I should have listened.
> It is too quiet up here without you.

After reading, the Keeper is quiet for a moment, then: "They wrote this... that same night?" Late in
the game, a Keeper can realize the others got letters too.

## How the player learns all this

- **Pip:** the opening, reminders, and a reaction to each relic.
- **Townsfolk and hermits:** the talk menu (see "Talking to people").
- **Keepers:** before and after their fight, and any time afterward as friendly NPCs.
- **Carvings and ruins:** the `LORE` lines become pages collected in the guidebook.
- **Shrines:** the typed lines become verses of the friends' old song.

## Talking to people

Everyone you can talk to shows their picture, says only a greeting, then offers a numbered menu: who
are you, tell me about your town (or this place), any rumors, what about the Keeper, and sometimes a
question of their own. Words live in `app/wanderpaw/folk.py`.

- **Quests are separate from bridges.** "Can I help you with anything?" starts the fetch quest for
  their lost thing, and bringing it back earns a favor: they'll train a pet a level, and you learn where
  the temple key is hidden.
- **Bridge repair is its own job.** Find a broken shortcut and your journal says who to ask. Once you've
  helped one of its two quest-givers, ask them to take it on and bring a part from each side. Asking
  before you've helped starts with the lost thing.
- **Rumors are useful.** Each person has some gossip, then points you to who knows about the key, and
  to a hermit (marked on your map and in your journal).
- **Keeper talk changes** once that land's relic is gone.
- **Quest item names** are underlined and colored everywhere you read them.

**Towns** have 8 to 10 buildings: two quest-givers, a notice board, an inn, a shop, and up to five
houses of named neighbors. Each town has a distant relative of its Keeper: Marina, Ashwing, Silverhoof,
Petal and Sizzle.

**Hermits** live out in the wilds, two in each land and two in the heartland, 12 in all. Each has a
story and a small favor (bring a few local finds, get coins and an item). Pip knows the heartland ones.
Between them they carry the clues about **Tumble**: Mabel saw him walking toward the Heartstone, Burdock
read that the stone needs tending, Cog hears humming inside it, Vesper charts a star that never moves,
and Nod talks in their sleep.

## Side quests and bad guys

- **No dark lord.** The quarrel is the enemy.
- **Letter runs** *(later)*: side quests carrying letters between towns, such as Captain Biscuit to Ms. Cinders.
- **A comic rival** *(optional, later):* a vain relic-hunting fox who always arrives just behind you.

## The ending

All five relics go into the pillars. The Keepers come to the hall and see each other for the first time
in 100 years. The Heartstone wakes, and **Tumble** steps out, an elementalist wizard with five floating
orbs over his head, one for each type. "You took your time. Good. It's a long walk."

The land calms: **the +10 levels from the relics go away.** You're now truly the Wanderpaw.

*Built 2026-11-03:* the pages are `lore.ENDING`, with the five friends and Tumble in front of the Heartstone. Dropping the relic levels is left for a later version (v1.x), along with the challenge arena.

## After the ending (later, not now)

- **Challenge arena:** appears after you finish the game, for trying out hard fights.
- Friendship Tokens restock once (already decided).

## Build notes

- `save["bosses"]` and `save["temples"]` already separate "won" from "has the relic", and `relics_out`
  counts relics, so the letter fits between them and the +2 lands in the right place.
- Needs new: letter progress per temple, Keeper NPC screens, keepsakes, Pip and the tutorial, Tumble's
  art, dropping the relic levels once `finished` is set.
- Terms: "Keeper" in the story. `terms.py` still says "Boss" and the temple text says "guardian", so
  those need a decision when the text is written.
- **Existing issue:** shrine lines are fixed text, so they can ask for letters a kid hasn't learned.
  The ink-fill rule should apply to shrines and fishing lines too.
