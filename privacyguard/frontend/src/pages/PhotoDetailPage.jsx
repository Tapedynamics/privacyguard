import React, { useEffect, useState, useRef } from 'react';
import PropTypes from 'prop-types';
import { useParams, Link as RouterLink } from 'react-router-dom';
import axios from 'axios';
import {
  Box,
  Typography,
  Button,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  TextField,
  Select,
  MenuItem,
  Alert,
  Link as MuiLink,
} from '@mui/material';

/**
 * PhotoDetailPage shows a single photo with its detected faces, allowing
 * administrators to assign names to faces, update consent status and
 * generate/view a blurred version where non‑approved faces are obfuscated.
 */
const PhotoDetailPage = ({ token }) => {
  const { id } = useParams();
  const photoId = parseInt(id, 10);
  const [photo, setPhoto] = useState(null);
  const [originalUrl, setOriginalUrl] = useState('');
  const [blurredUrl, setBlurredUrl] = useState('');
  const [error, setError] = useState(null);
  const imageRef = useRef(null);
  const [boxStyles, setBoxStyles] = useState([]);

  // Fetch photo details and URL on mount
  useEffect(() => {
    const fetchPhoto = async () => {
      try {
        const res = await axios.get(`/photos/${photoId}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        setPhoto(res.data);
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to load photo');
      }
    };
    const fetchUrl = async () => {
      try {
        const res = await axios.get(`/photos/${photoId}/url`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        setOriginalUrl(res.data.url);
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to load image');
      }
    };
    fetchPhoto();
    fetchUrl();
  }, [photoId, token]);

  // Update bounding box overlay styles when image loads or photo changes
  useEffect(() => {
    if (!photo || !imageRef.current) return;
    const handleLoad = () => {
      const img = imageRef.current;
      const w = img.naturalWidth;
      const h = img.naturalHeight;
      const styles = photo.faces.map((face) => {
        const { bbox } = face;
        const left = bbox.left * 100;
        const top = bbox.top * 100;
        const width = bbox.width * 100;
        const height = bbox.height * 100;
        return {
          position: 'absolute',
          border: '2px solid red',
          left: `${left}%`,
          top: `${top}%`,
          width: `${width}%`,
          height: `${height}%`,
          boxSizing: 'border-box',
        };
      });
      setBoxStyles(styles);
    };
    // When imageRef has src updated, call handleLoad once loaded
    const imgEl = imageRef.current;
    if (imgEl.complete) {
      // already loaded
      handleLoad();
    } else {
      imgEl.onload = handleLoad;
    }
  }, [photo]);

  // Handle updates to face name
  const handleNameUpdate = async (faceId, newName) => {
    try {
      await axios.post(
        `/photos/${photoId}/faces/${faceId}/name`,
        { name: newName },
        {
          headers: { Authorization: `Bearer ${token}` },
        },
      );
      // Refresh photo details
      const res = await axios.get(`/photos/${photoId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setPhoto(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update name');
    }
  };

  // Handle updates to consent status
  const handleConsentUpdate = async (faceId, newStatus) => {
    try {
      await axios.post(
        `/photos/${photoId}/faces/${faceId}/consent`,
        { consent_status: newStatus },
        {
          headers: { Authorization: `Bearer ${token}` },
        },
      );
      const res = await axios.get(`/photos/${photoId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setPhoto(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update consent');
    }
  };

  // Queue blur generation
  const handleQueueBlur = async () => {
    setError(null);
    try {
      await axios.post(
        `/photos/${photoId}/blur`,
        {},
        { headers: { Authorization: `Bearer ${token}` } },
      );
      // Optionally inform user that blur is queued
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to queue blur generation');
    }
  };

  // Fetch blurred URL
  const handleFetchBlurred = async () => {
    setError(null);
    try {
      const res = await axios.get(`/photos/${photoId}/blurred_url`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setBlurredUrl(res.data.url);
    } catch (err) {
      setError(err.response?.data?.detail || 'Blurred version not available yet');
    }
  };

  if (!photo) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography>Loading...</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 2 }}>
      <Button variant="outlined" component={RouterLink} to="/dashboard" sx={{ mb: 2 }}>
        Back to Dashboard
      </Button>
      <Typography variant="h5" mb={2}>
        Photo #{photo.id}: {photo.filename}
      </Typography>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      <Box sx={{ position: 'relative', display: 'inline-block', mb: 2 }}>
        {originalUrl && (
          <img
            ref={imageRef}
            src={originalUrl}
            alt="Photo"
            style={{ maxWidth: '100%', height: 'auto' }}
          />
        )}
        {/* Render bounding boxes */}
        {boxStyles.map((style, idx) => (
          <Box key={idx} sx={{ ...style }} />
        ))}
      </Box>
      <Box sx={{ mt: 2 }}>
        <Typography variant="h6">Faces</Typography>
        <Table size="small" sx={{ maxWidth: 600 }}>
          <TableHead>
            <TableRow>
              <TableCell>ID</TableCell>
              <TableCell>Name</TableCell>
              <TableCell>Consent</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {photo.faces.map((face) => (
              <TableRow key={face.id}>
                <TableCell>{face.id}</TableCell>
                <TableCell>
                  {face.name ? (
                    face.name
                  ) : (
                    <TextField
                      size="small"
                      placeholder="Enter name"
                      onBlur={(e) => {
                        const val = e.target.value.trim();
                        if (val) handleNameUpdate(face.id, val);
                      }}
                    />
                  )}
                </TableCell>
                <TableCell>
                  <Select
                    value={face.consent_status}
                    size="small"
                    onChange={(e) => handleConsentUpdate(face.id, e.target.value)}
                  >
                    <MenuItem value="pending">Pending</MenuItem>
                    <MenuItem value="approved">Approved</MenuItem>
                    <MenuItem value="rejected">Rejected</MenuItem>
                  </Select>
                </TableCell>
                <TableCell></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Box>
      <Box sx={{ mt: 3 }}>
        <Button variant="contained" onClick={handleQueueBlur} sx={{ mr: 2 }}>
          Queue Blur Generation
        </Button>
        <Button variant="outlined" onClick={handleFetchBlurred} sx={{ mr: 2 }}>
          Show Blurred Version
        </Button>
        {blurredUrl && (
          <MuiLink href={blurredUrl} target="_blank" rel="noopener" sx={{ mr: 2 }}>
            Open Blurred Image
          </MuiLink>
        )}
      </Box>
    </Box>
  );
};

PhotoDetailPage.propTypes = {
  token: PropTypes.string.isRequired,
};

export default PhotoDetailPage;