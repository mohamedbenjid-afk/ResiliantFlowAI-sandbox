/**
 * main.ts — RUL Pulse G2
 * Widget de surveillance RUL pour Even Realities G2
 *
 * Vues disponibles (navigation tempe gauche) :
 *   0 = Résumé (RUL + statut)
 *   1 = Détail capteurs live + seuils
 *   2..N = Pages de la prescription Lionel (si statut ≠ Nominal)
 *
 * Tempe droite → rafraîchissement RUL manuel
 * Tempe gauche → vue suivante (cycle)
 * Auto-refresh RUL toutes les 30s
 * Agent déclenché automatiquement dès statut ≠ Nominal
 */

import {
  EvenAppBridge,
  waitForEvenAppBridge,
  CreateStartUpPageContainer,
  TextContainerProperty,
  TextContainerUpgrade,
  OsEventTypeList,
  type EvenHubEvent,
} from '@evenrealities/even_hub_sdk'

import { fetchMachine, type MachineData } from './notion.ts'
import { fetchLiveRUL, fetchPrescription, type LiveRUL } from './rul_api.ts'

// ── Config ────────────────────────────────────────────────────────────────────

const REFRESH_MS     = Number(import.meta.env.VITE_REFRESH_INTERVAL_MS) || 5_000
const CONTAINER_ID   = 1
const CONTAINER_NAME = 'rul-display'

// ── État global ───────────────────────────────────────────────────────────────

let bridge: EvenAppBridge
let refreshTimer: ReturnType<typeof setInterval> | null = null

let currentView   = 0          // 0=résumé, 1=détail, 2..N=pages prescription
let prescPages:  string[] = [] // pages de la prescription en texte plain

let lastMeta: MachineData | null = null
let lastLive: LiveRUL | null = null
let isRefreshing  = false
let agentFetched  = false      // évite de relancer l'agent en boucle

// ── DEBUG tactile G2 ──────────────────────────────────────────────────────────
// Mettre à false une fois la gestuelle validée. Quand true, chaque événement
// reçu s'affiche sur les verres avec un compteur (pour voir si l'appui remonte).
const EVENT_DEBUG = false
let _evtCount = 0

// ── Formatage ─────────────────────────────────────────────────────────────────

// Largeur d'affichage G2 : au-delà de ~26 caractères la ligne repasse à la ligne.
// On tient tout sur 24 pour éviter tout retour à la ligne parasite.
const LINE_W = 24
const SEP_H = '━'.repeat(LINE_W)
const SEP_L = '─'.repeat(LINE_W)

function statusIcon(s: string): string {
  if (s === 'Critique') return '! CRITIQUE'
  if (s === 'Alerte')   return '▲ ALERTE'
  return '● NOMINAL'
}

function hhmm(): string {
  return new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
}

function totalViews(): number {
  return 2 + prescPages.length  // 0=résumé, 1=détail, 2..N=prescription
}

function buildSummaryView(live: LiveRUL, meta: MachineData | null): string {
  const lines = [
    SEP_H,
    `  RUL PULSE -- ${live.machine_id}`,
    SEP_H,
    `  STATUT : ${statusIcon(live.statut)}`,
    `  RUL    : ${live.rul_jours} jours`,
    `  UNITE  : ${meta?.unite ?? '--'}`,
    SEP_L,
    `  Vue 1/${totalViews()}  ${hhmm()}`,
    SEP_H,
  ]
  return lines.join('\n')
}

function buildDetailView(live: LiveRUL, meta: MachineData | null): string {
  return [
    SEP_H,
    `  DETAIL -- ${live.machine_id}`,
    SEP_H,
    `  STATUT : ${statusIcon(live.statut)}`,
    `  RUL    : ${live.rul_jours} jours`,
    SEP_L,
    `  TEMP : ${live.temperature} C`,
    `  VIB  : ${live.vibration} mm/s`,
    `  PRES : ${live.pression} bar`,
    SEP_L,
    `  T MAX   : ${meta?.seuil_temp != null ? `${meta.seuil_temp} C` : '--'}`,
    `  VIB MAX : ${meta?.seuil_vib  != null ? `${meta.seuil_vib} mm/s` : '--'}`,
    SEP_L,
    `  Vue 2/${totalViews()}  ${hhmm()}`,
    SEP_H,
  ].join('\n')
}

function buildPrescriptionView(pageIndex: number): string {
  const viewNum = 3 + pageIndex  // vue 3, 4, 5...
  const content = prescPages[pageIndex] ?? '(vide)'
  return [
    SEP_H,
    `  PRESCRIPTION p.${pageIndex + 1}/${prescPages.length}`,
    SEP_H,
    content,
    SEP_L,
    `  Vue ${viewNum}/${totalViews()}  ${hhmm()}`,
    SEP_H,
  ].join('\n')
}

function buildLoadingAgentView(): string {
  return [
    SEP_H,
    '  PRESCRIPTION LIONEL',
    SEP_H,
    '',
    '  Agent IA en cours...',
    '  (peut prendre 10-30s)',
    '',
    SEP_H,
  ].join('\n')
}

function buildLoadingView(): string {
  return [
    SEP_H,
    '  RUL PULSE -- P-17',
    SEP_H,
    '',
    '  Connexion...',
    '',
    SEP_H,
  ].join('\n')
}

function buildErrorView(msg: string): string {
  return [
    SEP_H,
    '  RUL PULSE -- ERREUR',
    SEP_H,
    '',
    `  ${msg.slice(0, 20)}`,
    '',
    `  Reessai...  ${hhmm()}`,
    SEP_H,
  ].join('\n')
}

// ── Affichage ─────────────────────────────────────────────────────────────────

async function updateDisplay(content: string): Promise<void> {
  await bridge.textContainerUpgrade(
    new TextContainerUpgrade({ containerID: CONTAINER_ID, containerName: CONTAINER_NAME, content })
  )
}

function currentViewContent(): string {
  if (!lastLive) return buildLoadingView()
  if (currentView === 0) return buildSummaryView(lastLive, lastMeta)
  if (currentView === 1) return buildDetailView(lastLive, lastMeta)
  // Vue prescription
  const pageIdx = currentView - 2
  if (prescPages.length === 0) return buildLoadingAgentView()
  return buildPrescriptionView(pageIdx)
}

// ── Agent Lionel ──────────────────────────────────────────────────────────────

async function loadPrescription(): Promise<void> {
  try {
    const resp = await fetchPrescription()
    if (resp.status === 'loading') {
      // Réessayer dans 5s
      setTimeout(() => { void loadPrescription() }, 5000)
      if (currentView >= 2) await updateDisplay(buildLoadingAgentView())
      return
    }
    if (resp.status === 'nominal') {
      prescPages = []
      return
    }
    if (resp.pages.length > 0) {
      prescPages = resp.pages
      agentFetched = true
      if (currentView >= 2) await updateDisplay(currentViewContent())
    }
  } catch {
    // Silencieux — l'agent n'est pas bloquant
  }
}

// ── Rafraîchissement RUL ──────────────────────────────────────────────────────

async function refresh(): Promise<void> {
  if (isRefreshing) return
  isRefreshing = true
  try {
    // RUL = source critique (api_rul). Notion (metadonnees machine) = optionnel :
    // une panne Notion ne doit PAS casser l'affichage du RUL sur les lunettes.
    const live = await fetchLiveRUL()
    if (!lastMeta) {
      try {
        lastMeta = await fetchMachine()
      } catch (e) {
        console.warn('[RUL Pulse] Notion indisponible (non bloquant):', e)
      }
    }
    lastLive = live

    // Déclencher l'agent si non-Nominal et pas encore fetché
    if (live.statut !== 'Nominal' && !agentFetched) {
      void loadPrescription()
    }
    // Réinitialiser le cache agent si on revient en Nominal
    if (live.statut === 'Nominal') {
      agentFetched = false
      prescPages   = []
      if (currentView >= 2) currentView = 0
    }

    await updateDisplay(currentViewContent())
  } catch (err) {
    await updateDisplay(buildErrorView(err instanceof Error ? err.message : 'Erreur'))
  } finally {
    isRefreshing = false
  }
}

function startAutoRefresh(): void {
  if (refreshTimer) clearInterval(refreshTimer)
  refreshTimer = setInterval(() => { void refresh() }, REFRESH_MS)
}

// ── Events G2 ─────────────────────────────────────────────────────────────────

function showCurrentView(): void {
  // Si on entre dans la zone prescription et que l'agent charge encore
  if (currentView >= 2 && prescPages.length === 0 && lastLive?.statut !== 'Nominal') {
    void updateDisplay(buildLoadingAgentView())
  } else {
    void updateDisplay(currentViewContent())
  }
}

function nextView(): void {
  currentView = (currentView + 1) % totalViews()
  showCurrentView()
}

function prevView(): void {
  currentView = (currentView - 1 + totalViews()) % totalViews()
  showCurrentView()
}

function handleEvent(event: EvenHubEvent): void {
  const sys  = event.sysEvent
  const text = event.textEvent
  const et   = sys?.eventType

  if (EVENT_DEBUG) {
    _evtCount++
    const anyEvt = event as unknown as Record<string, unknown>
    void updateDisplay([
      SEP_H, '  MODE DEBUG G2', SEP_H,
      '  EVENEMENTS RECUS : ' + _evtCount,
      '  sys.type = ' + String(sys?.eventType),
      '  sys.src  = ' + String(sys?.eventSource),
      '  txt.type = ' + String(text?.eventType),
      '  cles: ' + Object.keys(anyEvt).join(','),
      SEP_H,
    ].join('\n'))
    return
  }

  // ── Gestuelle G2 (mapping confirmé sur le firmware réel) ───────────────────
  // Valeurs brutes remontées par l'hôte (cf. enums OsEventTypeList / EventSourceType).
  const tt  = text?.eventType as unknown as number | undefined
  const src = sys?.eventSource as unknown as number | undefined

  // 1) GLISSEMENT sur la tempe → via textEvent :
  //      swipe bas = 2 (SCROLL_BOTTOM) → suivant ; swipe haut = 1 (SCROLL_TOP) → précédent
  if (tt === 2) { nextView(); return }   // SCROLL_BOTTOM_EVENT
  if (tt === 1) { prevView(); return }   // SCROLL_TOP_EVENT
  if (tt === 0) { nextView(); return }   // CLICK_EVENT (tap routé via textEvent)

  // 2) APPUI (tap) sur la tempe → via sysEvent (eventType undefined, seule la source compte) :
  //      gauche = 3 → suivant ; droite = 1 → précédent
  if (src === 3) { nextView(); return }  // TOUCH_EVENT_FROM_GLASSES_L
  if (src === 1) { prevView(); return }  // TOUCH_EVENT_FROM_GLASSES_R

  if (et === OsEventTypeList.FOREGROUND_ENTER_EVENT) {
    void refresh()
    startAutoRefresh()
  }
  if (et === OsEventTypeList.FOREGROUND_EXIT_EVENT) {
    if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null }
  }
}

// ── Démarrage ─────────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  bridge = await waitForEvenAppBridge()

  await bridge.createStartUpPageContainer(
    new CreateStartUpPageContainer({
      containerTotalNum: 1,
      textObject: [
        new TextContainerProperty({
          xPosition: 0, yPosition: 0,
          width: 576, height: 288,
          borderWidth: 0, borderColor: 0,
          paddingLength: 8,
          containerID: CONTAINER_ID,
          containerName: CONTAINER_NAME,
          content: buildLoadingView(),
          isEventCapture: 1,
        }),
      ],
    })
  )

  bridge.onEvenHubEvent(handleEvent)

  // ── Fallback clavier (surtout pour l'emulateur evenhub-simulator) ───────────
  // Fleche bas/droite = vue suivante ; haut/gauche = precedente ; R ou Espace = refresh.
  try {
    if (typeof window !== 'undefined' && window.addEventListener) {
      window.addEventListener('keydown', (e: KeyboardEvent) => {
        const k = e.key
        if (k === 'ArrowDown' || k === 'ArrowRight') { nextView() }
        else if (k === 'ArrowUp' || k === 'ArrowLeft') { prevView() }
        else if (k === 'r' || k === 'R' || k === ' ') { void refresh() }
        else return
        e.preventDefault()
      })
    }
  } catch { /* pas de window (contexte hardware) : ignore */ }

  await refresh()
  startAutoRefresh()
}

main().catch(err => { console.error('[RUL Pulse] Fatal:', err) })
