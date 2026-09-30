"""
Health check endpoints for production monitoring
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import torch
from datetime import datetime
import os
import psutil
from config.config import get_settings
from db.mongodb import get_database
from utils.logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)


def _get_overall_status(issues):
    if "database" in issues or "gpu_unavailable" in issues:
        return "unhealthy"
    if issues:
        return "degraded"
    return "healthy"


async def _get_database_status(issues):
    db_status = {"connected": False, "error": None}
    try:
        db = get_database()
        await db.command("ping")
        db_status["connected"] = True
    except Exception:
        db_status["error"] = "MongoDB connection failed"
        issues.append("database")
        logger.exception("Health check: MongoDB connection failed")
    return db_status


def _get_gpu_status(settings, issues):
    gpu_status = {
        "available": torch.cuda.is_available(),
        "device_count": 0,
        "devices": []
    }

    if torch.cuda.is_available():
        gpu_status["device_count"] = torch.cuda.device_count()
        for index in range(torch.cuda.device_count()):
            try:
                props = torch.cuda.get_device_properties(index)
                memory_allocated = torch.cuda.memory_allocated(index) / (1024 ** 3)
                memory_total = props.total_memory / (1024 ** 3)
                memory_percent = (memory_allocated / memory_total) * 100 if memory_total > 0 else 0

                gpu_status["devices"].append({
                    "id": index,
                    "name": props.name,
                    "memory_used_gb": round(memory_allocated, 2),
                    "memory_total_gb": round(memory_total, 2),
                    "memory_percent": round(memory_percent, 1)
                })

                if memory_percent > 90:
                    issues.append("gpu_memory")
                    logger.warning("Health check: GPU %s memory usage at %.1f%%", index, memory_percent)
            except Exception as exc:
                gpu_status["devices"].append({
                    "id": index,
                    "error": str(exc)
                })
    elif settings.device == "cuda":
        issues.append("gpu_unavailable")
        logger.warning("Health check: CUDA requested but not available")

    return gpu_status


def _get_streams_status(request):
    streams_status = {"active": 0, "total": 0, "streams": []}
    try:
        rtsp_manager = getattr(request.app.state, "rtsp_manager", None)
        if rtsp_manager:
            all_streams = rtsp_manager.get_all_streams()
            streams_status["total"] = len(all_streams)
            for info in all_streams:
                stream_info = {
                    "stream_id": info.get("stream_id", "Unknown"),
                    "name": info.get("stream_id", "Unknown"),
                    "status": info.get("status", "unknown"),
                    "fps": info.get("fps", 0)
                }
                streams_status["streams"].append(stream_info)
                if info.get("status") == "running":
                    streams_status["active"] += 1
    except Exception:
        logger.exception("Health check: Failed to get stream status")
    return streams_status


async def _get_inference_status(request, settings, issues):
    inference_status = {}
    try:
        from services.batched_inference import BatchedInferenceService
        service = BatchedInferenceService.get_instance()
        if service is not None:
            stats = service.stats
            avg_latency = stats.get("worker_avg_inference_ms", 0)
            queue_size = stats.get("queue_size", 0)
            queue_capacity = settings.inference_queue_size
            queue_util = queue_size / queue_capacity if queue_capacity > 0 else 0
            total_frames = stats.get("worker_frames", 1)
            errors = stats.get("worker_errors", 0)

            inference_status = {
                "latency_ms": round(avg_latency, 2),
                "queue_wait_ms_p50": round(stats.get("queue_wait_p50_ms", 0), 2),
                "queue_wait_ms_p95": round(stats.get("queue_wait_p95_ms", 0), 2),
                "model_ms_p50": round(stats.get("worker_model_p50_ms", 0), 2),
                "model_ms_p95": round(stats.get("worker_model_p95_ms", 0), 2),
                "inference_e2e_ms_p50": round(stats.get("worker_e2e_p50_ms", 0), 2),
                "inference_e2e_ms_p95": round(stats.get("worker_e2e_p95_ms", 0), 2),
                "queue_utilization": round(queue_util, 3),
                "queue_size": queue_size,
                "queue_capacity": queue_capacity,
                "error_rate": round(errors / max(total_frames, 1), 4),
                "total_frames": total_frames,
                "total_errors": errors,
                "batches_processed": stats.get("worker_batches", 0),
                "avg_batch_size": round(stats.get("worker_avg_batch_size", 0), 2),
            }

            if avg_latency > 500:
                issues.append("latency_sla_breach")
            if queue_util > 0.8:
                issues.append("queue_backlog")
            if errors / max(total_frames, 1) > 0.01:
                issues.append("high_error_rate")
    except ImportError:
        pass
    except Exception:
        logger.exception("Health check: Failed to get inference stats")

    try:
        rtsp_manager = getattr(request.app.state, "rtsp_manager", None)
        if rtsp_manager is not None:
            roi_p50_samples = []
            roi_p95_samples = []
            e2e_p50_samples = []
            e2e_p95_samples = []
            for worker in rtsp_manager._streams.values():
                ts = worker.get_timing_stats()
                if ts["roi_ms_p50"] > 0:
                    roi_p50_samples.append(ts["roi_ms_p50"])
                if ts["roi_ms_p95"] > 0:
                    roi_p95_samples.append(ts["roi_ms_p95"])
                if ts["end_to_end_ms_p50"] > 0:
                    e2e_p50_samples.append(ts["end_to_end_ms_p50"])
                if ts["end_to_end_ms_p95"] > 0:
                    e2e_p95_samples.append(ts["end_to_end_ms_p95"])

            if roi_p50_samples:
                inference_status["roi_ms_p50"] = round(sum(roi_p50_samples) / len(roi_p50_samples), 2)
            if roi_p95_samples:
                inference_status["roi_ms_p95"] = round(sum(roi_p95_samples) / len(roi_p95_samples), 2)
            if e2e_p50_samples:
                inference_status["end_to_end_ms_p50"] = round(sum(e2e_p50_samples) / len(e2e_p50_samples), 2)
            if e2e_p95_samples:
                inference_status["end_to_end_ms_p95"] = round(sum(e2e_p95_samples) / len(e2e_p95_samples), 2)
    except Exception:
        logger.exception("Health check: Failed collecting RTSP timing metrics")

    return inference_status


@router.get("/health")
async def health_check(request: Request):
    """
    Comprehensive system health check for production monitoring.

    Returns:
        - status: "healthy", "degraded", or "unhealthy"
        - database: MongoDB connection status
        - gpu: GPU availability and memory usage
        - streams: Active RTSP stream count
        - system: CPU and memory usage
    """
    settings = get_settings()
    issues = []

    db_status = await _get_database_status(issues)
    gpu_status = _get_gpu_status(settings, issues)
    streams_status = _get_streams_status(request)
    inference_status = await _get_inference_status(request, settings, issues)

    system_status = {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent if os.name != "nt" else psutil.disk_usage("C:\\").percent
    }

    if system_status["memory_percent"] > 90:
        issues.append("memory")
        logger.warning("Health check: System memory at %s%%", system_status["memory_percent"])
    if system_status["disk_percent"] > 90:
        issues.append("disk")
        logger.warning("Health check: Disk usage at %s%%", system_status["disk_percent"])

    overall_status = _get_overall_status(issues)

    return JSONResponse({
        "status": overall_status,
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "environment": settings.app_env,
        "issues": issues if issues else None,
        "database": db_status,
        "gpu": gpu_status,
        "streams": streams_status,
        "system": system_status,
        "inference": inference_status if inference_status else None
    })


@router.get("/health/simple")
async def simple_health_check():
    """
    Simple health check for load balancers and uptime monitoring.
    Returns 200 if service is running, regardless of component status.
    """
    return JSONResponse({
        "status": "ok",
        "timestamp": datetime.now().isoformat()
    })


@router.get("/health/inference")
async def inference_health_check(request: Request):
    """
    Detailed inference service health check.

    Monitors the GPU inference pipeline including:
    - Inference latency vs SLA
    - Queue utilization
    - Error rates
    - GPU memory pressure
    - Circuit breaker status

    Returns:
        - healthy: Boolean overall health status
        - issues: List of detected issues
        - metrics: Detailed performance metrics
        - slas: Service level agreement thresholds
    """
    settings = get_settings()
    issues = []
    metrics = {}

    try:
        from services.batched_inference import BatchedInferenceService
        service = BatchedInferenceService.get_instance()

        if service is not None:
            stats = service.stats
            avg_latency = stats.get("worker_avg_inference_ms", 0)
            metrics["latency_ms"] = round(avg_latency, 2)
            if avg_latency > 500:
                issues.append("latency_sla_breach")

            metrics["queue_wait_ms_p50"] = round(stats.get("queue_wait_p50_ms", 0), 2)
            metrics["queue_wait_ms_p95"] = round(stats.get("queue_wait_p95_ms", 0), 2)
            metrics["model_ms_p50"] = round(stats.get("worker_model_p50_ms", 0), 2)
            metrics["model_ms_p95"] = round(stats.get("worker_model_p95_ms", 0), 2)
            metrics["inference_e2e_ms_p50"] = round(stats.get("worker_e2e_p50_ms", 0), 2)
            metrics["inference_e2e_ms_p95"] = round(stats.get("worker_e2e_p95_ms", 0), 2)

            queue_size = stats.get("queue_size", 0)
            queue_capacity = settings.inference_queue_size
            queue_util = queue_size / queue_capacity if queue_capacity > 0 else 0
            metrics["queue_utilization"] = round(queue_util, 3)
            metrics["queue_size"] = queue_size
            metrics["queue_capacity"] = queue_capacity
            if queue_util > 0.8:
                issues.append("queue_backlog")

            total_frames = stats.get("worker_frames", 1)
            errors = stats.get("worker_errors", 0)
            error_rate = errors / max(total_frames, 1)
            metrics["error_rate"] = round(error_rate, 4)
            metrics["total_frames"] = total_frames
            metrics["total_errors"] = errors
            if error_rate > 0.01:
                issues.append("high_error_rate")

            metrics["batches_processed"] = stats.get("worker_batches", 0)
            metrics["avg_batch_size"] = round(stats.get("worker_avg_batch_size", 0), 2)

    except ImportError:
        issues.append("inference_service_unavailable")
    except Exception:
        issues.append("inference_stats_error")
        logger.exception("Inference health check error")

    if torch.cuda.is_available():
        try:
            allocated = torch.cuda.memory_allocated()
            total = torch.cuda.get_device_properties(0).total_memory
            gpu_util = (allocated / total) * 100
            metrics["gpu_memory_percent"] = round(gpu_util, 1)
            metrics["gpu_memory_allocated_gb"] = round(allocated / (1024**3), 2)
            metrics["gpu_memory_total_gb"] = round(total / (1024**3), 2)
            if gpu_util > 90:
                issues.append("gpu_memory_pressure")
        except Exception:
            logger.exception("Failed to get GPU memory")
            metrics["gpu_memory_percent"] = None

    try:
        from utils.circuit_breaker import CircuitBreakerRegistry
        registry = CircuitBreakerRegistry.get_instance()
        open_circuits = registry.list_open_circuits()
        if open_circuits:
            issues.append("circuit_breakers_open")
            metrics["open_circuits"] = open_circuits
    except ImportError:
        pass
    except Exception:
        pass

    try:
        rtsp_manager = getattr(request.app.state, "rtsp_manager", None)
        if rtsp_manager is not None:
            roi_p50_samples = []
            roi_p95_samples = []
            e2e_p50_samples = []
            e2e_p95_samples = []

            for worker in rtsp_manager._streams.values():
                timing_stats = worker.get_timing_stats()
                if timing_stats["roi_ms_p50"] > 0:
                    roi_p50_samples.append(timing_stats["roi_ms_p50"])
                if timing_stats["roi_ms_p95"] > 0:
                    roi_p95_samples.append(timing_stats["roi_ms_p95"])
                if timing_stats["end_to_end_ms_p50"] > 0:
                    e2e_p50_samples.append(timing_stats["end_to_end_ms_p50"])
                if timing_stats["end_to_end_ms_p95"] > 0:
                    e2e_p95_samples.append(timing_stats["end_to_end_ms_p95"])

            if roi_p50_samples:
                metrics["roi_ms_p50"] = round(sum(roi_p50_samples) / len(roi_p50_samples), 2)
            if roi_p95_samples:
                metrics["roi_ms_p95"] = round(sum(roi_p95_samples) / len(roi_p95_samples), 2)
            if e2e_p50_samples:
                metrics["end_to_end_ms_p50"] = round(sum(e2e_p50_samples) / len(e2e_p50_samples), 2)
            if e2e_p95_samples:
                metrics["end_to_end_ms_p95"] = round(sum(e2e_p95_samples) / len(e2e_p95_samples), 2)
    except Exception:
        logger.exception("Failed collecting RTSP timing metrics")

    healthy = len(issues) == 0

    slas = {
        "max_latency_ms": 500,
        "max_queue_utilization": 0.8,
        "max_error_rate": 0.01,
        "max_gpu_memory_percent": 90
    }

    return JSONResponse({
        "healthy": healthy,
        "timestamp": datetime.now().isoformat(),
        "issues": issues if issues else None,
        "metrics": metrics,
        "slas": slas
    })
