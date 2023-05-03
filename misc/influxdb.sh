#!/bin/bash
sudo docker run --rm -d -p 8086:8086 \
      -v /var/lib/influxdb2:/var/lib/influxdb2 \
      influxdb:2.0
sudo docker ps
