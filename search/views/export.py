from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
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
    
    a_journals = [
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

@csrf_exempt
@api_view(['POST'])
def export_excel(request):
    from search.services.region_detector import get_region_name
    
    articles = request.data.get('articles', [])
    if not articles:
        return Response({'error': 'No data to export'}, status=400)
    wb = Workbook()
    ws = wb.active
    if ws:
        ws.title = 'Search Results'
        # Nouvelles colonnes : Titre / Lien / Année / Journal / Rang / Nb sujet / CJP / Region
        headers = ['Titre article', 'Lien', 'Année publication', 'Journal', 'Rang', 'Nb de sujet', 'CJP', 'Region ou pays']
        ws.append(headers)
        for a in articles:
            # Classification de la revue (A+, A, B)
            quality = get_journal_ranking(a.get('journal', ''))
            
            # Nombre de participants (sans la confiance dans l'export)
            participants = str(a.get('sample_size', '')) if a.get('sample_size') else ''
            
            # Lien PubMed
            pmid = a.get('pmid', '')
            link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ''
            
            # Critère de Jugement Principal
            cjp = a.get('primary_outcome', '')
            
            # Région (convertir le code en nom lisible)
            region_code = a.get('region', '')
            region_name = get_region_name(region_code) if region_code else ''
            
            ws.append([
                a.get('title', ''),           # Titre article
                link,                          # Lien
                a.get('year', ''),            # Année publication
                a.get('journal', ''),         # Journal
                quality,                       # Rang (A+, A, B)
                participants,                  # Nb de sujet
                cjp,                          # CJP (Critère de Jugement Principal)
                region_name                    # Region ou pays
            ])
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
        wb.save(tmp.name)
        tmp.seek(0)
        data = tmp.read()
    resp = HttpResponse(data, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = f"attachment; filename=medical_search_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return resp

@csrf_exempt
@api_view(['POST'])
def export_pdf(request):
    articles = request.data.get('articles', [])
    if not articles:
        return Response({'error': 'No data to export'}, status=400)
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        doc = SimpleDocTemplate(tmp.name, pagesize=A4)
        styles = getSampleStyleSheet()
        custom_title = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, spaceAfter=20)
        elements = [Paragraph('Medical Search Results', custom_title), Spacer(1, 12)]
        for i, a in enumerate(articles[:25]):
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
        tmp.seek(0)
        pdf_data = tmp.read()
    resp = HttpResponse(pdf_data, content_type='application/pdf')
    resp['Content-Disposition'] = f"attachment; filename=medical_search_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return resp
