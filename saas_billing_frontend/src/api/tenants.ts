import apiClient from "./client";

export type MemberRole =
  | "OWNER"
  | "ADMIN"
  | "ACCOUNTANT"
  | "MEMBER";

export interface TeamMember {
  user_id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: MemberRole;
  is_active: boolean;
  joined_at: string;
}

export interface UpdateMemberData {
  role?: MemberRole;
  is_active?: boolean;
}

export interface InviteMemberData {
  email: string;
  role: Exclude<MemberRole, "OWNER">;
}

export type InvitationStatus = "PENDING" | "ACCEPTED" | "EXPIRED";

export interface Invitation {
  id: string;
  email: string;
  role: Exclude<MemberRole, "OWNER">;
  status: InvitationStatus;
  invited_by: string | null;
  created_at: string;
  expires_at: string;
  accepted_at: string | null;
  // Only returned by the server in DEBUG, for local testing.
  invitation_url?: string;
}

export interface InviteMemberResponse {
  message: string;
  invitation: Invitation;
}

export interface InvitationPreview {
  email: string;
  role: Exclude<MemberRole, "OWNER">;
  status: InvitationStatus;
  invited_by: string | null;
  organization_name: string;
  account_exists: boolean;
  expires_at: string;
}

export const getTeamMembers = async (
  organizationId: string,
): Promise<TeamMember[]> => {
  const response = await apiClient.get<TeamMember[]>(
    `/organizations/${organizationId}/members/`,
  );

  return response.data;
};

export const updateTeamMember = async (
  organizationId: string,
  userId: string,
  data: UpdateMemberData,
): Promise<TeamMember> => {
  const response = await apiClient.patch<TeamMember>(
    `/organizations/${organizationId}/members/${userId}/`,
    data,
  );

  return response.data;
};

export const removeTeamMember = async (
  organizationId: string,
  userId: string,
) => {
  const response = await apiClient.delete(
    `/organizations/${organizationId}/members/${userId}/`,
  );

  return response.data;
};

export const inviteTeamMember = async (
  organizationId: string,
  data: InviteMemberData,
): Promise<InviteMemberResponse> => {
  const response = await apiClient.post<InviteMemberResponse>(
    `/organizations/${organizationId}/invitations/`,
    data,
  );

  return response.data;
};

export interface CreateOrganizationData {
  name: string;
  billing_email?: string;
}

export interface CreatedOrganization {
  id: string;
  name: string;
  slug: string;
  role: MemberRole;
}

export async function createOrganization(
  data: CreateOrganizationData,
): Promise<CreatedOrganization> {
  const response = await apiClient.post<CreatedOrganization>(
    "/organizations/",
    data,
  );

  return response.data;
}

export async function getInvitations(
  organizationId: string,
): Promise<Invitation[]> {
  const response = await apiClient.get<Invitation[]>(
    `/organizations/${organizationId}/invitations/`,
  );

  return response.data;
}

export async function resendInvitation(
  organizationId: string,
  invitationId: string,
): Promise<Invitation> {
  const response = await apiClient.post<{ invitation: Invitation }>(
    `/organizations/${organizationId}/invitations/${invitationId}/resend/`,
  );

  return response.data.invitation;
}

export async function revokeInvitation(
  organizationId: string,
  invitationId: string,
): Promise<void> {
  await apiClient.delete(
    `/organizations/${organizationId}/invitations/${invitationId}/`,
  );
}

/** Public: who and which workspace an invitation link is for. */
export async function previewInvitation(
  token: string,
): Promise<InvitationPreview> {
  const response = await apiClient.get<InvitationPreview>(
    "/auth/invitations/preview/",
    { params: { token } },
  );

  return response.data;
}

export interface AcceptInvitationResponse {
  message: string;
  organization: { id: string; name: string; slug: string };
}

/** Signed-in user joins the workspace the invitation is for. */
export async function acceptInvitation(
  token: string,
): Promise<AcceptInvitationResponse> {
  const response = await apiClient.post<AcceptInvitationResponse>(
    "/auth/invitations/accept/",
    { token },
  );

  return response.data;
}
