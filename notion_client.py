# notion_client.py
# Connexion live aux 6 bases Notion ESCP — ResilientFlow AI
# Schémas mis à jour pour correspondre aux vraies bases ESCP

import re
import requests
import streamlit as st
import os

# ── CONFIG ────────────────────────────────────────────────────────────────────
NOTION_VERSION = "2022-06-28"
NOTION_BASE_URL = "https://api.notion.com/v1"

# IDs des 6 bases de données Notion (compte ESCP)
DB_IDS = {
    "machines":   "6653da63-bd5a-4191-815c-576b8c7fcfbc",   # 🏭 Équipements
    "equipe":     "3856b2ff-be3d-8151-8b3f-ee79dee0bc2b",   # 👷 Équipe Maintenance RH
    "pieces":     "ef896795-bd1a-4b20-a8ea-f121c9f846ff",   # 📦 Stock Composants
    "ordres_fab": "687e40c2-a3ff-4de0-be55-20cf411f5dd6",   # 📋 Ordres de Fabrication
    "historique": "94babab5-03bb-4c4d-9053-08d5bff301e3",   # 🔩 Plan de Maintenance
    "hse_docs":   "3856b2ff-be3d-816f-a163-ef4f8e43499d",   # 📚 Documentation & HSE
}


def _get_token() -> str:
    try:
        return st.secrets["NOTION_TOKEN"]
    except Exception:
        return os.environ.get("NOTION_TOKEN", "")


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_get_token()}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _query_db(db_id: str, filter_payload: dict = None, sorts: list = None) -> list:
    """Interroge une base Notion avec pagination automatique."""
    url = f"{NOTION_BASE_URL}/databases/{db_id}/query"
    body = {}
    if filter_payload:
        body["filter"] = filter_payload
    if sorts:
        body["sorts"] = sorts

    results, has_more, next_cursor = [], True, None
    while has_more:
        if next_cursor:
            body["start_cursor"] = next_cursor
        resp = requests.post(url, headers=_headers(), json=body, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        results.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")
    return results


def _prop(page: dict, name: str):
    """Extrait la valeur typée d'une propriété Notion."""
    p = page.get("properties", {}).get(name, {})
    t = p.get("type", "")
    if t == "title":
        return "".join(r.get("plain_text", "") for r in p.get("title", []))
    if t == "rich_text":
        return "".join(r.get("plain_text", "") for r in p.get("rich_text", []))
    if t == "number":
        return p.get("number")
    if t == "select":
        s = p.get("select")
        return s["name"] if s else None
    if t == "multi_select":
        return [s["name"] for s in p.get("multi_select", [])]
    if t == "date":
        d = p.get("date")
        return d["start"] if d else None
    if t == "url":
        return p.get("url")
    if t == "checkbox":
        return p.get("checkbox")
    return None


# ── 1. MACHINES / ÉQUIPEMENTS ────────────────────────────────────────────────
# Base ESCP : titre = "Équipement"
# Champs : Statut, Type, Ligne de production, Seuil Température (°C),
#          Seuil Vibration (mm/s), Seuil Pression (bar), RUL nominal (h),
#          Modèle, Fabricant, N° de série, Technicien référent, Notes,
#          Heures de fonctionnement total, Date de mise en service,
#          Documentation technique

def _extract_code(nom: str) -> str:
    """Extrait le code machine (ex: 'P-17') depuis un titre comme 'Pompe P-17'."""
    if not nom:
        return nom
    m = re.search(r'\b([A-Z]+-\d+)\b', nom)
    return m.group(1) if m else nom


@st.cache_data(ttl=30)
def get_machines(statut: str = None) -> list[dict]:
    """Toutes les machines, filtre optionnel par statut. Déduplique par code machine."""
    f = {"property": "Statut", "select": {"equals": statut}} if statut else None
    pages = _query_db(DB_IDS["machines"], f)
    raw = [_parse_machine(p) for p in pages]
    # Déduplication : garder une seule entrée par code machine (ex: P-17)
    # Priorité à l'entrée avec le RUL le plus bas (la plus critique)
    seen: dict[str, dict] = {}
    for m in raw:
        code = _extract_code(m["nom"])
        m["id"] = code  # normalise l'ID
        if code not in seen:
            seen[code] = m
        else:
            # Garder l'entrée avec le RUL le plus bas (plus critique)
            rul_existing = seen[code].get("rul_jours") or 9999
            rul_new = m.get("rul_jours") or 9999
            if rul_new < rul_existing:
                seen[code] = m
    return list(seen.values())


@st.cache_data(ttl=30)
def get_machine(machine_id: str) -> dict | None:
    """Machine par son code (ex: 'P-17'). Cherche dans le champ titre 'Équipement'."""
    pages = _query_db(
        DB_IDS["machines"],
        {"property": "Équipement", "title": {"contains": machine_id}}
    )
    if not pages:
        return None
    m = _parse_machine(pages[0])
    m["id"] = _extract_code(m["nom"])
    return m


def _parse_machine(p: dict) -> dict:
    nom = _prop(p, "Équipement") or ""
    return {
        "id":              _extract_code(nom),
        "nom":             nom,
        "type":            _prop(p, "Type"),
        "statut":          _prop(p, "Statut"),
        "rul_nominal_h":   _prop(p, "RUL nominal (h)"),
        # Convertir heures en jours pour compatibilité avec le reste de l'app
        "rul_jours":       round(_prop(p, "RUL nominal (h)") / 24, 1)
                           if _prop(p, "RUL nominal (h)") else None,
        "seuil_temp":      _prop(p, "Seuil Température (°C)"),
        "seuil_vib":       _prop(p, "Seuil Vibration (mm/s)"),
        "seuil_pression":  _prop(p, "Seuil Pression (bar)"),
        "modele":          _prop(p, "Modèle"),
        "fabricant":       _prop(p, "Fabricant"),
        "numero_serie":    _prop(p, "N° de série"),
        "responsable":     _prop(p, "Technicien référent"),
        "notes":           _prop(p, "Notes"),
        "heures_total":    _prop(p, "Heures de fonctionnement total"),
        "unite":           _prop(p, "Ligne de production"),
        "date_mise_service": _prop(p, "Date de mise en service"),
        "doc_technique":   _prop(p, "Documentation technique"),
        # Champs calculés / simulés (pas dans Notion ESCP — valeurs nulles par défaut)
        "temperature":     None,
        "vibration":       None,
        "score_degradation": None,
        "notes_ia":        None,
        "derniere_inspection": None,
        "prochaine_maintenance": None,
    }


# ── 2. ÉQUIPE MAINTENANCE ─────────────────────────────────────────────────────
# Base ESCP : titre = "Nom Technicien"
# Champs : Prénom, Rôle, Disponibilité, Habilitations, Zone assignée,
#          Spécialité, Heures restantes, Charge horaire (h/sem),
#          Téléphone, Certifications, Notes, Date prise de poste

@st.cache_data(ttl=60)
def get_equipe(disponibilite: str = None) -> list[dict]:
    """Équipe maintenance. Filtre optionnel par disponibilité."""
    f = {"property": "Disponibilité", "select": {"equals": disponibilite}} if disponibilite else None
    pages = _query_db(DB_IDS["equipe"], f)
    return [{
        "nom":              _prop(p, "Nom Technicien"),
        "prenom":           _prop(p, "Prénom"),
        "role":             _prop(p, "Rôle"),
        "specialite":       _prop(p, "Spécialité"),
        "habilitations":    _prop(p, "Habilitations"),       # list
        "disponibilite":    _prop(p, "Disponibilité"),
        "charge_horaire":   _prop(p, "Charge horaire (h/sem)"),
        "heures_restantes": _prop(p, "Heures restantes"),
        "zone":             _prop(p, "Zone assignée"),
        "certifications":   _prop(p, "Certifications"),
        "telephone":        _prop(p, "Téléphone"),
        "notes":            _prop(p, "Notes"),
        "date_poste":       _prop(p, "Date prise de poste"),
    } for p in pages]


# ── 3. PIÈCES DÉTACHÉES / STOCK COMPOSANTS ────────────────────────────────────
# Base ESCP : titre = "Composant"
# Champs : Statut stock, Catégorie, Critique, Stock actuel,
#          Stock minimum (seuil alerte), Stock maximum, Prix unitaire (€),
#          Délai réappro (jours), Fournisseur principal, Réf. fabricant,
#          Emplacement magasin, Équipements compatibles, Notes, Unité,
#          Date dernière commande

@st.cache_data(ttl=60)
def get_pieces(machine_id: str = None, statut_stock: str = None) -> list[dict]:
    """Pièces détachées. Filtres optionnels par machine et/ou statut stock."""
    filters = []
    if machine_id:
        # Le champ est "Équipements compatibles" (texte libre)
        filters.append({"property": "Équipements compatibles",
                         "rich_text": {"contains": machine_id}})
    if statut_stock:
        filters.append({"property": "Statut stock", "select": {"equals": statut_stock}})

    f = None if not filters else (filters[0] if len(filters) == 1 else {"and": filters})
    pages = _query_db(DB_IDS["pieces"], f)
    return [{
        "designation":     _prop(p, "Composant"),            # titre
        "reference":       _prop(p, "Réf. fabricant"),
        "categorie":       _prop(p, "Catégorie"),
        "machine":         _prop(p, "Équipements compatibles"),
        "emplacement":     _prop(p, "Emplacement magasin"),
        "stock_actuel":    _prop(p, "Stock actuel"),
        "stock_minimum":   _prop(p, "Stock minimum (seuil alerte)"),
        "stock_maximum":   _prop(p, "Stock maximum"),
        "statut_stock":    _prop(p, "Statut stock"),
        "critique":        _prop(p, "Critique"),
        "prix_unitaire":   _prop(p, "Prix unitaire (€)"),
        "fournisseur":     _prop(p, "Fournisseur principal"),
        "delai_livraison": _prop(p, "Délai réappro (jours)"),
        "unite":           _prop(p, "Unité"),
        "notes":           _prop(p, "Notes"),
        "date_commande":   _prop(p, "Date dernière commande"),
    } for p in pages]


# ── 4. ORDRES DE FABRICATION ──────────────────────────────────────────────────
# Base ESCP : titre = "Ordre de Fabrication"
# Champs : Statut, Ligne de production, Équipement concerné, Produit fabriqué,
#          Responsable OF, Notes, Quantité cible, Quantité réalisée,
#          Coût arrêt horaire (€), Date début, Date fin prévue,
#          Ligne de secours disponible

@st.cache_data(ttl=30)
def get_ordres_fabrication(statut: str = None, machine_id: str = None) -> list[dict]:
    """Ordres de fabrication. Filtres optionnels par statut et machine."""
    filters = []
    if statut:
        filters.append({"property": "Statut", "select": {"equals": statut}})
    if machine_id:
        filters.append({"property": "Équipement concerné",
                         "rich_text": {"contains": machine_id}})

    f = None if not filters else (filters[0] if len(filters) == 1 else {"and": filters})
    pages = _query_db(DB_IDS["ordres_fab"], f)
    return [{
        "reference":        _prop(p, "Ordre de Fabrication"),  # titre
        "produit":          _prop(p, "Produit fabriqué"),
        "statut":           _prop(p, "Statut"),
        "ligne":            _prop(p, "Ligne de production"),
        "machine":          _prop(p, "Équipement concerné"),
        "responsable":      _prop(p, "Responsable OF"),
        "date_debut":       _prop(p, "Date début"),
        "date_fin":         _prop(p, "Date fin prévue"),
        "qte_prevue":       _prop(p, "Quantité cible"),
        "qte_realisee":     _prop(p, "Quantité réalisée"),
        "cout_arret_h":     _prop(p, "Coût arrêt horaire (€)"),
        "secours_dispo":    _prop(p, "Ligne de secours disponible"),
        "notes":            _prop(p, "Notes"),
        # Champs absents dans ESCP — valeurs nulles pour compatibilité
        "priorite":         None,
        "duree_arret":      None,
        "impact_rul":       None,
        "cout_arret":       _prop(p, "Coût arrêt horaire (€)"),  # alias
    } for p in pages]


# ── 5. HISTORIQUE & PLAN DE MAINTENANCE ───────────────────────────────────────
# Base ESCP : titre = "Intervention"
# Champs : Statut, Type d'intervention, Équipement, Technicien assigné,
#          Composants à remplacer, Description, Résultat, Priorité,
#          Durée estimée (h), Durée réelle (h), Coût estimé (€),
#          Date planifiée, Date réalisée, Habilitation requise,
#          Procédure LOTO requise

@st.cache_data(ttl=60)
def get_historique(machine_id: str = None, statut: str = None, limit: int = 20) -> list[dict]:
    """Historique des interventions, triées par date planifiée décroissante."""
    filters = []
    if machine_id:
        filters.append({"property": "Équipement",
                         "rich_text": {"contains": machine_id}})
    if statut:
        filters.append({"property": "Statut", "select": {"equals": statut}})

    f = None if not filters else (filters[0] if len(filters) == 1 else {"and": filters})
    pages = _query_db(DB_IDS["historique"], f,
                      sorts=[{"property": "Date planifiée", "direction": "descending"}])
    return [{
        "titre":             _prop(p, "Intervention"),        # titre
        "machine":           _prop(p, "Équipement"),
        "type":              _prop(p, "Type d'intervention"),
        "statut":            _prop(p, "Statut"),
        "priorite":          _prop(p, "Priorité"),
        "technicien":        _prop(p, "Technicien assigné"),
        "date":              _prop(p, "Date planifiée"),
        "date_realisee":     _prop(p, "Date réalisée"),
        "duree_estimee":     _prop(p, "Durée estimée (h)"),
        "duree_reelle":      _prop(p, "Durée réelle (h)"),
        "cout_estime":       _prop(p, "Coût estimé (€)"),
        "description":       _prop(p, "Description"),
        "resultat":          _prop(p, "Résultat"),
        "composants":        _prop(p, "Composants à remplacer"),
        "habilitations":     _prop(p, "Habilitation requise"),  # list
        "loto_requis":       _prop(p, "Procédure LOTO requise"),
        # Aliases pour compatibilité avec le code existant des agents
        "actions":           _prop(p, "Description"),
        "pieces":            _prop(p, "Composants à remplacer"),
        "observations":      _prop(p, "Résultat"),
        "cout_intervention": _prop(p, "Coût estimé (€)"),
        "prochaine_echeance": None,
        "cout_arret_prod":   None,
        "rul_avant":         None,
        "rul_apres":         None,
        "cause_racine":      None,
        "alerte_ia":         None,
    } for p in pages[:limit]]


# ── 6. DOCUMENTATION & HSE ────────────────────────────────────────────────────
# Base ESCP : titre = "Titre document"
# Champs : Type, Statut, Machine concernée, EPI obligatoires, Niveau risque,
#          Persona destinataire, Contenu résumé, Version, Auteur,
#          Lien document, Date validation, Date révision

@st.cache_data(ttl=120)
def get_docs_hse(machine_id: str = None, type_doc: str = None, persona: str = None) -> list[dict]:
    """Documents HSE. Filtres optionnels par machine, type et persona destinataire."""
    filters = []
    if machine_id:
        filters.append({"property": "Machine concernée",
                         "rich_text": {"contains": machine_id}})
    if type_doc:
        filters.append({"property": "Type", "select": {"equals": type_doc}})

    f = None if not filters else (filters[0] if len(filters) == 1 else {"and": filters})
    pages = _query_db(DB_IDS["hse_docs"], f)

    docs = [{
        "titre":           _prop(p, "Titre document"),
        "type":            _prop(p, "Type"),
        "statut":          _prop(p, "Statut"),
        "machine":         _prop(p, "Machine concernée"),
        "niveau_risque":   _prop(p, "Niveau risque"),
        "epi":             _prop(p, "EPI obligatoires"),        # list
        "persona":         _prop(p, "Persona destinataire"),    # list
        "version":         _prop(p, "Version"),
        "auteur":          _prop(p, "Auteur"),
        "resume":          _prop(p, "Contenu résumé"),
        "lien":            _prop(p, "Lien document"),
        "date_validation": _prop(p, "Date validation"),
        "date_revision":   _prop(p, "Date révision"),
    } for p in pages]

    if persona:
        docs = [d for d in docs if persona in (d.get("persona") or [])]
    return docs


# ── CONTEXTE COMPLET MACHINE (agrégateur) ─────────────────────────────────────

@st.cache_data(ttl=30)
def get_contexte_machine(machine_id: str) -> dict:
    """
    Retourne le contexte complet d'une machine pour alimenter les 4 agents.

    Usage dans un agent :
        from notion_client import get_contexte_machine
        ctx = get_contexte_machine("P-17")
        rul = ctx["machine"]["rul_jours"]
        pieces_dispo = ctx["pieces"]
    """
    return {
        "machine":      get_machine(machine_id) or {},
        "pieces":       get_pieces(machine_id=machine_id),
        "ordres_fab":   get_ordres_fabrication(machine_id=machine_id, statut="En cours"),
        "historique":   get_historique(machine_id=machine_id, limit=5),
        "docs_hse":     get_docs_hse(machine_id=machine_id),
        "equipe_dispo": get_equipe(disponibilite="Disponible"),
    }


# ── MÉTRIQUES ROI (Agent Antoine) ────────────────────────────────────────────

@st.cache_data(ttl=300)
def get_metriques_roi() -> dict:
    """
    Calcule les KPIs ROI depuis l'historique Notion.
    Utilisé par l'Agent Antoine pour le dashboard exécutif.
    """
    interventions = get_historique(limit=100)
    # Statut "Réalisée" dans ESCP (était "Terminée" dans l'ancienne base)
    terminees     = [i for i in interventions if i["statut"] == "Réalisée"]
    # Type "Prédictive" dans ESCP (plus proche de prescriptive)
    prescriptives = [i for i in terminees
                     if i["type"] in ("Prédictive", "Préventive conditionnelle")]

    cout_interventions = sum(i.get("cout_intervention") or 0 for i in terminees)
    couts_evites       = sum(i.get("cout_arret_prod") or 0 for i in prescriptives)
    roi = round(couts_evites / cout_interventions, 1) if cout_interventions > 0 else 0

    # Statuts d'alerte dans ESCP : "Alerte" et "Critique"
    machines_alerte = get_machines(statut="Alerte") + get_machines(statut="Critique")

    return {
        "nb_interventions":   len(terminees),
        "nb_prescriptives":   len(prescriptives),
        "cout_interventions": cout_interventions,
        "couts_evites":       couts_evites,
        "roi":                roi,
        "machines_alerte":    len(machines_alerte),
        "detail_alertes":     machines_alerte,
    }


# ── CRÉER UNE INTERVENTION (POST) ─────────────────────────────────────────────

def create_intervention(data: dict) -> dict:
    """
    Crée un enregistrement dans le Plan de Maintenance Notion (base ESCP).

    Champs attendus dans `data` (tous optionnels sauf titre) :
        titre, machine, type, statut, technicien,
        date (ISO 8601), duree_reelle, cout, description,
        composants, resultat
    """
    url = f"{NOTION_BASE_URL}/pages"

    # Injecte cause_racine dans Description (pas de champ dédié en ESCP)
    desc_parts = [data.get("description") or data.get("actions") or ""]
    if data.get("cause_racine"):
        desc_parts.append(f"Cause racine : {data['cause_racine']}")
    description_text = " | ".join(p for p in desc_parts if p)

    # Injecte rul_avant dans Résultat (pas de champ dédié en ESCP)
    res_parts = [data.get("resultat") or data.get("observations") or ""]
    if data.get("rul_avant") is not None:
        res_parts.append(f"RUL avant intervention : {data['rul_avant']} j")
    resultat_text = " | ".join(p for p in res_parts if p)

    body = {
        "parent": {"database_id": DB_IDS["historique"]},
        "properties": {
            "Intervention": {
                "title": [{"text": {"content": data.get("titre", "Intervention")}}]
            },
            "Équipement": {
                "rich_text": [{"text": {"content": data.get("machine", "")}}]
            },
            "Type d'intervention": {
                "select": {"name": data.get("type", "Prédictive")}
            },
            "Statut": {
                "select": {"name": data.get("statut", "Réalisée")}
            },
            "Technicien assigné": {
                "rich_text": [{"text": {"content": data.get("technicien", "")}}]
            },
            "Description": {
                "rich_text": [{"text": {"content": description_text}}]
            },
            "Composants à remplacer": {
                "rich_text": [{"text": {"content": data.get("composants", data.get("pieces", ""))}}]
            },
            "Résultat": {
                "rich_text": [{"text": {"content": resultat_text}}]
            },
        },
    }

    if data.get("date"):
        body["properties"]["Date planifiée"] = {"date": {"start": data["date"]}}
    if data.get("date_realisee"):
        body["properties"]["Date réalisée"] = {"date": {"start": data["date_realisee"]}}
    if data.get("duree_reelle") is not None:
        body["properties"]["Durée réelle (h)"] = {"number": float(data["duree_reelle"])}
    if data.get("cout") is not None:
        body["properties"]["Coût estimé (€)"] = {"number": float(data["cout"])}
    if data.get("priorite"):
        body["properties"]["Priorité"] = {"select": {"name": data["priorite"]}}
    if data.get("loto_requis"):
        body["properties"]["Procédure LOTO requise"] = {"select": {"name": data["loto_requis"]}}

    resp = requests.post(url, headers=_headers(), json=body, timeout=10)
    resp.raise_for_status()
    return resp.json()
