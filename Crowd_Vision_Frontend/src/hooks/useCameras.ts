import { useState, useEffect, useCallback, useRef } from 'react';
import { Camera } from '@/types/camera';
import { rtspApi, BackendCamera } from '@/services/rtspApi';

const POLL_INTERVAL = 5000; // Poll every 5 seconds as suggested

interface UseCamerasOptions {
  includeRuntimeStatus?: boolean;
}

export function useCameras(options: UseCamerasOptions = {}) {
  const { includeRuntimeStatus = false } = options;
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [selectedCameraId, setSelectedCameraId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isFetchingRef = useRef(false);

  // Convert backend camera object to Frontend Camera interface
  const mapBackendCamera = useCallback((bCam: BackendCamera): Camera => {
    let loc = bCam.location;
    if (!loc || loc === 'Unknown') {
      if (bCam.fob_type === 'HYD') loc = 'Hyderabad Side';
      else if (bCam.fob_type === 'KZJ') loc = 'Kazipet Side';
      else loc = 'Platform / Booking';
    }
    return {
      id: bCam.camera_id,
      name: bCam.name,
      rtspUrl: bCam.rtsp_url,
      fobType: bCam.fob_type,
      zoneId: bCam.zone_id,
      status: bCam.status,
      isActive: bCam.is_active,
      location: loc,
      runtimeStatus: bCam.runtime_status,
      shardId: bCam.shard_id,
      isLocalWorker: bCam.is_local_worker,
      liveFrameAgeMs: bCam.live_frame_age_ms,
    } as Camera;
  }, []);

  // Fetch cameras from backend
  const fetchCameras = useCallback(async () => {
    if (isFetchingRef.current) {
      return;
    }
    isFetchingRef.current = true;

    try {
      // Query active cameras so all 20 active cameras are fetched
      const response = await rtspApi.listCameras({ status: 'active' });
      
      const mappedCameras = await Promise.all(response.cameras.map(async (c) => {
        let runtimeStatus = c.runtime_status;
        let isLocalWorker = c.is_local_worker;
        let liveFrameAgeMs = c.live_frame_age_ms;
        let shardId = c.shard_id;

        if (includeRuntimeStatus && c.status === 'active') {
          try {
            const statusRes = await rtspApi.getCameraRuntimeStatus(c.camera_id);
            if (statusRes.runtime_status) {
              runtimeStatus = statusRes.runtime_status;
            }
            if (statusRes.shard_id !== undefined) shardId = statusRes.shard_id;
            if (statusRes.is_local_worker !== undefined) isLocalWorker = statusRes.is_local_worker;
            if (statusRes.live_frame_age_ms !== undefined) liveFrameAgeMs = statusRes.live_frame_age_ms;
          } catch (e) {
            // Keep existing status on transient poll error
          }
        }
        
        return mapBackendCamera({
          ...c,
          runtime_status: runtimeStatus,
          is_local_worker: isLocalWorker,
          live_frame_age_ms: liveFrameAgeMs,
          shard_id: shardId
        });
      }));

      setCameras(mappedCameras);

      // Auto-select first camera if none selected
      if (!selectedCameraId && mappedCameras.length > 0) {
        setSelectedCameraId(mappedCameras[0].id);
      }

      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch cameras');
    } finally {
      isFetchingRef.current = false;
      setIsLoading(false);
    }
  }, [includeRuntimeStatus, mapBackendCamera, selectedCameraId]);

  // Initial fetch and polling
  useEffect(() => {
    fetchCameras();

    const interval = setInterval(fetchCameras, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchCameras]);

  // Start a camera stream
  const startCamera = async (id: string) => {
    try {
      await rtspApi.startCamera(id);
      await fetchCameras(); // Refresh state
    } catch (err) {
      throw err;
    }
  };

  // Stop a camera stream
  const stopCamera = async (id: string) => {
    try {
      await rtspApi.stopCamera(id);
      await fetchCameras(); // Refresh state
    } catch (err) {
      throw err;
    }
  };

  // Get stream status for a specific camera
  const getCameraStatus = async (id: string) => {
    try {
      return await rtspApi.getCameraRuntimeStatus(id);
    } catch (err) {
      throw err;
    }
  };

  // Get frame URL for a camera
  const getFrameUrl = (id: string, heatmap: boolean = false) => {
    return rtspApi.getFrameUrl(id, { heatmap });
  };

  // Update camera details
  const updateCamera = async (id: string, data: { name: string; rtspUrl: string }) => {
    try {
      // Call Backend
      const updatedBackendCamera = await rtspApi.updateCamera(id, { name: data.name, rtsp_url: data.rtspUrl });
      
      // Update Local State immediately
      setCameras((prev) => prev.map(c => 
        c.id === id 
            ? { ...c, name: updatedBackendCamera.name, rtspUrl: updatedBackendCamera.rtsp_url }
            : c
      ));
      
      return updatedBackendCamera;
    } catch (err) {
      throw err;
    }
  };

  const selectedCamera = cameras.find((c) => c.id === selectedCameraId) || null;

  return {
    cameras,
    selectedCamera,
    selectedCameraId,
    setSelectedCameraId,
    startCamera,
    stopCamera,
    updateCamera,
    getCameraStatus,
    getFrameUrl,
    refreshCameras: fetchCameras,
    isLoading,
    error,
  };
}
