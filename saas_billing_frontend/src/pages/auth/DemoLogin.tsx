// Shown only in the public demo (VITE_DEMO_MODE=true): one click fills in
// a demo account for each role, so visitors can see role-based access.

export const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === "true";

const DEMO_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD || "DemoPass123!";

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
      <div className="demo-login-title">Live demo — pick an account</div>

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
        Stripe is in test mode: pay with card 4242 4242 4242 4242.
      </div>
    </div>
  );
}
