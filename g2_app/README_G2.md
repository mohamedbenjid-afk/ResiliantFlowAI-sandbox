# RUL Pulse — Even Realities G2

Widget de surveillance en temps réel pour la Pompe P-17 — ResilientFlow AI.

---

## Prérequis

- Node.js ≥ 20
- Even Realities G2 + app Even Hub (iOS/Android)
- Token Notion (demander à Mohamed)

---

## Setup

```bash
cd g2_app
npm install

# Configurer les variables d'environnement
cp .env.example .env
# → Éditer .env et renseigner VITE_NOTION_TOKEN
```

---

## Lancer le simulateur (sans les lunettes)

```bash
npm run simulator
# Ouvrir http://localhost:4200 dans un navigateur
# Le simulateur émule l'affichage 576×288px des G2
```

---

## Tester sur les G2 (via QR code)

```bash
npm run dev
# → L'app Even Hub scanne le QR code affiché dans le terminal
# → L'app se charge sur les lunettes en temps réel
```

> ⚠️ Note : en mode développement (QR), le CORS de Notion peut bloquer les appels.
> Utiliser un proxy local si nécessaire (`vite.config.ts` → `server.proxy`).

---

## Build et déploiement sur Even Hub

```bash
npm run build
# → Dossier dist/ généré

# Uploader dist/ sur hub.evenrealities.com via l'interface développeur
# L'app est ensuite installable depuis Even Hub par les utilisateurs G2
```

---

## Utilisation

| Action | Résultat |
|---|---|
| Démarrage | Chargement + fetch Notion automatique |
| Tempe droite (tap) | Rafraîchissement manuel immédiat |
| Tempe gauche (tap) | Bascule Résumé ↔ Détail |
| Auto | Rafraîchissement toutes les 30 secondes |
| App en arrière-plan | Timer suspendu (reprise au retour) |

### Vue Résumé

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ◆ RUL PULSE — P-17
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  STATUT  : ▲ ALERTE
  RUL     : 47.0 jours
  UNITÉ   : Ligne 2
─────────────────────────────────
  [◄] Détails   [►] Refresh  14:32
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Vue Détail (tempe gauche)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ◆ DÉTAIL — P-17
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  STATUT  : ▲ ALERTE
  RUL     : 47.0 jours
─────────────────────────────────
  T° MAX  : 75 °C
  VIB MAX : 2.0 mm/s
  PRES MAX: 6.0 bar
─────────────────────────────────
  MODÈLE  : Pompe centrifuge X200
─────────────────────────────────
  [◄] Résumé     MAJ: 14:32
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Structure des fichiers

```
g2_app/
├── package.json       — Dépendances npm
├── tsconfig.json      — Config TypeScript
├── vite.config.ts     — Config Vite
├── app.json           — Manifest Even Hub
├── index.html         — Entrée HTML
├── .env.example       — Template variables d'env
├── .env               — (gitignored) Token Notion + config
└── src/
    ├── main.ts        — Logique G2, affichage, events
    └── notion.ts      — Client Notion (fetch machine P-17)
```

---

## Variables d'environnement

| Variable | Description | Défaut |
|---|---|---|
| `VITE_NOTION_TOKEN` | Token d'intégration Notion | **obligatoire** |
| `VITE_NOTION_DB_MACHINES` | ID base Équipements ESCP | pré-rempli |
| `VITE_MACHINE_ID` | Code machine à surveiller | `P-17` |
| `VITE_REFRESH_INTERVAL_MS` | Intervalle auto-refresh | `30000` |
