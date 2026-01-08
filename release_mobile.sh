#!/bin/bash
set -e

# Usage: ./release_mobile.sh [patch|minor|major]
TYPE=${1:-patch}

echo "🚀 Starting Mobile Release Process ($TYPE)..."

# Ensure we are on main
BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" != "main" ]; then
  echo "❌ Error: You must be on 'main' branch to release."
  exit 1
fi

# Fetch tags
git fetch --tags

# Get latest tag
LATEST=$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")
echo "🏷️  Latest tag: $LATEST"

# Parse version
VERSION=${LATEST#v}
IFS='.' read -r MAJOR MINOR PATCH <<< "$VERSION"

# Bump version
if [ "$TYPE" == "major" ]; then
  MAJOR=$((MAJOR + 1))
  MINOR=0
  PATCH=0
elif [ "$TYPE" == "minor" ]; then
  MINOR=$((MINOR + 1))
  PATCH=0
else
  PATCH=$((PATCH + 1))
fi

NEW_TAG="v$MAJOR.$MINOR.$PATCH"
echo "✨ New tag: $NEW_TAG"

# Confirm
read -p "Create and push tag $NEW_TAG? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Release cancelled."
    exit 1
fi

# Tag and Push
git tag -a "$NEW_TAG" -m "Mobile Release $NEW_TAG"
git push origin "$NEW_TAG"

echo "✅ Tag pushed! GitHub Actions workflow should start shortly."
echo "🔗 Check status: https://github.com/marcellopato/DoisP-s/actions"
