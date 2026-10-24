// Pet sprites (PLAN.md 11c-2, phase 4): 8 species x 3 growth stages
// (baby, young, grown), recolored per coloring. Original placeholder art.
// Keyed by app/pets.py's species and coloring ids.
//
// Drawn facing right; petSprite() flips the right-hand pet so both face
// the character. Palette keys: n outline, a/A fur and its shadow,
// b belly/muzzle, e eyes, k nose/paws, p inner ears, f face (sheep),
// h horns (goat).
//
// Needs sprites.js loaded first.

const PET_ROWS = {
  cat: {
    baby: [".....n.n.", "....nanan", "n...naean", "an..naakn", ".annaaaan", "..naaaabn", "..nannann"],
    young: ["........n.n.", ".......npnpn", ".......naaan", "n......naean", "an.....naakn", ".an.nnnaaan.", "..nnaaaaaan.", "...naaaaabn.", "...nan..nan."],
    grown: [
      "..........n..n..", "..........npnnpn", "..........naaaan", "n.........naeaen", "an........nabkbn",
      "an...nnnnnnaaan.", ".an.naaaaaaaaan.", "..nnaaaaaaaaaan.", "...naaaaaaaabbn.", "...naAaaaaaAbbn.",
      "...nan.....nan..", "...nnn.....nnn..",
    ],
  },
  dog: {
    baby: [".....nnn.", "n...nAaan", "an..nAean", ".an.naaak", "..nnaaaan", "..naaaabn", "..nannann"],
    young: [".......nnnn.", "n.....nAaaan", "an....nAaean", ".an...nAaaak", "..nnnnnaaan.", "..naaaaaaan.", "..naaaaaabn.", "..nan..nan..", "..nnn..nnn.."],
    grown: [
      "..........nnnn..", "n........naaaan.", "an.......nAaaaan", ".an......nAaeaan", ".an......nAaaaak",
      "..an.nnnnnnaaan.", "...nnaaaaaaaaan.", "...naaaaaaaaaan.", "...naaaaaaaabbn.", "...naAaaaaaAbbn.",
      "...nan.....nan..", "...nnn.....nnn..",
    ],
  },
  fox: {
    baby: [".....n.n.", "....nanan", "bn..naean", "ban.nabbk", ".nnnaaaan", "..naaaabn", "..nknnkn."],
    young: ["........n.n.", ".......nanan", "nn.....naaen", "bbn....nabbk", "bAan.nnaaan.", ".nnaaaaaabn.", "...naaaaabn.", "...nkn.nkn..", "...nnn.nnn.."],
    grown: [
      "...........n.n..", "..........nanan.", "..........naaaan", "nn........naaean", "bbn.......naabbk",
      "bAan..nnnnnaaan.", ".nAaannaaaaaabn.", "..nnaaaaaaaaabn.", "...naaaaaaaabbn.", "...naAaaaaaAbbn.",
      "...nkn.....nkn..", "...nnn.....nnn..",
    ],
  },
  bunny: {
    baby: [".....n.n", "....npnp", "....naan", "....naek", ".nnnnaan", "nbaaaabn", ".nnnnnn."],
    young: [".......n.n.", "......npnpn", "......npnpn", "......naaan", "......naean", ".nnn..naakn", "nbaannnaan.", "nbaaaaaaabn", ".naAaaaAbn.", "..nnnnnnn.."],
    grown: [
      ".........nn.nn", "........napnap", "........napnap", "........napnap", "........nannan",
      "........naaaan", "........naeaan", "..nnnn..naaakn", ".nbaaannnaaan.", "nbbaaaaaaaaan.",
      "nbaaaaaaaaabn.", ".naaAaaaaAbbn.", "..nnnnnnnnnn..",
    ],
  },
  sheep: {
    baby: [".nnn.nn..", "naaanaan.", "naaaaannn", "naAaaanfn", "naaaaanek", ".naaaann.", "..nf.nf..", "..nn.nn.."],
    young: [
      "..nnn.nnn....", ".naaanaaan...", "naaAaaaAaannn", "naaaaaaaanffn", "naAaaaAaanfek",
      "naaaaaaaaann.", ".naaAaaaAan..", "..nnnnnnnn...", "...nf...nf...", "...nn...nn...",
    ],
    grown: [
      "...nnn.nnn.nnn...", "..naaanaaanaaan..", ".naaaaaaaaaaannnn", "naaAaaaAaaaaanffn", "naaaaaaaaaaanffen",
      "naAaaaAaaaAaanffk", "naaaaaaaaaaaann..", ".naaAaaaAaaaAan..", "..naaaaaaaaaan...", "...nnnnnnnnnn....",
      "....nf....nf.....", "....nf....nf.....", "....nn....nn.....",
    ],
  },
  goat: {
    baby: ["......h..", "n....nnan", "an...naen", ".annnnaak", "..naaaaan", "..naaAan.", "..nkn.nkn"],
    young: ["........hh..", ".......h.nn.", "n.....nnaaan", "an.....naean", ".an.nnnnaaak", "..nnaaaaaanb", "...naaaaaan.", "...naAaaAan.", "...nan..nan.", "...nkn..nkn."],
    grown: [
      "...........hhh..", "..........h.nnn.", "..........nnaaan", "n........nnaaean", "an........naaaak",
      "an...nnnnnnaaan.", ".nnnnaaaaaaaanb.", "...naaaaaaaaaan.", "...naaaaaaaaaan.", "...naAaaaaaAaan.",
      "...nan.....nan..", "...nan.....nan..", "...nkn.....nkn..",
    ],
  },
  llama: {
    baby: ["....n.n.", "....naan", "....naen", "....naak", "....nan.", "....nan.", "nn..nan.", "nannnan.", ".naaaan.", ".nnnnnn.", ".nkn.nkn"],
    young: [
      ".......n.n.", ".......naan", ".......naen", ".......naak", ".......naan", ".......nan.", ".......nan.",
      "nn.....nan.", "nannnnnnan.", ".naaaaaaan.", "naAaaaaAan.", ".nnnnnnnnn.", "..nan..nan.", "..nkn..nkn.",
    ],
    grown: [
      "..........n.n.", ".........nanan", ".........naaan", ".........naean", ".........naaak", ".........naaan",
      ".........naan.", ".........naan.", ".........naan.", ".........naan.", "nn.......naan.", "nan.nnnnnnaan.",
      ".naaaaaaaaaan.", "naaAaaaaAaaan.", "naaaaaaaaaaan.", ".nnnnnnnnnnn..", "..nan....nan..", "..nan....nan..",
      "..nkn....nkn..",
    ],
  },
  hedgehog: {
    baby: ["..nAnAn.", ".nAaAabn", "nAaAabek", "naAaAbbn", ".nnnnnn.", "..nb.nb."],
    young: ["...nAnAn...", "..nAaAaAn..", ".nAaAaAbbn.", "nAaAaAabebn", "naAaAaAbbbk", ".nAaAaAnnn.", "..nnnnnnn..", "...nb..nb.."],
    grown: [
      "....n.n.n.....", "...nAnAnAn....", "..nAaAaAaAnn..", ".nAaAaAaAabbn.", "nAaAaAaAabbebn",
      "naAaAaAaAbbbbk", "nAaAaAaAabbbn.", ".nAaAaAaAnnn..", "..nnnnnnnn....", "...nb..nb.....",
    ],
  },
};

// [a, A, b] per coloring, plus per-species extras.
const PET_COLORS = {
  cat: {
    orange: ["#e0882e", "#b0621e", "#fbe8c8"], gray: ["#9a9aa4", "#74747e", "#e8e8ec"],
    black: ["#3a3640", "#24212a", "#6a6470"], white: ["#f4f0e8", "#cfc8bc", "#ffffff"],
    tabby: ["#a07040", "#7a5228", "#f0d8b0"],
  },
  dog: {
    golden: ["#e0b060", "#b88a3e", "#fbe8c8"], brown: ["#8a5a2c", "#5e3c1c", "#d8b088"],
    black: ["#3a3640", "#24212a", "#a0a0a8"], white: ["#f4f0e8", "#cfc8bc", "#ffffff"],
    gray: ["#9a9aa4", "#74747e", "#e8e8ec"],
  },
  fox: { red: ["#d9682b", "#a84a1a", "#fbf1dc"], arctic: ["#f4f0e8", "#cfd8e0", "#ffffff"], silver: ["#8a8a96", "#5a5a66", "#e8e8ec"] },
  bunny: {
    white: ["#f4f0e8", "#cfc8bc", "#ffffff"], brown: ["#a07a52", "#7a5a3a", "#f0e0c8"],
    gray: ["#9a9aa4", "#74747e", "#e8e8ec"], cream: ["#f0dcb0", "#d0b88a", "#fff6e0"],
    black: ["#3a3640", "#24212a", "#e8e8ec"],
  },
  sheep: {
    white: ["#f4f0e8", "#d8d0c4", "#3a3640"], cream: ["#f0dcb0", "#d0b88a", "#5c3a1a"],
    gray: ["#b0b0b8", "#8a8a94", "#3a3640"], black: ["#4a4650", "#2a2630", "#1a1820"],
    pink: ["#f6c0d6", "#e098b8", "#5a3a4a"],
  },
  goat: {
    white: ["#f4f0e8", "#cfc8bc", "#e8e0d4"], brown: ["#8a5a2c", "#5e3c1c", "#d8b088"],
    black: ["#3a3640", "#24212a", "#6a6470"], tan: ["#c8a874", "#a0844f", "#f0dcb0"],
  },
  llama: {
    white: ["#f4f0e8", "#cfc8bc", "#ffffff"], brown: ["#8a5a2c", "#5e3c1c", "#d8b088"],
    cream: ["#f0dcb0", "#d0b88a", "#fff6e0"], gray: ["#9a9aa4", "#74747e", "#e8e8ec"],
  },
  hedgehog: { brown: ["#7a5636", "#4a301c", "#e8c79a"], cream: ["#d8c0a0", "#a89070", "#f6e6d0"], dark: ["#4a3a30", "#2a1e18", "#c8a888"] },
};

function petPalette(species, color) {
  const [a, A, b] = (PET_COLORS[species] || {})[color] || ["#c8a874", "#a0844f", "#f0dcb0"];
  // sheep faces/legs use the third color; everyone else's is a light belly
  return { n: INK, a, A, b, e: INK, k: INK, p: "#f6aacb", f: b, h: "#8a7a6a" };
}

// pet: {species, color, stage, slot}. Slot 1 stands bottom-right facing
// left, slot 2 bottom-left facing right -- both toward the character.
// `at` overrides the position (e.g. the pet room's big portraits).
function petSprite(pet, at = null) {
  const rows = (PET_ROWS[pet.species] || PET_ROWS.cat)[pet.stage] || PET_ROWS.cat.baby;
  const width = rows[0].length;
  const faceLeft = at ? at.faceLeft : pet.slot === 1;
  return {
    x: at ? at.x : pet.slot === 1 ? 47 - width : 1,
    y: at ? at.y : 46 - rows.length,
    rows: faceLeft ? rows.map((r) => [...r].reverse().join("")) : rows,
    palette: petPalette(pet.species, pet.color),
  };
}

// Dev guard: every species/stage in a sample coloring.
checkSprites(
  Object.fromEntries(
    Object.keys(PET_ROWS).flatMap((species) =>
      ["baby", "young", "grown"].map((stage) => [
        `pet_${species}_${stage}`,
        petSprite({ species, stage, color: Object.keys(PET_COLORS[species])[0], slot: 1 }),
      ])
    )
  )
);
