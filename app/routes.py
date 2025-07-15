from flask import Blueprint, render_template, request, jsonify, send_file, current_app
import requests
import xml.etree.ElementTree as ET
import csv
import io
import json
import re
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
from .utils import generate_summary, extract_keywords, extract_primary_outcome, extract_sample_size, determine_study_type

main = Blueprint('main', __name__)

@main.route('/')
def index():
    # Pass domain and study type lists to the template
    domains = [
        {'value': 'cardiology', 'label': 'Cardiologie'},
        {'value': 'neurology', 'label': 'Neurologie'},
        {'value': 'oncology', 'label': 'Oncologie'},
        {'value': 'endocrinology', 'label': 'Endocrinologie'},
        {'value': 'immunology', 'label': 'Immunologie'},
        {'value': 'gastroenterology', 'label': 'Gastroentérologie'},
        {'value': 'pulmonology', 'label': 'Pneumologie'},
        {'value': 'rheumatology', 'label': 'Rhumatologie'},
        {'value': 'psychiatry', 'label': 'Psychiatrie'},
        {'value': 'dermatology', 'label': 'Dermatologie'},
        {'value': 'ophthalmology', 'label': 'Ophtalmologie'},
        {'value': 'pediatrics', 'label': 'Pédiatrie'},
        {'value': 'geriatrics', 'label': 'Gériatrie'},
        {'value': 'emergency', 'label': 'Médecine d\'urgence'},
        {'value': 'radiology', 'label': 'Radiologie'},
        {'value': 'pathology', 'label': 'Pathologie'},
        {'value': 'pharmacology', 'label': 'Pharmacologie'},
        {'value': 'epidemiology', 'label': 'Épidémiologie'},
        {'value': 'public_health', 'label': 'Santé publique'},
        {'value': 'genetics', 'label': 'Génétique'},
        {'value': 'infectious_diseases', 'label': 'Maladies infectieuses'},
        {'value': 'nutrition', 'label': 'Nutrition'},
        {'value': 'rehabilitation', 'label': 'Réhabilitation'},
        {'value': 'anesthesiology', 'label': 'Anesthésiologie'},
        {'value': 'surgery', 'label': 'Chirurgie'}
    ]
    study_types = [
        {'value': 'randomized_controlled_trial', 'label': 'Essai contrôlé randomisé'},
        {'value': 'cohort_study', 'label': 'Étude de cohorte'},
        {'value': 'case_control_study', 'label': 'Étude cas-témoins'},
        {'value': 'cross_sectional_study', 'label': 'Étude transversale'},
        {'value': 'systematic_review', 'label': 'Revue systématique'},
        {'value': 'meta_analysis', 'label': 'Méta-analyse'},
        {'value': 'case_report', 'label': 'Rapport de cas'},
        {'value': 'case_series', 'label': 'Série de cas'},
        {'value': 'clinical_trial', 'label': 'Essai clinique'},
        {'value': 'observational_study', 'label': 'Étude observationnelle'},
        {'value': 'longitudinal_study', 'label': 'Étude longitudinale'},
        {'value': 'prospective_study', 'label': 'Étude prospective'},
        {'value': 'retrospective_study', 'label': 'Étude rétrospective'},
        {'value': 'experimental_study', 'label': 'Étude expérimentale'},
        {'value': 'descriptive_study', 'label': 'Étude descriptive'}
    ]
    return render_template('search.html', domains=domains, study_types=study_types)

@main.route('/results', methods=['GET'])
def results_page():
    # Récupérer les paramètres de recherche
    keywords = request.args.get('keywords', '').strip()
    domain = request.args.get('domain', '')
    study_type = request.args.get('studyType', '')
    period = int(request.args.get('period', 10))
    max_results = int(request.args.get('maxResults', 100))

    # Calculer start et end year
    end_year = datetime.now().year
    start_year = end_year - period

    # Construire la requête PubMed
    query = build_pubmed_query(keywords, domain, study_type, start_year, end_year)
    # Récupérer les données
    articles = fetch_pubmed_data(query, max_results)

    # Traiter chaque article : résumé et mots-clés
    processed = []
    for art in articles:
        summary = generate_summary(art.get('abstract', ''))
        tags = extract_keywords(art.get('abstract', ''), num_keywords=5)
        # Lien PubMed
        pmid = art.get('pmid')
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else art.get('url', '#')
        processed.append({
            'title': art.get('title'),
            'authors': art.get('authors'),
            'journal': art.get('journal'),
            'year': art.get('year'),
            'summary': summary,
            'keywords': tags,
            'url': url
        })

    return render_template('analysis.html', articles=processed, keywords=keywords, domain=domain, period=period)

@main.route('/search', methods=['POST'])
def search():
    try:
        data = request.get_json()
        
        # Extract search parameters
        keywords = data.get('keywords', '').strip()
        domain = data.get('domain', '')
        study_type = data.get('studyType', '')
        start_year = data.get('startYear', '')
        end_year = data.get('endYear', '')
        max_results = int(data.get('maxResults', 100))
        
        # Validate required parameters
        if not keywords:
            return jsonify({'error': 'Mots-clés requis'}), 400
        
        # Build PubMed query
        query = build_pubmed_query(keywords, domain, study_type, start_year, end_year)
        
        print(f"Requête construite: {query}")
        
        # Fetch results from PubMed
        results = fetch_pubmed_data(query, max_results)
        print(f"Nombre de résultats trouvés: {len(results)}")
        
        return jsonify({
            'success': True,
            'articles': results,
            'total': len(results),
            'query': query
        })
    except Exception as e:
        print(f"Erreur dans /search: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@main.route('/export/<format>', methods=['POST'])
def export_results(format):
    try:
        data = request.get_json()
        
        # Get search parameters to re-run search
        keywords = data.get('keywords', '').strip()
        domain = data.get('domain', '')
        study_type = data.get('studyType', '')
        start_year = data.get('startYear', '')
        end_year = data.get('endYear', '')
        max_results = int(data.get('maxResults', 100))
        
        # Build query and fetch results
        query = build_pubmed_query(keywords, domain, study_type, start_year, end_year)
        results = fetch_pubmed_data(query, max_results)
        
        if not results:
            return jsonify({'error': 'Aucun résultat à exporter'}), 400
        
        if format == 'csv':
            return export_csv(results, query)
        elif format == 'pdf':
            return export_pdf(results, query)
        else:
            return jsonify({'error': 'Format non supporté'}), 400
    except Exception as e:
        print(f"Erreur dans export: {str(e)}")
        return jsonify({'error': str(e)}), 500

@main.route('/validate', methods=['POST'])
def validate_search():
    try:
        data = request.get_json()
        
        keywords = data.get('keywords', '').strip()
        domain = data.get('domain', '')
        study_type = data.get('studyType', '')
        start_year = data.get('startYear', '')
        end_year = data.get('endYear', '')
        
        messages = []
        valid = True
        
        # Validate keywords
        if not keywords:
            messages.append("Mots-clés requis")
            valid = False
        elif len(keywords) < 3:
            messages.append("Mots-clés trop courts (minimum 3 caractères)")
            valid = False
        
        # Validate year range
        if start_year and end_year:
            try:
                start_year_int = int(start_year)
                end_year_int = int(end_year)
                current_year = datetime.now().year
                
                if start_year_int > end_year_int:
                    messages.append("L'année de début doit être antérieure à l'année de fin")
                    valid = False
                
                if start_year_int < current_year - 50:
                    messages.append("L'année de début est trop ancienne (maximum 50 ans)")
                    valid = False
                
                if end_year_int > current_year:
                    messages.append("L'année de fin ne peut pas être dans le futur")
                    valid = False
                    
            except ValueError:
                messages.append("Format d'année invalide")
                valid = False
        
        # Add validation success message
        if valid:
            messages.append("Paramètres de recherche valides")
        
        return jsonify({
            'valid': valid,
            'messages': messages
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main.route('/domains', methods=['GET'])
def get_domains():
    """Return medical domains for the dropdown"""
    domains = [
        {'value': 'cardiology', 'label': 'Cardiologie'},
        {'value': 'neurology', 'label': 'Neurologie'},
        {'value': 'oncology', 'label': 'Oncologie'},
        {'value': 'endocrinology', 'label': 'Endocrinologie'},
        {'value': 'immunology', 'label': 'Immunologie'},
        {'value': 'gastroenterology', 'label': 'Gastroentérologie'},
        {'value': 'pulmonology', 'label': 'Pneumologie'},
        {'value': 'rheumatology', 'label': 'Rhumatologie'},
        {'value': 'psychiatry', 'label': 'Psychiatrie'},
        {'value': 'dermatology', 'label': 'Dermatologie'},
        {'value': 'ophthalmology', 'label': 'Ophtalmologie'},
        {'value': 'pediatrics', 'label': 'Pédiatrie'},
        {'value': 'geriatrics', 'label': 'Gériatrie'},
        {'value': 'emergency', 'label': 'Médecine d\'urgence'},
        {'value': 'radiology', 'label': 'Radiologie'},
        {'value': 'pathology', 'label': 'Pathologie'},
        {'value': 'pharmacology', 'label': 'Pharmacologie'},
        {'value': 'epidemiology', 'label': 'Épidémiologie'},
        {'value': 'public_health', 'label': 'Santé publique'},
        {'value': 'genetics', 'label': 'Génétique'},
        {'value': 'infectious_diseases', 'label': 'Maladies infectieuses'},
        {'value': 'nutrition', 'label': 'Nutrition'},
        {'value': 'rehabilitation', 'label': 'Réhabilitation'},
        {'value': 'anesthesiology', 'label': 'Anesthésiologie'},
        {'value': 'surgery', 'label': 'Chirurgie'}
    ]
    return jsonify(domains)

@main.route('/study-types', methods=['GET'])
def get_study_types():
    """Return study types for the dropdown"""
    study_types = [
        {'value': 'randomized_controlled_trial', 'label': 'Essai contrôlé randomisé'},
        {'value': 'cohort_study', 'label': 'Étude de cohorte'},
        {'value': 'case_control_study', 'label': 'Étude cas-témoins'},
        {'value': 'cross_sectional_study', 'label': 'Étude transversale'},
        {'value': 'systematic_review', 'label': 'Revue systématique'},
        {'value': 'meta_analysis', 'label': 'Méta-analyse'},
        {'value': 'case_report', 'label': 'Rapport de cas'},
        {'value': 'case_series', 'label': 'Série de cas'},
        {'value': 'clinical_trial', 'label': 'Essai clinique'},
        {'value': 'observational_study', 'label': 'Étude observationnelle'},
        {'value': 'longitudinal_study', 'label': 'Étude longitudinale'},
        {'value': 'prospective_study', 'label': 'Étude prospective'},
        {'value': 'retrospective_study', 'label': 'Étude rétrospective'},
        {'value': 'experimental_study', 'label': 'Étude expérimentale'},
        {'value': 'descriptive_study', 'label': 'Étude descriptive'}
    ]
    return jsonify(study_types)

@main.route('/suggestions', methods=['GET'])
def get_suggestions():
    """Return search suggestions based on query"""
    query = request.args.get('q', '').strip().lower()
    
    if len(query) < 2:
        return jsonify([])
    
    # Common medical terms and suggestions
    medical_terms = [
        'diabetes', 'hypertension', 'cancer', 'cardiology', 'neurology',
        'oncology', 'covid-19', 'immunology', 'pharmacology', 'genetics',
        'surgery', 'treatment', 'therapy', 'diagnosis', 'prognosis',
        'clinical trial', 'randomized controlled trial', 'meta-analysis',
        'systematic review', 'cohort study', 'case control', 'biomarker',
        'efficacy', 'safety', 'adverse events', 'mortality', 'morbidity',
        'inflammation', 'infection', 'antibiotic', 'antiviral', 'vaccine',
        'chemotherapy', 'radiotherapy', 'immunotherapy', 'precision medicine',
        'personalized medicine', 'genomics', 'proteomics', 'metabolomics'
    ]
    
    # Filter suggestions based on query
    suggestions = [term for term in medical_terms if query in term.lower()]
    
    # Limit to 10 suggestions
    return jsonify(suggestions[:10])

@main.route('/article/<pmid>', methods=['GET'])
def get_article_details(pmid):
    """Get detailed information about a specific article"""
    try:
        # This would typically fetch from a database or cache
        # For now, return a placeholder response
        return jsonify({
            'pmid': pmid,
            'title': 'Article details not implemented',
            'abstract': 'Full article details would be retrieved here',
            'authors': [],
            'journal': 'N/A',
            'year': None,
            'doi': None,
            'url': f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main.route('/test-pubmed')
def test_pubmed():
    """Test simple pour vérifier PubMed"""
    try:
        query = "diabetes AND cardiology[MeSH]"
        print(f"Test PubMed avec requête simple: {query}")
        articles = fetch_pubmed_data(query, 5)
        return f"<h1>Test PubMed</h1><p>Trouvé {len(articles)} articles</p><pre>{articles}</pre>"
    except Exception as e:
        return f"<h1>Erreur PubMed</h1><p>{str(e)}</p>"

def build_pubmed_query(keywords, domain, study_type, start_year, end_year):
    """Build a PubMed query string from search parameters"""
    query_parts = []
    
    # Add keywords
    if keywords:
        query_parts.append(keywords)
    
    # Add domain-specific terms
    domain_terms = {
        'cardiology': 'cardiology[MeSH] OR cardiovascular[MeSH] OR heart[MeSH]',
        'neurology': 'neurology[MeSH] OR brain[MeSH] OR nervous system[MeSH]',
        'oncology': 'oncology[MeSH] OR cancer[MeSH] OR tumor[MeSH] OR neoplasm[MeSH]',
        'endocrinology': 'endocrinology[MeSH] OR diabetes[MeSH] OR hormone[MeSH]',
        'immunology': 'immunology[MeSH] OR immune[MeSH] OR antibody[MeSH]',
        'gastroenterology': 'gastroenterology[MeSH] OR digestive[MeSH] OR gastrointestinal[MeSH]',
        'pulmonology': 'pulmonology[MeSH] OR respiratory[MeSH] OR lung[MeSH]',
        'rheumatology': 'rheumatology[MeSH] OR arthritis[MeSH] OR rheumatic[MeSH]',
        'psychiatry': 'psychiatry[MeSH] OR mental health[MeSH] OR psychiatric[MeSH]',
        'dermatology': 'dermatology[MeSH] OR skin[MeSH] OR dermatological[MeSH]',
        'ophthalmology': 'ophthalmology[MeSH] OR eye[MeSH] OR vision[MeSH]',
        'pediatrics': 'pediatrics[MeSH] OR child[MeSH] OR infant[MeSH]',
        'geriatrics': 'geriatrics[MeSH] OR aged[MeSH] OR elderly[MeSH]',
        'emergency': 'emergency medicine[MeSH] OR emergency[MeSH] OR trauma[MeSH]',
        'radiology': 'radiology[MeSH] OR imaging[MeSH] OR radiological[MeSH]',
        'pathology': 'pathology[MeSH] OR pathological[MeSH] OR disease[MeSH]',
        'pharmacology': 'pharmacology[MeSH] OR drug[MeSH] OR medication[MeSH]',
        'epidemiology': 'epidemiology[MeSH] OR population health[MeSH] OR public health[MeSH]',
        'public_health': 'public health[MeSH] OR population health[MeSH] OR epidemiology[MeSH]',
        'genetics': 'genetics[MeSH] OR genetic[MeSH] OR genomics[MeSH]',
        'infectious_diseases': 'infectious diseases[MeSH] OR infection[MeSH] OR microbiology[MeSH]',
        'nutrition': 'nutrition[MeSH] OR diet[MeSH] OR nutritional[MeSH]',
        'rehabilitation': 'rehabilitation[MeSH] OR physical therapy[MeSH] OR recovery[MeSH]',
        'anesthesiology': 'anesthesiology[MeSH] OR anesthesia[MeSH] OR anesthetic[MeSH]',
        'surgery': 'surgery[MeSH] OR surgical[MeSH] OR operative[MeSH]'
    }
    
    if domain and domain in domain_terms:
        query_parts.append(f'({domain_terms[domain]})')
    
    # Add study type filters
    study_type_terms = {
        'randomized_controlled_trial': 'randomized controlled trial[pt] OR randomized[tw]',
        'cohort_study': 'cohort study[tw] OR cohort[tw] OR prospective[tw]',
        'case_control_study': 'case control[tw] OR case-control[tw]',
        'cross_sectional_study': 'cross sectional[tw] OR cross-sectional[tw]',
        'systematic_review': 'systematic review[pt] OR systematic review[tw]',
        'meta_analysis': 'meta analysis[pt] OR meta-analysis[tw]',
        'case_report': 'case report[pt] OR case report[tw]',
        'case_series': 'case series[tw] OR case series[pt]',
        'clinical_trial': 'clinical trial[pt] OR clinical trial[tw]',
        'observational_study': 'observational study[tw] OR observational[tw]',
        'longitudinal_study': 'longitudinal study[tw] OR longitudinal[tw]',
        'prospective_study': 'prospective study[tw] OR prospective[tw]',
        'retrospective_study': 'retrospective study[tw] OR retrospective[tw]',
        'experimental_study': 'experimental study[tw] OR experimental[tw]',
        'descriptive_study': 'descriptive study[tw] OR descriptive[tw]'
    }
    
    if study_type and study_type in study_type_terms:
        query_parts.append(f'({study_type_terms[study_type]})')
    
    # Add date range
    if start_year and end_year:
        query_parts.append(f'("{start_year}"[Date - Publication] : "{end_year}"[Date - Publication])')
    elif start_year:
        query_parts.append(f'("{start_year}"[Date - Publication] : "3000"[Date - Publication])')
    elif end_year:
        query_parts.append(f'("1900"[Date - Publication] : "{end_year}"[Date - Publication])')
    
    # Join with AND
    return ' AND '.join(query_parts)

def fetch_pubmed_data(query, max_results=100):
    """Fetch data from PubMed with improved error handling and API key"""
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    search_url = f"{base_url}esearch.fcgi"
    fetch_url = f"{base_url}efetch.fcgi"
    
    try:
        # Limit max_results to prevent excessive API calls
        max_results = min(max_results, 200)
        
        # Search parameters
        search_params = {
            'db': 'pubmed',
            'term': query,
            'retmax': str(max_results),
            'retmode': 'json',
            'email': current_app.config.get('PUBMED_EMAIL'),
            'api_key': current_app.config.get('PUBMED_API_KEY')
        }
        
        print(f"Recherche PubMed avec la requête: {query}")
        print(f"Esearch URL: {response.request.url if (response := requests.PreparedRequest()) else 'n/a'}")
        
        # Search for IDs
        response = requests.get(search_url, params=search_params, timeout=30)
        print(f"Esearch paramètres: {search_params}")
        print(f"Esearch statut: {response.status_code}")
        response.raise_for_status()
        
        search_results = response.json()
        
        if 'esearchresult' not in search_results:
            print("Aucun résultat trouvé dans la réponse PubMed")
            return []
        
        id_list = search_results['esearchresult'].get('idlist', [])
        
        if not id_list:
            print("Aucun ID trouvé dans les résultats PubMed")
            return []
        
        print(f"Trouvé {len(id_list)} IDs d'articles")
        
        # Process articles in batches to avoid URL length limits
        results = []
        batch_size = 20  # Smaller batches for more stability
        
        for i in range(0, len(id_list), batch_size):
            batch_ids = id_list[i:i + batch_size]
            print(f"Traitement du lot {i//batch_size + 1}/{(len(id_list) + batch_size - 1)//batch_size} ({len(batch_ids)} articles)")
            
            try:
                # Fetch details for this batch
                fetch_params = {
                    'db': 'pubmed',
                    'id': ','.join(batch_ids),
                    'retmode': 'xml',
                    'email': current_app.config.get('PUBMED_EMAIL'),
                    'api_key': current_app.config.get('PUBMED_API_KEY')
                }
                
                print(f"Efetch paramètres lot: {fetch_params}")
                response = requests.get(fetch_url, params=fetch_params, timeout=30)
                print(f"Efetch statut: {response.status_code}")
                response.raise_for_status()
                
                if not response.content:
                    print(f"Réponse XML vide pour le lot {i//batch_size + 1}")
                    continue
                
                # Parse XML
                root = ET.fromstring(response.content)
                
                # Process articles from this batch
                batch_results = process_articles(root)
                results.extend(batch_results)
                
                print(f"Lot {i//batch_size + 1} traité: {len(batch_results)} articles ajoutés")
                
            except Exception as e:
                print(f"Erreur lors du traitement du lot {i//batch_size + 1}: {e}")
                continue
        
        print(f"Traitement terminé: {len(results)} articles au total")
        return results
    
    except requests.exceptions.RequestException as e:
        print(f"Erreur de requête PubMed: {e}")
        return []
    except ET.ParseError as e:
        print(f"Erreur de parsing XML: {e}")
        return []
    except Exception as e:
        print(f"Erreur inattendue dans fetch_pubmed_data: {e}")
        return []

def process_articles(root):
    """Process XML articles and return a list of dictionaries"""
    results = []
    for article in root.findall('.//PubmedArticle'):
        try:
            # Title
            title_elem = article.find('.//ArticleTitle')
            title = title_elem.text if title_elem is not None else 'Titre non disponible'
            
            # Abstract
            abstract_elem = article.find('.//Abstract/AbstractText')
            abstract = abstract_elem.text if abstract_elem is not None else ''
            
            # PMID
            pmid_elem = article.find('.//PMID')
            pmid = pmid_elem.text if pmid_elem is not None else ''
            
            # Publication date
            year_elem = article.find('.//PubDate/Year')
            year = int(year_elem.text) if year_elem is not None else None
            
            # Authors
            authors = []
            for author in article.findall('.//Author'):
                lastname = author.find('.//LastName')
                firstname = author.find('.//ForeName')
                if lastname is not None and firstname is not None:
                    authors.append(f"{lastname.text} {firstname.text}")
            
            # Journal
            journal_elem = article.find('.//Journal/Title')
            journal = journal_elem.text if journal_elem is not None else 'Journal non spécifié'
            
            # DOI
            doi_elem = article.find('.//ELocationID[@EIdType="doi"]')
            doi = doi_elem.text if doi_elem is not None else None
            
            # Advanced content analysis
            summary = generate_summary(abstract) if abstract else 'Résumé non disponible'
            keywords = extract_keywords(abstract) if abstract else []
            primary_outcome = extract_primary_outcome(abstract) if abstract else 'Non identifié'
            sample_size = extract_sample_size(abstract) if abstract else None
            
            # Safely combine title and abstract for study type analysis
            text_for_analysis = (title or '') + ' ' + (abstract or '')
            study_type = determine_study_type(text_for_analysis)
            
            # Build PubMed URL
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None
            
            # Generate mock citations for demonstration
            citations = len(authors) * 3 + (2023 - (year or 2023)) * 2
            
            results.append({
                'pmid': pmid,
                'title': title,
                'abstract': abstract,
                'summary': summary,
                'keywords': keywords,
                'primary_outcome': primary_outcome,
                'sample_size': sample_size,
                'study_type': study_type,
                'authors': authors,
                'journal': journal,
                'year': year,
                'doi': doi,
                'url': url,
                'citations': max(0, citations)  # Ensure non-negative
            })
        except Exception as e:
            print(f"Erreur lors du traitement de l'article: {e}")
            continue
            
    return results

def export_csv(results, query):
    """Exporter les résultats en CSV avec colonnes enrichies"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # En-têtes enrichies
    writer.writerow([
        'PMID', 'Titre', 'Auteurs', 'Journal', 'Année', 'DOI', 'URL PubMed',
        'Type d\'étude', 'Taille échantillon', 'Critères jugement principaux',
        'Résumé automatique', 'Mots-clés', 'Abstract complet'
    ])
    
    # Données
    for article in results:
        writer.writerow([
            article.get('pmid', ''),
            article.get('title', ''),
            '; '.join(article.get('authors', [])),
            article.get('journal', ''),
            article.get('year', ''),
            article.get('doi', ''),
            article.get('url', ''),
            article.get('study_type', ''),
            article.get('sample_size', ''),
            article.get('primary_outcome', ''),
            article.get('summary', ''),
            '; '.join(article.get('keywords', [])),
            article.get('abstract', '')
        ])
    
    # Créer la réponse
    output.seek(0)
    response = send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'DRCI_recherche_{datetime.now().strftime("%Y-%m-%d")}.csv'
    )
    return response

def export_pdf(results, query):
    """Exporter les résultats en PDF avec design professionnel"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=50, rightMargin=50, topMargin=50, bottomMargin=50)
    styles = getSampleStyleSheet()
    story = []
    
    # Styles personnalisés
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        textColor=colors.HexColor('#667eea'),
        alignment=1  # Centré
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=10,
        textColor=colors.HexColor('#666666')
    )
    
    article_title_style = ParagraphStyle(
        'ArticleTitle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=10,
        textColor=colors.HexColor('#333333')
    )
    
    # En-tête avec logo DRCI
    story.append(Paragraph("🧠 DRCI - Medical Research Analysis Platform", title_style))
    story.append(Paragraph("Direction de la Recherche Clinique et de l'Innovation", subtitle_style))
    story.append(Spacer(1, 20))
    
    # Tableau de synthèse
    summary_data = [
        ['Paramètre', 'Valeur'],
        ['Date de génération', datetime.now().strftime('%d/%m/%Y à %H:%M')],
        ['Requête de recherche', query],
        ['Nombre d\'articles analysés', str(len(results))],
        ['Période d\'analyse', 'Dernières publications']
    ]
    
    summary_table = Table(summary_data, colWidths=[3*inch, 3*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(summary_table)
    story.append(Spacer(1, 30))
    
    # Articles détaillés
    story.append(Paragraph("📋 Articles analysés", styles['Heading1']))
    story.append(Spacer(1, 20))
    
    for i, article in enumerate(results, 1):
        # Titre de l'article avec lien
        title_text = f"<b>{i}. {article.get('title', 'Titre non disponible')}</b>"
        story.append(Paragraph(title_text, article_title_style))
        
        # Informations de l'article
        info_data = [
            ['Auteurs', '; '.join(article.get('authors', ['Non spécifiés']))],
            ['Journal', article.get('journal', 'Non spécifié')],
            ['Année', str(article.get('year', 'Non spécifiée'))],
            ['Type d\'étude', article.get('study_type', 'Non déterminé')],
            ['Taille échantillon', str(article.get('sample_size', 'Non spécifiée'))],
            ['PMID', article.get('pmid', 'Non disponible')],
            ['DOI', article.get('doi', 'Non disponible')],
            ['URL PubMed', article.get('url', 'Non disponible')]
        ]
        
        info_table = Table(info_data, colWidths=[2*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP')
        ]))
        
        story.append(info_table)
        story.append(Spacer(1, 15))
        
        # Critères de jugement principal
        cjp_text = f"<b>🎯 Critères de jugement principaux:</b><br/>{article.get('primary_outcome', 'Non identifiés')}"
        story.append(Paragraph(cjp_text, styles['Normal']))
        story.append(Spacer(1, 10))
        
        # Résumé automatique
        summary_text = f"<b>📝 Résumé automatique:</b><br/>{article.get('summary', 'Résumé non disponible')}"
        story.append(Paragraph(summary_text, styles['Normal']))
        story.append(Spacer(1, 10))
        
        # Mots-clés
        keywords_text = f"<b>🔍 Mots-clés extraits:</b> {'; '.join(article.get('keywords', ['Aucun']))}"
        story.append(Paragraph(keywords_text, styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Saut de page tous les 2 articles
        if i % 2 == 0 and i < len(results):
            story.append(PageBreak())
    
    # Pied de page
    story.append(Spacer(1, 30))
    footer_text = f"Rapport généré automatiquement par DRCI Medical Research Analysis Platform - {datetime.now().strftime('%d/%m/%Y')}"
    story.append(Paragraph(footer_text, subtitle_style))
    
    # Construire le PDF
    doc.build(story)
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'DRCI_recherche_{datetime.now().strftime("%Y-%m-%d")}.pdf'
    )
