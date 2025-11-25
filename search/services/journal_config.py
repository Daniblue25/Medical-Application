"""
Configuration des 13 revues chirurgicales de rang A.
Liste officielle des revues chirurgicales ciblées dans les domaines:
- Chirurgie digestive
- Chirurgie hépatobiliaire
- Transplantation
- Endoscopie digestive
"""

# Mapping des codes de journaux vers les noms complets
# 13 REVUES CHIRURGICALES DE RANG A
TARGET_JOURNALS = {
    'nejm': 'New England Journal of Medicine',
    'lancet': 'The Lancet',
    'jama': 'Journal of the American Medical Association',
    'jama_surgery': 'JAMA Surgery',
    'bjs': 'British Journal of Surgery',
    'annals_surgery': 'Annals of Surgery',
    'int_j_surgery': 'International Journal of Surgery',
    'digestive_endoscopy': 'Digestive Endoscopy',
    'liver_transplant': 'Liver Transplantation',
    'j_american_college_surgeons': 'Journal of the American College of Surgeons',
    'am_j_transplant': 'American Journal of Transplantation',
    'endoscopy': 'Endoscopy',
    'hepatobiliary': 'Hepatobiliary Surgery and Nutrition',
}

# Liste complète des 13 revues chirurgicales de rang A
ALL_TARGET_JOURNALS = [
    'New England Journal of Medicine',           # NEJM
    'The Lancet',                                 # Lancet
    'Journal of the American Medical Association', # JAMA
    'JAMA Surgery',
    'British Journal of Surgery',                # BJS
    'Annals of Surgery',
    'International Journal of Surgery',
    'Digestive Endoscopy',
    'Liver Transplantation',
    'Journal of the American College of Surgeons',
    'American Journal of Transplantation',
    'Endoscopy',
    'Hepatobiliary Surgery and Nutrition',
]

# Variantes de noms pour la correspondance
JOURNAL_VARIANTS = {
    'New England Journal of Medicine': ['NEJM', 'N Engl J Med', 'New Engl J Med'],
    'The Lancet': ['Lancet'],
    'Journal of the American Medical Association': ['JAMA', 'J Am Med Assoc'],
    'JAMA Surgery': ['JAMA Surg', 'Jama Surg'],
    'British Journal of Surgery': ['BJS', 'Br J Surg', 'Brit J Surg'],
    'Annals of Surgery': ['Ann Surg', 'Annals Surg'],
    'International Journal of Surgery': ['Int J Surg'],
    'Digestive Endoscopy': ['Dig Endosc'],
    'Liver Transplantation': ['Liver Transpl', 'Liver Transplant'],
    'Journal of the American College of Surgeons': ['J Am Coll Surg', 'JACS'],
    'American Journal of Transplantation': ['Am J Transplant', 'Am J Transpl'],
    'Endoscopy': ['Endoscopy'],
    'Hepatobiliary Surgery and Nutrition': ['Hepatobiliary Surg Nutr', 'HPB Surg Nutr'],
}


def get_journal_name(code: str) -> str:
    """
    Convertit un code de journal en nom complet.
    
    Args:
        code: Code du journal (ex: 'nejm', 'lancet')
        
    Returns:
        Nom complet du journal ou chaîne vide si code invalide
    """
    return TARGET_JOURNALS.get(code, '')


def build_journal_filter(journal_code: str = '') -> str:
    """
    Construit un filtre PubMed pour un journal spécifique ou tous les journaux ciblés.
    
    Args:
        journal_code: Code du journal spécifique, ou chaîne vide pour tous
        
    Returns:
        Requête PubMed avec filtre de journal
    """
    if journal_code and journal_code in TARGET_JOURNALS:
        # Filtre pour un journal spécifique
        journal_name = TARGET_JOURNALS[journal_code]
        return f'"{journal_name}"[Journal]'
    elif journal_code == '':
        # Filtre pour tous les journaux ciblés (OR) - comportement par défaut
        journal_filters = [f'"{journal}"[Journal]' for journal in ALL_TARGET_JOURNALS]
        return f"({' OR '.join(journal_filters)})"
    else:
        # Pas de filtre (recherche dans toutes les revues PubMed)
        return ""


def is_target_journal(journal_name: str) -> bool:
    """
    Vérifie si un journal fait partie des journaux ciblés.
    
    Args:
        journal_name: Nom du journal à vérifier
        
    Returns:
        True si le journal est dans la liste cible, False sinon
    """
    if not journal_name:
        return False
    
    journal_lower = journal_name.lower().strip()
    
    # Vérifier correspondance exacte
    for target_journal in ALL_TARGET_JOURNALS:
        if journal_lower == target_journal.lower():
            return True
    
    # Vérifier les variantes
    for canonical, variants in JOURNAL_VARIANTS.items():
        if journal_lower == canonical.lower():
            return True
        for variant in variants:
            if journal_lower == variant.lower():
                return True
    
    return False


def get_journal_display_name(journal_name: str) -> str:
    """
    Retourne le nom d'affichage canonique d'un journal.
    
    Args:
        journal_name: Nom du journal (peut être une variante)
        
    Returns:
        Nom canonique du journal pour affichage
    """
    if not journal_name:
        return journal_name
    
    journal_lower = journal_name.lower().strip()
    
    # Vérifier correspondance dans les variantes
    for canonical, variants in JOURNAL_VARIANTS.items():
        if journal_lower == canonical.lower():
            return canonical
        for variant in variants:
            if journal_lower == variant.lower():
                return canonical
    
    return journal_name
