import streamlit as st

# ── STYLE CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
    <style>
    .stApp { background-color: #ffffff; }
    .escp-banner {
        background-color: #002349; color: #ffffff;
        padding: 12px; border-radius: 4px; text-align: center;
        margin-top: 5px; margin-bottom: 15px; font-size: 0.85rem;
        border-left: 4px solid #d4af37;
    }
    .profile-card {
        background-color: #f8fafc; border: 1px solid #e2e8f0;
        border-radius: 10px; padding: 24px 20px; text-align: center;
        height: 100%;
    }
    .profile-icon  { font-size: 2.8rem; margin-bottom: 10px; }
    .profile-title { font-size: 1.1rem; font-weight: 700; color: #1e293b; margin-bottom: 4px; }
    .profile-role  { font-size: 0.82rem; color: #64748b; margin-bottom: 14px; }
    .profile-desc  { font-size: 0.80rem; color: #475569; line-height: 1.5; margin-bottom: 16px; }
    .hero-title    { font-size: 2.4rem; font-weight: 800; color: #002349; margin-bottom: 4px; }
    .hero-subtitle { font-size: 1.05rem; color: #475569; margin-bottom: 24px; }
    .status-badge  {
        display: inline-block; background-color: #dcfce7; color: #166534;
        border-radius: 20px; padding: 3px 14px; font-size: 0.78rem;
        font-weight: 600; margin-bottom: 30px;
    }
    </style>
""", unsafe_allow_html=True)

# ── BANNIÈRE ──────────────────────────────────────────────────────────────────
st.markdown("""
    <div class="escp-banner">
        🎓 <b>Projet de Fin d'Études ESCP</b> &nbsp;|&nbsp;
        ⚙️ Sujet : <i>Maintenance Prescriptive & Industrie 4.0</i>
    </div>
""", unsafe_allow_html=True)

col_title, col_status = st.columns([3, 1])
with col_title:
    st.markdown('<div class="hero-title">⚙️ ResilientFlow AI</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-subtitle">Tableau de bord prescriptif — Couche IA v1 · Pompe P-17, Unité B</div>', unsafe_allow_html=True)
with col_status:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<span class="status-badge">✅ Système opérationnel</span>', unsafe_allow_html=True)

st.markdown("---")
st.markdown("### Sélectionnez votre espace de travail")
st.markdown(
    "Cette plateforme fournit une **vue adaptée à chaque métier** : de l'intervention terrain "
    "jusqu'à la décision stratégique, en passant par la planification et la conformité HSE."
)
st.markdown("<br>", unsafe_allow_html=True)

# ── 4 CARTES ─────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)

CARD_STYLE = "background-color:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:24px 20px;text-align:center;margin-bottom:12px;"
BTN_STYLE  = "width:100%;background:#002349;color:white;border:none;border-radius:6px;padding:10px 0;font-size:0.9rem;cursor:pointer;"

profiles = [
    (c1, "🔧", "Lionel",   "Technicien Terrain",
     "Accès temps réel aux capteurs, RUL, courbes de tendance, scénarios de défaillance et fiches GitHub.",
     "pages/1_Lionel.py", "➜ Ouvrir le terminal terrain"),
    (c2, "📋", "Sophie",   "Manager Maintenance",
     "Arbitrage planification, gestion des ressources humaines, stocks de pièces et ordonnancement.",
     "pages/2_Sophie.py", "➜ Ouvrir l'espace d'arbitrage"),
    (c3, "📊", "Antoine",  "Directeur Technique",
     "KPIs stratégiques, ROI de la couche prescriptive, simulation CAPEX vs OPEX et renouvellement matériel.",
     "pages/3_Antoine.py", "➜ Ouvrir le tableau stratégique"),
    (c4, "🛡️", "Leila",   "Responsable HSE",
     "Conformité ISO 45001, matrices de risques, EPI requis et génération automatique des dossiers d'audit.",
     "pages/4_Leila.py", "➜ Ouvrir l'espace HSE"),
]

for col, icon, name, role, desc, page_path, btn_label in profiles:
    with col:
        st.markdown(f"""
            <div style="{CARD_STYLE}">
                <div style="font-size:2.8rem;margin-bottom:10px;">{icon}</div>
                <div style="font-size:1.1rem;font-weight:700;color:#1e293b;margin-bottom:4px;">{name}</div>
                <div style="font-size:0.82rem;color:#64748b;margin-bottom:14px;">{role}</div>
                <div style="font-size:0.80rem;color:#475569;line-height:1.5;margin-bottom:16px;">{desc}</div>
            </div>
        """, unsafe_allow_html=True)
        if st.button(btn_label, key=f"btn_{name}", use_container_width=True, type="primary"):
            st.switch_page(page_path)

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("---")
st.caption("ResilientFlow AI · Couche Prescriptive v1 · Machine surveillée : Pompe P-17 — Unité B")
