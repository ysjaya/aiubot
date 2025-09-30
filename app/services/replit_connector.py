import os
import httpx
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Cache for the connection settings
_cached_settings = None
_cache_expiry = None

async def get_github_access_token() -> str:
    """
    Get GitHub access token from Replit connector
    Handles token caching and refresh
    """
    global _cached_settings, _cache_expiry
    
    # Check if cached token is still valid
    if _cached_settings and _cache_expiry:
        if datetime.fromisoformat(_cache_expiry.replace('Z', '+00:00')) > datetime.utcnow():
            return _cached_settings.get('access_token', '')
    
    # Get connector hostname and authentication
    hostname = os.getenv('REPLIT_CONNECTORS_HOSTNAME')
    
    # Try repl identity first, then deployment identity
    x_replit_token = None
    repl_identity = os.getenv('REPL_IDENTITY')
    web_repl_renewal = os.getenv('WEB_REPL_RENEWAL')
    
    if repl_identity:
        x_replit_token = f'repl {repl_identity}'
    elif web_repl_renewal:
        x_replit_token = f'depl {web_repl_renewal}'
    
    if not x_replit_token or not hostname:
        logger.warning("Replit connector not available, falling back to manual GitHub token")
        # Fallback to manual token if available
        github_token = os.getenv('GITHUB_TOKEN', '')
        if github_token:
            return github_token
        raise Exception("GitHub not connected via Replit connector and no manual token found")
    
    # Fetch connection settings from Replit
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f'https://{hostname}/api/v2/connection?include_secrets=true&connector_names=github',
                headers={
                    'Accept': 'application/json',
                    'X_REPLIT_TOKEN': x_replit_token
                },
                timeout=10.0
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to get GitHub connection: HTTP {response.status_code}")
            
            data = response.json()
            items = data.get('items', [])
            
            if not items:
                raise Exception("GitHub connection not found in Replit")
            
            connection = items[0]
            settings = connection.get('settings', {})
            
            # Try to get access token from different locations
            access_token = (
                settings.get('access_token') or
                settings.get('oauth', {}).get('credentials', {}).get('access_token')
            )
            
            if not access_token:
                raise Exception("No access token found in GitHub connection")
            
            # Update cache
            _cached_settings = settings
            _cache_expiry = settings.get('expires_at')
            
            logger.info("Successfully retrieved GitHub access token from Replit connector")
            return access_token
            
    except httpx.TimeoutException:
        logger.error("Timeout while fetching GitHub connection from Replit")
        raise Exception("GitHub connection timeout")
    except Exception as e:
        logger.error(f"Error getting GitHub token from Replit connector: {e}")
        raise

def get_github_access_token_sync() -> str:
    """
    Synchronous wrapper for getting GitHub token
    Uses environment variable fallback if connector not available
    """
    # Try to use Replit connector token first
    hostname = os.getenv('REPLIT_CONNECTORS_HOSTNAME')
    
    if hostname:
        # If connector is available, use async version
        import asyncio
        try:
            return asyncio.run(get_github_access_token())
        except Exception as e:
            logger.warning(f"Failed to get token from connector: {e}")
    
    # Fallback to environment variable
    github_token = os.getenv('GITHUB_TOKEN', '')
    if github_token:
        logger.info("Using GitHub token from environment variable")
        return github_token
    
    raise Exception("GitHub not connected and no token available")
