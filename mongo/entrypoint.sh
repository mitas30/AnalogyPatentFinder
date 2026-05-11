#!/bin/sh
set -e

DB_NAME="${MONGO_INITDB_DATABASE:-analogie_finder}"
FLAG_FILE="/data/db/initialized.flag"
SEED_DIR="/local-seed"
LOG_FILE="/var/log/mongodb.log"

import_seed_file() {
  file_name="$1"
  collection="$2"
  seed_file="$SEED_DIR/$file_name"

  if [ -f "$seed_file" ]; then
    echo "Importing $seed_file into $DB_NAME.$collection..."
    mongoimport --host localhost --db "$DB_NAME" --collection "$collection" --type json --file "$seed_file" --jsonArray
  else
    echo "Skipping $file_name: not found."
  fi
}

wait_for_mongo() {
  attempts=0

  until mongosh --quiet --host localhost --eval "db.adminCommand('ping').ok" >/dev/null 2>&1; do
    attempts=$((attempts + 1))

    if [ "$attempts" -ge 30 ]; then
      echo "MongoDB did not become ready in time." >&2
      exit 1
    fi

    sleep 1
  done
}

if [ -f "$FLAG_FILE" ]; then
  echo "MongoDB already initialized. Skipping local seed import."
  exec mongod --bind_ip_all --logpath "$LOG_FILE"
fi

if [ ! -f "$SEED_DIR/initial-data.json" ]; then
  echo "No local seed data found at $SEED_DIR/initial-data.json. MongoDB will start empty."
  exec mongod --bind_ip_all --logpath "$LOG_FILE"
fi

echo "Local seed data found. Importing initial data..."
mongod --bind_ip_all --logpath "$LOG_FILE" --fork
wait_for_mongo

import_seed_file "initial-data.json" "patents"
import_seed_file "initial-data2.json" "abstracts"
import_seed_file "initial-data3.json" "parameters"

touch "$FLAG_FILE"
echo "MongoDB local seed import completed."

mongod --shutdown
exec mongod --bind_ip_all --logpath "$LOG_FILE"
