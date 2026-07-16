# PLAYER_DATA_SPEC.md — MV Sports Agency
## Propuesta de enriquecimiento de datos · Jugadores

> Base: 78 jugadores scrapeados desde Transfermarkt
> Leyenda: ✅ Disponible en scraper · 🔧 Calculable/derivado · ✏️ Enriquecer manualmente

---

## 1. Card de jugador — vista grilla

Datos mínimos para la tarjeta en el catálogo. Todo viene del scraper, sin trabajo extra.

| Campo | Fuente | Cobertura | Uso visual |
|---|---|---|---|
| `image_url` (medium) | scraper | 78/78 | Foto principal |
| `name` / `last_name` | scraper | 78/78 | Nombre en card |
| `position` (label TM) | scraper | 78/78 | Badge de posición |
| `current_club.name` | scraper | 78/78 | Club actual |
| `current_club.logo_url` | scraper | 78/78 | Escudo del club |
| `citizenship` | scraper | 78/78 | Bandera de nacionalidad |
| `age` | 🔧 calcular desde `date_of_birth` | 78/78 | Edad debajo del nombre |
| `career_totals.appearances` | scraper | 78/78 | Stat 1: partidos |
| `career_totals.goals` | scraper | 78/78 | Stat 2: goles |
| `current_market_value` | scraper | 56/78 | Stat 3: valor de mercado |

**Criterio de diseño:** la card muestra exactamente 3 stats numéricos (partidos · goles · valor). Son los de mayor impacto visual y relevancia para el sector. El valor de mercado aparece solo si está disponible; si no, se omite el slot.

---

## 2. Ficha individual — header

### 2a. Identidad y contrato (desde scraper)

| Campo | Fuente | Cobertura | Nota |
|---|---|---|---|
| `image_url` (big) | scraper | 78/78 | Foto en alta resolución |
| `full_name` | scraper | 65/78 | Nombre en idioma del país natal |
| `main_position` | scraper | 75/78 | Posición principal |
| `other_positions` | scraper | 47/78 | Hasta 2 posiciones secundarias |
| `date_of_birth` → edad | 🔧 calcular | 78/78 | Mostrar edad + fecha |
| `place_of_birth.country` | scraper | 78/78 | País de nacimiento |
| `height` | 🔧 parsear `"1,82 m"` → `182` | 66/78 | En cm |
| `foot` | scraper | 67/78 | Pierna hábil |
| `citizenship` + `additional_citizenships` | scraper | 78/78 + 17/78 | Banderas de pasaportes |
| `current_club.name` + logo | scraper | 78/78 | Club con escudo |
| `contract_expires` | scraper | 78/78 | Fecha de vencimiento |
| `current_market_value` | scraper | 56/78 | Valor en EUR |
| `national_team.country` | scraper | parcial | Selección nacional si aplica |
| `international_caps` | scraper | parcial | Partidos internacionales |
| `shirt_number` | scraper | 38/78 | Número de camiseta |

### 2b. Enriquecimiento manual (✏️ — prioridad para el lanzamiento)

| Campo | Tipo | Prioridad | Descripción |
|---|---|---|---|
| `bio` | texto ~150 palabras | 🔴 Alta | Perfil profesional narrativo del jugador |
| `scout_summary` | texto ~50 palabras | 🔴 Alta | Descripción concisa para scouts y clubes |
| `strengths` | array de 3 tags | 🔴 Alta | Ej: `["Velocidad", "Presión alta", "Juego aéreo"]` |
| `highlights_url` | URL YouTube/Vimeo | 🟡 Media | Video de highlights para embed |
| `official_photo` | imagen URL | 🟡 Media | Foto oficial del club (mejor calidad que TM) |
| `preferred_system` | string | 🟢 Baja | Esquema táctico donde rinde mejor (ej: "4-3-3") |
| `agent_notes` | texto privado | 🟢 Baja | Notas internas (no mostrar en el sitio público) |

---

## 3. Bloque KPIs — impacto visual (4 números grandes)

Los 4 stats que se muestran en dorado debajo del header de la ficha. Son los de mayor peso visual y relevancia para scouts y clubes.

| # | Campo | Fuente | Fórmula |
|---|---|---|---|
| 1 | **Partidos de carrera** | ✅ `career_totals.appearances` | directo |
| 2 | **Goles de carrera** | ✅ `career_totals.goals` | directo |
| 3 | **Asistencias de carrera** | ✅ `career_totals.assists` | directo |
| 4 | **Goles cada 90 min** | 🔧 calcular | `(goals / minutes) × 90` |

> El G/90 es la métrica más valorada en el sector actualmente porque normaliza el rendimiento independientemente del tiempo de juego. Es el dato diferencial respecto a cualquier perfil básico de Transfermarkt.

---

## 4. Métricas derivadas

Calculables 100% desde los datos del scraper, sin trabajo manual adicional.

| Campo | Fórmula | Disponibilidad |
|---|---|---|
| `age` | `today - date_of_birth` en años | 78/78 |
| `goals_per_90` | `(career_totals.goals / career_totals.minutes) × 90` | 78/78 |
| `assists_per_90` | `(career_totals.assists / career_totals.minutes) × 90` | 78/78 |
| `goal_contributions` | `career_totals.goals + career_totals.assists` | 78/78 |
| `goal_contributions_per_90` | `(goal_contributions / career_totals.minutes) × 90` | 78/78 |
| `seasons_active` | `count(stats_by_season)` | 77/78 |
| `career_span_years` | `last_season - first_season` en stats_by_season | 77/78 |
| `avg_goals_per_season` | `career_totals.goals / seasons_active` | 77/78 |
| `clubs_count` | `count(clubs_history)` | 75/78 |
| `countries_played` | `count(unique countries en clubs_history)` | 75/78 |
| `leagues_played` | ligas distintas (set de clubs_history) | 75/78 |
| `contract_months_left` | `contract_expires - today` en meses | 78/78 |
| `min_per_appearance` | `career_totals.minutes / career_totals.appearances` | 78/78 |
| `transfer_fee_sum` | ✅ directo desde scraper | 78/78 |

---

## 5. Temporada actual — stats en curso

Primer elemento de `stats_by_season` (temporada más reciente).

| Campo | Cobertura | Uso |
|---|---|---|
| `appearances` | 77/78 | Partidos esta temporada |
| `goals` | 77/78 | Goles esta temporada |
| `assists` | 77/78 | Asistencias esta temporada |
| `minutes` | 77/78 | Minutos jugados |
| `yellow_cards` | 77/78 | ⚠️ No mostrar (dato negativo) |
| `market_value_last_update` | 56/78 | Fecha de última actualización del valor |

---

## 6. Historial de clubes y transferencias

### Clubs history (75/78 · promedio 4.7 clubes por jugador)

| Campo por entrada | Fuente | Nota |
|---|---|---|
| `club.name` | scraper | |
| `club.logo_url` | scraper | via href de TM |
| `club.country` | scraper | |
| `seasons` | scraper | rango de temporadas |
| `stats` | 🔧 join con `stats_by_season` | por `season_id` |

### Transfers (75/78 · promedio 6.6 transferencias por jugador · máx 19)

| Campo por entrada | Fuente | Nota |
|---|---|---|
| `date` / `season` | scraper | |
| `from` / `to` (club + href) | scraper | |
| `fee` | scraper | monto pagado |
| `market_value` (snapshot) | scraper | valor al momento |
| 🔧 `fee_vs_value_ratio` | calcular | `fee / market_value` |

---

## 7. Schema TypeScript (Content Collection)

```typescript
// src/content/config.ts

const Position = z.enum([
  'goalkeeper',
  'right-back', 'left-back', 'center-back',
  'defensive-mid', 'central-mid', 'attacking-mid',
  'right-winger', 'left-winger',
  'striker', 'second-striker'
])

const CareerEntry = z.object({
  club: z.string(),
  clubLogo: z.string().url().optional(),
  country: z.string(),
  from: z.string(),             // "2020" o "2020-07"
  to: z.string().optional(),    // undefined = actual
  appearances: z.number().optional(),
  goals: z.number().optional(),
  assists: z.number().optional(),
  minutes: z.number().optional(),
})

const TransferEntry = z.object({
  date: z.string(),
  season: z.string(),
  fromClub: z.string(),
  toClub: z.string(),
  fee: z.string().optional(),           // "€500k", "Gratis", "Préstamo"
  marketValueAtTime: z.string().optional(),
})

const StatsBySeason = z.object({
  seasonId: z.string(),           // "24/25"
  club: z.string(),
  appearances: z.number(),
  goals: z.number(),
  assists: z.number(),
  minutes: z.number(),
  yellowCards: z.number().optional(),
})

export const players = defineCollection({
  type: 'data',
  schema: z.object({

    // — Identidad (scraper) —
    id: z.string(),
    slug: z.string(),
    firstName: z.string(),
    lastName: z.string(),
    fullName: z.string().optional(),
    shirtNumber: z.number().optional(),
    dateOfBirth: z.string(),            // ISO: "1988-07-24"
    placeOfBirth: z.object({
      city: z.string().optional(),
      country: z.string(),
    }),
    height: z.number().optional(),      // cm: 182
    foot: z.enum(['left', 'right', 'both']).optional(),
    citizenship: z.string(),
    additionalCitizenships: z.array(z.string()).optional(),

    // — Posición (scraper) —
    position: Position,
    mainPosition: Position.optional(),
    otherPositions: z.array(Position).optional(),

    // — Club y contrato (scraper) —
    currentClub: z.string(),
    currentClubLogo: z.string().url().optional(),
    currentClubCountry: z.string().optional(),
    joined: z.string().optional(),
    contractExpires: z.string().optional(),  // ISO: "2026-06-30"

    // — Valor de mercado (scraper) —
    currentMarketValue: z.string().optional(),   // "€1.200.000"
    marketValueLastUpdate: z.string().optional(),

    // — Selección nacional (scraper, parcial) —
    nationalTeam: z.string().optional(),
    internationalCaps: z.number().optional(),
    internationalGoals: z.number().optional(),

    // — Totales de carrera (scraper) —
    careerTotals: z.object({
      appearances: z.number(),
      goals: z.number(),
      assists: z.number(),
      minutes: z.number(),
    }),
    transferFeeSum: z.string().optional(),

    // — Históricos (scraper) —
    career: z.array(CareerEntry),
    transfers: z.array(TransferEntry).optional(),
    statsBySeason: z.array(StatsBySeason).optional(),

    // — Enriquecimiento manual —
    bio: z.string().optional(),
    scoutSummary: z.string().optional(),
    strengths: z.array(z.string()).max(3).optional(),
    highlightsUrl: z.string().url().optional(),
    officialPhoto: z.string().optional(),
    preferredSystem: z.string().optional(),

    // — Meta —
    image: z.string().optional(),        // path en /public/images/players/
    transfermarktId: z.string().optional(),
    transfermarktUrl: z.string().url().optional(),
    category: z.enum(['professional', 'youth']).default('professional'),
    featured: z.boolean().default(false),
    active: z.boolean().default(true),
  })
})
```

---

## 8. Helpers calculados (`src/lib/players.ts`)

```typescript
// Edad
export function computeAge(dateOfBirth: string): number {
  const birth = new Date(dateOfBirth)
  const today = new Date()
  let age = today.getFullYear() - birth.getFullYear()
  const m = today.getMonth() - birth.getMonth()
  if (m < 0 || (m === 0 && today.getDate() < birth.getDate())) age--
  return age
}

// Goles cada 90 minutos
export function goalsPer90(goals: number, minutes: number): number {
  if (!minutes) return 0
  return Math.round((goals / minutes) * 90 * 100) / 100
}

// Participaciones en gol (goles + asistencias)
export function goalContributions(goals: number, assists: number): number {
  return goals + assists
}

// Meses restantes de contrato
export function contractMonthsLeft(contractExpires: string): number {
  const exp = new Date(contractExpires)
  const today = new Date()
  return Math.max(
    0,
    (exp.getFullYear() - today.getFullYear()) * 12 +
    (exp.getMonth() - today.getMonth())
  )
}

// Parsear altura desde string TM ("1,82 m" → 182)
export function parseHeight(raw: string): number {
  return Math.round(parseFloat(raw.replace(',', '.')) * 100)
}

// Países distintos jugados
export function countriesPlayed(career: CareerEntry[]): string[] {
  return [...new Set(career.map(e => e.country))]
}

// URL de Transfermarkt
export function transfermarktUrl(id: string): string {
  return `https://www.transfermarkt.com.ar/player/profil/spieler/${id}`
}

// Posición en español
export const positionLabels: Record<string, string> = {
  'goalkeeper':      'Arquero',
  'right-back':      'Lateral derecho',
  'left-back':       'Lateral izquierdo',
  'center-back':     'Defensor central',
  'defensive-mid':   'Mediocampista defensivo',
  'central-mid':     'Mediocampista central',
  'attacking-mid':   'Mediocampista ofensivo',
  'right-winger':    'Extremo derecho',
  'left-winger':     'Extremo izquierdo',
  'striker':         'Delantero centro',
  'second-striker':  'Segundo delantero',
}
```

---

## 9. Datos a omitir en v1

| Campo | Motivo |
|---|---|
| `injuries` (39/78) | Dato negativo, bajo llenado, no mostrar en catálogo de representados |
| `outfitter` (4/78) | Irrelevante para el sector, cobertura mínima |
| `last_contract_extension` (10/78) | Bajo llenado, poca relevancia visual |
| `gallery` (35/78, premium TM) | Imágenes de TM son premium; usar fotos propias |
| `achievements` (25/78) | Bajo llenado; si se suma, va en v2 como sección opcional |
| `yellow_cards` total | Dato negativo; no se exhibe en perfil de representado |
| `own_goals` | Dato negativo |
| `upcoming_transfers` | Son rumores, no confirmados |
| `stats_by_season` completo (gráfico) | Reservado para v2 como componente interactivo |

---

## 10. Roadmap de datos por etapa

### Etapa 1 — MVP (lanzamiento)
- ✅ Todo el scraper disponible (identidad, club, contrato, totales, clubs_history)
- 🔧 Métricas calculadas (age, G/90, contributions, contract_months_left)
- ✏️ bio + scout_summary + strengths para jugadores `featured: true` (prioridad)

### Etapa 2 — Post-lanzamiento
- ✏️ bio + scout_summary para todos los jugadores activos
- ✏️ highlights_url para el 50% de la plantilla
- 📊 Gráfico de evolución de valor de mercado por temporada (stats_by_season)
- 📊 Gráfico de goles por temporada (sparkline)

### Etapa 3 — Evolución
- 🔄 Integración directa con API de Transfermarkt (actualización automática)
- 🔍 Filtro "libre en menos de 6 meses" (via contract_months_left)
- 🌐 Fichas en español + inglés + portugués

---

*Harvi Digital — Proyecto MV Sports Agency*
*Versión 1.0 — Junio 2026*