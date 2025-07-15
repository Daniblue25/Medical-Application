import re
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
from rake_nltk import Rake


def extract_primary_outcome(abstract: str) -> str:
    """Extrait le critère de jugement principal d'un abstract"""
    if not abstract:
        return "Non identifié"
    
    # Patterns pour identifier les outcomes
    patterns = [
        r"primary outcome was (.*?)\.",
        r"primary endpoint was (.*?)\.",
        r"main outcome was (.*?)\.",
        r"primary objective was (.*?)\.",
        r"primary outcome measure was (.*?)\.",
        r"primary end point was (.*?)\.",
        r"the primary outcome (.*?)\.",
        r"mortality", r"survival", r"morbidity", r"complications",
        r"recurrence", r"quality of life", r"pain", r"function"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, abstract, re.IGNORECASE)
        if match:
            if match.groups():
                return match.group(1).strip()
            else:
                return pattern.replace("r", "").strip()
    
    return "Non identifié"


def extract_sample_size(abstract: str) -> int:
    """Extrait la taille d'échantillon d'un abstract"""
    if not abstract:
        return None
    
    # Patterns pour identifier la taille d'échantillon
    patterns = [
        r"n=(\d+)",
        r"n = (\d+)",
        r"(\d+) patients",
        r"(\d+) participants",
        r"(\d+) subjects",
        r"total of (\d+)",
        r"sample size.*?(\d+)",
        r"cohort of (\d+)",
        r"enrolled (\d+)",
        r"recruited (\d+)"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, abstract, re.IGNORECASE)
        if match:
            size = int(match.group(1))
            # Filtrer les valeurs non réalistes
            if 10 <= size <= 10000:
                return size
    
    return None


def extract_keywords(abstract: str, num_keywords: int = 5) -> list:
    """Extrait des mots-clés d'un abstract en utilisant RAKE"""
    if not abstract:
        return []
    
    try:
        r = Rake()
        r.extract_keywords_from_text(abstract)
        keywords = r.get_ranked_phrases()
        
        # Retourner les premiers mots-clés, nettoyés
        return [kw.lower().strip() for kw in keywords[:num_keywords] if len(kw.strip()) > 2]
    except:
        # Fallback simple en cas d'erreur
        words = abstract.lower().split()
        medical_terms = [w for w in words if len(w) > 4 and any(term in w for term in ['treatment', 'patient', 'study', 'clinical', 'therapy', 'medical', 'disease', 'cancer', 'drug'])]
        return medical_terms[:num_keywords]


def generate_summary(abstract: str, sentences_count: int = 2) -> str:
    """Génère un résumé automatique d'un abstract"""
    if not abstract or len(abstract.strip()) < 100:
        return "Résumé non disponible"
    
    try:
        parser = PlaintextParser.from_string(abstract, Tokenizer("english"))
        summarizer = LsaSummarizer()
        summary = summarizer(parser.document, sentences_count)
        
        return " ".join([str(sentence) for sentence in summary])
    except:
        # Fallback : retourner les deux premières phrases
        sentences = abstract.split('. ')
        if len(sentences) >= 2:
            return '. '.join(sentences[:2]) + '.'
        else:
            return abstract[:200] + "..." if len(abstract) > 200 else abstract


def determine_study_type(text: str) -> str:
    """Détermine le type d'étude à partir du texte"""
    if not text:
        return "Non spécifié"
    
    text_lower = text.lower()
    
    # Patterns pour différents types d'études
    study_types = {
        "Essai clinique randomisé": [
            "randomized controlled trial", "rct", "randomized trial",
            "randomized clinical trial", "randomized study"
        ],
        "Étude de cohorte": [
            "cohort study", "prospective study", "longitudinal study",
            "follow-up study", "cohort"
        ],
        "Étude cas-témoins": [
            "case-control study", "case control", "matched controls"
        ],
        "Série de cas": [
            "case series", "case report", "retrospective study",
            "retrospective analysis", "chart review"
        ],
        "Étude transversale": [
            "cross-sectional study", "cross sectional", "survey study"
        ],
        "Revue systématique": [
            "systematic review", "meta-analysis", "systematic literature review"
        ],
        "Étude observationnelle": [
            "observational study", "descriptive study"
        ]
    }
    
    for study_type, keywords in study_types.items():
        if any(keyword in text_lower for keyword in keywords):
            return study_type
    
    return "Étude clinique"

def extract_sample_size(text):
    """Extraire la taille d'échantillon d'un texte"""
    if not text:
        return None
    
    # Patterns pour identifier la taille d'échantillon
    patterns = [
        # Patterns directs
        r"(\d+)\s*patients?",
        r"(\d+)\s*subjects?",
        r"(\d+)\s*participants?",
        r"(\d+)\s*individuals?",
        r"(\d+)\s*cases?",
        r"(\d+)\s*people",
        r"(\d+)\s*adults?",
        r"(\d+)\s*children",
        r"(\d+)\s*men",
        r"(\d+)\s*women",
        
        # Patterns avec contexte
        r"sample\s*size.*?(\d+)",
        r"n\s*=\s*(\d+)",
        r"n\s*:\s*(\d+)",
        r"total\s*of\s*(\d+)",
        r"enrolled\s*(\d+)",
        r"recruited\s*(\d+)",
        r"included\s*(\d+)",
        
        # Patterns avec informations démographiques
        r"(\d+)\s*patients.*?age.*?years",
        r"(\d+)\s*patients.*?bmi",
        r"(\d+)\s*patients.*?body\s*mass\s*index",
        r"(\d+)\s*patients.*?female",
        r"(\d+)\s*patients.*?male",
        r"(\d+)\s*patients.*?range",
        
        # Patterns inversés (informations démographiques avant le nombre)
        r"median\s*age.*?(\d+)\s*patients",
        r"mean\s*age.*?(\d+)\s*patients",
        r"bmi.*?(\d+)\s*patients",
        r"body\s*mass\s*index.*?(\d+)\s*patients"
    ]
    
    found_sizes = []
    
    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.DOTALL)
        for match in matches:
            try:
                size = int(match.group(1))
                # Validation de la taille (doit être raisonnable pour une étude médicale)
                if 3 <= size <= 50000:  # Range élargi pour inclure les case series de 3 patients
                    found_sizes.append(size)
            except (ValueError, IndexError):
                continue
    
    if not found_sizes:
        return None
    
    # Si plusieurs tailles trouvées, prendre la plus fréquente ou la plus grande
    # Pour les études médicales, souvent la taille principale est mentionnée plusieurs fois
    if len(found_sizes) == 1:
        return found_sizes[0]
    
    # Compter les occurrences de chaque taille
    size_counts = {}
    for size in found_sizes:
        size_counts[size] = size_counts.get(size, 0) + 1
    
    # Retourner la taille la plus fréquente
    most_common_size = max(size_counts.items(), key=lambda x: x[1])[0]
    
    # Si plusieurs tailles ont la même fréquence, prendre la plus grande (souvent la taille totale)
    max_frequency = max(size_counts.values())
    candidates = [size for size, count in size_counts.items() if count == max_frequency]
    
    return max(candidates)


def generate_summary(abstract: str, sentences_count=2) -> str:
    """Génère un résumé automatique d'un abstract"""
    if not abstract or len(abstract) < 100:
        return abstract or "Résumé non disponible"
    
    try:
        parser = PlaintextParser.from_string(abstract, Tokenizer("english"))
        summarizer = LsaSummarizer()
        summary = summarizer(parser.document, sentences_count)
        return " ".join(str(sentence) for sentence in summary)
    except:
        # Fallback: prendre les premières phrases
        sentences = re.split(r'[.!?]+', abstract)
        return '. '.join(sentences[:sentences_count]) + '.'


def extract_keywords(text: str, num_keywords=5) -> list:
    """Extrait les mots-clés d'un texte"""
    if not text:
        return []
    
    try:
        rake = Rake(language='english')
        rake.extract_keywords_from_text(text)
        keywords = rake.get_ranked_phrases()[:num_keywords]
        return [kw for kw in keywords if len(kw) > 3]
    except:
        # Fallback: mots-clés simples
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
        return list(set(words))[:num_keywords]


def determine_study_type(text: str) -> str:
    """Détermine le type d'étude basé sur le titre et l'abstract"""
    if not text:
        return "Non déterminé"
    
    text = text.lower()
    
    # Patterns pour identifier les types d'études
    study_types = {
        "randomized controlled trial": [
            "randomized controlled trial", "randomized trial", "rct",
            "randomized", "randomisation", "randomization"
        ],
        "systematic review": [
            "systematic review", "meta-analysis", "systematic literature review",
            "meta analysis", "systematic review and meta-analysis"
        ],
        "cohort study": [
            "cohort study", "prospective study", "longitudinal study",
            "follow-up study", "prospective cohort"
        ],
        "case control study": [
            "case-control study", "case control", "case-control",
            "matched case-control"
        ],
        "cross-sectional study": [
            "cross-sectional", "cross sectional", "survey study",
            "prevalence study"
        ],
        "case series": [
            "case series", "case report", "case study"
        ],
        "observational study": [
            "observational study", "observational", "retrospective study"
        ]
    }
    
    for study_type, keywords in study_types.items():
        for keyword in keywords:
            if keyword in text:
                return study_type
    
    return "Étude non classifiée"


def analyze_trends(articles: list) -> dict:
    """Analyse les tendances temporelles des articles"""
    if not articles:
        return {}
    
    years = [article.get('year') for article in articles if article.get('year')]
    if not years:
        return {}
    
    year_counts = {}
    for year in years:
        year_counts[year] = year_counts.get(year, 0) + 1
    
    # Calculer la tendance
    sorted_years = sorted(year_counts.keys())
    if len(sorted_years) >= 2:
        early_count = sum(year_counts[year] for year in sorted_years[:len(sorted_years)//2])
        late_count = sum(year_counts[year] for year in sorted_years[len(sorted_years)//2:])
        trend = "croissante" if late_count > early_count else "décroissante"
    else:
        trend = "stable"
    
    return {
        'year_counts': year_counts,
        'trend': trend,
        'total_years': len(sorted_years)
    }