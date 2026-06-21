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
from llm_client import chat as _llm_chat


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


# ── IDs des bases Notion ResilientFlow ───────────────────────────────────────
DB_ORDRES_FAB = "d7ee45dab07943c1bda09a6b47089202"   # Ordres de fabrication
DB_HISTORIQUE = "6f53558bfbee455891efa53b6536d892"   # Historique & plan de maintenance
DB_PIECES     = "c22138baa8ca4806b19403108735bc68"   # Pièces détachées
DB_EQUIPE     = "0a82b4f53a26491c81e64b0cb8bb058c"   # Équipe maintenance


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
        filter_obj={"property": "Machine impactée", "rich_text": {"contains": equipement}},
        sorts=[{"property": "Priorité", "direction": "ascending"}]
    )
    of_en_cours, of_planifies = [], []
    for page in res:
        p = _p(page)
        statut = _text(p.get("Statut OF"))
        entry = {
            "reference":       _text(p.get("Référence OF")),
            "statut":          statut,
            "produit":         _text(p.get("Produit")),
            "ligne":           _text(p.get("Ligne de production")),
            "qte_prevue":      _text(p.get("Quantité prévue")),
            "qte_realisee":    _text(p.get("Quantité réalisée")),
            "cout_arret_eur":  _text(p.get("Coût arrêt (€)")),
            "duree_arret_h":   _text(p.get("Durée arrêt (h)")),
            "date_fin_prevue": _text(p.get("Date fin prévue")),
            "responsable":     _text(p.get("Responsable production")),
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
            {"property": "Machine", "rich_text": {"contains": equipement}},
            {"property": "Statut",  "select":    {"equals": "Planifiée"}},
        ]},
        sorts=[{"property": "Date intervention", "direction": "ascending"}]
    )
    return [
        {
            "titre":          _text(_p(p).get("Titre intervention")),
            "type":           _text(_p(p).get("Type")),
            "date":           _text(_p(p).get("Date intervention")),
            "prochaine_echeance": _text(_p(p).get("Prochaine échéance")),
            "duree_estimee_h":_text(_p(p).get("Durée estimée (h)")),
            "technicien":     _text(_p(p).get("Technicien assigné")),
            "cout_eur":       _text(_p(p).get("Coût intervention (€)")),
        }
        for p in res
    ] or [{"info": "Aucune intervention planifiée — fenêtre à créer"}]


def get_pieces_critiques_manquantes(equipement: str) -> list:
    """Pièces en rupture ou stock bas pouvant bloquer une intervention immédiate."""
    res = _notion_query(
        DB_PIECES,
        filter_obj={"and": [
            {"property": "Machine concernée", "rich_text": {"contains": equipement}},
            {"property": "Statut stock",      "select":    {"does_not_equal": "En stock"}},
        ]}
    )
    return [
        {
            "designation":     _text(_p(p).get("Désignation pièce")),
            "reference":       _text(_p(p).get("Référence")),
            "statut_stock":    _text(_p(p).get("Statut stock")),
            "stock_actuel":    _text(_p(p).get("Stock actuel")),
            "stock_minimum":   _text(_p(p).get("Stock minimum")),
            "delai_livraison": _text(_p(p).get("Délai livraison (j)")),
            "fournisseur":     _text(_p(p).get("Fournisseur")),
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
    if name == "get_impact_production":           return get_impact_production(inputs["equipement"])
    if name == "get_charge_techniciens":          return get_charge_techniciens(inputs["equipement"])
    if name == "get_fenetre_maintenance":         return get_fenetre_maintenance(inputs["equipement"])
    if name == "get_pieces_critiques_manquantes": return get_pieces_critiques_manquantes(inputs["equipement"])
    return {"erreur": f"Outil inconnu : {name}"}


# ── PROMPT SYSTÈME ────────────────────────────────────────────────────────────
SYSTEM = """Tu es l'assistant de Sophie, Manager Maintenance de l'Unité B.
Tu analyses les alertes machine pour l'aider à prendre des décisions de planification.

Ton rôle : arbitrer entre intervention immédiate et report, en tenant compte de :
- L'impact sur la production en cours (OF actifs, coût d'arrêt)
- La disponibilité des techniciens et leur charge
- La disponibilité des pièces nécessaires
- Les fenêtres de maintenance déjà planifiées

Format de réponse attendu :
1. **Situation** : résumé de l'alerte et des contraintes identifiées
2. **Option A — Intervention immédiate** : avantages, risques, coût estimé
3. **Option B — Report planifié** : date suggérée, conditions requises, risque RUL
4. **Recommandation** : quelle option privilégier et pourquoi
5. **Actions à lancer maintenant** : liste concrète (contacter Lionel, commander pièce, etc.)

Sois factuel. Chiffre les risques financiers quand tu le peux.
"""


# ── FONCTION PRINCIPALE ───────────────────────────────────────────────────────
def run_agent_sophie(c_rul: int, equipement: str = "Pompe P-17",
                     c_temp: float = None, c_vib: float = None) -> str:
    """
    Lance l'agent Sophie avec le RUL courant et le contexte machine.
    Retourne l'arbitrage planification en texte Markdown.
    """
    details = ""
    if c_temp: details += f"\n- Température : {c_temp:.1f}°C"
    if c_vib:  details += f"\n- Vibration   : {c_vib:.2f} mm/s"

    situation = (
        f"ALERTE MAINTENANCE — {equipement}\n"
        f"- RUL estimé : {c_rul}h{details}\n\n"
        f"Analyse l'impact production, la disponibilité des ressources "
        f"et recommande la meilleure stratégie d'intervention."
    )

    messages = [{"role": "user", "content": situation}]
    while True:
        resp = _llm_chat(system=SYSTEM, messages=messages, tools=TOOLS, max_tokens=2000)
        if resp.stop_reason == "end_turn":
            return resp.final_text()
        if resp.stop_reason == "tool_use":
            results = []
            for tc in resp.tool_calls():
                out = _execute(tc["name"], tc["input"])
                results.append({"type": "tool_result", "tool_use_id": tc.get("id", "tc0"),
                                "content": json.dumps(out, ensure_ascii=False)})
            messages.append({"role": "assistant", "content": resp.content})
            messages.append({"role": "user",      "content": results})


# ── TEST STANDALONE ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(run_agent_sophie(c_rul=18, equipement="Pompe P-17", c_temp=78.0, c_vib=5.8))
