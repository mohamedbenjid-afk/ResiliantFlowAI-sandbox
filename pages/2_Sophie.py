# pages/2_Sophie.py
# Agent Sophie — Manager Maintenance
# S0 Alertes · S1 Simulateur · S2 Affectation · S3 Rapport

import time
import datetime

import plotly.graph_objects as go
import streamlit as st

import notion_client as nc
from shared_state import COMMON_CSS, init_session_state, update_sensors

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Sophie — Planification", page_icon="📋", layout="wide")
st.markdown(COMMON_CSS, unsafe_allow_html=True)

# ── BANNIÈRE ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="escp-banner">
    🎓 <b>Projet de Fin d'Études ESCP</b> &nbsp;|&nbsp;
    ⚙️ Sujet : <i>Maintenance Prescriptive &amp; Industrie 4.0</i>
</div>
""", unsafe_allow_html=True)

# ── SESSION STATE & CAPTEURS ──────────────────────────────────────────────────
init_session_state()
c_temp, c_vib, c_pres, c_cur, c_rul, r_status, rul_pct = update_sensors()

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.page_link("streamlit_home.py", label="← Retour à l'accueil", use_container_width=True)
    st.markdown("---")
    st.markdown("### 📋 Sophie — Manager Maintenance")
    st.caption("Machine surveillée : **Pompe P-17** — Unité B")
    st.markdown("---")

    running_label = "⏸ Pause simulation" if st.session_state.running else "▶ Reprendre"
    if st.button(running_label, use_container_width=True):
        st.session_state.running = not st.session_state.running
        st.rerun()

    st.markdown("---")
    st.caption(f"Horodatage système : t = {st.session_state.tick}")
    st.caption(f"RUL estimé : {c_rul}h ({r_status})")

# ── COULEURS STATUT ───────────────────────────────────────────────────────────
STATUS_COLOR = {"Nominal": "#166534", "Alerte": "#b45309", "Critique": "#b91c1c"}
STATUS_BG    = {"Nominal": "#dcfce7", "Alerte": "#fef3c7", "Critique": "#fee2e2"}
STATUS_BORDER= {"Nominal": "#86efac", "Alerte": "#fde047", "Critique": "#fca5a5"}

# ── TABS ──────────────────────────────────────────────────────────────────────
tab0, tab1, tab2, tab3 = st.tabs([
    "📡 S0 — Alertes actives",
    "🔮 S1 — Simulateur d'impact",
    "👥 S2 — Affectation équipe",
    "📊 S3 — Rapport hebdo",
])

# ════════════════════════════════════════════════════════════════════════════════
# TAB 0 — S0 ALERTES ACTIVES
# ════════════════════════════════════════════════════════════════════════════════
with tab0:
    st.markdown("## 📡 Alertes actives — Parc machines")
    st.caption("Machines classées par urgence décroissante · Données temps réel Notion")

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _urgency_rank(statut: str, rul: float) -> tuple:
        """Clé de tri : (rang statut, RUL) — plus petit = plus urgent."""
        rank = {"Critique": 0, "Alerte": 1, "Hors service": 2}.get(statut, 3)
        return (rank, float(rul or 999))

    def _statut_from_rul(rul: float) -> str:
        if rul <= 24:   return "Critique"
        if rul <= 48:   return "Alerte"
        return "Nominal"

    def _card_style(statut: str) -> tuple:
        """Retourne (bg, border, icon, badge_color) selon statut."""
        if statut == "Critique":
            return "#fee2e2", "#ef4444", "🔴", "#b91c1c"
        elif statut == "Alerte":
            return "#fef3c7", "#f59e0b", "🟠", "#b45309"
        elif statut == "Hors service":
            return "#f3f4f6", "#6b7280", "⚫", "#374151"
        else:
            return "#f0fdf4", "#86efac", "🟢", "#166534"

    def _recommandation(statut: str, rul: float, nom: str) -> str:
        if statut == "Critique":
            return f"⚡ Intervention immédiate — RUL {rul:.0f}h, risque de panne imminente"
        elif statut == "Alerte":
            return f"⏰ Planifier intervention sous 48h — RUL {rul:.0f}h restantes"
        elif statut == "Hors service":
            return f"🔧 Hors service — attendre validation technique avant remise en route"
        else:
            return f"✅ Surveillance standard — RUL {rul:.0f}h, prochain contrôle selon planning"

    # ── Chargement machines depuis Notion ────────────────────────────────────
    try:
        machines = nc.get_machines()
        if not machines:
            raise ValueError("Liste vide")

        # Override P-17 avec valeurs simulateur (source de vérité temps réel)
        for m in machines:
            nom = m.get("nom", "")
            mid = m.get("id", "")
            if "P-17" in nom or "P-17" in mid:
                m["rul_jours"] = c_rul
                m["statut"]    = r_status

        # Convertir rul_jours → rul_heures pour cohérence avec simulateur
        for m in machines:
            if "rul_heures" not in m:
                rul_j = m.get("rul_jours") or 0
                m["rul_heures"] = rul_j  # simulateur retourne déjà en heures pour P-17

        notion_ok = True

    except Exception as e:
        notion_ok = False
        # Fallback données fictives représentatives
        machines = [
            {"id": "P-17",  "nom": "Pompe P-17",          "statut": r_status,    "rul_heures": c_rul,  "unite": "Unité B",   "responsable": "Sophie M."},
            {"id": "C-03",  "nom": "Compresseur C-03",     "statut": "Alerte",    "rul_heures": 36,     "unite": "Ligne 1",   "responsable": "Marc D."},
            {"id": "M-08",  "nom": "Moteur M-08",          "statut": "Nominal",   "rul_heures": 210,    "unite": "Ligne 2",   "responsable": "Fatima R."},
            {"id": "CV-01", "nom": "Convoyeur CV-01",      "statut": "Nominal",   "rul_heures": 320,    "unite": "Atelier A", "responsable": "Marc D."},
        ]

    if not notion_ok:
        st.warning("⚠️ Notion indisponible — données de démonstration affichées", icon="⚠️")

    # Trier par urgence décroissante
    machines_sorted = sorted(
        machines,
        key=lambda m: _urgency_rank(
            m.get("statut") or _statut_from_rul(m.get("rul_heures") or 999),
            m.get("rul_heures") or m.get("rul_jours") or 999
        )
    )

    # ── KPI résumé en haut ───────────────────────────────────────────────────
    nb_critique = sum(1 for m in machines if (m.get("statut") or "") == "Critique")
    nb_alerte   = sum(1 for m in machines if (m.get("statut") or "") == "Alerte")
    nb_nominal  = sum(1 for m in machines if (m.get("statut") or "") not in ("Critique", "Alerte", "Hors service"))
    nb_total    = len(machines)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🏭 Machines surveillées", nb_total)
    k2.metric("🔴 Critiques",  nb_critique, delta=None)
    k3.metric("🟠 En alerte",  nb_alerte,   delta=None)
    k4.metric("🟢 Nominales",  nb_nominal,  delta=None)

    st.markdown("---")

    # ── Liste des machines ────────────────────────────────────────────────────
    if not machines_sorted:
        st.info("Aucune machine trouvée.")
    else:
        for m in machines_sorted:
            nom    = m.get("nom", "?")
            mid    = m.get("id",  "?")
            rul    = float(m.get("rul_heures") or m.get("rul_jours") or 0)
            statut = m.get("statut") or _statut_from_rul(rul)
            unite  = m.get("unite", "—")
            resp   = m.get("responsable", "—")
            is_p17 = "P-17" in mid or "P-17" in nom

            bg, border, icon, badge_color = _card_style(statut)
            recommandation = _recommandation(statut, rul, nom)

            # Barre de progression RUL (sur 100h max pour lisibilité)
            rul_bar_pct = max(0.0, min(1.0, rul / 100.0))
            rul_bar_color = badge_color

            # Valeur RUL affichée avec unité adaptée
            if rul >= 48:
                rul_label = f"{rul:.0f}h ({rul/24:.1f}j)"
            else:
                rul_label = f"{rul:.0f}h"

            with st.container():
                st.markdown(
                    f'<div style="background:{bg};border-left:5px solid {border};'
                    f'border-radius:8px;padding:14px 18px;margin-bottom:10px;">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                    f'<div>'
                    f'  <span style="font-size:1.05rem;font-weight:700;">{icon} {nom}</span>'
                    f'  <span style="font-size:0.8rem;color:#64748b;margin-left:10px;">{mid} — {unite}</span>'
                    f'  {"<span style=\"font-size:0.75rem;background:#dbeafe;color:#1d4ed8;border-radius:4px;padding:2px 6px;margin-left:6px;\">⚡ SIMULATEUR ACTIF</span>" if is_p17 else ""}'
                    f'</div>'
                    f'<div style="text-align:right;">'
                    f'  <span style="font-size:0.85rem;font-weight:700;color:{badge_color};">{statut}</span>'
                    f'  <span style="font-size:0.8rem;color:#64748b;margin-left:10px;">RUL : <b>{rul_label}</b></span>'
                    f'</div>'
                    f'</div>'
                    f'<div style="margin-top:8px;background:#e2e8f0;border-radius:4px;height:6px;">'
                    f'  <div style="width:{rul_bar_pct*100:.1f}%;background:{rul_bar_color};'
                    f'  height:6px;border-radius:4px;transition:width 0.3s;"></div>'
                    f'</div>'
                    f'<div style="display:flex;justify-content:space-between;margin-top:8px;">'
                    f'  <span style="font-size:0.83rem;color:#374151;">{recommandation}</span>'
                    f'  <span style="font-size:0.78rem;color:#94a3b8;">Responsable : {resp}</span>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ── Graphique synthèse RUL par machine ───────────────────────────────────
    st.markdown("---")
    st.markdown("### 📊 Vue synthétique — RUL par machine")

    noms   = [m.get("nom", "?") for m in machines_sorted]
    ruls   = [float(m.get("rul_heures") or m.get("rul_jours") or 0) for m in machines_sorted]
    statuts = [m.get("statut") or _statut_from_rul(r) for m, r in zip(machines_sorted, ruls)]

    bar_colors = []
    for s in statuts:
        if s == "Critique":   bar_colors.append("rgba(239,68,68,0.85)")
        elif s == "Alerte":   bar_colors.append("rgba(245,158,11,0.85)")
        elif s == "Hors service": bar_colors.append("rgba(107,114,128,0.85)")
        else:                 bar_colors.append("rgba(34,197,94,0.85)")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=noms,
        y=ruls,
        marker_color=bar_colors,
        text=[f"{r:.0f}h" for r in ruls],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>RUL : %{y:.0f}h<extra></extra>",
    ))
    # Seuils d'alerte
    fig.add_hline(y=24, line_dash="dot", line_color="rgba(239,68,68,0.7)",
                  annotation_text="Critique (24h)", annotation_position="right")
    fig.add_hline(y=48, line_dash="dot", line_color="rgba(245,158,11,0.7)",
                  annotation_text="Alerte (48h)", annotation_position="right")

    fig.update_layout(
        height=300,
        margin=dict(l=0, r=60, t=20, b=0),
        paper_bgcolor="white",
        plot_bgcolor="white",
        yaxis=dict(
            title="RUL (heures)",
            showgrid=True,
            gridcolor="rgba(0,0,0,0.06)",
            zeroline=False,
        ),
        xaxis=dict(showgrid=False),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════════════════════════════════════════════
# TAB 1 — S1 SIMULATEUR D'IMPACT (placeholder)
# ════════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("## 🔮 Simulateur d'impact — *Sprint 3*")
    st.info("Cet onglet sera développé lors du Sprint 3 (US-S1).")

# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — S2 AFFECTATION ÉQUIPE (placeholder)
# ════════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("## 👥 Affectation équipe — *Sprint 3*")
    st.info("Cet onglet sera développé lors du Sprint 3 (US-S2).")

# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 — S3 RAPPORT HEBDO (placeholder)
# ════════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("## 📊 Rapport hebdomadaire — *Sprint 4*")
    st.info("Cet onglet sera développé lors du Sprint 4 (US-S3).")

# ── AUTO-REFRESH ──────────────────────────────────────────────────────────────
if st.session_state.running:
    time.sleep(1)
    st.rerun()
