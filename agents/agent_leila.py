"""
agents/agent_leila.py — Agent conformité HSE de Leila (Responsable HSE)
Rôle : générer automatiquement les matrices de risques, les exigences EPI
       et les preuves d'audit ISO 45001 à partir des données d'intervention.

Intégration dans pages/4_Leila.py :
    from agents.agent_leila import run_agent_leila
    audit = run_agent_leila(c_temp, c_vib, c_pres, c_rul)
"""

import os, json, re
from datetime import date

import sys, os as _os
sys.path.append(_os.path.join(_os.path.dirname(__file__), '..'))
from llm_client import chat as _llm_chat

# ── CLIENT NOTION PARTAGÉ ─────────────────────────────────────────────────────
# CORRECTION : cet agent réimplémentait son propre mini-client Notion avec des
# IDs de base codés en dur (DB_HISTORIQUE/DB_PIECES/DB_HSE/DB_EQUIPE) qui ne
# correspondaient plus aux bases [SANDBOX] réelles utilisées par
# `notion_client.py` et par `pages/4_Leila.py` — d'où des données HSE
# manquantes ou incohérentes. On utilise désormais le client Notion partagé,
# comme `agents/agent_lionel.py`.
import notion_client as nc


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
    docs_hse = [{
        "titre":            d.get("titre"),
        "type":             d.get("type"),
        "statut":           d.get("statut"),
        "niveau_risque":    d.get("niveau_risque"),
        "epi_obligatoires": d.get("epi"),        # list
        "persona":          d.get("persona"),    # list
        "resume":           d.get("resume"),
        "lien":             d.get("lien"),
        "date_validation":  d.get("date_validation"),
        "date_revision":    d.get("date_revision"),
    } for d in nc.get_docs_hse(machine_id=equipement)]

    habilitations = [{
        "technicien":    f"{e.get('prenom') or ''} {e.get('nom') or ''}".strip(),
        "habilitations": e.get("habilitations"),   # list
        "disponibilite": e.get("disponibilite"),
        "zone":          e.get("zone"),
    } for e in nc.get_equipe()]

    interventions = [{
        "titre":      i.get("titre"),
        "type":       i.get("type"),
        "date":       i.get("date"),
        "technicien": i.get("technicien"),
        "duree_h":    i.get("duree_estimee"),
    } for i in nc.get_historique(machine_id=equipement, statut="Planifiée")]

    return {
        "docs_hse":                 docs_hse or [{"info": "Aucun document HSE associé"}],
        "nb_docs_hse":              len(docs_hse),
        "habilitations_equipe":     habilitations,
        "interventions_planifiees": interventions or [{"info": "Aucune intervention planifiée"}],
        "norme_loto":               NORMES_LOTO,
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
    conformes, non_conformes = [], []
    for piece in nc.get_pieces(machine_id=equipement):
        ref   = piece.get("reference")
        fourn = piece.get("fournisseur")
        entry = {
            "designation":  piece.get("designation"),
            "reference":    ref,
            "fournisseur":  fourn,
            "statut_stock": piece.get("statut_stock"),
            "conforme":     bool(ref and fourn),
        }
        (conformes if entry["conforme"] else non_conformes).append(entry)

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


# ── FILET DE SÉCURITÉ 1min.ai ─────────────────────────────────────────────────
# llm_client._call_1minai ne détecte un tool_call que si la réponse COMMENCE
# par "{". Le modèle 1min.ai ignore souvent la consigne "réponds UNIQUEMENT
# avec ce JSON" et noie un ou plusieurs appels d'outil dans du texte narratif
# ("Je vais d'abord générer la matrice...\n{"tool_call": ...}"). Dans ce cas
# llm_client renvoie stop_reason="end_turn" avec le JSON brut tel quel, et
# sans ce filet les outils (donc Notion) ne sont jamais exécutés — d'où le
# JSON affiché tel quel dans Streamlit. On retrouve ici chaque bloc
# {"tool_call": {...}} avec un décodeur JSON incrémental (gère les accolades
# imbriquées) pour les exécuter nous-mêmes.
_TOOL_CALL_RE = re.compile(r'\{\s*"tool_call"')


def _extraire_tool_calls_noyes(texte: str) -> list[dict]:
    decoder = json.JSONDecoder()
    appels = []
    for m in _TOOL_CALL_RE.finditer(texte or ""):
        try:
            obj, _ = decoder.raw_decode(texte, m.start())
        except json.JSONDecodeError:
            continue
        tc = obj.get("tool_call", {})
        if tc.get("name"):
            appels.append(tc)
    return appels


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
    max_iterations = 6
    for _ in range(max_iterations):
        resp = _llm_chat(system=SYSTEM, messages=messages, tools=TOOLS, max_tokens=2000)

        if resp.stop_reason == "tool_use":
            appels = [{"name": tc["name"], "arguments": tc["input"], "id": tc.get("id", "tc0")}
                      for tc in resp.tool_calls()]
        elif resp.stop_reason == "end_turn":
            appels = [{"name": tc["name"], "arguments": tc.get("arguments", {}), "id": f"tc_noye_{i}"}
                      for i, tc in enumerate(_extraire_tool_calls_noyes(resp.final_text()))]
            if not appels:
                return resp.final_text()   # vraie réponse finale, aucun outil noyé dedans
        else:
            break

        results = [{
            "type": "tool_result", "tool_use_id": appel["id"],
            "content": json.dumps(_execute(appel["name"], appel["arguments"]), ensure_ascii=False),
        } for appel in appels]
        messages.append({"role": "assistant", "content": resp.content})
        messages.append({"role": "user",      "content": results})

    # Garde-fou : au-delà de max_iterations, on force une synthèse finale sans
    # outils plutôt que de laisser l'app tourner indéfiniment.
    messages.append({
        "role": "user",
        "content": (
            "Tu as maintenant toutes les données nécessaires. Rédige directement "
            "la synthèse finale au format demandé, en texte, sans appeler d'autre "
            "outil et sans réutiliser la syntaxe JSON tool_call."
        ),
    })
    resp = _llm_chat(system=SYSTEM, messages=messages, tools=None, max_tokens=2000)
    return resp.final_text()


# ── TEST STANDALONE ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(run_agent_leila(c_temp=117.0, c_vib=5.8, c_pres=4.6, c_rul=12))
