import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging

import requests
from requests import Response
from xml.etree import ElementTree
from .participant_extractor import ParticipantExtractor
from .llm_extractor import LLMParticipantExtractor
from .outcome_extractor import OutcomeExtractor
from .region_detector import get_region_from_affiliation
from .journal_config import build_journal_filter

logger = logging.getLogger(__name__)


BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
USER_AGENT = "MedSearchApp/1.0 (contact: support@example.com)"
DEFAULT_TIMEOUT = 12


class PubMedError(Exception):
    """Raised when the PubMed API returns an error response."""


PUBLICATION_TYPE_MAP = {
    "randomized_controlled": '"randomized controlled trial"[Publication Type]',
    "meta": '"meta-analysis"[Publication Type]',
    "cohort": '"cohort studies"[MeSH Terms]',
    "case_control": '"case-control studies"[MeSH Terms]',
    "systematic_review": '"systematic review"[Publication Type]',
}


def _request(endpoint: str, params: Dict[str, str]) -> Response:
    headers = {"User-Agent": USER_AGENT}
    api_key = os.getenv("PUBMED_API_KEY")
    if api_key:
        params["api_key"] = api_key
    response = requests.get(
        f"{BASE_URL}/{endpoint}",
        params=params,
        headers=headers,
        timeout=DEFAULT_TIMEOUT
    )
    response.raise_for_status()
    return response


def _build_query(term: str, study_type: str = "", journal_filter: str = "") -> str:
    query_parts = []
    
    # Si le terme contient déjà des opérateurs booléens (OR, AND), on le recherche dans titre OU abstract
    if term and ("OR" in term or "AND" in term):
        # Recherche dans titre OU abstract pour les mots-clés chirurgicaux
        query_parts.append(f"({term}[Title/Abstract])")
    elif term:
        # Recherche simple dans titre OU abstract
        query_parts.append(f"{term}[Title/Abstract]")
    
    mapped = PUBLICATION_TYPE_MAP.get(study_type)
    if mapped:
        query_parts.append(mapped)
    
    # Ajouter le filtre de journal ciblé
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
        last_author_affiliation = ""
        
        for author in article_node.findall("AuthorList/Author"):
            author_data = {
                "LastName": author.findtext("LastName") or "",
                "ForeName": author.findtext("ForeName") or "",
                "Initials": author.findtext("Initials") or "",
            }
            author_list.append(author_data)
            
            # Extraire l'affiliation du dernier auteur
            affiliation_node = author.find("AffiliationInfo/Affiliation")
            if affiliation_node is not None and affiliation_node.text:
                last_author_affiliation = affiliation_node.text
        
        authors = _normalise_authors(author_list)
        
        # Déterminer la région depuis l'affiliation du dernier auteur
        region = get_region_from_affiliation(last_author_affiliation) if last_author_affiliation else ""

        doi = None
        for id_node in node.findall("PubmedData/ArticleIdList/ArticleId"):
            if id_node.attrib.get("IdType") == "doi":
                doi = (id_node.text or "").strip()
                break

        mesh_terms = (
            [mt.text for mt in medline.findall("MeshHeadingList/MeshHeading/DescriptorName") if mt.text]
            if medline is not None
            else []
        )

        # Extraire le nombre de participants avec Regex v2.0 (rapide)
        # Note: LLM disponible via llm_extractor.py mais trop lent pour recherches temps réel
        # Utiliser LLM uniquement pour exports où précision > vitesse
        participant_info = ParticipantExtractor.extract_sample_size(abstract)
        
        # ✨ NOUVEAU : Extraction automatique des critères principaux
        outcomes = OutcomeExtractor.extract_outcomes(abstract)
        outcome_summary = OutcomeExtractor.extract_summary(abstract)

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
                "region": region,  # Région basée sur l'affiliation du dernier auteur
                "keywords": mesh_terms,
                "mesh_terms": mesh_terms,
                "citations": None,
                "impact_factor": None,
                "doi": doi,
                # ✨ Critère principal uniquement
                "primary_outcome": outcomes.get('primary_outcome'),
                "primary_outcome_confidence": outcomes.get('primary_outcome_confidence'),
                "has_outcomes": bool(outcomes.get('primary_outcome')),
                "outcome_summary": outcome_summary,
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
) -> Tuple[int, List[Dict]]:
    # Si aucun terme n'est fourni, rechercher tous les articles médicaux récents
    if not term or not term.strip():
        term = "medicine[MeSH Terms]"

    size = max(1, min(size, 200))
    esearch_params = {
        "db": "pubmed",
        "term": _build_query(term, study_type, journal_filter),
        "retstart": str(start),
        "retmax": str(size),
        "retmode": "json",
        "sort": "relevance",
    }

    if time_period and time_period != "all":
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
    payload = search_response.json()
    try:
        result = payload["esearchresult"]
        total_count = int(result.get("count", 0))
        ids = result.get("idlist", [])
    except (KeyError, ValueError) as exc:
        raise PubMedError(f"Unexpected response structure: {payload}") from exc

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