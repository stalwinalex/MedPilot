import React, { useState, useRef, useEffect } from 'react';
import {
  FileUp,
  FileText,
  Image as ImageIcon,
  Camera,
  RotateCcw,
  Check,
  X,
  AlertCircle,
  Loader2,
  Sparkles,
  Info
} from 'lucide-react';
import { getAuthToken } from '../api/client';

export default function TimetableImportModal({ isOpen, onClose, onParsedPreview }) {
  const [activeTab, setActiveTab] = useState('pdf'); // 'pdf', 'image', 'camera'
  const [selectedFile, setSelectedFile] = useState(null);
  const [filePreviewUrl, setFilePreviewUrl] = useState(null);
  const [isDragging, setIsDragging] = useState(false);

  // AI Agent API Key
  const [apiKey, setApiKey] = useState(() => localStorage.getItem('gemini_api_key') || '');
  const [showApiKeyInput, setShowApiKeyInput] = useState(false);

  // Camera State
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const [cameraActive, setCameraActive] = useState(false);
  const [capturedBlob, setCapturedBlob] = useState(null);
  const [cameraError, setCameraError] = useState('');

  // Processing State
  const [processing, setProcessing] = useState(false);
  const [progressMsg, setProgressMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    if (!isOpen) {
      stopCamera();
      resetState();
    }
  }, [isOpen]);

  useEffect(() => {
    if (activeTab === 'camera' && isOpen && !capturedBlob) {
      startCamera();
    } else {
      stopCamera();
    }
  }, [activeTab, isOpen, capturedBlob]);

  function resetState() {
    setSelectedFile(null);
    if (filePreviewUrl) URL.revokeObjectURL(filePreviewUrl);
    setFilePreviewUrl(null);
    setCapturedBlob(null);
    setCameraError('');
    setErrorMsg('');
    setProcessing(false);
    setProgressMsg('');
  }

  // Camera Handlers
  async function startCamera() {
    setCameraError('');
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('Camera access is not supported by your browser environment.');
      }
      const constraints = {
        video: {
          facingMode: { ideal: 'environment' },
          width: { ideal: 1920 },
          height: { ideal: 1080 }
        }
      };
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
      }
      setCameraActive(true);
    } catch (err) {
      console.warn('Camera initiation failed:', err);
      setCameraActive(false);
      setCameraError('Camera unavailable or permission denied. Upload a photo instead.');
    }
  }

  function stopCamera() {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    setCameraActive(false);
  }

  function handleCapturePhoto() {
    if (!videoRef.current || !canvasRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob((blob) => {
      if (blob) {
        setCapturedBlob(blob);
        const preview = URL.createObjectURL(blob);
        setFilePreviewUrl(preview);
        stopCamera();
      }
    }, 'image/jpeg', 0.92);
  }

  function handleRetakePhoto() {
    if (filePreviewUrl) URL.revokeObjectURL(filePreviewUrl);
    setFilePreviewUrl(null);
    setCapturedBlob(null);
    startCamera();
  }

  // File Drag & Drop / Input
  function handleFileSelect(file) {
    if (!file) return;
    setErrorMsg('');
    const ext = file.name.split('.').pop().toLowerCase();
    const validExts = activeTab === 'pdf' ? ['pdf'] : ['png', 'jpg', 'jpeg', 'webp'];

    if (!validExts.includes(ext)) {
      setErrorMsg(`Invalid file type. Please select a ${activeTab === 'pdf' ? 'PDF' : 'JPG/PNG'} document.`);
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      setErrorMsg('File size exceeds 10 MB limit.');
      return;
    }

    setSelectedFile(file);
    if (activeTab === 'image') {
      const url = URL.createObjectURL(file);
      setFilePreviewUrl(url);
    }
  }

  async function handleStartParsing() {
    setErrorMsg('');
    const fileToUpload = activeTab === 'camera' ? capturedBlob : selectedFile;

    if (!fileToUpload) {
      setErrorMsg('Please select or capture a timetable first.');
      return;
    }

    setProcessing(true);
    setProgressMsg('Uploading & analyzing timetable schedule...');

    try {
      const formData = new FormData();
      if (activeTab === 'camera') {
        formData.append('file', fileToUpload, 'captured_timetable.jpg');
      } else {
        formData.append('file', fileToUpload);
      }

      if (apiKey.trim()) {
        localStorage.setItem('gemini_api_key', apiKey.trim());
        formData.append('gemini_api_key', apiKey.trim());
      }

      const token = getAuthToken();
      const headers = {};
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const res = await fetch('/api/timetable/import/parse', {
        method: 'POST',
        headers,
        body: formData
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Upload failed with status ${res.status}`);
      }

      const parsedData = await res.json();
      setProgressMsg('Extracted successfully! Opening review...');

      setTimeout(() => {
        setProcessing(false);
        onClose();
        if (onParsedPreview) {
          onParsedPreview(parsedData);
        }
      }, 500);
    } catch (err) {
      setErrorMsg(err.message || 'Could not parse timetable. Try another image or PDF.');
      setProcessing(false);
    }
  }

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white border border-[#E7EAF0] rounded-3xl w-full max-w-xl shadow-float overflow-hidden flex flex-col animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="p-5 border-b border-[#E7EAF0] flex items-center justify-between bg-slate-50/60">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-[#CFEDE7] rounded-xl text-[#1A4B43]">
              <FileUp className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-800 flex items-center gap-2">
                Import Timetable
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[#CFEDE7] text-[#1A4B43]">
                  AI Vision Powered
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                Extract your medical college weekly schedule from PDF, photo, or camera.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={processing}
            className="p-1.5 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Selection */}
        <div className="grid grid-cols-3 border-b border-[#E7EAF0] bg-slate-50 text-xs font-semibold">
          <button
            onClick={() => { setActiveTab('pdf'); resetState(); }}
            disabled={processing}
            className={`py-3 flex items-center justify-center gap-2 border-b-2 transition-all cursor-pointer ${
              activeTab === 'pdf'
                ? 'border-[#72C9BE] text-[#1A4B43] bg-white'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <FileText className="w-4 h-4" />
            <span>Upload PDF</span>
          </button>

          <button
            onClick={() => { setActiveTab('image'); resetState(); }}
            disabled={processing}
            className={`py-3 flex items-center justify-center gap-2 border-b-2 transition-all cursor-pointer ${
              activeTab === 'image'
                ? 'border-[#72C9BE] text-[#1A4B43] bg-white'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <ImageIcon className="w-4 h-4" />
            <span>Upload Photo</span>
          </button>

          <button
            onClick={() => { setActiveTab('camera'); resetState(); }}
            disabled={processing}
            className={`py-3 flex items-center justify-center gap-2 border-b-2 transition-all cursor-pointer ${
              activeTab === 'camera'
                ? 'border-[#72C9BE] text-[#1A4B43] bg-white'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Camera className="w-4 h-4" />
            <span>Take Photo</span>
          </button>
        </div>

        {/* Tab Content */}
        <div className="p-6 space-y-4">
          {errorMsg && (
            <div className="p-3.5 rounded-xl text-xs bg-rose-50 border border-rose-200 text-rose-700 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* TAB 1: UPLOAD PDF */}
          {activeTab === 'pdf' && (
            <div
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setIsDragging(false);
                if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                  handleFileSelect(e.dataTransfer.files[0]);
                }
              }}
              className={`border-2 border-dashed rounded-2xl p-8 text-center transition-all ${
                isDragging
                  ? 'border-[#72C9BE] bg-[#CFEDE7]/20'
                  : selectedFile
                  ? 'border-[#72C9BE] bg-[#CFEDE7]/10'
                  : 'border-[#E7EAF0] bg-slate-50/50 hover:border-slate-300'
              }`}
            >
              <input
                type="file"
                id="pdf-upload-input"
                accept=".pdf,application/pdf"
                onChange={(e) => handleFileSelect(e.target.files[0])}
                className="hidden"
              />

              <label htmlFor="pdf-upload-input" className="cursor-pointer block space-y-3">
                <div className="w-12 h-12 mx-auto rounded-2xl bg-[#CFEDE7] text-[#1A4B43] flex items-center justify-center">
                  <FileText className="w-6 h-6" />
                </div>
                {selectedFile ? (
                  <div>
                    <p className="text-sm font-semibold text-[#1A4B43]">{selectedFile.name}</p>
                    <p className="text-xs text-slate-400 mt-0.5">
                      {(selectedFile.size / 1024).toFixed(1)} KB &bull; Click to change PDF
                    </p>
                  </div>
                ) : (
                  <div>
                    <p className="text-sm font-semibold text-slate-700">Click to browse or drag & drop PDF</p>
                    <p className="text-xs text-slate-400 mt-1">Supports college timetable PDFs up to 10MB</p>
                  </div>
                )}
              </label>
            </div>
          )}

          {/* TAB 2: UPLOAD IMAGE */}
          {activeTab === 'image' && (
            <div
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setIsDragging(false);
                if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                  handleFileSelect(e.dataTransfer.files[0]);
                }
              }}
              className={`border-2 border-dashed rounded-2xl p-6 text-center transition-all ${
                isDragging
                  ? 'border-[#72C9BE] bg-[#CFEDE7]/20'
                  : selectedFile
                  ? 'border-[#72C9BE] bg-[#CFEDE7]/10'
                  : 'border-[#E7EAF0] bg-slate-50/50 hover:border-slate-300'
              }`}
            >
              <input
                type="file"
                id="img-upload-input"
                accept=".png,.jpg,.jpeg,.webp,image/*"
                onChange={(e) => handleFileSelect(e.target.files[0])}
                className="hidden"
              />

              {filePreviewUrl ? (
                <div className="space-y-3">
                  <img
                    src={filePreviewUrl}
                    alt="Timetable Preview"
                    className="max-h-48 mx-auto rounded-xl object-contain border border-[#E7EAF0]"
                  />
                  <label
                    htmlFor="img-upload-input"
                    className="inline-block text-xs font-semibold text-[#1A4B43] hover:underline cursor-pointer"
                  >
                    Change Selected Image
                  </label>
                </div>
              ) : (
                <label htmlFor="img-upload-input" className="cursor-pointer block space-y-3">
                  <div className="w-12 h-12 mx-auto rounded-2xl bg-[#CFEDE7] text-[#1A4B43] flex items-center justify-center">
                    <ImageIcon className="w-6 h-6" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-slate-700">Click to upload photo of timetable</p>
                    <p className="text-xs text-slate-400 mt-1">PNG, JPG, JPEG, WEBP up to 10MB</p>
                  </div>
                </label>
              )}
            </div>
          )}

          {/* TAB 3: TAKE PHOTO (CAMERA) */}
          {activeTab === 'camera' && (
            <div className="space-y-3">
              {cameraError ? (
                <div className="text-center py-8 bg-slate-50 border border-slate-200 rounded-2xl p-6 space-y-3">
                  <Camera className="w-10 h-10 text-slate-400 mx-auto" />
                  <p className="text-xs text-rose-600 font-medium">{cameraError}</p>
                  <button
                    type="button"
                    onClick={() => setActiveTab('image')}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-800 cursor-pointer"
                  >
                    <ImageIcon className="w-4 h-4 text-[#72C9BE]" />
                    Upload Photo Instead
                  </button>
                </div>
              ) : capturedBlob ? (
                <div className="text-center space-y-3">
                  <img
                    src={filePreviewUrl}
                    alt="Captured Timetable"
                    className="max-h-60 mx-auto rounded-2xl border border-slate-200 object-contain shadow-sm"
                  />
                  <div className="flex items-center justify-center gap-3">
                    <button
                      type="button"
                      onClick={handleRetakePhoto}
                      className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 cursor-pointer"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      Retake Photo
                    </button>
                  </div>
                </div>
              ) : (
                <div className="relative rounded-2xl overflow-hidden bg-slate-900 border border-slate-200">
                  <video
                    ref={videoRef}
                    autoPlay
                    playsInline
                    muted
                    className="w-full h-64 object-cover"
                  />
                  {/* Alignment guide */}
                  <div className="absolute inset-4 border-2 border-dashed border-white/60 rounded-xl pointer-events-none flex items-center justify-center">
                    <span className="text-[10px] text-white bg-slate-900/80 px-2 py-0.5 rounded">
                      Align printed timetable inside box
                    </span>
                  </div>

                  <div className="p-3 bg-slate-900/90 flex flex-wrap items-center justify-center gap-2">
                    <button
                      type="button"
                      onClick={handleCapturePhoto}
                      disabled={!cameraActive}
                      className="inline-flex items-center gap-2 px-5 py-2 rounded-xl text-xs font-bold bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 shadow-sm transition-all cursor-pointer disabled:opacity-50"
                    >
                      <Camera className="w-4 h-4 stroke-[2.5]" />
                      <span>Snap Photo</span>
                    </button>

                    <input
                      type="file"
                      id="mobile-camera-capture"
                      accept="image/*"
                      capture="environment"
                      onChange={(e) => {
                        if (e.target.files && e.target.files[0]) {
                          handleFileSelect(e.target.files[0]);
                          setActiveTab('image');
                        }
                      }}
                      className="hidden"
                    />
                    <label
                      htmlFor="mobile-camera-capture"
                      className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white transition-colors cursor-pointer"
                    >
                      <span>Device Camera App</span>
                    </label>
                  </div>
                </div>
              )}
              <canvas ref={canvasRef} className="hidden" />
            </div>
          )}

          {/* AI Multimodal Vision Settings */}
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-3.5 space-y-2 text-xs text-slate-600">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-[#72C9BE] shrink-0" />
                <span className="font-semibold text-slate-800">AI Multimodal Vision Agent</span>
              </div>
              <button
                type="button"
                onClick={() => setShowApiKeyInput(!showApiKeyInput)}
                className="text-[11px] text-[#1A4B43] hover:underline font-semibold cursor-pointer"
              >
                {showApiKeyInput ? 'Hide Key' : apiKey ? '✓ Gemini Key Active' : '+ Optional Gemini Key'}
              </button>
            </div>
            {showApiKeyInput ? (
              <div className="pt-1">
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="Enter Gemini API key (optional - uses server default if empty)"
                  className="w-full py-2 px-3 bg-white border border-[#E7EAF0] rounded-xl text-slate-800 text-xs focus:border-[#72C9BE] focus:outline-none"
                />
              </div>
            ) : (
              <p className="text-[11px] text-slate-500">
                AI Vision Agent extracts days, times, and MBBS subjects with high precision.
              </p>
            )}
          </div>

          {/* Privacy & Extraction Notice */}
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 flex items-start gap-2 text-xs text-slate-500">
            <Info className="w-3.5 h-3.5 text-[#72C9BE] shrink-0 mt-0.5" />
            <span className="text-[11px]">
              Extracted classes will be presented in a review table where you can confirm or adjust before setting.
            </span>
          </div>

          {/* Action Buttons */}
          <div className="pt-2 flex items-center justify-end gap-3 border-t border-[#E7EAF0]">
            <button
              type="button"
              onClick={onClose}
              disabled={processing}
              className="px-4 py-2 rounded-xl text-xs font-medium text-slate-500 hover:text-slate-800 hover:bg-slate-100 cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleStartParsing}
              disabled={processing || (!selectedFile && !capturedBlob)}
              className="px-6 py-2 rounded-xl text-xs font-semibold bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 disabled:opacity-50 transition-colors flex items-center gap-2 shadow-xs cursor-pointer active:scale-95"
            >
              {processing ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>{progressMsg || 'Processing...'}</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>Scan & Set Timetable</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
