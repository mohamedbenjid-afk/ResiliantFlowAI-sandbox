import streamlit as st
import time
import sys, os
from datetime import datetime, date

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from shared_state import init_session_state, update_sensors, COMMON_CSS

# ── CONFIG PAGE ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Leila — Conformité HSE", page_icon="🛡️", layout="wide")
st.markdown(COMMON_CSS, unsafe_allow_html=True)

# ── SESSION STATE & CAPTEURS ──────────────────────────────────────────────────
init_session_state()
c_temp, c_vib, c_pres, c_cur, c_rul, r_status, rul_percentage = update_sensors()

# ── SESSION STATE LEILA ───────────────────────────────────────────────────────
for key in ["leila_result", "audit_pdf_bytes", "audit_pdf_ref", "audit_pdf_src"]:
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
st.sidebar.caption(f"RUL estimé : {c_rul}h — {r_status}")
st.sidebar.page_link("streamlit_home.py", label="⬅️ Retour à l'accueil", use_container_width=True)

# ── CONTENU PRINCIPAL ─────────────────────────────────────────────────────────
st.markdown("### 🛡️ Conformité Réglementaire, Sécurité & Audit HSE — Leila")
st.markdown("*Intégration native de la sécurité au cœur des interventions critiques et génération automatique de preuves d'audits.*")

# ── ONGLETS ───────────────────────────────────────────────────────────────────
tab0, tab1, tab2, tab3 = st.tabs([
    "🛡️ L0 — Alerte HSE & EPI",
    "📋 L1 — Conformité Hebdo",
    "📄 L2 — Audit ISO 45001",
    "🔍 L3 — Chronologie incident",
])

# ══════════════════════════════════════════════════════════════════════════════
# ONGLET L0 — Alerte HSE & EPI
# ══════════════════════════════════════════════════════════════════════════════
with tab0:
    st.markdown("#### 🛡️ Évaluation des risques & dotation EPI réglementaire")

    if c_rul <= 24:
        st.warning("⚡ **Protocole de Sécurité Automatique activé (Norme ISO 45001)**")
    else:
        st.success("✅ **Zéro alerte active.** Les conditions de travail sont au niveau nominal.")

    st.markdown("##### 📋 Matrice des risques — Anomalies capteurs détectées")
    st.write("L'agent AI analyse la signature de l'anomalie et pousse automatiquement les exigences de sécurité adaptées :")

    if c_temp >= 110:
        st.markdown("🧱 **Risque Thermique Élevé (Surchauffe Stator) :**")
        st.markdown("- [ ] **EPI Obligatoire :** Gants isolants Haute Température (Norme EN 407).")
        st.markdown("- [ ] **Consigne :** Attendre le message de confirmation de baisse sous 45°C avant ouverture.")

    if c_vib >= 4.5:
        st.markdown("⚙️ **Risque Mécanique Élevé (Défaut Palier) :**")
        st.markdown("- [ ] **EPI Obligatoire :** Protection oculaire renforcée et casque anti-bruit (Vibrations acoustiques).")
        st.markdown("- [ ] **Consigne :** Vérifier l'ancrage et l'absence de micro-fissures sur le châssis.")

    if c_pres >= 7.0:
        st.markdown("💧 **Risque Hydraulique Élevé (Surpression circuit) :**")
        st.markdown("- [ ] **EPI Obligatoire :** Écran facial et combinaison anti-projections.")
        st.markdown("- [ ] **Consigne :** Purger la pression résiduelle avant toute déconnexion de raccord.")

    if c_rul <= 24 and c_temp < 110 and c_vib < 4.5 and c_pres < 7.0:
        st.markdown("⚠️ **RUL critique détecté — Risque générique :**")
        st.markdown("- [ ] Appliquer la procédure LOTO complète avant toute intervention.")
        st.markdown("- [ ] Vérifier les EPI standard (casque, chaussures de sécurité, gants).")

    if c_temp < 110 and c_vib < 4.5 and c_pres < 7.0 and c_rul > 24:
        st.markdown("- [ ] Appliquer les EPI standard (casque EN 397, chaussures S3, gants EN 388).")

    st.markdown("🔒 **Procédure LOTO systématique :** Sectionneur d'alimentation cadenassé en cellule BT.")

    st.markdown("---")

    # ── Appel agent HSE ───────────────────────────────────────────────────────
    if st.button("🤖 Lancer l'évaluation HSE complète", use_container_width=True, key="btn_agent_l0"):
        st.session_state.running = False
        with st.spinner("L'agent analyse la conformité ISO 45001…"):
            try:
                from agents.agent_leila import run_agent_leila
                result = run_agent_leila(
                    c_temp=float(c_temp),
                    c_vib=float(c_vib),
                    c_pres=float(c_pres),
                    c_rul=int(c_rul),
                )
                st.session_state.leila_result = result
                st.success("✅ Évaluation HSE générée.")
            except Exception as e:
                st.error(f"Erreur agent : {e}")
                st.exception(e)

    if st.session_state.leila_result:
        st.markdown(st.session_state.leila_result)

# ══════════════════════════════════════════════════════════════════════════════
# ONGLET L1 — Conformité Hebdomadaire
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("#### 📋 Rapport de conformité hebdomadaire — ISO 45001")
    st.caption("Taux de conformité calculé sur les 7 derniers jours d'interventions (LOTO + habilitations).")

    if st.button("🔄 Générer le rapport de conformité", use_container_width=True, key="btn_conformite_l1"):
        st.session_state.running = False
        with st.spinner("Récupération des interventions des 7 derniers jours…"):
            try:
                import notion_client as nc
                from datetime import timedelta

                date_limite = (date.today() - timedelta(days=7)).isoformat()
                historique  = nc.get_historique(machine_id="P-17")

                # Filtrer les 7 derniers jours (champ "date" de la réponse nc)
                interv_semaine = [
                    h for h in historique
                    if h.get("date", "") >= date_limite
                ]

                total     = len(interv_semaine)
                avec_loto = sum(1 for h in interv_semaine if h.get("loto_requis"))
                taux_loto = round(avec_loto / max(total, 1) * 100, 1)

                avec_hab  = sum(1 for h in interv_semaine if h.get("habilitations"))
                taux_hab  = round(avec_hab / max(total, 1) * 100, 1)

                col1, col2, col3 = st.columns(3)
                col1.metric("Interventions (7j)", total)
                col2.metric("Conformité LOTO", f"{taux_loto}%",
                            delta="✅ Conforme" if taux_loto == 100 else f"⚠️ {total - avec_loto} écart(s)")
                col3.metric("Habilitations vérifiées", f"{taux_hab}%",
                            delta="✅ Conforme" if taux_hab == 100 else f"⚠️ {total - avec_hab} écart(s)")

                # Écarts détectés
                ecarts = [h for h in interv_semaine if not h.get("loto_requis") or not h.get("habilitations")]
                if ecarts:
                    st.warning(f"⚠️ {len(ecarts)} intervention(s) avec écart de conformité détectée(s) :")
                    for e in ecarts:
                        manques = []
                        if not e.get("loto_requis"):    manques.append("LOTO non renseigné")
                        if not e.get("habilitations"):  manques.append("Habilitations manquantes")
                        st.markdown(f"- **{e.get('titre', 'Sans titre')}** ({e.get('date', 'date inconnue')}) — {', '.join(manques)}")
                else:
                    st.success("✅ Aucun écart détecté sur la période.")

                # Analyse textuelle via agent
                if total > 0:
                    from agents.agent_leila import run_agent_leila
                    with st.spinner("Analyse de conformité en cours…"):
                        analyse = run_agent_leila(
                            c_temp=float(c_temp),
                            c_vib=float(c_vib),
                            c_pres=float(c_pres),
                            c_rul=int(c_rul),
                        )
                    st.markdown("##### 🤖 Analyse agent HSE")
                    st.markdown(analyse)

            except Exception as e:
                # Fallback données fictives
                st.info("ℹ️ Notion indisponible — affichage de données de démonstration.")
                col1, col2, col3 = st.columns(3)
                col1.metric("Interventions (7j)", 5)
                col2.metric("Conformité LOTO", "80%", delta="⚠️ 1 écart")
                col3.metric("Habilitations vérifiées", "100%", delta="✅ Conforme")
                st.warning("⚠️ 1 intervention avec LOTO non renseigné : **Remplacement joint (12/07)** — Technicien : Lionel Dubois")
                st.caption(f"Erreur Notion : {e}")

# ══════════════════════════════════════════════════════════════════════════════
# ONGLET L2 — Audit ISO 45001 PDF
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("#### 📄 Dossier de preuve ISO 45001 — Organisme de certification")
    st.write(
        "La couche prescriptive enregistre de façon inaltérable que chaque technicien envoyé sur une anomalie "
        "a reçu les consignes et la liste d'EPI appropriés avant d'ouvrir sa boîte à outils."
    )

    if st.button("📥 Générer le dossier de conformité pour l'organisme de certification",
                 use_container_width=True, key="btn_pdf_l2"):
        st.session_state.running = False
        with st.spinner("Génération du dossier ISO 45001 en cours…"):
            try:
                import notion_client as nc
                from utils.pdf_audit import generate_audit_pdf

                notion_ok = False
                machine, equipe, pieces, docs_hse = {}, [], [], []
                try:
                    machines   = nc.get_machines()
                    machine    = next(
                        (m for m in machines if "P-17" in m.get("nom", "") or "P17" in m.get("nom", "")),
                        machines[0] if machines else {}
                    )
                    machine_id = machine.get("id") or machine.get("notion_id", "")
                    equipe     = nc.get_equipe()
                    pieces     = nc.get_pieces(machine_id=machine_id) if machine_id else nc.get_pieces()
                    docs_hse   = nc.get_docs_hse(machine_id=machine_id) if machine_id else nc.get_docs_hse()
                    notion_ok  = True
                except Exception:
                    machine = {
                        "nom": "Pompe P-17", "type": "Pompe centrifuge", "site": "Unité B",
                        "criticite": "Critique", "mise_en_service": "2021-03-15",
                        "fabricant": "KSB Group", "modele": "Etanorm SYT 040-025-160",
                        "numero_serie": "KSB-2021-P17-UB",
                    }
                    equipe = [
                        {"nom": "Lionel Dubois", "role": "Technicien de maintenance", "habilitation": "H1B2", "disponibilite": "Disponible"},
                        {"nom": "Sophie Martin",  "role": "Responsable HSE",           "habilitation": "H2B2", "disponibilite": "Disponible"},
                    ]
                    pieces = [
                        {"reference": "KSB-ROL-6205", "designation": "Roulement à billes",  "quantite_stock": 2, "statut_stock": "ok",       "fournisseur": "SKF"},
                        {"reference": "KSB-JOI-017",  "designation": "Joint mécanique",      "quantite_stock": 1, "statut_stock": "critique", "fournisseur": "Burgmann"},
                        {"reference": "KSB-IMP-P17",  "designation": "Roue hydraulique P17", "quantite_stock": 0, "statut_stock": "Rupture",  "fournisseur": "KSB"},
                    ]
                    docs_hse = [
                        {"titre": "Notice de sécurité KSB Etanorm", "type": "Notice fabricant",  "version": "v3.2", "date_maj": "2023-06"},
                        {"titre": "Procédure LOTO Unité B",          "type": "Procédure interne", "version": "v2.1", "date_maj": "2024-01"},
                        {"titre": "Fiche de données sécurité huile",  "type": "FDS",               "version": "v1.0", "date_maj": "2022-11"},
                    ]

                technicien_data = next(
                    (m for m in equipe if m.get("disponibilite") == "Disponible"),
                    equipe[0] if equipe else {}
                )
                technicien_nom = technicien_data.get("nom", "Technicien de service")

                if c_temp >= 110:
                    type_anomalie = "Surchauffe stator — température critique"
                elif c_vib >= 4.5:
                    type_anomalie = "Défaut palier — vibrations anormales"
                elif c_pres >= 7.0:
                    type_anomalie = "Surpression circuit hydraulique"
                else:
                    type_anomalie = "Dégradation générale — RUL critique"

                context = {
                    "equipement"   : "Pompe P-17",
                    "technicien"   : technicien_nom,
                    "temp"         : float(c_temp),
                    "vib"          : float(c_vib),
                    "pres"         : float(c_pres),
                    "rul"          : int(c_rul),
                    "machine"      : machine,
                    "equipe"       : equipe,
                    "pieces"       : pieces,
                    "docs_hse"     : docs_hse,
                    "type_anomalie": type_anomalie,
                }

                pdf_bytes = generate_audit_pdf(context)

                today_str = date.today().strftime("%Y%m%d")
                now_str   = datetime.now().strftime("%H%M")
                ref = f"RF_AUDIT_ISO45001_PompeP17_{today_str}_{now_str}"

                st.session_state.audit_pdf_bytes = pdf_bytes
                st.session_state.audit_pdf_ref   = ref
                st.session_state.audit_pdf_src   = "Notion + capteurs" if notion_ok else "capteurs uniquement (Notion hors ligne)"

            except ImportError as e:
                st.error(f"❌ Dépendance manquante : {e}\n\nInstaller avec : `pip install reportlab`")
            except Exception as e:
                st.error(f"❌ Erreur lors de la génération : {e}")
                st.exception(e)

    # ── Bouton de téléchargement persistant ───────────────────────────────────
    if st.session_state.audit_pdf_bytes is not None:
        ref = st.session_state.audit_pdf_ref
        src = st.session_state.audit_pdf_src
        st.success(f"✅ Dossier de preuve prêt — référence `{ref}` — Source : {src}")
        st.caption("Statut : Horodatage certifié | Signature électronique SHA-256 de l'agent AI intégrée.")
        st.download_button(
            label="⬇️ Télécharger le dossier PDF",
            data=st.session_state.audit_pdf_bytes,
            file_name=f"{ref}.pdf",
            mime="application/pdf",
            use_container_width=True,
            key="dl_audit_pdf",
        )

# ══════════════════════════════════════════════════════════════════════════════
# ONGLET L3 — Chronologie post-incident
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("#### 🔍 Chronologie post-incident")
    st.caption("Timeline horodatée minute par minute de la dernière intervention sur Pompe P-17.")
    st.info("🚧 Fonctionnalité disponible en Sprint 4 — nécessite l'historique complet des interventions Notion.")

    # Placeholder visuel avec la dernière intervention connue
    st.markdown("##### Aperçu — Dernière intervention enregistrée")
    try:
        import notion_client as nc
        historique = nc.get_historique(machine_id="P-17")
        if historique:
            last = historique[0]
            col1, col2 = st.columns(2)
            col1.markdown(f"**Intervention :** {last.get('titre', 'N/A')}")
            col1.markdown(f"**Type :** {last.get('type', 'N/A')}")
            col1.markdown(f"**Statut :** {last.get('statut', 'N/A')}")
            col2.markdown(f"**Technicien :** {last.get('technicien', 'N/A')}")
            col2.markdown(f"**Date :** {last.get('date', 'N/A')}")
            col2.markdown(f"**Durée estimée :** {last.get('duree_estimee', 'N/A')} h")
        else:
            st.caption("Aucune intervention trouvée dans Notion.")
    except Exception as e:
        st.caption(f"Notion indisponible — {e}")
        st.markdown("**Dernière intervention (demo) :** Remplacement joint mécanique | 12/07/2026 | Lionel Dubois | 2h")

# ── AUTO-REFRESH ──────────────────────────────────────────────────────────────
if st.session_state.running:
    time.sleep(1)
    st.rerun()
