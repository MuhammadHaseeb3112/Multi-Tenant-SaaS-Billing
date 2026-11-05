import {
  useState,
  type FormEvent,
} from "react";

import {
  Link,
  useNavigate,
  useSearchParams,
} from "react-router-dom";

import { useAuth } from "../../context/AuthContext";

function Register() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { register } = useAuth();

  const urlInvitationToken =
    searchParams.get("token") || "";

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [organizationName, setOrganizationName] =
    useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] =
    useState("");

  const [invitationToken, setInvitationToken] =
    useState(urlInvitationToken);

  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] =
    useState(false);

  const getErrorMessage = (error: unknown): string => {
    if (
      typeof error === "object" &&
      error !== null &&
      "response" in error
    ) {
      const response = (
        error as {
          response?: {
            data?: unknown;
          };
        }
      ).response;

      const data = response?.data;

      if (typeof data === "string") {
        return data;
      }

      if (
        typeof data === "object" &&
        data !== null
      ) {
        const values = Object.values(data);

        for (const value of values) {
          if (Array.isArray(value) && value.length > 0) {
            return String(value[0]);
          }

          if (typeof value === "string") {
            return value;
          }
        }
      }
    }

    if (error instanceof Error) {
      return error.message;
    }

    return "Registration failed. Please check your information and try again.";
  };

  const handleSubmit = async (
    event: FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault();
    setError("");

    if (password.length < 8) {
      setError(
        "Password must be at least 8 characters long.",
      );
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    if (
      !invitationToken.trim() &&
      !organizationName.trim()
    ) {
      setError(
        "Enter an organization name or use an invitation token.",
      );
      return;
    }

    setIsSubmitting(true);

    try {
      await register({
        email: email.trim(),
        password,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        organization_name:
          organizationName.trim() || undefined,
        invitation_token:
          invitationToken.trim() || undefined,
      });

      navigate("/dashboard", {
        replace: true,
      });
    } catch (error) {
      setError(getErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  };

  const isInvitationRegistration =
    Boolean(invitationToken.trim());

  return (
    <div className="register-page">
      <div className="register-background" />

      <main className="register-container">
        <section className="register-card">
          <div className="register-brand">
            <div className="brand-icon">S</div>

            <div>
              <div className="brand-name">
                SaaS Billing
              </div>

              <div className="brand-subtitle">
                FINANCE PLATFORM
              </div>
            </div>
          </div>

          <div className="register-header">
            <div className="eyebrow">
              {isInvitationRegistration
                ? "TEAM INVITATION"
                : "GET STARTED"}
            </div>

            <h1>
              {isInvitationRegistration
                ? "Join your team"
                : "Create your account"}
            </h1>

            <p>
              {isInvitationRegistration
                ? "Complete your account to join the organization."
                : "Start managing your subscriptions, invoices and revenue."}
            </p>
          </div>

          {isInvitationRegistration && (
            <div className="invitation-banner">
              <span className="banner-icon">✓</span>

              <div>
                <strong>Invitation detected</strong>

                <p>
                  Your invitation token will be used
                  automatically during registration.
                </p>
              </div>
            </div>
          )}

          {error && (
            <div className="error-message">
              <span>!</span>
              {error}
            </div>
          )}

          <form
            className="register-form"
            onSubmit={handleSubmit}
          >
            <div className="form-row">
              <div className="form-field">
                <label htmlFor="firstName">
                  First name
                </label>

                <input
                  id="firstName"
                  type="text"
                  value={firstName}
                  onChange={(event) =>
                    setFirstName(event.target.value)
                  }
                  placeholder="John"
                  autoComplete="given-name"
                />
              </div>

              <div className="form-field">
                <label htmlFor="lastName">
                  Last name
                </label>

                <input
                  id="lastName"
                  type="text"
                  value={lastName}
                  onChange={(event) =>
                    setLastName(event.target.value)
                  }
                  placeholder="Doe"
                  autoComplete="family-name"
                />
              </div>
            </div>

            <div className="form-field">
              <label htmlFor="email">
                Email address
              </label>

              <input
                id="email"
                type="email"
                value={email}
                onChange={(event) =>
                  setEmail(event.target.value)
                }
                placeholder="you@example.com"
                autoComplete="email"
                required
              />
            </div>

            {!isInvitationRegistration && (
              <div className="form-field">
                <label htmlFor="organizationName">
                  Organization name
                </label>

                <input
                  id="organizationName"
                  type="text"
                  value={organizationName}
                  onChange={(event) =>
                    setOrganizationName(
                      event.target.value,
                    )
                  }
                  placeholder="Acme Inc."
                  autoComplete="organization"
                />

                <span className="field-hint">
                  You can skip this when joining an
                  organization by invitation.
                </span>
              </div>
            )}

            <div className="form-row">
              <div className="form-field">
                <label htmlFor="password">
                  Password
                </label>

                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(event) =>
                    setPassword(event.target.value)
                  }
                  placeholder="••••••••"
                  autoComplete="new-password"
                  required
                />

                <span className="field-hint">
                  Minimum 8 characters.
                </span>
              </div>

              <div className="form-field">
                <label htmlFor="confirmPassword">
                  Confirm password
                </label>

                <input
                  id="confirmPassword"
                  type="password"
                  value={confirmPassword}
                  onChange={(event) =>
                    setConfirmPassword(
                      event.target.value,
                    )
                  }
                  placeholder="••••••••"
                  autoComplete="new-password"
                  required
                />
              </div>
            </div>

            {!isInvitationRegistration && (
              <details className="invitation-details">
                <summary>
                  Have an invitation token?
                </summary>

                <div className="form-field">
                  <label htmlFor="invitationToken">
                    Invitation token
                  </label>

                  <input
                    id="invitationToken"
                    type="text"
                    value={invitationToken}
                    onChange={(event) =>
                      setInvitationToken(
                        event.target.value,
                      )
                    }
                    placeholder="Paste your invitation token"
                  />
                </div>
              </details>
            )}

            <button
              type="submit"
              className="register-button"
              disabled={isSubmitting}
            >
              {isSubmitting
                ? "Creating account..."
                : isInvitationRegistration
                  ? "Join organization"
                  : "Create account"}
            </button>
          </form>

          <div className="login-link">
            Already have an account?{" "}
            <Link to="/login">Sign in</Link>
          </div>
        </section>
      </main>

      <style>{`
        * {
          box-sizing: border-box;
        }

        .register-page {
          min-height: 100vh;
          position: relative;
          overflow: hidden;
          background:
            radial-gradient(
              circle at 20% 20%,
              rgba(99, 102, 241, 0.14),
              transparent 32%
            ),
            radial-gradient(
              circle at 80% 80%,
              rgba(124, 58, 237, 0.10),
              transparent 32%
            ),
            #090a10;
          color: #f8fafc;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 48px 20px;
        }

        .register-background {
          position: absolute;
          inset: 0;
          pointer-events: none;
          background-image:
            linear-gradient(
              rgba(255,255,255,0.018) 1px,
              transparent 1px
            ),
            linear-gradient(
              90deg,
              rgba(255,255,255,0.018) 1px,
              transparent 1px
            );
          background-size: 48px 48px;
          mask-image: linear-gradient(
            to bottom,
            black,
            transparent
          );
        }

        .register-container {
          position: relative;
          z-index: 1;
          width: 100%;
          max-width: 620px;
        }

        .register-card {
          background: rgba(16, 18, 27, 0.94);
          border: 1px solid rgba(148, 163, 184, 0.14);
          border-radius: 24px;
          padding: 38px;
          box-shadow:
            0 30px 80px rgba(0, 0, 0, 0.45),
            0 0 50px rgba(99, 102, 241, 0.07);
          backdrop-filter: blur(20px);
        }

        .register-brand {
          display: flex;
          align-items: center;
          gap: 12px;
          margin-bottom: 34px;
        }

        .brand-icon {
          width: 46px;
          height: 46px;
          border-radius: 13px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: linear-gradient(
            135deg,
            #6366f1,
            #8b5cf6
          );
          font-size: 22px;
          font-weight: 800;
          box-shadow:
            0 12px 28px rgba(99, 102, 241, 0.3);
        }

        .brand-name {
          font-size: 17px;
          font-weight: 800;
        }

        .brand-subtitle {
          margin-top: 2px;
          color: #64748b;
          font-size: 10px;
          letter-spacing: 0.13em;
          font-weight: 700;
        }

        .register-header {
          margin-bottom: 26px;
        }

        .eyebrow {
          color: #818cf8;
          font-size: 12px;
          font-weight: 800;
          letter-spacing: 0.12em;
          margin-bottom: 9px;
        }

        .register-header h1 {
          margin: 0;
          font-size: 32px;
          line-height: 1.15;
          letter-spacing: -0.03em;
        }

        .register-header p {
          margin: 10px 0 0;
          color: #64748b;
          font-size: 15px;
          line-height: 1.6;
        }

        .invitation-banner {
          display: flex;
          gap: 12px;
          align-items: flex-start;
          padding: 14px 16px;
          margin-bottom: 20px;
          border-radius: 12px;
          background: rgba(99, 102, 241, 0.10);
          border: 1px solid rgba(99, 102, 241, 0.20);
        }

        .banner-icon {
          width: 24px;
          height: 24px;
          flex-shrink: 0;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          background: #6366f1;
          font-size: 13px;
          font-weight: 800;
        }

        .invitation-banner strong {
          font-size: 13px;
        }

        .invitation-banner p {
          margin: 3px 0 0;
          color: #94a3b8;
          font-size: 12px;
          line-height: 1.5;
        }

        .error-message {
          display: flex;
          gap: 9px;
          align-items: center;
          padding: 13px 15px;
          margin-bottom: 20px;
          border-radius: 11px;
          color: #fecaca;
          background: rgba(239, 68, 68, 0.09);
          border: 1px solid rgba(239, 68, 68, 0.20);
          font-size: 13px;
        }

        .error-message span {
          width: 20px;
          height: 20px;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
          border-radius: 50%;
          background: rgba(239, 68, 68, 0.18);
          font-weight: 800;
        }

        .register-form {
          display: flex;
          flex-direction: column;
          gap: 18px;
        }

        .form-row {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 15px;
        }

        .form-field {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .form-field label {
          color: #cbd5e1;
          font-size: 13px;
          font-weight: 700;
        }

        .form-field input {
          width: 100%;
          height: 48px;
          padding: 0 14px;
          border-radius: 11px;
          border: 1px solid #252a3a;
          outline: none;
          background: #151822;
          color: #f8fafc;
          font-size: 14px;
          transition:
            border-color 0.2s ease,
            box-shadow 0.2s ease,
            background 0.2s ease;
        }

        .form-field input::placeholder {
          color: #475569;
        }

        .form-field input:focus {
          border-color: #6366f1;
          background: #171a26;
          box-shadow:
            0 0 0 3px rgba(99, 102, 241, 0.11);
        }

        .field-hint {
          color: #64748b;
          font-size: 11px;
          line-height: 1.4;
        }

        .invitation-details {
          border-top: 1px solid #202432;
          padding-top: 17px;
        }

        .invitation-details summary {
          cursor: pointer;
          color: #818cf8;
          font-size: 13px;
          font-weight: 700;
          margin-bottom: 15px;
        }

        .register-button {
          width: 100%;
          height: 50px;
          margin-top: 3px;
          border: 0;
          border-radius: 11px;
          cursor: pointer;
          color: white;
          font-size: 14px;
          font-weight: 800;
          background: linear-gradient(
            135deg,
            #6366f1,
            #7c3aed
          );
          box-shadow:
            0 12px 28px rgba(99, 102, 241, 0.24);
          transition:
            transform 0.2s ease,
            box-shadow 0.2s ease,
            opacity 0.2s ease;
        }

        .register-button:hover:not(:disabled) {
          transform: translateY(-1px);
          box-shadow:
            0 16px 34px rgba(99, 102, 241, 0.32);
        }

        .register-button:disabled {
          cursor: not-allowed;
          opacity: 0.55;
        }

        .login-link {
          margin-top: 24px;
          text-align: center;
          color: #64748b;
          font-size: 13px;
        }

        .login-link a {
          color: #818cf8;
          text-decoration: none;
          font-weight: 700;
        }

        .login-link a:hover {
          color: #a5b4fc;
        }

        @media (max-width: 600px) {
          .register-page {
            padding: 20px 12px;
          }

          .register-card {
            padding: 26px 20px;
            border-radius: 18px;
          }

          .register-header h1 {
            font-size: 27px;
          }

          .form-row {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  );
}

export default Register;