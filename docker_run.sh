#!/usr/bin/env bash
docker run -p $1:$2/tcp -p $1:$2/udp -v /opt/elocity:/opt/elocity ew-link-elocity
