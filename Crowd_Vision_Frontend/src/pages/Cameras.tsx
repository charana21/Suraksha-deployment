import { useState } from 'react';
import { PageLayout } from '@/components/layout/PageLayout';
import { useCameras } from '@/hooks/useCameras';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Video, MapPin, Play, Square, RefreshCw, Pencil, Save, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { rtspApi } from '@/services/rtspApi';
import { Camera } from '@/types/camera';

// Extracted Component to prevent re-renders and focus loss
function CameraCard({ 
    camera, 
    isProcessing, 
    onStart, 
    onStop, 
    onUpdate 
}: { 
    camera: Camera; 
    isProcessing: boolean;
    onStart: (id: string, name: string) => void;
    onStop: (id: string, name: string) => void;
    onUpdate: (id: string, data: { name: string; rtspUrl: string }) => Promise<any>;
}) {
    const [isEditing, setIsEditing] = useState(false);
    const [editForm, setEditForm] = useState({ name: camera.name, rtspUrl: camera.rtspUrl });

    const handleSave = async () => {
        try {
            await onUpdate(camera.id, editForm);
            setIsEditing(false);
            toast.success('Camera updated successfully');
        } catch (error) {
            toast.error('Failed to update camera');
        }
    };

    const handleCancel = () => {
        setIsEditing(false);
        setEditForm({ name: camera.name, rtspUrl: camera.rtspUrl }); // Reset
    };

    const rawStatus = camera.runtimeStatus || (camera.status === 'active' ? 'connecting' : 'stopped');
    const isRunning = rawStatus === 'running';
    const isConnecting = rawStatus === 'connecting' || rawStatus === 'reconnecting';
    const isStopped = rawStatus === 'stopped';
    const isError = rawStatus === 'error';

    // Mask credentials in RTSP URL if present
    const maskedRtspUrl = camera.rtspUrl ? camera.rtspUrl.replace(/\/\/[^:]+:[^@]+@/, '//***:***@') : '';

    return (
        <div className="group relative bg-[#0F141E] border border-white/5 rounded-2xl overflow-hidden transition-all duration-500 hover:border-primary/20 hover:shadow-2xl">
            {/* Status Header Bar */}
            <div className={cn(
                "h-1 w-full",
                isRunning && "bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]",
                isConnecting && "bg-amber-500 shadow-[0_0_10px_rgba(245,158,11,0.5)]",
                isProcessing && "bg-yellow-500",
                (isStopped || isError) && "bg-red-500"
            )} />

            <div className="p-6">
                {isEditing ? (
                    <div className="space-y-4 mb-4">
                        <div className="space-y-2">
                            <label className="text-xs font-medium text-muted-foreground uppercase">Camera Name</label>
                            <Input
                                value={editForm.name}
                                onChange={(e) => setEditForm(prev => ({ ...prev, name: e.target.value }))}
                                className="bg-card/5 border-white/10"
                                autoFocus
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-xs font-medium text-muted-foreground uppercase">RTSP URL</label>
                            <Input
                                value={editForm.rtspUrl}
                                onChange={(e) => setEditForm(prev => ({ ...prev, rtspUrl: e.target.value }))}
                                className="bg-card/5 border-white/10 font-mono text-xs"
                            />
                        </div>
                        <div className="flex items-center gap-2 pt-2">
                            <Button size="sm" onClick={handleSave} className="w-full bg-emerald-600 hover:bg-emerald-700">
                                <Save className="w-4 h-4 mr-2" /> Save
                            </Button>
                            <Button size="sm" variant="ghost" onClick={handleCancel} className="w-full bg-card/5 hover:bg-card/10">
                                <X className="w-4 h-4 mr-2" /> Cancel
                            </Button>
                        </div>
                    </div>
                ) : (
                    <>
                        <div className="flex items-start justify-between mb-6">
                            <div className="flex items-center gap-4">
                                <div className={cn(
                                    "w-12 h-12 rounded-xl flex items-center justify-center transition-colors duration-500",
                                    isRunning ? "bg-emerald-500/10 text-emerald-500" : isConnecting ? "bg-amber-500/10 text-amber-500" : "bg-card/5 text-foreground/40"
                                )}>
                                    <Video className="w-6 h-6" />
                                </div>
                                <div>
                                    <h3 className="font-bold text-lg text-foreground leading-tight">{camera.name}</h3>
                                    <div className="flex items-center gap-1.5 text-xs font-medium text-foreground/30 uppercase tracking-widest mt-1">
                                        <MapPin className="w-3 h-3" />
                                        {camera.location}
                                    </div>
                                </div>
                            </div>
                            <Button variant="ghost" size="icon" className="group-hover:opacity-100 opacity-0 transition-opacity" onClick={() => setIsEditing(true)}>
                                <Pencil className="w-4 h-4 text-muted-foreground" />
                            </Button>
                        </div>

                        <div className="space-y-4">
                            {/* Status Indicator */}
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2.5">
                                    <div className={cn(
                                        "w-2.5 h-2.5 rounded-full",
                                        isRunning && "bg-emerald-500 animate-pulse",
                                        isConnecting && "bg-amber-500 animate-pulse",
                                        isProcessing && "bg-yellow-500 animate-spin",
                                        (isStopped || isError) && "bg-red-500"
                                    )} />
                                    <span className={cn(
                                        "text-xs font-black uppercase tracking-widest",
                                        isRunning && "text-emerald-500",
                                        isConnecting && "text-amber-500",
                                        isProcessing && "text-yellow-500",
                                        (isStopped || isError) && "text-red-500"
                                    )}>
                                        {isProcessing ? 'PROCESSING' : isRunning ? 'RUNNING' : isConnecting ? (rawStatus === 'reconnecting' ? 'RECONNECTING' : 'CONNECTING') : 'STOPPED'}
                                    </span>
                                </div>
                                {camera.shardId !== undefined && (
                                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/5 border border-white/10 text-muted-foreground">
                                        Shard {camera.shardId}
                                    </span>
                                )}
                            </div>

                            <div className="text-xs text-muted-foreground truncate font-mono bg-background/20 p-2 rounded border border-white/5" title={maskedRtspUrl}>
                                {maskedRtspUrl}
                            </div>

                            {/* Action Buttons */}
                            <div className="grid grid-cols-2 gap-3 mt-6">
                                <Button
                                    onClick={() => onStart(camera.id, camera.name)}
                                    disabled={isRunning || isConnecting || isProcessing}
                                    className={cn(
                                        "rounded-xl font-bold uppercase tracking-widest text-[10px] h-11",
                                        isRunning || isConnecting ? "bg-card/5 border border-white/5" : "bg-emerald-500 hover:bg-emerald-600 text-foreground"
                                    )}
                                >
                                    <Play className="w-3 h-3 mr-2 fill-current" />
                                    Start
                                </Button>
                                <Button
                                    onClick={() => onStop(camera.id, camera.name)}
                                    disabled={(!isRunning && !isConnecting) || isProcessing}
                                    variant="secondary"
                                    className={cn(
                                        "rounded-xl font-bold uppercase tracking-widest text-[10px] h-11 border border-white/5",
                                        (!isRunning && !isConnecting) ? "bg-card/5" : "bg-card/10 hover:bg-card/20 text-foreground"
                                    )}
                                >
                                    <Square className="w-3 h-3 mr-2 fill-current" />
                                    Stop
                                </Button>
                            </div>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}

export default function Cameras() {
  const { cameras, refreshCameras, startCamera, stopCamera, updateCamera, isLoading, error } = useCameras({ includeRuntimeStatus: true });
  const [localProcessing, setLocalProcessing] = useState<Record<string, boolean>>({});

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<{ name: string; rtspUrl: string }>({ name: '', rtspUrl: '' });

  const handleStart = async (id: string, name: string) => {
    setLocalProcessing(prev => ({ ...prev, [id]: true }));
    toast.info(`Starting ${name}...`);

    try {
      await startCamera(id);
      toast.success(`${name} is likely running`);
    } catch (err) {
      toast.error(`Failed to start ${name}`);
    } finally {
       setLocalProcessing(prev => ({ ...prev, [id]: false }));
    }
  };

  const handleStop = async (id: string, name: string) => {
    setLocalProcessing(prev => ({ ...prev, [id]: true }));
    toast.info(`Stopping ${name}...`);

    try {
      await stopCamera(id);
      toast.info(`${name} stop command sent`);
    } catch (err) {
      toast.error(`Failed to stop ${name}`);
    } finally {
       setLocalProcessing(prev => ({ ...prev, [id]: false }));
    }
  };

  const hyderabadCameras = cameras.filter(c => c.fobType === 'HYD');
  const kazipetCameras = cameras.filter(c => c.fobType === 'KZJ');
  const platformBookingCameras = cameras.filter(c => c.fobType !== 'HYD' && c.fobType !== 'KZJ');

  const EmptyState = () => (
    <div className="py-20 bg-[#0F141E] border border-dashed border-white/10 rounded-3xl text-center">
        <Video className="w-16 h-16 text-foreground/10 mx-auto mb-6" />
        <h3 className="text-xl font-bold text-foreground mb-2">No Cameras Found</h3>
        <p className="text-sm text-foreground/30 max-w-sm mx-auto">
        No cameras configured for this section.
        </p>
    </div>
  );

  return (
    <PageLayout>
      <div className="space-y-8 animate-fade-in">
        {/* Page Header */}
        <div className="flex items-center justify-between pb-4 border-b border-white/5">
          <div>
            <h1 className="text-3xl font-black text-foreground tracking-tight">Cameras</h1>
            <p className="text-sm text-foreground/40 mt-1">
              Manage live CCTV streams across Secunderabad Station ({cameras.length} active)
            </p>
          </div>
           {error && (
               <div className="flex items-center gap-2 text-destructive font-bold bg-destructive/10 px-4 py-2 rounded-lg">
                   <span>Backend Offline</span>
                   <Button variant="ghost" size="icon" onClick={() => refreshCameras()}><RefreshCw className="w-4 h-4" /></Button>
               </div>
           )}
        </div>

        <Tabs defaultValue="ALL" className="w-full">
          <TabsList className="grid w-full grid-cols-2 lg:grid-cols-4 mb-8 bg-card/5 p-1 rounded-xl">
            <TabsTrigger
                value="ALL"
                className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground rounded-lg font-bold tracking-wide"
            >
                ALL CAMERAS ({cameras.length})
            </TabsTrigger>
            <TabsTrigger
                value="HYD"
                className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground rounded-lg font-bold tracking-wide"
            >
                HYDERABAD SIDE ({hyderabadCameras.length})
            </TabsTrigger>
            <TabsTrigger
                value="KZJ"
                className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground rounded-lg font-bold tracking-wide"
            >
                KAZIPET SIDE ({kazipetCameras.length})
            </TabsTrigger>
            <TabsTrigger
                value="PLATFORM_BOOKING"
                className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground rounded-lg font-bold tracking-wide"
            >
                PLATFORM / BOOKING ({platformBookingCameras.length})
            </TabsTrigger>
          </TabsList>
          
          <TabsContent value="ALL" className="mt-0">
             {cameras.length === 0 ? <EmptyState /> : (
                 <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                     {cameras.map(camera => (
                                 <CameraCard
                                     key={camera.id}
                                     camera={camera}
                            isProcessing={localProcessing[camera.id] || false}
                            onStart={handleStart}
                            onStop={handleStop}
                            onUpdate={updateCamera}
                         />
                     ))}
                 </div>
             )}
          </TabsContent>

          <TabsContent value="HYD" className="mt-0">
             {hyderabadCameras.length === 0 ? <EmptyState /> : (
                 <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                     {hyderabadCameras.map(camera => (
                                 <CameraCard
                                     key={camera.id}
                                     camera={camera}
                            isProcessing={localProcessing[camera.id] || false}
                            onStart={handleStart}
                            onStop={handleStop}
                            onUpdate={updateCamera}
                         />
                     ))}
                 </div>
             )}
          </TabsContent>
          
          <TabsContent value="KZJ" className="mt-0">
            {kazipetCameras.length === 0 ? <EmptyState /> : (
                 <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                     {kazipetCameras.map(camera => (
                         <CameraCard
                            key={camera.id}
                            camera={camera}
                            isProcessing={localProcessing[camera.id] || false}
                            onStart={handleStart}
                            onStop={handleStop}
                            onUpdate={updateCamera}
                         />
                     ))}
                 </div>
             )}
          </TabsContent>

          <TabsContent value="PLATFORM_BOOKING" className="mt-0">
            {platformBookingCameras.length === 0 ? <EmptyState /> : (
                 <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                     {platformBookingCameras.map(camera => (
                         <CameraCard
                            key={camera.id}
                            camera={camera}
                            isProcessing={localProcessing[camera.id] || false}
                            onStart={handleStart}
                            onStop={handleStop}
                            onUpdate={updateCamera}
                         />
                     ))}
                 </div>
             )}
          </TabsContent>
        </Tabs>

      </div>
    </PageLayout>
  );
}
