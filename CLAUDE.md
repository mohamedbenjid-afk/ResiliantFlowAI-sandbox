# CLAUDE.md — ResilientFlow AI
# Contexte projet pour développement assisté par IA

> **Comment utiliser ce fichier :** Colle son contenu en début de conversation avec Claude
> pour qu'il comprenne immédiatement l'architecture et génère du code cohérent avec l'existant.

---

## 🚀 DÉMARRAGE RAPIDE PAR MEMBRE — Fichiers de briefing Claude

Chaque membre dispose d'un fichier de briefing **à coller en début de session Claude** pour travailler sur son agent. Ces fichiers contiennent : les IDs Notion ESCP corrects, la table de correspondance des champs, le backlog US, et les instructions de réécriture.

| Membre | Persona | Fichier à ouvrir |
|---|---|---|
| **Sihem** | Sophie — Manager Maintenance | `BRIEFING_Sophie.md` |
| **Philippe** | Antoine — Directeur Technique | `BRIEFING_Antoine.md` |
| **Murielle** | Leila — Responsable HSE | `BRIEFING_Leila.md` |

> ⚠️ **Priorité absolue commune :** Les agents `agent_sophie.py`, `agent_antoine.py` et `agent_leila.py` utilisent tous des **IDs Notion incorrects** (ancienne base). Les briefings donnent les IDs ESCP corrects. Corriger les IDs en premier — aucun appel Notion ne fonctionne sinon.

---

## 1. Présentation du projet

**ResilientFlow AI** est un démonstrateur de maintenance prescriptive Industrie 4.0,
développé dans le cadre d'un projet de fin d'études ESCP.

- **Machine surveillée :** Pompe P-17, Unité B
- **Stack :** Python · Streamlit · Notion API · LLM via 1min.ai
- **Repo GitHub :** `mohamedbenjid-afk/ResiliantFlowAI` (branche de travail : `develop`)
- **App déployée :** Streamlit Cloud

### Ce que fait l'app

Un simulateur IoT génère des données capteurs (température, vibration, pression, courant)
selon des scénarios pré-configurés. Ces données font évoluer un indicateur RUL
(Remaining Useful Life). Quand le RUL franchit des seuils critiques, des **agents IA
prescriptifs** sont déclenchés et produisent des recommandations contextualisées.

**4 personas / agents :**
| Persona | Rôle | Fichier page | Fichier agent |
|---|---|---|---|
| Lionel | Technicien Terrain | `pages/1_Lionel.py` | `agents/agent_lionel.py` |
| Sophie | Manager Maintenance | `pages/2_Sophie.py` | `agents/agent_sophie.py` |
| Antoine | Directeur Technique | `pages/3_Antoine.py` | `agents/agent_antoine.py` |
| Leila | Responsable HSE | `pages/4_Leila.py` | `agents/agent_leila.py` |

---

## 2. Architecture des fichiers

```
ResiliantFlowAI/
├── streamlit_app.py          # Point d'entrée — st.navigation() vers les 4 pages
├── streamlit_home.py         # Page d'accueil avec les 4 cartes personas
├── shared_state.py           # Session state, simulateur capteurs, CSS commun
├── notion_client.py          # Toutes les fonctions d'accès aux 6 bases Notion
├── llm_client.py             # Client LLM (1min.ai) — fonction call_llm()
├── agents/
│   ├── agent_lionel.py       # ✅ COMPLET — sert de référence
│   ├── agent_sophie.py       # À enrichir
│   ├── agent_antoine.py      # À enrichir
│   └── agent_leila.py        # À enrichir
├── pages/
│   ├── 1_Lionel.py           # ✅ COMPLET — sert de référence (5 onglets K0→K4)
│   ├── 2_Sophie.py           # À enrichir
│   ├── 3_Antoine.py          # À enrichir
│   └── 4_Leila.py            # À enrichir
└── utils/
    ├── pdf_audit.py          # Générateur PDF audit ISO 45001 (pour Leila)
    └── pdf_codir.py          # Générateur PDF fiche CODIR (pour Antoine)
```

---

## 3. Bases de données Notion (6 bases)

```python
DB_IDS = {
    "machines":   "5279cb2a42b54b42936e22313521f825",
    "equipe":     "0a82b4f53a26491c81e64b0cb8bb058c",
    "pieces":     "c22138baa8ca4806b19403108735bc68",
    "ordres_fab": "d7ee45dab07943c1bda09a6b47089202",
    "historique": "6f53558bfbee455891efa53b6536d892",
    "hse_docs":   "b6ab3a9bd41d4967add92f27d1cd2d5c",
}
```

**Fonctions disponibles dans `notion_client.py` :**
- `get_machines(statut=None)` → liste machines triées par RUL
- `get_machine(machine_id)` → une machine par ID (ex: "P-17")
- `get_equipe(disponibilite=None)` → techniciens
- `get_pieces(machine_id=None, statut_stock=None)` → pièces détachées
- `get_ordres_fabrication(statut=None, machine_id=None)` → OFs
- `get_historique(machine_id=None, statut=None, limit=20)` → interventions
- `get_docs_hse(machine_id=None, type_doc=None, persona=None)` → documents HSE
- `get_contexte_machine(machine_id)` → contexte complet d'une machine (agrégateur)
- `get_metriques_roi()` → KPIs ROI pour Antoine
- `create_intervention(data)` → crée un enregistrement dans l'Historique

---

## 4. Simulateur capteurs — shared_state.py

```python
from shared_state import init_session_state, update_sensors, COMMON_CSS

init_session_state()  # à appeler une fois au démarrage
c_temp, c_vib, c_pres, c_cur, c_rul, r_status, rul_pct = update_sensors()
# r_status = "Nominal" (RUL > 60j) | "Alerte" (RUL > 2j) | "Critique" (RUL ≤ 2j)
```

**Scénarios pré-configurés :**
- **Normal :** temp=67°C, vib=0.8mm/s → RUL ≈ 70 jours → statut Nominal
- **Surchauffe :** temp=82°C, vib=3.5mm/s → RUL ≈ 1 jour → statut Critique

---

## 5. Client LLM — llm_client.py

```python
from llm_client import call_llm

response = call_llm(
    system_prompt="Tu es un expert...",
    messages=[{"role": "user", "content": "..."}],
    tools=[],        # liste d'outils optionnelle
    tool_choice={}   # optionnel
)
# Retourne une chaîne de texte (réponse LLM)
```

**Important :** L'API 1min.ai ne supporte pas nativement `tool_use`.
Le pattern utilisé dans les agents est : demander au LLM de choisir un outil
via du texte structuré, puis parser la réponse pour appeler la bonne fonction Notion.

---

## 6. Pattern d'un agent — référence : agent_lionel.py

```python
# Structure type d'un agent
TOOLS = [
    {"name": "get_fiche_equipement", "description": "...", "parameters": {...}},
    # ...
]

def _execute(name, inputs):
    """Dispatcher — mappe nom d'outil → fonction Notion."""
    if name == "get_fiche_equipement":
        return nc.get_machine(inputs.get("nom", "P-17"))
    # ...

def run_agent_xxx(c_temp, c_vib, c_pres, c_rul) -> str:
    """Point d'entrée de l'agent — retourne une recommandation en markdown."""
    ctx = nc.get_contexte_machine("P-17")
    # 1. Premier appel LLM → choix d'outil
    # 2. Exécution de l'outil → données Notion
    # 3. Deuxième appel LLM → recommandation finale
    return recommendation_markdown
```

---

## 7. Pattern d'une page Streamlit — référence : pages/1_Lionel.py

```python
st.set_page_config(page_title="...", page_icon="...", layout="wide")
st.markdown(COMMON_CSS, unsafe_allow_html=True)

# Sidebar obligatoire
with st.sidebar:
    st.page_link("streamlit_home.py", label="← Retour à l'accueil", use_container_width=True)
    # boutons, sliders...

# Données capteurs
c_temp, c_vib, c_pres, c_cur, c_rul, r_status, rul_pct = update_sensors()

# Onglets (adapter selon le persona)
tab0, tab1, ... = st.tabs(["📡 K0 — Surveillance", "📋 K1 — ...", ...])

with tab0:
    # contenu...

# Auto-refresh (K0 uniquement, optionnel)
if st.session_state.running:
    time.sleep(1)
    st.rerun()
```

**Règles importantes :**
- Toujours entourer les appels Notion d'un `try/except` avec fallback de données fictives
- L'agent IA doit être mis en cache dans `st.session_state` (ne pas appeler à chaque rerun)
- Utiliser `fillcolor="rgba(r,g,b,a)"` pour Plotly (pas de hex 8 chiffres)

---

## 8. Ce qu'il reste à développer par persona

### Sophie — Manager Maintenance (`pages/2_Sophie.py` + `agents/agent_sophie.py`)
- Tableau de planification des interventions avec arbitrage
- Gestion des ressources humaines (charge techniciens)
- Suivi des stocks et commandes de pièces
- Ordonnancement des ordres de fabrication impactés

### Antoine — Directeur Technique (`pages/3_Antoine.py` + `agents/agent_antoine.py`)
- KPIs stratégiques et ROI de la maintenance prescriptive
- Simulation CAPEX vs OPEX vs Correctif
- Dashboard exécutif avec graphiques Plotly
- Génération PDF fiche CODIR (via `utils/pdf_codir.py`)

### Leila — Responsable HSE (`pages/4_Leila.py` + `agents/agent_leila.py`)
- Conformité ISO 45001 et matrices de risques
- Gestion des EPI requis par intervention
- Génération automatique des dossiers d'audit PDF (via `utils/pdf_audit.py`)
- Suivi des incidents et plans de prévention

---

## 9. Backlog produit — User Stories par persona

> Utilise ce backlog pour comprendre ce que chaque membre doit implémenter.
> Les stories `⛔ Hors scope v1` sont reportées — ne pas les implémenter.

### Légende versions
- `v0` = Quick Win Sprint 2 — données figées OK, testable rapidement
- `v1` = Enrichissement Sprint 3 — appels Notion réels, agent branché
- `v2` = Finalisation Sprint 4 — intégration complète, démo jury

---

### ⚙️ Commun (Mohamed)

| ID | Sprint | Version | User Story | Critères de succès |
|----|--------|---------|------------|-------------------|
| US-00 | Sprint 0 | — | Configurer l'environnement partagé (Git, simulateur IoT, scénarios RUL, dépendances) | Dépôt Git. Simulateur configuré. requirements.txt versionné. |
| US-01a | Sprint 1 | v0 | Construire un simulateur IoT générant température, vibration, pression et RUL calculé par règles métier sur P-17 | Simulateur fonctionnel. 3 scénarios (nominal, dégradation, critique). |
| US-01b | Sprint 3 | v1 | Enrichir les scénarios de simulation (dégradation progressive, pannes soudaines) et câbler le seuil de déclenchement | 5+ scénarios. Seuil 48h classe A / 24h classe B. |
| US-02 | Sprint 1 | v0 | Assembler le contexte simulé (OF actif, équipe dispo, stock pièces) sous forme JSON statique | Fichier JSON documenté. Utilisable par les 4 membres. |
| US-03 | Sprint 3 | v1 | Implémenter le moteur prescriptif : 3 scénarios précalculés avec RUL projeté | 3 scénarios. Scénario optimal sélectionné automatiquement. Résultat < 1 sec. |
| US-D1 | Sprint 4 | v2 | Dérouler le scénario P-17 complet bout en bout sans interruption | Scénario < 5 min. 3 runs réussis. Dataset figé. Backup vidéo. |

---

### 🔧 Lionel — Technicien Terrain (Mohamed)

| ID | Sprint | Version | User Story | Critères de succès |
|----|--------|---------|------------|-------------------|
| US-K0 | Sprint 2 | v0 🏆 | Afficher en 1 écran : RUL de P-17, statut (OK/Alerte/Critique) et prescription recommandée | Écran unique. RUL affiché. Statut coloré. Prescription affichée. Données figées OK. |
| US-K1 | Sprint 3 | v1 | Recevoir un briefing de poste avec priorités du jour et action recommandée par alerte | Briefing < 30 sec. Alertes classées par urgence. 1 prescription par alerte. |
| US-K2 | Sprint 3 | v1 | Être guidé étape par étape lors de l'intervention P-17 (D-04, JM-220 B-12, vérifier débit 45 m³/h) | Séquence P-17 affichée. Étapes validables. Durée estimée 35 min. Consignes sécurité incluses. |
| US-K3 | Sprint 3 | v1 | Valider une intervention via formulaire 5 questions en 3 minutes | Formulaire ≤ 5 questions. Historique mis à jour. Notification Sophie générée. |
| US-K4 | Sprint 4 | v2 | Arbitrer entre 2 alertes simultanées en 30 secondes | Classement affiché avec justification RUL + criticité. |

---

### 📋 Sophie — Manager Maintenance (Sihem)

| ID | Sprint | Version | User Story | Critères de succès |
|----|--------|---------|------------|-------------------|
| US-S0 | Sprint 2 | v0 🏆 | Voir en 1 écran les alertes actives classées par urgence réelle avec le temps restant | Dashboard < 5 sec. Alertes avec criticité et temps restant. 5 alertes classées correctement. Données figées OK. |
| US-S1 | Sprint 3 | v1 | Simuler "que se passe-t-il si je reporte C-03 à jeudi ?" → 73 % risque, 47 000 EUR impact, recommandation | Simulation < 2 min. RUL projeté + risque % + impact EUR. Testé sur scénario C-03. |
| US-S2 | Sprint 3 | v1 | Affecter le bon technicien disponible en 1 clic avec vérification d'habilitation | Liste techniciens avec heures restantes. Alerte si habilitation manquante. Affectation en 1 clic. |
| US-S3 | Sprint 4 | v2 | Générer le rapport hebdomadaire de performance en 10 minutes | Rapport < 1 min. Taux dispo, arrêts évités, KPIs. Export PDF. |

---

### 📊 Antoine — Directeur Technique (Philippe)

| ID | Sprint | Version | User Story | Critères de succès |
|----|--------|---------|------------|-------------------|
| US-A0 | Sprint 2 | v0 🏆 | Afficher en 1 écran les 5 KPIs clés : disponibilité, arrêts évités, ROI (7,6x), coûts évités (312 000 EUR), risques à 30j | Dashboard < 3 sec. 5 KPIs présents. Données figées OK. |
| US-A1 | Sprint 3 | v1 | Recevoir une alerte immédiate dès qu'un risque majeur est détecté (RUL < seuil classe A) | Alerte < 5 min. Équipement, RUL, impact estimé, recommandation. |
| US-A2 | Sprint 3 | v1 | Simuler l'impact financier remplacement vs pannes sur 24 mois | Simulation < 2 min. Coût remplacement vs coût pannes projeté. ROI estimé. |
| US-A3 | Sprint 4 | v2 | Générer le rapport CODIR trimestriel | Rapport < 2 min. Export PDF/PPT. |

---

### 🛡️ Leila — Responsable HSE (Murielle)

| ID | Sprint | Version | User Story | Critères de succès |
|----|--------|---------|------------|-------------------|
| US-L0 | Sprint 2 | v0 🏆 | Recevoir une alerte HSE avec les EPI requis intégrés dans le bon de travail avant intervention | Alerte HSE < 1 min. EPI requis affichés selon type de défaillance. Fiche sécurité jointe. |
| US-L1 | Sprint 3 | v1 | Consulter un rapport de conformité hebdomadaire des interventions | Rapport < 1 min. Taux conformité %. Écarts détectés. Export PDF. |
| US-L2 | Sprint 3 | v1 | Générer le dossier audit ISO 45001 sur les 12 derniers mois | Dossier < 5 min. Format ISO 45001. Export PDF. |
| US-L3 | Sprint 4 | v2 | Reconstituer la chronologie d'une intervention post-incident | Timeline minute par minute. < 5 min. Horodatée. |

---

## 10. Règles de contribution

- Travailler sur la branche `develop` uniquement
- Ne jamais modifier : `shared_state.py`, `notion_client.py`, `llm_client.py`, `streamlit_app.py`, `streamlit_home.py`
- Ne pas toucher aux fichiers des autres personas
- Tester sur l'app staging avant de signaler que c'est prêt
- Token Notion : demander à Mohamed en privé (ne jamais commiter dans le code)
