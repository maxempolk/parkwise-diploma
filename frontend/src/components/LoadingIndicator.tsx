interface LoadingIndicatorProps {
  label?: string;
}

export function InlineLoader({ label = "Loading" }: LoadingIndicatorProps) {
  return <span aria-label={label} className="inline-loader" role="status"><i /><i /><i /></span>;
}

export function ButtonLoader({ label }: { label: string }) {
  return <><span aria-hidden="true" className="button-loader" />{label}</>;
}

export function PageLoader({ label = "Loading" }: LoadingIndicatorProps) {
  return <main aria-busy="true" className="page"><section className="panel page-loader" role="status"><span><InlineLoader label={label} />{label}</span><div className="skeleton-line heading" /><div className="skeleton-line" /><div className="skeleton-line short" /></section></main>;
}

export function RecordsSkeleton() {
  return <div aria-busy="true" className="records-skeleton" role="status"><span><InlineLoader label="Loading your parking" />Loading your parking</span><div className="skeleton-card" /><div className="skeleton-card" /><div className="skeleton-card" /></div>;
}
