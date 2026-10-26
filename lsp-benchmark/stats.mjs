// Statistics and formatting shared by the analysis scripts.

export const median = (xs) => {
    const s = [...xs].sort((a, b) => a - b);
    const mid = Math.floor(s.length / 2);
    return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
};

export const percentile = (xs, p) => {
    const s = [...xs].sort((a, b) => a - b);
    return s[Math.min(s.length - 1, Math.ceil(p * s.length) - 1)];
};

/** (slowest - fastest) / reported: how much a statistic varies between processes. */
export const variation = (perProcess, reported) => (Math.max(...perProcess) - Math.min(...perProcess)) / reported;

export const fmt = (ms) => (ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : ms >= 10 ? `${ms.toFixed(0)} ms` : `${ms.toFixed(1)} ms`);
