const algosdk = require('algosdk');

export function ensureEnvVariableIsSet(varName: string) {
    if (typeof process.env[varName] !== 'string') {
      throw new Error(`"${varName}" environment variable not set.`);
    }
}

export function checkVariables(variables: Array<string>) {
    for (let idx=0; idx < variables.length; idx++)
        ensureEnvVariableIsSet(variables[idx]);
}

// helper function to await transaction confirmation
// Function used to wait for a tx confirmation
export async function awaitForConfirmation(algodclient: any, txId: any) {
    let status = (await algodclient.status().do());
    let lastRound = status["last-round"];
      while (true) {
        const pendingInfo = await algodclient.pendingTransactionInformation(txId).do();
        if (pendingInfo["confirmed-round"] !== null && pendingInfo["confirmed-round"] > 0) {
          //Got the completed Transaction
          console.log("Transaction " + txId + " confirmed in round " + pendingInfo["confirmed-round"]);
          break;
        }
        lastRound++;
        await algodclient.statusAfterBlock(lastRound).do();
      }
}

async function sendRawTransaction(algoNode: any, signedTxn: any): Promise<boolean> {
  console.log('Sending transaction')
  const { txId } = await algoNode.sendRawTransaction(signedTxn).do();

  if (txId === null)
    return false;

  // Wait for confirmation
  console.log('Waiting for confirmation')
  let res = awaitForConfirmation(algoNode, txId).then(function (valid: any) {
    return true;
  }).catch(function (err: any) { return null; });

  if (await res === null)
    return false;

  // // display results
  console.log('Waiting for response');
  let transactionResponse = await algoNode.pendingTransactionInformation(txId).do();
  console.log('Transaction completed!');
  return true;
}

export async function executeTransaction(node: any, txn: any, wallet: any): Promise<boolean> {
    let signedTxn = txn.signTxn(wallet.sk);
    let txId = txn.txID().toString();
    console.log("Signed transaction with txID: %s", txId);
    return await sendRawTransaction(node,signedTxn);
}
  

export async function executeGroupTransaction(algoNode: any, txns: any, accounts: any): Promise<boolean> {
  algosdk.assignGroupID(txns);
  let stxns = [];
  for (let idx = 0; idx < txns.length; idx++) {
    let signedTxn = txns[idx].signTxn(accounts[idx].sk);
    stxns.push(signedTxn);
  }
  return await sendRawTransaction(algoNode, stxns);
}


export async function appOptIn(algoNode: any, wallet: any, appId: any): Promise<boolean> {
    const suggestedParams = await algoNode.getTransactionParams().do();
    let txn = algosdk.makeApplicationOptInTxn(wallet.addr, suggestedParams, appId);
    return executeTransaction(algoNode, txn, wallet);
}

export async function assetOptIn(algoNode: any, wallet: any, assetId: any): Promise<boolean>  {
    const suggestedParams = await algoNode.getTransactionParams().do();
    const txnAssetOptIn = algosdk.makeAssetTransferTxnWithSuggestedParamsFromObject({
        from: wallet.addr,
        to: wallet.addr,
        assetIndex: assetId,
        amount: 0,
        suggestedParams: suggestedParams,
      }
    );
    return executeTransaction(algoNode, txnAssetOptIn, wallet);
  }