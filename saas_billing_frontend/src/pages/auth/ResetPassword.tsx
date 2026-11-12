import { useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2, Loader2, LockKeyhole } from "lucide-react";

import {
  confirmPasswordReset,
  validatePasswordResetLink,
} from "../../api/auth";
import { firstApiError } from "../../utils/apiErrors";

import "./auth.css";

type LinkState = "checking" | "valid" | "invalid";

const INVALID_LINK =
  "This password reset link is invalid or has expired. Please request a new one.";

/**
 * Opened from the reset email: checks the link, then lets the user
 * choose a new password.
 */
function ResetPassword() {
  const [searchParams] = useSearchParams();
  const uid = searchParams.get("uid") ?? "";
  const token = searchParams.get("token") ?? "";

  const [linkState, setLinkState] = useState<LinkState>(
    uid && token ? "checking" : "invalid",
  );
  const [linkError, setLinkError] = useState(INVALID_LINK);

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [doneMessage, setDoneMessage] = useState("");

  useEffect(() => {
    if (!uid || !token) {
      return;
    }

    let cancelled = false;

    validatePasswordResetLink(uid, token)
      .then(() => {
        if (!cancelled) setLinkState("valid");
      })
      .catch((err) => {
        if (cancelled) return;
        setLinkError(firstApiError(err, INVALID_LINK));
        setLinkState("invalid");
      });

    return () => {
      cancelled = true;
    };
  }, [uid, token]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();

    if (password !== confirm) {
      setError("The two passwords do not match.");
      return;
    }

    setIsSubmitting(true);
    setError("");

    try {
      setDoneMessage(
        await confirmPasswordReset({
          uid,
          token,
          new_password: password,
          new_password_confirm: confirm,
        }),
      );
    } catch (err) {
      setError(firstApiError(err, "Could not reset your password."));
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderBody = () => {
    if (doneMessage) {
      return (
        <>
          <div className="auth-success" role="status">
            <CheckCircle2 size={20} />

            <div>
              <strong>Password updated</strong>
              <p>{doneMessage}</p>
            </div>
          </div>

          <Link className="auth-submit auth-submit-link" to="/login">
            Go to sign in
          </Link>
        </>
      );
    }

    if (linkState === "checking") {
      return (
        <div className="auth-checking" role="status">
          <Loader2 className="auth-spinner" size={20} />
          Checking your link...
        </div>
      );
    }

    if (linkState === "invalid") {
      return (
        <>
          <div className="auth-error" role="alert">
            {linkError}
          </div>

          <Link
            className="auth-submit auth-submit-link"
            to="/forgot-password"
          >
            Request a new link
          </Link>
        </>
      );
    }

    return (
      <>
        {error && (
          <div className="auth-error" role="alert">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-group">
            <label htmlFor="new-password">New password</label>

            <div className="input-wrapper">
              <LockKeyhole size={18} />

              <input
                id="new-password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="At least 8 characters"
                autoComplete="new-password"
                minLength={8}
                required
                disabled={isSubmitting}
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="confirm-password">Confirm new password</label>

            <div className="input-wrapper">
              <LockKeyhole size={18} />

              <input
                id="confirm-password"
                type="password"
                value={confirm}
                onChange={(event) => setConfirm(event.target.value)}
                placeholder="Repeat the new password"
                autoComplete="new-password"
                required
                disabled={isSubmitting}
              />
            </div>
          </div>

          <button
            type="submit"
            className="auth-submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <>
                <Loader2 className="auth-spinner" size={18} />
                Saving...
              </>
            ) : (
              "Set new password"
            )}
          </button>
        </form>
      </>
    );
  };

  return (
    <main className="auth-page">
      <section className="auth-card">
        <div className="auth-brand">
          <div className="auth-brand-mark">S</div>

          <span>SaaS Billing</span>
        </div>

        <div className="auth-header">
          <h1>Choose a new password</h1>

          <p>
            After this, you'll be signed out on every other device.
          </p>
        </div>

        {renderBody()}

        {!doneMessage && (
          <div className="auth-footer">
            <Link to="/login">Back to sign in</Link>
          </div>
        )}
      </section>
    </main>
  );
}

export default ResetPassword;
