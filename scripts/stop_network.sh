#!/bin/bash
set -e
echo -e "\e[1;31mStopping network...\e[0m"

SCRIPTS_PATH="$(dirname "$0")"
NETWORK_FOLDER="$SCRIPTS_PATH/network_data"
if [ -d "$NETWORK_FOLDER" ]; then
  # Take action if $DIR exists. #
  goal network stop -r $NETWORK_FOLDER
  goal network delete -r $NETWORK_FOLDER
fi

set +e