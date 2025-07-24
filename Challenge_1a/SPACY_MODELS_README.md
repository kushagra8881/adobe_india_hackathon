# SpaCy Models for Docker Deployment

## Current Setup

This project now includes the SpaCy model `.whl` files directly in the repository for more efficient Docker builds.

### Models Included

- `xx_ent_wiki_sm-3.7.0-py3-none-any.whl` - Multilingual model (primary)
- `en_core_web_sm-3.7.1-py3-none-any.whl` - English model (optional/fallback)

## Benefits of This Approach

✅ **Faster Docker builds** - No network downloads during build
✅ **Offline deployment** - Works in air-gapped environments  
✅ **Reliable CI/CD** - No download timeouts or network failures
✅ **Version consistency** - Exact model versions across deployments
✅ **Reproducible builds** - Same results every time

## Dockerfile Changes

The Dockerfile has been updated to install models from local `.whl` files instead of downloading them:

```dockerfile
# OLD (network download)
RUN python -m spacy download en_core_web_sm
RUN python -m spacy download xx_ent_wiki_sm

# NEW (local installation)
COPY models/*.whl /app/models/
RUN pip install --no-cache-dir /app/models/xx_ent_wiki_sm*.whl
RUN pip install --no-cache-dir /app/models/en_core_web_sm*.whl
```

## Repository Size Impact

- `xx_ent_wiki_sm`: ~15MB
- `en_core_web_sm`: ~12MB
- **Total**: ~27MB additional repository size

This is acceptable for most projects given the benefits.

## Updating Models

To update models in the future:

1. Run `python download_models.py` to get new versions
2. Update the URLs in `download_models.py` if needed
3. Commit the new `.whl` files to the repository

## Alternative: Separate Models Repository

For very large teams or if repository size is a concern, consider:

1. Create a separate repository for models
2. Use Git LFS (Large File Storage)
3. Download models in a separate CI/CD step

## Verification

Build and test the Docker image:

```bash
docker build -t your-app .
docker run your-app python -c "import spacy; print('Models:', spacy.util.find_installed_models())"
```

This should show both `xx_ent_wiki_sm` and `en_core_web_sm` as installed.
