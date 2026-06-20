# BRIEFING CLAUDE — Sophie (Manager Maintenance)
# À coller au début de ta session pour donner le contexte complet

---

## Contexte projet

**ResilientFlow AI** — démonstrateur de maintenance prescriptive Industrie 4.0 (projet fin d'études ESCP).
Stack : Python · Streamlit · Notion API · LLM via 1min.ai.
Machine surveillée : **Pompe P-17, Unité B**.

Repo GitHub : `mohamedbenjid-afk/ResiliantFlowAI` (branche `develop`).

Les fichiers à modifier sont dans `/Users/macdemohamed/Documents/Claude/Projects/ResilientFlow AI/`.
**Ne touche jamais** : `shared_state.py`, `notion_client.py`, `llm_client.py`, `streamlit_app.py`, `streamlit_home.py`.

---

## Ton périmètre : Sophie — Manager Maintenance

| Fichier | État actuel | À faire |
|---|---|---|
| `pages/2_Sophie.py` | ❌ À réécrire | Page complète avec onglets |
| `agents/agent_sophie.py` | ❌ DB IDs et noms de champs erronés | Corriger les IDs et les champs |

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

**Seuils d'alerte :**
- `r_status == "Critique"` → c_rul ≤ 24h
- `r_status == "Alerte"` → c_rul entre 25h et 48h
- `r_status == "Nominal"` → c_rul > 48h

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

> ⚠️ Le fichier `agents/agent_sophie.py` actuel utilise des IDs INCORRECTS (ancienne base Gmail). Remplacer par les IDs ci-dessus.

---

## Schéma Notion ESCP — Noms de champs CORRECTS

### Base Ordres de Fabrication (`ordres_fab`)
| Champ dans le fichier actuel (ERRONÉ) | Champ ESCP correct |
|---|---|
| `"Machine impactée"` (rich_text) | `"Équipement concerné"` (rich_text) |
| `"Référence OF"` (title) | `"Ordre de Fabrication"` (title) |
| `"Statut OF"` (select) | `"Statut"` (select) |
| `"Date fin prévue"` | `"Date fin prévue"` ✓ |
| `"Coût arrêt (€)"` | `"Coût arrêt horaire (€)"` |
| `"Durée arrêt (h)"` | ❌ N'existe pas en ESCP |
| `"Produit"` | `"Produit fabriqué"` |
| `"Ligne de production"` | `"Ligne de production"` ✓ |
| `"Responsable production"` | `"Responsable OF"` |
| `"Quantité prévue"` | `"Quantité cible"` |
| `"Quantité réalisée"` | `"Quantité réalisée"` ✓ |

Valeurs de `Statut` dans ESCP : `"En cours"`, `"Planifié"`, `"Terminé"`, `"Suspendu"`

### Base Historique / Plan de Maintenance (`historique`)
| Champ actuel (ERRONÉ) | Champ ESCP correct |
|---|---|
| `"Machine"` (rich_text) | `"Équipement"` (rich_text) |
| `"Statut"` → valeur `"Planifiée"` | `"Statut"` → valeur `"Planifiée"` ✓ |
| `"Titre intervention"` (title) | `"Intervention"` (title) |
| `"Type"` | `"Type d'intervention"` |
| `"Date intervention"` | `"Date planifiée"` |
| `"Durée estimée (h)"` | `"Durée estimée (h)"` ✓ |
| `"Technicien assigné"` | `"Technicien assigné"` ✓ |
| `"Coût intervention (€)"` | `"Coût estimé (€)"` |

### Base Pièces Détachées (`pieces`)
| Champ actuel (ERRONÉ) | Champ ESCP correct |
|---|---|
| `"Machine concernée"` (rich_text) | `"Équipements compatibles"` (rich_text) |
| `"Désignation pièce"` (title) | `"Composant"` (title) |
| `"Référence"` | `"Réf. fabricant"` |
| `"Statut stock"` (select) | `"Statut stock"` ✓ |
| `"Stock actuel"` (number) | `"Stock actuel"` ✓ |
| `"Stock minimum"` | `"Stock minimum (seuil alerte)"` |
| `"Délai livraison (j)"` | `"Délai réappro (jours)"` |
| `"Fournisseur"` | `"Fournisseur principal"` |

Valeurs de `Statut stock` dans ESCP : `"En stock"`, `"Stock faible"`, `"Rupture"`, `"Commandé"`

### Base Équipe Maintenance (`equipe`)
Les noms de champs sont corrects dans l'agent actuel. Vérification :
- `"Nom Technicien"` (title) ✓
- `"Prénom"` ✓, `"Rôle"` ✓, `"Spécialité"` ✓
- `"Habilitations"` (multi_select) ✓
- `"Disponibilité"` (select) ✓ → valeurs : `"Disponible"`, `"En intervention"`, `"Congé"`
- `"Charge horaire (h/sem)"` ✓, `"Heures restantes"` ✓
- `"Zone assignée"` ✓

---

## Fonctions disponibles dans notion_client.py

```python
import notion_client as nc

# Récupérer les OFs avec filtre
ofs = nc.get_ordres_fabrication(statut="En cours", machine_id="P-17")
# Retourne liste de dicts avec : reference, produit, statut, ligne, machine,
#   responsable, date_debut, date_fin, qte_prevue, qte_realisee, cout_arret_h, secours_dispo

# Interventions planifiées
planifiees = nc.get_historique(machine_id="P-17", statut="Planifiée")
# Retourne liste de dicts avec : titre, machine, type, statut, technicien,
#   date, duree_estimee, duree_reelle, cout_estime, description

# Pièces par machine et statut
pieces_ko = nc.get_pieces(machine_id="P-17", statut_stock="Rupture")
# Retourne liste de dicts avec : designation, reference, machine, stock_actuel,
#   stock_minimum, statut_stock, prix_unitaire, fournisseur, delai_livraison

# Équipe disponible
dispo = nc.get_equipe(disponibilite="Disponible")
# Retourne liste de dicts avec : nom, prenom, role, specialite, habilitations,
#   disponibilite, heures_restantes, zone

# Contexte complet machine
ctx = nc.get_contexte_machine("P-17")
# Clés : machine, pieces, ordres_fab, historique, docs_hse, equipe_dispo
```

---

## Backlog Sophie — User Stories à implémenter

### US-S0 — Dashboard alertes (v0, Sprint 2) ✅ partiellement fait
**Critères actuellement manquants :**
- Pas de multi-machine : la page ne montre que P-17
- Données figées (`CONTEXTE_USINE`) au lieu de Notion réel
- Valeurs du simulateur (83%, 45 500€) différentes du backlog (73%, 47 000€)

**Ce qu'il faut :** Un dashboard qui liste les machines en alerte depuis Notion, classées par RUL (urgence décroissante), avec statut coloré et temps restant.

### US-S1 — Simulateur d'impact "que se passe-t-il si je reporte ?" (v1, Sprint 3)
**Critères :**
- Simulation < 2 min
- Afficher : RUL projeté + risque % + impact EUR
- Valeurs correctes : **73% risque, 47 000€ impact** (pas 87%/45 500€)
- L'agent Sophie doit être appelé pour produire cette analyse

### US-S2 — Affectation technicien en 1 clic (v1, Sprint 3)
**Critères :**
- Liste des techniciens avec heures restantes (depuis Notion)
- Alerte si habilitation manquante pour le type d'intervention
- Affectation en 1 clic (écrire dans Notion avec `create_intervention`)

### US-S3 — Rapport hebdomadaire (v2, Sprint 4)
**Critères :**
- Rapport < 1 min
- Taux dispo, arrêts évités, KPIs
- Export PDF (pas encore de utils/pdf_sophie.py — à créer ou utiliser pdf_codir)

---

## Structure cible de pages/2_Sophie.py

Prendre modèle sur `pages/1_Lionel.py` (référence). Structure à 4 onglets :

```python
tab0, tab1, tab2, tab3 = st.tabs([
    "📡 S0 — Alertes actives",
    "🔮 S1 — Simulateur d'impact",
    "👥 S2 — Affectation équipe",
    "📊 S3 — Rapport hebdo",
])
```

**Sidebar obligatoire :**
```python
st.sidebar.markdown("### ResilientFlow AI\n*Couche Prescriptive v1*")
if st.sidebar.button("⏸️ Pause / ▶️ Reprendre", use_container_width=True):
    st.session_state.running = not st.session_state.running
st.sidebar.caption("Statut machine : Pompe P-17 (Unité B)")
st.sidebar.caption("Horodatage système : t = " + str(st.session_state.tick))
st.sidebar.caption(f"RUL estimé : {c_rul}h ({r_status})")
st.sidebar.page_link("streamlit_home.py", label="⬅️ Retour à l'accueil", use_container_width=True)
```

**Règles importantes :**
- Toujours entourer les appels Notion d'un `try/except` avec fallback de données fictives
- Mettre en cache les résultats agent dans `st.session_state` (ne pas appeler à chaque rerun)
- Ne pas utiliser `CONTEXTE_USINE` (données statiques obsolètes)
- Utiliser `fillcolor="rgba(r,g,b,a)"` pour Plotly (pas de hex 8 chiffres)

---

## Comment appeler l'agent Sophie

```python
# Dans pages/2_Sophie.py, onglet S1 :
if st.button("▶️ Lancer l'analyse d'impact"):
    st.session_state.running = False
    with st.spinner("Analyse en cours…"):
        try:
            from agents.agent_sophie import run_agent_sophie
            result = run_agent_sophie(c_rul=int(c_rul), equipement="P-17",
                                      c_temp=float(c_temp), c_vib=float(c_vib))
            st.session_state.sophie_result = result
        except Exception as e:
            st.error(f"Erreur agent : {e}")

if st.session_state.get("sophie_result"):
    st.markdown(st.session_state.sophie_result)
```

---

## Ce qu'il faut corriger dans agents/agent_sophie.py

1. **Remplacer les 4 DB IDs** (lignes 55-58) par les IDs ESCP corrects ci-dessus
2. **Dans `get_impact_production`** : changer tous les noms de champs (voir table de correspondance)
3. **Dans `get_fenetre_maintenance`** : `"Machine"` → `"Équipement"`, `"Planifiée"` reste correct, `"Titre intervention"` → `"Intervention"`, `"Date intervention"` → `"Date planifiée"`, `"Type"` → `"Type d'intervention"`
4. **Dans `get_pieces_critiques_manquantes`** : `"Machine concernée"` → `"Équipements compatibles"`, `"Désignation pièce"` → `"Composant"`, `"Délai livraison (j)"` → `"Délai réappro (jours)"`, `"Fournisseur"` → `"Fournisseur principal"`
5. **Dans `get_charge_techniciens`** : noms de champs corrects, mais vérifier `"Charge horaire (h/sem)"` ✓

---

## Client LLM — llm_client.py

```python
from llm_client import chat as _llm_chat

# Appel avec tools (agentic loop)
resp = _llm_chat(system=SYSTEM, messages=messages, tools=TOOLS, max_tokens=2000)
if resp.stop_reason == "end_turn":
    return resp.final_text()
if resp.stop_reason == "tool_use":
    for tc in resp.tool_calls():
        # tc["name"], tc["input"], tc["id"]
        ...
    messages.append({"role": "assistant", "content": resp.content})
    messages.append({"role": "user", "content": results})
```
