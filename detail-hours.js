(function attachHourlyWindow(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.DayglanceHourlyWindow = api;
})(globalThis, function createHourlyWindow() {
  function getHourlyWindow(times, day, isToday, currentHour) {
    const first = times.findIndex(time => time.slice(0, 10) === day);
    if (first < 0) return null;

    const nextDay = times.findIndex((time, index) => index > first && time.slice(0, 10) !== day);
    const dayEnd = nextDay < 0 ? Math.min(first + 24, times.length) : nextDay;
    let start = first;
    let end = Math.min(first + 24, times.length);
    let initialIndex = 8;

    if (isToday) {
      const currentStart = times.findIndex((time, index) => index >= first && time.slice(0, 13) >= currentHour);
      if (currentStart >= 0) start = currentStart;
      end = dayEnd;
      if (end - start <= 6 && nextDay >= 0) end = Math.min(nextDay + 4, times.length);
      initialIndex = 0;
    }

    return {start, end, initialIndex, includesTomorrow: isToday && end > dayEnd};
  }

  return {getHourlyWindow};
});

