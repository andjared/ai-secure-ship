import { useState } from "react";
import "./CodeModal.css";

interface CodeModalProps {
  onClose: () => void;
}

const CODE_LENGTH = 6;

export function CodeModal({ onClose }: CodeModalProps) {
  const [code, setCode] = useState("");
  return (
    <div className="code-modal">
      <div
        className="code-modal__dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="code-modal-title"
      >
        <button
          className="code-modal__close"
          type="button"
          aria-label="Close"
          onClick={onClose}
        >
          ×
        </button>
        <h2 id="code-modal-title" className="code-modal__title">
          Enter your verification code
        </h2>
        <p className="code-modal__text">
          We've sent a 6-digit code to the phone number on your account.
        </p>
        <div className="code-modal__digits">
          <input
            type="text"
            className="code-modal__input"
            value={code}
            onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))}
            maxLength={CODE_LENGTH}
            inputMode="numeric"
            autoComplete="one-time-code"
            autoFocus
            aria-label="6 digit code"
          />
          {Array.from({ length: CODE_LENGTH }, (_, i) => (
            <span
              key={i}
              aria-hidden
              className={`code-modal__digit${i === code.length ? " code-modal__digit--active" : ""}`}
            >
              {code[i]}
            </span>
          ))}
        </div>
        <button
          className="code-modal__verify"
          type="button"
          disabled={code.length < CODE_LENGTH}
        >
          Verify
        </button>
      </div>
    </div>
  );
}
