import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import BookPage from './pages/BookPage';
import FavoritesPage from './pages/FavoritesPage';
import ImportPage from './pages/ImportPage';
import InsightsPage from './pages/InsightsPage';
import LibraryPage from './pages/LibraryPage';
import SearchPage from './pages/SearchPage';
import SparkPage from './pages/SparkPage';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/spark" replace />} />
        <Route path="/spark" element={<SparkPage />} />
        <Route path="/library" element={<LibraryPage />} />
        <Route path="/books/:bookId" element={<BookPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/favorites" element={<FavoritesPage />} />
        <Route path="/import" element={<ImportPage />} />
        <Route path="/insights" element={<InsightsPage />} />
      </Route>
    </Routes>
  );
}
