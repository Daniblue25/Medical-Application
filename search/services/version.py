"""Version of the application and of its extraction rules (shown in the interface)."""

import os

EXTRACTION_VERSION = "3.2.0"

# Set at build/deploy time (e.g. docker build --build-arg GIT_COMMIT=$(git rev-parse --short HEAD))
GIT_COMMIT = os.getenv("GIT_COMMIT", "unknown")
