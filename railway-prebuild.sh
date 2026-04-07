#!/bin/bash
# Pre-build script: copies dashboard files into ai-router for Railway deployment
# Run this before committing if you've updated dashboard files

echo "Syncing dashboard files to ai-router/dashboard..."
rsync -av --delete \
    --exclude='.DS_Store' \
    dashboard/ ai-router/dashboard/

echo "Dashboard files synced successfully."
echo "Files in ai-router/dashboard:"
ls -la ai-router/dashboard/
