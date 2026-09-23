"""
Video analysis endpoints
"""
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
import aiofiles
import uuid
import os
from config.config import get_settings
from services.video_processor import VideoProcessor, processing_jobs
from api.security import require_authorized

router = APIRouter()
settings = get_settings()


@router.post(
    "/analyze",
    dependencies=[require_authorized],
    responses={400: {"description": "Invalid video content type"}},
)
async def analyze_video(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...)
):
    """Upload video for analysis"""
    allowed_types = ['video/mp4', 'video/avi', 'video/webm']
    
    if video.content_type not in allowed_types:
        raise HTTPException(400, f"Invalid type. Allowed: {allowed_types}")
    
    job_id = str(uuid.uuid4())
    
    ext = os.path.splitext(video.filename)[1] or '.mp4'
    upload_path = os.path.join(settings.upload_dir, f"{job_id}{ext}")
    output_path = os.path.join(settings.output_dir, f"{job_id}_analyzed.mp4")
    
    async with aiofiles.open(upload_path, 'wb') as f:
        content = await video.read()
        await f.write(content)
    
    processing_jobs[job_id] = {
        'status': 'queued',
        'progress': 0,
        'fileName': video.filename,
        'uploadPath': upload_path,
        'outputPath': output_path
    }
    
    processor = VideoProcessor()
    background_tasks.add_task(processor.process_video_task, job_id, upload_path, output_path)
    
    return JSONResponse({
        'jobId': job_id,
        'status': 'queued'
    })


@router.get(
    "/status/{job_id}",
    responses={404: {"description": "Job not found"}},
)
async def get_status(job_id: str):
    """Get processing status"""
    if job_id not in processing_jobs:
        raise HTTPException(404, 'Job not found')
    
    job = processing_jobs[job_id]
    
    response = {
        'jobId': job_id,
        'status': job['status'],
        'progress': job['progress'],
        'fileName': job.get('fileName')
    }
    
    if job['status'] == 'complete' and 'result' in job:
        result = job['result']
        response.update({
            'processedVideoUrl': f'/api/video/{job_id}',
            'analyticsUrl': result.get('analyticsUrl'),
            'processingTime': result.get('processingTime'),
            'frameCount': result.get('frameCount'),
            'heatmapsAvailable': True
        })
    
    if job['status'] == 'error':
        response['error'] = job.get('error', 'Unknown error')
    
    return JSONResponse(response)


@router.get(
    "/video/{job_id}",
    responses={
        400: {"description": "Video not ready"},
        404: {"description": "Job or video not found"},
    },
)
async def get_video(job_id: str):
    """Download processed video"""
    if job_id not in processing_jobs:
        raise HTTPException(404, 'Job not found')
    
    job = processing_jobs[job_id]
    
    if job.get('status') != 'complete':
        raise HTTPException(400, f'Video not ready. Status: {job.get("status")}')
    
    path = job.get('outputPath')
    
    if not path or not os.path.exists(path):
        raise HTTPException(404, 'Video not found')
    
    return FileResponse(
        path,
        media_type='video/mp4',
        headers={'Content-Disposition': f'inline; filename="{job_id}.mp4"'}
    )
