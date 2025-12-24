"""
API Configuration Module - Read API keys from Supabase

This allows changing API keys without redeploying the application.
Falls back to environment variables if database config not found.
"""

import os
from typing import Optional, Dict
from functools import lru_cache
from datetime import datetime, timedelta

# Cache expiry time (5 minutes)
_cache = {}
_cache_time = {}
CACHE_TTL = timedelta(minutes=5)


def _get_supabase_client():
    """Get Supabase client for reading configs"""
    try:
        from supabase import create_client
        url = os.environ.get('SUPABASE_URL', '')
        key = os.environ.get('SUPABASE_SERVICE_KEY', '')
        if url and key:
            return create_client(url, key)
    except Exception as e:
        print(f"[API Config] Failed to create Supabase client: {e}")
    return None


def _is_cache_valid(platform: str) -> bool:
    """Check if cached config is still valid"""
    if platform not in _cache_time:
        return False
    return datetime.now() - _cache_time[platform] < CACHE_TTL


def get_api_config(platform: str) -> Optional[Dict]:
    """
    Get API configuration for a platform.

    Returns dict with: api_key, api_host, enabled
    Falls back to environment variables if database not available.
    """
    # Check cache first
    if _is_cache_valid(platform):
        return _cache.get(platform)

    # Try to get from Supabase
    client = _get_supabase_client()
    if client:
        try:
            result = client.table('api_configs').select('*').eq('platform', platform).single().execute()
            if result.data:
                config = {
                    'api_key': result.data.get('api_key', ''),
                    'api_host': result.data.get('api_host', ''),
                    'enabled': result.data.get('enabled', True),
                    'notes': result.data.get('notes', ''),
                    'source': 'database'
                }
                # Update cache
                _cache[platform] = config
                _cache_time[platform] = datetime.now()
                return config
        except Exception as e:
            print(f"[API Config] Failed to get config from database for {platform}: {e}")

    # Fallback to environment variables
    env_key_map = {
        'instagram': 'INSTAGRAM_API_KEY',
        'tiktok': 'TIKTOK_API_KEY',
        'youtube': 'YOUTUBE_API_KEY',
        'twitter': 'TWITTER_API_KEY'
    }

    env_host_map = {
        'instagram': 'instagram120.p.rapidapi.com',
        'tiktok': 'tiktok-api23.p.rapidapi.com',
        'youtube': None,
        'twitter': 'twitter-api45.p.rapidapi.com'
    }

    env_var = env_key_map.get(platform)
    if env_var:
        api_key = os.environ.get(env_var, '')
        if api_key:
            config = {
                'api_key': api_key,
                'api_host': env_host_map.get(platform),
                'enabled': True,
                'notes': 'From environment variable',
                'source': 'env'
            }
            # Update cache
            _cache[platform] = config
            _cache_time[platform] = datetime.now()
            return config

    return None


def get_api_key(platform: str) -> str:
    """Get just the API key for a platform"""
    config = get_api_config(platform)
    return config.get('api_key', '') if config else ''


def get_api_host(platform: str) -> Optional[str]:
    """Get the API host for a platform (for RapidAPI)"""
    config = get_api_config(platform)
    return config.get('api_host') if config else None


def is_platform_enabled(platform: str) -> bool:
    """Check if a platform is enabled"""
    config = get_api_config(platform)
    return config.get('enabled', False) if config else False


def clear_cache(platform: str = None):
    """Clear config cache (useful after updates)"""
    if platform:
        _cache.pop(platform, None)
        _cache_time.pop(platform, None)
    else:
        _cache.clear()
        _cache_time.clear()


def get_all_configs() -> Dict[str, Dict]:
    """Get all API configurations"""
    platforms = ['instagram', 'tiktok', 'youtube', 'twitter']
    return {p: get_api_config(p) for p in platforms}
