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

@csrf_exempt
@api_view(['POST'])
def export_excel(request):
    articles = request.data.get('articles', [])
    if not articles:
        return Response({'error': 'No data to export'}, status=400)
    wb = Workbook()
    ws = wb.active
    if ws:
        ws.title = 'Search Results'
        headers = ['PMID', 'Title', 'Authors', 'Journal', 'Year', 'Study Type', 'Quality']
        ws.append(headers)
        for a in articles:
            ws.append([
                a.get('pmid', ''), a.get('title', ''), a.get('authors', ''), a.get('journal', ''),
                a.get('year', ''), a.get('study_type', ''), a.get('quality', '')
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
