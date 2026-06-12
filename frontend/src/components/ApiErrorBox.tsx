import GlassErrorState from './glass/GlassErrorState';

interface ApiErrorBoxProps {
  error: string | null;
}

export default function ApiErrorBox({ error }: ApiErrorBoxProps) {
  if (!error) return null;
  return <GlassErrorState message={friendlyError(error)} />;
}

function friendlyError(error: string) {
  const firstLine = error.split(/\r?\n/).find(Boolean)?.trim() ?? error;
  return firstLine.length > 260 ? `${firstLine.slice(0, 257)}...` : firstLine;
}
