import { useState, useRef, useEffect, type CSSProperties } from "react";
import dayjs from "dayjs";
import { DatePickerInput, type DatesRangeValue } from "@mantine/dates";
import { PageLayout } from "@/components/layout/PageLayout";
import {
  IconUsers,
  IconCircleCheck,
  IconCircleX,
  IconUser,
  IconDownload,
  IconFilter,
  IconX,
} from "@tabler/icons-react";
import { ActionIcon, Tooltip } from "@mantine/core";

// ── Types ─────────────────────────────────────────────────────────────────────
interface LoginRecord {
  id: number;
  userName: string;
  email: string;
  loginTime: string;
  status: "Success" | "Failed";
  loginType: "Web" | "Mobile App";
  ipAddress: string;
  location: string;
  device: string;
}

// ── Mock data (replace with API) ──────────────────────────────────────────────
const MOCK_DATA: LoginRecord[] = [
  { id: 1, userName: "Admin User",   email: "admin@example.com",        loginTime: "20 May 2025, 09:15 AM", status: "Success", loginType: "Web",        ipAddress: "192.168.1.10", location: "Mumbai, India",    device: "Chrome / Windows" },
  { id: 2, userName: "Rahul Sharma", email: "rahul.sharma@example.com", loginTime: "20 May 2025, 09:02 AM", status: "Success", loginType: "Web",        ipAddress: "192.168.1.25", location: "Pune, India",      device: "Edge / Windows" },
  { id: 3, userName: "Priya Patel",  email: "priya.patel@example.com",  loginTime: "20 May 2025, 08:45 AM", status: "Success", loginType: "Web",        ipAddress: "192.168.1.18", location: "Ahmedabad, India", device: "Chrome / Mac OS" },
  { id: 4, userName: "Sanjay Kumar", email: "sanjay.kumar@example.com", loginTime: "20 May 2025, 08:30 AM", status: "Failed",  loginType: "Web",        ipAddress: "192.168.1.33", location: "Delhi, India",     device: "Chrome / Windows" },
  { id: 5, userName: "Neha Singh",   email: "neha.singh@example.com",   loginTime: "20 May 2025, 08:21 AM", status: "Success", loginType: "Mobile App", ipAddress: "192.168.1.27", location: "Bangalore, India", device: "Android / 14" },
  { id: 6, userName: "Vikram Joshi", email: "vikram.joshi@example.com", loginTime: "20 May 2025, 08:10 AM", status: "Failed",  loginType: "Web",        ipAddress: "192.168.1.50", location: "Jaipur, India",    device: "Firefox / Windows" },
  { id: 7, userName: "Amit Verma",   email: "amit.verma@example.com",   loginTime: "20 May 2025, 07:55 AM", status: "Success", loginType: "Web",        ipAddress: "192.168.1.12", location: "Lucknow, India",   device: "Chrome / Windows" },
  { id: 8, userName: "Kavita Reddy", email: "kavita.reddy@example.com", loginTime: "20 May 2025, 07:40 AM", status: "Success", loginType: "Mobile App", ipAddress: "192.168.1.44", location: "Hyderabad, India", device: "iOS / 17" },
];

// ── Styles ────────────────────────────────────────────────────────────────────
const styles: Record<string, CSSProperties> = {
  card:         { border: "1px solid #333", borderRadius: 8, padding: 16, background: "#1a1a1a" },
  cardMb:       { border: "1px solid #333", borderRadius: 8, padding: 16, background: "#1a1a1a", marginBottom: 12 },
  title:        { fontSize: 18, fontWeight: 700, color: "#fff", margin: 0 },
  badge:        { background: "#333", color: "#d0d0d0", borderRadius: 99, padding: "2px 10px", fontSize: 12 },
  group:        { display: "flex", alignItems: "center", gap: 8 },
  groupBetween: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 },
  table:        { width: "100%", borderCollapse: "collapse" },
  th:           { textAlign: "left", padding: "10px", background: "#111", color: "#aaa", borderBottom: "1px solid #333" },
  td:           { padding: "10px", borderBottom: "1px solid #333", color: "#eee" },
  tdAlt:        { padding: "10px", borderBottom: "1px solid #333", color: "#eee", background: "#222" },
  emptyRow:     { textAlign: "center", padding: "20px", color: "#888" },
  statsGrid:    { display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 12 },
  statCard:     { border: "1px solid #333", borderRadius: 8, padding: 16, background: "#1a1a1a", display: "flex", alignItems: "center", gap: 12 },
  statIcon:     { width: 44, height: 44, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 },
  statLabel:    { fontSize: 12, color: "#888", marginBottom: 2 },
  statValue:    { fontSize: 22, fontWeight: 600, color: "#fff", lineHeight: 1.1 },
  statSub:      { fontSize: 11, color: "#666", marginTop: 2 },
  thInner:      { display: "flex", alignItems: "center", gap: 6, userSelect: "none" },
  filterIconBtn:{ background: "none", border: "none", cursor: "pointer", padding: 0, display: "flex", alignItems: "center" },
  dropdown: {
    position: "absolute", top: "calc(100% + 6px)", left: 0, zIndex: 100,
    background: "#1e1e1e", border: "1px solid #444", borderRadius: 6,
    padding: 8, minWidth: 180, boxShadow: "0 4px 20px rgba(0,0,0,0.6)",
  },
  dropdownInput: {
    width: "100%", padding: "6px 8px", background: "#2a2a2a",
    border: "1px solid #555", borderRadius: 4, color: "#eee",
    fontSize: 13, outline: "none", boxSizing: "border-box" as const,
  },
  dropdownOption: {
    padding: "6px 8px", borderRadius: 4, cursor: "pointer",
    fontSize: 13, color: "#ddd", display: "flex", alignItems: "center", gap: 8,
  },
  clearBtn: {
    marginTop: 6, width: "100%", padding: "5px 0", background: "#2a2a2a",
    border: "1px solid #555", borderRadius: 4, color: "#aaa",
    fontSize: 12, cursor: "pointer", display: "flex", alignItems: "center",
    justifyContent: "center", gap: 4,
  },
  badgeSuccess: { background: "rgba(47,158,68,0.15)",  color: "#69db7c", borderRadius: 99, padding: "2px 10px", fontSize: 12, display: "inline-block" },
  badgeFailed:  { background: "rgba(224,49,49,0.15)",  color: "#ff8787", borderRadius: 99, padding: "2px 10px", fontSize: 12, display: "inline-block" },
};

// ── Stat Card ─────────────────────────────────────────────────────────────────
interface StatCardProps {
  label: string;
  value: number | string;
  sub?: string;
  icon: React.ReactNode;
  iconBg: string;
  iconColor: string;
}

const StatCard = ({ label, value, sub, icon, iconBg, iconColor }: StatCardProps) => (
  <div style={styles.statCard}>
    <div style={{ ...styles.statIcon, background: iconBg, color: iconColor }}>{icon}</div>
    <div>
      <div style={styles.statLabel}>{label}</div>
      <div style={styles.statValue}>{value}</div>
      {sub && <div style={styles.statSub}>{sub}</div>}
    </div>
  </div>
);

// ── Column Filter Dropdown ────────────────────────────────────────────────────
type FilterType = "text" | "select";

interface ColumnFilterProps {
  label: string;
  filterType: FilterType;
  value: string;
  options?: string[];
  onChange: (val: string) => void;
  active: boolean;
}

const ColumnFilter = ({ label, filterType, value, options = [], onChange, active }: ColumnFilterProps) => {
  const [open, setOpen]       = useState(false);
  const [hovered, setHovered] = useState<string | null>(null);
  const ref                   = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    if (open) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  return (
    <div ref={ref} style={{ position: "relative", display: "inline-flex" }}>
      <button
        style={styles.filterIconBtn}
        onClick={(e) => { e.stopPropagation(); setOpen((p) => !p); }}
        title={`Filter by ${label}`}
      >
        <IconFilter size={13} style={{ color: active ? "#4dabf7" : "#555", transition: "color 0.15s" }} />
      </button>

      {open && (
        <div style={styles.dropdown} onClick={(e) => e.stopPropagation()}>
          {filterType === "text" ? (
            <input
              autoFocus
              style={styles.dropdownInput}
              placeholder={`Search ${label}...`}
              value={value}
              onChange={(e) => onChange(e.target.value)}
            />
          ) : (
            <div>
              {options.map((opt) => (
                <div
                  key={opt}
                  style={{
                    ...styles.dropdownOption,
                    background: hovered === opt ? "#2a2a2a" : value === opt ? "#1c3a5a" : "transparent",
                    color: value === opt ? "#4dabf7" : "#ddd",
                  }}
                  onMouseEnter={() => setHovered(opt)}
                  onMouseLeave={() => setHovered(null)}
                  onClick={() => { onChange(value === opt ? "" : opt); setOpen(false); }}
                >
                  {opt === "Success" && (
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#69db7c", display: "inline-block", flexShrink: 0 }} />
                  )}
                  {opt === "Failed" && (
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#ff8787", display: "inline-block", flexShrink: 0 }} />
                  )}
                  {opt}
                </div>
              ))}
            </div>
          )}

          {value && (
            <button
              style={styles.clearBtn}
              onClick={() => { onChange(""); setOpen(false); }}
            >
              <IconX size={11} /> Clear filter
            </button>
          )}
        </div>
      )}
    </div>
  );
};

// ── Main Component ────────────────────────────────────────────────────────────
const SystemAudits = () => {
  const [dateRange, setDateRange] = useState<DatesRangeValue>([
    dayjs().subtract(1, "days").toDate(),
    dayjs().toDate(),
  ]);

  const [filterUserName,  setFilterUserName]  = useState("");
  const [filterStatus,    setFilterStatus]    = useState("");
  const [filterLoginType, setFilterLoginType] = useState("");

  const filtered = MOCK_DATA.filter((row) => {
    if (filterUserName  && !row.userName.toLowerCase().includes(filterUserName.toLowerCase())) return false;
    if (filterStatus    && row.status    !== filterStatus)    return false;
    if (filterLoginType && row.loginType !== filterLoginType) return false;
    return true;
  });

  const totalLogins   = filtered.length;
  const successLogins = filtered.filter((r) => r.status === "Success").length;
  const failedLogins  = filtered.filter((r) => r.status === "Failed").length;
  const uniqueUsers   = new Set(filtered.map((r) => r.userName)).size;

  return (
    <PageLayout>
      {/* ── Heading card ── */}
      <div style={styles.cardMb}>
        <div style={styles.groupBetween}>
          <div style={styles.group}>
            <h4 style={styles.title}>System Audits</h4>
            <span style={styles.badge}>{totalLogins}</span>
          </div>

          <div style={styles.group}>
            <DatePickerInput
              type="range"
              placeholder="Select date range"
              value={dateRange}
              allowSingleDateInRange
              onChange={(val: DatesRangeValue) => setDateRange(val)}
              maxDate={dayjs().toDate()}
              clearable={false}
              size="xs"
            />
            <Tooltip label="Download Audits Summary">
              <ActionIcon color="green" variant="filled" size="30px" radius="sm">
                <IconDownload />
              </ActionIcon>
            </Tooltip>
          </div>
        </div>
      </div>

      {/* ── Stat cards ── */}
      {/* <div style={styles.statsGrid}>
        <StatCard label="Total Logins"   value={totalLogins}   icon={<IconUsers size={20} />}       iconBg="rgba(34,139,230,0.15)" iconColor="#4dabf7" />
        <StatCard label="Success Logins" value={successLogins} icon={<IconCircleCheck size={20} />} iconBg="rgba(47,158,68,0.15)"  iconColor="#69db7c" />
        <StatCard label="Failed Logins"  value={failedLogins}  icon={<IconCircleX size={20} />}     iconBg="rgba(224,49,49,0.15)"  iconColor="#ff8787" />
        <StatCard label="Unique Users"   value={uniqueUsers}   icon={<IconUser size={20} />}         iconBg="rgba(240,140,0,0.15)"  iconColor="#ffa94d" />
      </div> */}

      {/* ── Table card ── */}
      {/* <div style={styles.card}>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>
                <div style={styles.thInner}>
                  User Name
                  <ColumnFilter
                    label="User Name"
                    filterType="text"
                    value={filterUserName}
                    onChange={setFilterUserName}
                    active={!!filterUserName}
                  />
                </div>
              </th>

              <th style={styles.th}>Email</th>
              <th style={styles.th}>Login Time</th>

              <th style={styles.th}>
                <div style={styles.thInner}>
                  Status
                  <ColumnFilter
                    label="Status"
                    filterType="select"
                    value={filterStatus}
                    options={["Success", "Failed"]}
                    onChange={setFilterStatus}
                    active={!!filterStatus}
                  />
                </div>
              </th>

              <th style={styles.th}>
                <div style={styles.thInner}>
                  Login Type
                  <ColumnFilter
                    label="Login Type"
                    filterType="select"
                    value={filterLoginType}
                    options={["Web", "Mobile App"]}
                    onChange={setFilterLoginType}
                    active={!!filterLoginType}
                  />
                </div>
              </th>

              <th style={styles.th}>IP Address</th>
              <th style={styles.th}>Location</th>
              <th style={styles.th}>Device / Browser</th>
            </tr>
          </thead>

          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td style={styles.emptyRow} colSpan={8}>
                  No login history found.
                </td>
              </tr>
            ) : (
              filtered.map((row, i) => {
                const td = i % 2 === 0 ? styles.td : styles.tdAlt;
                return (
                  <tr key={row.id}>
                    <td style={td}>{row.userName}</td>
                    <td style={{ ...td, color: "#aaa" }}>{row.email}</td>
                    <td style={{ ...td, color: "#aaa" }}>{row.loginTime}</td>
                    <td style={td}>
                      <span style={row.status === "Success" ? styles.badgeSuccess : styles.badgeFailed}>
                        {row.status}
                      </span>
                    </td>
                    <td style={td}>{row.loginType}</td>
                    <td style={{ ...td, color: "#aaa", fontFamily: "monospace" }}>{row.ipAddress}</td>
                    <td style={{ ...td, color: "#aaa" }}>{row.location}</td>
                    <td style={{ ...td, color: "#aaa" }}>{row.device}</td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div> */}
    </PageLayout>
  );
};

export default SystemAudits;