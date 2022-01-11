from pyteal import *
import sys


class Constants:
    """
        Constant strings used in the smart contracts
    """
    Creator           = Bytes("Creator")               # Identified the account of the Asset creator, stored globally
    AssetId           = Bytes("AssetId")               # ID of the asset, stored globally
    amountPayment     = Bytes("amountPayment")         # Amount to be paid for the asset, stored locally on the seller's account
    amountASA         = Bytes("amountASA")             # Amount of asset sold, stored locally on the seller's account
    approveTransfer   = Bytes("approveTransfer")       # Approval variable, stored on the seller's and the buyer's accounts
    setupSale         = Bytes("setupSale")             # Method call
    buyASA            = Bytes("buyASA")                # Method call
    executeTransfer   = Bytes("executeTransfer")       # Method call
    royaltyFee        = Bytes("royaltyFee")            # Royalty fee in thousands
    claimFees         = Bytes("claimFees")             # Method call
    collectedFees     = Bytes("collectedFees")         # Amount of collected fees, stored globally
    refund            = Bytes("refund")                # Method call


@Subroutine(TealType.none)
def defaultTransactionChecks(txnId: Int) -> Expr:
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

@Subroutine(TealType.none)
def checkRoyaltyFeeComputation(amount: Int, royaltyFee: Int) -> Expr:
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


def approval_program():
    serviceCost = Int(2000) # cost of 2 inner transactions

    # [Step 1] Sequence used to initialize the smart contract. Should be called only at creation
    royaltyFeeArg = Btoi(Txn.application_args[2])
    assetDecimals = AssetParam.decimals(Btoi(Txn.application_args[1]))
    assetFrozen = AssetParam.defaultFrozen(Btoi(Txn.application_args[1]))
    initialize = Seq([
        Assert(Txn.type_enum() == TxnType.ApplicationCall),                  # Check if it's an application call
        Assert(Txn.application_args.length() == Int(3)),                     # Check that there are 3 arguments, Creator, AssetId and Royalty Fee
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
        Approve()
    ])

    # [Step 2] Sequence that sets up the sale of an ASA
    # There should be 3 arguments: 
    #   1. The first argument is the command to execute, in this case "setupSale"
    #   2. The second one is the payment amount
    #   3. The third one is the amount of ASA transfered
    # We first verify the the seller has enough ASA to sell, and then we locally save the arguments
    priceArg = Btoi(Txn.application_args[1])
    amountOfASAArg = Btoi(Txn.application_args[2])
    assetClawback = AssetParam.clawback(App.globalGet(Constants.AssetId))
    assetFreeze = AssetParam.freeze(App.globalGet(Constants.AssetId))
    setupSale = Seq([
        Assert(Txn.application_args.length() == Int(3)),                                      # Check that there are 3 arguments
        Assert(Global.group_size() == Int(1)),                                                # Verify that it is only 1 transaction
        defaultTransactionChecks(Int(0)),                                                     # Perform default transaction checks
        Assert(priceArg != Int(0)),                                                           # Check that the price is different than 0
        Assert(amountOfASAArg != Int(0)),                                                     # Check that the amount of ASA to transfer is different than 0                
        assetClawback,                                                                        # Verify that the clawback address is the contract
        Assert(assetClawback.hasValue()),
        Assert(assetClawback.value() == Global.current_application_address()),
        assetFreeze,                                                                          # Verify that the freeze address is the contract
        Assert(assetFreeze.hasValue()),
        Assert(assetFreeze.value() == Global.current_application_address()),
        Assert(                                                                               # Verify that the seller has enough ASA to sell
            getAccountASABalance(Txn.sender(), App.globalGet(Constants.AssetId))
                >=  amountOfASAArg),
        Assert(priceArg > serviceCost),                                                       # Check that the price is greater than the service cost
        App.localPut(Txn.sender(), Constants.amountPayment, priceArg),                        # Save the price
        App.localPut(Txn.sender(), Constants.amountASA, amountOfASAArg),                      # Save the amount of ASA to transfer
        App.localPut(Txn.sender(), Constants.approveTransfer, Int(0)),                        # Reject transfer until payment is done
        Approve()
    ])


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
    # Logic
    buyASA = Seq([
        Assert(Gtxn[0].application_args.length() == Int(3)),                                  # Check that there are 3 arguments
        Assert(Global.group_size() == Int(2)),                                                # Check that there are 2 transactions
        Assert(Gtxn[1].type_enum() == TxnType.Payment),                                       # Check that the second transaction is a payment
        Assert(App.globalGet(Constants.AssetId) == Btoi(Gtxn[0].application_args[1])),        # Check that the assetId is correct
        Assert(approval == Int(0)),                                                           # Check that the transfer has not been issued yet
        Assert(amountToBePaid == Gtxn[1].amount()),                                           # Check that the amount to be paid is correct
        Assert(amountAssetToBeTransfered == Btoi(Gtxn[0].application_args[2])),               # Check that there amount of ASA to sell is correct
        Assert(Global.current_application_address() == Gtxn[1].receiver()),                   # Check that the receiver of the payment is the App
        defaultTransactionChecks(Int(0)),                                                     # Perform default transaction checks
        defaultTransactionChecks(Int(1)),                                                     # Perform default transaction checks
        Assert(                                                                               # Verify that the seller has enough ASA to sell
            getAccountASABalance(seller, App.globalGet(Constants.AssetId))              
                >=  amountAssetToBeTransfered),
        App.localPut(seller, Constants.approveTransfer, Int(1)),                              # Approve the transfer from seller' side
        App.localPut(buyer, Constants.approveTransfer, Int(1)),                               # Approve the transfer from buyer' side
        Approve()
    ])

    # [Step 4] Sequence that transfers the ASA, pays the seller and sends royalty fees to the creator
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
        Assert(App.localGet(buyer, Constants.approveTransfer) == Int(1)),               # Check approval from buyer' side
        Assert(serviceCost < amountToBePaid),                                           # Check underflow
        Assert(                                                                         # Verify that the seller has enough ASA to sell
            getAccountASABalance(seller, App.globalGet(Constants.AssetId))              
                >=  amountAssetToBeTransfered),
        checkRoyaltyFeeComputation(amountToBePaid - serviceCost, royaltyFee),
        feesToBePaid.store(
            computeRoyaltyFee(amountToBePaid - serviceCost, royaltyFee)),               # Reduce number of subroutine calls by saving the variable inside a scratchvar variable
        Assert(Int(2 ** 64 - 1) - feesToBePaid.load() >= amountToBePaid - serviceCost), # Check overflow on payment
        Assert(Int(2 ** 64 - 1) - collectedFees >= feesToBePaid.load()),                # Check overflow on collected fees
        Assert(amountToBePaid - serviceCost > feesToBePaid.load()),
        transferAsset(seller,                                                           # Transfer asset
                      Gtxn[0].sender(),
                      App.globalGet(Constants.AssetId), amountAssetToBeTransfered),
        sendPayment(seller, amountToBePaid - serviceCost - feesToBePaid.load()),        # Pay seller
        App.globalPut(Constants.collectedFees, collectedFees + feesToBePaid.load()),    # Collect fees
        App.localDel(seller, Constants.amountPayment),                                  # Delete local variables
        App.localDel(seller, Constants.amountASA),
        App.localDel(seller, Constants.approveTransfer),
        App.localDel(buyer, Constants.approveTransfer),
        Approve()
    ])

    # Refund sequence
    # The buyer can get a refund if the payment has already been done but the NFT has not been transferred yet
    refund = Seq([
        Assert(Global.group_size() == Int(1)),                                           # Verify that it is only 1 transaction
        Assert(Txn.application_args.length() == Int(1)),                                 # Check that there is only 1 argument  
        defaultTransactionChecks(Int(0)),                                                # Perform default transaction checks
        Assert(App.localGet(seller, Constants.approveTransfer) == Int(1)),               # Asset that the payment has already been done
        Assert(App.localGet(buyer, Constants.approveTransfer) == Int(1)),
        Assert(amountToBePaid > Int(1000)),                                              # Underflow check: verify that the amount is greater than the transaction fee
        sendPayment(buyer, amountToBePaid - Int(1000)),                                  # Refund buyer
        App.localPut(seller, Constants.approveTransfer, Int(0)),                         # Reset local variables
        App.localDel(buyer, Constants.approveTransfer),
        Approve()
    ])

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
             

    # Check the transaction type and execute the corresponding code
    #   1. If application_id() is 0 then the program has just been created, so we initialize it
    #   2. If on_completion() is 0 we execute the onCall code
    return If(Txn.application_id() == Int(0)).Then(initialize)                  \
            .ElseIf(Txn.on_completion() == OnComplete.CloseOut).Then(Approve()) \
            .ElseIf(Txn.on_completion() == OnComplete.OptIn).Then(Approve())    \
            .ElseIf(Txn.on_completion() == Int(0)).Then(onCall)                 \
            .Else(Reject())


def clear_program():
    return Approve()

if __name__ == "__main__":
    # Compiles the approval program
    with open(sys.argv[1], "w+") as f:
        compiled = compileTeal(approval_program(), mode=Mode.Application, version=5)
        f.write(compiled)

    # Compiles the clear program
    with open(sys.argv[2], "w+") as f:
        compiled = compileTeal(clear_program(), mode=Mode.Application, version=5)
        f.write(compiled)