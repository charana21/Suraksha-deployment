import { TopNav } from '@/components/layout/TopNav';
import { FOBMapViewer } from '@/components/fob-map/FOBMapViewer';
import { useZoneAnalytics } from '@/hooks/useZoneAnalytics';

export default function FOBView() {
  const { zones } = useZoneAnalytics({ stationId: 'HYB' });

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <TopNav />

      <main className="flex-1 flex flex-col p-4 gap-6 overflow-y-auto">
        <div className="flex-shrink-0 relative">
          <FOBMapViewer
            zones={zones}
            title="FOB LIVE VIEW"
            className="h-auto min-h-[500px]"
          />
        </div>
      </main>
    </div>
  );
}
