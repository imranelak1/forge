export type Role = "viewer" | "member" | "admin" | "owner";
export interface User {
  id: string;
  name: string;
  email: string;
  email_verified: boolean;
}
export interface Organization {
  id: string;
  name: string;
  slug: string;
  role: Role;
  is_demo: boolean;
}
export interface Identity {
  user: User;
  session_id: string;
  organizations: Organization[];
  organizations_page?: { next_cursor: string | null; has_more: boolean };
}
export interface PageResult<T> {
  data: T[];
  page: { next_cursor: string | null; has_more: boolean };
}
export interface Member {
  id: string;
  user_id: string;
  name: string;
  email: string;
  role: Role;
}
export interface Session {
  id: string;
  created_at: string;
  expires_at: string;
  current: boolean;
}
export interface AuditEvent {
  id: string;
  action: string;
  actor_id: string | null;
  subject_id: string | null;
  created_at: string;
}
