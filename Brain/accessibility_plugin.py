#!/usr/bin/env python3
"""Accessibility Plugin for voice commands and screen reader capabilities."""

import time
from plugin_interface import BrowserPlugin

class AccessibilityPlugin(BrowserPlugin):
    """Plugin implementing Voice Control using Web Speech API inside the browser page."""

    def __init__(self, agent):
        self.agent = agent

    def execute(self, action: str, **kwargs):
        if action == "start_voice_control":
            return self.start_voice_control()
        else:
            return {"error": f"Unknown action: {action}"}

    def start_voice_control(self):
        """Injects Web Speech API voice command listener script into the active browser page."""
        js_code = """
        (() => {
            if (window.__voiceRecognitionInstance) {
                return { success: true, message: "Voice control is already active." };
            }
            
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) {
                return { error: "Web Speech API is not supported in this browser." };
            }
            
            const recognition = new SpeechRecognition();
            recognition.continuous = true;
            recognition.interimResults = false;
            recognition.lang = 'en-US';
            
            recognition.onstart = () => {
                console.log("[AccessibilityVoice] Listening for voice commands...");
                // Add indicator dot in bottom right
                const dot = document.createElement('div');
                dot.id = 'voice-indicator';
                dot.style.position = 'fixed';
                dot.style.bottom = '20px';
                dot.style.right = '20px';
                dot.style.width = '15px';
                dot.style.height = '15px';
                dot.style.borderRadius = '50%';
                dot.style.background = '#ff0000';
                dot.style.boxShadow = '0 0 10px #ff0000';
                dot.style.zIndex = '99999';
                document.body.appendChild(dot);
            };
            
            recognition.onresult = async (event) => {
                const command = event.results[event.results.length - 1][0].transcript.trim().toLowerCase();
                console.log("[AccessibilityVoice] Command recognized: " + command);
                
                // Show command visually on screen
                const overlay = document.createElement('div');
                overlay.innerText = "Voice Command: " + command;
                overlay.style.position = 'fixed';
                overlay.style.bottom = '50px';
                overlay.style.right = '20px';
                overlay.style.background = 'rgba(0,0,0,0.8)';
                overlay.style.color = '#fff';
                overlay.style.padding = '8px 16px';
                overlay.style.borderRadius = '8px';
                overlay.style.zIndex = '99999';
                document.body.appendChild(overlay);
                setTimeout(() => overlay.remove(), 3000);
                
                // Simple parsing inside page context
                if (command.startsWith('scroll down')) {
                    window.scrollBy(0, 400);
                } else if (command.startsWith('scroll up')) {
                    window.scrollBy(0, -400);
                } else if (command.startsWith('click ')) {
                    const text = command.replace('click ', '').trim();
                    // Simple text search click fallback
                    const buttons = Array.from(document.querySelectorAll('button, a, input[type=submit]'));
                    const target = buttons.find(b => b.innerText.toLowerCase().includes(text));
                    if (target) target.click();
                }
            };
            
            recognition.onerror = (e) => {
                console.error("[AccessibilityVoice] Error: " + e.error);
            };
            
            recognition.onend = () => {
                console.log("[AccessibilityVoice] Voice recognition ended.");
                const dot = document.getElementById('voice-indicator');
                if (dot) dot.remove();
                window.__voiceRecognitionInstance = null;
            };
            
            recognition.start();
            window.__voiceRecognitionInstance = recognition;
            return { success: true, message: "Voice control started successfully." };
        })()
        """
        print("Starting voice control in active page...")
        res = self.agent.bridge.execute("evaluate", code=js_code)
        return res
