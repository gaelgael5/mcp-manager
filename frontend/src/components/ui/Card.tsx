interface CardProps {
  children: React.ReactNode;
  title?: React.ReactNode;
  className?: string;
}

export function Card({ children, title, className = "" }: CardProps) {
  return (
    <div className={`rounded-lg border border-gray-200 bg-white shadow-sm ${className}`}>
      {title && <div className="border-b border-gray-200 px-4 py-3 font-medium">{title}</div>}
      <div className="p-4">{children}</div>
    </div>
  );
}
