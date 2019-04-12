#!/usr/bin/env bash
docker run -p $1:8080/tcp -p $1:8080/udp -v /opt/elocity:/opt/elocity ew-link-elocity
