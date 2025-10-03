# Medical Search Application - Copilot Instructions

## Architecture Overview

This is a professional Django 5 medical literature search application that provides a REST API for searching **real medical articles from PubMed ONLY**. No mock data is used - all articles come from the NCBI PubMed database via E-utilities API.

### Core Components

- **`search/services/pubmed_client.py`**: **ONLY** data source. Uses NCBI E-utilities to fetch real medical articles with complete metadata (titles, abstracts, PMIDs, DOIs, authors, journals, MeSH terms).
- **`search/views/search.py`**: Main API endpoint that orchestrates PubMed queries → pagination → caching. Returns error 503 if PubMed is unavailable.
- **`search/models.py`**: Django model for Article (currently unused, ready for database storage).

### Data Flow Pattern

```
User Request → /api/search
  ↓
Check cache (hash-based key)
  ↓
Query PubMed API (keyword optional - defaults to "medicine[MeSH Terms]")
  ↓
Success? → Return real PubMed articles with full metadata
  ↓
Failure? → Return HTTP 503 error (no fallback)
  ↓
Cache result for 15 minutes
```

## Critical Conventions

### Cache Management
- **Custom caching system** in `config/caching.py` tracks cache keys in a set (`search_cache_keys`)
- Cache threshold is configurable via `CACHE_THRESHOLD` env var (default: 50)
- Cache keys use `f"search:{hash(frozenset(params.items()))}"` pattern
- Frontend shows alert when cache is full via `cache_state` context processor
- Clear cache via `POST /api/cache/clear` or purge will happen automatically

### PubMed Integration (Production)
- **API calls limited to 200 results per request** (NCBI E-utilities limit)
- **Keyword is OPTIONAL**: Empty keyword defaults to `"medicine[MeSH Terms]"` for general medical articles
- **Study type filters** map to PubMed query syntax via `PUBLICATION_TYPE_MAP`:
  - `randomized_controlled` → `"randomized controlled trial"[Publication Type]`
  - `meta` → `"meta-analysis"[Publication Type]`
  - `cohort` → `"cohort studies"[MeSH Terms]`
  - `case_control` → `"case-control studies"[MeSH Terms]`
  - `systematic_review` → `"systematic review"[Publication Type]`
- **Time period filtering** uses PubMed `mindate`/`maxdate` parameters
- **No fallback data**: Returns HTTP 503 if PubMed API is unavailable
- **Optional `PUBMED_API_KEY`** env var for higher rate limits (10 req/sec vs 3 req/sec)

### API Response Structure
**Success response** (HTTP 200):
```json
{
  "status": "success",
  "data": [
    {
      "pmid": "32741486",
      "doi": "10.1016/j.ecl.2020.05.012",
      "title": "Diabetes Insipidus: An Update",
      "abstract": "The differential diagnosis of diabetes insipidus...",
      "authors": "Smith John, Doe Jane",
      "journal": "Endocrinology and metabolism clinics of North America",
      "year": 2020,
      "study_type": "Journal Article, Review",
      "mesh_terms": ["Diabetes Insipidus", "Diagnosis"],
      "quality": "",
      "sample_size": null,
      "region": "",
      "keywords": ["Diabetes Insipidus", "Diagnosis"],
      "citations": null,
      "impact_factor": null
    }
  ],
  "total": 1075347,
  "returned": 50,
  "page": 1,
  "page_size": 50,
  "page_count": 21507,
  "source": "pubmed",
  "cached": false,
  "message": "PubMed returned 1075347 articles (page 1/21507)"
}
```

**Error response** (HTTP 503 - PubMed unavailable):
```json
{
  "status": "error",
  "message": "PubMed API is currently unavailable. Please try again later.",
  "error": "Connection timeout"
}
```

## Development Workflows

### Running the Application
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run migrations (first time only)
python manage.py migrate

# Start server (or use task "Start Flask App")
python manage.py runserver
```

### Testing Strategy
- **`test_pubmed_only.py`**: Tests PubMed client with and without keyword (production test)
- **`test_pubmed_direct.py`**: Tests PubMed client directly without Django framework
- **`test_search_api.py`**: Tests Django `/api/search` endpoint (legacy)
- **`test_complete.py`**: Integration test for full workflow (legacy)
- Run tests: `python test_pubmed_only.py` (uses venv Python)
- Test page at: `http://127.0.0.1:8000/test/`

**Important**: All tests now verify **real PubMed data only** - no mock articles

### Debugging Tips
- Frontend logs to browser console: search for `console.log("[Search]")` in `search_v3.html`
- Backend uses `logging.getLogger(__name__)` - check terminal output
- PubMed failures trigger fallback with log: `"PubMed search failed; falling back to mock data"`

## Key Files Reference

- **`config/settings.py`**: Environment variables, cache config, REST framework settings
- **`search/urls.py`**: All API routes mapped to view functions
- **`search/views/export.py`**: Excel (openpyxl) and PDF (reportlab) generation - server-side exports
- **`templates/search/search_v3.html`**: Single-page app with Tailwind CSS + Chart.js
- **`static/css/styles.css`**: Minimal custom styles (Tailwind CDN used)

## Project-Specific Patterns

### Export Endpoints (Server-Side)
- **`/export/excel`**: POST with `{articles: [...]}` → Returns `.xlsx` file (openpyxl)
- **`/export/pdf`**: POST with `{articles: [...]}` → Returns `.pdf` file (reportlab, max 25 articles)
- Both generate temp files, read into memory, delete temp file, return as attachment
- Includes: PMID, title, authors, journal, year, study type, quality

### CSRF Handling
- Most API endpoints use `@csrf_exempt` (internal research tool)
- Frontend does not send CSRF tokens for API calls
- Production deployments should implement proper authentication

### Article Metadata from PubMed
Real articles include complete metadata:
- **Required fields**: `pmid`, `title`, `authors`, `journal`, `year`, `abstract`, `study_type`
- **Optional fields**: `doi`, `mesh_terms`, `keywords`, `quality`, `sample_size`, `region`
- **MeSH Terms**: Medical Subject Headings from NLM controlled vocabulary
- **Study Type**: Publication types from PubMed (e.g., "Journal Article, Review")

### Environment Variables
Create `.env` file with:
```
DJANGO_SECRET_KEY=your-secret-key
DEBUG=true
ALLOWED_HOSTS=*
CACHE_THRESHOLD=50
PUBMED_API_KEY=optional-ncbi-key
```

## Migration History
This codebase was migrated from Flask to Django 5. Documentation files (`DIAGNOSTIC_COMPLET.md`, `RECAP.md`) describe the migration process and testing validations.
