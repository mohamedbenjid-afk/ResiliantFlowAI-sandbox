import streamlit as st

# ── CONFIG PAGE ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ResilientFlow AI",
    page_icon="⚙️",
    layout="wide"
)

# ── NAVIGATION (API moderne Streamlit ≥ 1.36) ─────────────────────────────────
# Définition des pages — st.navigation gère le routing automatiquement
pg = st.navigation(
    [
        st.Page("streamlit_home.py",    title="Accueil",          icon="🏠", default=True),
        st.Page("pages/1_Lionel.py",   title="Lionel — Terrain", icon="🔧"),
        st.Page("pages/2_Sophie.py",   title="Sophie — Manager", icon="📋"),
        st.Page("pages/3_Antoine.py",  title="Antoine — Directeur", icon="📊"),
        st.Page("pages/4_Leila.py",    title="Leila — HSE",      icon="🛡️"),
    ],
    position="hidden"   # On masque la nav auto Streamlit, on gère nous-mêmes
)
pg.run()
