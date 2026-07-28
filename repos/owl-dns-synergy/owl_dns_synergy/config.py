"""
Unified configuration for OWL-DNS-Synergy.
Merges OWL-AGENT config.json + LLM-DNS-Proxy env vars.
"""

import os
import json
from pathlib import Path
from typing import Optional, List

SYNERGY_HOME = Path(os.getenv("OWL_DNS_SYNERGY_HOME", str(Path.home() / ".owl-dns-synergy")))
CONFIG_DIR = SYNERGY_HOME / "config"
CACHE_DIR = SYNERGY_HOME / "cache" / "http"
PROXY_CACHE_FILE = CONFIG_DIR / "proxy_cache.json"

CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class SynergyConfig:
    """Unified configuration from JSON file + environment variables."""

    def __init__(self):
        self._config = self._load_config()
        # Apply env var overrides
        self._apply_env()

    def _load_config(self) -> dict:
        config_file = CONFIG_DIR / "config.json"
        if config_file.exists():
            with open(config_file) as f:
                return json.load(f)
        # Write defaults
        defaults = {
            "cache_ttl": 300,
            "rate_limit": 1.0,
            "max_retries": 3,
            "countries": ["US", "GB", "DE", "FR", "CA"],
            "use_curl_cffi": True,
            "use_redis": False,
            "redis_url": "redis://localhost:6379",
            "dns_suffix": "_sonos._udp.local",
            "dns_port": 5353,
            "dns_host": "127.0.0.1",
            "openai_model": "gpt-4o",
            "openai_base_url": "https://api.openai.com/v1",
            "prometheus_port": 9090,
            "dns_flood_max_qps": 50,
            "dns_flood_burst": 100,
        }
        with open(config_file, "w") as f:
            json.dump(defaults, f, indent=2)
        return defaults

    def _apply_env(self):
        """Override config values with environment variables."""
        env_map = {
            "OPENAI_API_KEY": "openai_api_key",
            "OPENAI_BASE_URL": "openai_base_url",
            "OPENAI_MODEL": "openai_model",
            "LLM_PROXY_KEY": "llm_proxy_key",
            "LLM_DNS_SUFFIX": "dns_suffix",
            "PERPLEXITY_API_KEY": "perplexity_api_key",
            "REDIS_URL": "redis_url",
            "OWL_DNS_PROMETHEUS_PORT": "prometheus_port",
        }
        for env_key, config_key in env_map.items():
            val = os.getenv(env_key)
            if val:
                self._config[config_key] = val

    # --- Accessors ---
    @property
    def openai_api_key(self) -> Optional[str]:
        return self._config.get("openai_api_key") or os.getenv("OPENAI_API_KEY")

    @property
    def openai_base_url(self) -> str:
        return self._config.get("openai_base_url", "https://api.openai.com/v1")

    @property
    def openai_model(self) -> str:
        return self._config.get("openai_model", "gpt-4o")

    @property
    def perplexity_api_key(self) -> Optional[str]:
        return self._config.get("perplexity_api_key") or os.getenv("PERPLEXITY_API_KEY")

    @property
    def llm_proxy_key(self) -> Optional[str]:
        return self._config.get("llm_proxy_key") or os.getenv("LLM_PROXY_KEY")

    @property
    def dns_suffix(self) -> str:
        return self._config.get("dns_suffix", "_sonos._udp.local")

    @property
    def dns_host(self) -> str:
        return self._config.get("dns_host", "127.0.0.1")

    @property
    def dns_port(self) -> int:
        return self._config.get("dns_port", 5353)

    @property
    def redis_url(self) -> str:
        return self._config.get("redis_url", "redis://localhost:6379")

    @property
    def use_redis(self) -> bool:
        return self._config.get("use_redis", False)

    @property
    def use_curl_cffi(self) -> bool:
        return self._config.get("use_curl_cffi", True)

    @property
    def cache_ttl(self) -> int:
        return self._config.get("cache_ttl", 300)

    @property
    def max_retries(self) -> int:
        return self._config.get("max_retries", 3)

    @property
    def countries(self) -> List[str]:
        return self._config.get("countries", ["US", "GB", "DE", "FR", "CA"])

    @property
    def rate_limit(self) -> float:
        return self._config.get("rate_limit", 1.0)

    @property
    def prometheus_port(self) -> int:
        return self._config.get("prometheus_port", 9090)

    @property
    def dns_flood_max_qps(self) -> int:
        return self._config.get("dns_flood_max_qps", 50)

    @property
    def dns_flood_burst(self) -> int:
        return self._config.get("dns_flood_burst", 100)

    def get_dns_suffix_parts(self) -> list:
        return self.dns_suffix.split(".")

    def format_dns_query(self, prefix: str, *parts) -> str:
        middle = '.'.join(str(p) for p in parts) if parts else ""
        if middle:
            return f"{prefix}.{middle}.{self.dns_suffix}"
        return f"{prefix}.{self.dns_suffix}"

    def validate_dns_suffix_in_query(self, query_parts: list) -> bool:
        expected = self.get_dns_suffix_parts()
        if query_parts and query_parts[-1] == '':
            query_parts = query_parts[:-1]
        if len(query_parts) < len(expected):
            return False
        return query_parts[-len(expected):] == expected
