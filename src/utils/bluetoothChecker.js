

const { exec } = require('child_process');
const { MAC_SLOTS } = require('../config/dialsConfig');

// --- STATE MANAGEMENT ---
// We store the latest status in memory. 
// The API reads this variable instantly (0ms latency).
let globalStatusCache = {
  summary: { connected: 0, total: MAC_SLOTS.length },
  dials: MAC_SLOTS.map(s => ({ mac: s.mac, connected: false }))
};

// Track if the background worker is active
let isPolling = false;

// --- WORKER FUNCTION ---
const updateBluetoothStatus = () => {
  // -NoProfile: Skips loading user settings (Speed boost)
  // -NonInteractive: Prevents hanging
  const command = `powershell -NoProfile -NonInteractive -Command "Get-PnpDevice -Class 'Bluetooth' -Status 'OK' | Select-Object -ExpandProperty InstanceId"`;

  exec(command, { timeout: 5000 }, (error, stdout, stderr) => {
    try {
      // If error (e.g. no bluetooth adapter), assume all disconnected but don't crash
      const output = error ? '' : stdout.toString().toUpperCase();
      const connectedIds = new Set(output.split(/\r?\n/).map(s => s.trim()));

      // Map current results
      const updatedDials = MAC_SLOTS.map(slot => {
        const cleanMac = slot.mac.replace(/[:\s]/g, '').toUpperCase();
        // Check if the device ID string contains our MAC
        const isConnected = Array.from(connectedIds).some(id => id.includes(cleanMac));
        return { mac: slot.mac, connected: isConnected };
      });

      // Update Global Cache
      globalStatusCache = {
        summary: {
          connected: updatedDials.filter(d => d.connected).length,
          total: updatedDials.length
        },
        dials: updatedDials
      };
    } catch (err) {
      console.error('Error parsing Bluetooth data:', err.message);
    } finally {
      // Schedule next update in 2 seconds (Background loop)
      setTimeout(updateBluetoothStatus, 2000);
    }
  });
};

// --- INITIALIZATION ---
// Start the loop once when the file is first required
if (!isPolling) {
  isPolling = true;
  updateBluetoothStatus();
}

// --- EXPORT ---
// This function is now synchronous and INSTANT
async function getDialStatusWithCache() {
  return globalStatusCache;
}

// Keep export compatible with your controller
module.exports = { 
  checkAllDialsStatus: getDialStatusWithCache, 
  getDialStatusWithCache 
};