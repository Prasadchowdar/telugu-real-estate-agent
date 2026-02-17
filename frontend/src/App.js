import React from "react";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import CallMode from "./components/CallMode";
import "./App.css";

/**
 * Sri Sai Properties — Real-Time Telugu Voice Assistant
 * 
 * Single-page app with real-time voice conversation mode.
 * No push-to-talk — fully hands-free, conversational experience.
 */
function App() {
  return (
    <div className="app">
      <CallMode />
      <ToastContainer
        position="top-center"
        autoClose={3000}
        hideProgressBar={false}
        closeOnClick
        theme="dark"
      />
    </div>
  );
}

export default App;
