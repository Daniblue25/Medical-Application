"""
Import journal impact factors from the SIGAPS workbook ("Rang SIGAPS 2020-2024.xlsx").

Usage:
    python manage.py import_impact_factors "distribution/Rang SIGAPS 2020-2024.xlsx"

Only the impact factors of the requested year (default 2024) are kept. Journals
without an impact factor for that year are left out: the interface then shows
"Not available" rather than a value from another year.
"""

import json
import os
from datetime import datetime, timezone

from django.core.management.base import BaseCommand, CommandError

from search.services.impact_factor import IMPACT_FACTOR_YEAR, clear_cache, get_data_path


def _parse_if(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(',', '.')
    try:
        return float(text)
    except ValueError:
        return None


class Command(BaseCommand):
    help = "Build the impact factor lookup file from the SIGAPS workbook"

    def add_arguments(self, parser):
        parser.add_argument('workbook', help='Path to "Rang SIGAPS 2020-2024.xlsx"')
        parser.add_argument('--year', type=int, default=IMPACT_FACTOR_YEAR, help='Impact factor year to keep')
        parser.add_argument('--output', default=None, help='Output JSON (default: search/data/impact_factors_<year>.json)')

    def handle(self, *args, **options):
        import openpyxl

        path, year = options['workbook'], options['year']
        if not os.path.exists(path):
            raise CommandError(f"File not found: {path}")

        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.worksheets[0]
        rows = ws.iter_rows(values_only=True)
        header, subheader = next(rows), next(rows)

        # Row 1 holds the column names and the years; row 2 holds "IF" / "Cat." under each year.
        names = [str(h).strip().lower() if h is not None else '' for h in header]
        try:
            col_nlm, col_issn, col_essn, col_ta = (names.index(n) for n in ('nlmid', 'issn', 'essn', 'titre'))
            col_if = list(header).index(year)
        except ValueError as exc:
            raise CommandError(f"Unexpected workbook layout (missing column or year {year}): {exc}")
        if str(subheader[col_if]).strip().upper() != 'IF':
            raise CommandError(f"Column under {year} is '{subheader[col_if]}', expected 'IF'")

        journals, skipped = [], 0
        for row in rows:
            impact = _parse_if(row[col_if])
            if impact is None or not row[col_ta]:
                skipped += 1
                continue
            journals.append({
                'nlm_id': str(row[col_nlm]).strip() if row[col_nlm] is not None else '',
                'issn': [str(v).strip() for v in (row[col_issn], row[col_essn]) if v],
                'ta': str(row[col_ta]).strip(),
                'if': impact,
            })
        wb.close()

        output = options['output'] or get_data_path()
        os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
        with open(output, 'w', encoding='utf-8') as f:
            json.dump({
                'source': os.path.basename(path),
                'year': year,
                'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                'journals': journals,
            }, f, ensure_ascii=False, separators=(',', ':'))
        clear_cache()

        self.stdout.write(self.style.SUCCESS(
            f"{len(journals)} journals with a {year} impact factor written to {output} "
            f"({skipped} rows without a {year} value skipped)"
        ))
