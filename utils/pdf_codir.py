"""
utils/pdf_codir.py
Générateur de Fiche CODIR — Décision d'investissement maintenance
Format : 1 page A4, design exécutif, ReportLab Platypus

Usage:
    from utils.pdf_codir import generate_codir_pdf
    pdf_bytes = generate_codir_pdf(result)   # result = run_agent_antoine()
    st.download_button("Télécharger", pdf_bytes, file_name="CODIR_Antoine.pdf")

Correctifs (revue Antoine) :
  - _portfolio() : colonne "Dégradation" retirée (score_degradation_pct est
    TOUJOURS None dans agent_antoine.py, absent du schéma ESCP) — affichait
    littéralement "None %" sur chaque ligne.
  - _scenarios() : "Point mort" du scénario C affiche "—" au lieu de
    "None mois vs A" quand payback_vs_correctif_mois vaut None.
  - _signatures() : BUG DE MISE EN PAGE CORRIGÉ. L'ancienne version empilait
    des listes de Flowables brutes dans une cellule de Table à une seule
    ligne — les noms des signataires (Antoine, Agent AI, PDG) disparaissaient
    du rendu et le texte "Signature : ___" débordait hors de la page.
    Reconstruit en tableau multi-lignes classique (une ligne par info :
    nom / rôle / fonction / ligne de signature), chaque cellule étant un
    Paragraph correctement dimensionné à sa colonne — plus de débordement,
    alignement propre en 3 colonnes.
  - _analyse() : tronquée à ~220 caractères (2-3 lignes) au lieu des 25
    premières lignes brutes du markdown LLM, dont la longueur est
    imprévisible. Nécessaire pour garantir que le document tienne sur UNE
    page quelle que soit la longueur du texte généré par le LLM. L'analyse
    complète reste consultable dans l'app Streamlit (onglet CODIR).
  - Marges et espacements resserrés dans tout le document pour gagner de
    la place et tenir sur une seule page A4.

Correctifs v2 (CAE + stock + arbitrage — ce que le PDF n'affichait pas alors
que agent_antoine.py et 3_Antoine.py l'exposaient déjà) :
  - _scenarios() : ajout d'une ligne "Durée" et d'une ligne "CAE (€/an)"
    dans le tableau des 3 scénarios. A/B et C ne portent pas sur la même
    durée (horizon_ans vs duree_vie_remplacement_ans) : comparer leurs NPV
    brutes n'a pas de sens financier, c'est le Coût Annuel Équivalent (CAE)
    qui doit guider la lecture — le texte sous le tableau le précise
    désormais explicitement. Le taux d'actualisation affiché dans les
    hypothèses n'était plus qu'un "5%" figé en dur, indépendant du paramètre
    réellement utilisé par la simulation — remplacé par la valeur réelle
    (sc["taux_actualisation_pct"]).
  - Ajout de _stock() : section compacte (4 cases façon bandeau KPI) —
    valeur immobilisée, nb références, pièces en rupture, pièces en alerte —
    plus une ligne listant les ruptures si elles existent. N'apparaît que si
    result["stock"] est fourni.
  - Ajout de _arbitrage() : section compacte n'apparaissant QUE si
    result["arbitrage"] est renseigné (c.-à-d. qu'un budget CAPEX a été
    saisi dans l'UI) — bandeau budget disponible/utilisé/restant + gain
    annuel total, puis tableau des machines retenues (limité aux 5
    meilleures par ratio gain/investissement, avec mention du nombre
    d'exclues) pour ne pas déborder d'une page.
  - Sections numérotées dynamiquement (compteur incrémental) plutôt qu'en
    dur : comme l'arbitrage n'apparaît pas toujours, une numérotation figée
    (1, 2, 3, 4, 5...) aurait laissé un trou ou désynchronisé les titres
    selon les cas. Ajout de la nouvelle formule d'ajout local pour garder
    le format de nombres cohérent avec agent_antoine.py (point comme
    séparateur de milliers, jamais de virgule) — l'ancien fichier utilisait
    encore le formatage Python par défaut (virgule) par endroits.
"""

import io, hashlib, re
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
VIOLET      = HexColor("#7c3aed")
VIOLET_CLAIR= HexColor("#ede9fe")
GRIS_F      = HexColor("#374151")
GRIS_M      = HexColor("#6b7280")
GRIS_C      = HexColor("#f3f4f6")
GRIS_TC     = HexColor("#f9fafb")

W, H = A4


def _clean_niveau(txt: str) -> str:
    """Retire les emojis en tête de niveau_risque (ex: "🔴 CRITIQUE" -> "CRITIQUE") :
    Helvetica ne les supporte pas et les affiche en carrés noirs dans le PDF."""
    if not txt:
        return txt
    return re.sub(r'^[^\wÀ-ÿ]+\s*', '', txt).strip()


def _fmt(v, decimals: int = 0) -> str:
    """Formate un nombre avec points comme séparateurs de milliers (ex: 2.082.545),
    cohérent avec le format utilisé dans agent_antoine.py et 3_Antoine.py.
    Jamais de virgule, pour ne pas mélanger les conventions dans le PDF."""
    if v is None:
        return "—"
    try:
        s = f"{v:,.{decimals}f}"
    except (TypeError, ValueError):
        return str(v)
    return s.replace(",", ".")


# ── TEMPLATE DE PAGE ──────────────────────────────────────────────────────────
class _PT:
    def __init__(self, ref, generated_at):
        self.ref          = ref
        self.generated_at = generated_at

    def __call__(self, canvas, doc):
        canvas.saveState()
        # Header band
        canvas.setFillColor(BLEU)
        canvas.rect(0, H - 1.2*cm, W, 1.2*cm, fill=1, stroke=0)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.setFillColor(white)
        canvas.drawString(1.5*cm, H - 0.8*cm, "CONFIDENTIEL — FICHE CODIR")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(AMBRE)
        canvas.drawRightString(W - 1.5*cm, H - 0.8*cm, self.ref)
        # Footer band
        canvas.setFillColor(GRIS_C)
        canvas.rect(0, 0, W, 0.8*cm, fill=1, stroke=0)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(GRIS_M)
        canvas.drawCentredString(W/2, 0.28*cm,
            f"ResilientFlow AI — Généré le {self.generated_at} — Page {doc.page}")
        canvas.restoreState()


# ── STYLES ────────────────────────────────────────────────────────────────────
def _S():
    s = {}
    def ps(name, **kw):
        s[name] = ParagraphStyle(name, **kw)
    ps("h1",       fontName="Helvetica-Bold", fontSize=16, textColor=white,    alignment=TA_CENTER, spaceAfter=1)
    ps("h1sub",    fontName="Helvetica",      fontSize=9,  textColor=HexColor("#93c5fd"), alignment=TA_CENTER)
    ps("ref",      fontName="Helvetica-Bold", fontSize=8,  textColor=AMBRE,    alignment=TA_CENTER)
    ps("sec",      fontName="Helvetica-Bold", fontSize=9.5,textColor=white,    spaceBefore=0, spaceAfter=0)
    ps("body",     fontName="Helvetica",      fontSize=8.5,textColor=GRIS_F,   leading=10.5, spaceAfter=1)
    ps("body_b",   fontName="Helvetica-Bold", fontSize=8.5,textColor=GRIS_F,   leading=11.5)
    ps("small",    fontName="Helvetica",      fontSize=7.5,textColor=GRIS_M,   leading=10)
    ps("kpi_val",  fontName="Helvetica-Bold", fontSize=13, textColor=BLEU_MED, alignment=TA_CENTER)
    ps("kpi_val_s",fontName="Helvetica-Bold", fontSize=11, textColor=BLEU_MED, alignment=TA_CENTER)
    ps("kpi_lbl",  fontName="Helvetica",      fontSize=7.5,textColor=GRIS_M,   alignment=TA_CENTER)
    ps("reco",     fontName="Helvetica-Bold", fontSize=10, textColor=BLEU,     leading=14, spaceAfter=2)
    ps("footer_c", fontName="Helvetica",      fontSize=7,  textColor=GRIS_M,   alignment=TA_CENTER)
    ps("sig_lbl",  fontName="Helvetica-Bold", fontSize=8.5,textColor=BLEU,     alignment=TA_CENTER)
    ps("sig_sub",  fontName="Helvetica",      fontSize=7,  textColor=GRIS_M,   alignment=TA_CENTER)
    return s


def _sec_header(num, text, s):
    """Titre de section numéroté dynamiquement (voir _NumGen) plutôt qu'en dur,
    pour que la numérotation reste correcte même quand une section optionnelle
    (arbitrage) est absente."""
    tbl = Table([[Paragraph(f"{num}. {text}", s["sec"])]], colWidths=[W - 4*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), BLEU),
        ("TOPPADDING",    (0,0), (-1,-1), 2),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
    ]))
    return tbl


class _NumGen:
    """Compteur de sections. Un appel à next() retourne le prochain numéro."""
    def __init__(self):
        self._n = 0
    def next(self):
        self._n += 1
        return self._n


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
        ("TOPPADDING",    (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 10),
        ("LEFTPADDING",   (0,0), (-1,-1), 20),
        ("ROWBACKGROUNDS",(0,0), (-1,-1), [BLEU]),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.15*cm))

    # Tableau info
    eq    = ctx.get("equipement", "—")
    unite = ctx.get("unite", "—")
    rul   = ctx.get("rul_jours")
    deg   = ctx.get("score_deg")
    rul_str = f"{rul} j" if rul is not None else "—"
    deg_str = f"{deg} %" if deg is not None else "—"
    data  = [
        ["Équipement analysé", eq,       "Date CODIR",      ctx["date_codir"]],
        ["Unité / Zone",       unite,    "Directeur Tech.",  "Antoine"],
        ["RUL estimé",         rul_str,  "Dégradation",      deg_str],
        ["Statut machine",     ctx.get("statut", "—"), "Horizon analyse", f"{ctx.get('horizon', 3)} ans"],
    ]
    t = Table(data, colWidths=[4.2*cm, 5.8*cm, 4.2*cm, 5.8*cm])
    t.setStyle(TableStyle([
        ("FONTNAME",  (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME",  (2,0), (2,-1), "Helvetica-Bold"),
        ("FONTSIZE",  (0,0), (-1,-1), 8),
        ("TEXTCOLOR", (0,0), (0,-1), BLEU),
        ("TEXTCOLOR", (2,0), (2,-1), BLEU),
        ("BACKGROUND",(0,0), (-1,-1), GRIS_TC),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [white, GRIS_TC]),
        ("GRID",      (0,0), (-1,-1), 0.5, HexColor("#e5e7eb")),
        ("TOPPADDING",(0,0), (-1,-1), 3),
        ("BOTTOMPADDING",(0,0),(-1,-1), 3),
        ("LEFTPADDING", (0,0),(-1,-1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.07*cm))

    # Signature SHA-256
    h = hashlib.sha256(f"{ctx['reference']}{ctx['date_codir']}{eq}".encode()).hexdigest()[:32]
    sig_tbl = Table([[Paragraph(f"Empreinte numérique : {h.upper()}", s["small"])]],
                    colWidths=[W - 4*cm])
    sig_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), AMBRE_CLAIR),
        ("TOPPADDING",    (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ("BOX",           (0,0), (-1,-1), 1, AMBRE),
    ]))
    story.append(sig_tbl)
    story.append(Spacer(1, 0.15*cm))


# ── KPIs CLÉS ─────────────────────────────────────────────────────────────────
def _kpis(story, s, ctx, num):
    story.append(_sec_header(num, "INDICATEURS CLÉS", s))
    story.append(Spacer(1, 0.07*cm))

    hist = ctx.get("historique") or {}
    def _kv(v, suffix="", fallback="—"):
        if v is None: return fallback
        if isinstance(v, float) and v == int(v): v = int(v)
        return f"{v}{suffix}"
    kpis = [
        (_kv(hist.get('mtbf_jours'), " j"),    "MTBF",            BLEU_CLAIR),
        (_kv(hist.get('mttr_heures'), " h"),    "MTTR",            GRIS_C),
        (_kv(hist.get('roi_maintenance'), "×", "×—").replace("×", "× ") if hist.get('roi_maintenance') else "—",
                                                 "ROI Prescriptif", VERT_CLAIR),
        (f"{_fmt((hist.get('cout_total_maintenance_eur') or 0)/1000, 0)} k€", "OPEX Cumul",    GRIS_C),
        (f"{_fmt((hist.get('couts_arrets_evites_eur') or 0)/1000, 0)} k€",   "Arrêts évités", VERT_CLAIR),
        (str(hist.get('nb_pannes_correctives') or 0),                     "Pannes correct.",ROUGE_CLAIR),
    ]
    cells_val = [[Paragraph(v, s["kpi_val"]) for v, _, _ in kpis]]
    cells_lbl = [[Paragraph(l, s["kpi_lbl"]) for _, l, _ in kpis]]

    col_w = (W - 4*cm) / 6
    tv = Table(cells_val, colWidths=[col_w]*6)
    tl = Table(cells_lbl, colWidths=[col_w]*6)
    bg_style = [
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("TOPPADDING",    (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 1),
    ]
    for i, (_, _, c) in enumerate(kpis):
        bg_style.append(("BACKGROUND", (i,0), (i,-1), c))
    for tbl in [tv, tl]:
        tbl.setStyle(TableStyle(bg_style))
    story.append(tv)
    story.append(tl)
    story.append(Spacer(1, 0.07*cm))


# ── PORTFOLIO MACHINES ────────────────────────────────────────────────────────
def _portfolio(story, s, ctx, num):
    """
    Colonne "Dégradation" supprimée : score_degradation_pct vaut TOUJOURS
    None dans agent_antoine.py (absent du schéma ESCP) -> affichait
    littéralement "None %" sur chaque ligne. 5 colonnes au lieu de 6.
    """
    portfolio = ctx.get("portfolio")
    if not portfolio:
        return
    story.append(_sec_header(num, "PORTFOLIO MACHINES — RANKING PAR RISQUE", s))
    story.append(Spacer(1, 0.07*cm))

    hdr = [["Machine", "Unité", "RUL (j)", "Score risque", "Niveau"]]
    rows = []
    for m in portfolio.get("ranking", []):
        rows.append([
            m.get("machine", ""),
            m.get("unite", ""),
            str(m.get("rul_jours", 0)),
            f"{m.get('score_risque', 0)} / 100",
            _clean_niveau(m.get("niveau_risque", "")),
        ])

    data   = hdr + rows
    col_ws = [5.5*cm, 2.5*cm, 2*cm, 3*cm, 4*cm]
    t = Table(data, colWidths=col_ws)

    style = [
        ("BACKGROUND",    (0,0), (-1,0), BLEU_MED),
        ("TEXTCOLOR",     (0,0), (-1,0), white),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 8),
        ("GRID",          (0,0), (-1,-1), 0.4, HexColor("#e5e7eb")),
        ("ALIGN",         (2,0), (-1,-1), "CENTER"),
        ("TOPPADDING",    (0,0), (-1,-1), 2),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
    ]
    for i, row in enumerate(rows, 1):
        niveau = row[4]  # index décalé de 5 -> 4 après suppression de la colonne Dégradation
        bg = (ROUGE_CLAIR  if "CRITIQUE" in niveau else
              ORANGE_CLAIR if "ÉLEVÉ"    in niveau else
              AMBRE_CLAIR  if "MODÉRÉ"   in niveau else VERT_CLAIR)
        style.append(("BACKGROUND", (0,i), (-1,i), bg))

    t.setStyle(TableStyle(style))
    story.append(t)
    story.append(Spacer(1, 0.07*cm))


# ── TABLEAU 3 SCÉNARIOS ───────────────────────────────────────────────────────
def _scenarios(story, s, ctx, num):
    """
    v2 : ajout des lignes "Durée" et "CAE (€/an)". A/B (horizon_ans) et C
    (duree_vie_remplacement_ans) ne portent pas sur la même durée -> comparer
    leurs NPV brutes n'a pas de sens financier ; c'est le Coût Annuel
    Équivalent (CAE) qui doit guider la lecture, précisé explicitement sous
    le tableau. Le taux d'actualisation affiché reflète désormais la valeur
    réelle transmise à la simulation (sc["taux_actualisation_pct"]), plus le
    "5%" figé en dur de l'ancienne version.
    """
    sc = ctx.get("scenarios")
    if not sc:
        return
    story.append(_sec_header(num, "SIMULATION FINANCIÈRE — 3 SCÉNARIOS (CAE)", s))
    story.append(Spacer(1, 0.07*cm))

    sc_data  = sc.get("scenarios", {})
    horizon  = sc.get("horizon_ans", 3)
    hyp      = sc.get("hypotheses", {})
    taux_pct = sc.get("taux_actualisation_pct", 5)

    hyp_txt = (
        f"Hypothèses : panne moyenne {_fmt(hyp.get('cout_panne_moyen_eur', 0))} € · "
        f"{hyp.get('pannes_par_an_sans_prescriptif', 0)} pannes/an sans prescriptif · "
        f"{hyp.get('pannes_par_an_avec_prescriptif', 0)} avec · taux {_fmt(taux_pct, 1)}% · "
        f"CAPEX remplacement complet {_fmt(hyp.get('capex_complet_eur', 0))} €"
    )
    story.append(Paragraph(hyp_txt, s["small"]))
    story.append(Spacer(1, 0.07*cm))

    a = sc_data.get("A_correctif_pur", {})
    b = sc_data.get("B_maintien_prescriptif", {})
    c = sc_data.get("C_remplacement", {})
    duree_c = c.get("duree_annees", sc.get("duree_vie_remplacement_ans", 12))

    # Point mort : payback_vs_correctif_mois peut valoir None. Test explicite
    # sur None plutôt que .get(clé, "—") pour ne pas afficher "None mois vs A".
    payback_val = c.get("payback_vs_correctif_mois")
    payback_str = f"{_fmt(payback_val, 1)} mois vs A" if payback_val is not None else "—"

    hdr  = [["", f"A — Correctif pur ({horizon} ans)", f"B — Prescriptif ({horizon} ans)", f"C — Remplacement ({duree_c} ans)"]]
    rows = [
        ["Description",  a.get("description","")[:35], b.get("description","")[:35], c.get("description","")[:35]],
        ["Coût total",   f"{_fmt(a.get('cout_total_eur',0))} €", f"{_fmt(b.get('cout_total_eur',0))} €", f"{_fmt(c.get('cout_total_eur',0))} €"],
        ["NPV",          f"{_fmt(a.get('npv_eur',0))} €",        f"{_fmt(b.get('npv_eur',0))} €",        f"{_fmt(c.get('npv_eur',0))} €"],
        ["CAE (€/an)",   f"{_fmt(a.get('cout_annuel_equivalent_eur',0))} €", f"{_fmt(b.get('cout_annuel_equivalent_eur',0))} €", f"{_fmt(c.get('cout_annuel_equivalent_eur',0))} €"],
        ["Point mort",   "—", "—", payback_str],
    ]
    data   = hdr + rows
    col_ws = [3.5*cm, 5.5*cm, 5.5*cm, 5.5*cm]
    t = Table(data, colWidths=col_ws)

    reco = sc.get("recommandation_financiere", "")
    best_col = (1 if "A" in reco else 2 if "B" in reco else 3)
    # La ligne CAE (€/an) est celle qui fonde la recommandation -> mise en
    # évidence supplémentaire (bordure) pour guider l'œil du CODIR.
    # data rows après fusion de la durée dans l'en-tête : 0=hdr, 1=Description,
    # 2=Coût total, 3=NPV, 4=CAE, 5=Point mort.
    cae_row_idx = 4

    style = [
        ("BACKGROUND",    (0,0), (-1,0), BLEU_MED),
        ("TEXTCOLOR",     (0,0), (-1,0), white),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,0), 7.5),
        ("FONTNAME",      (0,1), (0,-1), "Helvetica-Bold"),
        ("TEXTCOLOR",     (0,1), (0,-1), BLEU),
        ("FONTSIZE",      (0,1), (-1,-1), 8),
        ("GRID",          (0,0), (-1,-1), 0.4, HexColor("#e5e7eb")),
        ("ALIGN",         (1,0), (-1,-1), "CENTER"),
        ("TOPPADDING",    (0,0), (-1,-1), 2),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [white, GRIS_TC, white, GRIS_TC, white]),
        ("BACKGROUND",    (best_col, cae_row_idx), (best_col, cae_row_idx), VERT_CLAIR),
        ("BOX",           (0, cae_row_idx), (-1, cae_row_idx), 0.8, BLEU_MED),
    ]
    t.setStyle(TableStyle(style))
    story.append(t)

    eco_cae = sc.get("economie_annuelle_cae_eur", 0)
    story.append(Spacer(1, 0.05*cm))
    story.append(Paragraph(
        f"Durées différentes A/B vs C : comparer au <b>CAE</b>, pas à la NPV brute. "
        f"Économie annuelle vs correctif : <b>{_fmt(eco_cae)} €/an</b> — Recommandation : <b>{reco}</b>",
        s["body"]
    ))
    story.append(Spacer(1, 0.07*cm))


# ── STOCK PIÈCES DÉTACHÉES (nouveau) ──────────────────────────────────────────
def _stock(story, s, ctx, num):
    """
    Section compacte façon bandeau KPI (même style que _kpis) — n'apparaît
    que si result["stock"] (get_etat_stock_strategique) est fourni. Reste
    volontairement courte pour ne pas faire déborder le document d'une page.
    """
    stock = ctx.get("stock")
    if not stock:
        return
    story.append(_sec_header(num, "STOCK PIÈCES DÉTACHÉES", s))
    story.append(Spacer(1, 0.07*cm))

    ruptures = stock.get("pieces_en_rupture", []) or []
    alertes  = stock.get("pieces_alerte", []) or []

    cells = [
        (f"{_fmt(stock.get('valeur_stock_immobilisee_eur', 0))} €", "Valeur immobilisée", BLEU_CLAIR),
        (str(stock.get("nb_references", 0)),                       "Références en stock", GRIS_C),
        (str(len(ruptures)),                                       "Pièces en rupture",
            ROUGE_CLAIR if ruptures else VERT_CLAIR),
        (str(len(alertes)),                                        "Pièces en alerte",
            ORANGE_CLAIR if alertes else VERT_CLAIR),
    ]
    cells_val = [[Paragraph(v, s["kpi_val_s"]) for v, _, _ in cells]]
    cells_lbl = [[Paragraph(l, s["kpi_lbl"]) for _, l, _ in cells]]
    col_w = (W - 4*cm) / 4
    tv = Table(cells_val, colWidths=[col_w]*4)
    tl = Table(cells_lbl, colWidths=[col_w]*4)
    bg_style = [
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("TOPPADDING",    (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 1),
    ]
    for i, (_, _, c) in enumerate(cells):
        bg_style.append(("BACKGROUND", (i,0), (i,-1), c))
    for tbl in [tv, tl]:
        tbl.setStyle(TableStyle(bg_style))
    story.append(tv)
    story.append(tl)

    if ruptures:
        noms = ", ".join(p.get("designation", "—") for p in ruptures[:4])
        if len(ruptures) > 4:
            noms += f" (+{len(ruptures) - 4} autres)"
        story.append(Paragraph(f"<b>En rupture :</b> {noms}", s["small"]))
    story.append(Spacer(1, 0.07*cm))


# ── ARBITRAGE BUDGÉTAIRE MULTI-MACHINES (nouveau, conditionnel) ──────────────
def _arbitrage(story, s, ctx, num):
    """
    N'apparaît QUE si result["arbitrage"] est fourni, c'est-à-dire qu'un
    budget CAPEX disponible a été saisi dans l'UI (US-A2, checkbox
    "Arbitrer entre plusieurs machines à risque"). Limité aux 5 machines
    retenues au meilleur ratio gain/investissement pour tenir sur 1 page ;
    les exclues sont résumées en une ligne, pas listées en détail.
    """
    arbitrage = ctx.get("arbitrage")
    if not arbitrage:
        return
    story.append(_sec_header(num, "ARBITRAGE BUDGÉTAIRE MULTI-MACHINES", s))
    story.append(Spacer(1, 0.07*cm))

    story.append(Paragraph(
        f"Budget disponible : <b>{_fmt(arbitrage.get('budget_disponible_eur', 0))} €</b> · "
        f"utilisé : <b>{_fmt(arbitrage.get('budget_utilise_eur', 0))} €</b> · "
        f"restant : <b>{_fmt(arbitrage.get('budget_restant_eur', 0))} €</b> · "
        f"gain annuel total : <b>{_fmt(arbitrage.get('gain_annuel_total_eur', 0))} €/an</b> · "
        f"{arbitrage.get('nb_machines_retenues', 0)} / {arbitrage.get('nb_machines_eligibles', 0)} "
        f"machine(s) retenue(s)",
        s["body"]
    ))
    story.append(Spacer(1, 0.05*cm))

    retenues = arbitrage.get("machines_retenues", []) or []
    non_retenues = arbitrage.get("machines_non_retenues", []) or []

    if retenues:
        hdr  = [["Machine (priorité)", "Niveau", "CAPEX", "Gain annuel", "Ratio €/€"]]
        rows = []
        for m in retenues[:5]:
            rows.append([
                f"{m.get('machine','')} ({m.get('unite','—')})",
                _clean_niveau(m.get("niveau_risque", "—")),
                f"{_fmt(m.get('capex_complet_eur', 0))} €",
                f"{_fmt(m.get('gain_annuel_eur', 0))} €/an",
                f"{m.get('ratio_gain_par_euro', 0):.3f}",
            ])
        data   = hdr + rows
        col_ws = [5.5*cm, 3*cm, 3*cm, 3.5*cm, 2*cm]
        t = Table(data, colWidths=col_ws)
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0), VIOLET),
            ("TEXTCOLOR",     (0,0), (-1,0), white),
            ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",      (0,0), (-1,-1), 7.5),
            ("GRID",          (0,0), (-1,-1), 0.4, HexColor("#e5e7eb")),
            ("ALIGN",         (2,0), (-1,-1), "CENTER"),
            ("TOPPADDING",    (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
            ("LEFTPADDING",   (0,0), (-1,-1), 5),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [white, VIOLET_CLAIR]),
        ]))
        story.append(t)
        if len(retenues) > 5:
            story.append(Paragraph(
                f"+ {len(retenues) - 5} autre(s) machine(s) retenue(s) — détail dans l'application.",
                s["small"]
            ))
    else:
        story.append(Paragraph("Aucune machine retenue dans le budget disponible.", s["small"]))

    if non_retenues:
        story.append(Paragraph(
            f"{len(non_retenues)} machine(s) éligible(s) non retenue(s) — budget insuffisant "
            f"pour cette itération (détail dans l'application).",
            s["small"]
        ))
    story.append(Spacer(1, 0.07*cm))


# ── ANALYSE LLM (extrait très court) ──────────────────────────────────────────
def _analyse(story, s, ctx, num):
    """
    Version tronquée à ~220 caractères (2-3 lignes) au lieu des 25 premières
    lignes brutes du markdown. Nécessaire pour garantir 1 page quelle que
    soit la longueur du texte généré par le LLM (imprévisible). L'analyse
    complète reste disponible dans l'app Streamlit (onglet CODIR).
    """
    analyse = ctx.get("analyse", "")
    if not analyse:
        return
    story.append(_sec_header(num, "ANALYSE AGENT AI — SYNTHÈSE", s))
    story.append(Spacer(1, 0.07*cm))

    # Nettoyage markdown basique (titres, gras) -> texte brut sur une ligne
    plain = re.sub(r'^#+\s*', '', analyse, flags=re.MULTILINE)
    plain = plain.replace('**', '').replace('\n', ' ').strip()
    plain = re.sub(r'\s+', ' ', plain)

    MAX_CHARS = 220
    if len(plain) > MAX_CHARS:
        plain = plain[:MAX_CHARS].rsplit(' ', 1)[0] + '…'

    story.append(Paragraph(plain, s["body"]))
    story.append(Paragraph(
        "Analyse complète disponible dans l'application ResilientFlow AI (onglet CODIR).",
        s["small"]
    ))
    story.append(Spacer(1, 0.07*cm))


# ── RECOMMANDATION ENCADRÉE ───────────────────────────────────────────────────
def _recommandation(story, s, ctx, num):
    sc      = ctx.get("scenarios") or {}
    reco    = sc.get("recommandation_financiere", "")
    eco_cae = sc.get("economie_annuelle_cae_eur", sc.get("economie_prescriptif_vs_correctif_eur", 0))
    hist    = ctx.get("historique") or {}
    roi     = hist.get("roi_maintenance", "—")
    mtbf    = hist.get("mtbf_jours", "—")

    story.append(_sec_header(num, "RECOMMANDATION CODIR", s))
    story.append(Spacer(1, 0.07*cm))

    reco_text = (
        f"Sur la base de l'analyse des données de fiabilité, de l'historique de maintenance "
        f"et de la simulation financière (comparaison au Coût Annuel Équivalent), "
        f"l'agent ResilientFlow AI recommande : <b>{reco}</b>.<br/><br/>"
        f"Le maintien de la couche prescriptive génère une économie annuelle estimée de "
        f"<b>{_fmt(eco_cae)} €/an</b> vs une stratégie corrective pure, avec un ROI de "
        f"<b>×{roi}</b> et un MTBF de <b>{mtbf} jours</b>."
    )

    tbl = Table([[Paragraph(reco_text, s["reco"])]], colWidths=[W - 4*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), BLEU_CLAIR),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 12),
        ("RIGHTPADDING",  (0,0), (-1,-1), 12),
        ("BOX",           (0,0), (-1,-1), 1.5, BLEU_MED),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.15*cm))


# ── SIGNATURES ────────────────────────────────────────────────────────────────
def _signatures(story, s, ctx):
    """
    Correctif : reconstruit en tableau multi-lignes classique.
    L'ancienne version empilait des listes de Flowables brutes dans une
    cellule de Table à une seule ligne, ce qui faisait disparaître les
    noms des signataires du rendu et provoquait un débordement du texte
    "Signature : ___" hors de la page. Chaque cellule est désormais un
    Paragraph correctement dimensionné à la largeur de sa colonne — plus
    de débordement, alignement propre en 3 colonnes bien délimitées.
    """
    # Rôle + fonction fusionnés sur une seule ligne (au lieu de deux) pour
    # gagner une ligne de tableau et faire tenir le bloc sur la page 1.
    signataires = [
        ("Antoine",  "Directeur Technique — Décision CAPEX/OPEX"),
        ("Agent AI", "ResilientFlow AI — Analyse prescriptive"),
        ("PDG",      "Direction Générale — Validation budgétaire"),
    ]

    col_w = (W - 4*cm) / 3
    data = [
        [Paragraph(n, s["sig_lbl"]) for n, r in signataires],
        [Paragraph(r, s["sig_sub"]) for n, r in signataires],
        [Paragraph("Signature :", s["sig_sub"]) for _ in signataires],
        [Paragraph("_______________________", s["sig_sub"]) for _ in signataires],
    ]
    t = Table(data, colWidths=[col_w]*3)
    t.setStyle(TableStyle([
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("LINEAFTER",     (0,0), (1,-1),  0.5, GRIS_M),
        ("TOPPADDING",    (0,0), (-1,-1), 1),
        ("BOTTOMPADDING", (0,0), (-1,-1), 1),
        ("TOPPADDING",    (0,2), (-1,2),  5),  # espace avant la ligne de signature
    ]))
    # KeepTogether : sans ça, ReportLab peut couper ce tableau entre deux
    # pages si l'espace restant est juste insuffisant (ex: noms sur une
    # page, ligne de signature sur la suivante) — rendu inacceptable pour
    # un document à faire signer. On préfère pousser tout le bloc sur la
    # page suivante plutôt que de le fragmenter.
    story.append(KeepTogether([
        HRFlowable(width="100%", thickness=0.5, color=GRIS_M),
        Spacer(1, 0.07*cm),
        t,
    ]))


# ── ENTRY POINT ───────────────────────────────────────────────────────────────
def generate_codir_pdf(result: dict) -> bytes:
    """
    Génère la fiche CODIR PDF (1 page) depuis le résultat de run_agent_antoine().

    Args:
        result (dict) : {
            "analyse":    str  — texte Markdown LLM
            "scenarios":  dict — simuler_scenarios_investissement()
            "portfolio":  dict — get_top_equipements_a_risque()
            "bilan":      dict — get_bilan_equipement()
            "historique": dict — get_historique_couts_maintenance()
            "stock":      dict — get_etat_stock_strategique() (optionnel)
            "arbitrage":  dict|None — arbitrer_budget_remplacement(), présent
                          uniquement si un budget CAPEX a été fourni dans l'UI
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
    stock     = result.get("stock")      or {}
    arbitrage = result.get("arbitrage")  or None
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
        "stock":       stock,
        "arbitrage":   arbitrage,
    }

    s   = _S()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.0*cm, bottomMargin=0.9*cm,
        title=f"Fiche CODIR — {eq}",
        author="ResilientFlow AI",
    )

    pt    = _PT(ref, ctx["generated_at"])
    story = []
    numgen = _NumGen()

    _cover(story, s, ctx)
    _kpis(story, s, ctx, numgen.next())
    _portfolio(story, s, ctx, numgen.next())
    _scenarios(story, s, ctx, numgen.next())
    _stock(story, s, ctx, numgen.next())
    if ctx.get("arbitrage"):
        _arbitrage(story, s, ctx, numgen.next())
    _analyse(story, s, ctx, numgen.next())
    _recommandation(story, s, ctx, numgen.next())
    _signatures(story, s, ctx)

    doc.build(story, onFirstPage=pt, onLaterPages=pt)
    return buf.getvalue()


# ── TEST STANDALONE ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Petit jeu de données factice pour vérifier que le PDF se génère et que
    # la numérotation des sections reste correcte avec ET sans arbitrage.
    fake_result = {
        "analyse": "**Synthèse** : la Pompe P-17 approche de sa limite de fatigue structurelle. "
                   "Le maintien de la couche prescriptive reste la meilleure option à court terme.",
        "scenarios": {
            "equipement": "Pompe P-17", "horizon_ans": 3, "taux_actualisation_pct": 5.0,
            "hypotheses": {"cout_panne_moyen_eur": 25000, "pannes_par_an_sans_prescriptif": 4.2,
                           "pannes_par_an_avec_prescriptif": 0.84, "capex_complet_eur": 86500},
            "scenarios": {
                "A_correctif_pur": {"description": "Arrêt prescriptif", "cout_total_eur": 315000,
                                     "npv_eur": -290000, "cout_annuel_equivalent_eur": 106500, "duree_annees": 3},
                "B_maintien_prescriptif": {"description": "Continuité ResilientFlow", "cout_total_eur": 45000,
                                            "npv_eur": -41000, "cout_annuel_equivalent_eur": 15000, "duree_annees": 3},
                "C_remplacement": {"description": "CAPEX complet 86.500 €, amorti sur 12 ans",
                                    "cout_total_eur": 104500, "npv_eur": -95000,
                                    "cout_annuel_equivalent_eur": 10700, "duree_annees": 12,
                                    "payback_vs_correctif_mois": 14.3},
            },
            "recommandation_financiere": "C — Remplacement",
            "economie_prescriptif_vs_correctif_eur": 270000,
            "economie_annuelle_cae_eur": 95800,
        },
        "portfolio": {"ranking": [
            {"machine": "Pompe P-17", "unite": "Unité B", "rul_jours": 12, "score_risque": 82, "niveau_risque": "🔴 CRITIQUE"},
            {"machine": "Compresseur C-03", "unite": "Unité A", "rul_jours": 45, "score_risque": 58, "niveau_risque": "🟠 ÉLEVÉ"},
        ]},
        "bilan": {"machine": "Pompe P-17", "unite": "Unité B", "rul_jours": 12, "statut": "Critique"},
        "historique": {"mtbf_jours": 87, "mttr_heures": 4.5, "roi_maintenance": 3.2,
                        "cout_total_maintenance_eur": 45000, "couts_arrets_evites_eur": 210000,
                        "nb_pannes_correctives": 6},
        "stock": {"valeur_stock_immobilisee_eur": 12500, "nb_references": 8,
                   "pieces_en_rupture": [{"designation": "Joint torique"}], "pieces_alerte": []},
        "arbitrage": {
            "budget_disponible_eur": 100000, "budget_utilise_eur": 86500, "budget_restant_eur": 13500,
            "gain_annuel_total_eur": 95800, "nb_machines_eligibles": 2, "nb_machines_retenues": 1,
            "machines_retenues": [{"machine": "Pompe P-17", "unite": "Unité B", "niveau_risque": "🔴 CRITIQUE",
                                    "capex_complet_eur": 86500, "gain_annuel_eur": 95800, "ratio_gain_par_euro": 1.107}],
            "machines_non_retenues": [{"machine": "Compresseur C-03", "unite": "Unité A", "niveau_risque": "🟠 ÉLEVÉ",
                                        "capex_complet_eur": 78000, "raison_exclusion": "Budget restant insuffisant"}],
        },
    }
    with open("test_codir.pdf", "wb") as f:
        f.write(generate_codir_pdf(fake_result))
    print("PDF généré : test_codir.pdf")
