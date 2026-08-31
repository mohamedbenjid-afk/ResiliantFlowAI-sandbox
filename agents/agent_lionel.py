import os, json, re

import sys as _sys, os as _os
_sys.path.append(_os.path.join(_os.path.dirname(__file__), '..'))
from llm_client import chat as _llm_chat

# ── CLIENT NOTION PARTAGÉ ─────────────────────────────────────────────────────
# CORRECTION (Lot B) : l'agent utilise désormais le client Notion partagé
# `notion_client.py` — qui pointe vers les bases SANDBOX correctes et le bon
# schéma ESCP (titre = "Équipement"). L'ancien mini-client embarqué pointait
# vers d'anciens IDs PROD codés en dur avec des noms de champs obsolètes
# ("Nom Machine"), d'où le "Fiche P-17 absente de la base".
import notion_client as nc


def _extract_code(nom: str) -> str:
    """Extrait le code machine (ex: 'P-17') depuis 'Pompe P-17'."""
    if not nom:
        return nom
    m = re.search(r'\b([A-Z]+-\d+)\b', nom)
    return m.group(1) if m else nom


# ── OUTILS TERRAIN (délégués au client Notion partagé) ────────────────────────

def get_fiche_equipement(nom: str) -> dict:
    """Fiche technique de la machine : seuils, statut, RUL, contexte."""
    code = _extract_code(nom)
    m = nc.get_machine(code) or nc.get_machine(nom)
    if not m:
        return {"erreur": f"'{nom}' non trouvé dans la base machines"}
    return {
        "machine":               m.get("nom"),
        "id_machine":            m.get("id"),
        "type":                  m.get("type"),
        "statut":                m.get("statut"),
        "rul_jours":             m.get("rul_jours"),
        "seuil_temp":            m.get("seuil_temp"),
        "seuil_vib":             m.get("seuil_vib"),
        "seuil_pression":        m.get("seuil_pression"),
        "unite":                 m.get("unite"),
        "responsable":           m.get("responsable"),
        "modele":                m.get("modele"),
        "fabricant":             m.get("fabricant"),
        "notes":                 m.get("notes"),
    }


def get_procedure_intervention(equipement: str, type_anomalie: str) -> dict:
    """Intervention planifiée la plus pertinente pour ce type d'anomalie."""
    code = _extract_code(equipement)
    interventions = nc.get_historique(machine_id=code, statut="Planifiée")
    if not interventions:
        return {"info": "Aucune intervention planifiée trouvée — contacter Sophie pour planification"}

    # Cherche une intervention liée au type d'anomalie, sinon prend la plus proche
    kws = [type_anomalie.lower(), "joint", "roulement", "vibr", "surchauf", "pression"]
    for it in interventions:
        titre = (it.get("titre") or "").lower()
        if any(kw in titre for kw in kws):
            return it
    return interventions[0]   # fallback : intervention la plus proche


def get_disponibilite_piece(nom_piece: str) -> dict:
    """Stock et emplacement magasin d'une pièce (recherche par désignation)."""
    pieces = nc.get_pieces()
    q = (nom_piece or "").lower()
    match = [p for p in pieces if q in (p.get("designation") or "").lower()]
    if not match:
        return {"erreur": f"'{nom_piece}' non trouvé en magasin"}
    p = match[0]
    stock = p.get("stock_actuel")
    return {
        "designation":     p.get("designation"),
        "reference":       p.get("reference"),
        "categorie":       p.get("categorie"),
        "stock_actuel":    stock,
        "stock_minimum":   p.get("stock_minimum"),
        "statut_stock":    p.get("statut_stock"),
        "emplacement":     p.get("emplacement"),
        "fournisseur":     p.get("fournisseur"),
        "delai_livraison": p.get("delai_livraison"),
        "notes":           p.get("notes"),
        "dispo_immediate": (stock or 0) > 0,
    }


# ── OUTILS DÉCLARÉS À L'AGENT ─────────────────────────────────────────────────
TOOLS = [
    {
        "name": "get_fiche_equipement",
        "description": "Récupère la fiche technique de la machine : seuils d'alerte (température, vibration, pression), statut, RUL, responsable et notes.",
        "input_schema": {
            "type": "object",
            "properties": {"nom": {"type": "string", "description": "Nom de la machine ex: 'Pompe P-17'"}},
            "required": ["nom"]
        }
    },
    {
        "name": "get_procedure_intervention",
        "description": "Récupère l'intervention planifiée la plus pertinente : titre, type, date, technicien assigné, composants à préparer.",
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
Tu reçois des relevés capteurs temps réel sur la Pompe P-17.

Le RUL (durée de vie résiduelle) est exprimé EN JOURS et provient du système
prédictif (GMAO). Un RUL faible = panne proche. Interprète toujours le RUL en jours.

Utilise les outils Notion pour confirmer les seuils machine, l'intervention
planifiée et le stock des pièces AVANT de conclure.

Ton rôle : guider Lionel avec des instructions claires et actionnables.
Format de réponse attendu :
1. **Diagnostic** : cause probable (1-2 phrases max), cohérente avec les seuils réels
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

    NB (Lot A) : le RUL est passé et affiché EN JOURS (cohérent avec K0 et
    shared_state). Les seuils annoncés correspondent au simulateur réel
    (surchauffe dès ~82 °C), pour éviter les diagnostics contradictoires.
    """
    situation = (
        f"ALERTE POMPE P-17 (Unité B) — relevés capteurs temps réel :\n"
        f"- Température : {c_temp:.1f} °C  (seuil alerte 75 °C · seuil critique 82 °C)\n"
        f"- Vibration   : {c_vib:.2f} mm/s (seuil alerte 2.5 · seuil critique 3.5 mm/s)\n"
        f"- Pression    : {c_pres:.1f} bar  (nominale ~4.4 bar)\n"
        f"- RUL estimé  : {c_rul} jours (source : système prédictif GMAO)\n\n"
        f"Analyse la situation et donne les instructions d'intervention terrain. "
        f"Commence par appeler get_fiche_equipement('Pompe P-17') pour confirmer "
        f"le contexte machine, puis vérifie l'intervention planifiée et les pièces."
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
    # Scénario surchauffe critique : 82 °C, 3.5 mm/s, RUL 1 jour
    print(run_agent_lionel(c_temp=82.0, c_vib=3.5, c_pres=4.4, c_rul=1))
