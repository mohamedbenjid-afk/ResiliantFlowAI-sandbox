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
from p17_context import P17_CONTEXT, prompt_context


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
SYSTEM = f"""Tu es l'assistant de terrain de Lionel, technicien habilité Mécanique/Hydraulique,
sur la Pompe P-17 (Unité B). Tu reçois des relevés capteurs temps réel.

Le RUL est exprimé EN JOURS (source : système prédictif GMAO). RUL faible = panne proche.
Utilise les outils Notion pour confirmer les seuils machine, l'intervention planifiée et le
stock des pièces AVANT de conclure. N'invente jamais de références : utilise le contexte fixe.

{prompt_context()}

Réponds pour un technicien SUR LE TERRAIN (tablette, gants, bruit). Lionel EXÉCUTE et
REND COMPTE ; il ne décide PAS d'arrêter la production ni de basculer sur la pompe de
secours — ces décisions appartiennent à Sophie (manager). Ton rôle : lui donner la
CONSIGNE claire à exécuter en sécurité, et lui dire quand ESCALADER.

RÈGLES DE FORMAT (IMPÉRATIVES) :
- Chaque section commence sur une NOUVELLE LIGNE, par son icône puis son titre en gras.
- Sépare CHAQUE section par une LIGNE VIDE (double retour à la ligne) pour qu'elles
  s'affichent bien l'une SOUS l'autre en Markdown. Ne colle jamais deux sections.
- Le « Mode opératoire » est une liste numérotée, une étape par ligne.

Suis EXACTEMENT cette trame (garde les lignes vides entre les sections) :

📋 **CONSIGNE** — 1 ligne : l'action prescrite à exécuter MAINTENANT (à l'impératif).

🩺 **Pourquoi** — cause probable + preuves chiffrées (valeur mesurée vs seuil).

⏱️ **Fenêtre** — délai avant casse (RUL, en jours) · durée sécurisation · durée réparation.

🦺 **Sécurité** — EPI adaptés au risque détecté + LOTO (disjoncteur, vannes, purge).

🔧 **Mode opératoire** —
1. étape courte à l'impératif (réf + durée)
2. étape suivante
3. …

🔩 **Pièces & magasin** — réf + casier + statut stock (Notion) ; donne un PLAN B si rupture.

🚨 **Escalade** — préviens Sophie AVANT tout arrêt production / si un arbitrage est nécessaire ; transmets-lui le coût d'arrêt ({P17_CONTEXT['cout_arret_eur_h']} €/h) comme élément de décision. Ce n'est PAS à toi de trancher l'arrêt.

🛑 **Limites** — si c'est hors de ton habilitation ou si tu constates un danger imprévu, tu STOPPES et tu escalades.

✅ **Compte-rendu** — critères chiffrés à valider en fin d'intervention (T, vib, P, couple).

Sois direct et concis. Pas de pavés, pas de blabla — mais respecte les lignes vides ci-dessus.
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


# ── BRIEF DU MATIN ────────────────────────────────────────────────────────────

def _fallback_brief(interventions: list, arbitrages: list) -> str:
    chauds = [i for i in interventions if str(i.get("priorite", "")).startswith("P1")]
    out = ["☀️ **Bonjour Lionel** — " + (
        f"{len(interventions)} intervention(s) affectée(s) aujourd'hui."
        if interventions else "aucune intervention affectée pour le moment.")]
    if chauds:
        out += ["", "🔥 **Sujets chauds**"]
        for i in chauds:
            out.append(f"- {i.get('titre','?')} ({i.get('machine','?')}) — à traiter en priorité")
    out += ["", "✅ **À faire aujourd'hui**"]
    for i in interventions:
        out.append(f"- [{i.get('priorite','?')}] {i.get('titre','?')} · {i.get('machine','?')} · ~{i.get('duree_estimee','?')} h")
    out += ["", "🧭 **Arbitrages de Sophie**"]
    out += [f"- {a}" for a in arbitrages] if arbitrages else ["- Priorités fixées par le plan de maintenance (P1 → P4)."]
    out += ["", "▶️ **Par où commencer** — traite d'abord les P1, puis P2/P3. Escalade à Sophie avant tout arrêt production."]
    return "\n".join(out)


def resumer_journee_lionel(interventions: list, arbitrages: list | None = None) -> str:
    """Brief matinal de Lionel à partir de ses interventions affectées (+ arbitrages
    Sophie). Utilise le LLM ; repli déterministe si indisponible."""
    arbitrages = arbitrages or []
    lignes = [
        f"- [{i.get('priorite','?')}] {i.get('titre','?')} · {i.get('machine','?')} · "
        f"{i.get('type','?')} · statut {i.get('statut','?')} · ~{i.get('duree_estimee','?')} h · "
        f"{'avec LOTO' if str(i.get('loto_requis','')).lower().startswith('o') else 'sans LOTO'}"
        for i in interventions
    ]
    arb_txt = "\n".join(f"- {a}" for a in arbitrages) if arbitrages else "- (aucun arbitrage transmis)"
    situation = (
        "Tu rédiges le BRIEF DU MATIN de Lionel, technicien de terrain. Il EXÉCUTE et rend "
        "compte ; il ne décide pas d'arrêter la production (ça, c'est Sophie).\n\n"
        "Interventions qui lui sont affectées aujourd'hui :\n" + "\n".join(lignes) + "\n\n"
        f"Arbitrages transmis par Sophie (manager) :\n{arb_txt}\n\n"
        "Rédige un brief COURT et scannable, en Markdown, avec une LIGNE VIDE entre chaque "
        "section (sinon ça se colle) :\n\n"
        "☀️ **Bonjour Lionel** — 1 phrase sur la charge du jour.\n\n"
        "🔥 **Sujets chauds** — les P1 / critiques à traiter en priorité.\n\n"
        "✅ **À faire aujourd'hui** — liste ordonnée par priorité (titre · machine · durée).\n\n"
        "🧭 **Arbitrages de Sophie** — ce que la manager a décidé / priorisé.\n\n"
        "▶️ **Par où commencer** — 1 recommandation. Rappelle d'escalader à Sophie avant tout arrêt production."
    )
    try:
        resp = _llm_chat(
            system="Tu es l'assistant de terrain de Lionel. Concis, factuel, orienté exécution.",
            messages=[{"role": "user", "content": situation}], tools=[], max_tokens=900,
        )
        txt = resp.final_text()
        if txt and len(txt.strip()) > 20:
            return txt
    except Exception:
        pass
    return _fallback_brief(interventions, arbitrages)


# ── TEST STANDALONE ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Scénario surchauffe critique : 82 °C, 3.5 mm/s, RUL 1 jour
    print(run_agent_lionel(c_temp=82.0, c_vib=3.5, c_pres=4.4, c_rul=1))
