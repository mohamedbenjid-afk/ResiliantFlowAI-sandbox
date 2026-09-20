"""
agents/agent_sophie.py — Agent d'arbitrage de Sophie (Manager Maintenance)
Rôle : évaluer l'impact production d'une alerte, arbitrer entre intervention
       immédiate et report, optimiser l'assignation des techniciens.
 
Intégration dans pages/2_Sophie.py :
    from agents.agent_sophie import run_agent_sophie
    arbitrage = run_agent_sophie(c_rul, equipement="Pompe P-17")
"""
 
import os, json
import requests as _requests
 
import sys, os as _os
sys.path.append(_os.path.join(_os.path.dirname(__file__), '..'))
from llm_client import chat as _llm_chat, chat_sans_outils
import logging
_log = logging.getLogger("resilientflow.agents")
 
 
def _get_secret(key):
    try:
        import streamlit as st
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, "")
 
 
# ── CLIENT NOTION via requests ────────────────────────────────────────────────
def _notion_query(database_id: str, filter_obj: dict = None, sorts: list = None) -> list:
    token = _get_secret("NOTION_TOKEN")
    url   = f"https://api.notion.com/v1/databases/{database_id}/query"
    headers = {
        "Authorization":  f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type":   "application/json",
    }
    payload = {}
    if filter_obj: payload["filter"] = filter_obj
    if sorts:      payload["sorts"]  = sorts
 
    results, has_more, cursor = [], True, None
    while has_more:
        if cursor:
            payload["start_cursor"] = cursor
        resp = _requests.post(url, headers=headers, json=payload, timeout=15)
        if not resp.ok:
            return []
        data = resp.json()
        results.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        cursor   = data.get("next_cursor")
    return results
 
 
# ── IDs Notion — alignés sur les bases [SANDBOX] de notion_client (source unique)
# NE PAS remettre d'IDs en dur : ils pointaient vers d'anciennes bases et
# déconnectaient l'agent des vraies données sandbox.
import re as _re
from notion_client import DB_IDS as _DB_IDS
DB_ORDRES_FAB = _DB_IDS["ordres_fab"]    # 📋 [SANDBOX] Ordres de Fabrication
DB_HISTORIQUE = _DB_IDS["historique"]    # 🔩 [SANDBOX] Plan de Maintenance
DB_PIECES     = _DB_IDS["pieces"]        # 📦 [SANDBOX] Stock Composants
DB_EQUIPE     = _DB_IDS["equipe"]        # 👷 [SANDBOX] Équipe Maintenance RH


def _extract_code(nom: str) -> str:
    """Extrait le code machine (ex: 'P-17') depuis 'Pompe P-17'."""
    if not nom:
        return nom
    m = _re.search(r'\b([A-Z]+-\d+)\b', nom)
    return m.group(1) if m else nom
 
 
# ── HELPERS ───────────────────────────────────────────────────────────────────
def _text(prop):
    if not prop: return ""
    t = prop.get("type")
    if t == "title":        return "".join(r["plain_text"] for r in prop.get("title", []))
    if t == "rich_text":    return "".join(r["plain_text"] for r in prop.get("rich_text", []))
    if t == "select":       s = prop.get("select"); return s["name"] if s else ""
    if t == "multi_select": return ", ".join(o["name"] for o in prop.get("multi_select", []))
    if t == "number":       v = prop.get("number"); return v if v is not None else ""
    if t == "date":         d = prop.get("date"); return d["start"] if d else ""
    return ""
 
def _p(page): return page.get("properties", {})
 
 
# ── OUTILS PLANIFICATION ──────────────────────────────────────────────────────
 
def get_impact_production(equipement: str) -> dict:
    """OF en cours et planifiés sur cet équipement avec coût d'arrêt."""
    res = _notion_query(
        DB_ORDRES_FAB,
        filter_obj={"property": "Équipement concerné", "rich_text": {"contains": equipement}},
        sorts=[{"property": "Priorité", "direction": "ascending"}]
    )
    of_en_cours, of_planifies = [], []
    for page in res:
        p = _p(page)
        statut = _text(p.get("Statut"))
        entry = {
            "reference":       _text(p.get("Ordre de Fabrication")),
            "statut":          statut,
            "produit":         _text(p.get("Produit fabriqué")),
            "ligne":           _text(p.get("Ligne de production")),
            "qte_prevue":      _text(p.get("Quantité cible")),
            "qte_realisee":    _text(p.get("Quantité réalisée")),
            "cout_arret_eur":  _text(p.get("Coût arrêt horaire (€)")),
            "date_fin_prevue": _text(p.get("Date fin prévue")),
            "responsable":     _text(p.get("Responsable OF")),
            "impact_rul":      _text(p.get("Impact RUL")),
        }
        if statut == "En cours":
            of_en_cours.append(entry)
        else:
            of_planifies.append(entry)
 
    return {
        "of_en_cours":  of_en_cours  or [{"info": "Aucun OF en cours sur cet équipement"}],
        "of_planifies": of_planifies or [{"info": "Aucun OF planifié"}],
        "total_of":     len(res),
        "cout_arret_total_eur": sum(float(o.get("cout_arret_eur") or 0) for o in of_en_cours),
    }
 
 
def get_charge_techniciens(equipement: str) -> list:
    """Disponibilité et charge de travail de l'équipe maintenance."""
    res = _notion_query(DB_EQUIPE)
    equipe = []
    for page in res:
        p = _p(page)
        equipe.append({
            "technicien":       _text(p.get("Nom Technicien")),
            "prenom":           _text(p.get("Prénom")),
            "role":             _text(p.get("Rôle")),
            "specialite":       _text(p.get("Spécialité")),
            "habilitations":    _text(p.get("Habilitations")),
            "disponibilite":    _text(p.get("Disponibilité")),
            "charge_h_sem":     _text(p.get("Charge horaire (h/sem)")),
            "heures_restantes": _text(p.get("Heures restantes")),
            "zone":             _text(p.get("Zone assignée")),
        })
    return equipe or [{"info": "Aucun technicien trouvé"}]
 
 
def get_fenetre_maintenance(equipement: str) -> list:
    """Interventions planifiées sur cet équipement — pour trouver un créneau optimal."""
    res = _notion_query(
        DB_HISTORIQUE,
        filter_obj={"and": [
            {"property": "Équipement",  "rich_text": {"contains": equipement}},
            {"property": "Statut",      "select":    {"equals": "Planifiée"}},
        ]},
        sorts=[{"property": "Date planifiée", "direction": "ascending"}]
    )
    return [
        {
            "titre":             _text(_p(p).get("Intervention")),
            "type":              _text(_p(p).get("Type d'intervention")),
            "date":              _text(_p(p).get("Date planifiée")),
            "duree_estimee_h":   _text(_p(p).get("Durée estimée (h)")),
            "technicien":        _text(_p(p).get("Technicien assigné")),
            "cout_eur":          _text(_p(p).get("Coût estimé (€)")),
        }
        for p in res
    ] or [{"info": "Aucune intervention planifiée — fenêtre à créer"}]
 
 
def get_pieces_critiques_manquantes(equipement: str) -> list:
    """Pièces en rupture ou stock bas pouvant bloquer une intervention immédiate."""
    res = _notion_query(
        DB_PIECES,
        filter_obj={"and": [
            {"property": "Équipements compatibles", "rich_text": {"contains": equipement}},
            {"property": "Statut stock",            "select":    {"does_not_equal": "En stock"}},
        ]}
    )
    return [
        {
            "designation":     _text(_p(p).get("Composant")),
            "reference":       _text(_p(p).get("Réf. fabricant")),
            "statut_stock":    _text(_p(p).get("Statut stock")),
            "stock_actuel":    _text(_p(p).get("Stock actuel")),
            "stock_minimum":   _text(_p(p).get("Stock minimum (seuil alerte)")),
            "delai_livraison": _text(_p(p).get("Délai réappro (jours)")),
            "fournisseur":     _text(_p(p).get("Fournisseur principal")),
            "notes":           _text(_p(p).get("Notes")),
        }
        for p in res
    ] or [{"info": "Aucune pièce critique manquante — stock OK pour intervention"}]
 
 
# ── OUTILS DÉCLARÉS À L'AGENT ─────────────────────────────────────────────────
TOOLS = [
    {
        "name": "get_impact_production",
        "description": "Récupère les OF en cours et planifiés sur cet équipement : coût d'arrêt, avancement, dates de fin. Permet d'évaluer le risque financier d'un arrêt.",
        "input_schema": {"type": "object", "properties": {"equipement": {"type": "string"}}, "required": ["equipement"]}
    },
    {
        "name": "get_charge_techniciens",
        "description": "Analyse la disponibilité et la charge de travail de l'équipe maintenance. Permet de trouver le technicien disponible avec les bonnes habilitations.",
        "input_schema": {"type": "object", "properties": {"equipement": {"type": "string"}}, "required": ["equipement"]}
    },
    {
        "name": "get_fenetre_maintenance",
        "description": "Liste les interventions planifiées avec leurs dates et durées. Permet de trouver un créneau d'arrêt optimal qui minimise l'impact production.",
        "input_schema": {"type": "object", "properties": {"equipement": {"type": "string"}}, "required": ["equipement"]}
    },
    {
        "name": "get_pieces_critiques_manquantes",
        "description": "Identifie les pièces en rupture ou stock bas qui pourraient bloquer une intervention immédiate. Essentiel pour l'arbitrage du timing.",
        "input_schema": {"type": "object", "properties": {"equipement": {"type": "string"}}, "required": ["equipement"]}
    }
]
 
 
def _execute(name, inputs):
    # Normalise l'identifiant machine ("Pompe P-17" -> "P-17") : les bases
    # stockent le code, pas le libellé complet.
    eq = _extract_code(inputs.get("equipement", ""))
    if name == "get_impact_production":           return get_impact_production(eq)
    if name == "get_charge_techniciens":          return get_charge_techniciens(eq)
    if name == "get_fenetre_maintenance":         return get_fenetre_maintenance(eq)
    if name == "get_pieces_critiques_manquantes": return get_pieces_critiques_manquantes(eq)
    return {"erreur": f"Outil inconnu : {name}"}
 
 
# ── PROMPT SYSTÈME ────────────────────────────────────────────────────────────
SYSTEM = """[RÔLE]
Tu es l'assistant de Sophie, Manager Maintenance de l'Unité B. Tu analyses les alertes machine pour l'aider à décider de la planification.

[MISSION]
Arbitrer entre intervention immédiate et report, et produire une recommandation chiffrée et actionnable. Tu proposes ; Sophie tranche.

[CONTEXTE]
Prends en compte : l'impact sur la production en cours (OF actifs, coût d'arrêt horaire), la disponibilité et la charge des techniciens, la disponibilité des pièces, et les fenêtres de maintenance déjà planifiées. Ces éléments te sont fournis dans le message et via les outils.

[OUTILS]
Interroge les outils Notion (historique, équipe, pièces) pour fonder ton arbitrage AVANT de conclure.

[CONTRAINTES]
N'invente aucun chiffre ni disponibilité : utilise uniquement les données fournies / les outils. Chiffre systématiquement le risque (%) et l'impact (€) quand les données le permettent ; sinon, indique « donnée manquante ».

[LIMITES & ESCALADE]
Tu prépares la décision, tu ne lances pas l'intervention toi-même. Escalade à Antoine (Directeur Technique) tout arbitrage à enjeu d'investissement (remplacement, CAPEX) ou dépassant le périmètre de planification.

[FORMAT] (Markdown)
1. **Situation** : résumé de l'alerte et des contraintes identifiées
2. **Option A — Intervention immédiate** : avantages, risques, coût estimé (€)
3. **Option B — Report planifié** : date suggérée, conditions requises, risque RUL (%)
4. **Recommandation** : option privilégiée + justification chiffrée
5. **Actions à lancer maintenant** : liste concrète (affecter Lionel, commander une pièce, prévenir la HSE…)

[TON]
Factuel, orienté décision. Chiffre les risques financiers dès que possible.
"""
 
 
# ── FONCTION PRINCIPALE ───────────────────────────────────────────────────────
def run_agent_sophie(c_rul: int, equipement: str = "Pompe P-17",
                     c_temp: float = None, c_vib: float = None) -> str:
    """Lance l'agent Sophie : pré-fetch des faits (impact production, équipe,
    pièces, fenêtres) injectés comme contexte, puis UN SEUL appel LLM pour
    l'arbitrage (pas de boucle tool_use = pas de fuite tool_call). Repli propre
    si le LLM est indisponible."""
    code = _extract_code(equipement)

    # ── Pré-fetch des faits réels (le LLM rédige, il n'invente pas) ────────────
    impact  = get_impact_production(code)
    equipe  = get_charge_techniciens(code)
    pieces  = get_pieces_critiques_manquantes(code)
    fenetre = get_fenetre_maintenance(code)

    details = ""
    if c_temp: details += f"\n- Température : {c_temp:.1f} °C"
    if c_vib:  details += f"\n- Vibration : {c_vib:.2f} mm/s"

    contexte = (
        f"ALERTE MAINTENANCE — {equipement} (code {code})\n"
        f"- RUL estimé : {c_rul} jours{details}\n\n"
        f"IMPACT PRODUCTION (OF & coût d'arrêt) :\n"
        f"{json.dumps(impact, ensure_ascii=False, indent=2)}\n\n"
        f"ÉQUIPE MAINTENANCE (disponibilité / charge) :\n"
        f"{json.dumps(equipe, ensure_ascii=False, indent=2)}\n\n"
        f"PIÈCES CRITIQUES MANQUANTES :\n"
        f"{json.dumps(pieces, ensure_ascii=False, indent=2)}\n\n"
        f"FENÊTRES DE MAINTENANCE PLANIFIÉES :\n"
        f"{json.dumps(fenetre, ensure_ascii=False, indent=2)}\n\n"
        f"À partir de CES données uniquement, arbitre entre intervention immédiate "
        f"et report, chiffre le risque (%) et l'impact (€), et recommande la "
        f"meilleure stratégie au format demandé."
    )

    texte = chat_sans_outils(system=SYSTEM, user=contexte, max_tokens=2000)
    if texte:
        _log.info("agent_sophie: reponse LLM (contexte pre-fetche)")
        return texte
    _log.warning("agent_sophie: LLM indisponible ou artefact -> repli")
    return (
        "⚠️ L'agent n'a pas pu conclure son analyse. "
        "Consulte les onglets S0 (alertes) et S2 (affectation) pour les données brutes."
    )
 
 
# ── TEST STANDALONE ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(run_agent_sophie(c_rul=2, equipement="Pompe P-17", c_temp=82.0, c_vib=3.5))
