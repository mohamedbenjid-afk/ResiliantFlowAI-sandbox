# pages/2_Sophie.py
# Agent Sophie — Manager Maintenance
# S0 Alertes actives · S1 Simulateur d'impact · S2 Affectation équipe · S3 Rapport hebdo

import time
import datetime

import plotly.graph_objects as go
import streamlit as st

import notion_client as nc
from shared_state import COMMON_CSS, init_session_state, update_sensors

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Sophie — Manager Maintenance", page_icon="📋", layout="wide")
st.markdown(COMMON_CSS, unsafe_allow_html=True)

# ── BANNIÈRE ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="escp-banner">
    🎓 <b>Projet de Fin d'Études ESCP</b> &nbsp;|&nbsp;
    ⚙️ Sujet : <i>Maintenance Prescriptive &amp; Industrie 4.0</i>
</div>
""", unsafe_allow_html=True)

# ── INIT & CAPTEURS ───────────────────────────────────────────────────────────
init_session_state()
c_temp, c_vib, c_pres, c_cur, c_rul, r_status, rul_pct = update_sensors()

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.page_link("streamlit_home.py", label="⬅️ Retour à l'accueil", use_container_width=True)
    st.markdown("---")
    st.markdown("### ResilientFlow AI\n*Couche Prescriptive v1*")
    st.markdown("---")
    running_label = "⏸️ Pause / ▶️ Reprendre"
    if st.sidebar.button(running_label, use_container_width=True):
        st.session_state.running = not st.session_state.running
        st.rerun()
    st.markdown("---")
    st.sidebar.caption("Statut machine : Pompe P-17 (Unité B)")
    st.sidebar.caption("Horodatage système : t = " + str(st.session_state.tick))
    st.sidebar.caption(f"RUL estimé : {c_rul}h ({r_status})")

# ── TABS ──────────────────────────────────────────────────────────────────────
tab0, tab1, tab2, tab3 = st.tabs([
    "📡 S0 — Alertes actives",
    "🔮 S1 — Simulateur d'impact",
    "👥 S2 — Affectation équipe",
    "📊 S3 — Rapport hebdo",
])

STATUS_COLOR  = {"Nominal": "#166534", "Alerte": "#b45309", "Critique": "#b91c1c"}
STATUS_BG     = {"Nominal": "#dcfce7", "Alerte": "#fef3c7", "Critique": "#fee2e2"}
STATUS_BORDER = {"Nominal": "#86efac", "Alerte": "#fde047", "Critique": "#ef4444"}

# ════════════════════════════════════════════════════════════════════════════════
# TAB 0 — S0 ALERTES ACTIVES
# ════════════════════════════════════════════════════════════════════════════════
with tab0:
    st.markdown("## 📡 Machines en alerte — classées par urgence décroissante")

    try:
        machines = nc.get_machines()
        if not machines:
            raise ValueError("Liste vide")
    except Exception:
        machines = [
            {"id": "P-17",  "nom": "Pompe P-17",        "statut": "Critique", "rul_jours": c_rul, "unite": "Unité B",  "responsable": "Sophie"},
            {"id": "C-03",  "nom": "Compresseur C-03",  "statut": "Alerte",   "rul_jours": 30,    "unite": "Ligne 1",  "responsable": "Sophie"},
            {"id": "M-08",  "nom": "Moteur M-08",       "statut": "Nominal",  "rul_jours": 90,    "unite": "Ligne 2",  "responsable": "Sophie"},
        ]

    # Aligner P-17 avec le simulateur temps réel
    for m in machines:
        if "P-17" in (m.get("id") or "") or "P-17" in (m.get("nom") or ""):
            m["rul_jours"] = c_rul
            m["statut"]    = r_status

    # Tri par urgence décroissante
    def _urgency_key(m):
        rank = {"Critique": 0, "Alerte": 1, "Hors service": 2}.get(m.get("statut", "Nominal"), 3)
        return (rank, m.get("rul_jours") or 999)

    machines_sorted = sorted(machines, key=_urgency_key)

    for m in machines_sorted:
        statut = m.get("statut") or "Nominal"
        rul    = m.get("rul_jours") or "?"
        nom    = m.get("nom", "?")
        mid    = m.get("id", "")
        unite  = m.get("unite", "")
        bg     = STATUS_BG.get(statut, "#f0fdf4")
        border = STATUS_BORDER.get(statut, "#86efac")
        color  = STATUS_COLOR.get(statut, "#166534")
        icon   = "🔴" if statut == "Critique" else ("🟠" if statut == "Alerte" else "🟢")

        if statut == "Critique":
            action = f"⚡ Intervention immédiate — RUL {rul}h, risque panne imminente"
        elif statut == "Alerte":
            action = f"⏰ Planifier maintenance sous 48h — RUL {rul}h"
        else:
            action = f"✅ Surveillance standard — RUL {rul}h"

        st.markdown(
            f'<div style="background:{bg};border-left:4px solid {border};'
            f'border-radius:6px;padding:14px;margin-bottom:8px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<span style="font-size:1.05rem;">{icon} <b>{nom}</b> '
            f'<span style="color:#64748b;font-size:0.85rem;">({mid}) — {unite}</span></span>'
            f'<span style="color:{color};font-weight:700;border:1px solid {border};'
            f'border-radius:20px;padding:3px 12px;font-size:0.82rem;">{statut} · {rul}h</span>'
            f'</div>'
            f'<div style="font-size:0.85rem;margin-top:6px;color:#374151;">{action}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # OFs actifs sur P-17
    st.markdown("---")
    st.markdown("### 🏭 Ordres de fabrication actifs — Pompe P-17")
    try:
        ofs = nc.get_ordres_fabrication(statut="En cours", machine_id="P-17")
        if ofs:
            for of in ofs:
                st.markdown(
                    f'<div class="doc-box">'
                    f'<b>{of.get("reference","—")}</b> &nbsp;|&nbsp; '
                    f'{of.get("produit","—")} &nbsp;|&nbsp; '
                    f'Ligne : {of.get("ligne","—")} &nbsp;|&nbsp; '
                    f'Fin prévue : {of.get("date_fin","—")} &nbsp;|&nbsp; '
                    f'Coût arrêt : <b>{of.get("cout_arret_h","—")} €/h</b>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.info("Aucun OF en cours sur P-17.")
    except Exception:
        st.warning("Données OF indisponibles — affichage de secours.")
        st.markdown(
            '<div class="doc-box"><b>OF-2026-042</b> &nbsp;|&nbsp; Pompe centrifuge série A &nbsp;|&nbsp; '
            'Ligne 2 &nbsp;|&nbsp; Fin prévue : 2026-07-02 &nbsp;|&nbsp; '
            'Coût arrêt : <b>1 200 €/h</b></div>',
            unsafe_allow_html=True,
        )

# ════════════════════════════════════════════════════════════════════════════════
# TAB 1 — S1 SIMULATEUR D'IMPACT
# ════════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("## 🔮 Simulateur d'impact — Que se passe-t-il si je reporte ?")

    # Métriques capteurs actuelles
    col_r, col_s, col_t, col_v = st.columns(4)
    col_r.metric("⏱ RUL actuel", f"{c_rul}h")
    col_s.metric("📊 Statut", r_status)
    col_t.metric("🌡 Température", f"{c_temp:.1f}°C")
    col_v.metric("📳 Vibration", f"{c_vib:.2f} mm/s")

    st.markdown("---")

    jours_report = st.slider(
        "⏳ De combien d'heures veux-tu reporter l'intervention ?",
        min_value=0, max_value=72, value=24, step=4,
        format="%d h",
    )

    # Calcul RUL projeté et risque (valeurs backlog US-S1 : 73% / 47 000€)
    rul_projete  = max(0, c_rul - jours_report)
    risque_base  = 73
    impact_base  = 47000

    if rul_projete <= 0:
        risque = 100
        impact = round(impact_base * 1.5)
        niveau = "CRITIQUE"
    elif rul_projete <= 12:
        risque = min(100, round(risque_base + (jours_report / 72) * 25, 1))
        impact = round(impact_base * (1 + jours_report / 48))
        niveau = "ÉLEVÉ"
    elif rul_projete <= 24:
        risque = round(risque_base + (jours_report / 72) * 15, 1)
        impact = round(impact_base * (1 + jours_report / 72))
        niveau = "MODÉRÉ"
    else:
        risque = round(max(0, risque_base - (rul_projete / 100) * 20), 1)
        impact = round(impact_base * (1 - (rul_projete - 24) / 200))
        niveau = "FAIBLE"

    color_risque = "#b91c1c" if risque >= 70 else ("#b45309" if risque >= 40 else "#166534")
    col_a, col_b, col_c = st.columns(3)
    col_a.markdown(
        f'<div style="background:#f8fafc;border-radius:8px;padding:16px;text-align:center;">'
        f'<div style="font-size:0.8rem;color:#64748b;">RUL projeté</div>'
        f'<div style="font-size:2rem;font-weight:800;color:#1e293b;">{rul_projete}h</div>'
        f'</div>', unsafe_allow_html=True,
    )
    col_b.markdown(
        f'<div style="background:#f8fafc;border-radius:8px;padding:16px;text-align:center;">'
        f'<div style="font-size:0.8rem;color:#64748b;">Risque panne</div>'
        f'<div style="font-size:2rem;font-weight:800;color:{color_risque};">{risque}%</div>'
        f'</div>', unsafe_allow_html=True,
    )
    col_c.markdown(
        f'<div style="background:#f8fafc;border-radius:8px;padding:16px;text-align:center;">'
        f'<div style="font-size:0.8rem;color:#64748b;">Impact estimé</div>'
        f'<div style="font-size:2rem;font-weight:800;color:#b45309;">{impact:,} €</div>'
        f'</div>', unsafe_allow_html=True,
    )

    st.markdown("---")

    # Appel agent Sophie — mis en cache dans session_state
    if st.button("▶️ Lancer l'analyse d'impact IA", use_container_width=True, type="primary"):
        st.session_state.running = False
        with st.spinner("Analyse en cours… (~30s)"):
            try:
                from agents.agent_sophie import run_agent_sophie
                result = run_agent_sophie(
                    c_rul=int(c_rul),
                    equipement="P-17",
                    c_temp=float(c_temp),
                    c_vib=float(c_vib),
                )
                st.session_state["sophie_result"] = result
            except Exception as e:
                st.session_state["sophie_result"] = None
                st.error(f"Erreur agent : {e}")

    if st.session_state.get("sophie_result"):
        with st.expander("🤖 Analyse IA — Agent Sophie", expanded=True):
            st.markdown(st.session_state["sophie_result"])
            if st.button("🔄 Relancer l'analyse", key="btn_relance_sophie"):
                st.session_state.pop("sophie_result", None)
                st.rerun()

# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — S2 AFFECTATION ÉQUIPE
# ════════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("## 👥 Affectation équipe — 1 clic")

    try:
        equipe_all = nc.get_equipe()
        if not equipe_all:
            raise ValueError("Liste vide")
    except Exception:
        equipe_all = [
            {"nom": "Bernard",  "prenom": "Lionel", "role": "Technicien Terrain",
             "specialite": "Mécanique/Hydraulique",
             "habilitations": "LOTO, Hydraulique haute pression",
             "disponibilite": "Disponible", "heures_restantes": 8, "zone": "Unité B"},
            {"nom": "Dupont",   "prenom": "Marc",   "role": "Technicien Électrique",
             "specialite": "Électricité",
             "habilitations": "Habilitation électrique B2",
             "disponibilite": "En intervention", "heures_restantes": 1, "zone": "Ligne 1"},
            {"nom": "Rousseau", "prenom": "Fatima", "role": "Technicienne Automatisme",
             "specialite": "Automatisme",
             "habilitations": "LOTO, Automatisme",
             "disponibilite": "Disponible", "heures_restantes": 6, "zone": "Ligne 2"},
        ]

    st.markdown("### ⚙️ Paramètres de l'intervention")
    col_eq, col_type = st.columns(2)
    with col_eq:
        equipement_cible = st.selectbox("Machine concernée", ["P-17", "C-03", "M-08"], index=0)
    with col_type:
        type_intervention = st.selectbox(
            "Type d'intervention",
            ["Prédictive", "Préventive", "Corrective", "Inspection"],
        )

    HABILITATIONS_REQUISES = {
        "Prédictive":  ["LOTO"],
        "Préventive":  ["LOTO"],
        "Corrective":  ["LOTO", "Hydraulique haute pression"],
        "Inspection":  [],
    }
    hab_requises = HABILITATIONS_REQUISES.get(type_intervention, [])

    st.markdown("---")
    st.markdown("### 👷 Techniciens")
    if hab_requises:
        st.caption(f"Habilitations requises pour **{type_intervention}** : {', '.join(hab_requises)}")

    dispo_order   = {"Disponible": 0, "En intervention": 1, "Congé": 2}
    equipe_sorted = sorted(
        equipe_all,
        key=lambda t: (dispo_order.get(t.get("disponibilite", "Congé"), 3), -(t.get("heures_restantes") or 0)),
    )

    # Vérifier si une confirmation est en cours pour un technicien
    confirmation_en_cours = any(
        st.session_state.get(f"confirm_{tech.get('prenom','')} {tech.get('nom','')}", False)
        for tech in equipe_sorted
    )

    for tech in equipe_sorted:
        nom_complet   = f"{tech.get('prenom','')} {tech.get('nom','')}"
        dispo         = tech.get("disponibilite", "Congé")
        heures        = tech.get("heures_restantes") or 0
        specialite    = tech.get("specialite", "—")
        habilitations_raw = tech.get("habilitations") or ""
        zone              = tech.get("zone", "—")

        confirm_key = f"confirm_{nom_complet}"

        # Si une confirmation est en cours pour un autre technicien, ne pas afficher celui-ci
        if confirmation_en_cours and not st.session_state.get(confirm_key, False):
            continue

        # notion_client peut retourner une liste (multi_select) ou une chaîne
        if isinstance(habilitations_raw, list):
            habs_tech     = [str(h).strip() for h in habilitations_raw if str(h).strip()]
            habilitations = ", ".join(habs_tech)
        else:
            habilitations = str(habilitations_raw) if habilitations_raw else ""
            habs_tech     = [h.strip() for h in habilitations.split(",") if h.strip()]
        manquantes = [h for h in hab_requises if h not in habs_tech]

        if dispo == "Disponible":
            bg_tech, color_dispo, icon_dispo = "#f0fdf4", "#166534", "🟢"
        elif dispo == "En intervention":
            bg_tech, color_dispo, icon_dispo = "#fef3c7", "#b45309", "🟠"
        else:
            bg_tech, color_dispo, icon_dispo = "#f3f4f6", "#6b7280", "⚫"

        hab_warning = (
            f'<div style="color:#b91c1c;font-size:0.78rem;margin-top:4px;">'
            f'⚠️ Habilitation(s) manquante(s) : {", ".join(manquantes)}</div>'
        ) if manquantes else ""

        col_info, col_btn = st.columns([4, 1])
        with col_info:
            st.markdown(
                f'<div style="background:{bg_tech};border-radius:8px;padding:12px;margin-bottom:6px;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<span>{icon_dispo} <b>{nom_complet}</b> — '
                f'<span style="color:#64748b;font-size:0.85rem;">{specialite} · {zone}</span></span>'
                f'<span style="color:{color_dispo};font-size:0.85rem;font-weight:600;">'
                f'{dispo} · {heures}h restantes</span>'
                f'</div>'
                f'<div style="font-size:0.78rem;color:#475569;margin-top:2px;">'
                f'Habilitations : {habilitations or "—"}</div>'
                f'{hab_warning}'
                f'</div>',
                unsafe_allow_html=True,
            )
        with col_btn:
            btn_disabled = dispo != "Disponible"
            btn_label    = "✅ Affecter" if not btn_disabled else ("🔄 Occupé" if dispo == "En intervention" else "❌ Absent")
            st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)

            if confirm_key not in st.session_state:
                st.session_state[confirm_key] = False

            # Bouton Affecter — affiché seulement si pas de confirmation en cours
            if not st.session_state.get(confirm_key, False):
                if st.button(btn_label, key=f"btn_affect_{nom_complet}", disabled=btn_disabled, use_container_width=True):
                    st.session_state[confirm_key] = True
                    st.rerun()

        # Zone de confirmation — affichée sous la ligne du technicien
        if st.session_state.get(confirm_key, False):
            st.warning(
                f"Confirmer l'affectation de **{nom_complet}** sur **{equipement_cible}** "
                f"({type_intervention}) — RUL actuel : {c_rul}h ?"
            )
            col_oui, col_non = st.columns(2)
            with col_oui:
                if st.button("✅ Confirmer", key=f"oui_{nom_complet}", use_container_width=True, type="primary"):
                    st.session_state[confirm_key] = False
                    today   = datetime.date.today().isoformat()
                    payload = {
                        "titre":         f"Intervention {equipement_cible} — {today}",
                        "machine":       equipement_cible,
                        "type":          type_intervention,
                        "statut":        "Planifiée",
                        "technicien":    nom_complet,
                        "date":          today,
                        "date_realisee": None,
                        "duree_reelle":  0.0,
                        "actions":       f"Affectation {type_intervention} sur {equipement_cible}",
                        "pieces":        "",
                        "cause_racine":  "",
                        "cout":          0.0,
                        "rul_avant":     c_rul,
                        "observations":  f"Assigné par Sophie — RUL {c_rul}h",
                    }
                    try:
                        with st.spinner(f"Affectation de {nom_complet}…"):
                            nc.create_intervention(payload)
                        st.success(f"✅ {nom_complet} affecté à l'intervention {equipement_cible} !")
                        if manquantes:
                            st.warning(f"⚠️ Habilitation(s) manquante(s) — non bloquant : {', '.join(manquantes)}")
                    except Exception as e:
                        st.error(f"Erreur Notion : {e}")
            with col_non:
                if st.button("❌ Annuler", key=f"non_{nom_complet}", use_container_width=True):
                    st.session_state[confirm_key] = False
                    st.rerun()

# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 — S3 RAPPORT HEBDOMADAIRE
# ════════════════════════════════════════════════════════════════════════════════
with tab3:
    semaine = datetime.date.today().isocalendar()[1]
    st.markdown(f"## 📊 Rapport hebdomadaire — Semaine {semaine}")

    try:
        historique   = nc.get_historique(machine_id="P-17")
        pieces_stock = nc.get_pieces(machine_id="P-17")
        equipe_dispo = nc.get_equipe()
        if not historique and not pieces_stock:
            raise ValueError("Données vides")
    except Exception:
        historique = [
            {"titre": "Remplacement joint P-17",       "type": "Préventive", "statut": "Réalisée",
             "date": "2026-06-23", "duree_estimee": 2, "technicien": "Lionel B.", "cout_estime": 850},
            {"titre": "Inspection C-03",                "type": "Inspection", "statut": "Réalisée",
             "date": "2026-06-24", "duree_estimee": 1, "technicien": "Marc D.",   "cout_estime": 300},
            {"titre": "Maintenance préventive M-08",   "type": "Préventive", "statut": "Planifiée",
             "date": "2026-06-30", "duree_estimee": 3, "technicien": "Fatima R.", "cout_estime": 600},
        ]
        pieces_stock = [
            {"designation": "Joints d'étanchéité P17",  "statut_stock": "En stock",    "stock_actuel": 2, "stock_minimum": 1},
            {"designation": "Roulements 6205-2RS",       "statut_stock": "Rupture",     "stock_actuel": 0, "stock_minimum": 2},
            {"designation": "Garnitures mécaniques",     "statut_stock": "En stock",    "stock_actuel": 3, "stock_minimum": 1},
            {"designation": "Filtre hydraulique FH-17",  "statut_stock": "Stock faible","stock_actuel": 1, "stock_minimum": 2},
        ]
        equipe_dispo = [
            {"nom": "Bernard",  "prenom": "Lionel", "disponibilite": "Disponible",     "heures_restantes": 8},
            {"nom": "Dupont",   "prenom": "Marc",   "disponibilite": "En intervention","heures_restantes": 1},
            {"nom": "Rousseau", "prenom": "Fatima", "disponibilite": "Disponible",     "heures_restantes": 6},
        ]

    # ── KPIs ──────────────────────────────────────────────────────────────────
    n_realisees   = sum(1 for i in historique if i.get("statut") == "Réalisée")
    n_total       = len(historique)
    taux_realisation = round(100 * n_realisees / n_total, 1) if n_total else 0
    cout_total    = sum(float(i.get("cout_estime") or 0) for i in historique if i.get("statut") == "Réalisée")
    n_ruptures    = sum(1 for p in pieces_stock if p.get("statut_stock") == "Rupture")
    n_dispos      = sum(1 for t in equipe_dispo if t.get("disponibilite") == "Disponible")
    arrêts_evites = n_realisees  # 1 maintenance préventive réalisée = 1 arrêt évité (proxy)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("✅ Taux réalisation",     f"{taux_realisation}%",       delta=f"{n_realisees}/{n_total} interventions")
    k2.metric("🛡 Arrêts évités",        f"{arrêts_evites}",           delta="cette semaine")
    k3.metric("⚠️ Ruptures stock",       f"{n_ruptures} pièce(s)")
    k4.metric("👷 Techniciens dispos",   f"{n_dispos}/{len(equipe_dispo)}")

    st.markdown("---")
    col_left, col_right = st.columns(2)

    # ── Graphique interventions ───────────────────────────────────────────────
    with col_left:
        st.markdown("### 🗓 Interventions de la semaine")
        titres = [i.get("titre", "—") for i in historique]
        durees = [float(i.get("duree_estimee") or 0) for i in historique]
        statuts_hist = [i.get("statut", "—") for i in historique]
        colors_stat  = {"Réalisée": "#22c55e", "Planifiée": "#3b82f6", "En cours": "#f59e0b", "Annulée": "#94a3b8"}
        bar_colors   = [colors_stat.get(s, "#94a3b8") for s in statuts_hist]

        fig_int = go.Figure(go.Bar(
            x=titres, y=durees,
            marker_color=bar_colors,
            text=statuts_hist,
            textposition="outside",
        ))
        fig_int.update_layout(
            height=260, margin=dict(l=0, r=0, t=10, b=70),
            paper_bgcolor="white", plot_bgcolor="white",
            yaxis=dict(title="Durée estimée (h)", gridcolor="rgba(0,0,0,0.06)"),
            xaxis=dict(tickangle=-20),
            showlegend=False,
        )
        st.plotly_chart(fig_int, use_container_width=True)

    # ── État du stock ─────────────────────────────────────────────────────────
    with col_right:
        st.markdown("### 🔩 État du stock pièces P-17")
        for p in pieces_stock:
            statut_s = p.get("statut_stock", "—")
            stock    = p.get("stock_actuel", 0)
            mini     = p.get("stock_minimum", 1)
            if statut_s == "En stock":
                icon_s, color_s = "✅", "#166534"
            elif statut_s == "Stock faible":
                icon_s, color_s = "⚠️", "#b45309"
            elif statut_s == "Rupture":
                icon_s, color_s = "❌", "#b91c1c"
            else:
                icon_s, color_s = "⬜", "#64748b"
            st.markdown(
                f'{icon_s} **{p.get("designation","?")}** — '
                f'<span style="color:{color_s}">Stock : {stock} (min {mini})</span>',
                unsafe_allow_html=True,
            )

    # ── Disponibilité équipe ──────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 👥 Charge équipe maintenance")
    labels_eq = [f"{t.get('prenom','')} {t.get('nom','')}" for t in equipe_dispo]
    heures_eq = [float(t.get("heures_restantes") or 0) for t in equipe_dispo]
    dispos_eq = [t.get("disponibilite", "Congé") for t in equipe_dispo]
    colors_eq = [
        "#22c55e" if d == "Disponible" else ("#f59e0b" if d == "En intervention" else "#94a3b8")
        for d in dispos_eq
    ]

    fig_eq = go.Figure(go.Bar(
        x=labels_eq, y=heures_eq,
        marker_color=colors_eq,
        text=[f"{h}h" for h in heures_eq],
        textposition="outside",
    ))
    fig_eq.update_layout(
        height=220, margin=dict(l=0, r=0, t=10, b=40),
        paper_bgcolor="white", plot_bgcolor="white",
        yaxis=dict(title="Heures restantes", gridcolor="rgba(0,0,0,0.06)"),
        showlegend=False,
    )
    st.plotly_chart(fig_eq, use_container_width=True)

    # ── Export PDF (à venir) ──────────────────────────────────────────────────
    st.markdown("---")
    st.info("📄 Export PDF du rapport — fonctionnalité à venir (utils/pdf_sophie.py)")

# ── AUTO-REFRESH ──────────────────────────────────────────────────────────────
if st.session_state.running:
    time.sleep(1)
    st.rerun()
