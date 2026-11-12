// Shown only in the public demo (VITE_DEMO_MODE=true): one click fills in
// a demo account for each role, so visitors can see role-based access.

export const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === "true";

const DEMO_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD || "DemoPass123!";

export const SOURCE_URL =
  "https://github.com/MuhammadHaseeb3112/Multi-Tenant-SaaS-Billing";

const ACCOUNTS = [
  { role: "Owner", email: "owner@demo.com", hint: "Full access" },
  { role: "Accountant", email: "accountant@demo.com", hint: "Invoices only" },
  { role: "Member", email: "member@demo.com", hint: "Read-only" },
];

interface DemoLoginProps {
  onPick: (email: string, password: string) => void;
  disabled?: boolean;
}

export default function DemoLogin({ onPick, disabled }: DemoLoginProps) {
  if (!DEMO_MODE) {
    return null;
  }

  return (
    <div className="demo-login" role="region" aria-label="Demo accounts">
      <div className="demo-login-badge">Portfolio demo · not a real company</div>

      <p className="demo-login-about">
        SaaS Billing is an open-source portfolio project by Muhammad Haseeb.
        All accounts are fake demo data and Stripe runs in test mode, so
        never enter real passwords or card details here.{" "}
        <a href={SOURCE_URL} target="_blank" rel="noopener noreferrer">
          View the source on GitHub
        </a>
        .
      </p>

      <div className="demo-login-title">Pick a demo account</div>

      <div className="demo-login-buttons">
        {ACCOUNTS.map((account) => (
          <button
            key={account.email}
            type="button"
            className="demo-login-button"
            disabled={disabled}
            onClick={() => onPick(account.email, DEMO_PASSWORD)}
          >
            <strong>{account.role}</strong>
            <span>{account.hint}</span>
          </button>
        ))}
      </div>

      <div className="demo-login-note">
        Password for every demo account: <code>{DEMO_PASSWORD}</code>. Test
        card: 4242 4242 4242 4242, any future date, any CVC.
      </div>
    </div>
  );
}
