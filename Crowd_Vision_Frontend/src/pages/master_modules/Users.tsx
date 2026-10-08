import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { IconEdit, IconEye, IconEyeOff, IconPlus } from "@tabler/icons-react";
import { toast } from "sonner";
import PhoneInput from "react-phone-input-2";
import type { CountryData } from "react-phone-input-2";
import "react-phone-input-2/lib/style.css";
import {
  Badge,
  Box,
  Button,
  Center,
  Checkbox,
  Collapse,
  Grid,
  Group,
  Loader,
  Modal,
  PasswordInput,
  Pagination,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  UnstyledButton,
} from "@mantine/core";
import { useAuth } from "@/context/AuthContext";
import { rolesApi, type RoleItem } from "../../services/roles";
import {
  usersApi,
  type UserItem,
  type UserPayload,
} from "../../services/users";
import { PageLayout } from "@/components/layout/PageLayout";

type UserFormState = {
  name: string;
  email: string;
  countryCode: string;
  phone: string;
  roleID: string;
  active: string;
  password: string;
  services: string[];
  gender: string;
};

const emptyForm = (): UserFormState => ({
  name: "",
  email: "",
  countryCode: "+91",
  phone: "",
  roleID: "",
  active: "",
  password: "",
  services: [],
  gender: "",
});

// key = backend value (sent to API), value = display label shown in UI
const SERVICE_LABELS: Record<string, string> = {
  twilio_platform_assigned_content_sid: "Train Information Alerts",
  twilio_train_delay_alert_content_sid: "Platform Change Alerts",
  twilio_whatsapp_booking_office_content_sid: "Booking Office Alerts",
  whatsapp_content_sid: "Fob Congestion Alerts",
  custom_whatsapp_message: "Camera Crowd Alerts",
  suraksha_ai: "Subscription Alerts",
  msg91_whatsapp_island_alert_template_id: "Island Alerts",
  msg91_whatsapp_fob_alert_template_id: "FOB Alerts",
};

// Returns the display label for a backend key (falls back to the key itself)
const getServiceLabel = (key: string): string => SERVICE_LABELS[key] ?? key;

const UserPage = () => {
  const { hasModulePermission } = useAuth();
  const [opened, setOpened] = useState(false);
  const [editingUser, setEditingUser] = useState<UserItem | null>(null);
  const [users, setUsers] = useState<UserItem[]>([]);
  const [roles, setRoles] = useState<RoleItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [rolesLoading, setRolesLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [rolesError, setRolesError] = useState("");
  const [form, setForm] = useState<UserFormState>(emptyForm());
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const canCreateUser = hasModulePermission("/user", "add");
  const canEditUser = hasModulePermission("/user", "edit");
  const [servicesOpen, setServicesOpen] = useState(false);
  const [phoneSource, setPhoneSource] = useState("");
  const servicesRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (servicesRef.current && !servicesRef.current.contains(e.target as Node)) {
        setServicesOpen(false);
      }
    };
    if (servicesOpen) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [servicesOpen]);

  useEffect(() => {
    let isMounted = true;
    const loadUsers = async () => {
      setLoading(true);
      setError("");
      try {
        const response = await usersApi.getUsers();
        if (!isMounted) return;
        setUsers(response.users || []);
      } catch (err) {
        if (!isMounted) return;
        setError(err instanceof Error ? err.message : "Failed to load users");
      } finally {
        if (isMounted) setLoading(false);
      }
    };
    loadUsers();
    return () => { isMounted = false; };
  }, []);

  useEffect(() => {
    let isMounted = true;
    const loadRoles = async () => {
      setRolesLoading(true);
      setRolesError("");
      try {
        const response = await rolesApi.getRoles();
        if (!isMounted) return;
        setRoles(response.roles || []);
      } catch (err) {
        if (!isMounted) return;
        setRolesError(err instanceof Error ? err.message : "Failed to load roles");
      } finally {
        if (isMounted) setRolesLoading(false);
      }
    };
    loadRoles();
    return () => { isMounted = false; };
  }, []);

  useEffect(() => {
    setPage(1);
  }, [pageSize]);

  useEffect(() => {
    const totalPages = Math.max(1, Math.ceil(users.length / pageSize));
    setPage((current) => Math.min(current, totalPages));
  }, [users.length, pageSize]);

  const roleNameById = useMemo(
    () => new Map(roles.map((role) => [role._id, role.name])),
    [roles],
  );

  const handleOpenCreate = () => {
    if (!canCreateUser) { toast.error("No Access"); return; }
    setEditingUser(null);
    setForm(emptyForm());
    setPhoneSource("");
    setOpened(true);
  };

  const handleEdit = (user: UserItem) => {
    if (!canEditUser) { toast.error("No Access"); return; }
    setEditingUser(user);

    setForm({
      name: user.name,
      email: user.email,
      countryCode: "+91",
      phone: "",
      roleID: user.roleID,
      active: String(user.active),
      password: "........",
      services: user.services || [],
      gender: user.gender || "",
    });
    setPhoneSource(user.phone);
    setOpened(true);
  };

  const handleClose = () => {
    setOpened(false);
    setEditingUser(null);
    setForm(emptyForm());
    setPhoneSource("");
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (
      !form.name.trim() ||
      !form.email.trim() ||
      !form.phone.trim() ||
      !form.roleID ||
      !form.active
    ) {
      toast.error("Please fill in all required user fields.");
      return;
    }

    if (!form.password.trim()) {
      toast.error("Password is required.");
      return;
    }

    // Combine country code + local number → E.164 format
    const e164Phone = `${form.countryCode}${form.phone.trim()}`;

    const payload: UserPayload = {
      name: form.name.trim(),
      email: form.email.trim(),
      phone: e164Phone,
      roleID: form.roleID,
      active: Number(form.active),
      services: form.services,
      ...(editingUser ? {} : { password: form.password.trim() }),
      gender: form.gender,
    };

    setSaving(true);
    try {
      const response = editingUser
        ? await usersApi.updateUser(editingUser._id, payload)
        : await usersApi.createUser(payload);

      setUsers((prev) =>
        editingUser
          ? prev.map((u) => (u._id === response.user._id ? response.user : u))
          : [response.user, ...prev],
      );

      toast.success(response.responseMsg);
      handleClose();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save user");
    } finally {
      setSaving(false);
    }
  };

  const roleOptions = roles.map((r) => ({ value: r._id, label: r.name }));
  const totalPages = Math.max(1, Math.ceil(users.length / pageSize));
  const paginatedUsers = users.slice((page - 1) * pageSize, page * pageSize);

  return (
    <PageLayout>
      {/* ── Modal ── */}
      <Modal
        opened={opened}
        onClose={handleClose}
        title={editingUser ? "Edit User" : "Create User"}
        size="lg"
        styles={{
          content: { background: "#1a1a1a", border: "1px solid #333" },
          header: { background: "#1a1a1a" },
          title: { color: "#fff", fontWeight: 600, fontSize: 16 },
          close: { color: "#aaa" },
        }}
      >
        <form onSubmit={handleSubmit}>
          <Stack gap={10}>
            <Grid gutter={12}>
              {/* Name */}
              <Grid.Col span={6}>
                <TextInput
                  label="Name"
                  placeholder="Enter name"
                  value={form.name}
                  onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                  styles={inputStyles()}
                />
              </Grid.Col>
              <Grid.Col span={6}>
                <Select
                  label="Gender"
                  placeholder="Select"
                  data={[
                    { value: "male", label: "Male" },
                    { value: "female", label: "Female" },
                  ]}
                  value={form.gender || null}
                  onChange={(val) => setForm((p) => ({ ...p, gender: val ?? "" }))}
                  styles={inputStyles()}
                />
              </Grid.Col>
              {/* Email */}
              <Grid.Col span={6}>
                <TextInput
                  label="Email"
                  placeholder="Enter email"
                  value={form.email}
                  onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))}
                  disabled={!!editingUser}
                  styles={inputStyles(!!editingUser)}
                />
              </Grid.Col>

              {/* Password */}
              <Grid.Col span={6}>
                <PasswordInput
                  label="Password"
                  placeholder={editingUser ? "Enter password for update" : "Enter password"}
                  value={form.password}
                  onChange={(e) => setForm((p) => ({ ...p, password: e.target.value }))}
                  disabled={!!editingUser}
                  visibilityToggleIcon={({ reveal }) =>
                    reveal ? <IconEyeOff size={18} /> : <IconEye size={18} />
                  }
                  styles={inputStyles(!!editingUser)}
                />
              </Grid.Col>

              {/* Phone — country code + local number */}
<Grid.Col span={12}>
  <Text size="sm" mb={4} style={{ color: "#cfcfcf", fontSize: 13 }}>
    Phone
  </Text>

  <Group gap={8} align="flex-start" wrap="nowrap">
    {phoneSource && (
      <Box style={{ display: "none" }}>
        <PhoneInput
          key={phoneSource}
          country="in"
          value={phoneSource}
          onMount={(value, data: CountryData | {}) => {
            if ("dialCode" in data && data.dialCode) {
              setForm((current) => ({
                ...current,
                countryCode: `+${data.dialCode}`,
                phone: value.slice(data.dialCode.length),
              }));
            }
          }}
        />
      </Box>
    )}

    {/* Country Code Dropdown */}
    <Box
      className="phone-input-dark"
      style={{
        width: 130,
        minWidth: 130,
      }}
    >
      <PhoneInput
        country="in"
        value={form.countryCode.replace("+", "")}
        onChange={(_, data: CountryData | {}) => {
          if ("dialCode" in data && data.dialCode) {
            setForm((current) => ({
              ...current,
              countryCode: `+${data.dialCode}`,
            }));
          }
        }}
        enableSearch
        specialLabel=""
        containerStyle={{
          width: "130px",
        }}
        inputStyle={{
          width: "130px",
          background: "#2a2a2a",
          color: "#fff",
          border: "1px solid #444",
        }}
        buttonStyle={{
          background: "#2a2a2a",
          border: "1px solid #444",
        }}
        dropdownStyle={{
          background: "#1f1f1f",
          color: "#fff",
          border: "1px solid #444",
        }}
        searchStyle={{
          background: "#2a2a2a",
          color: "#fff",
          border: "1px solid #444",
        }}
      />

      <style>{`
        .phone-input-dark .react-tel-input {
          width: 130px !important;
        }

        .phone-input-dark .react-tel-input .form-control {
          width: 130px !important;
          background: #2a2a2a !important;
          color: #fff !important;
          border: 1px solid #444 !important;
          box-shadow: none !important;
        }

        .phone-input-dark .react-tel-input .form-control::placeholder {
          color: #8a8a8a !important;
        }

        .phone-input-dark .react-tel-input .flag-dropdown {
          background: #2a2a2a !important;
          border: 1px solid #444 !important;
        }

        .phone-input-dark .react-tel-input .selected-flag:hover,
        .phone-input-dark .react-tel-input .selected-flag:focus {
          background: #333 !important;
        }

        .phone-input-dark .react-tel-input .country-list {
          background: #1f1f1f !important;
          color: #fff !important;
          border: 1px solid #444 !important;
        }

        .phone-input-dark .react-tel-input .country-list .country {
          background: #1f1f1f !important;
          color: #fff !important;
        }

        .phone-input-dark .react-tel-input .country-list .country:hover,
        .phone-input-dark .react-tel-input .country-list .country.highlight,
        .phone-input-dark .react-tel-input .country-list .country.active {
          background: #2f2f2f !important;
        }

        .phone-input-dark .react-tel-input .country-list .country .dial-code,
        .phone-input-dark .react-tel-input .country-list .country .country-name {
          color: #fff !important;
        }

        .phone-input-dark .react-tel-input .country-list .search {
          background: #2a2a2a !important;
          color: #fff !important;
          border-bottom: 1px solid #444 !important;
        }

        .phone-input-dark .react-tel-input .country-list .search::placeholder {
          color: #8a8a8a !important;
        }
      `}</style>
    </Box>

    {/* Phone Number Input */}
    <TextInput
      placeholder="Enter phone number"
      value={form.phone}
      onChange={(e) =>
        setForm((p) => ({
          ...p,
          phone: e.target.value.replace(/\D/g, ""),
        }))
      }
      style={{
        flex: 1,
      }}
      styles={inputStyles()}
    />
  </Group>
</Grid.Col>

              {/* Role */}
              <Grid.Col span={6}>
                <Select
                  label="Role"
                  placeholder="Select Role"
                  data={roleOptions}
                  value={form.roleID || null}
                  onChange={(val) => setForm((p) => ({ ...p, roleID: val ?? "" }))}
                  styles={inputStyles()}
                />
              </Grid.Col>

              {/* Status */}
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

              {/* Services multi-select */}
              <Grid.Col span={12}>
                <Text size="sm" mb={4} c="#cfcfcf">Services</Text>
                <Box ref={servicesRef} style={{ position: "relative" }}>
                  <UnstyledButton
                    onClick={() => setServicesOpen((p) => !p)}
                    style={{
                      width: "100%",
                      padding: "8px",
                      background: "#2a2a2a",
                      border: "1px solid #444",
                      borderRadius: 6,
                      color: form.services.length > 0 ? "#fff" : "#888",
                      textAlign: "left",
                      fontSize: 14,
                    }}
                  >
                    {form.services.length > 0
                      ? form.services.map(getServiceLabel).join(", ")
                      : "Select Services"}
                  </UnstyledButton>

                  <Collapse in={servicesOpen}>
                    <Box
                      style={{
                        background: "#2a2a2a",
                        border: "1px solid #444",
                        borderRadius: 6,
                        marginTop: 4,
                        maxHeight: 180,
                        overflowY: "auto",
                        zIndex: 100,
                        position: "relative",
                      }}
                    >
                      {Object.entries(SERVICE_LABELS).map(([backendKey, displayLabel]) => (
                        <Box
                          key={backendKey}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 8,
                            padding: "8px 12px",
                          }}
                        >
                          <Checkbox
                            checked={form.services.includes(backendKey)}
                            onChange={(e) =>
                              setForm((p) => ({
                                ...p,
                                services: e.target.checked
                                  ? [...p.services, backendKey]
                                  : p.services.filter((s) => s !== backendKey),
                              }))
                            }
                            label={
                              <Text size="sm" c="#fff">{displayLabel}</Text>
                            }
                            styles={{ input: { background: "#2a2a2a", borderColor: "#555" } }}
                          />
                        </Box>
                      ))}
                    </Box>
                  </Collapse>
                </Box>
              </Grid.Col>
            </Grid>

            {/* Actions */}
            <Group justify="flex-end" mt="md">
              <Button variant="default" onClick={handleClose}
                styles={{ root: { background: "#2a2a2a", border: "1px solid #444", color: "#ddd" } }}
              >
                Cancel
              </Button>
              <Button type="submit" loading={saving} disabled={saving}
                styles={{ root: { background: "#228be6" } }}
              >
                {saving ? "Saving..." : editingUser ? "Update" : "Submit"}
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
            <Title order={4} style={{ color: "#fff", margin: 0 }}>Users</Title>
            <Badge
              style={{ background: "#333", color: "#d0d0d0", borderRadius: 99 }}
              size="md"
            >
              {users.length}
            </Badge>
          </Group>

          <Button
            size="xs"
            leftSection={<IconPlus size={14} />}
            onClick={handleOpenCreate}
            disabled={!canCreateUser}
            title={canCreateUser ? "Create" : "No Access"}
            styles={{
              root: {
                background: "#228be6",
                opacity: canCreateUser ? 1 : 0.5,
                cursor: canCreateUser ? "pointer" : "not-allowed",
              },
            }}
          >
            Create
          </Button>
        </Group>

        {rolesError && <Text size="sm" c="#ff8f8f" mt={8}>{rolesError}</Text>}
      </Box>

      {/* ── Table card ── */}
      <Box p={16} style={{ border: "1px solid #333", borderRadius: 8, background: "#1a1a1a" }}>
        <Table style={{ width: "100%", borderCollapse: "collapse" }}>
          <Table.Thead>
            <Table.Tr>
              {["Name", "Email", "Phone", "Role", "Services", "Status", "Actions"].map((h) => (
                <Table.Th key={h} style={{ textAlign: "left", padding: "8px", background: "#111", color: "#aaa" }}>
                  {h}
                </Table.Th>
              ))}
            </Table.Tr>
          </Table.Thead>

          <Table.Tbody>
            {loading ? (
              <Table.Tr>
                <Table.Td colSpan={7} style={{ padding: "40px 8px", border: "none" }}>
                  <Center>
                    <Loader size="sm" color="#228be6" />
                  </Center>
                </Table.Td>
              </Table.Tr>
            ) : error ? (
              <Table.Tr>
                <Table.Td colSpan={7} style={{ padding: "40px 8px", border: "none" }}>
                  <Center>
                    <Text size="sm" c="#ff8f8f">{error}</Text>
                  </Center>
                </Table.Td>
              </Table.Tr>
            ) : users.length === 0 ? (
              <Table.Tr>
                <Table.Td colSpan={7} style={{ padding: "8px", color: "#eee" }}>
                  No users found.
                </Table.Td>
              </Table.Tr>
            ) : (
              paginatedUsers.map((user, index) => {
                const bg = index % 2 ? "#222" : "transparent";
                const tdStyle = {
                  padding: "8px",
                  borderBottom: "1px solid #333",
                  color: "#eee",
                  background: bg,
                };

                return (
                  <Table.Tr key={user._id}>
                    <Table.Td style={tdStyle}>{user.name}</Table.Td>
                    <Table.Td style={tdStyle}>{user.email}</Table.Td>
                    <Table.Td style={tdStyle}>{user.phone}</Table.Td>
                    <Table.Td style={tdStyle}>{roleNameById.get(user.roleID) || user.roleID}</Table.Td>
                    <Table.Td style={tdStyle}>
                      {user.services?.length
                        ? user.services.map(getServiceLabel).join(", ")
                        : "-"}
                    </Table.Td>
                    <Table.Td style={tdStyle}>{user.active === 1 ? "Active" : "Inactive"}</Table.Td>
                    <Table.Td style={tdStyle}>
                      <Box
                        component="span"
                        style={{
                          cursor: canEditUser ? "pointer" : "not-allowed",
                          color: "#aaa",
                          opacity: canEditUser ? 1 : 0.4,
                        }}
                        onClick={() => handleEdit(user)}
                        aria-disabled={!canEditUser}
                        title={canEditUser ? "Edit" : "No Access"}
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

function inputStyles(disabled = false) {
  return {
    label: { color: "#cfcfcf", fontSize: 13, marginBottom: 4 },
    input: {
      background: "#2a2a2a",
      border: "1px solid #444",
      color: "#fff",
      opacity: disabled ? 0.75 : 1,
      cursor: disabled ? "not-allowed" : "text",
      "&:focus": { borderColor: "#228be6" },
    },
  };
}

export default UserPage;
