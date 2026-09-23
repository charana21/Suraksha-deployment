/**
 * Crowd Analytics Metrics Utilities
 *
 * Production-grade labels and ranges for:
 * - People Count
 * - Density Average
 * - Motion Intensity
 * - Risk Score
 * - Risk Factors
 */

// ============================================================================
// PEOPLE COUNT LABELS
// ============================================================================

export function getPeopleCountLabel(count: number): string {
  if (count <= 30) return 'Light Crowd';
  if (count <= 80) return 'Moderate Crowd';
  if (count <= 150) return 'Heavy Crowd';
  if (count <= 250) return 'Very Dense';
  return 'Extremely Dense';
}

// ============================================================================
// DENSITY LABELS (people per 100x100px area)
// ============================================================================

export function getDensityLabel(density: number): string {
  if (density <= 1.5) return 'Very Light';
  if (density <= 3.0) return 'Light';
  if (density <= 6.0) return 'Moderate';
  if (density <= 10.0) return 'Dense';
  return 'Extremely Dense';
}

export type DensityLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'VERY HIGH';

export function getDensityLevel(density: number): DensityLevel {
  if (density <= 3.0) return 'LOW';
  if (density <= 6.0) return 'MODERATE';
  if (density <= 10.0) return 'HIGH';
  return 'VERY HIGH';
}

// ============================================================================
// MOTION INTENSITY LABELS (px/frame)
// ============================================================================

export type MotionLevel = 'STATIC' | 'SLOW' | 'NORMAL' | 'FAST' | 'RUNNING';

export function getMotionLevel(intensity: number): MotionLevel {
  if (intensity < 0.5) return 'STATIC';
  if (intensity < 2.0) return 'SLOW';
  if (intensity < 4.0) return 'NORMAL';
  if (intensity < 6.0) return 'FAST';
  return 'RUNNING';
}

export function getMotionDescription(level: MotionLevel): string {
  switch (level) {
    case 'STATIC': return '(no significant movement)';
    case 'SLOW': return '(slow walking, standing shuffles)';
    case 'NORMAL': return '(normal walking pace)';
    case 'FAST': return '(brisk walking, light jogging)';
    case 'RUNNING': return '(running, rushing movement)';
    default: return '(unknown)';
  }
}

export function getMotionLabel(motionIntensity: number): string {
  // Mapping based on new levels for backward compatibility if needed, 
  // or just return the level string itself if that's what's preferred.
  // The user explicitly wants "STATIC", "SLOW", etc. displayed.
  return getMotionLevel(motionIntensity);
}

// ============================================================================
// RISK SCORE LABELS (0 - 100)
// ============================================================================

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export function getRiskLevel(riskScore: number): RiskLevel {
  if (riskScore <= 30) return 'LOW';
  if (riskScore <= 60) return 'MEDIUM'; // Updated threshold
  if (riskScore <= 80) return 'HIGH';   // Updated threshold
  return 'CRITICAL';
}

export function getRiskLabel(riskScore: number): string {
  if (riskScore <= 30) return 'Low Risk';
  if (riskScore <= 60) return 'Medium Risk'; // Updated threshold
  if (riskScore <= 80) return 'High Risk';   // Updated threshold
  return 'CRITICAL RISK';
}

// ============================================================================
// RISK FACTORS LABELS
// ============================================================================

export interface RiskFactorMapping {
  pattern: RegExp;
  label: string;
  severity: 'info' | 'warning' | 'danger' | 'critical';
}

export const RISK_FACTOR_MAPPINGS: RiskFactorMapping[] = [
  {
    pattern: /stampede|dense.*fast.*compress/i,
    label: '🚨 STAMPEDE RISK',
    severity: 'critical',
  },
  {
    pattern: /crowd compression|compression detected/i,
    label: 'Crowd Compression Detected',
    severity: 'danger',
  },
  {
    pattern: /sudden acceleration/i,
    label: 'Sudden Acceleration',
    severity: 'danger',
  },
  {
    pattern: /fast movement.*dense/i,
    label: 'Fast Movement Detected',
    severity: 'warning',
  },
  {
    pattern: /very high.*density/i,
    label: 'Very High Crowd Density',
    severity: 'danger',
  },
  {
    pattern: /high.*density/i,
    label: 'High Crowd Density',
    severity: 'warning',
  },
  {
    pattern: /static.*crowd|queue/i,
    label: 'Static Queue (Safe)',
    severity: 'info',
  },
];

export function formatRiskFactor(rawFactor: string): {
  label: string;
  severity: 'info' | 'warning' | 'danger' | 'critical';
} {
  // Try to match against known patterns
  for (const mapping of RISK_FACTOR_MAPPINGS) {
    if (mapping.pattern.test(rawFactor)) {
      return {
        label: mapping.label,
        severity: mapping.severity,
      };
    }
  }

  // Default: return cleaned up version
  return {
    label: rawFactor,
    severity: 'warning',
  };
}

// ============================================================================
// FORMATTED DISPLAY VALUES
// ============================================================================

/**
 * Format density value for display
 * Returns the actual density value (not percentage)
 */
export function formatDensity(density: number): string {
  return density.toFixed(2);
}

/**
 * Format motion intensity for display
 * Returns the actual motion value in px/frame
 */
export function formatMotion(motionIntensity: number): string {
  return motionIntensity.toFixed(1);
}

/**
 * Format risk score for display
 * Returns score out of 100
 */
export function formatRiskScore(riskScore: number): string {
  return `${Math.round(riskScore)}/100`;
}

// ============================================================================
// COLOR UTILITIES
// ============================================================================

export function getRiskColor(riskLevel: RiskLevel): string {
  const colors: Record<RiskLevel, string> = {
    LOW: 'text-risk-low',
    MEDIUM: 'text-risk-medium',
    HIGH: 'text-risk-high',
    CRITICAL: 'text-risk-critical',
  };
  return colors[riskLevel];
}

export function getRiskBgColor(riskLevel: RiskLevel): string {
  const colors: Record<RiskLevel, string> = {
    LOW: 'bg-risk-low/10',
    MEDIUM: 'bg-risk-medium/10',
    HIGH: 'bg-risk-high/10',
    CRITICAL: 'bg-risk-critical/10',
  };
  return colors[riskLevel];
}

export function getDensityColor(densityLevel: DensityLevel): string {
  const colors: Record<DensityLevel, string> = {
    LOW: 'text-green-500',
    MODERATE: 'text-yellow-500',
    HIGH: 'text-orange-500',
    'VERY HIGH': 'text-red-500',
  };
  return colors[densityLevel];
}
