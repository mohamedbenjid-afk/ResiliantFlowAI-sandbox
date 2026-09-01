# notify.py
# Notification email d'alerte critique — ResilientFlow AI (persona Lionel).
# Envoie au technicien référent de la machine un email contenant l'alerte
# + le récap de la recommandation de l'agent IA.
#
# Ce module N'ALTÈRE PAS les fichiers protégés : il réutilise les fonctions
# internes de notion_client (DB_IDS, _query_db, _prop) en lecture seule.
#
# Secrets attendus (Streamlit Cloud → Settings → Secrets, ou variables d'env) :
#   GMAIL_ADDRESS       = "boite.dediee@gmail.com"      # compte expéditeur
#   GMAIL_APP_PASSWORD  = "xxxxxxxxxxxxxxxx"            # mot de passe d'application Gmail
#   ALERT_FROM_NAME     = "ResilientFlow AI — Alerte"   # (optionnel)

import os
import smtplib
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import notion_client as nc


def _secret(key: str, default: str = "") -> str:
    """Lit un secret depuis st.secrets (Streamlit Cloud) ou os.environ."""
    try:
        import streamlit as st
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, default)


# ── Résolution du destinataire depuis Notion ─────────────────────────────────
def _read_email(page: dict) -> str:
    """Lit une propriété Notion de type 'email' (non géré par notion_client._prop)."""
    p = page.get("properties", {}).get("Email", {})
    return p.get("email") or ""


def get_referent_email(machine_id: str = "P-17") -> tuple[str, str]:
    """Retourne (nom_referent, email) du technicien référent de la machine.
    Renvoie (nom, "") si aucun email n'est trouvé."""
    machine = nc.get_machine(machine_id) or {}
    referent = (machine.get("responsable") or "").strip()
    if not referent:
        return ("", "")

    # Parcourt la base Équipe et matche sur le nom complet ou le nom de famille
    pages = nc._query_db(nc.DB_IDS["equipe"])
    ref_low = referent.lower()
    for p in pages:
        prenom = (nc._prop(p, "Prénom") or "").strip()
        nom    = (nc._prop(p, "Nom Technicien") or "").strip()
        email  = _read_email(p)          # type 'email' lu directement
        complet = f"{prenom} {nom}".strip().lower()
        if email and (complet == ref_low or (nom and nom.lower() in ref_low)):
            return (referent, email)
    return (referent, "")


# ── Envoi SMTP Gmail ─────────────────────────────────────────────────────────
def _send_email(to_email: str, subject: str, text_body: str, html_body: str = None) -> dict:
    sender = _secret("GMAIL_ADDRESS")
    password = _secret("GMAIL_APP_PASSWORD")
    from_name = _secret("ALERT_FROM_NAME", "ResilientFlow AI — Alerte")

    if not sender or not password:
        return {"ok": False, "skipped": True,
                "error": "Secrets GMAIL_ADDRESS / GMAIL_APP_PASSWORD non configurés"}

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{sender}>"
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    if html_body:
        msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(sender, password)
            server.sendmail(sender, [to_email], msg.as_string())
        return {"ok": True, "skipped": False, "to": to_email}
    except Exception as e:
        return {"ok": False, "skipped": False, "error": str(e), "to": to_email}


# ── Point d'entrée : alerte critique ─────────────────────────────────────────
def envoyer_alerte_critique(machine_id: str, rul_jours, reco_markdown: str) -> dict:
    """Envoie l'alerte critique au référent de la machine.
    Retourne un dict : {ok, to, ref, skipped?, error?}."""
    ref_nom, email = get_referent_email(machine_id)
    if not email:
        return {"ok": False, "skipped": True, "ref": ref_nom,
                "error": f"Aucun email trouvé pour le référent « {ref_nom or '?'} »"}

    horodatage = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    machine_label = "Pompe P-17" if machine_id == "P-17" else machine_id
    subject = f"🔴 ALERTE CRITIQUE {machine_label} — RUL {rul_jours} j — action requise"

    text_body = (
        f"ALERTE MAINTENANCE PRESCRIPTIVE — ResilientFlow AI\n"
        f"{'='*52}\n\n"
        f"Machine   : {machine_label} (Unité B)\n"
        f"Statut    : CRITIQUE\n"
        f"RUL estimé: {rul_jours} jour(s)\n"
        f"Détecté le: {horodatage}\n"
        f"Référent  : {ref_nom}\n\n"
        f"RECOMMANDATION DE L'AGENT IA\n"
        f"{'-'*52}\n"
        f"{reco_markdown}\n\n"
        f"{'-'*52}\n"
        f"Email automatique — ne pas répondre. "
        f"Ouvrir l'app ResilientFlow AI pour le détail (onglets K0/K2)."
    )

    html_body = (
        f"<div style='font-family:Arial,sans-serif;max-width:640px;'>"
        f"<div style='background:#b91c1c;color:#fff;padding:14px 18px;border-radius:6px;'>"
        f"<b>🔴 ALERTE CRITIQUE — {machine_label}</b><br>"
        f"<span style='font-size:0.9rem;'>RUL estimé : <b>{rul_jours} jour(s)</b> — action immédiate requise</span>"
        f"</div>"
        f"<p style='color:#374151;'>Machine <b>{machine_label}</b> (Unité B) — détecté le {horodatage} — "
        f"référent : <b>{ref_nom}</b>.</p>"
        f"<h3 style='color:#111827;'>🤖 Recommandation de l'agent IA</h3>"
        f"<pre style='white-space:pre-wrap;background:#f8fafc;border:1px solid #e2e8f0;"
        f"border-radius:6px;padding:14px;font-family:inherit;font-size:0.92rem;color:#1e293b;'>"
        f"{reco_markdown}</pre>"
        f"<p style='color:#94a3b8;font-size:0.8rem;'>Email automatique ResilientFlow AI — ne pas répondre.</p>"
        f"</div>"
    )

    res = _send_email(email, subject, text_body, html_body)
    res["ref"] = ref_nom
    return res
