"""Test script to verify Google Cloud Vision API setup."""

import os
import sys
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

def test_vision_setup():
    """Test Google Vision Service initialization and configuration."""
    print("=" * 60)
    print("Google Cloud Vision API Setup Test")
    print("=" * 60)
    print()
    
    # Check environment variables
    print("1. Checking environment variables...")
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
    credentials_path = os.getenv("GOOGLE_CLOUD_VISION_CREDENTIALS_PATH")
    
    if project_id:
        print(f"   [OK] GOOGLE_CLOUD_PROJECT_ID: {project_id}")
    else:
        print("   [ERROR] GOOGLE_CLOUD_PROJECT_ID not found in environment")
    
    if credentials_path:
        print(f"   [OK] GOOGLE_CLOUD_VISION_CREDENTIALS_PATH: {credentials_path}")
        # Check if file exists
        if os.path.exists(credentials_path):
            print(f"   [OK] Credentials file exists: {credentials_path}")
        else:
            # Try relative to backend directory
            abs_path = backend_dir / credentials_path
            if abs_path.exists():
                print(f"   [OK] Credentials file exists (relative path): {abs_path}")
            else:
                print(f"   [ERROR] Credentials file NOT found at: {credentials_path}")
                print(f"   [ERROR] Also checked: {abs_path}")
                return False
    else:
        print("   [WARN] GOOGLE_CLOUD_VISION_CREDENTIALS_PATH not set (will use ADC)")
    
    print()
    
    # Try to import and initialize the service
    print("2. Testing Google Vision Service initialization...")
    try:
        # Import here to catch import errors
        from app.services.google_vision_service import GoogleVisionService
        from app.config import settings
        
        print(f"   Project ID from settings: {settings.GOOGLE_CLOUD_PROJECT_ID}")
        print(f"   Credentials path from settings: {settings.GOOGLE_CLOUD_VISION_CREDENTIALS_PATH}")
        
        # Initialize the service
        print("   Initializing GoogleVisionService...")
        service = GoogleVisionService()
        
        print("   [OK] Google Vision Service initialized successfully!")
        print(f"   [OK] Project ID: {service.project_id}")
        print(f"   [OK] Timeout: {service.timeout} seconds")
        print(f"   [OK] Max pages per request: {service.max_pages_per_request}")
        print(f"   [OK] Async enabled: {service.enable_async}")
        
        print()
        print("=" * 60)
        print("[SUCCESS] All checks passed! Google Vision API is ready to use.")
        print("=" * 60)
        return True
        
    except ImportError as e:
        print(f"   [ERROR] Import error: {e}")
        print("   Make sure you're running from the backend directory")
        return False
    except Exception as e:
        print(f"   [ERROR] Error initializing service: {e}")
        print()
        print("   Common issues:")
        print("   - Credentials file path is incorrect")
        print("   - Vision API not enabled in GCP project")
        print("   - Service account doesn't have permissions")
        print("   - Invalid JSON credentials file")
        print()
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_vision_setup()
    sys.exit(0 if success else 1)

