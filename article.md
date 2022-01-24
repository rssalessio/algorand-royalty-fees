# Royalty Fees on Algorand
This is a short tutorial that explains how to implement Royalty Fees for Algorand [NFTs](https://www.algorand.com/resources/blog/the-enduring-value-of-nfts-on-algorand) using [Teal v5](https://developer.algorand.org/docs/get-details/dapps/avm/teal/) and new features like [Inner Transactions](https://developer.algorand.org/docs/get-details/dapps/avm/teal/specification/#inner-transactions).

It's assumed that readers have sufficient programming knowledge, general familiarity with blockchain technology and Algorand terminology. Smart contracts are written in [PyTeal](https://pyteal.readthedocs.io/), and examples in Typescript.


To get all the code used in this tutorial, please refer to the following [GitHub repository](https://github.com/rssalessio/algorand-royalty-fees)!

# Requirements

1. Have a running [Algorand node](https://developer.algorand.org/docs/run-a-node/setup/install), or [use the sandbox](https://github.com/algorand/sandbox)
    * You can use the script ``scripts/start_network.sh`` to start a private network with all the wallets/variables already initialized.
    * To use the script type ``source scripts/start_network.sh`` from the root folder.
2. Having [PyTeal installed](https://pyteal.readthedocs.io/en/stable/installation.html) (requires python 3)
3. [_Optional_] If you want to run the example script in ``src/examples.ts`` you need to install [Node-js](https://nodejs.org/)
    * After installing Node you need to install the following libraries:  ``algosdk``, ``typescript``, and ``ts-node`` (simply type ``npm install`` in the src folder)

# Background

**Note**: We define an NFT to be an [ASA](https://developer.algorand.org/docs/get-details/asa/) with the _Total_ parameter set to 1, and the _Decimals_ parameter set to 0 (see also the following [ARC](https://github.com/algorandfoundation/ARCs/blob/main/ARCs/arc-0003.md)). In this tutorial we  use the word NFT and Asset interchangeably.

## 1. Introduction
**Royalty Fees play a huge role in the future of NFT sales on Blockchains, since they enable the possibility of guaranteeing fees on second sales of an NFT for original authors.**

Unfortunately, Royalty Fees are either not yet fully supported or completely unavailable on many blockchains. For example, [in Ethereum it is not possible to enforce Royalty fees on second sales](https://eips.ethereum.org/EIPS/eip-2981). As a consequence, marketplaces in Ethereum have to implement an internal (off-chain and therefore mostly centralized) solution to provide Royalty Fees, which can be easily cheated if the users avoid selling on that specific marketplace.

**Algorand on the other hand has provided many features that make it a very good candidate blockchain to implement Royalty Fees**. These features are:
1. Possibility to freeze an nft, and block the transfer of an nft
2. Possibility to send transactions and move nfts using smart contracts (Teal 5)
3. Even for migrated or bridged NFTs, the logic to control sales and after-sales steps and behavior can still be governed by smart contracts on Algorand.

**An earlier project on Algorand, [Algorealm](https://github.com/cusma/algorealm), shows an innovative first implementation of Royalty Fees on Algorand by using a [**clawback** address](https://developer.algorand.org/docs/get-details/transactions/transactions#clawbackaddr) and Teal v2**. However, the smart contract implemented in Algorealm  (which is the union of a [Stateful App](https://developer.algorand.org/docs/get-details/dapps/smart-contracts/apps/) and a [Smart signature](https://developer.algorand.org/docs/get-details/dapps/smart-contracts/smartsigs/)) can only approve or reject the transfer of an nft, without automatic calculation of royalty fee, or automatic transfer of an nft within the contract (because of limitations of TEAL V2). In their proposal, they make use of a smart contract that allows the transfer of an nft only upon payment of a pre-specified royalty fee. Because of these limitations, their implementation was more of static nature, application-specific, and therefore hard to scale.

**Now, by exploiting the capabilities of Teal v5**, It is possible to do much more and implement through a single [stateful smart contract Application](https://developer.algorand.org/docs/get-details/dapps/smart-contracts/apps/) that automatically handles the payment of royalty fees, and the transfer of nfts using [Inner Transactcions](https://developer.algorand.org/docs/get-details/dapps/smart-contracts/apps/?from_query=inner%20transactions#inner-transactions).

## 2. Method to collect royalty fees

1. The seller sets an nft up for sale on the App (the stateful smart contract).
2. The buyer pays the amount specified by the seller to the App.
3. The App receives the payment.
4. The nft is transferred from the seller to the buyer.
5. The App pays the seller the total amount minus the royalty fees (If applicable by being second sales). The full total amount would be paid to the seller if that's the first sale.
6. Royalty fees are collected in the App. The owner of the royalty fees (the Creator of the nft) can redeem the royalty fees whenever desired.

The method is also described in the following UML diagram

![EditorImages/2021/12/04 14:05/algorand_royalty_fees_scheme.drawio.jpg](https://algorand-devloper-portal-app.s3.amazonaws.com/static/EditorImages/2021/12/04%2014%3A05/algorand_royalty_fees_scheme.drawio.jpg)

# Steps

## 3. Creating the contract (approval program)
The smart contract consists of an approval program and a clearance program. The latter simply approves all requests, therefore let's just focus on the former.
For simplicity, it's assumed that the contract is deployed directly by the creator of the asset, the one that will collect all royalty fees.

Let's start by defining a list of constants that will be used in smart contract app development.

```python
from pyteal import *
import sys

class Constants:
    """
        Constant strings used in the smart contracts
    """
    Creator           = Bytes("Creator")               # Identified the account of the Asset creator, stored globally
    AssetId           = Bytes("AssetId")               # ID of the asset, stored globally
    amountPayment     = Bytes("amountPayment")         # Amount to be paid for the asset, stored locally on the seller's account
    approveTransfer   = Bytes("approveTransfer")       # Approval variable, stored on the seller's and the buyer's accounts
    setupSale         = Bytes("setupSale")             # Method call
    buy               = Bytes("buy")                   # Method call
    executeTransfer   = Bytes("executeTransfer")       # Method call
    royaltyFee        = Bytes("royaltyFee")            # Royalty fee in thousands
    waitingTime       = Bytes("waitingTime")           # Number of rounds to wait before the seller can force the transaction
    claimFees         = Bytes("claimFees")             # Method call
    collectedFees     = Bytes("collectedFees")         # Amount of collected fees, stored globally
    refund            = Bytes("refund")                # Method call
    roundSaleBegan    = Bytes("roundSaleBegan")        # Round in which the sale began

```

After having defined the list of constants, let's write the stateful smart contract with pyteal using ```python approval_program()``` function.

```python
# Check the transaction type and execute the corresponding code
#   1. If application_id() is 0 then the program has just been created, so we initialize it
#   2. If on_completion() is 0 we execute the onCall code
return If(Txn.application_id() == Int(0)).Then(initialize)                  \
        .ElseIf(Txn.on_completion() == OnComplete.CloseOut).Then(Approve()) \
        .ElseIf(Txn.on_completion() == OnComplete.OptIn).Then(Approve())    \
        .ElseIf(Txn.on_completion() == Int(0)).Then(onCall)                 \
        .Else(Reject())
```
First, the code needs to check if the App has just been initialized. In that case, the App should execute the sequence contained in the variable ``initialize``. Alternatively,  on ``CloseOut`` or ``OptIn`` the code simply approves the transaction. Otherwise, if it is a [``NoOp`` transaction](https://developer.algorand.org/docs/get-details/transactions/#application-noop-transaction), then the code executes the block in ``onCall``.

The ``initialize`` sequence is defined as follows

```python
# [Step 1] Sequence used to initialize the smart contract. Should be called only at creation
royaltyFeeArg = Btoi(Txn.application_args[2])
assetDecimals = AssetParam.decimals(Btoi(Txn.application_args[1]))
assetFrozen = AssetParam.defaultFrozen(Btoi(Txn.application_args[1]))
initialize = Seq([
    Assert(Txn.type_enum() == TxnType.ApplicationCall),                  # Check if it's an application call
    Assert(Txn.application_args.length() == Int(4)),                     # Check that there are 4 arguments, Creator, AssetId and Royalty Fee and Round Wait
    Assert(royaltyFeeArg > Int(0) and royaltyFeeArg <= Int(1000)),       # verify that the Royalty fee is between 0 and 1000
    defaultTransactionChecks(Int(0)),                                    # Perform default transaction checks
    assetDecimals,                                                       # Load the asset decimals
    Assert(assetDecimals.hasValue()),
    Assert(assetDecimals.value() == Int(0)),                             # Verify that there are no decimals
    assetFrozen,                                                         # Load the frozen parameter of the asset
    Assert(assetFrozen.hasValue()),
    Assert(assetFrozen.value() == Int(1)),                               # Verify that the asset is frozen
    App.globalPut(Constants.Creator, Txn.application_args[0]),           # Save the initial creator
    App.globalPut(Constants.AssetId, Btoi(Txn.application_args[1])),     # Save the asset ID
    App.globalPut(Constants.royaltyFee, royaltyFeeArg),                  # Save the royalty fee
    App.globalPut(Constants.waitingTime, Btoi(Txn.application_args[3])), # Save the waiting time in number of rounds
    Approve()
```
In the ``initialize`` sequence 4 arguments are expected: (1) the wallet's address of the creator, (2) the asset ID,  the (3) royalty fee in thousands, (4) the waiting time. All these variables are stored in the global state of the contract (3 integers and 1 Byte slice). The waiting time is a variable used by the App later in step 3. It allows the seller to force the NFT transfer if enough time has passed.


On the other hand, going back to the previous piece of code, the ``onCall`` method is an ``If`` statement that checks which action the user wants to perform:

```python
# onCall Sequence
# Checks that the first transaction is an Application call, and that there is at least 1 argument.
# Then it checks the first argument of the call. The first argument must be a valid value between
# "setupSale", "buy", "executeTransfer", "refund" and "claimFees"
onCall = If(Or(Txn.type_enum() != TxnType.ApplicationCall,
                Txn.application_args.length() == Int(0))
            ).Then(Reject())                                                                  \
            .ElseIf(Txn.application_args[0] == Constants.setupSale).Then(setupSale)              \
            .ElseIf(Txn.application_args[0] == Constants.buy).Then(buy)                          \
            .ElseIf(Txn.application_args[0] == Constants.executeTransfer).Then(executeTransfer)  \
            .ElseIf(Txn.application_args[0] == Constants.refund).Then(refund)                    \
            .ElseIf(Txn.application_args[0] == Constants.claimFees).Then(claimFees)              \
            .Else(Reject())
```

First, it checks that the user called the smart contract correctly. Then, the code checks the first argument of ``application_args`` (we use the first argument to discriminate between the various operations). As seen in the code there is a list of ``ElseIf`` statements that are used to distinguish between the various values. The accepted values are ``setupSale, buy, executeTransfer, refund, claimFees``.

1. ``setupSale`` Can be called by any user, and it is used to set up a new sale.
2. ``buy`` Any user that wants to buy the NFT needs to call this method first.
3. ``executeTransfer`` After paying, the buyer can finalize by transfering the NFT to his/her wallet. Alternatively, the user can get the money back by calling the ``refund method``. If the buyer does not do anything, the seller can also call this function to transfer the NFT if enough time has passed since the ``buy`` call.
4. ``refund`` This method can be used by the buyer to get the money back
5. ``claimFees`` This method can only be called by the creator of the NFT to collect royalty fees

Note that all other undefined requests are rejected.

Before going through these 5 methods, first, let's define some useful subroutines that will be used later on.

### 3.1 Subroutines
In this section are explained the 6 subroutines that appear in the code:
1. ``defaultTransactionChecks(txnId: Int) -> TealType.none`` this subroutine performs standard checks on the transaction.
2. ``sendPayment(receiver: Addr, amount: Int) -> TealType.none``: this subroutine sends a payment to a specific wallet.
3. ``transferAsset(sender: Addr, receiver: Addr, assetId: Int) -> TealType.none``: this subroutine transfers an asset from a wallet to another (the app must be set as clawback address for the asset).
4. ``checkNFTBalance(account: Addr, assetId: Int) -> TealType.none``: this subroutine checks that the account owns the NFT specified by ``assetId``.
5. ``computeRoyaltyFee(amount: Int, royaltyFee: Int) -> TealType.uint64``: this subroutine computes the royalty fees given a certain price.
6. `` checkRoyaltyFeeComputation(amount: Int, royaltyFee: Int) -> TealType.none``: This subroutine checks that there are no problems computing the royalty fee  given  the values of  ``amount`` and ``royaltyFee``.

#### 3.1.1 DefaultTransactionChecks
This subroutine is used to perform some default checks on the
incoming transactions.  For a given transaction, it verifies that  the ``rekeyTo``, ``closeRemainderTo``, and the ``assetCloseTo`` attributes are set equal to the zero address.

```python
@Subroutine(TealType.none)
def defaultTransactionChecks(txnId: Int) -> TealType.none:
    """
    This subroutine is used to perform some default checks on the
    incoming transactions.

    For a given index of the transaction to check, it verifies that
    the rekeyTo, closeRemainderTo, and the assetCloseTo attributes
    are set equal to the zero address

    :param Int txnId : Index of the transaction
    """
    return Seq([
        Assert(txnId < Global.group_size()),
        Assert(Gtxn[txnId].rekey_to() == Global.zero_address()),
        Assert(Gtxn[txnId].close_remainder_to() == Global.zero_address()),
        Assert(Gtxn[txnId].asset_close_to() == Global.zero_address())
    ])
```

#### 3.1.2 SendPayment
The ``SendPayment`` subroutine can be used to pay a wallet by submitting an inner transaction. Check also the description of the subroutine in the code.
```python
@Subroutine(TealType.none)
def sendPayment(receiver: Addr, amount: Int) -> TealType.none:
    """
    This subroutine can be used to send payments from the smart
    contract to other accounts using inner transactions

    :param Addr receiver : The receiver of the payment
    :param Int amount    : Amount to send in microalgos
    """
    return Seq([
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.Payment,
            TxnField.amount: amount,
            TxnField.receiver: receiver,
            TxnField.fee: Int(1000)
        }),
        InnerTxnBuilder.Submit(),
    ])
```

#### 3.1.3 TransferAsset
The ``TransferAsset`` subroutine can be used to transfer the NFT being sold from one account to another using an inner transaction (note that the contract must be the clawback address for that NFT).
```python
@Subroutine(TealType.none)
def transferAsset(sender: Addr, receiver: Addr, assetId: Int) -> TealType.none:
    """
    This subroutine can be used to transfer an asset
    from an account to another. 
    
    This subroutine can also be used to opt in an asset if ``amount``
    is 0 and ``sender`` is equal to ``receiver``.

    :param Addr sender   : Asset sender
    :param Addr receiver : Asset receiver
    :param Int assetId   : ID of the asset. Note that the id must also be passed in the ``foreignAssets``
                           field in the outer transaction (otherwise you will get a reference error)
    """
    return Seq([
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.asset_amount: Int(1),
            TxnField.asset_receiver: receiver,
            TxnField.asset_sender: sender,
            TxnField.xfer_asset: assetId,
            TxnField.fee: Global.min_txn_fee()
        }),
        InnerTxnBuilder.Submit(),
    ])
```

#### 3.1.4 CheckNFTBalance
The ``checkNFTBalance`` can be used to check if an account owns a specific NFT. It uses the ``AssetHolding.balance`` method to retrieve the balance.

```python
@Subroutine(TealType.none)
def checkNFTBalance(account: Addr, assetId: Int) -> TealType.none:
    """
    This subroutine checks that an account owns an NFT.
    Note that the asset id must also be passed in the ``foreignAssets``
    field in the outer transaction (otherwise you will get a reference error)

    :param Addr account  : The account to verify
    :param Int assetId   : ASA Id        
    """
    AssetAccountBalance = AssetHolding.balance(account, assetId)
    return Seq([
        AssetAccountBalance,
        Assert(AssetAccountBalance.hasValue() == Int(1)),
        Assert(AssetAccountBalance.value() == Int(1))
    ])
```
#### 3.1.5 ComputeRoyaltyFee
Next, there's the ``computeRoyaltyFee`` subroutine. This subroutine computes the fee for a specific payment amount and a given royalty fee (in thousands). For example, suppose one wants to set a royalty fee of 3.5%. In thousands is 35 (0.035 * 1000).

Given an amount ``x`` its needed to compute ``x * 35 / 1000`` to compute the royalty fee. Since there may be a remaining amount, it's also necessary to consider ``(x * 35) % 1000``. The remainder will be used to round up the fee (if it is greater than 500 then its rounded up, otherwise rounded down).

Note that we use the ``checkRoyaltyFeeComputation`` subroutine to check that the computation will not overflow.

Read also the description of the subrotuine for more information.
```python
@Subroutine(TealType.uint64)
def computeRoyaltyFee(amount: Int, royaltyFee: Int) -> TealType.uint64:
    """
    This subroutine computes the fee given a specific ``amount`` and the
    predefined ``royaltyFee``.
    The ``royaltyFee`` variable must be expressed in thousands.

    Note: make sure to call first checkRoyaltyFeeComputation() before calling
    this function

    :param Int amount       : The amount paid
    :param Int royaltyFee   : The royalty fee (in thousands)
    :return                 : Fee to be paid in microAlgos
    :rtype                  : Int            
    """
    # The safety of computing `remainder` and `division` is given by
    # calling the checkRoyaltyFeeComputation() function.
    remainder = ScratchVar(TealType.uint64)
    division = ScratchVar(TealType.uint64)

    # Computes the royalty fee. If the fee is equal to 0, or the amount is very small
    # the fee will be 0.
    # If the royalty fee is larger or equal to 1000 then we return the original amount.
    # If the remainder of royaltyFee * amount / 1000 is larger than 500 we round up the
    # result and return  1 + royaltyFee * amount / 1000. Otherwise we just return
    # royaltyFee * amount / 1000.

    return Seq([
        checkRoyaltyFeeComputation(amount, royaltyFee),
        remainder.store(Mod(Mul(amount, royaltyFee), Int(1000))),
        division.store(Div(Mul(amount, royaltyFee), Int(1000))),
        Return(If(Or(royaltyFee == Int(0), division.load() == Int(0))).Then(Int(0))   \
        .ElseIf(royaltyFee >= Int(1000)).Then(amount)                   \
        .ElseIf(remainder.load() > Int(500)).Then(division.load() + Int(1))           \
        .Else(division.load()))
    ])
```

#### 3.1.6 CheckRoyaltyFeeComputation
Last, but not least, there's the ``checkRoyaltyFeeComputation`` suborutine. This subroutine checks that there are no problems computing the royalty fee  given a specific ``amount`` and the predefined ``royaltyFee``. To do so, we first check that ``amount`` is greater than 0, and then verify that it can safely perform the division (see also the [this link](https://wiki.sei.cmu.edu/confluence/pages/viewpage.action?pageId=87152052) for more information about checking overflows/iunderflows).

```python
@Subroutine(TealType.none)
def checkRoyaltyFeeComputation(amount: Int, royaltyFee: Int) -> TealType.none:
    """
    This subroutine checks that there are no problems computing the
    royalty fee  given a specific ``amount`` and the predefined ``royaltyFee``.
    The ``royaltyFee`` variable must be expressed in thousands.

    :param Int amount       : The amount paid
    :param Int royaltyFee   : The royalty fee (in thousands)
    :return                 : Fee to be paid in microAlgos
    :rtype                  : Int
    """

    return Seq([
        Assert(amount > Int(0)),
        Assert(royaltyFee <= Div(Int(2 ** 64 - 1), amount)),
    ])
```

### 3.2 Setup sale method
Going back to the main part of smart contract,  let's look at the ``setupSale`` method. In this case, the user (the seller) has to provide the sale price for the NFT.

```python
# [Step 2] Sequence that sets up the sale of an NFT
# There should be 2 arguments: 
#   1. The first argument is the command to execute, in this case "setupSale"
#   2. The second one is the payment amount
# We first verify the the seller owns the NFT, and then we locally save the arguments
priceArg = Btoi(Txn.application_args[1])
assetClawback = AssetParam.clawback(App.globalGet(Constants.AssetId))
assetFreeze = AssetParam.freeze(App.globalGet(Constants.AssetId))
setupSale = Seq([
    Assert(Txn.application_args.length() == Int(2)),                                      # Check that there are 2 arguments
    Assert(Global.group_size() == Int(1)),                                                # Verify that it is only 1 transaction
    defaultTransactionChecks(Int(0)),                                                     # Perform default transaction checks
    Assert(priceArg > Int(0)),                                                            # Check that the price is greater than 0              
    assetClawback,                                                                        # Verify that the clawback address is the contract
    Assert(assetClawback.hasValue()),
    Assert(assetClawback.value() == Global.current_application_address()),
    assetFreeze,                                                                          # Verify that the freeze address is the contract
    Assert(assetFreeze.hasValue()),
    Assert(assetFreeze.value() == Global.current_application_address()),    
    checkNFTBalance(Txn.sender(), App.globalGet(Constants.AssetId)),                      # Verify that the seller owns the NFT
    Assert(priceArg > serviceCost),                                                       # Check that the price is greater than the service cost
    App.localPut(Txn.sender(), Constants.amountPayment, priceArg),                        # Save the price
    App.localPut(Txn.sender(), Constants.approveTransfer, Int(0)),                        # Reject transfer until payment is done
    Approve()
])
```

The code above starts by doing some standard checks. Note how the ``checkNFTBalance`` subroutine is called to verify that the seller owns the NFT.

The code ends by checking that the sale price is greater than the service cost, defined as ``serviceCost = Int(2) * Global.min_txn_fee() `` (which is 2000 micro algos, in standard condition), and stores it in the local account of the seller. The ``approveTransfer`` variable's value is also stored in local state , and set it to 0. This variable is used to indicate whether the seller has given his/her approval to transfer the NFT to a buyer.

### 3.3 Buy method

The next subroutine is the ``buy`` method. Calling this method requires 2 transactions:

1. The first one is a NoOp application call with 3 arguments: the "buyASA" argument, the asset id, and the amount of ASA to buy
2. The second transaction is a payment (that pays the full price). The receiver is the contract itself.

The code starts by loading some useful variables (the seller address, the amount to be paid, etc...) and does some standard checks. Code makes sure that the seller has not approved another buyer, and that the seller holds enough ASA. 

If all conditions are satisfied,  then code approves the transfer from both the seller's and buyer's perspectives. At this point, the buyer only needs to finalize the transaction to transfer the asset.

Note that we save in the seller's account a local variable, ``Constants.roundSaleBegan``,  which stores the round number in which the buyer has paid the required amount.

```python
# [Step 3] Sequence that approves the payment
# This step requires 2 transaction.
# The first transaction is a NoOp App call transaction. There should be 2 arguments: 
#   1. The first argument is the command to execute, in this case "buy"
#   2. The second argument is the asset id
# Moreover, in the first transaction we also pass the seller's address
# The second transaction is a payment (the receiver is the app).

# Save some useful variables
seller = Gtxn[0].accounts[1]                                                              # Save seller's address
amountToBePaid = App.localGet(seller, Constants.amountPayment)                            # Amount to be paid
approval = App.localGet(seller, Constants.approveTransfer)                                # Variable that checks if the transfer has alraedy been approved
buyer = Gtxn[0].sender()
# Logic
buy = Seq([
    Assert(Gtxn[0].application_args.length() == Int(2)),                                  # Check that there are 2 arguments
    Assert(Global.group_size() == Int(2)),                                                # Check that there are 2 transactions
    Assert(Gtxn[1].type_enum() == TxnType.Payment),                                       # Check that the second transaction is a payment
    Assert(App.globalGet(Constants.AssetId) == Btoi(Gtxn[0].application_args[1])),        # Check that the assetId is correct
    Assert(approval == Int(0)),                                                           # Check that the transfer has not been issued yet
    Assert(amountToBePaid == Gtxn[1].amount()),                                           # Check that the amount to be paid is correct
    Assert(Global.current_application_address() == Gtxn[1].receiver()),                   # Check that the receiver of the payment is the App
    defaultTransactionChecks(Int(0)),                                                     # Perform default transaction checks
    defaultTransactionChecks(Int(1)),                                                     # Perform default transaction checks
    checkNFTBalance(seller, App.globalGet(Constants.AssetId)),                            # Check that the seller owns the NFT
    Assert(buyer != seller),                                                              # Make sure the seller is not the buyer!
    App.localPut(seller, Constants.approveTransfer, Int(1)),                              # Approve the transfer from seller' side
    App.localPut(buyer, Constants.approveTransfer, Int(1)),                               # Approve the transfer from buyer' side
    App.localPut(seller, Constants.roundSaleBegan, Global.round()),                       # Save the round number
    Approve()
])
```
### 3.4 ExecuteTransfer method
Finally, we have the sequence that finalizes the transfer. At this step, the buyer is still able to get the funds back and cancel the transfer. If the buyer calls ``executeTransfer``, then the transfer is finalized. The asset is moved from the seller to the buyer, and the seller receives the payment minus the royalty fees.

If the buyer is not calling this method, then the seller can call it as long as the number of rounds is greater than the value in ``Constants.roundSaleBegan``  + the current round number. In this way the seller can force the transfer in case the buyer hasn't done it yet.

We use the subroutine ``computeRoyaltyFee`` to compute the royalty fee given the total paid amount minus the service cost.

Apart from the usual checks, we also make sure that both the seller and the buyer already approved the transaction. We then transfer the asset, and send the payment to the seller using the subroutines ``transferAsset`` and ``sendPayment``. Finally, we conclude by collecting the royalty fees for the creator and by deleting all the local variables.
```python
# [Step 4] Sequence that transfers the NFT, pays the seller and sends royalty fees to the creator
# This step requires 1 transaction.
# The  transaction is a NoOp App call transaction. There should be 1 arguments
#   1. The first argument is the command to execute, in this case "executeTransfer"
# We also account for the serviceCost to pay the inner transaction
royaltyFee = App.globalGet(Constants.royaltyFee)
collectedFees = App.globalGet(Constants.collectedFees)
feesToBePaid = ScratchVar(TealType.uint64)
executeTransfer = Seq([
    Assert(Gtxn[0].application_args.length() == Int(1)),                            # Check that there is only 1 argument
    Assert(Global.group_size() == Int(1)),                                          # Check that is only 1 transaction
    defaultTransactionChecks(Int(0)),                                               # Perform default transaction checks
    Assert(App.localGet(seller, Constants.approveTransfer) == Int(1)),              # Check that approval is set to 1 from seller' side
    Assert(Or(
        And(seller != buyer,
            App.localGet(buyer, Constants.approveTransfer) == Int(1)),              # Check approval from buyer' side
        Global.round() > App.globalGet(Constants.waitingTime)                       # Alternatively, the seller can force the transaction if enough
            + App.localGet(seller, Constants.roundSaleBegan))),                     # time has passed
    Assert(serviceCost < amountToBePaid),                                           # Check underflow
    checkNFTBalance(seller, App.globalGet(Constants.AssetId)),                      # Check that the seller owns the NFT
    feesToBePaid.store(                                                             # Reduce number of subroutine calls by saving the variable inside a scratchvar variable
        If(seller == App.globalGet(Constants.Creator)).Then(Int(0))                 # Compute royalty fees: if the seller is the creator, the fees are 0
        .Else(computeRoyaltyFee(amountToBePaid - serviceCost, royaltyFee))),        
    Assert(Int(2 ** 64 - 1) - feesToBePaid.load() >= amountToBePaid - serviceCost), # Check overflow on payment
    Assert(Int(2 ** 64 - 1) - collectedFees >= feesToBePaid.load()),                # Check overflow on collected fees
    Assert(amountToBePaid - serviceCost > feesToBePaid.load()),
    transferAsset(seller,                                                           # Transfer asset
                    Gtxn[0].sender(),
                    App.globalGet(Constants.AssetId)),
    sendPayment(seller, amountToBePaid - serviceCost - feesToBePaid.load()),        # Pay seller
    App.globalPut(Constants.collectedFees, collectedFees + feesToBePaid.load()),    # Collect fees
    App.localDel(seller, Constants.amountPayment),                                  # Delete local variables
    App.localDel(seller, Constants.approveTransfer),
    App.localDel(buyer, Constants.approveTransfer),
    Approve()
])
```
### 3.5 Refund Method
In case the buyer has already paid, but has not finalized the transaction using the ``executeTransfer`` sequence, it is still possible to claim back the funds by calling ``refund``. This sequence of code checks that the payment was done, and sends back to the buyer the total payment amount minus the transaction fee.

We end by cleaning the local variables.

```python
# Refund sequence
# The buyer can get a refund if the payment has already been done but the NFT has not been transferred yet
refund = Seq([
    Assert(Global.group_size() == Int(1)),                                           # Verify that it is only 1 transaction
    Assert(Txn.application_args.length() == Int(1)),                                 # Check that there is only 1 argument  
    defaultTransactionChecks(Int(0)),                                                # Perform default transaction checks
    Assert(buyer != seller),                                                         # Assert that the buyer is not the seller
    Assert(App.localGet(seller, Constants.approveTransfer) == Int(1)),               # Assert that the payment has already been done
    Assert(App.localGet(buyer, Constants.approveTransfer) == Int(1)),
    Assert(amountToBePaid > Global.min_txn_fee()),                                   # Underflow check: verify that the amount is greater than the transaction fee
    sendPayment(buyer, amountToBePaid - Global.min_txn_fee()),                       # Refund buyer
    App.localPut(seller, Constants.approveTransfer, Int(0)),                         # Reset local variables
    App.localDel(buyer, Constants.approveTransfer),
    Approve()
])
```
### 3.6 claimFees Method
Finally, we also create the ``claimFees`` method that can be called by the creator of the asset. This simply sends a payment to the creator with the collected amount of fees.

```python
# Claim Fees sequence
# This sequence can be called only by the creator.  It is used to claim all the royalty fees
# It may fail if the contract has not enough algo to pay the inner transaction (the creator should take
# care of funding the contract in this case)
claimFees = Seq([
    Assert(Global.group_size() == Int(1)),                                                 # Verify that it is only 1 transaction
    Assert(Txn.application_args.length() == Int(1)),                                       # Check that there is only 1 argument
    defaultTransactionChecks(Int(0)),                                                      # Perform default transaction checks
    Assert(Txn.sender() == App.globalGet(Constants.Creator)),                              # Verify that the sender is the creator
    Assert(App.globalGet(Constants.collectedFees) > Int(0)),                               # Check that there are enough fees to collect
    sendPayment(App.globalGet(Constants.Creator), App.globalGet(Constants.collectedFees)), # Pay creator
    App.globalPut(Constants.collectedFees, Int(0)),                                        # Reset collected fees
    Approve()
])
```


### 3.7 Possible changes and missing checks
Several possible changes can be made, depending on the needs.

1. First, note that the code is not intended to be production-ready.

2. Secondly, the asset can be transfered immediately (after the payment) to the buyer, without the need of confirming the transfer.

3. The royalty fees can also be sent immediately to the creator when the asset is transferred (by using another innerTransaction). However, to reduce the number of transactions it is advisable to use the ``claimFees`` sequence.

## 4. Setting up an Example scenario
An example scenario can be simulated where owner sells the asset two times.
Here 3 wallets are needed: 
1. ``wallet1`` creator of the asset, and deployer of the smart contract (this is not strictly required!)
2. ``wallet2`` First buyer
3. ``wallet3`` Second buyer

It proceeds as:
1. Start by creating the Asset using ``wallet1``
2. Deploy the smart contract using ``wallet1``
3. ``wallet1`` puts the NFT up for sale and ``wallet2`` buys it
4. ``wallet2`` puts the NFT up for sale and ``wallet3`` buys it
5. Finally, the fees are redeemed using ``wallet1``

Its assumed that there exist the variables ``$WALLET1_ADDR``, ``$WALLET2_ADDR`` and ``$WALLET3_ADDR``. Each one of these variables contains the corresponding wallet's address (note that if you source the script file in ``scripts/start_network.sh`` it will automatically set up all the variables for you).

### 4.1 Creating the asset
lets start by creating the asset (note that the asset is initially frozen).

The asset id is also stored in ``$ASSET_ID`` and make ``wallet2`` and ``wallet3`` opt-in the asset.

```python
# Create the asset
goal asset create --creator $WALLET1_ADDR --name "SpecialNFT" --unitname "SNFT" --total 1 --decimals 0 --defaultfrozen

# Save the Asset ID
export ASSET_ID="$(goal asset info --creator $WALLET1_ADDR --unitname "SNFT"  | awk '{print $3}' | head -1)"

# Asset Opt in
goal asset send --amount 0 --to $WALLET2_ADDR --from $WALLET2_ADDR --assetid $ASSET_ID
goal asset send --amount 0 --to $WALLET3_ADDR --from $WALLET3_ADDR --assetid $ASSET_ID
```
### 4.2 Creating the App and setting the clawback address
Now lets deploy the smart contract using ``wallet1``, and make all the wallets opt-in the app.

```python
# Royalty fee 3.5%, in thousands
ROYALTY_FEE=35

# compile PyTeal into TEAL
python3 src/smart_contract.py src/approval.teal src/clear.teal

# create app
GLOBAL_BYTES_SLICES=1
GLOBAL_INTS=3
LOCAL_BYTES_SLICES=0
LOCAL_INTS=3

export APP_ID=$(
  goal app create --creator "$WALLET1_ADDR" \
    --approval-prog src/approval.teal \
    --clear-prog src/clear.teal \
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


# Export App Address
export APP_ADDRESS=$(goal app info  --app-id "$APP_ID" | awk '{print $3}' | head -2 | tail -1)

# Fund App
goal clerk send -a 200000 -f $WALLET1_ADDR -t $APP_ADDRESS -N

# Setting clawback
goal asset config --assetid $ASSET_ID --manager $WALLET1_ADDR --new-clawback $APP_ADDRESS --new-freezer $APP_ADDRESS --new-manager ""

# App opt in
goal app optin --app-id $APP_ID --from $WALLET1_ADDR
goal app optin --app-id $APP_ID --from $WALLET2_ADDR
goal app optin --app-id $APP_ID --from $WALLET3_ADDR
```


### 4.3 Simulate sale from ``wallet1`` to ``wallet2``
Here the sale from ``wallet1`` to ``wallet2`` is simulated. 

Lets first fix a price and amount, and call the ``setupSale`` method using ``wallet1``. 3 arguments are passed: (1) ``setupSale``, (2) the price, (3) the amount. Moreover, the asset id must be specified using the ``--foreign-asset`` command.


```python
NFT_AMOUNT=1
NFT_PRICE=1000000
goal app call --app-id $APP_ID --from $WALLET1_ADDR --app-arg str:setupSale --app-arg int:$NFT_PRICE --app-arg int:$NFT_AMOUNT --foreign-asset $ASSET_ID
```

Now lets pay the contract using ``wallet2`` by make a group transaction:
1. The first transaction calls the ``buyASA`` method in the contract. There are 3 arguments: (1) ``setupSale``, (2) the asset idi, (3) the amount. Moreover, the asset id need to be specified using the ``--foreign-asset`` flag and the seller's account using the ``--app-account`` flag.
2. The second transaction is a payment. The total amount is paid directly the contract.


```python
# App call transaction
goal app call --app-id $APP_ID --from $WALLET2_ADDR --app-arg str:buyASA --app-arg int:$ASSET_ID --app-arg int:$NFT_AMOUNT --foreign-asset $ASSET_ID --app-account $WALLET1_ADDR --out txnAppCall.tx

# Payment transaction
goal clerk send --amount $NFT_PRICE --to $APP_ADDRESS --from $WALLET2_ADDR --out txnPayment.tx

# Make a group transaction
cat txnAppCall.tx txnPayment.tx > buyCombinedTxns.tx
goal clerk group -i buyCombinedTxns.tx -o buyGroupedTxns.tx
goal clerk sign -i buyGroupedTxns.tx -o signoutbuy.tx
goal clerk rawsend -f signoutbuy.tx
```
Now ``wallet2`` has paid the smart contract. It can still  get a refund by calling the ``refund`` method, or finalize the transaction by calling the ``executeTransfer`` method.

``wallet2`` can finalize the transaction by executing the following command
```python
goal app call --app-id $APP_ID --from $WALLET2_ADDR --app-arg str:executeTransfer --app-account $WALLET1_ADDR --foreign-asset $ASSET_ID
```

Now it can be verified that ``wallet2`` owns the asset
```python
goal account info -a $WALLET2_ADDR
```

Whereas the global state of the app can be verified to check the collected fees
```python
goal app read --global --app-id $APP_ID
```

And collected fees would be as
```python
 "collectedFees": {
    "tt": 2,
    "ui": 34930
  },
```

which is the correct amount, since the price is ``1000000``, the service cost is ``2000`` and the royalty fee is 3.5%, therefore ``(1000000-2000) * 0.035=34930``.
(Note that the service cost is 2000 because the smart contract has to do 2 transactions).


Alternatively, ``wallet2`` can get a refund by executing the following command (the seller's address needs to be specified using the ``-app-account`` flag).

```python
goal app call --app-id $APP_ID --from $WALLET2_ADDR --app-arg str:refund --app-account $WALLET1_ADDR
```

### 4.4 Simulate sale from ``wallet2`` to ``wallet3``
Now lets simulate the sale from ``wallet2`` to ``wallet3``. 

Again, the ``setupSale`` method is called using ``wallet2``. 3 arguments must be passed: (1) ``setupSale``, (2) the price, (3) the amount. Moreover, its also requierd to specify the asset id using the ``--foreign-asset`` command.

Same parameters are used as before for simplicity.
```python
goal app call --app-id $APP_ID --from $WALLET2_ADDR --app-arg str:setupSale --app-arg int:$NFT_PRICE --app-arg int:$NFT_AMOUNT --foreign-asset $ASSET_ID
```

Now lets pay the contract using ``wallet3`` by means of a group transaction:
1. The first transaction calls the ``buyASA`` method in the contract. There are 3 arguments: (1) ``setupSale``, (2) the asset idi, (3) the amount. Moreover, its also required to specify the asset id using the ``--foreign-asset`` flag and the seller's account using the ``--app-account`` flag.
2. The second transaction is payment of total amount, directly to the contract.


```python
# App call transaction
goal app call --app-id $APP_ID --from $WALLET3_ADDR --app-arg str:buyASA --app-arg int:$ASSET_ID --app-arg int:$NFT_AMOUNT --foreign-asset $ASSET_ID --app-account $WALLET2_ADDR --out txnAppCall.tx

# Payment transaction
goal clerk send --amount $NFT_PRICE --to $APP_ADDRESS --from $WALLET3_ADDR --out txnPayment.tx

# Make a group transaction
cat txnAppCall.tx txnPayment.tx > buyCombinedTxns.tx
goal clerk group -i buyCombinedTxns.tx -o buyGroupedTxns.tx
goal clerk sign -i buyGroupedTxns.tx -o signoutbuy.tx
goal clerk rawsend -f signoutbuy.tx
```
Now ``wallet3`` has paid the smart contract. It can still get a refund by calling the ``refund`` method, or finalize the transaction by calling the ``executeTransfer`` method.

``wallet3`` can finalize the transaction by executing the following command

```python
goal app call --app-id $APP_ID --from $WALLET3_ADDR --app-arg str:executeTransfer --app-account $WALLET2_ADDR --foreign-asset $ASSET_ID
```

Now code verifies that ``wallet3`` owns the asset using the command ``goal account info -a $WALLET3_ADDR``

It's also verified that the global state of the app to check the amount of collected fees using the command``goal app read --global --app-id $APP_ID``

And collected fees would be as
```python
 "collectedFees": {
    "tt": 2,
    "ui": 69860
  },
```

which is the correct amount. The creator (``wallet1``) can reclaim the fees using

```python
goal app call --app-id $APP_ID --from $WALLET1_ADDR --app-arg str:claimFees
```

## 5. Running the example script
You can also run the example scenario by executing the script in ``src/example.ts``. To run the script:

1. Create the network: ``source scripts/start_network.sh``
2. Create the asset and deploy the app ``source scripts/config.sh``
3. Run the example script ``ts-node src/example.ts``


## 6. Conclusions
In this guide, it is shown how to guarantee royalty fees using PyTeal (for Teal v5). Thanks to [Inner Transactions](https://developer.algorand.org/docs/get-details/dapps/avm/teal/specification/#inner-transactions) functionality, it's now possible to streamline transactions more efficiently using smart contracts on Algorand. In the future, it is expected for royalty fees to be standardized, and perhaps have a corresponding [ARC](https://github.com/algorandfoundation/ARCs/).

Thanks for reading!