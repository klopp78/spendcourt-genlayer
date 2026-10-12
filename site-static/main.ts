import { createClient } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import { TransactionHashVariant, TransactionStatus } from "genlayer-js/types";
import "./styles.css";

type Ethereum = { request(args: { method: string; params?: unknown[] }): Promise<unknown> };
declare global { interface Window { ethereum?: Ethereum } }
type Address = `0x${string}`;
let wallet: Address | null = null;
const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const input = (id: string) => ($(id) as HTMLInputElement).value.trim();
const short = (value: string) => value.length > 16 ? `${value.slice(0, 8)}…${value.slice(-6)}` : value;
const contract = () => input("contract-address") as Address;
const message = (error: unknown) => error instanceof Error ? error.message : String(error);

function setStatus(value: string, phase = "READY") { $("status").textContent = value; $("phase").textContent = phase; }
function setOutput(value: unknown) { $("output").textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2); }
function syncExplorer() { const value = contract(); $("short-address").textContent = short(value); ($("explorer") as HTMLAnchorElement).href = `https://explorer-studio.genlayer.com/address/${value}`; }
function extract(value: unknown, pattern: RegExp): string { if (typeof value === "string") return value.match(pattern)?.[0] ?? ""; if (value instanceof Uint8Array) return new TextDecoder().decode(value).match(pattern)?.[0] ?? ""; if (value && typeof value === "object") for (const child of Object.values(value as Record<string, unknown>)) { const found = extract(child, pattern); if (found) return found; } return ""; }
async function connect() { if (!window.ethereum) throw new Error("No browser wallet detected."); const accounts = await window.ethereum.request({ method: "eth_requestAccounts" }) as Address[]; if (!accounts[0]) throw new Error("No wallet account returned."); wallet = accounts[0]; $("connect").textContent = short(wallet); setStatus(`Wallet connected: ${short(wallet)}`); return wallet; }
function readClient() { return createClient({ chain: studionet }); }
async function write(functionName: string, args: string[], idPattern?: RegExp) {
  const account = wallet ?? await connect(); const client = createClient({ chain: studionet, account, provider: window.ethereum }); await client.connect("studionet");
  setStatus(`Submitting ${functionName} to full validator consensus...`, "SUBMITTING");
  const hash = await client.writeContract({ address: contract(), functionName, args, value: BigInt(0), leaderOnly: false }); $("tx").textContent = short(hash); setStatus(`Transaction ${short(hash)} submitted. Waiting for finality...`, "CONSENSUS");
  const receipt = await client.waitForTransactionReceipt({ hash, status: TransactionStatus.FINALIZED, interval: 3000, retries: 120, fullTransaction: true } as never);
  const id = idPattern ? extract(receipt, idPattern) : ""; setOutput(receipt); setStatus(id ? `Finalized. Contract returned ${id}.` : "Transaction finalized successfully.", "FINALIZED"); return id;
}
async function read(functionName: string, id: string) { setStatus(`Reading ${functionName} from LATEST_FINAL...`, "READBACK"); const value = await readClient().readContract({ address: contract(), functionName, args: [id], jsonSafeReturn: true, leaderOnly: true, transactionHashVariant: TransactionHashVariant.LATEST_FINAL }); const text = typeof value === "string" ? value : JSON.stringify(value); setOutput(JSON.parse(text || "{}")); setStatus(`Loaded ${id} from finalized contract state.`, "SUCCESS"); }

document.querySelectorAll<HTMLButtonElement>(".tab").forEach((tab) => tab.addEventListener("click", () => { document.querySelectorAll(".tab,.view").forEach((node) => node.classList.remove("active")); tab.classList.add("active"); $(tab.dataset.tab!).classList.add("active"); }));
$("connect").addEventListener("click", () => connect().catch((error) => setStatus(message(error), "FAILED")));
$("order").addEventListener("submit", (event) => { event.preventDefault(); write("register_order", [input("service-title"), input("agent"), input("payee"), input("currency"), input("budget"), input("deadline"), input("mandate"), input("policy"), input("repository")], /ord_[a-f0-9]{20}/).then((id) => { if (id) { $("order-id").textContent = id; ($("assessment-order") as HTMLInputElement).value = id; ($("settle-order") as HTMLInputElement).value = id; } }).catch((error) => setStatus(message(error), "FAILED")); });
$("assessment").addEventListener("submit", (event) => { event.preventDefault(); write("assess_delivery", [input("assessment-order"), input("invoice-number"), input("requested"), input("invoice-url"), input("execution-url"), input("deliverable-url"), input("payment-url")], /sct_[a-f0-9]{20}/).then((id) => { if (id) { $("assessment-id").textContent = id; ($("settle-assessment") as HTMLInputElement).value = id; } }).catch((error) => setStatus(message(error), "FAILED")); });
$("finalize").addEventListener("click", () => write("finalize_receipt", [input("settle-order"), input("settle-assessment")]).catch((error) => setStatus(message(error), "FAILED")));
$("execute").addEventListener("click", () => write("execute_settlement", [input("settle-order"), input("settle-assessment")]).catch((error) => setStatus(message(error), "FAILED")));
$("read-order").addEventListener("click", () => read("get_order", input("record-id")).catch((error) => setStatus(message(error), "FAILED")));
$("read-assessment").addEventListener("click", () => read("get_assessment", input("record-id")).catch((error) => setStatus(message(error), "FAILED")));
$("read-settlement").addEventListener("click", () => read("get_settlement", input("record-id")).catch((error) => setStatus(message(error), "FAILED")));
$("contract-address").addEventListener("input", syncExplorer); syncExplorer();
