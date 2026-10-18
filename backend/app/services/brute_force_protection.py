"""Brute force protection service for authentication endpoints."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from uuid import UUID

try:
    import redis
    from redis import Redis
except ImportError:
    redis = None
    Redis = None

from app.config import settings

logger = logging.getLogger(__name__)


class BruteForceProtection:
    """Service to track and prevent brute force attacks on authentication endpoints."""

    def __init__(self):
        """Initialize brute force protection service."""
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
                logger.info("Using Redis for brute force protection")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis for brute force protection: {e}")
                self.redis_client = None
        
        # In-memory storage as fallback (single instance only)
        if not self.redis_client:
            logger.info("Using in-memory storage for brute force protection (single instance only)")
            self._in_memory_storage: dict = {}

    def _get_key(self, identifier: str, identifier_type: str = "ip") -> str:
        """Generate Redis key for tracking attempts.
        
        Args:
            identifier: IP address or email
            identifier_type: Type of identifier ("ip" or "email")
        
        Returns:
            Redis key string
        """
        return f"brute_force:{identifier_type}:{identifier}"

    def _get_lockout_key(self, identifier: str, identifier_type: str = "ip") -> str:
        """Generate Redis key for lockout status.
        
        Args:
            identifier: IP address or email
            identifier_type: Type of identifier ("ip" or "email")
        
        Returns:
            Redis key string
        """
        return f"brute_force_lockout:{identifier_type}:{identifier}"

    def record_failed_attempt(self, identifier: str, identifier_type: str = "ip") -> Tuple[bool, Optional[int]]:
        """Record a failed authentication attempt.
        
        Args:
            identifier: IP address or email address
            identifier_type: Type of identifier ("ip" or "email")
        
        Returns:
            Tuple of (is_locked_out, remaining_attempts)
        """
        key = self._get_key(identifier, identifier_type)
        lockout_key = self._get_lockout_key(identifier, identifier_type)
        
        window_seconds = settings.BRUTE_FORCE_WINDOW_MINUTES * 60
        
        if self.redis_client:
            try:
                # Increment attempt counter
                attempts = self.redis_client.incr(key)
                
                # Set expiration on first attempt
                if attempts == 1:
                    self.redis_client.expire(key, window_seconds)
                
                # Check if locked out
                lockout_until = self.redis_client.get(lockout_key)
                if lockout_until:
                    lockout_time = datetime.fromisoformat(lockout_until)
                    if lockout_time > datetime.now(timezone.utc):
                        remaining_seconds = int((lockout_time - datetime.now(timezone.utc)).total_seconds())
                        return True, remaining_seconds
                    else:
                        # Lockout expired, clear it
                        self.redis_client.delete(lockout_key)
                
                # Check if max attempts reached
                if attempts >= settings.BRUTE_FORCE_MAX_ATTEMPTS:
                    # Set lockout
                    lockout_until = datetime.now(timezone.utc) + timedelta(
                        minutes=settings.BRUTE_FORCE_LOCKOUT_MINUTES
                    )
                    self.redis_client.set(
                        lockout_key,
                        lockout_until.isoformat(),
                        ex=settings.BRUTE_FORCE_LOCKOUT_MINUTES * 60
                    )
                    remaining_seconds = settings.BRUTE_FORCE_LOCKOUT_MINUTES * 60
                    logger.warning(
                        f"Brute force lockout activated for {identifier_type}:{identifier} "
                        f"after {attempts} failed attempts"
                    )
                    return True, remaining_seconds
                
                remaining = settings.BRUTE_FORCE_MAX_ATTEMPTS - attempts
                return False, remaining
                
            except Exception as e:
                logger.error(f"Error recording failed attempt in Redis: {e}")
                # Fall through to in-memory storage
                pass
        
        # In-memory storage fallback
        if identifier not in self._in_memory_storage:
            self._in_memory_storage[identifier] = {
                "attempts": 0,
                "first_attempt": datetime.now(timezone.utc),
                "lockout_until": None,
            }
        
        record = self._in_memory_storage[identifier]
        now = datetime.now(timezone.utc)
        
        # Reset if window expired
        if record["first_attempt"] + timedelta(minutes=settings.BRUTE_FORCE_WINDOW_MINUTES) < now:
            record["attempts"] = 0
            record["first_attempt"] = now
            record["lockout_until"] = None
        
        # Check if locked out
        if record["lockout_until"] and record["lockout_until"] > now:
            remaining_seconds = int((record["lockout_until"] - now).total_seconds())
            return True, remaining_seconds
        
        # Increment attempts
        record["attempts"] += 1
        
        # Check if max attempts reached
        if record["attempts"] >= settings.BRUTE_FORCE_MAX_ATTEMPTS:
            record["lockout_until"] = now + timedelta(minutes=settings.BRUTE_FORCE_LOCKOUT_MINUTES)
            remaining_seconds = settings.BRUTE_FORCE_LOCKOUT_MINUTES * 60
            logger.warning(
                f"Brute force lockout activated for {identifier_type}:{identifier} "
                f"after {record['attempts']} failed attempts"
            )
            return True, remaining_seconds
        
        remaining = settings.BRUTE_FORCE_MAX_ATTEMPTS - record["attempts"]
        return False, remaining

    def clear_attempts(self, identifier: str, identifier_type: str = "ip") -> None:
        """Clear failed attempts for an identifier (e.g., on successful login).
        
        Args:
            identifier: IP address or email address
            identifier_type: Type of identifier ("ip" or "email")
        """
        key = self._get_key(identifier, identifier_type)
        lockout_key = self._get_lockout_key(identifier, identifier_type)
        
        if self.redis_client:
            try:
                self.redis_client.delete(key)
                self.redis_client.delete(lockout_key)
            except Exception as e:
                logger.error(f"Error clearing attempts in Redis: {e}")
        else:
            # In-memory storage
            if identifier in self._in_memory_storage:
                del self._in_memory_storage[identifier]

    def is_locked_out(self, identifier: str, identifier_type: str = "ip") -> Tuple[bool, Optional[int]]:
        """Check if an identifier is currently locked out.
        
        Args:
            identifier: IP address or email address
            identifier_type: Type of identifier ("ip" or "email")
        
        Returns:
            Tuple of (is_locked_out, remaining_seconds)
        """
        lockout_key = self._get_lockout_key(identifier, identifier_type)
        
        if self.redis_client:
            try:
                lockout_until = self.redis_client.get(lockout_key)
                if lockout_until:
                    lockout_time = datetime.fromisoformat(lockout_until)
                    if lockout_time > datetime.now(timezone.utc):
                        remaining_seconds = int((lockout_time - datetime.now(timezone.utc)).total_seconds())
                        return True, remaining_seconds
                    else:
                        # Lockout expired
                        self.redis_client.delete(lockout_key)
                        return False, None
                return False, None
            except Exception as e:
                logger.error(f"Error checking lockout in Redis: {e}")
                return False, None
        
        # In-memory storage
        if identifier in self._in_memory_storage:
            record = self._in_memory_storage[identifier]
            if record["lockout_until"] and record["lockout_until"] > datetime.now(timezone.utc):
                remaining_seconds = int((record["lockout_until"] - datetime.now(timezone.utc)).total_seconds())
                return True, remaining_seconds
        
        return False, None


# Global instance
_brute_force_protection: Optional[BruteForceProtection] = None


def get_brute_force_protection() -> BruteForceProtection:
    """Get the global brute force protection instance."""
    global _brute_force_protection
    if _brute_force_protection is None:
        _brute_force_protection = BruteForceProtection()
    return _brute_force_protection

