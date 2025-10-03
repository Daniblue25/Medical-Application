import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests
from requests import Response
from xml.etree import ElementTree
from .participant_extractor import ParticipantExtractor


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
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    return response


def _build_query(term: str, study_type: str = "") -> str:
    query_parts = [term]
    mapped = PUBLICATION_TYPE_MAP.get(study_type)
    if mapped:
        query_parts.append(mapped)
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
        for author in article_node.findall("AuthorList/Author"):
            author_list.append(
                {
                    "LastName": author.findtext("LastName") or "",
                    "ForeName": author.findtext("ForeName") or "",
                    "Initials": author.findtext("Initials") or "",
                }
            )
        authors = _normalise_authors(author_list)

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

        # Extraire le nombre de participants de l'abstract
        participant_info = ParticipantExtractor.extract_sample_size(abstract)

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
                "region": "",
                "keywords": mesh_terms,
                "mesh_terms": mesh_terms,
                "citations": None,
                "impact_factor": None,
                "doi": doi,
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
) -> Tuple[int, List[Dict]]:
    # Si aucun terme n'est fourni, rechercher tous les articles médicaux récents
    if not term or not term.strip():
        term = "medicine[MeSH Terms]"

    size = max(1, min(size, 200))
    esearch_params = {
        "db": "pubmed",
        "term": _build_query(term, study_type),
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