/**
 * notion.ts
 * Client Notion léger pour l'app G2 — ResilientFlow AI
 *
 * Reproduit la logique de notion_client.py mais en TypeScript natif,
 * en utilisant fetch() (disponible dans le WebView des G2).
 *
 * Données lues : base "machines" (Équipements), machine P-17
 */

const NOTION_VERSION = '2022-06-28'
// En dev (proxy Vite), on évite CORS. En prod (Even Hub), appel direct.
const NOTION_BASE_URL = import.meta.env.DEV
  ? '/notion-api/v1'
  : 'https://api.notion.com/v1'

// Variables injectées par Vite au build (définies dans .env)
const NOTION_TOKEN      = import.meta.env.VITE_NOTION_TOKEN as string
const DB_MACHINES       = import.meta.env.VITE_NOTION_DB_MACHINES as string
const MACHINE_ID        = import.meta.env.VITE_MACHINE_ID as string || 'P-17'

// ── Types ─────────────────────────────────────────────────────────────────────

export interface MachineData {
  id:           string        // ex: "P-17"
  nom:          string        // ex: "Pompe P-17"
  statut:       string | null // ex: "Alerte", "Nominal", "Critique"
  rul_nominal_h: number | null // heures
  rul_jours:    number | null  // jours (calculé)
  seuil_temp:   number | null  // °C
  seuil_vib:    number | null  // mm/s
  seuil_pres:   number | null  // bar
  unite:        string | null  // ex: "Unité B"
  modele:       string | null
  derniere_maj: string         // ISO timestamp de la lecture
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function notionHeaders(): Record<string, string> {
  return {
    'Authorization':  `Bearer ${NOTION_TOKEN}`,
    'Notion-Version': NOTION_VERSION,
    'Content-Type':   'application/json',
  }
}

type NotionProp = Record<string, unknown>

function prop(page: Record<string, unknown>, name: string): unknown {
  const properties = page['properties'] as Record<string, NotionProp> | undefined
  if (!properties) return null
  const p = properties[name]
  if (!p) return null
  const t = p['type'] as string

  if (t === 'title') {
    const items = p['title'] as Array<{ plain_text: string }>
    return items?.map(r => r.plain_text).join('') ?? null
  }
  if (t === 'rich_text') {
    const items = p['rich_text'] as Array<{ plain_text: string }>
    return items?.map(r => r.plain_text).join('') ?? null
  }
  if (t === 'number')      return p['number'] ?? null
  if (t === 'select')      return (p['select'] as { name: string } | null)?.name ?? null
  if (t === 'multi_select') return (p['multi_select'] as Array<{ name: string }>).map(s => s.name)
  if (t === 'date')        return (p['date'] as { start: string } | null)?.start ?? null
  return null
}

function extractCode(nom: string): string {
  const m = nom.match(/\b([A-Z]+-\d+)\b/)
  return m ? m[1] : nom
}

function parseMachine(page: Record<string, unknown>): MachineData {
  const nom        = (prop(page, 'Équipement') as string) ?? ''
  const rul_h      = prop(page, 'RUL nominal (h)') as number | null

  return {
    id:            extractCode(nom),
    nom,
    statut:        prop(page, 'Statut') as string | null,
    rul_nominal_h: rul_h,
    rul_jours:     rul_h != null ? Math.round(rul_h / 24 * 10) / 10 : null,
    seuil_temp:    prop(page, 'Seuil Température (°C)') as number | null,
    seuil_vib:     prop(page, 'Seuil Vibration (mm/s)') as number | null,
    seuil_pres:    prop(page, 'Seuil Pression (bar)') as number | null,
    unite:         prop(page, 'Ligne de production') as string | null,
    modele:        prop(page, 'Modèle') as string | null,
    derniere_maj:  new Date().toISOString(),
  }
}

// ── API publique ───────────────────────────────────────────────────────────────

/**
 * Récupère les données de la machine P-17 (ou celle configurée via .env).
 * Lance une exception si l'appel échoue.
 */
export async function fetchMachine(machineId: string = MACHINE_ID): Promise<MachineData> {
  const url  = `${NOTION_BASE_URL}/databases/${DB_MACHINES}/query`
  const body = {
    filter: {
      property: 'Équipement',
      title:    { contains: machineId },
    },
  }

  const resp = await fetch(url, {
    method:  'POST',
    headers: notionHeaders(),
    body:    JSON.stringify(body),
  })

  if (!resp.ok) {
    throw new Error(`Notion API error ${resp.status}: ${await resp.text()}`)
  }

  const data   = await resp.json() as { results: Record<string, unknown>[] }
  const pages  = data.results

  if (!pages.length) {
    throw new Error(`Machine "${machineId}" introuvable dans Notion`)
  }

  // Si plusieurs entrées, garder celle avec le RUL le plus bas (plus critique)
  const machines = pages.map(parseMachine)
  machines.sort((a, b) => (a.rul_jours ?? 9999) - (b.rul_jours ?? 9999))
  return machines[0]
}

/**
 * Dérive le statut RUL à partir des jours restants (même logique que shared_state.py).
 * Utilisé en fallback si le champ Statut Notion n'est pas rempli.
 */
export function deriveStatut(rul_jours: number | null): 'Nominal' | 'Alerte' | 'Critique' {
  if (rul_jours == null) return 'Alerte'
  if (rul_jours > 60)   return 'Nominal'
  if (rul_jours > 2)    return 'Alerte'
  return 'Critique'
}
