import re
import logging

logger = logging.getLogger(__name__)


def _normalize_number_str(s: str) -> str:
    """
    Normalize number string by removing thousand separators (comma, dot, space).
    
    Handles:
    - English format: 1,505 → 1505
    - European format: 1.505 → 1505 (dot as thousand separator)
    - Space separator: 1 505 → 1505
    
    Logic: A dot followed by exactly 3 digits is a thousand separator, not decimal.
    Examples:
        "1.505" → "1505" (1,505 patients in European format)
        "1.5" → "1" (1.5 is decimal, take integer part)
        "1,234,567" → "1234567"
        "1.234.567" → "1234567"
    """
    if not s:
        return s
    
    # Remove spaces (thousand separators in some locales)
    s = s.replace(' ', '')
    
    # Remove commas (English thousand separator)
    s = s.replace(',', '')
    
    # Handle dots: if followed by exactly 3 digits, it's a thousand separator
    # Otherwise (1-2 digits or end), it's a decimal point - truncate after it
    result = []
    i = 0
    while i < len(s):
        if s[i] == '.':
            # Count digits after the dot
            j = i + 1
            while j < len(s) and s[j].isdigit():
                j += 1
            digits_after = j - i - 1
            
            if digits_after == 3:
                # Thousand separator - skip the dot, keep the digits
                i += 1
                continue
            else:
                # Decimal point - stop here (truncate decimal part)
                break
        else:
            result.append(s[i])
        i += 1
    
    return ''.join(result)


class ParticipantExtractor:
    """Extract participant/patient count from PubMed abstracts"""
    
    # Mapping of English written numbers to digits
    WRITTEN_NUMBERS = {
        # Base numbers
        'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
        'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20,
        
        # Tens
        'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70,
        'eighty': 80, 'ninety': 90,
        
        # Multipliers
        'hundred': 100, 'thousand': 1000, 'million': 1000000,
    }
    
    # Screening-related words  — numbers near these describe the funnel, not the study sample
    SCREENING_WORDS = {
        'screened', 'assessed', 'evaluated for eligibility', 'assessed for eligibility',
        'were screened', 'were assessed', 'identified', 'potentially eligible',
    }
    
    # Patterns pour détecter les nombres en chiffres
    # Ordre important: les patterns les plus spécifiques et prioritaires en premier
    # Note: (?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}) captures numbers with separators (34,684) or without (9843)
    NUMERIC_PATTERNS = [
        # ── ULTRA-PRIORITY: Screening→Enrollment funnels ──
        # "screened 6148 patients, of whom 751 were included/enrolled"
        r'(?:screened|assessed)\s+(?:\d[\d,\s]*)\s+\w+[^.]*?(?:of\s+(?:whom|these|which|them))\s*,?\s*((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+(?:\w+\s+)?(?:were\s+)?(?:included|enrolled|recruited|randomized|randomised|eligible)',
        
        # "6148 were screened... 751 were included/enrolled" (separate clause)
        r'(?:\d[\d,\s]*)\s+(?:were\s+)?(?:screened|assessed)[^.]*?(?:and\s+)?((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+(?:were\s+)?(?:included|enrolled|recruited|randomized|randomised)',
        
        # "total of 3971 patients were assessed, and 217 patients were enrolled"
        r'(?:total\s+of\s+)?\d[\d,\s]*\s+(?:patients?|participants?|subjects?)\s+(?:[\w\s]*?)(?:were\s+)?(?:screened|assessed)[^.]*?(?:and\s+)?((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+(?:patients?\s+)?(?:were\s+)?(?:included|enrolled|recruited|randomized|randomised)',
        
        # "screened X patients and enrolled Y patients" (verb-first, same sentence)
        r'(?:screened|assessed)\s+\d[\d,]*\s+(?:patients?|participants?|subjects?)[^.]*?enrolled\s+((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+(?:patients?|participants?|subjects?)',
        
        # "screened 500 patients. Of these, 200 were excluded and 300 were enrolled" (cross-sentence)
        r'(?:screened|assessed)\s+\d[\d,]*\s+(?:patients?|participants?|subjects?)[^.]*\.\s*(?:Of\s+(?:these|them|whom)[^.]*?)((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+(?:were\s+)?(?:enrolled|included|recruited|randomized)',
        
        # ── PRIORITAIRES: Déclarations principales (début d'abstract) ──
        # "In total, 119 individuals participated"
        r'(?:in\s+)?total[,.\\s]+((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+(?:participants?|patients?|subjects?|individuals?|cases?)\s+(?:participated|enrolled|were\s+included|were\s+recruited)',
        
        # "119 participants were enrolled/included/recruited"
        r'((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+(?:participants?|patients?|subjects?|individuals?|cases?)\s+(?:participated|were\s+enrolled|were\s+included|were\s+recruited|were\s+randomized|were\s+randomised)',
        
        # "A total of 119 participants"
        r'total\s+of\s+((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+(?:participants?|patients?|subjects?|individuals?|cases?)',
        
        # "The study included 119 participants"
        r'(?:study|trial|analysis)\s+(?:included|enrolled|recruited)\s+((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+(?:participants?|patients?|subjects?|individuals?|cases?)',
        
        # "planned enrollment is 700 participants" / "enrollment of 700 patients"
        r'(?:planned\s+)?enrollment\s+(?:is|was|of)\s+((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+(?:adult\s+)?(?:participants?|patients?|subjects?|individuals?)',
        
        # "will enroll 700 participants" / "to enroll 700 patients"
        r'(?:will|to)\s+enroll\s+((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+(?:adult\s+)?(?:participants?|patients?|subjects?|individuals?)',
        
        # "enrolling 700 participants"
        r'enrolling\s+((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+(?:adult\s+)?(?:participants?|patients?|subjects?|individuals?)',
        
        # "119 patients" / "612 burned children" / "100 deceased donors" (broad match)
        r'((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+(?:(?:consecutive|eligible|enrolled|study|deceased|obese|adult|pediatric|surgical|hospitalized|burned|selected|total|medical)\s+)*(?:participants?|patients?|subjects?|individuals?|cases?|children|neonates?|infants?|donors?|adults?|women|men|volunteers?|students?)',
        
        # SECONDAIRES: Formats avec N = (souvent sous-groupes)
        # Sample size patterns
        r'sample\s+size\s*[:\(]?\s*[Nn]?\s*=?\s*((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))',
        r'enrolled\s+((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+(?:participants?|patients?|subjects?)',
        
        # Study population
        r'study\s+population\s*[:\(]?\s*[Nn]?\s*=?\s*((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))',
        r'cohort\s+of\s+((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+(?:participants?|patients?|subjects?)',
        
        # Pattern N = (peut être un sous-groupe, donc moins prioritaire)
        r'[Nn]\s*=\s*((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))',
        
        # "enrolled 53 eyes" / "enrolled 130 adults" / "enrolled 10 pediatric patients"
        r'enrolled\s+((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+(?:eyes?|adults?|children|pediatric\s+patients?|healthy\s+(?:adults?|volunteers?))',
        
        # "randomized 1:1" - capture le contexte de randomisation
        r'((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+(?:participants?|patients?)\s+(?:were\s+)?randomized\s+(?:1\s*:\s*1|in\s+a\s+1\s*:\s*1)',
        
        # "randomly assigned 100 patients"
        r'randomly\s+assigned\s+((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+(?:participants?|patients?|subjects?)',
        
        # "recruited 100 patients from..."
        r'recruited\s+((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+(?:participants?|patients?|subjects?)',
        
        # "comprising 100 patients"
        r'comprising\s+((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+(?:participants?|patients?|subjects?)',
        
        # "involved 100 patients"
        r'involved\s+((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+(?:participants?|patients?|subjects?)',
        
        # "conducted on 100 patients"
        r'conducted\s+(?:on|in|with)\s+((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+(?:participants?|patients?|subjects?)',
        
        # "analyzed 100 patients" / "analysis of 100 patients"
        r'analy[sz](?:ed|is)\s+(?:of\s+)?((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+(?:participants?|patients?|subjects?)',
        
        # "completed by 100 participants"
        r'completed\s+by\s+((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+(?:participants?|patients?|subjects?)',
        
        # "data from 100 patients"
        r'data\s+from\s+((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+(?:participants?|patients?|subjects?)',
        
        # "100 eligible patients"
        r'((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+eligible\s+(?:participants?|patients?|subjects?)',
        
        # "100 consecutive patients"
        r'((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+consecutive\s+(?:participants?|patients?|subjects?)',
        
        # "screened 200 patients" / "100 were screened"
        r'screened\s+((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+(?:participants?|patients?|subjects?)',
        
        # "100 evaluable patients"
        r'((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+evaluable\s+(?:participants?|patients?|subjects?)',
        
        # "assigned 50 to... and 50 to..." (capture le premier groupe)
        r'assigned\s+((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+(?:participants?|patients?|subjects?)',
        
        # "among 100 patients"
        r'among\s+((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+(?:participants?|patients?|subjects?)',
        
        # Participants/patients avec format variable
        r'(?:participants?|patients?|subjects?|individuals?|cases?)\s*[:\(]?\s*[Nn]?\s*=?\s*((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))',
        
        # Entre parenthèses ou crochets (souvent précisions, donc basse priorité)
        r'\([\s\w]*[Nn]\s*=\s*((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))[\s\w]*\)',
        r'\[[\s\w]*[Nn]\s*=\s*((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))[\s\w]*\]',

        # "310 were randomized" / "120 were randomly assigned" (no patient noun)
        r'((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+were\s+(?:randomly\s+)?(?:randomized|randomised|assigned|allocated|enrolled|included|recruited)',

        # "7775 total participants" (number before "total")
        r'((?:\d{1,3}(?:[,.\\s]\d{3})+|\d{1,6}))\s+total\s+(?:participants?|patients?|subjects?)',
    ]
    
    # Reusable sub-patterns for written numbers (English only, PubMed is English)
    _TENS = r'(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)'
    _ONES = r'(?:one|two|three|four|five|six|seven|eight|nine)'
    _TEENS = r'(?:ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen)'
    _TENS_COMPOUND = rf'(?:{_TENS}(?:-{_ONES})?)'
    _SIMPLE_NUM = rf'(?:{_TENS_COMPOUND}|{_TEENS}|{_ONES})'
    _HUNDRED_NUM = rf'(?:{_ONES}\s+hundred(?:\s+{_SIMPLE_NUM})?)'
    _THOUSAND_NUM = rf'(?:{_ONES}\s+thousand(?:\s+{_HUNDRED_NUM}|\s+{_SIMPLE_NUM})?)'
    _ANY_WRITTEN = rf'(?:{_THOUSAND_NUM}|{_HUNDRED_NUM}|{_SIMPLE_NUM})'
    _NOUNS = r'(?:participants?|patients?|subjects?|individuals?|cases?)'
    
    # Patterns for written numbers — MOST SPECIFIC FIRST to avoid partial matches
    WRITTEN_PATTERNS = [
        # PRIORITY 1: "X thousand [Y hundred] [Z] patients" (most specific)
        rf'({_THOUSAND_NUM})\s+{_NOUNS}',
        
        # PRIORITY 2: "X hundred [Y] patients" 
        rf'({_HUNDRED_NUM})\s+{_NOUNS}',
        
        # PRIORITY 3: "total of X hundred patients"
        rf'total\s+of\s+({_ANY_WRITTEN})\s+{_NOUNS}',
        
        # PRIORITY 4: "enrolled X hundred patients"
        rf'(?:enrolled|included|recruited|randomized)\s+({_ANY_WRITTEN})\s+{_NOUNS}',
        
        # PRIORITY 5: Simple "twenty-five patients" / "ten patients"
        rf'({_SIMPLE_NUM})\s+{_NOUNS}',
        
        # PRIORITY 6: "participants (n = twenty-five)"
        rf'{_NOUNS}\s*\([Nn]\s*=\s*({_ANY_WRITTEN})\)',
    ]
    
    # Context keywords for confidence scoring
    CONTEXT_KEYWORDS = [
        'participants', 'patients', 'subjects', 'individuals', 'cases',
        'sample', 'cohort', 'population', 'enrolled', 'recruited',
        'randomized', 'studied', 'analyzed', 'included',
    ]
    
    @classmethod
    def _parse_written_number(cls, text: str) -> int | None:
        """Parse an English written number into an integer.
        
        Handles:
          - Simple: 'twenty', 'five'
          - Compound: 'twenty-five'
          - Hundreds: 'four hundred seventy-two'
          - Thousands: 'two thousand three hundred fifty'
        """
        text = text.lower().strip()
        if not text:
            return None
        
        # Tokenize: split on spaces, then further split hyphenated parts
        # e.g. 'four hundred seventy-two' -> ['four', 'hundred', 'seventy-two']
        raw_tokens = text.split()
        
        # Resolve each token
        def _resolve_token(tok: str) -> int | None:
            """Resolve a single token (possibly hyphenated) to a number."""
            if tok in cls.WRITTEN_NUMBERS:
                return cls.WRITTEN_NUMBERS[tok]
            if '-' in tok:
                parts = tok.split('-')
                if len(parts) == 2 and all(p in cls.WRITTEN_NUMBERS for p in parts):
                    return cls.WRITTEN_NUMBERS[parts[0]] + cls.WRITTEN_NUMBERS[parts[1]]
            return None
        
        # Build the number using a stack-based approach for multipliers
        # Process: accumulate current group, multiply by hundred/thousand when encountered
        total = 0
        current = 0  # accumulator for the current group
        i = 0
        
        while i < len(raw_tokens):
            tok = raw_tokens[i]
            
            if tok == 'thousand':
                # current (or 1 if nothing before) * 1000
                total += (current if current > 0 else 1) * 1000
                current = 0
                i += 1
            elif tok == 'hundred':
                # current (or 1 if nothing before) * 100
                current = (current if current > 0 else 1) * 100
                i += 1
            else:
                val = _resolve_token(tok)
                if val is not None:
                    current += val
                    i += 1
                else:
                    # Unknown token, skip
                    i += 1
        
        total += current
        return total if total > 0 else None
    
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
        
        # 3. Try multi-arm summation: detect "(n = X) ... (n = Y)" patterns
        arm_result = cls._try_multi_arm_summation(abstract)
        if arm_result:
            results.append(arm_result)
        
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
        
        # ── Post-processing: prefer enrollment total over per-arm value ──
        # In RCTs, the NLP may pick a per-arm value instead of the total.
        # If we find a clear "total enrollment" number ≈ 2× our result, use it.
        best_result = cls._prefer_enrollment_total(abstract, best_result, results)
        
        return {
            'sample_size': best_result['sample_size'],
            'confidence': confidence,
            'matched_text': best_result['matched_text'],
            'method': best_result['method']
        }
    
    @classmethod
    def _prefer_enrollment_total(cls, abstract: str, best: dict, all_results: list) -> dict:
        """
        Post-processing: if the selected result looks like a per-arm value,
        check if the abstract mentions a total that is ~2× this value.
        If so, return the total instead.
        
        Common patterns:
          - "200 consecutive patients" where NLP picked "108 patients" (per-arm)
          - "A total of 100 patients were randomized" where NLP picked "(n=50)"
          - "386 patients were enrolled" where NLP picked "173 patients"
        """
        best_n = best.get('sample_size')
        if not best_n or best_n < 5:
            return best
        
        # Don't override if the current best is already a high-confidence enrollment total
        # (patterns 0-9 are enrollment/total patterns with base score >= 0.88)
        best_method = best.get('method', '')
        if best_method.startswith('numeric_pattern_'):
            try:
                pat_idx = int(best_method.split('_')[-1])
                if pat_idx <= 9:  # High-confidence enrollment patterns
                    return best
            except ValueError:
                pass
        if best_method in ('multi_arm_sum', 'enrollment_total_override'):
            return best
        
        # Also skip if matched text contains strong enrollment context
        matched_lower = best.get('matched_text', '').lower()
        strong_enrollment = ['randomized', 'randomised', 'enrolled', 'total of',
                             'were included', 'participated', 'were recruited']
        if any(kw in matched_lower for kw in strong_enrollment):
            return best
        
        abstract_lower = abstract.lower()
        
        # Only try if there's RCT context
        rct_keywords = ['randomiz', 'randomis', 'assigned', 'allocated', 'group',
                        'arm', 'versus', ' vs ', 'compared', 'control', 'placebo']
        if not any(kw in abstract_lower for kw in rct_keywords):
            return best
        
        # Look for a candidate total among all results
        # A "total" is a number that is between 1.7× and 2.5× our best result
        # (accounts for imbalances between arms and multi-arm trials with 2-3 arms)
        target_lo = best_n * 1.7
        target_hi = best_n * 2.5
        
        best_total_candidate = None
        best_total_score = 0
        
        for r in all_results:
            n = r.get('sample_size')
            if not n or n == best_n:
                continue
            if target_lo <= n <= target_hi:
                # Found a ~2× candidate — check if it's a total/enrollment count
                method = r.get('method', '')
                matched = r.get('matched_text', '').lower()
                score = r.get('confidence_score', 0)
                
                # Boost if matched text contains total/enrollment context  
                is_total = False
                total_patterns = [
                    'total', 'enrolled', 'included', 'randomized', 'randomised',
                    'consecutive', 'underwent', 'recruited', 'participated',
                ]
                for tp in total_patterns:
                    if tp in matched:
                        is_total = True
                        break
                
                # Also check the abstract context around this number
                if not is_total:
                    # Find position of this number in abstract
                    n_str = str(n)
                    idx = abstract.find(n_str)
                    if idx >= 0:
                        ctx = abstract[max(0, idx-60):idx+len(n_str)+60].lower()
                        for tp in total_patterns:
                            if tp in ctx:
                                is_total = True
                                break
                
                if is_total and (best_total_candidate is None or score > best_total_score):
                    best_total_candidate = r
                    best_total_score = score
        
        if best_total_candidate:
            return best_total_candidate
        
        # Also try: if the abstract says "X patients" or "a total of X" where
        # X ≈ 2×best and this number wasn't in our results (edge case)
        total_enrollment_patterns = [
            r'(?:a\s+)?total\s+of\s+(\d[\d,]*)\s+(?:patients?|participants?|subjects?|individuals?|people)',
            r'(\d[\d,]*)\s+(?:consecutive\s+)?(?:patients?|participants?|subjects?)\s+(?:were\s+)?(?:randomized|randomised|enrolled|recruited|included)',
            r'(?:randomized|randomised|enrolled|recruited)\s+(\d[\d,.]*?)\s+(?:patients?|participants?|subjects?)',
            r'(?:study|trial)\s+(?:of|included|enrolled|with)\s+(\d[\d,.]*?)\s+(?:patients?|participants?|subjects?)',
        ]
        
        for pat in total_enrollment_patterns:
            for m in re.finditer(pat, abstract, re.IGNORECASE):
                try:
                    n = int(_normalize_number_str(m.group(1)))
                except (ValueError, IndexError):
                    continue
                if target_lo <= n <= target_hi:
                    return {
                        'sample_size': n,
                        'confidence_score': 0.92,
                        'matched_text': m.group().strip(),
                        'method': 'enrollment_total_override',
                        'type': 'numeric',
                    }
        
        return best
    
    @classmethod
    def _extract_number_from_match(cls, match):
        """Extrait le nombre d'un match regex, gère les séparateurs de milliers (virgule, point, espace)"""
        for group_num in range(1, match.lastindex + 1 if match.lastindex else 1):
            try:
                group_text = match.group(group_num)
                if group_text:
                    # Normalize thousand separators (comma, dot, space)
                    cleaned = _normalize_number_str(group_text)
                    if cleaned.isdigit():
                        return int(cleaned)
            except:
                continue
        return None
    
    @classmethod
    def _try_multi_arm_summation(cls, abstract: str) -> dict | None:
        """
        Detect multi-arm RCT patterns like "(n = 528) or (n = 528)" and sum arms.
        Also handles "(group_name; n=X)" and "(group_name, n = X)" patterns.
        Only used when no explicit total is stated nearby.
        Returns a result dict or None.
        """
        # Find all (n = X), [n = X], (group; n=X), (group, n = X) patterns
        # The key requirement is that n=X appears inside brackets
        arm_matches = list(re.finditer(
            r'[\(\[](?:[^)\]]*?[,;]\s*)?[Nn][\s\u2009\u00a0]*=[\s\u2009\u00a0]*(\d[\d,]*)\s*[\)\]]',
            abstract
        ))
        if len(arm_matches) < 2:
            return None
        
        # Check if arms appear close together (within 200 chars) 
        # and that there's randomization context
        for i in range(len(arm_matches) - 1):
            m1 = arm_matches[i]
            m2 = arm_matches[i + 1]
            gap = m2.start() - m1.end()
            if gap > 200:
                continue
            
            # Check for randomization/arm context between or around the matches
            context_start = max(0, m1.start() - 100)
            context_end = min(len(abstract), m2.end() + 50)
            context = abstract[context_start:context_end].lower()
            
            arm_keywords = ['randomiz', 'randomis', 'assigned', 'allocated',
                            'group', 'arm', 'vs', 'versus', 'compared',
                            'intervention', 'control', 'placebo']
            if not any(kw in context for kw in arm_keywords):
                continue
            
            # Check that no explicit total is already stated within 200 chars before
            pre_context = abstract[max(0, m1.start() - 200):m1.start()].lower()
            if re.search(r'total\s+of\s+\d', pre_context):
                return None  # explicit total exists, don't sum
            
            # Sum all consecutive arms
            n1 = int(_normalize_number_str(m1.group(1)))
            total = n1
            matched_parts = [m1.group()]
            
            for j in range(i + 1, len(arm_matches)):
                mj = arm_matches[j]
                if mj.start() - arm_matches[j - 1].end() > 200:
                    break
                nj = int(_normalize_number_str(mj.group(1)))
                total += nj
                matched_parts.append(mj.group())
            
            if total >= 10 and len(matched_parts) >= 2:
                return {
                    'sample_size': total,
                    'confidence_score': 0.82,  # Good but not highest
                    'matched_text': ' + '.join(matched_parts),
                    'method': 'multi_arm_sum',
                    'type': 'numeric'
                }
        
        return None
    
    @classmethod
    def _calculate_confidence(cls, abstract: str, match, pattern: str, pattern_index: int, pattern_type: str) -> float:
        """Calcule un score de confiance basé sur le contexte et la position"""
        score = 0.0
        
        # Contexte autour du match
        start = max(0, match.start() - 100)
        end = min(len(abstract), match.end() + 100)
        context = abstract[start:end].lower()
        
        # Score de base selon le pattern et type
        if pattern_type == 'numeric':
            # Updated: indices shifted +3 for 3 new ultra-priority screening→enrollment patterns
            base_scores = {
                0: 0.98,  # Screening→enrollment funnel "of whom X were included" - ULTRA
                1: 0.98,  # "X screened... Y were included" - ULTRA
                2: 0.98,  # "total of X assessed... Y were enrolled" - ULTRA
                3: 0.98,  # "screened X and enrolled Y" (verb-first) - ULTRA
                4: 0.98,  # "screened X. Of these, Y enrolled" (cross-sentence) - ULTRA
                5: 0.95,  # "In total, 119 individuals participated"
                6: 0.95,  # "119 patients were enrolled"
                7: 0.90,  # "total of 119 participants"
                8: 0.90,  # "study included 119 participants"
                9: 0.90,  # "planned enrollment is 700"
                10: 0.88, # "will enroll 700"
                11: 0.88, # "enrolling 700"
                12: 0.85, # "119 patients" simple
                13: 0.75, # sample size
                14: 0.75, # enrolled 123
                15: 0.70, # study population
                16: 0.70, # cohort of 123
                17: 0.60, # N = 123
                18: 0.65, # enrolled 53 eyes/adults
                19: 0.70, # randomized 1:1
                20: 0.70, # randomly assigned
                21: 0.70, # recruited 100
                22: 0.68, # comprising 100
                23: 0.68, # involved 100
                24: 0.68, # conducted on 100
                25: 0.67, # analyzed 100
                26: 0.65, # completed by 100
                27: 0.65, # data from 100
                28: 0.65, # 100 eligible
                29: 0.65, # 100 consecutive
                30: 0.45, # screened 200 patients — LOW (screening count)
                31: 0.65, # 100 evaluable
                32: 0.60, # assigned 50
                33: 0.60, # among 100
                34: 0.55, # patients: N = 123
                35: 0.50, # (N = 123)
                36: 0.50, # [N = 123]
                37: 0.88, # "N were randomized" (no patient noun)
                38: 0.85, # "N total participants"
            }
            score += base_scores.get(pattern_index, 0.6)
        else:  # written
            written_base_scores = {
                0: 0.92,  # "X thousand patients"
                1: 0.90,  # "X hundred patients"
                2: 0.88,  # "total of X hundred patients"
                3: 0.88,  # "enrolled/included X hundred patients"
                4: 0.75,  # Simple "twenty-five patients"
                5: 0.70,  # "patients (n = twenty-five)"
            }
            score += written_base_scores.get(pattern_index, 0.7)
        
        # ── SCREENING PENALTY ──
        # Only penalize if the matched number ITSELF is described as a screening count
        # Use a narrow window: 15 chars before the match number through 80 chars after
        narrow_pre = abstract[max(0, match.start() - 15):match.start()].lower()
        narrow_post = abstract[match.end():min(len(abstract), match.end() + 80)].lower()
        matched_lower = match.group().lower()
        
        # Direct screening: "screened 6148 patients" or "6148 patients were screened"
        is_screening = False
        if re.search(r'(?:screened|assessed\s+for\s+eligibility)', narrow_pre):
            is_screening = True
        if re.search(r'(?:were\s+)?(?:screened|assessed\s+for\s+eligibility)', narrow_post):
            is_screening = True
        # "total of X patients were assessed/screened" — only if "assessed/screened" is in post
        if re.search(r'total\s+of', matched_lower) and re.search(r'(?:assessed|screened|evaluated)', narrow_post):
            is_screening = True
        
        if is_screening:
            # Heavy penalty if followed by enrollment language (confirms this is the screening funnel)
            if re.search(r'(?:of\s+(?:whom|these|which|them)|were\s+(?:excluded|ineligible))', narrow_post):
                score -= 0.40
            else:
                score -= 0.25
        
        # BONUS IMPORTANT: Position dans l'abstract
        abstract_length = len(abstract)
        position_ratio = match.start() / abstract_length if abstract_length > 0 else 0.5
        
        if position_ratio < 0.2:
            score += 0.15
        elif position_ratio < 0.4:
            score += 0.05
        elif position_ratio > 0.8:
            score -= 0.10
        
        # Bonus pour mots-clés dans le contexte
        keyword_count = sum(1 for keyword in cls.CONTEXT_KEYWORDS if keyword in context)
        score += min(keyword_count * 0.05, 0.15)
        
        # MALUS si "N =" est présent (souvent un sous-groupe, pas le total)
        if re.search(r'[Nn]\s*=', match.group()):
            if not re.search(r'total', context, re.IGNORECASE):
                score -= 0.15
        
        # Bonus pour verbes d'action
        if any(word in context for word in ['participated', 'enrolled', 'recruited', 'included', 'randomized']):
            score += 0.10
        
        # Bonus si "in total" ou "a total of" dans le contexte (but NOT "assessed/screened")
        if re.search(r'(?:in\s+)?total\s+of', context, re.IGNORECASE):
            if not re.search(r'(?:screened|assessed|evaluated)', context, re.IGNORECASE):
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
                    score -= 0.4
                elif num > 100000:
                    score -= 0.2
                elif 30 <= num <= 10000:
                    score += 0.05  # Léger bonus pour tailles typiques
        except:
            pass
        
        return max(0.0, score)  # No cap — score is used for internal ranking only