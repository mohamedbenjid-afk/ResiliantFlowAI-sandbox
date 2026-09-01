"""
utils/pdf_sophie.py
Générateur de Rapport Hebdomadaire — Agent Sophie (Manager Maintenance)
Format : A4, ReportLab Platypus — même charte que utils/pdf_codir.py

Usage:
    from utils.pdf_sophie import generate_sophie_pdf
    pdf_bytes = generate_sophie_pdf(ctx)
    st.download_button("Télécharger", pdf_bytes, file_name="Rapport_Sophie.pdf")

ctx attendu (voir pages/2_Sophie.py, TAB 3 — S3 RAPPORT HEBDOMADAIRE) :
    {
        "semaine":       int,
        "machine":       str,   # ex "Pompe P-17"
        "rul":           int/float,
        "statut":        str,   # "Nominal" / "Alerte" / "Critique"
        "historique":    list[dict]  # titre, type, statut, date, technicien, duree_estimee, cout_estime
        "pieces_stock":  list[dict]  # designation, statut_stock, stock_actuel, stock_minimum
    }
"""

import io
from datetime import datetime, date

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
)

# ── PALETTE (identique à pdf_codir.py) ─────────────────────────────────────────
BLEU        = HexColor("#1e3a5f")
BLEU_MED    = HexColor("#2563eb")
BLEU_CLAIR  = HexColor("#dbeafe")
AMBRE       = HexColor("#d97706")
VERT        = HexColor("#16a34a")
VERT_CLAIR  = HexColor("#dcfce7")
ROUGE       = HexColor("#dc2626")
ROUGE_CLAIR = HexColor("#fee2e2")
GRIS_F      = HexColor("#374151")
GRIS_M      = HexColor("#6b7280")
GRIS_C      = HexColor("#f3f4f6")
GRIS_TC     = HexColor("#f9fafb")

STATUT_COLOR = {"Nominal": VERT, "Alerte": AMBRE, "Critique": ROUGE}
STATUT_BG    = {"Nominal": VERT_CLAIR, "Alerte": HexColor("#fef3c7"), "Critique": ROUGE_CLAIR}

W, H = A4


# ── TEMPLATE DE PAGE ────────────────────────────────────────────────────────────
class _PT:
    def __init__(self, ref, generated_at):
        self.ref = ref
        self.generated_at = generated_at

    def __call__(self, canvas, doc):
        canvas.saveState()
        canvas.setFillColor(BLEU)
        canvas.rect(0, H - 1.4 * cm, W, 1.4 * cm, fill=1, stroke=0)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.setFillColor(white)
        canvas.drawString(1.8 * cm, H - 0.95 * cm, "RAPPORT HEBDOMADAIRE — AGENT SOPHIE")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(AMBRE)
        canvas.drawRightString(W - 1.8 * cm, H - 0.95 * cm, self.ref)
        canvas.setFillColor(GRIS_C)
        canvas.rect(0, 0, W, 1.0 * cm, fill=1, stroke=0)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(GRIS_M)
        canvas.drawCentredString(
            W / 2, 0.35 * cm,
            f"ResilientFlow AI — Généré le {self.generated_at} — Page {doc.page}"
        )
        canvas.restoreState()


# ── STYLES ──────────────────────────────────────────────────────────────────────
def _S():
    s = {}
    def ps(name, **kw):
        s[name] = ParagraphStyle(name, **kw)
    ps("h1",      fontName="Helvetica-Bold", fontSize=17, textColor=white, alignment=TA_CENTER, spaceAfter=2)
    ps("h1sub",   fontName="Helvetica",      fontSize=10, textColor=HexColor("#93c5fd"), alignment=TA_CENTER)
    ps("ref",     fontName="Helvetica-Bold", fontSize=9,  textColor=AMBRE, alignment=TA_CENTER)
    ps("sec",     fontName="Helvetica-Bold", fontSize=10, textColor=white, spaceBefore=3, spaceAfter=2)
    ps("body",    fontName="Helvetica",      fontSize=9,  textColor=GRIS_F, leading=13)
    ps("small",   fontName="Helvetica",      fontSize=8,  textColor=GRIS_M, leading=11)
    ps("kpi_val", fontName="Helvetica-Bold", fontSize=15, textColor=BLEU_MED, alignment=TA_CENTER)
    ps("kpi_lbl", fontName="Helvetica",      fontSize=8,  textColor=GRIS_M, alignment=TA_CENTER)
    ps("cell",    fontName="Helvetica",      fontSize=7.5,textColor=GRIS_F, leading=9)
    return s


def _sec_header(text, s):
    tbl = Table([[Paragraph(text, s["sec"])]], colWidths=[W - 4 * cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BLEU),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return tbl


# ── EN-TÊTE / COUVERTURE ────────────────────────────────────────────────────────
def _cover(story, s, ctx):
    tbl = Table([[
        Paragraph(f"RAPPORT HEBDOMADAIRE — SEMAINE {ctx['semaine']}", s["h1"]),
        Paragraph("Agent Sophie · Manager Maintenance", s["h1sub"]),
        Paragraph(f"Réf. {ctx['reference']}", s["ref"]),
    ]], colWidths=[W - 4 * cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BLEU),
        ("TOPPADDING", (0, 0), (-1, -1), 16),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
        ("LEFTPADDING", (0, 0), (-1, -1), 20),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.4 * cm))

    statut = ctx.get("statut", "—")
    data = [
        ["Machines couvertes", ctx.get("machine", "—"), "Date rapport", ctx["date_str"]],
        ["RUL P-17 (temps réel)", f"{ctx.get('rul', '—')}j", "Statut P-17", statut],
    ]
    t = Table(data, colWidths=[4.2 * cm, 5.8 * cm, 4.2 * cm, 5.8 * cm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), BLEU),
        ("TEXTCOLOR", (2, 0), (2, -1), BLEU),
        ("BACKGROUND", (0, 0), (-1, -1), GRIS_TC),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [white, GRIS_TC]),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#e5e7eb")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.4 * cm))


# ── KPIs ─────────────────────────────────────────────────────────────────────
def _kpis(story, s, ctx):
    story.append(_sec_header("1. INDICATEURS DE LA SEMAINE", s))
    story.append(Spacer(1, 0.2 * cm))

    def _plural(n, singulier, pluriel):
        return singulier if n == 1 else pluriel

    kpis = [
        (f"{ctx['taux_realisation']}%", "Taux réalisation", BLEU_CLAIR),
        (str(ctx["arrets_evites"]), _plural(ctx["arrets_evites"], "Arrêt évité", "Arrêts évités"), VERT_CLAIR),
        (str(ctx["n_ruptures"]), _plural(ctx["n_ruptures"], "Rupture stock", "Ruptures stock"), ROUGE_CLAIR if ctx["n_ruptures"] else GRIS_C),
        (f"{ctx['n_dispos']}/{ctx['n_equipe']}", "Techniciens dispos", GRIS_C),
    ]
    cells_val = [[Paragraph(v, s["kpi_val"]) for v, _, _ in kpis]]
    cells_lbl = [[Paragraph(l, s["kpi_lbl"]) for _, l, _ in kpis]]
    col_w = (W - 4 * cm) / len(kpis)

    tv = Table(cells_val, colWidths=[col_w] * len(kpis))
    tl = Table(cells_lbl, colWidths=[col_w] * len(kpis))
    bg_style = [
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for i, (_, _, c) in enumerate(kpis):
        bg_style.append(("BACKGROUND", (i, 0), (i, 0), c))
    tv.setStyle(TableStyle(bg_style))
    tl.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))

    story.append(tv)
    story.append(tl)
    story.append(Spacer(1, 0.3 * cm))


# ── INTERVENTIONS DE LA SEMAINE ─────────────────────────────────────────────────
def _interventions(story, s, ctx):
    story.append(_sec_header("2. INTERVENTIONS DE LA SEMAINE", s))
    story.append(Spacer(1, 0.2 * cm))

    hist = ctx.get("historique") or []
    if not hist:
        story.append(Paragraph("Aucune intervention enregistrée cette semaine.", s["body"]))
        story.append(Spacer(1, 0.3 * cm))
        return

    hdr = [["Machine", "Intervention", "Type", "Statut", "Date", "Technicien", "Durée", "Coût"]]
    rows = []
    for i in hist:
        cout  = i.get("cout_estime")
        duree = i.get("duree_estimee")
        rows.append([
            i.get("machine") or "—",
            Paragraph(i.get("titre") or "—", s["cell"]),
            Paragraph(i.get("type") or "—", s["cell"]),
            i.get("statut") or "—",
            i.get("date") or "—",
            Paragraph(i.get("technicien") or "—", s["cell"]),
            f"{duree}h" if isinstance(duree, (int, float)) else "—",
            f"{cout:,.0f} €" if isinstance(cout, (int, float)) else "—",
        ])
    t = Table(hdr + rows, colWidths=[1.8 * cm, 3.3 * cm, 2.1 * cm, 2.0 * cm, 2.0 * cm, 2.5 * cm, 1.6 * cm, 1.7 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLEU_MED),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#e5e7eb")),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, GRIS_TC]),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3 * cm))


# ── ÉTAT DU STOCK ────────────────────────────────────────────────────────────────
def _stock(story, s, ctx):
    story.append(_sec_header("3. ÉTAT DU STOCK PIÈCES", s))
    story.append(Spacer(1, 0.2 * cm))

    pieces = ctx.get("pieces_stock") or []
    if not pieces:
        story.append(Paragraph("Aucune donnée de stock disponible.", s["body"]))
        story.append(Spacer(1, 0.3 * cm))
        return

    def _num(v):
        return str(v) if isinstance(v, (int, float)) else "—"

    hdr = [["Machine", "Pièce", "Statut", "Stock actuel", "Stock minimum"]]
    rows = [[
        p.get("machine") or "—",
        Paragraph(p.get("designation") or "—", s["cell"]),
        p.get("statut_stock") or "—",
        _num(p.get("stock_actuel")),
        _num(p.get("stock_minimum")),
    ] for p in pieces]
    t = Table(hdr + rows, colWidths=[2.5 * cm, 5.5 * cm, 4 * cm, 3 * cm, 3 * cm])

    style = [
        ("BACKGROUND", (0, 0), (-1, 0), BLEU_MED),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#e5e7eb")),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, GRIS_TC]),
    ]
    for idx, p in enumerate(pieces, start=1):
        if p.get("statut_stock") == "Rupture":
            style.append(("BACKGROUND", (2, idx), (2, idx), ROUGE_CLAIR))
        elif p.get("statut_stock") == "Stock faible":
            style.append(("BACKGROUND", (2, idx), (2, idx), HexColor("#fef3c7")))
    t.setStyle(TableStyle(style))
    story.append(t)
    story.append(Spacer(1, 0.3 * cm))


# ── ENTRY POINT ──────────────────────────────────────────────────────────────────
def generate_sophie_pdf(data: dict) -> bytes:
    """
    Génère le rapport hebdomadaire PDF de l'Agent Sophie.

    Args:
        data (dict): voir docstring du module — construit directement depuis
                     les variables déjà calculées dans TAB 3 de pages/2_Sophie.py.

    Returns:
        bytes: contenu PDF prêt pour st.download_button()
    """
    now = datetime.now()
    today = date.today()
    semaine = data.get("semaine", today.isocalendar()[1])

    ref = f"RAPPORT_SOPHIE_S{semaine}_{today.strftime('%Y%m%d')}_{now.strftime('%H%M')}"

    ctx = {
        "reference": ref,
        "date_str": today.strftime("%d/%m/%Y"),
        "generated_at": now.strftime("%d/%m/%Y à %H:%M"),
        "semaine": semaine,
        "machine": data.get("machine", "Pompe P-17"),
        "rul": data.get("rul", "—"),
        "statut": data.get("statut", "—"),
        "taux_realisation": data.get("taux_realisation", 0),
        "arrets_evites": data.get("arrets_evites", 0),
        "n_ruptures": data.get("n_ruptures", 0),
        "n_dispos": data.get("n_dispos", 0),
        "n_equipe": data.get("n_equipe", 0),
        "historique": data.get("historique", []),
        "pieces_stock": data.get("pieces_stock", []),
    }

    s = _S()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=1.8 * cm, bottomMargin=1.4 * cm,
        title=f"Rapport Hebdomadaire Sophie — Semaine {semaine}",
        author="ResilientFlow AI",
    )

    pt = _PT(ref, ctx["generated_at"])
    story = []

    _cover(story, s, ctx)
    _kpis(story, s, ctx)
    _interventions(story, s, ctx)
    _stock(story, s, ctx)

    doc.build(story, onFirstPage=pt, onLaterPages=pt)
    return buf.getvalue()
