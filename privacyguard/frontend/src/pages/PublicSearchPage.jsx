import React, { useState } from 'react';
import axios from 'axios';
import { Box, Typography, Button, Input, List, ListItem, Link as MuiLink, Alert } from '@mui/material';

/**
 * PublicSearchPage consente ai clienti di caricare un selfie e ottenere i link
 * alle foto (a piena risoluzione) in cui appaiono. Non richiede autenticazione.
 */
const PublicSearchPage = () => {
  const [file, setFile] = useState(null);
  const [results, setResults] = useState([]);
  const [error, setError] = useState(null);

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const handleSearch = async () => {
    if (!file) return;
    setError(null);
    const formData = new FormData();
    formData.append('file', file);
    try {
      const response = await axios.post('/client/search', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResults(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Ricerca non riuscita');
    }
  };

  return (
    <Box sx={{ p: 2 }}>
      <Typography variant="h5" mb={2}>
        Trova le tue foto
      </Typography>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      <Input type="file" onChange={handleFileChange} />
      <Button variant="contained" sx={{ ml: 2 }} onClick={handleSearch}>
        Cerca
      </Button>
      {results.length > 0 && (
        <Box mt={3}>
          <Typography>Foto trovate:</Typography>
          <List>
            {results.map((item) => (
              <ListItem key={item.photo_id}>
                <MuiLink href={item.url} target="_blank" rel="noopener">
                  Foto #{item.photo_id}
                </MuiLink>
              </ListItem>
            ))}
          </List>
        </Box>
      )}
    </Box>
  );
};

export default PublicSearchPage;