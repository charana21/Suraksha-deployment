import React, { useCallback, useState } from 'react';
import { Upload, Film, X, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import type { UploadState } from '@/types/analysis';

interface VideoUploaderProps {
  onUpload: (file: File) => void;
  uploadState: UploadState;
  onCancel: () => void;
}

const ACCEPTED_FORMATS = ['video/mp4', 'video/avi', 'video/quicktime', 'video/x-msvideo'];
const MAX_FILE_SIZE = 500 * 1024 * 1024; // 500MB

export const VideoUploader: React.FC<VideoUploaderProps> = ({
  onUpload,
  uploadState,
  onCancel,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [dragError, setDragError] = useState<string | null>(null);

  const validateFile = (file: File): string | null => {
    if (!ACCEPTED_FORMATS.includes(file.type)) {
      return 'Invalid file format. Please upload MP4, AVI, or MOV files.';
    }
    if (file.size > MAX_FILE_SIZE) {
      return 'File too large. Maximum size is 500MB.';
    }
    return null;
  };

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      setDragError(null);

      const file = e.dataTransfer.files[0];
      if (file) {
        const error = validateFile(file);
        if (error) {
          setDragError(error);
          return;
        }
        onUpload(file);
      }
    },
    [onUpload]
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setDragError(null);
      const file = e.target.files?.[0];
      if (file) {
        const error = validateFile(file);
        if (error) {
          setDragError(error);
          return;
        }
        onUpload(file);
      }
    },
    [onUpload]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  if (uploadState.status === 'uploading' || uploadState.status === 'processing') {
    return (
      <div className="glass-panel glow-border p-8 animate-fade-in-up">
        <div className="flex flex-col items-center gap-6">
          <div className="relative">
            <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center">
              <Film className="w-10 h-10 text-primary animate-pulse" />
            </div>
            <div className="absolute inset-0 rounded-full border-2 border-primary/30 animate-ping" />
          </div>

          <div className="text-center space-y-2">
            <h3 className="text-lg font-semibold text-foreground">
              {uploadState.status === 'uploading' ? 'Uploading Video' : 'Analyzing Video with AI'}
            </h3>
            <p className="text-sm text-muted-foreground font-mono">
              {uploadState.fileName}
            </p>
            {uploadState.status === 'processing' && (
              <p className="text-xs text-muted-foreground">
                Running YOLOv8 detection & density analysis...
              </p>
            )}
          </div>

          <div className="w-full max-w-md space-y-2">
            <Progress value={uploadState.progress} className="h-2" />
            <div className="flex justify-between text-xs text-muted-foreground font-mono">
              <span>{uploadState.progress}%</span>
              <span>
                {uploadState.status === 'uploading'
                  ? 'Uploading to server...'
                  : 'Processing frames...'}
              </span>
            </div>
          </div>

          <Button variant="outline" size="sm" onClick={onCancel}>
            <X className="w-4 h-4 mr-2" />
            Cancel
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'glass-panel glow-border p-8 transition-all duration-300 animate-fade-in-up',
        isDragging && 'border-primary bg-primary/5 scale-[1.02]'
      )}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
    >
      <div className="flex flex-col items-center gap-6">
        <div
          className={cn(
            'w-24 h-24 rounded-2xl bg-secondary flex items-center justify-center transition-all duration-300',
            isDragging && 'bg-primary/20 scale-110'
          )}
        >
          <Upload
            className={cn(
              'w-12 h-12 text-muted-foreground transition-colors duration-300',
              isDragging && 'text-primary'
            )}
          />
        </div>

        <div className="text-center space-y-2">
          <h3 className="text-xl font-semibold text-foreground">
            Upload Video for Analysis
          </h3>
          <p className="text-sm text-muted-foreground max-w-md">
            Drag and drop your video file here, or click to browse.
            <br />
            <span className="font-mono text-xs">
              Supported formats: MP4, AVI, MOV (max 500MB)
            </span>
          </p>
        </div>

        {(dragError || uploadState.error) && (
          <div className="flex flex-col items-center gap-2 px-4 py-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm max-w-md">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{dragError || uploadState.error}</span>
            </div>
            {uploadState.error?.includes('backend') && (
              <p className="text-xs text-muted-foreground text-center">
                Make sure the Python backend is running at localhost:8000 or configure VITE_API_URL
              </p>
            )}
          </div>
        )}

        <div className="flex gap-4">
          <label>
            <input
              type="file"
              accept=".mp4,.avi,.mov,video/mp4,video/avi,video/quicktime"
              onChange={handleFileSelect}
              className="hidden"
            />
            <Button variant="glow" size="lg" asChild>
              <span className="cursor-pointer">
                <Film className="w-5 h-5 mr-2" />
                Select Video
              </span>
            </Button>
          </label>
        </div>

        <div className="flex items-center gap-8 pt-4 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-risk-low" />
            <span>Low Risk</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-risk-medium" />
            <span>Medium</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-risk-high" />
            <span>High</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-risk-critical" />
            <span>Critical</span>
          </div>
        </div>
      </div>
    </div>
  );
};
