import { useMemo, useState } from "react";
import {
  ArrowLeft,
  Bell,
  Building2,
  Check,
  Lock,
  LogOut,
  Mail,
  Save,
  Shield,
  User,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { useOrganization } from "../../context/OrganizationContext";

export default function Settings() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  // Was the user's FIRST organization (wrong name/role after switching).
  const { activeOrganization: organization } = useOrganization();

  const [firstName, setFirstName] = useState(
    user?.first_name ?? "",
  );

  const [lastName, setLastName] = useState(
    user?.last_name ?? "",
  );

  const [email] = useState(user?.email ?? "");

  const [emailNotifications, setEmailNotifications] =
    useState(true);

  const [billingNotifications, setBillingNotifications] =
    useState(true);

  const [saved, setSaved] = useState(false);

  const initials = useMemo(() => {
    const first = firstName?.charAt(0) ?? "";
    const last = lastName?.charAt(0) ?? "";

    const value = `${first}${last}`.trim();

    if (value) {
      return value.toUpperCase();
    }

    return email?.charAt(0)?.toUpperCase() || "U";
  }, [firstName, lastName, email]);

  const handleSave = () => {
    // Profile update API can be connected here
    // when the backend profile-update endpoint is added.
    setSaved(true);

    window.setTimeout(() => {
      setSaved(false);
    }, 2500);
  };

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="settings-page">
      <style>{`
        .settings-page {
          min-height: 100vh;
          background:
            radial-gradient(
              circle at 85% 5%,
              rgba(99, 102, 241, 0.10),
              transparent 28%
            ),
            #080910;
          color: #f8fafc;
          padding: 42px 48px 80px;
          box-sizing: border-box;
        }

        .settings-container {
          max-width: 1180px;
          margin: 0 auto;
        }

        .settings-header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 24px;
          margin-bottom: 36px;
        }

        .settings-heading {
          display: flex;
          align-items: flex-start;
          gap: 18px;
        }

        .back-button {
          width: 56px;
          height: 56px;
          border: 1px solid #252938;
          background: #10121a;
          color: #dbe4f0;
          border-radius: 14px;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          transition: 0.2s ease;
          flex-shrink: 0;
        }

        .back-button:hover {
          background: #171a25;
          border-color: #3b4052;
          transform: translateX(-2px);
        }

        .settings-title {
          margin: 0;
          font-size: 36px;
          line-height: 1.1;
          font-weight: 800;
          letter-spacing: -0.8px;
        }

        .settings-subtitle {
          margin: 9px 0 0;
          color: #91a0b8;
          font-size: 16px;
        }

        .save-button {
          border: 0;
          min-height: 50px;
          padding: 0 20px;
          border-radius: 13px;
          background: linear-gradient(
            135deg,
            #6366f1,
            #7c3aed
          );
          color: white;
          font-size: 15px;
          font-weight: 700;
          display: flex;
          align-items: center;
          gap: 9px;
          cursor: pointer;
          box-shadow: 0 12px 30px rgba(99, 102, 241, 0.22);
          transition: 0.2s ease;
        }

        .save-button:hover {
          transform: translateY(-1px);
          box-shadow: 0 16px 35px rgba(99, 102, 241, 0.28);
        }

        .settings-grid {
          display: grid;
          grid-template-columns: 240px minmax(0, 1fr);
          gap: 24px;
          align-items: start;
        }

        .settings-sidebar {
          border: 1px solid #252938;
          background: #10121a;
          border-radius: 18px;
          padding: 10px;
          position: sticky;
          top: 24px;
        }

        .settings-nav-item {
          width: 100%;
          border: 0;
          background: transparent;
          color: #94a3b8;
          padding: 13px 14px;
          border-radius: 11px;
          display: flex;
          align-items: center;
          gap: 11px;
          text-align: left;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
        }

        .settings-nav-item.active {
          background: rgba(99, 102, 241, 0.14);
          color: #a5b4fc;
        }

        .settings-nav-item:hover {
          background: #171a24;
          color: #e2e8f0;
        }

        .settings-content {
          display: flex;
          flex-direction: column;
          gap: 20px;
        }

        .settings-card {
          background: #10121a;
          border: 1px solid #252938;
          border-radius: 18px;
          overflow: hidden;
        }

        .card-header {
          padding: 23px 26px 19px;
          border-bottom: 1px solid #252938;
        }

        .card-title-row {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .card-icon {
          width: 38px;
          height: 38px;
          border-radius: 10px;
          background: rgba(99, 102, 241, 0.13);
          color: #8b8ff8;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .card-title {
          margin: 0;
          font-size: 18px;
          font-weight: 750;
        }

        .card-description {
          margin: 7px 0 0;
          color: #8290a8;
          font-size: 14px;
        }

        .card-body {
          padding: 26px;
        }

        .profile-top {
          display: flex;
          align-items: center;
          gap: 17px;
          margin-bottom: 25px;
          padding-bottom: 22px;
          border-bottom: 1px solid #252938;
        }

        .avatar {
          width: 64px;
          height: 64px;
          border-radius: 16px;
          background: linear-gradient(
            135deg,
            #6366f1,
            #7c3aed
          );
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          font-size: 21px;
          font-weight: 800;
          box-shadow: 0 10px 25px rgba(99, 102, 241, 0.20);
        }

        .profile-name {
          font-size: 17px;
          font-weight: 750;
          color: #f8fafc;
        }

        .profile-email {
          margin-top: 4px;
          color: #8190a9;
          font-size: 14px;
        }

        .form-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 18px;
        }

        .form-group {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .form-group.full {
          grid-column: 1 / -1;
        }

        .form-label {
          color: #dbe3ef;
          font-size: 13px;
          font-weight: 650;
        }

        .form-input {
          width: 100%;
          box-sizing: border-box;
          min-height: 46px;
          padding: 0 14px;
          border: 1px solid #2a2e3d;
          border-radius: 11px;
          background: #171923;
          color: #f8fafc;
          outline: none;
          font-size: 14px;
          transition: 0.2s ease;
        }

        .form-input:focus {
          border-color: #6366f1;
          box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.10);
        }

        .form-input:disabled {
          color: #7f8ba0;
          cursor: not-allowed;
          background: #13151d;
        }

        .help-text {
          color: #69778d;
          font-size: 12px;
        }

        .organization-info {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 16px;
        }

        .info-box {
          border: 1px solid #272b39;
          background: #151720;
          border-radius: 13px;
          padding: 17px;
        }

        .info-label {
          color: #75839a;
          font-size: 12px;
          margin-bottom: 7px;
        }

        .info-value {
          color: #f1f5f9;
          font-size: 15px;
          font-weight: 650;
          word-break: break-word;
        }

        .security-row,
        .notification-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 20px;
          padding: 18px 0;
          border-bottom: 1px solid #252938;
        }

        .security-row:first-child,
        .notification-row:first-child {
          padding-top: 0;
        }

        .security-row:last-child,
        .notification-row:last-child {
          border-bottom: 0;
          padding-bottom: 0;
        }

        .row-left {
          display: flex;
          align-items: center;
          gap: 13px;
        }

        .row-icon {
          width: 38px;
          height: 38px;
          border-radius: 10px;
          background: #171a24;
          color: #9aa6bc;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
        }

        .row-title {
          color: #e8edf5;
          font-size: 14px;
          font-weight: 650;
        }

        .row-description {
          margin-top: 4px;
          color: #75839a;
          font-size: 12px;
        }

        .secondary-button {
          min-height: 42px;
          padding: 0 15px;
          border-radius: 10px;
          border: 1px solid #303545;
          background: #171923;
          color: #dbe3ef;
          font-weight: 650;
          cursor: pointer;
        }

        .secondary-button:hover {
          background: #1d202c;
        }

        .toggle {
          width: 46px;
          height: 26px;
          padding: 3px;
          border: 0;
          border-radius: 99px;
          background: #303442;
          cursor: pointer;
          transition: 0.2s ease;
          flex-shrink: 0;
        }

        .toggle.on {
          background: #6366f1;
        }

        .toggle-knob {
          width: 20px;
          height: 20px;
          border-radius: 50%;
          background: white;
          transition: 0.2s ease;
          transform: translateX(0);
        }

        .toggle.on .toggle-knob {
          transform: translateX(20px);
        }

        .danger-card {
          border-color: rgba(239, 68, 68, 0.25);
        }

        .danger-card .card-icon {
          background: rgba(239, 68, 68, 0.10);
          color: #f87171;
        }

        .logout-button {
          border: 1px solid rgba(239, 68, 68, 0.35);
          background: rgba(239, 68, 68, 0.07);
          color: #fca5a5;
          min-height: 42px;
          padding: 0 15px;
          border-radius: 10px;
          font-weight: 700;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .logout-button:hover {
          background: rgba(239, 68, 68, 0.13);
        }

        .saved-message {
          display: flex;
          align-items: center;
          gap: 7px;
          color: #34d399;
          font-size: 13px;
          font-weight: 650;
          margin-right: 12px;
        }

        .header-actions {
          display: flex;
          align-items: center;
        }

        @media (max-width: 900px) {
          .settings-page {
            padding: 28px 20px 60px;
          }

          .settings-grid {
            grid-template-columns: 1fr;
          }

          .settings-sidebar {
            position: static;
            display: flex;
            overflow-x: auto;
          }

          .settings-nav-item {
            white-space: nowrap;
          }
        }

        @media (max-width: 640px) {
          .settings-header {
            flex-direction: column;
          }

          .settings-title {
            font-size: 30px;
          }

          .header-actions {
            width: 100%;
          }

          .save-button {
            width: 100%;
            justify-content: center;
          }

          .form-grid,
          .organization-info {
            grid-template-columns: 1fr;
          }

          .form-group.full {
            grid-column: auto;
          }

          .card-body,
          .card-header {
            padding: 20px;
          }

          .security-row,
          .notification-row {
            align-items: flex-start;
          }
        }
      `}</style>

      <div className="settings-container">
        <header className="settings-header">
          <div className="settings-heading">
            <button
              type="button"
              className="back-button"
              onClick={() => navigate("/dashboard")}
              aria-label="Back to dashboard"
            >
              <ArrowLeft size={23} />
            </button>

            <div>
              <h1 className="settings-title">
                Settings
              </h1>

              <p className="settings-subtitle">
                Manage your profile, organization and
                notification preferences.
              </p>
            </div>
          </div>

          <div className="header-actions">
            {saved && (
              <span className="saved-message">
                <Check size={17} />
                Saved
              </span>
            )}

            <button
              type="button"
              className="save-button"
              onClick={handleSave}
            >
              <Save size={17} />
              Save Changes
            </button>
          </div>
        </header>

        <div className="settings-grid">
          <aside className="settings-sidebar">
            <button
              type="button"
              className="settings-nav-item active"
            >
              <User size={17} />
              Profile
            </button>

            <button
              type="button"
              className="settings-nav-item"
            >
              <Building2 size={17} />
              Organization
            </button>

            <button
              type="button"
              className="settings-nav-item"
            >
              <Shield size={17} />
              Security
            </button>

            <button
              type="button"
              className="settings-nav-item"
            >
              <Bell size={17} />
              Notifications
            </button>
          </aside>

          <main className="settings-content">
            {/* Profile */}
            <section className="settings-card">
              <div className="card-header">
                <div className="card-title-row">
                  <div className="card-icon">
                    <User size={19} />
                  </div>

                  <div>
                    <h2 className="card-title">
                      Profile
                    </h2>

                    <p className="card-description">
                      Update your personal information.
                    </p>
                  </div>
                </div>
              </div>

              <div className="card-body">
                <div className="profile-top">
                  <div className="avatar">
                    {initials}
                  </div>

                  <div>
                    <div className="profile-name">
                      {firstName || lastName
                        ? `${firstName} ${lastName}`.trim()
                        : email || "User"}
                    </div>

                    <div className="profile-email">
                      {email}
                    </div>
                  </div>
                </div>

                <div className="form-grid">
                  <div className="form-group">
                    <label
                      className="form-label"
                      htmlFor="first-name"
                    >
                      First name
                    </label>

                    <input
                      id="first-name"
                      className="form-input"
                      value={firstName}
                      onChange={(event) =>
                        setFirstName(event.target.value)
                      }
                      placeholder="First name"
                    />
                  </div>

                  <div className="form-group">
                    <label
                      className="form-label"
                      htmlFor="last-name"
                    >
                      Last name
                    </label>

                    <input
                      id="last-name"
                      className="form-input"
                      value={lastName}
                      onChange={(event) =>
                        setLastName(event.target.value)
                      }
                      placeholder="Last name"
                    />
                  </div>

                  <div className="form-group full">
                    <label
                      className="form-label"
                      htmlFor="email"
                    >
                      Email address
                    </label>

                    <input
                      id="email"
                      className="form-input"
                      value={email}
                      disabled
                      readOnly
                    />

                    <span className="help-text">
                      Email address is managed by your
                      account.
                    </span>
                  </div>
                </div>
              </div>
            </section>

            {/* Organization */}
            <section className="settings-card">
              <div className="card-header">
                <div className="card-title-row">
                  <div className="card-icon">
                    <Building2 size={19} />
                  </div>

                  <div>
                    <h2 className="card-title">
                      Organization
                    </h2>

                    <p className="card-description">
                      Information about your current
                      workspace.
                    </p>
                  </div>
                </div>
              </div>

              <div className="card-body">
                <div className="organization-info">
                  <div className="info-box">
                    <div className="info-label">
                      Organization name
                    </div>

                    <div className="info-value">
                      {organization?.name || "—"}
                    </div>
                  </div>

                  <div className="info-box">
                    <div className="info-label">
                      Workspace slug
                    </div>

                    <div className="info-value">
                      {organization?.slug || "—"}
                    </div>
                  </div>

                  <div className="info-box">
                    <div className="info-label">
                      Your role
                    </div>

                    <div className="info-value">
                      {organization?.role || "—"}
                    </div>
                  </div>

                  <div className="info-box">
                    <div className="info-label">
                      Organization ID
                    </div>

                    <div className="info-value">
                      {organization?.id || "—"}
                    </div>
                  </div>
                </div>
              </div>
            </section>

            {/* Security */}
            <section className="settings-card">
              <div className="card-header">
                <div className="card-title-row">
                  <div className="card-icon">
                    <Lock size={19} />
                  </div>

                  <div>
                    <h2 className="card-title">
                      Security
                    </h2>

                    <p className="card-description">
                      Manage account security settings.
                    </p>
                  </div>
                </div>
              </div>

              <div className="card-body">
                <div className="security-row">
                  <div className="row-left">
                    <div className="row-icon">
                      <Lock size={18} />
                    </div>

                    <div>
                      <div className="row-title">
                        Password
                      </div>

                      <div className="row-description">
                        Password management can be
                        connected to the backend endpoint.
                      </div>
                    </div>
                  </div>

                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() => {
                      // Password change endpoint can be
                      // connected when available.
                    }}
                  >
                    Change Password
                  </button>
                </div>

                <div className="security-row">
                  <div className="row-left">
                    <div className="row-icon">
                      <Shield size={18} />
                    </div>

                    <div>
                      <div className="row-title">
                        Authentication
                      </div>

                      <div className="row-description">
                        Your account is protected with JWT
                        authentication.
                      </div>
                    </div>
                  </div>

                  <span className="help-text">
                    JWT Enabled
                  </span>
                </div>
              </div>
            </section>

            {/* Notifications */}
            <section className="settings-card">
              <div className="card-header">
                <div className="card-title-row">
                  <div className="card-icon">
                    <Bell size={19} />
                  </div>

                  <div>
                    <h2 className="card-title">
                      Notifications
                    </h2>

                    <p className="card-description">
                      Choose which billing notifications
                      you want to receive.
                    </p>
                  </div>
                </div>
              </div>

              <div className="card-body">
                <div className="notification-row">
                  <div className="row-left">
                    <div className="row-icon">
                      <Mail size={18} />
                    </div>

                    <div>
                      <div className="row-title">
                        Email notifications
                      </div>

                      <div className="row-description">
                        Receive important organization
                        activity notifications by email.
                      </div>
                    </div>
                  </div>

                  <button
                    type="button"
                    className={`toggle ${
                      emailNotifications ? "on" : ""
                    }`}
                    onClick={() =>
                      setEmailNotifications(
                        (value) => !value,
                      )
                    }
                    aria-label="Toggle email notifications"
                  >
                    <div className="toggle-knob" />
                  </button>
                </div>

                <div className="notification-row">
                  <div className="row-left">
                    <div className="row-icon">
                      <Bell size={18} />
                    </div>

                    <div>
                      <div className="row-title">
                        Billing notifications
                      </div>

                      <div className="row-description">
                        Receive subscription, invoice and
                        payment updates.
                      </div>
                    </div>
                  </div>

                  <button
                    type="button"
                    className={`toggle ${
                      billingNotifications ? "on" : ""
                    }`}
                    onClick={() =>
                      setBillingNotifications(
                        (value) => !value,
                      )
                    }
                    aria-label="Toggle billing notifications"
                  >
                    <div className="toggle-knob" />
                  </button>
                </div>
              </div>
            </section>

            {/* Logout */}
            <section className="settings-card danger-card">
              <div className="card-header">
                <div className="card-title-row">
                  <div className="card-icon">
                    <LogOut size={19} />
                  </div>

                  <div>
                    <h2 className="card-title">
                      Account
                    </h2>

                    <p className="card-description">
                      Sign out from your current session.
                    </p>
                  </div>
                </div>
              </div>

              <div className="card-body">
                <div className="security-row">
                  <div>
                    <div className="row-title">
                      Sign out
                    </div>

                    <div className="row-description">
                      You will be returned to the login
                      page.
                    </div>
                  </div>

                  <button
                    type="button"
                    className="logout-button"
                    onClick={() => {
                      void handleLogout();
                    }}
                  >
                    <LogOut size={17} />
                    Logout
                  </button>
                </div>
              </div>
            </section>
          </main>
        </div>
      </div>
    </div>
  );
}