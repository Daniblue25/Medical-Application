"""
Medical Search Platform - PubMed Client Service
Copyright (c) 2025 DRCI - CHU Clermont-Ferrand
All rights reserved.

Author: FIANKO Kossi Jean-Jacques Daniel
License: MIT License (see LICENSE file)
"""

import os
import re
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging
from urllib.request import urlopen

import requests
from requests import Response
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from xml.etree import ElementTree
from .participant_extractor import ParticipantExtractor
from .outcome_extractor import OutcomeExtractor
from .region_detector import get_region_from_affiliation, get_country_code
from .multicenter_detector import detect_multicenter
from .journal_config import build_journal_filter, build_nursing_journal_filter

logger = logging.getLogger(__name__)


BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
USER_AGENT = "MedLitSearchApp/1.0 (contact: support@example.com)"
DEFAULT_TIMEOUT = 12
MAX_PUBMED_LIMIT = 100000  # Maximum articles accessible via PubMed E-utilities


def _normalize_proxy_url(proxy_value: Optional[str]) -> Optional[str]:
    if not proxy_value:
        return None

    normalized = proxy_value.strip()
    if not normalized:
        return None

    if "://" not in normalized:
        normalized = f"http://{normalized}"

    return normalized


def _sanitize_proxy_for_log(proxy_value: Optional[str]) -> str:
    if not proxy_value:
        return "<none>"

    return re.sub(r"(https?://)([^:@/]+):([^@/]+)@", r"\1***:***@", proxy_value, flags=re.IGNORECASE)


def _extract_proxy_from_pac(pac_content: str) -> Optional[str]:
    if not pac_content:
        return None

    matches = re.findall(r'PROXY\s+([^\s;"\']+)', pac_content, flags=re.IGNORECASE)
    if not matches:
        return None

    return _normalize_proxy_url(matches[-1])


def _parse_windows_proxy_server(proxy_server: str) -> Optional[str]:
    if not proxy_server:
        return None

    proxy_server = proxy_server.strip()
    if not proxy_server:
        return None

    if '=' not in proxy_server:
        return _normalize_proxy_url(proxy_server)

    proxy_entries = {}
    for chunk in proxy_server.split(';'):
        if '=' not in chunk:
            continue
        scheme, value = chunk.split('=', 1)
        proxy_entries[scheme.strip().lower()] = value.strip()

    return (
        _normalize_proxy_url(proxy_entries.get('https'))
        or _normalize_proxy_url(proxy_entries.get('http'))
        or _normalize_proxy_url(next(iter(proxy_entries.values()), None))
    )


def _get_windows_proxy_url() -> Optional[str]:
    if os.name != 'nt':
        return None

    try:
        import winreg
    except ImportError:
        return None

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        ) as registry_key:
            def read_registry_value(name: str, default: object = '') -> object:
                try:
                    return winreg.QueryValueEx(registry_key, name)[0]
                except FileNotFoundError:
                    return default

            proxy_enable = bool(read_registry_value('ProxyEnable', 0))
            proxy_server = str(read_registry_value('ProxyServer', ''))
            auto_config_url = str(read_registry_value('AutoConfigURL', ''))
    except OSError as exc:
        logger.warning("Unable to read Windows proxy configuration: %s", exc)
        return None

    explicit_proxy = _parse_windows_proxy_server(proxy_server) if proxy_enable else None
    if explicit_proxy:
        return explicit_proxy

    if not auto_config_url:
        return None

    try:
        with urlopen(auto_config_url, timeout=5) as response:
            pac_content = response.read().decode('utf-8', errors='ignore')
    except OSError as exc:
        logger.warning("Unable to load PAC file from %s: %s", auto_config_url, exc)
        return None

    return _extract_proxy_from_pac(pac_content)


def _build_proxy_configuration() -> Dict[str, str]:
    https_proxy = _normalize_proxy_url(
        os.getenv('PUBMED_HTTPS_PROXY')
        or os.getenv('HTTPS_PROXY')
        or os.getenv('https_proxy')
    )
    http_proxy = _normalize_proxy_url(
        os.getenv('PUBMED_HTTP_PROXY')
        or os.getenv('HTTP_PROXY')
        or os.getenv('http_proxy')
    )

    if https_proxy or http_proxy:
        resolved_https_proxy = https_proxy or http_proxy
        resolved_http_proxy = http_proxy or https_proxy
        if resolved_https_proxy and resolved_http_proxy:
            return {
                'https': resolved_https_proxy,
                'http': resolved_http_proxy,
            }

    windows_proxy = _get_windows_proxy_url()
    if not windows_proxy:
        return {}

    return {
        'https': windows_proxy,
        'http': windows_proxy,
    }

# Persistent HTTP session with retry strategy
_session = requests.Session()
_retry = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST"],
)
_session.mount("https://", HTTPAdapter(max_retries=_retry))
_session.mount("http://", HTTPAdapter(max_retries=_retry))

_proxy_configuration = _build_proxy_configuration()
if _proxy_configuration:
    _session.proxies.update(_proxy_configuration)
    logger.info(
        "PubMed proxy configured | https=%s | http=%s",
        _sanitize_proxy_for_log(_proxy_configuration.get('https')),
        _sanitize_proxy_for_log(_proxy_configuration.get('http')),
    )

# NCBI E-utilities API Configuration (chargé depuis .env)
NCBI_API_KEY = os.getenv('NCBI_API_KEY')
NCBI_EMAIL = os.getenv('NCBI_EMAIL')


class PubMedError(Exception):
    """Raised when the PubMed API returns an error response."""


PUBLICATION_TYPE_MAP = {
    # Clinical Trials
    "adaptive_clinical_trial": '"Adaptive Clinical Trial"[Publication Type]',
    "clinical_trial": '"Clinical Trial"[Publication Type]',
    "clinical_trial_protocol": '"Clinical Trial Protocol"[Publication Type]',
    "clinical_trial_phase_i": '"Clinical Trial, Phase I"[Publication Type]',
    "clinical_trial_phase_ii": '"Clinical Trial, Phase II"[Publication Type]',
    "clinical_trial_phase_iii": '"Clinical Trial, Phase III"[Publication Type]',
    "clinical_trial_phase_iv": '"Clinical Trial, Phase IV"[Publication Type]',
    "controlled_clinical_trial": '"Controlled Clinical Trial"[Publication Type]',
    "equivalence_trial": '"Equivalence Trial"[Publication Type]',
    "pragmatic_clinical_trial": '"Pragmatic Clinical Trial"[Publication Type]',
    "randomized_controlled_trial": '"Randomized Controlled Trial"[Publication Type]',
    
    # Studies
    "randomized_clinical_trial": '"Randomized Controlled Trial"[Publication Type]',
    "case_reports": '"Case Reports"[Publication Type]',
    "clinical_study": '"Clinical Study"[Publication Type]',
    "comparative_study": '"Comparative Study"[Publication Type]',
    "evaluation_study": '"Evaluation Study"[Publication Type]',
    "multicenter_study": '"Multicenter Study"[Publication Type]',
    "observational_study": '"Observational Study"[Publication Type]',
    "twin_study": '"Twin Study"[Publication Type]',
    "validation_study": '"Validation Study"[Publication Type]',
    
    # Reviews & Meta-analyses
    "meta_analysis": '"Meta-Analysis"[Publication Type]',
    "network_meta_analysis": '"Network Meta-Analysis"[Publication Type]',
    "review": '"Review"[Publication Type]',
    "systematic_review": '"Systematic Review"[Publication Type]',
    
    # Guidelines
    "guideline": '"Guideline"[Publication Type]',
    "practice_guideline": '"Practice Guideline"[Publication Type]',
    
    # Other
    "classical_article": '"Classical Article"[Publication Type]',
    "clinical_conference": '"Clinical Conference"[Publication Type]',
    
    # Legacy mappings (for backward compatibility)
    "randomized_controlled": '"Randomized Controlled Trial"[Publication Type]',
    "meta": '"Meta-Analysis"[Publication Type]',
    "cohort": '"Cohort Studies"[MeSH Terms]',
    "case_control": '"Case-Control Studies"[MeSH Terms]',
}

ALLOWED_PUBLICATION_TYPES = {
    "case_reports",
    "classical_article",
    "clinical_study",
    "comparative_study",
    "controlled_clinical_trial",
    "randomized_controlled_trial",
    "randomized_clinical_trial",
    "meta_analysis",
    "network_meta_analysis",
    "observational_study",
    "multicenter_study",
    "review",
    "systematic_review",
    "validation_study",
}


def _request(endpoint: str, params: Dict[str, str]) -> Response:
    headers = {"User-Agent": USER_AGENT}
    
    # Utiliser la clé API et l'email configurés
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY
    else:
        logger.warning("NCBI_API_KEY not set - requests may be rate-limited")
    
    if NCBI_EMAIL:
        params["email"] = NCBI_EMAIL
    
    # Calculer la taille approximative de l'URL
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE_URL}/{endpoint}"
    
    logger.info(f"PubMed request: {endpoint} - Query: {params.get('term', 'N/A')[:100]}")
    
    # Si l'URL est trop longue (> 2000 caractères), utiliser POST
    if len(url) + len(query_string) > 2000:
        response = _session.post(
            url,
            data=params,
            headers=headers,
            timeout=DEFAULT_TIMEOUT
        )
    else:
        response = _session.get(
            url,
            params=params,
            headers=headers,
            timeout=DEFAULT_TIMEOUT
        )
    
    logger.info(f"PubMed response: {response.status_code} - Content-Type: {response.headers.get('Content-Type', 'unknown')}")
    response.raise_for_status()
    return response


def _build_query(term: str, study_type: str = "", journal_filter: str = "") -> str:
    query_parts = []
    
    # Preprocess term: convert semicolons to AND operators
    if term:
        # Split by semicolons, strip whitespace, filter empty parts
        parts = [p.strip() for p in term.split(';') if p.strip()]
        if len(parts) > 1:
            # Multiple terms separated by semicolons -> combine with AND
            term = ' AND '.join(parts)
    
    # Build comprehensive search: Title/Abstract, MeSH Terms, and Author Keywords
    # [Other Term] captures Author Keywords in PubMed
    if term and ("OR" in term or "AND" in term):
        # For complex queries with boolean operators
        query_parts.append(f"(({term}[Title/Abstract]) OR ({term}[MeSH Terms]) OR ({term}[Other Term]))")
    elif term:
        # Simple search across all relevant fields
        query_parts.append(f"(({term}[Title/Abstract]) OR ({term}[MeSH Terms]) OR ({term}[Other Term]))")
    # Note: if term is empty and journal_filter is set, we'll search ALL articles from those journals
    
    # Handle multiple study types (list or comma-separated string)
    if study_type:
        types: List[str] = []
        if isinstance(study_type, list):
            types = study_type
        elif isinstance(study_type, str):
            types = [t.strip() for t in study_type.split(',') if t.strip()]
        
        mapped_types: List[str] = []
        for raw_type in types:
            normalized = raw_type.strip().lower()
            if not normalized or normalized not in ALLOWED_PUBLICATION_TYPES:
                continue
            mapped = PUBLICATION_TYPE_MAP.get(normalized)
            if mapped:
                mapped_types.append(mapped)
        
        if mapped_types:
            if len(mapped_types) > 1:
                # Combine with OR if multiple types
                query_parts.append(f"({' OR '.join(mapped_types)})")
            else:
                query_parts.append(mapped_types[0])
    
    # Add targeted journal filter
    if journal_filter == 'nurse':
        journal_query = build_nursing_journal_filter()
    else:
        journal_query = build_journal_filter(journal_filter)
    if journal_query:
        query_parts.append(journal_query)
    
    return " AND ".join(filter(None, query_parts))


def _parse_int(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _grab_year(pubdate: Dict[str, str]) -> Optional[int]:
    if not pubdate:
        return None
    year = pubdate.get("year") or pubdate.get("Year")
    if year:
        parsed = _parse_int(year)
        if parsed is not None:
            return parsed
    medline_date = pubdate.get("MedlineDate")
    if medline_date:
        match = re.search(r"(19|20)\d{2}", medline_date)
        if match:
            return int(match.group(0))
    return None


def _normalise_authors(author_list: List[Dict[str, str]]) -> str:
    authors: List[str] = []
    for author in author_list or []:
        last = author.get("LastName")
        fore = author.get("ForeName") or author.get("Initials")
        if last and fore:
            authors.append(f"{last} {fore}")
        elif last:
            authors.append(last)
    return ", ".join(authors)


def _parse_article_xml(xml_text: str) -> List[Dict]:
    """
    Parse PubMed XML response into article dictionaries.
    Uses last author affiliation for region detection.
    """
    root = ElementTree.fromstring(xml_text)
    articles: List[Dict] = []

    for node in root.findall(".//PubmedArticle"):
        medline = node.find("MedlineCitation")
        article_node = medline.find("Article") if medline is not None else None
        if article_node is None:
            continue

        pmid = medline.findtext("PMID") if medline is not None else None
        
        title_node = article_node.find("ArticleTitle")
        title = ""
        if title_node is not None:
            title = ElementTree.tostring(title_node, encoding="unicode", method="text")
        
        # Fallback: use VernacularTitle for non-English articles where ArticleTitle is "[Not Available]."
        if not title or title.strip().lower() in ("[not available].", "[not available]"):
            vernacular_node = article_node.find("VernacularTitle")
            if vernacular_node is not None:
                title = ElementTree.tostring(vernacular_node, encoding="unicode", method="text")

        abstract_texts = article_node.findall("Abstract/AbstractText")
        abstract = "\n".join(
            ElementTree.tostring(text, encoding="unicode", method="text").strip()
            for text in abstract_texts
        ).strip()

        journal_title = article_node.findtext("Journal/Title")
        pub_date_node = article_node.find("Journal/JournalIssue/PubDate")
        pubdate_dict: Dict[str, str] = {}
        if pub_date_node is not None:
            for child in pub_date_node:
                if child.text:
                    pubdate_dict[child.tag] = child.text
        year = _grab_year(pubdate_dict) or 0

        publication_types = [
            pt.text
            for pt in article_node.findall("PublicationTypeList/PublicationType")
            if pt.text
        ]

        author_list: List[Dict[str, str]] = []
        first_author_affiliation = ""
        last_author_affiliation = ""
        
        authors_nodes = article_node.findall("AuthorList/Author")
        for idx, author in enumerate(authors_nodes):
            author_data = {
                "LastName": author.findtext("LastName") or "",
                "ForeName": author.findtext("ForeName") or "",
                "Initials": author.findtext("Initials") or "",
            }
            author_list.append(author_data)
            
            # Extraire l'affiliation de l'auteur
            affiliation_node = author.find("AffiliationInfo/Affiliation")
            if affiliation_node is not None and affiliation_node.text:
                # Premier auteur (index 0)
                if idx == 0:
                    first_author_affiliation = affiliation_node.text
                # Dernier auteur (toujours mettre à jour pour avoir le dernier)
                last_author_affiliation = affiliation_node.text
        
        authors = _normalise_authors(author_list)
        
        # Determine region and country from affiliations
        # Extract both for reference
        first_author_region = get_region_from_affiliation(first_author_affiliation) if first_author_affiliation else ""
        first_author_country = get_country_code(first_author_affiliation) if first_author_affiliation else ""
        last_author_region = get_region_from_affiliation(last_author_affiliation) if last_author_affiliation else ""
        last_author_country = get_country_code(last_author_affiliation) if last_author_affiliation else ""

        # Use last author affiliation for region detection
        country = last_author_country
        region = last_author_region

        doi = ''
        for id_node in node.findall("PubmedData/ArticleIdList/ArticleId"):
            if id_node.attrib.get("IdType") == "doi":
                doi = (id_node.text or "").strip()
                break

        mesh_terms = (
            [mt.text for mt in medline.findall("MeshHeadingList/MeshHeading/DescriptorName") if mt.text]
            if medline is not None
            else []
        )
        
        # Extraire les vrais Keywords (KeywordList) depuis le XML PubMed
        keywords = (
            [kw.text for kw in medline.findall("KeywordList/Keyword") if kw.text]
            if medline is not None
            else []
        )
        
        # Extraire la langue de l'article
        language = ""
        if article_node is not None:
            lang_node = article_node.find("Language")
            if lang_node is not None and lang_node.text:
                language = lang_node.text.strip()  # e.g. "eng", "fre", "ger", "spa"

        # Extraire le nombre de participants avec Regex v2.0 (rapide)
        # Note: LLM disponible via llm_extractor.py mais trop lent pour recherches temps réel
        # Utiliser LLM uniquement pour exports où précision > vitesse
        participant_info = ParticipantExtractor.extract_sample_size(abstract)
        
        # ✨ NOUVEAU : Extraction automatique des critères principaux
        outcomes = OutcomeExtractor.extract_outcomes(abstract)
        outcome_summary = OutcomeExtractor.extract_summary(abstract)
        
        # ✨ Détection du caractère multicentrique
        multicenter_info = detect_multicenter(abstract, last_author_affiliation)

        articles.append(
            {
                "pmid": pmid,
                "title": (title or "").strip(),
                "authors": authors,
                "journal": journal_title or "",
                "year": year,
                "quality": "",
                "abstract": abstract,
                "summary": abstract,
                "study_type": ", ".join(publication_types),
                "sample_size": participant_info['sample_size'],
                "sample_size_confidence": participant_info['confidence'],
                "sample_size_source": participant_info['matched_text'],
                "region": region,  # Region based on last author affiliation
                "first_author_region": first_author_region,  # First author region
                "country": country,  # Primary country (last author)
                "first_author_country": first_author_country,  # First author country
                "last_author_country": last_author_country,  # Last author country
                "affiliation": last_author_affiliation,  # Primary affiliation (last author)
                "first_author_affiliation": first_author_affiliation,  # First author affiliation
                "last_author_affiliation": last_author_affiliation,  # Last author affiliation
                "language": language,  # Article language (eng, fre, ger, spa, etc.)
                "keywords": keywords,  # Real Keywords from KeywordList
                "mesh_terms": mesh_terms,
                "citations": None,
                "impact_factor": None,
                "doi": doi,
                # ✨ Critères extraits automatiquement
                "primary_outcome": outcomes.get('primary_outcome'),
                "primary_outcome_confidence": outcomes.get('primary_outcome_confidence'),
                "adverse_events": outcomes.get('adverse_events'),
                "adverse_events_confidence": outcomes.get('adverse_events_confidence'),
                "efficacy": outcomes.get('efficacy'),
                "efficacy_confidence": outcomes.get('efficacy_confidence'),
                "results": outcomes.get('results'),
                "results_confidence": outcomes.get('results_confidence'),
                "safety": outcomes.get('safety'),
                "safety_confidence": outcomes.get('safety_confidence'),
                "has_outcomes": bool(outcomes.get('primary_outcome') or outcomes.get('adverse_events') 
                                    or outcomes.get('efficacy') or outcomes.get('results') or outcomes.get('safety')),
                "outcome_summary": outcome_summary,
                # ✨ Caractère multicentrique
                "is_multicenter": multicenter_info.get('is_multicenter'),
                "multicenter_confidence": multicenter_info.get('confidence'),
                "center_count": multicenter_info.get('center_count'),
                "multicenter_evidence": multicenter_info.get('evidence'),
            }
        )

    return articles


def search_pubmed(
    *,
    term: str = "",
    start: int = 0,
    size: int = 50,
    study_type: str = "",
    time_period: str = "",
    journal_filter: str = "",
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
) -> Tuple[int, List[Dict]]:
    # If no term is provided and no journal filter is set, search all recent medical articles
    if not term or not term.strip():
        term = "medicine[MeSH Terms]"

    # 🚨 LIMITE PUBMED : Maximum articles accessibles
    if start >= MAX_PUBMED_LIMIT:
        logger.warning(f"Start index {start} exceeds PubMed limit ({MAX_PUBMED_LIMIT}). Resetting to 0.")
        start = 0
    
    if start + size > MAX_PUBMED_LIMIT:
        size = MAX_PUBMED_LIMIT - start
        logger.warning(f"Adjusted size to {size} to respect PubMed limit.")
    
    size = max(1, min(size, 200))
    esearch_params = {
        "db": "pubmed",
        "term": _build_query(term, study_type, journal_filter),
        "retstart": str(start),
        "retmax": str(size),
        "retmode": "json",
        "sort": "relevance",
    }

    # Priorité aux années personnalisées (year_from/year_to) sur time_period
    # Intervalle fermé [year_from, year_to] - les deux années sont incluses
    if year_from or year_to:
        today = datetime.now()
        start_year = int(year_from) if year_from else 1900
        end_year = int(year_to) if year_to else today.year
        esearch_params["mindate"] = f"{start_year}/01/01"
        esearch_params["maxdate"] = f"{end_year}/12/31"
        esearch_params["datetype"] = "pdat"  # Publication date
    elif time_period and time_period != "all":
        try:
            years = int(time_period)
        except (TypeError, ValueError):
            years = None
        if years:
            today = datetime.now()
            start_year = max(1900, today.year - years)
            esearch_params["mindate"] = f"{start_year}/{today.month:02d}/{today.day:02d}"
            esearch_params["maxdate"] = f"{today.year}/{today.month:02d}/{today.day:02d}"

    search_response = _request("esearch.fcgi", esearch_params)
    try:
        payload = search_response.json()
    except json.JSONDecodeError as exc:
        # PubMed sometimes returns HTML/XML error pages; surface a clearer message with a small snippet.
        cleaned_text = re.sub(r"[\x00-\x1f\x7f]", " ", search_response.text or "")
        snippet = cleaned_text[:500].strip()
        logger.error(f"PubMed non-JSON response. Status: {search_response.status_code}, Content-Type: {search_response.headers.get('Content-Type')}, Response: {snippet}")
        raise PubMedError(f"PubMed API error - received non-JSON response. This may be due to rate limiting or API issues. Response snippet: {snippet[:200]}") from exc
    try:
        result = payload["esearchresult"]
        total_count = int(result.get("count", 0))
        ids = result.get("idlist", [])
    except (KeyError, ValueError) as exc:
        raise PubMedError(f"Unexpected response structure: {payload}") from exc

    # 🚨 LIMITE PUBMED : Plafonner le total_count
    if total_count > MAX_PUBMED_LIMIT:
        logger.warning(f"PubMed found {total_count} articles but limit is {MAX_PUBMED_LIMIT}. Capping total.")
        total_count = MAX_PUBMED_LIMIT

    if not ids:
        return 0, []

    efetch_params = {
        "db": "pubmed",
        "id": ",".join(ids),
        "retmode": "xml",
    }
    fetch_response = _request("efetch.fcgi", efetch_params)
    articles = _parse_article_xml(fetch_response.text)
    
    return total_count, articles