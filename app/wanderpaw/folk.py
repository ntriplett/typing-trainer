"""Wanderpaw's people (LORE.md): what everyone you can talk to says.

Everyone has a greeting and a line about themselves. What they say about the
town, the Keeper and rumors comes from their own lines if they have any, or
else from their region's shared ones. {town}, {keeper} and {relic} get filled
in. Words only: save.py holds the rules.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Person:
    name: str
    species: str
    hello: str
    who: str
    rumor: str = ""
    extra: tuple[tuple[str, str], ...] = ()  # (what you ask, what they say)


@dataclass(frozen=True, slots=True)
class Hermit:
    person: Person
    place: str  # about where they live
    keeper: str  # about the Keepers
    want: str  # what they'd like: a forage find
    count: int
    ask: str
    thanks: str
    coins: int = 0
    item: str = ""


ASK = {
    "who": "Who are you?",
    "town": "Tell me about your town",
    "place": "Tell me about this place",
    "rumors": "Do you know any rumors?",
    "keeper": "What do you know about the Keeper here?",
    "keepers": "What do you know about the Keepers?",
}
HELP = "Can I help you with anything?"


# --- what people in each town say -------------------------------------------------------

TOWN = {
    "splash": (
        "{town} is all boats and puddles. If your feet are dry, you aren't trying.",
        "Everybody here can swim, even the ones who say they can't.",
        "We used to trade with the {ember} lands every day. Then the ferry broke, and now we just wave.",
        "Fish on Monday, fish on Tuesday. On Wednesday, we have a change and eat fish.",
    ),
    "ember": (
        "{town} never gets cold. The rocks stay warm all night, so everyone sleeps outside.",
        "We light the lanterns at dusk. Every single one. It's the rule, and also it's pretty.",
        "The old tunnel used to bring us visitors. It's been quiet since the cave-in.",
        "Don't touch the rocks by the springs. Or do! Then you'll know why I said that.",
    ),
    "dream": (
        "{town} is a quiet place. Keep your voice down after lunch, and after breakfast too.",
        "Everyone here naps. It isn't lazy. We call it practicing.",
        "On clear nights, the whole town climbs up to count the stars. Nobody has ever finished.",
        "We used to walk the moonlit footbridge to the {leaf} lands. Only a few threads are left of it now.",
    ),
    "leaf": (
        "{town} grows everything! Turnips, carrots, more turnips. It's mostly turnips.",
        "Plant anything here and it comes up by morning. We lost a shovel that way.",
        "Bunnies and goats have been arguing over the hedges for three hundred years. It's going well.",
        "The vine ladder used to take the mail up the cliff. These days the letters come very late.",
    ),
    "shock": (
        "{town} hums. You stop hearing it after a week. Then you can't sleep without it.",
        "Everything here runs on wind and lightning, and most of it runs on time.",
        "When the bell on the hill rings, everyone brings in the washing. A storm's coming.",
        "Our lift once carried folks down to the {splash} lands. Now it just hangs there, looking sorry.",
    ),
}

KEEPER = {
    "splash": (
        "Nerissa, the mermaid? She hasn't come up from her temple in a hundred years. The tides have been gentle, though.",
        "My grandmother said Nerissa used to sing on the rocks. Now you only hear her on very still nights. It's sad music.",
        "They say the Tide Shell keeps the water where it belongs. Nobody here would dare take it.",
        "Nerissa blames herself for the big flood. Everyone forgave her long ago, but nobody ever told her.",
    ),
    "ember": (
        "Solenne, the phoenix, guards the Hearth Flame. Very proud. Very bright. Don't stare!",
        "Solenne was put out once, in the flood. Nobody talks about it where Solenne can hear.",
        "On cold nights, we can see the glow from Solenne's temple. It's nice, in a lonely sort of way.",
        "They say Solenne's temper scorched a whole valley in the Bad Season. Then Solenne cried for a year.",
    ),
    "dream": (
        "Lunelle, the unicorn, watches over our dreams. Have you had a nice one lately? That was Lunelle.",
        "Lunelle thinks everyone is safest asleep. On a good pillow, I agree.",
        "They say the Moon Opal is why no one here ever has a nightmare. I wouldn't want to lose that.",
        "Lunelle's sleep drifted too far, once. A whole garden stopped blooming. They don't talk about it.",
    ),
    "leaf": (
        "Primrose, the fairy, looks after the Evergreen Leaf. She's small. Don't tell her that.",
        "Primrose knows every flower by name. She knows yours too, if you've picked any. Careful.",
        "Her garden went to sleep in the Bad Season. It took years to wake. She's never gotten over it.",
        "Primrose's vines tangled up the dragon's machines, so they say. Then the dragon stopped writing.",
    ),
    "shock": (
        "Old Rumble, the dragon? Loud. Very loud. He sits up there with his machines and shouts at the weather.",
        "Old Rumble hasn't had a visitor in a hundred years. He tells everyone he likes it that way.",
        "The Storm Feather keeps our storms in order. That's why they come on time.",
        "They say Old Rumble's lightning struck the sea, and he and the mermaid haven't spoken since.",
    ),
}

KEEPER_AFTER = {
    "splash": ("The water's restless since the Tide Shell left. But I heard Nerissa singing again, and it wasn't sad.", "You really talked to Nerissa? And she listened? Well, I never."),
    "ember": ("The fires burn wild since the Hearth Flame left. But Solenne's glow looks warmer somehow.", "Solenne has been asking about the neighbors. Solenne! Asking about someone else!"),
    "dream": ("Folks here are having odd dreams since the Moon Opal left. But Lunelle came down and said good morning. Good morning!", "Lunelle's awake, and it's the talk of the town. Quietly, of course."),
    "leaf": ("The weeds are wild since the Evergreen Leaf left. But Primrose smiled at a bunny yesterday. A real smile!", "Primrose has started planting flowers along the road, for whoever might visit."),
    "shock": ("The storms are running late since the Storm Feather left. But Old Rumble fixed the big machine, and it hums all day.", "Old Rumble waved at me. I think it was a wave. It knocked my hat off."),
}

RUMORS = {
    "splash": ("They say a whole boat of lost letters sank off the Isles. Probably just a story.", "The old-timers say the fish swim in circles round the Keeper's temple.", "Somebody's been digging on the beach at night. It's the dog. It's always the dog."),
    "ember": ("They say there's a cave that's warm enough to bake bread. I've had the bread. It's a bit rocky.", "Some nights, one lantern on the far hill lights itself. Nobody lives up there.", "An old story says a wizard walked through the fire once and came out with his hat still on."),
    "dream": ("They say if you dream of a door, you should knock. I always wake up first.", "A mist comes in from the vale at night, and in it you can hear someone counting.", "The stars moved last week. Only a little. Only I noticed."),
    "leaf": ("They say there's a pumpkin out past the woods as big as a house. Someone lives in it.", "The old statue by the road has a hat, and five stones floating over it. Who was it? Nobody knows.", "A seed fell from the sky last spring. It's still growing. We've stopped measuring."),
    "shock": ("They say the machines in the old mine still run at night, all by themselves.", "When the wind's right, you can hear a bell ringing and nobody's there to ring it.", "A letter came last month, a hundred years late. It said: \"Back soon.\" It wasn't signed."),
}


# --- the two quest-givers in each town --------------------------------------------------

GIVERS = {
    ("splash", "splash"): Person("Captain Biscuit", "dog", "", "Captain Biscuit, master of the old ferry! Well. Master of the bank where she's stuck.",
                                 extra=(("How long have you been a captain?", "Since breakfast on my first birthday! I named myself. Nobody argued."),)),
    ("splash", "shock"): Person("Grandpa Shellby", "turtle", "", "Shellby. I'm a hundred and thirty... no, forty. I built the cliffside lift when I was young and fast.",
                                extra=(("What was it like, a hundred years ago?", "Everyone went everywhere. A wizard came through with the mail, every single week. Tumble, his name was. Terrible jokes."),)),
    ("ember", "ember"): Person("Ms. Cinders", "fox", "", "I light the lamps. All of them. I've never once been late, unless you count the mornings.",
                               extra=(("Why do you light so many lamps?", "So that anyone coming home can find the way. Somebody might yet, you know."),)),
    ("ember", "splash"): Person("Sunny Scales", "lizard", "", "Sunny Scales. I lie on warm rocks and I have opinions about which ones are best.",
                                extra=(("Which rock is the best?", "The one you're not on. It's always warmer over there. That's the great sadness of my life."),)),
    ("dream", "dream"): Person("Lady Lulla", "llama", "", "I am Lady Lulla, reader of the stars. They've told me many things. Mostly about you, lately.",
                               extra=(("What do the stars say about me?", "They say a sixth friend is still out there, and that you'll be surprised. They also say you should eat more vegetables."),)),
    ("dream", "ember"): Person("Woolsey", "sheep", "", "I'm Woolsey. I count things. Sheep, mostly. It's a family thing, and it gets awkward at reunions.",
                              extra=(("What are you counting now?", "Three thousand and... oh. You made me lose my place. That's okay. One, two..."),)),
    ("leaf", "leaf"): Person("Nanny Bramble", "goat", "", "Nanny Bramble. I keep the hedges, and the bunnies in line. My grandmother planted that vine ladder.",
                             extra=(("Do you really eat anything?", "Anything but broccoli. And one time, a letter. It was a very boring letter. I've known a mail carrier who says the same."),)),
    ("leaf", "dream"): Person("Clover Hop", "bunny", "", "Clover Hop! I spin! I weave! I wove half the moonlit footbridge, and I talk a lot! Hi!",
                              extra=(("How do you weave moonlight?", "Very, very fast! Before the sun comes up! Otherwise it's just thread, and it's sad about it."),)),
    ("shock", "shock"): Person("Professor Whiskers", "cat", "", "Professor Whiskers, inventor! Doctor of gears! I also nap, but that's for science.",
                               extra=(("What are you inventing?", "A machine that wakes me when it's time for a nap. Early results are confusing."),)),
    ("shock", "leaf"): Person("Zip", "snake", "", "Zip, ssssir! Fastest mail in the land. Only mail in the land, these days. There isn't much of it.",
                              extra=(("Did you know the old mail carriers?", "Pip the goat trained me. Tumble trained Pip. Then Tumble went out with one last bag, and... well. Sssad story."),)),
}


# --- innkeepers and shopkeepers ---------------------------------------------------------

INNKEEPERS = {
    "splash": Person("Mama Paddle", "dog", "Come in, come in! Shake off out there, not in here!", "Mama Paddle. I've run the Soggy Paw for thirty years. The floor has never once been dry.", rumor="A traveler paid me with a shell last week, and it hummed all night."),
    "ember": Person("Hearthy", "lizard", "Sit by the fire! There's always a spot by the fire. It's mostly fire in here.", "I'm Hearthy. I keep the Warm Hearth warm, which is a very easy job around here.", rumor="Guests have been saying the hot springs bubble in a pattern lately. Like someone tapping."),
    "dream": Person("Dozy", "llama", "Mmm? Oh, a guest. Welcome. Don't mind me, I was resting my eyes.", "I'm Dozy, and this is the Sleepy Llama. Nobody's ever complained about the beds. Nobody's ever stayed awake long enough.", rumor="Someone checked in ten years ago and hasn't woken up. Very good review, though."),
    "leaf": Person("Patch", "bunny", "Hello, hello! Carrot soup? It's carrot soup. It's always carrot soup.", "Patch, of the Carrot Patch. Yes, I named it after me. Or me after it. It was a long time ago.", rumor="The goats are planning something. I don't know what. There's been a lot of chewing."),
    "shock": Person("Sprocket", "cat", "Welcome to the Spark and Sprocket. Mind the kettle, it talks.", "I'm Sprocket. The Spark was my partner. He left in a thunderstorm and never paid his share.", rumor="The kettle said a name last night. \"Tumble.\" Then it boiled over."),
}
SHOPKEEPERS = {
    "splash": Person("Shelly", "turtle", "Oh! Hello. Sorry, this net's got me in a knot.", "Shelly. Grandpa Shellby started this shop. I've been untangling his nets ever since.", rumor="Grandpa's lost his reading glasses again. Then again, so has everyone in this family."),
    "ember": Person("Old Cinder", "fox", "Boots, charms, maps! Come in, have a look.", "Old Cinder, of Cinder and Sons. Those are the sons. They'll tell you they're the clever ones.", rumor="Someone bought every map we had of the north. Paid in old coins, from before the Bad Season."),
    "dream": Person("Madame Morrow", "sheep", "Bottles, bottles, everywhere. Do come in, softly.", "Madame Morrow. I brew by moonlight. In daylight, my potions just taste like socks.", rumor="A potion I made last night glows when you say the word \"Heartstone.\" I don't know why I tried that."),
    "leaf": Person("Hopkin", "bunny", "Welcome, welcome! A bit of everything, and a hop away from anywhere!", "Hopkin! I sell everything. If I don't have it, I can grow it. If I can't grow it, you don't need it.", rumor="I sold a seed to a stranger who said it was for an old friend in the middle of the world."),
    "shock": Person("Tick", "snake", "Odd things for odd jobssss. Have a look around.", "They call me Tick. The cat on the counter is the real owner. I just do the talking.", rumor="The cat knows something. The cat always knows something. It won't say."),
}


# --- the houses in each town ------------------------------------------------------------

HOUSES = {
    "splash": (
        Person("Bo", "dog", "Woof! Want to play fetch? No? Okay!", "I'm Bo! I fetch! I've fetched almost everything in this town!", rumor="I buried a bone by the docks. Don't tell anyone."),
        Person("Mossback", "turtle", "No need to hurry. The river will still be here tomorrow.", "Mossback. I've been walking to the market since Tuesday.", rumor="The river's been a little higher. I noticed it two years ago. I'm only now getting around to telling someone."),
        Person("Wren", "dog", "Oh, good! A new person! Have you seen my boat?", "I'm Wren. I built a boat. It's somewhere in the bay, I think, or on it. Hopefully on it.", extra=(("What's your boat called?", "Unsinkable. It was called Unsinkable Two until the first one got found."),)),
        Person("Marina", "mermaid", "Oh! You startled me. I was singing to the fish.", "Marina. Nerissa's my great-aunt. We don't visit. She doesn't visit anyone.", rumor="The fish never sing back. But last night, something far out in the deep did."),
        Person("Tideline", "turtle", "Careful, you're standing on my garden. It's a very small garden.", "I'm Tideline. I grow seaweed, and I measure the tide each morning. It's a slow, happy life.", extra=(("What's the tide doing?", "Going in and out. I'll let you know if it changes its mind."),)),
    ),
    "ember": (
        Person("Rusk", "fox", "Lantern light is the best light. Everyone knows that.", "Rusk. I make lanterns. I've never made a bad one, and I've never made a cheap one.", rumor="Have you seen the rocks glow at night? Like embers! That's new, you know."),
        Person("Basker", "lizard", "Find a warm rock and stay a while.", "I'm Basker. This is my rock. The one over there is my other rock.", extra=(("Isn't it too hot here?", "There's no such thing. I tried to find out once. I got a tan."),)),
        Person("Scarlet", "fox", "Shh! I'm listening to the embers. They pop in patterns.", "Scarlet. I study fire. Everyone else just stares at it, but I take notes.", rumor="My notes say the fires have been restless since the Heartstone flickered. Did you feel that too?"),
        Person("Ashwing", "phoenix", "Oh, hello. Pardon the ash. I've just gotten up.", "Ashwing. Solenne is my cousin. Every hundred years I nap in the ashes. Very refreshing.", rumor="I was alive before the Bad Season. Well, a version of me was. We were all such good friends."),
        Person("Ember Jo", "lizard", "Is it dinnertime? It feels like dinnertime.", "I'm Ember Jo. I cook everything on a hot rock. Eggs, soup, and once, by accident, my hat.", extra=(("How was the hat?", "Chewy. It needed salt."),)),
    ),
    "dream": (
        Person("Stargazer Dill", "llama", "Have you counted the stars tonight? I got to a thousand.", "I'm Dill. I look up. People say I should look where I'm going, but I've been to where I'm going.", rumor="There's a new star over the Heartstone. Or it's an old one, getting brighter."),
        Person("Fleece", "sheep", "I dreamed of a giant carrot. It was delicious.", "I'm Fleece. I dream, and then I write it all down. I have three hundred books about carrots.", extra=(("Do you ever dream of anything else?", "Once, a wizard holding a tiny light in the dark. He looked tired. Then it went back to carrots."),)),
        Person("Hush", "sheep", "Shh... the whole town naps after lunch.", "Hush. That's both my name and what I'd like you to do.", rumor="Whisper it: the Keeper's magic is why we sleep so well. Please don't wake it up."),
        Person("Silverhoof", "unicorn", "Greetings. My horn glows when someone tells the truth. Yours is glowing now.", "Silverhoof. Lunelle is my aunt. We all have a little of the old magic. Lunelle just has rather more of it.", rumor="Lunelle cried in their sleep once, and it rained here for a month."),
        Person("Velvet", "llama", "Oh, hello. Have you tried the pillows? You should try the pillows.", "I'm Velvet. I make pillows. Nobody has ever stayed awake long enough to tell me if they're good.", extra=(("What's in your pillows?", "Moon petals, a little wool, and a very calm thought."),)),
    ),
    "leaf": (
        Person("Nibbles", "bunny", "Carrots! Do you have carrots?", "I'm Nibbles! I like carrots! That's most of what there is to know!", rumor="There's a secret carrot somewhere. The best one. I've been looking my whole life."),
        Person("Old Gruff", "goat", "I'll eat anything. Except broccoli.", "Gruff. I keep the hill clear. Nobody asked me to. I was just hungry.", extra=(("Why not broccoli?", "We had a falling out. I don't want to talk about it."),)),
        Person("Bunty", "bunny", "Every bunny in town has forty cousins. At least. Are you one?", "I'm Bunty. I write down the family tree. It's less of a tree and more of a hedge.", rumor="My forty-first cousin says the weeds grew a foot in one night. The land's waking up, she says."),
        Person("Petal", "flower_fairy", "Oh! Mind your feet! Every flower in town has a name. That one's Gerald.", "I'm Petal. Primrose is my big cousin, though you mustn't call her small. I look after the flowers in town.", rumor="Gerald says a cold wind came through from the middle of the world. Gerald's usually right."),
        Person("Tuft", "goat", "Hello there. I'm just on my way up that wall.", "I'm Tuft. I climb things. Walls, roofs, the mayor. He didn't mind much.", extra=(("Why climb everything?", "You can see the whole land from the top of the mayor. Well, from the top of the hill behind him."),)),
    ),
    "shock": (
        Person("Purrl", "cat", "I'm not napping. I'm thinking with my eyes closed.", "Purrl. I think for a living. Nobody pays me, but I think that's fine.", rumor="I've been thinking about the Heartstone. Something's keeping it lit. Stones don't just do that."),
        Person("Slither", "snake", "Sssome say the wind up here can light a lamp.", "Slither. I keep the wind vanes turning. It's a very twisty job, but I'm the right shape.", extra=(("Can the wind really light a lamp?", "Yesss, if you ask it nicely, and you have a good copper wire."),)),
        Person("Bellwether", "cat", "If the bell rings on the hill, a storm is coming.", "Bellwether. I watch the bell, and I tell everyone when it rings. They can also hear the bell. I tell them anyway.", rumor="The bell rang last week with no storm at all. That's never happened."),
        Person("Sizzle", "dragon", "Don't mind the sparks. I sneeze when I'm happy.", "Sizzle. Old Rumble is my uncle. He's louder. Everyone's louder than me, but he's louder than all of them.", rumor="Uncle keeps an old letter he never finished. He thinks nobody knows."),
        Person("Coil", "snake", "Hold this wire, would you? No, not that end!", "I'm Coil. I wire up the town. Everything here works, and I can only explain about half of it.", extra=(("Which half?", "The half that isn't smoking."),)),
    ),
}


# --- hermits, out in the wilds ----------------------------------------------------------

HERMITS = {
    "camp:0": Hermit(
        Person("Old Barnaby", "turtle", "Oh! A visitor. Give me a minute, I'm turning around.",
               "Barnaby. I walked out here to get away from the noise, about eighty years ago. It was a very slow walk.",
               rumor="On a clear day I can see the Heartstone from my porch. It was brighter when I was young. Everything was.",
               extra=(("What was the Heartstone like back then?", "Like the sun coming up, all day long. Five friends danced around it every spring. I watched them from right here."),)),
        "This is the heartland. It doesn't belong to any one type. That's why the five friends picked it.",
        "I knew them all, back when they'd still come down the road together. They were loud. I miss the noise now.",
        "clover", 3, "I'm making my clover tea, but it takes me all week to reach the clover. Could you bring me 3?",
        "Ahh, that's the stuff. Here, take this. I've been meaning to give it to someone for forty years.", coins=150, item="Energy Tonic"),
    "camp:1": Hermit(
        Person("Mabel Thrum", "sheep", "Come in, dear! Sit, sit. Do you need mittens? You look like you need mittens.",
               "Mabel. I knit. I made mittens for every mail carrier who ever came down this road, and Pip ate three pairs.",
               rumor="Pip told you Tumble never arrived, didn't he? Well, I saw Tumble that last night. He wasn't walking toward any of the temples. He was walking toward the Heartstone.",
               extra=(("What was Tumble like?", "Tall hat, big laugh, five little lights bobbing round his head. He said they were for reading at night. He told the worst jokes in the world, and I'd give anything to hear another."),)),
        "It's quiet out here. The road used to be busy. Now it's me and the crickets, and we've run out of things to say.",
        "They used to come for tea, all five. Old Rumble broke two chairs. I'd love to break out the good chairs again.",
        "clover", 2, "I dye my wool with clover. I can't get out to the far field like I used to. Would you bring me 2?",
        "Lovely, dear. Take these, and don't tell Pip.", coins=200, item="Lucky Charm"),
    "splash:0": Hermit(
        Person("Salty Pete", "dog", "Ahoy! Stand back, I've just painted that.",
               "Salty Pete, keeper of a lighthouse that's nowhere near the sea. I built it in the wrong place. I'm too stubborn to move it.",
               rumor="My light caught something out on the water last month. An old mailbag, floating against the tide.",
               extra=(("Why did you build it here?", "The map was upside down. It's a very good lighthouse for ships sailing through a field."),)),
        "Marsh and reeds, as far as you can see. The frogs are good company, and they never ask about the lighthouse.",
        "Nerissa flooded this whole marsh, back in the Bad Season. She came and fixed my roof after, at night, thinking I wouldn't see.",
        "river shell", 3, "I polish my lamp with crushed river shell. I'm nearly out. Could you bring me 3?",
        "Shining like new! Here's a little something for your trouble.", coins=200, item="Mana Drop"),
    "splash:1": Hermit(
        Person("Auntie Tidewater", "turtle", "Well, look who's come to see me. Take off your shoes. Everything's wet anyway.",
               "Everyone calls me Auntie. I'm nobody's aunt. I collect what the water brings in.",
               rumor="The water brought in a letter last spring. The ink was gone, all but one word: \"sorry.\"",
               extra=(("What's the best thing you've found?", "A boot, with another boot inside it. I've been thinking about that for years."),)),
        "The river brings me everything sooner or later. What the river takes, it gives back downstream.",
        "When Nerissa sings, the whole river goes still. She doesn't know we all stop to listen.",
        "river shell", 2, "I'm finishing a shell wall, and I'm 2 river shells short. Could you find me some?",
        "Perfect! The wall is done. Well, this part of it. Here, take this.", coins=150, item="Ward Potion"),
    "ember:0": Hermit(
        Person("Charcoal", "lizard", "Don't move! ...Oh, you moved. I was drawing you.",
               "Charcoal. I paint with burnt sticks. I've drawn every day of the last forty years, and most of them look the same.",
               rumor="There's a very old painting in a cave near here. Six figures around a glowing stone. People always say five, but count them.",
               extra=(("What do you paint?", "The Bad Season, mostly, from the old stories. One bird, one flood, one sad friend at a time."),)),
        "It's all red rock out here, and the sunsets look like somebody lit the sky. I've never gotten bored of it.",
        "Solenne came by once and looked at my painting of the fire. Didn't say anything. Stood there for an hour.",
        "warm pebble", 3, "I grind warm pebbles for my red paint. I'm all out. Could you bring me 3?",
        "That's the color! Take this. Art doesn't pay, but I do.", coins=200, item="Sneak Cloak"),
    "ember:1": Hermit(
        Person("Old Sootfoot", "fox", "Stay back from the edge, young one. I've seen what happens. Well, I've caused it.",
               "Sootfoot. I fought fires in the Bad Season, when I was a pup. These days I just watch for smoke.",
               rumor="Tumble once walked straight through a burning valley to deliver one postcard. It said, \"Wish you were here.\"",
               extra=(("What was the Bad Season like?", "The water and the fire and the storm, all at once, all by accident. Nobody meant it. That's what makes it so sad."),)),
        "This is a good lookout. From here I can see the whole heath. If anything lights up, I'm the first to shout about it.",
        "Solenne isn't as fierce as all that. Solenne pulled three of us out of the blaze, and was gone before we could say thanks.",
        "warm pebble", 2, "My feet get cold on the night watch. Two warm pebbles in my boots would do it. Could you bring them?",
        "Oh, that's the stuff. My toes thank you. Here, you've earned this.", coins=150, item="Energy Tonic"),
    "dream:0": Hermit(
        Person("Nod", "sheep", "Zzz... the third one... has a hat... oh! Hello. Was I talking?",
               "I'm Nod. I talk in my sleep, and it keeps coming true. That's why I moved out here.",
               rumor="Last night I said, \"He's holding it, he's so tired, tell them to hurry.\" I don't know who I meant. It worried me.",
               extra=(("What else have you said in your sleep?", "That you'd come. That you'd ask me that. And something about turnips, which I still don't understand."),)),
        "The mist comes up at sunset. It's very good for sleeping, and not very good for anything else.",
        "Lunelle visits my dreams sometimes. We don't talk. We just sit by a lake. It's nice, but Lunelle always looks sad.",
        "moon petal", 3, "Moon petals help me sleep without saying anything scary. I need 3. Would you bring them?",
        "Thank you. Now maybe I'll get some quiet sleep. Take this. I dreamed you'd need it.", coins=200, item="Mana Drop"),
    "dream:1": Hermit(
        Person("Madame Vesper", "llama", "You're late. No, wait, you're early. The stars are hard to read today.",
               "Vesper. I keep the sky charts, every star for two hundred years. My mother did it before me.",
               rumor="One small star has been sitting right over the Heartstone for a hundred years and it never moves. It's not on any old chart.",
               extra=(("Can I see your charts?", "You can look. Please don't sneeze. The last visitor sneezed, and we lost a whole constellation."),)),
        "This is the highest point in the vale. You can see every star from here, and on a good night, you can see tomorrow's weather.",
        "They were all born under the same stars, you know, all five. Six, if you count Tumble. I always count Tumble.",
        "moon petal", 2, "I burn moon petals to clear the mist from my lens. Could you bring me 2?",
        "Clear as anything! Here, the stars say this is yours.", coins=150, item="Treasure Map"),
    "leaf:0": Hermit(
        Person("Burdock", "goat", "Mmf. Hello. Sorry. I'm eating a book. It's quite good so far.",
               "Burdock. I read everything, and then I eat it, so I can't lend you anything.",
               rumor="I ate a very old book about the Heartstone. It said a stone like that needs someone to tend it. It tasted of dust and worry.",
               extra=(("What's the best book you've eaten?", "A cookbook. It was like eating twice."),)),
        "The deep woods. The trees don't mind me, and they drop a new leaf whenever I run out of things to read.",
        "I once ate a letter from Primrose to Old Rumble. By mistake! It was the sweetest thing I ever tasted. I've felt bad ever since.",
        "acorn", 3, "I've been reading about acorn jam, and now I can't stop thinking about it. Could you bring me 3 acorns?",
        "Mmm! The book was right. Here, take this. I can't eat it.", coins=200, item="Lucky Charm"),
    "leaf:1": Hermit(
        Person("Thimble", "bunny", "Hi! Do you want to see my pumpkin? You're standing in it!",
               "I'm Thimble! I grew a pumpkin, and then I moved in. It's very roomy, and I'm never hungry.",
               rumor="My pumpkin grew twice as fast after the Heartstone flickered. Things are stirring. It's so exciting!",
               extra=(("What happens when the pumpkin goes bad?", "I grow another one! I've moved eleven times. The neighbors think I'm very fancy."),)),
        "This is my patch! Everything out here grows big. There's a turnip over there I'm a little scared of.",
        "Primrose came to see my pumpkin! She said it was \"adequate.\" That's the nicest thing anyone's ever said to me!",
        "acorn", 2, "I'm building a pumpkin door, and I need 2 acorns for the handles. Can you get some?",
        "Yay! A door! I've never had a door! Here, here, take this!", coins=150, item="Ward Potion"),
    "shock:0": Hermit(
        Person("Cog", "cat", "Stand clear! It's perfectly safe! Probably! Oh, hello.",
               "Cog. I was Professor Whiskers' best student, before the incident. We don't speak of the incident. It was a very small crater.",
               rumor="I built a machine to listen to the Heartstone. It's making a tiny sound. Like somebody humming to keep awake.",
               extra=(("What are you building?", "A mail machine! It'll deliver every letter in the land by itself. So far it has delivered one wall."),)),
        "The windiest ridge in the land. Everything here's bolted down, including my lunch.",
        "Old Rumble has the finest machines ever made. Primrose's vines wrecked them, and he's been fixing them alone ever since. He won't take help. I've offered.",
        "spark berry", 3, "Spark berries make a fine little battery. I need 3. Would you bring them?",
        "It's working! It's smoking, but it's working! Here, take this before it stops.", coins=200, item="Mender's Feather"),
    "shock:1": Hermit(
        Person("Whistle", "snake", "Sssh, listen. Do you hear the wind? It's saying something. No, wait, that's just the wind.",
               "Whistle. I keep the storm rod, up on the peak. When the lightning comes, I'm the one who sends it somewhere safe.",
               rumor="I found a mitten up here, a hundred years old, hand-knitted. It's still warm. I don't know why it's still warm.",
               extra=(("Isn't that dangerous?", "Very! But sssomebody has to, and I don't have any hair to lose."),)),
        "From up here, you can see all five lands on a clear day. They look so close together. You'd never know they don't talk.",
        "Old Rumble roars at the storms, but I've seen him sitting up there at night, just looking at the sea.",
        "spark berry", 2, "Spark berries keep my storm rod sharp. I need 2. Could you bring them up for me?",
        "Now that's a fine rod. Take this, and stay low when you go down.", coins=150, item="Full Mana Potion"),
}


def pick(pool: tuple[str, ...], name: str) -> str:
    """Their line from a shared pool: always the same one for the same person."""
    return pool[zlib.crc32(name.encode()) % len(pool)]


def seed_of(name: str) -> int:
    """Their looks."""
    return zlib.crc32(f"wanderpaw-folk:{name}".encode()) % 2**31
