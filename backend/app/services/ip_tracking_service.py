"""IP tracking service for rate limiting and blocking."""

import logging
from typing import Optional, Set, Tuple
from datetime import datetime, timedelta, timezone

try:
    import redis
    from redis import Redis
except ImportError:
    redis = None
    Redis = None

from app.config import settings

logger = logging.getLogger(__name__)


class IPTrackingService:
    """Service to track IP addresses for rate limiting and blocking."""

    def __init__(self):
        """Initialize IP tracking service."""
        self.redis_client: Optional[Redis] = None
        
        # Try to connect to Redis if configured
        if settings.RATE_LIMIT_STORAGE_URL:
            try:
                self.redis_client = redis.from_url(
                    settings.RATE_LIMIT_STORAGE_URL,
                    decode_responses=True
                )
                # Test connection
                self.redis_client.ping()
                logger.info("Using Redis for IP tracking")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis for IP tracking: {e}")
                self.redis_client = None
        
        # In-memory storage as fallback (single instance only)
        if not self.redis_client:
            logger.info("Using in-memory storage for IP tracking (single instance only)")
            self._in_memory_storage: dict = {}
            self._blacklist: Set[str] = set()
            self._whitelist: Set[str] = set()

    def _get_request_count_key(self, ip: str) -> str:
        """Generate Redis key for request count tracking."""
        return f"ip_requests:{ip}"

    def _get_error_count_key(self, ip: str) -> str:
        """Generate Redis key for error count tracking."""
        return f"ip_errors:{ip}"

    def track_request(self, ip: str) -> None:
        """Track a request from an IP address.
        
        Args:
            ip: IP address to track
        """
        if not ip or ip == "unknown":
            return
        
        key = self._get_request_count_key(ip)
        window_seconds = 60  # 1 minute window
        
        if self.redis_client:
            try:
                # Increment request count
                count = self.redis_client.incr(key)
                
                # Set expiration on first request
                if count == 1:
                    self.redis_client.expire(key, window_seconds)
            except Exception as e:
                logger.error(f"Error tracking request in Redis: {e}")
        else:
            # In-memory storage
            now = datetime.now(timezone.utc)
            if ip not in self._in_memory_storage:
                self._in_memory_storage[ip] = {
                    "requests": [],
                    "errors": [],
                }
            
            record = self._in_memory_storage[ip]
            # Remove old requests outside window
            cutoff = now - timedelta(seconds=window_seconds)
            record["requests"] = [
                ts for ts in record["requests"] if ts > cutoff
            ]
            record["requests"].append(now)

    def track_error(self, ip: str) -> None:
        """Track an error response for an IP address.
        
        Args:
            ip: IP address to track
        """
        if not ip or ip == "unknown":
            return
        
        key = self._get_error_count_key(ip)
        window_seconds = 300  # 5 minute window
        
        if self.redis_client:
            try:
                # Increment error count
                count = self.redis_client.incr(key)
                
                # Set expiration on first error
                if count == 1:
                    self.redis_client.expire(key, window_seconds)
            except Exception as e:
                logger.error(f"Error tracking error in Redis: {e}")
        else:
            # In-memory storage
            now = datetime.now(timezone.utc)
            if ip not in self._in_memory_storage:
                self._in_memory_storage[ip] = {
                    "requests": [],
                    "errors": [],
                }
            
            record = self._in_memory_storage[ip]
            # Remove old errors outside window
            cutoff = now - timedelta(seconds=window_seconds)
            record["errors"] = [
                ts for ts in record["errors"] if ts > cutoff
            ]
            record["errors"].append(now)

    def get_request_count(self, ip: str, window_seconds: int = 60) -> int:
        """Get request count for an IP in a time window.
        
        Args:
            ip: IP address
            window_seconds: Time window in seconds
        
        Returns:
            Number of requests in the window
        """
        if not ip or ip == "unknown":
            return 0
        
        key = self._get_request_count_key(ip)
        
        if self.redis_client:
            try:
                count = self.redis_client.get(key)
                return int(count) if count else 0
            except Exception as e:
                logger.error(f"Error getting request count from Redis: {e}")
                return 0
        else:
            # In-memory storage
            if ip not in self._in_memory_storage:
                return 0
            
            record = self._in_memory_storage[ip]
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(seconds=window_seconds)
            return len([ts for ts in record["requests"] if ts > cutoff])

    def get_error_count(self, ip: str, window_seconds: int = 300) -> int:
        """Get error count for an IP in a time window.
        
        Args:
            ip: IP address
            window_seconds: Time window in seconds
        
        Returns:
            Number of errors in the window
        """
        if not ip or ip == "unknown":
            return 0
        
        key = self._get_error_count_key(ip)
        
        if self.redis_client:
            try:
                count = self.redis_client.get(key)
                return int(count) if count else 0
            except Exception as e:
                logger.error(f"Error getting error count from Redis: {e}")
                return 0
        else:
            # In-memory storage
            if ip not in self._in_memory_storage:
                return 0
            
            record = self._in_memory_storage[ip]
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(seconds=window_seconds)
            return len([ts for ts in record["errors"] if ts > cutoff])

    def is_blacklisted(self, ip: str) -> bool:
        """Check if an IP is blacklisted.
        
        Args:
            ip: IP address to check
        
        Returns:
            True if IP is blacklisted
        """
        if not ip or ip == "unknown":
            return False
        
        if self.redis_client:
            try:
                key = f"ip_blacklist:{ip}"
                return self.redis_client.exists(key) > 0
            except Exception as e:
                logger.error(f"Error checking blacklist in Redis: {e}")
                return False
        else:
            return ip in self._blacklist

    def is_whitelisted(self, ip: str) -> bool:
        """Check if an IP is whitelisted.
        
        Args:
            ip: IP address to check
        
        Returns:
            True if IP is whitelisted
        """
        if not ip or ip == "unknown":
            return False
        
        if self.redis_client:
            try:
                key = f"ip_whitelist:{ip}"
                return self.redis_client.exists(key) > 0
            except Exception as e:
                logger.error(f"Error checking whitelist in Redis: {e}")
                return False
        else:
            return ip in self._whitelist

    def add_to_blacklist(self, ip: str, ttl_seconds: Optional[int] = None) -> None:
        """Add an IP to the blacklist.
        
        Args:
            ip: IP address to blacklist
            ttl_seconds: Optional TTL in seconds (None = permanent)
        """
        if not ip or ip == "unknown":
            return
        
        if self.redis_client:
            try:
                key = f"ip_blacklist:{ip}"
                if ttl_seconds:
                    self.redis_client.setex(key, ttl_seconds, "1")
                else:
                    self.redis_client.set(key, "1")
                logger.info(f"Added IP {ip} to blacklist")
            except Exception as e:
                logger.error(f"Error adding to blacklist in Redis: {e}")
        else:
            self._blacklist.add(ip)
            logger.info(f"Added IP {ip} to blacklist")

    def remove_from_blacklist(self, ip: str) -> None:
        """Remove an IP from the blacklist.
        
        Args:
            ip: IP address to remove
        """
        if not ip or ip == "unknown":
            return
        
        if self.redis_client:
            try:
                key = f"ip_blacklist:{ip}"
                self.redis_client.delete(key)
                logger.info(f"Removed IP {ip} from blacklist")
            except Exception as e:
                logger.error(f"Error removing from blacklist in Redis: {e}")
        else:
            self._blacklist.discard(ip)
            logger.info(f"Removed IP {ip} from blacklist")


# Global instance
_ip_tracking_service: Optional[IPTrackingService] = None


def get_ip_tracking_service() -> IPTrackingService:
    """Get the global IP tracking service instance."""
    global _ip_tracking_service
    if _ip_tracking_service is None:
        _ip_tracking_service = IPTrackingService()
    return _ip_tracking_service

