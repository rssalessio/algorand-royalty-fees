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

### 3.1 Subroutines

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
### 3.2 Initialization
### 3.3 SetupSale method
### 3.4 BuyASA method
### 3.5 ExecuteTransfer method
### 3.6 SetupSale method
### 3.7 Refund Method
### 3.8 claimFees Method

## 4. Setting up an Example scenario
### 4.1 Creating the asset
### 4.2 Creating the App
### 4.3 Simulate sales
### 4.4 Verify royalty fees

## 5. Conclusions

