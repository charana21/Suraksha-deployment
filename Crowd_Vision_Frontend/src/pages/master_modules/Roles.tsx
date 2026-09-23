import { useEffect, useMemo, useState } from "react";

import type { FormEvent } from "react";

import {
  IconPlus,
  IconEdit,
  IconLock,
} from "@tabler/icons-react";

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

import {
  modulesApi,
  type ModuleItem,
} from "../../services/modules";

import {
  rolesApi,
  type RoleItem,
  type RolePermission,
  type RolePayload,
} from "../../services/roles";

import { PageLayout } from "@/components/layout/PageLayout";

/* =========================================================
   CONSTANTS
   ========================================================= */

const permissionKeys = [
  "add",
  "edit",
  "view",
  "delete",
] as const;

/* =========================================================
   TYPES
   ========================================================= */

type RoleFormState = {
  name: string;
  description: string;
  level: string;
  isSuperUser: boolean;
  active: string;
  permissions: RolePermission[];
};

/* =========================================================
   FORM HELPERS
   ========================================================= */

const emptyForm = (
  modules: ModuleItem[] = []
): RoleFormState => ({
  name: "",
  description: "",
  level: "",
  isSuperUser:
    undefined as unknown as boolean,
  active: "",
  permissions: modules.map(
    (module) => ({
      moduleID: module._id,
      add: 0,
      edit: 0,
      view: 0,
      delete: 0,
    })
  ),
});

const mergePermissions = (
  modules: ModuleItem[],
  permissions: RolePermission[] = []
) =>
  modules.map((module) => {
    const existing = permissions.find(
      (p) =>
        p.moduleID === module._id
    );

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
  modules: ModuleItem[]
): RoleFormState => ({
  name: role.name ?? "",
  description:
    role.description ?? "",
  level: String(role.level),
  isSuperUser: Boolean(
    role.isSuperUser
  ),
  active:
    role.active === 1
      ? "1"
      : "0",
  permissions:
    mergePermissions(
      modules,
      role.permissions || []
    ),
});

/* =========================================================
   THEME-AWARE INPUT STYLES
   ========================================================= */

const inputStyles = () => ({
  label: {
    color:
      "hsl(var(--foreground))",
    fontSize: 13,
    fontWeight: 500,
    marginBottom: 4,
  },

  input: {
    background:
      "hsl(var(--background))",

    border:
      "1px solid hsl(var(--border))",

    color:
      "hsl(var(--foreground))",

    "&:focus": {
      borderColor:
        "hsl(var(--primary))",
    },

    "&:hover": {
      borderColor:
        "hsl(var(--border))",
    },
  },

  textarea: {
    background:
      "hsl(var(--background))",

    border:
      "1px solid hsl(var(--border))",

    color:
      "hsl(var(--foreground))",

    "&:focus": {
      borderColor:
        "hsl(var(--primary))",
    },

    "&:hover": {
      borderColor:
        "hsl(var(--border))",
    },
  },

  /* Mantine Select dropdown */

  dropdown: {
    background:
      "hsl(var(--card)) !important",

    border:
      "1px solid hsl(var(--border))",

    color:
      "hsl(var(--foreground)) !important",

    boxShadow:
      "0 8px 24px rgba(0, 0, 0, 0.15)",
  },

  /* Mantine Select options */

  option: {
    background:
      "hsl(var(--card)) !important",

    color:
      "hsl(var(--foreground)) !important",

    "&:hover": {
      background:
        "hsl(var(--muted)) !important",

      color:
        "hsl(var(--foreground)) !important",
    },

    "&[data-combobox-active]": {
      background:
        "hsl(var(--muted)) !important",

      color:
        "hsl(var(--foreground)) !important",
    },

    "&[data-combobox-selected]": {
      background:
        "hsl(var(--muted)) !important",

      color:
        "hsl(var(--foreground)) !important",
    },
  },
});

/* =========================================================
   TABLE BASE STYLE
   ========================================================= */

const tdBase: React.CSSProperties = {
  padding: "8px 12px",

  borderBottom:
    "1px solid hsl(var(--border))",

  verticalAlign:
    "middle",

  color:
    "hsl(var(--foreground))",
};

/* =========================================================
   COMPONENT
   ========================================================= */

const RolePage = () => {
  const { hasModulePermission } =
    useAuth();

  const [opened, setOpened] =
    useState(false);

  const [
    permissionsModalOpen,
    setPermissionsModalOpen,
  ] = useState(false);

  const [selectedRole, setSelectedRole] =
    useState<RoleItem | null>(null);

  const [roles, setRoles] =
    useState<RoleItem[]>([]);

  const [modules, setModules] =
    useState<ModuleItem[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [modulesLoading, setModulesLoading] =
    useState(true);

  const [error, setError] =
    useState("");

  const [modulesError, setModulesError] =
    useState("");

  const [saving, setSaving] =
    useState(false);

  const [
    permissionsSaving,
    setPermissionsSaving,
  ] = useState(false);

  const [form, setForm] =
    useState<RoleFormState>(
      emptyForm()
    );

  const [
    permissionDraft,
    setPermissionDraft,
  ] = useState<RolePermission[]>(
    []
  );

  const [page, setPage] =
    useState(1);

  const [pageSize, setPageSize] =
    useState(10);

  const canCreateRole =
    hasModulePermission(
      "/roles",
      "add"
    );

  const canEditRole =
    hasModulePermission(
      "/roles",
      "edit"
    );

  /* =========================================================
     LOAD ROLES
     ========================================================= */

  useEffect(() => {
    let isMounted = true;

    const loadRoles = async () => {
      setLoading(true);
      setError("");

      try {
        const response =
          await rolesApi.getRoles();

        if (!isMounted) return;

        setRoles(
          response.roles || []
        );
      } catch (err) {
        if (!isMounted) return;

        setError(
          err instanceof Error
            ? err.message
            : "Failed to load roles"
        );
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    loadRoles();

    return () => {
      isMounted = false;
    };
  }, []);

  /* =========================================================
     LOAD MODULES
     ========================================================= */

  useEffect(() => {
    let isMounted = true;

    const loadModules = async () => {
      setModulesLoading(true);
      setModulesError("");

      try {
        const response =
          await modulesApi.getModules();

        if (!isMounted) return;

        setModules(
          response.modules || []
        );
      } catch (err) {
        if (!isMounted) return;

        setModulesError(
          err instanceof Error
            ? err.message
            : "Failed to load modules"
        );
      } finally {
        if (isMounted) {
          setModulesLoading(false);
        }
      }
    };

    loadModules();

    return () => {
      isMounted = false;
    };
  }, []);

  /* =========================================================
     UPDATE FORM PERMISSIONS
     ========================================================= */

  useEffect(() => {
    if (!opened) return;

    setForm((prev) => ({
      ...prev,

      permissions:
        mergePermissions(
          modules,
          selectedRole
            ? selectedRole.permissions ||
                prev.permissions
            : prev.permissions
        ),
    }));
  }, [
    modules,
    opened,
    selectedRole,
  ]);

  /* =========================================================
     UPDATE PERMISSION DRAFT
     ========================================================= */

  useEffect(() => {
    if (!permissionsModalOpen) {
      return;
    }

    setPermissionDraft(
      mergePermissions(
        modules,
        selectedRole?.permissions ||
          []
      )
    );
  }, [
    modules,
    permissionsModalOpen,
    selectedRole,
  ]);

  /* =========================================================
     PAGINATION
     ========================================================= */

  useEffect(() => {
    setPage(1);
  }, [pageSize]);

  useEffect(() => {
    const totalPages =
      Math.max(
        1,
        Math.ceil(
          roles.length /
            pageSize
        )
      );

    setPage((current) =>
      Math.min(
        current,
        totalPages
      )
    );
  }, [
    roles.length,
    pageSize,
  ]);

  /* =========================================================
     DERIVED DATA
     ========================================================= */

  const moduleNameById =
    new Map(
      modules.map((m) => [
        m._id,
        m.name,
      ])
    );

  const permissionRows =
    useMemo(
      () =>
        mergePermissions(
          modules,
          permissionDraft
        ),
      [
        modules,
        permissionDraft,
      ]
    );

  const totalPages =
    Math.max(
      1,
      Math.ceil(
        roles.length /
          pageSize
      )
    );

  const paginatedRoles =
    roles.slice(
      (page - 1) *
        pageSize,
      page *
        pageSize
    );

  /* =========================================================
     OPEN CREATE
     ========================================================= */

  const handleOpenCreate =
    () => {
      if (!canCreateRole) {
        toast.error("No Access");
        return;
      }

      setSelectedRole(null);

      setForm(
        emptyForm(modules)
      );

      setOpened(true);
    };

  /* =========================================================
     OPEN EDIT
     ========================================================= */

  const handleOpenEdit = (
    role: RoleItem
  ) => {
    if (!canEditRole) {
      toast.error("No Access");
      return;
    }

    setSelectedRole(role);

    setForm(
      buildFormFromRole(
        role,
        modules
      )
    );

    setOpened(true);
  };

  /* =========================================================
     OPEN PERMISSIONS
     ========================================================= */

  const handleOpenPermissions =
    (role: RoleItem) => {
      setSelectedRole(role);

      setPermissionDraft(
        mergePermissions(
          modules,
          role.permissions || []
        )
      );

      setPermissionsModalOpen(
        true
      );
    };

  /* =========================================================
     CLOSE MODAL
     ========================================================= */

  const handleCloseModal = () => {
    setOpened(false);
    setSelectedRole(null);
    setForm(
      emptyForm(modules)
    );
  };

  const handleClosePermissionsModal =
    () => {
      setPermissionsModalOpen(
        false
      );

      setSelectedRole(null);

      setPermissionDraft([]);
    };

  /* =========================================================
     UPDATE PERMISSION
     ========================================================= */

  const updatePermission = (
    moduleID: string,
    key: keyof Omit<
      RolePermission,
      "moduleID"
    >,
    checked: boolean
  ) => {
    setPermissionDraft((prev) =>
      prev.map((p) =>
        p.moduleID === moduleID
          ? {
              ...p,
              [key]:
                checked ? 1 : 0,
            }
          : p
      )
    );
  };

  /* =========================================================
     SAVE PERMISSIONS
     ========================================================= */

  const handlePermissionsSubmit =
    async () => {
      if (!selectedRole) {
        toast.error(
          "Please select a role."
        );

        return;
      }

      setPermissionsSaving(true);

      try {
        const response =
          await rolesApi.updateRolePermissions(
            selectedRole._id,
            permissionRows
          );

        setRoles((prev) =>
          prev.map((r) =>
            r._id ===
            response.role._id
              ? response.role
              : r
          )
        );

        setSelectedRole(
          response.role
        );

        toast.success(
          response.responseMsg
        );

        handleClosePermissionsModal();
      } catch (err) {
        toast.error(
          err instanceof Error
            ? err.message
            : "Failed to update permissions"
        );
      } finally {
        setPermissionsSaving(
          false
        );
      }
    };

  /* =========================================================
     SAVE ROLE
     ========================================================= */

  const handleSubmit = async (
    event: FormEvent<HTMLFormElement>
  ) => {
    event.preventDefault();

    if (
      !form.name.trim() ||
      !form.description.trim()
    ) {
      toast.error(
        "Please fill in the role name and description."
      );

      return;
    }

    const payload: RolePayload = {
      name: form.name.trim(),

      description:
        form.description.trim(),

      level: Number(form.level),

      isSuperUser:
        form.isSuperUser,

      permissions:
        form.permissions,

      active:
        Number(form.active),
    };

    setSaving(true);

    try {
      const response =
        selectedRole
          ? await rolesApi.updateRole(
              selectedRole._id,
              payload
            )
          : await rolesApi.createRole(
              payload
            );

      const savedRole =
        response.role;

      setRoles((prev) =>
        selectedRole
          ? prev.map((r) =>
              r._id ===
              savedRole._id
                ? savedRole
                : r
            )
          : [
              savedRole,
              ...prev,
            ]
      );

      toast.success(
        response.responseMsg
      );

      handleCloseModal();
    } catch (err) {
      toast.error(
        err instanceof Error
          ? err.message
          : "Failed to save role"
      );
    } finally {
      setSaving(false);
    }
  };

  /* =========================================================
     THEME-AWARE MODAL STYLES
     ========================================================= */

  const modalStyles = {
    content: {
      background:
        "hsl(var(--card))",

      border:
        "1px solid hsl(var(--border))",
    },

    header: {
      background:
        "hsl(var(--card))",

      color:
        "hsl(var(--foreground))",
    },

    body: {
      background:
        "hsl(var(--card))",

      color:
        "hsl(var(--foreground))",
    },

    title: {
      color:
        "hsl(var(--foreground))",

      fontWeight: 600,
      fontSize: 16,
    },

    
close: {
  color: "hsl(var(--foreground)) !important",
  background: "transparent",

  "&:hover": {
    background: "hsl(var(--muted))",
    color: "hsl(var(--foreground)) !important",
  },

  "&:focus": {
    color: "hsl(var(--foreground)) !important",
  },
},
  };
  return (
    <PageLayout>

      {/* =====================================================
          PERMISSIONS MODAL
          ===================================================== */}

      <Modal
        opened={
          permissionsModalOpen
        }
        onClose={
          handleClosePermissionsModal
        }
        title={
          selectedRole
            ? `${selectedRole.name} Permissions`
            : "Permissions"
        }
        size="lg"
        styles={modalStyles}
      >
        <Stack gap={16}>

          <ScrollArea h={500}>
            <Table
              style={{
                width: "100%",
                borderCollapse:
                  "collapse",
                fontSize: 13,
              }}
            >
              <Table.Thead>
                <Table.Tr>
                  {[
                    "Module",
                    "Add",
                    "Edit",
                    "View",
                    "Delete",
                  ].map((h) => (
                    <Table.Th
                      key={h}
                      style={{
                        textAlign:
                          "left",

                        padding:
                          "8px 12px",

                        background:
                          "hsl(var(--secondary))",

                        borderBottom:
                          "1px solid hsl(var(--border))",

                        fontWeight:
                          600,

                        fontSize: 12,

                        color:
                          "hsl(var(--foreground))",
                      }}
                    >
                      {h}
                    </Table.Th>
                  ))}
                </Table.Tr>
              </Table.Thead>

              <Table.Tbody>

                {permissionRows.length ===
                0 ? (
                  <Table.Tr>
                    <Table.Td
                      colSpan={5}
                      style={tdBase}
                    >
                      No permissions
                      available.
                    </Table.Td>
                  </Table.Tr>
                ) : (
                  permissionRows.map(
                    (perm, idx) => {
                      const bg =
                        idx % 2 === 1
                          ? "hsl(var(--secondary))"
                          : "transparent";

                      const td = {
                        ...tdBase,
                        background:
                          bg,
                      };

                      return (
                        <Table.Tr
                          key={
                            perm.moduleID
                          }
                        >
                          <Table.Td
                            style={td}
                          >
                            {moduleNameById.get(
                              perm.moduleID
                            ) ||
                              perm.moduleID}
                          </Table.Td>

                          {permissionKeys.map(
                            (key) => (
                              <Table.Td
                                key={key}
                                style={{
                                  ...td,
                                  textAlign:
                                    "center",
                                }}
                              >
                                <Checkbox
  checked={perm[key] === 1}
  onChange={(e) =>
    updatePermission(
      perm.moduleID,
      key,
      e.target.checked
    )
  }
  color="blue"
  styles={{
    input: {
      cursor: "pointer",

      "&:checked": {
        backgroundColor: "#228be6 !important",
        borderColor: "#228be6 !important",
      },
    },

    icon: {
      color: "#ffffff !important",
    },
  }}

                                />
                              </Table.Td>
                            )
                          )}
                        </Table.Tr>
                      );
                    }
                  )
                )}

              </Table.Tbody>
            </Table>
          </ScrollArea>

          <Group justify="flex-end">

            <Button
              variant="default"
              onClick={
                handleClosePermissionsModal
              }
              styles={{
                root: {
                  background:
                    "hsl(var(--background))",

                  border:
                    "1px solid hsl(var(--border))",

                  color:
                    "hsl(var(--foreground))",

                  "&:hover": {
                    background:
                      "hsl(var(--muted))",

                    color:
                      "hsl(var(--foreground))",
                  },
                },
              }}
            >
              Close
            </Button>

            <Button
              onClick={
                handlePermissionsSubmit
              }
              loading={
                permissionsSaving
              }
              disabled={
                permissionsSaving
              }
              styles={{
                root: {
                  background:
                    "hsl(var(--primary))",

                  color:
                    "hsl(var(--primary-foreground))",

                  "&:hover": {
                    background:
                      "hsl(var(--primary))",

                    filter:
                      "brightness(0.95)",
                  },
                },
              }}
            >
              {permissionsSaving
                ? "Saving..."
                : "Save"}
            </Button>

          </Group>
        </Stack>
      </Modal>

      {/* =====================================================
          CREATE / EDIT ROLE MODAL
          ===================================================== */}

      <Modal
        opened={opened}
        onClose={handleCloseModal}
        title={
          selectedRole
            ? "Edit Role"
            : "Create Role"
        }
        size="lg"
        styles={modalStyles}
      >
        <form
          onSubmit={handleSubmit}
        >
          <Stack gap={16}>

            <Grid gutter={12}>

              {/* Role Name */}

              <Grid.Col span={6}>
                <TextInput
                  label="Role Name"
                  placeholder="Enter role name"
                  value={form.name}
                  onChange={(e) =>
                    setForm((p) => ({
                      ...p,

                      name:
                        e.target.value,
                    }))
                  }
                  styles={
                    inputStyles()
                  }
                />
              </Grid.Col>

              {/* Level */}

              <Grid.Col span={6}>
                <NumberInput
                  label="Level"
                  placeholder="Enter level"
                  min={1}
                  value={
                    form.level === ""
                      ? ""
                      : Number(
                          form.level
                        )
                  }
                  onChange={(val) =>
                    setForm((p) => ({
                      ...p,

                      level:
                        val === ""
                          ? ""
                          : String(
                              val
                            ),
                    }))
                  }
                  styles={
                    inputStyles()
                  }
                />
              </Grid.Col>

              {/* Description */}

              <Grid.Col span={12}>
                <Textarea
                  label="Description"
                  placeholder="Enter description"
                  value={
                    form.description
                  }
                  onChange={(e) =>
                    setForm((p) => ({
                      ...p,

                      description:
                        e.target.value,
                    }))
                  }
                  minRows={3}
                  autosize
                  styles={
                    inputStyles()
                  }
                />
              </Grid.Col>

              {/* Super User */}

              <Grid.Col span={6}>
                <Select
                  label="Super User"
                  placeholder="Select"
                  data={[
                    {
                      value: "0",
                      label: "No",
                    },
                    {
                      value: "1",
                      label: "Yes",
                    },
                  ]}
                  value={
                    form.isSuperUser ===
                    undefined
                      ? null
                      : form.isSuperUser
                        ? "1"
                        : "0"
                  }
                  onChange={(val) =>
                    setForm((p) => ({
                      ...p,

                      isSuperUser:
                        val === "1",
                    }))
                  }
                  styles={
                    inputStyles()
                  }
                />
              </Grid.Col>

              {/* Status */}

              <Grid.Col span={6}>
                <Select
                  label="Status"
                  placeholder="Select"
                  data={[
                    {
                      value: "1",
                      label: "Active",
                    },
                    {
                      value: "0",
                      label:
                        "Inactive",
                    },
                  ]}
                  value={
                    form.active || null
                  }
                  onChange={(val) =>
                    setForm((p) => ({
                      ...p,

                      active:
                        val ?? "",
                    }))
                  }
                  styles={
                    inputStyles()
                  }
                />
              </Grid.Col>

            </Grid>

            {/* Actions */}

            <Group justify="flex-end">

              <Button
                variant="default"
                onClick={
                  handleCloseModal
                }
                styles={{
                  root: {
                    background:
                      "hsl(var(--background))",

                    border:
                      "1px solid hsl(var(--border))",

                    color:
                      "hsl(var(--foreground))",

                    "&:hover": {
                      background:
                        "hsl(var(--muted))",

                      color:
                        "hsl(var(--foreground))",
                    },
                  },
                }}
              >
                Cancel
              </Button>

              <Button
                type="submit"
                loading={saving}
                disabled={saving}
                styles={{
                  root: {
                    background:
                      "hsl(var(--primary))",

                    color:
                      "hsl(var(--primary-foreground))",

                    "&:hover": {
                      background:
                        "hsl(var(--primary))",

                      filter:
                        "brightness(0.95)",
                    },
                  },
                }}
              >
                {saving
                  ? "Saving..."
                  : selectedRole
                    ? "Update"
                    : "Submit"}
              </Button>

            </Group>
          </Stack>
        </form>
      </Modal>

      {/* =====================================================
          HEADER CARD
          ===================================================== */}

      <Box
        mb={12}
        p={16}
        style={{
          border:
            "1px solid hsl(var(--border))",

          borderRadius: 8,

          background:
            "hsl(var(--card))",
        }}
      >
        <Group
          justify="space-between"
          align="center"
        >

          <Group
            gap={8}
            align="center"
          >
            <Title
              order={4}
              style={{
                color:
                  "hsl(var(--foreground))",

                margin: 0,
              }}
            >
              Role Management
            </Title>

            <Badge
              style={{
                background:
                  "hsl(var(--secondary))",

                color:
                  "hsl(var(--secondary-foreground))",

                borderRadius: 99,
              }}
              size="md"
            >
              {roles.length}
            </Badge>
          </Group>

          <Button
            size="xs"
            leftSection={
              <IconPlus size={14} />
            }
            onClick={
              handleOpenCreate
            }
            disabled={!canCreateRole}
            styles={{
              root: {
                background:
                  "hsl(var(--primary))",

                color:
                  "hsl(var(--primary-foreground))",

                opacity:
                  canCreateRole
                    ? 1
                    : 0.5,

                cursor:
                  canCreateRole
                    ? "pointer"
                    : "not-allowed",

                "&:hover": {
                  background:
                    "hsl(var(--primary))",
                },
              },
            }}
          >
            Create
          </Button>

        </Group>
      </Box>

      {/* =====================================================
          TABLE CARD
          ===================================================== */}

      <Box
        p={16}
        style={{
          border:
            "1px solid hsl(var(--border))",

          borderRadius: 8,

          background:
            "hsl(var(--card))",
        }}
      >
        <ScrollArea mah={500}>

          <Table
            style={{
              width: "100%",
              borderCollapse:
                "collapse",
              fontSize: 13,
            }}
          >

            <Table.Thead>
              <Table.Tr>

                {[
                  "Role Name",
                  "Description",
                  "Status",
                  "Actions",
                ].map((h) => (
                  <Table.Th
                    key={h}
                    style={{
                      textAlign:
                        "left",

                      padding:
                        "8px 12px",

                      background:
                        "hsl(var(--secondary))",

                      borderBottom:
                        "1px solid hsl(var(--border))",

                      fontWeight:
                        600,

                      fontSize: 12,

                      color:
                        "hsl(var(--foreground))",
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
                  <Table.Td
                    colSpan={4}
                    style={{
                      padding:
                        "40px 12px",

                      border: "none",
                    }}
                  >
                    <Center>
                      <Loader
                        size="sm"
                        color="hsl(var(--primary))"
                      />
                    </Center>
                  </Table.Td>
                </Table.Tr>
              ) : error ? (
                <Table.Tr>
                  <Table.Td
                    colSpan={4}
                    style={{
                      padding:
                        "40px 12px",

                      border: "none",
                    }}
                  >
                    <Center>
                      <Text
                        size="sm"
                        style={{
                          color:
                            "hsl(var(--destructive))",
                        }}
                      >
                        {error}
                      </Text>
                    </Center>
                  </Table.Td>
                </Table.Tr>
              ) : roles.length === 0 ? (
                <Table.Tr>
                  <Table.Td
                    colSpan={4}
                    style={tdBase}
                  >
                    No roles found.
                  </Table.Td>
                </Table.Tr>
              ) : (
                paginatedRoles.map(
                  (role, idx) => {
                    const bg =
                      idx % 2 === 1
                        ? "hsl(var(--secondary))"
                        : "transparent";

                    const td = {
                      ...tdBase,
                      background:
                        bg,
                    };

                    return (
                      <Table.Tr
                        key={role._id}
                      >

                        <Table.Td
                          style={td}
                        >
                          <Text
                            size="sm"
                            style={{
                              color:
                                "hsl(var(--foreground))",
                            }}
                          >
                            {role.name}
                          </Text>
                        </Table.Td>

                        <Table.Td
                          style={td}
                        >
                          <Text
                            size="sm"
                            style={{
                              color:
                                "hsl(var(--foreground))",
                            }}
                          >
                            {
                              role.description
                            }
                          </Text>
                        </Table.Td>

                        <Table.Td
                          style={td}
                        >
                          <Text
                            size="sm"
                            style={{
                              color:
                                "hsl(var(--foreground))",
                            }}
                          >
                            {role.active ===
                            1
                              ? "Active"
                              : "Inactive"}
                          </Text>
                        </Table.Td>

                        <Table.Td
                          style={td}
                        >
                          <Group gap={8}>

                            {/* Permissions */}

                            <Box
                              component="span"
                              style={{
                                cursor:
                                  "pointer",

                                color:
                                  "hsl(var(--muted-foreground))",

                                display:
                                  "inline-flex",
                              }}
                              onClick={() =>
                                handleOpenPermissions(
                                  role
                                )
                              }
                              title="Permissions"
                            >
                              <IconLock
                                size={18}
                              />
                            </Box>

                            {/* Edit */}

                            <Box
                              component="span"
                              style={{
                                cursor:
                                  canEditRole
                                    ? "pointer"
                                    : "not-allowed",

                                color:
                                  "hsl(var(--muted-foreground))",

                                display:
                                  "inline-flex",

                                opacity:
                                  canEditRole
                                    ? 1
                                    : 0.4,
                              }}
                              onClick={() =>
                                handleOpenEdit(
                                  role
                                )
                              }
                              title={
                                canEditRole
                                  ? "Edit"
                                  : "No Access"
                              }
                              aria-disabled={
                                !canEditRole
                              }
                            >
                              <IconEdit
                                size={18}
                              />
                            </Box>

                          </Group>
                        </Table.Td>

                      </Table.Tr>
                    );
                  }
                )
              )}

            </Table.Tbody>
          </Table>

        </ScrollArea>

        {/* =====================================================
            PAGINATION
            ===================================================== */}

        <Group
          justify="space-between"
          align="center"
          mt={12}
          gap={12}
          wrap="wrap"
        >

          <Group
            gap={8}
            align="center"
          >

            <Text
              size="sm"
              style={{
                color:
                  "hsl(var(--muted-foreground))",
              }}
            >
              Records per page
            </Text>

            <Select
              data={[
                "10",
                "20",
                "30",
              ]}
              value={String(
                pageSize
              )}
              onChange={(value) =>
                setPageSize(
                  Number(
                    value ?? "10"
                  )
                )
              }
              w={70}
              styles={{
                input: {
                  background:
                    "hsl(var(--background))",

                  border:
                    "1px solid hsl(var(--border))",

                  color:
                    "hsl(var(--foreground))",

                  cursor:
                    "pointer",

                  "&:hover": {
                    background:
                      "hsl(var(--background))",

                    borderColor:
                      "hsl(var(--border))",

                    color:
                      "hsl(var(--foreground))",
                  },
                },

                dropdown: {
                  background:
                    "hsl(var(--card)) !important",

                  border:
                    "1px solid hsl(var(--border))",

                  color:
                    "hsl(var(--foreground)) !important",
                },

                option: {
                  background:
                    "hsl(var(--card)) !important",

                  color:
                    "hsl(var(--foreground)) !important",

                  "&:hover": {
                    background:
                      "hsl(var(--muted)) !important",

                    color:
                      "hsl(var(--foreground)) !important",
                  },

                  "&[data-combobox-active]": {
                    background:
                      "hsl(var(--muted)) !important",

                    color:
                      "hsl(var(--foreground)) !important",
                  },

                  "&[data-combobox-selected]": {
                    background:
                      "hsl(var(--muted)) !important",

                    color:
                      "hsl(var(--foreground)) !important",
                  },
                },
              }}
            />

          </Group>

          <Pagination
            value={page}
            onChange={setPage}
            total={totalPages}
            size="sm"
            styles={{
              control: {
                background:
                  "hsl(var(--background))",

                borderColor:
                  "hsl(var(--border))",

                color:
                  "hsl(var(--foreground))",

                "&:hover": {
                  background:
                    "hsl(var(--muted))",

                  color:
                    "hsl(var(--foreground))",
                },

                "&[data-active]": {
                  background:
                    "hsl(var(--primary))",

                  borderColor:
                    "hsl(var(--primary))",

                  color:
                    "hsl(var(--primary-foreground))",
                },
              },
            }}
          />

        </Group>
      </Box>
    </PageLayout>
  );
};

export default RolePage;