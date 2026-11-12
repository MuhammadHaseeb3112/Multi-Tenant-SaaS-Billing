import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Loader2, Mail, MailCheck } from "lucide-react";

import { requestPasswordReset } from "../../api/auth";
import { firstApiError } from "../../utils/apiErrors";

import "./auth.css";

/**
 * "Forgot password": asks for the email and sends a reset link. The
 * answer is the same whether or not the email has an account.
 */
function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [sentMessage, setSentMessage] = useState("");

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();

    if (!email.trim()) {
      setError("Please enter your email address.");
      return;
    }

    setIsSubmitting(true);
    setError("");

    try {
      setSentMessage(await requestPasswordReset(email.trim()));
    } catch (err) {
      setError(
        firstApiError(err, "Could not send the reset link. Try again."),
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-card">
        <div className="auth-brand">
          <div className="auth-brand-mark">S</div>

          <span>SaaS Billing</span>
        </div>

        <div className="auth-header">
          <h1>Forgot your password?</h1>

          <p>
            Enter your email and we'll send you a link to choose a new
            one.
          </p>
        </div>

        {sentMessage ? (
          <div className="auth-success" role="status">
            <MailCheck size={20} />

            <div>
              <strong>Check your inbox</strong>
              <p>{sentMessage}</p>
              <p>The link works once and expires in 1 hour.</p>
            </div>
          </div>
        ) : (
          <>
            {error && (
              <div className="auth-error" role="alert">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="auth-form">
              <div className="form-group">
                <label htmlFor="email">Email address</label>

                <div className="input-wrapper">
                  <Mail size={18} />

                  <input
                    id="email"
                    name="email"
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="you@example.com"
                    autoComplete="email"
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
                    Sending...
                  </>
                ) : (
                  "Send reset link"
                )}
              </button>
            </form>
          </>
        )}

        <div className="auth-footer">
          <Link to="/login">Back to sign in</Link>
        </div>
      </section>
    </main>
  );
}

export default ForgotPassword;
