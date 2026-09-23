import React from 'react';
import { Users, Clock, Layers, Zap, TrendingUp, Shield } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { AnalysisResult, RiskLevel } from '@/types/analysis';
import { formatRiskScore, getRiskColor } from '@/lib/metrics';

interface MetricsPanelProps {
  result: AnalysisResult;
}

export const MetricsPanel: React.FC<MetricsPanelProps> = ({ result }) => {
  const metrics = [

    {
      icon: TrendingUp,
      label: 'Avg Risk Score',
      value: formatRiskScore(result.averageRiskScore),
      subtext: 'Across zones',
      valueClass: getRiskColor(result.maxRiskLevel),
    },
    {
      icon: Shield,
      label: 'Max Risk Level',
      value: result.maxRiskLevel,
      subtext: 'Current status',
      valueClass: getRiskColor(result.maxRiskLevel),
    },
    {
      icon: Layers,
      label: 'Frames Analyzed',
      value: result.frameCount.toLocaleString(),
      subtext: `@ ${result.fps.toFixed(1)} FPS`,
    },
    {
      icon: Clock,
      label: 'Processing Time',
      value: `${result.processingTime.toFixed(1)}s`,
      subtext: 'Duration',
    },
    {
      icon: Zap,
      label: 'Active Alerts',
      value: result.alerts.length.toString(),
      subtext: result.alerts.length > 0 ? 'Action required' : 'All clear',
      valueClass: result.alerts.length > 0 ? 'text-risk-high' : 'text-risk-low',
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 animate-fade-in-up">
      {metrics.map((metric, index) => (
        <div
          key={metric.label}
          className="glass-panel p-4 space-y-3"
          style={{ animationDelay: `${index * 50}ms` }}
        >
          <div className="flex items-center gap-2 text-muted-foreground">
            <metric.icon className="w-4 h-4" />
            <span className="metric-label">{metric.label}</span>
          </div>
          <p className={cn('metric-value', metric.valueClass || 'text-foreground')}>
            {metric.value}
          </p>
          <p className="text-xs text-muted-foreground">{metric.subtext}</p>
        </div>
      ))}
    </div>
  );
};
