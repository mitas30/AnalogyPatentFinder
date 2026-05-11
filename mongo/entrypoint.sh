#!/bin/sh
set -e

exec mongod --bind_ip_all --logpath /var/log/mongodb.log
