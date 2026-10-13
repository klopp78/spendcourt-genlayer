import { createClient } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import { ExecutionResult, TransactionHashVariant, TransactionStatus } from "genlayer-js/types";

export const SPEND_COURT_CONTRACT_ADDRESS = (process.env.NEXT_PUBLIC_SPEND_COURT_CONTRACT_ADDRESS ?? "0x02a74A1f39d0d00047833b4DE54B4100baFB2D96") as `0x${string}`;
export type WalletAddress = `0x${string}`;
const client = (account?: WalletAddress) => createClient({ chain: studionet, account });
const address = (override?: WalletAddress) => override ?? SPEND_COURT_CONTRACT_ADDRESS;

async function read(functionName: string, args: string[], contractAddress?: WalletAddress) {
  return client().readContract({ address: address(contractAddress), functionName, args, jsonSafeReturn: true, leaderOnly: true, transactionHashVariant: TransactionHashVariant.LATEST_FINAL });
}
async function write(walletAddress: WalletAddress, functionName: string, args: string[], contractAddress?: WalletAddress) {
  const connected = client(walletAddress); await connected.connect("studionet");
  const hash = await connected.writeContract({ address: address(contractAddress), functionName, args, value: BigInt(0), leaderOnly: false });
  const receipt = await connected.waitForTransactionReceipt({ hash, status: TransactionStatus.FINALIZED, fullTransaction: true });
  if ((receipt as { txExecutionResultName?: ExecutionResult }).txExecutionResultName !== ExecutionResult.FINISHED_WITH_RETURN) {
    throw new Error("Transaction finalized without GenVM SUCCESS");
  }
  return { hash, receipt };
}
export const getOrder = (id: string, contractAddress?: WalletAddress) => read("get_order", [id], contractAddress);
export const getAssessment = (id: string, contractAddress?: WalletAddress) => read("get_assessment", [id], contractAddress);
export const getSettlement = (id: string, contractAddress?: WalletAddress) => read("get_settlement", [id], contractAddress);
export const registerOrder = (wallet: WalletAddress, args: string[], contractAddress?: WalletAddress) => write(wallet, "register_order", args, contractAddress);
export const assessDelivery = (wallet: WalletAddress, args: string[], contractAddress?: WalletAddress) => write(wallet, "assess_delivery", args, contractAddress);
export const finalizeReceipt = (wallet: WalletAddress, orderId: string, assessmentId: string, contractAddress?: WalletAddress) => write(wallet, "finalize_receipt", [orderId, assessmentId], contractAddress);
export const executeSettlement = (wallet: WalletAddress, orderId: string, assessmentId: string, paymentManifestUrl: string, paymentTransactionUrl: string, contractAddress?: WalletAddress) => write(wallet, "execute_settlement", [orderId, assessmentId, paymentManifestUrl, paymentTransactionUrl], contractAddress);
