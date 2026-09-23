import { useEffect, useMemo, useState } from "react";
import {
  CalendarDays,
  Loader2,
  ChevronLeft,
  ChevronRight,
  Search,
} from "lucide-react";
import { IconDownload } from "@tabler/icons-react";
import {
  DatePickerInput,
  type DatesRangeValue,
} from "@mantine/dates";
import dayjs from "dayjs";
import { format } from "date-fns";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";

import { cn } from "@/lib/utils";
import { trainsApi } from "@/services/trainsApi";
import { ArrivalHistoryRecord } from "@/types/trains";

interface ArrivalHistoryModalProps {
  trainNumber?: string;
  trainName?: string;
  overlay?: boolean;

  /** Renders as a standalone search-triggered modal with an editable train number field. */
  searchMode?: boolean;
}

const PAGE_SIZE = 10;

const API_DATE_FORMAT = "yyyy-MM-dd";

const formatScheduleDate = (value: string) => {
  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return format(parsed, "dd MMM yyyy");
};

export function ArrivalHistoryModal({
  trainNumber = "",
  trainName,
  overlay,
  searchMode,
}: ArrivalHistoryModalProps) {
  const today = useMemo(() => dayjs().toDate(), []);

  const tenDaysAgo = useMemo(
    () => dayjs().subtract(9, "day").toDate(),
    []
  );

  const [open, setOpen] = useState(false);

  const [range, setRange] = useState<DatesRangeValue>([
    tenDaysAgo,
    today,
  ]);

  const [records, setRecords] = useState<
    ArrivalHistoryRecord[]
  >([]);

  const [loading, setLoading] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const [downloading, setDownloading] = useState(false);

  const [page, setPage] = useState(1);

  const [trainNumberQuery, setTrainNumberQuery] =
    useState(trainNumber);

  const [rangeStart, rangeEnd] = range;

  const activeTrainNumber = trainNumberQuery.trim();

  /* =========================================================
     OPEN / CLOSE
     ========================================================= */

  const handleOpenChange = (next: boolean) => {
    setOpen(next);

    if (next && searchMode) {
      setTrainNumberQuery(trainNumber);
      setRecords([]);
      setError(null);
      setLoading(false);
      setPage(1);
    }
  };

  /* =========================================================
     FETCH ARRIVAL HISTORY
     ========================================================= */

  useEffect(() => {
    if (
      !open ||
      !rangeStart ||
      !activeTrainNumber
    ) {
      setLoading(false);

      if (!activeTrainNumber) {
        setRecords([]);
        setError(null);
      }

      return;
    }

    const startDate = format(
      rangeStart,
      API_DATE_FORMAT
    );

    const endDate = format(
      rangeEnd || rangeStart,
      API_DATE_FORMAT
    );

    let cancelled = false;

    setLoading(true);
    setError(null);

    const handle = setTimeout(() => {
      trainsApi
        .getArrivalHistory({
          trainNumber: activeTrainNumber,
          startDate,
          endDate,
        })
        .then((data) => {
          if (cancelled) return;

          setRecords(
            Array.isArray(data.trains)
              ? data.trains
              : []
          );

          setPage(1);
        })
        .catch((err) => {
          if (cancelled) return;

          setError(
            err instanceof Error
              ? err.message
              : "Failed to load arrival history"
          );

          setRecords([]);
        })
        .finally(() => {
          if (!cancelled) {
            setLoading(false);
          }
        });
    }, searchMode ? 400 : 0);

    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [
    open,
    rangeStart,
    rangeEnd,
    activeTrainNumber,
    searchMode,
  ]);

  /* =========================================================
     PAGINATION
     ========================================================= */

  const totalPages = Math.max(
    1,
    Math.ceil(records.length / PAGE_SIZE)
  );

  const pagedRecords = records.slice(
    (page - 1) * PAGE_SIZE,
    page * PAGE_SIZE
  );

  /* =========================================================
     DOWNLOAD
     ========================================================= */

  const handleDownload = async () => {
    if (!rangeStart || !activeTrainNumber) {
      return;
    }

    setDownloading(true);

    try {
      await trainsApi.downloadArrivalHistory({
        trainNumber: activeTrainNumber,
        startDate: format(
          rangeStart,
          API_DATE_FORMAT
        ),
        endDate: format(
          rangeEnd || rangeStart,
          API_DATE_FORMAT
        ),
      });
    } catch (err) {
    } finally {
      setDownloading(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={handleOpenChange}
    >
      {/* =====================================================
          TRIGGER
         ===================================================== */}

      <DialogTrigger asChild>
        {searchMode ? (
          <button
            type="button"
            aria-label="Search train arrival history"
            className={cn(
              "flex items-center justify-center h-6 w-6 rounded-md transition-colors",

              overlay
                ? "text-white/60 hover:text-white hover:bg-white/10"
                : "text-muted-foreground hover:text-foreground hover:bg-muted"
            )}
          >
            <Search className="h-4 w-4" />
          </button>
        ) : (
          <button
            type="button"
            className={cn(
              "flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider transition-colors",

              overlay
                ? "text-white/60 hover:text-white"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {/* Calendar / Arrival History trigger */}
          </button>
        )}
      </DialogTrigger>

      {/* =====================================================
          MODAL
          
          IMPORTANT:
          We DO NOT use `overlay` here to determine light/dark.
          The `dark:` classes follow the actual application theme.
         ===================================================== */}

      <DialogContent
        className={cn(
          "max-w-3xl max-h-[85vh] flex flex-col",

          // LIGHT MODE
          "bg-background text-foreground border-border",

          // DARK MODE
          "dark:bg-zinc-900 dark:text-white dark:border-white/20"
        )}
      >
        {/* ===================================================
            HEADER
           =================================================== */}

        <DialogHeader>
          <DialogTitle
            className={cn(
              "flex items-center gap-2",

              "text-foreground",
              "dark:text-white"
            )}
          >
            <CalendarDays
              className={cn(
                "h-5 w-5",

                "text-emerald-500",
                "dark:text-emerald-400"
              )}
            />

            <span>Arrival History</span>

            {!searchMode ? (
              <span
                className={cn(
                  "text-sm font-normal",

                  "text-muted-foreground",
                  "dark:text-white/50"
                )}
              >
                {trainNumber}

                {trainName
                  ? ` · ${trainName}`
                  : ""}
              </span>
            ) : (
              activeTrainNumber &&
              !loading &&
              !error &&
              records.length > 0 && (
                <span
                  className={cn(
                    "text-sm font-normal",

                    "text-muted-foreground",
                    "dark:text-white/50"
                  )}
                >
                  {records[0]?.train_number ||
                    activeTrainNumber}

                  {records[0]?.api_response_raw
                    ?.name
                    ? ` · ${records[0].api_response_raw.name}`
                    : ""}
                </span>
              )
            )}
          </DialogTitle>
        </DialogHeader>

        {/* ===================================================
            SEARCH + DATE + DOWNLOAD
           =================================================== */}

        <div
          className={cn(
            "flex items-center justify-between gap-3 border-b pb-3",

            "border-border",
            "dark:border-white/10"
          )}
        >
          {/* TRAIN NUMBER SEARCH */}

          {searchMode ? (
            <Input
              type="text"
              inputMode="numeric"
              placeholder="Enter Train Number"
              value={trainNumberQuery}
              onChange={(e) =>
                setTrainNumberQuery(
                  e.target.value
                )
              }
              className={cn(
                "h-10 w-48",

                // LIGHT MODE
                "bg-background text-foreground border-input",
                "placeholder:text-muted-foreground",

                // DARK MODE
                "dark:bg-white/5 dark:text-white dark:border-white/20",
                "dark:placeholder:text-white/40"
              )}
              autoFocus
            />
          ) : (
            <div />
          )}

          {/* DATE + DOWNLOAD */}

          <div className="flex items-center gap-3">
            <DatePickerInput
  type="range"
  placeholder="Select date range"
  value={range}
  onChange={setRange}
  allowSingleDateInRange
  maxDate={today}
  clearable={false}
  size="xs"
  leftSection={
    <CalendarDays className="h-4 w-4 text-gray-500" />
  }
  className="w-64"
  styles={{
    input: {
      backgroundColor: "#ffffff",
      color: "#111827",
      borderColor: "#d1d5db",
    },
    placeholder: {
      color: "#6b7280",
    },
  }}
  defaultLevel="month"
  maxLevel="decade"
  popoverProps={{
    withinPortal: false,
  }}
/>
          

            <MantineDownloadButton
              downloading={downloading}
              disabled={
                !rangeStart ||
                !activeTrainNumber
              }
              onClick={handleDownload}
            />
          </div>
        </div>

        {/* ===================================================
            CONTENT
           =================================================== */}

        <div className="flex-1 overflow-auto min-h-[240px]">
          {/* LOADING */}

          {loading ? (
            <div
              className={cn(
                "flex items-center justify-center h-full py-16",

                "text-muted-foreground",
                "dark:text-white/60"
              )}
            >
              <Loader2 className="h-5 w-5 mr-2 animate-spin" />

              Loading arrival history...
            </div>
          ) : error ? (
            /* ERROR */

            <div className="flex items-center justify-center h-full py-16 text-red-500 text-sm">
              {error}
            </div>
          ) : searchMode &&
            !activeTrainNumber ? (
            /* EMPTY SEARCH */

            <div
              className={cn(
                "flex items-center justify-center h-full py-16 text-sm",

                "text-muted-foreground",
                "dark:text-white/50"
              )}
            >
              Enter a train number to search
              its arrival history.
            </div>
          ) : records.length === 0 ? (
            /* NO RECORDS */

            <div
              className={cn(
                "flex items-center justify-center h-full py-16 text-sm",

                "text-muted-foreground",
                "dark:text-white/50"
              )}
            >
              No Records Found
            </div>
          ) : (
            /* =================================================
               TABLE
               ================================================= */

            <Table>
              <TableHeader>
                <TableRow
                  className={cn(
                    "hover:bg-transparent",

                    "border-border",
                    "dark:border-white/10"
                  )}
                >
                  <TableHead
                    className={cn(
                      "text-muted-foreground",
                      "dark:text-white/60"
                    )}
                  >
                    Train Number
                  </TableHead>

                  <TableHead
                    className={cn(
                      "text-muted-foreground",
                      "dark:text-white/60"
                    )}
                  >
                    Station Name
                  </TableHead>

                  <TableHead
                    className={cn(
                      "text-muted-foreground",
                      "dark:text-white/60"
                    )}
                  >
                    Schedule Date
                  </TableHead>

                  <TableHead
                    className={cn(
                      "text-muted-foreground",
                      "dark:text-white/60"
                    )}
                  >
                    Actual Arrival
                  </TableHead>

                  <TableHead
                    className={cn(
                      "text-muted-foreground",
                      "dark:text-white/60"
                    )}
                  >
                    Actual Departure
                  </TableHead>
                </TableRow>
              </TableHeader>

              <TableBody>
                {pagedRecords.map((record) => (
                  <TableRow
                    key={record._id}
                    className={cn(
                      "border-border hover:bg-muted/30",

                      "dark:border-white/5 dark:hover:bg-white/5"
                    )}
                  >
                    {/* TRAIN NUMBER */}

                    <TableCell
                      className={cn(
                        "font-mono",

                        "text-foreground",
                        "dark:text-white/90"
                      )}
                    >
                      {record.train_number}
                    </TableCell>

                    {/* STATION NAME */}

                    <TableCell
                      className={cn(
                        "text-foreground",
                        "dark:text-white/90"
                      )}
                    >
                      {record.api_response_raw
                        ?.name || "—"}
                    </TableCell>

                    {/* SCHEDULE DATE */}

                    <TableCell
                      className={cn(
                        "text-muted-foreground",
                        "dark:text-white/70"
                      )}
                    >
                      {formatScheduleDate(
                        record.schedule_date
                      )}
                    </TableCell>

                    {/* ACTUAL ARRIVAL */}

                    <TableCell
                      className={cn(
                        "text-foreground",
                        "dark:text-white/90"
                      )}
                    >
                      {record.actual_arrival ||
                        "—"}
                    </TableCell>

                    {/* ACTUAL DEPARTURE */}

                    <TableCell
                      className={cn(
                        "text-foreground",
                        "dark:text-white/90"
                      )}
                    >
                      {record.actual_departure ||
                        "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>

        {/* ===================================================
            PAGINATION
           =================================================== */}

        {!loading &&
          !error &&
          records.length > 0 && (
            <div
              className={cn(
                "flex items-center justify-between pt-2 border-t",

                "border-border",
                "dark:border-white/10"
              )}
            >
              {/* RECORD COUNT */}

              <span
                className={cn(
                  "text-xs",

                  "text-muted-foreground",
                  "dark:text-white/50"
                )}
              >
                Showing{" "}
                {(page - 1) * PAGE_SIZE + 1}
                –
                {Math.min(
                  page * PAGE_SIZE,
                  records.length
                )}{" "}
                of {records.length} records
              </span>

              {/* PAGINATION */}

              <div className="flex items-center gap-1">
                {/* PREVIOUS */}

                <Button
                  variant="ghost"
                  size="icon"
                  className={cn(
                    "h-7 w-7",

                    "text-muted-foreground hover:bg-muted hover:text-foreground",

                    "dark:text-white/70 dark:hover:bg-white/10 dark:hover:text-white",

                    "disabled:opacity-30"
                  )}
                  onClick={() =>
                    setPage((p) =>
                      Math.max(1, p - 1)
                    )
                  }
                  disabled={page <= 1}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>

                {/* PAGE */}

                <span
                  className={cn(
                    "text-xs px-2",

                    "text-muted-foreground",
                    "dark:text-white/60"
                  )}
                >
                  Page {page} of {totalPages}
                </span>

                {/* NEXT */}

                <Button
                  variant="ghost"
                  size="icon"
                  className={cn(
                    "h-7 w-7",

                    "text-muted-foreground hover:bg-muted hover:text-foreground",

                    "dark:text-white/70 dark:hover:bg-white/10 dark:hover:text-white",

                    "disabled:opacity-30"
                  )}
                  onClick={() =>
                    setPage((p) =>
                      Math.min(
                        totalPages,
                        p + 1
                      )
                    )
                  }
                  disabled={
                    page >= totalPages
                  }
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
      </DialogContent>
    </Dialog>
  );
}

/* =========================================================
   DOWNLOAD BUTTON

   Kept separate so we can control Light/Dark styling cleanly.
   ========================================================= */

function MantineDownloadButton({
  downloading,
  disabled,
  onClick,
}: {
  downloading: boolean;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || downloading}
      className={cn(
        "inline-flex items-center justify-center gap-2",
        "h-9 px-4 rounded-md",
        "text-sm font-medium",
        "transition-colors",

        // LIGHT MODE
        "bg-muted text-foreground",
        "hover:bg-muted/80",

        // DARK MODE
        "dark:bg-white/10 dark:text-white",
        "dark:hover:bg-white/15",

        // DISABLED
        "disabled:pointer-events-none disabled:opacity-50"
      )}
    >
      {downloading ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : (
        <IconDownload size={16} />
      )}

      Download
    </button>
  );
}