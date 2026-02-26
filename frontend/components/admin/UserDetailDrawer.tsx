"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { t, type Lang } from "@/lib/i18n";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAdminToast } from "@/components/ui/admin-toast";
import * as Dialog from "@radix-ui/react-dialog";
import { X, Loader2, Trash2, Ban, CheckCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { API_BASE } from "@/lib/admin-utils";

interface UserDetail {
  id: string;
  email: string | null;
  nickname: string | null;
  bio: string | null;
  birth_year: number | null;
  plan: string;
  role: string;
  status: string;
  created_at: string;
  last_active: string | null;
  agreed_terms_at: string | null;
  suspend_reason: string | null;
  suspended_until: string | null;
}

interface UserDetailDrawerProps {
  open: boolean;
  onClose: () => void;
  userId: string | null;
  lang: Lang;
  onUpdated: () => void;
}

const PLAN_BADGE: Record<string, string> = {
  free: "bg-secondary text-muted-foreground",
  pro: "bg-yellow-500/20 text-yellow-400",
  pro_plus: "bg-purple-500/20 text-purple-400",
};

const STATUS_BADGE: Record<string, string> = {
  active: "text-green-400",
  suspended: "text-red-400",
  deleted: "text-muted-foreground",
};

export default function UserDetailDrawer({
  open,
  onClose,
  userId,
  lang,
  onUpdated,
}: UserDetailDrawerProps) {
  const { user } = useAuth();
  const { toast } = useAdminToast();
  const queryClient = useQueryClient();
  const locale = lang === "en" ? "en-US" : "ko-KR";

  const [editPlan, setEditPlan] = useState<string>("");
  const [editRole, setEditRole] = useState<string>("");
  const [confirmDelete, setConfirmDelete] = useState(false);

  // Fetch user detail
  const {
    data: detail,
    isLoading,
    isError,
  } = useQuery<UserDetail>({
    queryKey: ["admin-user-detail", userId],
    queryFn: async () => {
      if (!user || !userId) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/admin/users/${userId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed to load user");
      return res.json();
    },
    enabled: open && !!user && !!userId,
  });

  // Sync editable fields when detail loads
  useEffect(() => {
    if (detail) {
      setEditPlan(detail.plan);
      setEditRole(detail.role);
    }
  }, [detail]);

  // Reset confirm state when drawer closes
  useEffect(() => {
    if (!open) {
      setConfirmDelete(false);
    }
  }, [open]);

  // Update mutation (plan, role, suspend/unsuspend)
  const updateMutation = useMutation({
    mutationFn: async (body: Record<string, unknown>) => {
      if (!user || !userId) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/admin/users/${userId}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error("Update failed");
      return res.json();
    },
    onSuccess: () => {
      toast(t(lang, "admin_toast_updated"), "success");
      queryClient.invalidateQueries({ queryKey: ["admin-user-detail", userId] });
      onUpdated();
    },
    onError: () => {
      toast(t(lang, "admin_toast_error"), "error");
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: async () => {
      if (!user || !userId) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/admin/users/${userId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Delete failed");
    },
    onSuccess: () => {
      toast(t(lang, "admin_toast_deleted"), "success");
      queryClient.invalidateQueries({ queryKey: ["admin-user-detail", userId] });
      onUpdated();
      onClose();
    },
    onError: () => {
      toast(t(lang, "admin_toast_error"), "error");
    },
  });

  const handlePlanChange = (plan: string) => {
    setEditPlan(plan);
    updateMutation.mutate({ plan });
  };

  const handleRoleChange = (role: string) => {
    setEditRole(role);
    updateMutation.mutate({ role });
  };

  const handleSuspendToggle = () => {
    if (detail?.status === "suspended") {
      updateMutation.mutate({ suspended_until: null, suspend_reason: null });
    } else {
      updateMutation.mutate({
        suspended_until: new Date(Date.now() + 7 * 86400_000).toISOString(),
        suspend_reason: lang === "ko" ? "관리자 정지" : "Suspended by admin",
      });
    }
  };

  const handleDelete = () => {
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    deleteMutation.mutate();
  };

  const isSuspended = detail?.status === "suspended";
  const isMutating = updateMutation.isPending || deleteMutation.isPending;

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(v) => {
        if (!v) onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50" />
        <Dialog.Content className="fixed inset-y-0 right-0 z-50 w-full sm:w-[400px] bg-card border-l border-border overflow-y-auto shadow-xl">
          {/* Header */}
          <div className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-card px-5 py-4">
            <Dialog.Title className="text-lg font-bold text-foreground">
              {t(lang, "admin_user_detail")}
            </Dialog.Title>
            <Dialog.Close asChild>
              <button className="rounded-lg p-1.5 text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors">
                <X className="h-5 w-5" />
              </button>
            </Dialog.Close>
          </div>

          {/* Body */}
          <div className="p-5 space-y-5">
            {isLoading ? (
              <div className="flex items-center justify-center py-20">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                <span className="ml-2 text-sm text-muted-foreground">
                  {t(lang, "admin_loading")}
                </span>
              </div>
            ) : isError || !detail ? (
              <div className="flex items-center justify-center py-20">
                <p className="text-sm text-muted-foreground">
                  {t(lang, "admin_toast_error")}
                </p>
              </div>
            ) : (
              <>
                {/* User Identity Section */}
                <div className="rounded-xl border border-border p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-base font-semibold text-foreground">
                      {detail.nickname || t(lang, "admin_no_name")}
                    </h3>
                    <div className="flex items-center gap-2">
                      <span
                        className={cn(
                          "rounded-full px-2.5 py-0.5 text-[10px] font-medium",
                          PLAN_BADGE[detail.plan] || "bg-secondary"
                        )}
                      >
                        {detail.plan.toUpperCase()}
                      </span>
                      <span
                        className={cn(
                          "text-xs font-medium",
                          STATUS_BADGE[detail.status]
                        )}
                      >
                        {detail.status}
                      </span>
                    </div>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {detail.email || "\u2014"}
                  </p>
                </div>

                {/* Detail Fields Section */}
                <div className="rounded-xl border border-border divide-y divide-border">
                  <DetailRow label={t(lang, "admin_user_email")} value={detail.email || "\u2014"} />
                  <DetailRow label={t(lang, "admin_user_nickname")} value={detail.nickname || t(lang, "admin_no_name")} />
                  <DetailRow label={t(lang, "admin_user_bio")} value={detail.bio || "\u2014"} />
                  <DetailRow
                    label={t(lang, "admin_user_birth_year")}
                    value={detail.birth_year ? String(detail.birth_year) : "\u2014"}
                  />
                  <DetailRow label={t(lang, "admin_user_plan")} value={detail.plan.toUpperCase()} />
                  <DetailRow label={t(lang, "admin_user_role")} value={detail.role} />
                  <DetailRow label={t(lang, "admin_user_status")} value={detail.status} />
                  <DetailRow
                    label={t(lang, "admin_user_joined")}
                    value={new Date(detail.created_at).toLocaleString(locale)}
                  />
                  <DetailRow
                    label={t(lang, "admin_user_last_active")}
                    value={
                      detail.last_active
                        ? new Date(detail.last_active).toLocaleString(locale)
                        : "\u2014"
                    }
                  />
                  <DetailRow
                    label={t(lang, "admin_user_terms_agreed")}
                    value={
                      detail.agreed_terms_at
                        ? new Date(detail.agreed_terms_at).toLocaleString(locale)
                        : "\u2014"
                    }
                  />
                  <DetailRow
                    label={t(lang, "admin_user_suspend_reason")}
                    value={detail.suspend_reason || "\u2014"}
                  />
                  <DetailRow
                    label={t(lang, "admin_user_suspended_until")}
                    value={
                      detail.suspended_until
                        ? new Date(detail.suspended_until).toLocaleString(locale)
                        : "\u2014"
                    }
                  />
                </div>

                {/* Editable Actions Section */}
                <div className="rounded-xl border border-border p-4 space-y-4">
                  {/* Plan Dropdown */}
                  <div className="flex items-center justify-between">
                    <label className="text-sm font-medium text-foreground">
                      {t(lang, "admin_user_plan")}
                    </label>
                    <select
                      value={editPlan}
                      onChange={(e) => handlePlanChange(e.target.value)}
                      disabled={isMutating}
                      className="rounded-lg border border-border bg-background text-sm px-3 py-1.5 outline-none focus:border-primary disabled:opacity-50"
                    >
                      <option value="free">FREE</option>
                      <option value="pro">PRO</option>
                      <option value="pro_plus">PRO+</option>
                    </select>
                  </div>

                  {/* Role Dropdown */}
                  <div className="flex items-center justify-between">
                    <label className="text-sm font-medium text-foreground">
                      {t(lang, "admin_user_role")}
                    </label>
                    <select
                      value={editRole}
                      onChange={(e) => handleRoleChange(e.target.value)}
                      disabled={isMutating}
                      className="rounded-lg border border-border bg-background text-sm px-3 py-1.5 outline-none focus:border-primary disabled:opacity-50"
                    >
                      <option value="user">user</option>
                      <option value="moderator">moderator</option>
                      <option value="admin">admin</option>
                    </select>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="space-y-3">
                  {/* Suspend / Unsuspend */}
                  <button
                    onClick={handleSuspendToggle}
                    disabled={isMutating}
                    className={cn(
                      "w-full flex items-center justify-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium transition-colors disabled:opacity-50",
                      isSuspended
                        ? "border-green-500/30 text-green-400 hover:bg-green-500/10"
                        : "border-red-500/30 text-red-400 hover:bg-red-500/10"
                    )}
                  >
                    {isSuspended ? (
                      <>
                        <CheckCircle className="h-4 w-4" />
                        {t(lang, "admin_unsuspend")}
                      </>
                    ) : (
                      <>
                        <Ban className="h-4 w-4" />
                        {t(lang, "admin_suspend")}
                      </>
                    )}
                  </button>

                  {/* Delete */}
                  <button
                    onClick={handleDelete}
                    disabled={isMutating}
                    className={cn(
                      "w-full flex items-center justify-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium transition-colors disabled:opacity-50",
                      confirmDelete
                        ? "border-red-500 bg-red-500/20 text-red-300 hover:bg-red-500/30"
                        : "border-border text-muted-foreground hover:bg-secondary hover:text-foreground"
                    )}
                  >
                    {deleteMutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                    {confirmDelete
                      ? t(lang, "admin_user_delete_confirm")
                      : t(lang, "admin_user_delete")}
                  </button>
                </div>
              </>
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

/* ------------------------------------------------------------------ */
/*  Detail Row helper                                                  */
/* ------------------------------------------------------------------ */

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4 px-4 py-3">
      <span className="text-xs text-muted-foreground shrink-0">{label}</span>
      <span className="text-sm text-foreground text-right break-all">{value}</span>
    </div>
  );
}
