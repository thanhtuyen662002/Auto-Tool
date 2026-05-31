interface ApiErrorBoxProps {
  error: string | null;
}

export default function ApiErrorBox({ error }: ApiErrorBoxProps) {
  if (!error) return null;
  return (
    <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
      {error}
    </div>
  );
}
