import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import axios from 'axios';
import {
  Box,
  Typography,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  CircularProgress,
  Button,
} from '@mui/material';
import { Link } from 'react-router-dom';

const DashboardPage = ({ token }) => {
  const [loading, setLoading] = useState(true);
  const [photos, setPhotos] = useState([]);

  useEffect(() => {
    const fetchPhotos = async () => {
      try {
        const response = await axios.get('/photos', {
          headers: { Authorization: `Bearer ${token}` },
        });
        setPhotos(response.data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchPhotos();
  }, [token]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
        <CircularProgress />
      </Box>
    );
  }
  // Functions to handle exports
  const handleExport = async (type) => {
    try {
      const endpoint = type === 'approved' ? '/export/approved' : '/export/privacy-safe';
      const response = await axios.get(endpoint, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob',
      });
      // Create a link and trigger download
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', type === 'approved' ? 'approved_photos.zip' : 'privacy_safe_photos.zip');
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
    } catch (err) {
      console.error('Export failed', err);
    }
  };

  return (
    <Box sx={{ p: 2 }}>
      <Typography variant="h5" mb={2}>
        Photos
      </Typography>
      <Box sx={{ mb: 2 }}>
        <Button variant="contained" sx={{ mr: 2 }} onClick={() => handleExport('approved')}>
          Export Approved
        </Button>
        <Button variant="contained" color="secondary" onClick={() => handleExport('privacy-safe')}>
          Export Privacy Safe
        </Button>
      </Box>
      <Table>
        <TableHead>
          <TableRow>
            <TableCell>ID</TableCell>
            <TableCell>Filename</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Faces</TableCell>
            <TableCell>Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {photos.map((photo) => (
            <TableRow key={photo.id}>
              <TableCell>{photo.id}</TableCell>
              <TableCell>{photo.filename}</TableCell>
              <TableCell>{photo.status}</TableCell>
              <TableCell>{photo.faces ? photo.faces.length : 0}</TableCell>
              <TableCell>
                <Button
                  variant="outlined"
                  size="small"
                  component={Link}
                  to={`/photos/${photo.id}`}
                >
                  Details
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Box>
  );
};

DashboardPage.propTypes = {
  token: PropTypes.string.isRequired,
};

export default DashboardPage;