# Google Cloud Vision API Setup Guide

This guide explains how to set up Google Cloud Vision API for OCR processing in the application.

## Overview

The application uses Google Cloud Vision API for high-quality OCR (Optical Character Recognition) processing. This replaces the previous Tesseract OCR implementation and provides better accuracy and performance.

## Prerequisites

1. A Google Cloud Platform (GCP) account
2. A GCP project with billing enabled
3. Google Cloud Vision API enabled

## Step 1: Create a GCP Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Note your Project ID (you'll need this for configuration)

## Step 2: Enable Vision API

1. Navigate to **APIs & Services** > **Library**
2. Search for "Cloud Vision API"
3. Click **Enable**

Alternatively, use the gcloud CLI:

```bash
gcloud services enable vision.googleapis.com --project=YOUR_PROJECT_ID
```

## Step 3: Create Service Account

1. Go to **IAM & Admin** > **Service Accounts**
2. Click **Create Service Account**
3. Enter a name (e.g., `docfoundry-vision`)
4. Click **Create and Continue**
5. Grant the role: **Cloud Vision API User** (or `roles/cloudvision.user`)
6. Click **Continue** and **Done**

## Step 4: Create Service Account Key

1. Click on the service account you just created
2. Go to the **Keys** tab
3. Click **Add Key** > **Create new key**
4. Choose **JSON** format
5. Download the JSON file
6. **Important**: Store this file securely and never commit it to version control

## Step 5: Configure Application

### Option A: Application Default Credentials (ADC) - Recommended for Production

For production deployments (e.g., Google Cloud Run, GCE, GKE):

1. The service account JSON should be mounted as a volume or provided via environment variable
2. Set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to the path of the JSON file:

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

Or in Docker:

```yaml
# docker-compose.yml
services:
  backend:
    environment:
      - GOOGLE_APPLICATION_CREDENTIALS=/app/gcp-credentials.json
    volumes:
      - ./service-account-key.json:/app/gcp-credentials.json:ro
```

### Option B: Service Account File Path - For Local Development

For local development, you can specify the path directly:

1. Set environment variables in `.env`:

```bash
GOOGLE_CLOUD_PROJECT_ID=your-project-id
GOOGLE_CLOUD_VISION_CREDENTIALS_PATH=/path/to/service-account-key.json
```

2. Or use Application Default Credentials by running:

```bash
gcloud auth application-default login
```

## Step 6: Environment Variables

Required environment variables:

- `GOOGLE_CLOUD_PROJECT_ID` (required): Your GCP project ID
- `GOOGLE_CLOUD_VISION_CREDENTIALS_PATH` (optional): Path to service account JSON file
  - If not set, uses Application Default Credentials (ADC)
- `GOOGLE_APPLICATION_CREDENTIALS` (optional): Alternative way to specify credentials path
  - Used by Google Cloud libraries for ADC

Optional configuration:

- `GOOGLE_CLOUD_VISION_TIMEOUT_SECONDS` (default: 60): API timeout in seconds
- `GOOGLE_CLOUD_VISION_MAX_PAGES_PER_REQUEST` (default: 5): Max pages per batch for PDFs
- `GOOGLE_CLOUD_VISION_ENABLE_ASYNC` (default: true): Use async batch API for PDFs

## Step 7: Verify Setup

Test the configuration:

```python
from app.services.google_vision_service import GoogleVisionService

service = GoogleVisionService()
# If no error is raised, configuration is correct
```

## Language Support

The application supports multiple languages. Language codes are automatically mapped from various formats to Google Vision's ISO 639-1 format:

- Tesseract codes (e.g., `eng`, `ell`, `fra`) → ISO 639-1 (`en`, `el`, `fr`)
- ISO 639-1 codes (e.g., `en`, `el`, `fr`) → Used directly
- Multi-language codes (e.g., `eng+fra`) → Multiple hints (`['en', 'fr']`)

Supported languages include: English, Greek, French, Spanish, German, Italian, Portuguese, Russian, Japanese, Korean, Chinese (Simplified/Traditional), Arabic, Hindi, and many more.

See `app/services/ocr_language_mapper.py` for the complete list.

## Cost Considerations

### Pricing

- **First 1,000 pages/month**: Free
- **Additional pages**: $1.50 per 1,000 pages

### Cost Optimization Tips

1. **Monitor Usage**: Set up billing alerts in Google Cloud Console
2. **Quota Limits**: Set daily/monthly quotas to prevent unexpected costs
3. **Caching**: Consider caching OCR results for repeated documents
4. **Image Quality**: Don't over-process images (Vision API handles various qualities well)

### Setting Up Billing Alerts

1. Go to **Billing** > **Budgets & alerts**
2. Create a budget
3. Set alert thresholds (e.g., 50%, 90%, 100% of budget)
4. Configure notification channels

## Troubleshooting

### Error: "Permission Denied"

**Cause**: Service account doesn't have the required permissions.

**Solution**:

1. Verify the service account has the `Cloud Vision API User` role
2. Check that Vision API is enabled for your project

### Error: "Project ID not found"

**Cause**: `GOOGLE_CLOUD_PROJECT_ID` is not set or incorrect.

**Solution**:

1. Verify the environment variable is set correctly
2. Check that the project ID matches your GCP project

### Error: "Credentials not found"

**Cause**: Service account credentials are not accessible.

**Solution**:

1. Verify `GOOGLE_APPLICATION_CREDENTIALS` points to a valid JSON file
2. Check file permissions (should be readable)
3. For production, ensure the service account JSON is mounted/available

### Error: "Quota Exceeded"

**Cause**: API quota limit reached.

**Solution**:

1. Check your quota usage in Google Cloud Console
2. Request a quota increase if needed
3. Implement rate limiting in your application

### Error: "Timeout"

**Cause**: Request took too long to complete.

**Solution**:

1. Increase `GOOGLE_CLOUD_VISION_TIMEOUT_SECONDS`
2. For large PDFs, ensure `GOOGLE_CLOUD_VISION_ENABLE_ASYNC` is `true`
3. Check network connectivity

## Security Best Practices

1. **Never commit credentials**: Add `*.json` service account files to `.gitignore`
2. **Use least privilege**: Grant only the `Cloud Vision API User` role
3. **Rotate keys**: Regularly rotate service account keys
4. **Monitor access**: Review service account usage logs
5. **Use ADC in production**: Prefer Application Default Credentials over file paths

## Migration from Tesseract

If migrating from Tesseract:

1. All Tesseract language codes are automatically mapped to Google Vision format
2. Existing `ocr_language` values in the database will continue to work
3. No database migration is required
4. The `engine` field in metadata will change from `"tesseract"` to `"google_vision"`

## Additional Resources

- [Google Cloud Vision API Documentation](https://cloud.google.com/vision/docs)
- [Vision API Pricing](https://cloud.google.com/vision/pricing)
- [Service Accounts Guide](https://cloud.google.com/iam/docs/service-accounts)
- [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials)

## Support

For issues specific to this application, check the application logs and error messages. For Google Cloud Vision API issues, refer to the [Google Cloud Support](https://cloud.google.com/support) documentation.
