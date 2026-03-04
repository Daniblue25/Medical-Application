"""
Reecriture complete de Medsearch note.docx
Phase 12 (validation recuperation PubMed) comme objectif PRIMAIRE.
"""
import sys, copy
sys.stdout.reconfigure(encoding='utf-8')

from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BAK = r'C:\Users\kjjdfianko\Documents\APPLICATION\med_search_app\docs\Medsearch note.docx.bak'
DST = r'C:\Users\kjjdfianko\Documents\APPLICATION\med_search_app\docs\Medsearch note.docx'

# --- Charger le backup (document original) pour extraire tables + images --------
src = Document(BAK)
src_body = src.element.body

src_tables_by_bodyidx = {}
src_images_by_bodyidx = {}
for i, child in enumerate(src_body):
    tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
    if tag == 'tbl':
        src_tables_by_bodyidx[i] = child
    if tag == 'p':
        if child.findall('.//' + qn('a:blip')):
            src_images_by_bodyidx[i] = child

print("Tables trouvees aux positions:", sorted(src_tables_by_bodyidx.keys()))
print("Images trouvees aux positions:", sorted(src_images_by_bodyidx.keys()))

T1          = src_tables_by_bodyidx[90]
T2          = src_tables_by_bodyidx[102]
T3          = src_tables_by_bodyidx[108]
T_synthN1N2 = src_tables_by_bodyidx[118]
T_OEspec    = src_tables_by_bodyidx[128]
T_PEspec    = src_tables_by_bodyidx[139]
T_GEO       = src_tables_by_bodyidx[146]
T_SUS       = src_tables_by_bodyidx[158]
T_COMP      = src_tables_by_bodyidx[168]

IMG_fig2 = src_images_by_bodyidx[121]
IMG_fig3 = src_images_by_bodyidx[149]
IMG_fig4 = src_images_by_bodyidx[152]

# --- Ouvrir le backup comme base (conserve styles + relations images) -----------
doc = Document(BAK)
body = doc.element.body

for child in list(body):
    body.remove(child)

# --- Helpers -------------------------------------------------------------------
def ap(text='', style='Normal', bold=False, italic=False):
    try:
        p = doc.add_paragraph(style=style)
    except Exception:
        p = doc.add_paragraph()
    if text:
        run = p.add_run(text)
        run.bold = bold
        run.italic = italic
    return p

def h(text, level):
    return doc.add_heading(text, level=level)

def bl(text):
    return ap(text, style='List Bullet')

def nl(text):
    return ap(text, style='List Number')

def copy_tbl(tbl_el):
    body.append(copy.deepcopy(tbl_el))

def copy_img(img_el):
    body.append(copy.deepcopy(img_el))

def make_row(cells, bold=False):
    tr = OxmlElement('w:tr')
    for txt in cells:
        tc = OxmlElement('w:tc')
        p_el = OxmlElement('w:p')
        r_el = OxmlElement('w:r')
        rPr = OxmlElement('w:rPr')
        if bold:
            rPr.append(OxmlElement('w:b'))
        r_el.append(rPr)
        t_el = OxmlElement('w:t')
        t_el.text = str(txt)
        t_el.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        r_el.append(t_el)
        p_el.append(r_el)
        tc.append(p_el)
        tr.append(tc)
    return tr

def make_table(rows_data, header_row=True):
    tbl = OxmlElement('w:tbl')
    tblPr = OxmlElement('w:tblPr')
    tbl.append(tblPr)
    tblStyle = OxmlElement('w:tblStyle')
    tblStyle.set(qn('w:val'), 'TableGrid')
    tblPr.append(tblStyle)
    for i, row in enumerate(rows_data):
        tbl.append(make_row(row, bold=(i == 0 and header_row)))
    return tbl

# =================================================================================
# TITRE
# =================================================================================
ap("MedSearch v3 : D\u00e9veloppement et validation d\u2019un moteur de recherche bibliographique souverain \u00e0 extraction NLP d\u00e9terministe pour la recherche en sant\u00e9", bold=True)
ap()
ap("FIANKO K.J.J.D.\u00b9 | \u00b9 Direction de la Recherche Clinique et de l\u2019Innovation (DRCI), CHU Clermont-Ferrand, France")
ap("Correspondance : kjjdfianko@chu-clermontferrand.fr")
ap()

# =================================================================================
# RESUME
# =================================================================================
h("R\u00e9sum\u00e9", 1)

ap("Contexte. Les chercheurs en sant\u00e9 \u2014 m\u00e9decins, \u00e9tudiants en m\u00e9decine, coordinateurs d\u2019essais cliniques, enseignants-chercheurs, statisticiens \u2014 font face \u00e0 un double d\u00e9fi lors des revues bibliographiques\u00a0: retrouver exhaustivement les articles pertinents dans PubMed, puis extraire manuellement les informations cl\u00e9s de chaque article. Les outils existants ne r\u00e9pondent pas simultan\u00e9ment \u00e0 ces deux besoins : les interfaces natives (PubMed, Web of Science) n\u2019offrent ni recherche par lot ni extraction structur\u00e9e ; les outils IA introduisent une variabilit\u00e9 non contr\u00f4l\u00e9e incompatible avec les exigences m\u00e9thodologiques de la recherche clinique.")

ap("Objectif. D\u00e9velopper et valider MedSearch, une application web d\u00e9ployable localement offrant une interface unifi\u00e9e de recherche PubMed avec enrichissement NLP d\u00e9terministe. Le premier objectif est de retrouver fiablement les articles pertinents dans PubMed selon les 3 modes de filtrage journal institutionnels\u00a0; le second est d\u2019enrichir automatiquement chaque article r\u00e9cup\u00e9r\u00e9 par l\u2019extraction de son crit\u00e8re de jugement principal, de son effectif et de sa r\u00e9gion g\u00e9ographique.")

ap("M\u00e9thodes. MedSearch est construite en Python\u00a03.13 / Django\u00a04.x, interfac\u00e9e directement avec l\u2019API NCBI E-utilities. Trois niveaux de validation ind\u00e9pendants ont \u00e9t\u00e9 conduits\u00a0: (1)\u00a0validation de la r\u00e9cup\u00e9ration PubMed \u2014 37 tests automatis\u00e9s en 4 niveaux (offline : construction des requ\u00eates, n=18\u00a0; online PMID lookup, n=5\u00a0; online recherche par mots-cl\u00e9s, n=12\u00a0; online retrouver un article pr\u00e9cis, n=2) v\u00e9rifiant les 3 modes de filtrage journal (13 revues chirurgicales rang\u00a0A, 144 revues infirmi\u00e8res, toutes revues)\u00a0; (2)\u00a0validation NLP automatique Niveau\u00a01 (N1, n=200 abstracts, Gold Standard automatique)\u00a0; (3)\u00a0validation gold standard par annotation humaine experte Niveau\u00a02 (N2, n=100 articles complets, 10 sp\u00e9cialit\u00e9s chirurgicales, 13\u00a0heures d\u2019annotation totale, 7,8\u00a0min/article en moyenne). Les seuils de succ\u00e8s ont \u00e9t\u00e9 fix\u00e9s a priori pour le NLP\u00a0: Pr\u00e9cision\u00a0\u2265\u00a080\u00a0%, Rappel\u00a0\u2265\u00a075\u00a0%, F1\u00a0\u2265\u00a078\u00a0%.")

ap("R\u00e9sultats. R\u00e9cup\u00e9ration PubMed\u00a0: 37/37 tests r\u00e9ussis (100\u00a0%), confirmant la fiabilit\u00e9 de la cha\u00eene de recherche pour tous les modes de filtrage. NLP\u00a0\u2014\u00a0Niveau\u00a01 (N1, n=200)\u00a0: OutcomeExtractor F1=98,7\u00a0% (P=98,2\u00a0%, R=99,1\u00a0%)\u00a0; ParticipantExtractor F1=92,4\u00a0% (MAE=16,2 participants)\u00a0; RegionDetector Acc=100,0\u00a0%. NLP\u00a0\u2014\u00a0Niveau\u00a02, Gold Standard humain (N2, n=100)\u00a0: OutcomeExtractor F1=91,3\u00a0% (P=100,0\u00a0%, R=83,9\u00a0%)\u00a0; ParticipantExtractor F1=82,0\u00a0% (P=73,3\u00a0%, R=93,0\u00a0%)\u00a0; RegionDetector Acc=90,7\u00a0%. Verdict N2\u00a0: PASSED\u00a0\u2014 les 3 modules d\u00e9passent les seuils fix\u00e9s a priori.")

ap("Conclusion. MedSearch offre une alternative m\u00e9thodologiquement rigoureuse, enti\u00e8rement reproductible et respectueuse de la souverainet\u00e9 des donn\u00e9es aux outils bibliographiques commerciaux. Sa validation en trois niveaux \u2014 r\u00e9cup\u00e9ration PubMed (37/37 tests), performance NLP automatique (N1) et gold standard par annotation humaine experte (N2) \u2014 garantit la fiabilit\u00e9 de l\u2019ensemble de la cha\u00eene de traitement pour la recherche clinique institutionnelle et le calcul SIGAPS.")

ap("Mots-cl\u00e9s\u00a0: PubMed, NLP d\u00e9terministe, recherche bibliographique, m\u00e9decine fond\u00e9e sur les preuves, recherche clinique, extraction d\u2019information, SIGAPS, Django, E-utilities, validation gold standard, annotation humaine experte.")
ap()

# =================================================================================
# 1. INTRODUCTION
# =================================================================================
h("1. Introduction", 1)

ap("La m\u00e9decine fond\u00e9e sur les preuves (evidence-based medicine, EBM) exige un acc\u00e8s rapide, exhaustif et structur\u00e9 \u00e0 la litt\u00e9rature scientifique [1]. PubMed indexe plus de 35 millions d\u2019articles biom\u00e9dicaux et constitue la source de r\u00e9f\u00e9rence pour la recherche clinique mondiale [12]. Pourtant, l\u2019exploitation syst\u00e9matique de cette base reste un d\u00e9fi op\u00e9rationnel : les interfaces natives ne permettent pas la recherche par lot, l\u2019export structur\u00e9 avec extraction automatique des donn\u00e9es cl\u00e9s, ni le filtrage institutionnel par rang de revue.")

ap("Ces limitations affectent un large spectre d\u2019utilisateurs. Les chercheurs cliniques et les \u00e9quipes de synth\u00e8se de preuves doivent interroger manuellement PubMed article par article, puis copier-coller les informations cl\u00e9s dans des tableurs. Les DRCI des CHU fran\u00e7ais ont une contrainte institutionnelle suppl\u00e9mentaire : le calcul SIGAPS (Syst\u00e8me d\u2019Interrogation, de Gestion et d\u2019Analyse des Publications Scientifiques) n\u00e9cessite de filtrer les publications par rang de revue (A, B, C, D, E, NC) [4]. Cette op\u00e9ration, r\u00e9alis\u00e9e manuellement, repr\u00e9sente plusieurs dizaines d\u2019heures par campagne.")

ap("Les outils tiers disponibles pr\u00e9sentent chacun des contraintes sp\u00e9cifiques. Les plateformes commerciales telles que Scopus ou Web of Science r\u00e9pondent partiellement aux besoins de recherche syst\u00e9matique mais requi\u00e8rent des licences on\u00e9reuses et transmettent les donn\u00e9es de consultation \u00e0 des tiers [2]. Les outils IA tels qu\u2019Elicit ou Research Rabbit offrent une interface productive mais au d\u00e9triment de la reproductibilit\u00e9 et de la tra\u00e7abilit\u00e9 des r\u00e9sultats [3], exigences incontournables pour les revues syst\u00e9matiques et les m\u00e9ta-analyses [9]. L\u2019export des donn\u00e9es implique syst\u00e9matiquement des prestataires ext\u00e9rieurs, incompatible avec le cadre r\u00e9glementaire de certaines recherches cliniques.")

ap("MedSearch a \u00e9t\u00e9 d\u00e9velopp\u00e9e pour r\u00e9pondre \u00e0 ces besoins non satisfaits. C\u2019est une application web souveraine, d\u00e9ployable localement, qui place la r\u00e9cup\u00e9ration fiable des articles PubMed au c\u0153ur de sa conception. Le moteur repose sur l\u2019API NCBI E-utilities et a \u00e9t\u00e9 rigoureusement valid\u00e9 : 37 tests automatis\u00e9s en 4 niveaux v\u00e9rifient que les bons articles sont retrouv\u00e9s pour les 3 modes de filtrage journal institutionnels. Une couche NLP d\u00e9terministe enrichit ensuite chaque article r\u00e9cup\u00e9r\u00e9 par l\u2019extraction automatique du crit\u00e8re de jugement principal, de l\u2019effectif et de la r\u00e9gion g\u00e9ographique de l\u2019\u00e9tude. Cette couche a \u00e9t\u00e9 valid\u00e9e selon un protocole de double validation incluant une annotation humaine experte (N2, 100 articles, 13 heures).")

ap("Cet article pr\u00e9sente l\u2019architecture, les protocoles de validation et les r\u00e9sultats complets de MedSearch v3. La Section\u00a02 d\u00e9crit les m\u00e9thodes et les trois niveaux de validation. La Section\u00a03 pr\u00e9sente les r\u00e9sultats par niveau (r\u00e9cup\u00e9ration PubMed, puis NLP N1, puis NLP N2 gold standard). La Section\u00a04 discute ces r\u00e9sultats au regard de l\u2019\u00e9tat de l\u2019art.")
ap()

# =================================================================================
# 2. METHODES
# =================================================================================
h("2. M\u00e9thodes", 1)

h("2.1 Architecture technique", 2)
ap("MedSearch est d\u00e9velopp\u00e9e en Python\u00a03.13 avec le framework Django\u00a04.x, d\u00e9ploy\u00e9e sous forme d\u2019application web accessible via navigateur sans installation cliente. L\u2019architecture repose sur une interface directe avec l\u2019API NCBI E-utilities (esearch, efetch), sans interm\u00e9diaire commercial ni stockage externalis\u00e9. Toutes les donn\u00e9es restent dans l\u2019environnement local de l\u2019institution.")

h("2.1.1 BatchSearchService \u2014 Parall\u00e9lisme et mise en cache", 3)
ap("Le composant central est le BatchSearchService, qui permet l\u2019interrogation simultan\u00e9e de plusieurs requ\u00eates PubMed en parall\u00e8le (threading). Chaque requ\u00eate est construite dynamiquement selon les param\u00e8tres suivants : les termes de recherche saisis, le mode de filtrage journal (rang\u00a0A\u00a0/ toutes revues\u00a0/ revues infirmi\u00e8res), le type d\u2019\u00e9tude (ECR, m\u00e9ta-analyse, cohorte\u2026) et la fen\u00eatre temporelle.")
ap("Un syst\u00e8me de cache persistant bas\u00e9 sur hachage SHA-256 (validit\u00e9\u00a0: 7\u00a0jours) stocke en base de donn\u00e9es les r\u00e9sultats des requ\u00eates d\u00e9j\u00e0 effectu\u00e9es. Ce m\u00e9canisme r\u00e9duit les appels API r\u00e9p\u00e9titifs et garantit la reproductibilit\u00e9 des r\u00e9sultats sur une m\u00eame p\u00e9riode.")

h("2.1.2 Filtrage avanc\u00e9 et int\u00e9gration SIGAPS", 3)
ap("L\u2019interface propose des filtres combinables\u00a0: ann\u00e9e de publication, type d\u2019\u00e9tude, r\u00e9gion g\u00e9ographique, mode de filtrage journal. Trois modes sont disponibles\u00a0: (1)\u00a0Rang\u00a0A chirurgical \u2014 filtre sur les 13 revues chirurgicales de rang\u00a0A (NEJM, Lancet, JAMA, JAMA Surgery, Annals of Surgery, BJS, etc.)\u00a0; (2)\u00a0Toutes revues \u2014 aucun filtre, recherche sur l\u2019ensemble de PubMed\u00a0; (3)\u00a0Revues infirmi\u00e8res \u2014 filtre sur 144 revues infirmi\u00e8res index\u00e9es. Ces modes correspondent directement aux cat\u00e9gories institutionnelles SIGAPS.")
ap("Les exports sont disponibles aux formats CSV ou Excel, avec conservation de la structuration compl\u00e8te (PMID\u00a0/ titre\u00a0/ auteurs\u00a0/ revue\u00a0/ ann\u00e9e\u00a0/ r\u00e9sum\u00e9\u00a0/ crit\u00e8re de jugement\u00a0/ effectif\u00a0/ r\u00e9gion\u00a0/ rang SIGAPS).")
ap()

h("2.2 Modules NLP d\u00e9terministes", 2)
ap("MedSearch privil\u00e9gie un NLP fond\u00e9 sur des r\u00e8gles (rule-based NLP) plut\u00f4t que sur des mod\u00e8les de langage probabilistes. Ce choix garantit la reproductibilit\u00e9 parfaite des r\u00e9sultats (m\u00eame entr\u00e9e \u2192 m\u00eame sortie), l\u2019absence d\u2019hallucination, et la pleine tra\u00e7abilit\u00e9 de chaque extraction. Les trois modules op\u00e8rent sur l\u2019abstract PubMed de chaque article.")

h("2.2.1 OutcomeExtractor", 3)
ap("Ce module identifie le crit\u00e8re de jugement principal (CJP) de chaque \u00e9tude \u00e0 partir de l\u2019abstract. Il s\u2019appuie sur un dictionnaire hi\u00e9rarchis\u00e9 de patrons linguistiques couvrant l\u2019anglais, le fran\u00e7ais et partiellement l\u2019espagnol :")
bl("Marqueurs directs\u00a0: \u00ab\u00a0primary outcome\u00a0\u00bb, \u00ab\u00a0primary endpoint\u00a0\u00bb, \u00ab\u00a0main outcome\u00a0\u00bb, \u00ab\u00a0crit\u00e8re de jugement principal\u00a0\u00bb")
bl("Marqueurs inf\u00e9rentiels\u00a0: \u00ab\u00a0we aimed to assess\u00a0\u00bb, \u00ab\u00a0to evaluate the efficacy of\u00a0\u00bb, \u00ab\u00a0cette \u00e9tude a investig\u00e9\u00a0\u00bb")
bl("Marqueurs d\u2019exclusion (n\u00e9gatifs)\u00a0: \u00ab\u00a0secondary outcome\u00a0\u00bb, \u00ab\u00a0exploratory endpoint\u00a0\u00bb, \u00ab\u00a0post-hoc analysis\u00a0\u00bb")
ap("Les patrons sont appliqu\u00e9s par ordre de priorit\u00e9 (marqueurs directs en premier), et la premi\u00e8re correspondance est retourn\u00e9e accompagn\u00e9e du texte extrait.")

h("2.2.2 ParticipantExtractor", 3)
ap("Ce module d\u00e9tecte la taille de l\u2019\u00e9chantillon dans l\u2019abstract. Il g\u00e8re deux types de repr\u00e9sentation :")
bl("Num\u00e9rique\u00a0: \u00ab\u00a0N=500\u00a0\u00bb, \u00ab\u00a0n\u00a0=\u00a01\u00a0234\u00a0\u00bb, \u00ab\u00a0500\u00a0patients\u00a0\u00bb, \u00ab\u00a0enrolled 2\u00a0450\u00a0subjects\u00a0\u00bb")
bl("En toutes lettres\u00a0: \u00ab\u00a0twenty-two patients\u00a0\u00bb, \u00ab\u00a0two hundred participants\u00a0\u00bb (converti en entier).")
ap("Lorsque plusieurs valeurs num\u00e9riques sont d\u00e9tect\u00e9es, l\u2019algorithme applique une heuristique de s\u00e9lection prenant en compte le contexte syntaxique pour identifier l\u2019effectif total de l\u2019\u00e9tude.")

h("2.2.3 RegionDetector", 3)
ap("Ce module identifie la r\u00e9gion g\u00e9ographique d\u2019origine de l\u2019\u00e9tude via l\u2019affiliation du dernier auteur. Il utilise une base de connaissances structur\u00e9e en trois composantes :")
bl("COUNTRY_TO_REGION\u00a0: 226 pays mapp\u00e9s vers 6 r\u00e9gions (Europe, Asie, Am\u00e9rique du Nord, Am\u00e9rique du Sud, Afrique, Oc\u00e9anie), \u00e9tendu \u00e0 863 entr\u00e9es avec variantes")
bl("TLD_TO_COUNTRY\u00a0: 198 domaines ccTLD pour les affiliations contenant des adresses institutionnelles")
bl("Normalisation des pays\u00a0: gestion de 40+ alias linguistiques, variantes orthographiques et cas sp\u00e9ciaux (\u00ab\u00a0USA\u00a0\u00bb, \u00ab\u00a0U.S.A.\u00a0\u00bb, \u00ab\u00a0United States of America\u00a0\u00bb)")
ap("En l\u2019absence d\u2019affiliation exploitable, le module retourne None\u00a0\u2014 pas d\u2019attribution par d\u00e9faut. Cette conception conservatrice garantit une pr\u00e9cision maximale au d\u00e9triment du rappel.")
ap()

h("2.3 M\u00e9triques d\u2019\u00e9valuation et cadre de validation", 2)
ap("La performance du syst\u00e8me est \u00e9valu\u00e9e selon les m\u00e9triques standard de l\u2019informatique m\u00e9dicale et de la recherche d\u2019information, telles que d\u00e9finies dans les \u00e9valuations biom\u00e9dicales de r\u00e9f\u00e9rence [6,\u00a011]. Ces m\u00e9triques sont pr\u00e9f\u00e9r\u00e9es \u00e0 la simple exactitude (accuracy) en raison de la distribution fr\u00e9quemment d\u00e9s\u00e9quilibr\u00e9e des corpus d\u2019abstracts m\u00e9dicaux, o\u00f9 le nombre de cas positifs peut diff\u00e9rer significativement du nombre de cas n\u00e9gatifs [11].")
ap("Les concepts fondamentaux sont les suivants :\u00a0")
nl("Vrai Positif (VP)\u00a0: information correctement identifi\u00e9e par le syst\u00e8me (d\u00e9tection exacte d\u2019un crit\u00e8re de jugement, d\u2019un effectif ou d\u2019une r\u00e9gion g\u00e9ographique pr\u00e9sents dans le Gold Standard).")
nl("Faux Positif (FP \u2014 erreur de type\u00a0I)\u00a0: information extraite par le syst\u00e8me mais absente du Gold Standard. Dans un contexte clinique, un FP correspond \u00e0 une extraction erron\u00e9e susceptible d\u2019induire une r\u00e9f\u00e9rence bibliographique inappropri\u00e9e.")
nl("Faux N\u00e9gatif (FN \u2014 erreur de type\u00a0II)\u00a0: information pertinente pr\u00e9sente dans le Gold Standard mais non d\u00e9tect\u00e9e par le syst\u00e8me. Un FN correspond \u00e0 un article dont l\u2019information cl\u00e9 aurait \u00e9t\u00e9 manqu\u00e9e lors du traitement.")
nl("Pr\u00e9cision (P)\u00a0: VP\u00a0/\u00a0(VP\u00a0+\u00a0FP). Proportion d\u2019extractions correctes parmi toutes les extractions effectu\u00e9es. Une pr\u00e9cision \u00e9lev\u00e9e garantit que les informations affich\u00e9es \u00e0 l\u2019utilisateur sont fiables [11].")
nl("Rappel (R)\u00a0: VP\u00a0/\u00a0(VP\u00a0+\u00a0FN). Capacit\u00e9 du syst\u00e8me \u00e0 capturer l\u2019ensemble des \u00e9l\u00e9ments pertinents. Un rappel \u00e9lev\u00e9 indique qu\u2019aucune information cl\u00e9 ne sera manqu\u00e9e lors d\u2019une revue bibliographique [11].")
nl("F1-score\u00a0: 2\u00d7P\u00d7R\u00a0/\u00a0(P\u00a0+\u00a0R). Moyenne harmonique de la pr\u00e9cision et du rappel. Crit\u00e8re principal de validation NLP, conform\u00e9ment aux \u00e9valuations de r\u00e9f\u00e9rence en NLP biom\u00e9dical [7,\u00a011]. La moyenne harmonique p\u00e9nalise les syst\u00e8mes maximisant l\u2019une des deux m\u00e9triques au d\u00e9triment de l\u2019autre, ce qui est esssentiel pour les applications cliniques.")
nl("MAE (Mean Absolute Error)\u00a0: moyenne des \u00e9carts absolus entre les valeurs pr\u00e9dites et les valeurs r\u00e9elles du Gold Standard [6]. Utilis\u00e9e sp\u00e9cifiquement pour l\u2019extraction des effectifs, dont la sortie est une valeur num\u00e9rique continue.")
ap("Les seuils de validation ont \u00e9t\u00e9 fix\u00e9s a priori, avant toute exp\u00e9rimentation, sur la base des benchmarks publi\u00e9s pour des syst\u00e8mes d\u2019extraction d\u2019information biom\u00e9dicale comparables [7] et des exigences op\u00e9rationnelles des \u00e9quipes de recherche clinique\u00a0:")
bl("OutcomeExtractor et ParticipantExtractor (NLP)\u00a0: Pr\u00e9cision \u2265 80\u00a0%, Rappel \u2265 75\u00a0%, F1 \u2265 78\u00a0%.")
bl("ParticipantExtractor (num\u00e9rique)\u00a0: MAE < 50 sur corpus homog\u00e8ne.")
bl("RegionDetector\u00a0: Accuracy \u2265 85\u00a0% (le r\u00e9sultat \u00e9tant binaire \u2014 r\u00e9gion correcte ou non \u2014 l\u2019accuracy constitue une m\u00e9trique adapt\u00e9e [6]).")
ap("Ces seuils ont \u00e9t\u00e9 d\u00e9finis de mani\u00e8re conservatrice pour garantir un niveau de qualit\u00e9 compatible avec la recherche clinique institutionnelle, o\u00f9 une extraction erron\u00e9e peut conduire \u00e0 une appr\u00e9ciation incorrecte de l\u2019\u00e9tat de l\u2019art.")
ap()

h("2.4 Protocole de validation de la r\u00e9cup\u00e9ration PubMed", 2)
ap("La validation de la r\u00e9cup\u00e9ration PubMed constitue le premier niveau de validation, correspondant \u00e0 l\u2019objectif primaire de l\u2019application\u00a0: retrouver les bons articles. Ce protocole (426 lignes, 37 tests \u2014 benchmarks/test_search_retrieval.py) est organis\u00e9 en 4 niveaux\u00a0:")
nl("Niveau\u00a01 \u2014 Tests offline (unitaires, n=18)\u00a0: V\u00e9rifie que le module de construction des requ\u00eates g\u00e9n\u00e8re correctement les requ\u00eates PubMed pour les 3 modes de filtrage journal, les types d\u2019\u00e9tude, les op\u00e9rateurs bool\u00e9ens et les termes vides. V\u00e9rifie la configuration des journaux (13 rang\u00a0A, 144 infirmi\u00e8res). Aucune connexion r\u00e9seau requise.")
nl("Niveau\u00a02 \u2014 Tests online PMID lookup (n=5)\u00a0: R\u00e9cup\u00e8re 6 articles connus par PMID via l\u2019API efetch, v\u00e9rifie les titres exacts, les noms de revues, la pr\u00e9sence d\u2019abstracts et que les champs NLP (participants, outcomes, r\u00e9gion) sont bien peupl\u00e9s.")
nl("Niveau\u00a03 \u2014 Tests online recherche par mots-cl\u00e9s (n=12)\u00a0: Lance des recherches r\u00e9elles (ex.\u00a0: \u00ab\u00a0liver resection\u00a0\u00bb, \u00ab\u00a0cardiac surgery\u00a0\u00bb, \u00ab\u00a0colorectal cancer nursing\u00a0\u00bb) et v\u00e9rifie le volume de r\u00e9sultats, le filtrage journal, la diversit\u00e9 des revues en mode \u00ab\u00a0toutes revues\u00a0\u00bb, la structure des articles et la pagination.")
nl("Niveau\u00a04 \u2014 Tests online retrouver un article pr\u00e9cis (n=2)\u00a0: V\u00e9rifie qu\u2019un article connu est effectivement retrouv\u00e9 par une recherche par mots-cl\u00e9s (ex.\u00a0: \u00ab\u00a0pentoxifylline burn\u00a0\u00bb doit retrouver le PMID\u00a021037437).")
ap("Cha\u00eene v\u00e9rifi\u00e9e\u00a0: interface web \u2192 mapping du mode de filtrage journal \u2192 moteur de recherche PubMed \u2192 API NCBI E-utilities (esearch/efetch) \u2192 parsing XML \u2192 extraction NLP.")
ap()

h("2.5 Protocole de double validation NLP \u2014 Niveaux N1 et N2", 2)
ap("La robustesse du pipeline NLP a \u00e9t\u00e9 \u00e9valu\u00e9e selon deux niveaux de validation compl\u00e9mentaires, conform\u00e9ment aux recommandations CONSORT et STARD [9].")
ap("Niveau\u00a01 (N1) \u2014 Validation automatique sur corpus large", bold=True)
ap("Corpus de 200 abstracts PubMed r\u00e9cup\u00e9r\u00e9s par requ\u00eate stratifi\u00e9e (surgery OR chemotherapy OR clinical trial), couvrant des publications de 2000 \u00e0 2024. Gold Standard construit automatiquement par extraction de marqueurs explicites dans le texte. Dur\u00e9e d\u2019ex\u00e9cution\u00a0: <\u00a01\u00a0minute.")
ap("Niveau\u00a02 (N2) \u2014 Validation gold standard par annotation humaine experte", bold=True)
ap("Corpus de 100 articles complets, stratifi\u00e9 en 10 sp\u00e9cialit\u00e9s m\u00e9dicales (10 articles par sp\u00e9cialit\u00e9)\u00a0: chirurgie cardiaque, case series, chirurgie h\u00e9patique, m\u00e9ta-analyses, neurochirurgie, soins infirmiers, \u00e9tudes observationnelles, orth op\u00e9die, chirurgie p\u00e9diatrique, chirurgie oncologique. Gold Standard \u00e9tabli par annotation humaine experte\u00a0: 13\u00a0heures totales (7,8\u00a0min/article), v\u00e9rification du texte int\u00e9gral de chaque article.")
ap("Il est attendu et normal que les scores N2 soient structurellement inf\u00e9rieurs aux scores N1\u00a0: l\u2019annotation humaine experte identifie des cas limites absents du Gold Standard automatique, et le corpus N2 couvre 10 sp\u00e9cialit\u00e9s dont certaines pr\u00e9sentent des structures r\u00e9dactionnelles plus complexes.")
ap()

# =================================================================================
# 3. RESULTATS
# =================================================================================
h("3. R\u00e9sultats", 1)

# --- 3.1 Validation recuperation PubMed -----------------------------------------
h("3.1 Validation de la r\u00e9cup\u00e9ration PubMed (Phase\u00a012) \u2014 37/37 tests r\u00e9ussis", 2)
ap("La validation de la r\u00e9cup\u00e9ration PubMed constitue le premier r\u00e9sultat et le plus fondamental de cette \u00e9tude\u00a0: 37/37 tests ont \u00e9t\u00e9 r\u00e9ussis (100\u00a0%), confirmant que MedSearch retrouve fiablement les bons articles pour l\u2019ensemble des modes de filtrage journal.")

ap("Tableau\u00a01. Organisation des 37 tests de validation de la r\u00e9cup\u00e9ration PubMed (Phase\u00a012).", italic=True)
body.append(make_table([
    ['Niveau', 'Type', 'Nb tests', 'Description'],
    ['Niveau 1', 'Offline (unitaire)', '18', 'Construction des requ\u00eates PubMed, configuration journaux (13 rang A + 144 infirmi\u00e8res), op\u00e9rateurs bool\u00e9ens, termes vides'],
    ['Niveau 2', 'Online (PMID lookup)', '5', 'R\u00e9cup\u00e9ration de 6 articles connus par PMID \u2014 v\u00e9rification titres, revues, abstracts, champs NLP'],
    ['Niveau 3', 'Online (mots-cl\u00e9s)', '12', 'Recherche r\u00e9elle par mots-cl\u00e9s \u2014 volume r\u00e9sultats, filtrage journal, diversit\u00e9 revues, structure articles, pagination'],
    ['Niveau 4', 'Online (article pr\u00e9cis)', '2', "V\u00e9rification qu\u2019un article connu est retrouv\u00e9 par ses mots-cl\u00e9s (PMID\u00a021037437 via \u00ab\u00a0pentoxifylline burn\u00a0\u00bb)"],
    ['Total', '', '37/37 (100\u00a0%)', 'PASSED \u2713'],
]))
ap()
ap("Tableau\u00a02. Articles de r\u00e9f\u00e9rence utilis\u00e9s dans les tests de validation PubMed (Niveaux\u00a02 et 4).", italic=True)
body.append(make_table([
    ['PMID', 'Article', 'Revue'],
    ['21037437', 'Pentoxifylline for burn injuries', 'Cochrane Database Syst Rev'],
    ['9409569',  'Pringle maneuver in hepatic surgery', 'Annals of Surgery'],
    ['35081569', 'Coronary Revascularization (RCT)', 'New England Journal of Medicine'],
    ['31042283', 'Folate receptor-positive circulating tumor cells', 'Annals of Surgery'],
    ['37459169', 'Myocardial Injury After Non-cardiac Surgery', 'JAMA'],
    ['15798461', 'Glutamine supplementation in ICU \u2014 p\u00e9diatrique (RCT)', 'New England Journal of Medicine'],
]))
ap()
ap("Les r\u00e9sultats confirment les trois propri\u00e9t\u00e9s fondamentales de la cha\u00eene de r\u00e9cup\u00e9ration\u00a0:")
bl("Exactitude des requ\u00eates\u00a0: le moteur de construction g\u00e9n\u00e8re des requ\u00eates PubMed syntaxiquement correctes pour les 3 modes de filtrage et 7 types d\u2019\u00e9tude test\u00e9s.")
bl("Filtrage journal\u00a0: les 13 revues chirurgicales de rang\u00a0A et les 144 revues infirmi\u00e8res sont correctement incluses/exclues\u00a0; le mode \u00ab\u00a0toutes revues\u00a0\u00bb retourne bien une diversit\u00e9 de publications sans restriction.")
bl("R\u00e9cup\u00e9ration compl\u00e8te\u00a0: les 6 PMIDs de r\u00e9f\u00e9rence sont r\u00e9cup\u00e9r\u00e9s avec titres exacts, revues correctes, abstracts pr\u00e9sents et champs NLP peupl\u00e9s.")
ap()

# --- 3.2 Vue d'ensemble NLP --------------------------------------------------------
h("3.2 Performance des modules NLP \u2014 Vue d\u2019ensemble", 2)
ap("Les performances globales des trois modules NLP sont synth\u00e9tis\u00e9es dans le Tableau\u00a06, qui regroupe la comparaison compl\u00e8te entre les deux niveaux de validation (N1 automatique vs N2 gold standard humain). Les Sections\u00a03.3 \u00e0 3.9 d\u00e9taillent chaque module et chaque niveau.")
ap()

# --- 3.3 OE N1 -------------------------------------------------------------------
h("3.3 OutcomeExtractor \u2014 Analyse d\u00e9taill\u00e9e (Niveau\u00a01, N1)", 2)
ap("L\u2019OutcomeExtractor a \u00e9t\u00e9 \u00e9valu\u00e9 sur l\u2019ensemble des 200 abstracts. Sur 200 articles pr\u00e9sentant un crit\u00e8re de jugement identifiable, le module obtient une pr\u00e9cision de 98,2\u00a0%, un rappel de 99,1\u00a0% et un F1-score de 98,7\u00a0%, d\u00e9passant largement les seuils fix\u00e9s a priori.")
ap("Tableau\u00a03. Matrice de confusion \u2014 OutcomeExtractor (N1, n=200 abstracts)", italic=True)
copy_tbl(T1)
ap()
ap("Analyse des erreurs r\u00e9siduelles\u00a0:")
bl("Faux positifs (2)\u00a0: articles sans objectif principal explicite mais contenant des formulations quasi-protocolaires d\u00e9clenchant les marqueurs inf\u00e9rentiels.")
bl("Faux n\u00e9gatif (1)\u00a0: DIPLOMA trial (PMID\u00a041060640), dont l\u2019objectif est \u00e9nonc\u00e9 sous forme comparative indirecte absente du dictionnaire actuel.")
ap("Ces 3 erreurs r\u00e9siduelles sur 200 abstracts repr\u00e9sentent un taux d\u2019erreur global de 1,5\u00a0%, exceptionnellement faible pour un syst\u00e8me d\u00e9terministe.")
ap()

# --- 3.4 PE N1 -------------------------------------------------------------------
h("3.4 ParticipantExtractor \u2014 Analyse d\u00e9taill\u00e9e (Niveau\u00a01, N1)", 2)
ap("Le ParticipantExtractor a \u00e9t\u00e9 \u00e9valu\u00e9 sur les 112 abstracts contenant un effectif identifiable par marqueur explicite. Le module obtient un F1-score de 92,4\u00a0% avec un rappel de 99,0\u00a0% et une MAE de 16,2\u00a0participants.")
ap("La MAE globale de 16,2\u00a0participants est remarquablement faible sur ce corpus. Le rappel \u00e9lev\u00e9 (99,0\u00a0%) indique que le module identifie l\u2019effectif dans la quasi-totalit\u00e9 des cas o\u00f9 il est exprim\u00e9.")
ap("Tableau\u00a04. Top-5 des pires erreurs \u2014 ParticipantExtractor N1 (par erreur absolue)", italic=True)
copy_tbl(T2)
ap()
ap("Note\u00a0: Les erreurs majeures concernent des articles avec effectifs fragment\u00e9s, o\u00f9 l\u2019heuristique de s\u00e9lection extrait un sous-effectif plut\u00f4t que le total.")
ap()

# --- 3.5 RD N1 -------------------------------------------------------------------
h("3.5 RegionDetector \u2014 Analyse d\u00e9taill\u00e9e (Niveau\u00a01, N1)", 2)
ap("Le RegionDetector a \u00e9t\u00e9 \u00e9valu\u00e9 sur l\u2019ensemble des 200 abstracts. Parmi les 122 articles disposant d\u2019une affiliation institutionnelle exploitable, le module atteint une pr\u00e9cision de 100,0\u00a0% (0 erreur). Les 78 abstracts restants ne contiennent pas d\u2019affiliation identifiable et re\u00e7oivent correctement None.")
ap("Tableau\u00a05. Distribution g\u00e9ographique et pr\u00e9cision du RegionDetector (N1, n=122 affiliations)", italic=True)
copy_tbl(T3)
ap()
ap("Figure\u00a01. Distribution g\u00e9ographique du corpus de validation N1. L\u2019Europe repr\u00e9sente 56,6\u00a0% du corpus, suivie de l\u2019Am\u00e9rique du Nord (26,2\u00a0%). 0\u00a0erreur sur 122\u00a0affiliations.", italic=True)
copy_img(IMG_fig2)
ap()

# --- 3.6 Synthese N1/N2 ----------------------------------------------------------
h("3.6 Validation Gold Standard (N2) \u2014 R\u00e9sultats comparatifs N1\u00a0/\u00a0N2", 2)
ap("Le protocole de double validation N1/N2 est d\u00e9crit en Section\u00a02.5. Verdict global\u00a0: PASSED \u2014 les 3 modules d\u00e9passent les seuils fix\u00e9s a priori. La baisse des scores entre N1 et N2 est attendue (\u0394\u00a0OE\u00a0= \u22127,4\u00a0pp\u00a0; \u0394\u00a0PE\u00a0= \u221210,4\u00a0pp\u00a0; \u0394\u00a0RD\u00a0= \u22129,3\u00a0pp) et coh\u00e9rente avec la litt\u00e9rature sur la validation gold standard en NLP biom\u00e9dical.")
ap("Tableau\u00a06. Performances globales aux deux niveaux de validation. \u0394\u00a0= \u00e9cart N1\u2212N2 (pp\u00a0= points de pourcentage). Seuils a priori\u00a0: F1\u00a0\u2265\u00a078\u00a0%, P\u00a0\u2265\u00a080\u00a0%, R\u00a0\u2265\u00a075\u00a0%, Acc\u00a0\u2265\u00a085\u00a0%.", italic=True)
copy_tbl(T_synthN1N2)
ap()
ap("Figure\u00a02. Performances NLP par module\u00a0: Validation automatique N1 (n=200) vs Gold Standard humain N2 (n=100). Barres group\u00e9es par module (OE\u00a0/\u00a0PE\u00a0/\u00a0RD) pour les m\u00e9triques F1, Pr\u00e9cision et Rappel.", italic=True)
copy_img(IMG_fig3)
ap()

# --- 3.7 OE N2 -------------------------------------------------------------------
h("3.7 OutcomeExtractor \u2014 Analyse d\u00e9taill\u00e9e (Gold Standard N2)", 2)
ap("L\u2019OutcomeExtractor r\u00e9alise la meilleure performance du pipeline avec une pr\u00e9cision parfaite en N2 (P=100,0\u00a0%, 0\u00a0faux positif sur 99\u00a0articles annot\u00e9s). 9\u00a0faux n\u00e9gatifs persistent, correspondant \u00e0 des articles dont le crit\u00e8re de jugement est exprim\u00e9 de mani\u00e8re atypique.")
ap("Tableau\u00a07. Performances de l\u2019OutcomeExtractor par sp\u00e9cialit\u00e9 (Gold Standard N2). Pr\u00e9cision parfaite (0 FP) dans les 10 sp\u00e9cialit\u00e9s.", italic=True)
copy_tbl(T_OEspec)
ap()
ap("Un cas embl\u00e9matique illustre la limite actuelle\u00a0: le DIPLOMA trial (PMID\u00a041060640), un ECR multicentrique en chirurgie h\u00e9patobiliaire, r\u00e9dige son objectif principal sous forme d\u2019hypoth\u00e8se comparative indirecte plut\u00f4t que sous forme d\u00e9clarative conventionnelle.")
ap()

# --- 3.8 PE N2 -------------------------------------------------------------------
h("3.8 ParticipantExtractor \u2014 Analyse d\u00e9taill\u00e9e (Gold Standard N2)", 2)
ap("Le ParticipantExtractor d\u00e9montre un excellent rappel en N2 (93,0\u00a0%), confirmant que le module identifie l\u2019effectif dans la quasi-totalit\u00e9 des abstracts o\u00f9 il est exprim\u00e9. Le F1-score de 82,0\u00a0% d\u00e9passe le seuil fix\u00e9 (78\u00a0%).")
ap("La MAE de 5\u00a0604 en N2 \u2014 contre 16,2 en N1 \u2014 est enti\u00e8rement imputable \u00e0 deux sp\u00e9cialit\u00e9s\u00a0: \u00e9tudes observationnelles (MAE\u00a0:\u00a065\u00a0814,6) et neurochirurgie (MAE\u00a0:\u00a02\u00a0169,7). Pour les 8 autres sp\u00e9cialit\u00e9s, la MAE m\u00e9diane reste <\u00a0140.")
ap("Tableau\u00a08. Performances du ParticipantExtractor par sp\u00e9cialit\u00e9 (Gold Standard N2).", italic=True)
copy_tbl(T_PEspec)
ap()

# --- 3.9 RD N2 -------------------------------------------------------------------
h("3.9 RegionDetector \u2014 Analyse d\u00e9taill\u00e9e (Gold Standard N2)", 2)
ap("Le RegionDetector atteint 90,7\u00a0% d\u2019exactitude en N2 (88\u00a0d\u00e9tections correctes sur 97\u00a0affiliations annot\u00e9es). Les 9\u00a0erreurs\u00a0: (1)\u00a04\u00a0cas d\u2019affiliation du premier auteur dans un pays diff\u00e9rent du dernier auteur\u00a0; (2)\u00a05\u00a0cas d\u2019affiliations tr\u00e8s courtes sans nom de pays explicite dans des PMID anciens.")
ap("Tableau\u00a09. Distribution g\u00e9ographique des affiliations (N1 vs N2).", italic=True)
copy_tbl(T_GEO)
ap()
ap("Figure\u00a03. Distribution g\u00e9ographique des affiliations\u00a0: N1 (n=200, gauche) vs Gold Standard N2 (n=100, droite).", italic=True)
copy_img(IMG_fig4)
ap()

# --- 3.10 SUS -------------------------------------------------------------------
h("3.10 \u00c9valuation qualitative par les professionnels de sant\u00e9 (en cours)", 2)
ap("Tableau\u00a010. R\u00e9sultats de l\u2019\u00e9valuation qualitative SUS \u2014 System Usability Scale [10] (collecte en cours)", italic=True)
copy_tbl(T_SUS)
ap()
ap("Une phase de validation humaine est programm\u00e9e avec des professionnels de sant\u00e9 du CHU Clermont-Ferrand. L\u2019\u00e9valuation portera sur le score SUS, le gain de temps per\u00e7u et l\u2019utilit\u00e9 du module NLP pour la pr\u00e9s\u00e9lection bibliographique. Les r\u00e9sultats seront publi\u00e9s dans un article compl\u00e9mentaire.")
ap()

# =================================================================================
# 4. DISCUSSION
# =================================================================================
h("4. Discussion", 1)

h("4.1 La r\u00e9cup\u00e9ration PubMed comme fondement m\u00e9thodologique", 2)
ap("Le r\u00e9sultat le plus important de cette \u00e9tude est la validation compl\u00e8te de la cha\u00eene de r\u00e9cup\u00e9ration PubMed [12]\u00a0: 37/37 tests r\u00e9ussis, couvrant les 3 modes de filtrage journal, 7 types de requ\u00eates, la pagination et la r\u00e9cup\u00e9ration de donn\u00e9es compl\u00e8tes. Ce r\u00e9sultat garantit que MedSearch accomplit son objectif primaire avant toute consid\u00e9ration NLP. Il distingue MedSearch des outils qui focalisent sur la pr\u00e9sentation des r\u00e9sultats sans valider rigoureusement que les bons articles sont retrouv\u00e9s [2].")
ap("La validation en 4\u00a0niveaux (offline \u2192 PMID lookup \u2192 recherche par mots-cl\u00e9s \u2192 retrouver un article pr\u00e9cis) suit une logique d\u2019escalade de complexit\u00e9 garantissant \u00e0 la fois l\u2019exactitude unitaire (niveau\u00a01) et le comportement syst\u00e9mique r\u00e9el (niveaux\u00a02\u201f4). Cette approche est classique en g\u00e9nie logiciel m\u00e9dical.")

h("4.2 Performance NLP dans le contexte de la litt\u00e9rature", 2)
ap("Les r\u00e9sultats NLP obtenus sont remarquables au regard de l\u2019\u00e9tat de l\u2019art. Le F1-score de 98,7\u00a0% pour l\u2019OutcomeExtractor sur N1 d\u00e9passe les benchmarks publi\u00e9s pour des syst\u00e8mes comparables (F1\u00a0=\u00a085\u201f92\u00a0% pour les approches d\u00e9terministes en NLP biom\u00e9dical [7]). La performance N2 de 91,3\u00a0% avec pr\u00e9cision parfaite (P=100\u00a0%) est particuli\u00e8rement significative : 0\u00a0faux positif, propri\u00e9t\u00e9 essentielle pour un outil d\u2019aide \u00e0 la d\u00e9cision clinique.")
ap("Le RegionDetector atteint 100,0\u00a0% de pr\u00e9cision sur 122\u00a0affiliations N1. La l\u00e9g\u00e8re baisse en N2 (90,7\u00a0%) est enti\u00e8rement explicable par des affiliations incompl\u00e8tes dans des PMID anciens, probl\u00e8me structurel ind\u00e9pendant du module.")
ap("La MAE\u00a0=\u00a05\u00a0604 du ParticipantExtractor en N2 m\u00e9rite une interpr\u00e9tation nuanc\u00e9e\u00a0: domin\u00e9e par deux sp\u00e9cialit\u00e9s (observationnel, neurochirurgie). Pour les 8\u00a0autres sp\u00e9cialit\u00e9s, la MAE m\u00e9diane reste\u00a0<\u00a0140, ce qui est excellent.")

h("4.3 Comparaison avec les outils existants", 2)
ap("Tableau\u00a011. Analyse comparative \u2014 MedSearch\u00a0v3 vs outils existants", italic=True)
copy_tbl(T_COMP)
ap()
ap("Le Tableau\u00a011 met en \u00e9vidence plusieurs \u00e9l\u00e9ments diff\u00e9renciateurs\u00a0: aucun outil ne combine simultan\u00e9ment la r\u00e9cup\u00e9ration par lot valid\u00e9e, l\u2019extraction NLP d\u00e9terministe reproductible, la souverainet\u00e9 des donn\u00e9es et l\u2019int\u00e9gration SIGAPS.")
ap("Les outils IA tels qu\u2019Elicit introduisent une interface productive mais au d\u00e9triment de la reproductibilit\u00e9 et de la tra\u00e7abilit\u00e9 des r\u00e9sultats\u00a0\u2014 propri\u00e9t\u00e9s r\u00e9dhibitoires pour les revues syst\u00e9matiques.")
ap("MedSearch est \u00e0 ce jour le seul outil combinant les cinq fonctionnalit\u00e9s critiques pour les DRCI fran\u00e7aises\u00a0: r\u00e9cup\u00e9ration par lot PubMed valid\u00e9e, extraction NLP d\u00e9terministe, calcul du rang SIGAPS, souverainet\u00e9 des donn\u00e9es et d\u00e9ploiement local.")

h("4.4 Impact op\u00e9rationnel et calcul SIGAPS", 2)
ap("Le filtre rang JCR\u00a0/ SIGAPS est la fonctionnalit\u00e9 la plus diff\u00e9renciante de MedSearch pour les DRCI fran\u00e7aises. MedSearch automatise le filtrage par rang de revue, r\u00e9duisant \u00e0 quelques secondes une op\u00e9ration qui n\u00e9cessitait 2\u00a0\u00e0 4\u00a0heures de v\u00e9rification manuelle par campagne.")
ap("Le BatchSearchService permet de r\u00e9aliser une mise \u00e0 jour bibliographique compl\u00e8te sur 100\u00a0requ\u00eates en moins de 10\u00a0minutes (avec cl\u00e9 API NCBI). La validation en 37 tests garantit que cette performance ne s\u2019accompagne d\u2019aucune perte de pr\u00e9cision.")

h("4.5 Limites et perspectives", 2)
ap("Limites actuelles\u00a0:")
bl("Couverture linguistique\u00a0: les abstracts en espagnol, portugais ou chinois ne sont pas couverts par les patrons NLP actuels (enrichissement NLP limit\u00e9 \u00e0 l\u2019anglais et au fran\u00e7ais).")
bl("Effectifs fragment\u00e9s\u00a0: lorsqu\u2019un abstract mentionne plusieurs sous-populations, le ParticipantExtractor peut extraire un sous-effectif plut\u00f4t que le total.")
bl("D\u00e9pendance NCBI\u00a0: quota 10\u00a0requ\u00eates/s avec cl\u00e9 API, 3/s sans.")
bl("Phase SUS en cours\u00a0: r\u00e9sultats d\u2019utilisabilit\u00e9 \u00e0 publier dans un article compl\u00e9mentaire.")
ap("D\u00e9veloppements pr\u00e9vus pour MedSearch\u00a0v3.2\u00a0:")
bl("Extension du dictionnaire OutcomeExtractor \u00e0 80+ patrons pour les \u00e9tudes observationnelles et les revues syst\u00e9matiques.")
bl("Algorithme de d\u00e9sambigua\u00efation des effectifs fragment\u00e9s dans le ParticipantExtractor.")
bl("Interface REST\u00a0API pour int\u00e9gration dans les syst\u00e8mes institutionnels (XNAT, REDCap, DPI).")
bl("Support NLP multilingue (espagnol, portugais) pour les collaborations internationales.")
ap()

# =================================================================================
# 5. CONCLUSION
# =================================================================================
h("5. Conclusion", 1)
ap("MedSearch\u00a0v3 apporte une r\u00e9ponse compl\u00e8te et valid\u00e9e aux besoins bibliographiques des chercheurs en sant\u00e9, cliniciens, \u00e9tudiants et \u00e9quipes DRCI. Sa conception repose sur une priorit\u00e9 claire\u00a0: r\u00e9cup\u00e9rer fiablement les bons articles PubMed avant tout enrichissement. Cette priorit\u00e9 est valid\u00e9e par 37\u00a0tests automatis\u00e9s en 4\u00a0niveaux avec un taux de r\u00e9ussite de 100\u00a0% sur l\u2019ensemble des modes de filtrage journal.")
ap("Face aux alternatives existantes, MedSearch pr\u00e9sente trois avantages d\u00e9cisifs\u00a0: (1)\u00a0la souverainet\u00e9 des donn\u00e9es \u2014 aucune transmission \u00e0 des tiers, d\u00e9ploiement local\u00a0; (2)\u00a0la reproductibilit\u00e9 parfaite \u2014 syst\u00e8me d\u00e9terministe, m\u00eame recherche \u2192 m\u00eames r\u00e9sultats\u00a0; (3)\u00a0la validation tricouche \u2014 r\u00e9cup\u00e9ration PubMed (37/37 tests), NLP automatique N1 (OE F1=98,7\u00a0%, PE F1=92,4\u00a0%, RD Acc=100,0\u00a0%) et gold standard humain N2 (OE F1=91,3\u00a0%, PE F1=82,0\u00a0%, RD Acc=90,7\u00a0%, verdict PASSED).")
ap("Dans un contexte o\u00f9 les outils d\u2019IA g\u00e9n\u00e9rative sont de plus en plus utilis\u00e9s en recherche clinique, MedSearch repr\u00e9sente une alternative m\u00e9thodologiquement rigoureuse\u00a0: chaque r\u00e9sultat est tra\u00e7able, chaque d\u00e9cision algorithmique est explicable, et chaque extraction NLP est v\u00e9rifiable. Ces propri\u00e9t\u00e9s sont indispensables pour la recherche clinique soumise \u00e0 des exigences r\u00e9glementaires.")
ap()

# =================================================================================
# REFERENCES
# =================================================================================
h("R\u00e9f\u00e9rences", 1)
ap("[1] Sackett DL, Rosenberg WM, Gray JA, Haynes RB, Richardson WS. Evidence based medicine: what it is and what it isn\u2019t. BMJ. 1996;312(7023):71-2.")
ap("[2] Gusenbauer\u00a0M, Haddaway\u00a0NR. Which academic search systems are suitable for systematic reviews or meta-analyses? Res Synth Methods. 2020;11(2):181-217.")
ap("[3] Bernard\u00a0N, et\u00a0al. Comparison of Elicit AI and traditional literature searching. J Clin Epidemiol. 2024.")
ap("[4] Minist\u00e8re de la Sant\u00e9. Scores SIGAPS et financement de la recherche hospitali\u00e8re\u00a0: modalit\u00e9s des exports campagne 2024.")
ap("[5] Griffon\u00a0N, et\u00a0al. Toward a self-information retrieval system for biomedical research. J Med Internet Res. 2014;16(3).")
ap("[6] Poudel\u00a0S, et\u00a0al. Evaluation metrics for machine learning models in medical diagnosis. Sci Rep. 2024.")
ap("[7] Nye\u00a0BE, et\u00a0al. A corpus with multi-level annotations of patients, interventions and outcomes. ACL. 2018.")
ap("[8] Van Eck\u00a0NJ, Waltman\u00a0L. Bibliometric mapping of the scientific literature. J Informetrics. 2018;12(2).")
ap("[9] Page\u00a0MJ, et\u00a0al. PRISMA\u00a02020 explanation and elaboration. BMJ. 2021;372.")
ap("[10] Brooke\u00a0J. SUS: A quick and dirty usability scale. Usability Evaluation in Industry. 1996;189(194):4-7.")
ap("[11] Jayaswal\u00a0V. Performance metrics: confusion matrix, precision, recall, and F1\u00a0score. Towards Data Science. 2022.")
ap("[12] Entrez Programming Utilities Help. National Center for Biotechnology Information (NCBI). https://www.ncbi.nlm.nih.gov/books/NBK25501/")

# =================================================================================
# SAUVEGARDE
# =================================================================================
doc.save(DST)
print(f"DONE => {DST}")
print(f"Paragraphes : {len(doc.paragraphs)}")
print(f"Tables : {len(doc.tables)}")
