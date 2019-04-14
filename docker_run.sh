#!/usr/bin/env bash
docker run -p $1:9069/tcp -p $1:9069/udp -v /opt/slockit/configs:/etc/elocity ew-link-config-api
