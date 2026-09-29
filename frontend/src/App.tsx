import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import ChatPage from "@/pages/ChatPage";
import KnowledgePage from "@/pages/KnowledgePage";
import RecallTestPage from "@/pages/RecallTestPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ChatPage />} />
        <Route path="/knowledge" element={<KnowledgePage />} />
        <Route path="/knowledge/recall" element={<RecallTestPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
