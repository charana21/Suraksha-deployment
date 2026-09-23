import { useEffect, useState } from "react";

import type { FormEvent, CSSProperties } from "react";

import {
  IconPlus,
  IconEdit,
} from "@tabler/icons-react";

import { toast } from "sonner";

import {
  Badge,
  Box,
  Button,
  Center,
  Grid,
  Group,
  Loader,
  Modal,
  Pagination,
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
  type ModulePayload,
} from "../../services/modules";

import { PageLayout } from "@/components/layout/PageLayout";

/* =========================================================
   HELPERS
   ========================================================= */

const getRowLabel = (item: ModuleItem) =>
  item.active ? "Active" : "Inactive";

type ModuleFormState = {
  name: string;
  description: string;
  urlName: string;
  master: string;
  active: string;
};

const emptyForm: ModuleFormState = {
  name: "",
  description: "",
  urlName: "",
  master: "",
  active: "",
};

/* =========================================================
   THEME-SAFE INPUT STYLES
   ========================================================= */

const inputStyles = () => ({
  label: {
    color: "hsl(var(--foreground))",
    fontSize: 13,
    fontWeight: 500,
    marginBottom: 6,
  },

  input: {
    background: "hsl(var(--background))",
    border: "1px solid hsl(var(--border))",
    color: "hsl(var(--foreground))",

    "&:focus": {
      borderColor: "hsl(var(--primary))",
    },

    "&:hover": {
      borderColor: "hsl(var(--border))",
    },
  },

  textarea: {
    background: "hsl(var(--background))",
    border: "1px solid hsl(var(--border))",
    color: "hsl(var(--foreground))",

    "&:focus": {
      borderColor: "hsl(var(--primary))",
    },

    "&:hover": {
      borderColor: "hsl(var(--border))",
    },
  },

  /* Mantine Select dropdown */
  dropdown: {
    background: "hsl(var(--card)) !important",
    border: "1px solid hsl(var(--border))",
    color: "hsl(var(--foreground)) !important",
    boxShadow: "0 8px 24px rgba(0, 0, 0, 0.15)",
  },

  /* Mantine Select options */
  option: {
    background: "hsl(var(--card)) !important",
    color: "hsl(var(--foreground)) !important",

    "&:hover": {
      background: "hsl(var(--muted)) !important",
      color: "hsl(var(--foreground)) !important",
    },

    "&[data-combobox-active]": {
      background: "hsl(var(--muted)) !important",
      color: "hsl(var(--foreground)) !important",
    },

    "&[data-combobox-selected]": {
      background: "hsl(var(--muted)) !important",
      color: "hsl(var(--foreground)) !important",
    },
  },
});

/* =========================================================
   TABLE CELL BASE STYLE
   ========================================================= */

const tdBase: CSSProperties = {
  padding: "8px",
  borderBottom: "1px solid hsl(var(--border))",
  color: "hsl(var(--foreground))",
};

/* =========================================================
   COMPONENT
   ========================================================= */

const ModulePage = () => {
  const { hasModulePermission } = useAuth();

  const [opened, setOpened] = useState(false);

  const [editing, setEditing] =
    useState<ModuleItem | null>(null);

  const [modules, setModules] =
    useState<ModuleItem[]>([]);

  const [loading, setLoading] = useState(true);

  const [error, setError] = useState("");

  const [saving, setSaving] = useState(false);

  const [form, setForm] =
    useState<ModuleFormState>(emptyForm);

  const [page, setPage] = useState(1);

  const [pageSize, setPageSize] =
    useState(10);

  const canCreateModule =
    hasModulePermission("/modules", "add");

  const canEditModule =
    hasModulePermission("/modules", "edit");

  /* =========================================================
     LOAD MODULES
     ========================================================= */

  useEffect(() => {
    let isMounted = true;

    const loadModules = async () => {
      setLoading(true);
      setError("");

      try {
        const response =
          await modulesApi.getModules();

        if (!isMounted) return;

        setModules(response.modules || []);
      } catch (err) {
        if (!isMounted) return;

        setError(
          err instanceof Error
            ? err.message
            : "Failed to load modules"
        );
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    loadModules();

    return () => {
      isMounted = false;
    };
  }, []);

  /* =========================================================
     PAGE SIZE
     ========================================================= */

  useEffect(() => {
    setPage(1);
  }, [pageSize]);

  /* =========================================================
     KEEP PAGE VALID
     ========================================================= */

  useEffect(() => {
    const totalPages = Math.max(
      1,
      Math.ceil(
        modules.length / pageSize
      )
    );

    setPage((current) =>
      Math.min(current, totalPages)
    );
  }, [modules.length, pageSize]);

  /* =========================================================
     FORM
     ========================================================= */

  const resetForm = () => {
    setEditing(null);
    setForm(emptyForm);
  };

  const openCreateModal = () => {
    if (!canCreateModule) {
      toast.error("No Access");
      return;
    }

    resetForm();
    setOpened(true);
  };

  const openEditModal = (
    module: ModuleItem
  ) => {
    if (!canEditModule) {
      toast.error("No Access");
      return;
    }

    setEditing(module);

    setForm({
      name: module.name ?? "",
      description: module.description ?? "",
      urlName: module.urlName ?? "",
      master: module.master
        ? "true"
        : "false",
      active: String(module.active),
    });

    setOpened(true);
  };

  const handleClose = () => {
    setOpened(false);
    resetForm();
  };

  /* =========================================================
     SUBMIT
     ========================================================= */

  const handleSubmit = async (
    e: FormEvent<HTMLFormElement>
  ) => {
    e.preventDefault();

    if (
      !form.name.trim() ||
      !form.description.trim() ||
      !form.urlName.trim() ||
      !form.master ||
      !form.active
    ) {
      toast.error(
        "Please fill in all required module fields."
      );
      return;
    }

    const payload: ModulePayload = {
      name: form.name.trim(),
      description: form.description.trim(),
      urlName: form.urlName.trim(),
      master: form.master === "true",
      active: Number(form.active),
    };

    setSaving(true);

    try {
      const response = editing
        ? await modulesApi.updateModule(
            editing._id,
            payload
          )
        : await modulesApi.createModule(
            payload
          );

      const savedModule = response.module;

      setModules((prev) =>
        editing
          ? prev.map((m) =>
              m._id === savedModule._id
                ? savedModule
                : m
            )
          : [savedModule, ...prev]
      );

      toast.success(response.responseMsg);

      handleClose();
    } catch (err) {
      toast.error(
        err instanceof Error
          ? err.message
          : "Failed to save module"
      );
    } finally {
      setSaving(false);
    }
  };

  /* =========================================================
     PAGINATION DATA
     ========================================================= */

  const totalPages = Math.max(
    1,
    Math.ceil(
      modules.length / pageSize
    )
  );

  const paginatedModules =
    modules.slice(
      (page - 1) * pageSize,
      page * pageSize
    );

  /* =========================================================
     MODAL STYLES
     ========================================================= */

  const modalStyles = {
    content: {
      background: "hsl(var(--card))",
      border: "1px solid hsl(var(--border))",
    },

    header: {
      background: "hsl(var(--card))",
      color: "hsl(var(--foreground))",
    },

    body: {
      background: "hsl(var(--card))",
      color: "hsl(var(--foreground))",
    },

    title: {
      color: "hsl(var(--foreground))",
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
          MODAL
          ===================================================== */}

      <Modal
        opened={opened}
        onClose={handleClose}
        title={
          editing
            ? "Edit Module"
            : "Create Module"
        }
        size="lg"
        styles={modalStyles}
      >
        <form onSubmit={handleSubmit}>
          <Stack gap={16}>

            <Grid gutter={12}>

              {/* Module Name */}

              <Grid.Col span={6}>
                <TextInput
                  label="Module Name"
                  placeholder="Enter module name"
                  value={form.name}
                  onChange={(e) =>
                    setForm((p) => ({
                      ...p,
                      name: e.target.value,
                    }))
                  }
                  styles={inputStyles()}
                />
              </Grid.Col>

              {/* URL Name */}

              <Grid.Col span={6}>
                <TextInput
                  label="URL Name"
                  placeholder="Enter route path (e.g. /users)"
                  value={form.urlName}
                  onChange={(e) =>
                    setForm((p) => ({
                      ...p,
                      urlName:
                        e.target.value,
                    }))
                  }
                  styles={inputStyles()}
                />
              </Grid.Col>

              {/* Master Module */}

              <Grid.Col span={6}>
                <Select
                  label="Master Module"
                  placeholder="Select"
                  data={[
                    {
                      value: "false",
                      label: "No",
                    },
                    {
                      value: "true",
                      label: "Yes",
                    },
                  ]}
                  value={
                    form.master || null
                  }
                  onChange={(val) =>
                    setForm((p) => ({
                      ...p,
                      master: val ?? "",
                    }))
                  }
                  styles={inputStyles()}
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
                      label: "Inactive",
                    },
                  ]}
                  value={
                    form.active || null
                  }
                  onChange={(val) =>
                    setForm((p) => ({
                      ...p,
                      active: val ?? "",
                    }))
                  }
                  styles={inputStyles()}
                />
              </Grid.Col>

              {/* Description */}

              <Grid.Col span={12}>
                <Textarea
                  label="Description"
                  placeholder="Enter module description"
                  value={form.description}
                  onChange={(e) =>
                    setForm((p) => ({
                      ...p,
                      description:
                        e.target.value,
                    }))
                  }
                  minRows={3}
                  autosize
                  styles={inputStyles()}
                />
              </Grid.Col>

            </Grid>

            {/* Actions */}

            <Group
              justify="flex-end"
              mt={4}
            >
              <Button
                variant="default"
                onClick={handleClose}
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
                  : editing
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
              Module Management
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
              {modules.length}
            </Badge>
          </Group>

          <Button
            size="xs"
            leftSection={
              <IconPlus size={14} />
            }
            onClick={openCreateModal}
            disabled={!canCreateModule}
            styles={{
              root: {
                background:
                  "hsl(var(--primary))",
                color:
                  "hsl(var(--primary-foreground))",
                opacity:
                  canCreateModule
                    ? 1
                    : 0.5,
                cursor:
                  canCreateModule
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
        <Table
          style={{
            width: "100%",
            borderCollapse:
              "collapse",
          }}
        >
          <Table.Thead>
            <Table.Tr>

              {[
                "Name",
                "Route",
                "Description",
                "Status",
                "Actions",
              ].map((h) => (
                <Table.Th
                  key={h}
                  style={{
                    textAlign: "left",
                    padding: "8px",
                    background:
                      "hsl(var(--secondary))",
                    color:
                      "hsl(var(--foreground))",
                    borderBottom:
                      "1px solid hsl(var(--border))",
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
                  colSpan={5}
                  style={{
                    padding:
                      "40px 8px",
                    border: "none",
                  }}
                >
                  <Center>
                    <Loader
                      size="sm"
                      color="var(--primary)"
                    />
                  </Center>
                </Table.Td>
              </Table.Tr>
            ) : error ? (
              <Table.Tr>
                <Table.Td
                  colSpan={5}
                  style={{
                    padding:
                      "40px 8px",
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
            ) : modules.length === 0 ? (
              <Table.Tr>
                <Table.Td
                  colSpan={5}
                  style={{
                    ...tdBase,
                    textAlign:
                      "center",
                  }}
                >
                  No modules found.
                </Table.Td>
              </Table.Tr>
            ) : (
              paginatedModules.map(
                (m, i) => {
                  const bg =
                    i % 2
                      ? "hsl(var(--secondary))"
                      : "transparent";

                  const td = {
                    ...tdBase,
                    background: bg,
                  };

                  return (
                    <Table.Tr
                      key={m._id}
                    >
                      <Table.Td
                        style={td}
                      >
                        {m.name}
                      </Table.Td>

                      <Table.Td
                        style={td}
                      >
                        {m.urlName}
                      </Table.Td>

                      <Table.Td
                        style={td}
                      >
                        {m.description}
                      </Table.Td>

                      <Table.Td
                        style={td}
                      >
                        {getRowLabel(m)}
                      </Table.Td>

                      <Table.Td
                        style={td}
                      >
                        <Box
                          component="span"
                          style={{
                            cursor:
                              canEditModule
                                ? "pointer"
                                : "not-allowed",

                            color:
                              "hsl(var(--muted-foreground))",

                            opacity:
                              canEditModule
                                ? 1
                                : 0.4,

                            display:
                              "inline-flex",
                          }}
                          onClick={() =>
                            openEditModal(m)
                          }
                          aria-disabled={
                            !canEditModule
                          }
                          title={
                            canEditModule
                              ? "Edit"
                              : "No Access"
                          }
                        >
                          <IconEdit
                            size={18}
                          />
                        </Box>
                      </Table.Td>
                    </Table.Tr>
                  );
                }
              )
            )}

          </Table.Tbody>
        </Table>

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
              value={String(pageSize)}
              onChange={(value) =>
                setPageSize(
                  Number(value ?? "10")
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
                  cursor: "pointer",

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
                  color:
                    "hsl(var(--primary-foreground))",
                  borderColor:
                    "hsl(var(--primary))",
                },
              },
            }}
          />
        </Group>
      </Box>
    </PageLayout>
  );
};

export default ModulePage;