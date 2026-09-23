import { Camera } from '@/types/camera';
import { cn } from '@/lib/utils';
import { Video, Circle, ChevronDown } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

interface CameraSelectorProps {
  cameras: Camera[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function CameraSelector({ cameras, selectedId, onSelect }: CameraSelectorProps) {
  const selectedCamera = cameras.find(c => c.id === selectedId);

  return (
    <div className="glass-panel p-4">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Video className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm font-medium text-foreground">Camera Source</span>
        </div>
        
        <Select value={selectedId || ''} onValueChange={onSelect}>
          <SelectTrigger className="w-[280px]">
            <SelectValue placeholder="Select camera">
              {selectedCamera && (
                <div className="flex items-center gap-2">
                  <Circle
                    className={cn(
                      'w-2 h-2 fill-current',
                      selectedCamera.status === 'running' && 'text-status-active',
                      selectedCamera.status === 'connecting' && 'text-status-warning',
                      (selectedCamera.status === 'error' || selectedCamera.status === 'stopped') && 'text-status-inactive'
                    )}
                  />
                  <span className="truncate">{selectedCamera.name}</span>
                </div>
              )}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            {cameras.map((camera) => (
              <SelectItem key={camera.id} value={camera.id}>
                <div className="flex items-center gap-3 w-full">
                  <Circle
                    className={cn(
                      'w-2 h-2 fill-current flex-shrink-0',
                          camera.status === 'running' && 'text-status-active',
                          camera.status === 'connecting' && 'text-status-warning',
                          (camera.status === 'error' || camera.status === 'stopped') && 'text-status-inactive'
                        )}
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{camera.name}</p>
                    <p className="text-xs text-muted-foreground truncate">{camera.location}</p>
                  </div>
                  <span className="text-xs text-muted-foreground capitalize">{camera.status}</span>
                </div>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Quick camera chips for fast switching */}
        <div className="hidden md:flex items-center gap-2 flex-wrap">
          {cameras.slice(0, 5).map((camera) => (
            <button
              key={camera.id}
              onClick={() => onSelect(camera.id)}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors',
                selectedId === camera.id
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
              )}
            >
              <Circle
                className={cn(
                  'w-1.5 h-1.5 fill-current',
                  camera.status === 'running' && 'text-status-active',
                  camera.status === 'connecting' && 'text-status-warning',
                  (camera.status === 'error' || camera.status === 'stopped') && 'text-status-inactive',
                  selectedId === camera.id && 'text-primary-foreground'
                )}
              />
              {camera.location}
            </button>
          ))}
          {cameras.length > 5 && (
            <span className="text-xs text-muted-foreground">+{cameras.length - 5} more</span>
          )}
        </div>
      </div>
    </div>
  );
}
