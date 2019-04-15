# Energyweb Hardware Link for Elocity / London Hydro

EWF Link App to integrate EV-Charging stations with OCPP-J v1.6 protocol with the Certificates of Origin DApp. Allowing owners to trade green energy tokens on the blockchain.

## Run test from docker compose
1. Spin the containers:
`docker-compose up`

2. Configure the EV-charging station to connect to your machine IP and port. On the **EBee's Bender Controller** the USB host always assign the connected to IP `192.168.123.220`. 
`ws://192.168.123.220:8000/your_charging_station_id`

3. Configure elocity app with test configuration:
```bash
curl --request POST \
  --url http://localhost:8060/config \
  --header 'content-type: application/json' \
  --data '{
 "consumers": [
 ],
 "producers": [
  {
   "name": "ChargingPoint0901454d4800007340d2",
   "energy-meter": {
    "module": "tasks.chargepoint",
    "class_name": "EVchargerEnergyMeter",
    "class_parameters": {
     "service_urls": ["http://localhost:80"],
      "manufacturer":"Ebee",
      "model":"EV-Charge Point Energy Meter",
      "serial_number":"0901454d4800007340d2",
      "energy_unit":"WATT_HOUR",
      "is_accumulated": false,
      "connector_id": 1
    }
   },
   "carbon-emission": {
    "module": "energyweb.carbonemission",
    "class_name": "WattimeV1",
    "class_parameters": {
     "usr": "energyweb",
     "pwd": "en3rgy!web",
     "ba": "FR",
     "hours_from_now": 24
    }
   },
   "smart-contract": {
    "module": "energyweb.smart_contract.origin_v1",
    "class_name": "OriginProducer",
    "class_parameters": {
     "asset_id": 2,
     "wallet_add": "0x4A616994A229565f7f7E96161eFd78b780bf24e2",
     "wallet_pwd": "1b17e7cb5879a18fb6c9e7aee03a66841f2aa10102bd537752ecbdb5b6252d2f",
     "client_url": "https://rpc.slock.it/tobalaba"
    }
   }
  }
 ],
 "ocpp16-server": {
  "host": "192.168.123.220",
  "port": 8000
 },
 "elastic-sync": {
  "service_urls": ["http://localhost:80"]
 }
}'
```

## Run stable version from docker hub

### Configuration api
Run the command bellow and send POST request to `/config` with configuration json to write it to `/etc/ew-link.config`. Elocity App will look for the configuration file before it starts. Default port is `9069`

`docker run -p 8060:9069 -v /etc:/etc slockit\ew-link-config-api:v1-x64`

### Elocity App
Service ports are specified on `ew-link.config`, be sure to specify ports with `-p` docker parameter before running. 

`docker run -v /etc:/etc slockit\ew-link-elocity:v1-x64`

### Raspberry Pi 2, 3+

`docker run -p 8060:9069 -v /etc:/etc slockit\ew-link-config-api:v1-ARM32v7`

`docker run -p 8000:8080/tcp -p 8000:8080/udp -v /etc:/etc slockit\ew-link-elocity:v1-ARM32v7`

## Build and run local Docker containers
This method is architecture agnostic as long as Alpine and Python images are available to target.
```bash
./docker_build.sh
./docker_run.sh 80 8080
git fetch
git checkout config-api
./docker_build.sh
./docker_run.sh 81
```