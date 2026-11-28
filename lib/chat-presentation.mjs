const names = {
  EMAIL: "email",
  PERSON: "name",
  PASSWORD: "password",
  API_KEY: "API key",
  TOKEN: "token",
  PRIVATE_KEY: "private key",
  PHONE: "phone",
  ADDRESS: "address",
  PRIVATE_IP: "IP address",
  ACCOUNT: "account",
  ORGANIZATION: "organization",
};
// Display only. Stored messages, source names, privacy mappings and API payloads stay intact.
export function conversationLabel(value, fallback = "New conversation") {
  return (
    String(value || "")
      .replace(
        /<VEC_([A-Z_]+)_(?:[a-f0-9]{6,32}>|[a-f0-9]{0,32}(?=$|\.\.\.|…))/g,
        (_, type) => `[${names[type] || "private detail"}]`,
      )
      .replace(/\s+/g, " ")
      .trim() || fallback
  );
}
export function submitsOnEnter(event) {
  return (
    event.key === "Enter" &&
    !event.shiftKey &&
    !event.isComposing &&
    !event.nativeEvent?.isComposing &&
    event.keyCode !== 229 &&
    event.nativeEvent?.keyCode !== 229
  );
}
