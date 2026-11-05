import { useEffect, useRef, useState } from "react";
import { useOrganization } from "../context/OrganizationContext";

function IconBuilding({ size = 20 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M4 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16" />
      <path d="M2 21h20" />
      <path d="M8 7h2" />
      <path d="M8 11h2" />
      <path d="M8 15h2" />
      <path d="M16 9h4v12" />
      <path d="M16 13h2" />
      <path d="M16 17h2" />
    </svg>
  );
}

function IconChevron({ open }: { open: boolean }) {
  return (
    <svg
      width="17"
      height="17"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{
        transform: open ? "rotate(180deg)" : "rotate(0deg)",
        transition: "transform 0.2s ease",
      }}
    >
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

function IconCheck({ size = 19 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="m5 12 4 4L19 6" />
    </svg>
  );
}

function IconPlus({ size = 17 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </svg>
  );
}

export default function WorkspaceSwitcher() {
  const {
    organizations,
    activeOrganization,
    setActiveOrganization,
  } = useOrganization();

  const [open, setOpen] = useState(false);

  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        wrapperRef.current &&
        !wrapperRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const handleSelect = (organizationId: string) => {
    setActiveOrganization(organizationId);
    setOpen(false);
  };

  return (
    <div ref={wrapperRef} className="workspace-switcher">
      <style>{`
        .workspace-switcher {
          position: relative;
          width: 100%;
          min-width: 0;
          z-index: 200;
        }

        .workspace-trigger {
          width: 100%;
          min-height: 68px;
          padding: 10px 12px;
          border-radius: 14px;
          border: 1px solid rgba(148, 163, 184, 0.13);
          background:
            linear-gradient(
              145deg,
              rgba(255, 255, 255, 0.045),
              rgba(255, 255, 255, 0.018)
            );
          color: #f8fafc;
          display: flex;
          align-items: center;
          gap: 11px;
          cursor: pointer;
          text-align: left;
          transition:
            border-color 0.2s ease,
            background 0.2s ease,
            box-shadow 0.2s ease;
        }

        .workspace-trigger:hover,
        .workspace-trigger.open {
          border-color: rgba(129, 140, 248, 0.55);
          background:
            linear-gradient(
              145deg,
              rgba(99, 102, 241, 0.10),
              rgba(255, 255, 255, 0.025)
            );
          box-shadow: 0 8px 25px rgba(0, 0, 0, 0.16);
        }

        .workspace-icon {
          width: 43px;
          height: 43px;
          flex-shrink: 0;
          border-radius: 12px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: #c7d2fe;
          background: linear-gradient(
            135deg,
            #6366f1,
            #8b5cf6
          );
          box-shadow:
            0 8px 20px rgba(99, 102, 241, 0.24),
            inset 0 1px rgba(255, 255, 255, 0.22);
        }

        .workspace-copy {
          min-width: 0;
          flex: 1;
        }

        .workspace-caption {
          color: #64748b;
          font-size: 10px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 1px;
          line-height: 1;
          margin-bottom: 7px;
        }

        .workspace-name {
          color: #f8fafc;
          font-size: 13px;
          font-weight: 700;
          line-height: 1.2;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .workspace-chevron {
          color: #94a3b8;
          width: 22px;
          height: 22px;
          flex-shrink: 0;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .workspace-dropdown {
          position: absolute;
          top: calc(100% + 9px);
          left: 0;
          width: 100%;
          min-width: 250px;
          padding: 7px;
          border-radius: 14px;
          background: #141620;
          border: 1px solid rgba(148, 163, 184, 0.17);
          box-shadow:
            0 25px 70px rgba(0, 0, 0, 0.45),
            0 8px 25px rgba(0, 0, 0, 0.25);
          backdrop-filter: blur(18px);
          animation: workspaceDropdownIn 0.16s ease-out;
          z-index: 999;
        }

        @keyframes workspaceDropdownIn {
          from {
            opacity: 0;
            transform: translateY(-5px);
          }

          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .workspace-dropdown-title {
          padding: 10px 11px 9px;
          color: #64748b;
          font-size: 10px;
          font-weight: 750;
          text-transform: uppercase;
          letter-spacing: 1px;
        }

        .workspace-list {
          display: flex;
          flex-direction: column;
          gap: 3px;
        }

        .workspace-option {
          width: 100%;
          border: 0;
          border-radius: 10px;
          background: transparent;
          color: #cbd5e1;
          padding: 10px;
          display: flex;
          align-items: center;
          gap: 10px;
          cursor: pointer;
          text-align: left;
          transition:
            background 0.18s ease,
            color 0.18s ease;
        }

        .workspace-option:hover {
          background: rgba(99, 102, 241, 0.09);
          color: #f8fafc;
        }

        .workspace-option.active {
          background: rgba(99, 102, 241, 0.13);
        }

        .workspace-option-icon {
          width: 38px;
          height: 38px;
          flex-shrink: 0;
          border-radius: 10px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: #a5b4fc;
          background: rgba(99, 102, 241, 0.13);
          border: 1px solid rgba(129, 140, 248, 0.12);
        }

        .workspace-option-copy {
          min-width: 0;
          flex: 1;
        }

        .workspace-option-name {
          color: #f1f5f9;
          font-size: 12px;
          font-weight: 700;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .workspace-option-role {
          color: #64748b;
          font-size: 10px;
          font-weight: 600;
          margin-top: 3px;
          text-transform: uppercase;
        }

        .workspace-option-check {
          color: #818cf8;
          width: 22px;
          height: 22px;
          flex-shrink: 0;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .workspace-divider {
          height: 1px;
          margin: 6px 4px;
          background: rgba(148, 163, 184, 0.09);
        }

        .workspace-add {
          width: 100%;
          border: 0;
          background: transparent;
          color: #818cf8;
          padding: 9px 10px;
          border-radius: 9px;
          display: flex;
          align-items: center;
          gap: 9px;
          cursor: pointer;
          font-size: 11px;
          font-weight: 650;
          text-align: left;
        }

        .workspace-add:hover {
          background: rgba(99, 102, 241, 0.08);
          color: #a5b4fc;
        }

        .workspace-empty {
          padding: 14px 11px;
          color: #64748b;
          font-size: 11px;
        }

        /*
         * Sidebar:
         * Keep the dropdown inside the sidebar instead of allowing
         * it to overflow from the left side of the screen.
         */
        
        .sidebar .workspace-switcher {
        width: calc(100% + 24px);
        margin-left: -24px;
        }

        /*
         * Topbar:
         * Give the topbar version a slightly wider dropdown.
         */
        .topbar .workspace-switcher {
          width: 310px;
          flex-shrink: 0;
        }

        .topbar .workspace-dropdown {
          width: 100%;
        }

        @media (max-width: 800px) {
          .topbar .workspace-switcher {
            width: 240px;
          }
        }

        @media (max-width: 600px) {
          .topbar .workspace-switcher {
            width: 210px;
          }

          .workspace-trigger {
            min-height: 58px;
            padding: 8px 10px;
          }

          .workspace-icon {
            width: 38px;
            height: 38px;
          }

          .workspace-caption {
            font-size: 9px;
          }

          .workspace-name {
            font-size: 12px;
          }
        }
      `}</style>

      <button
        type="button"
        className={`workspace-trigger ${open ? "open" : ""}`}
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-haspopup="listbox"
      >
        <div className="workspace-icon">
          <IconBuilding size={21} />
        </div>

        <div className="workspace-copy">
          <div className="workspace-caption">
            Workspace
          </div>

          <div className="workspace-name">
            {activeOrganization?.name || "No workspace"}
          </div>
        </div>

        <div className="workspace-chevron">
          <IconChevron open={open} />
        </div>
      </button>

      {open && (
        <div
          className="workspace-dropdown"
          role="listbox"
          aria-label="Workspaces"
        >
          <div className="workspace-dropdown-title">
            Your workspaces
          </div>

          <div className="workspace-list">
            {organizations.length > 0 ? (
              organizations.map((organization) => {
                const isActive =
                  organization.id === activeOrganization?.id;

                return (
                  <button
                    key={organization.id}
                    type="button"
                    className={`workspace-option ${
                      isActive ? "active" : ""
                    }`}
                    onClick={() =>
                      handleSelect(organization.id)
                    }
                    role="option"
                    aria-selected={isActive}
                  >
                    <div className="workspace-option-icon">
                      <IconBuilding size={18} />
                    </div>

                    <div className="workspace-option-copy">
                      <div className="workspace-option-name">
                        {organization.name}
                      </div>

                      <div className="workspace-option-role">
                        {organization.role}
                      </div>
                    </div>

                    {isActive && (
                      <div className="workspace-option-check">
                        <IconCheck />
                      </div>
                    )}
                  </button>
                );
              })
            ) : (
              <div className="workspace-empty">
                No workspaces available.
              </div>
            )}
          </div>

          <div className="workspace-divider" />

          <button
            type="button"
            className="workspace-add"
            onClick={() => {
              setOpen(false);
              // Organization creation can be connected later.
            }}
          >
            <IconPlus size={16} />
            Add workspace
          </button>
        </div>
      )}
    </div>
  );
}