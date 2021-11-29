# Royalty Fees on Algorand
This is a short tutorial that explains how to implement Royalty Fees using Inner Transactions and Teal v5 capabilities in Algorand.
The smart contract has been written in PyTeal, and all the examples are written using Typescript.

We assume that the reader has programming knowledge, and that she/he is already familiarity with Blockchains technology.


## 1. Introduction
**Royalty Fees play a huge role in the future of Blockchains, since they enable the possibility of guaranteeing fees  on second sales of an asset.** Unfortunately, Royalty Fees are yet not fully implemented on Blokchains. 

For example, [in Ethereum it is not possible to enforce Royalty fees on second sales](https://eips.ethereum.org/EIPS/eip-2981). As a consequence, marketplaces in Ethereum have to implement an internal solution to provide Royalty Fees, which can be easily avoided if the users avoid selling on that specific marketplace.

**Algorand on the other hand has some features that make it a candidate blockchain where to implement Royalty Fees**. These features are:
1. Possibility to freeze an asset, and block the transfer of an asset
2. Possibility to send transactions and move assets using smart contracts (Teal 5)

**An earlier project on Algorand, [Algorealm](https://github.com/cusma/algorealm), shows a first implementation of Royalty Fees on Algorand by using a [**clawback** address](https://developer.algorand.org/docs/get-details/transactions/transactions#clawbackaddr) and Teal v2**. However, the smart contract implemented in Algorealm  (which is the union of a [Stateful App](https://developer.algorand.org/docs/get-details/dapps/smart-contracts/apps/) and 1 [Smart signature](https://developer.algorand.org/docs/get-details/dapps/smart-contracts/smartsigs/)) only accepts or rejects the transfer of an asset, and it is not able to  compute automatically a royalty fee, or too automatically move an asset. In their proposal they make use of a smart contract that allows the transfer of an asset only upon payment of a specific royalty fee. Because of these limitations, their implementation is application-specific, and hard to scale.

**Now it is possible to do much better by exploiting the capabilities of Teal v5**. It is possible to implement only 1 [stateful App](https://developer.algorand.org/docs/get-details/dapps/smart-contracts/apps/) that handles automatically the payment of royalty fees, and the transfer of assets using [Inner Transactcions](https://developer.algorand.org/docs/get-details/dapps/smart-contracts/apps/?from_query=inner%20transactions#inner-transactions).

## 2. Method to collect royalty fees
**Roughly speaking, the method works as follows:**
1. The seller sets up an asset for sale on the App (the smart contract)
2. The buyer pays the amount specified by the seller to the App
3. If the buyer is fully convinced he/she can continue with the payment
   * The asset is transfered from the seller to the buyer
   * The app pays the seller the total amount minus the royalty fees
   * Royalty fees are collected in the App. The owner of the royalty fees (the Creator of the asset) can redeem the royalty fees whenever he/she wants.

The method is also described the following UML diagram

![Royalty Fees in Algorand - Diagram](imgs/algorand_royalty_fees_scheme.drawio.svg)

One may wonder why it is necessary for the Buyer to first pay and then finalize the transfer. I personally prefer it this way. How many times you bought something and then you regretted doing so?

In case you don't like this solution, it is still possible to combine all the steps together (I will explain this later).

## 3. Creating the contract (approval program)
The smart contract  consists of an approval program and a clearance program. The latter simply returns 1 to all requests, therefore we just focus on the former.

We assume for simplicity that the contract is deployed directly by the creator of the asset, the one that will collect all royalty fees. In this way the smart contract can be directly intialized by the creator.

We start by defining a list of constants that will turn out to be useful while developing the App.
```python
from pyteal import *
import sys

class Constants:
    """
        Constant strings used in the smart contracts
    """
    Creator           = Bytes("Creator")         # Identified the account of the Asset creator, stored globally
    AssetId           = Bytes("AssetId")         # ID of the asset, stored globally
    amountPayment     = Bytes("amountPayment")   # Amount to be paid, stored locally on the seller's account
    amountASA         = Bytes("amountASA")       # Amount of asset sold, stored locally on the seller's account
    approveTransfer   = Bytes("approveTransfer") # Approval variable, stored on the seller's and buyer's accounts
    setupSale         = Bytes("setupSale")       # Method call
    buyASA            = Bytes("buyASA")          # Method call
    executeTransfer   = Bytes("executeTransfer") # Method call
    royaltyFee        = Bytes("royaltyFee")      # Royalty fee in thousands
    claimFees         = Bytes("claimFees")       # Method call
    collectedFees     = Bytes("collectedFees")   # Amount of collected fees, stored globally
    refund            = Bytes("refund")          # Method call
```

After having defined the list of constants, we can write the piece of code that is executed upon calling the contract.
We define the ```python approval_program()``` function, which contains the code executed by the App. This function returns the following piece of code
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
We start by checking if the App has just been initialized. If so we call the sequence contained in the variable ``initialize``. On ``CloseOut`` or ``OptIn`` we simply approve the transaction. Otherwise, if it is a [``NoOp`` transaction](https://developer.algorand.org/docs/get-details/transactions/#application-noop-transaction), we execute the code in ``onCall``.

The ``initialize`` sequence is defined as follows
```python
# [Step 1] Sequence used to initialize the smart contract. Should be called only at creation
royaltyFeeArg = Btoi(Txn.application_args[2])
initialize = Seq([
    Assert(Txn.type_enum() == TxnType.ApplicationCall),             # Check if it's an application call
    Assert(Txn.application_args.length() == Int(3)),                # We need 3 arguments, Creator, AssetId and Royalty Fee
    Assert(royaltyFeeArg >= Int(0) and royaltyFeeArg <= Int(1000)), # verify that the Royalty fee is in [0, 1000]
    App.globalPut(Constants.Creator, Txn.application_args[0]),      # Save the initial creator
    App.globalPut(Constants.AssetId, Btoi(Txn.application_args[1])),# Save the asset ID
    App.globalPut(Constants.royaltyFee, royaltyFeeArg),             # Save the royalty fee
    Approve()
])
```
In the ``initialize`` sequence we expect 3 arguments: (1) the wallet's address of the creator, (2) the asset ID and the (3) royalty fee in thousands. We save all these variables in the global state of the contract (2 integers and 1 Bytes slice).



On the other hand, going back to the previous piece of code, the ``onCall`` method is an ``If`` statement that checks which action the user wants to perform:
```python
# onCall Sequence
# Checks that the first transaction is an Application call, and then checks
# the first argument of the call. The first argument must be a valid value between
# "setupSale", "buyASA", "executeTransfer", "refund" and "claimFees"
onCall = If(Gtxn[0].type_enum() != TxnType.ApplicationCall).Then(Reject())                        \
         .ElseIf(Gtxn[0].application_args[0] == Constants.setupSale).Then(setupSale)              \
         .ElseIf(Gtxn[0].application_args[0] == Constants.buyASA).Then(buyASA)                    \
         .ElseIf(Gtxn[0].application_args[0] == Constants.executeTransfer).Then(executeTransfer)  \
         .ElseIf(Gtxn[0].application_args[0] == Constants.refund).Then(refund)                    \
         .ElseIf(Gtxn[0].application_args[0] == Constants.claimFees).Then(claimFees)              \
         .Else(Reject())
````
First, we check that the user called the smart contract correctly. Then we check the first argument of the ``ApplicationCall``. As you can see in the code there is a list of ``ElseIf`` statementents that are used to distinguish between the various values. The accepted values are ``setupSale, buyASA, executeTransfer, refund, claimFees``.
1. ``setupSale`` Can be called by any user, and it is used to set up a new sale.
2. ``buyASA`` Any user that wants to buy the asset needs to call this method first.
3. ``executeTransfer`` After paying, the buyer can finalize by transfering the asset to his/her wallet. Alternatively, the user can get the money back by calling the ``refund method``
4. ``refund`` This method can be used by the buyter to get the money back
5. ``claimFees`` This method can only be called by the creator of the asset to collect royalty fees

Note that we obviously reject all other undefined requests. 

We will now go thorugh these 5 methods, but, before doing so, we first define some useful subroutines that will come in handy later on.

### 3.1 SetupSale method
```python
# [Step 2] Sequence that sets up the sale of an ASA
    # There should be 3 arguments: 
    #   1. The first argument is the command to execute, in this case "setupSale"
    #   2. The second one is the payment amount
    #   3. The third one is the amount of ASA transfered
    # We first verify the the seller has enough ASA to sell, and then we locally save the arguments
    priceArg = Btoi(Txn.application_args[1])
    amountOfASAArg = Btoi(Txn.application_args[2])
    setupSale = Seq([
        Assert(Txn.application_args.length() == Int(3)),                                      # Check that there are 3 arguments
        Assert(Global.group_size() == Int(1)),                                                # Verify that it is only 1 transaction
        Assert(priceArg != Int(0)),                                                           # Check that the price is different than 0
        Assert(amountOfASAArg != Int(0)),                                                     # Check that the amount of ASA to transfer is different than 0                
        Assert(                                                                               # Verify that the seller has enough ASA to sell
            getAccountASABalance(Txn.sender(), App.globalGet(Constants.AssetId))
                >=  amountOfASAArg),
        Assert(priceArg > serviceCost),                                                       # Check that the price is greater than the service cost
        App.localPut(Txn.sender(), Constants.amountPayment, priceArg),                        # Save the price
        App.localPut(Txn.sender(), Constants.amountASA, amountOfASAArg),                      # Save the amount of ASA to transfer
        App.localPut(Txn.sender(), Constants.approveTransfer, Int(0)),                        # Reject transfer until payment is done
        Approve()
    ])
```
### 3.2 BuyASA method
```python
# [Step 3] Sequence that approves the payment for the ASA
    # This step requires 2 transaction.
    # The first transaction is a NoOp App call transaction. There should be 3 arguments: 
    #   1. The first argument is the command to execute, in this case "buyASA"
    #   2. The second argument is the asset id
    #   3. The third argument is the amount of ASA to buy
    # Moreover, in the first transaction we also pass the seller's address
    # The second transaction is a payment (the receiver is the app).

    # Save some useful variables
    seller = Gtxn[0].accounts[1]                                                              # Save seller's address
    amountToBePaid = App.localGet(seller, Constants.amountPayment)                            # Amount to be paid
    amountAssetToBeTransfered = App.localGet(seller, Constants.amountASA)                     # Amount of ASA
    approval = App.localGet(seller, Constants.approveTransfer)                                # Variable that checks if the transfer has alraedy been approved
    buyer = Gtxn[0].sender()
    buyASA = Seq([
        Assert(Gtxn[0].application_args.length() == Int(3)),                                  # Check that there are 3 arguments
        Assert(Global.group_size() == Int(2)),                                                # Check that there are 2 transactions
        Assert(Gtxn[1].type_enum() == TxnType.Payment),                                       # Check that the second transaction is a payment
        Assert(App.globalGet(Constants.AssetId) == Btoi(Gtxn[0].application_args[1])),        # Check that the assetId is correct
        Assert(approval == Int(0)),                                                           # Check that the transfer has not been issued yet
        Assert(amountToBePaid == Gtxn[1].amount()),                                           # Check that the amount to be paid is correct
        Assert(amountAssetToBeTransfered == Btoi(Gtxn[0].application_args[2])),               # Check that there amount of ASA to sell is correct
        Assert(Global.current_application_address() == Gtxn[1].receiver()),                   # Check that the receiver of the payment is the App
        Assert(                                                                               # Verify that the seller has enough ASA to sell
            getAccountASABalance(seller, App.globalGet(Constants.AssetId))              
                >=  amountAssetToBeTransfered),
        App.localPut(seller, Constants.approveTransfer, Int(1)),                              # Approve the transfer from seller' side
        App.localPut(buyer, Constants.approveTransfer, Int(1)),                               # Approve the transfer from buyer' side
        Approve()
    ])
```
### 3.3 ExecuteTransfer method
```python
# [Step 4] Sequence that transfers the ASA, pays the seller and sends royalty fees to the creator
    # This step requires 1 transaction.
    # The  transaction is a NoOp App call transaction. There should be 1 arguments
    #   1. The first argument is the command to execute, in this case "executeTransfer"
    # We also account for the serviceCost to pay the inner transaction
    royaltyFee = App.globalGet(Constants.royaltyFee)
    collectedFees = App.globalGet(Constants.collectedFees)
    feesToBePaid = computeRoyaltyFee(amountToBePaid - serviceCost, royaltyFee)
    executeTransfer = Seq([
        Assert(Gtxn[0].application_args.length() == Int(1)),                            # Check that there is only 1 argument
        Assert(Global.group_size() == Int(1)),                                          # Check that is only 1 transaction
        Assert(approval == Int(1)),                                                     # Check that approval is set to 1 from seller' side
        Assert(App.localGet(buyer, Constants.approveTransfer) == Int(1)),               # Check approval from buyer' side
        Assert(                                                                         # Verify that the seller has enough ASA to sell
            getAccountASABalance(seller, App.globalGet(Constants.AssetId))              
                >=  amountAssetToBeTransfered),
        Assert(amountToBePaid - serviceCost > feesToBePaid),
        transferAsset(seller,                                                           # Transfer asset
                      Gtxn[0].sender(),
                      App.globalGet(Constants.AssetId), amountAssetToBeTransfered),
        sendPayment(seller, amountToBePaid - serviceCost - feesToBePaid),               # Pay seller
        App.globalPut(Constants.collectedFees, collectedFees + feesToBePaid),           # Collect fees, perhaps check for overflow?
        App.localDel(seller, Constants.amountPayment),                                  # Delete local variables
        App.localDel(seller, Constants.amountASA),
        App.localDel(seller, Constants.approveTransfer),
        App.localDel(buyer, Constants.approveTransfer),
        Approve()
    ])
```
### 3.4 Refund Method
```python
# Refund sequence
    # The buyer can get a refund if the payment has already been done but the NFT has not been transferred yet
    refund = Seq([
        Assert(Global.group_size() == Int(1)),                                           # Verify that it is only 1 transaction
        Assert(Txn.application_args.length() == Int(3)),                                 # Check that there is only 1 argument
        Assert(approval == Int(1)),                                                      # Asset that the payment has already been done
        Assert(App.localGet(buyer, Constants.approveTransfer) == Int(1)),
        Assert(amountToBePaid > Int(1000)),                                              # Verify that the amount is greater than the transaction fee
        sendPayment(buyer, amountToBePaid - Int(1000)),                                  # Refund buyer
        App.localPut(seller, Constants.approveTransfer, Int(0)),                         # Reset local variables
        App.localDel(buyer, Constants.approveTransfer),
        Approve()
    ])
```
### 3.5 claimFees Method
```python
# Claim Fees sequence
    # This sequence can be called only by the creator.  It is used to claim all the royalty fees
    # It may fail if the contract has not enough algo to pay the inner transaction (the creator should take
    # care of funding the contract in this case)
    claimFees = Seq([
        Assert(Global.group_size() == Int(1)),                                                 # Verify that it is only 1 transaction
        Assert(Txn.application_args.length() == Int(3)),                                       # Check that there is only 1 argument
        Assert(Txn.sender() == App.globalGet(Constants.Creator)),                              # Verify that the sender is the creator
        Assert(App.globalGet(Constants.collectedFees) > Int(0)),                               # Check that there are enough fees to collect
        sendPayment(App.globalGet(Constants.Creator), App.globalGet(Constants.collectedFees)), # Pay creator
        App.globalPut(Constants.collectedFees, Int(0)),                                        # Reset collected fees
        Approve()
    ])
```
### 3.6 Subroutines

```python
@Subroutine(TealType.none)
def sendPayment(receiver: Addr, amount: Int) -> Expr:
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


@Subroutine(TealType.none)
def transferAsset(sender: Addr, receiver: Addr, assetId: Int, amount: Int) -> Expr:
    """
    This subroutine can be used to transfer an asset
    from an account to another. 
    
    This subroutine can also be used to opt in an asset if ``amount``
    is 0 and ``sender`` is equal to ``receiver``.

    :param Addr sender   : Asset sender
    :param Addr receiver : Asset receiver
    :param Int assetId   : ID of the asset. Note that the id must also be passed in the ``foreignAssets``
                           field in the outer transaction (otherwise you will get a reference error)
    :param Int amount    : The amount of the asset to be transferred. A zero amount transferred to self allocates
                           that asset in the account's Asset map.
    """
    return Seq([
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.asset_amount: amount,
            TxnField.asset_receiver: receiver,
            TxnField.asset_sender: sender,
            TxnField.xfer_asset: assetId,
            TxnField.fee: Int(1000)
        }),
        InnerTxnBuilder.Submit(),
    ])

@Subroutine(TealType.uint64)
def getAccountASABalance(account: Addr, assetId: Int) -> TealType.uint64:
    """
    This subroutine returns the amount of ASA held by a certain
    account. Note that the asset id must also be passed in the ``foreignAssets``
    field in the outer transaction (otherwise you will get a reference error)

    :param Addr account  : The account to verify
    :param Int assetId   : ASA Id
    :return              : Amount of ASA held by the account
                           Returns 0 if the account does not have
                           any ASA of type ``assetId``.
    :rtype               : Int            
    """
    AssetAccountBalance = AssetHolding.balance(account, assetId)
    return Seq([
        AssetAccountBalance,
        If(AssetAccountBalance.hasValue() == Int(1)) \
        .Then(AssetAccountBalance.value())           \
        .Else(Int(0))
    ])


@Subroutine(TealType.uint64)
def computeRoyaltyFee(amount: Int, royaltyFee: Int) -> TealType.uint64:
    """
    This subroutine computes the fee given a specific ``amount`` and the
    predefined ``royaltyFee``.
    The ``royaltyFee`` variable must be expressed in thousands.

    Note that we assume that amount * royaltyFee will not overflow.
    In case it does, it will trigger an error and the transaction will
    fail.

    :param Int amount       : The amount paid
    :param Int royaltyFee   : The royalty fee (in thousands)
    :return                 : Fee to be paid in microAlgos
    :rtype                  : Int            
    """
    # If Mul() overflows the transaction will fail
    remainder = Mod(Mul(amount, royaltyFee), Int(1000))
    division = Div(Mul(amount, royaltyFee), Int(1000))

    # Computes the royalty fee. If the fee is equal to 0, or the amount is very small
    # the fee will be 0.
    # If the royalty fee is larger or equal to 1000 then we return the original amount.
    # If the remainder of royaltyFee * amount / 1000 is larger than 500 we round up the
    # result and return  1 + royaltyFee * amount / 1000. Otherwise we just return
    # royaltyFee * amount / 1000.
    return If(Or(royaltyFee == Int(0), division == Int(0))).Then(Int(0))   \
           .ElseIf(royaltyFee >= Int(1000)).Then(amount)                   \
           .ElseIf(remainder > Int(500)).Then(division + Int(1))           \
           .Else(division)
```
## 4. Setting up an Example scenario
### 4.1 Creating the asset
### 4.2 Creating the App
### 4.3 Simulate sales
### 4.4 Verify royalty fees

## 5. Conclusions

