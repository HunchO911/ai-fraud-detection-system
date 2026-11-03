import axios from "axios";

// Change this if your Django server runs on a different port
const API = axios.create({
  baseURL: "http://127.0.0.1:8000/api/", // Django backend URL
  headers: {
    "Content-Type": "application/json",
  },
});

// Automatically add token to every request (if available)
API.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default API;