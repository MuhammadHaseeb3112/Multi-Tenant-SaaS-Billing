import { useCallback, useEffect, useMemo, useState } from "react";
import {
  RefreshCw,
  Search,
  UserPlus,
  Shield,
  X,
} from "lucide-react";

import { useAuth } from "../../context/AuthContext";
import { useOrganization } from "../../context/OrganizationContext";
import {
  getInvitations,
  getTeamMembers,
  inviteTeamMember,
  removeTeamMember,
  resendInvitation,
  revokeInvitation,
  updateTeamMember,
} from "../../api/tenants";

import type {
  Invitation,
  InviteMemberData,
  MemberRole,
  TeamMember,
} from "../../api/tenants";

function TeamPage() {

    const { user } = useAuth();
    const { activeOrganization } = useOrganization();

    const organizationId = activeOrganization?.id ?? null;
    const currentRole = activeOrganization?.role as MemberRole | undefined;

  const [members, setMembers] = useState<TeamMember[]>([]);
  // Only OWNER/ADMIN load the member list (see fetchMembers).
  const [loading, setLoading] = useState(
    organizationId !== null &&
      (currentRole === "OWNER" || currentRole === "ADMIN"),
  );
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");

  const [showInvite, setShowInvite] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] =
    useState<Exclude<MemberRole, "OWNER">>("MEMBER");
  const [inviting, setInviting] = useState(false);
  const [inviteMessage, setInviteMessage] = useState("");

  const canManageTeam =
    currentRole === "OWNER" || currentRole === "ADMIN";

  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [invitationsError, setInvitationsError] = useState("");
  const [busyInvitation, setBusyInvitation] = useState<string | null>(null);

  const fetchInvitations = useCallback(async () => {
    if (!organizationId || !canManageTeam) {
      return;
    }

    await getInvitations(organizationId)
      .then((data) => {
        setInvitations(data);
        setInvitationsError("");
      })
      .catch((err: unknown) => {
        console.error("Failed to load invitations:", err);
        setInvitationsError("Failed to load invitations.");
      });
  }, [organizationId, canManageTeam]);

  useEffect(() => {
    void fetchInvitations();
  }, [fetchInvitations]);

  const showNotice = (message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 5000);
  };

  const apiErrorMessage = (err: unknown, fallback: string) => {
    const data = (err as { response?: { data?: unknown } })?.response
      ?.data;

    if (data && typeof data === "object") {
      const detail = (data as { detail?: unknown }).detail;
      if (typeof detail === "string") return detail;

      const first = Object.values(data)
        .flat()
        .find((value) => typeof value === "string");
      if (typeof first === "string") return first;
    }

    return fallback;
  };

  const handleResend = async (invitation: Invitation) => {
    if (!organizationId) return;

    setBusyInvitation(invitation.id);

    try {
      await resendInvitation(organizationId, invitation.id);
      showNotice(`Invitation sent again to ${invitation.email}.`);
      await fetchInvitations();
    } catch (err) {
      alert(apiErrorMessage(err, "Failed to resend invitation."));
    } finally {
      setBusyInvitation(null);
    }
  };

  const handleRevoke = async (invitation: Invitation) => {
    if (!organizationId) return;

    const confirmed = window.confirm(
      `Cancel the invitation for ${invitation.email}? The link in their email will stop working.`,
    );

    if (!confirmed) return;

    setBusyInvitation(invitation.id);

    try {
      await revokeInvitation(organizationId, invitation.id);
      setInvitations((current) =>
        current.filter((item) => item.id !== invitation.id),
      );
      showNotice(`Invitation for ${invitation.email} was cancelled.`);
    } catch (err) {
      alert(apiErrorMessage(err, "Failed to cancel invitation."));
    } finally {
      setBusyInvitation(null);
    }
  };

  // Fetches and stores data; sets no state before the request, so it can
  // run straight from the mount effect. The members API is OWNER/ADMIN
  // only, so other roles never call it (they see a message instead).
  const fetchMembers = useCallback(async () => {
    if (!organizationId || !canManageTeam) {
      return;
    }

    await getTeamMembers(organizationId)
      .then((data) => {
        setMembers(data);
        setError("");
      })
      .catch((err: unknown) => {
        console.error("Failed to load team members:", err);
        setError("Failed to load team members.");
      })
      .finally(() => setLoading(false));
  }, [organizationId, canManageTeam]);

  useEffect(() => {
    void fetchMembers();
  }, [fetchMembers]);

  // Refresh button and after invite / role change / removal.
  const loadMembers = async () => {
    if (!organizationId || !canManageTeam) {
      return;
    }

    setLoading(true);
    setError("");

    await Promise.all([fetchMembers(), fetchInvitations()]);
  };

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

      // Close the form and confirm on the page itself.
      setInviteMessage("");
      setShowInvite(false);
      showNotice(
        `${response.message || "Invitation sent successfully."} (${data.email})`,
      );
      void fetchInvitations();

      setInviteEmail("");
      setInviteRole("MEMBER");
    } catch (err: any) {
      console.error("Invitation failed:", err);

      const data = err?.response?.data;
      const firstFieldError =
        data && typeof data === "object"
          ? Object.values(data).flat().find((v) => typeof v === "string")
          : undefined;

      const message =
        data?.detail ||
        (firstFieldError as string | undefined) ||
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
      showNotice(`${member.email} was removed from this organization.`);
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

        .team-notice {
          margin-bottom: 16px;
          padding: 12px 16px;
          border-radius: 12px;
          border: 1px solid rgba(34, 197, 94, 0.3);
          background: rgba(34, 197, 94, 0.1);
          color: #86efac;
          font-size: 14px;
          animation: team-notice-in 0.3s ease;
        }

        @keyframes team-notice-in {
          from { opacity: 0; transform: translateY(-6px); }
          to { opacity: 1; transform: none; }
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

        .remove-button:disabled,
        .resend-button:disabled {
          opacity: .5;
          cursor: not-allowed;
        }

        .invitations-section {
          margin-top: 28px;
        }

        .invitations-head {
          margin-bottom: 12px;
        }

        .invitations-head h2 {
          margin: 0;
          font-size: 18px;
          color: #f8fafc;
        }

        .invitations-head p {
          margin: 4px 0 0;
          color: #64748b;
          font-size: 13px;
        }

        .member-email-cell {
          color: #e2e8f0;
          font-weight: 600;
        }

        .invite-pending {
          background: rgba(245,158,11,.12);
          color: #fbbf24;
        }

        .invite-accepted {
          background: rgba(16,185,129,.12);
          color: #34d399;
        }

        .invite-expired {
          background: rgba(148,163,184,.12);
          color: #94a3b8;
        }

        .invite-actions {
          display: flex;
          gap: 8px;
        }

        .resend-button {
          height: 34px;
          padding: 0 11px;
          border: 1px solid rgba(99,102,241,.3);
          border-radius: 8px;
          background: rgba(99,102,241,.08);
          color: #a5b4fc;
          cursor: pointer;
        }

        .resend-button:hover {
          background: rgba(99,102,241,.15);
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

        {notice && (
          <div className="team-notice" role="status">
            {notice}
          </div>
        )}

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

        {canManageTeam && (
          <section className="invitations-section" aria-labelledby="invitations-title">
            <div className="invitations-head">
              <h2 id="invitations-title">Invitations</h2>
              <p>
                Everyone you invited and where their invitation stands.
                Links expire after 7 days.
              </p>
            </div>

            <div className="team-card">
              {invitationsError ? (
                <div className="error-state">{invitationsError}</div>
              ) : invitations.length === 0 ? (
                <div className="empty-state">
                  No invitations sent yet.
                </div>
              ) : (
                <div className="team-table-wrapper">
                  <table className="team-table">
                    <thead>
                      <tr>
                        <th>Email</th>
                        <th>Role</th>
                        <th>Status</th>
                        <th>Invited by</th>
                        <th>Sent</th>
                        <th>Expires</th>
                        <th>Actions</th>
                      </tr>
                    </thead>

                    <tbody>
                      {invitations.map((invitation) => {
                        const isAccepted =
                          invitation.status === "ACCEPTED";
                        const busy = busyInvitation === invitation.id;

                        return (
                          <tr key={invitation.id}>
                            <td className="member-email-cell">
                              {invitation.email}
                            </td>
                            <td>{formatRole(invitation.role)}</td>
                            <td>
                              <span
                                className={`status invite-${invitation.status.toLowerCase()}`}
                              >
                                {formatRole(invitation.status)}
                              </span>
                            </td>
                            <td>{invitation.invited_by || "—"}</td>
                            <td>
                              {new Date(
                                invitation.created_at,
                              ).toLocaleDateString()}
                            </td>
                            <td>
                              {isAccepted
                                ? "—"
                                : new Date(
                                    invitation.expires_at,
                                  ).toLocaleDateString()}
                            </td>
                            <td>
                              {!isAccepted && (
                                <div className="invite-actions">
                                  <button
                                    className="resend-button"
                                    disabled={busy}
                                    onClick={() =>
                                      void handleResend(invitation)
                                    }
                                  >
                                    Resend
                                  </button>
                                  <button
                                    className="remove-button"
                                    disabled={busy}
                                    onClick={() =>
                                      void handleRevoke(invitation)
                                    }
                                  >
                                    Cancel
                                  </button>
                                </div>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </section>
        )}
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

// Remount the page when the active organization changes, so every piece
// of state (loading flags, data, errors) starts fresh for the new org and
// a slow response for the previous org can never overwrite the new one.
function Team() {
  const { activeOrganization } = useOrganization();

  return <TeamPage key={activeOrganization?.id ?? "none"} />;
}

export default Team;