"""
Détection du caractère multicentrique des études biomédicales.

Analyse le texte d'un abstract et les affiliations des auteurs pour
déterminer si une étude est monocentrique, multicentrique, ou si
l'information n'est pas disponible.

Hiérarchie de détection :
  1. Mentions explicites dans l'abstract ("multicenter", "multicentre", "multi-site")
  2. Nombre de centres/sites/hôpitaux mentionnés ("conducted at 12 centers")
  3. Mots-clés de registres/réseaux/consortiums
  4. Mentions explicites monocentriques ("single-center", "single institution")
  5. Analyse des affiliations (multiples pays/villes = probable multicentrique)
"""

import re
from typing import Optional


# ============================================================================
# PATTERNS EXPLICITES MULTICENTRIQUES
# ============================================================================
# Ordered by specificity (most specific first)

_MULTICENTER_EXPLICIT = [
    # Explicit "multicenter/multicentre/multi-center" keywords
    re.compile(r'\b(?:multi[- ]?cent(?:er|re)|multisite|multi[- ]?site|multi[- ]?institutional)\b', re.IGNORECASE),
    # "conducted at/in X centers/sites/hospitals"
    re.compile(r'(?:conducted|performed|carried\s+out)\s+(?:at|in|across)\s+(\d+)\s+(?:centers?|centres?|sites?|hospitals?|institutions?|clinics?)', re.IGNORECASE),
    # "X centers/sites participated"
    re.compile(r'(\d+)\s+(?:centers?|centres?|sites?|hospitals?|institutions?|clinics?)\s+(?:participated|were\s+included|contributed|enrolled)', re.IGNORECASE),
    # "from X centers/hospitals" (optional adjective allowed: "from 3 academic hospitals")
    re.compile(r'from\s+(\d+)\s+(?:\w+\s+)?(?:centers?|centres?|sites?|hospitals?|institutions?|clinics?)', re.IGNORECASE),
    # "across X countries/centers"
    re.compile(r'across\s+(\d+)\s+(?:countries|centers?|centres?|sites?|hospitals?|institutions?)', re.IGNORECASE),
    # "in X countries and Y centers"
    re.compile(r'in\s+(\d+)\s+countries?\s+(?:and\s+)?(\d+)\s+(?:centers?|centres?|sites?)', re.IGNORECASE),
    # Network/consortium/collaborative patterns
    re.compile(r'\b(?:consortium|collaborative\s+group|research\s+network|cooperative\s+group|study\s+group|working\s+group)\b', re.IGNORECASE),
    # Registry patterns (typically large multicenter)
    re.compile(r'\b(?:national|international|regional|nationwide)\s+(?:registry|database|cohort|network|survey)\b', re.IGNORECASE),
    # "pooled data from X hospitals/centers"
    re.compile(r'pooled\s+(?:data|analysis)\s+from\s+(?:\d+\s+)?(?:centers?|centres?|sites?|hospitals?|institutions?)', re.IGNORECASE),
    # French patterns
    re.compile(r'\b(?:multi[- ]?centrique|pluri[- ]?centrique)\b', re.IGNORECASE),
    re.compile(r'(?:réalisée?|conduite?|menée?)\s+(?:dans|à\s+travers)\s+(\d+)\s+(?:centres?|hôpitaux|établissements?|sites?)', re.IGNORECASE),
    re.compile(r'\b(?:registre|réseau|consortium)\s+(?:national|international|régional|multicentrique)\b', re.IGNORECASE),
]

# ============================================================================
# PATTERNS EXPLICITES MONOCENTRIQUES
# ============================================================================
_SINGLE_CENTER_EXPLICIT = [
    re.compile(r'\b(?:single[- ]?cent(?:er|re)|single[- ]?site|single[- ]?institution(?:al)?)\b', re.IGNORECASE),
    re.compile(r'\b(?:at\s+(?:a\s+single|one|our)\s+(?:center|centre|site|hospital|institution))\b', re.IGNORECASE),
    re.compile(r'\bconducted\s+at\s+(?:the\s+)?(?:\w+\s+){1,4}(?:Hospital|Medical\s+Center|University)\b', re.IGNORECASE),
    # French
    re.compile(r'\b(?:mono[- ]?centrique|uni[- ]?centrique)\b', re.IGNORECASE),
    re.compile(r'(?:réalisée?|conduite?|menée?)\s+(?:dans|à)\s+(?:un\s+seul|notre)\s+(?:centre|hôpital|établissement|service)', re.IGNORECASE),
]

# ============================================================================
# EXTRACTION DU NOMBRE DE CENTRES
# ============================================================================
_CENTER_COUNT_PATTERNS = [
    re.compile(r'(?:conducted|performed|carried\s+out)\s+(?:at|in|across)\s+(\d+)\s+(?:centers?|centres?|sites?|hospitals?|institutions?)', re.IGNORECASE),
    re.compile(r'(\d+)\s+(?:centers?|centres?|sites?|hospitals?|institutions?)\s+(?:participated|included|contributed|enrolled|in)', re.IGNORECASE),
    re.compile(r'from\s+(\d+)\s+(?:centers?|centres?|sites?|hospitals?|institutions?)', re.IGNORECASE),
    re.compile(r'across\s+(\d+)\s+(?:countries?|centers?|centres?|sites?)', re.IGNORECASE),
    re.compile(r'(\d+)\s+(?:centers?|centres?|sites?|hospitals?)\s+(?:in|across)\s+(\d+)\s+countries?', re.IGNORECASE),
    re.compile(r'(?:dans|à\s+travers)\s+(\d+)\s+(?:centres?|hôpitaux|établissements?)', re.IGNORECASE),
]


def detect_multicenter(
    abstract: str,
    affiliation: str = "",
) -> dict:
    """
    Détecte le caractère multicentrique d'une étude.

    Args:
        abstract: Texte de l'abstract.
        affiliation: Affiliation du dernier auteur (optionnel).

    Returns:
        dict: {
            'is_multicenter': bool or None,   # True/False/None (unknown)
            'confidence': str,                 # 'high', 'medium', 'low'
            'center_count': int or None,       # Nombre de centres si détecté
            'evidence': str,                   # Texte justificatif
        }
    """
    if not abstract or len(abstract.strip()) < 30:
        return {
            'is_multicenter': None,
            'confidence': 'none',
            'center_count': None,
            'evidence': '',
        }

    # ── Priority 1: Explicit multicenter keywords ──
    for pattern in _MULTICENTER_EXPLICIT:
        m = pattern.search(abstract)
        if m:
            # If the pattern captured a numeric count, check it's > 1
            try:
                matched_count = int(m.group(1))
            except (IndexError, ValueError):
                matched_count = None
            if matched_count is not None and matched_count == 1:
                # "from 1 center" → single-center, not multicenter
                return {
                    'is_multicenter': False,
                    'confidence': 'medium',
                    'center_count': 1,
                    'evidence': m.group().strip(),
                }
            center_count = matched_count if matched_count and matched_count > 1 else _extract_center_count(abstract)
            return {
                'is_multicenter': True,
                'confidence': 'high',
                'center_count': center_count,
                'evidence': m.group().strip(),
            }

    # ── Priority 2: Explicit single-center keywords ──
    for pattern in _SINGLE_CENTER_EXPLICIT:
        m = pattern.search(abstract)
        if m:
            return {
                'is_multicenter': False,
                'confidence': 'high',
                'center_count': 1,
                'evidence': m.group().strip(),
            }

    # ── Priority 3: Numeric center count (implies multicenter if > 1) ──
    center_count = _extract_center_count(abstract)
    if center_count is not None:
        if center_count > 1:
            return {
                'is_multicenter': True,
                'confidence': 'high',
                'center_count': center_count,
                'evidence': f'{center_count} centers detected',
            }
        elif center_count == 1:
            return {
                'is_multicenter': False,
                'confidence': 'medium',
                'center_count': 1,
                'evidence': '1 center detected',
            }

    # ── Priority 4: Indirect multicenter evidence from affiliations ──
    if affiliation:
        multi_evidence = _check_affiliation_multicenter(abstract, affiliation)
        if multi_evidence:
            return multi_evidence

    # ── No evidence found ──
    return {
        'is_multicenter': None,
        'confidence': 'none',
        'center_count': None,
        'evidence': '',
    }


def _extract_center_count(text: str) -> Optional[int]:
    """Extract the number of centers/sites from text."""
    for pattern in _CENTER_COUNT_PATTERNS:
        m = pattern.search(text)
        if m:
            try:
                count = int(m.group(1))
                if 1 <= count <= 5000:
                    return count
            except (ValueError, IndexError):
                continue
    return None


def _check_affiliation_multicenter(abstract: str, affiliation: str) -> Optional[dict]:
    """
    Indirect multicenter evidence: if abstract mentions multiple
    countries/cities AND the affiliation contains multiple institutions.
    """
    abstract_lower = abstract.lower()

    # Check for multiple country mentions in abstract
    country_keywords = [
        'united states', 'united kingdom', 'france', 'germany', 'japan',
        'china', 'canada', 'australia', 'italy', 'spain', 'brazil',
        'india', 'south korea', 'netherlands', 'sweden', 'switzerland',
    ]
    countries_found = [c for c in country_keywords if c in abstract_lower]

    if len(countries_found) >= 2:
        return {
            'is_multicenter': True,
            'confidence': 'medium',
            'center_count': None,
            'evidence': f'Multiple countries: {", ".join(countries_found[:3])}',
        }

    # Check for "and" linking multiple institutions in affiliation
    aff_lower = affiliation.lower()
    institution_keywords = ['university', 'hospital', 'medical center',
                            'institute', 'clinic', 'department']
    inst_count = sum(1 for kw in institution_keywords if kw in aff_lower)
    if inst_count >= 2 and (' and ' in aff_lower or '; ' in aff_lower):
        return {
            'is_multicenter': True,
            'confidence': 'low',
            'center_count': None,
            'evidence': 'Multiple institutions in affiliation',
        }

    return None
