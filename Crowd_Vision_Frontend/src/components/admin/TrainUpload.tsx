import { useState, useRef } from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Upload, FileSpreadsheet, CheckCircle, AlertTriangle, Loader2 } from 'lucide-react';
import { trainsApi } from '@/services/trainsApi';
import { TrainUploadResponse } from '@/types/trains';
import { cn } from "@/lib/utils";

export function TrainUpload() {
  const [file, setFile] = useState<File | null>(null);
  const [replaceDates, setReplaceDates] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<TrainUploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
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
      const response = await trainsApi.uploadTrainSchedule(file, replaceDates);
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
    <div className="w-full">
      <div className="bg-muted/30 p-6 border-b flex items-center gap-4">
        <div className="p-3 bg-primary/10 rounded-xl">
           <FileSpreadsheet className="h-6 w-6 text-primary" />
        </div>
        <div>
           <h2 className="text-xl font-semibold">Upload Train Schedule</h2>
           <p className="text-sm text-muted-foreground">Update the upcoming trains list via Excel file.</p>
        </div>
      </div>
      
      <div className="p-6 space-y-6">
        <div className="space-y-4">
          <div className="grid w-full items-center gap-2">
            <Label htmlFor="train-file" className="text-base font-medium">Select Schedule File</Label>
            <div className={cn(
               "border-2 border-dashed rounded-xl p-8 transition-colors flex flex-col items-center justify-center gap-2 cursor-pointer",
               file ? "border-primary/50 bg-primary/5" : "border-muted-foreground/20 hover:border-primary/30 hover:bg-muted/10"
            )}
            onClick={() => fileInputRef.current?.click()}
            >
               <Input 
                ref={fileInputRef}
                id="train-file" 
                type="file" 
                accept=".xlsx,.xls"
                onChange={handleFileChange}
                disabled={uploading}
                className="hidden"
              />
              {file ? (
                 <>
                    <FileSpreadsheet className="h-8 w-8 text-primary" />
                    <p className="font-medium text-foreground">{file.name}</p>
                    <p className="text-xs text-muted-foreground">Click to change</p>
                 </>
              ) : (
                <>
                   <Upload className="h-8 w-8 text-muted-foreground/50" />
                   <p className="font-medium text-muted-foreground">Click to browse or drag file here</p>
                   <p className="text-xs text-muted-foreground/70">Supports .xlsx and .xls</p>
                </>
              )}
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <Checkbox 
              id="replace-dates" 
              checked={replaceDates} 
              onCheckedChange={(c) => setReplaceDates(c === true)}
              disabled={uploading}
            />
            <Label htmlFor="replace-dates" className="text-sm font-normal text-muted-foreground">
              Replace existing schedules for detected dates
            </Label>
          </div>

          {error && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>Error</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {result && result.status === 'success' && (
            <Alert className="border-emerald-500 bg-emerald-500/10 dark:bg-emerald-500/20">
              <CheckCircle className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
              <AlertTitle className="text-emerald-700 dark:text-emerald-400">Upload Successful</AlertTitle>
              <AlertDescription className="text-emerald-600 dark:text-emerald-300 text-sm mt-1">
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 mt-2">
                  <span>Processed: <strong>{result.records_processed}</strong></span>
                  <span>Inserted: <strong>{result.records_inserted}</strong></span>
                  <span>Updated: <strong>{result.records_updated}</strong></span>
                  <span>Skipped: <strong>{result.records_skipped}</strong></span>
                </div>
                {result.dates_found && result.dates_found.length > 0 && (
                  <div className="mt-2 text-xs opacity-90">
                    Dates: {result.dates_found.join(', ')}
                  </div>
                )}
              </AlertDescription>
            </Alert>
          )}
        </div>
      </div>
      
      <div className="flex flex-col-reverse sm:flex-row justify-end gap-3 p-6 pt-0">
         <Button variant="outline" onClick={() => setFile(null)} disabled={!file || uploading}>Clear</Button>
         <Button 
          onClick={handleUpload} 
          disabled={!file || uploading} 
          className="min-w-[120px]"
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
    </div>
  );
}
