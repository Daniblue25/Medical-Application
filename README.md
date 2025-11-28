# Medical Search Platform v3.1

**Author:** FIANKO Kossi Jean-Jacques Daniel  
**Copyright:** © 2025 DRCI - CHU Clermont-Ferrand. All rights reserved.  
**License:** MIT License (see LICENSE file)

---

## Overview

Medical Search Platform is an advanced web application for searching and analyzing medical literature from PubMed. The platform provides intelligent filtering, batch search capabilities, caching system, and comprehensive analytics.

## Key Features

### v3.1 Features
- **SQLite Cache System**: 7-day cache validity for faster repeated searches
- **Batch Search**: Search multiple keywords simultaneously (separated by `;` or newlines)
- **Region Filtering**: Filter articles by geographic region (last author location)
- **Real-time Analytics**: Interactive charts for publication trends
- **Export Capabilities**: Export results to CSV format
- **Advanced Filters**: Journal quality, study type, publication year, sample size

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

6. **Start development server**
```bash
python manage.py runserver
```

7. **Access the application**
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
- Click "Export to CSV" to download results
- Includes all article metadata and filters applied

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
│   ├── services/        # Business logic (PubMed client, region detector, LLM extractor)
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

## Documentation

- **BENCHMARK.md**: Comparative analysis and competitive positioning
- **REGION_FILTER_FIX.md**: Technical documentation on region filter implementation
- **LICENSE**: MIT License terms and conditions

## Version History

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
**Project:** Medical Search Platform  
**Version:** 3.1  
**Year:** 2025

This software is the intellectual property of DRCI - CHU Clermont-Ferrand and is protected under copyright law. Unauthorized use, reproduction, or distribution is prohibited without explicit permission from the copyright holder.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright (c) 2025 DRCI - CHU Clermont-Ferrand

---

**For questions or support, please contact the author.**
