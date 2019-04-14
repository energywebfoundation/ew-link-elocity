# Energyweb Hardware Link for Elocity / London Hydro

Link apps are hardware software designed to run in forever on single board computers like an electronic appliance.

## Run stable version from docker hub

### Configuration api
Run the command bellow and send POST request to `/config` with configuration json to write it to `/etc/ew-link.config`. Elocity App will look for the configuration file before it starts. Default port is `9069`

`docker run -p 80:9069 -v /etc:/etc slockit\ew-link-config-api:v1-x64`

### Elocity App
Service ports are specified on `ew-link.config`, be sure to specify ports with `-p` docker parameter before running. 

`docker run -v /etc:/etc slockit\ew-link-elocity:v1-x64`

### Raspberry Pi 2, 3+

`docker run -p 80:9069 -v /etc:/etc slockit\ew-link-config-api:v1-ARM32v7`

`docker run -v /etc:/etc slockit\ew-link-elocity:v1-ARM32v7`

## Build and run local Docker containers
This method is architecture agnostic as long as Alpine and Python images are available to target.
```bash
./docker_build.sh
./docker_run.sh ew-link-elocity-alpine 80 8080
```