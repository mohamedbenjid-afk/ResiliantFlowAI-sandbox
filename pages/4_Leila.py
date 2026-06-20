import streamlit as st
import time
import sys, os
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from shared_state import init_session_state, update_sensors, COMMON_CSS

# ── CONFIG PAGE ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Leila — Conformité HSE", page_icon="🛡️", layout="wide")
st.markdown(COMMON_CSS, unsafe_allow_html=True)

# ── SESSION STATE & CAPTEURS ──────────────────────────────────────────────────
init_session_state()
c_temp, c_vib, c_pres, c_cur, c_rul, r_status, rul_percentage = update_sensors()

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
st.markdown("### 🛡️ Conformité Réglementaire, Sécurité & Audit HSE — Leila")
st.markdown("*Intégration native de la sécurité au cœur des interventions critiques et génération automatique de preuves d'audits.*")

if c_rul <= 24:
    st.warning("⚡ **Protocole de Sécurité Automatique activé (Norme ISO 45001)**")
    st.markdown("#### 📋 Matrice des risques et dotation réglementaire requise")
    st.write("L'agent AI a analysé la signature de l'anomalie en cours et pousse automatiquement les exigences de sécurité adaptées :")

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

    st.markdown("🔒 **Procédure LOTO systématique :** Sectionneur d'alimentation cadenassé en cellule BT.")

else:
    st.success("✅ **Zéro alerte active.** Les conditions de travail et la sécurité de l'Unité B sont au niveau nominal.")

st.markdown("---")
st.markdown("#### 📄 Registre réglementaire et Dossier de Preuve ISO 45001")
st.write(
    "La couche prescriptive enregistre de façon inaltérable que chaque technicien envoyé sur une anomalie "
    "a reçu les consignes et la liste d'EPI appropriés avant d'ouvrir sa boîte à outils."
)

# ── Initialisation session_state pour persister le PDF entre reruns ───────────
if "audit_pdf_bytes" not in st.session_state:
    st.session_state.audit_pdf_bytes = None
if "audit_pdf_ref" not in st.session_state:
    st.session_state.audit_pdf_ref = None
if "audit_pdf_src" not in st.session_state:
    st.session_state.audit_pdf_src = None

if st.button("📥 Générer le dossier de conformité pour l'organisme de certification", use_container_width=True):
    # Stopper le refresh pendant la génération
    st.session_state.running = False
    with st.spinner("Génération du dossier ISO 45001 en cours…"):
        try:
            import notion_client as nc
            from utils.pdf_audit import generate_audit_pdf

            # ── Récupération des données Notion (avec fallback si indisponible) ─
            notion_ok = False
            machine, equipe, pieces, docs_hse = {}, [], [], []
            try:
                machines = nc.get_machines()
                machine = next(
                    (m for m in machines if "P-17" in m.get("nom", "") or "P17" in m.get("nom", "")),
                    machines[0] if machines else {}
                )
                machine_id = machine.get("id") or machine.get("notion_id", "")
                equipe   = nc.get_equipe()
                pieces   = nc.get_pieces(machine_id=machine_id) if machine_id else nc.get_pieces()
                docs_hse = nc.get_docs_hse(machine_id=machine_id) if machine_id else nc.get_docs_hse()
                notion_ok = True
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

            from datetime import date
            today_str = date.today().strftime("%Y%m%d")
            now_str   = datetime.now().strftime("%H%M")
            ref = f"RF_AUDIT_ISO45001_PompeP17_{today_str}_{now_str}"

            # ── Persister en session_state pour survivre au rerun ─────────────
            st.session_state.audit_pdf_bytes = pdf_bytes
            st.session_state.audit_pdf_ref   = ref
            st.session_state.audit_pdf_src   = "Notion + capteurs" if notion_ok else "capteurs uniquement (Notion hors ligne)"

        except ImportError as e:
            st.error(f"❌ Dépendance manquante : {e}\n\nInstaller avec : `pip install reportlab`")
        except Exception as e:
            st.error(f"❌ Erreur lors de la génération : {e}")
            st.exception(e)

# ── Bouton de téléchargement persistant (hors du if st.button) ───────────────
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

# ── AUTO-REFRESH ──────────────────────────────────────────────────────────────
if st.session_state.running:
    time.sleep(1)
    st.rerun()
