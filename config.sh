#!/bin/bash
echo -e "\e[1;31mAlgorand Royalty Fees Tutorial\e[0m"

set -e
export SHELLOPTS


PYTHON=python3
gcmd="goal -d $NETWORK_FOLDER/Node1"

# Royalty fee 3.5%
ROYALTY_FEE=35

#############################
# Create ASSET
#############################
echo -e "\e[1;32mCreator:\e[0m $WALLET1_ADDR"
echo -e "\e[1;32mCreating asset Special NFT \e[0m"
${gcmd} asset create --creator $WALLET1_ADDR --name "SpecialNFT" --unitname "SNFT" --total 1 --decimals 0 --defaultfrozen
echo -e "\e[1;32mAccount info \e[0m"
${gcmd} account info   -a $WALLET1_ADDR
export ASSET_ID="$(${gcmd} asset info --creator $WALLET1_ADDR --unitname "SNFT"  | awk '{print $3}' | head -1)"
echo -e "\e[1;32mAsset id:\e[0m $ASSET_ID"
#############################


# #############################
# # Deploy Stateful Contract
# #############################
PYTEAL_CONTRACT="src/smart_contract.py"
TEAL_APPROVAL="src/approval.teal"
TEAL_CLEAR="src/clear.teal"

# compile PyTeal into TEAL
echo -e "\e[1;32mCompiling Stateful contract to TEAL\e[0m"
"$PYTHON" "$PYTEAL_CONTRACT" "$TEAL_APPROVAL" "$TEAL_CLEAR"

# create app
echo -e "\e[1;32mDeploying stateful contract\e[0m"
GLOBAL_BYTES_SLICES=1
GLOBAL_INTS=3
LOCAL_BYTES_SLICES=1
LOCAL_INTS=5

export APP_ID=$(
  ${gcmd} app create --creator "$WALLET1_ADDR" \
    --approval-prog "$TEAL_APPROVAL" \
    --clear-prog "$TEAL_CLEAR" \
    --global-byteslices "$GLOBAL_BYTES_SLICES" \
    --global-ints "$GLOBAL_INTS" \
    --local-byteslices "$LOCAL_BYTES_SLICES" \
    --local-ints "$LOCAL_INTS" \
    --app-arg addr:$WALLET1_ADDR \
    --app-arg int:$ASSET_ID \
    --app-arg int:$ROYALTY_FEE |
    grep Created |
    awk '{ print $6 }'
)
echo -e "\e[1;32mApp ID:\e[0m $APP_ID"

export APP_ADDRESS=$(${gcmd} app info  --app-id "$APP_ID" | awk '{print $3}' | head -2 | tail -1)
echo -e "\e[1;32mApp ID:\e[0m $APP_ADDRESS"

echo -e "\e[1;32mFunding Stateful app\e[0m"
${gcmd} clerk send -a 2000000 -f $WALLET1_ADDR -t $APP_ADDRESS -N


echo -e "\e[1;32mSetting clawback to asset\e[0m"
${gcmd} asset config --assetid $ASSET_ID --manager $WALLET1_ADDR --new-clawback $APP_ADDRESS --new-freezer $APP_ADDRESS --new-manager "" 

set +e


