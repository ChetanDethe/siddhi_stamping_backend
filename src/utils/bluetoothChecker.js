// utils/bluetoothChecker.js
const { exec } = require('child_process');
const util = require('util');
const execAsync = util.promisify(exec);
const { MAC_SLOTS } = require('../config/dialsConfig');

// Cache to prevent hitting PowerShell too often
let cache = { data: null, lastFetch: 0 };
const CACHE_TTL = 1500; // 1.5 seconds

async function getConnectedDevices() {
  const now = Date.now();
  if (cache.data && (now - cache.lastFetch < CACHE_TTL)) {
    return cache.data;
  }

  try {
    // OPTIMIZATION: Fetch ALL Bluetooth devices in ONE command
    // We look for devices with Status 'OK'
    const command = `powershell -Command "Get-PnpDevice -Class 'Bluetooth' -Status 'OK' | Select-Object -ExpandProperty InstanceId"`;
    const { stdout } = await execAsync(command, { timeout: 4000 });
    
    // Store as a Set for O(1) lookup speed
    const connectedIds = new Set(stdout.toUpperCase().split(/\r?\n/).map(s => s.trim()));
    
    cache = { data: connectedIds, lastFetch: now };
    return connectedIds;
  } catch (error) {
    console.error('Bluetooth check error:', error.message);
    return new Set(); // Return empty set on error so server doesn't crash
  }
}

async function checkAllDialsStatus() {
  // 1. Get all connected IDs once
  const connectedIds = await getConnectedDevices();
  
  // 2. Map against your config
  const results = MAC_SLOTS.map(slot => {
    const cleanMac = slot.mac.replace(/[:\s]/g, '').toUpperCase();
    // Check if the MAC exists in the connected IDs
    // We check if the ID *includes* the MAC because InstanceIds are long strings
    const isConnected = Array.from(connectedIds).some(id => id.includes(cleanMac));

    return {
      mac: slot.mac,
      connected: isConnected
    };
  });

  return {
    summary: {
      connected: results.filter(r => r.connected).length,
      total: results.length
    },
    dials: results
  };
}

// Wrapper for controller compatibility
async function getDialStatusWithCache() {
  return await checkAllDialsStatus();
}

module.exports = { checkAllDialsStatus, getDialStatusWithCache };

