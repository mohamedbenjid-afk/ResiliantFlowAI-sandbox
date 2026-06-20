import streamlit as st
import time
import sys, os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from shared_state import (
    init_session_state, update_sensors, CONTEXTE_USINE, COMMON_CSS
)

# ── CONFIG PAGE ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Sophie — Arbitrage & Planification", page_icon="📋", layout="wide")
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
st.markdown("### 📋 Espace d'Arbitrage et Pilotage des Ressources — Sophie")
st.markdown("*Résolution des conflits de planification (Équipes, Pièces détachées, Fenêtres de production).*")

if c_rul <= 24:
    st.error("🚨 **ALERTE CRITIQUE POMPE P-17 : Arbitrage requis immédiatement**")

    c_prod, c_stock = st.columns(2)
    with c_prod:
        st.info(
            "**Contexte de Production Actif :**\n\n"
            "• Ordre en cours : " + CONTEXTE_USINE["production"]["ordre_fabrication_actif"] + "\n\n"
            "• Ligne impactée : " + CONTEXTE_USINE["production"]["ligne_concerne"] + "\n\n"
            "• Coût d'arrêt horaire : " + str(CONTEXTE_USINE["production"]["cout_arret_heure"]) + " €/h"
        )
    with c_stock:
        st.warning(
            "**Disponibilité Pièces en Magasin :**\n\n" +
            CONTEXTE_USINE["stocks"]["pieces_disponibles"]
        )

    st.markdown("---")
    st.markdown("#### 🔮 Simulateur d'impact sur la planification")

    action_planif = st.radio(
        "Sélectionner une option d'ordonnancement :",
        [
            "🎯 Intervenir immédiatement (Arrêt court coordonné avec la prod)",
            "⏳ Reporter la maintenance à la fin de la semaine prochaine",
        ]
    )

    if action_planif == "⏳ Reporter la maintenance à la fin de la semaine prochaine":
        st.markdown(
            "<div style='background-color:#fef2f2;border-left:5px solid #ef4444;"
            "padding:15px;border-radius:4px;'>"
            "❌ <b>RISQUE DE CASSE EN EXPLOITATION DIRECTE : 87%</b><br>"
            "Le RUL calculé par l'agent AI s'épuisera avant la date visée.<br>"
            "<b>Perte de marge sèche projetée : 45 500 €</b> "
            "(7 heures d'arrêt non maîtrisé en plein pic de charge).</div>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            "<div style='background-color:#f0fdf4;border-left:5px solid #10b981;"
            "padding:15px;border-radius:4px;'>"
            "✅ <b>STRATÉGIE SÉCURISÉE (Arbitrage validé par l'IA)</b><br>"
            "Arrêt planifié en période creuse. La production bascule automatiquement sur la ligne de secours.<br>"
            "<b>Coût financier maîtrisé : 0 € de pénalités.</b></div>",
            unsafe_allow_html=True
        )

    st.markdown("---")
    st.markdown("#### 👥 Gestion de la charge et assignation d'équipe")
    st.write("L'agent analyse les profils pour recommander le technicien disponible possédant le bon niveau d'accréditation.")
    st.success("👉 **Affectation optimale trouvée :** " + CONTEXTE_USINE["equipe"]["technicien_recommande"])
    st.caption("Alternative non retenue : " + CONTEXTE_USINE["equipe"]["technicien_secondaire"])

    if st.button("Confirmer l'affectation et envoyer l'ordre de travail", use_container_width=True):
        st.success("Ordre d'intervention généré. Fiche technique GitHub poussée sur le terminal terrain de Lionel.")

else:
    st.success("✅ **Unité B nominale.** L'agent IA n'a détecté aucun goulot d'étranglement "
               "ni besoin d'arbitrage en urgence.")

# ── AUTO-REFRESH ──────────────────────────────────────────────────────────────
if st.session_state.running:
    time.sleep(1)
    st.rerun()
