"""
api_rul.py — ResilientFlow AI · Microservice RUL live
======================================================
FastAPI qui expose le RUL temps réel de la Pompe P-17.
Miroir exact de la logique shared_state.py (ne pas modifier shared_state.py).

Lancer :
    pip install fastapi uvicorn
    python api_rul.py

Endpoints :
    GET  /api/rul              → RUL courant + statut + capteurs
    POST /api/scenario         → Changer le scénario (nominal / surchauffe / critique)
    GET  /api/scenario         → Scénario actuel
    GET  /api/agent            → Prescription Lionel (agent IA, déclenché si non-Nominal)

Port : 8000 (configurable via ENV_PORT)
"""

import os
import re
import time

# ── Charger les secrets Streamlit comme variables d'env ───────────────────────
# (nécessaire pour llm_client.py et agent_lionel.py hors Streamlit)
_SECRETS_FILE = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
if os.path.exists(_SECRETS_FILE):
    with open(_SECRETS_FILE) as _f:
        for _line in _f:
            _line = _line.strip()
            if "=" in _line and not _line.startswith("#"):
                _k, _, _v = _line.partition("=")
                _v = _v.strip().strip('"').strip("'")
                os.environ.setdefault(_k.strip(), _v)
import numpy as np
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
# NB : run_agent_lionel est importé PARESSEUSEMENT dans _generate_prescription
# pour que le service RUL + la télécommande tournent sans streamlit/notion.

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="ResilientFlow AI — RUL API",
    description="RUL live de la Pompe P-17 pour Even Realities G2",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Scénarios (miroir de shared_state.py) ─────────────────────────────────────

SCENARIOS = {
    "nominal": {
        "label":     "Nominal",
        "base_temp": 67.0,
        "base_vib":  0.8,
        "base_pres": 4.4,
        "base_cur":  20.7,
    },
    "degradation": {
        "label":     "Dégradation",
        "base_temp": 75.0,
        "base_vib":  2.5,
        "base_pres": 4.2,
        "base_cur":  22.0,
    },
    "surchauffe": {
        "label":     "Surchauffe critique",
        "base_temp": 82.0,
        "base_vib":  3.5,
        "base_pres": 4.0,
        "base_cur":  24.5,
    },
    "critique": {
        "label":     "Défaillance imminente",
        "base_temp": 84.5,
        "base_vib":  3.9,
        "base_pres": 3.8,
        "base_cur":  25.0,
    },
}

# État courant
_state = {
    "scenario": "nominal",
    "tick": 0,
}

# Cache prescription (évite de relancer l'agent à chaque requête G2)
_prescription_cache: dict = {
    "scenario":  None,   # scénario pour lequel la prescription a été générée
    "pages":     [],     # liste de strings (pages de texte plain pour G2)
    "raw":       "",     # texte complet brut
    "loading":   False,  # en cours de génération
    "error":     None,
}


# ── Helpers prescription ──────────────────────────────────────────────────────

def _strip_markdown(text: str) -> str:
    """Supprime le Markdown pour l'affichage G2 (monochrome, texte seul)."""
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)   # **gras**
    text = re.sub(r'\*(.*?)\*',     r'\1', text)    # *italique*
    text = re.sub(r'#{1,6}\s*',     '',    text)    # ## titres
    text = re.sub(r'`(.*?)`',       r'\1', text)    # `code`
    return text


def _paginate(text: str, lines_per_page: int = 6) -> list[str]:
    """Découpe le texte en pages de N lignes pour l'affichage G2."""
    lines = [l for l in text.splitlines() if l.strip()]
    pages = []
    for i in range(0, len(lines), lines_per_page):
        pages.append('\n'.join(lines[i:i + lines_per_page]))
    return pages or ["(vide)"]


def _generate_prescription(scenario_key: str, live: dict) -> None:
    """Appelé en arrière-plan. Met à jour _prescription_cache."""
    _prescription_cache["loading"] = True
    _prescription_cache["error"]   = None
    try:
        from agents.agent_lionel import run_agent_lionel  # import paresseux
        raw = run_agent_lionel(
            c_temp=live["temperature"],
            c_vib=live["vibration"],
            c_pres=live["pression"],
            c_rul=int(live["rul_jours"]),  # agent attend des JOURS (Lot A)
        )
        plain = _strip_markdown(raw)
        _prescription_cache["raw"]      = raw
        _prescription_cache["pages"]    = _paginate(plain)
        _prescription_cache["scenario"] = scenario_key
    except Exception as exc:
        _prescription_cache["error"] = str(exc)
        _prescription_cache["pages"] = [f"Erreur agent: {str(exc)[:80]}"]
    finally:
        _prescription_cache["loading"] = False


# ── Calcul RUL (aligné sur shared_state.py — Lot C) ───────────────────────────
# RUL nominal de référence en JOURS (identique à shared_state.RUL_NOMINAL).
RUL_NOMINAL = 90


def compute_rul(scenario_key: str) -> dict:
    sc = SCENARIOS.get(scenario_key, SCENARIOS["nominal"])

    c_temp = sc["base_temp"] + np.random.uniform(-0.5,  0.5)
    c_vib  = max(0.1, sc["base_vib"]  + np.random.uniform(-0.05, 0.05))
    c_pres = max(0.1, sc["base_pres"] + np.random.uniform(-0.05, 0.05))
    c_cur  = max(0.0, sc["base_cur"]  + np.random.uniform(-0.2,  0.2))

    temp_stress = max(0.0, (c_temp - 70.0) / 15.0)
    vib_stress  = max(0.0, (c_vib  -  1.0) /  3.0)
    pres_stress = max(0.0, abs(c_pres - 4.5) / 4.0)
    stress = min(1.0, temp_stress * 0.50 + vib_stress * 0.40 + pres_stress * 0.10)

    c_rul = max(0, int(RUL_NOMINAL * (1.0 - stress) ** 3))

    r_status = "Nominal" if c_rul > 45 else ("Alerte" if c_rul > 3 else "Critique")

    _state["tick"] += 1

    return {
        "machine_id":   "P-17",
        "scenario":     scenario_key,
        "scenario_label": sc["label"],
        "rul_jours":    c_rul,
        "statut":       r_status,
        "temperature":  round(float(c_temp), 1),
        "vibration":    round(float(c_vib),  2),
        "pression":     round(float(c_pres), 2),
        "courant":      round(float(c_cur),  1),
        "tick":         _state["tick"],
        "timestamp":    time.time(),
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/rul")
def get_rul():
    """Retourne le RUL courant, statut et valeurs capteurs."""
    return compute_rul(_state["scenario"])


class ScenarioRequest(BaseModel):
    scenario: str  # "nominal" | "degradation" | "surchauffe" | "critique"


@app.post("/api/scenario")
def set_scenario(req: ScenarioRequest):
    """Change le scénario de simulation."""
    if req.scenario not in SCENARIOS:
        return {
            "error": f"Scénario inconnu. Valeurs valides : {list(SCENARIOS.keys())}"
        }
    _state["scenario"] = req.scenario
    return {
        "ok": True,
        "scenario": req.scenario,
        "label": SCENARIOS[req.scenario]["label"],
    }


@app.get("/api/scenario")
def get_scenario():
    """Retourne le scénario actif."""
    sc = _state["scenario"]
    return {
        "scenario": sc,
        "label": SCENARIOS[sc]["label"],
        "available": list(SCENARIOS.keys()),
    }


@app.get("/api/agent")
def get_agent(background_tasks: BackgroundTasks):
    """
    Retourne la prescription Lionel pour le scénario courant.
    - Si statut Nominal → pas de prescription nécessaire.
    - Si déjà en cache pour ce scénario → retour immédiat.
    - Si en cours de génération → status "loading".
    - Sinon → lance la génération en arrière-plan et retourne "loading".
    """
    live = compute_rul(_state["scenario"])
    scenario_key = _state["scenario"]

    if live["statut"] == "Nominal":
        return {
            "status":   "nominal",
            "message":  "RUL nominal — aucune prescription requise.",
            "pages":    [],
            "loading":  False,
        }

    # Cache valide pour ce scénario ?
    if (
        _prescription_cache["scenario"] == scenario_key
        and _prescription_cache["pages"]
        and not _prescription_cache["loading"]
    ):
        return {
            "status":  "ready",
            "pages":   _prescription_cache["pages"],
            "loading": False,
            "error":   _prescription_cache["error"],
        }

    # Déjà en cours ?
    if _prescription_cache["loading"]:
        return {"status": "loading", "pages": [], "loading": True}

    # Lancer en arrière-plan
    _prescription_cache["pages"]    = []
    _prescription_cache["scenario"] = scenario_key
    background_tasks.add_task(_generate_prescription, scenario_key, live)
    return {"status": "loading", "pages": [], "loading": True}


# ── Télécommande de démo (1 clic → change le scénario, les lunettes suivent) ──

_CONTROL_HTML = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ResilientFlow — Télécommande G2</title>
<style>
 body{margin:0;font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#0b1220;color:#e2e8f0;
   display:flex;flex-direction:column;align-items:center;padding:24px;}
 h1{font-size:1.1rem;font-weight:600;margin:0 0 4px;}
 .sub{color:#94a3b8;font-size:.85rem;margin-bottom:18px;}
 .live{background:#111a2e;border:1px solid #1e293b;border-radius:14px;padding:18px 24px;text-align:center;
   min-width:260px;margin-bottom:18px;}
 .rul{font-size:2.6rem;font-weight:800;line-height:1;}
 .pill{display:inline-block;padding:4px 14px;border-radius:20px;font-weight:700;font-size:.8rem;margin-top:8px;}
 .btns{display:grid;grid-template-columns:1fr 1fr;gap:12px;width:100%;max-width:360px;}
 button{border:0;border-radius:12px;padding:16px;font-size:1rem;font-weight:600;color:#fff;cursor:pointer;}
 .b-nom{background:#166534;} .b-deg{background:#b45309;} .b-sur{background:#c2410c;} .b-cri{background:#b91c1c;}
 button:active{transform:scale(.97);}
 .full{grid-column:1/3;}
</style></head><body>
 <h1>🕶️ Télécommande démo — Pompe P-17</h1>
 <div class="sub">Change le scénario en direct · les lunettes G2 suivent</div>
 <div class="live">
   <div style="color:#94a3b8;font-size:.8rem;">RUL estimé</div>
   <div class="rul" id="rul">— <span style="font-size:1rem;font-weight:400;color:#94a3b8;">j</span></div>
   <div class="pill" id="pill" style="background:#1e293b;">…</div>
   <div id="sensors" style="color:#64748b;font-size:.78rem;margin-top:8px;"></div>
 </div>
 <div class="btns">
   <button class="b-nom" onclick="setSc('nominal')">✅ Normal</button>
   <button class="b-deg" onclick="setSc('degradation')">⚠️ Dégradation</button>
   <button class="b-sur full" onclick="setSc('surchauffe')">🔥 Surchauffe critique</button>
   <button class="b-cri full" onclick="setSc('critique')">🔴 Défaillance imminente</button>
 </div>
<script>
 async function setSc(s){await fetch('/api/scenario',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scenario:s})});poll();}
 async function poll(){try{const r=await fetch('/api/rul');const d=await r.json();
   document.getElementById('rul').innerHTML=d.rul_jours+' <span style="font-size:1rem;font-weight:400;color:#94a3b8;">j</span>';
   const p=document.getElementById('pill');p.textContent=d.statut;
   p.style.background=d.statut==='Critique'?'#b91c1c':(d.statut==='Alerte'?'#b45309':'#166534');
   document.getElementById('sensors').textContent=`T ${d.temperature}°C · vib ${d.vibration} mm/s · P ${d.pression} bar`;
 }catch(e){}}
 poll();setInterval(poll,2000);
</script></body></html>"""


@app.get("/control", response_class=HTMLResponse)
def control():
    """Page télécommande pour la démo (localhost:8000/control)."""
    return _CONTROL_HTML


@app.get("/")
def root():
    return {
        "service": "ResilientFlow AI — RUL API",
        "version": "1.0.0",
        "control": "/control",
        "docs": "/docs",
    }


# ── Démarrage ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"[RUL API] Démarrage sur http://localhost:{port}")
    print(f"[RUL API] Docs : http://localhost:{port}/docs")
    uvicorn.run(app, host="0.0.0.0", port=port)
