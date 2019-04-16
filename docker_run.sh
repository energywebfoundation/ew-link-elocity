#!/usr/bin/env bash
docker run -p $1:8000/tcp -p $1:8000/udp -v /opt/slockit/configs:/etc/elocity slockit/ew-link-elocity:v1-x64
