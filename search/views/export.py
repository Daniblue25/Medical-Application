from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import HttpResponse
import os
import tempfile
from openpyxl import Workbook
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from datetime import datetime


def get_journal_ranking(journal_name):
    """Classifie une revue médicale selon les standards A+, A, B"""
    if not journal_name:
        return 'B'
        
    aplus_journals = [
        'New England Journal of Medicine', 'The Lancet', 'Journal of the American Medical Association',
        'Nature Medicine', 'Cell', 'Science', 'Nature', 'The BMJ', 'Annals of Internal Medicine',
        'JAMA Internal Medicine', 'Circulation', 'Nature Genetics', 'The Lancet Oncology',
        'Journal of Clinical Investigation', 'Nature Immunology', 'Blood', 'Gastroenterology',
        'Journal of Clinical Oncology', 'The Lancet Neurology', 'Nature Cell Biology'
    ]
    
    # Revues de rang A : inclut les 13 revues chirurgicales + autres revues médicales de qualité
    a_journals = [
        # 13 revues chirurgicales ciblées (rang A)
        'JAMA Surgery',
        'British Journal of Surgery',
        'Annals of Surgery',
        'International Journal of Surgery',
        'Digestive Endoscopy',
        'Liver Transplantation',
        'Journal of the American College of Surgeons',
        'American Journal of Transplantation',
        'Endoscopy',
        'Hepatobiliary Surgery and Nutrition',
        # Autres revues médicales de rang A
        'American Journal of Medicine', 'PLOS Medicine', 'European Heart Journal',
        'Journal of the American College of Cardiology', 'Diabetes Care', 'Hepatology',
        'Archives of Internal Medicine', 'Clinical Infectious Diseases', 'Kidney International',
        'Journal of Hepatology', 'American Journal of Respiratory and Critical Care Medicine',
        'Arthritis & Rheumatism', 'Journal of Allergy and Clinical Immunology',
        'American Journal of Psychiatry', 'Journal of Clinical Endocrinology & Metabolism',
        'Hypertension', 'Journal of Immunology', 'Cancer Research', 
        'Proceedings of the National Academy of Sciences', 'European Journal of Heart Failure', 
        'Thorax', 'Gut', 'Brain', 'Journal of Neuroscience'
    ]
    
    normalized_journal = journal_name.lower().strip()
    
    # Vérifier A+
    for journal in aplus_journals:
        if normalized_journal in journal.lower() or journal.lower() in normalized_journal:
            return 'A+'
    
    # Vérifier A
    for journal in a_journals:
        if normalized_journal in journal.lower() or journal.lower() in normalized_journal:
            return 'A'
    
    return 'B'

@api_view(['POST'])
def export_excel(request):
    from search.services.region_detector import get_region_name, get_country_name
    
    articles = request.data.get('articles', [])
    if not articles:
        return Response({'error': 'No data to export'}, status=400)
    wb = Workbook()
    ws = wb.active
    if ws:
        ws.title = 'Search Results'
        # Columns: PMID / Title / Link / Year / Journal / Rank / Language / Sample Size / Primary Outcome / Keywords / First Author Country / Last Author Country / Region
        headers = ['PMID', 'Titre article', 'Lien', 'Année publication', 'Journal', 'Rang', 'Langue', 'Nb de sujet', 'CJP', 'Keywords', 'First Author Country', 'Last Author Country', 'Region']
        ws.append(headers)
        for a in articles:
            # Journal classification (A+, A, B): respect chosen rank if provided
            quality = a.get('journal_rank') or get_journal_ranking(a.get('journal', ''))
            
            # Number of participants (without confidence in export)
            participants = str(a.get('sample_size', '')) if a.get('sample_size') else ''
            
            # PubMed link
            pmid = a.get('pmid', '')
            link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ''
            
            # Primary outcome (CJP)
            cjp = a.get('primary_outcome', '')
            
            # Keywords — use only `keywords`; if absent, leave empty
            keywords = a.get('keywords')
            if keywords:
                if isinstance(keywords, list):
                    keywords_str = '; '.join(keywords)
                else:
                    keywords_str = str(keywords)
            else:
                keywords_str = ''
            
            # First Author Country (from first_author_affiliation or first_author_country)
            first_author_country = a.get('first_author_country', '')
            if not first_author_country:
                first_affiliation = a.get('first_author_affiliation', '')
                first_author_country = get_country_name(first_affiliation) if first_affiliation else ''
            else:
                # Convert country code to display name
                first_author_country = first_author_country.title() if first_author_country else ''
            first_author_country = first_author_country if first_author_country else 'Unknown'
            
            # Last Author Country (from last_author_country or last_author_affiliation or affiliation)
            last_author_country = a.get('last_author_country', '')
            if not last_author_country:
                last_affiliation = a.get('last_author_affiliation', '') or a.get('affiliation', '')
                last_author_country = get_country_name(last_affiliation) if last_affiliation else ''
            else:
                # Convert country code to display name
                last_author_country = last_author_country.title() if last_author_country else ''
            last_author_country = last_author_country if last_author_country else 'Unknown'
            
            # Region (convert code to readable name)
            region_code = a.get('region', '')
            region_name = get_region_name(region_code) if region_code else 'Unknown'
            
            # Language display name
            lang_code = (a.get('language', '') or '').lower()
            lang_names = {
                'eng': 'English', 'fre': 'French', 'ger': 'German', 'spa': 'Spanish',
                'ita': 'Italian', 'por': 'Portuguese', 'chi': 'Chinese', 'jpn': 'Japanese',
                'kor': 'Korean', 'rus': 'Russian', 'ara': 'Arabic', 'tur': 'Turkish',
                'pol': 'Polish', 'dut': 'Dutch', 'dan': 'Danish', 'swe': 'Swedish',
                'nor': 'Norwegian', 'fin': 'Finnish', 'cze': 'Czech', 'hun': 'Hungarian',
                'rum': 'Romanian', 'gre': 'Greek', 'heb': 'Hebrew', 'per': 'Persian',
                'tha': 'Thai', 'ukr': 'Ukrainian',
            }
            language = lang_names.get(lang_code, lang_code.upper() if lang_code else '')
            
            ws.append([
                pmid,                          # PMID
                a.get('title', ''),           # Article title
                link,                          # Link
                a.get('year', ''),            # Publication year
                a.get('journal', ''),         # Journal
                quality,                       # Rank (A+, A, B)
                language,                      # Language
                participants,                  # Sample size
                cjp,                          # Primary outcome (CJP)
                keywords_str,                  # Keywords
                first_author_country,          # First Author Country
                last_author_country,           # Last Author Country
                region_name                    # Region
            ])
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            tmp_path = tmp.name
            wb.save(tmp_path)
        with open(tmp_path, 'rb') as f:
            data = f.read()
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
    resp = HttpResponse(data, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = f"attachment; filename=medical_search_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return resp

@api_view(['POST'])
def export_pdf(request):
    articles = request.data.get('articles', [])
    if not articles:
        return Response({'error': 'No data to export'}, status=400)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            tmp_path = tmp.name
        doc = SimpleDocTemplate(tmp_path, pagesize=A4)
        styles = getSampleStyleSheet()
        custom_title = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, spaceAfter=20)
        elements = [Paragraph('Medical Search Results', custom_title), Spacer(1, 12)]
        for i, a in enumerate(articles):
            elements.append(Paragraph(f"<b>{i+1}. {a.get('title','Untitled')}</b>", styles['Heading2']))
            meta = f"""
            <b>Authors:</b> {a.get('authors','N/A')}<br/>
            <b>Journal:</b> {a.get('journal','N/A')} ({a.get('year','')})<br/>
            <b>Study Type:</b> {a.get('study_type','N/A')}<br/>
            <b>Quality:</b> {a.get('quality','N/A')}
            """
            elements.append(Paragraph(meta, styles['Normal']))
            elements.append(Spacer(1, 10))
        doc.build(elements)
        with open(tmp_path, 'rb') as f:
            pdf_data = f.read()
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
    resp = HttpResponse(pdf_data, content_type='application/pdf')
    resp['Content-Disposition'] = f"attachment; filename=medical_search_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return resp
