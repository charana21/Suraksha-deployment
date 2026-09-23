import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Wifi, WifiOff, RefreshCw } from 'lucide-react';

interface ConnectionIndicatorProps {
  connectionState: string;
  lastUpdate?: Date | null;
}

/**
 * Connection indicator showing WebSocket connection status
 */
export function ConnectionIndicator({ connectionState, lastUpdate }: ConnectionIndicatorProps) {
  const getVariant = () => {
    switch (connectionState) {
      case 'connected':
        return 'success' as const;
      case 'connecting':
        return 'warning' as const;
      case 'disconnected':
        return 'destructive' as const;
      default:
        return 'secondary' as const;
    }
  };

  const getIcon = () => {
    switch (connectionState) {
      case 'connected':
        return <Wifi className="h-3 w-3" />;
      case 'connecting':
        return <RefreshCw className="h-3 w-3 animate-spin" />;
      case 'disconnected':
        return <WifiOff className="h-3 w-3" />;
      default:
        return null;
    }
  };

  const getLabel = () => {
    switch (connectionState) {
      case 'connected':
        return 'Live';
      case 'connecting':
        return 'Connecting';
      case 'disconnected':
        return 'Offline';
      default:
        return connectionState;
    }
  };

  const getTooltipText = () => {
    if (connectionState === 'connected' && lastUpdate) {
      const timeSinceUpdate = Math.floor((Date.now() - lastUpdate.getTime()) / 1000);
      return `Connected - Last update ${timeSinceUpdate}s ago`;
    }
    return connectionState === 'connected'
      ? 'Connected to WebSocket'
      : connectionState === 'connecting'
      ? 'Reconnecting to server...'
      : 'Disconnected from server';
  };

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge variant={getVariant()} className="flex items-center gap-1 cursor-help">
            {getIcon()}
            {getLabel()}
          </Badge>
        </TooltipTrigger>
        <TooltipContent>
          <p>{getTooltipText()}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
