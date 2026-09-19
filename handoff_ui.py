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


# ── Tri par urgence (priorite puis date) ───────────────────────────────────────
_PRIO_RANK = {"P1 - Critique": 1, "P2 - Haute": 2, "P3 - Normale": 3, "P4 - Basse": 4}


def _tri_urgence(i):
    return (_PRIO_RANK.get(str(i.get("priorite") or ""), 9),
            str(i.get("date") or "9999-12-31"))


def _table_interv_lionel(rows, actionnable=False):
    """Tableau compact d'interventions. Si actionnable, un bouton 'Traiter'
    selectionne l'intervention (ouvre le panneau consigne/CR sur la page)."""
    widths = [3.4, 1.0, 1.9, 1.3, 1.2, 1.5]
    labels = ["Intervention", "Machine", "Type", "Priorité", "Date",
              "Action" if actionnable else "Statut"]
    header = st.columns(widths)
    for col, label in zip(header, labels):
        col.markdown("**" + label + "**")
    st.markdown("<hr style='margin:2px 0 6px 0;border:none;border-top:1px solid #d0d0d0'>",
                unsafe_allow_html=True)
    for i in rows:
        iid = i.get("id")
        c = st.columns(widths)
        c[0].write(str(i.get("titre", "Intervention")))
        c[1].write(str(i.get("machine", "-")))
        c[2].write(str(i.get("type", "-")))
        c[3].write(str(i.get("priorite")) if i.get("priorite") else "-")
        c[4].write(str(i.get("date")) if i.get("date") else "-")
        if actionnable:
            if c[5].button("▶️ Traiter", key="trait_" + str(iid), use_container_width=True):
                st.session_state["intervention_active"] = i
                st.rerun()
        else:
            c[5].caption("⏳ HSE")


def tables_interventions_lionel(nom_technicien="Lionel"):
    """Deux listes triees par urgence (priorite puis date) : pretes a lancer
    (validees HSE, statut En cours) et en attente HSE (statut Planifiee).
    La consigne de l'agent est figee sur l'intervention des l'affectation ;
    'Traiter' ouvre le panneau de consigne + compte-rendu plus bas sur la page."""
    def _miennes(statut):
        return sorted(
            [i for i in _interventions(statut=statut)
             if nom_technicien.lower() in str(i.get("technicien", "")).lower()],
            key=_tri_urgence)

    pretes = _miennes("En cours")
    attente = _miennes("Planifiée")

    st.markdown("#### ✅ Prêtes à lancer (validées HSE)")
    if pretes:
        _table_interv_lionel(pretes, actionnable=True)
    else:
        st.caption("Aucune intervention validée par la HSE pour le moment.")

    st.markdown("#### ⏳ En attente de validation HSE")
    if attente:
        _table_interv_lionel(attente, actionnable=False)
    else:
        st.caption("Aucune intervention en attente de validation.")
    st.divider()



# ── Prescription agent P-17 (generee a l'affectation, figee sur l'intervention) ─
def _prescription_p17_fallback(c_temp, c_vib, c_pres, c_rul):
    """Procedure corrective P-17 standard, utilisee si le LLM est indisponible."""
    return (
        "### 🔧 DÉCISION — Intervention corrective immédiate P-17\n\n"
        "**Fenêtre :** sous 24 h (RUL estimé " + str(c_rul) + " j — seuil critique franchi)\n\n"
        "**Diagnostic :** surchauffe (" + str(c_temp) + " °C) et vibration élevée ("
        + str(c_vib) + " mm/s) → dégradation du roulement **6205-2RS** en fin de vie.\n\n"
        "**Procédure (≈ 35 min) :**\n"
        "1. Consigner (LOTO) : ouvrir le disjoncteur **Q-17A**\n"
        "2. Isoler : fermer les vannes **V-17A** (amont) et **V-17B** (aval)\n"
        "3. Purger le carter via le point **PT-17**\n"
        "4. Remplacer le roulement **6205-2RS** (kit **B-07**)\n"
        "5. Graisser **Mobilux EP2** — couple carter **45 N·m**\n"
        "6. Redémarrer, vérifier **débit 45 m³/h** et **vibration < 1.5 mm/s**\n\n"
        "**Sécurité :** gants + lunettes + chaussures S3, cadenas LOTO obligatoire."
    )


def generer_prescription_p17(c_temp, c_vib, c_pres, c_rul):
    """Genere la recommandation de l'agent pour P-17 (surchauffe). Repli statique
    si le LLM (1min.ai) est indisponible. Le texte retourne est destine a etre
    ecrit sur l'intervention (Notion) au moment de l'affectation par Sophie."""
    try:
        from agents.agent_lionel import run_agent_lionel
        txt = run_agent_lionel(c_temp, c_vib, c_pres, c_rul)
        if txt and len(str(txt).strip()) > 40:
            return str(txt)
    except Exception:
        pass
    return _prescription_p17_fallback(c_temp, c_vib, c_pres, c_rul)



def popup_lionel(nom_technicien="Lionel"):
    """Pop-up chez Lionel des qu'une intervention Planifiée lui est affectee.
    Renvoie True si un dialog a ete ouvert (pour eviter d'en ouvrir un 2e)."""
    if not _HAS_DIALOG:
        return False
    vues = st.session_state.setdefault("_lionel_popup_vues", set())
    nouvelles = [i for i in _interventions(statut="Planifiée")
                 if nom_technicien.lower() in str(i.get("technicien", "")).lower()
                 and i.get("id") and i["id"] not in vues]
    if not nouvelles:
        return False
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
    return True


def popup_lionel_hse_ok(nom_technicien="Lionel"):
    """2e pop-up chez Lionel : Leila a valide (statut En cours) -> feu vert HSE."""
    if not _HAS_DIALOG:
        return False
    vues = st.session_state.setdefault("_lionel_hse_ok_vues", set())
    ok = [i for i in _interventions(statut="En cours")
          if nom_technicien.lower() in str(i.get("technicien", "")).lower()
          and i.get("id") and i["id"] not in vues]
    if not ok:
        return False
    interv = ok[0]

    @st.dialog("Feu vert HSE - tu peux demarrer")
    def _dlg():
        st.success("Leila (HSE) a autorise l'intervention " + str(interv.get("machine", "P-17")) + ".")
        st.markdown("Les consignes sont poussees sur tes lunettes G2. Tu peux demarrer l'intervention.")
        if st.button("Demarrer l'intervention", use_container_width=True, type="primary"):
            vues.add(interv["id"])
            st.rerun()

    _dlg()
    return True


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


def liste_validation_leila(machine=None):
    """Recap (tableau) des interventions en attente de validation HSE.
    Le bouton "Verifier" ouvre une checklist HSE obligatoire ; l'autorisation
    n'est possible que si tous les controles sont coches.
      Autoriser -> statut "En cours" (declenche le pop-up feu vert chez Lionel).
      Decliner  -> statut "Reportee" (refus HSE)."""
    a_valider = _interventions(statut="Planifiée", machine=machine)
    st.markdown("#### 🛡️ Interventions à valider (HSE)")
    if not a_valider:
        st.info("Aucune intervention en attente de validation HSE.")
        return

    widths = [3.6, 1.0, 1.9, 2.0, 1.3, 1.4]
    header = st.columns(widths)
    for col, label in zip(header, ["Intervention", "Machine", "Technicien",
                                   "Type", "Priorité", "Action"]):
        col.markdown("**" + label + "**")
    st.markdown("<hr style='margin:2px 0 6px 0;border:none;border-top:1px solid #d0d0d0'>",
                unsafe_allow_html=True)

    for interv in a_valider:
        iid = interv.get("id")
        c = st.columns(widths)
        c[0].write(str(interv.get("titre", "Intervention")))
        c[1].write(str(interv.get("machine", "-")))
        c[2].write(str(interv.get("technicien")) if interv.get("technicien") else "-")
        c[3].write(str(interv.get("type", "-")))
        c[4].write(str(interv.get("priorite")) if interv.get("priorite") else "-")
        if c[5].button("🔍 Vérifier", key="hse_check_" + str(iid)):
            st.session_state["_leila_verif"] = iid
            st.rerun()
    st.divider()

    # ── Checklist HSE obligatoire (dialog) ─────────────────────────────────────
    vid = st.session_state.get("_leila_verif")
    if not vid:
        return
    interv = next((i for i in a_valider if i.get("id") == vid), None)
    if interv is None:
        st.session_state.pop("_leila_verif", None)
        return
    if not _HAS_DIALOG:
        return

    @st.dialog("Contrôle HSE avant autorisation")
    def _dlg():
        st.markdown("**" + str(interv.get("titre", "Intervention")) + "** — "
                    + str(interv.get("machine", "-")))
        hab = interv.get("habilitations")
        if hab:
            st.caption("Habilitation requise : "
                       + (", ".join(hab) if isinstance(hab, list) else str(hab)))
        st.markdown("Contrôles obligatoires avant intervention :")
        c1 = st.checkbox("EPI adaptés portés", key="epi_a_" + str(vid))
        c2 = st.checkbox("Consignation électrique (LOTO)", key="epi_b_" + str(vid))
        c3 = st.checkbox("Circuit purgé / pression contrôlée", key="epi_c_" + str(vid))
        c4 = st.checkbox("Habilitation du technicien vérifiée", key="epi_d_" + str(vid))
        tous = c1 and c2 and c3 and c4
        if not tous:
            st.warning("Coche les 4 contrôles pour pouvoir autoriser l'intervention.")
        if st.button("✅ AUTORISER L'INTERVENTION", disabled=not tous,
                     type="primary", use_container_width=True, key="auth_" + str(vid)):
            try:
                nc.set_statut_intervention(
                    vid, "En cours",
                    note="Autorisée HSE — EPI, consignation, pression, habilitation vérifiés — écart HSE : 0")
                st.session_state.pop("_leila_verif", None)
                st.success("Intervention autorisée — envoyée à Lionel.")
                st.rerun()
            except Exception as e:
                st.error("Échec Notion : " + str(e))
        if st.button("✖ Décliner (sécurité non réunie)", use_container_width=True,
                     key="decl_" + str(vid)):
            try:
                nc.set_statut_intervention(
                    vid, "Reportée",
                    note="Refusée par la HSE - conditions de sécurité non réunies.")
                st.session_state.pop("_leila_verif", None)
                st.warning("Intervention refusée (reportée).")
                st.rerun()
            except Exception as e:
                st.error("Échec Notion : " + str(e))

    _dlg()

def banniere_sophie_cloture(machine="P-17"):
    """Banniere chez Sophie quand une intervention est cloturee (Réalisée)."""
    if _interventions(statut="Réalisée", machine=machine):
        st.success("Intervention " + machine + " cloturee par le technicien - rapport disponible dans l'historique.")
