# p17_context.py
# Contexte terrain FIXE de la Pompe P-17 — SOURCE UNIQUE partagée par
# l'agent (agents/agent_lionel.py) et la procédure K2 (pages/1_Lionel.py).
# But : éviter que l'agent invente des références et garantir la cohérence
# agent ↔ K2. Toute ref terrain P-17 doit venir d'ici.

P17_CONTEXT = {
    "machine":          "Pompe P-17",
    "unite":            "Unité B",
    # ── Consignation LOTO ────────────────────────────────────────────────
    "disjoncteur":      "Q-17A",
    "vanne_amont":      "V-17A",
    "vanne_aval":       "V-17B",
    "point_purge":      "PT-17",
    # ── Magasin / consommables ───────────────────────────────────────────
    "kit_casier":       "B-07",
    "graisse":          "Mobilux EP2",
    "roulement_ref":    "6205-2RS",
    "couple_carter_nm": 45,
    # ── Critères de remise en service ────────────────────────────────────
    "valid_temp_max":   70,      # °C
    "valid_vib_max":    1.5,     # mm/s
    "valid_pres_min":   3.5,     # bar
    # ── Production (source : Notion Ordres de Fabrication — OF-2026-89A) ──
    "of_actif":         "OF-2026-89A — Série hydraulique XR7",
    "cout_arret_eur_h": 6500,    # €/h sur Unité B
    "ligne_secours":    True,     # pompe de secours disponible
}


def cout_arret_estime(heures: float) -> int:
    """Coût d'arrêt production estimé pour une durée d'immobilisation (heures)."""
    return int(P17_CONTEXT["cout_arret_eur_h"] * max(0.0, heures))


def prompt_context() -> str:
    """Bloc CONTEXTE FIXE P-17 injecté dans le prompt système de l'agent."""
    c = P17_CONTEXT
    secours = "disponible" if c["ligne_secours"] else "indisponible"
    return (
        "CONTEXTE FIXE P-17 (utilise ces références, n'en invente aucune autre) :\n"
        f"- LOTO : disjoncteur {c['disjoncteur']}, vannes {c['vanne_amont']} (amont) / "
        f"{c['vanne_aval']} (aval), purge {c['point_purge']}.\n"
        f"- Magasin : kit casier {c['kit_casier']}, roulement réf {c['roulement_ref']}, "
        f"graisse {c['graisse']}, couple carter {c['couple_carter_nm']} N·m.\n"
        f"- Remise en service validée si : T < {c['valid_temp_max']} °C, "
        f"vib < {c['valid_vib_max']} mm/s, P > {c['valid_pres_min']} bar.\n"
        f"- Production : {c['of_actif']} en cours sur {c['unite']}, "
        f"coût d'arrêt {c['cout_arret_eur_h']} €/h, ligne de secours {secours}."
    )
