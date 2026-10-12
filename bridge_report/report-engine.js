function makeBridgeReportEngine(data) {
  const polynomial = (c, t) => {
    const evalNested = (a, b, q) => Array.isArray(a)
      ? a.map((v, i) => evalNested(v, b[i], q[i])) : a + t * b + t * t * q;
    return evalNested(c[0], c[1], c[2]);
  };
  function evaluate(station) {
    if (!Number.isFinite(station) || station < data.start || station > data.end)
      throw new Error('Station is outside the bridge.');
    const piece = data.pieces.find(p => station >= p.start && station < p.end) || data.pieces.at(-1);
    const t = (station-piece.start)/(piece.end-piece.start);
    const value = Object.fromEntries(Object.entries(piece.fields).map(([k,c]) => [k,polynomial(c,t)]));
    const road = data.road.filter(r => station >= r.start-1e-9 && station <= r.end+1e-9).at(-1);
    const dx = road ? station-road.start : 0;
    value.roadway = road ? road.z+road.g*dx+road.q*dx*dx : null;
    value.clearance = value.bottom.map(bottom => road ? bottom-value.roadway : null);
    const support = data.supports.find(s => Math.abs(s.station-station)<1e-7) || null;
    const components = support ? support.components : piece.components.map(c => ({kind:c.kind,beam:c.beam,
      xy:polynomial(c.y,t).map((y,i) => [c.x[i],y])}));
    return {...value, station, span:piece.span, support, components};
  }
  function parseStation(raw) {
    const value=String(raw).trim();
    if (/^\d+\+\d{1,2}(?:\.\d+)?$/.test(value)) {
      const [hundreds, feet]=value.split('+').map(Number);
      if (feet>=100) return NaN;
      return 100*hundreds+feet;
    }
    return /^(?:\d+(?:\.\d*)?|\.\d+)$/.test(value) ? Number(value) : NaN;
  }
  function stationLabel(value, digits=2) {
    const factor=10**digits;
    const rounded=Math.round(value*factor)/factor;
    const hundreds=Math.floor(rounded/100);
    return `${hundreds}+${(rounded-hundreds*100).toFixed(digits).padStart(digits?3+digits:2,'0')}`;
  }
  return {evaluate,parseStation,stationLabel};
}
if (typeof module !== 'undefined' && module.exports) module.exports={makeBridgeReportEngine};
