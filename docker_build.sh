#!/usr/bin/env bash
docker build -t ew-link-elocity .
docker build -t ew-link-elocity-alpine -f Dockerfile.alpine .
