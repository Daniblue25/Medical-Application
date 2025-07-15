from flask import Blueprint, render_template, request, flash
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import time
from app.utils import extract_primary_outcome, extract_sample_size, summarize_abstract

pubmed = Blueprint("pubmed", __name__)

@pubmed.route('/search', methods=['GET', 'POST'])
def search():
    results = []
    if request.method == 'POST':
        query = request.form.get('query')
        try:
            results = fetch_pubmed_articles(query)
        except Exception as e:
            flash(f"Erreur lors de la recherche PubMed: {e}", 'danger')
    return render_template('search.html', results=results)


def fetch_pubmed_articles(query, retmax=500):
    current_year = str(datetime.now().year)
    params = {
        'db': 'pubmed',
        'term': query,
        'retmax': retmax,
        'mindate': '1975',
        'maxdate': current_year,
        'retmode': 'xml'
    }
    url_esearch = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
    res = requests.get(url_esearch, params=params)
    root = ET.fromstring(res.content)
    id_list = [id_elem.text for id_elem in root.findall('.//Id')]
    if not id_list:
        return []

    time.sleep(0.3)
    url_efetch = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'
    efetch_params = {
        'db': 'pubmed',
        'id': ','.join(id_list),
        'retmode': 'xml'
    }
    res2 = requests.get(url_efetch, params=efetch_params)
    root2 = ET.fromstring(res2.content)

    results = []
    for article in root2.findall('.//PubmedArticle'):
        art = article.find('.//Article')
        journal = art.find('.//JournalIssue/PubDate/Year')
        year = journal.text if journal is not None else 'n.d.'
        title_elem = art.find('ArticleTitle')
        title = title_elem.text if title_elem is not None else ''
        abstract_elem = art.find('.//AbstractText')
        abstract_text = abstract_elem.text if abstract_elem is not None else ''
        primary = extract_primary_outcome(abstract_text)
        sample = extract_sample_size(abstract_text)
        summary = summarize_abstract(abstract_text)
        typ = article.find('.//PublicationType')
        study_type = typ.text if typ is not None else ''

        results.append({
            'title': title,
            'year': year,
            'type': study_type,
            'outcome': primary,
            'sample': sample,
            'summary': summary,
            'abstract': abstract_text
        })
    return results