import type { ReactNode } from 'react';

export default function SubtitleReviewLayout({ toolbar, video, editor, bottom }: { toolbar: ReactNode; video: ReactNode; editor: ReactNode; bottom?: ReactNode }) {
  return <div className="grid min-w-0 gap-5"><div>{toolbar}</div><div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-5 min-[900px]:grid-cols-[minmax(320px,0.42fr)_minmax(0,0.58fr)]"><div className="min-w-0">{video}</div><div className="min-w-0">{editor}</div></div>{bottom}</div>;
}
