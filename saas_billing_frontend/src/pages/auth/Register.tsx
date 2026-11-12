import {
  useEffect,
  useState,
  type FormEvent,
} from "react";

import {
  Link,
  useNavigate,
  useSearchParams,
} from "react-router-dom";

import {
  acceptInvitation,
  previewInvitation,
  type InvitationPreview,
} from "../../api/tenants";
import { useAuth } from "../../context/AuthContext";
import { useOrganization } from "../../context/OrganizationContext";

type InviteState =
  | { kind: "none" }
  | { kind: "loading" }
  | { kind: "invalid" }
  | { kind: "ready"; preview: InvitationPreview };

const ROLE_LABEL: Record<string, string> = {
  ADMIN: "Admin",
  ACCOUNTANT: "Accountant",
  MEMBER: "Member",
};

function Register() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const {
    register,
    user,
    isAuthenticated,
    isLoading: authLoading,
    logout,
    refreshUser,
  } = useAuth();
  const { selectNewOrganization } = useOrganization();

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

  // Invitation link: look up who it is for, so the email is fixed
  // to the invited address and the workspace is named.
  const [invite, setInvite] = useState<InviteState>(
    urlInvitationToken ? { kind: "loading" } : { kind: "none" },
  );

  useEffect(() => {
    if (!urlInvitationToken) {
      return;
    }

    let cancelled = false;

    previewInvitation(urlInvitationToken)
      .then((preview) => {
        if (cancelled) return;
        setInvite({ kind: "ready", preview });
        setEmail(preview.email);
      })
      .catch(() => {
        if (!cancelled) setInvite({ kind: "invalid" });
      });

    return () => {
      cancelled = true;
    };
  }, [urlInvitationToken]);

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

  const preview =
    invite.kind === "ready" ? invite.preview : null;

  const signedInAs = isAuthenticated ? user?.email ?? "" : "";

  // New person with a valid pending invitation: show the sign-up form
  // with the invited email locked. Everything else gets a panel.
  const showSignupForm =
    invite.kind === "none" ||
    (preview !== null &&
      preview.status === "PENDING" &&
      !preview.account_exists &&
      !authLoading &&
      !isAuthenticated);

  const handleAccept = () => {
    setError("");
    setIsSubmitting(true);

    acceptInvitation(urlInvitationToken)
      .then(async (result) => {
        selectNewOrganization(result.organization.id);
        await refreshUser();
        navigate("/dashboard", { replace: true });
      })
      .catch((err) => setError(getErrorMessage(err)))
      .finally(() => setIsSubmitting(false));
  };

  const renderInvitePanel = () => {
    if (invite.kind === "loading" || authLoading) {
      return (
        <div className="invite-panel">
          <p>Checking your invitation...</p>
        </div>
      );
    }

    if (invite.kind === "invalid") {
      return (
        <div className="invite-panel invite-panel-error">
          <strong>This invitation link is not valid.</strong>
          <p>
            It may have been revoked, or a newer invitation was sent.
            Ask the workspace admin to send it again.
          </p>
          <Link className="invite-panel-link" to="/login">
            Go to sign in
          </Link>
        </div>
      );
    }

    if (!preview) {
      return null;
    }

    if (preview.status === "ACCEPTED") {
      return (
        <div className="invite-panel">
          <strong>This invitation was already accepted.</strong>
          <p>Sign in with {preview.email} to open {preview.organization_name}.</p>
          <Link className="invite-panel-button" to="/login">
            Sign in
          </Link>
        </div>
      );
    }

    if (preview.status === "EXPIRED") {
      return (
        <div className="invite-panel invite-panel-error">
          <strong>This invitation has expired.</strong>
          <p>
            Ask {preview.invited_by || "the workspace admin"} to resend
            it from the Team page.
          </p>
        </div>
      );
    }

    if (isAuthenticated) {
      if (signedInAs.toLowerCase() === preview.email.toLowerCase()) {
        return (
          <div className="invite-panel">
            <p>
              You are signed in as <strong>{signedInAs}</strong>.
            </p>
            <button
              type="button"
              className="register-button"
              onClick={handleAccept}
              disabled={isSubmitting}
            >
              {isSubmitting
                ? "Joining..."
                : `Join ${preview.organization_name}`}
            </button>
          </div>
        );
      }

      return (
        <div className="invite-panel invite-panel-error">
          <strong>Different account.</strong>
          <p>
            You are signed in as {signedInAs}, but this invitation is
            for <strong>{preview.email}</strong>. Sign out, then open the
            link again.
          </p>
          <button
            type="button"
            className="invite-panel-button"
            onClick={() => void logout()}
          >
            Sign out
          </button>
        </div>
      );
    }

    if (preview.account_exists) {
      return (
        <div className="invite-panel">
          <p>
            <strong>{preview.email}</strong> already has an account.
            Sign in to accept the invitation.
          </p>
          <Link
            className="invite-panel-button"
            to={`/login?invite=${encodeURIComponent(urlInvitationToken)}`}
          >
            Sign in to accept
          </Link>
        </div>
      );
    }

    return null;
  };

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

          {preview && (
            <div className="invitation-banner">
              <span className="banner-icon">✓</span>

              <div>
                <strong>
                  Join {preview.organization_name} as{" "}
                  {ROLE_LABEL[preview.role] ?? preview.role}
                </strong>

                <p>
                  {preview.invited_by
                    ? `${preview.invited_by} invited ${preview.email}.`
                    : `Invitation for ${preview.email}.`}
                </p>
              </div>
            </div>
          )}

          {!showSignupForm && renderInvitePanel()}

          {error && (
            <div className="error-message">
              <span>!</span>
              {error}
            </div>
          )}

          {showSignupForm && (
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
                readOnly={preview !== null}
                aria-readonly={preview !== null}
                className={preview ? "input-locked" : undefined}
              />

              {preview && (
                <span className="field-hint">
                  The invitation is for this email, so it can't be
                  changed.
                </span>
              )}
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
          )}

          <div className="login-link">
            Already have an account?{" "}
            <Link to="/login">Sign in</Link>
          </div>
        </section>
      </main>

      <style>{`
        .invite-panel {
          margin-bottom: 20px;
          padding: 18px;
          border-radius: 14px;
          border: 1px solid rgba(99, 102, 241, 0.25);
          background: rgba(99, 102, 241, 0.08);
          color: #cbd5e1;
          display: grid;
          gap: 10px;
        }

        .invite-panel p {
          margin: 0;
          line-height: 1.5;
        }

        .invite-panel strong {
          color: #f8fafc;
        }

        .invite-panel-error {
          border-color: rgba(248, 113, 113, 0.3);
          background: rgba(248, 113, 113, 0.08);
        }

        .invite-panel-button {
          justify-self: start;
          display: inline-flex;
          align-items: center;
          height: 40px;
          padding: 0 18px;
          border: 0;
          border-radius: 10px;
          background: linear-gradient(135deg, #6366f1, #7c3aed);
          color: #ffffff;
          font-weight: 650;
          text-decoration: none;
          cursor: pointer;
        }

        .invite-panel-link {
          color: #a5b4fc;
          font-weight: 600;
        }

        .input-locked {
          opacity: 0.8;
          cursor: not-allowed;
        }

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