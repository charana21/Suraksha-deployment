import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { IconPlus, IconEdit, IconLock } from "@tabler/icons-react";
import { toast } from "sonner";
import {
  Badge,
  Box,
  Button,
  Center,
  Checkbox,
  Grid,
  Group,
  Loader,
  Modal,
  NumberInput,
  Pagination,
  ScrollArea,
  Select,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
  Title,
} from "@mantine/core";
import { useAuth } from "@/context/AuthContext";
import { modulesApi, type ModuleItem } from "../../services/modules";
import {
  rolesApi,
  type RoleItem,
  type RolePermission,
  type RolePayload,
} from "../../services/roles";
import { PageLayout } from "@/components/layout/PageLayout";

const permissionKeys = ["add", "edit", "view", "delete"] as const;

type RoleFormState = {
  name: string;
  description: string;
  level: string;
  isSuperUser: boolean;
  active: string;
  permissions: RolePermission[];
};

const emptyForm = (modules: ModuleItem[] = []): RoleFormState => ({
  name: "",
  description: "",
  level: "",
  isSuperUser: undefined as unknown as boolean,
  active: "",
  permissions: modules.map((module) => ({
    moduleID: module._id,
    add: 0,
    edit: 0,
    view: 0,
    delete: 0,
  })),
});

const mergePermissions = (
  modules: ModuleItem[],
  permissions: RolePermission[] = [],
) =>
  modules.map((module) => {
    const existing = permissions.find((p) => p.moduleID === module._id);
    return {
      moduleID: module._id,
      add: existing?.add ?? 0,
      edit: existing?.edit ?? 0,
      view: existing?.view ?? 0,
      delete: existing?.delete ?? 0,
    };
  });

const buildFormFromRole = (
  role: RoleItem,
  modules: ModuleItem[],
): RoleFormState => ({
  name: role.name ?? "",
  description: role.description ?? "",
  level: String(role.level),
  isSuperUser: Boolean(role.isSuperUser),
  active: role.active === 1 ? "1" : "0",
  permissions: mergePermissions(modules, role.permissions || []),
});

/** Shared dark-theme styles for Mantine inputs */
const inputStyles = () => ({
  label: { color: "#c0c0c0", fontSize: 13, fontWeight: 500, marginBottom: 4 },
  input: {
    background: "#2a2a2a",
    border: "1px solid #444",
    color: "#fff",
    "&:focus": { borderColor: "#228be6" },
  },
});

const tdBase: React.CSSProperties = {
  padding: "8px 12px",
  borderBottom: "1px solid #2a2a2a",
  verticalAlign: "middle",
  color: "#e0e0e0",
};

const RolePage = () => {
  const { hasModulePermission } = useAuth();
  const [opened, setOpened] = useState(false);
  const [permissionsModalOpen, setPermissionsModalOpen] = useState(false);
  const [selectedRole, setSelectedRole] = useState<RoleItem | null>(null);
  const [roles, setRoles] = useState<RoleItem[]>([]);
  const [modules, setModules] = useState<ModuleItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [modulesLoading, setModulesLoading] = useState(true);
  const [error, setError] = useState("");
  const [modulesError, setModulesError] = useState("");
  const [saving, setSaving] = useState(false);
  const [permissionsSaving, setPermissionsSaving] = useState(false);
  const [form, setForm] = useState<RoleFormState>(emptyForm());
  const [permissionDraft, setPermissionDraft] = useState<RolePermission[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const canCreateRole = hasModulePermission("/roles", "add");
  const canEditRole = hasModulePermission("/roles", "edit");

  useEffect(() => {
    let isMounted = true;
    const loadRoles = async () => {
      setLoading(true);
      setError("");
      try {
        const response = await rolesApi.getRoles();
        if (!isMounted) return;
        setRoles(response.roles || []);
      } catch (err) {
        if (!isMounted) return;
        setError(err instanceof Error ? err.message : "Failed to load roles");
      } finally {
        if (isMounted) setLoading(false);
      }
    };
    loadRoles();
    return () => { isMounted = false; };
  }, []);

  useEffect(() => {
    let isMounted = true;
    const loadModules = async () => {
      setModulesLoading(true);
      setModulesError("");
      try {
        const response = await modulesApi.getModules();
        if (!isMounted) return;
        setModules(response.modules || []);
      } catch (err) {
        if (!isMounted) return;
        setModulesError(err instanceof Error ? err.message : "Failed to load modules");
      } finally {
        if (isMounted) setModulesLoading(false);
      }
    };
    loadModules();
    return () => { isMounted = false; };
  }, []);

  useEffect(() => {
    if (!opened) return;
    setForm((prev) => ({
      ...prev,
      permissions: mergePermissions(
        modules,
        selectedRole ? selectedRole.permissions || prev.permissions : prev.permissions,
      ),
    }));
  }, [modules, opened, selectedRole]);

  useEffect(() => {
    if (!permissionsModalOpen) return;
    setPermissionDraft(mergePermissions(modules, selectedRole?.permissions || []));
  }, [modules, permissionsModalOpen, selectedRole]);

  useEffect(() => {
    setPage(1);
  }, [pageSize]);

  useEffect(() => {
    const totalPages = Math.max(1, Math.ceil(roles.length / pageSize));
    setPage((current) => Math.min(current, totalPages));
  }, [roles.length, pageSize]);

  const moduleNameById = new Map(modules.map((m) => [m._id, m.name]));

  const permissionRows = useMemo(
    () => mergePermissions(modules, permissionDraft),
    [modules, permissionDraft],
  );
  const totalPages = Math.max(1, Math.ceil(roles.length / pageSize));
  const paginatedRoles = roles.slice((page - 1) * pageSize, page * pageSize);

  const handleOpenCreate = () => {
    if (!canCreateRole) { toast.error("No Access"); return; }
    setSelectedRole(null);
    setForm(emptyForm(modules));
    setOpened(true);
  };

  const handleOpenEdit = (role: RoleItem) => {
    if (!canEditRole) { toast.error("No Access"); return; }
    setSelectedRole(role);
    setForm(buildFormFromRole(role, modules));
    setOpened(true);
  };

  const handleOpenPermissions = (role: RoleItem) => {
    setSelectedRole(role);
    setPermissionDraft(mergePermissions(modules, role.permissions || []));
    setPermissionsModalOpen(true);
  };

  const handleCloseModal = () => {
    setOpened(false);
    setSelectedRole(null);
    setForm(emptyForm(modules));
  };

  const handleClosePermissionsModal = () => {
    setPermissionsModalOpen(false);
    setSelectedRole(null);
    setPermissionDraft([]);
  };

  const updatePermission = (
    moduleID: string,
    key: keyof Omit<RolePermission, "moduleID">,
    checked: boolean,
  ) => {
    setPermissionDraft((prev) =>
      prev.map((p) =>
        p.moduleID === moduleID ? { ...p, [key]: checked ? 1 : 0 } : p,
      ),
    );
  };

  const handlePermissionsSubmit = async () => {
    if (!selectedRole) { toast.error("Please select a role."); return; }
    setPermissionsSaving(true);
    try {
      const response = await rolesApi.updateRolePermissions(selectedRole._id, permissionRows);
      setRoles((prev) =>
        prev.map((r) => (r._id === response.role._id ? response.role : r)),
      );
      setSelectedRole(response.role);
      toast.success(response.responseMsg);
      handleClosePermissionsModal();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update permissions");
    } finally {
      setPermissionsSaving(false);
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!form.name.trim() || !form.description.trim()) {
      toast.error("Please fill in the role name and description.");
      return;
    }
    const payload: RolePayload = {
      name: form.name.trim(),
      description: form.description.trim(),
      level: Number(form.level),
      isSuperUser: form.isSuperUser,
      permissions: form.permissions,
      active: Number(form.active),
    };
    setSaving(true);
    try {
      const response = selectedRole
        ? await rolesApi.updateRole(selectedRole._id, payload)
        : await rolesApi.createRole(payload);
      const savedRole = response.role;
      setRoles((prev) =>
        selectedRole
          ? prev.map((r) => (r._id === savedRole._id ? savedRole : r))
          : [savedRole, ...prev],
      );
      toast.success(response.responseMsg);
      handleCloseModal();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save role");
    } finally {
      setSaving(false);
    }
  };

  const modalStyles = {
    content: { background: "#1a1a1a", border: "1px solid #333" },
    header: { background: "#1a1a1a" },
    title: { color: "#fff", fontWeight: 600, fontSize: 16 },
    close: { color: "#aaa" },
  };

  return (
    <PageLayout>
      {/* ── Permissions Modal ── */}
      <Modal
        opened={permissionsModalOpen}
        onClose={handleClosePermissionsModal}
        title={selectedRole ? `${selectedRole.name} Permissions` : "Permissions"}
        size="lg"
        styles={modalStyles}
      >
        <Stack gap={16}>
          <ScrollArea h={500}>
            <Table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <Table.Thead>
                <Table.Tr>
                  {["Module", "Add", "Edit", "View", "Delete"].map((h) => (
                    <Table.Th
                      key={h}
                      style={{
                        textAlign: "left",
                        padding: "8px 12px",
                        background: "#111",
                        borderBottom: "1px solid #333",
                        fontWeight: 600,
                        fontSize: 12,
                        color: "#a0a0a0",
                      }}
                    >
                      {h}
                    </Table.Th>
                  ))}
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {permissionRows.length === 0 ? (
                  <Table.Tr>
                    <Table.Td colSpan={5} style={tdBase}>
                      No permissions available.
                    </Table.Td>
                  </Table.Tr>
                ) : (
                  permissionRows.map((perm, idx) => {
                    const bg = idx % 2 === 1 ? "#222" : "transparent";
                    const td = { ...tdBase, background: bg };
                    return (
                      <Table.Tr key={perm.moduleID}>
                        <Table.Td style={td}>
                          {moduleNameById.get(perm.moduleID) || perm.moduleID}
                        </Table.Td>
                        {permissionKeys.map((key) => (
                          <Table.Td key={key} style={{ ...td, textAlign: "center" }}>
                            <Checkbox
                              checked={perm[key] === 1}
                              onChange={(e) =>
                                updatePermission(perm.moduleID, key, e.target.checked)
                              }
                              styles={{
                                input: { background: "#2a2a2a", borderColor: "#555", cursor: "pointer" },
                              }}
                            />
                          </Table.Td>
                        ))}
                      </Table.Tr>
                    );
                  })
                )}
              </Table.Tbody>
            </Table>
          </ScrollArea>

          <Group justify="flex-end">
            <Button
              variant="default"
              onClick={handleClosePermissionsModal}
              styles={{ root: { background: "#2a2a2a", border: "1px solid #444", color: "#ddd" } }}
            >
              Close
            </Button>
            <Button
              onClick={handlePermissionsSubmit}
              loading={permissionsSaving}
              disabled={permissionsSaving}
              styles={{ root: { background: "#228be6" } }}
            >
              {permissionsSaving ? "Saving..." : "Save"}
            </Button>
          </Group>
        </Stack>
      </Modal>

      {/* ── Create / Edit Role Modal ── */}
      <Modal
        opened={opened}
        onClose={handleCloseModal}
        title={selectedRole ? "Edit Role" : "Create Role"}
        size="lg"
        styles={modalStyles}
      >
        <form onSubmit={handleSubmit}>
          <Stack gap={16}>
            <Grid gutter={12}>
              <Grid.Col span={6}>
                <TextInput
                  label="Role Name"
                  placeholder="Enter role name"
                  value={form.name}
                  onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                  styles={inputStyles()}
                />
              </Grid.Col>

              <Grid.Col span={6}>
                <NumberInput
                  label="Level"
                  placeholder="Enter level"
                  min={1}
                  value={form.level === "" ? "" : Number(form.level)}
                  onChange={(val) =>
                    setForm((p) => ({ ...p, level: val === "" ? "" : String(val) }))
                  }
                  styles={inputStyles()}
                />
              </Grid.Col>

              <Grid.Col span={12}>
                <Textarea
                  label="Description"
                  placeholder="Enter description"
                  value={form.description}
                  onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
                  minRows={3}
                  autosize
                  styles={inputStyles()}
                />
              </Grid.Col>

              <Grid.Col span={6}>
                <Select
                  label="Super User"
                  placeholder="Select"
                  data={[
                    { value: "0", label: "No" },
                    { value: "1", label: "Yes" },
                  ]}
                  value={
                    form.isSuperUser === undefined
                      ? null
                      : form.isSuperUser
                        ? "1"
                        : "0"
                  }
                  onChange={(val) =>
                    setForm((p) => ({ ...p, isSuperUser: val === "1" }))
                  }
                  styles={inputStyles()}
                />
              </Grid.Col>

              <Grid.Col span={6}>
                <Select
                  label="Status"
                  placeholder="Select"
                  data={[
                    { value: "1", label: "Active" },
                    { value: "0", label: "Inactive" },
                  ]}
                  value={form.active || null}
                  onChange={(val) => setForm((p) => ({ ...p, active: val ?? "" }))}
                  styles={inputStyles()}
                />
              </Grid.Col>
            </Grid>

            <Group justify="flex-end">
              <Button
                variant="default"
                onClick={handleCloseModal}
                styles={{ root: { background: "#2a2a2a", border: "1px solid #444", color: "#ddd" } }}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                loading={saving}
                disabled={saving}
                styles={{ root: { background: "#228be6" } }}
              >
                {saving ? "Saving..." : selectedRole ? "Update" : "Submit"}
              </Button>
            </Group>
          </Stack>
        </form>
      </Modal>

      {/* ── Header card ── */}
      <Box
        mb={12}
        p={16}
        style={{ border: "1px solid #333", borderRadius: 8, background: "#1a1a1a" }}
      >
        <Group justify="space-between" align="center">
          <Group gap={8} align="center">
            <Title order={4} style={{ color: "#fff", margin: 0 }}>Role Management</Title>
            <Badge
              style={{ background: "#333", color: "#d0d0d0", borderRadius: 99 }}
              size="md"
            >
              {roles.length}
            </Badge>
          </Group>

          <Button
            size="xs"
            leftSection={<IconPlus size={14} />}
            onClick={handleOpenCreate}
            disabled={!canCreateRole}
            title={canCreateRole ? "Create" : "No Access"}
            styles={{
              root: {
                background: "#228be6",
                opacity: canCreateRole ? 1 : 0.5,
                cursor: canCreateRole ? "pointer" : "not-allowed",
              },
            }}
          >
            Create
          </Button>
        </Group>
      </Box>

      {/* ── Table card ── */}
      <Box p={16} style={{ border: "1px solid #333", borderRadius: 8, background: "#1a1a1a" }}>
        <ScrollArea mah={500}>
          <Table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <Table.Thead>
              <Table.Tr>
                {["Role Name", "Description", "Status", "Actions"].map((h) => (
                  <Table.Th
                    key={h}
                    style={{
                      textAlign: "left",
                      padding: "8px 12px",
                      background: "#111",
                      borderBottom: "1px solid #333",
                      fontWeight: 600,
                      fontSize: 12,
                      color: "#a0a0a0",
                    }}
                  >
                    {h}
                  </Table.Th>
                ))}
              </Table.Tr>
            </Table.Thead>

            <Table.Tbody>
              {loading ? (
                <Table.Tr>
                  <Table.Td colSpan={4} style={{ padding: "40px 12px", border: "none" }}>
                    <Center>
                      <Loader size="sm" color="#228be6" />
                    </Center>
                  </Table.Td>
                </Table.Tr>
              ) : error ? (
                <Table.Tr>
                  <Table.Td colSpan={4} style={{ padding: "40px 12px", border: "none" }}>
                    <Center>
                      <Text size="sm" c="#ff8f8f">{error}</Text>
                    </Center>
                  </Table.Td>
                </Table.Tr>
              ) : roles.length === 0 ? (
                <Table.Tr>
                  <Table.Td colSpan={4} style={tdBase}>No roles found.</Table.Td>
                </Table.Tr>
              ) : (
                paginatedRoles.map((role, idx) => {
                  const bg = idx % 2 === 1 ? "#222" : "transparent";
                  const td = { ...tdBase, background: bg };
                  return (
                    <Table.Tr key={role._id}>
                      <Table.Td style={td}>
                        <Text size="sm" c="#e0e0e0">{role.name}</Text>
                      </Table.Td>
                      <Table.Td style={td}>
                        <Text size="sm" c="#e0e0e0">{role.description}</Text>
                      </Table.Td>
                      <Table.Td style={td}>
                        <Text size="sm" c="#e0e0e0">
                          {role.active === 1 ? "Active" : "Inactive"}
                        </Text>
                      </Table.Td>
                      <Table.Td style={td}>
                        <Group gap={8}>
                          <Box
                            component="span"
                            style={{ cursor: "pointer", color: "#a0a0a0", display: "inline-flex" }}
                            onClick={() => handleOpenPermissions(role)}
                            title="Permissions"
                          >
                            <IconLock size={18} />
                          </Box>
                          <Box
                            component="span"
                            style={{
                              cursor: canEditRole ? "pointer" : "not-allowed",
                              color: "#a0a0a0",
                              display: "inline-flex",
                              opacity: canEditRole ? 1 : 0.4,
                            }}
                            onClick={() => handleOpenEdit(role)}
                            title={canEditRole ? "Edit" : "No Access"}
                            aria-disabled={!canEditRole}
                          >
                            <IconEdit size={18} />
                          </Box>
                        </Group>
                      </Table.Td>
                    </Table.Tr>
                  );
                })
              )}
            </Table.Tbody>
          </Table>
        </ScrollArea>

        <Group justify="space-between" align="center" mt={12} gap={12} wrap="wrap">
          <Group gap={8} align="center">
            <Text size="sm" c="#aaa">
              Records per page
            </Text>
            <Select
              data={["10", "20", "30"]}
              value={String(pageSize)}
              onChange={(value) => setPageSize(Number(value ?? "10"))}
              w={70}
              styles={{
                input: {
                  background: "#2a2a2a",
                  border: "1px solid #444",
                  color: "#fff",
                },
              }}
            />
          </Group>

          <Pagination
            value={page}
            onChange={setPage}
            total={totalPages}
            size="sm"
            color="blue"
            styles={{
              control: {
                background: "#2a2a2a",
                borderColor: "#444",
                color: "#ddd",
              },
            }}
          />
        </Group>
      </Box>
    </PageLayout>
  );
};

export default RolePage;
