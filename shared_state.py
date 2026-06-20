# shared_state.py
# Module partagé : initialisation du session state, mise à jour capteurs, config GitHub
import streamlit as st
import numpy as np
import requests
import os

# ── SECRETS : lus depuis Streamlit Cloud ou variables d'environnement ─────────
# Ne jamais écrire les tokens directement dans le code !
def get_secret(key: str) -> str:
    """Lit un secret depuis st.secrets (Streamlit Cloud) ou os.environ (local)."""
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, "")

# ── CONFIGURATION GITHUB ─────────────────────────────────────────────────────
GITHUB_USER   = "VOTRE_NOM_UTILISATEUR_GITHUB"
GITHUB_REPO   = "maintenance-knowledge-base"
GITHUB_BRANCH = "main"


def get_github_file(path, is_json=False):
    url = (
        "https://raw.githubusercontent.com/"
        + GITHUB_USER + "/" + GITHUB_REPO + "/" + GITHUB_BRANCH + "/" + path
    )
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json() if is_json else response.text
        return None
    except Exception:
        return None


# ── DONNÉES DE CONTEXTE USINE ─────────────────────────────────────────────────
CONTEXTE_USINE = {
    "production": {
        "ordre_fabrication_actif": "OF-2026-89A",
        "ligne_concerne":          "Ligne 2",
        "cout_arret_heure":        6500,
    },
    "equipe": {
        "technicien_recommande":  "Lionel (Habilité Mécanique/Hydraulique - Charge : 32h/40h)",
        "technicien_secondaire":  "Marc D. (Habilité Électricité - Surcharge : 39h/40h)",
    },
    "stocks": {
        "pieces_disponibles": (
            "Joints d'étanchéité P17 (En stock : 2) | "
            "Roulements (Stock : 0 - Commande en cours)"
        ),
    },
}


# ── CSS COMMUN ────────────────────────────────────────────────────────────────
COMMON_CSS = """
<style>
.stApp { background-color: #ffffff; }
div[data-testid="stMetric"] {
    background-color: #fcfcfc !important;
    border: 1px solid #eeeeee !important;
    padding: 8px 15px !important;
    border-radius: 5px !important;
}
.threshold-label {
    color: #ef4444; font-size: 0.75rem; font-weight: bold;
    display: block; margin-top: -10px; margin-bottom: 5px;
}
.doc-box {
    background-color: #f0fdf4; border: 1px solid #bbf7d0;
    padding: 15px; border-radius: 5px;
    margin-top: 10px; margin-bottom: 10px;
}
.escp-banner {
    background-color: #002349; color: #ffffff;
    padding: 12px; border-radius: 4px; text-align: center;
    margin-top: 5px; margin-bottom: 15px; font-size: 0.85rem;
    border-left: 4px solid #d4af37;
}
</style>
"""


# ── INITIALISATION & MISE À JOUR DU SESSION STATE ────────────────────────────
def init_session_state():
    if "history" not in st.session_state:
        st.session_state.history = {
            "time": list(range(30)),
            "temp": [67.0] * 30,
            "vib":  [0.8]  * 30,
            "pres": [4.4]  * 30,
            "rul":  [72.0] * 30,
        }
    defaults = {
        "base_temp": 67.0,
        "base_vib":  0.8,
        "base_pres": 4.4,
        "base_cur":  20.7,
        "tick":      757,
        "running":   True,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def update_sensors():
    """Met à jour les capteurs et retourne (c_temp, c_vib, c_pres, c_cur, c_rul, r_status, rul_pct)."""
    if st.session_state.running:
        st.session_state.tick += 1
        c_temp = st.session_state.base_temp + np.random.uniform(-0.5,  0.5)
        c_vib  = max(0.1, st.session_state.base_vib  + np.random.uniform(-0.05, 0.05))
        c_pres = max(0.1, st.session_state.base_pres + np.random.uniform(-0.05, 0.05))
        c_cur  = max(0.0, st.session_state.base_cur  + np.random.uniform(-0.2,  0.2))

        # Stress basé sur des seuils opérationnels :
        #   temp  : neutre ≤ 70 °C   → max = 85 °C
        #   vib   : neutre ≤ 1 mm/s  → max = 4 mm/s
        temp_stress = max(0.0, (c_temp - 70.0) / 15.0)
        vib_stress  = max(0.0, (c_vib  -  1.0) /  3.0)
        pres_stress = max(0.0, abs(c_pres - 4.5) / 4.0)
        stress = min(1.0, temp_stress * 0.50 + vib_stress * 0.40 + pres_stress * 0.10)
        # Exposant 3 → Nominal ≈ 70 j  |  Surchauffe ≈ 1 j
        c_rul  = max(0, int(72 * (1.0 - stress) ** 3))

        for key, val in zip(["temp", "vib", "pres", "rul"], [c_temp, c_vib, c_pres, c_rul]):
            st.session_state.history[key].append(val)
        st.session_state.history["time"].append(st.session_state.tick)

        for k in st.session_state.history:
            if len(st.session_state.history[k]) > 30:
                st.session_state.history[k].pop(0)
    else:
        c_temp = st.session_state.history["temp"][-1]
        c_vib  = st.session_state.history["vib"][-1]
        c_pres = st.session_state.history["pres"][-1]
        c_cur  = st.session_state.base_cur
        c_rul  = st.session_state.history["rul"][-1]

    r_status = "Nominal" if c_rul > 60 else ("Alerte" if c_rul > 2 else "Critique")
    rul_pct  = float(max(0.0, min(1.0, c_rul / 72.0)))
    return c_temp, c_vib, c_pres, c_cur, c_rul, r_status, rul_pct
