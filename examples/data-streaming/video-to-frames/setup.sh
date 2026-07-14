#!/bin/sh
# System-level setup for the derived container image. Runs during
# `model-compose up` on the first launch, before pip install. Idempotent.
set -e

apt-get update
apt-get install -y --no-install-recommends ffmpeg
rm -rf /var/lib/apt/lists/*
