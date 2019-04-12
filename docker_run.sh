#!/usr/bin/env bash
docker run -p $1:8000/tcp -p $1:8000/udp -v /opt/elocity:/opt/elocity ew-link-config-api
