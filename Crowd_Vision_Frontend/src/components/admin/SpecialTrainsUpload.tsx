import { useState, useRef } from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Upload, FileSpreadsheet, CheckCircle, AlertTriangle, Loader2, Train } from 'lucide-react';
import { calendarApi } from '@/services/calendarApi';
import { TrainUploadResponse } from '@/types/trains';
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

export function SpecialTrainsUpload() {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<TrainUploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
      setResult(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setUploading(true);
    setError(null);
    setResult(null);

    try {
      const response = await calendarApi.uploadSpecialTrainsData(file);
      setResult(response);
      if (response.status !== 'success') {
          setError(response.message || 'Upload failed');
      }
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (err: any) {
      setError(err.message || "Failed to upload file");
    } finally {
      setUploading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" className="gap-2 border-primary/20 hover:border-primary/50 hover:bg-primary/5">
          <Train className="h-4 w-4" />
          Upload Special Trains
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Upload Special Trains Data</DialogTitle>
          <DialogDescription>
            Upload an Excel file to update the special trains list and passenger counts.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          <div className="space-y-4">
            <div className="grid w-full items-center gap-2">
              <Label htmlFor="special-trains-file" className="text-sm font-medium">Select Excel File (.xlsx, .xls)</Label>
              <div 
                className={cn(
                  "border-2 border-dashed rounded-xl p-8 transition-colors flex flex-col items-center justify-center gap-2 cursor-pointer",
                  file ? "border-primary/50 bg-primary/5" : "border-muted-foreground/20 hover:border-primary/30 hover:bg-muted/10"
                )}
                onClick={() => fileInputRef.current?.click()}
              >
                <Input 
                  ref={fileInputRef}
                  id="special-trains-file" 
                  type="file" 
                  accept=".xlsx,.xls"
                  onChange={handleFileChange}
                  disabled={uploading}
                  className="hidden"
                />
                {file ? (
                  <>
                    <FileSpreadsheet className="h-8 w-8 text-primary" />
                    <p className="font-medium text-sm text-foreground text-center break-all px-4">{file.name}</p>
                    <p className="text-xs text-muted-foreground">Click to change</p>
                  </>
                ) : (
                  <>
                    <Upload className="h-8 w-8 text-muted-foreground/50" />
                    <p className="font-medium text-muted-foreground text-sm">Click to browse or drag file here</p>
                    <p className="text-xs text-muted-foreground/70">Required columns: train_number, schedule_date, total_passengers</p>
                  </>
                )}
              </div>
            </div>

            {error && (
              <Alert variant="destructive" className="py-2 px-3">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle className="text-xs">Error</AlertTitle>
                <AlertDescription className="text-xs">{error}</AlertDescription>
              </Alert>
            )}

            {result && result.status === 'success' && (
              <Alert className="border-emerald-500 bg-emerald-500/10 dark:bg-emerald-500/20 py-2 px-3">
                <CheckCircle className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                <AlertTitle className="text-xs text-emerald-700 dark:text-emerald-400">Upload Successful</AlertTitle>
                <AlertDescription className="text-xs text-emerald-600 dark:text-emerald-300 mt-1">
                  <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 mt-1">
                    <span>Processed: <strong>{result.records_processed}</strong></span>
                    <span>Inserted: <strong>{result.records_inserted}</strong></span>
                    <span>Updated: <strong>{result.records_updated}</strong></span>
                  </div>
                </AlertDescription>
              </Alert>
            )}
          </div>
        </div>

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="ghost" onClick={() => setOpen(false)} disabled={uploading}>Cancel</Button>
          <Button 
            variant="ghost" 
            onClick={() => {setFile(null); setResult(null); setError(null);}} 
            disabled={!file || uploading}
          >
            Clear
          </Button>
          <Button 
            onClick={handleUpload} 
            disabled={!file || uploading} 
            className="min-w-[100px]"
          >
            {uploading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Uploading...
              </>
            ) : (
              <>
                <Upload className="mr-2 h-4 w-4" />
                Upload
              </>
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
