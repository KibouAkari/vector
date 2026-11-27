"use client";
export default function PrivacyReceipt({ receipt }) {
  if (!receipt || receipt.mode !== "masked" || !receipt.replaced) return null;
  return (
    <details className="privacy-receipt">
      <summary>{receipt.replaced} Angaben vor dem Versand maskiert</summary>
      <p>
        Versandfassung mit Platzhaltern. Der Chat zeigt lokal wiederhergestellte
        Angaben.
      </p>
      <pre>{receipt.sentText}</pre>
    </details>
  );
}
