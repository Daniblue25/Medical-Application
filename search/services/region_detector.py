"""
Module pour détecter la région géographique à partir de l'affiliation des auteurs.
Analyse l'affiliation du dernier auteur pour déterminer le pays et la région.
"""

import re
from typing import Optional


# ════════════════════════════════════════════════════════════════════════════════
# MAPPING EXHAUSTIF : tous les pays du monde (ONU + observateurs + territoires)
# → région géographique.  ~250 entrées + alias courants.
# ════════════════════════════════════════════════════════════════════════════════
COUNTRY_TO_REGION = {
    # ── North America & Central America & Caribbean ─────────────────────────
    'united states': 'north_america',
    'usa': 'north_america',
    'us': 'north_america',
    'u.s.a.': 'north_america',
    'canada': 'north_america',
    'mexico': 'north_america',
    'guatemala': 'north_america',
    'honduras': 'north_america',
    'el salvador': 'north_america',
    'nicaragua': 'north_america',
    'costa rica': 'north_america',
    'panama': 'north_america',
    'cuba': 'north_america',
    'jamaica': 'north_america',
    'haiti': 'north_america',
    'dominican republic': 'north_america',
    'trinidad and tobago': 'north_america',
    'barbados': 'north_america',
    'bahamas': 'north_america',
    'belize': 'north_america',
    'antigua and barbuda': 'north_america',
    'dominica': 'north_america',
    'grenada': 'north_america',
    'saint kitts and nevis': 'north_america',
    'saint lucia': 'north_america',
    'saint vincent and the grenadines': 'north_america',
    'puerto rico': 'north_america',

    # ── South America ───────────────────────────────────────────────────────
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
    'french guiana': 'south_america',

    # ── Europe ──────────────────────────────────────────────────────────────
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
    'czechia': 'europe',
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
    'russian federation': 'europe',
    'ukraine': 'europe',
    'turkey': 'europe',
    'albania': 'europe',
    'andorra': 'europe',
    'armenia': 'europe',
    'azerbaijan': 'europe',
    'belarus': 'europe',
    'bosnia and herzegovina': 'europe',
    'cyprus': 'europe',
    'georgia': 'europe',
    'kosovo': 'europe',
    'liechtenstein': 'europe',
    'malta': 'europe',
    'moldova': 'europe',
    'republic of moldova': 'europe',
    'monaco': 'europe',
    'montenegro': 'europe',
    'north macedonia': 'europe',
    'macedonia': 'europe',
    'san marino': 'europe',
    'vatican': 'europe',
    'holy see': 'europe',

    # ── Asia (East, South-East, South, Central) ─────────────────────────────
    'china': 'asia',
    "people's republic of china": 'asia',
    'japan': 'asia',
    'south korea': 'asia',
    'republic of korea': 'asia',
    'korea': 'asia',
    'north korea': 'asia',
    'india': 'asia',
    'singapore': 'asia',
    'hong kong': 'asia',
    'taiwan': 'asia',
    'republic of china': 'asia',
    'thailand': 'asia',
    'malaysia': 'asia',
    'indonesia': 'asia',
    'philippines': 'asia',
    'vietnam': 'asia',
    'viet nam': 'asia',
    'pakistan': 'asia',
    'bangladesh': 'asia',
    'iran': 'asia',
    'iraq': 'asia',
    'israel': 'asia',
    'saudi arabia': 'asia',
    'united arab emirates': 'asia',
    'uae': 'asia',
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
    'burma': 'asia',
    'cambodia': 'asia',
    'laos': 'asia',
    'mongolia': 'asia',
    'kazakhstan': 'asia',
    'uzbekistan': 'asia',
    'turkmenistan': 'asia',
    'tajikistan': 'asia',
    'kyrgyzstan': 'asia',
    'brunei': 'asia',
    'bhutan': 'asia',
    'maldives': 'asia',
    'timor-leste': 'asia',
    'east timor': 'asia',
    'palestine': 'asia',
    'palestinian territory': 'asia',
    'syria': 'asia',
    'syrian arab republic': 'asia',
    'yemen': 'asia',

    # ── Africa ──────────────────────────────────────────────────────────────
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
    'south sudan': 'africa',
    'senegal': 'africa',
    'cameroon': 'africa',
    'ivory coast': 'africa',
    "cote d'ivoire": 'africa',
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
    'democratic republic of the congo': 'africa',
    'republic of the congo': 'africa',
    'benin': 'africa',
    'togo': 'africa',
    'sierra leone': 'africa',
    'liberia': 'africa',
    'central african republic': 'africa',
    'chad': 'africa',
    'eritrea': 'africa',
    'djibouti': 'africa',
    'equatorial guinea': 'africa',
    'gabon': 'africa',
    'gambia': 'africa',
    'the gambia': 'africa',
    'guinea': 'africa',
    'guinea-bissau': 'africa',
    'lesotho': 'africa',
    'mauritania': 'africa',
    'mauritius': 'africa',
    'seychelles': 'africa',
    'cape verde': 'africa',
    'cabo verde': 'africa',
    'sao tome and principe': 'africa',
    'comoros': 'africa',
    'eswatini': 'africa',
    'swaziland': 'africa',

    # ── Oceania ─────────────────────────────────────────────────────────────
    'australia': 'oceania',
    'new zealand': 'oceania',
    'fiji': 'oceania',
    'papua new guinea': 'oceania',
    'samoa': 'oceania',
    'tonga': 'oceania',
    'vanuatu': 'oceania',
    'solomon islands': 'oceania',
    'kiribati': 'oceania',
    'micronesia': 'oceania',
    'marshall islands': 'oceania',
    'palau': 'oceania',
    'nauru': 'oceania',
    'tuvalu': 'oceania',
    'new caledonia': 'oceania',
    'french polynesia': 'oceania',
}

# ════════════════════════════════════════════════════════════════════════════════
# MAPPING VILLES → PAYS : capitales + villes médicales/universitaires majeures
# Utilisé en fallback (priorité 4) quand le pays n'est pas explicite.
# ~250 entrées couvrant toutes les régions du monde.
# ════════════════════════════════════════════════════════════════════════════════
CITY_TO_COUNTRY = {
    # ── USA (grandes villes médicales) ──────────────────────────────────────
    'new york': 'usa', 'boston': 'usa', 'chicago': 'usa',
    'houston': 'usa', 'philadelphia': 'usa', 'san francisco': 'usa',
    'los angeles': 'usa', 'san diego': 'usa', 'dallas': 'usa',
    'atlanta': 'usa', 'miami': 'usa', 'seattle': 'usa',
    'washington': 'usa', 'baltimore': 'usa', 'detroit': 'usa',
    'denver': 'usa', 'pittsburgh': 'usa', 'cleveland': 'usa',
    'st. louis': 'usa', 'minneapolis': 'usa', 'nashville': 'usa',
    'rochester': 'usa', 'ann arbor': 'usa', 'durham': 'usa',
    'new haven': 'usa', 'chapel hill': 'usa', 'indianapolis': 'usa',

    # ── Canada ──────────────────────────────────────────────────────────────
    'toronto': 'canada', 'montreal': 'canada', 'vancouver': 'canada',
    'ottawa': 'canada', 'calgary': 'canada', 'edmonton': 'canada',
    'quebec': 'canada', 'winnipeg': 'canada', 'halifax': 'canada',

    # ── Mexico & Central America & Caribbean ────────────────────────────────
    'mexico city': 'mexico', 'guadalajara': 'mexico', 'monterrey': 'mexico',
    'guatemala city': 'guatemala', 'tegucigalpa': 'honduras',
    'san salvador': 'el salvador', 'managua': 'nicaragua',
    'san jose': 'costa rica', 'panama city': 'panama',
    'havana': 'cuba', 'kingston': 'jamaica',
    'port-au-prince': 'haiti', 'santo domingo': 'dominican republic',
    'port of spain': 'trinidad and tobago', 'nassau': 'bahamas',

    # ── South America ───────────────────────────────────────────────────────
    'sao paulo': 'brazil', 'rio de janeiro': 'brazil', 'brasilia': 'brazil',
    'buenos aires': 'argentina', 'santiago': 'chile',
    'bogota': 'colombia', 'medellin': 'colombia',
    'lima': 'peru', 'caracas': 'venezuela', 'quito': 'ecuador',
    'la paz': 'bolivia', 'asuncion': 'paraguay',
    'montevideo': 'uruguay', 'georgetown': 'guyana', 'paramaribo': 'suriname',

    # ── UK ──────────────────────────────────────────────────────────────────
    'london': 'uk', 'manchester': 'uk', 'birmingham': 'uk',
    'glasgow': 'uk', 'edinburgh': 'uk', 'liverpool': 'uk',
    'leeds': 'uk', 'oxford': 'uk', 'cambridge': 'uk',
    'bristol': 'uk', 'sheffield': 'uk', 'nottingham': 'uk',
    'cardiff': 'uk', 'belfast': 'uk', 'southampton': 'uk',

    # ── France (villes CHU) ─────────────────────────────────────────────────
    'paris': 'france', 'lyon': 'france', 'marseille': 'france',
    'toulouse': 'france', 'bordeaux': 'france', 'lille': 'france',
    'nice': 'france', 'nantes': 'france', 'strasbourg': 'france',
    'montpellier': 'france', 'rennes': 'france', 'grenoble': 'france',
    'rouen': 'france', 'clermont-ferrand': 'france', 'nancy': 'france',
    'dijon': 'france', 'tours': 'france', 'angers': 'france',
    'brest': 'france', 'caen': 'france', 'reims': 'france',
    'metz': 'france', 'amiens': 'france', 'besançon': 'france',
    'limoges': 'france', 'poitiers': 'france', 'saint-etienne': 'france',
    'creteil': 'france', 'bobigny': 'france', 'boulogne-billancourt': 'france',

    # ── Germany ─────────────────────────────────────────────────────────────
    'berlin': 'germany', 'munich': 'germany', 'hamburg': 'germany',
    'frankfurt': 'germany', 'heidelberg': 'germany', 'cologne': 'germany',
    'dusseldorf': 'germany', 'tubingen': 'germany', 'freiburg': 'germany',
    'essen': 'germany', 'hannover': 'germany', 'leipzig': 'germany',
    'dresden': 'germany', 'bonn': 'germany',

    # ── Italy ───────────────────────────────────────────────────────────────
    'rome': 'italy', 'milan': 'italy', 'naples': 'italy',
    'turin': 'italy', 'bologna': 'italy', 'florence': 'italy',
    'padua': 'italy', 'genoa': 'italy', 'verona': 'italy',

    # ── Spain ───────────────────────────────────────────────────────────────
    'madrid': 'spain', 'barcelona': 'spain', 'valencia': 'spain',
    'seville': 'spain', 'bilbao': 'spain', 'malaga': 'spain',

    # ── Netherlands ─────────────────────────────────────────────────────────
    'amsterdam': 'netherlands', 'rotterdam': 'netherlands',
    'utrecht': 'netherlands', 'leiden': 'netherlands',
    'groningen': 'netherlands', 'nijmegen': 'netherlands',

    # ── Belgium ─────────────────────────────────────────────────────────────
    'brussels': 'belgium', 'leuven': 'belgium',
    'ghent': 'belgium', 'antwerp': 'belgium', 'liege': 'belgium',

    # ── Switzerland ─────────────────────────────────────────────────────────
    'zurich': 'switzerland', 'geneva': 'switzerland',
    'bern': 'switzerland', 'basel': 'switzerland', 'lausanne': 'switzerland',

    # ── Scandinavia ─────────────────────────────────────────────────────────
    'stockholm': 'sweden', 'gothenburg': 'sweden', 'malmo': 'sweden', 'uppsala': 'sweden',
    'oslo': 'norway', 'bergen': 'norway', 'trondheim': 'norway',
    'copenhagen': 'denmark', 'aarhus': 'denmark',
    'helsinki': 'finland', 'turku': 'finland', 'tampere': 'finland',
    'reykjavik': 'iceland',

    # ── Eastern Europe ──────────────────────────────────────────────────────
    'warsaw': 'poland', 'krakow': 'poland', 'wroclaw': 'poland',
    'prague': 'czech republic', 'brno': 'czech republic',
    'budapest': 'hungary', 'vienna': 'austria', 'innsbruck': 'austria', 'graz': 'austria',
    'bucharest': 'romania', 'cluj-napoca': 'romania',
    'zagreb': 'croatia', 'belgrade': 'serbia', 'sofia': 'bulgaria',
    'bratislava': 'slovakia', 'ljubljana': 'slovenia',
    'moscow': 'russia', 'saint petersburg': 'russia',
    'kyiv': 'ukraine', 'kharkiv': 'ukraine',
    'vilnius': 'lithuania', 'riga': 'latvia', 'tallinn': 'estonia',
    'minsk': 'belarus', 'chisinau': 'moldova',

    # ── Southeast Europe & Mediterranean ────────────────────────────────────
    'lisbon': 'portugal', 'porto': 'portugal', 'coimbra': 'portugal',
    'athens': 'greece', 'thessaloniki': 'greece',
    'dublin': 'ireland', 'cork': 'ireland', 'galway': 'ireland',
    'luxembourg': 'luxembourg',
    'istanbul': 'turkey', 'ankara': 'turkey', 'izmir': 'turkey',
    'tirana': 'albania', 'nicosia': 'cyprus',
    'sarajevo': 'bosnia and herzegovina', 'skopje': 'north macedonia',
    'podgorica': 'montenegro', 'pristina': 'kosovo',
    'valletta': 'malta', 'tbilisi': 'georgia',
    'yerevan': 'armenia', 'baku': 'azerbaijan',

    # ── Japan ───────────────────────────────────────────────────────────────
    'tokyo': 'japan', 'osaka': 'japan', 'kyoto': 'japan',
    'nagoya': 'japan', 'kobe': 'japan', 'yokohama': 'japan',
    'sendai': 'japan', 'sapporo': 'japan', 'fukuoka': 'japan',

    # ── China ───────────────────────────────────────────────────────────────
    'beijing': 'china', 'shanghai': 'china', 'hong kong': 'china',
    'guangzhou': 'china', 'shenzhen': 'china', 'chengdu': 'china',
    'wuhan': 'china', 'nanjing': 'china', 'hangzhou': 'china',
    'xi\'an': 'china', 'tianjin': 'china', 'changsha': 'china',

    # ── South Korea ─────────────────────────────────────────────────────────
    'seoul': 'south korea', 'busan': 'south korea', 'daegu': 'south korea',
    'incheon': 'south korea', 'daejeon': 'south korea',

    # ── India ───────────────────────────────────────────────────────────────
    'new delhi': 'india', 'mumbai': 'india', 'bangalore': 'india',
    'chennai': 'india', 'kolkata': 'india', 'hyderabad': 'india',
    'pune': 'india', 'ahmedabad': 'india', 'chandigarh': 'india',

    # ── Southeast Asia ──────────────────────────────────────────────────────
    'singapore': 'singapore', 'taipei': 'taiwan',
    'bangkok': 'thailand', 'chiang mai': 'thailand',
    'kuala lumpur': 'malaysia', 'jakarta': 'indonesia',
    'manila': 'philippines', 'cebu': 'philippines',
    'hanoi': 'vietnam', 'ho chi minh city': 'vietnam',
    'phnom penh': 'cambodia', 'vientiane': 'laos',
    'yangon': 'myanmar', 'naypyidaw': 'myanmar',
    'bandar seri begawan': 'brunei', 'dili': 'timor-leste',

    # ── Central Asia ────────────────────────────────────────────────────────
    'nur-sultan': 'kazakhstan', 'astana': 'kazakhstan', 'almaty': 'kazakhstan',
    'tashkent': 'uzbekistan', 'bishkek': 'kyrgyzstan',
    'dushanbe': 'tajikistan', 'ashgabat': 'turkmenistan',
    'ulaanbaatar': 'mongolia',

    # ── Middle East ─────────────────────────────────────────────────────────
    'tehran': 'iran', 'isfahan': 'iran', 'shiraz': 'iran',
    'baghdad': 'iraq', 'erbil': 'iraq',
    'tel aviv': 'israel', 'jerusalem': 'israel', 'haifa': 'israel',
    'riyadh': 'saudi arabia', 'jeddah': 'saudi arabia',
    'dubai': 'united arab emirates', 'abu dhabi': 'united arab emirates',
    'beirut': 'lebanon', 'amman': 'jordan',
    'kuwait city': 'kuwait', 'doha': 'qatar',
    'muscat': 'oman', 'manama': 'bahrain',
    'damascus': 'syria', 'sanaa': 'yemen',
    'kabul': 'afghanistan', 'ramallah': 'palestine',

    # ── South Asia ──────────────────────────────────────────────────────────
    'islamabad': 'pakistan', 'karachi': 'pakistan', 'lahore': 'pakistan',
    'dhaka': 'bangladesh', 'chittagong': 'bangladesh',
    'colombo': 'sri lanka', 'kathmandu': 'nepal',
    'thimphu': 'bhutan', 'male': 'maldives',

    # ── Africa — North ──────────────────────────────────────────────────────
    'cairo': 'egypt', 'alexandria': 'egypt',
    'casablanca': 'morocco', 'rabat': 'morocco',
    'algiers': 'algeria', 'tunis': 'tunisia',
    'tripoli': 'libya', 'khartoum': 'sudan',

    # ── Africa — West ──────────────────────────────────────────────────────
    'lagos': 'nigeria', 'abuja': 'nigeria', 'ibadan': 'nigeria',
    'accra': 'ghana', 'kumasi': 'ghana',
    'dakar': 'senegal', 'abidjan': 'ivory coast',
    'douala': 'cameroon', 'yaounde': 'cameroon',
    'bamako': 'mali', 'ouagadougou': 'burkina faso',
    'niamey': 'niger', 'conakry': 'guinea',
    'freetown': 'sierra leone', 'monrovia': 'liberia',
    'cotonou': 'benin', 'lome': 'togo',
    'banjul': 'gambia', 'bissau': 'guinea-bissau',
    'nouakchott': 'mauritania', 'praia': 'cape verde',

    # ── Africa — East ──────────────────────────────────────────────────────
    'nairobi': 'kenya', 'mombasa': 'kenya',
    'addis ababa': 'ethiopia', 'dar es salaam': 'tanzania',
    'kampala': 'uganda', 'kigali': 'rwanda',
    'bujumbura': 'burundi', 'mogadishu': 'somalia',
    'asmara': 'eritrea', 'djibouti': 'djibouti',
    'juba': 'south sudan', 'antananarivo': 'madagascar',

    # ── Africa — Southern ───────────────────────────────────────────────────
    'cape town': 'south africa', 'johannesburg': 'south africa',
    'pretoria': 'south africa', 'durban': 'south africa',
    'maputo': 'mozambique', 'lilongwe': 'malawi', 'blantyre': 'malawi',
    'lusaka': 'zambia', 'harare': 'zimbabwe',
    'gaborone': 'botswana', 'windhoek': 'namibia',
    'luanda': 'angola', 'mbabane': 'eswatini',
    'maseru': 'lesotho', 'port louis': 'mauritius',

    # ── Africa — Central ────────────────────────────────────────────────────
    'kinshasa': 'congo', 'brazzaville': 'congo',
    'libreville': 'gabon', 'bangui': 'central african republic',
    "n'djamena": 'chad', 'malabo': 'equatorial guinea',

    # ── Oceania ─────────────────────────────────────────────────────────────
    'sydney': 'australia', 'melbourne': 'australia', 'brisbane': 'australia',
    'perth': 'australia', 'adelaide': 'australia', 'canberra': 'australia',
    'auckland': 'new zealand', 'wellington': 'new zealand', 'christchurch': 'new zealand',
    'suva': 'fiji', 'port moresby': 'papua new guinea',
    'apia': 'samoa', 'port vila': 'vanuatu', 'honiara': 'solomon islands',
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

# ════════════════════════════════════════════════════════════════════════════════
# MAPPING TLD → Pays (ccTLD ISO 3166-1 alpha-2 + TLD génériques significatifs)
# ════════════════════════════════════════════════════════════════════════════════
TLD_TO_COUNTRY = {
    # ── Generic / special TLDs ──
    'gov': 'usa',
    'edu': 'usa',       # vast majority is US; non-US universities use .ac.uk, .edu.au, etc.
    'mil': 'usa',

    # ── Europe ──
    'al': 'albania', 'ad': 'andorra', 'am': 'armenia', 'at': 'austria',
    'az': 'azerbaijan', 'by': 'belarus', 'be': 'belgium',
    'ba': 'bosnia and herzegovina', 'bg': 'bulgaria', 'hr': 'croatia',
    'cy': 'cyprus', 'cz': 'czech republic', 'dk': 'denmark', 'ee': 'estonia',
    'fi': 'finland', 'fr': 'france', 'ge': 'georgia', 'de': 'germany',
    'gr': 'greece', 'hu': 'hungary', 'is': 'iceland', 'ie': 'ireland',
    'it': 'italy', 'xk': 'kosovo', 'lv': 'latvia', 'li': 'liechtenstein',
    'lt': 'lithuania', 'lu': 'luxembourg', 'mk': 'north macedonia',
    'mt': 'malta', 'md': 'moldova', 'mc': 'monaco', 'me': 'montenegro',
    'nl': 'netherlands', 'no': 'norway', 'pl': 'poland', 'pt': 'portugal',
    'ro': 'romania', 'ru': 'russia', 'sm': 'san marino', 'rs': 'serbia',
    'sk': 'slovakia', 'si': 'slovenia', 'es': 'spain', 'se': 'sweden',
    'ch': 'switzerland', 'tr': 'turkey', 'ua': 'ukraine', 'uk': 'united kingdom',
    'va': 'vatican',

    # ── Americas ──
    'us': 'usa', 'ca': 'canada', 'mx': 'mexico',
    'gt': 'guatemala', 'hn': 'honduras', 'sv': 'el salvador',
    'ni': 'nicaragua', 'cr': 'costa rica', 'pa': 'panama',
    'cu': 'cuba', 'jm': 'jamaica', 'ht': 'haiti', 'do': 'dominican republic',
    'tt': 'trinidad and tobago', 'bb': 'barbados', 'bs': 'bahamas',
    'bz': 'belize', 'pr': 'puerto rico',
    'br': 'brazil', 'ar': 'argentina', 'cl': 'chile', 'co': 'colombia',
    'pe': 'peru', 've': 'venezuela', 'ec': 'ecuador', 'bo': 'bolivia',
    'py': 'paraguay', 'uy': 'uruguay', 'gy': 'guyana', 'sr': 'suriname',

    # ── Asia & Middle East ──
    'cn': 'china', 'jp': 'japan', 'kr': 'south korea', 'kp': 'north korea',
    'in': 'india', 'sg': 'singapore', 'hk': 'hong kong', 'tw': 'taiwan',
    'th': 'thailand', 'my': 'malaysia', 'id': 'indonesia', 'ph': 'philippines',
    'vn': 'vietnam', 'pk': 'pakistan', 'bd': 'bangladesh', 'ir': 'iran',
    'iq': 'iraq', 'il': 'israel', 'sa': 'saudi arabia', 'ae': 'united arab emirates',
    'lb': 'lebanon', 'jo': 'jordan', 'kw': 'kuwait', 'qa': 'qatar',
    'om': 'oman', 'bh': 'bahrain', 'af': 'afghanistan', 'np': 'nepal',
    'lk': 'sri lanka', 'mm': 'myanmar', 'kh': 'cambodia', 'la': 'laos',
    'mn': 'mongolia', 'kz': 'kazakhstan', 'uz': 'uzbekistan',
    'tm': 'turkmenistan', 'tj': 'tajikistan', 'kg': 'kyrgyzstan',
    'bn': 'brunei', 'bt': 'bhutan', 'mv': 'maldives', 'tl': 'timor-leste',
    'ps': 'palestine', 'sy': 'syria', 'ye': 'yemen',

    # ── Africa ──
    'za': 'south africa', 'eg': 'egypt', 'ng': 'nigeria', 'ke': 'kenya',
    'et': 'ethiopia', 'gh': 'ghana', 'tz': 'tanzania', 'ug': 'uganda',
    'ma': 'morocco', 'dz': 'algeria', 'tn': 'tunisia', 'ly': 'libya',
    'sd': 'sudan', 'ss': 'south sudan', 'sn': 'senegal', 'cm': 'cameroon',
    'ci': 'ivory coast', 'mg': 'madagascar', 'ml': 'mali', 'bf': 'burkina faso',
    'ne': 'niger', 'mz': 'mozambique', 'mw': 'malawi', 'zm': 'zambia',
    'zw': 'zimbabwe', 'bw': 'botswana', 'na': 'namibia', 'rw': 'rwanda',
    'bi': 'burundi', 'so': 'somalia', 'ao': 'angola', 'cd': 'congo',
    'cg': 'congo', 'bj': 'benin', 'tg': 'togo', 'sl': 'sierra leone',
    'lr': 'liberia', 'cf': 'central african republic', 'td': 'chad',
    'er': 'eritrea', 'dj': 'djibouti', 'gq': 'equatorial guinea',
    'ga': 'gabon', 'gm': 'gambia', 'gn': 'guinea', 'gw': 'guinea-bissau',
    'ls': 'lesotho', 'mr': 'mauritania', 'mu': 'mauritius', 'sc': 'seychelles',
    'cv': 'cape verde', 'st': 'sao tome and principe', 'km': 'comoros',
    'sz': 'eswatini',

    # ── Oceania ──
    'au': 'australia', 'nz': 'new zealand', 'fj': 'fiji',
    'pg': 'papua new guinea', 'ws': 'samoa', 'to': 'tonga', 'vu': 'vanuatu',
    'sb': 'solomon islands', 'ki': 'kiribati', 'fm': 'micronesia',
    'mh': 'marshall islands', 'pw': 'palau', 'nr': 'nauru', 'tv': 'tuvalu',
    'nc': 'new caledonia', 'pf': 'french polynesia',
}

# ════════════════════════════════════════════════════════════════════════════════
# Abréviations d'états US — collisions fréquentes avec les TLD de pays
# (MA → Morocco, MD → Moldova, NC → New Caledonia, CA → Canada, PA → Panama, etc.)
# ════════════════════════════════════════════════════════════════════════════════
US_STATE_ABBREVIATIONS = {
    'al', 'ak', 'az', 'ar', 'ca', 'co', 'ct', 'de', 'fl', 'ga',
    'hi', 'id', 'il', 'in', 'ia', 'ks', 'ky', 'la', 'ma', 'md',
    'me', 'mi', 'mn', 'ms', 'mo', 'mt', 'ne', 'nv', 'nh', 'nj',
    'nm', 'ny', 'nc', 'nd', 'oh', 'ok', 'or', 'pa', 'ri', 'sc',
    'sd', 'tn', 'tx', 'ut', 'vt', 'va', 'wa', 'wv', 'wi', 'wy',
    'dc',  # District of Columbia
}

US_STATE_NAMES = {
    'alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado',
    'connecticut', 'delaware', 'florida', 'georgia', 'hawaii', 'idaho',
    'illinois', 'indiana', 'iowa', 'kansas', 'kentucky', 'louisiana',
    'maine', 'maryland', 'massachusetts', 'michigan', 'minnesota',
    'mississippi', 'missouri', 'montana', 'nebraska', 'nevada',
    'new hampshire', 'new jersey', 'new mexico', 'new york',
    'north carolina', 'north dakota', 'ohio', 'oklahoma', 'oregon',
    'pennsylvania', 'rhode island', 'south carolina', 'south dakota',
    'tennessee', 'texas', 'utah', 'vermont', 'virginia', 'washington',
    'west virginia', 'wisconsin', 'wyoming', 'district of columbia',
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
    "nanjing university": "china",
    "sun yat-sen": "china",
    "wuhan university": "china",
    "sichuan university": "china",
    "chinese academy of sciences": "china",
    "west china hospital": "china",
    "huazhong university": "china",
    "zhongshan hospital": "china",
    "tongji university": "china",
    
    # Japan
    "tokyo university": "japan",
    "kyoto university": "japan",
    "osaka university": "japan",
    "tohoku university": "japan",
    "keio university": "japan",
    "nagoya university": "japan",
    "hokkaido university": "japan",
    "kyushu university": "japan",
    "jikei university": "japan",
    "juntendo university": "japan",
    
    # Germany
    "charité": "germany",
    "charite": "germany",
    "heidelberg university": "germany",
    "lmu munich": "germany",
    "tum": "germany",
    "technische universität münchen": "germany",
    "university of freiburg": "germany",
    "university of tübingen": "germany",
    "university of göttingen": "germany",
    "humboldt": "germany",
    "max planck": "germany",
    "rwth aachen": "germany",
    "hannover medical school": "germany",
    "university hospital hamburg": "germany",
    "university of bonn": "germany",
    "university of cologne": "germany",
    "universitätsklinikum": "germany",
    "universitaetsklinikum": "germany",
    "dkfz": "germany",
    
    # Italy
    "università di": "italy",
    "universita di": "italy",
    "sapienza": "italy",
    "politecnico di milano": "italy",
    "university of bologna": "italy",
    "university of padova": "italy",
    "university of milan": "italy",
    "university of florence": "italy",
    "university of turin": "italy",
    "university of naples": "italy",
    "university of rome": "italy",
    "humanitas": "italy",
    "san raffaele": "italy",
    "istituto nazionale": "italy",
    "irccs": "italy",
    "gemelli": "italy",
    
    # Spain
    "universidad de": "spain",
    "universitat de": "spain",
    "hospital clínic": "spain",
    "hospital clinic": "spain",
    "hospital la paz": "spain",
    "hospital val d'hebron": "spain",
    "hospital gregorio marañón": "spain",
    "university of barcelona": "spain",
    "university of navarra": "spain",
    "cnic": "spain",
    "cnio": "spain",
    "hospital ramón y cajal": "spain",
    
    # Netherlands
    "erasmus mc": "netherlands",
    "erasmus university": "netherlands",
    "leiden university": "netherlands",
    "university of amsterdam": "netherlands",
    "umc utrecht": "netherlands",
    "radboud": "netherlands",
    "maastricht university": "netherlands",
    "vrije universiteit": "netherlands",
    "groningen university": "netherlands",
    "vu amsterdam": "netherlands",
    "university medical center": "netherlands",
    "lumc": "netherlands",
    "amc amsterdam": "netherlands",
    
    # Sweden
    "karolinska": "sweden",
    "uppsala university": "sweden",
    "lund university": "sweden",
    "gothenburg university": "sweden",
    "stockholm university": "sweden",
    "sahlgrenska": "sweden",
    "umeå university": "sweden",
    
    # Denmark
    "copenhagen university": "denmark",
    "aarhus university": "denmark",
    "rigshospitalet": "denmark",
    "odense university": "denmark",
    "aalborg university": "denmark",
    
    # Norway
    "university of oslo": "norway",
    "ntnu": "norway",
    "haukeland university hospital": "norway",
    "university of bergen": "norway",
    "oslo university hospital": "norway",
    
    # Finland
    "university of helsinki": "finland",
    "university of turku": "finland",
    "university of tampere": "finland",
    "university of oulu": "finland",
    "hus helsinki university hospital": "finland",
    
    # Switzerland
    "eth zürich": "switzerland",
    "eth zurich": "switzerland",
    "epfl": "switzerland",
    "university of zurich": "switzerland",
    "university of bern": "switzerland",
    "university of geneva": "switzerland",
    "university of basel": "switzerland",
    "university of lausanne": "switzerland",
    "chuv": "switzerland",
    "inselspital": "switzerland",
    
    # Belgium
    "ku leuven": "belgium",
    "université libre de bruxelles": "belgium",
    "ulb": "belgium",
    "ucl louvain": "belgium",
    "university of ghent": "belgium",
    "university of antwerp": "belgium",
    "university of liège": "belgium",
    
    # Austria
    "medical university of vienna": "austria",
    "university of vienna": "austria",
    "medical university of graz": "austria",
    "university of innsbruck": "austria",
    
    # South Korea
    "seoul national university": "south korea",
    "yonsei university": "south korea",
    "samsung medical center": "south korea",
    "asan medical center": "south korea",
    "korea university": "south korea",
    "kaist": "south korea",
    "sungkyunkwan": "south korea",
    "severance hospital": "south korea",
    "catholic university of korea": "south korea",
    "kyung hee university": "south korea",
    
    # India
    "aiims": "india",
    "all india institute": "india",
    "iit": "india",
    "tata memorial": "india",
    "cmch vellore": "india",
    "pgimer": "india",
    "jipmer": "india",
    "nimhans": "india",
    "sgpgi": "india",
    "manipal": "india",
    "apollo hospital": "india",
    "fortis healthcare": "india",
    
    # Brazil
    "universidade de são paulo": "brazil",
    "universidade de sao paulo": "brazil",
    "usp": "brazil",
    "unicamp": "brazil",
    "ufrj": "brazil",
    "unifesp": "brazil",
    "fiocruz": "brazil",
    "hospital albert einstein": "brazil",
    "hospital sírio-libanês": "brazil",
    "hospital das clínicas": "brazil",
    
    # Mexico
    "unam": "mexico",
    "instituto nacional de": "mexico",
    "tec de monterrey": "mexico",
    "hospital general de méxico": "mexico",
    
    # Argentina
    "university of buenos aires": "argentina",
    "uba": "argentina",
    "hospital italiano": "argentina",
    "fundación favaloro": "argentina",
    
    # Turkey
    "hacettepe": "turkey",
    "ankara university": "turkey",
    "istanbul university": "turkey",
    "marmara university": "turkey",
    "ege university": "turkey",
    "cerrahpaşa": "turkey",
    "cerrahpasa": "turkey",
    
    # Israel
    "hebrew university": "israel",
    "weizmann institute": "israel",
    "technion": "israel",
    "tel aviv university": "israel",
    "hadassah": "israel",
    "sheba medical center": "israel",
    "rabin medical center": "israel",
    "soroka": "israel",
    
    # Iran
    "tehran university": "iran",
    "shahid beheshti": "iran",
    "isfahan university": "iran",
    "mashhad university": "iran",
    "tabriz university": "iran",
    
    # Poland
    "jagiellonian university": "poland",
    "university of warsaw": "poland",
    "medical university of warsaw": "poland",
    "medical university of gdansk": "poland",
    "medical university of lodz": "poland",
    
    # Greece
    "university of athens": "greece",
    "aristotle university": "greece",
    "university of thessaloniki": "greece",
    "university of crete": "greece",
    
    # Portugal
    "university of lisbon": "portugal",
    "university of porto": "portugal",
    "university of coimbra": "portugal",
    
    # Ireland
    "trinity college dublin": "ireland",
    "university college dublin": "ireland",
    "royal college of surgeons in ireland": "ireland",
    "rcsi": "ireland",
    "university of galway": "ireland",
    
    # Singapore
    "national university of singapore": "singapore",
    "nus": "singapore",
    "nanyang technological": "singapore",
    "duke-nus": "singapore",
    "singapore general hospital": "singapore",
    
    # Taiwan
    "national taiwan university": "taiwan",
    "national cheng kung university": "taiwan",
    "taipei veterans general hospital": "taiwan",
    "chang gung": "taiwan",
    "china medical university, taichung": "taiwan",
    
    # Thailand
    "mahidol university": "thailand",
    "chulalongkorn": "thailand",
    "siriraj hospital": "thailand",
    "ramathibodi hospital": "thailand",
    
    # Saudi Arabia
    "king saud university": "saudi arabia",
    "king abdulaziz university": "saudi arabia",
    "king faisal specialist hospital": "saudi arabia",
    "kfshrc": "saudi arabia",
    "alfaisal university": "saudi arabia",
    
    # Egypt
    "cairo university": "egypt",
    "ain shams university": "egypt",
    "alexandria university": "egypt",
    "mansoura university": "egypt",
    
    # South Africa
    "university of cape town": "south africa",
    "university of witwatersrand": "south africa",
    "stellenbosch university": "south africa",
    "university of pretoria": "south africa",
    "university of kwazulu-natal": "south africa",
    
    # Nigeria
    "university of ibadan": "nigeria",
    "university of lagos": "nigeria",
    "obafemi awolowo university": "nigeria",
    
    # Kenya
    "university of nairobi": "kenya",
    "aga khan university hospital, nairobi": "kenya",
    
    # New Zealand
    "university of auckland": "new zealand",
    "university of otago": "new zealand",
    
    # Malaysia
    "university of malaya": "malaysia",
    "universiti kebangsaan malaysia": "malaysia",
    "universiti sains malaysia": "malaysia",
    
    # Colombia
    "universidad de los andes": "colombia",
    "universidad nacional de colombia": "colombia",
    "fundación santa fe de bogotá": "colombia",
    
    # Chile
    "universidad de chile": "chile",
    "pontificia universidad católica de chile": "chile",
    
    # Czech Republic
    "charles university": "czech republic",
    "masaryk university": "czech republic",
    
    # Hungary
    "semmelweis university": "hungary",
    "university of debrecen": "hungary",
    
    # Romania
    "university of bucharest": "romania",
    "carol davila university": "romania",
    
    # Pakistan
    "aga khan university": "pakistan",
    "university of health sciences, lahore": "pakistan",
    
    # Bangladesh
    "university of dhaka": "bangladesh",
    "bsmmu": "bangladesh",
    
    # Vietnam
    "hanoi medical university": "vietnam",
    "ho chi minh city university": "vietnam",
    
    # Philippines
    "university of the philippines": "philippines",
    "philippine general hospital": "philippines",
    
    # Indonesia
    "university of indonesia": "indonesia",
    "gadjah mada university": "indonesia",
}

# ════════════════════════════════════════════════════════════════════════════════
# COUNTRY_DISPLAY_NAMES — auto-generated from COUNTRY_TO_REGION
# Only overrides needed for names that don't title-case nicely.
# ════════════════════════════════════════════════════════════════════════════════
_DISPLAY_OVERRIDES = {
    'usa': 'United States',
    'us': 'United States',
    'u.s.a.': 'United States',
    'united states': 'United States',
    'uk': 'United Kingdom',
    'united kingdom': 'United Kingdom',
    'uae': 'United Arab Emirates',
    'united arab emirates': 'United Arab Emirates',
    "people's republic of china": 'China',
    'republic of korea': 'South Korea',
    'republic of china': 'Taiwan',
    'republic of moldova': 'Moldova',
    'republic of the congo': 'Republic of the Congo',
    'democratic republic of the congo': 'Democratic Republic of the Congo',
    'russian federation': 'Russia',
    'korean': 'South Korea',
    'korea': 'South Korea',
    'czech republic': 'Czech Republic',
    'czechia': 'Czech Republic',
    'bosnia and herzegovina': 'Bosnia and Herzegovina',
    'north macedonia': 'North Macedonia',
    'trinidad and tobago': 'Trinidad and Tobago',
    'antigua and barbuda': 'Antigua and Barbuda',
    'saint kitts and nevis': 'Saint Kitts and Nevis',
    'saint vincent and the grenadines': 'Saint Vincent and the Grenadines',
    'dominican republic': 'Dominican Republic',
    'central african republic': 'Central African Republic',
    'sao tome and principe': 'São Tomé and Príncipe',
    'guinea-bissau': 'Guinea-Bissau',
    'timor-leste': 'Timor-Leste',
    'east timor': 'Timor-Leste',
    'south korea': 'South Korea',
    'north korea': 'North Korea',
    'south africa': 'South Africa',
    'south sudan': 'South Sudan',
    'sri lanka': 'Sri Lanka',
    'hong kong': 'Hong Kong',
    'burkina faso': 'Burkina Faso',
    'cabo verde': 'Cape Verde',
    'cape verde': 'Cape Verde',
    'ivory coast': "Côte d'Ivoire",
    "cote d'ivoire": "Côte d'Ivoire",
    'the gambia': 'Gambia',
    'papua new guinea': 'Papua New Guinea',
    'new zealand': 'New Zealand',
    'new caledonia': 'New Caledonia',
    'french polynesia': 'French Polynesia',
    'french guiana': 'French Guiana',
    'saudi arabia': 'Saudi Arabia',
    'san marino': 'San Marino',
    'holy see': 'Vatican City',
    'el salvador': 'El Salvador',
    'costa rica': 'Costa Rica',
    'puerto rico': 'Puerto Rico',
    'solomon islands': 'Solomon Islands',
    'marshall islands': 'Marshall Islands',
    'syrian arab republic': 'Syria',
    'palestinian territory': 'Palestine',
    'viet nam': 'Vietnam',
    'burma': 'Myanmar',
    'swaziland': 'Eswatini',
}

COUNTRY_DISPLAY_NAMES = {
    key: _DISPLAY_OVERRIDES.get(key, key.title())
    for key in COUNTRY_TO_REGION
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
        # USA variants
        'u.s.a': 'usa', 'u.s.a.': 'usa', 'u.s': 'usa', 'u.s.': 'usa',
        'united states of america': 'united states',
        'the united states': 'united states',
        # UK variants
        'u.k': 'uk', 'u.k.': 'uk', 'great britain': 'united kingdom',
        'england': 'united kingdom', 'scotland': 'united kingdom',
        'wales': 'united kingdom', 'northern ireland': 'united kingdom',
        # China variants
        'p.r. china': 'china', 'p.r.china': 'china', 'pr china': 'china',
        "people's republic of china": 'china', 'mainland china': 'china',
        # Korea
        'republic of korea': 'south korea', 'rok': 'south korea',
        "democratic people's republic of korea": 'north korea', 'dprk': 'north korea',
        # UAE
        'uae': 'united arab emirates',
        # Russia
        'russian federation': 'russia',
        # Other common aliases
        'czechia': 'czech republic',
        "cote d'ivoire": 'ivory coast',
        'republic of china': 'taiwan', 'chinese taipei': 'taiwan',
        'burma': 'myanmar',
        'swaziland': 'eswatini',
        'cabo verde': 'cape verde',
        'republic of moldova': 'moldova',
        'the gambia': 'gambia',
        'east timor': 'timor-leste',
        'viet nam': 'vietnam',
        'syrian arab republic': 'syria',
        'lao pdr': 'laos',
        "lao people's democratic republic": 'laos',
        'the netherlands': 'netherlands',
        'holland': 'netherlands',
        'republic of the congo': 'congo',
        'democratic republic of the congo': 'congo',
        'drc': 'congo',
        'palestinian territory': 'palestine',
        'state of palestine': 'palestine',
        'west bank': 'palestine',
        'iran (islamic republic of)': 'iran',
        'islamic republic of iran': 'iran',
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
            # (vérifié AVANT les états US pour gérer "Georgia" → pays d'Europe)
            if country_text in COUNTRY_TO_REGION:
                return country_text
            
            # Vérifier si c'est une abréviation d'état US (MA, MD, NC, CA...)
            # ou un nom d'état US (California, Massachusetts...)
            # Ces collisions avec les TLD sont très fréquentes dans les affiliations US
            if country_text in US_STATE_ABBREVIATIONS or country_text in US_STATE_NAMES:
                return 'usa'
            
            # Essayer aussi en TLD si c'est court (ex: 'uk' au lieu de 'united kingdom')
            if country_text in TLD_TO_COUNTRY:
                return TLD_TO_COUNTRY[country_text]
    
    # ════════════════════════════════════════════════════════════
    # PRIORITÉ 2 : NOM D'UNIVERSITÉ CONNU (très fiable)
    # ════════════════════════════════════════════════════════════
    # Tri par longueur décroissante pour éviter les sous-chaînes
    # (ex: "ucl" ne doit pas matcher avant "ucla" ou "ucl louvain")
    for uni, country in sorted(UNIVERSITY_TO_COUNTRY.items(), key=lambda x: len(x[0]), reverse=True):
        # Utiliser des frontières de mot pour éviter les faux positifs
        if re.search(r'\b' + re.escape(uni) + r'\b', affiliation_lower):
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
