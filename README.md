# algorand-royalty-fees

AUTHOR: Alessio Russo [alessior@kth.se](alessior@kth.se)
LICENSE: [MIT](https://github.com/rssalessio/algorand-royalty-fees/blob/master/LICENSE)
Donations address: ``DG44ST47RRVBKPFIQ633XK47TWSVDELX42L33ZNJE22KZW3GQLDVDSZDAY`` 

## Introduction

## Install
Please follow the following steps. Note that step 5 is optional depending on wether you have an Algorand node or you are using the sandbox.

1. Have a running Algorand node
    * You can [install an Algorand node](https://developer.algorand.org/docs/run-a-node/setup/install)
    * Alternatively you can [use the sandbox](https://github.com/algorand/sandbox)
2. Install PyTeal (requires python 3) ```pip3 install pyteal```
3. Install [Node-js](https://nodejs.org/)
4. We also need to install some libraries to use Node. In this case we use the ``algosdk`` library, ``typescript`` and ``ts-node``.
    * Go inside the ``src`` folder and write ``npm install .`` to install the requires dependencies. 
    * Alternatively, if you want to install them globally you can instead run in the shell the following commands
        ```npm install -g typescript
        npm install -g ts-node
        npm install -g algosdk```
5. [Optional] This step is required only if you installed an Algorand node:
    * To set up a private network just run the command ``source start_network.sh``
    * To stop the network run the command ``source stop_network.sh``

## How to run


## General Teal guidelines
- [PyTeal documentation](https://pyteal.readthedocs.io/)
- [Teal guidelines](https://developer.algorand.org/docs/get-details/dapps/avm/teal/guidelines/)