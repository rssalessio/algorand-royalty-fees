#!/bin/bash
set -e

SCRIPTS_PATH="$(dirname "$0")"
NETWORK_FOLDER="$SCRIPTS_PATH/network_data"
echo -e "\e[1;31mStarting network \e[0m"

if [ -d "$NETWORK_FOLDER" ]; then
  # Take action if $DIR exists. #
  $SCRIPTS_PATH/stop_network.sh
fi


goal network create -n testNetwork -t $SCRIPTS_PATH/config.json -r $NETWORK_FOLDER
echo '{
	"Version": 16,
	"GossipFanout": 0,
	"NetAddress": "127.0.0.1:0",
	"DNSBootstrapID": "",
	"EnableProfiler": true,
    "EnableDeveloperAPI": true
}' > $NETWORK_FOLDER/Node1/config.json


goal network start -r $NETWORK_FOLDER
goal network status -r $NETWORK_FOLDER
NODE1_ADDRESS=$(goal account list -d $NETWORK_FOLDER/Node1 | awk '{print $2}')


export WALLET1_KEY="glass junk struggle potato core lazy armor buyer video law reject illegal aim pipe flip mimic firm pizza marriage shy wagon auto motor about soap"
export WALLET1_ADDR="$(goal account import -m "$WALLET1_KEY" -d $NETWORK_FOLDER/Node1 | awk '{print $2}')"

export WALLET2_KEY="convince coyote apple hood harsh good scrap journey citizen giraffe exercise device hen essay oyster move oyster cube impose olympic strategy phone flavor about allow"
export WALLET2_ADDR="$(goal account import -m "$WALLET2_KEY" -d $NETWORK_FOLDER/Node1 | awk '{print $2}')"

export WALLET3_KEY="execute rare matter winner peanut obtain mansion place symbol mirror income frown such once narrow will crane decorate olive gentle bless vendor critic absent year"
export WALLET3_ADDR="$(goal account import -m "$WALLET3_KEY" -d $NETWORK_FOLDER/Node1 | awk '{print $2}')"

echo -e "\e[1;36mWallet1 address:\e[0m $WALLET1_ADDR"
echo -e "\e[1;36mWallet2 address:\e[0m $WALLET2_ADDR"
echo -e "\e[1;36mWallet3 address:\e[0m $WALLET3_ADDR"


echo -e "\e[1;36mFunding wallets\e[0m"
goal clerk send -a 200000000 -f $NODE1_ADDRESS -t $WALLET1_ADDR -d $NETWORK_FOLDER/Node1 -N
goal clerk send -a 200000000 -f $NODE1_ADDRESS -t $WALLET2_ADDR -d $NETWORK_FOLDER/Node1 -N
goal clerk send -a 200000000 -f $NODE1_ADDRESS -t $WALLET3_ADDR -d $NETWORK_FOLDER/Node1 -N

echo -e "\e[1;31mNetwork created\e[0m"
set +e