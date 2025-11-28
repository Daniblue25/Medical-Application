import re
import logging

logger = logging.getLogger(__name__)

class ParticipantExtractor:
    """Extract participant/patient count from PubMed abstracts"""
    
    # Mapping des nombres en lettres vers chiffres
    WRITTEN_NUMBERS = {
        # Nombres simples anglais
        'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
        'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20,
        
        # Dizaines
        'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70,
        'eighty': 80, 'ninety': 90,
        
        # Centaines et plus
        'hundred': 100, 'thousand': 1000, 'million': 1000000,
        
        # Nombres composés courants
        'twenty-one': 21, 'twenty-two': 22, 'twenty-three': 23, 'twenty-four': 24, 'twenty-five': 25,
        'twenty-six': 26, 'twenty-seven': 27, 'twenty-eight': 28, 'twenty-nine': 29,
        'thirty-one': 31, 'thirty-two': 32, 'thirty-three': 33, 'thirty-four': 34, 'thirty-five': 35,
        'thirty-six': 36, 'thirty-seven': 37, 'thirty-eight': 38, 'thirty-nine': 39,
        'forty-one': 41, 'forty-two': 42, 'forty-three': 43, 'forty-four': 44, 'forty-five': 45,
        'fifty-one': 51, 'fifty-two': 52, 'fifty-three': 53, 'fifty-four': 54, 'fifty-five': 55,
        'sixty-one': 61, 'sixty-two': 62, 'sixty-three': 63, 'sixty-four': 64, 'sixty-five': 65,
        
        # Nombres français
        'un': 1, 'une': 1, 'deux': 2, 'trois': 3, 'quatre': 4, 'cinq': 5,
        'six': 6, 'sept': 7, 'huit': 8, 'neuf': 9, 'dix': 10,
        'onze': 11, 'douze': 12, 'treize': 13, 'quatorze': 14, 'quinze': 15,
        'seize': 16, 'vingt': 20, 'trente': 30, 'quarante': 40, 'cinquante': 50,
        'soixante': 60, 'cent': 100, 'mille': 1000
    }
    
    # Patterns pour détecter les nombres en chiffres
    # Ordre important: les patterns les plus spécifiques et prioritaires en premier
    # Note: (?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}) capture les nombres avec ou sans séparateurs (34,684 ou 34684)
    NUMERIC_PATTERNS = [
        # PRIORITAIRES: Déclarations principales (début d'abstract)
        # "In total, 119 individuals participated"
        r'(?:in\s+)?total[,\s]+((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))\s+(?:participants?|patients?|subjects?|individuals?|cases?)\s+(?:participated|enrolled|were\s+included|were\s+recruited)',
        
        # "119 participants were enrolled/included/recruited"
        r'((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))\s+(?:participants?|patients?|subjects?|individuals?|cases?)\s+(?:participated|were\s+enrolled|were\s+included|were\s+recruited|were\s+randomized)',
        
        # "A total of 119 participants"
        r'total\s+of\s+((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))\s+(?:participants?|patients?|subjects?|individuals?|cases?)',
        
        # "The study included 119 participants"
        r'(?:study|trial|analysis)\s+(?:included|enrolled|recruited)\s+((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))\s+(?:participants?|patients?|subjects?|individuals?|cases?)',
        
        # "planned enrollment is 700 participants" / "enrollment of 700 patients"
        r'(?:planned\s+)?enrollment\s+(?:is|was|of)\s+((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))\s+(?:adult\s+)?(?:participants?|patients?|subjects?|individuals?)',
        
        # "will enroll 700 participants" / "to enroll 700 patients"
        r'(?:will|to)\s+enroll\s+((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))\s+(?:adult\s+)?(?:participants?|patients?|subjects?|individuals?)',
        
        # "enrolling 700 participants"
        r'enrolling\s+((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))\s+(?:adult\s+)?(?:participants?|patients?|subjects?|individuals?)',
        
        # "119 patients" ou "119 participants" (simple mais efficace en début)
        r'((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))\s+(?:participants?|patients?|subjects?|individuals?|cases?)',
        
        # SECONDAIRES: Formats avec N = (souvent sous-groupes)
        # Sample size patterns
        r'sample\s+size\s*[:\(]?\s*[Nn]?\s*=?\s*((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))',
        r'enrolled\s+((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))\s+(?:participants?|patients?|subjects?)',
        
        # Study population
        r'study\s+population\s*[:\(]?\s*[Nn]?\s*=?\s*((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))',
        r'cohort\s+of\s+((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))\s+(?:participants?|patients?|subjects?)',
        
        # Pattern N = (peut être un sous-groupe, donc moins prioritaire)
        r'[Nn]\s*=\s*((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))',
        
        # "enrolled 53 eyes" / "enrolled 130 adults" / "enrolled 10 pediatric patients"
        r'enrolled\s+((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))\s+(?:eyes?|adults?|children|pediatric\s+patients?|healthy\s+(?:adults?|volunteers?))',
        
        # "randomized 1:1" - capture le contexte de randomisation
        r'((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))\s+(?:participants?|patients?)\s+(?:were\s+)?randomized\s+(?:1\s*:\s*1|in\s+a\s+1\s*:\s*1)',
        
        # "randomly assigned 100 patients"
        r'randomly\s+assigned\s+((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))\s+(?:participants?|patients?|subjects?)',
        
        # "recruited 100 patients from..."
        r'recruited\s+((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))\s+(?:participants?|patients?|subjects?)',
        
        # "comprising 100 patients"
        r'comprising\s+((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))\s+(?:participants?|patients?|subjects?)',
        
        # "involved 100 patients"
        r'involved\s+((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))\s+(?:participants?|patients?|subjects?)',
        
        # "conducted on 100 patients"
        r'conducted\s+(?:on|in|with)\s+((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))\s+(?:participants?|patients?|subjects?)',
        
        # "analyzed 100 patients" / "analysis of 100 patients"
        r'analy[sz](?:ed|is)\s+(?:of\s+)?((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))\s+(?:participants?|patients?|subjects?)',
        
        # "completed by 100 participants"
        r'completed\s+by\s+((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))\s+(?:participants?|patients?|subjects?)',
        
        # "data from 100 patients"
        r'data\s+from\s+((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))\s+(?:participants?|patients?|subjects?)',
        
        # "100 eligible patients"
        r'((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))\s+eligible\s+(?:participants?|patients?|subjects?)',
        
        # "100 consecutive patients"
        r'((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))\s+consecutive\s+(?:participants?|patients?|subjects?)',
        
        # "screened 200 patients" / "100 were screened"
        r'screened\s+((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))\s+(?:participants?|patients?|subjects?)',
        
        # "100 evaluable patients"
        r'((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))\s+evaluable\s+(?:participants?|patients?|subjects?)',
        
        # "assigned 50 to... and 50 to..." (capture le premier groupe)
        r'assigned\s+((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))\s+(?:participants?|patients?|subjects?)',
        
        # "among 100 patients"
        r'among\s+((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))\s+(?:participants?|patients?|subjects?)',
        
        # Participants/patients avec format variable
        r'(?:participants?|patients?|subjects?|individuals?|cases?)\s*[:\(]?\s*[Nn]?\s*=?\s*((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))',
        
        # Entre parenthèses ou crochets (souvent précisions, donc basse priorité)
        r'\([\s\w]*[Nn]\s*=\s*((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))[\s\w]*\)',
        r'\[[\s\w]*[Nn]\s*=\s*((?:\d{1,3}(?:[,\s]\d{3})*|\d{1,6}))[\s\w]*\]',
    ]
    
    # Patterns pour nombres en lettres
    WRITTEN_PATTERNS = [
        # Format: "twenty-five participants"
        r'((?:(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:-(?:one|two|three|four|five|six|seven|eight|nine))?)|(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty))\s+(?:participants?|patients?|subjects?|individuals?|cases?)',
        
        # Format: "participants (n = twenty-five)"
        r'(?:participants?|patients?|subjects?|individuals?|cases?)\s*\([Nn]\s*=\s*((?:(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:-(?:one|two|three|four|five|six|seven|eight|nine))?)|(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty))\)',
        
        # Format: "enrolled twenty patients"
        r'enrolled\s+((?:(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:-(?:one|two|three|four|five|six|seven|eight|nine))?)|(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty))\s+(?:participants?|patients?|subjects?)',
        
        # Format: "a total of fifteen subjects"
        r'total\s+of\s+((?:(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:-(?:one|two|three|four|five|six|seven|eight|nine))?)|(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty))\s+(?:participants?|patients?|subjects?|individuals?|cases?)',
        
        # Format avec "hundred": "one hundred fifty participants"
        r'((?:one|two|three|four|five|six|seven|eight|nine)\s+hundred(?:\s+(?:(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:-(?:one|two|three|four|five|six|seven|eight|nine))?|(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen)))?)\s+(?:participants?|patients?|subjects?|individuals?|cases?)',
        
        # Format français: "vingt-cinq participants"
        r'((?:(?:vingt|trente|quarante|cinquante|soixante)(?:-(?:un|une|deux|trois|quatre|cinq|six|sept|huit|neuf))?)|(?:un|une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|treize|quatorze|quinze|seize|vingt))\s+(?:participants?|patients?|sujets?|individus?|cas?)',
    ]
    
    # Mots-clés pour valider le contexte
    CONTEXT_KEYWORDS = [
        'participants', 'patients', 'subjects', 'individuals', 'cases',
        'sample', 'cohort', 'population', 'enrolled', 'recruited',
        'randomized', 'studied', 'analyzed', 'included', 'sujets'
    ]
    
    @classmethod
    def _parse_written_number(cls, text: str) -> int | None:
        """Convertit un nombre écrit en lettres en chiffre"""
        text = text.lower().strip()
        
        # Cas simple: nombre direct dans le dictionnaire
        if text in cls.WRITTEN_NUMBERS:
            return cls.WRITTEN_NUMBERS[text]
        
        # Gestion des nombres composés comme "twenty-five"
        if '-' in text:
            parts = text.split('-')
            if len(parts) == 2 and all(part in cls.WRITTEN_NUMBERS for part in parts):
                return cls.WRITTEN_NUMBERS[parts[0]] + cls.WRITTEN_NUMBERS[parts[1]]
        
        # Gestion des centaines: "one hundred fifty"
        words = text.split()
        if len(words) >= 2:
            total = 0
            i = 0
            while i < len(words):
                word = words[i]
                
                if word in cls.WRITTEN_NUMBERS:
                    value = cls.WRITTEN_NUMBERS[word]
                    
                    # Si le mot suivant est "hundred"
                    if i + 1 < len(words) and words[i + 1] == 'hundred':
                        total += value * 100
                        i += 2
                        # Ajouter le reste si présent
                        if i < len(words):
                            remaining = ' '.join(words[i:])
                            if remaining in cls.WRITTEN_NUMBERS:
                                total += cls.WRITTEN_NUMBERS[remaining]
                            elif '-' in remaining and len(remaining.split()) == 1:
                                # Gestion "twenty-five" après "hundred"
                                parts = remaining.split('-')
                                if len(parts) == 2 and all(p in cls.WRITTEN_NUMBERS for p in parts):
                                    total += cls.WRITTEN_NUMBERS[parts[0]] + cls.WRITTEN_NUMBERS[parts[1]]
                        break
                    else:
                        total += value
                        i += 1
                else:
                    i += 1
            
            if total > 0:
                return total
        
        return None
    
    @classmethod
    def extract_sample_size(cls, abstract: str) -> dict:
        """
        Extrait le nombre de participants d'un abstract PubMed
        
        Args:
            abstract: Texte de l'abstract
            
        Returns:
            dict: {
                'sample_size': int or None,
                'confidence': str ('high', 'medium', 'low'),
                'matched_text': str,
                'method': str
            }
        """
        if not abstract or len(abstract.strip()) < 20:
            return {
                'sample_size': None,
                'confidence': 'none',
                'matched_text': '',
                'method': 'no_abstract'
            }
        
        results = []
        
        # 1. Chercher les patterns numériques classiques
        for i, pattern in enumerate(cls.NUMERIC_PATTERNS):
            matches = re.finditer(pattern, abstract, re.IGNORECASE)
            
            for match in matches:
                number = cls._extract_number_from_match(match)
                
                if number and 5 <= number <= 1000000:
                    confidence_score = cls._calculate_confidence(
                        abstract, match, pattern, i, 'numeric'
                    )
                    
                    results.append({
                        'sample_size': number,
                        'confidence_score': confidence_score,
                        'matched_text': match.group().strip(),
                        'method': f'numeric_pattern_{i}',
                        'type': 'numeric'
                    })
        
        # 2. Chercher les patterns en lettres
        for i, pattern in enumerate(cls.WRITTEN_PATTERNS):
            matches = re.finditer(pattern, abstract, re.IGNORECASE)
            
            for match in matches:
                # Extraire le nombre en lettres
                written_number = None
                for group_num in range(1, match.lastindex + 1 if match.lastindex else 1):
                    try:
                        text = match.group(group_num)
                        if text:
                            written_number = cls._parse_written_number(text)
                            if written_number:
                                break
                    except:
                        continue
                
                if written_number and 5 <= written_number <= 1000000:
                    confidence_score = cls._calculate_confidence(
                        abstract, match, pattern, i, 'written'
                    )
                    
                    results.append({
                        'sample_size': written_number,
                        'confidence_score': confidence_score,
                        'matched_text': match.group().strip(),
                        'method': f'written_pattern_{i}',
                        'type': 'written'
                    })
        
        if not results:
            return {
                'sample_size': None,
                'confidence': 'none',
                'matched_text': '',
                'method': 'no_match'
            }
        
        # Trier par score de confiance et prendre le meilleur
        best_result = max(results, key=lambda x: x['confidence_score'])
        
        # Convertir le score en niveau de confiance
        if best_result['confidence_score'] >= 0.8:
            confidence = 'high'
        elif best_result['confidence_score'] >= 0.5:
            confidence = 'medium'
        else:
            confidence = 'low'
        
        return {
            'sample_size': best_result['sample_size'],
            'confidence': confidence,
            'matched_text': best_result['matched_text'],
            'method': best_result['method']
        }
    
    @classmethod
    def _extract_number_from_match(cls, match):
        """Extrait le nombre d'un match regex, gère les séparateurs de milliers (virgule, espace)"""
        for group_num in range(1, match.lastindex + 1 if match.lastindex else 1):
            try:
                group_text = match.group(group_num)
                if group_text:
                    # Supprimer les séparateurs de milliers (virgule et espace)
                    cleaned = group_text.replace(',', '').replace(' ', '')
                    if cleaned.isdigit():
                        return int(cleaned)
            except:
                continue
        return None
    
    @classmethod
    def _calculate_confidence(cls, abstract: str, match, pattern: str, pattern_index: int, pattern_type: str) -> float:
        """Calcule un score de confiance basé sur le contexte et la position"""
        score = 0.0
        
        # Contexte autour du match
        start = max(0, match.start() - 50)
        end = min(len(abstract), match.end() + 50)
        context = abstract[start:end].lower()
        
        # Score de base selon le pattern et type
        if pattern_type == 'numeric':
            # Nouveau système: patterns prioritaires ont les meilleurs scores
            base_scores = {
                0: 0.95,  # "In total, 119 individuals participated" - PRIORITÉ MAX
                1: 0.95,  # "119 participants/patients were enrolled" - PRIORITÉ MAX
                2: 0.90,  # "total of 119 participants/patients" - HAUTE PRIORITÉ
                3: 0.90,  # "study included 119 participants/patients" - HAUTE PRIORITÉ
                4: 0.90,  # "planned enrollment is 700 participants" - HAUTE PRIORITÉ
                5: 0.88,  # "will enroll 700 participants" - HAUTE PRIORITÉ
                6: 0.88,  # "enrolling 700 participants" - HAUTE PRIORITÉ
                7: 0.85,  # "119 participants/patients" simple - PRIORITÉ MOYENNE-HAUTE
                8: 0.75,  # sample size: 123
                9: 0.75,  # enrolled 123 participants/patients
                10: 0.70, # study population
                11: 0.70, # cohort of 123 patients
                12: 0.60, # N = 123 (souvent sous-groupe) - PRIORITÉ BASSE
                13: 0.65, # participants/patients: N = 123
                14: 0.50, # (N = 123) entre parenthèses - TRÈS BASSE PRIORITÉ
                15: 0.50, # [N = 123] entre crochets - TRÈS BASSE PRIORITÉ
            }
            score += base_scores.get(pattern_index, 0.6)
        else:  # written
            # Les nombres en lettres sont moins fréquents mais souvent plus précis
            score += 0.7
        
        # BONUS IMPORTANT: Position dans l'abstract
        # Les premières phrases mentionnent généralement le nombre total
        abstract_length = len(abstract)
        position_ratio = match.start() / abstract_length if abstract_length > 0 else 0.5
        
        if position_ratio < 0.2:  # Premiers 20% de l'abstract
            score += 0.15  # Fort bonus
        elif position_ratio < 0.4:  # Premiers 40%
            score += 0.05  # Léger bonus
        elif position_ratio > 0.8:  # Derniers 20%
            score -= 0.10  # Malus (souvent des sous-analyses)
        
        # Bonus pour mots-clés dans le contexte
        keyword_count = sum(1 for keyword in cls.CONTEXT_KEYWORDS if keyword in context)
        score += min(keyword_count * 0.05, 0.15)  # Réduit l'impact
        
        # MALUS si "N =" est présent (souvent un sous-groupe, pas le total)
        # SAUF si c'est dans le pattern principal avec "total"
        if re.search(r'[Nn]\s*=', match.group()):
            if not re.search(r'total', context, re.IGNORECASE):
                score -= 0.15  # Malus au lieu de bonus !
        
        # Bonus pour verbes d'action (participated, enrolled, recruited)
        if any(word in context for word in ['participated', 'enrolled', 'recruited', 'included', 'randomized']):
            score += 0.10
        
        # Bonus si "in total" ou "a total of" dans le contexte
        if re.search(r'(?:in\s+)?total\s+of', context, re.IGNORECASE):
            score += 0.15
        
        # Bonus pour les nombres en lettres dans certains contextes
        if pattern_type == 'written':
            if any(word in context for word in ['enrolled', 'recruited', 'included']):
                score += 0.1
        
        # Malus/bonus selon la taille du nombre
        try:
            num = None
            if pattern_type == 'numeric':
                num_text = re.search(r'(\d+)', match.group())
                if num_text:
                    num = int(num_text.group(1))
            else:
                # Pour les nombres en lettres, extraire depuis matched_text
                for group_num in range(1, match.lastindex + 1 if match.lastindex else 1):
                    try:
                        text = match.group(group_num)
                        if text:
                            num = cls._parse_written_number(text)
                            if num:
                                break
                    except:
                        continue
            
            if num:
                if num < 10:
                    score -= 0.4  # Malus plus fort pour très petits nombres
                elif num > 100000:
                    score -= 0.2
                elif 30 <= num <= 10000:
                    score += 0.05  # Léger bonus pour tailles typiques
        except:
            pass
        
        return min(1.0, max(0.0, score))