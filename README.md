# Royalty Fees on Algorand
This is a short tutorial that explains how to implement Royalty Fees using [Inner Transactions](https://developer.algorand.org/docs/get-details/dapps/avm/teal/specification/#inner-transactions) and [Teal v5](https://developer.algorand.org/docs/get-details/dapps/avm/teal/) capabilities in Algorand.
The smart contract has been written in [PyTeal](https://pyteal.readthedocs.io/), and all the examples are written using Typescript.

We assume that the reader has programming knowledge, and that she/he is already familiarity with Blockchains technology.

For a complete description of the tutorial, please refer to the [main article]((https://github.com/rssalessio/algorand-royalty-fees/blob/main/article.md)).
Otherwise, just check the **Install** section and the **How to run** section.

AUTHOR: Alessio Russo (alessior@kth.se)

LICENSE: [MIT](https://github.com/rssalessio/algorand-royalty-fees/blob/master/LICENSE)

Donations address (Algorand wallet): ``DG44ST47RRVBKPFIQ633XK47TWSVDELX42L33ZNJE22KZW3GQLDVDSZDAY`` 

## Introduction
**Royalty Fees play a huge role in the future of Blockchains, since they enable the possibility of guaranteeing fees  on second sales of an asset.** Unfortunately, Royalty Fees are yet not fully implemented on Blokchains. 

For example, [in Ethereum it is not possible to enforce Royalty fees on second sales](https://eips.ethereum.org/EIPS/eip-2981). As a consequence, marketplaces in Ethereum have to implement an internal solution to provide Royalty Fees, which can be easily avoided if the users avoid selling on that specific marketplace.

**Algorand on the other hand has some features that make it a candidate blockchain where to implement Royalty Fees**. These features are:
1. Possibility to freeze an asset, and block the transfer of an asset
2. Possibility to send transactions and move assets using smart contracts (Teal 5)

**An earlier project on Algorand, [Algorealm](https://github.com/cusma/algorealm), shows a first implementation of Royalty Fees on Algorand by using a [**clawback** address](https://developer.algorand.org/docs/get-details/transactions/transactions#clawbackaddr) and Teal v2**. However, the smart contract implemented in Algorealm  (which is the union of a [Stateful App](https://developer.algorand.org/docs/get-details/dapps/smart-contracts/apps/) and 1 [Smart signature](https://developer.algorand.org/docs/get-details/dapps/smart-contracts/smartsigs/)) only accepts or rejects the transfer of an asset, and it is not able to  compute automatically a royalty fee, or to automatically move an asset. In their proposal they make use of a smart contract that allows the transfer of an asset only upon payment of a specific royalty fee. Because of these limitations, their implementation is application-specific, and hard to scale.

**Now it is possible to do much better by exploiting the capabilities of Teal v5**. It is possible to implement only 1 [stateful App](https://developer.algorand.org/docs/get-details/dapps/smart-contracts/apps/) that handles automatically the payment of royalty fees, and the transfer of assets using [Inner Transactcions](https://developer.algorand.org/docs/get-details/dapps/smart-contracts/apps/?from_query=inner%20transactions#inner-transactions).

**Roughly speaking, the scheme works as follows:**
1. The seller sets up an asset for sale on the App (the smart contract)
2. The buyer pays the amount specified by the seller to the App
3. If the buyer is fully convinced he/she can continue with the payment
   * The asset is transfered from the seller to the buyer
   * The app pays the seller the total amount minus the royalty fees
   * Royalty fees are collected in the App. The owner of the royalty fees (the Creator of the asset) can redeem the royalty fees whenever he/she wants.

Using this method it is possible to build a general Royalty Fee smart contract that can handle royalty fees on the Algorand blockchain. To keep reading, please refer to the main article. 

Check the **Install** section to install all the needed software.
Check the **How to run** section to see how to run an example.

## Install
Please follow the following steps. Note that step 5 is optional depending on wether you have an Algorand node or you are using the sandbox.

1. Have a running Algorand node
    * You can [install an Algorand node](https://developer.algorand.org/docs/run-a-node/setup/install)
    * Alternatively you can [use the sandbox](https://github.com/algorand/sandbox)
2. Install PyTeal (requires python 3) ```pip3 install pyteal```
3. Install [Node-js](https://nodejs.org/)
4. We also need to install some libraries to use Node. In this case we use the ``algosdk`` library, ``typescript`` and ``ts-node``.
    * From the root folder write ``npm install ./src/`` to install the requires dependencies. 
    * Alternatively, if you want to install them globally you can instead run in the shell the following commands
        ```
        npm install -g typescript
        npm install -g ts-node
        npm install -g algosdk
        ```
5. [_Optional_] This step is needed only if you installed an Algorand node:
    * To set up a private network just run the command ``source scripts/start_network.sh``
    * To stop the network run the command ``source scripts/stop_network.sh``

## How to run
To run the example

1. Create the network: ``source scripts/start_network.sh``
2. Create the asset and deploy the app ``source scripts/config.sh``
3. Run the example script ``ts-node src/example.ts``

Alternatively you can check the guide [here](https://github.com/rssalessio/algorand-royalty-fees/blob/main/article.md)

## General Teal guidelines
- [PyTeal documentation](https://pyteal.readthedocs.io/)
- [Teal guidelines](https://developer.algorand.org/docs/get-details/dapps/avm/teal/guidelines/)