import { AlertCircle, AlertTriangle, Info } from 'lucide-react';
import type { StartValidationMessage } from '../../types/startWorkflow';

export default function StartValidationAlert({ messages }: { messages: StartValidationMessage[] }) {
  if (!messages.length) return null;
  return (
    <div className="grid gap-2">
      {messages.map((message) => {
        const Icon = message.tone === 'error' ? AlertCircle : message.tone === 'warning' ? AlertTriangle : Info;
        const className =
          message.tone === 'error'
            ? 'border-rose-300/20 bg-rose-400/10 text-rose-100'
            : message.tone === 'warning'
              ? 'border-amber-300/20 bg-amber-400/10 text-amber-100'
              : 'border-cyan-300/20 bg-cyan-300/10 text-cyan-100';
        return (
          <div className={`flex items-start gap-2 rounded-md border px-3 py-2 text-sm leading-6 ${className}`} key={message.id}>
            <Icon className="mt-1 shrink-0" size={16} />
            <span>{message.message}</span>
          </div>
        );
      })}
    </div>
  );
}
