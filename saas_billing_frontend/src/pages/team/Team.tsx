import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  RefreshCw,
  Search,
  UserPlus,
  Shield,
  X,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../../context/AuthContext";
import { useOrganization } from "../../context/OrganizationContext";
import {
  getTeamMembers,
  inviteTeamMember,
  removeTeamMember,
  updateTeamMember,
} from "../../api/tenants";

import type {
  InviteMemberData,
  MemberRole,
  TeamMember,
} from "../../api/tenants";

function Team() {

    const navigate = useNavigate();
    const { user } = useAuth();
    const { activeOrganization } = useOrganization();

    const organizationId = activeOrganization?.id ?? null;
    const currentRole = activeOrganization?.role as MemberRole | undefined;

  const [members, setMembers] = useState<TeamMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");

  const [showInvite, setShowInvite] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] =
    useState<Exclude<MemberRole, "OWNER">>("MEMBER");
  const [inviting, setInviting] = useState(false);
  const [inviteMessage, setInviteMessage] = useState("");

  const canManageTeam =
    currentRole === "OWNER" || currentRole === "ADMIN";

  const loadMembers = async () => {
    if (!organizationId) {
      setMembers([]);
      setLoading(false);
      return;
    }

    // The members API is OWNER/ADMIN only; don't call it just to
    // show other roles a "Failed to load" error.
    if (!canManageTeam) {
      setMembers([]);
      setError("");
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError("");

      const data = await getTeamMembers(organizationId);
      setMembers(data);
    } catch (err) {
      console.error("Failed to load team members:", err);
      setError("Failed to load team members.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadMembers();
  }, [organizationId, canManageTeam]);

  const filteredMembers = useMemo(() => {
    const query = search.trim().toLowerCase();

    if (!query) {
      return members;
    }

    return members.filter((member) =>
      [
        member.first_name,
        member.last_name,
        member.email,
        member.role,
      ].some((value) =>
        String(value).toLowerCase().includes(query),
      ),
    );
  }, [members, search]);

const getInitials = (member: TeamMember) => {
    const first = member.first_name?.charAt(0) || "";
    const last = member.last_name?.charAt(0) || "";
    const emailInitial = member.email?.charAt(0) || "";

    return (
        `${first}${last}`.toUpperCase() ||
        emailInitial.toUpperCase() ||
        "U"
    );
};


const formatRole = (role: string) => {
    return role.charAt(0) + role.slice(1).toLowerCase();
};

const handleInvite = async () => {
    if (!organizationId || !inviteEmail.trim()) {
      return;
    }

    try {
      setInviting(true);
      setInviteMessage("");

      const data: InviteMemberData = {
        email: inviteEmail.trim(),
        role: inviteRole,
      };

      const response = await inviteTeamMember(
        organizationId,
        data,
      );

      setInviteMessage(
        response.message || "Invitation sent successfully.",
      );

      setInviteEmail("");
      setInviteRole("MEMBER");
    } catch (err: any) {
      console.error("Invitation failed:", err);

      const message =
        err?.response?.data?.detail ||
        "Failed to send invitation.";

      setInviteMessage(message);
    } finally {
      setInviting(false);
    }
  };

  const handleRoleChange = async (
    member: TeamMember,
    role: MemberRole,
  ) => {
    if (!organizationId || member.role === role) {
      return;
    }

    try {
      const updated = await updateTeamMember(
        organizationId,
        member.user_id,
        { role },
      );

      setMembers((current) =>
        current.map((item) =>
          item.user_id === updated.user_id
            ? updated
            : item,
        ),
      );
    } catch (err: any) {
      console.error("Failed to update member:", err);

      alert(
        err?.response?.data?.detail ||
          "Failed to update member role.",
      );
    }
  };

  const handleRemove = async (member: TeamMember) => {
    if (!organizationId) {
      return;
    }

    const confirmed = window.confirm(
      `Remove ${member.email} from this organization?`,
    );

    if (!confirmed) {
      return;
    }

    try {
      await removeTeamMember(
        organizationId,
        member.user_id,
      );

      setMembers((current) =>
        current.filter(
          (item) => item.user_id !== member.user_id,
        ),
      );
    } catch (err: any) {
      console.error("Failed to remove member:", err);

      alert(
        err?.response?.data?.detail ||
          "Failed to remove member.",
      );
    }
  };

  return (
    <div className="team-page">
      <style>{`
        .team-page {
          min-height: 100vh;
          background: #090a10;
          color: #f8fafc;
          padding: 32px;
        }

        .team-container {
          max-width: 1400px;
          margin: 0 auto;
        }

        .team-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 20px;
          margin-bottom: 28px;
        }

        .team-title-row {
          display: flex;
          align-items: center;
          gap: 14px;
        }

        .back-button {
          width: 42px;
          height: 42px;
          border: 1px solid #252735;
          background: #11131b;
          border-radius: 10px;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          color: #cbd5e1;
        }

        .back-button:hover {
          background: #181a25;
        }

        .team-title {
          margin: 0;
          font-size: 28px;
          font-weight: 700;
        }

        .team-subtitle {
          margin: 5px 0 0;
          color: #7f8aa3;
          font-size: 14px;
        }

        .invite-button {
          height: 44px;
          padding: 0 18px;
          border: none;
          border-radius: 10px;
          background: linear-gradient(
            135deg,
            #6366f1,
            #7c3aed
          );
          color: white;
          font-weight: 700;
          display: flex;
          align-items: center;
          gap: 8px;
          cursor: pointer;
          box-shadow: 0 8px 25px rgba(99,102,241,.22);
        }

        .invite-button:hover {
          opacity: .92;
        }

        .team-toolbar {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 16px;
          margin-bottom: 18px;
        }

        .search-wrapper {
          position: relative;
          width: 320px;
        }

        .search-icon {
          position: absolute;
          left: 13px;
          top: 50%;
          transform: translateY(-50%);
          color: #64748b;
        }

        .search-input {
          width: 100%;
          height: 42px;
          box-sizing: border-box;
          padding: 0 14px 0 40px;
          border: 1px solid #252735;
          border-radius: 10px;
          background: #11131b;
          color: white;
          outline: none;
        }

        .search-input:focus {
          border-color: #6366f1;
        }

        .refresh-button {
          height: 42px;
          padding: 0 14px;
          border: 1px solid #252735;
          border-radius: 10px;
          background: #11131b;
          color: #cbd5e1;
          display: flex;
          align-items: center;
          gap: 8px;
          cursor: pointer;
        }

        .refresh-button:hover {
          background: #181a25;
        }

        .team-card {
          background: #101219;
          border: 1px solid #242632;
          border-radius: 14px;
          overflow: hidden;
        }

        .team-table-wrapper {
          overflow-x: auto;
        }

        .team-table {
          width: 100%;
          border-collapse: collapse;
          min-width: 850px;
        }

        .team-table th {
          text-align: left;
          padding: 15px 20px;
          background: #12141d;
          border-bottom: 1px solid #242632;
          color: #7f8aa3;
          font-size: 12px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: .04em;
        }

        .team-table td {
          padding: 17px 20px;
          border-bottom: 1px solid #1d202b;
          font-size: 14px;
          vertical-align: middle;
        }

        .team-table tr:last-child td {
          border-bottom: none;
        }

        .member-cell {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .avatar {
          width: 38px;
          height: 38px;
          border-radius: 10px;
          background: linear-gradient(
            135deg,
            #6366f1,
            #8b5cf6
          );
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 13px;
          font-weight: 800;
          color: white;
        }

        .member-name {
          font-weight: 600;
          color: #f8fafc;
        }

        .member-email {
          color: #64748b;
          font-size: 13px;
          margin-top: 2px;
        }

        .role-select {
          height: 36px;
          padding: 0 10px;
          border: 1px solid #2a2d3a;
          border-radius: 8px;
          background: #171923;
          color: #cbd5e1;
          outline: none;
        }

        .role-select:focus {
          border-color: #6366f1;
        }

        .owner-role {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          color: #c4b5fd;
          font-weight: 600;
        }

        .status {
          display: inline-flex;
          padding: 5px 9px;
          border-radius: 7px;
          font-size: 12px;
          font-weight: 700;
        }

        .status-active {
          background: rgba(16,185,129,.12);
          color: #34d399;
        }

        .status-inactive {
          background: rgba(148,163,184,.12);
          color: #94a3b8;
        }

        .remove-button {
          height: 34px;
          padding: 0 11px;
          border: 1px solid rgba(239,68,68,.25);
          border-radius: 8px;
          background: rgba(239,68,68,.07);
          color: #f87171;
          cursor: pointer;
        }

        .remove-button:hover {
          background: rgba(239,68,68,.13);
        }

        .empty-state,
        .loading-state,
        .error-state {
          padding: 55px 20px;
          text-align: center;
          color: #64748b;
        }

        .error-state {
          color: #f87171;
        }

        .modal-overlay {
          position: fixed;
          inset: 0;
          background: rgba(0,0,0,.65);
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 20px;
          z-index: 1000;
        }

        .modal {
          width: 100%;
          max-width: 500px;
          background: #11131b;
          border: 1px solid #292c39;
          border-radius: 16px;
          padding: 24px;
          box-shadow: 0 25px 80px rgba(0,0,0,.45);
        }

        .modal-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 22px;
        }

        .modal-title {
          margin: 0;
          font-size: 21px;
        }

        .modal-subtitle {
          margin: 5px 0 0;
          color: #7f8aa3;
          font-size: 13px;
        }

        .close-button {
          width: 34px;
          height: 34px;
          border: none;
          border-radius: 8px;
          background: #191b25;
          color: #94a3b8;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .form-group {
          margin-bottom: 17px;
        }

        .form-label {
          display: block;
          margin-bottom: 7px;
          color: #cbd5e1;
          font-size: 13px;
          font-weight: 600;
        }

        .form-input,
        .form-select {
          width: 100%;
          height: 44px;
          box-sizing: border-box;
          padding: 0 12px;
          border: 1px solid #292c39;
          border-radius: 9px;
          background: #181a24;
          color: white;
          outline: none;
        }

        .form-input:focus,
        .form-select:focus {
          border-color: #6366f1;
        }

        .invite-message {
          margin: 12px 0;
          padding: 10px 12px;
          border-radius: 8px;
          background: rgba(99,102,241,.10);
          color: #a5b4fc;
          font-size: 13px;
        }

        .modal-footer {
          display: flex;
          justify-content: flex-end;
          gap: 10px;
          margin-top: 22px;
        }

        .cancel-button {
          height: 42px;
          padding: 0 16px;
          border: 1px solid #292c39;
          border-radius: 9px;
          background: #181a24;
          color: #cbd5e1;
          cursor: pointer;
        }

        .submit-button {
          height: 42px;
          padding: 0 18px;
          border: none;
          border-radius: 9px;
          background: #6366f1;
          color: white;
          font-weight: 700;
          cursor: pointer;
        }

        .submit-button:disabled {
          opacity: .5;
          cursor: not-allowed;
        }

        @media (max-width: 700px) {
          .team-page {
            padding: 20px;
          }

          .team-header {
            align-items: flex-start;
            flex-direction: column;
          }

          .team-toolbar {
            align-items: stretch;
            flex-direction: column;
          }

          .search-wrapper {
            width: 100%;
          }
        }
      `}</style>

      <div className="team-container">
        <div className="team-header">
          <div className="team-title-row">
            <button
              className="back-button"
              onClick={() => navigate("/dashboard")}
              title="Back to Dashboard"
            >
              <ArrowLeft size={19} />
            </button>

            <div>
              <h1 className="team-title">
                Team
              </h1>

              <p className="team-subtitle">
                Manage your organization members and roles.
              </p>
            </div>
          </div>

          {canManageTeam && (
            <button
              className="invite-button"
              onClick={() => {
                setInviteMessage("");
                setShowInvite(true);
              }}
            >
              <UserPlus size={17} />
              Invite Member
            </button>
          )}
        </div>

        <div className="team-toolbar">
          <div className="search-wrapper">
            <Search
              size={17}
              className="search-icon"
            />

            <input
              className="search-input"
              placeholder="Search members..."
              value={search}
              onChange={(event) =>
                setSearch(event.target.value)
              }
            />
          </div>

          <button
            className="refresh-button"
            onClick={loadMembers}
            disabled={loading}
          >
            <RefreshCw size={16} />
            Refresh
          </button>
        </div>

        <div className="team-card">
          {!canManageTeam ? (
            <div className="empty-state">
              Only owners and admins can view and manage the team.
            </div>
          ) : loading ? (
            <div className="loading-state">
              Loading team members...
            </div>
          ) : error ? (
            <div className="error-state">
              {error}
            </div>
          ) : filteredMembers.length === 0 ? (
            <div className="empty-state">
              No team members found.
            </div>
          ) : (
            <div className="team-table-wrapper">
              <table className="team-table">
                <thead>
                  <tr>
                    <th>Member</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Joined</th>
                    {canManageTeam && (
                      <th>Actions</th>
                    )}
                  </tr>
                </thead>

                <tbody>
                  {filteredMembers.map((member) => {
                    const isOwner =
                      member.role === "OWNER";

                    const canModify =
                      canManageTeam &&
                      !isOwner &&
                      member.user_id !==
                        user?.id;

                    return (
                      <tr key={member.user_id}>
                        <td>
                          <div className="member-cell">
                            <div className="avatar">
                              {getInitials(member)}
                            </div>

                            <div>
                                <div className="member-name">
                                {`${member.first_name} ${member.last_name}`.trim() ||
                                    member.email.split("@")[0]}
                                </div>

                              <div className="member-email">
                                {member.email}
                              </div>
                            </div>
                          </div>
                        </td>

                        <td>
                          {isOwner ? (
                            <span className="owner-role">
                              <Shield size={15} />
                              Owner
                            </span>
                          ) : canModify ? (
                            <select
                              className="role-select"
                              value={member.role}
                              onChange={(event) =>
                                handleRoleChange(
                                  member,
                                  event.target.value as MemberRole,
                                )
                              }
                            >
                              <option value="ADMIN">
                                Admin
                              </option>

                              <option value="ACCOUNTANT">
                                Accountant
                              </option>

                              <option value="MEMBER">
                                Member
                              </option>
                            </select>
                          ) : (
                            <span>
                              {formatRole(member.role)}
                            </span>
                          )}
                        </td>

                        <td>
                          <span
                            className={`status ${
                              member.is_active
                                ? "status-active"
                                : "status-inactive"
                            }`}
                          >
                            {member.is_active
                              ? "Active"
                              : "Inactive"}
                          </span>
                        </td>

                        <td>
                          {new Date(
                            member.joined_at,
                          ).toLocaleDateString()}
                        </td>

                        {canManageTeam && (
                          <td>
                            {canModify && (
                              <button
                                className="remove-button"
                                onClick={() =>
                                  handleRemove(member)
                                }
                              >
                                Remove
                              </button>
                            )}
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {showInvite && (
        <div
          className="modal-overlay"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setShowInvite(false);
            }
          }}
        >
          <div className="modal">
            <div className="modal-header">
              <div>
                <h2 className="modal-title">
                  Invite team member
                </h2>

                <p className="modal-subtitle">
                  Send an invitation to join this organization.
                </p>
              </div>

              <button
                className="close-button"
                onClick={() => setShowInvite(false)}
              >
                <X size={17} />
              </button>
            </div>

            <div className="form-group">
              <label className="form-label">
                Email address
              </label>

              <input
                className="form-input"
                type="email"
                placeholder="member@example.com"
                value={inviteEmail}
                onChange={(event) =>
                  setInviteEmail(event.target.value)
                }
              />
            </div>

            <div className="form-group">
              <label className="form-label">
                Role
              </label>

              <select
                className="form-select"
                value={inviteRole}
                onChange={(event) =>
                  setInviteRole(
                    event.target.value as Exclude<
                      MemberRole,
                      "OWNER"
                    >,
                  )
                }
              >
                <option value="MEMBER">
                  Member
                </option>

                <option value="ACCOUNTANT">
                  Accountant
                </option>

                <option value="ADMIN">
                  Admin
                </option>
              </select>
            </div>

            {inviteMessage && (
              <div className="invite-message">
                {inviteMessage}
              </div>
            )}

            <div className="modal-footer">
              <button
                className="cancel-button"
                onClick={() => setShowInvite(false)}
              >
                Cancel
              </button>

              <button
                className="submit-button"
                onClick={handleInvite}
                disabled={
                  inviting ||
                  !inviteEmail.trim()
                }
              >
                {inviting
                  ? "Sending..."
                  : "Send Invitation"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Team;