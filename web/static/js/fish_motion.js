// How fish swim in a tank (PLAN.md 11k), and how a tank is drawn. Fish
// steer toward a goal while keeping their space:
//   behavior.height     where it likes to swim (0 the bottom, 1 the top);
//                       it stays near there more often than not
//   behavior.schooling  small schooling fish keep together and turn as one
//   curious             explores the tank (driftwood, ships, arches) and
//                       wanders away from its height
//   friendly            shy fish (low) hide in plants, caves and castles
//   playful             rides the bubbles from bubblers and chests
//   energy              swims faster
// Fish always face the way they swim. Each fish has a depth z (0 back .. 1
// front): it passes behind middle-layer pieces when z < 0.5, in front when
// above; back pieces are always behind fish, front pieces always in front.
// Coordinates are tank units (aquarium_items.js TANK_W x TANK_H); a fish's
// x, y is its center.
//
//   const world = FishMotion.create(fish, tank, items, scale);
//   setInterval(() => FishMotion.step(world), 100);
//   drawTankScene(ctx, unit, world, t);

const FishMotion = (() => {
  const SURFACE = 3;
  const FLOOR = TANK_H - SUBSTRATE_H + 1;
  const rand = (a, b) => a + Math.random() * (b - a);
  const trait = (f, k) => (f.genes.personality || {})[k] ?? 0.5;
  const behavior = (f, k, d) => (f.genes.behavior || {})[k] ?? d;

  // What the tank's pieces mean to fish: boxes to hide in, explore, swim through, bubble columns.
  function features(pieces, items) {
    const out = { hide: [], explore: [], through: [], bubbles: [] };
    for (const p of pieces) {
      const item = items[p.item_id];
      if (!item) continue;
      const box = { x: p.x, y: p.y - item.h, w: item.w, h: item.h, layer: p.layer };
      for (const k of item.sees || []) out[k].push(box);
    }
    return out;
  }

  function create(fish, tank, items, scale) {
    const world = { fish: [], pieces: tank.pieces, items, scale, feats: features(tank.pieces, items), t: 0 };
    world.fish = fish.map((f, i) => {
      const size = petSize(f.genes, f.growth);
      const w = size.w * scale;
      const h = size.h * scale;
      const height = behavior(f, "height", 0.5);
      const prefY = FLOOR - h / 2 - height * (FLOOR - SURFACE - h);
      return {
        f,
        w,
        h,
        x: rand(w, TANK_W - w),
        y: prefY + rand(-4, 4),
        z: Math.random(),
        vx: (i % 2 ? -1 : 1) * 0.2,
        vy: 0,
        dir: i % 2 ? -1 : 1,
        prefY,
        school: behavior(f, "schooling", 0.3),
        bottom: height < 0.25,
        e: trait(f, "energy"),
        c: trait(f, "curious"),
        shy: 1 - trait(f, "friendly"),
        pl: trait(f, "playful"),
        goal: null,
        state: "swim",
        timer: 0,
        frame: 0,
        tz: Math.random(),
      };
    });
    return world;
  }

  function clampGoal(fish, x, y) {
    return [Math.min(Math.max(x, fish.w / 2 + 1), TANK_W - fish.w / 2 - 1), Math.min(Math.max(y, SURFACE + fish.h / 2), FLOOR - fish.h / 2)];
  }

  const center = (box) => [box.x + box.w / 2, box.y + box.h / 2];

  // Pick what to do next.
  function choose(world, fish) {
    const F = world.feats;
    const options = [["cruise", 2]];
    if (F.hide.length) options.push(["hide", fish.shy * 1.6]);
    if (F.explore.length || F.through.length) options.push(["explore", fish.c * 1.4]);
    if (F.bubbles.length) options.push(["bubbles", fish.pl * 1.1]);
    options.push(["roam", fish.c * 0.6]);
    if (fish.bottom) options.push(["poke", 1.2]);
    const total = options.reduce((t, [, w]) => t + w, 0);
    let r = Math.random() * total;
    const what = (options.find(([, w]) => (r -= w) <= 0) || options[0])[0];

    fish.state = what;
    fish.timer = Math.floor(rand(60, 160));
    fish.tz = Math.random();
    if (what === "hide") {
      const spot = F.hide[Math.floor(Math.random() * F.hide.length)];
      const [cx, cy] = center(spot);
      fish.goal = clampGoal(fish, cx + rand(-spot.w / 4, spot.w / 4), cy + spot.h / 4);
      fish.tz = spot.layer === "front" ? rand(0, 0.9) : spot.layer === "middle" ? rand(0.05, 0.4) : rand(0, 1); // tucked behind it
      fish.timer = Math.floor(rand(120, 260) * (0.6 + fish.shy));
    } else if (what === "explore") {
      const list = [...F.explore, ...F.through];
      const spot = list[Math.floor(Math.random() * list.length)];
      const [cx, cy] = center(spot);
      if (F.through.includes(spot)) {
        // swim through: aim past the far side of the opening
        const side = fish.x < cx ? 1 : -1;
        fish.goal = clampGoal(fish, cx + side * (spot.w / 2 + fish.w), spot.y + spot.h * 0.7);
        fish.tz = 0.45;
      } else fish.goal = clampGoal(fish, cx + rand(-spot.w / 2, spot.w / 2), cy + rand(-spot.h / 2, 0));
    } else if (what === "bubbles") {
      const b = F.bubbles[Math.floor(Math.random() * F.bubbles.length)];
      fish.goal = clampGoal(fish, b.x + b.w / 2, b.y - 2);
      fish.ride = b;
    } else if (what === "poke") {
      fish.goal = clampGoal(fish, rand(0, TANK_W), FLOOR);
    } else if (what === "roam") {
      fish.goal = clampGoal(fish, rand(0, TANK_W), rand(SURFACE, FLOOR));
    } else {
      // cruise: somewhere along its own height
      fish.goal = clampGoal(fish, rand(0, TANK_W), fish.prefY + rand(-5, 5));
    }
  }

  function stepFish(world, fish) {
    if (!fish.goal || --fish.timer <= 0) choose(world, fish);
    const maxSpeed = 0.18 + fish.e * 0.32;
    let [gx, gy] = fish.goal;
    if (fish.state === "bubbles" && Math.abs(fish.x - gx) < 2) gy = SURFACE + fish.h / 2; // ride up the stream
    let ax = (gx - fish.x) * 0.004;
    let ay = (gy - fish.y) * 0.006;
    const near = Math.hypot(gx - fish.x, gy - fish.y) < 3;
    if (near && (fish.state === "hide" || fish.state === "explore")) {
      ax *= 0.2; // linger
      ay *= 0.2;
    } else if (near) fish.goal = null;

    // schooling: steer toward schoolmates and match their heading
    if (fish.school > 0.45) {
      const mates = world.fish.filter((o) => o !== fish && o.school > 0.45 && Math.hypot(o.x - fish.x, o.y - fish.y) < 40);
      if (mates.length) {
        const mx = mates.reduce((s, o) => s + o.x, 0) / mates.length;
        const my = mates.reduce((s, o) => s + o.y, 0) / mates.length;
        const mvx = mates.reduce((s, o) => s + o.vx, 0) / mates.length;
        const pull = fish.school * 0.008;
        ax += (mx - fish.x) * pull * 0.3 + (mvx - fish.vx) * pull * 4;
        ay += (my - fish.y) * pull * 0.3;
      }
    }
    // keep a little space
    for (const o of world.fish) {
      if (o === fish) continue;
      const dx = fish.x - o.x;
      const dy = fish.y - o.y;
      const d = Math.hypot(dx, dy);
      const room = (fish.w + o.w) / 3;
      if (d > 0 && d < room) {
        ax += (dx / d) * 0.02;
        ay += (dy / d) * 0.02;
      }
    }
    // a gentle bob, and sinking back toward its height when idle
    ay += Math.sin((world.t + fish.x) / 20) * 0.002;
    fish.vx = (fish.vx + ax) * 0.97;
    fish.vy = (fish.vy + ay) * 0.9;
    const speed = Math.hypot(fish.vx, fish.vy);
    if (speed > maxSpeed) {
      fish.vx *= maxSpeed / speed;
      fish.vy *= maxSpeed / speed;
    }
    // fish swim forward: a fish too slow sideways keeps drifting the way it faces
    if (Math.abs(fish.vx) < 0.03) fish.vx = fish.dir * 0.03;
    fish.x += fish.vx;
    fish.y += fish.vy;
    [fish.x, fish.y] = clampGoal(fish, fish.x, fish.y);
    if (fish.x <= fish.w / 2 + 1.01 || fish.x >= TANK_W - fish.w / 2 - 1.01) fish.vx = -fish.vx; // turn at the glass
    if (Math.sign(fish.vx) !== fish.dir && Math.abs(fish.vx) > 0.02) fish.dir = Math.sign(fish.vx); // flip to face forward
    fish.z += (fish.tz - fish.z) * 0.01;
    fish.frame += 0.2 + speed * 2; // fins beat faster when swimming fast
  }

  function step(world) {
    world.t += 1;
    for (const fish of world.fish) stepFish(world, fish);
  }

  function drawFish(world, px, fish) {
    drawPet(px, fish.x - fish.w / 2, fish.y + fish.h / 2, fish.f.genes, fish.f.growth, {
      frame: Math.floor(fish.frame),
      faceLeft: fish.dir < 0,
      scale: world.scale,
      shadow: false,
    });
  }

  return { create, step, drawFish, features };
})();

// A whole tank, back to front: its look (cached), back pieces, far fish,
// middle pieces, near fish, front pieces, and the glass. `unit` is screen
// pixels per tank unit; `t` animates plants and bubbles.
function drawTankScene(ctx, unit, world, tank, t, cache = {}) {
  const key = `${tank.background}|${tank.substrate}|${unit}`;
  if (cache.key !== key) {
    const look = document.createElement("canvas");
    look.width = Math.round(TANK_W * unit);
    look.height = Math.round(TANK_H * unit);
    const lctx = look.getContext("2d");
    drawAquaLook((x, y, w, h, c) => {
      lctx.fillStyle = c;
      lctx.fillRect(x * unit, y * unit, w * unit, h * unit);
    }, tank.background, tank.substrate);
    cache.key = key;
    cache.look = look;
  }
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(cache.look, 0, 0);
  const px = (x, y, w, h, c) => {
    ctx.fillStyle = c;
    ctx.fillRect(x * unit, y * unit, w * unit, h * unit);
  };
  const items = world.items;
  const pieces = (layer) => {
    for (const p of tank.pieces) if (p.layer === layer && items[p.item_id]) drawAquaPiece(px, { id: p.item_id, ...items[p.item_id] }, p.x, p.y, p.flip, t + p.id * 7);
  };
  const fish = [...world.fish].sort((a, b) => a.z - b.z);
  pieces("back");
  for (const f of fish) if (f.z < 0.5) FishMotion.drawFish(world, px, f);
  pieces("middle");
  for (const f of fish) if (f.z >= 0.5) FishMotion.drawFish(world, px, f);
  pieces("front");
  px(0, 0, TANK_W, 1.2, "rgba(220, 240, 255, 0.35)"); // the water's surface
  px(2, 4, 0.8, TANK_H - 14, "rgba(255, 255, 255, 0.12)"); // glass shine
}
