#!/usr/bin/env python3
"""
Create and deploy a dedicated, non-intrusive Grafana Dashboard for:
- Kubernetes Pods (CPU & RAM breakdown by pod)
- Dual NVIDIA RTX A4000 GPU Metrics (Utilization, Thermals, VRAM)
- Power Consumption (Watts per GPU and Total)
- Network Bandwidth (Station physical NIC eno1 & K8s CNI bridge cni0)
- Host Node Resources (Total CPU, Total RAM)

Does NOT modify or overwrite any existing Grafana dashboards.
"""

import json
import urllib.request
import urllib.error

GRAFANA_URL = "http://localhost:3000"
AUTH_HEADER = "Basic YWRtaW46U2VydmVyQDEy"  # admin:Server@12
DATASOURCE_UID = "cfxqamywhfsowd"

dashboard_payload = {
    "dashboard": {
        "id": None,
        "uid": "suraksha-k8s-pods-monitoring",
        "title": "Kubernetes & Pods Monitoring (CPU, GPU, Power, RAM, Net)",
        "tags": ["kubernetes", "pods", "gpu", "power", "network", "crowdvision"],
        "timezone": "browser",
        "schemaVersion": 39,
        "version": 1,
        "refresh": "10s",
        "time": {
            "from": "now-30m",
            "to": "now"
        },
        "timepicker": {
            "refresh_intervals": ["5s", "10s", "30s", "1m", "5m", "15m", "30m", "1h"]
        },
        "panels": [
            # -------------------------------------------------------------
            # ROW 0: Overview KPI Stat Cards
            # -------------------------------------------------------------
            {
                "id": 1,
                "title": "Host Total CPU",
                "type": "stat",
                "gridPos": {"h": 4, "w": 3, "x": 0, "y": 0},
                "datasource": {"type": "prometheus", "uid": DATASOURCE_UID},
                "targets": [
                    {
                        "expr": "100 - (avg by (instance) (rate(node_cpu_seconds_total{mode=\"idle\"}[1m])) * 100)",
                        "legendFormat": "CPU",
                        "refId": "A"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "percent",
                        "min": 0,
                        "max": 100,
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "yellow", "value": 70},
                                {"color": "red", "value": 85}
                            ]
                        }
                    }
                },
                "options": {
                    "colorMode": "background",
                    "graphMode": "area",
                    "justifyMode": "auto",
                    "reduceOptions": {"calcs": ["lastNotNull"], "values": False}
                }
            },
            {
                "id": 2,
                "title": "Host RAM Used",
                "type": "stat",
                "gridPos": {"h": 4, "w": 3, "x": 3, "y": 0},
                "datasource": {"type": "prometheus", "uid": DATASOURCE_UID},
                "targets": [
                    {
                        "expr": "node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes",
                        "legendFormat": "RAM Used",
                        "refId": "A"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "bytes",
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "yellow", "value": 85899345920},  # 80 GB
                                {"color": "red", "value": 118111600640}   # 110 GB
                            ]
                        }
                    }
                },
                "options": {
                    "colorMode": "background",
                    "graphMode": "area",
                    "justifyMode": "auto",
                    "reduceOptions": {"calcs": ["lastNotNull"], "values": False}
                }
            },
            {
                "id": 3,
                "title": "Total GPU Power Draw",
                "type": "stat",
                "gridPos": {"h": 4, "w": 4, "x": 6, "y": 0},
                "datasource": {"type": "prometheus", "uid": DATASOURCE_UID},
                "targets": [
                    {
                        "expr": "sum(DCGM_FI_DEV_POWER_USAGE)",
                        "legendFormat": "Power",
                        "refId": "A"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "watt",
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "yellow", "value": 200},
                                {"color": "red", "value": 260}
                            ]
                        }
                    }
                },
                "options": {
                    "colorMode": "background",
                    "graphMode": "area",
                    "justifyMode": "auto",
                    "reduceOptions": {"calcs": ["lastNotNull"], "values": False}
                }
            },
            {
                "id": 4,
                "title": "GPU 0 (RTX A4000) Temp & Util",
                "type": "stat",
                "gridPos": {"h": 4, "w": 4, "x": 10, "y": 0},
                "datasource": {"type": "prometheus", "uid": DATASOURCE_UID},
                "targets": [
                    {
                        "expr": "DCGM_FI_DEV_GPU_TEMP{gpu=\"0\"}",
                        "legendFormat": "Temp: {{modelName}}",
                        "refId": "A"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "celsius",
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "yellow", "value": 85},
                                {"color": "red", "value": 93}
                            ]
                        }
                    }
                },
                "options": {
                    "colorMode": "value",
                    "graphMode": "none",
                    "justifyMode": "auto",
                    "reduceOptions": {"calcs": ["lastNotNull"], "values": False}
                }
            },
            {
                "id": 5,
                "title": "GPU 1 (RTX A4000) Temp & Util",
                "type": "stat",
                "gridPos": {"h": 4, "w": 4, "x": 14, "y": 0},
                "datasource": {"type": "prometheus", "uid": DATASOURCE_UID},
                "targets": [
                    {
                        "expr": "DCGM_FI_DEV_GPU_TEMP{gpu=\"1\"}",
                        "legendFormat": "Temp: {{modelName}}",
                        "refId": "A"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "celsius",
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "yellow", "value": 85},
                                {"color": "red", "value": 93}
                            ]
                        }
                    }
                },
                "options": {
                    "colorMode": "value",
                    "graphMode": "none",
                    "justifyMode": "auto",
                    "reduceOptions": {"calcs": ["lastNotNull"], "values": False}
                }
            },
            {
                "id": 6,
                "title": "Station Network Ingress (eno1)",
                "type": "stat",
                "gridPos": {"h": 4, "w": 3, "x": 18, "y": 0},
                "datasource": {"type": "prometheus", "uid": DATASOURCE_UID},
                "targets": [
                    {
                        "expr": "rate(container_network_receive_bytes_total{interface=\"eno1\"}[1m])",
                        "legendFormat": "Rx Rate",
                        "refId": "A"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "binBps",
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "blue", "value": 10485760}
                            ]
                        }
                    }
                },
                "options": {
                    "colorMode": "value",
                    "graphMode": "area",
                    "justifyMode": "auto",
                    "reduceOptions": {"calcs": ["lastNotNull"], "values": False}
                }
            },
            {
                "id": 7,
                "title": "Active K3s Pods",
                "type": "stat",
                "gridPos": {"h": 4, "w": 3, "x": 21, "y": 0},
                "datasource": {"type": "prometheus", "uid": DATASOURCE_UID},
                "targets": [
                    {
                        "expr": "count(count by (container_label_io_kubernetes_pod_name) (container_cpu_usage_seconds_total{container_label_io_kubernetes_pod_name!=\"\"}))",
                        "legendFormat": "Pods",
                        "refId": "A"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "short",
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "blue", "value": None}
                            ]
                        }
                    }
                },
                "options": {
                    "colorMode": "value",
                    "graphMode": "none",
                    "justifyMode": "auto",
                    "reduceOptions": {"calcs": ["lastNotNull"], "values": False}
                }
            },

            # -------------------------------------------------------------
            # ROW 1: Kubernetes Pods CPU & Memory Monitoring
            # -------------------------------------------------------------
            {
                "id": 100,
                "title": "Kubernetes Pods Workload Monitoring (CPU & RAM)",
                "type": "row",
                "gridPos": {"h": 1, "w": 24, "x": 0, "y": 4},
                "collapsed": False
            },
            {
                "id": 8,
                "title": "Pod CPU Utilization (Cores by Pod)",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 5},
                "datasource": {"type": "prometheus", "uid": DATASOURCE_UID},
                "targets": [
                    {
                        "expr": "sum by (container_label_io_kubernetes_pod_name) (rate(container_cpu_usage_seconds_total{container_label_io_kubernetes_pod_name!=\"\"}[1m]))",
                        "legendFormat": "{{container_label_io_kubernetes_pod_name}}",
                        "refId": "A"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "short",
                        "custom": {
                            "drawStyle": "line",
                            "lineInterpolation": "smooth",
                            "lineWidth": 2,
                            "fillOpacity": 15,
                            "showPoints": "never"
                        }
                    }
                },
                "options": {
                    "legend": {
                        "displayMode": "table",
                        "placement": "bottom",
                        "calcs": ["lastNotNull", "max"]
                    },
                    "tooltip": {"mode": "multi", "sort": "desc"}
                }
            },
            {
                "id": 9,
                "title": "Pod Memory Working Set (RAM by Pod)",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 5},
                "datasource": {"type": "prometheus", "uid": DATASOURCE_UID},
                "targets": [
                    {
                        "expr": "sum by (container_label_io_kubernetes_pod_name) (container_memory_working_set_bytes{container_label_io_kubernetes_pod_name!=\"\"})",
                        "legendFormat": "{{container_label_io_kubernetes_pod_name}}",
                        "refId": "A"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "bytes",
                        "custom": {
                            "drawStyle": "line",
                            "lineInterpolation": "smooth",
                            "lineWidth": 2,
                            "fillOpacity": 15,
                            "showPoints": "never"
                        }
                    }
                },
                "options": {
                    "legend": {
                        "displayMode": "table",
                        "placement": "bottom",
                        "calcs": ["lastNotNull", "max"]
                    },
                    "tooltip": {"mode": "multi", "sort": "desc"}
                }
            },

            # -------------------------------------------------------------
            # ROW 2: NVIDIA GPU Performance, Power & Thermals
            # -------------------------------------------------------------
            {
                "id": 200,
                "title": "NVIDIA GPU Performance, Power Consumption & Thermals",
                "type": "row",
                "gridPos": {"h": 1, "w": 24, "x": 0, "y": 13},
                "collapsed": False
            },
            {
                "id": 10,
                "title": "GPU Power Consumption (Watts)",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 6, "x": 0, "y": 14},
                "datasource": {"type": "prometheus", "uid": DATASOURCE_UID},
                "targets": [
                    {
                        "expr": "DCGM_FI_DEV_POWER_USAGE",
                        "legendFormat": "GPU {{gpu}} ({{modelName}})",
                        "refId": "A"
                    },
                    {
                        "expr": "sum(DCGM_FI_DEV_POWER_USAGE)",
                        "legendFormat": "Total Dual GPU Power",
                        "refId": "B"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "watt",
                        "custom": {
                            "drawStyle": "line",
                            "lineWidth": 2,
                            "fillOpacity": 10
                        }
                    }
                },
                "options": {
                    "legend": {"displayMode": "table", "placement": "bottom", "calcs": ["lastNotNull", "max"]},
                    "tooltip": {"mode": "multi"}
                }
            },
            {
                "id": 11,
                "title": "GPU Temperatures (°C)",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 6, "x": 6, "y": 14},
                "datasource": {"type": "prometheus", "uid": DATASOURCE_UID},
                "targets": [
                    {
                        "expr": "DCGM_FI_DEV_GPU_TEMP",
                        "legendFormat": "GPU {{gpu}} ({{modelName}})",
                        "refId": "A"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "celsius",
                        "min": 40,
                        "max": 105,
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "yellow", "value": 85},
                                {"color": "red", "value": 93}
                            ]
                        },
                        "custom": {
                            "drawStyle": "line",
                            "lineWidth": 2.5,
                            "fillOpacity": 10,
                            "thresholdsStyle": {"mode": "line"}
                        }
                    }
                },
                "options": {
                    "legend": {"displayMode": "table", "placement": "bottom", "calcs": ["lastNotNull", "max"]},
                    "tooltip": {"mode": "multi"}
                }
            },
            {
                "id": 12,
                "title": "GPU Compute Engine Utilization (%)",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 6, "x": 12, "y": 14},
                "datasource": {"type": "prometheus", "uid": DATASOURCE_UID},
                "targets": [
                    {
                        "expr": "DCGM_FI_DEV_GPU_UTIL",
                        "legendFormat": "GPU {{gpu}} Util",
                        "refId": "A"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "percent",
                        "min": 0,
                        "max": 100,
                        "custom": {
                            "drawStyle": "line",
                            "lineWidth": 2,
                            "fillOpacity": 15
                        }
                    }
                },
                "options": {
                    "legend": {"displayMode": "table", "placement": "bottom", "calcs": ["lastNotNull", "mean"]},
                    "tooltip": {"mode": "multi"}
                }
            },
            {
                "id": 13,
                "title": "GPU Framebuffer Memory (VRAM Used)",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 6, "x": 18, "y": 14},
                "datasource": {"type": "prometheus", "uid": DATASOURCE_UID},
                "targets": [
                    {
                        "expr": "DCGM_FI_DEV_FB_USED * 1024 * 1024",
                        "legendFormat": "GPU {{gpu}} VRAM",
                        "refId": "A"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "bytes",
                        "max": 17179869184,  # 16 GB
                        "custom": {
                            "drawStyle": "line",
                            "lineWidth": 2,
                            "fillOpacity": 20
                        }
                    }
                },
                "options": {
                    "legend": {"displayMode": "table", "placement": "bottom", "calcs": ["lastNotNull", "max"]},
                    "tooltip": {"mode": "multi"}
                }
            },

            # -------------------------------------------------------------
            # ROW 3: Network Bandwidth & Pod Traffic (Net)
            # -------------------------------------------------------------
            {
                "id": 300,
                "title": "Network Bandwidth & Traffic Consumption (Net)",
                "type": "row",
                "gridPos": {"h": 1, "w": 24, "x": 0, "y": 22},
                "collapsed": False
            },
            {
                "id": 14,
                "title": "Station Physical Network Traffic (eno1)",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 23},
                "datasource": {"type": "prometheus", "uid": DATASOURCE_UID},
                "targets": [
                    {
                        "expr": "rate(container_network_receive_bytes_total{interface=\"eno1\"}[1m])",
                        "legendFormat": "Station Ingress (Rx) — eno1",
                        "refId": "A"
                    },
                    {
                        "expr": "rate(container_network_transmit_bytes_total{interface=\"eno1\"}[1m])",
                        "legendFormat": "Station Egress (Tx) — eno1",
                        "refId": "B"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "binBps",
                        "custom": {
                            "drawStyle": "line",
                            "lineWidth": 2,
                            "fillOpacity": 15
                        }
                    }
                },
                "options": {
                    "legend": {"displayMode": "table", "placement": "bottom", "calcs": ["lastNotNull", "mean", "max"]},
                    "tooltip": {"mode": "multi"}
                }
            },
            {
                "id": 15,
                "title": "Kubernetes CNI Pod Bridge Traffic (cni0)",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 23},
                "datasource": {"type": "prometheus", "uid": DATASOURCE_UID},
                "targets": [
                    {
                        "expr": "rate(container_network_receive_bytes_total{interface=\"cni0\"}[1m])",
                        "legendFormat": "Pod Bridge Ingress (Rx) — cni0",
                        "refId": "A"
                    },
                    {
                        "expr": "rate(container_network_transmit_bytes_total{interface=\"cni0\"}[1m])",
                        "legendFormat": "Pod Bridge Egress (Tx) — cni0",
                        "refId": "B"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "binBps",
                        "custom": {
                            "drawStyle": "line",
                            "lineWidth": 2,
                            "fillOpacity": 15
                        }
                    }
                },
                "options": {
                    "legend": {"displayMode": "table", "placement": "bottom", "calcs": ["lastNotNull", "mean", "max"]},
                    "tooltip": {"mode": "multi"}
                }
            }
        ]
    },
    "overwrite": True
}

def post_dashboard():
    req = urllib.request.Request(
        f"{GRAFANA_URL}/api/dashboards/db",
        data=json.dumps(dashboard_payload).encode("utf-8"),
        headers={
            "Authorization": AUTH_HEADER,
            "Content-Type": "application/json"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            print("[SUCCESS] Dashboard created in Grafana:")
            print(f"  Status: {data.get('status')}")
            print(f"  UID:    {data.get('uid')}")
            print(f"  URL:    {GRAFANA_URL}{data.get('url')}")
    except urllib.error.HTTPError as e:
        print(f"[ERROR] Failed to post dashboard (HTTP {e.code}): {e.read().decode()}")

if __name__ == "__main__":
    post_dashboard()
