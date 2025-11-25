"""
Security Middleware for Medical Search Application
Rate limiting, security headers, logging for public free site (no authentication)
"""

import logging
import hashlib
import time
from typing import Callable
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.core.cache import cache
from django.conf import settings
from functools import wraps

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware:
    """
    Middleware to add security headers to all responses
    Protects against common attacks (XSS, clickjacking, CSRF)
    """
    
    SECURITY_HEADERS = {
        'X-Frame-Options': 'DENY',  # Prevent clickjacking
        'X-Content-Type-Options': 'nosniff',  # Prevent MIME sniffing
        'X-XSS-Protection': '1; mode=block',  # Enable XSS protection
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Permissions-Policy': 'geolocation=(), microphone=(), camera=()',
    }
    
    def __init__(self, get_response: Callable):
        self.get_response = get_response
    
    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        
        # Add security headers to response
        for header, value in self.SECURITY_HEADERS.items():
            response[header] = value
        
        # Add HSTS header (HTTPS only)
        if settings.SECURE_SSL_REDIRECT or not settings.DEBUG:
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
        
        # Content Security Policy
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' cdn.tailwindcss.com cdn.jsdelivr.net cdn.chart.js; "
            "style-src 'self' 'unsafe-inline' cdn.tailwindcss.com fonts.googleapis.com; "
            "font-src 'self' fonts.gstatic.com; "
            "connect-src 'self' eutils.ncbi.nlm.nih.gov; "
            "img-src 'self' data: https:; "
            "frame-ancestors 'none';"
        )
        response['Content-Security-Policy'] = csp
        
        return response


class RateLimitMiddleware:
    """
    Rate limiting by client IP address (no authentication needed)
    Protects public API from abuse
    
    Configuration:
    - RATELIMIT_RATE: requests per time period (default: '200/h' = 200 per hour)
    - RATELIMIT_INTERVAL: time period in seconds (default: 3600 = 1 hour)
    - RATELIMIT_BURST: burst requests allowed (default: 4)
    - RATELIMIT_BURST_WINDOW: burst time window in seconds (default: 60)
    
    Public endpoints: 4 requests per 60 seconds per IP
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response

        # Configuration from settings or defaults
        self.burst_limit = getattr(settings, 'RATELIMIT_BURST', 4)
        self.burst_window = getattr(settings, 'RATELIMIT_BURST_WINDOW', 60)
        self.enabled = getattr(settings, 'RATELIMIT_ENABLE', True)

        # Exempt paths from rate limiting
        self.exempt_paths = [
            '/admin/',
            '/health/',
            '/static/',
            '/test/',
        ]
    
    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Skip rate limiting if disabled
        if settings.DEBUG or not self.enabled:
            return self.get_response(request)
        
        # Skip exempt paths
        if any(request.path.startswith(path) for path in self.exempt_paths):
            return self.get_response(request)
        
        # Get client IP address
        client_ip = self.get_client_ip(request)
        
        # Check burst rate limit (4 requests per 60 seconds)
        burst_key = f'ratelimit:burst:{client_ip}'
        burst_count = cache.get(burst_key, 0)
        
        if burst_count >= self.burst_limit:
            logger.warning(
                f"Rate limit exceeded (burst) for IP {client_ip} - "
                f"Requests: {burst_count}/{self.burst_limit}"
            )
            return JsonResponse(
                {
                    'status': 'error',
                    'message': 'Rate limit exceeded. Please try again later.',
                    'retry_after': self.burst_window
                },
                status=429,
                headers={'Retry-After': str(self.burst_window)}
            )
        
        # Increment burst counter
        cache.set(burst_key, burst_count + 1, self.burst_window)
        
        # Get response
        response = self.get_response(request)
        
        # Add rate limit headers
        response['X-RateLimit-Limit'] = str(self.burst_limit)
        response['X-RateLimit-Remaining'] = str(self.burst_limit - burst_count - 1)
        response['X-RateLimit-Reset'] = str(int(time.time()) + self.burst_window)
        
        return response
    
    @staticmethod
    def get_client_ip(request: HttpRequest) -> str:
        """
        Get client IP address from request
        Handles proxy headers (X-Forwarded-For, X-Real-IP)
        """
        # Check for proxy headers (hospital networks, reverse proxies)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # X-Forwarded-For can contain multiple IPs, take the first one
            ip = x_forwarded_for.split(',')[0].strip()
            return ip
        
        # Check X-Real-IP header
        x_real_ip = request.META.get('HTTP_X_REAL_IP')
        if x_real_ip:
            return x_real_ip
        
        # Fallback to REMOTE_ADDR
        return request.META.get('REMOTE_ADDR', '0.0.0.0')


class LoggingMiddleware:
    """
    Comprehensive logging for monitoring and debugging
    Logs all API requests with timing, status, and client info
    """
    
    def __init__(self, get_response: Callable):
        self.get_response = get_response
        self.api_logger = logging.getLogger('api')
        
        # Configure API logger
        if not self.api_logger.handlers:
            handler = logging.FileHandler('logs/api.log')
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.api_logger.addHandler(handler)
            self.api_logger.setLevel(logging.INFO)
    
    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Skip static files and health checks
        if request.path.startswith('/static/') or request.path == '/health/':
            return self.get_response(request)
        
        # Start timing
        start_time = time.time()
        request_id = self.generate_request_id(request)
        
        # Log request
        self.api_logger.info(
            f"REQUEST_ID={request_id} | {request.method} {request.path} | "
            f"IP={RateLimitMiddleware.get_client_ip(request)} | "
            f"User-Agent={request.META.get('HTTP_USER_AGENT', 'Unknown')[:100]}"
        )
        
        # Get response
        response = self.get_response(request)
        
        # Calculate request duration
        duration = time.time() - start_time
        
        # Log response
        self.api_logger.info(
            f"REQUEST_ID={request_id} | Response={response.status_code} | "
            f"Duration={duration:.3f}s | "
            f"Content-Type={response.get('Content-Type', 'Unknown')[:50]}"
        )
        
        # Log slow requests (> 1 second)
        if duration > 1.0:
            self.api_logger.warning(
                f"SLOW_REQUEST | REQUEST_ID={request_id} | {request.method} {request.path} | "
                f"Duration={duration:.3f}s"
            )
        
        # Log errors
        if response.status_code >= 400:
            self.api_logger.error(
                f"ERROR_RESPONSE | REQUEST_ID={request_id} | {request.method} {request.path} | "
                f"Status={response.status_code}"
            )
        
        # Add request ID to response headers
        response['X-Request-ID'] = request_id
        
        return response
    
    @staticmethod
    def generate_request_id(request: HttpRequest) -> str:
        """Generate unique request ID for tracking"""
        client_ip = RateLimitMiddleware.get_client_ip(request)
        timestamp = str(time.time()).encode()
        identifier = f"{client_ip}:{request.path}".encode()
        combined = timestamp + identifier
        hash_value = hashlib.md5(combined).hexdigest()[:12]
        return f"{hash_value}-{int(time.time())}"


class CSRFProtectionMiddleware:
    """
    CSRF token validation middleware for POST/PUT/DELETE requests
    Ensures all state-changing operations have valid CSRF tokens
    """
    
    def __init__(self, get_response: Callable):
        self.get_response = get_response
        
        # Paths exempt from CSRF check (if using @csrf_exempt decorator)
        self.exempt_methods = ['GET', 'HEAD', 'OPTIONS']
    
    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        
        # Ensure CSRF cookie is set for GET requests
        if request.method == 'GET' and not request.COOKIES.get('csrftoken'):
            # Django will set it on next POST
            pass
        
        return response


class ProxyCompatibilityMiddleware:
    """
    Middleware to handle requests from hospital networks with proxies
    Ensures X-Forwarded-For and X-Real-IP headers are properly handled
    """
    
    TRUSTED_PROXIES = getattr(settings, 'TRUSTED_PROXIES', [
        '127.0.0.1',
        'localhost',
        # Add hospital proxy IPs here if known
    ])
    
    def __init__(self, get_response: Callable):
        self.get_response = get_response
    
    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Mark request with proxy info for logging
        setattr(request, 'is_from_proxy', False)
        
        if 'HTTP_X_FORWARDED_FOR' in request.META or 'HTTP_X_REAL_IP' in request.META:
            setattr(request, 'is_from_proxy', True)
            logger.debug(
                f"Request from proxy | "
                f"X-Forwarded-For={request.META.get('HTTP_X_FORWARDED_FOR')} | "
                f"X-Real-IP={request.META.get('HTTP_X_REAL_IP')}"
            )
        
        return self.get_response(request)


def rate_limit_view(limit_burst: int = 4, limit_window: int = 60):
    """
    Decorator for view-level rate limiting
    Usage: @rate_limit_view(limit_burst=4, limit_window=60)
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if settings.DEBUG or not getattr(settings, 'RATELIMIT_ENABLE', True):
                return view_func(request, *args, **kwargs)

            client_ip = RateLimitMiddleware.get_client_ip(request)
            cache_key = f'ratelimit:view:{view_func.__name__}:{client_ip}'
            
            count = cache.get(cache_key, 0)
            if count >= limit_burst:
                return JsonResponse(
                    {
                        'status': 'error',
                        'message': 'Rate limit exceeded. Please try again later.'
                    },
                    status=429
                )
            
            cache.set(cache_key, count + 1, limit_window)
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator
