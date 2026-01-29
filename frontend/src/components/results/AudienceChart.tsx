'use client';

import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

interface AudienceChartProps {
  genders: Record<string, number>;
  ageDistribution: Record<string, number>;
}

const GENDER_COLORS = {
  female: '#ec4899',
  Female: '#ec4899',
  male: '#6366f1',
  Male: '#6366f1',
  unknown: '#6b6b70',
};

const AGE_GRADIENT = [
  '#d4a574', // accent gold
  '#e8c9a8', // gold light
  '#d4a574',
  '#b8895a', // gold dark
  '#d4a574',
];

// Custom tooltip component for dark theme
const CustomTooltip = ({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number }>; label?: string }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-dark-secondary border border-dark-border rounded-lg px-3 py-2 shadow-lg">
        <p className="text-light-secondary text-xs">{label}</p>
        <p className="text-light-primary font-mono font-medium">
          {payload[0].value.toFixed(1)}%
        </p>
      </div>
    );
  }
  return null;
};

export function AudienceChart({ genders, ageDistribution }: AudienceChartProps) {
  // Format gender data for pie chart
  const genderData = Object.entries(genders || {}).map(([key, value]) => ({
    name: key.charAt(0).toUpperCase() + key.slice(1),
    value: value,
    color: GENDER_COLORS[key as keyof typeof GENDER_COLORS] || '#6b6b70',
  }));

  // Format age data for bar chart
  const ageData = Object.entries(ageDistribution || {})
    .map(([range, value]) => ({
      range,
      value: value,
    }))
    .sort((a, b) => {
      // Sort by age range
      const getMinAge = (range: string) => parseInt(range.split('-')[0]) || parseInt(range);
      return getMinAge(a.range) - getMinAge(b.range);
    });

  const hasGenderData = genderData.length > 0 && genderData.some(d => d.value > 0);
  const hasAgeData = ageData.length > 0 && ageData.some(d => d.value > 0);

  if (!hasGenderData && !hasAgeData) {
    return (
      <div className="text-center py-6 text-light-tertiary text-sm">
        Sin datos demográficos de audiencia
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <h4 className="text-sm font-semibold text-light-primary uppercase tracking-wider">
        Demografía de Audiencia
      </h4>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Gender Distribution */}
        {hasGenderData && (
          <div className="bg-dark-tertiary/30 rounded-lg p-4">
            <h5 className="text-xs text-light-tertiary mb-3 uppercase tracking-wider">
              Género
            </h5>
            <div className="flex items-center gap-4">
              <div className="w-20 h-20">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={genderData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={22}
                      outerRadius={36}
                      strokeWidth={0}
                    >
                      {genderData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="flex-1 space-y-2">
                {genderData.map((entry) => (
                  <div key={entry.name} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-2.5 h-2.5 rounded-full"
                        style={{ backgroundColor: entry.color }}
                      />
                      <span className="text-light-secondary">{entry.name}</span>
                    </div>
                    <span className="font-mono font-medium text-light-primary">
                      {entry.value.toFixed(1)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Age Distribution */}
        {hasAgeData && (
          <div className="bg-dark-tertiary/30 rounded-lg p-4">
            <h5 className="text-xs text-light-tertiary mb-3 uppercase tracking-wider">
              Grupos de Edad
            </h5>
            <div className="h-[100px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={ageData} layout="vertical" barCategoryGap={4}>
                  <XAxis
                    type="number"
                    hide
                    domain={[0, 'dataMax']}
                  />
                  <YAxis
                    type="category"
                    dataKey="range"
                    width={40}
                    tick={{ fontSize: 10, fill: '#a1a1a6' }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    content={<CustomTooltip />}
                    cursor={{ fill: 'rgba(212, 165, 116, 0.1)' }}
                  />
                  <Bar
                    dataKey="value"
                    radius={[0, 4, 4, 0]}
                  >
                    {ageData.map((_, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={AGE_GRADIENT[index % AGE_GRADIENT.length]}
                      />
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
