const { exec } = require('child_process');
const util = require('util');
const execAsync = util.promisify(exec);

async function isConnectedWindows(mac) {
  try {
    // Multiple PowerShell commands to check Bluetooth/HID device status
    const commands = [
      // Method 1: Check PnP devices (most reliable for HID)
      `powershell -Command "Get-PnpDevice | Where-Object { $_.InstanceId -match '${mac.toUpperCase()}' } | Select-Object -ExpandProperty Status"`,
      
      // Method 2: Check Bluetooth devices specifically
      `powershell -Command "Get-PnpDevice | Where-Object { $_.InstanceId -like '*${mac.toUpperCase()}*' -and $_.Class -eq 'Bluetooth' } | Select-Object -ExpandProperty Status"`,
    ];

    for (const command of commands) {
      try {
        const { stdout } = await execAsync(command, { timeout: 5000 });
        const status = stdout.trim().toUpperCase();
        
        // Check for connected/OK status
        if (status.includes('OK') || status.includes('1') || status === 'DEVPRESENT') {
          return true;
        }
      } catch (err) {
        // Try next method if one fails
        continue;
      }
    }
    
    return false;
  } catch (error) {
    console.log(`Error checking MAC ${mac}:`, error.message);
    return false;
  }
}

async function checkAllDialsStatus() {
  const { MAC_SLOTS } = require('../config/dialsConfig');
  
  const results = [];
  // console.log('🔍 Checking dial connection status...');
  
  for (const slot of MAC_SLOTS) {
    // console.log(`Checking ${slot.name} (${slot.mac})...`);
    const connected = await isConnectedWindows(slot.mac);
    results.push({
      name: slot.name,
      mac: slot.mac,
      connected: connected,
      timestamp: new Date().toISOString()
    });
  }
  
  const connectedCount = results.filter(r => r.connected).length;
  const totalCount = results.length;
  
  return {
    summary: {
      connected: connectedCount,
      disconnected: totalCount - connectedCount,
      total: totalCount,
      allConnected: connectedCount === totalCount
    },
    dials: results
  };
}


const cache = new Map();
const CACHE_DURATION = 5 * 1000; // 5 seconds

async function getDialStatusWithCache() {
  const now = Date.now();
  const cacheKey = 'dials_status';
  
  if (cache.has(cacheKey) && (now - cache.get(cacheKey).timestamp) < CACHE_DURATION) {
    console.log('📦 Using cached dial status');
    return cache.get(cacheKey).data;
  }
  
  const freshData = await checkAllDialsStatus();
  cache.set(cacheKey, { data: freshData, timestamp: now });
  
  return freshData;
}

module.exports = { checkAllDialsStatus, getDialStatusWithCache };

