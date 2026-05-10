import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import BookPage from './pages/BookPage';
import ImportPage from './pages/ImportPage';
import InsightsPage from './pages/InsightsPage';
import LibraryPage from './pages/LibraryPage';
import SparkPage from './pages/SparkPage';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/spark" replace />} />
        <Route path="/spark" element={<SparkPage />} />
        <Route path="/library" element={<LibraryPage />} />
        <Route path="/books/:bookId" element={<BookPage />} />
        <Route path="/import" element={<ImportPage />} />
        <Route path="/insights" element={<InsightsPage />} />
      </Route>
    </Routes>
  );
}
