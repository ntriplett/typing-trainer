// How pets move around a scene (PLAN.md 11i, 11j), shared by the Pets hub,
// the habitats, and the Pet Shop's rooms. Each pet is a small state
// machine: idle, walk (wander, go to a prop, go sit by a friend), nap, hop,
// chase/run (play), leap (up onto a ledge or back down), swim, splash, fly
// (where area.sky says so), and a prop's own action (bask, nap, dig, jump in). Its personality picks what
// it does next and how:
//   energy   walks and animates faster, hops and leaps more, rests less
//   sleepy   naps more often, and longer
//   friendly goes to sit near other friendly pets; shy ones keep away
//   curious  walks over to the scene's props
//   playful  hops, chases other playful pets, splashes in water
// and its species leans some ways too (CLIMBERS, SWIMMERS, BASKERS).
// Positions are in scene units: x is a pet's left edge, y its feet.
//
//   const world = PetMotion.create(pets, area, scale);
//   setInterval(() => PetMotion.step(world), 120);
//   PetMotion.draw(world, px, {ctx, unit, tags});  // px(x, y, w, h, color) in scene units
//
// area: {left, right, top, bottom, props, terrain}. top..bottom is where
// feet can be on the ground. sky: true is a pet's real home (a habitat): FLIERS
// take to the air there, and mermaids live in its biggest pool. Anywhere else
// a grown mermaid just sits and flicks her tail.
// props: [{id, x, y, action, ledge, who}], action
// one of look (default), bask, nap, dig, jump; ledge: the ledge it's on.
// terrain (all optional, rects in feet coordinates):
//   water:  [{x, y, w, h, color}]  swimmers swim in it; others go around or hop across
//   blocks: [{x, y, w, h}]         no feet in here (rocks, trunks, furniture)
//   ledges: [{x0, x1, y, who}]     raised walkways pets leap up onto
// `who` (props and ledges, optional): the species allowed (a bed for cats
// and bunnies); everyone when left out.
//
// PetMotion.drawOne(world, w, px, opts) draws one pet, for scenes that layer
// pets between their own things (the bedroom's furniture).

const PetMotion = (() => {
  // how much each species likes to climb, swim, or bask (added to its odds)
  const CLIMBERS = { goat: 1.4, cat: 0.9, lizard: 0.8, sheep: 0.5, llama: 0.5, fox: 0.5, dragon: 0.5, unicorn: 0.3 };
  const SWIMMERS = { turtle: 1.6, dog: 0.6, snake: 0.5, dragon: 0.2 };
  const BASKERS = { lizard: 1.5, snake: 1.4, turtle: 1.2, phoenix: 1.2, dragon: 0.9, cat: 0.6 };
  // how much each species likes to fly (added to its odds)
  const FLIERS = { flower_fairy: 5, dragon: 0.3, phoenix: 0.3 };
  const FLY_FROM_GROWTH = 4; // younger ones walk
  const FLY_HEIGHT = [10, 24]; // scene units, as the room allows
  const FLUTTER_TICKS = 3; // a grown fairy's wings, sitting still
  const ABOVE_WATER = 0.72; // how much of a swimming mermaid's height shows
  const SWIM_REACH = 40; // she swims this far at a go

  const rand = (a, b) => a + Math.random() * (b - a);
  const trait = (p, k) => (p.genes.personality || {})[k] ?? 0.5;
  const center = (w) => w.x + w.width / 2;
  const inside = (cx, y, r) => cx >= r.x && cx <= r.x + r.w && y >= r.y && y <= r.y + r.h;
  const pick = (list) => list[Math.floor(Math.random() * list.length)];

  function terrain(world) {
    return world.area.terrain || {};
  }

  function waterAt(world, cx, y) {
    return (terrain(world).water || []).find((r) => inside(cx, y, r));
  }

  function blocked(world, cx, y) {
    return (terrain(world).blocks || []).some((r) => inside(cx, y, r));
  }

  const swims = (w) => (SWIMMERS[w.p.species] || 0) >= 0.5;
  const allowed = (thing, w) => !thing.who || thing.who.includes(w.p.species);
  const canFly = (world, w) => Boolean(world.area.sky) && w.p.growth >= FLY_FROM_GROWTH && w.p.species in FLIERS;

  function create(pets, area, scale) {
    const world = { walkers: [], area, scale };
    world.walkers = pets.map((p, i) => {
      const settled = p.species === "mermaid" && !isPetRooted(p);
      const pool = settled && area.sky ? biggestPool(area) : null;
      const swimPose = pool && petScenePose(p.genes, p.growth, "water");
      const genes = settled && !pool ? petOnLand(p.genes) : p.genes;
      const size = petSize(genes, p.growth);
      const w = {
        p,
        genes,
        settled, // doesn't walk anywhere
        pool, // the water she stays in
        swimPose,
        width: (swimPose ? swimPose.headW : size.w) * scale, // a swimmer goes by her body: the tail just trails
        height: swimPose ? (swimPose.h - swimPose.blank) * ABOVE_WATER * scale : size.h * scale,
        x: 0,
        y: 0,
        dir: i % 2 ? -1 : 1,
        ledge: null, // the ledge it stands on, or null on the ground
        state: "idle",
        timer: Math.floor(rand(5, 40)),
        hop: 0,
        phase: 0,
        frame: 0,
        ticks: 0,
        still: isPetEgg(p) || isPetRooted(p),
        sways: isPetRooted(p), // stays put, but stays alive
        flutters: p.species === "flower_fairy", // once grown, her wings never stop
        e: trait(p, "energy"),
        s: trait(p, "sleepy"),
        f: trait(p, "friendly"),
        c: trait(p, "curious"),
        pl: trait(p, "playful"),
      };
      const [x, y] = w.pool ? poolSpot(w) : isPetRooted(p) && p.species === "mermaid" && area.sky ? shoreSpot(world, w) : groundSpot(world, w, false);
      w.x = x;
      w.y = y;
      return w;
    });
    return world;
  }

  // --- where a pet can go -------------------------------------------------------------

  // A random spot on the ground: not in a block, and not in water unless `wet`.
  function groundSpot(world, w, wet) {
    const a = world.area;
    let best = null;
    for (let k = 0; k < 16; k++) {
      const x = rand(a.left, Math.max(a.left, a.right - w.width));
      const y = rand(a.top, a.bottom);
      const cx = x + w.width / 2;
      if (blocked(world, cx, y)) continue;
      if (Boolean(waterAt(world, cx, y)) !== wet) continue;
      best = [x, y];
      break;
    }
    return best || [a.left, a.bottom];
  }

  // The biggest stretch of connected water: its rects, or null if there's none.
  function biggestPool(area) {
    const rects = (area.terrain && area.terrain.water) || [];
    const touch = (a, b) => a.x <= b.x + b.w && b.x <= a.x + a.w && a.y <= b.y + b.h && b.y <= a.y + a.h;
    const size = (pool) => pool.reduce((t, r) => t + r.w * r.h, 0);
    const left = [...rects];
    let best = null;
    while (left.length) {
      const pool = [left.pop()];
      for (let i = 0; i < pool.length; i++) {
        for (let k = left.length - 1; k >= 0; k--) if (touch(pool[i], left[k])) pool.push(...left.splice(k, 1));
      }
      if (!best || size(pool) > size(best)) best = pool;
    }
    return best;
  }

  const inPool = (pool, cx, y) => pool.some((r) => inside(cx, y, r));

  // A random spot in her water, by the size of its parts.
  function poolSpot(w) {
    let r = Math.random() * w.pool.reduce((t, p) => t + p.w * p.h, 0);
    const rect = w.pool.find((p) => (r -= p.w * p.h) <= 0) || w.pool[0];
    return [rand(rect.x, rect.x + rect.w) - w.width / 2, rand(rect.y, rect.y + rect.h)];
  }

  // Somewhere near that she can swim straight to, or null. A winding stream
  // rules out most spots, so she goes a bit at a time.
  function swimSpot(w) {
    for (let k = 0; k < 12; k++) {
      const [x, y] = poolSpot(w);
      if (Math.hypot(x - w.x, y - w.y) > SWIM_REACH) continue;
      let clear = true;
      for (let t = 0.1; t < 1 && clear; t += 0.1) clear = inPool(w.pool, w.x + (x - w.x) * t + w.width / 2, w.y + (y - w.y) * t);
      if (clear) return [x, y];
    }
    return null;
  }

  // A pearl or clam waits at the water's edge.
  function shoreSpot(world, w) {
    const pool = biggestPool(world.area);
    if (!pool) return groundSpot(world, w, false);
    const rect = pool.reduce((a, b) => (b.w * b.h > a.w * a.h ? b : a));
    const y = Math.min(rect.y + rect.h + 1, world.area.bottom);
    const x = rand(rect.x, rect.x + rect.w) - w.width / 2;
    const cx = x + w.width / 2;
    return blocked(world, cx, y) || waterAt(world, cx, y) ? groundSpot(world, w, false) : [x, y];
  }

  function ledgeSpot(world, w, ledge) {
    const lo = ledge.x0;
    const hi = Math.max(lo, ledge.x1 - w.width);
    return [rand(lo, hi), ledge.y];
  }

  // Wandering stays nearby: slow pets would spend all day crossing the scene.
  const WANDER = 45;

  function nearbySpot(world, w) {
    let spot = null;
    for (let k = 0; k < 8; k++) {
      spot = groundSpot(world, w, false);
      if (Math.hypot(spot[0] - w.x, (spot[1] - w.y) * 2) <= WANDER) break;
    }
    return spot;
  }

  function randomSpot(world, w) {
    if (w.ledge !== null) return ledgeSpot(world, w, terrain(world).ledges[w.ledge]);
    const others = world.walkers.filter((o) => o !== w && o.ledge === null);
    if (w.f >= 0.35 || !others.length) return nearbySpot(world, w);
    // shy: of a few spots, the one furthest from everyone else
    let best = null;
    let bestRoom = -1;
    for (let k = 0; k < 4; k++) {
      const [x, y] = groundSpot(world, w, false);
      const room = Math.min(...others.map((o) => Math.hypot(x + w.width / 2 - center(o), (y - o.y) * 2)));
      if (room > bestRoom) [best, bestRoom] = [[x, y], room];
    }
    return best;
  }

  function clampTo(world, w, x, y) {
    if (w.ledge !== null) {
      const l = terrain(world).ledges[w.ledge];
      return [Math.min(Math.max(x, l.x0), Math.max(l.x0, l.x1 - w.width)), l.y];
    }
    const a = world.area;
    return [Math.min(Math.max(x, a.left), a.right - w.width), Math.min(Math.max(y, a.top), a.bottom)];
  }

  function walkTo(world, w, x, y, then = "idle", speedUp = 1) {
    [w.tx, w.ty] = clampTo(world, w, x, y);
    w.state = "walk";
    w.then = then;
    w.speed = (0.16 + w.e * 0.28) * speedUp;
  }

  function leapTo(w, x, y, ledge) {
    w.state = "leap";
    w.from = [w.x, w.y];
    w.tx = x;
    w.ty = y;
    w.toLedge = ledge;
    w.t = 0;
    const dist = Math.hypot(x - w.x, y - w.y);
    w.leapRate = (0.06 + w.e * 0.05) * Math.min(1.5, 12 / Math.max(6, dist));
    w.arc = Math.max(4, w.y - y + 4);
    if (Math.abs(x - w.x) > 0.3) w.dir = x < w.x ? -1 : 1;
  }

  // Up, over one or more spots with a hover at each, and down on the last.
  function takeOff(world, w, legs, then = "idle") {
    w.state = "fly";
    w.ledge = null;
    w.legs = legs;
    w.then = then;
    w.landing = false;
    w.landLedge = null;
    w.timer = 0;
    w.cruise = rand(...FLY_HEIGHT);
    w.speed = 0.3 + w.e * 0.3;
    flyOn(world, w);
  }

  // The next spot: anywhere on the way, somewhere to stand on the last leg.
  function flyOn(world, w) {
    const a = world.area;
    if (w.legs > 1) {
      [w.tx, w.ty] = [rand(a.left, Math.max(a.left, a.right - w.width)), rand(a.top, a.bottom)];
      return;
    }
    const ledges = (terrain(world).ledges || []).map((l, i) => [l, i]).filter(([l]) => allowed(l, w));
    if (ledges.length && Math.random() < 0.3) {
      const [ledge, i] = pick(ledges);
      w.landLedge = i;
      [w.tx, w.ty] = ledgeSpot(world, w, ledge);
    } else [w.tx, w.ty] = groundSpot(world, w, false);
  }

  function stepFlight(world, w) {
    w.ticks += 1;
    if (w.ticks % 2 === 0) w.frame += 1; // flapping
    const room = Math.max(0, w.y - w.height - 2);
    const target = w.landing ? 0 : Math.min(room, w.cruise);
    w.hop += Math.min(0.6, Math.max(-0.6, target - w.hop));
    if (w.landing) {
      if (w.hop > 0) return;
      w.hop = 0;
      w.ledge = w.landLedge;
      if (w.then === "happy") startHappy(w);
      else rest(w);
    } else if (w.timer > 0) {
      w.timer -= 1; // hovering
    } else if (moveToward(world, w, w.tx, w.ty, w.speed, true)) {
      if (w.legs > 1) {
        w.legs -= 1;
        w.timer = Math.floor(rand(8, 40));
        flyOn(world, w);
      } else w.landing = true;
    }
  }

  // --- choosing what to do next ---------------------------------------------------------

  function weighted(options) {
    const total = options.reduce((t, [, wgt]) => t + wgt, 0);
    let r = Math.random() * total;
    for (const [what, wgt] of options) {
      r -= wgt;
      if (r <= 0) return what;
    }
    return options[0][0];
  }

  // A mermaid: swims about her pool if she has one, and otherwise stays put.
  function chooseSettled(w) {
    const options = [["flick", 1], ["idle", 1.5]];
    if (w.s > 0.3) options.push(["nap", w.s * 0.8]);
    if (w.pool) options.push(["swim", 1.5 + w.e]);
    const what = weighted(options);
    const spot = what === "swim" && swimSpot(w);
    if (spot) {
      [w.tx, w.ty] = spot;
      w.state = "paddle";
      w.then = "idle";
      w.speed = 0.14 + w.e * 0.2;
    } else if (what === "flick") {
      w.state = "flick";
      w.timer = Math.floor(rand(6, 18));
    } else if (what === "nap") {
      w.state = "nap";
      w.timer = Math.floor(rand(60, 160) * (0.5 + w.s));
    } else rest(w, 1.5);
  }

  function choose(world, w) {
    if (w.settled) return chooseSettled(w);
    const t = terrain(world);
    const ledges = t.ledges || [];
    const water = t.water || [];
    const species = w.p.species;
    const others = world.walkers.filter((o) => o !== w && !o.still && o.ledge === w.ledge);
    const friends = others.filter((o) => o.f > 0.5 && !o.pool && o.state !== "walk" && o.state !== "leap" && o.state !== "fly");
    const players = others.filter((o) => o.pl > 0.5 && !o.settled && o.state !== "nap" && o.state !== "leap" && o.state !== "fly");
    const props = (world.area.props || []).filter((p) => (p.ledge ?? null) === w.ledge && allowed(p, w));
    const options = [["wander", 1]];
    if (w.s > 0.3) options.push(["nap", w.s * 1.2]);
    options.push(["hop", w.e * 0.6 + w.pl * 0.5]);
    for (const prop of props) {
      const lean = prop.action === "bask" ? BASKERS[species] || 0 : prop.action === "nap" ? w.s : prop.action === "jump" || prop.action === "dig" ? w.pl * 0.6 : 0;
      options.push([prop, (w.c * 1.2 + lean) / Math.max(1, props.length / 2)]);
    }
    if (friends.length && w.f > 0.5) options.push(["friend", w.f * 1.3]);
    if (players.length && w.pl > 0.5) options.push(["chase", w.pl * 1.0]);
    if (w.ledge !== null || ledges.some((l) => allowed(l, w))) options.push(["climb", w.e * 0.5 + (CLIMBERS[species] || 0) + (w.ledge !== null ? 0.6 : 0)]);
    if (water.length && w.ledge === null) {
      if (swims(w)) options.push(["swim", (SWIMMERS[species] || 0) + w.pl * 0.3]);
      else options.push(["splash", w.pl * 0.5]);
    }
    if (canFly(world, w)) options.push(["fly", FLIERS[species] + w.e * 0.5]);
    const what = weighted(options);

    if (what === "fly") {
      takeOff(world, w, 1 + Math.floor(rand(0, 3)));
    } else if (what === "nap") {
      w.state = "nap";
      w.timer = Math.floor(rand(60, 160) * (0.5 + w.s));
    } else if (what === "hop") {
      w.state = "hop";
      w.hops = 1 + Math.floor(rand(1, 2 + w.e * 3 + w.pl * 2));
      w.phase = 0;
    } else if (typeof what === "object") {
      walkTo(world, w, what.x - w.width / 2 + rand(-3, 3), what.y + rand(0, 2), "prop");
      w.prop = what;
    } else if (what === "friend") {
      const friend = weighted(friends.map((o) => [o, o.f]));
      const side = center(w) < center(friend) ? -1 : 1;
      walkTo(world, w, friend.x + side * (friend.width / 2 + w.width / 2 + 2), friend.y + rand(-1, 1), "cuddle");
      w.lookAt = center(friend);
    } else if (what === "chase") {
      const target = pick(players);
      w.state = "chase";
      w.target = target;
      w.timer = Math.floor(rand(40, 90));
      w.speed = (0.15 + w.e * 0.3) * 1.4;
      if (target.state !== "chase") {
        const [x, y] = randomSpot(world, target); // the other pet runs off, hopping
        walkTo(world, target, x, y, "idle", 1.3);
        target.running = true;
      }
    } else if (what === "climb") {
      climb(world, w, ledges);
    } else if (what === "swim") {
      const [x, y] = groundSpot(world, w, true);
      walkTo(world, w, x, y, "swim");
    } else if (what === "splash") {
      splashSpot(world, w, water);
    } else {
      const [x, y] = randomSpot(world, w);
      walkTo(world, w, x, y);
    }
  }

  // Up onto a nearby ledge, along to another, or back down to the ground.
  function climb(world, w, ledges) {
    const cx = center(w);
    const near = ledges
      .map((l, i) => ({ l, i, gap: Math.max(0, l.x0 - cx, cx - l.x1) + Math.abs(l.y - w.y) }))
      .filter((c) => c.i !== w.ledge && allowed(c.l, w));
    if (w.ledge !== null && (!near.length || Math.random() < 0.5)) {
      // down: somewhere on the ground below
      const a = world.area;
      for (let k = 0; k < 10; k++) {
        const x = Math.min(Math.max(w.x + rand(-14, 14), a.left), a.right - w.width);
        const y = rand(a.top, a.bottom);
        if (!blocked(world, x + w.width / 2, y) && !waterAt(world, x + w.width / 2, y)) return leapTo(w, x, y, null);
      }
      return leapTo(w, w.x, world.area.top, null);
    }
    if (!near.length) return;
    const to = weighted(near.map((c) => [c, 1 / (1 + c.gap / 8)]));
    const x = Math.min(Math.max(cx - w.width / 2 + rand(-6, 6), to.l.x0), Math.max(to.l.x0, to.l.x1 - w.width));
    leapTo(w, x, to.l.y, to.i);
  }

  // Playful pets run to the water's edge and splash about.
  function splashSpot(world, w, water) {
    const pool = pick(water);
    const x = rand(pool.x, pool.x + pool.w) - w.width / 2;
    const above = pool.y - 1 >= world.area.top;
    walkTo(world, w, x, above ? pool.y - 1 : pool.y + pool.h + 1, "splash");
  }

  function rest(w, longer = 1) {
    w.state = "idle";
    w.timer = Math.floor(rand(15, 50) * (1.4 - w.e) * longer);
    w.running = false;
  }

  // What a pet does when it gets to a prop.
  function atProp(w) {
    const prop = w.prop;
    w.dir = prop.x < center(w) ? -1 : 1;
    const action = prop.action || "look";
    if (action === "nap") {
      w.state = "nap";
      w.timer = Math.floor(rand(100, 220) * (0.6 + w.s));
    } else if (action === "bask") {
      w.state = "bask";
      w.timer = Math.floor(rand(120, 260) * (0.5 + (BASKERS[w.p.species] || 0.3)));
    } else if (action === "dig" || action === "jump") {
      w.state = action;
      w.timer = Math.floor(rand(30, 70));
      w.phase = 0;
      w.bits = prop.color || "#8b5a2b";
    } else {
      w.state = "look";
      w.timer = Math.floor(rand(40, 100));
    }
  }

  // --- one tick ------------------------------------------------------------------------

  function moveToward(world, w, tx, ty, speed, flying = false) {
    const dx = tx - w.x;
    const dy = (ty - w.y) * 2; // depth moves at half speed
    const d = Math.hypot(dx, dy);
    if (d <= speed) {
      w.x = tx;
      w.y = ty;
      return true;
    }
    const nx = w.x + (dx / d) * speed;
    const ny = w.y + (dy / d) * speed * 0.5;
    if (!flying && w.ledge === null && blocked(world, nx + w.width / 2, ny)) return null; // bumped into something
    w.x = nx;
    w.y = ny;
    if (Math.abs(dx) > 0.3) w.dir = dx < 0 ? -1 : 1;
    return false;
  }

  function animate(w, moving) {
    w.ticks += 1;
    const every = Math.max(1, Math.round(4 - w.e * 3)); // energetic legs go faster
    if (moving && w.ticks % every === 0) w.frame += 1;
    if (moving) return;
    if (!w.flutters || w.state === "nap") w.frame = 0;
    else if (w.ticks % FLUTTER_TICKS === 0) w.frame += 1;
  }

  // A treat or toy lands at (x, y): pets in `ids` run to it, then bounce
  // about happily with hearts. onArrive(walker) is called for the first one
  // there (a treat gets eaten).
  function attract(world, ids, x, y, onArrive) {
    let first = true;
    for (const w of world.walkers) {
      if (w.still || !ids.includes(w.p.id)) continue;
      const tx = x - w.width / 2 + rand(-5, 5);
      const ty = y + rand(-2, 2);
      w.arrive = first ? onArrive : null;
      first = false;
      if (w.settled) {
        if (w.pool) {
          // as near as the water goes
          const cx = x;
          const rect = w.pool.reduce((a, b) => (Math.hypot(cx - mid(b)[0], y - mid(b)[1]) < Math.hypot(cx - mid(a)[0], y - mid(a)[1]) ? b : a));
          w.tx = Math.min(Math.max(cx, rect.x), rect.x + rect.w) - w.width / 2;
          w.ty = Math.min(Math.max(y, rect.y), rect.y + rect.h);
          w.state = "paddle";
          w.then = "happy";
          w.speed = 0.3 + w.e * 0.2;
        } else startHappy(w); // can't come, but pleased all the same
        continue;
      }
      if (canFly(world, w)) {
        takeOff(world, w, 1, "happy"); // straight there, down low
        [w.tx, w.ty] = [tx, ty];
        w.landLedge = null;
        w.cruise = FLY_HEIGHT[0];
        w.speed *= 1.5;
      } else if (w.ledge !== null) {
        leapTo(w, tx, ty, null); // hop down first; it walks over once it lands
        w.after = { x: tx, y: ty };
      } else walkTo(world, w, tx, ty, "happy", 1.5);
      w.running = true;
    }
  }

  function startHappy(w) {
    w.state = "happy";
    w.timer = Math.floor(rand(60, 110));
    w.phase = 0;
    w.running = false;
    if (w.arrive) {
      w.arrive(w);
      w.arrive = null;
    }
  }

  const mid = (r) => [r.x + r.w / 2, r.y + r.h / 2];

  const RESTING = new Set(["idle", "nap", "look", "cuddle", "bask"]);

  const SWAY_TICKS = 3; // a rooted pet's frames: slower than walking legs

  function stepOne(world, w) {
    if (w.still) {
      if (w.sways && ++w.ticks % SWAY_TICKS === 0) w.frame += 1;
      return;
    }
    if (w.state === "fly") return stepFlight(world, w);
    let moving = false;
    if (w.state === "paddle") {
      moving = true;
      if (moveToward(world, w, w.tx, w.ty, w.speed, true)) {
        if (w.then === "happy") startHappy(w);
        else rest(w);
      }
    } else if (w.state === "flick") {
      w.ticks += 1;
      if (w.ticks % 2 === 0) w.frame += 1;
      if (--w.timer <= 0) rest(w, 1.5);
      return;
    } else if (RESTING.has(w.state)) {
      w.hop = 0;
      if (--w.timer <= 0) choose(world, w);
    } else if (w.state === "hop") {
      w.phase += 0.3 + w.e * 0.25;
      w.hop = Math.abs(Math.sin(w.phase)) * (2 + w.e * 2 + w.pl);
      if (w.phase >= Math.PI * w.hops) {
        w.hop = 0;
        rest(w);
      }
    } else if (w.state === "dig" || w.state === "jump" || w.state === "splash") {
      w.phase += w.state === "dig" ? 0.8 : 0.35 + w.e * 0.2;
      w.hop = w.state === "dig" ? 0 : Math.abs(Math.sin(w.phase)) * (w.state === "jump" ? 3 + w.pl * 2 : 1.5);
      moving = w.state === "dig";
      if (--w.timer <= 0) {
        w.hop = 0;
        rest(w);
      }
    } else if (w.state === "happy") {
      w.phase += 0.35 + w.e * 0.2;
      w.hop = Math.abs(Math.sin(w.phase)) * (2.5 + w.pl * 2);
      if (Math.sin(w.phase / 3) > 0.95) w.dir = -w.dir; // spinning with joy
      moving = true;
      if (--w.timer <= 0) {
        w.hop = 0;
        rest(w);
      }
    } else if (w.state === "leap") {
      w.t = Math.min(1, w.t + w.leapRate);
      w.x = w.from[0] + (w.tx - w.from[0]) * w.t;
      w.y = w.from[1] + (w.ty - w.from[1]) * w.t;
      w.hop = Math.sin(Math.PI * w.t) * w.arc;
      if (w.t >= 1) {
        w.hop = 0;
        w.ledge = w.toLedge;
        if (w.after) {
          walkTo(world, w, w.after.x, w.after.y, "happy", 1.5); // on its way to a treat or toy
          w.after = null;
        } else rest(w, 0.7);
      }
    } else if (w.state === "walk" || w.state === "swim") {
      moving = true;
      const cx = center(w);
      const wet = w.ledge === null && waterAt(world, cx, w.y);
      const bouncy = w.running || w.e > 0.7 || (wet && !swims(w)); // hop across water you can't swim
      w.phase += 0.4;
      w.hop = bouncy && w.state !== "swim" ? Math.abs(Math.sin(w.phase)) * (w.running || wet ? 2.5 : 1) : 0;
      const arrived = moveToward(world, w, w.tx, w.ty, w.state === "swim" ? w.speed * 0.6 : w.speed);
      if (arrived === null) rest(w); // blocked: think again
      else if (arrived) {
        w.hop = 0;
        if (w.state === "swim") {
          // paddle about the water a while, then climb out
          if (--w.laps > 0) {
            const [x, y] = groundSpot(world, w, true);
            [w.tx, w.ty] = [x, y];
          } else {
            const [x, y] = groundSpot(world, w, false);
            walkTo(world, w, x, y);
          }
        } else if (w.then === "swim") {
          w.state = "swim";
          w.laps = 2 + Math.floor(rand(0, 4));
          const [x, y] = groundSpot(world, w, true);
          [w.tx, w.ty] = [x, y];
        } else if (w.then === "splash") {
          w.state = "splash";
          w.timer = Math.floor(rand(30, 60) * (0.5 + w.pl));
          w.phase = 0;
        } else if (w.then === "prop") {
          atProp(w);
        } else if (w.then === "happy") {
          startHappy(w);
        } else if (w.then === "cuddle") {
          w.state = "cuddle";
          w.dir = w.lookAt < center(w) ? -1 : 1;
          w.timer = Math.floor(rand(40, 100) * (1 + w.f));
        } else rest(w);
      }
    } else if (w.state === "chase") {
      moving = true;
      const t = w.target;
      w.phase += 0.45;
      w.hop = Math.abs(Math.sin(w.phase)) * 2.5;
      const side = center(w) < center(t) ? -1 : 1;
      const r = moveToward(world, w, t.x + side * (t.width / 2 + 1), t.y, w.speed);
      if (r === null || --w.timer <= 0 || t.state === "nap" || t.state === "fly" || t.ledge !== w.ledge) {
        w.hop = 0;
        w.dir = center(t) < center(w) ? -1 : 1;
        rest(w, 0.6);
      }
    }
    animate(w, moving);
  }

  function step(world) {
    for (const w of world.walkers) stepOne(world, w);
  }

  // --- drawing --------------------------------------------------------------------------

  function draw(world, px, opts = {}) {
    for (const w of [...world.walkers].sort((a, b) => a.y - b.y)) drawOne(world, w, px, opts);
  }

  // Her waist at the waterline: the tail shows, dimmed, only where there's water under it.
  function drawSwimmer(world, w, px) {
    const { genes, h, blank } = w.swimPose;
    const color = (w.pool[0].color || "#4a8ab0") + "99";
    const line = w.y;
    const body = center(w);
    const under = (x, y, pw, ph, c) => {
      const [mx, my] = [x + pw / 2, y + ph / 2];
      const above = my <= line;
      if (!(above && Math.abs(mx - body) <= w.width * 0.75) && !inPool(w.pool, mx, my)) return; // no stray fluke on dry land
      px(x, y, pw, ph, c);
      if (!above) px(x, y, pw, ph, color);
    };
    const bottom = line + (h - blank) * (1 - ABOVE_WATER) * world.scale + blank * world.scale - w.hop;
    const cx = center(w);
    const faceLeft = w.dir < 0;
    const fromLeft = (faceLeft ? w.swimPose.w - w.swimPose.headX : w.swimPose.headX) * world.scale;
    drawPet(under, cx - fromLeft, bottom, genes, w.p.growth, { frame: w.frame, faceLeft, scale: world.scale, shadow: false });
    // the ripple around her, a little wider every other frame
    const span = w.width * (0.55 + (w.frame % 2) * 0.1);
    px(cx - span, line - 0.25, span * 0.7, 0.5, "rgba(220, 240, 250, 0.85)");
    px(cx + span * 0.3, line - 0.25, span * 0.7, 0.5, "rgba(220, 240, 250, 0.85)");
    if (w.state === "flick" || w.state === "paddle") droplets(px, { ...w, y: line + 1 }, "rgba(220, 240, 250, 0.8)");
  }

  function drawOne(world, w, px, { ctx, unit, tags = false } = {}) {
    if (w.pool) {
      drawSwimmer(world, w, px);
      if (ctx && w.state === "nap") snore(ctx, unit, w);
      if (w.state === "happy") hearts(px, w);
      if (ctx && tags && w.p.name) nameTag(ctx, unit, w);
      return;
    }
    const cx = center(w);
    const pool = w.ledge === null && w.hop === 0 && waterAt(world, cx, w.y);
    const sink = pool && swims(w) ? Math.min(3, w.height * 0.25) : 0; // swimmers sit low in the water
    const air = w.state === "fly" ? flightPose(world, w) : null;
    if (w.p.species !== "fish" && !pool) {
      const shadow = air ? Math.max(0.3, 0.7 - w.hop * 0.015) : 0.7; // it shrinks as the pet climbs
      px(cx - (w.width * shadow) / 2, w.y - 0.5, w.width * shadow, 1, "rgba(40, 60, 20, 0.25)");
    }
    if (air) drawPet(px, cx - (air.w * world.scale) / 2, w.y - w.hop + air.blank * world.scale, air.genes, w.p.growth, { frame: w.frame, faceLeft: w.dir < 0, scale: world.scale, shadow: false });
    else drawPet(px, w.x, w.y - w.hop + sink, w.genes, w.p.growth, { frame: w.frame, faceLeft: w.dir < 0, scale: world.scale, shadow: false });
    w.shownHeight = air ? (air.h - air.blank) * world.scale : w.height;
    if (pool) {
      const top = w.y - Math.max(1, w.height * 0.35) + sink;
      px(w.x - 1, top, w.width + 2, w.y + sink - top + 0.5, pool.color ? `${pool.color}cc` : "rgba(74, 138, 176, 0.8)");
      px(w.x - 1, top, w.width + 2, 0.5, "rgba(220, 240, 250, 0.8)"); // the waterline
      if (w.frame % 2) px(w.x - 2, top + 0.5, 1, 0.5, "rgba(220, 240, 250, 0.8)");
    }
    if (w.state === "splash" || (w.state === "walk" && pool && !swims(w))) droplets(px, w, "rgba(200, 230, 250, 0.9)");
    if (w.state === "dig" || w.state === "jump") droplets(px, w, w.bits);
    if (ctx && w.state === "nap") snore(ctx, unit, w);
    if (w.state === "happy") hearts(px, w);
    if (ctx && tags && w.p.name) nameTag(ctx, unit, w);
  }

  function flightPose(world, w) {
    w.air ||= petScenePose(w.p.genes, w.p.growth, "air");
    return w.air;
  }

  // A few bits flying up around a pet's feet (water, dirt, leaves).
  function droplets(px, w, color) {
    for (let i = 0; i < 4; i++) {
      const k = (w.ticks * 7 + i * 13) % 10;
      const side = i % 2 ? -1 : 1;
      px(center(w) + side * (w.width * 0.3 + k * 0.3), w.y - 1 - Math.sin((k / 10) * Math.PI) * 4, 0.6, 0.6, color);
    }
  }

  const HEART = [".X.X.", "XXXXX", ".XXX.", "..X.."];

  function hearts(px, w) {
    for (let i = 0; i < 2; i++) {
      const rise = ((w.timer * 0.6 + i * 9) % 18) / 18;
      const hx = center(w) + (i ? w.width * 0.3 : -w.width * 0.35) + Math.sin(rise * 6) * 1.2;
      const hy = w.y - w.height - 2 - rise * 7;
      HEART.forEach((row, j) => [...row].forEach((c, k) => c === "X" && px(hx + k * 0.8, hy + j * 0.8, 0.8, 0.8, "#e84a6a")));
    }
  }

  function snore(ctx, unit, w) {
    const rise = (w.timer % 30) / 30;
    ctx.font = `${Math.round(unit * 3)}px 'Jersey 10', sans-serif`;
    ctx.fillStyle = "rgba(59, 36, 23, " + (1 - rise).toFixed(2) + ")";
    ctx.textAlign = "left";
    ctx.fillText("z", (center(w) + w.width * 0.3 + rise * 2) * unit, (w.y - w.height - rise * 4) * unit);
  }

  function nameTag(ctx, unit, w) {
    const cx = center(w) * unit;
    const top = (w.y - w.hop - (w.shownHeight || w.height) - 1) * unit;
    ctx.font = `${Math.round(unit * 3.7)}px 'Jersey 10', sans-serif`;
    ctx.textAlign = "center";
    ctx.lineWidth = 4;
    ctx.strokeStyle = "#3b2417";
    ctx.strokeText(w.p.name, cx, top);
    ctx.fillStyle = "#fbf1dc";
    ctx.fillText(w.p.name, cx, top);
  }

  return { create, step, draw, drawOne, attract };
})();
