// How pets move around a scene (PLAN.md 11i, 11j), shared by the Pets hub,
// the habitats, and the Pet Shop's rooms. Each pet is a small state
// machine: idle, walk (wander, go to a prop, go sit by a friend), nap, hop,
// chase/run (play), leap (up onto a ledge or back down), swim, splash, and
// a prop's own action (bask, nap, dig, jump in). Its personality picks what
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
// feet can be on the ground. props: [{id, x, y, action, ledge}], action one
// of look (default), bask, nap, dig, jump; ledge: the ledge it's on. terrain
// (all optional, rects in feet coordinates):
//   water:  [{x, y, w, h, color}]  swimmers swim in it; others go around or hop across
//   blocks: [{x, y, w, h}]         no feet in here (rocks, trunks, furniture)
//   ledges: [{x0, x1, y}]          raised walkways pets leap up onto

const PetMotion = (() => {
  // how much each species likes to climb, swim, or bask (added to its odds)
  const CLIMBERS = { goat: 1.4, cat: 0.9, lizard: 0.8, sheep: 0.5, llama: 0.5, fox: 0.5, dragon: 0.5, unicorn: 0.3 };
  const SWIMMERS = { turtle: 1.6, dog: 0.6, snake: 0.5, dragon: 0.2 };
  const BASKERS = { lizard: 1.5, snake: 1.4, turtle: 1.2, phoenix: 1.2, dragon: 0.9, cat: 0.6 };

  const rand = (a, b) => a + Math.random() * (b - a);
  const trait = (p, k) => (p.genes.personality || {})[k] ?? 0.5;
  const isEgg = (p) => p.growth === 0 && (p.species === "dragon" || p.species === "phoenix");
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

  function create(pets, area, scale) {
    const world = { walkers: [], area, scale };
    world.walkers = pets.map((p, i) => {
      const size = petSize(p.genes, p.growth);
      const w = {
        p,
        width: size.w * scale,
        height: size.h * scale,
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
        still: isEgg(p),
        e: trait(p, "energy"),
        s: trait(p, "sleepy"),
        f: trait(p, "friendly"),
        c: trait(p, "curious"),
        pl: trait(p, "playful"),
      };
      const [x, y] = groundSpot(world, w, false);
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

  function choose(world, w) {
    const t = terrain(world);
    const ledges = t.ledges || [];
    const water = t.water || [];
    const species = w.p.species;
    const others = world.walkers.filter((o) => o !== w && !o.still && o.ledge === w.ledge);
    const friends = others.filter((o) => o.f > 0.5 && o.state !== "walk" && o.state !== "leap");
    const players = others.filter((o) => o.pl > 0.5 && o.state !== "nap" && o.state !== "leap");
    const props = (world.area.props || []).filter((p) => (p.ledge ?? null) === w.ledge);
    const options = [["wander", 1]];
    if (w.s > 0.3) options.push(["nap", w.s * 1.2]);
    options.push(["hop", w.e * 0.6 + w.pl * 0.5]);
    for (const prop of props) {
      const lean = prop.action === "bask" ? BASKERS[species] || 0 : prop.action === "nap" ? w.s : prop.action === "jump" || prop.action === "dig" ? w.pl * 0.6 : 0;
      options.push([prop, (w.c * 1.2 + lean) / Math.max(1, props.length / 2)]);
    }
    if (friends.length && w.f > 0.5) options.push(["friend", w.f * 1.3]);
    if (players.length && w.pl > 0.5) options.push(["chase", w.pl * 1.0]);
    if (ledges.length) options.push(["climb", w.e * 0.5 + (CLIMBERS[species] || 0) + (w.ledge !== null ? 0.6 : 0)]);
    if (water.length && w.ledge === null) {
      if (swims(w)) options.push(["swim", (SWIMMERS[species] || 0) + w.pl * 0.3]);
      else options.push(["splash", w.pl * 0.5]);
    }
    const what = weighted(options);

    if (what === "nap") {
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
      .filter((c) => c.i !== w.ledge);
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

  function moveToward(world, w, tx, ty, speed) {
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
    if (w.ledge === null && blocked(world, nx + w.width / 2, ny)) return null; // bumped into something
    w.x = nx;
    w.y = ny;
    if (Math.abs(dx) > 0.3) w.dir = dx < 0 ? -1 : 1;
    return false;
  }

  function animate(w, moving) {
    w.ticks += 1;
    const every = Math.max(1, Math.round(4 - w.e * 3)); // energetic legs go faster
    if (moving && w.ticks % every === 0) w.frame += 1;
    if (!moving) w.frame = 0;
  }

  const RESTING = new Set(["idle", "nap", "look", "cuddle", "bask"]);

  function stepOne(world, w) {
    if (w.still) return;
    let moving = false;
    if (RESTING.has(w.state)) {
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
    } else if (w.state === "leap") {
      w.t = Math.min(1, w.t + w.leapRate);
      w.x = w.from[0] + (w.tx - w.from[0]) * w.t;
      w.y = w.from[1] + (w.ty - w.from[1]) * w.t;
      w.hop = Math.sin(Math.PI * w.t) * w.arc;
      if (w.t >= 1) {
        w.hop = 0;
        w.ledge = w.toLedge;
        rest(w, 0.7);
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
      if (r === null || --w.timer <= 0 || t.state === "nap" || t.ledge !== w.ledge) {
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

  function draw(world, px, { ctx, unit, tags = false } = {}) {
    for (const w of [...world.walkers].sort((a, b) => a.y - b.y)) {
      const cx = center(w);
      const pool = w.ledge === null && w.hop === 0 && waterAt(world, cx, w.y);
      const sink = pool && swims(w) ? Math.min(3, w.height * 0.25) : 0; // swimmers sit low in the water
      if (w.p.species !== "fish" && !pool) px(w.x + w.width * 0.15, w.y - 0.5, w.width * 0.7, 1, "rgba(40, 60, 20, 0.25)"); // shadow
      drawPet(px, w.x, w.y - w.hop + sink, w.p.genes, w.p.growth, { frame: w.frame, faceLeft: w.dir < 0, scale: world.scale, shadow: false });
      if (pool) {
        const top = w.y - Math.max(1, w.height * 0.35) + sink;
        px(w.x - 1, top, w.width + 2, w.y + sink - top + 0.5, pool.color ? `${pool.color}cc` : "rgba(74, 138, 176, 0.8)");
        px(w.x - 1, top, w.width + 2, 0.5, "rgba(220, 240, 250, 0.8)"); // the waterline
        if (w.frame % 2) px(w.x - 2, top + 0.5, 1, 0.5, "rgba(220, 240, 250, 0.8)");
      }
      if (w.state === "splash" || (w.state === "walk" && pool && !swims(w))) droplets(px, w, "rgba(200, 230, 250, 0.9)");
      if (w.state === "dig" || w.state === "jump") droplets(px, w, w.bits);
      if (ctx && w.state === "nap") snore(ctx, unit, w);
      if (ctx && tags && w.p.name) nameTag(ctx, unit, w);
    }
  }

  // A few bits flying up around a pet's feet (water, dirt, leaves).
  function droplets(px, w, color) {
    for (let i = 0; i < 4; i++) {
      const k = (w.ticks * 7 + i * 13) % 10;
      const side = i % 2 ? -1 : 1;
      px(center(w) + side * (w.width * 0.3 + k * 0.3), w.y - 1 - Math.sin((k / 10) * Math.PI) * 4, 0.6, 0.6, color);
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
    const top = (w.y - w.hop - w.height - 1) * unit;
    ctx.font = `${Math.round(unit * 3.7)}px 'Jersey 10', sans-serif`;
    ctx.textAlign = "center";
    ctx.lineWidth = 4;
    ctx.strokeStyle = "#3b2417";
    ctx.strokeText(w.p.name, cx, top);
    ctx.fillStyle = "#fbf1dc";
    ctx.fillText(w.p.name, cx, top);
  }

  return { create, step, draw };
})();
