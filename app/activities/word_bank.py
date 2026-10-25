"""Short, everyday words for "Real words!" pages. A lesson only uses the
words it can spell entirely with keys the learner has been taught.
"""

from __future__ import annotations

import random

WORDS: tuple[str, ...] = tuple(
    dict.fromkeys(
    """
    a as ad add ads dad dads sad lad lads fad all fall falls hall halls ask asks lass flask salad
    alfalfa glad gas flag flags has had half hall dash flash shall ash lash sash gal gals hag
    jag jab lag lags slag slab

    the and to of in is it you that he was for on are with his they at be this have from or one
    had by but not what all were we when your can said there use an each which she do how their
    if will up other about out many then them these so some her would make like him into time
    has look two more write go see no way could people my than first water been call who now
    find long down day did get come made may part over new sound take only little work know
    place year live me back give most very after thing our just name good sentence man think
    say great where help through much before line right too mean old any same tell boy follow
    came want show also around form three small set put end does another well large must big
    even such because turn here why ask went men read need land different home us move try
    kind hand picture again change off play spell air away animal house point page letter
    mother answer found study still learn should world high every near add food between own
    below country plant last school father keep tree never start city earth eye light thought
    head under story saw left few while along might close something seem next hard open
    example begin life always those both paper together got group often run important until
    children side feet car mile night walk white sea began grow took river four carry state
    once book hear stop without second later miss idea enough eat face watch far really almost
    let above girl sometimes mountain cut young talk soon list song being leave family

    cat dog sun fun red bed pig hat sat mat fish dish wish jump hop top pop mad sit fit kit
    lid hid dig fig wig jig gift lift soft frog log fog hog jar star art arm farm park dark
    bark shark hike bike kite rice nice mice ice slide ride hide wide tide lime fire tire desk
    task mask fork sky fly dry cry spy shy key toy joy hay lay ray stay tray clay jelly happy
    puppy kitty silly funny sunny jolly jet net pet wet vet yes yet hill fill still kid tall
    wall ball doll pull full bell sell tell yell well fell jog hug rug bug mug cup pup jam ham
    ram yam zoo zip zap box fox six mix fix wax ox quiz quit queen quick van vest very cave
    wave save gave brave game name same tame lake cake bake make take rake snake shake apple
    pear plum nut seed leaf leaves acorn pumpkin pie fall autumn cozy warm sweater scarf mitten
    owl bird nest egg hen duck goose sheep goat cow horse pony llama bunny fox deer bear moon
    rain snow wind cloud storm pond lake creek boat fishing rod hook worm berry jam toast bread
    milk tea soup corn bean farm barn gate fence path road map

    glass salsa slash flash flasks salads shells skill skills spill drill grill dress kiss
    hello jelly happy sleepy kitten mitten garden basket blanket pillow window shadow yellow
    purple orange silver golden rabbit turtle monkey donkey parrot puppet rocket planet comet
    castle tunnel bridge forest meadow valley island desert jungle canyon harbor market
    pirate wizard dragon knight goblin unicorn robot sticker crayon pencil marker eraser
    cookie muffin waffle pancake noodle pickle carrot potato tomato cherry banana lemon melon
    peach grape honey butter cheese pretzel popcorn sandwich picnic sprinkle cupcake
    camping hiking skating sledding fishing jumping running sliding hopping digging
    building climbing painting reading singing dancing baking cooking riding swimming
    friend family sister brother grandma grandpa teacher neighbor helper player
    blocks crafts puzzle marble kitty jigsaw bubble giggle wiggle jiggle tickle sparkle
    lantern compass treasure backpack sleeping campfire firefly ladybug beetle spider
    feather pebble pinecone acorns maple branch flower flowers petal sunflower daisy
    raindrop rainbow thunder breeze frosty chilly snowman snowball icicle puddle
    pumpkins scarecrow harvest hayride tractor chicken rooster piglet kitten hamster
    goldfish squirrel chipmunk raccoon hedgehog badger beaver otter falcon eagle robin
    sparrow crows magic potion wonder secret quest level score bonus power super
    jolly fluffy cuddly sleepy grumpy silly speedy sneaky clever brave gentle mighty
    """.split()
    )
)


def words_for(new_keys: list[str], known_keys: list[str], count: int, rng: random.Random) -> list[str]:
    """Up to `count` different words spelled only with `known_keys` + `new_keys`,
    each using at least one new key.
    """
    allowed = set(known_keys) | set(new_keys)
    fits = sorted({w for w in WORDS if set(w) <= allowed and set(w) & set(new_keys)})
    return rng.sample(fits, min(count, len(fits)))
