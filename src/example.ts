const algosdk = require('algosdk');

import {checkVariables, appOptIn, assetOptIn,executeGroupTransaction} from './utils'

let requiredVariables: Array<string> = [
    'TEST_ALGOD_TOKEN',
    'TEST_ALGOD_SERVER',
    'TEST_ALGOD_PORT',
    'WALLET1_ADDR',
    'WALLET2_ADDR',
    'WALLET3_ADDR',
    'WALLET1_KEY',
    'WALLET2_KEY',
    'WALLET3_KEY',
    'APP_ID',
    'APP_ADDRESS',
    'ASSET_ID'
  ];

async function sale(wallet1: any, wallet2: any) {
  
}


async function main() {
  // Load environment variables
  console.log('[X] Checking if environment variables are set....')
  checkVariables(requiredVariables);
  console.log('[X] Variables set! Checking node...')

  // Load node
  const algoNode = new algosdk.Algodv2(process.env.TEST_ALGOD_TOKEN, process.env.TEST_ALGOD_SERVER, process.env.TEST_ALGOD_PORT);

  // Check if the node is connected
  if (await algoNode.status().do()) {
    console.log('[X] Node is connected!');
  } else {
    console.log('[!] Node not connected!');
    return;
  }

  // Load asset and app parameters
  const amountPayment: number = 200000;
  const assetIndex: number = parseInt(process.env.ASSET_ID!);
  const appId: number = parseInt(process.env.APP_ID!);
  const appAddress: string = (process.env.APP_ADDRESS!).trim();

  // Load accounts
  let wallet1Key: string = process.env.WALLET1_KEY!;
  let wallet2Key: string = process.env.WALLET2_KEY!;
  let wallet3Key: string = process.env.WALLET3_KEY!;

  console.log("[X] Loading wallets")

  const wallet1 = algosdk.mnemonicToSecretKey(wallet1Key.trim());
  const wallet2 = algosdk.mnemonicToSecretKey(wallet2Key.trim());
  const wallet3 = algosdk.mnemonicToSecretKey(wallet3Key.trim());

  // get suggested parameters
  let suggestedParams = await algoNode.getTransactionParams().do();
  suggestedParams.flatFee = true;
  suggestedParams.fee = 1000;

  // App opt-in
  console.log('[X] App opt-in')
  await appOptIn(algoNode, wallet1, appId);
  await appOptIn(algoNode, wallet2, appId);
  await appOptIn(algoNode, wallet3, appId);

  // Asset opt-in
  console.log('[X] Asset opt-in')
  await assetOptIn(algoNode, wallet2, assetIndex);
  await assetOptIn(algoNode, wallet3, assetIndex);

  console.log('[X] Initializing sale from wallet 1. Calling `setupTransfer` method from wallet 1');
  // call the created application
  let appTxn = algosdk.makeApplicationNoOpTxnFromObject({
    from: wallet1.addr,
    suggestedParams: suggestedParams,
    appIndex: appId,
    appArgs: [new Uint8Array(Buffer.from('setupSale')),
     algosdk.encodeUint64(amountPayment),
     ],
    foreignAssets: [assetIndex]          // We need to specify the asset id in foreignAssets, so that the smart contract can load it
    }
  );

  // Execute transaction
  await executeGroupTransaction(algoNode, [appTxn], [wallet1]);
  console.log('[X] Sale initialized');
  console.log('[X] Sending payment from wallet 2 to smart contract. Calling `buy` method from wallet 2');

  // call the  method 'buy'. Note that we must specify in the transaction field `foreignAssets` the assetId, otherwise the smart contract
  // can't load it correctly. Same for the seller's address, which should be specified in the `accounts` field
  appTxn = algosdk.makeApplicationNoOpTxnFromObject({
    from: wallet2.addr,
    suggestedParams: suggestedParams,
    appIndex: appId,
    appArgs: [new Uint8Array(Buffer.from('buy')),  algosdk.encodeUint64(assetIndex)],
    accounts: [wallet1.addr],                 // We need to specify the seller's account here, so that the smart contract can load it
    foreignAssets: [assetIndex]               // We need to specify the asset id in foreignAssets, so that the smart contract can load it
  });

  // Pay the app
  let paymentTxn = algosdk.makePaymentTxnWithSuggestedParamsFromObject({
      from: wallet2.addr,
      to: appAddress,
      amount: amountPayment,
      suggestedParams: suggestedParams,
    }
  )

  // Execute transaction
  await executeGroupTransaction(algoNode,
    [appTxn, paymentTxn],
    [wallet2, wallet2]);
  console.log('[X] Payment accepted');
  console.log('[X] Finalizing transfer. Calling `executeTransfer` method from wallet 2');

  // Call 'executeTransfer'. Note that we must specify in the transaction field `foreignAssets` the assetId, otherwise the smart contract
  // can't load it correctly. Same for the seller's address, which should be specified in the `accounts` field
  appTxn = algosdk.makeApplicationNoOpTxnFromObject({
    from: wallet2.addr,
    suggestedParams: suggestedParams,
    appIndex: appId,
    appArgs: [new Uint8Array(Buffer.from('executeTransfer'))],
    accounts: [wallet1.addr],              // We need to specify the seller's account here, so that the smart contract can load it
    foreignAssets: [assetIndex]            // We need to specify the asset id in foreignAssets, so that the smart contract can load it
  });

  // Execute transaction
  await executeGroupTransaction(algoNode, [appTxn], [wallet2]);
  
  console.log('[X] Asset correctly transfered from wallet 1 to wallet 2!');
  console.log('=============================================================')
  console.log('[X] Initializing sale from wallet 2. Calling `setupTransfer` method from wallet 2');
  
  // call the created application
  appTxn = algosdk.makeApplicationNoOpTxnFromObject({
    from: wallet2.addr,
    suggestedParams: suggestedParams,
    appIndex: appId,
    appArgs: [new Uint8Array(Buffer.from('setupSale')),
     algosdk.encodeUint64(amountPayment)
     ],
    foreignAssets: [assetIndex]
    }
  );

  await executeGroupTransaction(algoNode, [appTxn], [wallet2]);
  console.log('[X] Sale initialized');
  console.log('[X] Sending payment from wallet 3 to smart contract. Calling `buy` method from wallet 3');

  // call the created application
  appTxn = algosdk.makeApplicationNoOpTxnFromObject({
    from: wallet3.addr,
    suggestedParams: suggestedParams,
    appIndex: appId,
    appArgs: [new Uint8Array(Buffer.from('buy')),  algosdk.encodeUint64(assetIndex)],
    accounts: [wallet2.addr],
    foreignAssets: [assetIndex]
  });

  // Pay the app
  paymentTxn = algosdk.makePaymentTxnWithSuggestedParamsFromObject({
      from: wallet3.addr,
      to: appAddress,
      amount: amountPayment,
      suggestedParams: suggestedParams,
    }
  )

  await executeGroupTransaction(algoNode,
    [appTxn, paymentTxn],
    [wallet3, wallet3]);

  console.log('[X] Payment accepted');
  console.log('[X] Finalizing transfer. Calling `executeTransfer` method from wallet 2');

  appTxn = algosdk.makeApplicationNoOpTxnFromObject({
    from: wallet3.addr,
    suggestedParams: suggestedParams,
    appIndex: appId,
    appArgs: [new Uint8Array(Buffer.from('executeTransfer'))],
    accounts: [wallet2.addr, wallet1.addr],
    foreignAssets: [assetIndex]
  });
  await executeGroupTransaction(algoNode, [appTxn], [wallet3]);
  console.log('[X] Asset correctly transfered from wallet 2 to wallet 3!');
  
}

main().catch(console.error)
