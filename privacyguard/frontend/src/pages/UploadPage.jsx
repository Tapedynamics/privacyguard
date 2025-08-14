import React, { useState } from 'react';
import PropTypes from 'prop-types';
import axios from 'axios';
import { Box, Typography, Button, Input, List, ListItem, Alert } from '@mui/material';

const UploadPage = ({ token }) => {
  const [files, setFiles] = useState([]);
  const [uploadedIds, setUploadedIds] = useState([]);
  const [error, setError] = useState(null);

  const handleFilesChange = (e) => {
    setFiles(Array.from(e.target.files));
  };

  const handleUpload = async () => {
    if (!files.length) return;
    setError(null);
    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));
    try {
      const response = await axios.post('/upload', formData, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data',
        },
      });
      setUploadedIds(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Upload failed');
    }
  };

  return (
    <Box sx={{ p: 2 }}>
      <Typography variant="h5" mb={2}>
        Upload Photos
      </Typography>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      <Input type="file" multiple onChange={handleFilesChange} />
      <Button variant="contained" sx={{ ml: 2 }} onClick={handleUpload}>
        Upload
      </Button>
      {uploadedIds.length > 0 && (
        <Box mt={3}>
          <Typography>Uploaded photo IDs:</Typography>
          <List>
            {uploadedIds.map((id) => (
              <ListItem key={id}>{id}</ListItem>
            ))}
          </List>
        </Box>
      )}
    </Box>
  );
};

UploadPage.propTypes = {
  token: PropTypes.string.isRequired,
};

export default UploadPage;