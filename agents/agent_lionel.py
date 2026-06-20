import os, json
import requests as _requests

import sys as _sys, os as _os
_sys.path.append(_os.path.join(_os.path.dirname(__file__), '..'))
from llm_client import chat as _llm_chat


def _get_secret(key):
    try:
        import streamlit as st
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, "")


# ── CLIENT NOTION via requests ────────────────────────────────────────────────
def _notion_query(database_id: str, filter_obj: dict = None, sorts: list = None) -> list:
    """Requête Notion Database API directement via requests."""
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
DB_MACHINES   = "5279cb2a42b54b42936e22313521f825"   # Machines & équipements
DB_HISTORIQUE = "6f53558bfbee455891efa53b6536d892"   # Historique & plan de maintenance
DB_PIECES     = "c22138baa8ca4806b19403108735bc68"   # Pièces détachées


# ── HELPERS NOTION ────────────────────────────────────────────────────────────
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


# ── OUTILS TERRAIN ────────────────────────────────────────────────────────────

def get_fiche_equipement(nom: str) -> dict:
    """Seuils, état de dégradation et prochaine maintenance prévue."""
    res = _notion_query(
        DB_MACHINES,
        filter_obj={"property": "Nom Machine", "title": {"contains": nom}}
    )
    if not res:
        return {"erreur": f"'{nom}' non trouvé dans la base machines"}
    p = _p(res[0])
    return {
        "machine":               _text(p.get("Nom Machine")),
        "id_machine":            _text(p.get("ID Machine")),
        "type":                  _text(p.get("Type")),
        "statut":                _text(p.get("Statut")),
        "rul_jours":             _text(p.get("RUL (jours)")),
        "temperature_actuelle":  _text(p.get("Température actuelle (°C)")),
        "vibration_actuelle":    _text(p.get("Vibration actuelle (mm/s)")),
        "score_degradation_pct": _text(p.get("Score dégradation (%)")),
        "seuil_temp":            _text(p.get("Seuil température (°C)")),
        "seuil_vib":             _text(p.get("Seuil vibration (mm/s)")),
        "unite":                 _text(p.get("Unité / Zone")),
        "responsable":           _text(p.get("Responsable")),
        "derniere_inspection":   _text(p.get("Dernière inspection")),
        "prochaine_maintenance": _text(p.get("Prochaine maintenance")),
        "notes_ia":              _text(p.get("Notes IA")),
    }


def get_procedure_intervention(equipement: str, type_anomalie: str) -> dict:
    """Intervention planifiée la plus pertinente pour ce type d'anomalie."""
    res = _notion_query(
        DB_HISTORIQUE,
        filter_obj={"and": [
            {"property": "Machine",  "rich_text": {"contains": equipement}},
            {"property": "Statut",   "select":    {"equals": "Planifiée"}},
        ]},
        sorts=[{"property": "Date intervention", "direction": "ascending"}]
    )
    if not res:
        return {"info": "Aucune intervention planifiée trouvée — contacter Sophie pour planification"}

    # Cherche une intervention liée au type d'anomalie, sinon prend la plus proche
    for page in res:
        p = _p(page)
        titre = _text(p.get("Titre intervention")).lower()
        if any(kw in titre for kw in [type_anomalie.lower(), "joint", "roulement", "vibr", "surchauf", "pression"]):
            return _format_intervention(p)
    return _format_intervention(_p(res[0]))   # fallback : intervention la plus proche


def _format_intervention(p: dict) -> dict:
    return {
        "titre":          _text(p.get("Titre intervention")),
        "type":           _text(p.get("Type")),
        "statut":         _text(p.get("Statut")),
        "date":           _text(p.get("Date intervention")),
        "duree_estimee_h":_text(p.get("Durée estimée (h)")),
        "technicien":     _text(p.get("Technicien assigné")),
        "pieces":         _text(p.get("Pièces remplacées")),
        "actions":        _text(p.get("Actions réalisées")),
        "cause_racine":   _text(p.get("Cause racine")),
        "cout_eur":       _text(p.get("Coût intervention (€)")),
        "observations":   _text(p.get("Observations")),
    }


def get_disponibilite_piece(nom_piece: str) -> dict:
    """Stock et emplacement magasin d'une pièce."""
    res = _notion_query(
        DB_PIECES,
        filter_obj={"property": "Désignation pièce", "title": {"contains": nom_piece}}
    )
    if not res:
        return {"erreur": f"'{nom_piece}' non trouvé en magasin"}
    p = _p(res[0])
    stock = _text(p.get("Stock actuel"))
    return {
        "designation":     _text(p.get("Désignation pièce")),
        "reference":       _text(p.get("Référence")),
        "categorie":       _text(p.get("Catégorie")),
        "stock_actuel":    stock,
        "stock_minimum":   _text(p.get("Stock minimum")),
        "statut_stock":    _text(p.get("Statut stock")),
        "emplacement":     _text(p.get("Emplacement magasin")),
        "fournisseur":     _text(p.get("Fournisseur")),
        "delai_livraison": _text(p.get("Délai livraison (j)")),
        "notes":           _text(p.get("Notes")),
        "dispo_immediate": int(stock or 0) > 0,
    }


# ── OUTILS DÉCLARÉS À L'AGENT ─────────────────────────────────────────────────
TOOLS = [
    {
        "name": "get_fiche_equipement",
        "description": "Récupère la fiche technique de la machine : seuils d'alerte (température, vibration), score de dégradation, RUL, prochaine maintenance et notes IA.",
        "input_schema": {
            "type": "object",
            "properties": {"nom": {"type": "string", "description": "Nom de la machine ex: 'Pompe P-17'"}},
            "required": ["nom"]
        }
    },
    {
        "name": "get_procedure_intervention",
        "description": "Récupère l'intervention planifiée la plus pertinente : titre, type, date, durée estimée, technicien assigné, pièces à préparer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "equipement":    {"type": "string"},
                "type_anomalie": {"type": "string", "description": "Nature du problème ex: 'vibration', 'surchauffe', 'pression'"}
            },
            "required": ["equipement", "type_anomalie"]
        }
    },
    {
        "name": "get_disponibilite_piece",
        "description": "Vérifie si une pièce est disponible en magasin et indique son emplacement exact.",
        "input_schema": {
            "type": "object",
            "properties": {"nom_piece": {"type": "string", "description": "Nom ou mot-clé de la pièce ex: 'joint', 'roulement', 'filtre'"}},
            "required": ["nom_piece"]
        }
    }
]


def _execute(name, inputs):
    if name == "get_fiche_equipement":       return get_fiche_equipement(inputs["nom"])
    if name == "get_procedure_intervention": return get_procedure_intervention(inputs["equipement"], inputs["type_anomalie"])
    if name == "get_disponibilite_piece":    return get_disponibilite_piece(inputs["nom_piece"])
    return {"erreur": f"Outil inconnu : {name}"}


# ── PROMPT SYSTÈME ────────────────────────────────────────────────────────────
SYSTEM = """Tu es l'assistant de terrain de Lionel, technicien habilité Mécanique/Hydraulique.
Tu reçois des alertes capteurs en temps réel sur la Pompe P-17.

Ton rôle : guider Lionel avec des instructions claires et actionnables.
Format de réponse attendu :
1. **Diagnostic** : quelle est la cause probable (1-2 phrases max)
2. **Urgence** : niveau de priorité (Immédiat / Dans les 4h / Planifiable)
3. **Avant d'intervenir** : EPI requis + LOTO si nécessaire
4. **Étapes d'intervention** : liste numérotée, concrète
5. **Pièces à préparer** : ce que Lionel doit sortir du magasin avec l'emplacement

Sois direct. Lionel est sur le terrain, pas derrière un bureau. Pas de blabla.
"""


# ── FONCTION PRINCIPALE ───────────────────────────────────────────────────────
def run_agent_lionel(c_temp: float, c_vib: float, c_pres: float, c_rul: int) -> str:
    """
    Lance l'agent Lionel avec les valeurs capteurs courantes.
    Retourne la prescription terrain en texte Markdown.
    """
    situation = (
        f"ALERTE POMPE P-17 :\n"
        f"- Température : {c_temp:.1f}°C (seuil 110°C)\n"
        f"- Vibration   : {c_vib:.2f} mm/s (seuil 4.5 mm/s)\n"
        f"- Pression    : {c_pres:.1f} bar (seuil 7.0 bar)\n"
        f"- RUL estimé  : {c_rul}h\n\n"
        f"Que dois-je faire ? Donne-moi les instructions d'intervention."
    )

    messages = [{"role": "user", "content": situation}]
    while True:
        resp = _llm_chat(system=SYSTEM, messages=messages, tools=TOOLS, max_tokens=1500)
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
    print(run_agent_lionel(c_temp=117.0, c_vib=5.8, c_pres=4.6, c_rul=12))
