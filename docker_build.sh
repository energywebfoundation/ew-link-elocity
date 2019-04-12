#!/usr/bin/env bash
#docker build -t ew-link-config-api .
pipenv lock -r > requirements.txt
docker build -t ew-link-config-api -f Dockerfile.alpine .
