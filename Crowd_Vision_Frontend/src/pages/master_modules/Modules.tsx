import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { IconPlus, IconEdit } from "@tabler/icons-react";
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

const getRowLabel = (item: ModuleItem) => (item.active ? "Active" : "Inactive");

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

const inputStyles = () => ({
  label: { color: "#cfcfcf", fontSize: 13, fontWeight: 500, marginBottom: 6 },
  input: {
    background: "#2a2a2a",
    border: "1px solid #444",
    color: "#fff",
    "&:focus": { borderColor: "#228be6" },
  },
});

const tdBase: React.CSSProperties = {
  padding: "8px",
  borderBottom: "1px solid #333",
  color: "#eee",
};

const ModulePage = () => {
  const { hasModulePermission } = useAuth();
  const [opened, setOpened] = useState(false);
  const [editing, setEditing] = useState<ModuleItem | null>(null);
  const [modules, setModules] = useState<ModuleItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<ModuleFormState>(emptyForm);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const canCreateModule = hasModulePermission("/modules", "add");
  const canEditModule = hasModulePermission("/modules", "edit");

  useEffect(() => {
    let isMounted = true;
    const loadModules = async () => {
      setLoading(true);
      setError("");
      try {
        const response = await modulesApi.getModules();
        if (!isMounted) return;
        setModules(response.modules || []);
      } catch (err) {
        if (!isMounted) return;
        setError(err instanceof Error ? err.message : "Failed to load modules");
      } finally {
        if (isMounted) setLoading(false);
      }
    };
    loadModules();
    return () => { isMounted = false; };
  }, []);

  useEffect(() => {
    setPage(1);
  }, [pageSize]);

  useEffect(() => {
    const totalPages = Math.max(1, Math.ceil(modules.length / pageSize));
    setPage((current) => Math.min(current, totalPages));
  }, [modules.length, pageSize]);

  const resetForm = () => {
    setEditing(null);
    setForm(emptyForm);
  };

  const openCreateModal = () => {
    if (!canCreateModule) { toast.error("No Access"); return; }
    resetForm();
    setOpened(true);
  };

  const openEditModal = (module: ModuleItem) => {
    if (!canEditModule) { toast.error("No Access"); return; }
    setEditing(module);
    setForm({
      name: module.name ?? "",
      description: module.description ?? "",
      urlName: module.urlName ?? "",
      master: module.master ? "true" : "false",
      active: String(module.active),
    });
    setOpened(true);
  };

  const handleClose = () => {
    setOpened(false);
    resetForm();
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!form.name.trim() || !form.description.trim() || !form.urlName.trim() || !form.master || !form.active) {
      toast.error("Please fill in all required module fields.");
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
        ? await modulesApi.updateModule(editing._id, payload)
        : await modulesApi.createModule(payload);
      const savedModule = response.module;
      setModules((prev) =>
        editing
          ? prev.map((m) => (m._id === savedModule._id ? savedModule : m))
          : [savedModule, ...prev],
      );
      toast.success(response.responseMsg);
      handleClose();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save module");
    } finally {
      setSaving(false);
    }
  };

  const totalPages = Math.max(1, Math.ceil(modules.length / pageSize));
  const paginatedModules = modules.slice((page - 1) * pageSize, page * pageSize);

  return (
    <PageLayout>
      {/* ── Modal ── */}
      <Modal
        opened={opened}
        onClose={handleClose}
        title={editing ? "Edit Module" : "Create Module"}
        size="lg"
        styles={{
          content: { background: "#1a1a1a", border: "1px solid #333" },
          header: { background: "#1a1a1a" },
          title: { color: "#fff", fontWeight: 600, fontSize: 16 },
          close: { color: "#aaa" },
        }}
      >
        <form onSubmit={handleSubmit}>
          <Stack gap={16}>
            <Grid gutter={12}>
              <Grid.Col span={6}>
                <TextInput
                  label="Module Name"
                  placeholder="Enter module name"
                  value={form.name}
                  onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                  styles={inputStyles()}
                />
              </Grid.Col>

              <Grid.Col span={6}>
                <TextInput
                  label="URL Name"
                  placeholder="Enter route path (e.g. /users)"
                  value={form.urlName}
                  onChange={(e) => setForm((p) => ({ ...p, urlName: e.target.value }))}
                  styles={inputStyles()}
                />
              </Grid.Col>

              <Grid.Col span={6}>
                <Select
                  label="Master Module"
                  placeholder="Select"
                  data={[
                    { value: "false", label: "No" },
                    { value: "true", label: "Yes" },
                  ]}
                  value={form.master || null}
                  onChange={(val) => setForm((p) => ({ ...p, master: val ?? "" }))}
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

              <Grid.Col span={12}>
                <Textarea
                  label="Description"
                  placeholder="Enter module description"
                  value={form.description}
                  onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
                  minRows={3}
                  autosize
                  styles={inputStyles()}
                />
              </Grid.Col>
            </Grid>

            <Group justify="flex-end" mt={4}>
              <Button
                variant="default"
                onClick={handleClose}
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
                {saving ? "Saving..." : editing ? "Update" : "Submit"}
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
            <Title order={4} style={{ color: "#fff", margin: 0 }}>Module Management</Title>
            <Badge
              style={{ background: "#333", color: "#d0d0d0", borderRadius: 99 }}
              size="md"
            >
              {modules.length}
            </Badge>
          </Group>

          <Button
            size="xs"
            leftSection={<IconPlus size={14} />}
            onClick={openCreateModal}
            disabled={!canCreateModule}
            title={canCreateModule ? "Create" : "No Access"}
            styles={{
              root: {
                background: "#228be6",
                opacity: canCreateModule ? 1 : 0.5,
                cursor: canCreateModule ? "pointer" : "not-allowed",
              },
            }}
          >
            Create
          </Button>
        </Group>
      </Box>

      {/* ── Table card ── */}
      <Box p={16} style={{ border: "1px solid #333", borderRadius: 8, background: "#1a1a1a" }}>
        <Table style={{ width: "100%", borderCollapse: "collapse" }}>
          <Table.Thead>
            <Table.Tr>
              {["Name", "Route", "Description", "Status", "Actions"].map((h) => (
                <Table.Th
                  key={h}
                  style={{ textAlign: "left", padding: "8px", background: "#111", color: "#aaa" }}
                >
                  {h}
                </Table.Th>
              ))}
            </Table.Tr>
          </Table.Thead>

          <Table.Tbody>
            {loading ? (
              <Table.Tr>
                <Table.Td colSpan={5} style={{ padding: "40px 8px", border: "none" }}>
                  <Center>
                    <Loader size="sm" color="#228be6" />
                  </Center>
                </Table.Td>
              </Table.Tr>
            ) : error ? (
              <Table.Tr>
                <Table.Td colSpan={5} style={{ padding: "40px 8px", border: "none" }}>
                  <Center>
                    <Text size="sm" c="#ff8f8f">{error}</Text>
                  </Center>
                </Table.Td>
              </Table.Tr>
            ) : modules.length === 0 ? (
              <Table.Tr>
                <Table.Td colSpan={5} style={{ ...tdBase, textAlign: "center" }}>
                  No modules found.
                </Table.Td>
              </Table.Tr>
            ) : (
              paginatedModules.map((m, i) => {
                const bg = i % 2 ? "#222" : "transparent";
                const td = { ...tdBase, background: bg };
                return (
                  <Table.Tr key={m._id}>
                    <Table.Td style={td}>{m.name}</Table.Td>
                    <Table.Td style={td}>{m.urlName}</Table.Td>
                    <Table.Td style={td}>{m.description}</Table.Td>
                    <Table.Td style={td}>{getRowLabel(m)}</Table.Td>
                    <Table.Td style={td}>
                      <Box
                        component="span"
                        style={{
                          cursor: canEditModule ? "pointer" : "not-allowed",
                          color: "#aaa",
                          opacity: canEditModule ? 1 : 0.4,
                        }}
                        onClick={() => openEditModal(m)}
                        aria-disabled={!canEditModule}
                        title={canEditModule ? "Edit" : "No Access"}
                      >
                        <IconEdit size={18} />
                      </Box>
                    </Table.Td>
                  </Table.Tr>
                );
              })
            )}
          </Table.Tbody>
        </Table>

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

export default ModulePage;
