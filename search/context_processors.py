from config.caching import cache_is_full

from search.services.impact_factor import IMPACT_FACTOR_YEAR, lookup_impact_factor
from search.services.version import EXTRACTION_VERSION, GIT_COMMIT
from search.services.journal_config import (
    FORMER_JOURNAL_TITLES, NURSING_JOURNALS, SURGERY_JOURNAL_TIERS, SURGERY_TIER_ORDER,
)


def cache_state(request):
    return {'CACHE_IS_FULL': cache_is_full()}


def journal_lists(request):
    """Surgery journal tiers (with their impact factor) and journal counts, for the templates."""
    tiers = []
    for code in SURGERY_TIER_ORDER:
        tier = SURGERY_JOURNAL_TIERS[code]
        journals = []
        for abbrev, name in tier['journals']:
            found = lookup_impact_factor(journal_abbrev=abbrev)
            journals.append({
                'abbrev': abbrev,
                'name': name,
                'impact_factor': found['impact_factor'] if found else None,
                'former_title': abbrev in FORMER_JOURNAL_TITLES,
            })
        count = sum(1 for j in journals if not j['former_title'])
        tiers.append({'code': code, 'label': tier['label'], 'journals': journals, 'count': count})
    return {
        'SURGERY_TIERS': tiers,
        'SURGERY_JOURNAL_COUNT': sum(t['count'] for t in tiers),
        'NURSING_JOURNAL_COUNT': len(NURSING_JOURNALS),
        'IMPACT_FACTOR_YEAR': IMPACT_FACTOR_YEAR,
        'EXTRACTION_VERSION': EXTRACTION_VERSION,
        'GIT_COMMIT': GIT_COMMIT,
    }
