"use client";

import {
  useState
} from "react";

export default function PrivacyTest() {
  const [
    input,
    setInput
  ] = useState("");

  const [
    result,
    setResult
  ] = useState(null);

  const [
    loading,
    setLoading
  ] = useState(false);

  async function analyse(event) {
    event.preventDefault();

    setLoading(true);

    try {
      const response =
        await fetch(
          "/api/privacy/classify",
          {
            method: "POST",

            headers: {
              "Content-Type":
                "application/json"
            },

            body: JSON.stringify({
              text: input
            })
          }
        );

      const data =
        await response.json();

      setResult(data);

    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={analyse}>

      <textarea
        className="vector-textarea"
        placeholder="Paste text, logs or other content here. The analysis happens locally on your Vector server."
        value={input}
        onChange={
          (event) =>
            setInput(
              event.target.value
            )
        }
      />

      <button
        className="control-button"
        type="submit"
        disabled={
          loading ||
          input.length === 0
        }
      >
        {
          loading
            ? "Analysing..."
            : "Analyse locally"
        }
      </button>

      {
        result && (
          <>
            <div className="result-grid">

              <div className="result-box">
                <div className="result-label">
                  Classification
                </div>

                <div
                  className={
                    `result-value privacy-${result.classification}`
                  }
                >
                  {
                    result.classification
                      .toUpperCase()
                  }
                </div>
              </div>

              <div className="result-box">
                <div className="result-label">
                  Findings
                </div>

                <div className="result-value">
                  {
                    result.findings
                      .reduce(
                        (total, item) =>
                          total +
                          item.count,
                        0
                      )
                  }
                </div>
              </div>

              <div className="result-box">
                <div className="result-label">
                  External AI
                </div>

                <div className="result-value">
                  {
                    result.externalAIAllowed
                      ? "Allowed"
                      : "Blocked"
                  }
                </div>
              </div>

            </div>

            {
              result.findings.length > 0 && (
                <div className="finding-list">

                  {
                    result.findings.map(
                      (finding) => (
                        <div
                          className="finding-row"
                          key={finding.type}
                        >
                          <span className="finding-name">
                            {finding.type}
                          </span>

                          <span className="finding-count">
                            {
                              finding.count
                            } detected
                          </span>
                        </div>
                      )
                    )
                  }

                </div>
              )
            }

            <div className="redacted-preview">
              {result.redacted}
            </div>
          </>
        )
      }

    </form>
  );
}
