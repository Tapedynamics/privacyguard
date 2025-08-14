import React, { useState } from 'react';
import { Routes, Route, useNavigate, Link } from 'react-router-dom';
import { AppBar, Toolbar, Typography, Button, Box } from '@mui/material';

import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import UploadPage from './pages/UploadPage';
import ClientSearchPage from './pages/ClientSearchPage';
import PhotoDetailPage from './pages/PhotoDetailPage';
import PublicSearchPage from './pages/PublicSearchPage';

function App() {
  const navigate = useNavigate();
  const [token, setToken] = useState(localStorage.getItem('token'));

  const handleLogin = (tok) => {
    setToken(tok);
    localStorage.setItem('token', tok);
    navigate('/dashboard');
  };

  const handleLogout = () => {
    setToken(null);
    localStorage.removeItem('token');
    navigate('/');
  };

  if (!token) {
    // Quando l'utente non è autenticato permettiamo di accedere alla pagina di ricerca pubblica
    return (
      <Routes>
        <Route path="/search" element={<PublicSearchPage />} />
        <Route path="*" element={<LoginPage onLogin={handleLogin} />} />
      </Routes>
    );
  }

  return (
    <Box>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            PrivacyGuard Admin
          </Typography>
          <Button color="inherit" component={Link} to="/dashboard">
            Dashboard
          </Button>
          <Button color="inherit" component={Link} to="/upload">
            Upload
          </Button>
          <Button color="inherit" component={Link} to="/client-search">
            Client Search
          </Button>
          <Button color="inherit" component={Link} to="/search">
            Public Search
          </Button>
          <Button color="inherit" onClick={handleLogout}>
            Logout
          </Button>
        </Toolbar>
      </AppBar>
      <Routes>
        <Route path="/dashboard" element={<DashboardPage token={token} />} />
        <Route path="/upload" element={<UploadPage token={token} />} />
        <Route path="/client-search" element={<ClientSearchPage />} />
        <Route path="/photos/:id" element={<PhotoDetailPage token={token} />} />
        <Route path="/search" element={<PublicSearchPage />} />
        <Route path="*" element={<DashboardPage token={token} />} />
      </Routes>
    </Box>
  );
}

export default App;