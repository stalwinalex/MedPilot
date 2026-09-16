import React, { createContext, useContext, useState, useEffect } from 'react';
import { apiRequest, setAuthToken, getAuthToken } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadUser() {
      const token = getAuthToken();
      if (!token) {
        setLoading(false);
        return;
      }
      try {
        const profile = await apiRequest('/auth/me');
        setUser(profile);
      } catch (err) {
        console.warn('Session expired or invalid:', err);
        setAuthToken(null);
        setUser(null);
      } finally {
        setLoading(false);
      }
    }

    loadUser();

    const handleUnauthorized = () => setUser(null);
    window.addEventListener('auth:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized);
  }, []);

  const login = async (email, password) => {
    const data = await apiRequest('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    setAuthToken(data.access_token);
    setUser(data.user);
    return data;
  };

  const register = async (formData) => {
    const data = await apiRequest('/auth/register', {
      method: 'POST',
      body: JSON.stringify(formData),
    });
    setAuthToken(data.access_token);
    setUser(data.user);
    return data;
  };

  const logout = () => {
    setAuthToken(null);
    setUser(null);
  };

  const updateProfile = async (updatedFields) => {
    const updated = await apiRequest('/auth/me', {
      method: 'PUT',
      body: JSON.stringify(updatedFields),
    });
    setUser(updated);
    return updated;
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, updateProfile }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
