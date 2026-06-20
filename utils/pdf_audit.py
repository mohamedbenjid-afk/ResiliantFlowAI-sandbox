"""
utils/pdf_audit.py
Générateur de Dossier de Preuve de Conformité ISO 45001:2018
pour les interventions de maintenance sur la Pompe P-17.

Usage:
    from utils.pdf_audit import generate_audit_pdf
    pdf_bytes = generate_audit_pdf(context)
    st.download_button("Télécharger", pdf_bytes, file_name="RF_AUDIT_...pdf")
"""

import io
import hashlib
from datetime import datetime, date
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.colors import HexColor, white, black, Color
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle,
    Spacer, HRFlowable, KeepTogether, PageBreak
)
from reportlab.platypus.flowables import Flowable

# ── PALETTE ───────────────────────────────────────────────────────────────────
BLEU_FONCE   = HexColor("#1e3a5f")
BLEU_MOYEN   = HexColor("#2563eb")
BLEU_CLAIR   = HexColor("#dbeafe")
AMBRE        = HexColor("#d97706")
AMBRE_CLAIR  = HexColor("#fef3c7")
ROUGE        = HexColor("#dc2626")
ROUGE_CLAIR  = HexColor("#fee2e2")
VERT         = HexColor("#16a34a")
VERT_CLAIR   = HexColor("#dcfce7")
ORANGE       = HexColor("#ea580c")
ORANGE_CLAIR = HexColor("#ffedd5")
GRIS_FONCE   = HexColor("#374151")
GRIS_MOYEN   = HexColor("#6b7280")
GRIS_CLAIR   = HexColor("#f3f4f6")
GRIS_TRES_CLAIR = HexColor("#f9fafb")

W, H = A4

# ── STYLES ────────────────────────────────────────────────────────────────────
def _styles():
    base = getSampleStyleSheet()
    s = {}
    s["titre_doc"] = ParagraphStyle(
        "titre_doc", fontName="Helvetica-Bold", fontSize=20,
        textColor=white, alignment=TA_CENTER, spaceAfter=4
    )
    s["sous_titre"] = ParagraphStyle(
        "sous_titre", fontName="Helvetica", fontSize=11,
        textColor=HexColor("#93c5fd"), alignment=TA_CENTER, spaceAfter=2
    )
    s["ref_doc"] = ParagraphStyle(
        "ref_doc", fontName="Helvetica-Bold", fontSize=9,
        textColor=AMBRE, alignment=TA_CENTER
    )
    s["section"] = ParagraphStyle(
        "section", fontName="Helvetica-Bold", fontSize=11,
        textColor=white, spaceBefore=4, spaceAfter=2, leftIndent=0
    )
    s["body"] = ParagraphStyle(
        "body", fontName="Helvetica", fontSize=9,
        textColor=GRIS_FONCE, leading=13, spaceAfter=3
    )
    s["body_bold"] = ParagraphStyle(
        "body_bold", fontName="Helvetica-Bold", fontSize=9,
        textColor=GRIS_FONCE, leading=13
    )
    s["small"] = ParagraphStyle(
        "small", fontName="Helvetica", fontSize=8,
        textColor=GRIS_MOYEN, leading=11
    )
    s["footer"] = ParagraphStyle(
        "footer", fontName="Helvetica", fontSize=7.5,
        textColor=GRIS_MOYEN, alignment=TA_CENTER
    )
    s["cell"] = ParagraphStyle(
        "cell", fontName="Helvetica", fontSize=8.5,
        textColor=GRIS_FONCE, leading=11
    )
    s["cell_bold"] = ParagraphStyle(
        "cell_bold", fontName="Helvetica-Bold", fontSize=8.5,
        textColor=GRIS_FONCE, leading=11
    )
    s["cell_white"] = ParagraphStyle(
        "cell_white", fontName="Helvetica-Bold", fontSize=8.5,
        textColor=white, leading=11
    )
    s["conforme"] = ParagraphStyle(
        "conforme", fontName="Helvetica-Bold", fontSize=10,
        textColor=VERT, alignment=TA_CENTER
    )
    return s


# ── HELPERS ───────────────────────────────────────────────────────────────────
def _section_header(text, styles, num=None):
    """Bloc titre de section avec fond bleu foncé."""
    label = f"{num}. {text}" if num else text
    data = [[Paragraph(label, styles["section"])]]
    t = Table(data, colWidths=[W - 4*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), BLEU_FONCE),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ("RIGHTPADDING",  (0,0), (-1,-1), 10),
        ("ROUNDEDCORNERS", [4]),
    ]))
    return t


def _risk_color(level: str):
    if level in ("CRITIQUE", "ÉLEVÉ"):   return ROUGE,  ROUGE_CLAIR
    if level == "MOYEN":                  return ORANGE, ORANGE_CLAIR
    return VERT, VERT_CLAIR


def _prob_grav(val, seuil) -> tuple[int, int]:
    """Calcule probabilité et gravité à partir du rapport val/seuil."""
    ratio = val / seuil if seuil else 1
    if ratio >= 1.3:   return 4, 5
    if ratio >= 1.1:   return 3, 4
    if ratio >= 0.95:  return 3, 3
    if ratio >= 0.80:  return 2, 2
    return 1, 1


def _risk_level(prob: int, grav: int) -> str:
    score = prob * grav
    if score >= 12: return "CRITIQUE"
    if score >= 6:  return "ÉLEVÉ"
    if score >= 3:  return "MOYEN"
    return "FAIBLE"


def _hr(color=BLEU_CLAIR):
    return HRFlowable(width="100%", thickness=0.5, color=color, spaceAfter=4, spaceBefore=4)


def _sp(h=6):
    return Spacer(1, h)


# ── PAGE TEMPLATE (header / footer) ──────────────────────────────────────────
class _PageTemplate:
    def __init__(self, ref, date_str, equipement):
        self.ref = ref
        self.date_str = date_str
        self.equipement = equipement

    def __call__(self, canvas, doc):
        canvas.saveState()
        # ── En-tête ──
        canvas.setFillColor(BLEU_FONCE)
        canvas.rect(0, H - 1.4*cm, W, 1.4*cm, fill=1, stroke=0)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(white)
        canvas.drawString(1.5*cm, H - 0.9*cm, "⚡ ResilientFlow AI — Maintenance Prescriptive")
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(HexColor("#93c5fd"))
        canvas.drawRightString(W - 1.5*cm, H - 0.9*cm, f"Réf. {self.ref}")

        # ── Pied de page ──
        canvas.setFillColor(GRIS_CLAIR)
        canvas.rect(0, 0, W, 1.2*cm, fill=1, stroke=0)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(GRIS_MOYEN)
        canvas.drawString(1.5*cm, 0.45*cm,
            f"ISO 45001:2018 — Dossier de Preuve de Conformité — {self.equipement} — {self.date_str}")
        canvas.drawRightString(W - 1.5*cm, 0.45*cm,
            f"Page {doc.page}")
        canvas.setFillColor(BLEU_FONCE)
        canvas.rect(0, 1.2*cm, W, 0.05*cm, fill=1, stroke=0)
        canvas.restoreState()


# ── COVER PAGE ────────────────────────────────────────────────────────────────
def _cover(story, styles, ctx):
    ref  = ctx["reference"]
    now  = ctx["datetime_generation"]
    equi = ctx["equipement"]

    # Bloc bleu cover
    data = [[
        Paragraph("DOSSIER DE PREUVE DE CONFORMITÉ", styles["titre_doc"]),
        Paragraph("ISO 45001 : 2018 — Management de la Santé et Sécurité au Travail", styles["sous_titre"]),
        Paragraph(f"Réf. {ref}", styles["ref_doc"]),
    ]]
    cover_t = Table([[v] for v in data[0]], colWidths=[W - 4*cm])
    cover_t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), BLEU_FONCE),
        ("TOPPADDING",    (0,0), (-1,-1), 16),
        ("BOTTOMPADDING", (0,0), (-1,-1), 16),
        ("LEFTPADDING",   (0,0), (-1,-1), 24),
        ("RIGHTPADDING",  (0,0), (-1,-1), 24),
    ]))
    story.append(_sp(30))
    story.append(cover_t)
    story.append(_sp(20))

    # Tableau info couverture
    rows = [
        ["Organisation",       ctx.get("organisation", "Unité Industrielle B — Use case fictif")],
        ["Site / Zone",        ctx.get("site", "Unité B — Zone Production")],
        ["Équipement",         equi],
        ["Type d'anomalie",    ctx.get("type_anomalie", "Dégradation mécanique / thermique")],
        ["Technicien",         ctx.get("technicien", "Lionel")],
        ["Date de génération", now],
        ["Valide jusqu'au",    ctx.get("validite_fin", "—")],
        ["Norme de référence", "ISO 45001:2018"],
        ["Statut",             ctx.get("statut", "Généré — En attente de signature")],
    ]
    col_w = [(W - 4*cm) * r for r in [0.38, 0.62]]
    t = Table(rows, colWidths=col_w)
    t.setStyle(TableStyle([
        ("FONTNAME",  (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME",  (1,0), (1,-1), "Helvetica"),
        ("FONTSIZE",  (0,0), (-1,-1), 9),
        ("TEXTCOLOR", (0,0), (0,-1), BLEU_FONCE),
        ("TEXTCOLOR", (1,0), (1,-1), GRIS_FONCE),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [white, GRIS_TRES_CLAIR]),
        ("GRID",      (0,0), (-1,-1), 0.3, HexColor("#d1d5db")),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ("RIGHTPADDING",  (0,0), (-1,-1), 10),
        # Ligne statut en vert
        ("BACKGROUND", (0,8), (-1,8), VERT_CLAIR),
        ("TEXTCOLOR",  (1,8), (1,8),  VERT),
        ("FONTNAME",   (1,8), (1,8),  "Helvetica-Bold"),
    ]))
    story.append(t)
    story.append(_sp(20))

    # Signature électronique
    sig_hash = hashlib.sha256(f"{ref}{now}".encode()).hexdigest()[:32].upper()
    sig_data = [[
        Paragraph(
            f"<b>Signature électronique :</b> {sig_hash}<br/>"
            f"<font color='#6b7280' size='7'>Généré automatiquement par ResilientFlow AI · "
            f"Document fictif à des fins pédagogiques (ESCP Extension 2025)</font>",
            styles["small"]
        )
    ]]
    sig_t = Table(sig_data, colWidths=[W - 4*cm])
    sig_t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), AMBRE_CLAIR),
        ("LEFTPADDING",  (0,0), (-1,-1), 10),
        ("RIGHTPADDING", (0,0), (-1,-1), 10),
        ("TOPPADDING",   (0,0), (-1,-1), 8),
        ("BOTTOMPADDING",(0,0), (-1,-1), 8),
        ("BOX", (0,0), (-1,-1), 0.5, AMBRE),
    ]))
    story.append(sig_t)
    story.append(PageBreak())


# ── SECTION 1 : IDENTIFICATION ────────────────────────────────────────────────
def _section_identification(story, styles, ctx):
    story.append(_section_header("IDENTIFICATION DE L'INTERVENTION", styles, 1))
    story.append(_sp(6))

    machine = ctx.get("machine", {})
    rows = [
        [Paragraph("<b>Champ</b>", styles["cell_white"]),
         Paragraph("<b>Valeur</b>", styles["cell_white"])],
        ["Équipement",           ctx["equipement"]],
        ["ID Machine",           machine.get("id", "P-17")],
        ["Type machine",         machine.get("type", "Pompe centrifuge")],
        ["Unité / Zone",         machine.get("unite", "Unité B — Zone Production")],
        ["Responsable machine",  machine.get("responsable", "Sophie M.")],
        ["Statut actuel",        machine.get("statut", "Alerte critique")],
        ["RUL estimé",           f"{ctx.get('rul', 0)} heures"],
        ["Température capteur",  f"{ctx.get('temp', 0):.1f} °C  (seuil : {machine.get('seuil_temp', 110)} °C)"],
        ["Vibration capteur",    f"{ctx.get('vib', 0):.2f} mm/s  (seuil : {machine.get('seuil_vib', 4.5)} mm/s)"],
        ["Pression capteur",     f"{ctx.get('pres', 0):.1f} bar"],
        ["Dernière inspection",  machine.get("derniere_inspection", "—")],
        ["Prochaine maintenance",machine.get("prochaine_maintenance", "—")],
        ["Technicien assigné",   ctx.get("technicien", "Lionel")],
        ["Date d'intervention",  ctx.get("date_intervention", ctx["datetime_generation"][:10])],
        ["Type d'intervention",  ctx.get("type_anomalie", "Maintenance prescriptive — Dégradation progressive")],
    ]
    col_w = [(W - 4*cm) * r for r in [0.38, 0.62]]
    t = Table(
        [[Paragraph(str(r[0]), styles["cell_bold"] if i == 0 else styles["cell"]),
          Paragraph(str(r[1]), styles["cell_white"] if i == 0 else styles["cell"])]
         for i, r in enumerate(rows)],
        colWidths=col_w
    )
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), BLEU_MOYEN),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [white, GRIS_TRES_CLAIR]),
        ("GRID",      (0,0), (-1,-1), 0.3, HexColor("#d1d5db")),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("RIGHTPADDING",  (0,0), (-1,-1), 8),
    ]))
    story.append(t)
    story.append(_sp(10))


# ── SECTION 2 : MATRICE DES RISQUES ──────────────────────────────────────────
def _section_risques(story, styles, ctx):
    story.append(_section_header("ANALYSE ET MATRICE DES RISQUES", styles, 2))
    story.append(_sp(4))
    story.append(Paragraph(
        "Évaluation des risques identifiés selon ISO 45001:2018 §6.1.2 — "
        "Probabilité (P) × Gravité (G) = Score de criticité.",
        styles["body"]
    ))
    story.append(_sp(6))

    temp  = ctx.get("temp", 90);  seuil_t = float(ctx.get("machine", {}).get("seuil_temp", 110) or 110)
    vib   = ctx.get("vib",  3);   seuil_v = float(ctx.get("machine", {}).get("seuil_vib",  4.5) or 4.5)
    pres  = ctx.get("pres", 5);   seuil_p = 7.0
    rul   = ctx.get("rul",  48)

    risques = [
        {
            "danger": "Risque thermique — Surchauffe stator",
            "cause":  "Température capteur anormale",
            "prob": _prob_grav(temp, seuil_t)[0],
            "grav": _prob_grav(temp, seuil_t)[1],
            "mesures": "Gants isolants HT (EN 407) · Attendre refroidissement < 45°C avant ouverture",
            "norme": "NF EN 407 · ISO 13732",
        },
        {
            "danger": "Risque mécanique — Défaut palier / vibrations",
            "cause":  "Vibration hors seuil",
            "prob": _prob_grav(vib, seuil_v)[0],
            "grav": _prob_grav(vib, seuil_v)[1],
            "mesures": "Protection oculaire renforcée (EN 166) · Casque anti-bruit · Vérifier ancrage",
            "norme": "ISO 10816 · EN 166 · EN 352",
        },
        {
            "danger": "Risque hydraulique — Surpression circuit",
            "cause":  "Pression résiduelle au-delà du seuil nominal",
            "prob": _prob_grav(pres, seuil_p)[0],
            "grav": _prob_grav(pres, seuil_p)[1],
            "mesures": "Écran facial + combinaison anti-projections · Purger avant déconnexion",
            "norme": "EN 388 · EN ISO 11612",
        },
        {
            "danger": "Risque électrique — Court-circuit résiduel",
            "cause":  "Intervention sans consignation LOTO",
            "prob": 2 if rul < 24 else 1,
            "grav": 5,
            "mesures": "LOTO obligatoire — sectionneur cadenassé cellule BT · Habilitation BR exigée",
            "norme": "NF C18-510 · IEC 60900",
        },
        {
            "danger": "Risque ergonomique — Manutention / posture",
            "cause":  "Accès difficile à la pompe P-17",
            "prob": 2,
            "grav": 2,
            "mesures": "Équipement de levage · Analyse posturale · Pause toutes 45 min",
            "norme": "ISO 11228 · EN 1005",
        },
    ]

    # En-tête tableau
    headers = [
        Paragraph("<b>Danger identifié</b>",       styles["cell_white"]),
        Paragraph("<b>Cause</b>",                   styles["cell_white"]),
        Paragraph("<b>P</b>",                       styles["cell_white"]),
        Paragraph("<b>G</b>",                       styles["cell_white"]),
        Paragraph("<b>Score</b>",                   styles["cell_white"]),
        Paragraph("<b>Criticité</b>",               styles["cell_white"]),
        Paragraph("<b>Mesures de prévention</b>",   styles["cell_white"]),
        Paragraph("<b>Norme</b>",                   styles["cell_white"]),
    ]

    rows = [headers]
    style_cmds = [
        ("BACKGROUND", (0,0), (-1,0), BLEU_MOYEN),
        ("GRID",      (0,0), (-1,-1), 0.3, HexColor("#d1d5db")),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 5),
        ("RIGHTPADDING",  (0,0), (-1,-1), 5),
        ("VALIGN",    (0,0), (-1,-1), "TOP"),
    ]

    for i, r in enumerate(risques):
        score  = r["prob"] * r["grav"]
        level  = _risk_level(r["prob"], r["grav"])
        fg, bg = _risk_color(level)
        row_i  = i + 1
        rows.append([
            Paragraph(r["danger"],   styles["cell_bold"]),
            Paragraph(r["cause"],    styles["cell"]),
            Paragraph(str(r["prob"]), styles["cell"]),
            Paragraph(str(r["grav"]), styles["cell"]),
            Paragraph(f"<b>{score}</b>", styles["cell_bold"]),
            Paragraph(f"<b>{level}</b>", styles["cell_bold"]),
            Paragraph(r["mesures"],  styles["cell"]),
            Paragraph(r["norme"],    styles["cell"]),
        ])
        style_cmds += [
            ("BACKGROUND", (5, row_i), (5, row_i), bg),
            ("TEXTCOLOR",  (5, row_i), (5, row_i), fg),
            ("ROWBACKGROUNDS", (0, row_i), (4, row_i), [white if i%2==0 else GRIS_TRES_CLAIR]),
            ("ROWBACKGROUNDS", (6, row_i), (-1, row_i), [white if i%2==0 else GRIS_TRES_CLAIR]),
        ]

    col_w = [w * (W - 4*cm) for w in [0.20, 0.14, 0.04, 0.04, 0.05, 0.08, 0.28, 0.17]]
    t = Table(rows, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle(style_cmds))
    story.append(t)

    # Légende
    story.append(_sp(6))
    legende = [
        [Paragraph("P = Probabilité (1=Rare → 5=Quasi-certain)  |  G = Gravité (1=Négligeable → 5=Catastrophique)  |  "
                   "Score = P×G  |  FAIBLE ≤ 2  |  MOYEN 3–5  |  ÉLEVÉ 6–11  |  CRITIQUE ≥ 12",
                   styles["small"])]
    ]
    lt = Table(legende, colWidths=[W - 4*cm])
    lt.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), BLEU_CLAIR),
        ("LEFTPADDING",  (0,0), (-1,-1), 8), ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING",   (0,0), (-1,-1), 5), ("BOTTOMPADDING",(0,0), (-1,-1), 5),
    ]))
    story.append(lt)
    story.append(_sp(10))


# ── SECTION 3 : EPI ──────────────────────────────────────────────────────────
def _section_epi(story, styles, ctx):
    story.append(_section_header("DOTATION EPI OBLIGATOIRE", styles, 3))
    story.append(_sp(4))
    story.append(Paragraph(
        "Équipements de Protection Individuelle requis conformément aux risques identifiés (§4.2). "
        "La remise doit être tracée avant départ sur site.",
        styles["body"]
    ))
    story.append(_sp(6))

    epis = [
        ["Gants isolants Haute Température",   "EN 407 Classe 4",     "Risque thermique",    "✓ En stock"],
        ["Protection oculaire renforcée",       "EN 166 Grade 1",      "Risque mécanique",    "✓ En stock"],
        ["Casque anti-bruit",                   "EN 352-1",            "Vibrations acoustiques","✓ En stock"],
        ["Écran facial anti-projections",       "EN 166 / EN 168",     "Risque hydraulique",  "✓ En stock"],
        ["Combinaison anti-projections",        "EN ISO 11612",        "Risque hydraulique",  "✓ En stock"],
        ["Chaussures de sécurité S3",           "EN ISO 20345",        "Tous risques",        "✓ En stock"],
        ["Harnais antichute (si en hauteur)",   "EN 361",              "Risque chute",        "⚠ Vérifier"],
        ["Gants anti-coupure",                  "EN 388 Niveau 4",     "Risque mécanique",    "✓ En stock"],
    ]
    headers = [
        Paragraph("<b>EPI</b>",             styles["cell_white"]),
        Paragraph("<b>Norme / Classe</b>",  styles["cell_white"]),
        Paragraph("<b>Risque couvert</b>",  styles["cell_white"]),
        Paragraph("<b>Disponibilité</b>",   styles["cell_white"]),
        Paragraph("<b>Remis le</b>",        styles["cell_white"]),
        Paragraph("<b>Signature tech.</b>", styles["cell_white"]),
    ]
    rows = [headers]
    for epi in epis:
        dispo = epi[3]
        rows.append([
            Paragraph(epi[0], styles["cell_bold"]),
            Paragraph(epi[1], styles["cell"]),
            Paragraph(epi[2], styles["cell"]),
            Paragraph(dispo,  styles["cell_bold"] if "✓" in dispo else styles["cell"]),
            Paragraph("__/__/____", styles["cell"]),
            Paragraph("_____________", styles["cell"]),
        ])

    col_w = [w * (W - 4*cm) for w in [0.26, 0.16, 0.20, 0.12, 0.13, 0.13]]
    t = Table(rows, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), BLEU_MOYEN),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [white, GRIS_TRES_CLAIR]),
        ("GRID",      (0,0), (-1,-1), 0.3, HexColor("#d1d5db")),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 5),
        ("RIGHTPADDING",  (0,0), (-1,-1), 5),
        ("VALIGN",    (0,0), (-1,-1), "TOP"),
    ]))
    story.append(t)
    story.append(_sp(10))


# ── SECTION 4 : PROCÉDURE LOTO ────────────────────────────────────────────────
def _section_loto(story, styles, ctx):
    story.append(_section_header("PROCÉDURE LOTO — CONSIGNATION / DÉCONSIGNATION", styles, 4))
    story.append(_sp(4))
    story.append(Paragraph(
        "Conformément à NF C18-510 et ISO 50001 — Procédure de Condamnation et Cadenassage "
        "obligatoire avant toute intervention sur la Pompe P-17.",
        styles["body"]
    ))
    story.append(_sp(6))

    etapes = [
        ("1", "CONSIGNATION", "Identifier l'équipement à consigner — Pompe P-17, Unité B",
         "Technicien",    ""),
        ("2", "CONSIGNATION", "Informer le responsable de production de l'arrêt imminent",
         "Technicien",    ""),
        ("3", "CONSIGNATION", "Arrêter la pompe via le tableau de commande local",
         "Technicien",    ""),
        ("4", "CONSIGNATION", "Ouvrir le sectionneur d'alimentation en cellule BT",
         "Technicien",    ""),
        ("5", "CONSIGNATION", "Apposer le cadenas personnel (référence : LOTO-P17-{tech})",
         "Technicien",    ""),
        ("6", "CONSIGNATION", "Condamner la vanne d'aspiration et de refoulement",
         "Technicien",    ""),
        ("7", "CONSIGNATION", "Purger la pression résiduelle du circuit hydraulique",
         "Technicien",    ""),
        ("8", "CONSIGNATION", "Vérifier l'absence de tension (VAT) avec testeur homologué",
         "Technicien",    ""),
        ("9", "CONSIGNATION", "Apposer la pancarte de consignation sur le sectionneur",
         "Technicien",    ""),
        ("10", "CONSIGNATION","Valider la consignation — Signature et horodatage",
         "Technicien + Superviseur", ""),
        ("—", "—",            "INTERVENTION EN COURS", "", ""),
        ("11", "DÉCONSIGNATION","Vérifier que l'équipement est prêt à être remis en service",
         "Technicien",    ""),
        ("12", "DÉCONSIGNATION","Retirer les outils et pièces de l'enceinte de travail",
         "Technicien",    ""),
        ("13", "DÉCONSIGNATION","Enlever le cadenas personnel et la pancarte",
         "Technicien",    ""),
        ("14", "DÉCONSIGNATION","Remettre le sectionneur en position fermée",
         "Technicien",    ""),
        ("15", "DÉCONSIGNATION","Informer le responsable production de la remise en service",
         "Technicien",    ""),
        ("16", "DÉCONSIGNATION","Démarrer la pompe et vérifier le fonctionnement normal",
         "Technicien + Superviseur", ""),
    ]

    headers = [
        Paragraph("<b>Étape</b>",       styles["cell_white"]),
        Paragraph("<b>Phase</b>",       styles["cell_white"]),
        Paragraph("<b>Action</b>",      styles["cell_white"]),
        Paragraph("<b>Responsable</b>", styles["cell_white"]),
        Paragraph("<b>Horodatage</b>",  styles["cell_white"]),
        Paragraph("<b>Visa</b>",        styles["cell_white"]),
    ]
    rows = [headers]
    for e in etapes:
        if e[0] == "—":
            rows.append([
                Paragraph("", styles["cell"]),
                Paragraph("", styles["cell"]),
                Paragraph(f"<b>{e[2]}</b>", styles["cell_bold"]),
                Paragraph("", styles["cell"]),
                Paragraph("", styles["cell"]),
                Paragraph("", styles["cell"]),
            ])
        else:
            phase_col = BLEU_CLAIR if "CONSI" in e[1] else AMBRE_CLAIR
            rows.append([
                Paragraph(e[0], styles["cell_bold"]),
                Paragraph(e[1], styles["cell"]),
                Paragraph(e[2].format(tech=ctx.get("technicien","Lionel")), styles["cell"]),
                Paragraph(e[3], styles["cell"]),
                Paragraph("__:__", styles["cell"]),
                Paragraph("___", styles["cell"]),
            ])

    col_w = [w * (W - 4*cm) for w in [0.05, 0.14, 0.40, 0.17, 0.12, 0.12]]
    t = Table(rows, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), BLEU_MOYEN),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [white, GRIS_TRES_CLAIR]),
        ("BACKGROUND",    (0,11), (-1,11), AMBRE_CLAIR),
        ("GRID",      (0,0), (-1,-1), 0.3, HexColor("#d1d5db")),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (-1,-1), 5),
        ("RIGHTPADDING",  (0,0), (-1,-1), 5),
        ("VALIGN",    (0,0), (-1,-1), "TOP"),
    ]))
    story.append(t)
    story.append(_sp(10))


# ── SECTION 5 : HABILITATIONS ────────────────────────────────────────────────
def _section_habilitations(story, styles, ctx):
    story.append(_section_header("HABILITATIONS ET QUALIFICATIONS TECHNICIEN", styles, 5))
    story.append(_sp(6))

    techniciens = ctx.get("equipe", [])
    if not techniciens:
        techniciens = [{
            "nom": "DUPONT", "prenom": "Lionel",
            "role": "Technicien de maintenance",
            "specialite": "Mécanique / Hydraulique",
            "habilitations": "M-H, BR, Hydraulique, Habilitation pomperie",
            "certifications": "CACES R484, Travail en hauteur, SST",
            "disponibilite": "Disponible",
            "charge_horaire": 35, "heures_restantes": 18,
            "zone": "Unité B",
        }]

    headers = [
        Paragraph("<b>Technicien</b>",       styles["cell_white"]),
        Paragraph("<b>Rôle</b>",             styles["cell_white"]),
        Paragraph("<b>Spécialité</b>",       styles["cell_white"]),
        Paragraph("<b>Habilitations</b>",    styles["cell_white"]),
        Paragraph("<b>Certifications</b>",   styles["cell_white"]),
        Paragraph("<b>Disponibilité</b>",    styles["cell_white"]),
        Paragraph("<b>Zone</b>",             styles["cell_white"]),
        Paragraph("<b>Statut</b>",           styles["cell_white"]),
    ]
    rows = [headers]
    for t_data in techniciens:
        dispo = t_data.get("disponibilite", "—")
        rows.append([
            Paragraph(f"<b>{t_data.get('nom','—')} {t_data.get('prenom','')}</b>", styles["cell_bold"]),
            Paragraph(t_data.get("role", "—"), styles["cell"]),
            Paragraph(t_data.get("specialite", "—"), styles["cell"]),
            Paragraph(t_data.get("habilitations", "—"), styles["cell"]),
            Paragraph(t_data.get("certifications", "—"), styles["cell"]),
            Paragraph(dispo, styles["cell"]),
            Paragraph(t_data.get("zone", "—"), styles["cell"]),
            Paragraph("✓ CONFORME" if dispo == "Disponible" else "⚠ À VÉRIFIER", styles["cell_bold"]),
        ])

    col_w = [w * (W - 4*cm) for w in [0.15, 0.14, 0.13, 0.16, 0.16, 0.10, 0.08, 0.08]]
    t = Table(rows, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), BLEU_MOYEN),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [white, GRIS_TRES_CLAIR]),
        ("GRID",      (0,0), (-1,-1), 0.3, HexColor("#d1d5db")),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 5),
        ("RIGHTPADDING",  (0,0), (-1,-1), 5),
        ("VALIGN",    (0,0), (-1,-1), "TOP"),
    ]))
    story.append(t)
    story.append(_sp(10))


# ── SECTION 6 : TRAÇABILITÉ PIÈCES ───────────────────────────────────────────
def _section_pieces(story, styles, ctx):
    story.append(_section_header("TRAÇABILITÉ DES PIÈCES DÉTACHÉES", styles, 6))
    story.append(_sp(4))
    story.append(Paragraph(
        "Conformément à ISO 45001:2018 §8.1.3 — Traçabilité des équipements et fournitures "
        "utilisés lors de l'intervention. Chaque pièce doit être référencée et son fournisseur validé.",
        styles["body"]
    ))
    story.append(_sp(6))

    pieces = ctx.get("pieces", [])
    if not pieces:
        pieces = [
            {"designation": "Roulement SKF 6210-2RS", "reference": "SKF-6210-2RS",
             "categorie": "Roulement", "fournisseur": "SKF France",
             "stock_actuel": 2, "statut_stock": "Stock critique", "emplacement": "B3-E12"},
            {"designation": "Joint d'étanchéité Burgmann MG1",
             "reference": "BM-MG1-40MM", "categorie": "Joint",
             "fournisseur": "Burgmann Industries", "stock_actuel": 3,
             "statut_stock": "En stock", "emplacement": "B2-A04"},
            {"designation": "Filtre hydraulique Parker F3", "reference": "PF3-200L",
             "categorie": "Filtration", "fournisseur": "Parker Hannifin",
             "stock_actuel": 0, "statut_stock": "Rupture", "emplacement": "—"},
        ]

    headers = [
        Paragraph("<b>Désignation</b>",      styles["cell_white"]),
        Paragraph("<b>Référence</b>",         styles["cell_white"]),
        Paragraph("<b>Catégorie</b>",         styles["cell_white"]),
        Paragraph("<b>Fournisseur</b>",       styles["cell_white"]),
        Paragraph("<b>Stock dispo</b>",       styles["cell_white"]),
        Paragraph("<b>Emplacement</b>",       styles["cell_white"]),
        Paragraph("<b>Statut</b>",            styles["cell_white"]),
        Paragraph("<b>N° lot utilisé</b>",    styles["cell_white"]),
    ]
    rows = [headers]
    for p in pieces:
        statut = p.get("statut_stock", "—")
        if "Rupture" in statut:
            st_col, st_bg = ROUGE, ROUGE_CLAIR
        elif "critique" in statut.lower() or "Alerte" in statut:
            st_col, st_bg = ORANGE, ORANGE_CLAIR
        else:
            st_col, st_bg = VERT, VERT_CLAIR
        rows.append([
            Paragraph(p.get("designation", "—"),  styles["cell_bold"]),
            Paragraph(p.get("reference", "—"),    styles["cell"]),
            Paragraph(p.get("categorie", "—"),    styles["cell"]),
            Paragraph(p.get("fournisseur", "—"),  styles["cell"]),
            Paragraph(str(p.get("stock_actuel", 0)), styles["cell"]),
            Paragraph(p.get("emplacement", "—"),  styles["cell"]),
            Paragraph(statut, styles["cell"]),
            Paragraph("______________", styles["cell"]),
        ])

    col_w = [w * (W - 4*cm) for w in [0.22, 0.14, 0.10, 0.16, 0.08, 0.10, 0.11, 0.09]]
    t = Table(rows, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), BLEU_MOYEN),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [white, GRIS_TRES_CLAIR]),
        ("GRID",      (0,0), (-1,-1), 0.3, HexColor("#d1d5db")),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 5),
        ("RIGHTPADDING",  (0,0), (-1,-1), 5),
        ("VALIGN",    (0,0), (-1,-1), "TOP"),
    ]))
    story.append(t)
    story.append(_sp(10))


# ── SECTION 7 : DOCS HSE CONSULTÉS ───────────────────────────────────────────
def _section_docs_hse(story, styles, ctx):
    story.append(_section_header("DOCUMENTS HSE CONSULTÉS", styles, 7))
    story.append(_sp(6))

    docs = ctx.get("docs_hse", [])
    if not docs:
        docs = [
            {"titre": "Procédure LOTO Pompe P-17", "type": "Procédure",
             "niveau_risque": "Élevé", "statut": "Validé", "version": "v3",
             "auteur": "Leila HSE", "date_validation": "2025-01-15"},
            {"titre": "Fiche EPI Intervention Pompe", "type": "Fiche sécurité",
             "niveau_risque": "Élevé", "statut": "Validé", "version": "v2",
             "auteur": "Leila HSE", "date_validation": "2025-02-01"},
            {"titre": "Audit ISO 45001 — Score 87/100", "type": "Rapport audit",
             "niveau_risque": "Moyen", "statut": "Validé", "version": "v1",
             "auteur": "Cabinet externe", "date_validation": "2025-03-10"},
        ]

    headers = [
        Paragraph("<b>Titre document</b>", styles["cell_white"]),
        Paragraph("<b>Type</b>",           styles["cell_white"]),
        Paragraph("<b>Risque</b>",         styles["cell_white"]),
        Paragraph("<b>Version</b>",        styles["cell_white"]),
        Paragraph("<b>Auteur</b>",         styles["cell_white"]),
        Paragraph("<b>Validé le</b>",      styles["cell_white"]),
        Paragraph("<b>Statut</b>",         styles["cell_white"]),
    ]
    rows = [headers]
    for d in docs:
        rows.append([
            Paragraph(d.get("titre", "—"),           styles["cell_bold"]),
            Paragraph(d.get("type", "—"),            styles["cell"]),
            Paragraph(d.get("niveau_risque", "—"),   styles["cell"]),
            Paragraph(d.get("version", "—"),         styles["cell"]),
            Paragraph(d.get("auteur", "—"),          styles["cell"]),
            Paragraph(d.get("date_validation", "—"), styles["cell"]),
            Paragraph("✓ " + d.get("statut", "—"),  styles["cell_bold"]),
        ])

    col_w = [w * (W - 4*cm) for w in [0.28, 0.14, 0.09, 0.07, 0.14, 0.12, 0.16]]
    t = Table(rows, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), BLEU_MOYEN),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [white, GRIS_TRES_CLAIR]),
        ("GRID",      (0,0), (-1,-1), 0.3, HexColor("#d1d5db")),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 5),
        ("RIGHTPADDING",  (0,0), (-1,-1), 5),
        ("VALIGN",    (0,0), (-1,-1), "TOP"),
    ]))
    story.append(t)
    story.append(_sp(10))


# ── SECTION 8 : DÉCLARATION DE CONFORMITÉ ────────────────────────────────────
def _section_declaration(story, styles, ctx):
    story.append(PageBreak())
    story.append(_section_header("DÉCLARATION DE CONFORMITÉ", styles, 8))
    story.append(_sp(8))

    texte = (
        f"La présente déclaration atteste que l'intervention de maintenance réalisée sur <b>{ctx['equipement']}</b> "
        f"par le technicien <b>{ctx.get('technicien','Lionel')}</b> le <b>{ctx.get('date_intervention', ctx['datetime_generation'][:10])}</b> "
        f"a été préparée, exécutée et documentée conformément aux exigences de la norme "
        f"<b>ISO 45001:2018 — Systèmes de management de la santé et de la sécurité au travail</b>.<br/><br/>"
        f"Les éléments suivants ont été vérifiés et sont conformes :<br/>"
        f"✓ Analyse des risques réalisée et mesures de prévention définies<br/>"
        f"✓ Équipements de Protection Individuelle (EPI) remis et vérifiés<br/>"
        f"✓ Procédure LOTO appliquée et tracée avec horodatage<br/>"
        f"✓ Habilitations technicien vérifiées et à jour<br/>"
        f"✓ Traçabilité des pièces détachées assurée (références fournisseurs)<br/>"
        f"✓ Documents HSE consultés et à jour<br/><br/>"
        f"Ce dossier constitue la preuve documentaire requise pour un audit de certification ISO 45001:2018. "
        f"Il est conservé pendant <b>5 ans</b> conformément aux obligations légales (Code du travail, Art. R4121-1)."
    )
    data = [[Paragraph(texte, styles["body"])]]
    t = Table(data, colWidths=[W - 4*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), BLEU_CLAIR),
        ("LEFTPADDING",  (0,0), (-1,-1), 16),
        ("RIGHTPADDING", (0,0), (-1,-1), 16),
        ("TOPPADDING",   (0,0), (-1,-1), 14),
        ("BOTTOMPADDING",(0,0), (-1,-1), 14),
        ("BOX", (0,0), (-1,-1), 1.5, BLEU_MOYEN),
    ]))
    story.append(t)
    story.append(_sp(16))


# ── SECTION 9 : VALIDATION ────────────────────────────────────────────────────
def _section_validation(story, styles, ctx):
    story.append(_section_header("VALIDATION ET SIGNATURES", styles, 9))
    story.append(_sp(8))

    sig_data = [
        [Paragraph("<b>Technicien intervenant</b>", styles["cell_white"]),
         Paragraph("<b>Responsable Maintenance (Sophie)</b>", styles["cell_white"]),
         Paragraph("<b>Responsable HSE (Leila)</b>", styles["cell_white"])],
        [
            Paragraph(f"Nom : {ctx.get('technicien','Lionel')}<br/><br/>"
                      "Signature :<br/><br/><br/>___________________<br/><br/>"
                      f"Date : ___/___/______", styles["cell"]),
            Paragraph("Nom : Sophie M.<br/><br/>"
                      "Signature :<br/><br/><br/>___________________<br/><br/>"
                      "Date : ___/___/______", styles["cell"]),
            Paragraph("Nom : Leila D.<br/><br/>"
                      "Signature :<br/><br/><br/>___________________<br/><br/>"
                      "Date : ___/___/______", styles["cell"]),
        ]
    ]
    col_w = [(W - 4*cm) / 3] * 3
    t = Table(sig_data, colWidths=col_w)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), BLEU_MOYEN),
        ("GRID",      (0,0), (-1,-1), 0.5, HexColor("#d1d5db")),
        ("TOPPADDING",    (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 10),
        ("LEFTPADDING",   (0,0), (-1,-1), 14),
        ("RIGHTPADDING",  (0,0), (-1,-1), 14),
        ("VALIGN",    (0,0), (-1,-1), "TOP"),
        ("ROWHEIGHT", (0,1), (-1,1), 3*cm),
    ]))
    story.append(t)
    story.append(_sp(14))

    # Tampon de validation ResilientFlow AI
    ref      = ctx["reference"]
    now      = ctx["datetime_generation"]
    sig_hash = hashlib.sha256(f"{ref}{now}".encode()).hexdigest()[:32].upper()

    stamp_data = [[
        Paragraph(
            f"<b>⚡ VALIDÉ PAR RESILIENTFLOW AI</b><br/>"
            f"Référence : {ref}<br/>"
            f"Généré le : {now}<br/>"
            f"Hash de validation : {sig_hash}<br/>"
            f"<font color='#6b7280' size='7'>Document fictif — Use case pédagogique ESCP Extension 2025 — "
            f"Non opposable légalement</font>",
            styles["small"]
        )
    ]]
    stamp_t = Table(stamp_data, colWidths=[W - 4*cm])
    stamp_t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), AMBRE_CLAIR),
        ("BOX",    (0,0), (-1,-1), 1.5, AMBRE),
        ("LEFTPADDING",  (0,0), (-1,-1), 14),
        ("RIGHTPADDING", (0,0), (-1,-1), 14),
        ("TOPPADDING",   (0,0), (-1,-1), 10),
        ("BOTTOMPADDING",(0,0), (-1,-1), 10),
    ]))
    story.append(stamp_t)


# ── FONCTION PRINCIPALE ───────────────────────────────────────────────────────
def generate_audit_pdf(context: dict) -> bytes:
    """
    Génère le dossier de preuve ISO 45001 en PDF.

    Args:
        context (dict) : {
            "equipement"        : "Pompe P-17",
            "technicien"        : "Lionel",
            "temp"              : 117.0,   # °C
            "vib"               : 5.8,     # mm/s
            "pres"              : 4.6,     # bar
            "rul"               : 12,      # heures
            "machine"           : dict,    # from notion_client.get_machine()
            "equipe"            : list,    # from notion_client.get_equipe()
            "pieces"            : list,    # from notion_client.get_pieces()
            "docs_hse"          : list,    # from notion_client.get_docs_hse()
            "type_anomalie"     : str,
        }

    Returns:
        bytes : contenu PDF prêt pour st.download_button()
    """
    # Enrichir le contexte
    now = datetime.now()
    today = date.today()
    ctx = {**context}
    ctx["datetime_generation"] = now.strftime("%d/%m/%Y à %H:%M:%S")
    ctx["date_intervention"]   = today.isoformat()
    ctx["organisation"]        = "Unité Industrielle B — Use case fictif ResilientFlow AI"
    ctx["site"]                = "Unité B — Zone Production"
    equi_slug = ctx.get("equipement", "P17").replace(" ", "_").replace("-", "")
    ctx["reference"] = f"RF_AUDIT_ISO45001_{equi_slug}_{today.strftime('%Y%m%d')}_{now.strftime('%H%M')}"
    from datetime import timedelta
    ctx["validite_fin"] = (today + timedelta(days=90)).strftime("%d/%m/%Y")
    ctx["statut"] = "Généré automatiquement — En attente de signature manuscrite"

    styles = _styles()
    buf    = io.BytesIO()
    doc    = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm,  bottomMargin=1.6*cm,
        title=f"Dossier de Preuve ISO 45001 — {ctx['equipement']}",
        author="ResilientFlow AI",
        subject="Dossier de preuve de conformité maintenance",
    )

    pt = _PageTemplate(ctx["reference"], ctx["datetime_generation"], ctx["equipement"])
    story = []

    _cover(story, styles, ctx)
    _section_identification(story, styles, ctx)
    _section_risques(story, styles, ctx)
    _section_epi(story, styles, ctx)
    _section_loto(story, styles, ctx)
    _section_habilitations(story, styles, ctx)
    _section_pieces(story, styles, ctx)
    _section_docs_hse(story, styles, ctx)
    _section_declaration(story, styles, ctx)
    _section_validation(story, styles, ctx)

    doc.build(story, onFirstPage=pt, onLaterPages=pt)
    return buf.getvalue()
