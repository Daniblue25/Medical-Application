from django.urls import path
from django.views.generic import TemplateView
from .views.search import search_api, sample_api, export_all_results, batch_search_api
from .views.export import export_excel, export_pdf
from .views.cache import clear_cache, cache_status

urlpatterns = [
    path('', TemplateView.as_view(template_name='search/search_v3.html'), name='search-home'),
    path('about/', TemplateView.as_view(template_name='search/about.html'), name='about'),
    path('api/search/', search_api, name='api-search'),
    path('api/batch-search/', batch_search_api, name='api-batch-search'),
    path('api/sample/', sample_api, name='api-sample'),
    path('api/export-all/', export_all_results, name='export-all-results'),
    path('export/excel/', export_excel, name='export-excel'),
    path('export/pdf/', export_pdf, name='export-pdf'),
    path('api/cache/clear/', clear_cache, name='cache-clear'),
    path('api/cache/status/', cache_status, name='cache-status'),
]
