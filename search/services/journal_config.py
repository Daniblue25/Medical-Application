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


# Liste des revues infirmières (Nursing Journals)
NURSING_JOURNALS = [
    'AACN Adv Crit Care',
    'Adv Emerg Nurs J',
    'Adv Neonatal Care',
    'Adv Skin Wound Care',
    'Am J Crit Care',
    'Am J Nurs',
    'ANS Adv Nurs Sci',
    'AORN J',
    'Appl Nurs Res',
    'Arch Psychiatr Nurs',
    'Asian Nurs Res (Korean Soc Nurs Sci)',
    'Assist Inferm Ric',
    'Aust Crit Care',
    'Aust J Rural Health',
    'Australas Emerg Care',
    'Biol Res Nurs',
    'Birth',
    'Cancer Nurs',
    'Can J Nurs Res',
    'Clin J Oncol Nurs',
    'Clin Nurse Spec',
    'Clin Nurs Res',
    'Compr Child Adolesc Nurs',
    'Comput Inform Nurs',
    'Contemp Nurse',
    'Creat Nurs',
    'Crit Care Nurs Clin North Am',
    'Crit Care Nurse',
    'Dimens Crit Care Nurs',
    'Eur J Cardiovasc Nurs',
    'Eur J Oncol Nurs',
    'Gastroenterol Nurs',
    'Geriatr Nurs',
    'Heart Lung',
    'Holist Nurs Pract',
    'Int Emerg Nurs',
    'Intensive Crit Care Nurs',
    'Int J Ment Health Nurs',
    'Int J Nurs Educ Scholarsh',
    'Int J Nurs Knowl',
    'Int J Nurs Pract',
    'Int J Nurs Stud',
    'Int J Older People Nurs',
    'Int J Orthop Trauma Nurs',
    'Int J Palliat Nurs',
    'Int J Qual Stud Health Well-being',
    'Int Nurs Rev',
    'Invest Educ Enferm',
    'Issues Ment Health Nurs',
    'J Addict Nurs',
    'J Adv Nurs',
    'J Am Assoc Nurse Pract',
    'J Am Psychiatr Nurses Assoc',
    'J Assoc Nurses AIDS Care',
    'J Cardiovasc Nurs',
    'J Child Adolesc Psychiatr Nurs',
    'J Child Health Care',
    'J Christ Nurs',
    'J Clin Nurs',
    'J Community Health Nurs',
    'J Contin Educ Nurs',
    'J Dr Nurs Pract',
    'J Emerg Nurs',
    'J Fam Nurs',
    'J Forensic Nurs',
    'J Gerontol Nurs',
    'J Holist Nurs',
    'J Hosp Palliat Nurs',
    'J Hum Lact',
    'J Infus Nurs',
    'J Korean Acad Nurs',
    'J Midwifery Womens Health',
    'JMIR Nurs',
    'J Neurosci Nurs',
    'J Nurs Adm',
    'J Nurs Care Qual',
    'J Nurs Educ',
    'J Nurses Prof Dev',
    'J Nurs Manag',
    'J Nurs Meas',
    'J Nurs Res',
    'J Nurs Scholarsh',
    'J Obstet Gynecol Neonatal Nurs',
    'J Pediatr Health Care',
    'J Pediatr Hematol Oncol Nurs',
    'J Pediatr Nurs',
    'J Perianesth Nurs',
    'J Perinat Neonatal Nurs',
    'Jpn J Nurs Sci',
    'J Prof Nurs',
    'J Psychiatr Ment Health Nurs',
    'J Psychosoc Nurs Ment Health Serv',
    'J Ren Care',
    'J Sch Nurs',
    'J Spec Pediatr Nurs',
    'J Tissue Viability',
    'J Transcult Nurs',
    'J Trauma Nurs',
    'J Vasc Nurs',
    'J Wound Ostomy Continence Nurs',
    'MCN Am J Matern Child Nurs',
    'Midwifery',
    'Neonatal Netw',
    'Nephrol Nurs J',
    'Nurs Clin North Am',
    'Nurs Crit Care',
    'Nurse Educ',
    'Nurse Educ Pract',
    'Nurse Educ Today',
    'Nurse Pract',
    'Nurse Res',
    'Nurs Ethics',
    'Nurs Forum',
    'Nurs Health Sci',
    'Nurs Inq',
    'Nurs Open',
    'Nurs Outlook',
    'Nurs Philos',
    'Nurs Res',
    'Nurs Sci Q',
    'Nurs Womens Health',
    'Oncol Nurs Forum',
    'Orthop Nurs',
    'Pain Manag Nurs',
    'Perspect Psychiatr Care',
    'Pflege',
    'Policy Polit Nurs Pract',
    'Public Health Nurs',
    'Rech Soins Infirm',
    'Rehabil Nurs',
    'Res Gerontol Nurs',
    'Res Nurs Health',
    'Res Theory Nurs Pract',
    'Rev Bras Enferm',
    'Rev Esc Enferm USP',
    'Rev Lat Am Enfermagem',
    'Scand J Caring Sci',
    'Semin Oncol Nurs',
    'West J Nurs Res',
    'Women Birth',
    'Womens Health Nurs',
    'Workplace Health Saf',
    'Worldviews Evid Based Nurs',
    'Wound Manag Prev',
]


def build_nursing_journal_filter() -> str:
    """
    Construit un filtre PubMed pour toutes les revues infirmières.
    Utilise la liste complète des 144 journaux infirmiers.
    """
    journal_filters = [f'"{journal}"[Journal]' for journal in NURSING_JOURNALS]
    return f"({' OR '.join(journal_filters)})"


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
