"""
agents/agent_antoine.py — Agent stratégique d'Antoine (Directeur Technique)
Rôle : analyser les tendances de fiabilité, calculer le ROI de la maintenance
       prescriptive, modéliser les décisions CAPEX vs OPEX.

Améliorations v2 :
  - MTBF / MTTR calculés depuis l'historique réel
  - Vue portfolio multi-machine avec ranking par risque
  - Simulation 3 scénarios NPV (correctif / prescriptif / remplacement)
  - run_agent_antoine() retourne un dict avec données brutes pour le PDF CODIR
"""

import os, json
from datetime import datetime
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


# ── CLIENT NOTION ─────────────────────────────────────────────────────────────
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
        if cursor: payload["start_cursor"] = cursor
        resp = _requests.post(url, headers=headers, json=payload, timeout=15)
        if not resp.ok: return []
        data = resp.json()
        results.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        cursor   = data.get("next_cursor")
    return results


# ── IDs Notion ────────────────────────────────────────────────────────────────
DB_MACHINES   = "5279cb2a42b54b42936e22313521f825"
DB_ORDRES_FAB = "d7ee45dab07943c1bda09a6b47089202"
DB_HISTORIQUE = "6f53558bfbee455891efa53b6536d892"
DB_PIECES     = "c22138baa8ca4806b19403108735bc68"


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

def _num(prop) -> float:
    v = _text(prop)
    try:    return float(v)
    except: return 0.0

def _p(page): return page.get("properties", {})


# ── OUTIL 1 : bilan équipement ────────────────────────────────────────────────
def get_bilan_equipement(nom: str) -> dict:
    """État de dégradation et données de fiabilité pour évaluer un remplacement CAPEX."""
    res = _notion_query(DB_MACHINES,
        filter_obj={"property": "Nom Machine", "title": {"contains": nom}})
    if not res:
        return {"erreur": f"'{nom}' non trouvé dans la base machines"}
    p = _p(res[0])
    score_deg = _num(p.get("Score dégradation (%)"))
    return {
        "machine":               _text(p.get("Nom Machine")),
        "id_machine":            _text(p.get("ID Machine")),
        "type":                  _text(p.get("Type")),
        "statut":                _text(p.get("Statut")),
        "rul_jours":             _num(p.get("RUL (jours)")),
        "score_degradation_pct": score_deg,
        "vie_restante_pct":      round(100 - score_deg, 1),
        "temperature_actuelle":  _num(p.get("Température actuelle (°C)")),
        "vibration_actuelle":    _num(p.get("Vibration actuelle (mm/s)")),
        "seuil_temp":            _num(p.get("Seuil température (°C)")),
        "seuil_vib":             _num(p.get("Seuil vibration (mm/s)")),
        "unite":                 _text(p.get("Unité / Zone")),
        "responsable":           _text(p.get("Responsable")),
        "derniere_inspection":   _text(p.get("Dernière inspection")),
        "prochaine_maintenance": _text(p.get("Prochaine maintenance")),
        "notes_ia":              _text(p.get("Notes IA")),
    }


# ── OUTIL 2 : historique coûts + MTBF/MTTR ────────────────────────────────────
def get_historique_couts_maintenance(equipement: str) -> dict:
    """Coûts cumulés, ROI prescriptif, MTBF et MTTR calculés depuis l'historique réel."""
    res = _notion_query(DB_HISTORIQUE,
        filter_obj={"property": "Machine", "rich_text": {"contains": equipement}},
        sorts=[{"property": "Date intervention", "direction": "ascending"}])

    toutes, pannes, prescriptives = [], [], []
    cout_total, cout_arrets = 0.0, 0.0
    durees_pannes, dates_pannes = [], []

    for page in res:
        p      = _p(page)
        statut = _text(p.get("Statut"))
        type_  = _text(p.get("Type"))
        cout   = _num(p.get("Coût intervention (€)"))
        arret  = _num(p.get("Coût arrêt production (€)"))
        duree_r= _num(p.get("Durée réelle (h)"))
        date_i = _text(p.get("Date intervention"))

        entry = {
            "titre":           _text(p.get("Titre intervention")),
            "type":            type_,
            "statut":          statut,
            "date":            date_i,
            "duree_estimee_h": _num(p.get("Durée estimée (h)")),
            "duree_reelle_h":  duree_r,
            "cout_eur":        cout,
            "cout_arret_eur":  arret,
            "rul_avant":       _num(p.get("RUL avant intervention (j)")),
            "rul_apres":       _num(p.get("RUL après intervention (j)")),
            "cause_racine":    _text(p.get("Cause racine")),
        }
        toutes.append(entry)

        if statut == "Terminée":
            cout_total  += cout
            cout_arrets += arret
            if type_ == "Panne corrective":
                pannes.append(entry)
                if duree_r > 0: durees_pannes.append(duree_r)
                if date_i:      dates_pannes.append(date_i)
            if type_ == "Maintenance prescriptive":
                prescriptives.append(entry)

    # MTBF
    mtbf_jours = None
    if len(dates_pannes) >= 2:
        try:
            dts    = sorted([datetime.strptime(d, "%Y-%m-%d") for d in dates_pannes])
            deltas = [(dts[i+1] - dts[i]).days for i in range(len(dts)-1)]
            mtbf_jours = round(sum(deltas) / len(deltas), 1)
        except Exception:
            pass

    # MTTR
    mttr_heures = round(sum(durees_pannes) / len(durees_pannes), 1) if durees_pannes else None

    # ROI
    roi = round(cout_arrets / cout_total, 1) if cout_total > 0 else 0

    # Tendance coûts pannes
    tendance_cout = None
    if len(pannes) >= 4:
        debut = sum(p["cout_eur"] for p in pannes[:2]) / 2
        fin   = sum(p["cout_eur"] for p in pannes[-2:]) / 2
        tendance_cout = round((fin - debut) / debut * 100, 1) if debut else None

    return {
        "nb_interventions":           len(toutes),
        "nb_pannes_correctives":      len(pannes),
        "nb_prescriptives":           len(prescriptives),
        "cout_total_maintenance_eur": round(cout_total, 2),
        "couts_arrets_evites_eur":    round(cout_arrets, 2),
        "roi_maintenance":            roi,
        "mtbf_jours":                 mtbf_jours,
        "mttr_heures":                mttr_heures,
        "tendance_cout_pct":          tendance_cout,
        "detail_interventions":       toutes,
    }


# ── OUTIL 3 : exposition financière production ────────────────────────────────
def get_exposition_financiere_production(equipement: str) -> dict:
    """Coût d'exposition totale si la machine tombe en panne non planifiée."""
    res = _notion_query(DB_ORDRES_FAB,
        filter_obj={"property": "Machine impactée", "rich_text": {"contains": equipement}})
    exposition_totale = 0.0
    details = []
    for page in res:
        p    = _p(page)
        cout = _num(p.get("Coût arrêt (€)"))
        exposition_totale += cout
        details.append({
            "reference":      _text(p.get("Référence OF")),
            "statut":         _text(p.get("Statut OF")),
            "cout_arret_eur": cout,
            "duree_arret_h":  _num(p.get("Durée arrêt (h)")),
        })
    return {
        "exposition_financiere_totale_eur": round(exposition_totale, 2),
        "nb_of_impactes": len(details),
        "of_impactes":    details,
    }


# ── OUTIL 4 : stock stratégique ───────────────────────────────────────────────
def get_etat_stock_strategique(equipement: str) -> dict:
    """Valeur immobilisée en stock + pièces critiques — vision trésorerie."""
    res = _notion_query(DB_PIECES,
        filter_obj={"property": "Machine concernée", "rich_text": {"contains": equipement}})
    valeur_stock = 0.0
    pieces = []
    for page in res:
        p      = _p(page)
        stock  = _num(p.get("Stock actuel"))
        prix   = _num(p.get("Prix unitaire (€)"))
        valeur = round(stock * prix, 2)
        statut = _text(p.get("Statut stock"))
        valeur_stock += valeur
        pieces.append({
            "designation":        _text(p.get("Désignation pièce")),
            "reference":          _text(p.get("Référence")),
            "stock":              stock,
            "prix_unitaire":      prix,
            "valeur_immobilisee": valeur,
            "statut_stock":       statut,
            "delai_livraison":    _num(p.get("Délai livraison (j)")),
        })
    return {
        "valeur_stock_immobilisee_eur": round(valeur_stock, 2),
        "nb_references":     len(pieces),
        "pieces_en_rupture": [p for p in pieces if p["statut_stock"] == "Rupture"],
        "pieces_alerte":     [p for p in pieces if "Alerte" in p.get("statut_stock", "")],
        "detail_stock":      pieces,
    }


# ── OUTIL 5 : portfolio multi-machine ─────────────────────────────────────────
def get_top_equipements_a_risque() -> dict:
    """
    Vue portfolio DT : toutes les machines classées par score de risque combiné
    (RUL, dégradation, dépassements seuils, statut).
    """
    machines = _notion_query(DB_MACHINES)
    ranking  = []

    for m in machines:
        p           = _p(m)
        nom         = _text(p.get("Nom Machine"))
        rul         = _num(p.get("RUL (jours)")) or 999
        deg         = _num(p.get("Score dégradation (%)"))
        statut      = _text(p.get("Statut"))
        temp        = _num(p.get("Température actuelle (°C)"))
        seuil_temp  = _num(p.get("Seuil température (°C)")) or 9999
        vib         = _num(p.get("Vibration actuelle (mm/s)"))
        seuil_vib   = _num(p.get("Seuil vibration (mm/s)")) or 9999

        rul_score    = max(0, min(100, (1 - rul / 180) * 100)) if rul < 180 else 0
        seuil_score  = (50 if temp > seuil_temp else 0) + (50 if vib > seuil_vib else 0)
        statut_score = {"Alerte critique": 100, "En maintenance": 60,
                        "Arrêtée": 80, "En service": 0}.get(statut, 0)

        risque = round(0.40 * rul_score + 0.35 * deg + 0.15 * seuil_score + 0.10 * statut_score, 1)
        niveau = ("🔴 CRITIQUE" if risque >= 70 else
                  "🟠 ÉLEVÉ"   if risque >= 45 else
                  "🟡 MODÉRÉ"  if risque >= 25 else "🟢 FAIBLE")

        ranking.append({
            "machine":               nom,
            "id_machine":            _text(p.get("ID Machine")),
            "unite":                 _text(p.get("Unité / Zone")),
            "responsable":           _text(p.get("Responsable")),
            "statut":                statut,
            "rul_jours":             rul if rul < 999 else 0,
            "score_degradation_pct": deg,
            "score_risque":          risque,
            "niveau_risque":         niveau,
            "depassement_temp":      temp > seuil_temp,
            "depassement_vib":       vib > seuil_vib,
        })

    ranking.sort(key=lambda x: x["score_risque"], reverse=True)
    return {
        "nb_machines":  len(ranking),
        "nb_critiques": sum(1 for m in ranking if "CRITIQUE" in m["niveau_risque"]),
        "nb_eleves":    sum(1 for m in ranking if "ÉLEVÉ"    in m["niveau_risque"]),
        "nb_nominaux":  sum(1 for m in ranking if "FAIBLE"   in m["niveau_risque"]),
        "ranking":      ranking,
        "priorite_1":   ranking[0] if ranking else None,
    }


# ── OUTIL 6 : simulation 3 scénarios NPV ─────────────────────────────────────
def simuler_scenarios_investissement(
    equipement: str,
    cout_remplacement_eur: float = 85000,
    horizon_ans: int = 3,
    taux_actualisation: float = 0.05,
) -> dict:
    """
    Scénario A — Correctif pur : pannes au rythme historique, coûts croissants
    Scénario B — Maintien prescriptif : approche ResilientFlow actuelle
    Scénario C — Remplacement maintenant : CAPEX immédiat + maintenance résiduelle faible
    """
    hist  = get_historique_couts_maintenance(equipement)
    bilan = get_bilan_equipement(equipement)

    pannes = [i for i in hist["detail_interventions"]
              if i["type"] == "Panne corrective" and i["statut"] == "Terminée"]
    presc  = [i for i in hist["detail_interventions"]
              if i["type"] == "Maintenance prescriptive" and i["statut"] == "Terminée"]

    cout_panne_moyen = (
        sum(p["cout_eur"] + p["cout_arret_eur"] for p in pannes) / len(pannes)
        if pannes else 25000
    )
    cout_prescriptif_annuel = (
        sum(p["cout_eur"] for p in presc) if presc else 3500
    )

    mtbf         = hist.get("mtbf_jours") or 180
    pannes_par_an_correctif   = round(365 / mtbf, 2)
    pannes_par_an_prescriptif = round(pannes_par_an_correctif * 0.20, 2)

    deg              = bilan.get("score_degradation_pct", 50) if isinstance(bilan, dict) else 50
    facteur_escalade = 1 + (deg / 100) * 0.30

    def npv(cashflows):
        return sum(cf / (1 + taux_actualisation) ** t for t, cf in enumerate(cashflows, 1))

    cf_a = [-pannes_par_an_correctif * cout_panne_moyen * (facteur_escalade ** y)
            for y in range(1, horizon_ans + 1)]
    cf_b = [-(cout_prescriptif_annuel * (1.03 ** y) + pannes_par_an_prescriptif * cout_panne_moyen)
            for y in range(1, horizon_ans + 1)]
    cf_c = [-cout_remplacement_eur] + [-1500] * horizon_ans

    npv_a = npv(cf_a)
    npv_b = npv(cf_b)
    npv_c = cf_c[0] + npv(cf_c[1:])

    cout_total_a = -sum(cf_a)
    cout_total_b = -sum(cf_b)
    cout_total_c = -sum(cf_c)

    meilleur = max(
        [("B — Maintien prescriptif", npv_b),
         ("C — Remplacement",         npv_c),
         ("A — Correctif pur",        npv_a)],
        key=lambda x: x[1]
    )[0]

    eco_annuelle = (cout_total_a - cout_total_c) / horizon_ans
    payback_mois = round((cout_remplacement_eur / eco_annuelle) * 12, 1) if eco_annuelle > 0 else None

    return {
        "equipement":    equipement,
        "horizon_ans":   horizon_ans,
        "hypotheses": {
            "cout_panne_moyen_eur":           round(cout_panne_moyen, 0),
            "pannes_par_an_sans_prescriptif": pannes_par_an_correctif,
            "pannes_par_an_avec_prescriptif": pannes_par_an_prescriptif,
            "cout_prescriptif_annuel_eur":    round(cout_prescriptif_annuel, 0),
            "cout_remplacement_eur":          cout_remplacement_eur,
        },
        "scenarios": {
            "A_correctif_pur": {
                "description":             "Arrêt prescriptif — pannes au rythme historique",
                "cashflows_annuels_eur":   [round(c, 0) for c in cf_a],
                "cout_total_eur":          round(cout_total_a, 0),
                "npv_eur":                 round(npv_a, 0),
            },
            "B_maintien_prescriptif": {
                "description":             "Continuité ResilientFlow AI — réduction pannes 80%",
                "cashflows_annuels_eur":   [round(c, 0) for c in cf_b],
                "cout_total_eur":          round(cout_total_b, 0),
                "npv_eur":                 round(npv_b, 0),
            },
            "C_remplacement": {
                "description":             f"Remplacement immédiat — CAPEX {cout_remplacement_eur:,.0f} €",
                "cashflows_annuels_eur":   [round(c, 0) for c in cf_c],
                "cout_total_eur":          round(cout_total_c, 0),
                "npv_eur":                 round(npv_c, 0),
                "payback_vs_correctif_mois": payback_mois,
            },
        },
        "recommandation_financiere":               meilleur,
        "economie_prescriptif_vs_correctif_eur":  round(cout_total_a - cout_total_b, 0),
    }


# ── DÉCLARATION DES OUTILS ────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "get_bilan_equipement",
        "description": "Bilan de vie : RUL, score dégradation, vie restante, seuils.",
        "input_schema": {"type": "object", "properties": {"nom": {"type": "string"}}, "required": ["nom"]}
    },
    {
        "name": "get_historique_couts_maintenance",
        "description": "Coûts cumulés, ROI prescriptif, MTBF et MTTR depuis l'historique réel.",
        "input_schema": {"type": "object", "properties": {"equipement": {"type": "string"}}, "required": ["equipement"]}
    },
    {
        "name": "get_exposition_financiere_production",
        "description": "Exposition financière totale en cas de panne non planifiée (ordres de fab actifs).",
        "input_schema": {"type": "object", "properties": {"equipement": {"type": "string"}}, "required": ["equipement"]}
    },
    {
        "name": "get_etat_stock_strategique",
        "description": "Valeur stock immobilisée, ruptures, délais fournisseur.",
        "input_schema": {"type": "object", "properties": {"equipement": {"type": "string"}}, "required": ["equipement"]}
    },
    {
        "name": "get_top_equipements_a_risque",
        "description": "Portfolio DT : toutes les machines classées par score de risque combiné pour arbitrage budgétaire CODIR.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "simuler_scenarios_investissement",
        "description": "Simule 3 scénarios sur 3 ans avec NPV : A) correctif pur, B) maintien prescriptif, C) remplacement. Calcule point mort et recommandation optimale.",
        "input_schema": {
            "type": "object",
            "properties": {
                "equipement":            {"type": "string"},
                "cout_remplacement_eur": {"type": "number"},
                "horizon_ans":           {"type": "integer"},
            },
            "required": ["equipement"]
        }
    },
]


def _execute(name, inputs):
    if name == "get_bilan_equipement":                 return get_bilan_equipement(inputs["nom"])
    if name == "get_historique_couts_maintenance":     return get_historique_couts_maintenance(inputs["equipement"])
    if name == "get_exposition_financiere_production": return get_exposition_financiere_production(inputs["equipement"])
    if name == "get_etat_stock_strategique":           return get_etat_stock_strategique(inputs["equipement"])
    if name == "get_top_equipements_a_risque":         return get_top_equipements_a_risque()
    if name == "simuler_scenarios_investissement":
        return simuler_scenarios_investissement(
            equipement=inputs["equipement"],
            cout_remplacement_eur=inputs.get("cout_remplacement_eur", 85000),
            horizon_ans=inputs.get("horizon_ans", 3),
        )
    return {"erreur": f"Outil inconnu : {name}"}


# ── PROMPT SYSTÈME ─────────────────────────────────────────────────────────────
SYSTEM = """Tu es l'assistant stratégique d'Antoine, Directeur Technique.
Tu analyses des données de fiabilité industrielle pour l'aider à prendre
des décisions d'investissement et de politique de maintenance.

Format de réponse strict (Markdown) :
1. **Synthèse exécutive** — 3 lignes max, chiffres clés (MTBF, ROI, RUL)
2. **Vue portfolio** — ranking des machines par score de risque
3. **Analyse OPEX** — coûts cumulés, MTBF/MTTR, tendance
4. **Simulation scénarios** — tableau comparatif A/B/C avec coût total et NPV
5. **Exposition au risque** — perte estimée en cas de panne non maîtrisée
6. **Recommandation CODIR** — une seule décision chiffrée, clairement formulée

Sois synthétique et chiffré. Antoine parle au CODIR. Jamais plus de 3 niveaux de bullet.
"""


# ── FONCTION PRINCIPALE ────────────────────────────────────────────────────────
def run_agent_antoine(equipement: str = "Pompe P-17", c_rul: int = None) -> dict:
    """
    Lance l'agent Antoine.

    Stratégie : pré-fetch de toutes les données en Python, puis
    UN SEUL appel LLM pour rédiger l'analyse. Compatible 1min.ai et Anthropic.

    Retourne un dict :
      analyse    : texte Markdown LLM
      scenarios  : dict brut 3 scénarios NPV (pour PDF CODIR)
      portfolio  : ranking machines (pour PDF CODIR)
      bilan      : bilan équipement
      historique : KPIs MTBF/MTTR/ROI
    """
    # ── 1. Pré-fetch toutes les données directement ───────────────────────────
    raw_portfolio  = get_top_equipements_a_risque()
    raw_bilan      = get_bilan_equipement(equipement)
    raw_historique = get_historique_couts_maintenance(equipement)
    raw_exposition = get_exposition_financiere_production(equipement)
    raw_stock      = get_etat_stock_strategique(equipement)
    raw_scenarios  = simuler_scenarios_investissement(equipement)

    # ── 2. Construire le contexte complet pour le LLM ─────────────────────────
    rul_info = f" | RUL capteur : {c_rul}j" if c_rul else ""

    sc      = raw_scenarios.get("scenarios", {})
    a_cout  = sc.get("A_correctif_pur",       {}).get("cout_total_eur", 0)
    b_cout  = sc.get("B_maintien_prescriptif",{}).get("cout_total_eur", 0)
    c_cout  = sc.get("C_remplacement",         {}).get("cout_total_eur", 0)
    a_npv   = sc.get("A_correctif_pur",       {}).get("npv_eur", 0)
    b_npv   = sc.get("B_maintien_prescriptif",{}).get("npv_eur", 0)
    c_npv   = sc.get("C_remplacement",         {}).get("npv_eur", 0)
    payback = sc.get("C_remplacement",         {}).get("payback_vs_correctif_mois")
    reco    = raw_scenarios.get("recommandation_financiere", "—")
    eco     = raw_scenarios.get("economie_prescriptif_vs_correctif_eur", 0)

    portfolio_lines = "\n".join(
        f"  - {m['machine']} ({m['unite']}) : RUL={m['rul_jours']}j, "
        f"dégradation={m['score_degradation_pct']}%, risque={m['score_risque']}/100 {m['niveau_risque']}"
        for m in raw_portfolio.get("ranking", [])
    )

    hist = raw_historique
    contexte = f"""
DONNÉES D'ANALYSE — {equipement}{rul_info}

## PORTFOLIO ({raw_portfolio.get('nb_machines', 0)} machines)
{portfolio_lines or "Aucune machine disponible."}

## BILAN ÉQUIPEMENT {equipement}
- Statut : {raw_bilan.get('statut', '—')} | Unité : {raw_bilan.get('unite', '—')}
- RUL : {raw_bilan.get('rul_jours', '—')} j | Dégradation : {raw_bilan.get('score_degradation_pct', '—')} %
- Température : {raw_bilan.get('temperature_actuelle', '—')} °C (seuil {raw_bilan.get('seuil_temp', '—')} °C)
- Vibration : {raw_bilan.get('vibration_actuelle', '—')} mm/s (seuil {raw_bilan.get('seuil_vib', '—')} mm/s)

## HISTORIQUE MAINTENANCE
- {hist.get('nb_interventions', 0)} interventions dont {hist.get('nb_pannes_correctives', 0)} pannes correctives
- MTBF : {hist.get('mtbf_jours', '—')} j | MTTR : {hist.get('mttr_heures', '—')} h
- OPEX cumulé : {hist.get('cout_total_maintenance_eur', 0):,.0f} €
- Arrêts évités par prescriptif : {hist.get('couts_arrets_evites_eur', 0):,.0f} €
- ROI prescriptif : × {hist.get('roi_maintenance', '—')}

## EXPOSITION FINANCIÈRE PRODUCTION
- Exposition si panne non planifiée : {raw_exposition.get('exposition_financiere_totale_eur', 0):,.0f} €
- Ordres de fabrication impactés : {raw_exposition.get('nb_of_impactes', 0)}

## STOCK PIÈCES DÉTACHÉES
- Valeur immobilisée : {raw_stock.get('valeur_stock_immobilisee_eur', 0):,.0f} €
- Pièces en rupture : {len(raw_stock.get('pieces_en_rupture', []))} | En alerte : {len(raw_stock.get('pieces_alerte', []))}

## SIMULATION 3 SCÉNARIOS (horizon {raw_scenarios.get('horizon_ans', 3)} ans)
| Scénario | Coût total | NPV |
|---|---|---|
| A — Correctif pur | {a_cout:,.0f} € | {a_npv:,.0f} € |
| B — Maintien prescriptif | {b_cout:,.0f} € | {b_npv:,.0f} € |
| C — Remplacement ({raw_scenarios.get('hypotheses', {}).get('cout_remplacement_eur', 85000):,.0f} €) | {c_cout:,.0f} € | {c_npv:,.0f} € |
Point mort C vs A : {payback} mois | Économie B vs A : {eco:,.0f} €
Recommandation financière : {reco}
"""

    messages = [{"role": "user", "content": contexte}]

    # ── 3. Un seul appel LLM pour rédiger l'analyse ───────────────────────────
    resp    = _llm_chat(system=SYSTEM, messages=messages, max_tokens=2500)
    analyse = resp.final_text()

    return {
        "analyse":    analyse,
        "scenarios":  raw_scenarios,
        "portfolio":  raw_portfolio,
        "bilan":      raw_bilan,
        "historique": raw_historique,
    }


# ── TEST STANDALONE ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    result = run_agent_antoine(equipement="Pompe P-17", c_rul=18)
    print(result["analyse"])
