import React, { useState, useEffect } from 'react';
import {
  Users,
  UserPlus,
  Share2,
  Inbox,
  Check,
  X,
  FileText,
  Download,
  AlertCircle,
  Clock,
  Sparkles,
  Shield,
  Search,
  ExternalLink
} from 'lucide-react';
import { apiRequest } from '../api/client';

export default function FriendsPage() {
  const [activeTab, setActiveTab] = useState('circle'); // 'circle', 'requests', 'shared_with_me'
  const [friends, setFriends] = useState([]);
  const [requests, setRequests] = useState([]);
  const [sharedItems, setSharedItems] = useState([]);
  const [myResources, setMyResources] = useState([]);
  const [loading, setLoading] = useState(true);

  // New Request Form
  const [recipientEmail, setRecipientEmail] = useState('');
  const [sendingRequest, setSendingRequest] = useState(false);
  const [requestMsg, setRequestMsg] = useState({ type: '', text: '' });

  // Share Modal
  const [showShareModal, setShowShareModal] = useState(false);
  const [selectedFriendId, setSelectedFriendId] = useState('');
  const [selectedResourceId, setSelectedResourceId] = useState('');
  const [sharingLoading, setSharingLoading] = useState(false);
  const [shareMsg, setShareMsg] = useState({ type: '', text: '' });

  useEffect(() => {
    loadAllData();
  }, []);

  async function loadAllData() {
    setLoading(true);
    try {
      const [fData, rData, sData, mData] = await Promise.all([
        apiRequest('/friends/').catch(() => []),
        apiRequest('/friends/requests').catch(() => []),
        apiRequest('/friends/shared-with-me').catch(() => []),
        apiRequest('/resources/').catch(() => []),
      ]);
      setFriends(fData || []);
      setRequests(rData || []);
      setSharedItems(sData || []);
      setMyResources(mData || []);
    } catch (err) {
      console.error('Failed to load friends data:', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleSendRequest(e) {
    e.preventDefault();
    if (!recipientEmail.trim()) return;
    setSendingRequest(true);
    setRequestMsg({ type: '', text: '' });
    try {
      const res = await apiRequest('/friends/requests', {
        method: 'POST',
        body: JSON.stringify({ recipient_email: recipientEmail.trim() }),
      });
      setRequestMsg({ type: 'success', text: res.message || 'Friend request sent successfully!' });
      setRecipientEmail('');
    } catch (err) {
      setRequestMsg({ type: 'error', text: err.message || 'Could not send request' });
    } finally {
      setSendingRequest(false);
    }
  }

  async function handleRespondRequest(requestId, action) {
    try {
      await apiRequest(`/friends/requests/${requestId}/respond?action=${action}`, {
        method: 'POST',
      });
      setRequests((prev) => prev.filter((r) => r.id !== requestId));
      if (action === 'accept') {
        const fData = await apiRequest('/friends/');
        setFriends(fData || []);
      }
    } catch (err) {
      alert(err.message || `Failed to ${action} request`);
    }
  }

  async function handleShareResource(e) {
    e.preventDefault();
    if (!selectedFriendId || !selectedResourceId) {
      setShareMsg({ type: 'error', text: 'Please select both a peer and a resource.' });
      return;
    }
    setSharingLoading(true);
    setShareMsg({ type: '', text: '' });
    try {
      const res = await apiRequest('/friends/share', {
        method: 'POST',
        body: JSON.stringify({
          resource_id: selectedResourceId,
          recipient_user_id: selectedFriendId,
          permission: 'view',
        }),
      });
      setShareMsg({ type: 'success', text: res.message || 'Resource shared!' });
      setTimeout(() => {
        setShowShareModal(false);
        setShareMsg({ type: '', text: '' });
      }, 1200);
    } catch (err) {
      setShareMsg({ type: 'error', text: err.message || 'Failed to share resource' });
    } finally {
      setSharingLoading(false);
    }
  }

  async function handleDownloadPdf(resourceId, title) {
    try {
      const blob = await apiRequest(`/resources/${resourceId}/pdf`);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${title.replace(/\s+/g, '_')}_MedPilot.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      alert('PDF generation/download failed: ' + err.message);
    }
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 space-y-6 pb-24">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#E7EAF0] pb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2.5">
            <span className="p-2 rounded-xl bg-[#CFEDE7] text-[#1A4B43]">
              <Users className="w-5 h-5" />
            </span>
            <span>Study Circle & Resource Sharing</span>
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Private, student-to-student academic collaboration. Share study notes, PYQ analyses, and flashcards with your batchmates.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              if (friends.length === 0) {
                alert('You need to add study circle friends before you can share resources.');
                return;
              }
              setShowShareModal(true);
            }}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 shadow-sm transition-all cursor-pointer active:scale-95"
          >
            <Share2 className="w-4 h-4" />
            <span>Share a Resource</span>
          </button>
        </div>
      </div>

      {/* Security & Privacy Banner */}
      <div className="bg-slate-50 border border-slate-200 rounded-2xl p-4 flex items-start gap-3 text-xs text-slate-600">
        <Shield className="w-4 h-4 text-[#72C9BE] shrink-0 mt-0.5" />
        <div>
          <span className="font-semibold text-slate-800">Private & Safe Sharing: </span>
          MedPilot is NOT a public social network. Resources can only be exchanged between mutually accepted student peers. Your academic notes and attendance data remain completely private.
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center border-b border-[#E7EAF0] gap-2">
        <button
          onClick={() => setActiveTab('circle')}
          className={`px-4 py-3 text-xs font-bold uppercase tracking-wider border-b-2 transition-all flex items-center gap-2 cursor-pointer ${
            activeTab === 'circle'
              ? 'border-[#72C9BE] text-[#1A4B43]'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          <Users className="w-4 h-4" />
          <span>My Circle ({friends.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('requests')}
          className={`px-4 py-3 text-xs font-bold uppercase tracking-wider border-b-2 transition-all flex items-center gap-2 cursor-pointer ${
            activeTab === 'requests'
              ? 'border-[#72C9BE] text-[#1A4B43]'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          <UserPlus className="w-4 h-4" />
          <span>Requests</span>
          {requests.length > 0 && (
            <span className="px-1.5 py-0.5 rounded-full text-[10px] bg-rose-500 text-white font-bold">
              {requests.length}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab('shared_with_me')}
          className={`px-4 py-3 text-xs font-bold uppercase tracking-wider border-b-2 transition-all flex items-center gap-2 cursor-pointer ${
            activeTab === 'shared_with_me'
              ? 'border-[#72C9BE] text-[#1A4B43]'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          <Inbox className="w-4 h-4" />
          <span>Shared With Me ({sharedItems.length})</span>
        </button>
      </div>

      {/* TAB 1: MY CIRCLE */}
      {activeTab === 'circle' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Friends List (2 cols) */}
          <div className="lg:col-span-2 space-y-4">
            <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
              <span>Connected MBBS Batchmates</span>
              <span className="text-[#1A4B43] font-mono font-semibold">({friends.length})</span>
            </h2>

            {loading ? (
              <div className="text-center py-12 text-slate-400 text-xs">Loading peers...</div>
            ) : friends.length === 0 ? (
              <div className="bg-white border border-dashed border-[#E7EAF0] rounded-2xl p-10 text-center shadow-card">
                <Users className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                <h3 className="text-sm font-bold text-slate-700">No peers in your circle yet</h3>
                <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
                  Add batchmates from your medical college using their registered email to exchange notes and study decks.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {friends.map((friend) => (
                  <div
                    key={friend.id}
                    className="bg-white border border-[#E7EAF0] rounded-2xl p-4 flex items-center justify-between hover:border-slate-300 transition-all shadow-card"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-[#CFEDE7] text-[#1A4B43] font-bold flex items-center justify-center text-sm shadow-xs">
                        {friend.full_name?.charAt(0) || 'M'}
                      </div>
                      <div className="overflow-hidden">
                        <p className="text-sm font-semibold text-slate-800 truncate">{friend.full_name}</p>
                        <p className="text-xs text-slate-400 truncate">{friend.email}</p>
                        <p className="text-[11px] text-[#1A4B43] font-medium truncate mt-0.5">{friend.college || 'Medical College'}</p>
                      </div>
                    </div>
                    <button
                      onClick={() => {
                        setSelectedFriendId(friend.id);
                        setShowShareModal(true);
                      }}
                      title="Share a resource with this friend"
                      className="p-2 rounded-xl text-slate-400 hover:text-[#1A4B43] hover:bg-slate-50 transition-colors cursor-pointer"
                    >
                      <Share2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Add Friend Box (1 col) */}
          <div className="bg-white border border-[#E7EAF0] rounded-2xl p-5 h-fit space-y-4 shadow-card">
            <div className="flex items-center gap-2 text-slate-800 font-bold text-sm">
              <UserPlus className="w-4 h-4 text-[#72C9BE]" />
              <span>Invite a Batchmate</span>
            </div>
            <p className="text-xs text-slate-500 leading-relaxed">
              Enter the email address of a fellow MBBS student registered on MedPilot to send them an invitation.
            </p>

            <form onSubmit={handleSendRequest} className="space-y-3">
              <div>
                <input
                  type="email"
                  required
                  placeholder="batchmate@medschool.edu"
                  value={recipientEmail}
                  onChange={(e) => setRecipientEmail(e.target.value)}
                  className="w-full bg-slate-50 border border-[#E7EAF0] rounded-xl px-3.5 py-2.5 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:bg-white focus:border-[#72C9BE] transition-colors"
                />
              </div>

              {requestMsg.text && (
                <div
                  className={`p-3 rounded-xl text-xs flex items-center gap-2 ${
                    requestMsg.type === 'success'
                      ? 'bg-[#CFEDE7] text-[#1A4B43] border border-[#72C9BE]'
                      : 'bg-rose-50 text-rose-700 border border-rose-200'
                  }`}
                >
                  <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                  <span>{requestMsg.text}</span>
                </div>
              )}

              <button
                type="submit"
                disabled={sendingRequest || !recipientEmail.trim()}
                className="w-full py-2.5 rounded-xl text-xs font-semibold bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 disabled:opacity-50 transition-colors flex items-center justify-center gap-2 cursor-pointer shadow-xs"
              >
                {sendingRequest ? (
                  <span>Sending Invitation...</span>
                ) : (
                  <>
                    <UserPlus className="w-4 h-4 stroke-[2.5]" />
                    <span>Send Friend Request</span>
                  </>
                )}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* TAB 2: REQUESTS */}
      {activeTab === 'requests' && (
        <div className="space-y-4 max-w-2xl">
          <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
            <span>Pending Friend Requests</span>
            <span className="text-[#1A4B43] font-mono font-semibold">({requests.length})</span>
          </h2>

          {requests.length === 0 ? (
            <div className="bg-white border border-dashed border-[#E7EAF0] rounded-2xl p-10 text-center shadow-card">
              <Inbox className="w-10 h-10 text-slate-300 mx-auto mb-3" />
              <h3 className="text-sm font-bold text-slate-700">No pending invitations</h3>
              <p className="text-xs text-slate-400 mt-1">
                When batchmates send you a connection request, you'll be able to accept or decline here.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {requests.map((req) => (
                <div
                  key={req.id}
                  className="bg-white border border-[#E7EAF0] rounded-2xl p-4 flex items-center justify-between shadow-card"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-[#CFEDE7] text-[#1A4B43] font-bold flex items-center justify-center text-sm shadow-xs">
                      {req.sender?.full_name?.charAt(0) || 'M'}
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-slate-800">{req.sender?.full_name || 'Medical Student'}</p>
                      <p className="text-xs text-slate-400">{req.sender?.email}</p>
                      <p className="text-[11px] text-[#1A4B43] font-medium mt-0.5">{req.sender?.college || 'Medical College'}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleRespondRequest(req.id, 'accept')}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 shadow-xs transition-colors cursor-pointer"
                    >
                      <Check className="w-3.5 h-3.5 stroke-[2.5]" />
                      Accept
                    </button>
                    <button
                      onClick={() => handleRespondRequest(req.id, 'reject')}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-slate-100 hover:bg-rose-50 text-slate-600 hover:text-rose-700 transition-colors cursor-pointer"
                    >
                      <X className="w-3.5 h-3.5" />
                      Decline
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 3: SHARED WITH ME */}
      {activeTab === 'shared_with_me' && (
        <div className="space-y-4">
          <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
            <span>Academic Materials Shared With You</span>
            <span className="text-[#1A4B43] font-mono font-semibold">({sharedItems.length})</span>
          </h2>

          {sharedItems.length === 0 ? (
            <div className="bg-white border border-dashed border-[#E7EAF0] rounded-2xl p-10 text-center shadow-card">
              <Inbox className="w-10 h-10 text-slate-300 mx-auto mb-3" />
              <h3 className="text-sm font-bold text-slate-700">No shared study materials yet</h3>
              <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
                When fellow students in your circle share notes, MCQs, or summaries with you, they will appear here.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {sharedItems.map((item) => (
                <div
                  key={item.shared_id}
                  className="bg-white border border-[#E7EAF0] rounded-2xl p-4 flex flex-col justify-between hover:border-slate-300 transition-all shadow-card space-y-4"
                >
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full bg-[#CFEDE7] text-[#1A4B43]">
                        {item.resource_type || 'Study Notes'}
                      </span>
                      <span className="text-[11px] text-slate-400 flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {new Date(item.created_at).toLocaleDateString()}
                      </span>
                    </div>

                    <h3 className="text-sm font-semibold text-slate-800 line-clamp-2">
                      {item.title}
                    </h3>

                    <p className="text-xs text-slate-500">
                      Shared by <span className="text-[#1A4B43] font-semibold">{item.shared_by}</span>
                    </p>
                  </div>

                  <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
                    <span className="text-[11px] text-slate-400 capitalize">
                      Access: {item.permission}
                    </span>

                    <button
                      onClick={() => handleDownloadPdf(item.resource_id, item.title)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-slate-100 hover:bg-[#CFEDE7] text-slate-700 hover:text-[#1A4B43] transition-colors cursor-pointer"
                    >
                      <Download className="w-3.5 h-3.5" />
                      Download PDF
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* SHARE RESOURCE MODAL */}
      {showShareModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white border border-[#E7EAF0] rounded-2xl w-full max-w-md p-6 space-y-4 shadow-float animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between border-b border-[#E7EAF0] pb-3">
              <h3 className="text-base font-bold text-slate-800 flex items-center gap-2">
                <span className="p-1.5 rounded-lg bg-[#CFEDE7] text-[#1A4B43]">
                  <Share2 className="w-4 h-4" />
                </span>
                <span>Share Academic Resource</span>
              </h3>
              <button
                onClick={() => setShowShareModal(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleShareResource} className="space-y-3.5">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Select Batchmate (From Circle)
                </label>
                <select
                  required
                  value={selectedFriendId}
                  onChange={(e) => setSelectedFriendId(e.target.value)}
                  className="w-full bg-slate-50 border border-[#E7EAF0] rounded-xl px-3.5 py-2.5 text-sm text-slate-800 focus:outline-none focus:bg-white focus:border-[#72C9BE] transition-colors"
                >
                  <option value="">-- Choose a peer --</option>
                  {friends.map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.full_name} ({f.email})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Select Resource to Share
                </label>
                {myResources.length === 0 ? (
                  <p className="text-xs text-amber-800 p-2.5 bg-amber-50 rounded-xl border border-amber-200">
                    You have not generated any resources yet. Create study notes or MCQs in "Resources & PDFs" first.
                  </p>
                ) : (
                  <select
                    required
                    value={selectedResourceId}
                    onChange={(e) => setSelectedResourceId(e.target.value)}
                    className="w-full bg-slate-50 border border-[#E7EAF0] rounded-xl px-3.5 py-2.5 text-sm text-slate-800 focus:outline-none focus:bg-white focus:border-[#72C9BE] transition-colors"
                  >
                    <option value="">-- Choose a resource --</option>
                    {myResources.map((r) => (
                      <option key={r.id} value={r.id}>
                        [{r.resource_type?.toUpperCase()}] {r.title}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              {shareMsg.text && (
                <div
                  className={`p-3 rounded-xl text-xs flex items-center gap-2 ${
                    shareMsg.type === 'success'
                      ? 'bg-[#CFEDE7] text-[#1A4B43] border border-[#72C9BE]'
                      : 'bg-rose-50 text-rose-700 border border-rose-200'
                  }`}
                >
                  <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                  <span>{shareMsg.text}</span>
                </div>
              )}

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-[#E7EAF0]">
                <button
                  type="button"
                  onClick={() => setShowShareModal(false)}
                  className="px-4 py-2 rounded-xl text-xs font-medium text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={sharingLoading || myResources.length === 0}
                  className="px-5 py-2 rounded-xl text-xs font-semibold bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 disabled:opacity-50 transition-colors cursor-pointer shadow-xs"
                >
                  {sharingLoading ? 'Sharing...' : 'Share Resource'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
