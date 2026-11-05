import apiClient from "./client";

export interface Notification {
  id: string;
  title: string;
  message: string;
  notification_type: string;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
}

export interface UnreadCountResponse {
  unread_count: number;
}

export const getNotifications = async (
  organizationId: string,
): Promise<Notification[]> => {
  const response = await apiClient.get<Notification[]>(
    `/notifications/organizations/${organizationId}/`,
  );

  return response.data;
};

export const getUnreadNotificationCount = async (
  organizationId: string,
): Promise<number> => {
  const response =
    await apiClient.get<UnreadCountResponse>(
      `/notifications/organizations/${organizationId}/unread-count/`,
    );

  return response.data.unread_count;
};

export const markNotificationAsRead = async (
  organizationId: string,
  notificationId: string,
): Promise<Notification> => {
  const response =
    await apiClient.post<Notification>(
      `/notifications/organizations/${organizationId}/${notificationId}/read/`,
    );

  return response.data;
};

export const markAllNotificationsAsRead = async (
  organizationId: string,
): Promise<void> => {
  await apiClient.post(
    `/notifications/organizations/${organizationId}/read-all/`,
  );
};