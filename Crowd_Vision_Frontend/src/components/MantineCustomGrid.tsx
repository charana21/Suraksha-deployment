"use client";
 
import {
  DataTable,
  type DataTableColumn,
  type DataTableSortStatus,
} from "mantine-datatable";
import { useEffect, useState } from "react";
import { useMantineColorScheme, Box } from "@mantine/core";
import cx from "clsx";
import "./DataGridStyles.css";
import React from "react";
// import { appColors } from "./colors";
 
type CustomDataTableProps<T extends Record<string, unknown>> = {
  data: T[];
  columns: DataTableColumn<T>[];
  height?: string | number;
  pageSizes?: number[];
  radius?: string | number;
  padding?: string | number;
  striped?: boolean;
  pinLastColumn?: boolean;
  loading?: boolean;
};
 
export default function MantineDataGrid<T extends Record<string, unknown>>({
  data,
  columns,
  height = 400,
  pageSizes = [10, 15, 20],
  radius = "xs",
  padding = "xs",
  striped = true,
  pinLastColumn,
  loading = false,
}: CustomDataTableProps<T>) {
  const [pageSize, setPageSize] = useState(pageSizes[0]);
  const [page, setPage] = useState(1);
  const [records, setRecords] = useState<T[]>([]);
  const [sortStatus, setSortStatus] = useState<DataTableSortStatus<T> | null>(
    null
  );
  const { colorScheme } = useMantineColorScheme();
 
  useEffect(() => {
    setPage(1);
  }, [pageSize, data]);
 
  useEffect(() => {
    let sorted = [...data];
    if (sortStatus) {
      const { columnAccessor, direction } = sortStatus;
      sorted.sort((a, b) => {
        const aValue = a[columnAccessor];
        const bValue = b[columnAccessor];
 
        if (typeof aValue === "number" && typeof bValue === "number") {
          return direction === "asc" ? aValue - bValue : bValue - aValue;
        }
        return direction === "asc"
          ? String(aValue).localeCompare(String(bValue))
          : String(bValue).localeCompare(String(aValue));
      });
    }
 
    const from = (page - 1) * pageSize;
    const to = from + pageSize;
    setRecords(sorted.slice(from, to));
  }, [page, pageSize, data, sortStatus]);
 
  return (
    <Box p={padding}>
      <DataTable
        height={height}
        withTableBorder
        borderRadius={radius}
        striped={striped}
        highlightOnHover
        horizontalSpacing="xs"
        verticalSpacing="sm"
        records={records}
        columns={columns}
        // paginationActiveBackgroundColor={appColors.primary}
        totalRecords={data.length}
        recordsPerPage={pageSize}
        page={page}
        onPageChange={setPage}
        recordsPerPageOptions={pageSizes}
        onRecordsPerPageChange={setPageSize}
        sortStatus={sortStatus ?? undefined}
        onSortStatusChange={setSortStatus}
        paginationSize="sm"
        fetching={loading}
        loadingText="Loading data..."
        noRecordsText="No records found"
        paginationText={({ from, to, totalRecords }) =>
          ` ${from} - ${to} of ${totalRecords}`
        }
        paginationWithEdges
        classNames={{
          table: cx({
            "light-header": colorScheme === "light",
            "dark-header": colorScheme === "dark",
          }),
        }}
        {...(pinLastColumn ? { pinLastColumn: true } : {})}
      />
    </Box>
  );
}