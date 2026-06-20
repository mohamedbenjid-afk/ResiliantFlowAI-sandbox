"""
agents/agent_leila.py — Agent conformité HSE de Leila (Responsable HSE)
Rôle : générer automatiquement les matrices de risques, les exigences EPI
       et les preuves d'audit ISO 45001 à partir des données d'intervention.

Intégration dans pages/4_Leila.py :
    from agents.agent_leila import run_agent_leila
    audit = run_agent_leila(c_temp, c_vib, c_pres, c_rul)
"""

import os, json
from datetime import date
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
DB_HISTORIQUE = "6f53558bfbee455891efa53b6536d892"   # Historique & plan de maintenance
DB_PIECES     = "c22138baa8ca4806b19403108735bc68"   # Pièces détachées
DB_HSE        = "b6ab3a9bd41d4967add92f27d1cd2d5c"   # Documentation & HSE
DB_EQUIPE     = "0a82b4f53a26491c81e64b0cb8bb058c"   # Équipe maintenance (habilitations)


# ── HELPERS ───────────────────────────────────────────────────────────────────
def _text(prop):
    if not prop: return ""
    t = prop.get("type")
    if t == "title":        return "".join(r["plain_text"] for r in prop.get("title", []))
    if t == "rich_text":    return "".join(r["plain_text"] for r in prop.get("rich_text", []))
    if t == "select":       s = prop.get("select"); return s["name"] if s else ""
    if t == "multi_select": return [o["name"] for o in prop.get("multi_select", [])]
    if t == "number":       v = prop.get("number"); return v if v is not None else ""
    if t == "date":         d = prop.get("date"); return d["start"] if d else ""
    if t == "url":          return prop.get("url") or ""
    return ""

def _p(page): return page.get("properties", {})


# ── RÉFÉRENTIEL HSE INTERNE (données réglementaires statiques) ────────────────
EPI_PAR_RISQUE = {
    "thermique":   ["Gants isolants HT (EN 407)", "Écran facial anti-chaleur", "Combinaison ignifugée"],
    "mecanique":   ["Lunettes de protection (EN 166)", "Casque anti-bruit (EN 352)", "Gants anti-coupure (EN 388)"],
    "hydraulique": ["Écran facial anti-projection", "Combinaison anti-projections", "Bottes de sécurité étanches"],
    "electrique":  ["Gants isolants classe 2 (EN 60903)", "Écran facial arc électrique", "Vêtement arc flash"],
    "standard":    ["Casque de sécurité (EN 397)", "Chaussures S3 (EN 345)", "Gants de travail (EN 388)"],
}

NORMES_LOTO = {
    "procedure": "ISO 50001 + NF EN 1037 — Condamnation et cadenassage",
    "etapes": [
        "1. Identifier toutes les sources d'énergie (électrique, hydraulique, pneumatique)",
        "2. Informer les personnes concernées de l'arrêt",
        "3. Éteindre l'équipement via la commande officielle",
        "4. Condamner le sectionneur principal avec cadenas personnel",
        "5. Dissiper les énergies résiduelles (décharge condensateurs, purge pression)",
        "6. Vérifier l'absence d'énergie résiduelle (essai de mise en marche)",
        "7. Apposer la consigne de sécurité visible",
    ]
}


# ── OUTILS HSE ────────────────────────────────────────────────────────────────

def get_exigences_hse_intervention(equipement: str) -> dict:
    """Documents HSE, exigences EPI et procédures LOTO pour cet équipement."""
    # Documents HSE associés à la machine
    docs_res = _notion_query(
        DB_HSE,
        filter_obj={"property": "Machine concernée", "rich_text": {"contains": equipement}}
    )
    docs_hse = []
    for page in docs_res:
        p = _p(page)
        docs_hse.append({
            "titre":           _text(p.get("Titre document")),
            "type":            _text(p.get("Type")),
            "statut":          _text(p.get("Statut")),
            "niveau_risque":   _text(p.get("Niveau risque")),
            "epi_obligatoires":_text(p.get("EPI obligatoires")),   # list
            "persona":         _text(p.get("Persona destinataire")), # list
            "resume":          _text(p.get("Contenu résumé")),
            "lien":            _text(p.get("Lien document")),
            "date_validation": _text(p.get("Date validation")),
            "date_revision":   _text(p.get("Date révision")),
        })

    # Habilitations de l'équipe
    equipe_res = _notion_query(DB_EQUIPE)
    habilitations = [{
        "technicien":   _text(_p(p).get("Nom Technicien")),
        "habilitations":_text(_p(p).get("Habilitations")),  # list
        "disponibilite":_text(_p(p).get("Disponibilité")),
        "zone":         _text(_p(p).get("Zone assignée")),
    } for p in equipe_res]

    # Interventions planifiées
    interv_res = _notion_query(
        DB_HISTORIQUE,
        filter_obj={"and": [
            {"property": "Machine", "rich_text": {"contains": equipement}},
            {"property": "Statut",  "select":    {"equals": "Planifiée"}},
        ]},
        sorts=[{"property": "Date intervention", "direction": "ascending"}]
    )
    interventions = [{
        "titre":     _text(_p(p).get("Titre intervention")),
        "type":      _text(_p(p).get("Type")),
        "date":      _text(_p(p).get("Date intervention")),
        "technicien":_text(_p(p).get("Technicien assigné")),
        "duree_h":   _text(_p(p).get("Durée estimée (h)")),
    } for p in interv_res]

    return {
        "docs_hse":               docs_hse or [{"info": "Aucun document HSE associé"}],
        "nb_docs_hse":            len(docs_hse),
        "habilitations_equipe":   habilitations,
        "interventions_planifiees": interventions or [{"info": "Aucune intervention planifiée"}],
        "norme_loto":             NORMES_LOTO,
    }


def get_matrice_risques_capteurs(c_temp: float, c_vib: float, c_pres: float) -> dict:
    """Génère la matrice de risques à partir des valeurs capteurs en temps réel."""
    risques = []

    if c_temp >= 110:
        risques.append({
            "type":      "Thermique",
            "niveau":    "ÉLEVÉ" if c_temp >= 120 else "MODÉRÉ",
            "valeur":    f"{c_temp:.1f}°C",
            "seuil":     "110°C",
            "cause":     "Surchauffe stator / garniture mécanique",
            "epi":       EPI_PAR_RISQUE["thermique"],
            "consignes": ["Attendre refroidissement < 45°C avant ouverture", "Ne pas toucher les surfaces"],
            "norme":     "EN 563 — Températures de surface",
        })

    if c_vib >= 4.5:
        risques.append({
            "type":      "Mécanique",
            "niveau":    "ÉLEVÉ" if c_vib >= 6.0 else "MODÉRÉ",
            "valeur":    f"{c_vib:.2f} mm/s",
            "seuil":     "4.5 mm/s",
            "cause":     "Défaut palier / roulement dégradé",
            "epi":       EPI_PAR_RISQUE["mecanique"],
            "consignes": ["Vérifier l'ancrage du châssis", "Contrôler absence de micro-fissures"],
            "norme":     "ISO 10816 — Vibrations mécaniques",
        })

    if c_pres >= 7.0:
        risques.append({
            "type":      "Hydraulique",
            "niveau":    "ÉLEVÉ" if c_pres >= 8.5 else "MODÉRÉ",
            "valeur":    f"{c_pres:.1f} bar",
            "seuil":     "7.0 bar",
            "cause":     "Surpression circuit / colmatage filtre",
            "epi":       EPI_PAR_RISQUE["hydraulique"],
            "consignes": ["Purger la pression résiduelle avant déconnexion", "Utiliser raccords anti-projection"],
            "norme":     "EN 14460 — Résistance aux explosions",
        })

    if not risques:
        risques.append({
            "type":      "Standard",
            "niveau":    "FAIBLE",
            "valeur":    "Tous capteurs nominaux",
            "seuil":     "N/A",
            "cause":     "Maintenance préventive planifiée",
            "epi":       EPI_PAR_RISQUE["standard"],
            "consignes": ["Appliquer procédure LOTO standard"],
            "norme":     "ISO 45001 — Systèmes de management SST",
        })

    return {
        "date_evaluation":    date.today().isoformat(),
        "equipement":         "Pompe P-17",
        "nb_risques":         len(risques),
        "risque_maximal":     max((r["niveau"] for r in risques),
                                  key=lambda x: ["FAIBLE","MODÉRÉ","ÉLEVÉ"].index(x)),
        "risques_identifies": risques,
        "loto_obligatoire":   True,
        "norme_reference":    "ISO 45001:2018 — Management de la santé et sécurité au travail",
    }


def get_conformite_pieces(equipement: str) -> dict:
    """Vérifie la traçabilité réglementaire des pièces (référence + fournisseur)."""
    res = _notion_query(
        DB_PIECES,
        filter_obj={"property": "Machine concernée", "rich_text": {"contains": equipement}}
    )
    conformes, non_conformes = [], []
    for page in res:
        p     = _p(page)
        ref   = _text(p.get("Référence"))
        fourn = _text(p.get("Fournisseur"))
        entry = {
            "designation": _text(p.get("Désignation pièce")),
            "reference":   ref,
            "fournisseur": fourn,
            "statut_stock":_text(p.get("Statut stock")),
            "conforme":    bool(ref and fourn),
        }
        if entry["conforme"]:
            conformes.append(entry)
        else:
            non_conformes.append(entry)

    total = len(conformes) + len(non_conformes)
    return {
        "taux_conformite_pct":  round(len(conformes) / max(total, 1) * 100, 1),
        "nb_pieces_total":      total,
        "pieces_conformes":     conformes,
        "pieces_non_conformes": non_conformes,
        "observation":          "Toutes pièces conformes" if not non_conformes
                                else f"{len(non_conformes)} pièce(s) sans traçabilité complète",
    }


def generer_rapport_audit(equipement: str, technicien: str = "Lionel") -> dict:
    """Génère les métadonnées du dossier de preuve ISO 45001."""
    today = date.today().isoformat()
    ref   = f"RF_AUDIT_ISO45001_{equipement.replace(' ', '_').replace('-', '')}_{today}.pdf"
    return {
        "reference_dossier":   ref,
        "date_generation":     today,
        "technicien_concerne": technicien,
        "equipement":          equipement,
        "norme":               "ISO 45001:2018",
        "contenu_dossier": [
            "Matrice des risques identifiés (générée automatiquement)",
            "Liste EPI obligatoires validée",
            "Procédure LOTO appliquée (étapes horodatées)",
            "Habilitations technicien vérifiées",
            "Traçabilité pièces détachées (référence fournisseur)",
            "Documents HSE machine consultés",
            "Signature électronique agent ResilientFlow AI",
        ],
        "statut":         "Généré — Prêt pour transmission organisme certificateur",
        "validite_jours": 90,
    }


# ── OUTILS DÉCLARÉS À L'AGENT ─────────────────────────────────────────────────
TOOLS = [
    {
        "name": "get_exigences_hse_intervention",
        "description": "Récupère les documents HSE, exigences EPI, habilitations de l'équipe et interventions planifiées pour cet équipement. Permet de vérifier la conformité réglementaire.",
        "input_schema": {"type": "object", "properties": {"equipement": {"type": "string"}}, "required": ["equipement"]}
    },
    {
        "name": "get_matrice_risques_capteurs",
        "description": "Génère la matrice de risques en temps réel à partir des valeurs capteurs. Identifie les risques thermiques, mécaniques et hydrauliques avec les EPI réglementaires associés.",
        "input_schema": {
            "type": "object",
            "properties": {
                "c_temp": {"type": "number", "description": "Température en °C"},
                "c_vib":  {"type": "number", "description": "Vibration en mm/s"},
                "c_pres": {"type": "number", "description": "Pression en bar"},
            },
            "required": ["c_temp", "c_vib", "c_pres"]
        }
    },
    {
        "name": "get_conformite_pieces",
        "description": "Vérifie la traçabilité réglementaire des pièces détachées (référence + fournisseur). Essentiel pour la conformité ISO 45001.",
        "input_schema": {"type": "object", "properties": {"equipement": {"type": "string"}}, "required": ["equipement"]}
    },
    {
        "name": "generer_rapport_audit",
        "description": "Génère les métadonnées du dossier de preuve ISO 45001 avec référence, horodatage et contenu certifié.",
        "input_schema": {
            "type": "object",
            "properties": {
                "equipement":  {"type": "string"},
                "technicien":  {"type": "string", "description": "Nom du technicien intervenant"}
            },
            "required": ["equipement"]
        }
    }
]


def _execute(name, inputs):
    if name == "get_exigences_hse_intervention": return get_exigences_hse_intervention(inputs["equipement"])
    if name == "get_matrice_risques_capteurs":   return get_matrice_risques_capteurs(inputs["c_temp"], inputs["c_vib"], inputs["c_pres"])
    if name == "get_conformite_pieces":          return get_conformite_pieces(inputs["equipement"])
    if name == "generer_rapport_audit":          return generer_rapport_audit(inputs["equipement"], inputs.get("technicien", "Lionel"))
    return {"erreur": f"Outil inconnu : {name}"}


# ── PROMPT SYSTÈME ────────────────────────────────────────────────────────────
SYSTEM = """Tu es l'assistant HSE de Leila, Responsable Santé-Sécurité-Environnement.
Tu analyses les situations d'intervention pour garantir la conformité ISO 45001.

Ton rôle : identifier les risques réglementaires, prescrire les EPI obligatoires,
vérifier la conformité des procédures et générer les preuves d'audit.

Format de réponse attendu :
1. **Niveau de risque global** : FAIBLE / MODÉRÉ / ÉLEVÉ avec justification
2. **Matrice des risques identifiés** : tableau risque / niveau / EPI requis / norme
3. **Procédure LOTO** : étapes obligatoires si applicable
4. **Points de non-conformité** : ce qui manque ou doit être corrigé
5. **Dossier de preuve** : référence du rapport généré et contenu

Sois précis sur les normes (EN, ISO, NF). Leila répond devant un auditeur externe.
"""


# ── FONCTION PRINCIPALE ───────────────────────────────────────────────────────
def run_agent_leila(c_temp: float, c_vib: float, c_pres: float, c_rul: int) -> str:
    """
    Lance l'agent Leila avec les valeurs capteurs courantes.
    Retourne l'évaluation HSE complète en texte Markdown.
    """
    situation = (
        f"ÉVALUATION HSE — Pompe P-17, Unité B\n"
        f"- Température : {c_temp:.1f}°C\n"
        f"- Vibration   : {c_vib:.2f} mm/s\n"
        f"- Pression    : {c_pres:.1f} bar\n"
        f"- RUL estimé  : {c_rul}h\n\n"
        f"Réalise l'évaluation HSE complète : matrice de risques, EPI requis, "
        f"conformité LOTO, traçabilité pièces et génère le dossier d'audit ISO 45001."
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
    print(run_agent_leila(c_temp=117.0, c_vib=5.8, c_pres=4.6, c_rul=12))
