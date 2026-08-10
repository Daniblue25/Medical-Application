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
        # Columns: PMID / Title / Link / Year / Journal / Language / Sample Size / Primary Outcome / Center Type / Keywords / First Author Country / Last Author Country / Region
        headers = ['PMID', 'Title', 'Link', 'Publication Year', 'Language', 'Journal', 'Sample Size', 'Primary Outcome', 'Center Type', 'Keywords', 'First Author Country', 'Last Author Country', 'Region']
        ws.append(headers)
        for a in articles:
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
                language,                      # Language
                participants,                  # Sample size
                cjp,                          # Primary outcome (CJP)
                'Multicenter' if a.get('is_multicenter') is True else ('Monocenter' if a.get('is_multicenter') is False else ''),  # Center Type
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
            <b>Study Type:</b> {a.get('study_type','N/A')}
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


@api_view(['POST'])
def export_ris(request):
    """
    Export search results in RIS format (.ris) for import into
    Zotero, Mendeley, EndNote, and other reference managers.
    """
    articles = request.data.get('articles', [])
    if not articles:
        return Response({'error': 'No data to export'}, status=400)

    lines = []
    for a in articles:
        lines.append('TY  - JOUR')

        title = (a.get('title') or '').strip()
        if title:
            lines.append(f'TI  - {title}')

        # Authors — PubMed returns a comma-separated string
        authors_raw = (a.get('authors') or '').strip()
        if authors_raw:
            for author in authors_raw.split(','):
                author = author.strip()
                if author:
                    lines.append(f'AU  - {author}')

        journal = (a.get('journal') or '').strip()
        if journal:
            lines.append(f'JO  - {journal}')
            lines.append(f'T2  - {journal}')

        year = str(a.get('year') or '').strip()
        if year:
            lines.append(f'PY  - {year}')

        abstract = (a.get('abstract') or '').strip()
        if abstract:
            lines.append(f'AB  - {abstract}')

        keywords = a.get('keywords')
        if keywords:
            kw_list = keywords if isinstance(keywords, list) else [keywords]
            for kw in kw_list:
                kw = str(kw).strip()
                if kw:
                    lines.append(f'KW  - {kw}')

        doi = (a.get('doi') or '').strip()
        if doi:
            lines.append(f'DO  - {doi}')

        pmid = (str(a.get('pmid') or '')).strip()
        if pmid:
            lines.append(f'UR  - https://pubmed.ncbi.nlm.nih.gov/{pmid}/')
            lines.append(f'AN  - {pmid}')

        language = (a.get('language') or '').strip()
        if language:
            lines.append(f'LA  - {language}')

        lines.append('ER  - ')
        lines.append('')  # blank line between records

    content = '\r\n'.join(lines)
    resp = HttpResponse(content, content_type='application/x-research-info-systems; charset=utf-8')
    resp['Content-Disposition'] = f"attachment; filename=medical_search_{datetime.now().strftime('%Y%m%d_%H%M%S')}.ris"
    return resp
