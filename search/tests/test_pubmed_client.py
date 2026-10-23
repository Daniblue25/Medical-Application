import os
from unittest.mock import patch

from search.services import pubmed_client


def test_extract_proxy_from_pac_returns_default_proxy():
    pac_content = '''
    function FindProxyForURL(url, host) {
        if (dnsDomainIs(host, "example.org")) return "DIRECT";
        return "PROXY proxy.example.org:8080";
    }
    '''

    proxy = pubmed_client._extract_proxy_from_pac(pac_content)

    assert proxy == 'http://proxy.example.org:8080'


def test_build_proxy_configuration_prefers_environment_variables():
    with patch.dict(
        os.environ,
        {
            'PUBMED_HTTP_PROXY': 'http://proxy-http.example:8080',
            'PUBMED_HTTPS_PROXY': 'proxy-https.example:8443',
        },
        clear=True,
    ):
        with patch('search.services.pubmed_client._get_windows_proxy_url', return_value=None):
            proxies = pubmed_client._build_proxy_configuration()

    assert proxies == {
        'http': 'http://proxy-http.example:8080',
        'https': 'http://proxy-https.example:8443',
    }


def test_build_proxy_configuration_falls_back_to_windows_proxy():
    with patch.dict(os.environ, {}, clear=True):
        with patch(
            'search.services.pubmed_client._get_windows_proxy_url',
            return_value='http://proxy.example.org:8080',
        ):
            proxies = pubmed_client._build_proxy_configuration()

    assert proxies == {
        'http': 'http://proxy.example.org:8080',
        'https': 'http://proxy.example.org:8080',
    }