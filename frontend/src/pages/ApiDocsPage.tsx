import { useEffect, useRef } from "react";

export function ApiDocsPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    // Load Swagger UI CSS
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "https://unpkg.com/swagger-ui-dist@5/swagger-ui.css";
    document.head.appendChild(link);

    // Load Swagger UI JS
    const script = document.createElement("script");
    script.src = "https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js";
    script.onload = () => {
      if (containerRef.current && (window as any).SwaggerUIBundle) {
        (window as any).SwaggerUIBundle({
          url: "/api/v1/openapi-search.json",
          domNode: containerRef.current,
          presets: [(window as any).SwaggerUIBundle.presets.apis],
          layout: "BaseLayout",
          deepLinking: true,
          tryItOutEnabled: true,
        });
      }
    };
    document.body.appendChild(script);

    return () => {
      document.head.removeChild(link);
      document.body.removeChild(script);
    };
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">API Documentation</h1>
        <a
          href="/api/v1/openapi-search.json"
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-blue-600 hover:underline"
        >
          OpenAPI Spec (JSON)
        </a>
      </div>
      <div ref={containerRef} className="bg-white rounded-lg border border-gray-200 p-4" />
    </div>
  );
}
