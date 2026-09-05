# pages/1_Lionel.py
# Agent Lionel — Technicien Terrain
# K0 Surveillance · K1 Briefing · K2 Procédure · K3 Post-intervention · K4 Arbitrage

import time
import datetime

import plotly.graph_objects as go
import streamlit as st

import notion_client as nc
from agents.agent_lionel import run_agent_lionel, resumer_journee_lionel
from shared_state import COMMON_CSS, init_session_state, update_sensors, RUL_NOMINAL
from p17_context import P17_CONTEXT

# Lot D — rafraîchissement K0 via fragment si la version de Streamlit le permet
_HAS_FRAGMENT = hasattr(st, "fragment")


def _fallback_reco_lionel(c_temp, c_vib, c_pres, c_rul) -> str:
    """Prescription de repli si le LLM (1min.ai) est indisponible.

    Évite tout crash de la page : on affiche la séquence corrective P-17
    standard (mêmes gestes que la démo lunettes), au lieu de propager
    l'exception de l'agent.
    """
    cout = P17_CONTEXT.get("cout_arret_eur_h", 6500)
    return f"""### 🔧 DÉCISION — Intervention corrective immédiate P-17

**Fenêtre :** sous 24 h (RUL estimé {c_rul} j — seuil critique franchi)

**Diagnostic :** surchauffe ({c_temp} °C) et vibration élevée ({c_vib} mm/s) → dégradation du roulement **6205-2RS** en fin de vie.

**Procédure (≈ 35 min) :**
1. Consigner (LOTO) : ouvrir le disjoncteur **Q-17A**
2. Isoler : fermer les vannes **V-17A** (amont) et **V-17B** (aval)
3. Purger le carter via le point **PT-17**
4. Remplacer le roulement **6205-2RS** (kit **B-07**)
5. Graisser **Mobilux EP2** — couple carter **45 N·m**
6. Redémarrer, vérifier **débit 45 m³/h** et **vibration < 1.5 mm/s**

**Sécurité :** gants + lunettes + chaussures S3, cadenas LOTO obligatoire.

**Coût d'arrêt évité :** ~{cout} €/h.
"""

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Lionel — Terrain", page_icon="🔧", layout="wide")
st.markdown(COMMON_CSS, unsafe_allow_html=True)

# ── BANNIÈRE ─────────────────────────────────────────────────────────────────
st.markdown("""
<div class="escp-banner">
    🎓 <b>Projet de Fin d'Études ESCP</b> &nbsp;|&nbsp;
    ⚙️ Sujet : <i>Maintenance Prescriptive &amp; Industrie 4.0</i>
</div>
""", unsafe_allow_html=True)

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.page_link("streamlit_home.py", label="← Retour à l'accueil", use_container_width=True)
    st.markdown("---")
    st.markdown("### 🔧 Lionel — Technicien Terrain")
    st.caption("Machine surveillée : **Pompe P-17** — Unité B")
    st.markdown("---")

    init_session_state()
    # Démarrage EN PAUSE par défaut : l'app est stable sur tous les onglets ;
    # presser ▶ lance le rafraîchissement live de K0 pour la démo.
    if "_started_paused" not in st.session_state:
        st.session_state.running = False
        st.session_state["_started_paused"] = True
    running_label = "⏸ Pause simulation" if st.session_state.running else "▶ Reprendre le live (K0)"
    if st.button(running_label, use_container_width=True):
        st.session_state.running = not st.session_state.running
        st.rerun()

    st.markdown("---")
    st.markdown("**Paramètres de simulation**")
    st.session_state.base_temp = st.slider("Température de base (°C)", 55.0, 85.0,
                                           float(st.session_state.base_temp), 0.5)
    st.session_state.base_vib  = st.slider("Vibration de base (mm/s)", 0.1, 4.0,
                                           float(st.session_state.base_vib), 0.05)
    st.session_state.base_pres = st.slider("Pression de base (bar)", 0.5, 7.0,
                                           float(st.session_state.base_pres), 0.1)

    st.markdown("---")
    st.markdown("**Scénarios**")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        if st.button("🔥 Surchauffe", use_container_width=True):
            st.session_state.base_temp = 82.0
            st.session_state.base_vib  = 3.5
            st.session_state.running = True   # relance le live pour jouer le scénario
            st.rerun()
    with col_s2:
        if st.button("✅ Normal", use_container_width=True):
            st.session_state.base_temp = 67.0
            st.session_state.base_vib  = 0.8
            st.session_state.base_pres = 4.4
            st.session_state.running = True
            st.rerun()

    st.markdown("---")
    _refresh_s = st.slider("⏱ Intervalle rafraîchissement K0 (s)", 1, 5,
                           int(st.session_state.get("refresh_s", 2)))
    st.session_state["refresh_s"] = _refresh_s

# ── SENSOR DATA ───────────────────────────────────────────────────────────────
c_temp, c_vib, c_pres, c_cur, c_rul, r_status, rul_pct = update_sensors()

STATUS_COLOR = {"Nominal": "#166534", "Alerte": "#b45309", "Critique": "#b91c1c"}
STATUS_BG    = {"Nominal": "#dcfce7", "Alerte": "#fef3c7", "Critique": "#fee2e2"}

# ── TABS — K2 « Procédure » visible uniquement en Alerte/Critique (surchauffe) ─
_show_k2 = r_status in ("Alerte", "Critique")
_labels = ["☀️ Ma journée", "📊 Mon poste", "📡 K0 — Surveillance", "📋 K1 — Briefing"]
if _show_k2:
    _labels.append("🔧 K2 — Procédure 🔔")
_labels += ["✅ K3 — Post-intervention", "⚖️ K4 — Arbitrage"]

_tabs = st.tabs(_labels)
tab_jour = _tabs[0]
tab_dash = _tabs[1]
tab0 = _tabs[2]
tab1 = _tabs[3]
if _show_k2:
    tab2 = _tabs[4]
    tab3 = _tabs[5]
    tab4 = _tabs[6]
else:
    tab2 = None
    tab3 = _tabs[4]
    tab4 = _tabs[5]

# ════════════════════════════════════════════════════════════════════════════════
# ONGLET « ☀️ Ma journée » — brief matinal (agent) + choix traiter / reporter
# ════════════════════════════════════════════════════════════════════════════════
_PORDER = {"P1 - Critique": 0, "P2 - Haute": 1, "P3 - Normale": 2, "P4 - Basse": 3}

_FALLBACK_INTERV = [
    {"titre": "Remplacement roulement P-17 (surchauffe)", "machine": "P-17", "type": "Corrective",
     "statut": "Planifiée", "priorite": "P1 - Critique", "duree_estimee": 0.6, "loto_requis": "Oui",
     "composants": "Roulement 6205-2RS (casier B-07)", "habilitations": ["Mécanique"],
     "description": "Surchauffe + vibration élevée → roulement 6205-2RS en fin de vie."},
    {"titre": "Contrôle vibratoire pompe V-08", "machine": "V-08", "type": "Préventive conditionnelle",
     "statut": "Planifiée", "priorite": "P2 - Haute", "duree_estimee": 0.3, "loto_requis": "Non",
     "habilitations": ["Mécanique"], "description": "Relevé vibratoire + analyse spectrale suite alerte capteur."},
    {"titre": "Graissage préventif convoyeur C-12", "machine": "C-12", "type": "Préventive systématique",
     "statut": "Planifiée", "priorite": "P3 - Normale", "duree_estimee": 0.4, "loto_requis": "Non",
     "habilitations": ["Mécanique"], "description": "Graissage périodique des paliers + contrôle courroie."},
]


def _charger_mes_interventions():
    try:
        items = nc.get_historique(limit=50) or []
        mine = [i for i in items
                if "lionel" in str(i.get("technicien", "")).lower()
                and str(i.get("statut", "")) in ("Planifiée", "En cours")]
        return mine or _FALLBACK_INTERV
    except Exception:
        return _FALLBACK_INTERV


def _charger_arbitrages_sophie():
    try:
        pages = nc._query_db(nc.DB_IDS["decisions_sophie"], None, None) or []
        arbs = []
        for p in pages[:5]:
            t = nc._prop(p, "Décision") or nc._prop(p, "Titre") or nc._prop(p, "Name") or ""
            if t:
                arbs.append(str(t))
        return arbs
    except Exception:
        return []


with tab_jour:
    st.subheader("☀️ Ma journée — " + datetime.date.today().strftime("%d/%m/%Y"))
    st.caption("Ton brief du matin, tes interventions affectées et les arbitrages de Sophie.")

    if "mes_interventions" not in st.session_state:
        st.session_state["mes_interventions"] = _charger_mes_interventions()
    _interv = sorted(st.session_state["mes_interventions"],
                     key=lambda i: _PORDER.get(i.get("priorite", ""), 9))

    if "arbitrages_sophie" not in st.session_state:
        st.session_state["arbitrages_sophie"] = _charger_arbitrages_sophie() or [
            "P-17 priorisée en P1 — arrêt/bascule à valider avec Sophie avant intervention."
        ]
    _arbitrages = st.session_state["arbitrages_sophie"]

    _cbrief, _crefr = st.columns([4, 1])
    with _crefr:
        if st.button("🔄 Brief", use_container_width=True):
            st.session_state.pop("_brief_jour", None)
    if "_brief_jour" not in st.session_state:
        with st.spinner("🤖 L'agent prépare ton brief du matin…"):
            try:
                st.session_state["_brief_jour"] = resumer_journee_lionel(_interv, _arbitrages)
            except Exception as _e:
                st.session_state["_brief_jour"] = "_(brief indisponible : " + str(_e)[:80] + ")_"
    st.markdown(st.session_state["_brief_jour"])

    st.divider()
    st.markdown("#### 🗂️ Mes interventions — je traite ou je reporte")
    for _idx, _it in enumerate(_interv):
        with st.container(border=True):
            _c1, _c2, _c3 = st.columns([5, 2, 2])
            _loto = str(_it.get("loto_requis", "")).lower().startswith("o")
            _c1.markdown(
                f"**{_it.get('titre','?')}**  \n"
                f"{_it.get('machine','?')} · {_it.get('type','?')} · ~{_it.get('duree_estimee','?')} h · "
                f"{'🔒 LOTO' if _loto else 'sans LOTO'}"
            )
            _c2.markdown(f"**{_it.get('priorite','?')}**")
            if _c3.button("Traiter", key=f"trait_{_idx}", use_container_width=True):
                st.session_state["intervention_active"] = _it
                st.success("Sélectionnée → onglet 🔧 Procédure")
            if _c3.button("Reporter", key=f"rep_{_idx}", use_container_width=True):
                st.info("Report transmis à Sophie (arbitrage).")
    if st.session_state.get("intervention_active"):
        st.caption("Intervention en cours : **"
                   + st.session_state["intervention_active"].get("titre", "") + "**")

# ════════════════════════════════════════════════════════════════════════════════
# ONGLET DASHBOARD — « Mon poste » (accueil)
# ════════════════════════════════════════════════════════════════════════════════
with tab_dash:
    st.markdown("## 📊 Mon poste — Lionel Dumont")
    st.caption("Technicien terrain · Unité B · Vue parc — sélectionnez une machine")

    _MACHINES = ["P-17", "C-03", "M-08", "P-09", "V-12"]
    _sel = st.selectbox("🏭 Machine", _MACHINES, index=0, key="dash_machine")

    _mois = datetime.date.today().strftime("%Y-%m")
    def _mmatch(i):
        return _sel in (i.get("machine") or "")

    # ── Contexte de la machine sélectionnée ───────────────────────────────────
    try:
        _mrec = nc.get_machine(_sel) or {}
    except Exception:
        _mrec = {}
    _mnom = _mrec.get("nom") or _sel
    _munite = _mrec.get("unite") or "—"
    _ref_nom = _mrec.get("responsable") or "—"

    if _sel == "P-17":
        _rul_val, _stat, _live = c_rul, r_status, True
    else:
        _rul_val = int(_mrec.get("rul_jours") or 90)
        _stat = _mrec.get("statut") or ("Nominal" if _rul_val > 45 else ("Alerte" if _rul_val > 3 else "Critique"))
        _live = False
    _rul_pct_sel = max(0.0, min(1.0, _rul_val / RUL_NOMINAL))

    # ── Indicateurs recalculés pour la machine sélectionnée ───────────────────
    try:
        _hist = nc.get_historique(limit=200)
    except Exception:
        _hist = []
    _mine      = [i for i in _hist if _mmatch(i)]
    _a_faire   = sum(1 for i in _mine if i.get("statut") == "Planifiée")
    _en_retard = sum(1 for i in _mine if i.get("statut") == "En retard")
    _realisees = [i for i in _mine if i.get("statut") == "Réalisée"]
    _real_mois = sum(1 for i in _realisees if (i.get("date_realisee") or "").startswith(_mois))
    _durees    = [i.get("duree_reelle") for i in _realisees if i.get("duree_reelle")]
    _tmoyen    = round(sum(_durees) / len(_durees) * 60) if _durees else None
    _presc     = sum(1 for i in _realisees if i.get("type") in ("Prédictive", "Préventive conditionnelle"))
    _ppresc    = round(_presc / len(_realisees) * 100) if _realisees else None

    # Référent de la machine + sa disponibilité
    try:
        _eq = nc.get_equipe()
    except Exception:
        _eq = []
    _rl = _ref_nom.lower()
    _me = next((t for t in _eq
                if f"{t.get('prenom','')} {t.get('nom','')}".strip().lower() == _rl
                or (t.get('nom') and t.get('nom').lower() in _rl)), None)
    _heures = _me.get("heures_restantes") if _me else None
    _dispo  = (_me.get("disponibilite") if _me else None) or "—"

    _plan = sorted([i for i in _mine if i.get("statut") == "Planifiée"],
                   key=lambda i: i.get("date") or "9999-99-99")
    _prochaine = _plan[0] if _plan else None

    try:
        _pieces = nc.get_pieces(machine_id=_sel)
    except Exception:
        _pieces = []
    try:
        _machines = nc.get_machines()
        for _m in _machines:
            if "P-17" in ((_m.get("id") or "") + (_m.get("nom") or "")):
                _m["rul_jours"] = c_rul
                _m["statut"] = r_status
    except Exception:
        _machines = []
    _alertes = [m for m in _machines
                if (m.get("statut") in ("Alerte", "Critique")) or ((m.get("rul_jours") or 999) <= 45)]
    _urgent = min(_alertes, key=lambda m: m.get("rul_jours") or 999) if _alertes else None

    # ── Style dashboard (proche de la charte visuelle) ────────────────────────
    st.markdown("""
    <style>
    .rf-hero{background:#ffffff;border:1px solid #e6e8ec;border-radius:14px;padding:20px 24px;
      display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap;align-items:center;}
    .rf-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;}
    .rf-kpi{background:#f8fafc;border:1px solid #eef1f5;border-radius:12px;padding:14px 16px;}
    .rf-kpi .l{font-size:0.78rem;color:#64748b;}
    .rf-kpi .v{font-size:1.55rem;font-weight:700;margin-top:6px;line-height:1;}
    .rf-lab{font-size:0.82rem;color:#475569;font-weight:600;margin-bottom:4px;}
    .rf-row{display:flex;align-items:center;justify-content:space-between;padding:7px 0;border-top:1px solid #f1f5f9;}
    .rf-pill{font-size:0.72rem;padding:3px 10px;border-radius:20px;font-weight:600;}
    </style>
    """, unsafe_allow_html=True)

    # ── Héros machine sélectionnée ────────────────────────────────────────────
    _bg = STATUS_BG.get(_stat, "#f1f5f9")
    _col = STATUS_COLOR.get(_stat, "#475569")
    _live_tag = "surveillance temps réel" if _live else "suivi GMAO"
    _proch_txt = _prochaine['titre'] if _prochaine else "Aucune intervention planifiée"
    _proch_date = f"📅 {_prochaine.get('date')}" if _prochaine and _prochaine.get('date') else ""
    st.markdown(
        f'<div class="rf-hero">'
        f'<div><div style="font-size:0.82rem;color:#64748b;">{_mnom} · {_munite} · réf. {_ref_nom} · {_live_tag}</div>'
        f'<div style="display:flex;align-items:baseline;gap:10px;margin-top:6px;">'
        f'<span style="font-size:2.8rem;font-weight:800;color:#0f172a;line-height:1;">{_rul_val}</span>'
        f'<span style="color:#64748b;">jours de RUL</span>'
        f'<span class="rf-pill" style="background:{_bg};color:{_col};">{_stat}</span></div>'
        f'<div style="height:6px;background:#eef1f5;border-radius:20px;margin-top:12px;width:250px;overflow:hidden;">'
        f'<div style="width:{max(3, int(_rul_pct_sel * 100))}%;height:100%;background:{_col};"></div></div></div>'
        f'<div style="border-left:1px solid #eef1f5;padding-left:22px;min-width:230px;">'
        f'<div style="font-size:0.82rem;color:#64748b;">Prochaine intervention</div>'
        f'<div style="font-size:1rem;font-weight:600;color:#0f172a;margin-top:3px;">{_proch_txt}</div>'
        f'<div style="font-size:0.8rem;color:#64748b;margin-top:2px;">{_proch_date}</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown("")

    # ── Tuiles KPI ────────────────────────────────────────────────────────────
    def _tile(icon, label, val, color="#0f172a"):
        return (f'<div class="rf-kpi"><div class="l">{icon} {label}</div>'
                f'<div class="v" style="color:{color}">{val}</div></div>')
    _tm = f"{_tmoyen} min" if _tmoyen else "—"
    _pp = f"{_ppresc} %" if _ppresc is not None else "—"
    _hh = f"{_heures:.0f} h" if _heures is not None else "—"
    _tiles = "".join([
        _tile("📋", "À faire", _a_faire),
        _tile("⚠️", "En retard", _en_retard, "#b45309" if _en_retard else "#0f172a"),
        _tile("✅", "Réalisées ce mois", _real_mois, "#166534"),
        _tile("⏱", "Temps moyen", _tm),
        _tile("💡", "Part prescriptive", _pp, "#2563eb"),
        _tile("👤", f"Dispo réf. · {_dispo}", _hh, "#166534" if _dispo == "Disponible" else "#0f172a"),
    ])
    st.markdown(f'<div class="rf-kpis">{_tiles}</div>', unsafe_allow_html=True)
    st.markdown("")

    # ── Thème Plotly commun ───────────────────────────────────────────────────
    def _theme(fig, h):
        fig.update_layout(height=h, margin=dict(l=8, r=8, t=8, b=8),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          font=dict(family="ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif",
                                    size=12, color="#64748b"), showlegend=False)
        fig.update_xaxes(showgrid=False, zeroline=False, showline=False, ticks="",
                         tickfont=dict(color="#94a3b8", size=11))
        fig.update_yaxes(gridcolor="#eef1f5", zeroline=False, showline=False, ticks="",
                         tickfont=dict(color="#94a3b8", size=11))
        return fig
    _CFG = {"displayModeBar": False}

    # ── Courbe RUL (pleine largeur) ───────────────────────────────────────────
    with st.container(border=True):
        if _live:
            st.markdown(f'<div class="rf-lab">📈 RUL {_mnom} — 30 derniers relevés (temps réel)</div>', unsafe_allow_html=True)
            _rul_hist = list(st.session_state.history["rul"])
        else:
            st.markdown(f'<div class="rf-lab">📈 RUL {_mnom} — tendance estimée (GMAO) · pilote temps réel : P-17</div>', unsafe_allow_html=True)
            _startv = _rul_val * 1.6
            _wig = [0, 1, 0, -1]
            _rul_hist = [max(0, round(_startv + (_rul_val - _startv) * (k / 29) + _wig[k % 4])) for k in range(30)]
        _figr = go.Figure()
        _figr.add_trace(go.Scatter(y=_rul_hist, mode="lines",
                                   line=dict(color="#2a78d6", width=2.5, shape="spline"),
                                   fill="tozeroy", fillcolor="rgba(42,120,214,0.08)",
                                   hovertemplate="%{y:.0f} j<extra></extra>"))
        _figr.add_hline(y=45, line=dict(color="#f59e0b", width=1.5, dash="dot"),
                        annotation_text="seuil 45 j", annotation_position="top left",
                        annotation_font=dict(size=10, color="#b45309"))
        _theme(_figr, 200)
        _figr.update_xaxes(showticklabels=False)
        st.plotly_chart(_figr, use_container_width=True, config=_CFG)

    # ── Interventions (6 derniers mois) + Répartition par type ────────────────
    _cA, _cB = st.columns(2)
    with _cA:
        with st.container(border=True):
            st.markdown('<div class="rf-lab">📅 Interventions réalisées — 6 derniers mois</div>', unsafe_allow_html=True)
            _MOIS_FR = ["", "janv.", "févr.", "mars", "avr.", "mai", "juin",
                        "juil.", "août", "sept.", "oct.", "nov.", "déc."]
            _tday = datetime.date.today()
            _months = []
            for _k in range(5, -1, -1):
                _mm, _yy = _tday.month - _k, _tday.year
                while _mm <= 0:
                    _mm += 12
                    _yy -= 1
                _months.append((f"{_yy:04d}-{_mm:02d}", f"{_MOIS_FR[_mm]} {str(_yy)[2:]}"))
            _counts = {k: 0 for k, _ in _months}
            for i in _realisees:
                _d = (i.get("date_realisee") or i.get("date") or "")[:7]
                if _d in _counts:
                    _counts[_d] += 1
            _figm = go.Figure(go.Bar(x=[lab for _, lab in _months],
                                     y=[_counts[k] for k, _ in _months],
                                     marker_color="#2a78d6", marker_line_width=0,
                                     hovertemplate="%{y} interv.<extra></extra>"))
            _theme(_figm, 210)
            _figm.update_layout(bargap=0.5)
            _figm.update_yaxes(dtick=1, rangemode="tozero")
            st.plotly_chart(_figm, use_container_width=True, config=_CFG)
    with _cB:
        with st.container(border=True):
            st.markdown('<div class="rf-lab">🧩 Répartition par type</div>', unsafe_allow_html=True)
            _types = {}
            for i in _realisees:
                _k = i.get("type") or "Autre"
                _types[_k] = _types.get(_k, 0) + 1
            if not _types:
                _types = {"Prédictive": 5, "Préventive conditionnelle": 2,
                          "Corrective": 2, "Préventive systématique": 1}
            _tot = sum(_types.values()) or 1
            _figt = go.Figure(go.Pie(labels=list(_types.keys()), values=list(_types.values()),
                                     hole=0.62, sort=False,
                                     marker=dict(colors=["#2a78d6", "#1baf7a", "#eda100", "#e34948", "#8b5cf6"],
                                                 line=dict(color="#ffffff", width=2)),
                                     textinfo="none",
                                     hovertemplate="%{label} : %{value} (%{percent})<extra></extra>"))
            _figt.update_layout(height=210, margin=dict(l=8, r=8, t=8, b=8),
                                paper_bgcolor="rgba(0,0,0,0)",
                                font=dict(size=11, color="#64748b"),
                                legend=dict(orientation="h", y=-0.08, x=0.5, xanchor="center"),
                                annotations=[dict(text=str(_tot), x=0.5, y=0.5, font_size=22,
                                                  showarrow=False, font_color="#0f172a")])
            st.plotly_chart(_figt, use_container_width=True, config=_CFG)

    # ── Stock critique + Alertes parc ─────────────────────────────────────────
    _cS, _cAl = st.columns(2)
    with _cS:
        with st.container(border=True):
            st.markdown(f'<div class="rf-lab">🔩 Stock pièces critiques {_sel}</div>', unsafe_allow_html=True)
            _crit = [p for p in _pieces if (p.get("stock_actuel") or 0) < (p.get("stock_minimum") or 1)]
            if _crit:
                for p in _crit:
                    _stock = p.get("stock_actuel") or 0
                    _mini = p.get("stock_minimum") or 1
                    if _stock <= 0:
                        _ic, _pbg, _pcl, _lbl = "❌", "#fee2e2", "#b91c1c", "rupture"
                    else:
                        _ic, _pbg, _pcl, _lbl = "🟠", "#fef3c7", "#b45309", "sous seuil"
                    st.markdown(
                        f'<div class="rf-row"><span style="font-size:0.9rem;color:#0f172a;">{_ic} {p.get("designation","?")}</span>'
                        f'<span class="rf-pill" style="background:{_pbg};color:{_pcl};">{_lbl} · {_stock}/{_mini}</span></div>',
                        unsafe_allow_html=True,
                    )
            elif _pieces:
                st.success("✅ Aucune pièce sous seuil.")
            else:
                st.info("Stock indisponible.")
    with _cAl:
        with st.container(border=True):
            st.markdown('<div class="rf-lab">🏭 Alertes parc actives</div>', unsafe_allow_html=True)
            _urg_txt = (f'Plus urgente : <b>{_urgent.get("nom", _urgent.get("id"))}</b> — RUL {_urgent.get("rul_jours","?")} j'
                        if _urgent else "Aucune machine en alerte")
            st.markdown(
                f'<div style="display:flex;align-items:baseline;gap:10px;">'
                f'<span style="font-size:2rem;font-weight:800;color:#b45309;">{len(_alertes)}</span>'
                f'<span style="color:#64748b;">machines en alerte</span></div>'
                f'<div style="font-size:0.9rem;color:#334155;margin-top:8px;">{_urg_txt}</div>',
                unsafe_allow_html=True,
            )

# ════════════════════════════════════════════════════════════════════════════════
# TAB 0 — K0 SURVEILLANCE
# ════════════════════════════════════════════════════════════════════════════════
def _render_k0():
    c_temp, c_vib, c_pres, c_cur, c_rul, r_status, rul_pct = update_sensors()
    st.markdown("## 📡 Surveillance temps réel — Pompe P-17")

    # KPI metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🌡 Température", f"{c_temp:.1f} °C",
              delta=f"{c_temp - 67:.1f}",
              delta_color="inverse" if c_temp > 75 else "normal")
    m2.metric("📳 Vibration", f"{c_vib:.2f} mm/s",
              delta=f"{c_vib - 0.8:.2f}",
              delta_color="inverse" if c_vib > 2.5 else "normal")
    m3.metric("💧 Pression", f"{c_pres:.2f} bar",
              delta=f"{c_pres - 4.4:.2f}")
    m4.metric("⚡ Courant", f"{c_cur:.1f} A")

    # RUL
    st.markdown("---")
    rul_col, status_col = st.columns([3, 1])
    with rul_col:
        st.markdown(f"### ⏱ RUL estimé : **{c_rul} jours**")
        st.progress(rul_pct)
        if c_rul <= 45:
            st.markdown(
                f'<span class="threshold-label">⚠️ Seuil opérationnel franchi — intervention recommandée</span>',
                unsafe_allow_html=True,
            )
    with status_col:
        st.markdown(
            f'<div style="background:{STATUS_BG[r_status]};color:{STATUS_COLOR[r_status]};'
            f'border-radius:8px;padding:16px;text-align:center;font-weight:700;font-size:1.1rem;">'
            f'{r_status}</div>',
            unsafe_allow_html=True,
        )

    # NB : la recommandation IA est rendue HORS de ce fragment (voir bloc après
    # `with tab0`) pour éviter que le rafraîchissement 2 s ne réinitialise le
    # scroll pendant qu'on lit la reco.

    # Trend charts
    st.markdown("---")
    st.markdown("### 📈 Tendances (30 dernières mesures)")
    hist = st.session_state.history

    CHART_CONFIGS = [
        ("temp", "Température",  "°C",   "#ef4444", "rgba(239,68,68,0.12)"),
        ("vib",  "Vibration",    "mm/s", "#f59e0b", "rgba(245,158,11,0.12)"),
        ("pres", "Pression",     "bar",  "#8b5cf6", "rgba(139,92,246,0.12)"),
    ]

    ch1, ch2, ch3 = st.columns(3)
    for col, (key, label, unit, color, fill_color) in zip([ch1, ch2, ch3], CHART_CONFIGS):
        vals = list(hist[key])
        times = list(hist["time"])
        v_min = min(vals) if vals else 0
        v_max = max(vals) if vals else 1
        padding = (v_max - v_min) * 0.2 or 1

        fig = go.Figure()
        # Zone de remplissage
        fig.add_trace(go.Scatter(
            x=times, y=vals,
            mode="lines",
            line=dict(color=color, width=2.5, shape="spline", smoothing=0.8),
            fill="tozeroy",
            fillcolor=fill_color,
            hovertemplate=f"<b>%{{y:.2f}} {unit}</b><extra></extra>",
        ))
        # Valeur actuelle en marqueur
        if vals:
            fig.add_trace(go.Scatter(
                x=[times[-1]], y=[vals[-1]],
                mode="markers+text",
                marker=dict(color=color, size=9, line=dict(color="white", width=2)),
                text=[f"<b>{vals[-1]:.1f}</b>"],
                textposition="top center",
                textfont=dict(color=color, size=11),
                hoverinfo="skip",
            ))
        fig.update_layout(
            title=dict(
                text=f"<b>{label}</b> <span style='font-size:11px;color:#64748b;'>({unit})</span>",
                font=dict(size=13, color="#1e293b"),
                x=0.02,
            ),
            margin=dict(l=4, r=4, t=38, b=24),
            height=220,
            showlegend=False,
            xaxis=dict(
                showticklabels=False,
                showgrid=False,
                zeroline=False,
            ),
            yaxis=dict(
                range=[max(0, v_min - padding), v_max + padding],
                showgrid=True,
                gridcolor="rgba(0,0,0,0.06)",
                tickfont=dict(size=10, color="#64748b"),
                zeroline=False,
            ),
            paper_bgcolor="white",
            plot_bgcolor="white",
        )
        col.plotly_chart(fig, use_container_width=True)


# Rendu K0 — fragment live : rafraîchit uniquement ce bloc, la page ne saute plus
if _HAS_FRAGMENT and st.session_state.running:
    _render_k0 = st.fragment(run_every=f"{_refresh_s}s")(_render_k0)

with tab0:
    _render_k0()

    # ── Recommandation IA — rendue hors fragment (pas de reset scroll toutes les 2 s)
    if r_status == "Critique":
        if st.session_state.get("_agent_status") != "Critique":
            # L'agent appelle le LLM 1min.ai : si l'API échoue (quota, panne…),
            # on bascule sur une prescription de repli au lieu de planter la page.
            try:
                with st.spinner("🤖 Analyse IA en cours..."):
                    st.session_state["_agent_reco"] = run_agent_lionel(c_temp, c_vib, c_pres, c_rul)
                st.session_state["_agent_reco_fallback"] = False
            except Exception as _agent_err:
                st.session_state["_agent_reco"] = _fallback_reco_lionel(c_temp, c_vib, c_pres, c_rul)
                st.session_state["_agent_reco_fallback"] = True
                st.session_state["_agent_reco_error"] = str(_agent_err)[:300]
            st.session_state["_agent_status"] = "Critique"
            # Notification email au technicien référent — UNE SEULE FOIS par épisode critique
            if not st.session_state.get("_email_sent"):
                try:
                    from notify import envoyer_alerte_critique
                    with st.spinner("📧 Envoi de l'alerte au technicien..."):
                        st.session_state["_email_result"] = envoyer_alerte_critique(
                            "P-17", c_rul, st.session_state["_agent_reco"]
                        )
                except Exception as e:
                    st.session_state["_email_result"] = {"ok": False, "error": str(e)}
                st.session_state["_email_sent"] = True
        with st.expander("🤖 Recommandation IA — Agent Lionel", expanded=True):
            if st.session_state.get("_agent_reco_fallback"):
                st.info("ℹ️ IA momentanément indisponible — prescription standard P-17 affichée.")
            st.markdown(st.session_state.get("_agent_reco", ""))
            if st.button("🔄 Nouvelle analyse", key="btn_refresh_agent"):
                with st.spinner("Analyse en cours..."):
                    st.session_state["_agent_reco"] = run_agent_lionel(c_temp, c_vib, c_pres, c_rul)
                st.rerun()
        # Bandeau statut de la notification email
        _er = st.session_state.get("_email_result")
        if _er:
            if _er.get("ok"):
                st.success(f"📧 Alerte envoyée à {_er.get('ref','')} — {_er.get('to','')}")
            elif _er.get("skipped"):
                st.info(f"📧 Notification email non envoyée — {_er.get('error','configuration manquante')}.")
            else:
                st.warning(f"📧 Échec de l'envoi email : {_er.get('error','?')}")
    else:
        st.session_state.pop("_agent_status", None)
        st.session_state.pop("_agent_reco", None)
        st.session_state.pop("_email_sent", None)
        st.session_state.pop("_email_result", None)

# ════════════════════════════════════════════════════════════════════════════════
# TAB 1 — K1 BRIEFING
# ════════════════════════════════════════════════════════════════════════════════
if tab1 is not None:
  with tab1:
    st.markdown("## 📋 Briefing du quart")
    _bf_today = datetime.date.today().strftime("%d/%m/%Y")
    st.caption(f"Lionel Dumont · quart du {_bf_today} · Unité B")

    st.markdown("""
    <style>
    .bf-lab{font-size:0.84rem;color:#475569;font-weight:600;margin:10px 0 8px;}
    .bf-row{display:flex;align-items:center;gap:12px;padding:11px 14px;border-top:1px solid #f1f5f9;}
    .bf-pil{font-size:0.7rem;font-weight:700;padding:3px 8px;border-radius:6px;flex-shrink:0;}
    .bf-st{font-size:0.72rem;padding:3px 10px;border-radius:20px;flex-shrink:0;white-space:nowrap;}
    .bf-meta{font-size:0.77rem;color:#94a3b8;margin-top:2px;}
    </style>
    """, unsafe_allow_html=True)

    def _is_lio(t):
        return "lionel" in (t or "").lower()

    try:
        _bh = nc.get_historique(limit=200)
    except Exception:
        _bh = []
    _mes = [i for i in _bh if _is_lio(i.get("technicien"))
            and i.get("statut") in ("Planifiée", "En retard", "En cours")]
    _PRANK = {"P1 - Critique": 0, "P2 - Haute": 1, "P3 - Normale": 2, "P4 - Basse": 3}
    _mes.sort(key=lambda i: (_PRANK.get(i.get("priorite"), 4), i.get("date") or "9999"))

    try:
        _bm = nc.get_machines()
        for _m in _bm:
            if "P-17" in ((_m.get("id") or "") + (_m.get("nom") or "")):
                _m["rul_jours"] = c_rul
                _m["statut"] = r_status
    except Exception:
        _bm = []
    _bfal = [m for m in _bm if (m.get("statut") in ("Alerte", "Critique"))
             or ((m.get("rul_jours") or 999) <= 45)]
    _bfal.sort(key=lambda m: m.get("rul_jours") or 999)

    st.markdown(
        f'<div style="display:flex;gap:8px;margin-bottom:4px;">'
        f'<span style="font-size:0.72rem;color:#b45309;background:#fef3c7;padding:4px 10px;border-radius:20px;">{len(_bfal)} alerte(s)</span>'
        f'<span style="font-size:0.72rem;color:#475569;background:#f1f5f9;padding:4px 10px;border-radius:20px;">{len(_mes)} intervention(s)</span>'
        f'</div>', unsafe_allow_html=True)

    # ── À traiter aujourd'hui ──────────────────────────────────────────────────
    st.markdown('<div class="bf-lab">🚨 À traiter aujourd\'hui</div>', unsafe_allow_html=True)
    if _bfal:
        for m in _bfal:
            _nm = m.get("nom", m.get("id", "?"))
            _rul = m.get("rul_jours", "?")
            _stt = m.get("statut", "Alerte")
            _crit = (_stt == "Critique") or ((m.get("rul_jours") or 999) <= 3)
            _pbg, _pcl = ("#fee2e2", "#b91c1c") if _crit else ("#fef3c7", "#b45309")
            _act = ("Intervention immédiate — risque de panne imminente."
                    if _crit else "Planifier l'intervention sous 48h — surveiller les seuils.")
            st.markdown(
                f'<div style="background:#fff;border:1px solid #e6e8ec;border-radius:12px;padding:12px 16px;'
                f'margin-bottom:8px;display:flex;align-items:center;gap:12px;">'
                f'<span style="width:9px;height:9px;border-radius:50%;background:{_pcl};flex-shrink:0;"></span>'
                f'<div style="flex:1;min-width:0;"><span style="font-weight:600;color:#0f172a;">{_nm}</span> '
                f'<span class="bf-st" style="background:{_pbg};color:{_pcl};">RUL {_rul} j · {_stt}</span>'
                f'<div class="bf-meta" style="color:#64748b;">{_act}</div></div></div>',
                unsafe_allow_html=True)
    else:
        st.success("✅ Aucune machine en alerte — parc nominal.")

    # ── Mes interventions du poste ─────────────────────────────────────────────
    st.markdown('<div class="bf-lab">📋 Mes interventions du poste</div>', unsafe_allow_html=True)
    if _mes:
        _PILL = {"P1 - Critique": ("P1", "#fee2e2", "#b91c1c"),
                 "P2 - Haute":    ("P2", "#fef3c7", "#b45309"),
                 "P3 - Normale":  ("P3", "#f1f5f9", "#475569"),
                 "P4 - Basse":    ("P4", "#f1f5f9", "#94a3b8")}
        _STP = {"En retard": ("en retard", "#fee2e2", "#b91c1c"),
                "Planifiée": ("à faire", "#f1f5f9", "#475569"),
                "En cours":  ("en cours", "#dbeafe", "#1d4ed8")}
        _rows = ""
        for i in _mes:
            _pl, _pbg, _pcl = _PILL.get(i.get("priorite"), ("P—", "#f1f5f9", "#94a3b8"))
            _sl, _sbg, _scl = _STP.get(i.get("statut"), (i.get("statut") or "", "#f1f5f9", "#475569"))
            _mach = i.get("machine") or "?"
            _pieces = i.get("pieces") or i.get("composants") or ""
            _meta = f'📅 {i.get("date") or "TBD"}'
            if _pieces:
                _meta += f' · 🔩 {_pieces}'
            _rows += (
                f'<div class="bf-row">'
                f'<span class="bf-pil" style="background:{_pbg};color:{_pcl};">{_pl}</span>'
                f'<div style="flex:1;min-width:0;"><div style="color:#0f172a;">{i.get("titre","")} '
                f'<span style="color:#64748b;">· {_mach}</span></div>'
                f'<div class="bf-meta">{_meta}</div></div>'
                f'<span class="bf-st" style="background:{_sbg};color:{_scl};">{_sl}</span></div>')
        st.markdown(
            f'<div style="background:#fff;border:1px solid #e6e8ec;border-radius:12px;overflow:hidden;">{_rows}</div>',
            unsafe_allow_html=True)
    else:
        st.info("Aucune intervention assignée sur ce poste.")

    # ── Renforts disponibles ───────────────────────────────────────────────────
    st.markdown('<div class="bf-lab">👥 Renforts disponibles</div>', unsafe_allow_html=True)
    try:
        _eqp = nc.get_equipe()
    except Exception:
        _eqp = []
    if _eqp:
        _cards = ""
        for t in _eqp:
            _dispo = t.get("disponibilite") or "Inconnu"
            _dot = "#1baf7a" if _dispo == "Disponible" else (
                   "#b45309" if "interv" in _dispo.lower() else "#94a3b8")
            _pren, _nom = t.get("prenom", "") or "", t.get("nom", "") or ""
            _ini = (_pren[:1] + _nom[:1]).upper() or "?"
            _h = t.get("heures_restantes")
            _sub = t.get("specialite") or t.get("role") or ""
            if _h is not None:
                _sub += f' · {_h:.0f} h'
            _cards += (
                f'<div style="background:#fff;border:1px solid #e6e8ec;border-radius:12px;padding:11px 14px;'
                f'display:flex;align-items:center;gap:10px;">'
                f'<div style="width:34px;height:34px;border-radius:50%;background:#eff6ff;color:#1d4ed8;'
                f'display:flex;align-items:center;justify-content:center;font-size:0.8rem;font-weight:600;">{_ini}</div>'
                f'<div style="flex:1;min-width:0;"><div style="font-size:0.9rem;color:#0f172a;">{_pren} {_nom}</div>'
                f'<div style="font-size:0.77rem;color:#94a3b8;">{_dispo} · {_sub}</div></div>'
                f'<span style="width:9px;height:9px;border-radius:50%;background:{_dot};flex-shrink:0;"></span></div>')
        st.markdown(
            f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;">{_cards}</div>',
            unsafe_allow_html=True)
    else:
        st.info("Équipe indisponible.")

# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — K2 PROCÉDURE
# ════════════════════════════════════════════════════════════════════════════════
if tab2 is not None:
  with tab2:
    st.markdown("## 📘 Procédure d'intervention — Pompe P-17")
    st.caption("Machine instrumentée pilote · Unité B")

    st.markdown("""
    <style>
    .k2-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin:8px 0 14px;}
    .k2-tile{background:#f8fafc;border:1px solid #eef1f5;border-radius:12px;padding:11px 14px;}
    .k2-tile .l{font-size:0.74rem;color:#64748b;}
    .k2-tile .v{font-size:1.05rem;font-weight:700;color:#0f172a;margin-top:3px;}
    .k2-pill{font-size:0.75rem;padding:4px 12px;border-radius:20px;font-weight:600;white-space:nowrap;}
    .k2-epi{font-size:0.8rem;padding:4px 12px;border-radius:20px;display:inline-block;margin:3px;}
    </style>
    """, unsafe_allow_html=True)

    # Détection type d'anomalie depuis capteurs
    if c_temp > 75:
        anomalie = "Surchauffe"
    elif c_vib > 2.5:
        anomalie = "Vibration excessive"
    elif c_pres < 2.0:
        anomalie = "Pression insuffisante"
    else:
        anomalie = "Usure normale"

    # ── Statut en pastille ────────────────────────────────────────────────────
    _sbg = STATUS_BG.get(r_status, "#f1f5f9")
    _scl = STATUS_COLOR.get(r_status, "#475569")
    _smsg = {"Critique": "intervention immédiate requise",
             "Alerte": "planifier sous 48h",
             "Nominal": "aucune intervention requise — procédure de référence"}.get(r_status, "")
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:4px;flex-wrap:wrap;">'
        f'<span class="k2-pill" style="background:{_sbg};color:{_scl};">{r_status} · RUL {c_rul} j</span>'
        f'<span style="color:#64748b;font-size:0.9rem;">Anomalie : '
        f'<b style="color:#0f172a;">{anomalie}</b> — {_smsg}</span></div>',
        unsafe_allow_html=True,
    )

    # ── Ressources en tuiles ──────────────────────────────────────────────────
    duree_map = {
        "Surchauffe":            ("~35 min", "Roulement 6205-2RS", "2 tech."),
        "Vibration excessive":   ("~45 min", "Roulements + garnitures", "2 tech."),
        "Pression insuffisante": ("~20 min", "Garniture / joints", "1 tech."),
        "Usure normale":         ("~25 min", "Filtres + consommables", "1 tech."),
    }
    duree_est, pieces_est, equipe_est = duree_map.get(anomalie, ("~30 min", "À déterminer", "1 tech."))
    st.markdown(
        f'<div class="k2-tiles">'
        f'<div class="k2-tile"><div class="l">⏱ Durée</div><div class="v">{duree_est}</div></div>'
        f'<div class="k2-tile"><div class="l">🔩 Pièces</div><div class="v" style="font-size:0.9rem;">{pieces_est}</div></div>'
        f'<div class="k2-tile"><div class="l">👷 Équipe</div><div class="v">{equipe_est}</div></div>'
        f'<div class="k2-tile"><div class="l">📦 Kit</div><div class="v" style="font-size:0.95rem;">casier {P17_CONTEXT["kit_casier"]}</div></div>'
        f'<div class="k2-tile"><div class="l">💶 Coût d\'arrêt</div><div class="v">{P17_CONTEXT["cout_arret_eur_h"]} €/h</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── EPI par anomalie ──────────────────────────────────────────────────────
    EPI_PAR_ANOMALIE = {
        "Surchauffe": [("🪖", "casque", True), ("🧤", "gants anti-coupure", True),
                       ("🥽", "lunettes", True), ("👟", "chaussures S3", True),
                       ("🔥", "gants thermiques", True), ("👔", "combinaison ignifugée", False)],
        "Vibration excessive": [("🪖", "casque", True), ("🧤", "gants anti-coupure", True),
                                ("🥽", "lunettes", True), ("👟", "chaussures S3", True),
                                ("🎧", "bouchons anti-bruit", True)],
        "Pression insuffisante": [("🪖", "casque", True), ("🧤", "gants anti-coupure", True),
                                  ("🥽", "lunettes", True), ("👟", "chaussures S3", True),
                                  ("🧥", "combinaison étanche", True)],
        "Usure normale": [("🪖", "casque", True), ("🧤", "gants anti-coupure", True),
                          ("🥽", "lunettes", True), ("👟", "chaussures S3", True)],
    }
    epis = EPI_PAR_ANOMALIE.get(anomalie, EPI_PAR_ANOMALIE["Usure normale"])
    obligatoires = [e for e in epis if e[2]]
    recommandes  = [e for e in epis if not e[2]]
    _epi_h = "".join(f'<span class="k2-epi" style="background:#dcfce7;color:#166534;">{i} {l}</span>'
                     for i, l, _ in obligatoires)
    _rec_h = "".join(f'<span class="k2-epi" style="background:#fef9c3;color:#854d0e;">{i} {l} · recommandé</span>'
                     for i, l, _ in recommandes)
    st.markdown(
        f'<div style="background:#fff;border:1px solid #e6e8ec;border-radius:12px;padding:14px 16px;margin-bottom:12px;">'
        f'<div style="font-weight:600;margin-bottom:8px;color:#475569;font-size:0.86rem;">🦺 EPI obligatoires — {anomalie}</div>'
        f'<div>{_epi_h}{_rec_h}</div></div>',
        unsafe_allow_html=True,
    )

    # ── Checklist par phase (étapes adaptées à l'anomalie) ────────────────────
    _P1 = [
        "Mettre les EPI adaptés à l'anomalie",
        f"Récupérer le kit d'intervention au casier {P17_CONTEXT['kit_casier']}",
        "Vérifier la disponibilité des pièces en stock",
        "Prévenir le manager Sophie de l'arrêt",
    ]
    _P2 = [
        f"Consigner le disjoncteur {P17_CONTEXT['disjoncteur']} + cadenas",
        f"Fermer les vannes {P17_CONTEXT['vanne_amont']} / {P17_CONTEXT['vanne_aval']}",
        f"Purger la pression via {P17_CONTEXT['point_purge']}",
        "Apposer la plaque de consignation + VAT",
    ]
    _P3_BY = {
        "Surchauffe": [
            "Attendre refroidissement carter < 40 °C",
            "Déposer le carter avant (4 vis M12, clé 19)",
            f"Extraire le roulement {P17_CONTEXT['roulement_ref']} (extracteur hydraulique)",
            f"Contrôler l'arbre et regraisser ({P17_CONTEXT['graisse']})",
            f"Monter le roulement neuf, couple carter {P17_CONTEXT['couple_carter_nm']} N·m",
        ],
        "Vibration excessive": [
            "Contrôler le jeu axial / radial des paliers",
            "Déposer l'accouplement et le carter",
            "Remplacer roulements + garnitures mécaniques",
            "Réaligner l'accouplement au comparateur",
            "Contrôler le balourd et équilibrer",
        ],
        "Pression insuffisante": [
            "Vérifier le niveau et l'amorçage",
            "Déposer le corps de pompe",
            "Remplacer la garniture mécanique / joints",
            "Contrôler l'usure de la roue et des bagues",
            "Remonter et vérifier l'étanchéité",
        ],
        "Usure normale": [
            "Inspection visuelle générale",
            "Contrôle du serrage et des fixations",
            "Remplacer filtres et consommables",
            "Graissage des points de lubrification",
            "Relevé des paramètres de référence",
        ],
    }
    _P4 = [
        "Retirer les consignations LOTO",
        "Démarrage progressif + surveillance 15 min",
        f"Valider T < {P17_CONTEXT['valid_temp_max']} °C · vib < {P17_CONTEXT['valid_vib_max']} mm/s · P > {P17_CONTEXT['valid_pres_min']} bar",
    ]
    PHASES = [
        ("🦺 Phase 1 — préparation & EPI", "~5 min", _P1),
        ("🔒 Phase 2 — consignation LOTO", "~8 min", _P2),
        (f"🔧 Phase 3 — intervention · {anomalie.lower()}", "~18 min", _P3_BY.get(anomalie, _P3_BY["Usure normale"])),
        ("✅ Phase 4 — remise en service", "~7 min", _P4),
    ]

    st.markdown("### ✅ Checklist d'intervention")
    _all_states = []
    for _pi, (ptitle, ptime, psteps) in enumerate(PHASES):
        _pdone = sum(st.session_state.get(f"chk_{anomalie}_{_pi}_{j}", False) for j in range(len(psteps)))
        with st.container(border=True):
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<span style="font-weight:600;">{ptitle}</span>'
                f'<span style="font-size:0.8rem;color:#64748b;">{ptime} · {_pdone}/{len(psteps)}</span></div>',
                unsafe_allow_html=True)
            for j, stp in enumerate(psteps):
                _v = st.checkbox(stp, key=f"chk_{anomalie}_{_pi}_{j}")
                _all_states.append(_v)

    checked_total = sum(_all_states)
    step_total = len(_all_states)
    pct_done = checked_total / step_total if step_total else 0
    st.progress(pct_done, text=f"{checked_total}/{step_total} étapes validées")

    if pct_done == 1.0:
        st.success("✅ Procédure complète — passez à l'onglet **K3 Post-intervention**.")

    # ── Actions : réinitialiser + bon de travail ──────────────────────────────
    col_r, col_g = st.columns([1, 2])
    with col_r:
        if st.button("🔄 Réinitialiser", use_container_width=True):
            for _pi, (_, _, psteps) in enumerate(PHASES):
                for j in range(len(psteps)):
                    st.session_state.pop(f"chk_{anomalie}_{_pi}_{j}", None)
            st.rerun()
    with col_g:
        if st.button("📤 Générer et envoyer le bon de travail à Sophie",
                     use_container_width=True, type="primary"):
            _epi_txt = ", ".join(l for _, l, _ in obligatoires)
            _recap = (f"Ressources : durée {duree_est} · pièces {pieces_est} · {equipe_est} · "
                      f"kit casier {P17_CONTEXT['kit_casier']}\nEPI : {_epi_txt}\n\nÉTAPES :")
            for _pi, (ptitle, ptime, psteps) in enumerate(PHASES):
                _recap += f"\n\n{ptitle} ({ptime})"
                for j, stp in enumerate(psteps):
                    _dn = st.session_state.get(f"chk_{anomalie}_{_pi}_{j}", False)
                    _recap += f"\n  [{'x' if _dn else ' '}] {stp}"
            _recap += f"\n\nAvancement : {checked_total}/{step_total} étapes."
            try:
                from notify import envoyer_bon_de_travail
                with st.spinner("📤 Envoi du bon de travail au manager..."):
                    _bt = envoyer_bon_de_travail("Pompe P-17", anomalie, r_status, c_rul, _recap)
            except Exception as e:
                _bt = {"ok": False, "error": str(e)}
            if _bt.get("ok"):
                st.success(f"📧 Bon de travail envoyé à {_bt.get('ref', 'Sophie')} (manager) — {_bt.get('to', '')}")
            elif _bt.get("skipped"):
                st.info(f"📧 Non envoyé — {_bt.get('error', 'configuration manquante')}.")
            else:
                st.warning(f"📧 Échec de l'envoi : {_bt.get('error', '?')}")
            with st.expander("📋 Aperçu du bon de travail envoyé"):
                st.text(_recap)

# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 — K3 POST-INTERVENTION
# ════════════════════════════════════════════════════════════════════════════════
if tab3 is not None:
  with tab3:
    st.markdown("## 📝 Rapport post-intervention")

    if st.session_state.get("k3_submitted"):
        # ── Confirmation post-soumission ─────────────────────────────────────
        last = st.session_state.get("k3_last_payload", {})
        st.success("✅ Rapport enregistré dans Notion !")
        st.markdown(
            f'<div style="background:#f0fdf4;border-left:4px solid #22c55e;border-radius:6px;'
            f'padding:14px;margin:8px 0;">'
            f'<b>📋 Récapitulatif :</b><br>'
            f'Machine : <b>{last.get("machine","—")}</b> &nbsp;|&nbsp; '
            f'Type : <b>{last.get("type","—")}</b> &nbsp;|&nbsp; '
            f'Statut : <b>{last.get("statut","—")}</b><br>'
            f'<small style="color:#166534;">{last.get("actions","")[:120]}{"..." if len(last.get("actions","")) > 120 else ""}</small>'
            f'</div>',
            unsafe_allow_html=True,
        )
        # Notification Sophie
        st.markdown(
            '<div style="background:#eff6ff;border-left:4px solid #3b82f6;border-radius:6px;'
            'padding:12px;margin-top:8px;">'
            '📬 <b>Notification envoyée à Sophie (Manager Maintenance)</b><br>'
            '<small style="color:#1e40af;">Sophie a été alertée automatiquement — '
            'elle peut planifier la prochaine maintenance via son tableau de bord.</small>'
            '</div>',
            unsafe_allow_html=True,
        )
        if st.button("📋 Soumettre un nouveau rapport"):
            st.session_state["k3_submitted"] = False
            st.session_state.pop("k3_last_payload", None)
            st.rerun()
    else:
        st.caption("5 questions — moins de 3 minutes")
        with st.form("form_post_intervention", clear_on_submit=False):

            # Q1 — Machine
            f_machine = st.selectbox(
                "1️⃣  Machine concernée",
                ["Pompe P-17 (P-17)", "Compresseur C-03 (C-03)",
                 "Convoyeur CV-01 (CV-01)", "Autre"],
                index=0,
            )

            col_q2, col_q3, col_q4 = st.columns(3)
            with col_q2:
                # Q2 — Type
                f_type = st.selectbox(
                    "2️⃣  Type d'intervention",
                    ["Prédictive", "Préventive", "Préventive conditionnelle",
                     "Corrective", "Inspection"],
                )
            with col_q3:
                # Q3 — Statut final
                f_statut = st.selectbox(
                    "3️⃣  Statut final",
                    ["Réalisée", "En cours", "Planifiée", "Annulée"],
                )
            with col_q4:
                # Durée réelle (alimente le coût / les KPIs)
                f_duree = st.number_input(
                    "⏱ Durée réelle (h)", min_value=0.0, max_value=24.0, step=0.5, value=0.0
                )

            # Q4 — Actions
            f_actions = st.text_area(
                "4️⃣  Actions réalisées",
                placeholder="Ex : Remplacement roulement 6205-2RS, regraissage Mobilux EP2, remontage carter...",
                height=90,
            )

            # Q5 — Observations / résultat
            f_observations = st.text_area(
                "5️⃣  Résultat & observations",
                placeholder="Ex : Machine repart nominale — T=68°C, vib=0.9 mm/s, pression 4.2 bar...",
                height=70,
            )

            submitted = st.form_submit_button(
                "📤 Valider et notifier Sophie", use_container_width=True, type="primary"
            )

        if submitted:
            machine_label = f_machine.split("(")[0].strip()
            machine_id    = f_machine.split("(")[-1].rstrip(")") if "(" in f_machine else f_machine
            today         = datetime.date.today().isoformat()
            # Titre descriptif (Lot A-5) : évite les doublons génériques dans Notion
            _resume = (f_actions or "intervention").strip().split("\n")[0][:40]
            payload = {
                "titre":        f"{f_type} {machine_id} — {_resume} ({today})",
                "machine":      machine_label,
                "type":         f_type,
                "statut":       f_statut,
                "technicien":   "Lionel Dumont",
                "date":         today,
                "date_realisee": today,
                "duree_reelle": float(f_duree),   # saisi par le technicien
                "actions":      f_actions,
                "pieces":       "",
                "cause_racine": "",
                "cout":         0.0,
                "rul_avant":    c_rul,   # injecté automatiquement depuis le simulateur
                "observations": f_observations,
            }
            try:
                with st.spinner("Enregistrement dans Notion..."):
                    nc.create_intervention(payload)
                    nc.get_historique.clear()
                st.session_state["k3_submitted"]    = True
                st.session_state["k3_last_payload"] = payload
                st.balloons()
                st.rerun()
            except Exception as e:
                st.error(f"Erreur Notion : {e}")
                st.info("💡 Vérifiez que le token NOTION_TOKEN est configuré dans les secrets Streamlit.")

# ════════════════════════════════════════════════════════════════════════════════
# TAB 4 — K4 ARBITRAGE
# ════════════════════════════════════════════════════════════════════════════════
if tab4 is not None:
  with tab4:
    st.markdown("## ⚖️ Arbitrage multi-machine")
    st.caption("Aide à la décision : quelle machine traiter en priorité ?")

    # Dégradation simulée selon le statut du simulateur (pour P-17)
    _DEG_BY_STATUS = {"Critique": 88, "Alerte": 45, "Nominal": 8}

    def score_alerte(machine: dict) -> float:
        """Calcule un score d'urgence 0–100 (100 = urgence maximale)."""
        rul  = machine.get("rul_jours") or RUL_NOMINAL
        deg  = machine.get("score_degradation") or 0
        rul_score = max(0, (1 - rul / RUL_NOMINAL)) * 60
        deg_score = (deg / 100) * 40
        return round(rul_score + deg_score, 1)

    try:
        all_machines = nc.get_machines()
        if not all_machines:
            raise ValueError("Aucune machine Notion")
    except Exception:
        # Fallback — données fictives représentatives
        all_machines = [
            {"id": "P-17",  "nom": "Pompe P-17",         "statut": "Alerte",
             "rul_jours": 18, "score_degradation": 45, "temperature": 77.2, "vibration": 2.8,
             "unite": "Unité B", "responsable": "Lionel Dumont"},
            {"id": "C-03",  "nom": "Compresseur C-03",   "statut": "Alerte",
             "rul_jours": 20, "score_degradation": 38, "temperature": 65.1, "vibration": 1.4,
             "unite": "Ligne 1", "responsable": "Marc Lefebvre"},
            {"id": "M-08",  "nom": "Moteur M-08",        "statut": "Nominal",
             "rul_jours": 100, "score_degradation": 8, "temperature": 52.0, "vibration": 0.6,
             "unite": "Ligne 2", "responsable": "Marc Lefebvre"},
        ]

    # ── Aligner P-17 avec le simulateur (K0) ──────────────────────────────────
    # Le simulateur est la source de vérité pour P-17.
    # On écrase les valeurs statiques Notion avec les valeurs temps réel.
    for m in all_machines:
        if "P-17" in (m.get("id") or "") or "P-17" in (m.get("nom") or ""):
            m["rul_jours"]        = c_rul
            m["statut"]           = r_status
            m["temperature"]      = c_temp
            m["vibration"]        = c_vib
            m["score_degradation"] = _DEG_BY_STATUS.get(r_status, 20)
    # ──────────────────────────────────────────────────────────────────────────

    # Trier par score décroissant et prendre les 2 premières
    ranked = sorted(all_machines, key=score_alerte, reverse=True)
    top2   = ranked[:2] if len(ranked) >= 2 else ranked

    # Affichage comparatif
    if len(top2) >= 2:
        m_a, m_b = top2[0], top2[1]
        score_a, score_b = score_alerte(m_a), score_alerte(m_b)

        col_a, col_mid, col_b = st.columns([2, 1, 2])
        for col, m, score in [(col_a, m_a, score_a), (col_b, m_b, score_b)]:
            statut_m = m.get("statut") or "Nominal"
            if statut_m == "Critique" or score >= 60:
                bg, score_color, badge = "#fee2e2", "#b91c1c", "🔴 Critique"
            elif statut_m == "Alerte" or score >= 30:
                bg, score_color, badge = "#fef3c7", "#b45309", "🟠 Alerte"
            else:
                bg, score_color, badge = "#f0fdf4", "#166534", "🟢 Nominal"
            with col:
                st.markdown(
                    f'<div style="background:{bg};border-radius:10px;padding:20px;text-align:center;">'
                    f'<div style="font-size:1.3rem;font-weight:700;">{m.get("nom","?")}</div>'
                    f'<div style="color:#64748b;">{m.get("id","")} — {m.get("unite","")}</div>'
                    f'<div style="font-size:0.8rem;margin-top:4px;">{badge}</div>'
                    f'<hr style="margin:10px 0;">'
                    f'<div style="font-size:2rem;font-weight:800;color:{score_color};">'
                    f'{score}<span style="font-size:1rem;">/100</span></div>'
                    f'<div style="font-size:0.82rem;color:#475569;">Score urgence</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                _t = m.get("temperature")
                _v = m.get("vibration")
                _deg = m.get("score_degradation")
                st.markdown("")
                st.markdown(f"**RUL :** {m.get('rul_jours','?')} j")
                st.markdown(f"**Dégradation :** {f'{_deg:.0f} %' if _deg is not None else 'n/a'}")
                st.markdown(f"**Statut :** {statut_m}")
                st.markdown(f"**Température :** {f'{_t:.1f} °C' if _t is not None else 'n/a'}")
                st.markdown(f"**Vibration :** {f'{_v:.2f} mm/s' if _v is not None else 'n/a'}")
                st.markdown(f"**Responsable :** {m.get('responsable','?')}")

        with col_mid:
            st.markdown("<br><br><br><br>", unsafe_allow_html=True)
            st.markdown(
                '<div style="text-align:center;font-size:2rem;color:#94a3b8;">VS</div>',
                unsafe_allow_html=True,
            )

        # Recommandation
        st.markdown("---")
        winner = m_a if score_a >= score_b else m_b
        delta  = abs(score_a - score_b)
        if delta >= 20:
            st.error(
                f"🔴 **Intervention prioritaire : {winner.get('nom')}** — Score d'urgence {score_alerte(winner)}/100. "
                f"Différence significative ({delta:.0f} pts) : traitement immédiat recommandé."
            )
        elif delta >= 8:
            st.warning(
                f"🟡 **Privilégier : {winner.get('nom')}** — Score d'urgence légèrement supérieur ({delta:.0f} pts). "
                f"Concertez-vous avec Sophie pour la planification."
            )
        else:
            st.info(
                f"🔵 **Scores proches** ({delta:.0f} pts d'écart). Consultez Sophie (Manager) pour arbitrer "
                f"selon les contraintes de production et disponibilité équipe."
            )

        # Graphique comparatif
        st.markdown("---")
        st.markdown("### 📊 Comparaison des indicateurs")
        indicators = ["Score urgence", "Dégradation (%)", "Température (°C/100)", "Vibration (×10)"]
        vals_a = [
            score_a,
            m_a.get("score_degradation") or 0,
            (m_a.get("temperature") or 0) / 100 * 100,
            (m_a.get("vibration") or 0) * 10,
        ]
        vals_b = [
            score_b,
            m_b.get("score_degradation") or 0,
            (m_b.get("temperature") or 0) / 100 * 100,
            (m_b.get("vibration") or 0) * 10,
        ]

        fig = go.Figure(data=[
            go.Bar(name=m_a.get("nom","M1"), x=indicators, y=vals_a,
                   marker_color="#ef4444", opacity=0.85),
            go.Bar(name=m_b.get("nom","M2"), x=indicators, y=vals_b,
                   marker_color="#3b82f6", opacity=0.85),
        ])
        fig.update_layout(
            barmode="group",
            legend=dict(orientation="h", y=1.1),
            paper_bgcolor="white", plot_bgcolor="white",
            margin=dict(l=0, r=0, t=30, b=0),
            height=300,
        )
        st.plotly_chart(fig, use_container_width=True)

    elif len(top2) == 1:
        st.info(f"Une seule machine disponible : **{top2[0].get('nom')}** — Score {score_alerte(top2[0])}/100.")
    else:
        st.warning("Aucune machine à comparer.")

    # Toutes les machines
    with st.expander("📋 Classement complet du parc", expanded=False):
        for i, m in enumerate(ranked, 1):
            score = score_alerte(m)
            icon = "🔴" if score >= 60 else ("🟡" if score >= 30 else "🟢")
            st.markdown(f"{i}. {icon} **{m.get('nom')}** — Score {score}/100 — RUL {m.get('rul_jours','?')} j")

# ── AUTO-REFRESH — repli uniquement si les fragments ne sont pas supportés ────
# (Lot D) Avec fragment, seul le bloc K0 se rafraîchit → plus de saut de page.
if (not _HAS_FRAGMENT) and st.session_state.running:
    time.sleep(_refresh_s)
    st.rerun()
