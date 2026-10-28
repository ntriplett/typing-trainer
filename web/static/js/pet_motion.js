// How pets move around a scene (PLAN.md 11i), shared by the Pets hub and
// the habitats. Each pet is a small state machine: idle, walk (wander, go
// look at a prop, go sit by a friend), nap, hop, chase/run (play). Its
// personality picks what it does next and how:
//   energy   walks and animates faster, hops more, rests less
//   sleepy   naps more often, and longer
//   friendly goes to sit near other friendly pets; shy ones keep away
//   curious  walks over to look at the scene's props
//   playful  hops, and chases other playful pets around
// Positions are in scene units: x is a pet's left edge, y its feet.
//
//   const world = PetMotion.create(pets, area, scale);   // area: {left, right, top, bottom, props}
//   setInterval(() => PetMotion.step(world), 120);
//   PetMotion.draw(world, px, {ctx, unit, tags});        // px(x, y, w, h, color) in scene units

const PetMotion = (() => {
  const rand = (a, b) => a + Math.random() * (b - a);
  const trait = (p, k) => (p.genes.personality || {})[k] ?? 0.5;
  const isEgg = (p) => p.growth === 0 && (p.species === "dragon" || p.species === "phoenix");
  const center = (w) => w.x + w.width / 2;
  const dist = (a, b) => Math.hypot(center(a) - center(b), (a.y - b.y) * 2);

  function create(pets, area, scale) {
    const walkers = pets.map((p, i) => {
      const size = petSize(p.genes, p.growth);
      const width = size.w * scale;
      return {
        p,
        width,
        height: size.h * scale,
        x: area.left + ((i * 41) % Math.max(1, area.right - area.left - width)),
        y: area.top + ((i * 13) % Math.max(1, area.bottom - area.top)),
        dir: i % 2 ? -1 : 1,
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
    });
    return { walkers, area, scale };
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

  function clampTo(world, w, x, y) {
    const a = world.area;
    return [Math.min(Math.max(x, a.left), a.right - w.width), Math.min(Math.max(y, a.top), a.bottom)];
  }

  function randomSpot(world, w) {
    const a = world.area;
    const spot = () => [rand(a.left, a.right - w.width), rand(a.top, a.bottom)];
    if (w.f >= 0.35) return spot();
    // shy: of a few spots, the one furthest from everyone else
    const others = world.walkers.filter((o) => o !== w);
    let best = spot();
    let bestRoom = -1;
    for (let k = 0; k < 4; k++) {
      const [x, y] = spot();
      const room = Math.min(...others.map((o) => Math.hypot(x + w.width / 2 - center(o), (y - o.y) * 2)), 999);
      if (room > bestRoom) [best, bestRoom] = [[x, y], room];
    }
    return best;
  }

  function walkTo(world, w, x, y, then = "idle", speedUp = 1) {
    [w.tx, w.ty] = clampTo(world, w, x, y);
    w.state = "walk";
    w.then = then;
    w.speed = (0.12 + w.e * 0.3) * speedUp;
  }

  function choose(world, w) {
    const others = world.walkers.filter((o) => o !== w && !o.still);
    const friends = others.filter((o) => o.f > 0.5 && o.state !== "walk");
    const players = others.filter((o) => o.pl > 0.5 && o.state !== "nap");
    const props = world.area.props || [];
    const options = [["wander", 1]];
    if (w.s > 0.3) options.push(["nap", w.s * 1.2]);
    options.push(["hop", w.e * 0.6 + w.pl * 0.5]);
    if (props.length) options.push(["visit", w.c * 1.2]);
    if (friends.length && w.f > 0.5) options.push(["friend", w.f * 1.3]);
    if (players.length && w.pl > 0.5) options.push(["chase", w.pl * 1.0]);
    const what = weighted(options);

    if (what === "nap") {
      w.state = "nap";
      w.timer = Math.floor(rand(60, 160) * (0.5 + w.s));
    } else if (what === "hop") {
      w.state = "hop";
      w.hops = 1 + Math.floor(rand(1, 2 + w.e * 3 + w.pl * 2));
      w.phase = 0;
    } else if (what === "visit") {
      const prop = props[Math.floor(Math.random() * props.length)];
      walkTo(world, w, prop.x - w.width / 2 + rand(-4, 4), prop.y + rand(0, 3), "look");
      w.lookAt = prop.x;
    } else if (what === "friend") {
      const friend = weighted(friends.map((o) => [o, o.f]));
      const side = center(w) < center(friend) ? -1 : 1;
      walkTo(world, w, friend.x + side * (friend.width / 2 + w.width / 2 + 2), friend.y + rand(-1, 1), "cuddle");
      w.lookAt = center(friend);
    } else if (what === "chase") {
      const target = players[Math.floor(Math.random() * players.length)];
      w.state = "chase";
      w.target = target;
      w.timer = Math.floor(rand(40, 90));
      w.speed = (0.15 + w.e * 0.3) * 1.4;
      if (target.state !== "chase") {
        // the other pet runs off, hopping
        const [x, y] = randomSpot(world, target);
        walkTo(world, target, x, y, "idle", 1.3);
        target.running = true;
      }
    } else {
      const [x, y] = randomSpot(world, w);
      walkTo(world, w, x, y);
    }
  }

  function rest(w, longer = 1) {
    w.state = "idle";
    w.timer = Math.floor(rand(15, 50) * (1.4 - w.e) * longer);
    w.running = false;
  }

  // --- one tick ------------------------------------------------------------------------

  function moveToward(w, tx, ty, speed) {
    const dx = tx - w.x;
    const dy = (ty - w.y) * 2; // depth moves at half speed
    const d = Math.hypot(dx, dy);
    if (d <= speed) {
      w.x = tx;
      w.y = ty;
      return true;
    }
    w.x += (dx / d) * speed;
    w.y += (dy / d) * speed * 0.5;
    if (Math.abs(dx) > 0.3) w.dir = dx < 0 ? -1 : 1;
    return false;
  }

  function animate(w, moving) {
    w.ticks += 1;
    const every = Math.max(1, Math.round(4 - w.e * 3)); // energetic legs go faster
    if (moving && w.ticks % every === 0) w.frame += 1;
    if (!moving) w.frame = 0;
  }

  function stepOne(world, w) {
    if (w.still) return;
    let moving = false;
    if (w.state === "idle" || w.state === "nap" || w.state === "look" || w.state === "cuddle") {
      w.hop = 0;
      if (--w.timer <= 0) choose(world, w);
    } else if (w.state === "hop") {
      w.phase += 0.3 + w.e * 0.25;
      w.hop = Math.abs(Math.sin(w.phase)) * (2 + w.e * 2 + w.pl);
      if (w.phase >= Math.PI * w.hops) {
        w.hop = 0;
        rest(w);
      }
    } else if (w.state === "walk") {
      moving = true;
      const bouncy = w.running || w.e > 0.7;
      w.phase += 0.4;
      w.hop = bouncy ? Math.abs(Math.sin(w.phase)) * (w.running ? 2.5 : 1) : 0;
      if (moveToward(w, w.tx, w.ty, w.speed)) {
        w.hop = 0;
        if (w.then === "look" || w.then === "cuddle") {
          w.state = w.then;
          w.dir = w.lookAt < center(w) ? -1 : 1;
          w.timer = Math.floor(rand(40, 100) * (w.then === "cuddle" ? 1 + w.f : 1));
        } else rest(w);
      }
    } else if (w.state === "chase") {
      moving = true;
      const t = w.target;
      w.phase += 0.45;
      w.hop = Math.abs(Math.sin(w.phase)) * 2.5;
      const side = center(w) < center(t) ? -1 : 1;
      moveToward(w, t.x + side * (t.width / 2 + 1), t.y, w.speed);
      if (--w.timer <= 0 || t.state === "nap") {
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
      px(w.x + w.width * 0.15, w.y - 0.5, w.width * 0.7, 1, "rgba(40, 60, 20, 0.25)"); // shadow
      drawPet(px, w.x, w.y - w.hop, w.p.genes, w.p.growth, { frame: w.frame, faceLeft: w.dir < 0, scale: world.scale });
      if (ctx && w.state === "nap") snore(ctx, unit, w);
      if (ctx && tags && w.p.name) nameTag(ctx, unit, w);
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
