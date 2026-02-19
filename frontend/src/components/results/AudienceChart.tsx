'use client';

import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

interface AudienceChartProps {
  genders: Record<string, number>;
  ageDistribution: Record<string, number>;
}

// Updated palette for light theme
const GENDER_COLORS = {
  female: '#D95F8F',
  Female: '#D95F8F',
  male:   '#4A6FA5',
  Male:   '#4A6FA5',
  unknown:'#B5BEC8',
};

// Clay gradient for age bars
const AGE_COLORS = [
  '#D07055',
  '#C4714A',
  '#B85C38',
  '#C98C6A',
  '#D4A882',
];

// Light-themed tooltip
const CustomTooltip = ({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ value: number }>;
  label?: string;
}) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-dark-secondary border border-dark-border/60 rounded-lg px-3 py-2 shadow-card">
        <p className="text-light-secondary text-xs">{label}</p>
        <p className="text-ember-warm font-mono font-medium text-sm">
          {payload[0].value.toFixed(1)}%
        </p>
      </div>
    );
  }
  return null;
};

export function AudienceChart({ genders, ageDistribution }: AudienceChartProps) {
  const genderData = Object.entries(genders || {}).map(([key, value]) => ({
    name: key.charAt(0).toUpperCase() + key.slice(1),
    value,
    color: GENDER_COLORS[key as keyof typeof GENDER_COLORS] || '#B5BEC8',
  }));

  const ageData = Object.entries(ageDistribution || {})
    .map(([range, value]) => ({ range, value }))
    .sort((a, b) => {
      const getMinAge = (r: string) => parseInt(r.split('-')[0]) || parseInt(r);
      return getMinAge(a.range) - getMinAge(b.range);
    });

  const hasGenderData = genderData.length > 0 && genderData.some((d) => d.value > 0);
  const hasAgeData = ageData.length > 0 && ageData.some((d) => d.value > 0);

  if (!hasGenderData && !hasAgeData) {
    return (
      <div className="text-center py-5 text-light-tertiary/50 text-sm">
        Sin datos demográficos
      </div>
    );
  }

  return (
    <div className="space-y-3.5">
      <h4 className="text-[10px] font-semibold text-ember-warm/70 uppercase tracking-[0.10em]">
        Demografía de Audiencia
      </h4>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Gender donut */}
        {hasGenderData && (
          <div className="bg-dark-tertiary/40 rounded-lg p-3.5 border border-dark-border/30">
            <h5 className="text-[10px] text-light-tertiary/60 mb-3 uppercase tracking-wider font-mono">
              Género
            </h5>
            <div className="flex items-center gap-3">
              <div className="w-[72px] h-[72px] flex-shrink-0">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={genderData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={20}
                      outerRadius={32}
                      strokeWidth={0}
                    >
                      {genderData.map((entry, i) => (
                        <Cell key={`cell-${i}`} fill={entry.color} />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="flex-1 space-y-1.5">
                {genderData.map((entry) => (
                  <div key={entry.name} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-1.5">
                      <div
                        className="w-2 h-2 rounded-full"
                        style={{ backgroundColor: entry.color }}
                      />
                      <span className="text-light-secondary">{entry.name}</span>
                    </div>
                    <span className="font-mono font-medium text-light-primary tabular-nums">
                      {entry.value.toFixed(1)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Age bars */}
        {hasAgeData && (
          <div className="bg-dark-tertiary/40 rounded-lg p-3.5 border border-dark-border/30">
            <h5 className="text-[10px] text-light-tertiary/60 mb-3 uppercase tracking-wider font-mono">
              Grupos de Edad
            </h5>
            <div className="h-[90px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={ageData} layout="vertical" barCategoryGap={5}>
                  <XAxis type="number" hide domain={[0, 'dataMax']} />
                  <YAxis
                    type="category"
                    dataKey="range"
                    width={36}
                    tick={{ fontSize: 10, fill: '#8B98A7', fontFamily: 'var(--font-dm-mono)' }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    content={<CustomTooltip />}
                    cursor={{ fill: 'rgba(184, 92, 56, 0.05)' }}
                  />
                  <Bar dataKey="value" radius={[0, 3, 3, 0]}>
                    {ageData.map((_, i) => (
                      <Cell key={`cell-${i}`} fill={AGE_COLORS[i % AGE_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
