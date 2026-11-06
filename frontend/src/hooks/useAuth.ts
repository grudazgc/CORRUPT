import { useCallback, useEffect, useState } from "react";
import { useConnection, useWallet } from "@solana/wallet-adapter-react";
import { VersionedTransaction } from "@solana/web3.js";
import bs58 from "bs58";

import { api } from "../lib/api";

const TOKEN_KEY = "corrupt.jwt";

/**
 * Authenticates the connected wallet by signing a challenge message, then
 * exposes the JWT for subsequent API calls. The signature is off-chain: it
 * costs nothing and authorises no transfer.
 */
export function useAuth() {
  const { connection } = useConnection();
  const { publicKey, signMessage, sendTransaction, connected } = useWallet();
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!connected) {
      localStorage.removeItem(TOKEN_KEY);
      setToken(null);
    }
  }, [connected]);

  const signIn = useCallback(async () => {
    if (!publicKey || !signMessage) {
      setError("This wallet cannot sign messages. Try Phantom or Solflare.");
      return null;
    }
    setBusy(true);
    setError(null);
    try {
      const wallet = publicKey.toBase58();
      const challenge = await api.challenge(wallet);
      const signature = await signMessage(new TextEncoder().encode(challenge.message));
      const result = await api.verify(wallet, bs58.encode(signature));
      localStorage.setItem(TOKEN_KEY, result.access_token);
      setToken(result.access_token);
      return result.access_token;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
      return null;
    } finally {
      setBusy(false);
    }
  }, [publicKey, signMessage]);

  const signOut = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
  }, []);

  /**
   * Deserializes the unsigned transaction returned by `/prepare`, refreshes
   * its blockhash, has the wallet sign it, and broadcasts it.
   */
  const signAndSendPrepared = useCallback(
    async (base64Transaction: string) => {
      if (!publicKey) throw new Error("Connect a wallet first");
      const bytes = Uint8Array.from(atob(base64Transaction), (char) => char.charCodeAt(0));
      const versioned = VersionedTransaction.deserialize(bytes);

      const latest = await connection.getLatestBlockhash();
      versioned.message.recentBlockhash = latest.blockhash;

      const signature = await sendTransaction(versioned, connection, {
        skipPreflight: false,
        maxRetries: 3,
      });
      const confirmation = await connection.confirmTransaction(
        {
          signature,
          blockhash: latest.blockhash,
          lastValidBlockHeight: latest.lastValidBlockHeight,
        },
        "confirmed",
      );
      if (confirmation.value.err) {
        throw new Error(`Transaction failed: ${JSON.stringify(confirmation.value.err)}`);
      }
      return signature;
    },
    [connection, publicKey, sendTransaction],
  );

  return { token, signIn, signOut, busy, error, signAndSendPrepared };
}
