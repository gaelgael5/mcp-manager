import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const queryClient = new QueryClient();

function Placeholder({ title }: { title: string }) {
  return <div className="p-8"><h1 className="text-2xl font-bold">{title}</h1><p className="text-gray-500 mt-2">Coming soon...</p></div>;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Placeholder title="Dashboard" />} />
          <Route path="/services" element={<Placeholder title="Services" />} />
          <Route path="/services/:id" element={<Placeholder title="Service Detail" />} />
          <Route path="/targets" element={<Placeholder title="Targets" />} />
          <Route path="/sync" element={<Placeholder title="Sync" />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
