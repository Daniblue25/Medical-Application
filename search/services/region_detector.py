"""
Module pour détecter la région géographique à partir de l'affiliation des auteurs.
Analyse l'affiliation du dernier auteur pour déterminer le pays et la région.
"""

import re
from typing import Optional


# Mapping des pays vers les régions
COUNTRY_TO_REGION = {
    # North America
    'united states': 'north_america',
    'usa': 'north_america',
    'us': 'north_america',
    'canada': 'north_america',
    'mexico': 'north_america',
    
    # Europe
    'france': 'europe',
    'germany': 'europe',
    'united kingdom': 'europe',
    'uk': 'europe',
    'italy': 'europe',
    'spain': 'europe',
    'netherlands': 'europe',
    'belgium': 'europe',
    'switzerland': 'europe',
    'sweden': 'europe',
    'norway': 'europe',
    'denmark': 'europe',
    'finland': 'europe',
    'poland': 'europe',
    'austria': 'europe',
    'portugal': 'europe',
    'greece': 'europe',
    'ireland': 'europe',
    'czech republic': 'europe',
    'hungary': 'europe',
    'romania': 'europe',
    'croatia': 'europe',
    'serbia': 'europe',
    'bulgaria': 'europe',
    'slovakia': 'europe',
    'slovenia': 'europe',
    'luxembourg': 'europe',
    'iceland': 'europe',
    'estonia': 'europe',
    'latvia': 'europe',
    'lithuania': 'europe',
    'russia': 'europe',
    'ukraine': 'europe',
    
    # Asia
    'china': 'asia',
    'japan': 'asia',
    'south korea': 'asia',
    'korea': 'asia',
    'india': 'asia',
    'singapore': 'asia',
    'hong kong': 'asia',
    'taiwan': 'asia',
    'thailand': 'asia',
    'malaysia': 'asia',
    'indonesia': 'asia',
    'philippines': 'asia',
    'vietnam': 'asia',
    'pakistan': 'asia',
    'bangladesh': 'asia',
    'israel': 'asia',
    'saudi arabia': 'asia',
    'united arab emirates': 'asia',
    'uae': 'asia',
    'turkey': 'asia',
    'iran': 'asia',
    'iraq': 'asia',
    'lebanon': 'asia',
    'jordan': 'asia',
    'kuwait': 'asia',
    'qatar': 'asia',
    'oman': 'asia',
    'bahrain': 'asia',
    'afghanistan': 'asia',
    'nepal': 'asia',
    'sri lanka': 'asia',
    'myanmar': 'asia',
    'cambodia': 'asia',
    'laos': 'asia',
    'mongolia': 'asia',
    'kazakhstan': 'asia',
    'uzbekistan': 'asia',
    
    # Africa
    'south africa': 'africa',
    'egypt': 'africa',
    'nigeria': 'africa',
    'kenya': 'africa',
    'ethiopia': 'africa',
    'ghana': 'africa',
    'tanzania': 'africa',
    'uganda': 'africa',
    'morocco': 'africa',
    'algeria': 'africa',
    'tunisia': 'africa',
    'libya': 'africa',
    'sudan': 'africa',
    'senegal': 'africa',
    'cameroon': 'africa',
    'ivory coast': 'africa',
    'madagascar': 'africa',
    'mali': 'africa',
    'burkina faso': 'africa',
    'niger': 'africa',
    'mozambique': 'africa',
    'malawi': 'africa',
    'zambia': 'africa',
    'zimbabwe': 'africa',
    'botswana': 'africa',
    'namibia': 'africa',
    'rwanda': 'africa',
    'burundi': 'africa',
    'somalia': 'africa',
    'angola': 'africa',
    'congo': 'africa',
    
    # South America
    'brazil': 'south_america',
    'argentina': 'south_america',
    'chile': 'south_america',
    'colombia': 'south_america',
    'peru': 'south_america',
    'venezuela': 'south_america',
    'ecuador': 'south_america',
    'bolivia': 'south_america',
    'paraguay': 'south_america',
    'uruguay': 'south_america',
    'guyana': 'south_america',
    'suriname': 'south_america',
    
    # Oceania
    'australia': 'oceania',
    'new zealand': 'oceania',
    'fiji': 'oceania',
    'papua new guinea': 'oceania',
    'samoa': 'oceania',
}


# Patterns pour extraire les pays depuis les affiliations
COUNTRY_PATTERNS = [
    # Pattern pour les pays en fin de phrase (format classique)
    r',\s*([A-Z][a-zA-Z\s]+)\.?\s*$',
    # Pattern pour les codes postaux US/Canada suivis du pays
    r'\b[A-Z]{2}\s+\d{5}(?:-\d{4})?,?\s+([A-Z][a-zA-Z\s]+)',
    # Pattern pour les emails avec domaine pays
    r'@[a-zA-Z0-9.-]+\.([a-z]{2,3})\b',
]


def normalize_country(country: str) -> str:
    """
    Normalise le nom d'un pays pour la correspondance.
    
    Args:
        country: Nom du pays brut
        
    Returns:
        Nom du pays normalisé en minuscules
    """
    if not country:
        return ""
    
    # Supprimer la ponctuation et normaliser
    country = country.strip().lower()
    country = re.sub(r'[.,;]', '', country)
    
    # Mappings spéciaux pour les abréviations communes
    special_mappings = {
        'u.s.a': 'usa',
        'u.s': 'usa',
        'u.k': 'uk',
        'p.r. china': 'china',
        'p.r.china': 'china',
        "people's republic of china": 'china',
        'republic of korea': 'south korea',
        'uae': 'united arab emirates',
    }
    
    return special_mappings.get(country, country)


def extract_country_from_affiliation(affiliation: str) -> Optional[str]:
    """
    Extrait le nom du pays depuis une affiliation d'auteur.
    
    Args:
        affiliation: Texte de l'affiliation
        
    Returns:
        Nom du pays normalisé ou None si non trouvé
    """
    if not affiliation:
        return None
    
    # Essayer chaque pattern
    for pattern in COUNTRY_PATTERNS:
        match = re.search(pattern, affiliation)
        if match:
            country = normalize_country(match.group(1))
            # Vérifier si le pays est dans notre mapping
            if country in COUNTRY_TO_REGION:
                return country
    
    # Fallback: chercher directement les noms de pays dans le texte
    affiliation_lower = affiliation.lower()
    for country in COUNTRY_TO_REGION.keys():
        if country in affiliation_lower:
            return country
    
    return None


def get_region_from_affiliation(affiliation: str) -> str:
    """
    Détermine la région géographique depuis une affiliation.
    
    Args:
        affiliation: Texte de l'affiliation de l'auteur
        
    Returns:
        Code de région ('north_america', 'europe', 'asia', 'africa', 
        'south_america', 'oceania') ou chaîne vide si non déterminé
    """
    country = extract_country_from_affiliation(affiliation)
    if country:
        return COUNTRY_TO_REGION.get(country, '')
    return ''


def get_region_name(region_code: str) -> str:
    """
    Convertit un code de région en nom lisible.
    
    Args:
        region_code: Code de région ('north_america', etc.)
        
    Returns:
        Nom de région lisible
    """
    region_names = {
        'north_america': 'North America',
        'europe': 'Europe',
        'asia': 'Asia',
        'africa': 'Africa',
        'south_america': 'South America',
        'oceania': 'Oceania',
    }
    return region_names.get(region_code, 'Global')
