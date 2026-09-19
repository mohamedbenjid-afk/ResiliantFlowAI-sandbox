import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import time
import sys, os
from datetime import datetime, date

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from shared_state import init_session_state, update_sensors, COMMON_CSS
import notion_client as nc


def _fmt_fr(v, decimals: int = 0) -> str:
    """Formate un nombre avec points comme séparateurs de milliers (ex: 2.905),
    utilisée dans tous les onglets pour un affichage cohérent des chiffres."""
    if v is None:
        return "—"
    try:
        s = f"{v:,.{decimals}f}"
    except (TypeError, ValueError):
        return str(v)
    return s.replace(",", ".")


def _kpi_card(col, label: str, value: str, border_color: str, bg_color: str, help_text: str = ""):
    """Carte KPI colorée réutilisable (onglets A0 et A2). help_text optionnel
    affiché comme info-bulle native du navigateur (survol), pour ne pas perdre
    l'équivalent du paramètre help= de st.metric()."""
    title_attr = f' title="{help_text}"' if help_text else ""
    col.markdown(
        f'''<div{title_attr} style="background:{bg_color};border-left:4px solid {border_color};
        border-radius:8px;padding:12px 14px;min-height:78px;">
        <div style="font-size:0.78rem;color:#4b5563;margin-bottom:4px;">{label}</div>
        <div style="font-size:1.5rem;font-weight:700;color:#111827;">{value}</div>
        </div>''',
        unsafe_allow_html=True
    )


def _risk_card(col, machine: str, rul: str, score, niveau: str, unite: str):
    """Carte portfolio colorée selon le niveau de risque (onglet A1)."""
    if "CRITIQUE" in niveau:
        border, bg, icon = "#dc2626", "#fee2e2", "🔴"
    elif "ÉLEVÉ" in niveau:
        border, bg, icon = "#ea580c", "#ffedd5", "🟠"
    elif "MODÉRÉ" in niveau:
        border, bg, icon = "#eab308", "#fef9c3", "🟡"
    else:
        border, bg, icon = "#16a34a", "#dcfce7", "🟢"
    col.markdown(
        f'''<div style="background:{bg};border-left:4px solid {border};
        border-radius:8px;padding:12px 14px;min-height:118px;">
        <div style="font-size:0.78rem;color:#4b5563;font-weight:600;margin-bottom:4px;">{machine}</div>
        <div style="font-size:1.4rem;font-weight:700;color:#111827;">RUL : {rul} j</div>
        <div style="font-size:0.82rem;color:#374151;margin-top:2px;">↑ Score risque : {score}/100</div>
        <div style="font-size:0.8rem;color:#4b5563;margin-top:8px;">{icon} {niveau} | {unite}</div>
        </div>''',
        unsafe_allow_html=True
    )


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

# US-A0 : sidebar corrigée — RUL + statut sur une seule ligne, avec code couleur
_sidebar_icon = {"Nominal": "🟢", "Alerte": "🟠", "Critique": "🔴"}.get(r_status, "⚪")
st.sidebar.caption(f"{_sidebar_icon} RUL estimé : {c_rul}h — **{r_status}**")

st.sidebar.page_link("streamlit_home.py", label="⬅️ Retour à l'accueil", use_container_width=True)

# ── CONTENU PRINCIPAL ─────────────────────────────────────────────────────────
st.markdown("### 📊 Indicateurs Stratégiques et ROI Financement — Antoine")
st.markdown("*Analyse multi-machine, MTBF/MTTR, simulation CAPEX vs OPEX et fiche CODIR.*")

# ── US-A1 : Alerte immédiate temps réel (bandeau toujours visible) ────────────
if r_status in ("Alerte", "Critique"):
    _icon = "🔴" if r_status == "Critique" else "🟠"
    st.error(
        f"{_icon} **Alerte {r_status} — Pompe P-17 (Unité B)**  \n"
        f"RUL restant : **{c_rul} h** ({rul_percentage:.0f}% de vie restante).  \n"
        f"**Impact estimé :** risque d'arrêt de production non planifié.  \n"
        f"**Recommandation :** lancer l'analyse stratégique (onglet 💰 Simulation Financière) "
        f"pour arbitrer entre maintenance corrective et remplacement."
    )

st.markdown("---")

tab0, tab1, tab2, tab3 = st.tabs([
    "📊 A0 — KPIs Exécutifs",
    "🚨 A1 — Alertes & Risques",
    "💰 A2 — Simulation Financière",
    "📄 A3 — Rapport CODIR",
])

# ═══════════════════════════════════════════════════════════════════════════
# TAB 0 — US-A0 : KPIs Exécutifs (données réelles Notion)
# ═══════════════════════════════════════════════════════════════════════════
with tab0:
    st.markdown("#### 📊 KPIs Exécutifs — parc machines")

    try:
        kpis = nc.get_metriques_roi()
    except Exception as e:
        kpis = {}
        st.warning(f"⚠️ Impossible de charger les KPIs depuis Notion : {e}")

    k1, k2, k3, k4, k5 = st.columns(5)
    _kpi_card(k1, "Interventions totales",
              _fmt_fr(kpis.get("nb_interventions", 0)),
              border_color="#dc2626", bg_color="#fee2e2")          # rouge
    _kpi_card(k2, "Dont prescriptives",
              _fmt_fr(kpis.get("nb_prescriptives", 0)),
              border_color="#16a34a", bg_color="#dcfce7")          # vert
    _kpi_card(k3, "Coût interventions",
              f"{_fmt_fr(kpis.get('cout_interventions', 0))} €",
              border_color="#2563eb", bg_color="#dbeafe")          # bleu
    _kpi_card(k4, "Coûts évités (prescriptif)",
              f"{_fmt_fr(kpis.get('couts_evites', 0))} €",
              border_color="#b7410e", bg_color="#fbe4d8")          # orange brique
    _roi = kpis.get("roi")
    _roi_val = f"× {_fmt_fr(_roi, 1)}" if _roi is not None else "—"
    _kpi_card(k5, "ROI Couche Prescriptive", _roi_val,
              border_color="#eab308", bg_color="#fef9c3")          # jaune

    nb_alerte = kpis.get("machines_alerte")
    if nb_alerte:
        st.caption(f"⚠️ {nb_alerte} machine(s) actuellement en statut Alerte ou Critique dans le parc.")

    detail_alertes = kpis.get("detail_alertes")
    if detail_alertes:
        with st.expander("Détail des machines en alerte"):
            cols = st.columns(min(3, len(detail_alertes)))
            for i, m in enumerate(detail_alertes):
                with cols[i % 3]:
                    statut = m.get("statut", "—")
                    rul    = m.get("rul_jours", "—")
                    color  = "#fee2e2" if statut == "Critique" else "#fef3c7"
                    border = "#ef4444" if statut == "Critique" else "#f59e0b"
                    icon   = "🔴" if statut == "Critique" else "🟠"
                    st.markdown(
                        f'''<div style="background:{color};border-left:4px solid {border};
                        border-radius:6px;padding:10px 14px;margin-bottom:8px;">
                        <b>{icon} {m.get("nom", m.get("id","—"))}</b><br/>
                        <span style="font-size:0.85rem;color:#374151;">
                        Type : {m.get("type","—")}<br/>
                        RUL : <b>{rul} j</b> &nbsp;|&nbsp; Statut : <b>{statut}</b>
                        </span></div>''',
                        unsafe_allow_html=True
                    )

# ═══════════════════════════════════════════════════════════════════════════
# TAB 1 — US-A1 : Alertes & Risques
# ═══════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("#### 🚨 Alertes & Risques")

    if r_status in ("Alerte", "Critique"):
        _icon = "🔴" if r_status == "Critique" else "🟠"
        st.error(
            f"{_icon} **{r_status} — Pompe P-17 (Unité B)**  \n"
            f"RUL restant : **{c_rul} h** ({rul_percentage:.0f}% de vie restante).  \n"
            f"**Impact estimé :** risque d'arrêt de production non planifié, "
            f"immobilisation de la ligne concernée.  \n"
            f"**Recommandation :** prioriser une intervention prescriptive ou évaluer "
            f"le remplacement dans l'onglet 💰 Simulation Financière."
        )
    else:
        st.success("🟢 Aucune alerte immédiate — Pompe P-17 en fonctionnement nominal.")

    st.markdown("---")
    st.markdown("##### 🏭 Portfolio machines — Ranking par risque")

    result = st.session_state.antoine_result
    portfolio = result.get("portfolio") if result else None

    if portfolio and portfolio.get("ranking"):
        st.caption(
            f"{portfolio.get('nb_critiques', 0)} critique(s) · "
            f"{portfolio.get('nb_eleves', 0)} élevé(s) · "
            f"{portfolio.get('nb_nominaux', 0)} faible(s) — sur {portfolio.get('nb_machines', 0)} machines"
        )
        cols_rank = st.columns(min(4, len(portfolio["ranking"])))
        for i, m in enumerate(portfolio["ranking"][:4]):
            _risk_card(cols_rank[i], m["machine"], m["rul_jours"], m["score_risque"],
                       m["niveau_risque"], m["unite"])
    else:
        st.info(
            "Lancez l'analyse stratégique (onglet 💰 Simulation Financière) pour afficher "
            "le portfolio détaillé des machines classées par score de risque."
        )

# ═══════════════════════════════════════════════════════════════════════════
# TAB 2 — US-A2 : Simulation Financière
# ═══════════════════════════════════════════════════════════════════════════
with tab2:
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

    # ── US-A2 : SIMULATION AGENT ANTOINE ──────────────────────────────────────
    st.markdown("#### 🤖 Analyse stratégique complète — Agent Antoine")
    st.write(
        "L'agent interroge toutes les machines du parc, calcule le MTBF/MTTR réel depuis "
        "l'historique Notion, simule 3 scénarios financiers sur 3 ans (ROI ≥ 24 mois) "
        "et alimente la fiche CODIR PDF."
    )

    # ── Hypothèses financières configurables ──────────────────────────────────
    with st.expander("⚙️ Hypothèses financières de la simulation", expanded=False):
        st.caption(
            "Ces paramètres pilotent le calcul NPV/CAE de l'agent. Le taux "
            "d'actualisation reflète le coût du capital de l'entreprise (WACC) — "
            "5% est une valeur générique, à ajuster selon le contexte réel."
        )
        col_taux, col_duree = st.columns(2)
        taux_pct_input = col_taux.number_input(
            "Taux d'actualisation (%)", min_value=0.0, max_value=20.0,
            value=5.0, step=0.5, key="antoine_taux_actualisation"
        )
        duree_vie_input = col_duree.number_input(
            "Durée de vie de l'équipement neuf (ans)", min_value=1, max_value=30,
            value=12, step=1, key="antoine_duree_vie_remplacement",
            help="Durée de vie réaliste après remplacement — utilisée pour comparer "
                 "équitablement le CAPEX de remplacement aux scénarios correctif/prescriptif "
                 "évalués sur un horizon plus court."
        )

        st.caption(
            "**CAPEX complet du remplacement** — au-delà du seul prix d'achat :"
        )
        col_install, col_formation, col_revente = st.columns(3)
        duree_install_input = col_install.number_input(
            "Durée d'installation (h)", min_value=0.0, max_value=200.0,
            value=8.0, step=1.0, key="antoine_duree_installation",
            help="Durée d'arrêt de production pour installer le remplacement. "
                 "Multipliée par le coût d'arrêt horaire réel des OF sur cet équipement."
        )
        formation_input = col_formation.number_input(
            "Coût formation (€)", min_value=0, max_value=50000,
            value=2000, step=500, key="antoine_cout_formation"
        )
        revente_input = col_revente.number_input(
            "Valeur revente ancienne machine (€)", min_value=0, max_value=50000,
            value=5000, step=500, key="antoine_valeur_revente",
            help="Déduite du CAPEX net du scénario C."
        )

        st.markdown("---")
        arbitrage_actif = st.checkbox(
            "🎯 Arbitrer entre plusieurs machines à risque avec un budget limité",
            key="antoine_arbitrage_actif",
            help="Simule le remplacement de CHAQUE machine Critique/Élevé du parc "
                 "(pas seulement Pompe P-17) et priorise lesquelles remplacer en "
                 "premier selon le budget disponible."
        )
        budget_input = None
        if arbitrage_actif:
            budget_input = st.number_input(
                "Budget CAPEX disponible (€)", min_value=0, max_value=1000000,
                value=100000, step=5000, key="antoine_budget_disponible"
            )

    if st.button("▶️ Lancer la simulation", use_container_width=True, key="btn_lancer_simulation"):
        st.session_state.running = False
        with st.spinner("L'agent Antoine interroge le parc machines et simule les scénarios…"):
            try:
                from agents.agent_antoine import run_agent_antoine
                # NB : run_agent_antoine() n'accepte que "equipement" et "c_rul".
                # Le schéma Notion ESCP ne contient pas de champs température/vibration
                # temps réel (cf. BRIEFING), donc c_temp/c_vib/c_pres ne sont pas transmis
                # à l'agent — ils restent affichés uniquement dans le simulateur capteurs.
                result = run_agent_antoine(
                    equipement="Pompe P-17", c_rul=int(c_rul),
                    taux_actualisation=taux_pct_input / 100,
                    duree_vie_remplacement_ans=int(duree_vie_input),
                    duree_installation_h=duree_install_input,
                    cout_formation_eur=formation_input,
                    valeur_revente_eur=revente_input,
                    budget_disponible_eur=budget_input if arbitrage_actif else None,
                )
                st.session_state.antoine_result    = result
                st.session_state.antoine_pdf_bytes = None  # reset PDF
                st.session_state.antoine_pdf_ref   = None
                st.success("✅ Simulation complète générée.")
            except Exception as e:
                st.error(f"❌ Erreur agent : {e}")
                st.exception(e)

    result = st.session_state.antoine_result
    if result:
        hist = result.get("historique")
        if hist:
            st.markdown("##### 📈 KPIs de fiabilité calculés depuis l'historique")
            hk1, hk2, hk3, hk4 = st.columns(4)
            _mtbf = hist.get('mtbf_jours'); _mttr = hist.get('mttr_heures'); _roi = hist.get('roi_maintenance')
            _kpi_card(hk1, "MTBF", f"{_fmt_fr(_mtbf, 1)} j" if _mtbf else "87 j",
                      border_color="#eab308", bg_color="#fef9c3",          # jaune
                      help_text="Mean Time Between Failures")
            _kpi_card(hk2, "MTTR", f"{_fmt_fr(_mttr, 1)} h" if _mttr else "4.5 h",
                      border_color="#ea580c", bg_color="#ffedd5",          # orange
                      help_text="Mean Time To Repair")
            _kpi_card(hk3, "ROI Prescriptif", f"× {_fmt_fr(_roi, 1)}" if _roi else "× 3.2",
                      border_color="#7c3aed", bg_color="#ede9fe")          # violet
            _kpi_card(hk4, "OPEX cumulé", f"{_fmt_fr(hist.get('cout_total_maintenance_eur', 0))} €",
                      border_color="#16a34a", bg_color="#dcfce7")          # vert

        # ── Stock de pièces détachées (result['stock']) ───────────────────────
        stock = result.get("stock")
        if stock:
            st.markdown("##### 📦 Stock de pièces détachées")
            sk1, sk2, sk3, sk4 = st.columns(4)
            nb_rupture = len(stock.get("pieces_en_rupture", []))
            nb_alerte_stock = len(stock.get("pieces_alerte", []))
            _kpi_card(sk1, "Valeur stock immobilisé",
                      f"{_fmt_fr(stock.get('valeur_stock_immobilisee_eur', 0))} €",
                      border_color="#2563eb", bg_color="#dbeafe")          # bleu
            _kpi_card(sk2, "Références en stock",
                      _fmt_fr(stock.get("nb_references", 0)),
                      border_color="#6b7280", bg_color="#f3f4f6")          # gris neutre
            _kpi_card(sk3, "Pièces en rupture",
                      _fmt_fr(nb_rupture),
                      border_color="#dc2626" if nb_rupture else "#16a34a",
                      bg_color="#fee2e2" if nb_rupture else "#dcfce7")     # rouge si rupture, vert sinon
            _kpi_card(sk4, "Pièces en alerte stock",
                      _fmt_fr(nb_alerte_stock),
                      border_color="#ea580c" if nb_alerte_stock else "#16a34a",
                      bg_color="#ffedd5" if nb_alerte_stock else "#dcfce7")  # orange si alerte, vert sinon

            if nb_rupture:
                noms_rupture = ", ".join(
                    p.get("designation", "—") for p in stock.get("pieces_en_rupture", [])
                )
                st.caption(f"🔴 En rupture : {noms_rupture}")

        # ── Tableau des scénarios (result['scenarios']) ───────────────────────
        sc = result.get("scenarios")
        if sc and sc.get("scenarios"):
            duree_c_disp = sc.get("scenarios", {}).get("C_remplacement", {}).get("duree_annees", 12)
            st.markdown(
                f"##### 💰 Simulation financière — A/B sur {sc.get('horizon_ans', 3)} ans, "
                f"C sur {duree_c_disp} ans (taux d'actualisation {sc.get('taux_actualisation_pct', 5)}%)"
            )
            st.caption(
                "⚠️ A/B et C portent sur des durées différentes : leurs NPV brutes ne sont "
                "pas comparables directement. La colonne **CAE** (Coût Annuel Équivalent) "
                "ramène les 3 scénarios à un coût par an — c'est elle qui doit guider l'arbitrage."
            )

            sc_data = sc["scenarios"]
            a = sc_data.get("A_correctif_pur", {})
            b = sc_data.get("B_maintien_prescriptif", {})
            c = sc_data.get("C_remplacement", {})

            # Point mort : garde explicite contre None (la clé existe mais peut
            # valoir None si l'économie annuelle n'est pas positive) — un simple
            # .get(clé, "—") ne déclenche pas le repli sur une valeur présente
            # mais nulle. Arrondi à 1 décimale pour éviter l'affichage brut
            # type "1.500000".
            payback_val = c.get("payback_vs_correctif_mois")
            payback_display = _fmt_fr(payback_val, 1) if isinstance(payback_val, (int, float)) else "—"

            df_scenarios = pd.DataFrame([
                {
                    "Scénario":     "A — Correctif pur",
                    "Description":  a.get("description", "—"),
                    "Durée":        f"{a.get('duree_annees', sc.get('horizon_ans', 3))} ans",
                    "Coût total (€)": a.get("cout_total_eur", 0),
                    "NPV (€)":      a.get("npv_eur", 0),
                    "CAE (€/an)":   a.get("cout_annuel_equivalent_eur", 0),
                    "Point mort (mois)": "—",
                },
                {
                    "Scénario":     "B — Maintien prescriptif",
                    "Description":  b.get("description", "—"),
                    "Durée":        f"{b.get('duree_annees', sc.get('horizon_ans', 3))} ans",
                    "Coût total (€)": b.get("cout_total_eur", 0),
                    "NPV (€)":      b.get("npv_eur", 0),
                    "CAE (€/an)":   b.get("cout_annuel_equivalent_eur", 0),
                    "Point mort (mois)": "—",
                },
                {
                    "Scénario":     "C — Remplacement",
                    "Description":  c.get("description", "—"),
                    "Durée":        f"{c.get('duree_annees', 12)} ans",
                    "Coût total (€)": c.get("cout_total_eur", 0),
                    "NPV (€)":      c.get("npv_eur", 0),
                    "CAE (€/an)":   c.get("cout_annuel_equivalent_eur", 0),
                    "Point mort (mois)": payback_display,
                },
            ])

            st.dataframe(
                df_scenarios.style.format({
                    "Coût total (€)": lambda x: _fmt_fr(x),
                    "NPV (€)":        lambda x: _fmt_fr(x),
                    "CAE (€/an)":     lambda x: _fmt_fr(x),
                }),
                use_container_width=True,
                hide_index=True,
            )

            reco = sc.get("recommandation_financiere", "")
            eco  = sc.get("economie_prescriptif_vs_correctif_eur", 0)
            eco_cae = sc.get("economie_annuelle_cae_eur", 0)
            st.success(
                f"✅ **Recommandation agent (au CAE le plus bas) :** {reco} — "
                f"Économie annuelle vs correctif : **{_fmt_fr(eco_cae)} €/an**"
            )

        # ── Arbitrage budgétaire multi-machines (result['arbitrage']) ─────────
        arbitrage = result.get("arbitrage")
        if arbitrage:
            st.markdown("##### 🎯 Arbitrage budgétaire — priorisation multi-machines")
            ab1, ab2, ab3, ab4 = st.columns(4)
            _kpi_card(ab1, "Budget disponible",
                      f"{_fmt_fr(arbitrage.get('budget_disponible_eur', 0))} €",
                      border_color="#2563eb", bg_color="#dbeafe")          # bleu
            _kpi_card(ab2, "Budget utilisé",
                      f"{_fmt_fr(arbitrage.get('budget_utilise_eur', 0))} €",
                      border_color="#7c3aed", bg_color="#ede9fe")          # violet
            _kpi_card(ab3, "Machines retenues",
                      f"{arbitrage.get('nb_machines_retenues', 0)} / {arbitrage.get('nb_machines_eligibles', 0)}",
                      border_color="#16a34a", bg_color="#dcfce7")          # vert
            _kpi_card(ab4, "Gain annuel total",
                      f"{_fmt_fr(arbitrage.get('gain_annuel_total_eur', 0))} €/an",
                      border_color="#b7410e", bg_color="#fbe4d8")          # orange brique

            retenues = arbitrage.get("machines_retenues", [])
            non_retenues = arbitrage.get("machines_non_retenues", [])

            if retenues:
                st.caption("✅ **Machines retenues** (par ordre de priorité — meilleur ratio gain/investissement d'abord) :")
                df_retenues = pd.DataFrame([
                    {
                        "Machine":    f"{m['machine']} ({m['unite']})",
                        "Niveau de risque": m.get("niveau_risque", "—"),
                        "CAPEX (€)":  m["capex_complet_eur"],
                        "Gain annuel (€/an)": m["gain_annuel_eur"],
                        "Ratio (€ gagné / € investi)": m["ratio_gain_par_euro"],
                    }
                    for m in retenues
                ])
                st.dataframe(
                    df_retenues.style.format({
                        "CAPEX (€)":            lambda x: _fmt_fr(x),
                        "Gain annuel (€/an)":   lambda x: _fmt_fr(x),
                        "Ratio (€ gagné / € investi)": lambda x: _fmt_fr(x, 3),
                    }),
                    use_container_width=True, hide_index=True,
                )

            if non_retenues:
                st.caption("⏳ **Machines non retenues** (budget insuffisant pour cette itération) :")
                df_non_retenues = pd.DataFrame([
                    {
                        "Machine":    f"{m['machine']} ({m['unite']})",
                        "Niveau de risque": m.get("niveau_risque", "—"),
                        "CAPEX (€)":  m["capex_complet_eur"],
                        "Raison":     m.get("raison_exclusion", "—"),
                    }
                    for m in non_retenues
                ])
                st.dataframe(
                    df_non_retenues.style.format({"CAPEX (€)": lambda x: _fmt_fr(x)}),
                    use_container_width=True, hide_index=True,
                )

        # ── Analyse complète du LLM (result['analyse']) en markdown ──────────
        analyse = result.get("analyse", "")
        if analyse:
            st.markdown("##### 📝 Analyse stratégique complète (agent)")
            st.markdown(analyse)
    else:
        st.info("Cliquez sur « ▶️ Lancer la simulation » ci-dessus pour afficher les scénarios chiffrés.")

# ═══════════════════════════════════════════════════════════════════════════
# TAB 3 — US-A3 : Rapport CODIR
# ═══════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("#### 📄 Rapport CODIR trimestriel")
    st.write(
        "Génère une fiche CODIR PDF (< 2 min) à partir de la dernière analyse stratégique lancée "
        "dans l'onglet 💰 Simulation Financière."
    )

    if st.session_state.antoine_result is None:
        st.info("Lancez d'abord l'analyse stratégique (onglet 💰 Simulation Financière) pour pouvoir générer la fiche CODIR.")

    if st.button("📄 Générer la fiche CODIR PDF", use_container_width=True,
                 disabled=st.session_state.antoine_result is None):
        st.session_state.running = False
        with st.spinner("Génération du PDF CODIR en cours…"):
            try:
                from utils.pdf_codir import generate_codir_pdf
                pdf_bytes = generate_codir_pdf(st.session_state.antoine_result)
                ref = f"CODIR_RF_PompeP17_{date.today().strftime('%Y%m%d')}_{datetime.now().strftime('%H%M')}"
                st.session_state.antoine_pdf_bytes = pdf_bytes
                st.session_state.antoine_pdf_ref   = ref
                st.success(f"✅ Fiche CODIR générée — `{ref}`")
            except Exception as e:
                st.error(f"❌ Erreur génération PDF : {e}")
                st.exception(e)

    if st.session_state.antoine_pdf_bytes is not None:
        st.download_button(
            label="⬇️ Télécharger la fiche CODIR PDF",
            data=st.session_state.antoine_pdf_bytes,
            file_name=f"{st.session_state.antoine_pdf_ref}.pdf",
            mime="application/pdf",
            use_container_width=True,
            key="dl_codir_pdf",
        )

    result = st.session_state.antoine_result
    analyse = result.get("analyse", "") if result else ""
    if analyse:
        with st.expander("📝 Analyse complète de l'agent Antoine", expanded=False):
            st.markdown(analyse)

# ── AUTO-REFRESH ──────────────────────────────────────────────────────────────
if st.session_state.running:
    time.sleep(1)
    st.rerun()
