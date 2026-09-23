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
    return {
      id: bCam.camera_id,
      name: bCam.name, // DIRECT MAPPING - Fixes "name not used" issue
      rtspUrl: bCam.rtsp_url,
      fobType: bCam.fob_type,
      zoneId: bCam.zone_id,
      status: bCam.status,
      isActive: bCam.is_active,
      location: bCam.fob_type === 'HYD' ? 'Hyderabad Side' : 'Kazipet Side',
      runtimeStatus: bCam.runtime_status,
    } as Camera;
  }, []);

  // Fetch cameras from backend
  const fetchCameras = useCallback(async () => {
    if (isFetchingRef.current) {
      return;
    }
    isFetchingRef.current = true;

    try {
      const response = await rtspApi.listCameras();
      
      // We might need to fetch runtime status for each active camera if the list endpoint doesn't return it
      // For now, let's assume list returns the base config. 
      // The prompt says: "Poll GET /api/cameras/{id}/status ... to get authoritative runtime status"
      // So we might need a secondary step or the UI component does it.
      // For the list, we map what we have.
      
      const mappedCameras = await Promise.all(response.cameras.map(async (c) => {
        // Option: we could parallel fetch status here if list doesn't have it, 
        // but maybe better to let the UI component poll for active ones or do it here if list is small.
        // Let's rely on what list returns for now + basic mapping.
        
        let runtimeStatus = c.runtime_status;
        // If the camera is marked as 'active' (configured), we might want to know its stream status.
        // Doing this for ALL cameras every 5s might be heavy if there are many. 
        // But for < 20 cameras it's fine.
        if (includeRuntimeStatus && c.is_active && !runtimeStatus) {
             try {
               const statusRes = await rtspApi.getCameraRuntimeStatus(c.camera_id);
               runtimeStatus = statusRes.runtime_status;
             } catch (e) {
             }
        }
        
        return mapBackendCamera({ ...c, runtime_status: runtimeStatus });
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
