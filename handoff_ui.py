# handoff_ui.py
# Pop-ups et notifications inter-personas du scenario P-17.
# Les personas tournent dans des sessions Streamlit differentes : l'etat
# transite par Notion (champ Statut de l'intervention), pas par st.session_state.
# Cycle : Planifiée (Sophie affecte) -> En cours (Leila autorise HSE) -> Réalisée (Lionel cloture)

import streamlit as st
import notion_client as nc

_HAS_DIALOG = hasattr(st, "dialog")


def _interventions(statut=None, machine=None):
    try:
        items = nc.get_historique(limit=50) or []
    except Exception:
        return []
    out = []
    for i in items:
        if statut and str(i.get("statut", "")) != statut:
            continue
        if machine and machine.lower() not in str(i.get("machine", "")).lower():
            continue
        out.append(i)
    return out


def popup_lionel(nom_technicien="Lionel"):
    """Pop-up chez Lionel des qu'une intervention Planifiée lui est affectee."""
    if not _HAS_DIALOG:
        return
    vues = st.session_state.setdefault("_lionel_popup_vues", set())
    nouvelles = [i for i in _interventions(statut="Planifiée")
                 if nom_technicien.lower() in str(i.get("technicien", "")).lower()
                 and i.get("id") and i["id"] not in vues]
    if not nouvelles:
        return
    interv = nouvelles[0]

    @st.dialog("Nouvelle intervention assignee")
    def _dlg():
        st.markdown("### Nouvelle intervention assignee par Sophie")
        st.markdown("**Intervention :** " + str(interv.get("titre", "Intervention")))
        st.markdown("**Equipement :** " + str(interv.get("machine", "P-17")))
        st.markdown("**Type :** " + str(interv.get("type", "-")))
        st.warning("Statut : en attente de validation HSE (Leila) avant demarrage.")
        st.info("Tu recevras le feu vert des que Leila aura valide la securite.")
        if st.button("OK, vu", use_container_width=True, type="primary"):
            vues.add(interv["id"])
            st.rerun()

    _dlg()


def popup_lionel_hse_ok(nom_technicien="Lionel"):
    """2e pop-up chez Lionel : Leila a valide (statut En cours) -> feu vert HSE."""
    if not _HAS_DIALOG:
        return
    vues = st.session_state.setdefault("_lionel_hse_ok_vues", set())
    ok = [i for i in _interventions(statut="En cours")
          if nom_technicien.lower() in str(i.get("technicien", "")).lower()
          and i.get("id") and i["id"] not in vues]
    if not ok:
        return
    interv = ok[0]

    @st.dialog("Feu vert HSE - tu peux demarrer")
    def _dlg():
        st.success("Leila (HSE) a autorise l'intervention " + str(interv.get("machine", "P-17")) + ".")
        st.markdown("Les consignes sont poussees sur tes lunettes G2. Tu peux demarrer l'intervention.")
        if st.button("Demarrer l'intervention", use_container_width=True, type="primary"):
            vues.add(interv["id"])
            st.rerun()

    _dlg()


def carte_etat_hse_lionel(nom_technicien="Lionel"):
    """Etat HSE de l'intervention de Lionel + cloture une fois autorisee."""
    mine = [i for i in (_interventions(statut="Planifiée") + _interventions(statut="En cours"))
            if nom_technicien.lower() in str(i.get("technicien", "")).lower()]
    if not mine:
        return
    interv = mine[0]
    statut = str(interv.get("statut", ""))
    machine = str(interv.get("machine", "P-17"))
    if statut == "Planifiée":
        st.warning("Intervention " + machine + " : en attente de validation HSE de Leila avant de demarrer.")
    elif statut == "En cours":
        st.success("Intervention " + machine + " autorisee par la HSE - prete a demarrer.")
        if interv.get("id") and st.button("Marquer l'intervention terminee", type="primary"):
            try:
                nc.set_statut_intervention(interv["id"], "Réalisée",
                                           note="Intervention realisee et cloturee par le technicien.")
                st.success("Intervention cloturee. Sophie en est notifiee.")
                st.rerun()
            except Exception as e:
                st.error("Echec Notion : " + str(e))


def popup_leila_validation(machine="P-17"):
    """Pop-up chez Leila : intervention Planifiée a valider (gate HSE)."""
    if not _HAS_DIALOG:
        return
    traitees = st.session_state.setdefault("_leila_popup_traitees", set())
    a_valider = [i for i in _interventions(statut="Planifiée", machine=machine)
                 if i.get("id") and i["id"] not in traitees]
    if not a_valider:
        return
    interv = a_valider[0]

    @st.dialog("Validation HSE requise")
    def _dlg():
        st.markdown("### Validation HSE requise")
        st.markdown("**Intervention :** " + str(interv.get("titre", "Intervention"))
                    + " (" + str(interv.get("machine", machine)) + ")")
        st.markdown("Controles requis avant intervention :")
        st.markdown("- EPI adaptes")
        st.markdown("- Consignation electrique (LOTO)")
        st.markdown("- Pression controlee")
        st.markdown("- Habilitation du technicien")
        c1, c2 = st.columns(2)
        if c1.button("Autoriser l'intervention", use_container_width=True, type="primary"):
            try:
                nc.set_statut_intervention(interv["id"], "En cours",
                                           note="Autorisee HSE (EPI, consignation, habilitation) - ecart HSE : 0")
                st.session_state["_leila_last_auth"] = interv.get("machine", machine)
            except Exception as e:
                st.error("Echec de la mise a jour Notion : " + str(e))
                return
            traitees.add(interv["id"])
            st.rerun()
        if c2.button("Plus tard", use_container_width=True):
            traitees.add(interv["id"])
            st.rerun()

    _dlg()


def banniere_sophie_cloture(machine="P-17"):
    """Banniere chez Sophie quand une intervention est cloturee (Réalisée)."""
    if _interventions(statut="Réalisée", machine=machine):
        st.success("Intervention " + machine + " cloturee par le technicien - rapport disponible dans l'historique.")
