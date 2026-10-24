# MedLitSearch Platform v3.2

**Author:** FIANKO Kossi Jean-Jacques Daniel  
**Copyright:** © 2025 DRCI - CHU Clermont-Ferrand. All rights reserved.  
**License:** MIT License (see LICENSE file)

---

## Overview

MedLitSearch Platform is an advanced web application for searching and analyzing medical literature from PubMed. The platform provides intelligent filtering, batch search capabilities, caching system, and comprehensive analytics.

## Key Features

### Features
- **SQLite Cache System**: 7-day cache validity for faster repeated searches
- **Batch Search**: Search multiple keywords simultaneously (separated by `;` or newlines)
- **Journal Filter**: All PubMed journals, Surgery (two groups: High and Medium Impact Factor) or Nurse (144 nursing journals)
- **Impact Factor**: Journal Impact Factor (Clarivate JCR 2024) shown in the details of each result and in the Excel export
- **Region Filtering**: Filter articles by geographic region (last author location)
- **Real-time Analytics**: Interactive charts for publication trends
- **Export Capabilities**: Export results to Excel (.xlsx) or RIS (Zotero, Mendeley, EndNote)
- **Advanced Filters**: Article type, surgery type, publication years, region, study center

### Core Functionality
- PubMed API integration with intelligent caching
- Region detection from author affiliations
- Automated deduplication (by PMID)
- Responsive design with Tailwind CSS
- RESTful API backend with Django REST Framework

## Quick Start

### Prerequisites
- Python 3.8 or higher
- pip (Python package installer)

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd med_search_app
```

2. **Create virtual environment**
```bash
python -m venv venv
```

3. **Activate virtual environment**
- Windows: `venv\Scripts\activate`
- Linux/Mac: `source venv/bin/activate`

4. **Install dependencies**
```bash
pip install -r requirements.txt
```

5. **Run migrations**
```bash
python manage.py migrate
```

6. **Import the journal impact factors** (optional)
```bash
python manage.py import_impact_factors "distribution/Rang SIGAPS 2020-2024.xlsx"
```
This builds `search/data/impact_factors_2024.json` from the SIGAPS workbook (2024 values only).
The file is not versioned (licensed JCR data). Without it, impact factors are shown as "Not available".

7. **Start development server**
```bash
python manage.py runserver
```

8. **Access the application**
Open your browser and navigate to: `http://127.0.0.1:8000`

## Usage

### Single Search
1. Enter keywords in the search box
2. Optionally select filters (region, journal quality, study type, etc.)
3. Click "Search" or press Enter
4. View and analyze results

### Batch Search
1. Enter multiple keywords separated by `;` or newlines
2. Maximum 10 queries per batch
3. Results are automatically combined and deduplicated
4. Example:
```
diabetes treatment
hypertension therapy
cancer immunotherapy
```

### Region Filter
- Filter articles by geographic region based on last author affiliation
- Available regions: North America, Europe, Asia, Africa, South America, Oceania
- Change filter anytime to re-filter current results instantly

### Export Results
- Click "Excel" or "RIS" to download the results (with the region, year and study-center filters applied)
- The Excel file includes the journal impact factor, sample size, primary outcome and author countries

## Technology Stack

- **Backend**: Django 5.0.7 + Django REST Framework 3.15
- **Frontend**: Vanilla JavaScript + Tailwind CSS
- **Database**: SQLite (cache storage)
- **API**: PubMed E-utilities
- **Python**: 3.13

## Project Structure

```
med_search_app/
├── config/              # Django settings and configuration
├── search/              # Main application
│   ├── services/        # Business logic (PubMed client, deterministic rule-based extractors)
│   ├── views/           # API endpoints (search, export, cache)
│   └── models.py        # Database models (SearchCache, CachedArticle)
├── templates/           # HTML templates
│   └── search/
│       ├── search_v3.html   # Main SPA interface
│       └── about.html       # About page with benchmark
├── static/              # Static files (CSS)
├── manage.py            # Django management script
├── requirements.txt     # Python dependencies
└── LICENSE              # MIT License
```

## Performance

- **Cache Hit**: ~50ms (instant results from local database)
- **Cache Miss**: ~2-5 seconds (PubMed API fetch + processing)
- **Batch Search**: 5 parallel workers, ~3-10 seconds for 10 queries
- **Region Filtering**: Instant (client-side processing)

## Reproducibility

The extractors are deterministic (regular expressions and rules, no machine-learning
or generative model): the same abstract always produces the same extracted value.

## Documentation

- **LICENSE**: MIT License terms and conditions

## Version History

### v3.2 (2026)
- Article language detection; NLP extraction rules for English and French abstracts
- Multicenter detector
- Journal filter with Surgery groups (High / Medium Impact Factor) and journal impact factor (Clarivate JCR 2024)

### v3.1 (2025)
- Added SQLite cache system (7-day validity)
- Implemented batch search with parallel processing
- Added client-side region filtering
- Enhanced user feedback with filter statistics
- Created comprehensive About page

### v3.0 (2025)
- Initial release with PubMed integration
- Basic filtering and analytics
- CSV export functionality

## Author Information

**Name:** FIANKO Kossi Jean-Jacques Daniel  
**Project:** MedLitSearch Platform  
**Version:** 3.2  
**Year:** 2026

This software is the intellectual property of DRCI - CHU Clermont-Ferrand and is protected under copyright law. Unauthorized use, reproduction, or distribution is prohibited without explicit permission from the copyright holder.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright (c) 2025 DRCI - CHU Clermont-Ferrand

---

**For questions or support, please contact the author.**
