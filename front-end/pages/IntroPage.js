import React, { useState, useEffect } from 'react';

export default function ClassroomBackground() {
  const [imageUrl, setImageUrl] = useState('');
  const [detentionSlipUrl, setDetentionSlipUrl] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    const loadImages = async () => {
      try {
        // Load classroom background
        const bgData = await window.fs.readFile('blurry_classroom.png');
        const bgBlob = new Blob([bgData], { type: 'blurry_classroom/png' });
        const bgUrl = URL.createObjectURL(bgBlob);
        setImageUrl(bgUrl);

        // Load detention slip
        const slipData = await window.fs.readFile('detention_slip.png');
        const slipBlob = new Blob([slipData], { type: 'detention_slip/png' });
        const slipUrl = URL.createObjectURL(slipBlob);
        setDetentionSlipUrl(slipUrl);
      } catch (error) {
        console.error('Error loading images:', error);
        setError(`Failed to load images: ${error.message}`);
      }
    };
    
    loadImages();
  }, []);

  return (
    <div className="relative w-full h-screen overflow-hidden">
      {/* Background Image */}
      {imageUrl && (
        <div 
          className="absolute inset-0 bg-cover bg-center"
          style={{
            backgroundImage: `url(${imageUrl})`,
          }}
        />
      )}
      
      {/* Error message */}
      {error && (
        <div className="absolute top-4 left-1/2 transform -translate-x-1/2 bg-red-500 text-white px-6 py-3 rounded-lg z-20">
          {error}
        </div>
      )}
      
      {/* Detention Slip Overlay */}
      <div className="relative z-10 flex items-center justify-center h-full p-8">
        {detentionSlipUrl && (
          <img 
            src={detentionSlipUrl} 
            alt="Detention Slip" 
            className="max-w-4xl w-full h-auto shadow-2xl"
          />
        )}
        {!detentionSlipUrl && !error && (
          <div className="text-white text-xl">Loading images...</div>
        )}
      </div>
    </div>
  );
}