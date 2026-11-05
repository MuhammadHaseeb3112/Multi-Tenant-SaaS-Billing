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

export interface InviteMemberResponse {
  message: string;
  invitation: {
    id: string;
    email: string;
    role: string;
    expires_at: string;
    invitation_url: string;
  };
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