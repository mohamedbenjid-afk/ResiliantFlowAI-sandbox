# BRIEFING CLAUDE — Leila (Responsable HSE)
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

## Ton périmètre : Leila — Responsable HSE

| Fichier | État actuel | À faire |
|---|---|---|
| `pages/4_Leila.py` | ⚠️ Fonctionnel mais sans tabs ni agent | Ajouter onglets + appel agent |
| `agents/agent_leila.py` | ❌ DB IDs incorrects + champs erronés | Corriger les IDs et les champs |

---

## Simulateur capteurs — comment ça marche

```python
from shared_state import init_session_state, update_sensors, COMMON_CSS
init_session_state()
c_temp, c_vib, c_pres, c_cur, c_rul, r_status, rul_pct = update_sensors()
# c_rul = RUL en heures (0-100 dans le simulateur)
# r_status = "Nominal" | "Alerte" | "Critique"
# c_temp en °C, c_vib en mm/s, c_pres en bar
```

**Seuils pour les risques HSE dans l'agent actuel :**
- Risque thermique : `c_temp >= 110`
- Risque mécanique : `c_vib >= 4.5`
- Risque hydraulique : `c_pres >= 7.0`

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

> ⚠️ Le fichier `agents/agent_leila.py` actuel utilise des IDs **INCORRECTS** :
> - `DB_HISTORIQUE = "6f53558b..."` → doit être `"94babab5-03bb-4c4d-9053-08d5bff301e3"`
> - `DB_PIECES     = "c22138ba..."` → doit être `"ef896795-bd1a-4b20-a8ea-f121c9f846ff"`
> - `DB_HSE        = "b6ab3a9b..."` → doit être `"3856b2ff-be3d-816f-a163-ef4f8e43499d"`
> - `DB_EQUIPE     = "0a82b4f5..."` → doit être `"3856b2ff-be3d-8151-8b3f-ee79dee0bc2b"`

---

## Schéma Notion ESCP — Noms de champs CORRECTS

### Base Historique (`historique`)
| Champ dans l'agent actuel (ERRONÉ) | Champ ESCP correct |
|---|---|
| `"Machine"` (rich_text filter) | `"Équipement"` (rich_text) |
| `"Statut"` → valeur `"Planifiée"` | `"Statut"` → valeur **`"Planifiée"`** ✓ |
| `"Titre intervention"` (title) | `"Intervention"` (title) |
| `"Type"` | `"Type d'intervention"` |
| `"Date intervention"` | `"Date planifiée"` |
| `"Technicien assigné"` | `"Technicien assigné"` ✓ |
| `"Durée estimée (h)"` | `"Durée estimée (h)"` ✓ |

### Base Pièces (`pieces`)
| Champ actuel (ERRONÉ) | Champ ESCP correct |
|---|---|
| `"Machine concernée"` (rich_text) | `"Équipements compatibles"` (rich_text) |
| `"Désignation pièce"` (title) | `"Composant"` (title) |
| `"Référence"` | `"Réf. fabricant"` |
| `"Fournisseur"` | `"Fournisseur principal"` |
| `"Statut stock"` ✓ | `"Statut stock"` ✓ |

### Base Équipe (`equipe`)
Les noms dans l'agent sont corrects :
- `"Nom Technicien"` (title) ✓, `"Habilitations"` (multi_select) ✓
- `"Disponibilité"` (select) ✓, `"Zone assignée"` ✓

Valeurs de `Disponibilité` : `"Disponible"`, `"En intervention"`, `"Congé"`

### Base Documentation & HSE (`hse_docs`)
Tous les noms sont corrects dans l'agent :
- `"Titre document"` ✓, `"Type"` ✓, `"Statut"` ✓
- `"Machine concernée"` ✓, `"Niveau risque"` ✓
- `"EPI obligatoires"` (multi_select) ✓
- `"Persona destinataire"` (multi_select) ✓ → valeurs : `"Leila"`, `"Sophie"`, `"Lionel"`, `"Antoine"`
- `"Contenu résumé"` ✓, `"Lien document"` ✓
- `"Date validation"` ✓, `"Date révision"` ✓

---

## Fonctions disponibles dans notion_client.py

```python
import notion_client as nc

# Documents HSE par machine et/ou persona
docs = nc.get_docs_hse(machine_id="P-17", persona="Leila")
# Retourne : titre, type, statut, machine, niveau_risque, epi (list),
#   persona (list), version, auteur, resume, lien, date_validation, date_revision

# Historique des interventions
hist = nc.get_historique(machine_id="P-17", statut="Planifiée")
# Retourne : titre, machine, type, statut, technicien, date,
#   duree_estimee, duree_reelle, habilitations (list), loto_requis

# Équipe disponible
equipe = nc.get_equipe(disponibilite="Disponible")
# Retourne : nom, prenom, role, specialite, habilitations (list),
#   disponibilite, heures_restantes, zone

# Pièces
pieces = nc.get_pieces(machine_id="P-17")
# Retourne : designation, reference, categorie, machine, emplacement,
#   stock_actuel, stock_minimum, statut_stock, critique, prix_unitaire,
#   fournisseur, delai_livraison

# Contexte complet
ctx = nc.get_contexte_machine("P-17")
# Clés : machine, pieces, ordres_fab, historique, docs_hse, equipe_dispo
```

---

## Backlog Leila — User Stories à implémenter

### US-L0 — Alerte HSE avec EPI (v0, Sprint 2) ✅ partiellement fait
**Critères actuellement manquants :**
- La page affiche les EPI par type d'anomalie capteur — c'est bien
- Mais l'**agent HSE n'est pas appelé** (agent_leila.py importé nulle part dans la page)
- Le contenu est statique — pas de données Notion réelles
- La page n'a pas de structure à onglets

**Ce qu'il faut :**
- Brancher l'agent sur les données Notion réelles
- L'alerte doit inclure : type anomalie, EPI requis par norme, habilitation requise technicien

### US-L1 — Rapport de conformité hebdomadaire (v1, Sprint 3)
**Critères :**
- Rapport < 1 min
- Taux de conformité en % (interventions avec LOTO respecté, habilitations vérifiées)
- Écarts détectés
- Export PDF (ou tableau dans la page)

**Comment faire :**
- Récupérer les interventions réalisées dans les 7 derniers jours via `nc.get_historique()`
- Calculer le taux : interventions avec `loto_requis` renseigné / total
- L'agent peut générer l'analyse textuelle

### US-L2 — Dossier audit ISO 45001 PDF (v1, Sprint 3) ✅ fait
La génération PDF via `utils/pdf_audit.py` est déjà implémentée dans la page. Vérifier qu'elle fonctionne une fois les DB IDs corrigés dans l'agent.

### US-L3 — Chronologie post-incident (v2, Sprint 4)
**Critères :**
- Timeline minute par minute d'une intervention
- < 5 min, horodatée
- Utiliser l'historique Notion + les données capteurs de la session

---

## Structure cible de pages/4_Leila.py

La page actuelle est plate (une seule page sans onglets). À restructurer en 4 onglets :

```python
tab0, tab1, tab2, tab3 = st.tabs([
    "🛡️ L0 — Alerte HSE & EPI",
    "📋 L1 — Conformité Hebdo",
    "📄 L2 — Audit ISO 45001",
    "🔍 L3 — Chronologie incident",
])
```

**Sidebar à corriger (affiche "heures" sans statut) :**
```python
st.sidebar.caption(f"RUL estimé : {c_rul}h — {r_status}")
```

**Onglet L0 :** Conserver la matrice EPI existante (elle est bien faite), mais y ajouter l'appel à l'agent.

**Onglet L1 :** Nouveau — rapport conformité hebdo.

**Onglet L2 :** Déplacer le bouton PDF CODIR existant ici.

**Onglet L3 :** Nouveau — timeline incident.

---

## Comment appeler l'agent Leila

L'agent existe (`agents/agent_leila.py`) mais n'est **pas appelé dans la page**. À ajouter :

```python
# Initialisation session state (hors onglets, au début de la page)
for key in ["leila_result", "audit_pdf_bytes", "audit_pdf_ref", "audit_pdf_src"]:
    if key not in st.session_state:
        st.session_state[key] = None

# Dans l'onglet L0 :
if st.button("🤖 Lancer l'évaluation HSE complète", use_container_width=True):
    st.session_state.running = False
    with st.spinner("L'agent analyse la conformité ISO 45001…"):
        try:
            from agents.agent_leila import run_agent_leila
            result = run_agent_leila(
                c_temp=float(c_temp), c_vib=float(c_vib),
                c_pres=float(c_pres), c_rul=int(c_rul)
            )
            st.session_state.leila_result = result
            st.success("✅ Évaluation HSE générée.")
        except Exception as e:
            st.error(f"Erreur agent : {e}")
            st.exception(e)

if st.session_state.leila_result:
    st.markdown(st.session_state.leila_result)
```

---

## Ce qu'il faut corriger dans agents/agent_leila.py

### Priorité 1 — DB IDs (lignes 56-59)
```python
# REMPLACER :
DB_HISTORIQUE = "6f53558bfbee455891efa53b6536d892"   # ❌ ERRONÉ
DB_PIECES     = "c22138baa8ca4806b19403108735bc68"   # ❌ ERRONÉ
DB_HSE        = "b6ab3a9bd41d4967add92f27d1cd2d5c"   # ❌ ERRONÉ
DB_EQUIPE     = "0a82b4f53a26491c81e64b0cb8bb058c"   # ❌ ERRONÉ

# PAR :
DB_HISTORIQUE = "94babab5-03bb-4c4d-9053-08d5bff301e3"
DB_PIECES     = "ef896795-bd1a-4b20-a8ea-f121c9f846ff"
DB_HSE        = "3856b2ff-be3d-816f-a163-ef4f8e43499d"
DB_EQUIPE     = "3856b2ff-be3d-8151-8b3f-ee79dee0bc2b"
```

### Priorité 2 — Fonction `get_exigences_hse_intervention`
- **Filtre historique** : `{"property": "Machine", ...}` → `{"property": "Équipement", ...}`
- **Sort historique** : `"Date intervention"` → `"Date planifiée"`
- **Champs historique** : `"Titre intervention"` → `"Intervention"`, `"Type"` → `"Type d'intervention"`, `"Date intervention"` → `"Date planifiée"`
- **Filtre pièces** : `"Machine concernée"` → `"Équipements compatibles"` (mais cette fonction ne lit pas les pièces, seulement HSE docs + equipe + historique)

### Priorité 3 — Fonction `get_conformite_pieces`
- Filtre : `{"property": "Machine concernée", ...}` → `{"property": "Équipements compatibles", ...}`
- `"Désignation pièce"` (title) → `"Composant"` (title)
- `"Référence"` → `"Réf. fabricant"`
- `"Fournisseur"` → `"Fournisseur principal"`

### Note sur `get_matrice_risques_capteurs` et `generer_rapport_audit`
Ces deux fonctions n'utilisent **pas Notion** — elles calculent localement depuis les valeurs capteurs et retournent des données statiques. Elles sont **correctes et à conserver telles quelles**.

---

## Client LLM — llm_client.py

```python
from llm_client import chat as _llm_chat

# Agentic loop (pour les outils)
resp = _llm_chat(system=SYSTEM, messages=messages, tools=TOOLS, max_tokens=2000)
if resp.stop_reason == "end_turn":
    return resp.final_text()
if resp.stop_reason == "tool_use":
    for tc in resp.tool_calls():
        out = _execute(tc["name"], tc["input"])
        results.append({"type": "tool_result",
                        "tool_use_id": tc.get("id", "tc0"),
                        "content": json.dumps(out, ensure_ascii=False)})
    messages.append({"role": "assistant", "content": resp.content})
    messages.append({"role": "user", "content": results})
```

---

## Règles importantes

- Toujours entourer les appels Notion d'un `try/except` avec fallback de données fictives (voir le pattern existant dans la page actuelle autour du bouton PDF)
- Mettre en cache les résultats agent dans `st.session_state` (ne pas rappeler à chaque rerun)
- Utiliser `fillcolor="rgba(r,g,b,a)"` pour Plotly (pas de hex 8 chiffres)
- La page actuelle a de bons fallbacks de données statiques — les conserver en cas d'erreur Notion
