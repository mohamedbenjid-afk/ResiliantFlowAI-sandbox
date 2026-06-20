# BRIEFING CLAUDE — Antoine (Directeur Technique)
# À coller au début de ta session pour donner le contexte complet

---

## ⚠️ RÈGLES DE TRAVAIL — ENVIRONNEMENT SANDBOX

> **Tu travailles UNIQUEMENT dans l'environnement sandbox.** Aucune modification sur le repo de production ni sur les bases Notion de production.

| Règle | Détail |
|---|---|
| **Repo GitHub** | Travailler exclusivement sur `mohamedbenjid-afk/ResiliantFlowAI-sandbox` — branche `develop` |
| **Bases Notion** | Utiliser uniquement les bases préfixées `[SANDBOX]` — ne jamais toucher aux bases sans préfixe |
| **Création de base** | Toute nouvelle base Notion **doit** commencer par `[SANDBOX] ` (ex : `[SANDBOX] Ma Nouvelle Base`) |
| **Déploiement** | Tester sur l'app Streamlit sandbox uniquement — ne jamais déployer sur l'app de production |
| **Accord requis** | Toute création de base Notion doit être signalée à Mohamed avant ou après création |

---

## Contexte projet

**ResilientFlow AI** — démonstrateur de maintenance prescriptive Industrie 4.0 (projet fin d'études ESCP).
Stack : Python · Streamlit · Notion API · LLM via 1min.ai.
Machine surveillée : **Pompe P-17, Unité B**.

Repo GitHub (sandbox) : `mohamedbenjid-afk/ResiliantFlowAI-sandbox` (branche `develop`).

**Ne touche jamais** : `shared_state.py`, `notion_client.py`, `llm_client.py`, `streamlit_app.py`, `streamlit_home.py`.

---

## Ton périmètre : Antoine — Directeur Technique

| Fichier | État actuel | À faire |
|---|---|---|
| `pages/3_Antoine.py` | ⚠️ Page fonctionnelle mais à améliorer | Améliorer sidebar + structure |
| `agents/agent_antoine.py` | ❌ DB IDs INCORRECTS + champs erronés | Corriger les IDs et les champs |

---

## Simulateur capteurs — comment ça marche

```python
from shared_state import init_session_state, update_sensors, COMMON_CSS
init_session_state()
c_temp, c_vib, c_pres, c_cur, c_rul, r_status, rul_pct = update_sensors()
# c_rul = RUL en heures (0-100 dans le simulateur)
# r_status = "Nominal" | "Alerte" | "Critique"
# rul_pct = pourcentage restant
```

---

## Bases Notion ESCP — IDs CORRECTS

```python
DB_IDS = {
    "machines":   "6653da63-bd5a-4191-815c-576b8c7fcfbc",
    "equipe":     "3856b2ff-be3d-8151-8b3f-ee79dee0bc2b",
    "pieces":     "ef896795-bd1a-4b20-a8ea-f121c9f846ff",
    "ordres_fab": "687e40c2-a3ff-4de0-be55-20cf411f5dd6",
    "historique": "94babab5-03bb-4c4d-9053-08d5bff301e3",
    "hse_docs":   "3856b2ff-be3d-816f-a163-ef4f8e43499d",
}
```

> ⚠️ Le fichier `agents/agent_antoine.py` actuel utilise des IDs **INCORRECTS** (ancienne base) :
> - `DB_MACHINES   = "5279cb2a..."` → doit être `"6653da63-bd5a-4191-815c-576b8c7fcfbc"`
> - `DB_ORDRES_FAB = "d7ee45da..."` → doit être `"687e40c2-a3ff-4de0-be55-20cf411f5dd6"`
> - `DB_HISTORIQUE = "6f53558b..."` → doit être `"94babab5-03bb-4c4d-9053-08d5bff301e3"`
> - `DB_PIECES     = "c22138ba..."` → doit être `"ef896795-bd1a-4b20-a8ea-f121c9f846ff"`

---

## Schéma Notion ESCP — Noms de champs CORRECTS

### Base Machines / Équipements (`machines`)
| Champ dans l'agent actuel (ERRONÉ) | Champ ESCP correct |
|---|---|
| `"Nom Machine"` (title filter) | `"Équipement"` (title) |
| `"RUL (jours)"` (number) | ❌ N'existe pas → utiliser `"RUL nominal (h)"` ÷ 24 |
| `"Score dégradation (%)"` | ❌ N'existe pas en ESCP → retourner None |
| `"Température actuelle (°C)"` | ❌ N'existe pas → retourner None |
| `"Vibration actuelle (mm/s)"` | ❌ N'existe pas → retourner None |
| `"Seuil température (°C)"` | `"Seuil Température (°C)"` |
| `"Seuil vibration (mm/s)"` | `"Seuil Vibration (mm/s)"` |
| `"Unité / Zone"` | `"Ligne de production"` |
| `"Responsable"` | `"Technicien référent"` |
| `"Dernière inspection"` | ❌ N'existe pas → None |
| `"Prochaine maintenance"` | ❌ N'existe pas → None |
| `"Notes IA"` | `"Notes"` |

Champs qui **existent** dans ESCP : `"Statut"` (select), `"Type"`, `"Modèle"`, `"Fabricant"`, `"N° de série"`, `"Heures de fonctionnement total"`, `"Date de mise en service"`, `"Seuil Pression (bar)"`

Valeurs de `Statut` dans ESCP : `"Nominal"`, `"Alerte"`, `"Critique"`, `"Hors service"`

### Base Historique (`historique`)
| Champ dans l'agent actuel (ERRONÉ) | Champ ESCP correct |
|---|---|
| `"Machine"` (rich_text filter) | `"Équipement"` (rich_text) |
| `"Titre intervention"` (title) | `"Intervention"` (title) |
| `"Type"` | `"Type d'intervention"` |
| `"Statut"` → valeur `"Terminée"` | `"Statut"` → valeur **`"Réalisée"`** |
| `"Type"` → valeur `"Panne corrective"` | → valeur **`"Corrective"`** |
| `"Type"` → valeur `"Maintenance prescriptive"` | → valeur **`"Prédictive"`** |
| `"Coût intervention (€)"` | `"Coût estimé (€)"` |
| `"Coût arrêt production (€)"` | ❌ N'existe pas → 0.0 |
| `"Date intervention"` | `"Date planifiée"` |
| `"RUL avant intervention (j)"` | ❌ N'existe pas → None |
| `"RUL après intervention (j)"` | ❌ N'existe pas → None |
| `"Cause racine"` | ❌ N'existe pas → None |

Champs qui **existent** : `"Durée estimée (h)"` ✓, `"Durée réelle (h)"` ✓, `"Priorité"` ✓, `"Technicien assigné"` ✓

### Base Ordres de Fabrication (`ordres_fab`)
| Champ actuel (ERRONÉ) | Champ ESCP correct |
|---|---|
| `"Machine impactée"` (rich_text) | `"Équipement concerné"` (rich_text) |
| `"Référence OF"` (title) | `"Ordre de Fabrication"` (title) |
| `"Statut OF"` | `"Statut"` |
| `"Coût arrêt (€)"` | `"Coût arrêt horaire (€)"` |
| `"Durée arrêt (h)"` | ❌ N'existe pas → 0.0 |

### Base Pièces (`pieces`)
| Champ actuel (ERRONÉ) | Champ ESCP correct |
|---|---|
| `"Machine concernée"` (rich_text) | `"Équipements compatibles"` (rich_text) |
| `"Désignation pièce"` (title) | `"Composant"` (title) |
| `"Référence"` | `"Réf. fabricant"` |
| `"Délai livraison (j)"` | `"Délai réappro (jours)"` |
| `"Stock actuel"` ✓ | `"Stock actuel"` ✓ |
| `"Prix unitaire (€)"` ✓ | `"Prix unitaire (€)"` ✓ |
| `"Statut stock"` ✓ | `"Statut stock"` ✓ |

---

## Fonctions disponibles dans notion_client.py

```python
import notion_client as nc

# Toutes les machines classées par RUL
machines = nc.get_machines()
# Retourne liste de dicts : nom, statut, rul_jours (= RUL nominal (h)/24),
#   seuil_temp, seuil_vib, seuil_pression, modele, fabricant, unite, responsable

# Machines en alerte/critique
alertes = nc.get_machines(statut="Alerte") + nc.get_machines(statut="Critique")

# Historique interventions
hist = nc.get_historique(machine_id="P-17", limit=50)
# Retourne : titre, machine, type, statut, date, duree_estimee, duree_reelle,
#   cout_estime, description, resultat, technicien

# OFs actifs
ofs = nc.get_ordres_fabrication(statut="En cours", machine_id="P-17")
# Retourne : reference, produit, statut, ligne, machine, cout_arret_h

# Pièces en rupture
ruptures = nc.get_pieces(machine_id="P-17", statut_stock="Rupture")

# KPIs ROI (métriques calculées)
kpis = nc.get_metriques_roi()
# Retourne : nb_interventions, nb_prescriptives, cout_interventions,
#   couts_evites, roi, machines_alerte, detail_alertes
```

---

## Backlog Antoine — User Stories à implémenter

### US-A0 — Dashboard KPIs (v0, Sprint 2) ✅ partiellement fait
**Critères manquants :**
- Les 5 KPIs sont affichés mais statiques/hardcodés — doivent venir de `nc.get_metriques_roi()`
- La sidebar affiche le RUL en "heures" → doit afficher `r_status` aussi
- Pas de tab structure (page plate sans onglets)

**Ce qu'il faut :** Relier les 3 KPI metrics (312 000€, 96.4%, 7.6x) à des données Notion réelles.

### US-A1 — Alerte immédiate si RUL < seuil (v1, Sprint 3)
**Critères :**
- Alerte visible dès que `r_status in ("Alerte", "Critique")`
- Contient : équipement, RUL, impact estimé, recommandation
- Idéalement dans un onglet ou section dédiée

### US-A2 — Simulation financière remplacement vs pannes (v1, Sprint 3)
**Critères :**
- Simulation < 2 min
- Comparer coût remplacement vs coût pannes projeté
- ROI estimé sur 24 mois minimum
- La fonction `simuler_scenarios_investissement()` dans l'agent fait déjà ça — il faut juste corriger les DB IDs et champs pour que les données réelles arrivent

### US-A3 — Rapport CODIR trimestriel (v2, Sprint 4)
**Critères :**
- Rapport < 2 min
- Export PDF via `utils/pdf_codir.py` (déjà implémenté dans la page)
- Le bouton PDF existe déjà dans la page — vérifier qu'il fonctionne une fois les DB IDs corrigés

---

## Structure cible de pages/3_Antoine.py

La page a déjà une bonne base. À améliorer :

```python
# Sidebar à corriger (ligne 31-39 actuellement) :
st.sidebar.caption("RUL estimé : " + str(c_rul) + " h — " + r_status)
# Remplacer "heures" par une indication claire avec statut coloré

# Structure onglets à ajouter :
tab0, tab1, tab2, tab3 = st.tabs([
    "📊 A0 — KPIs Exécutifs",
    "🚨 A1 — Alertes & Risques",
    "💰 A2 — Simulation Financière",
    "📄 A3 — Rapport CODIR",
])
```

---

## Ce qu'il faut corriger dans agents/agent_antoine.py

### Priorité 1 — DB IDs (lignes 55-58)
```python
# REMPLACER :
DB_MACHINES   = "5279cb2a42b54b42936e22313521f825"   # ❌ ERRONÉ
DB_ORDRES_FAB = "d7ee45dab07943c1bda09a6b47089202"   # ❌ ERRONÉ
DB_HISTORIQUE = "6f53558bfbee455891efa53b6536d892"   # ❌ ERRONÉ
DB_PIECES     = "c22138baa8ca4806b19403108735bc68"   # ❌ ERRONÉ

# PAR :
DB_MACHINES   = "6653da63-bd5a-4191-815c-576b8c7fcfbc"
DB_ORDRES_FAB = "687e40c2-a3ff-4de0-be55-20cf411f5dd6"
DB_HISTORIQUE = "94babab5-03bb-4c4d-9053-08d5bff301e3"
DB_PIECES     = "ef896795-bd1a-4b20-a8ea-f121c9f846ff"
```

### Priorité 2 — Fonction `get_bilan_equipement`
- Changer le filter : `{"property": "Équipement", "title": {"contains": nom}}`
- `"RUL (jours)"` → `round(_num(p.get("RUL nominal (h)")) / 24, 1)`
- `"Score dégradation (%)"` → None (champ absent en ESCP)
- `"Température actuelle (°C)"` → None (absent)
- `"Vibration actuelle (mm/s)"` → None (absent)
- `"Seuil température (°C)"` → `"Seuil Température (°C)"`
- `"Seuil vibration (mm/s)"` → `"Seuil Vibration (mm/s)"`
- `"Unité / Zone"` → `"Ligne de production"`
- `"Responsable"` → `"Technicien référent"`
- `"Notes IA"` → `"Notes"`

### Priorité 3 — Fonction `get_historique_couts_maintenance`
- Filter : `{"property": "Équipement", "rich_text": {"contains": equipement}}`
- Sort : `{"property": "Date planifiée", "direction": "ascending"}`
- `"Statut"` valeur `"Terminée"` → `"Réalisée"`
- `"Type"` valeur `"Panne corrective"` → `"Corrective"`
- `"Type"` valeur `"Maintenance prescriptive"` → `"Prédictive"`
- `"Coût intervention (€)"` → `"Coût estimé (€)"`
- `"Coût arrêt production (€)"` → absent, lire 0.0 par défaut
- `"Date intervention"` → `"Date planifiée"`
- `"Titre intervention"` → `"Intervention"`

### Priorité 4 — Fonctions `get_exposition_financiere_production` et `get_top_equipements_a_risque`
- Voir les tables de correspondance ci-dessus pour chaque champ
- Pour `get_top_equipements_a_risque` : comme les capteurs temps réel n'existent pas en ESCP, le score risque doit être calculé uniquement sur RUL et statut (pas sur temp/vib)

---

## Client LLM — llm_client.py

L'agent Antoine utilise une stratégie optimisée : **pré-fetch de toutes les données en Python, puis 1 seul appel LLM**. Ce pattern est correct et à conserver. L'appel se fait via :

```python
from llm_client import chat as _llm_chat

resp    = _llm_chat(system=SYSTEM, messages=messages, max_tokens=2500)
analyse = resp.final_text()
```

La fonction `run_agent_antoine()` retourne un **dict** (pas une string) avec les clés :
`analyse`, `scenarios`, `portfolio`, `bilan`, `historique` — à conserver tel quel car la page et le PDF CODIR en dépendent.
