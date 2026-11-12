import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Eye, EyeOff, Loader2, LockKeyhole, Mail } from "lucide-react";

import { previewInvitation } from "../../api/tenants";
import { useAuth } from "../../context/AuthContext";
import DemoLogin from "./DemoLogin";

import "./auth.css";

function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  // Arrived from an invitation for an existing account: fill in the
  // invited email and go back to the invitation after signing in.
  const [searchParams] = useSearchParams();
  const inviteToken = searchParams.get("invite") ?? "";
  const [inviteFor, setInviteFor] = useState("");

  useEffect(() => {
    if (!inviteToken) {
      return;
    }

    let cancelled = false;

    previewInvitation(inviteToken)
      .then((preview) => {
        if (cancelled) return;
        setEmail(preview.email);
        setInviteFor(preview.organization_name);
      })
      .catch(() => {
        // Invalid link: the invitation page explains it after sign-in.
      });

    return () => {
      cancelled = true;
    };
  }, [inviteToken]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    setError("");

    if (!email.trim()) {
      setError("Please enter your email address.");
      return;
    }

    if (!password) {
      setError("Please enter your password.");
      return;
    }

    try {
      setIsSubmitting(true);

      await login({
        email: email.trim(),
        password,
      });

      navigate(
        inviteToken
          ? `/accept-invitation?token=${encodeURIComponent(inviteToken)}`
          : "/dashboard",
        { replace: true },
      );
    } catch (error: unknown) {
      if (
        typeof error === "object" &&
        error !== null &&
        "response" in error
      ) {
        const response = (
          error as {
            response?: {
              status?: number;
              data?: {
                detail?: string;
                non_field_errors?: string[];
                email?: string[];
                password?: string[];
              };
            };
          }
        ).response;

        const data = response?.data;

        // No answer at all, or a server-side failure: the password is
        // not the problem, so don't blame the credentials.
        if (!response || (response.status ?? 0) >= 500) {
          setError(
            "The server is not responding. Please try again in a moment.",
          );
          return;
        }

        setError(
          data?.detail ||
            data?.non_field_errors?.[0] ||
            data?.email?.[0] ||
            data?.password?.[0] ||
            "Unable to sign in. Please check your credentials.",
        );
      } else {
        setError("Unable to connect to the server. Please try again.");
      }
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
          <h1>Welcome back</h1>

          <p>
            {inviteFor
              ? `Sign in to accept your invitation to ${inviteFor}.`
              : "Sign in to manage your subscriptions, invoices, and billing."}
          </p>
        </div>

        {error && (
          <div className="auth-error" role="alert">
            {error}
          </div>
        )}

        <DemoLogin
          disabled={isSubmitting}
          onPick={(demoEmail, demoPassword) => {
            setEmail(demoEmail);
            setPassword(demoPassword);
            setError("");
          }}
        />

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

          <div className="form-group">
            <div className="password-label-row">
              <label htmlFor="password">Password</label>

              <Link className="forgot-link" to="/forgot-password">
                Forgot password?
              </Link>
            </div>

            <div className="input-wrapper">
              <LockKeyhole size={18} />

              <input
                id="password"
                name="password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(event) =>
                  setPassword(event.target.value)
                }
                placeholder="Enter your password"
                autoComplete="current-password"
                disabled={isSubmitting}
              />

              <button
                type="button"
                className="password-toggle"
                onClick={() =>
                  setShowPassword((current) => !current)
                }
                aria-label={
                  showPassword
                    ? "Hide password"
                    : "Show password"
                }
                disabled={isSubmitting}
              >
                {showPassword ? (
                  <EyeOff size={18} />
                ) : (
                  <Eye size={18} />
                )}
              </button>
            </div>
          </div>

          <button
            type="submit"
            className="auth-submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <>
                <Loader2
                  size={18}
                  className="auth-spinner"
                />
                Signing in...
              </>
            ) : (
              "Sign in"
            )}
          </button>
        </form>

        <div className="auth-footer">
          <span>Don't have an account?</span>

          <Link to="/register">Create an account</Link>
        </div>
      </section>
    </main>
  );
}

export default Login;