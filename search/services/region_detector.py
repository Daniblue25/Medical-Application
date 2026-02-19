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

# Mapping villes -> pays pour inférence
CITY_TO_COUNTRY = {
    # USA
    'new york': 'usa',
    'boston': 'usa',
    'chicago': 'usa',
    'houston': 'usa',
    'philadelphia': 'usa',
    'san francisco': 'usa',
    'los angeles': 'usa',
    'san diego': 'usa',
    'dallas': 'usa',
    'atlanta': 'usa',
    'miami': 'usa',
    'seattle': 'usa',
    'washington': 'usa',
    'baltimore': 'usa',
    'detroit': 'usa',
    'denver': 'usa',
    'pittsburgh': 'usa',
    'cleveland': 'usa',
    'st. louis': 'usa',
    'minneapolis': 'usa',
    # UK
    'london': 'uk',
    'manchester': 'uk',
    'birmingham': 'uk',
    'glasgow': 'uk',
    'edinburgh': 'uk',
    'liverpool': 'uk',
    'leeds': 'uk',
    'oxford': 'uk',
    'cambridge': 'uk',
    'bristol': 'uk',
    # Canada
    'toronto': 'canada',
    'montreal': 'canada',
    'vancouver': 'canada',
    'ottawa': 'canada',
    'calgary': 'canada',
    'edmonton': 'canada',
    'quebec': 'canada',
    # Australia
    'sydney': 'australia',
    'melbourne': 'australia',
    'brisbane': 'australia',
    'perth': 'australia',
    'adelaide': 'australia',
    # France (Villes principales et CHU)
    'paris': 'france',
    'lyon': 'france',
    'marseille': 'france',
    'toulouse': 'france',
    'bordeaux': 'france',
    'lille': 'france',
    'nice': 'france',
    'nantes': 'france',
    'strasbourg': 'france',
    'montpellier': 'france',
    'rennes': 'france',
    'grenoble': 'france',
    'rouen': 'france',
    'clermont-ferrand': 'france',
    'nancy': 'france',
    'dijon': 'france',
    'tours': 'france',
    'angers': 'france',
    'brest': 'france',
    'caen': 'france',
    'reims': 'france',
    'metz': 'france',
    'amiens': 'france',
    'besançon': 'france',
    'limoges': 'france',
    'poitiers': 'france',
    'saint-etienne': 'france',
    'creteil': 'france',
    'bobigny': 'france',
    'boulogne-billancourt': 'france',
    # Germany
    'berlin': 'germany',
    'munich': 'germany',
    'hamburg': 'germany',
    'frankfurt': 'germany',
    'heidelberg': 'germany',
    # Italy
    'rome': 'italy',
    'milan': 'italy',
    'naples': 'italy',
    'turin': 'italy',
    # Spain
    'madrid': 'spain',
    'barcelona': 'spain',
    'valencia': 'spain',
    'seville': 'spain',
    # Japan
    'tokyo': 'japan',
    'osaka': 'japan',
    'kyoto': 'japan',
    # China
    'beijing': 'china',
    'shanghai': 'china',
    'hong kong': 'china',
}

# Territoires français (mappés vers 'france')
FRANCE_TERRITORIES = [
    # France métropolitaine
    'france',
    # Régions d'outre-mer (DROM)
    'guadeloupe',
    'martinique',
    'guyane',
    'french guiana',
    'guyane française',
    'guyane francaise',
    'réunion',
    'reunion',
    'la réunion',
    'la reunion',
    'mayotte',
    # Collectivités d'outre-mer (COM)
    'saint-pierre-et-miquelon',
    'saint pierre et miquelon',
    'saint-pierre and miquelon',
    'saint barthélemy',
    'saint barthelemy',
    'saint-barthélemy',
    'saint-barthelemy',
    'saint martin',
    'saint-martin',
    'wallis-et-futuna',
    'wallis et futuna',
    'wallis and futuna',
    'polynésie française',
    'polynesie francaise',
    'french polynesia',
    'nouvelle-calédonie',
    'nouvelle caledonie',
    'new caledonia',
    # Corse
    'corse',
    'corsica',
    # Villes françaises communes dans affiliations
    'paris',
    'lyon',
    'marseille',
    'toulouse',
    'bordeaux',
    'lille',
    'nice',
    'nantes',
    'strasbourg',
    'montpellier',
    'rennes',
    'grenoble',
    'rouen',
    'clermont-ferrand',
]

# Mapping TLD -> Pays (pour détection email)
TLD_TO_COUNTRY = {
    # Europe
    'uk': 'united kingdom',
    'fr': 'france',
    'de': 'germany',
    'it': 'italy',
    'es': 'spain',
    'nl': 'netherlands',
    'be': 'belgium',
    'ch': 'switzerland',
    'se': 'sweden',
    'no': 'norway',
    'dk': 'denmark',
    'fi': 'finland',
    'pl': 'poland',
    'at': 'austria',
    'pt': 'portugal',
    'gr': 'greece',
    'ie': 'ireland',
    'ru': 'russia',
    # Americas
    'us': 'usa',
    'gov': 'usa',
    'edu': 'usa', # Majoritaire
    'ca': 'canada',
    'br': 'brazil',
    'ar': 'argentina',
    'mx': 'mexico',
    # Asia
    'cn': 'china',
    'jp': 'japan',
    'kr': 'south korea',
    'in': 'india',
    'sg': 'singapore',
    'hk': 'hong kong',
    'tw': 'taiwan',
    'th': 'thailand',
    # Oceania
    'au': 'australia',
    'nz': 'new zealand',
    # Africa
    'za': 'south africa',
}

# Mapping Universités -> Pays (Inférence forte)
UNIVERSITY_TO_COUNTRY = {
    # UK
    "wolverhampton": "united kingdom",  # Ajout spécifique suite à la demande
    "university of wolverhampton": "united kingdom",
    "oxford": "united kingdom",
    "cambridge": "united kingdom",
    "ucl": "united kingdom",
    "imperial college": "united kingdom",
    "kcl": "united kingdom",
    "king's college": "united kingdom",
    "edinburgh": "united kingdom",
    "manchester": "united kingdom",
    "glasgow": "united kingdom",
    "birmingham": "united kingdom",
    "bristol": "united kingdom",
    "southampton": "united kingdom",
    "leeds": "united kingdom",
    "sheffield": "united kingdom",
    "nottingham": "united kingdom",
    "newcastle university": "united kingdom",
    "liverpool": "united kingdom",
    "cardiff": "united kingdom",
    "queen mary": "united kingdom",
    "nhs": "united kingdom", # National Health Service

    # USA
    "harvard": "usa",
    "stanford": "usa",
    "johns hopkins": "usa",
    "yale": "usa",
    "duke": "usa",
    "princeton": "usa",
    "cornell": "usa",
    "columbia university": "usa",
    "mayo clinic": "usa",
    "cleveland clinic": "usa",
    "massachusetts general hospital": "usa",
    "brigham and women": "usa",
    "mount sinai": "usa",
    "vanderbilt": "usa",
    "emory": "usa",
    "northwestern university": "usa",
    "university of california": "usa",
    "ucla": "usa",
    "ucsf": "usa",
    "ucsd": "usa",
    "university of washington": "usa",
    "university of michigan": "usa",
    "university of pennsylvania": "usa",
    "penn state": "usa",
    "ohio state": "usa",
    
    # France
    "sorbonne": "france",
    "ap-hp": "france",
    "aphp": "france",
    "inserm": "france",
    "cnrs": "france",
    "pasteur": "france",
    "curie": "france",
    "gustave roussy": "france",
    "chu de": "france",
    "chru": "france",
    "université de paris": "france",
    "paris cité": "france",
    "paris-saclay": "france",
    "aix-marseille": "france",
    
    # Canada
    "toronto": "canada",
    "ubc": "canada",
    "mcgill": "canada",
    "mcmaster": "canada",
    "montreal": "canada",
    "alberta": "canada",
    "calgary": "canada",
    "ottawa": "canada",
    "laval": "canada",
    "western university": "canada",
    
    # Australia
    "melbourne": "australia",
    "sydney": "australia",
    "queensland": "australia",
    "monash": "australia",
    "unsw": "australia",
    "anu": "australia",
    
    # China
    "peking university": "china",
    "tsinghua": "china",
    "fudan": "china",
    "shanghai jiao tong": "china",
    "zhejiang university": "china",
    
    # Japan
    "tokyo university": "japan",
    "kyoto university": "japan",
    "osaka university": "japan",
    "tohoku university": "japan",
}

# Mapping des noms de pays normalisés vers les noms d'affichage
COUNTRY_DISPLAY_NAMES = {
    'united states': 'United States',
    'usa': 'United States',
    'us': 'United States',
    'canada': 'Canada',
    'mexico': 'Mexico',
    'france': 'France',
    'germany': 'Germany',
    'united kingdom': 'United Kingdom',
    'uk': 'United Kingdom',
    'italy': 'Italy',
    'spain': 'Spain',
    'netherlands': 'Netherlands',
    'belgium': 'Belgium',
    'switzerland': 'Switzerland',
    'sweden': 'Sweden',
    'norway': 'Norway',
    'denmark': 'Denmark',
    'finland': 'Finland',
    'poland': 'Poland',
    'austria': 'Austria',
    'portugal': 'Portugal',
    'greece': 'Greece',
    'ireland': 'Ireland',
    'czech republic': 'Czech Republic',
    'hungary': 'Hungary',
    'romania': 'Romania',
    'croatia': 'Croatia',
    'serbia': 'Serbia',
    'bulgaria': 'Bulgaria',
    'slovakia': 'Slovakia',
    'slovenia': 'Slovenia',
    'luxembourg': 'Luxembourg',
    'iceland': 'Iceland',
    'estonia': 'Estonia',
    'latvia': 'Latvia',
    'lithuania': 'Lithuania',
    'russia': 'Russia',
    'ukraine': 'Ukraine',
    'china': 'China',
    'japan': 'Japan',
    'south korea': 'South Korea',
    'korea': 'South Korea',
    'india': 'India',
    'singapore': 'Singapore',
    'hong kong': 'Hong Kong',
    'taiwan': 'Taiwan',
    'thailand': 'Thailand',
    'malaysia': 'Malaysia',
    'indonesia': 'Indonesia',
    'philippines': 'Philippines',
    'vietnam': 'Vietnam',
    'pakistan': 'Pakistan',
    'bangladesh': 'Bangladesh',
    'israel': 'Israel',
    'saudi arabia': 'Saudi Arabia',
    'united arab emirates': 'United Arab Emirates',
    'uae': 'United Arab Emirates',
    'turkey': 'Turkey',
    'iran': 'Iran',
    'iraq': 'Iraq',
    'lebanon': 'Lebanon',
    'jordan': 'Jordan',
    'kuwait': 'Kuwait',
    'qatar': 'Qatar',
    'oman': 'Oman',
    'bahrain': 'Bahrain',
    'afghanistan': 'Afghanistan',
    'nepal': 'Nepal',
    'sri lanka': 'Sri Lanka',
    'myanmar': 'Myanmar',
    'cambodia': 'Cambodia',
    'laos': 'Laos',
    'mongolia': 'Mongolia',
    'kazakhstan': 'Kazakhstan',
    'uzbekistan': 'Uzbekistan',
    'south africa': 'South Africa',
    'egypt': 'Egypt',
    'nigeria': 'Nigeria',
    'kenya': 'Kenya',
    'ethiopia': 'Ethiopia',
    'ghana': 'Ghana',
    'tanzania': 'Tanzania',
    'uganda': 'Uganda',
    'morocco': 'Morocco',
    'algeria': 'Algeria',
    'tunisia': 'Tunisia',
    'libya': 'Libya',
    'sudan': 'Sudan',
    'senegal': 'Senegal',
    'cameroon': 'Cameroon',
    'ivory coast': 'Ivory Coast',
    'madagascar': 'Madagascar',
    'mali': 'Mali',
    'burkina faso': 'Burkina Faso',
    'niger': 'Niger',
    'mozambique': 'Mozambique',
    'malawi': 'Malawi',
    'zambia': 'Zambia',
    'zimbabwe': 'Zimbabwe',
    'botswana': 'Botswana',
    'namibia': 'Namibia',
    'rwanda': 'Rwanda',
    'burundi': 'Burundi',
    'somalia': 'Somalia',
    'angola': 'Angola',
    'congo': 'Congo',
    'brazil': 'Brazil',
    'argentina': 'Argentina',
    'chile': 'Chile',
    'colombia': 'Colombia',
    'peru': 'Peru',
    'venezuela': 'Venezuela',
    'ecuador': 'Ecuador',
    'bolivia': 'Bolivia',
    'paraguay': 'Paraguay',
    'uruguay': 'Uruguay',
    'guyana': 'Guyana',
    'suriname': 'Suriname',
    'australia': 'Australia',
    'new zealand': 'New Zealand',
    'fiji': 'Fiji',
    'papua new guinea': 'Papua New Guinea',
    'samoa': 'Samoa',
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
    Hiérarchie stricte pour éviter ambiguïté.
    
    Args:
        affiliation: Texte de l'affiliation
        
    Returns:
        Nom du pays normalisé ou None si non trouvé
    """
    if not affiliation:
        return None
    
    affiliation_lower = affiliation.lower()
    # Compute leading whitespace length to detect tokens at the very start
    leading_ws_len = len(affiliation_lower) - len(affiliation_lower.lstrip())
    
    # ════════════════════════════════════════════════════════════
    # PRIORITÉ 1 : PAYS EXPLICITE EN FIN DE CHAÎNE (99% des cas)
    # ════════════════════════════════════════════════════════════
    # Format: "Ville, Pays." ou "Université, Pays"
    # Cette est LA source de vérité principale
    for pattern in COUNTRY_PATTERNS:
        match = re.search(pattern, affiliation)
        if match:
            country_text = normalize_country(match.group(1))
            # Validation stricte: le pays trouvé DOIT être dans nos mappings
            if country_text in COUNTRY_TO_REGION:
                return country_text
            # Essayer aussi en TLD si c'est court (ex: 'uk' au lieu de 'united kingdom')
            if country_text in TLD_TO_COUNTRY:
                return TLD_TO_COUNTRY[country_text]
    
    # ════════════════════════════════════════════════════════════
    # PRIORITÉ 2 : NOM D'UNIVERSITÉ CONNU (très fiable)
    # ════════════════════════════════════════════════════════════
    for uni, country in UNIVERSITY_TO_COUNTRY.items():
         if uni in affiliation_lower:
            return country
    
    # ════════════════════════════════════════════════════════════
    # PRIORITÉ 3 : EXTENSION EMAIL / TLD (fiable)
    # ════════════════════════════════════════════════════════════
    email_match = re.search(r'@[a-zA-Z0-9.-]+\.([a-z]{2,3})\b', affiliation_lower)
    if email_match:
        tld = email_match.group(1)
        if tld in TLD_TO_COUNTRY:
            return TLD_TO_COUNTRY[tld]
    
    # ════════════════════════════════════════════════════════════
    # PRIORITÉ 4 : NOM DE VILLE CONNU (modéré)
    # ════════════════════════════════════════════════════════════
    # Iterate cities and ensure the match does not occur at the very start
    for city, country in CITY_TO_COUNTRY.items():
        pattern = re.compile(r'\b' + re.escape(city) + r'\b')
        for m in pattern.finditer(affiliation_lower):
            # Skip matches that start at the beginning of the affiliation (after leading spaces)
            if m.start() <= leading_ws_len:
                continue
            return country
    
    # ════════════════════════════════════════════════════════════
    # PRIORITÉ 5 : TERRITOIRES FRANÇAIS (spécifique)
    # ════════════════════════════════════════════════════════════
    for territory in FRANCE_TERRITORIES:
        if territory in affiliation_lower:
            return 'france'

    # ════════════════════════════════════════════════════════════
    # PRIORITÉ 6 : RECHERCHE FLOUE DE NOM DE PAYS (fallback)
    # ════════════════════════════════════════════════════════════
    for country in COUNTRY_TO_REGION.keys():
        idx = affiliation_lower.find(country)
        if idx != -1 and idx > leading_ws_len:
            return country
    
    return None


def get_country_name(affiliation: str) -> str:
    """
    Retourne le nom du pays lisible depuis une affiliation.
    
    Args:
        affiliation: Texte de l'affiliation de l'auteur
        
    Returns:
        Nom du pays en format lisible ou chaîne vide
    """
    country = extract_country_from_affiliation(affiliation)
    if country:
        return COUNTRY_DISPLAY_NAMES.get(country, country.title())
    return ''


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


def is_france_affiliation(affiliation: str) -> bool:
    """
    Vérifie si une affiliation correspond à la France ou un territoire français.
    
    Args:
        affiliation: Texte de l'affiliation de l'auteur
        
    Returns:
        True si l'affiliation est en France ou territoire français
    """
    if not affiliation:
        return False
    
    affiliation_lower = affiliation.lower()
    
    # Vérifier les territoires français
    for territory in FRANCE_TERRITORIES:
        if territory in affiliation_lower:
            return True
    
    return False


def get_country_code(affiliation: str) -> str:
    """
    Retourne le code pays normalisé depuis une affiliation.
    
    Args:
        affiliation: Texte de l'affiliation de l'auteur
        
    Returns:
        Code pays normalisé ('france', 'usa', etc.) ou chaîne vide
    """
    country = extract_country_from_affiliation(affiliation)
    return country if country else ''
