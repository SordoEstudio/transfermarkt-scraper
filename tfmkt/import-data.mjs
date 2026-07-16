/**
 * import-data.mjs — genera las content collections.
 *
 *   spec/players.json     (array, schema normalizado player_data_spec §7)
 *                         → src/content/players/<slug>.json
 *   mv_coaches_rich.json  (JSONL, TM verbatim)
 *                         → src/content/coaches/<code>.json
 *
 * Jugadores: dataset ya enriquecido (CMS-shaped). Acá solo se marca `featured`
 * y se MOCKEA el enriquecimiento manual (bio, scoutSummary, strengths,
 * highlightsUrl, officialPhoto) para los 3 primeros, hasta tener data real.
 *
 * Uso:  node scripts/import-data.mjs   (o `pnpm import-data`)
 */
import fs from 'node:fs';
import path from 'node:path';

const readJSONL = (f) =>
  fs.readFileSync(f, 'utf8').split(/\r?\n/).filter(Boolean).map((l) => JSON.parse(l));

function wipeJson(dir) {
  for (const f of fs.readdirSync(dir)) if (f.endsWith('.json')) fs.unlinkSync(path.join(dir, f));
}

/** Mock de enriquecimiento por slug — reemplazar con data real del CMS. */
const MOCK = {
  'gabriel-rojas': {
    bio: 'Lateral izquierdo de marcada vocación ofensiva, formado en San Lorenzo y con pasos por Peñarol y el fútbol mexicano antes de consolidarse en Racing Club. Su lectura del juego por la banda y la precisión en el último pase lo convirtieron en uno de los carrileros más constantes de la Liga Profesional. Zurdo de buen recorrido, combina solidez defensiva con llegada al área rival.',
    scoutSummary: 'Carrilero zurdo moderno: proyección, centros y sacrificio en las dos áreas. Rinde en esquemas de línea de cuatro y de tres.',
    strengths: ['Proyección ofensiva', 'Centros precisos', 'Resistencia física'],
    highlightsUrl: 'https://www.youtube.com/embed/L3374C3OyrY',
    officialPhoto: 'https://img.a.transfermarkt.technology/portrait/big/471639-1724348729.png?lm=1',
    preferredSystem: '4-3-3',
  },
  'ignacio-vazquez': {
    bio: 'Defensor central de fuerte presencia aérea y temperamento competitivo. Jerarquiza la última línea con anticipo y una salida limpia que habilita el juego asociado desde el fondo. Líder natural dentro del campo, ordena a sus compañeros y se impone en el juego directo.',
    scoutSummary: 'Central diestro dominante en el juego aéreo, seguro en el mano a mano y con buena primera salida. Perfil de líder defensivo.',
    strengths: ['Juego aéreo', 'Anticipo', 'Salida limpia'],
    highlightsUrl: 'https://www.youtube.com/embed/L3374C3OyrY',
    officialPhoto: 'https://img.a.transfermarkt.technology/portrait/big/552635-1771030896.jpg?lm=1',
    preferredSystem: '4-4-2',
  },
  'cesar-ibanez': {
    bio: 'Lateral izquierdo veloz y de mucho despliegue, capaz de cubrir todo el sector por su buen estado físico. Aporta amplitud en ataque y repliega con criterio. Su versatilidad le permite jugar también de extremo cuando el equipo lo requiere.',
    scoutSummary: 'Lateral-carrilero zurdo de gran motor. Velocidad, despliegue y polifuncionalidad por la izquierda.',
    strengths: ['Velocidad', 'Despliegue', 'Polifuncionalidad'],
    highlightsUrl: 'https://www.youtube.com/embed/L3374C3OyrY',
    officialPhoto: 'https://img.a.transfermarkt.technology/portrait/big/674391-1755535385.jpg?lm=1',
    preferredSystem: '3-5-2',
  },
  'lucas-vera': {
    bio: 'Mediocampista central de buen pie y gran lectura del juego. Equilibra recuperación y distribución, ordena el mediocampo y suma llegada al área rival. Constante en el ida y vuelta, es una pieza fiable para cualquier sistema de tres mediocampistas.',
    scoutSummary: 'Volante central box-to-box: recupera, distribuye limpio y aparece en el área. Motor del mediocampo.',
    strengths: ['Distribución', 'Recuperación', 'Llegada al área'],
    highlightsUrl: 'https://www.youtube.com/embed/L3374C3OyrY',
    preferredSystem: '4-3-3',
  },
};

// ── Players (dataset enriquecido) ────────────────────────────
const players = JSON.parse(fs.readFileSync('spec/players.json', 'utf8'));

// Backfill desde el scraper raw (no están en el enriquecido): nº camiseta y galería.
// Normalizadores compartidos jugadores↔técnicos (mismo shape en el raw).
// NOTA licencia: casi toda la galería es IMAGO `premium:true`. Se importa igual (el cliente
// quiere mostrarla); si hay que gatear por derechos, filtrar aquí por `!g.premium`.
const normGallery = (arr) => arr
  .filter((g) => g && g.url)
  .map((g) => ({ url: g.url, title: g.title ?? '', source: g.source ?? '' }));
const normAchievements = (arr) => arr
  .filter((a) => a && a.title)
  .map((a) => ({ title: a.title, count: Number(a.count) || 1 }));

const shirtByCode = {};
const galleryByCode = {};
const achByCode = {};
const natFlagByCode = {};
if (fs.existsSync('mv_players_rich.json')) {
  for (const r of readJSONL('mv_players_rich.json')) {
    if (!r.code) continue;
    const n = parseInt(String(r.shirt_number ?? '').replace(/[^\d]/g, ''), 10);
    if (Number.isFinite(n)) shirtByCode[r.code] = n;
    if (Array.isArray(r.gallery) && r.gallery.length) {
      galleryByCode[r.code] = normGallery(r.gallery);
    }
    if (Array.isArray(r.achievements) && r.achievements.length) {
      achByCode[r.code] = normAchievements(r.achievements);
    }
    // Bandera de selección (el transformado solo trae el nombre; ver FRONT_CHANGES §3).
    // `head` es cuadrada (150x150) → `small` (20x12) es rectangular como bandera.
    if (r.national_team?.is_national_team && r.national_team.flag_url) {
      natFlagByCode[r.code] = r.national_team.flag_url.replace('/flagge/head/', '/flagge/small/');
    }
  }
}
// `mv` parsea valor de mercado para elegir featured.
const mv = (s) => {
  if (!s) return 0;
  const n = parseFloat(String(s).replace('€', '').replace(/m|k/i, '').replace(',', '.'));
  return /m$/i.test(s) ? n * 1e6 : /k$/i.test(s) ? n * 1e3 : n || 0;
};
// Fotos oficiales locales en public/images/players (nombres flexibles).
// Match por tokens: el archivo debe contener firstName y lastName del jugador.
const norm = (s) => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
const photoDir = 'public/images/players';
const officialPhotoBySlug = {};
if (fs.existsSync(photoDir)) {
  const fileList = fs.readdirSync(photoDir).filter((f) => /\.(jpe?g|png|webp|avif)$/i.test(f));
  for (const p of players) {
    const first = norm(p.firstName);
    const last = norm(p.lastName);
    const matches = fileList.filter((f) => {
      const toks = norm(f.replace(/\.[^.]+$/, '')).split(/[_\-. ]+/);
      return toks.includes(first) && toks.includes(last);
    });
    if (matches.length) {
      // Si hay varias, preferir la que tenga "ft" (foto principal) o la más corta.
      const pick = matches.find((f) => /(^|[_\-. ])ft([_\-. ]|\.)/i.test(f)) ?? matches.sort((a, b) => a.length - b.length)[0];
      officialPhotoBySlug[p.slug] = `/images/players/${pick}`;
    }
  }
}

const mockSlugs = Object.keys(MOCK);
const topValue = [...players].sort((a, b) => mv(b.currentMarketValue) - mv(a.currentMarketValue))[0]?.slug;
const featured = new Set([...mockSlugs, topValue].filter(Boolean));

// "Without Club" (TM, sin club) → "Sin club" en todo texto de display.
const sinClub = (rec) => JSON.parse(JSON.stringify(rec).split('Without Club').join('Sin club'));

const pdir = 'src/content/players';
wipeJson(pdir);
for (const p of players) {
  const rec = sinClub({
    ...p,
    ...(shirtByCode[p.slug] != null ? { shirtNumber: shirtByCode[p.slug] } : {}),
    ...(galleryByCode[p.slug] ? { gallery: galleryByCode[p.slug] } : {}),
    ...(achByCode[p.slug] ? { achievements: achByCode[p.slug] } : {}),
    ...(natFlagByCode[p.slug] ? { nationalTeamFlag: natFlagByCode[p.slug] } : {}),
    featured: featured.has(p.slug),
    active: p.active ?? true,
    ...(MOCK[p.slug] ?? {}),
    // Foto oficial local (gana sobre el mock) si existe en /public/images/players.
    ...(officialPhotoBySlug[p.slug] ? { officialPhoto: officialPhotoBySlug[p.slug] } : {}),
  });
  fs.writeFileSync(path.join(pdir, `${p.slug}.json`), JSON.stringify(rec, null, 2));
}
console.log(`players: ${players.length} (featured: ${[...featured].join(', ')}; mock: ${mockSlugs.join(', ')})`);

// ── Coaches (TM verbatim) ────────────────────────────────────
const COACH_FEATURED = new Set(['jorge-sampaoli']);
// Enriquecimiento manual MOCK de técnicos (equivalente a MOCK de jugadores).
// Reemplazar con data real. Solo jorge-sampaoli por ahora.
const COACH_MOCK = {
  'jorge-sampaoli': {
    bio: 'Entrenador argentino de identidad marcada: presión alta, salida limpia desde el fondo y un juego de posición que busca dominar al rival con y sin pelota. Con pasos por Universidad de Chile, Sevilla, la Selección de Chile —campeón de la Copa América 2015— y la Selección Argentina, construyó una carrera internacional basada en equipos intensos y protagonistas.',
    scoutSummary: 'Perfil ideal para proyectos que priorizan protagonismo, presión coordinada y desarrollo de futbolistas jóvenes dentro de un modelo de juego claro.',
    strengths: ['Presión alta coordinada', 'Juego de posición', 'Gestión de plantel'],
    // Galería + palmarés = data REAL del raw (ver loop de coaches). highlights sigue MOCK (sin video real).
    highlightsUrl: 'https://www.youtube.com/embed/L3374C3OyrY',
  },
};
const coaches = readJSONL('mv_coaches_rich.json');
const cdir = 'src/content/coaches';
wipeJson(cdir);
for (const c of coaches) {
  const rec = sinClub({
    ...c,
    // Galería + palmarés reales (mismo shape que jugadores).
    ...(Array.isArray(c.gallery) && c.gallery.length ? { gallery: normGallery(c.gallery) } : {}),
    ...(Array.isArray(c.achievements) && c.achievements.length ? { achievements: normAchievements(c.achievements) } : {}),
    featured: COACH_FEATURED.has(c.code),
    active: true,
    ...(COACH_MOCK[c.code] ?? {}),
  });
  fs.writeFileSync(path.join(cdir, `${c.code}.json`), JSON.stringify(rec, null, 2));
}
console.log(`coaches: ${coaches.length} (featured: ${[...COACH_FEATURED].join(', ')}; mock: ${Object.keys(COACH_MOCK).join(', ')})`);
