// Zebot sprite: original 32x32 pixel art ("Monitor-Rack"), drawn in code.
// A CRT head with an antenna on top of a small rack body whose drive-bay LEDs
// follow the mood. Palette: "Petróleo nocturno".

export const SIZE = 32;

const C = {
  K: "#0B1622", // outline
  D: "#13283A", // dark body
  B: "#0B6E75", // petrol
  L: "#2EC4B6", // light petrol
  W: "#E6EDF3", // highlight
  S: "#06111A", // screen
  V: "#9D8CFF", // violet accent
  A: "#FFC857", // amber (tired)
  R: "#FF6B6B", // red (exhausted)
  Z: "#2A4A5A", // dim (asleep)
};

export const MOODS = ["feliz", "normal", "cansado", "triste", "agotado", "dormido"];

const FACE = { feliz: C.L, normal: C.L, cansado: C.A, triste: C.V, agotado: C.R, dormido: C.Z };
const TIP = { feliz: C.V, normal: C.L, cansado: C.A, triste: C.V, agotado: C.R, dormido: C.Z };

function painter(ctx) {
  const rect = (x, y, w, h, c) => { ctx.fillStyle = c; ctx.fillRect(x, y, w, h); };
  return { rect, px: (x, y, c) => rect(x, y, 1, 1, c) };
}

// Face in a 16x10 area at (ox, oy): eyes + mouth.
function face(g, ox, oy, mood, t) {
  const c = FACE[mood];
  const blink = mood !== "dormido" && mood !== "agotado" && t % 3200 < 140;
  for (const ex of [ox + 3, ox + 10]) {
    const ey = oy + 2;
    if (blink) { g.rect(ex, ey + 2, 3, 1, c); continue; }
    switch (mood) {
      case "feliz": g.px(ex, ey + 2, c); g.px(ex + 1, ey + 1, c); g.px(ex + 2, ey + 2, c); break;
      case "normal": g.rect(ex, ey, 3, 3, c); g.px(ex, ey, C.W); break;
      case "cansado": g.rect(ex, ey + 2, 3, 1, c); g.rect(ex, ey + 1, 3, 1, C.D); break;
      case "triste":
        g.rect(ex, ey + 1, 3, 2, c);
        g.px(ex === ox + 3 ? ex + 2 : ex, ey - 1, c);
        if (ex === ox + 3 && Math.floor(t / 400) % 2) g.px(ex, ey + 4, C.V);
        break;
      case "agotado": [[0, 0], [2, 0], [1, 1], [0, 2], [2, 2]].forEach(([a, b]) => g.px(ex + a, ey + b, c)); break;
      case "dormido": g.rect(ex, ey + 2, 3, 1, c); break;
    }
  }
  const mx = ox + 5, my = oy + 7;
  switch (mood) {
    case "feliz": g.px(mx, my - 1, c); g.rect(mx + 1, my, 4, 1, c); g.px(mx + 5, my - 1, c); break;
    case "normal": g.px(mx + 1, my - 1, c); g.rect(mx + 2, my, 2, 1, c); g.px(mx + 4, my - 1, c); break;
    case "cansado": g.rect(mx + 2, my, 3, 1, c); break;
    case "triste": g.px(mx + 1, my + 1, c); g.rect(mx + 2, my, 2, 1, c); g.px(mx + 4, my + 1, c); break;
    case "agotado": for (let i = 0; i < 6; i++) g.px(mx + i, my + (i % 2), c); break;
    case "dormido": g.rect(mx + 2, my, 2, 1, c); break;
  }
}

function leds(mood, t) {
  const on = Math.floor(t / 350) % 2 === 0;
  return {
    feliz: [C.L, on ? C.V : C.L, C.V],
    normal: [C.L, on ? C.L : C.B, C.B],
    cansado: [C.A, on ? C.A : C.D, C.D],
    triste: [C.V, C.D, C.D],
    agotado: [on ? C.R : C.D, C.D, C.D],
    dormido: [C.Z, C.D, C.D],
  }[mood];
}

function zzz(g, x, y, t) {
  const frames = Math.floor(t / 500) % 3;
  const z = [[0, 0], [1, 0], [2, 0], [1, 1], [0, 2], [1, 2], [2, 2]];
  for (let i = 0; i <= frames; i++) z.forEach(([a, b]) => g.px(x + i * 3 + a, y - i * 3 + b, C.Z));
}

/**
 * Draw Zebot.
 * @param {CanvasRenderingContext2D} ctx 32x32 context
 * @param {string} mood one of MOODS
 * @param {number} t time in ms
 * @param {{jump?: number, wave?: boolean}} fx jump: 0..1 progress of a hop; wave: raise right arm
 */
export function drawZebot(ctx, mood, t, fx = {}) {
  const g = painter(ctx);
  ctx.clearRect(0, 0, SIZE, SIZE);
  const still = mood === "dormido" || mood === "agotado";
  let y = still ? 0 : Math.floor(t / 450) % 2;
  if (fx.jump) y -= Math.round(Math.sin(Math.PI * fx.jump) * 4);
  const slump = mood === "agotado" ? 1 : 0; // head sinks into the body

  // Antenna
  const tipOn = Math.floor(t / 600) % 2 && mood !== "dormido";
  g.rect(15, 1 + y + slump, 2, 3, C.K);
  g.rect(14, 0 + y + slump, 4, 2, C.K);
  g.rect(15, 0 + y + slump, 2, 1, tipOn ? TIP[mood] : C.D);

  // CRT head
  const hy = y + slump;
  g.rect(6, 4 + hy, 20, 14, C.K);
  g.rect(7, 5 + hy, 18, 12, C.B);
  g.rect(7, 5 + hy, 18, 1, C.L);
  g.rect(7, 5 + hy, 1, 11, C.L);
  g.rect(9, 7 + hy, 14, 8, mood === "dormido" ? "#040B11" : C.S);
  face(g, 8, 6 + hy, mood, t);

  // Neck + rack body with three drive bays
  g.rect(13, 18 + y, 6, 1, C.K);
  g.rect(14, 18 + y, 4, 1, C.B);
  g.rect(8, 19 + y, 16, 10, C.K);
  g.rect(9, 20 + y, 14, 8, C.D);
  const l = leds(mood, t);
  for (let i = 0; i < 3; i++) {
    const by = 20 + i * 3 + y;
    g.rect(10, by, 12, 2, C.B);
    g.rect(10, by, 12, 1, C.L);
    g.px(20, by + 1, l[i]);
    g.px(18, by + 1, l[(i + 1) % 3]);
  }

  // Arms (raised when happy or waving)
  g.rect(6, 20 + y, 2, 5, C.K);
  if (fx.wave) {
    const up = Math.floor(t / 200) % 2;
    g.rect(24, 15 + y - up, 2, 5, C.K);
    g.px(25, 14 + y - up, C.L);
  } else {
    g.rect(24, 20 + y, 2, 5, C.K);
  }
  if (mood === "feliz" && !fx.wave) { g.rect(5, 17 + y, 2, 3, C.K); g.rect(25, 17 + y, 2, 3, C.K); }

  // Legs and floor shadow
  g.rect(10, 29 + y, 3, 2, C.K);
  g.rect(19, 29 + y, 3, 2, C.K);
  ctx.globalAlpha = fx.jump ? 0.25 : 1;
  g.rect(9, 31, 5, 1, C.D);
  g.rect(18, 31, 5, 1, C.D);
  ctx.globalAlpha = 1;

  if (mood === "dormido") zzz(g, 23, 2 + y, t);
}
