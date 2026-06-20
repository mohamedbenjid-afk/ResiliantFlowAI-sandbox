"""
utils/pdf_codir.py
Générateur de Fiche CODIR — Décision d'investissement maintenance
Format : 2 pages A4, design exécutif, ReportLab Platypus

Usage:
    from utils.pdf_codir import generate_codir_pdf
    pdf_bytes = generate_codir_pdf(result)   # result = run_agent_antoine()
    st.download_button("Télécharger", pdf_bytes, file_name="CODIR_Antoine.pdf")
"""

import io, hashlib
from datetime import datetime, date
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle,
    Spacer, HRFlowable, KeepTogether, PageBreak
)

# ── PALETTE ───────────────────────────────────────────────────────────────────
BLEU        = HexColor("#1e3a5f")
BLEU_MED    = HexColor("#2563eb")
BLEU_CLAIR  = HexColor("#dbeafe")
AMBRE       = HexColor("#d97706")
AMBRE_CLAIR = HexColor("#fef3c7")
VERT        = HexColor("#16a34a")
VERT_CLAIR  = HexColor("#dcfce7")
ROUGE       = HexColor("#dc2626")
ROUGE_CLAIR = HexColor("#fee2e2")
ORANGE      = HexColor("#ea580c")
ORANGE_CLAIR= HexColor("#ffedd5")
GRIS_F      = HexColor("#374151")
GRIS_M      = HexColor("#6b7280")
GRIS_C      = HexColor("#f3f4f6")
GRIS_TC     = HexColor("#f9fafb")

W, H = A4


# ── TEMPLATE DE PAGE ──────────────────────────────────────────────────────────
class _PT:
    def __init__(self, ref, generated_at):
        self.ref          = ref
        self.generated_at = generated_at

    def __call__(self, canvas, doc):
        canvas.saveState()
        # Header band
        canvas.setFillColor(BLEU)
        canvas.rect(0, H - 1.4*cm, W, 1.4*cm, fill=1, stroke=0)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.setFillColor(white)
        canvas.drawString(1.8*cm, H - 0.95*cm, "CONFIDENTIEL — FICHE CODIR")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(AMBRE)
        canvas.drawRightString(W - 1.8*cm, H - 0.95*cm, self.ref)
        # Footer band
        canvas.setFillColor(GRIS_C)
        canvas.rect(0, 0, W, 1.0*cm, fill=1, stroke=0)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(GRIS_M)
        canvas.drawCentredString(W/2, 0.35*cm,
            f"ResilientFlow AI — Généré le {self.generated_at} — Page {doc.page}")
        canvas.restoreState()


# ── STYLES ────────────────────────────────────────────────────────────────────
def _S():
    s = {}
    def ps(name, **kw):
        s[name] = ParagraphStyle(name, **kw)
    ps("h1",       fontName="Helvetica-Bold", fontSize=18, textColor=white,    alignment=TA_CENTER, spaceAfter=2)
    ps("h1sub",    fontName="Helvetica",      fontSize=10, textColor=HexColor("#93c5fd"), alignment=TA_CENTER)
    ps("ref",      fontName="Helvetica-Bold", fontSize=9,  textColor=AMBRE,    alignment=TA_CENTER)
    ps("sec",      fontName="Helvetica-Bold", fontSize=10, textColor=white,    spaceBefore=3, spaceAfter=2)
    ps("body",     fontName="Helvetica",      fontSize=9,  textColor=GRIS_F,   leading=13, spaceAfter=2)
    ps("body_b",   fontName="Helvetica-Bold", fontSize=9,  textColor=GRIS_F,   leading=13)
    ps("small",    fontName="Helvetica",      fontSize=8,  textColor=GRIS_M,   leading=11)
    ps("kpi_val",  fontName="Helvetica-Bold", fontSize=22, textColor=BLEU_MED, alignment=TA_CENTER)
    ps("kpi_lbl",  fontName="Helvetica",      fontSize=8,  textColor=GRIS_M,   alignment=TA_CENTER)
    ps("reco",     fontName="Helvetica-Bold", fontSize=11, textColor=BLEU,     leading=16, spaceAfter=4)
    ps("footer_c", fontName="Helvetica",      fontSize=8,  textColor=GRIS_M,   alignment=TA_CENTER)
    ps("sig_lbl",  fontName="Helvetica-Bold", fontSize=9,  textColor=BLEU,     alignment=TA_CENTER)
    ps("sig_sub",  fontName="Helvetica",      fontSize=8,  textColor=GRIS_M,   alignment=TA_CENTER)
    return s


def _sec_header(text, s):
    tbl = Table([[Paragraph(text, s["sec"])]], colWidths=[W - 4*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), BLEU),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
    ]))
    return tbl


# ── PAGE DE GARDE ─────────────────────────────────────────────────────────────
def _cover(story, s, ctx):
    # Bloc header bleu
    tbl = Table([[
        Paragraph("FICHE DÉCISIONNELLE CODIR", s["h1"]),
        Paragraph("Maintenance Industrielle & Investissement", s["h1sub"]),
        Paragraph(f"Réf. {ctx['reference']}", s["ref"]),
    ]], colWidths=[W - 4*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), BLEU),
        ("TOPPADDING",    (0,0), (-1,-1), 18),
        ("BOTTOMPADDING", (0,0), (-1,-1), 18),
        ("LEFTPADDING",   (0,0), (-1,-1), 20),
        ("ROWBACKGROUNDS",(0,0), (-1,-1), [BLEU]),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.4*cm))

    # Tableau info
    eq    = ctx.get("equipement", "—")
    unite = ctx.get("unite", "—")
    rul   = ctx.get("rul_jours", "—")
    deg   = ctx.get("score_deg", "—")
    data  = [
        ["Équipement analysé", eq,          "Date CODIR",    ctx["date_codir"]],
        ["Unité / Zone",       unite,        "Directeur Tech.", "Antoine"],
        ["RUL estimé",         f"{rul} j",  "Dégradation",   f"{deg} %"],
        ["Statut machine",     ctx.get("statut", "—"), "Horizon analyse", f"{ctx.get('horizon', 3)} ans"],
    ]
    t = Table(data, colWidths=[4.2*cm, 5.8*cm, 4.2*cm, 5.8*cm])
    t.setStyle(TableStyle([
        ("FONTNAME",  (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME",  (2,0), (2,-1), "Helvetica-Bold"),
        ("FONTSIZE",  (0,0), (-1,-1), 9),
        ("TEXTCOLOR", (0,0), (0,-1), BLEU),
        ("TEXTCOLOR", (2,0), (2,-1), BLEU),
        ("BACKGROUND",(0,0), (-1,-1), GRIS_TC),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [white, GRIS_TC]),
        ("GRID",      (0,0), (-1,-1), 0.5, HexColor("#e5e7eb")),
        ("TOPPADDING",(0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
        ("LEFTPADDING", (0,0),(-1,-1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3*cm))

    # Signature SHA-256
    h = hashlib.sha256(f"{ctx['reference']}{ctx['date_codir']}{eq}".encode()).hexdigest()[:32]
    sig_tbl = Table([[Paragraph(f"Empreinte numérique : {h.upper()}", s["small"])]],
                    colWidths=[W - 4*cm])
    sig_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), AMBRE_CLAIR),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ("BOX",           (0,0), (-1,-1), 1, AMBRE),
    ]))
    story.append(sig_tbl)
    story.append(Spacer(1, 0.4*cm))


# ── KPIs CLÉS ─────────────────────────────────────────────────────────────────
def _kpis(story, s, ctx):
    story.append(_sec_header("1. INDICATEURS CLÉS", s))
    story.append(Spacer(1, 0.2*cm))

    hist = ctx.get("historique") or {}
    kpis = [
        (f"{hist.get('mtbf_jours', '—')} j",   "MTBF",           BLEU_CLAIR),
        (f"{hist.get('mttr_heures', '—')} h",   "MTTR",           GRIS_C),
        (f"× {hist.get('roi_maintenance', '—')}","ROI Prescriptif",VERT_CLAIR),
        (f"{hist.get('cout_total_maintenance_eur', 0):,.0f} €",
                                                 "OPEX Cumul",     GRIS_C),
        (f"{hist.get('couts_arrets_evites_eur', 0):,.0f} €",
                                                 "Arrêts évités",  VERT_CLAIR),
        (f"{hist.get('nb_pannes_correctives', 0)}","Pannes correctives", ROUGE_CLAIR),
    ]
    cells_val = [[Paragraph(v, s["kpi_val"]) for v, _, _ in kpis]]
    cells_lbl = [[Paragraph(l, s["kpi_lbl"]) for _, l, _ in kpis]]
    bg_colors = [c for _, _, c in kpis]

    col_w = (W - 4*cm) / 6
    tv = Table(cells_val, colWidths=[col_w]*6)
    tl = Table(cells_lbl, colWidths=[col_w]*6)
    for tbl in [tv, tl]:
        tbl.setStyle(TableStyle([
            ("ALIGN",         (0,0), (-1,-1), "CENTER"),
            ("TOPPADDING",    (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("ROWBACKGROUNDS",(0,0), (-1,-1), [bg_colors]),
        ]))
    story.append(tv)
    story.append(tl)
    story.append(Spacer(1, 0.3*cm))


# ── PORTFOLIO MACHINES ────────────────────────────────────────────────────────
def _portfolio(story, s, ctx):
    portfolio = ctx.get("portfolio")
    if not portfolio:
        return
    story.append(_sec_header("2. PORTFOLIO MACHINES — RANKING PAR RISQUE", s))
    story.append(Spacer(1, 0.2*cm))

    hdr = [["Machine", "Unité", "RUL (j)", "Dégradation", "Score risque", "Niveau"]]
    rows = []
    for m in portfolio.get("ranking", []):
        rows.append([
            m.get("machine", ""),
            m.get("unite", ""),
            str(m.get("rul_jours", 0)),
            f"{m.get('score_degradation_pct', 0)} %",
            f"{m.get('score_risque', 0)} / 100",
            m.get("niveau_risque", ""),
        ])

    data   = hdr + rows
    col_ws = [5.5*cm, 2.5*cm, 2*cm, 3*cm, 3*cm, 4*cm]
    t = Table(data, colWidths=col_ws)

    style = [
        ("BACKGROUND",    (0,0), (-1,0), BLEU_MED),
        ("TEXTCOLOR",     (0,0), (-1,0), white),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 8.5),
        ("GRID",          (0,0), (-1,-1), 0.4, HexColor("#e5e7eb")),
        ("ALIGN",         (2,0), (-1,-1), "CENTER"),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
    ]
    for i, row in enumerate(rows, 1):
        niveau = row[5]
        bg = (ROUGE_CLAIR  if "CRITIQUE" in niveau else
              ORANGE_CLAIR if "ÉLEVÉ"    in niveau else
              AMBRE_CLAIR  if "MODÉRÉ"   in niveau else VERT_CLAIR)
        style.append(("BACKGROUND", (0,i), (-1,i), bg))

    t.setStyle(TableStyle(style))
    story.append(t)
    story.append(Spacer(1, 0.3*cm))


# ── TABLEAU 3 SCÉNARIOS ───────────────────────────────────────────────────────
def _scenarios(story, s, ctx):
    sc = ctx.get("scenarios")
    if not sc:
        return
    story.append(_sec_header("3. SIMULATION FINANCIÈRE — 3 SCÉNARIOS", s))
    story.append(Spacer(1, 0.2*cm))

    sc_data = sc.get("scenarios", {})
    horizon = sc.get("horizon_ans", 3)
    hyp     = sc.get("hypotheses", {})

    # Hypothèses
    hyp_txt = (
        f"Hypothèses : coût panne moyen {hyp.get('cout_panne_moyen_eur', 0):,.0f} € · "
        f"{hyp.get('pannes_par_an_sans_prescriptif', 0)} pannes/an sans prescriptif · "
        f"{hyp.get('pannes_par_an_avec_prescriptif', 0)} pannes/an avec prescriptif · "
        f"taux actualisation 5%"
    )
    story.append(Paragraph(hyp_txt, s["small"]))
    story.append(Spacer(1, 0.15*cm))

    a = sc_data.get("A_correctif_pur", {})
    b = sc_data.get("B_maintien_prescriptif", {})
    c = sc_data.get("C_remplacement", {})

    hdr  = [["", "A — Correctif pur", "B — Prescriptif (actuel)", f"C — Remplacement"]]
    rows = [
        ["Description",    a.get("description","")[:35], b.get("description","")[:35], c.get("description","")[:35]],
        ["Coût total", f"{a.get('cout_total_eur',0):,.0f} €", f"{b.get('cout_total_eur',0):,.0f} €", f"{c.get('cout_total_eur',0):,.0f} €"],
        ["NPV",        f"{a.get('npv_eur',0):,.0f} €",       f"{b.get('npv_eur',0):,.0f} €",       f"{c.get('npv_eur',0):,.0f} €"],
        ["Point mort", "—", "—", f"{c.get('payback_vs_correctif_mois','—')} mois vs A"],
    ]
    data   = hdr + rows
    col_ws = [3.5*cm, 5.5*cm, 5.5*cm, 5.5*cm]
    t = Table(data, colWidths=col_ws)

    reco = sc.get("recommandation_financiere", "")
    best_col = (1 if "A" in reco else 2 if "B" in reco else 3)

    style = [
        ("BACKGROUND",    (0,0), (-1,0), BLEU_MED),
        ("TEXTCOLOR",     (0,0), (-1,0), white),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME",      (0,1), (0,-1), "Helvetica-Bold"),
        ("TEXTCOLOR",     (0,1), (0,-1), BLEU),
        ("FONTSIZE",      (0,0), (-1,-1), 8.5),
        ("GRID",          (0,0), (-1,-1), 0.4, HexColor("#e5e7eb")),
        ("ALIGN",         (1,0), (-1,-1), "CENTER"),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [white, GRIS_TC, white, GRIS_TC]),
        # Colonne meilleure en vert clair
        ("BACKGROUND", (best_col, 1), (best_col, -1), VERT_CLAIR),
    ]
    t.setStyle(TableStyle(style))
    story.append(t)

    eco = sc.get("economie_prescriptif_vs_correctif_eur", 0)
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph(
        f"✅ Économie prescriptif vs correctif sur {horizon} ans : <b>{eco:,.0f} €</b> — "
        f"Recommandation : <b>{reco}</b>",
        s["body"]
    ))
    story.append(Spacer(1, 0.3*cm))


# ── ANALYSE LLM (extrait) ─────────────────────────────────────────────────────
def _analyse(story, s, ctx):
    analyse = ctx.get("analyse", "")
    if not analyse:
        return
    story.append(_sec_header("4. ANALYSE AGENT AI — SYNTHÈSE", s))
    story.append(Spacer(1, 0.2*cm))

    # On prend les 800 premiers caractères de l'analyse (synthèse exécutive)
    lines = analyse.split("\n")
    for line in lines[:25]:
        line = line.strip()
        if not line:
            story.append(Spacer(1, 0.1*cm))
            continue
        if line.startswith("##"):
            story.append(Paragraph(line.replace("#","").strip(), s["body_b"]))
        elif line.startswith("**") and line.endswith("**"):
            story.append(Paragraph(line.replace("**",""), s["body_b"]))
        else:
            story.append(Paragraph(line.replace("**","<b>",1).replace("**","</b>",1), s["body"]))
    story.append(Spacer(1, 0.3*cm))


# ── RECOMMANDATION ENCADRÉE ───────────────────────────────────────────────────
def _recommandation(story, s, ctx):
    sc   = ctx.get("scenarios") or {}
    reco = sc.get("recommandation_financiere", "")
    eco  = sc.get("economie_prescriptif_vs_correctif_eur", 0)
    hist = ctx.get("historique") or {}
    roi  = hist.get("roi_maintenance", "—")
    mtbf = hist.get("mtbf_jours", "—")

    story.append(_sec_header("5. RECOMMANDATION CODIR", s))
    story.append(Spacer(1, 0.2*cm))

    reco_text = (
        f"Sur la base de l'analyse des données de fiabilité, de l'historique de maintenance "
        f"et de la simulation financière sur {sc.get('horizon_ans', 3)} ans, "
        f"l'agent ResilientFlow AI recommande : <b>{reco}</b>.<br/><br/>"
        f"Le maintien de la couche prescriptive génère une économie estimée de "
        f"<b>{eco:,.0f} €</b> vs une stratégie corrective pure, avec un ROI de "
        f"<b>×{roi}</b> et un MTBF de <b>{mtbf} jours</b>."
    )

    tbl = Table([[Paragraph(reco_text, s["reco"])]], colWidths=[W - 4*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), BLEU_CLAIR),
        ("TOPPADDING",    (0,0), (-1,-1), 12),
        ("BOTTOMPADDING", (0,0), (-1,-1), 12),
        ("LEFTPADDING",   (0,0), (-1,-1), 14),
        ("RIGHTPADDING",  (0,0), (-1,-1), 14),
        ("BOX",           (0,0), (-1,-1), 1.5, BLEU_MED),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.4*cm))


# ── SIGNATURES ────────────────────────────────────────────────────────────────
def _signatures(story, s, ctx):
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRIS_M))
    story.append(Spacer(1, 0.3*cm))

    signataires = [
        ("Antoine", "Directeur Technique",    "Décision CAPEX/OPEX"),
        ("Agent AI", "ResilientFlow AI",       "Analyse prescriptive"),
        ("PDG",      "Direction Générale",     "Validation budgétaire"),
    ]
    cells = [[
        [Paragraph(n, s["sig_lbl"]),
         Paragraph(r, s["sig_sub"]),
         Paragraph(f, s["sig_sub"]),
         Spacer(1, 0.6*cm),
         Paragraph("Signature : _______________", s["sig_sub"])]
        for n, r, f in signataires
    ]]
    col_w = (W - 4*cm) / 3
    t = Table(cells[0], colWidths=[col_w]*3)
    t.setStyle(TableStyle([
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("LINEAFTER",     (0,0), (1,-1),  0.5, GRIS_M),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(t)


# ── ENTRY POINT ───────────────────────────────────────────────────────────────
def generate_codir_pdf(result: dict) -> bytes:
    """
    Génère la fiche CODIR PDF depuis le résultat de run_agent_antoine().

    Args:
        result (dict) : {
            "analyse":    str  — texte Markdown LLM
            "scenarios":  dict — simuler_scenarios_investissement()
            "portfolio":  dict — get_top_equipements_a_risque()
            "bilan":      dict — get_bilan_equipement()
            "historique": dict — get_historique_couts_maintenance()
        }

    Returns:
        bytes : contenu PDF prêt pour st.download_button()
    """
    now   = datetime.now()
    today = date.today()

    bilan     = result.get("bilan")     or {}
    hist      = result.get("historique") or {}
    scenarios = result.get("scenarios")  or {}
    portfolio = result.get("portfolio")  or {}
    analyse   = result.get("analyse", "")

    eq     = bilan.get("machine")  or scenarios.get("equipement") or "Équipement"
    eq_slug= eq.replace(" ", "_").replace("-", "")
    ref    = f"CODIR_RF_{eq_slug}_{today.strftime('%Y%m%d')}_{now.strftime('%H%M')}"

    ctx = {
        "reference":   ref,
        "date_codir":  today.strftime("%d/%m/%Y"),
        "generated_at":now.strftime("%d/%m/%Y à %H:%M"),
        "equipement":  eq,
        "unite":       bilan.get("unite", "—"),
        "rul_jours":   bilan.get("rul_jours", "—"),
        "score_deg":   bilan.get("score_degradation_pct", "—"),
        "statut":      bilan.get("statut", "—"),
        "horizon":     scenarios.get("horizon_ans", 3),
        "analyse":     analyse,
        "scenarios":   scenarios,
        "portfolio":   portfolio,
        "historique":  hist,
    }

    s   = _S()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=1.8*cm, bottomMargin=1.4*cm,
        title=f"Fiche CODIR — {eq}",
        author="ResilientFlow AI",
    )

    pt    = _PT(ref, ctx["generated_at"])
    story = []

    _cover(story, s, ctx)
    _kpis(story, s, ctx)
    _portfolio(story, s, ctx)
    _scenarios(story, s, ctx)
    _analyse(story, s, ctx)
    _recommandation(story, s, ctx)
    _signatures(story, s, ctx)

    doc.build(story, onFirstPage=pt, onLaterPages=pt)
    return buf.getvalue()
