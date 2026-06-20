import streamlit as st
import plotly.graph_objects as go
import time
import sys, os
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from shared_state import init_session_state, update_sensors, COMMON_CSS

# ── CONFIG PAGE ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Antoine — Indicateurs Stratégiques", page_icon="📊", layout="wide")
st.markdown(COMMON_CSS, unsafe_allow_html=True)

# ── SESSION STATE & CAPTEURS ──────────────────────────────────────────────────
init_session_state()
c_temp, c_vib, c_pres, c_cur, c_rul, r_status, rul_percentage = update_sensors()

# Initialisation session_state pour persister les résultats
for key in ["antoine_result", "antoine_pdf_bytes", "antoine_pdf_ref"]:
    if key not in st.session_state:
        st.session_state[key] = None

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
st.sidebar.markdown("""
    <div class="escp-banner">
        🎓 <b>Projet de Fin d'Études ESCP</b><br>
        ⚙️ <i>Maintenance Prescriptive & Industrie 4.0</i>
    </div>
""", unsafe_allow_html=True)

st.sidebar.markdown("### ResilientFlow AI\n*Couche Prescriptive v1*")

if st.sidebar.button("⏸️ Pause / ▶️ Reprendre", use_container_width=True):
    st.session_state.running = not st.session_state.running

st.sidebar.caption("Statut machine : Pompe P-17 (Unité B)")
st.sidebar.caption("Horodatage système : t = " + str(st.session_state.tick))
st.sidebar.caption("RUL estimé : " + str(c_rul) + " heures")
st.sidebar.page_link("streamlit_home.py", label="⬅️ Retour à l'accueil", use_container_width=True)

# ── CONTENU PRINCIPAL ─────────────────────────────────────────────────────────
st.markdown("### 📊 Indicateurs Stratégiques et ROI Financement — Antoine")
st.markdown("*Analyse multi-machine, MTBF/MTTR, simulation CAPEX vs OPEX et fiche CODIR.*")

# ── KPIs statiques rapides ────────────────────────────────────────────────────
k1, k2, k3 = st.columns(3)
k1.metric("Pertes de production évitées", "312 000 €",  delta="+14 alertes anticipées")
k2.metric("Taux de Disponibilité (OEE)",  "96.4 %",     delta="+2.1 % vs Année N-1")
k3.metric("ROI Couche Prescriptive",      "7.6 x",      delta="Target CODIR dépassée")

st.markdown("---")

# ── Graphique scénario budgétaire (statique, illustratif) ────────────────────
st.markdown("#### 🔮 Projection financière illustrative — Pompe P-17")

col_strat, col_graph = st.columns([1, 2])
with col_strat:
    mode_invest = st.selectbox(
        "Simuler un scénario budgétaire :",
        [
            "Conserver la pompe P-17 (Continuer en maintenance prescriptive)",
            "Investir dans le remplacement par la pompe neuve AlphaFlow-18",
        ]
    )
    st.info(
        "**Avis de l'agent AI :** Bien que la couche prescriptive repousse la panne de la P-17, "
        "l'équipement approche de sa limite de fatigue structurelle."
    )

with col_graph:
    timeline = ["Actuel", "Année +1", "Année +2", "Année +3"]
    fig = go.Figure()
    if "Conserver" in mode_invest:
        fig.add_trace(go.Scatter(
            x=timeline, y=[12000, 29000, 55000, 89000],
            name="Coût OPEX Cumulé", line=dict(color="#f59e0b", width=3)
        ))
        fig.update_layout(title="Projection dépenses cumulées (€)", height=200,
                          margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("🔴 **Alerte :** Explosion des coûts de rechange à partir de l'année +2.")
    else:
        fig.add_trace(go.Scatter(
            x=timeline, y=[80000, 82000, 84000, 86000],
            name="Plan CAPEX amorti", line=dict(color="#10b981", width=3)
        ))
        fig.update_layout(title="Frais acquisition et intégration (€)", height=200,
                          margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("✅ Point mort financier atteint dès le 14ème mois.")

st.markdown("---")

# ── ANALYSE AGENT ANTOINE ─────────────────────────────────────────────────────
st.markdown("#### 🤖 Analyse stratégique complète — Agent Antoine")
st.write(
    "L'agent interroge toutes les machines du parc, calcule le MTBF/MTTR réel depuis "
    "l'historique Notion, simule 3 scénarios financiers sur 3 ans et génère une fiche CODIR PDF."
)

col_btn1, col_btn2 = st.columns(2)

with col_btn1:
    if st.button("▶️ Lancer l'analyse stratégique", use_container_width=True):
        st.session_state.running = False
        with st.spinner("L'agent Antoine interroge le parc machines et simule les scénarios…"):
            try:
                from agents.agent_antoine import run_agent_antoine
                result = run_agent_antoine(equipement="Pompe P-17", c_rul=int(c_rul))
                st.session_state.antoine_result    = result
                st.session_state.antoine_pdf_bytes = None  # reset PDF
                st.session_state.antoine_pdf_ref   = None
                st.success("✅ Analyse complète générée.")
            except Exception as e:
                st.error(f"❌ Erreur agent : {e}")
                st.exception(e)

with col_btn2:
    if st.button("📄 Générer la fiche CODIR PDF", use_container_width=True,
                 disabled=st.session_state.antoine_result is None):
        st.session_state.running = False
        with st.spinner("Génération du PDF CODIR en cours…"):
            try:
                from utils.pdf_codir import generate_codir_pdf
                pdf_bytes = generate_codir_pdf(st.session_state.antoine_result)
                from datetime import date
                ref = f"CODIR_RF_PompeP17_{date.today().strftime('%Y%m%d')}_{datetime.now().strftime('%H%M')}"
                st.session_state.antoine_pdf_bytes = pdf_bytes
                st.session_state.antoine_pdf_ref   = ref
                st.success(f"✅ Fiche CODIR générée — `{ref}`")
            except Exception as e:
                st.error(f"❌ Erreur génération PDF : {e}")
                st.exception(e)

# ── Affichage résultat analyse ────────────────────────────────────────────────
if st.session_state.antoine_result:
    result = st.session_state.antoine_result

    # Portfolio machines
    portfolio = result.get("portfolio")
    if portfolio and portfolio.get("ranking"):
        st.markdown("##### 🏭 Portfolio machines — Ranking par risque")
        cols_rank = st.columns(min(4, len(portfolio["ranking"])))
        for i, m in enumerate(portfolio["ranking"][:4]):
            with cols_rank[i]:
                niveau = m["niveau_risque"]
                color  = ("🔴" if "CRITIQUE" in niveau else
                          "🟠" if "ÉLEVÉ"    in niveau else
                          "🟡" if "MODÉRÉ"   in niveau else "🟢")
                st.metric(
                    label=m["machine"],
                    value=f"RUL : {m['rul_jours']} j",
                    delta=f"Score risque : {m['score_risque']}/100",
                    delta_color="inverse" if m["score_risque"] > 50 else "normal"
                )
                st.caption(f"{color} {niveau} | {m['unite']}")

    # Historique KPIs
    hist = result.get("historique")
    if hist:
        st.markdown("##### 📈 KPIs de fiabilité calculés depuis l'historique")
        hk1, hk2, hk3, hk4 = st.columns(4)
        hk1.metric("MTBF", f"{hist.get('mtbf_jours', '—')} j",     help="Mean Time Between Failures")
        hk2.metric("MTTR", f"{hist.get('mttr_heures', '—')} h",    help="Mean Time To Repair")
        hk3.metric("ROI Prescriptif", f"× {hist.get('roi_maintenance', '—')}")
        hk4.metric("OPEX cumulé", f"{hist.get('cout_total_maintenance_eur', 0):,.0f} €")

    # Scénarios NPV
    sc = result.get("scenarios")
    if sc and sc.get("scenarios"):
        st.markdown("##### 💰 Simulation 3 scénarios — NPV sur 3 ans")
        sc_data = sc["scenarios"]
        sa, sb, sc3 = st.columns(3)
        a = sc_data.get("A_correctif_pur", {})
        b = sc_data.get("B_maintien_prescriptif", {})
        c = sc_data.get("C_remplacement", {})

        with sa:
            st.error(f"**A — Correctif pur**\n\nCoût total : **{a.get('cout_total_eur',0):,.0f} €**\n\nNPV : {a.get('npv_eur',0):,.0f} €")
        with sb:
            st.success(f"**B — Prescriptif (actuel)**\n\nCoût total : **{b.get('cout_total_eur',0):,.0f} €**\n\nNPV : {b.get('npv_eur',0):,.0f} €")
        with sc3:
            st.info(f"**C — Remplacement**\n\nCoût total : **{c.get('cout_total_eur',0):,.0f} €**\n\nPoint mort : {c.get('payback_vs_correctif_mois','—')} mois")

        reco = sc.get("recommandation_financiere", "")
        eco  = sc.get("economie_prescriptif_vs_correctif_eur", 0)
        st.success(f"✅ **Recommandation agent :** {reco} — Économie vs correctif : **{eco:,.0f} €**")

    # Analyse LLM
    analyse = result.get("analyse", "")
    if analyse:
        with st.expander("📝 Analyse complète de l'agent Antoine", expanded=False):
            st.markdown(analyse)

# ── Bouton téléchargement PDF (persistant) ────────────────────────────────────
if st.session_state.antoine_pdf_bytes is not None:
    st.download_button(
        label="⬇️ Télécharger la fiche CODIR PDF",
        data=st.session_state.antoine_pdf_bytes,
        file_name=f"{st.session_state.antoine_pdf_ref}.pdf",
        mime="application/pdf",
        use_container_width=True,
        key="dl_codir_pdf",
    )

# ── AUTO-REFRESH ──────────────────────────────────────────────────────────────
if st.session_state.running:
    time.sleep(1)
    st.rerun()
