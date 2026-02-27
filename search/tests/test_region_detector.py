"""
Unit tests for RegionDetector.
Tests country and region detection from author affiliations.
Covers original countries + Phase 6 worldwide expansion (226 countries).
"""
import pytest
from search.services.region_detector import (
    get_region_from_affiliation, get_country_code, get_country_name,
    COUNTRY_TO_REGION, TLD_TO_COUNTRY, CITY_TO_COUNTRY, COUNTRY_DISPLAY_NAMES,
)


class TestGetCountryCode:
    """Tests for country code extraction from affiliations."""

    def test_us_affiliation(self):
        affiliation = "Department of Surgery, Mayo Clinic, Rochester, Minnesota, United States"
        assert get_country_code(affiliation) in ('usa', 'united states', 'us')

    def test_france_affiliation(self):
        affiliation = "Service de Chirurgie Digestive, CHU Clermont-Ferrand, France"
        assert get_country_code(affiliation) == 'france'

    def test_uk_affiliation(self):
        affiliation = "Department of Surgery, University of Oxford, Oxford, United Kingdom"
        country = get_country_code(affiliation)
        assert country in ('uk', 'united kingdom')

    def test_japan_affiliation(self):
        affiliation = "Department of Gastroenterological Surgery, Kyoto University, Kyoto, Japan"
        assert get_country_code(affiliation) == 'japan'

    def test_china_affiliation(self):
        affiliation = "Hepatobiliary Surgery, West China Hospital, Sichuan University, Chengdu, China"
        assert get_country_code(affiliation) == 'china'

    def test_australia_affiliation(self):
        affiliation = "Royal Melbourne Hospital, University of Melbourne, Melbourne, Australia"
        assert get_country_code(affiliation) == 'australia'

    def test_empty_affiliation(self):
        assert get_country_code("") == ""

    def test_none_affiliation(self):
        # Should handle None gracefully
        try:
            result = get_country_code(None)
            assert result == "" or result is None
        except (TypeError, AttributeError):
            pass  # Acceptable if it raises on None

    def test_city_based_detection(self):
        """Should detect country from city name when country is not explicit."""
        affiliation = "Harvard Medical School, Boston, MA 02115"
        country = get_country_code(affiliation)
        assert country in ('usa', 'united states', 'us')


class TestGetRegionFromAffiliation:
    """Tests for region extraction from affiliations."""

    def test_north_america(self):
        affiliation = "Johns Hopkins Hospital, Baltimore, Maryland, United States"
        assert get_region_from_affiliation(affiliation) == 'north_america'

    def test_europe_france(self):
        affiliation = "Hôpital Beaujon, AP-HP, Clichy, France"
        assert get_region_from_affiliation(affiliation) == 'europe'

    def test_europe_germany(self):
        affiliation = "Charité University Hospital, Berlin, Germany"
        assert get_region_from_affiliation(affiliation) == 'europe'

    def test_asia_south_korea(self):
        affiliation = "Samsung Medical Center, Seoul, South Korea"
        assert get_region_from_affiliation(affiliation) == 'asia'

    def test_africa(self):
        affiliation = "University of Cape Town, Cape Town, South Africa"
        assert get_region_from_affiliation(affiliation) == 'africa'

    def test_south_america(self):
        affiliation = "Hospital das Clínicas, Universidade de São Paulo, São Paulo, Brazil"
        assert get_region_from_affiliation(affiliation) == 'south_america'

    def test_oceania(self):
        affiliation = "Royal Prince Alfred Hospital, Sydney, Australia"
        assert get_region_from_affiliation(affiliation) == 'oceania'

    def test_empty_returns_empty(self):
        result = get_region_from_affiliation("")
        assert result == "" or result is None


# ════════════════════════════════════════════════════════════════════════════════
# Phase 6+: Tests for newly added countries (worldwide expansion)
# ════════════════════════════════════════════════════════════════════════════════

class TestNewCountriesEurope:
    """Tests for European countries added in Phase 6."""

    def test_albania(self):
        assert get_region_from_affiliation("Faculty of Medicine, Tirana, Albania.") == 'europe'

    def test_cyprus(self):
        assert get_region_from_affiliation("Dept of Internal Med, Nicosia, Cyprus.") == 'europe'

    def test_kosovo(self):
        assert get_region_from_affiliation("Faculty of Med, Pristina, Kosovo.") == 'europe'

    def test_malta(self):
        assert get_region_from_affiliation("University of Malta, Msida, Malta.") == 'europe'

    def test_belarus(self):
        assert get_region_from_affiliation("Research Center, Minsk, Belarus.") == 'europe'

    def test_georgia(self):
        """Georgia should map to europe (not a US state)."""
        assert get_region_from_affiliation("Dept of Surgery, Tbilisi, Georgia.") == 'europe'

    def test_bosnia(self):
        assert get_region_from_affiliation("Clinical Center, Sarajevo, Bosnia and Herzegovina.") == 'europe'

    def test_turkey(self):
        """Turkey mapped to europe by medical convention."""
        assert get_region_from_affiliation("Ankara University Hospital, Ankara, Turkey.") == 'europe'


class TestNewCountriesAmericas:
    """Tests for Americas countries added in Phase 6."""

    def test_cuba(self):
        assert get_region_from_affiliation("Hospital Nacional, Havana, Cuba.") == 'north_america'

    def test_costa_rica(self):
        assert get_region_from_affiliation("Institute of Health, San Jose, Costa Rica.") == 'north_america'

    def test_guatemala(self):
        assert get_region_from_affiliation("Hospital General, Guatemala City, Guatemala.") == 'north_america'

    def test_jamaica(self):
        assert get_region_from_affiliation("University Hospital, Kingston, Jamaica.") == 'north_america'

    def test_uruguay(self):
        assert get_region_from_affiliation("Hospital de Clinicas, Montevideo, Uruguay.") == 'south_america'

    def test_ecuador(self):
        assert get_region_from_affiliation("Hospital Metropolitano, Quito, Ecuador.") == 'south_america'


class TestNewCountriesAsia:
    """Tests for Asian countries added in Phase 6."""

    def test_kyrgyzstan(self):
        assert get_region_from_affiliation("National Center, Bishkek, Kyrgyzstan.") == 'asia'

    def test_tajikistan(self):
        assert get_region_from_affiliation("Research Institute, Dushanbe, Tajikistan.") == 'asia'

    def test_bhutan(self):
        assert get_region_from_affiliation("National Hospital, Thimphu, Bhutan.") == 'asia'

    def test_syria(self):
        assert get_region_from_affiliation("Medical Faculty, Damascus, Syria.") == 'asia'

    def test_yemen(self):
        assert get_region_from_affiliation("National Hospital, Sanaa, Yemen.") == 'asia'

    def test_timor_leste(self):
        assert get_region_from_affiliation("National Institute, Dili, Timor-Leste.") == 'asia'

    def test_maldives(self):
        assert get_region_from_affiliation("Indira Gandhi Hospital, Male, Maldives.") == 'asia'


class TestNewCountriesAfrica:
    """Tests for African countries added in Phase 6."""

    def test_benin(self):
        assert get_region_from_affiliation("Hospital, Cotonou, Benin.") == 'africa'

    def test_togo(self):
        assert get_region_from_affiliation("CHU Sylvanus Olympio, Lome, Togo.") == 'africa'

    def test_sierra_leone(self):
        assert get_region_from_affiliation("National Hospital, Freetown, Sierra Leone.") == 'africa'

    def test_chad(self):
        assert get_region_from_affiliation("Hospital General, N'Djamena, Chad.") == 'africa'

    def test_eritrea(self):
        assert get_region_from_affiliation("Orotta Medical Center, Asmara, Eritrea.") == 'africa'

    def test_south_sudan(self):
        assert get_region_from_affiliation("Juba Teaching Hospital, Juba, South Sudan.") == 'africa'

    def test_eswatini(self):
        assert get_region_from_affiliation("National Hospital, Mbabane, Eswatini.") == 'africa'

    def test_mauritius(self):
        assert get_region_from_affiliation("Jawaharlal Nehru Hospital, Port Louis, Mauritius.") == 'africa'


class TestNewCountriesOceania:
    """Tests for Oceania countries added in Phase 6."""

    def test_fiji(self):
        assert get_region_from_affiliation("Colonial War Memorial Hospital, Suva, Fiji.") == 'oceania'

    def test_vanuatu(self):
        assert get_region_from_affiliation("Vila Central Hospital, Port Vila, Vanuatu.") == 'oceania'

    def test_papua_new_guinea(self):
        assert get_region_from_affiliation("Port Moresby General Hospital, Papua New Guinea.") == 'oceania'

    def test_samoa(self):
        assert get_region_from_affiliation("National Hospital, Apia, Samoa.") == 'oceania'


class TestCityBasedDetection:
    """Tests for city-based country inference (CITY_TO_COUNTRY)."""

    def test_tehran(self):
        assert get_country_code("Dept of Cardiology, Tehran University of Medical Sciences.") == 'iran'

    def test_cairo(self):
        assert get_country_code("Faculty of Medicine, Cairo University.") == 'egypt'

    def test_nairobi(self):
        assert get_country_code("University of Nairobi, College of Health Sciences.") == 'kenya'

    def test_bangkok(self):
        assert get_country_code("Faculty of Medicine, Siriraj Hospital, Bangkok.") == 'thailand'

    def test_buenos_aires(self):
        assert get_country_code("Hospital de Clinicas, Buenos Aires.") == 'argentina'

    def test_istanbul(self):
        assert get_country_code("Faculty of Medicine, Istanbul University.") == 'turkey'


class TestDisplayNames:
    """Tests for COUNTRY_DISPLAY_NAMES correctness."""

    def test_usa_display_name(self):
        assert COUNTRY_DISPLAY_NAMES['usa'] == 'United States'

    def test_uk_display_name(self):
        assert COUNTRY_DISPLAY_NAMES['uk'] == 'United Kingdom'

    def test_south_korea_display(self):
        assert COUNTRY_DISPLAY_NAMES['south korea'] == 'South Korea'

    def test_timor_leste_display(self):
        assert COUNTRY_DISPLAY_NAMES['timor-leste'] == 'Timor-Leste'

    def test_ivory_coast_display(self):
        assert COUNTRY_DISPLAY_NAMES['ivory coast'] == "Côte d'Ivoire"


class TestDictionaryCompleteness:
    """Meta-tests: verify dictionaries are consistent and complete."""

    def test_all_countries_have_display_names(self):
        """Every key in COUNTRY_TO_REGION should have a display name."""
        missing = [k for k in COUNTRY_TO_REGION if k not in COUNTRY_DISPLAY_NAMES]
        assert missing == [], f"Missing display names for: {missing}"

    def test_minimum_country_count(self):
        """We should have at least 220 country entries."""
        assert len(COUNTRY_TO_REGION) >= 220

    def test_minimum_tld_count(self):
        """We should have at least 190 TLD entries."""
        assert len(TLD_TO_COUNTRY) >= 190

    def test_minimum_city_count(self):
        """We should have at least 200 city entries after expansion."""
        assert len(CITY_TO_COUNTRY) >= 200

    def test_all_regions_covered(self):
        """All 6 regions should be present."""
        regions = set(COUNTRY_TO_REGION.values())
        expected = {'north_america', 'south_america', 'europe', 'asia', 'africa', 'oceania'}
        assert regions == expected
