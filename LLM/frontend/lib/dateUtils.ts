/**
 * Utilidades para formateo de fechas
 */

export function formatDistanceToNow(date: Date | string): string {
  const now = new Date();
  const target = typeof date === 'string' ? new Date(date) : date;
  const diffMs = now.getTime() - target.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSecs < 60) {
    return 'hace unos segundos';
  } else if (diffMins < 60) {
    return `hace ${diffMins} ${diffMins === 1 ? 'minuto' : 'minutos'}`;
  } else if (diffHours < 24) {
    return `hace ${diffHours} ${diffHours === 1 ? 'hora' : 'horas'}`;
  } else if (diffDays < 7) {
    return `hace ${diffDays} ${diffDays === 1 ? 'día' : 'días'}`;
  } else {
    return target.toLocaleDateString('es-ES', {
      day: 'numeric',
      month: 'short',
      year: target.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
    });
  }
}

export function formatDate(date: Date | string): string {
  const target = typeof date === 'string' ? new Date(date) : date;
  return target.toLocaleDateString('es-ES', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function isToday(date: Date | string): boolean {
  const target = typeof date === 'string' ? new Date(date) : date;
  const today = new Date();
  return (
    target.getDate() === today.getDate() &&
    target.getMonth() === today.getMonth() &&
    target.getFullYear() === today.getFullYear()
  );
}

export function isYesterday(date: Date | string): boolean {
  const target = typeof date === 'string' ? new Date(date) : date;
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  return (
    target.getDate() === yesterday.getDate() &&
    target.getMonth() === yesterday.getMonth() &&
    target.getFullYear() === yesterday.getFullYear()
  );
}
