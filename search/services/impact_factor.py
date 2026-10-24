"""
Journal Impact Factor lookup (JCR 2024 values, from the SIGAPS 2020-2024 list).

The data file is generated from the SIGAPS workbook with:
    python manage.py import_impact_factors "distribution/Rang SIGAPS 2020-2024.xlsx"

It is not versioned (JCR values are licensed data). When the file is missing,
every lookup returns None and the interface shows "Not available".

Matching order: NLM Unique ID, then ISSN (print or electronic), then NLM title
abbreviation (MedlineTA). These identifiers come from the PubMed XML record.
"""

import json
import logging
import os
from typing import Dict, Iterable, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

IMPACT_FACTOR_YEAR = 2024


def get_data_path() -> str:
    default = os.path.join(settings.BASE_DIR, 'search', 'data', f'impact_factors_{IMPACT_FACTOR_YEAR}.json')
    return getattr(settings, 'IMPACT_FACTOR_FILE', None) or os.getenv('IMPACT_FACTOR_FILE') or default


def normalize_nlm_id(value) -> str:
    """PubMed zero-pads NLM IDs ('0372354'), the SIGAPS list does not ('372354')."""
    return str(value or '').strip().upper().lstrip('0')


def normalize_issn(value) -> str:
    return str(value or '').strip().upper().replace('-', '')


def normalize_title(value) -> str:
    return ' '.join(str(value or '').lower().split())


_AMBIGUOUS = object()  # marks an ISSN or abbreviation shared by journals with different impact factors
_index_cache = {'key': None, 'index': None}


def _build_index(path: str) -> Dict[str, Dict]:
    index = {'nlm': {}, 'issn': {}, 'ta': {}}
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for journal in data.get('journals', []):
        entry = {'impact_factor': journal['if'], 'impact_factor_year': data.get('year', IMPACT_FACTOR_YEAR)}
        if journal.get('nlm_id'):
            index['nlm'][normalize_nlm_id(journal['nlm_id'])] = entry
        keys = [('issn', normalize_issn(i)) for i in journal.get('issn', [])]
        if journal.get('ta'):
            keys.append(('ta', normalize_title(journal['ta'])))
        for kind, key in keys:
            previous = index[kind].get(key)
            if previous is None:
                index[kind][key] = entry
            elif previous is not _AMBIGUOUS and previous['impact_factor'] != entry['impact_factor']:
                index[kind][key] = _AMBIGUOUS  # never guess between two journals
    logger.info(f"Impact factors loaded: {len(data.get('journals', []))} journals from {path}")
    return index


def _load_index() -> Dict[str, Dict]:
    """Return the lookup index, reloading it whenever the data file appears or changes."""
    path = get_data_path()
    try:
        key = (path, os.path.getmtime(path))
    except OSError:
        if _index_cache['key'] != (path, None):
            logger.warning(f"Impact factor file not found ({path}): impact factors will be shown as not available")
            _index_cache.update(key=(path, None), index={'nlm': {}, 'issn': {}, 'ta': {}})
        return _index_cache['index']
    if _index_cache['key'] != key:
        _index_cache.update(key=key, index=_build_index(path))
    return _index_cache['index']


def lookup_impact_factor(nlm_id: str = '', issns: Iterable[str] = (), journal_abbrev: str = '') -> Optional[Dict]:
    """Return {'impact_factor': float, 'impact_factor_year': int} or None if unknown."""
    index = _load_index()
    if nlm_id and normalize_nlm_id(nlm_id) in index['nlm']:
        return index['nlm'][normalize_nlm_id(nlm_id)]
    candidates = [index['issn'].get(normalize_issn(i)) for i in issns or ()]
    if journal_abbrev:
        candidates.append(index['ta'].get(normalize_title(journal_abbrev)))
    for entry in candidates:
        if entry is not None and entry is not _AMBIGUOUS:
            return entry
    return None


def clear_cache():
    """Reload the data file on next lookup (used after an import and in tests)."""
    _index_cache.update(key=None, index=None)
