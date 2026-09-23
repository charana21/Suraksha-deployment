
import { useEffect, useState } from "react";

import {
  ActionIcon,
  Badge,
  Box,
  Center,
  Group,
  Loader,
  Pagination,
  Select,
  Table,
  Text,
  Title,
  Tooltip,
} from "@mantine/core";

import { PageLayout } from "@/components/layout/PageLayout";

import {
  whatsappAuditsApi,
  type WhatsAppAuditRecord,
} from "@/services/whatsappAudits";

import { IconDownload } from "@tabler/icons-react";

const formatTimestamp = (value: string) => {
  if (!value) return "-";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
};

const formatCoordinates = (
  record: WhatsAppAuditRecord,
) => {
  const coords = record.location?.coordinates;

  if (!coords || coords.length < 2) return "-";

  const [longitude, latitude] = coords;

  return `${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
};

const escapeHtml = (value: string) =>
  value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

const WhatsAppAudits = () => {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const [audits, setAudits] =
    useState<WhatsAppAuditRecord[]>([]);

  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let isMounted = true;

    const loadAudits = async () => {
      setLoading(true);
      setError("");

      try {
        const response =
          await whatsappAuditsApi.getAudits();

        if (!isMounted) return;

        const today = new Date()
          .toISOString()
          .slice(0, 10);

        const todayAudits = (
          response.locations || []
        ).filter(
          (a) => a.loginDate === today,
        );

        setAudits(todayAudits);
        setTotalCount(todayAudits.length);
      } catch (err) {
        if (!isMounted) return;

        setError(
          err instanceof Error
            ? err.message
            : "Failed to load audits",
        );
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    loadAudits();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    setPage(1);
  }, [pageSize]);

  useEffect(() => {
    const totalPages = Math.max(
      1,
      Math.ceil(audits.length / pageSize),
    );

    setPage((current) =>
      Math.min(current, totalPages),
    );
  }, [audits.length, pageSize]);

  const totalPages = Math.max(
    1,
    Math.ceil(audits.length / pageSize),
  );

  const paginatedAudits = audits.slice(
    (page - 1) * pageSize,
    page * pageSize,
  );

  const handleDownload = () => {
    if (paginatedAudits.length === 0) return;

    const rows = paginatedAudits
      .map(
        (audit) => `
          <tr>
            <td>${escapeHtml(
              audit.platform || "-",
            )}</td>
            <td>${escapeHtml(
              audit.phoneNumber || "-",
            )}</td>
            <td>${escapeHtml(
              audit.loginDate || "-",
            )}</td>
          </tr>
        `,
      )
      .join("");

    const html = `
      <html>
        <head>
          <meta charset="utf-8" />
        </head>
        <body>
          <table border="1">
            <thead>
              <tr>
                <th>Platform</th>
                <th>Phone Number</th>
                <th>Login Date</th>
              </tr>
            </thead>
            <tbody>
              ${rows}
            </tbody>
          </table>
        </body>
      </html>
    `;

    const blob = new Blob([html], {
      type: "application/vnd.ms-excel;charset=utf-8",
    });

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = `whatsapp_audits_page_${page}.xls`;

    link.click();

    URL.revokeObjectURL(url);
  };

  return (
    <PageLayout>
      {/* ── Header card ── */}
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
              Today's WhatsApp Audits
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
              {totalCount || audits.length}
            </Badge>
          </Group>

         <Tooltip
  label="Download"
  styles={{
    tooltip: {
      background: "hsl(var(--secondary))",
      color: "hsl(var(--foreground))",
      border: "1px solid hsl(var(--border))",
    },
  }}
>
  <ActionIcon
    color="green"
    variant="filled"
    size="30px"
    radius="sm"
    onClick={handleDownload}
  >
    <IconDownload />
  </ActionIcon>
</Tooltip>
        </Group>
      </Box>

      {/* ── Table card ── */}
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
                "Platform",
                "Phone Number",
                "Login Date",
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
                  colSpan={3}
                  style={{
                    padding:
                      "40px 8px",
                    border: "none",
                  }}
                >
                  <Center>
                    <Loader
                      size="sm"
                      color="#228be6"
                    />
                  </Center>
                </Table.Td>
              </Table.Tr>
            ) : error ? (
              <Table.Tr>
                <Table.Td
                  colSpan={3}
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
                          "#ff8f8f",
                      }}
                    >
                      {error}
                    </Text>
                  </Center>
                </Table.Td>
              </Table.Tr>
            ) : audits.length === 0 ? (
              <Table.Tr>
                <Table.Td
                  colSpan={3}
                  style={{
                    padding: "8px",
                    color:
                      "hsl(var(--foreground))",
                  }}
                >
                  No audits found.
                </Table.Td>
              </Table.Tr>
            ) : (
              paginatedAudits.map(
                (audit, index) => {
                  const bg =
                    index % 2
                      ? "hsl(var(--secondary))"
                      : "transparent";

                  const tdStyle = {
                    padding: "8px",
                    borderBottom:
                      "1px solid hsl(var(--border))",
                    color:
                      "hsl(var(--foreground))",
                    background: bg,
                  };

                  return (
                    <Table.Tr
                      key={audit._id}
                    >
                      <Table.Td
                        style={tdStyle}
                      >
                        {audit.platform ||
                          "-"}
                      </Table.Td>

                      <Table.Td
                        style={tdStyle}
                      >
                        {audit.phoneNumber ||
                          "-"}
                      </Table.Td>

                      <Table.Td
                        style={tdStyle}
                      >
                        <Text
                          size="sm"
                          style={{
                            color:
                              "hsl(var(--foreground))",
                          }}
                        >
                        </Text>

                        <Text
                          size="sm"
                          style={{
                            color:
                              "hsl(var(--muted-foreground))",
                          }}
                        >
                          {audit.loginDate ||
                            "-"}
                        </Text>
                      </Table.Td>
                    </Table.Tr>
                  );
                },
              )
            )}
          </Table.Tbody>
        </Table>

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
                  Number(
                    value ?? "10",
                  ),
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
                },

                dropdown: {
                  background:
                    "hsl(var(--background))",
                  border:
                    "1px solid hsl(var(--border))",
                },

                option: {
                  color:
                    "hsl(var(--foreground))",
                  background:
                    "hsl(var(--background))",
                },

                optionHovered: {
                  background:
                    "hsl(var(--secondary))",
                  color:
                    "hsl(var(--foreground))",
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
                background:
                  "hsl(var(--background))",
                borderColor:
                  "hsl(var(--border))",
                color:
                  "hsl(var(--foreground))",
              },
            }}
          />
        </Group>
      </Box>
    </PageLayout>
  );
};

export default WhatsAppAudits;